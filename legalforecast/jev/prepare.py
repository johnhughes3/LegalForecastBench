"""Reusable Luna summaries of the same blinded documents used by other models."""

from __future__ import annotations

import math
import os
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent, AgentRetries
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.live_model_solver import (
    _estimated_cost,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    model_registry_entry_sha256,
)
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    AttemptStateError,
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.release import ForecastExecution

from .packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    request_byte_count,
    require_request_fits,
)
from .summaries import (
    SUMMARY_INSTRUCTIONS,
    SUMMARY_PROMPT_VERSION,
    DocumentSummary,
    SummaryCache,
)

_UNBOUNDED_SUMMARY_BYTES = (1 << 63) - 1


def prepare_summaries(
    execution: ForecastExecution,
    *,
    entry: ModelRegistryEntry,
    cache_path: Path,
    ledger_path: Path,
    ceiling_microusd: int,
) -> dict[str, int]:
    """Summarize each whole document once, persisting progress and spend."""

    if entry.provider != "openai" or entry.model_id != "gpt-5.6-luna":
        raise ValueError(
            "summary preparation requires the frozen GPT-5.6 Luna registry"
        )
    if type(ceiling_microusd) is not int or ceiling_microusd <= 0:
        raise ValueError("ceiling_microusd must be a positive integer")
    cache = SummaryCache.load(cache_path, execution.release.release_digest)
    identity = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "release": execution.release.release_digest,
                "model": model_registry_entry_sha256(entry),
                "prompt": SUMMARY_PROMPT_VERSION,
                "request_byte_budget": JEV_REQUEST_BYTE_BUDGET,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    created = reused = 0
    with SqliteProviderSpendAuthority(
        ledger_path,
        authority_identity_sha256=identity,
        cycle_id=execution.release.release_id,
        provider="openai",
        account="jev-summaries",
        cap_microusd=ceiling_microusd,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=identity,
            max_billable_attempts=1,
            failure_threshold=1,
            failure_window_seconds=86_400,
        ),
    ) as authority:
        for case in execution.release.cases:
            units = tuple(
                u
                for u in execution.release.prediction_units
                if u.case_id == case.case_id
            )
            documents = case_documents(execution, units)
            overhead = request_byte_count(
                case_request(
                    units, documents, summaries={d.document_id: "" for d in documents}
                )
            )
            # Leave room for JSON escaping, and validate the actual assembled
            # request before it can reach Jev. Never truncate a paid summary.
            budget = (JEV_REQUEST_BYTE_BUDGET - overhead) * 4 // (5 * len(documents))
            if budget < 500:
                raise ValueError(
                    f"too many questions/documents for useful summaries: {case.case_id}"
                )
            texts: dict[str, str] = {}
            for document in documents:
                key = ProviderSpendKey(
                    execution.release.release_id,
                    "openai",
                    "jev-summaries",
                    "document_summary",
                    entry.registry_key,
                    document.document_id,
                    "none",
                    1,
                )
                prior = cache.get(
                    case.case_id,
                    document.document_id,
                    document.source_sha256,
                    entry.model_id,
                    _UNBOUNDED_SUMMARY_BYTES,
                )
                if prior is not None:
                    try:
                        lease = authority.adopt_attempt(key, attempt_ordinal=1)
                    except AttemptStateError as exc:
                        raise ValueError(
                            "summary cache has no matching provider ledger attempt: "
                            f"{document.document_id}"
                        ) from exc
                    authority.record_response(
                        lease,
                        input_tokens=prior.input_tokens,
                        output_tokens=prior.output_tokens,
                        actual_microusd=math.ceil(prior.estimated_cost_usd * 1_000_000),
                        response_sha256=str(
                            RAW_BYTES_RAW_SHA256_V1.commit(
                                prior.text.encode("utf-8"),
                                domain=PUBLIC_RUN_RECEIPT_V1,
                            ).digest
                        ),
                    )
                    if len(prior.text.encode("utf-8")) > budget:
                        raise ValueError(
                            "Luna summary exceeds its byte budget: "
                            f"{document.document_id}"
                        )
                    texts[document.document_id] = prior.text
                    reused += 1
                    continue
                prompt = ARTIFACT_CANONICAL_JSON_V1.encode(
                    {
                        "document": dict(document.description),
                        "text": document.text,
                        "maximum_summary_utf8_bytes": budget,
                        "target_words": max(50, budget // 9),
                    }
                ).decode("utf-8")
                if len(prompt.encode("utf-8")) + 8192 > entry.context_limit:
                    raise ValueError(
                        "document exceeds conservative Luna input budget: "
                        f"{document.document_id}"
                    )
                reservation = conservative_reservation_microusd(
                    context_limit=len(prompt.encode("utf-8")) + 8192,
                    max_output_tokens=8192,
                    input_token_price=entry.input_token_price,
                    output_token_price=entry.output_token_price,
                    long_context_surcharge=entry.long_context_surcharge,
                )
                handler = ProviderSpendAttemptHandler(
                    authority=authority,
                    key=key,
                    reservation_microusd=reservation,
                )
                api_key = os.environ.get("OPENAI_API_KEY", "")
                if not api_key:
                    raise ValueError(
                        "OPENAI_API_KEY is required for uncached summaries"
                    )
                agent = Agent(
                    OpenAIResponsesModel(
                        entry.model_id,
                        provider=OpenAIProvider(
                            openai_client=AsyncOpenAI(api_key=api_key, max_retries=0)
                        ),
                    ),
                    output_type=str,
                    instructions=SUMMARY_INSTRUCTIONS,
                    retries=AgentRetries(output=0, tools=0),
                    model_settings=OpenAIResponsesModelSettings(
                        max_tokens=8192,
                        timeout=900,
                        openai_service_tier="flex",
                        openai_reasoning_effort="high",
                    ),
                )

                def call(
                    agent: Agent[None, str] = agent, prompt: str = prompt
                ) -> dict[str, object]:
                    result = agent.run_sync(
                        prompt, usage_limits=UsageLimits(request_limit=1)
                    )
                    usage = result.usage
                    input_tokens = usage.input_tokens
                    output_tokens = usage.output_tokens
                    if (
                        type(input_tokens) is not int
                        or type(output_tokens) is not int
                        or input_tokens < 0
                        or output_tokens < 0
                    ):
                        raise ValueError("Luna token usage is invalid")
                    return {
                        "text": result.output,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost": _estimated_cost(  # pyright: ignore[reportPrivateUsage]
                            entry,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        ),
                    }

                payload = handler.run_attempt(1, call)
                ordinal = handler.durable_attempt_ordinal(1)
                try:
                    text = payload["text"]
                    input_tokens = payload["input_tokens"]
                    output_tokens = payload["output_tokens"]
                    cost = payload["cost"]
                    if (
                        type(text) is not str
                        or type(input_tokens) is not int
                        or type(output_tokens) is not int
                        or type(cost) is not float
                        or input_tokens < 0
                        or output_tokens < 0
                        or cost < 0
                    ):
                        raise ValueError("Luna response payload is invalid")
                    summary = DocumentSummary(
                        document_id=document.document_id,
                        source_sha256=document.source_sha256,
                        text=text,
                        model=entry.model_id,
                        prompt_version=SUMMARY_PROMPT_VERSION,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=cost,
                    )
                except BaseException as exc:
                    handler.record_post_response_failure(
                        ordinal, failure_type=type(exc).__name__
                    )
                    raise
                # Keep paid output even if it is too long: no silent truncation
                # and no second purchase on an automatic retry.
                try:
                    cache.put(case.case_id, summary)
                except BaseException as exc:
                    handler.record_post_response_failure(
                        ordinal, failure_type=type(exc).__name__
                    )
                    raise
                handler.settle_attempt(
                    ordinal,
                    input_tokens=summary.input_tokens,
                    output_tokens=summary.output_tokens,
                    actual_cost_usd=summary.estimated_cost_usd,
                    raw_output=summary.text,
                )
                if len(summary.text.encode("utf-8")) > budget:
                    raise ValueError(
                        f"Luna summary exceeds its byte budget: {document.document_id}"
                    )
                texts[document.document_id] = summary.text
                created += 1
            require_request_fits(case_request(units, documents, summaries=texts))
        spent = authority.snapshot()
    return {
        "created": created,
        "reused": reused,
        "spent_microusd": spent.committed_microusd,
    }
