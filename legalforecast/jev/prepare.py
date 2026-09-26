"""Reusable summaries of the same blinded documents used by other models."""

from __future__ import annotations

import hashlib
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
    AdditionalAttemptPermit,
    AttemptStateError,
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.release import ForecastExecution
from legalforecast.runner.gateway import (
    VERCEL_AI_GATEWAY_BASE_URL,
    gateway_model_profile,
    gateway_request_extra_body,
)

from .packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    request_byte_count,
    require_request_fits,
)
from .summaries import (
    SHORT_SUMMARY_PROMPT_VERSION,
    SUMMARY_INSTRUCTIONS,
    SUMMARY_PROMPT_VERSION,
    DocumentSummary,
    SummaryCache,
)
from .summary_recovery import recover_saved_overrun

_UNBOUNDED_SUMMARY_BYTES = (1 << 63) - 1
_SUMMARY_REQUEST_OUTPUT_TOKENS = 8192
_LUNA_SUMMARY_ENTRY = ("openai", "gpt-5.6-luna")
_GROK_SUMMARY_ENTRY = ("vercel_ai_gateway", "spacexai/grok-4.6")


def _summary_key(
    execution: ForecastExecution,
    entry: ModelRegistryEntry,
    *,
    case_id: str,
    document_id: str,
) -> ProviderSpendKey:
    summary_identity = ARTIFACT_CANONICAL_JSON_V1.encode(
        {"case_id": case_id, "document_id": document_id}
    ).decode("utf-8")
    return ProviderSpendKey(
        execution.release.release_id,
        entry.provider,
        "jev-summaries",
        "document_summary",
        entry.registry_key,
        summary_identity,
        "none",
        1,
    )


def _summary_agent(entry: ModelRegistryEntry, *, api_key: str) -> Agent[None, str]:
    """Build the no-tools summary agent for one frozen summary registry entry."""

    provider = entry.provider
    if (provider, entry.model_id) == _LUNA_SUMMARY_ENTRY:
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
        return agent

    if (provider, entry.model_id) == _GROK_SUMMARY_ENTRY:
        gateway_provider = OpenAIProvider(
            openai_client=AsyncOpenAI(
                api_key=api_key,
                base_url=VERCEL_AI_GATEWAY_BASE_URL,
                max_retries=0,
            )
        )
        agent = Agent(
            OpenAIResponsesModel(
                entry.model_id,
                provider=gateway_provider,
                profile=gateway_model_profile(gateway_provider, entry.model_id),
            ),
            output_type=str,
            instructions=SUMMARY_INSTRUCTIONS,
            retries=AgentRetries(output=0, tools=0),
            model_settings=OpenAIResponsesModelSettings(
                max_tokens=8192,
                timeout=900,
                openai_store=False,
                extra_body=gateway_request_extra_body(entry.model_id),
                openai_reasoning_effort="high",
            ),
        )
        return agent

    raise ValueError(
        "summary preparation requires the frozen GPT-5.6 Luna or Grok 4.6 "
        "Gateway registry"
    )


def prepare_summaries(
    execution: ForecastExecution,
    *,
    entry: ModelRegistryEntry,
    cache_path: Path,
    ledger_path: Path,
    ceiling_microusd: int,
    reconcile_saved_overrun: bool = False,
    summary_profile: str = "standard",
    retry_ambiguous_attempt_id: str | None = None,
) -> dict[str, int]:
    """Summarize each whole document once, persisting progress and spend."""

    if (entry.provider, entry.model_id) not in {
        _LUNA_SUMMARY_ENTRY,
        _GROK_SUMMARY_ENTRY,
    }:
        raise ValueError(
            "summary preparation requires the frozen GPT-5.6 Luna or Grok 4.6 "
            "Gateway registry"
        )
    if type(ceiling_microusd) is not int or ceiling_microusd <= 0:
        raise ValueError("ceiling_microusd must be a positive integer")
    if summary_profile not in {"standard", "short"}:
        raise ValueError("unsupported summary profile")
    prompt_version = (
        SHORT_SUMMARY_PROMPT_VERSION
        if summary_profile == "short"
        else SUMMARY_PROMPT_VERSION
    )
    request_byte_budget = (
        24_000 if summary_profile == "short" else JEV_REQUEST_BYTE_BUDGET
    )
    if reconcile_saved_overrun and summary_profile != "standard":
        raise ValueError(
            "saved-overrun reconciliation applies only to the original standard profile"
        )
    if reconcile_saved_overrun:
        recover_saved_overrun(
            execution,
            entry=entry,
            cache_path=cache_path,
            ledger_path=ledger_path,
            ceiling_microusd=ceiling_microusd,
        )
    summary_label = (
        "Luna" if (entry.provider, entry.model_id) == _LUNA_SUMMARY_ENTRY else "Grok"
    )
    cache = SummaryCache.load(
        cache_path, execution.release.release_digest, prompt_version=prompt_version
    )
    identity = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "release": execution.release.release_digest,
                "model": model_registry_entry_sha256(entry),
                "prompt": prompt_version,
                "request_byte_budget": request_byte_budget,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    created = reused = 0
    with SqliteProviderSpendAuthority(
        ledger_path,
        authority_identity_sha256=identity,
        cycle_id=execution.release.release_id,
        provider=entry.provider,
        account="jev-summaries",
        cap_microusd=ceiling_microusd,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=identity,
            max_billable_attempts=1,
            failure_threshold=1,
            failure_window_seconds=86_400,
        ),
    ) as authority:
        retry_logical_key: str | None = None
        if retry_ambiguous_attempt_id is not None:
            retry_logical_key, replacement_complete = (
                authority.ambiguous_replacement_status(retry_ambiguous_attempt_id)
            )
            found = False
            for prior_case in execution.release.cases:
                prior_units = tuple(
                    unit
                    for unit in execution.release.prediction_units
                    if unit.case_id == prior_case.case_id
                )
                for prior_document in case_documents(execution, prior_units):
                    prior_key = _summary_key(
                        execution,
                        entry,
                        case_id=prior_case.case_id,
                        document_id=prior_document.document_id,
                    )
                    if prior_key.logical_call_key != retry_logical_key:
                        continue
                    found = True
                    cached = cache.get(
                        prior_case.case_id,
                        prior_document.document_id,
                        prior_document.source_sha256,
                        entry.model_id,
                        _UNBOUNDED_SUMMARY_BYTES,
                    )
                    if (cached is not None) != replacement_complete:
                        raise AttemptStateError(
                            "ambiguous retry cache does not match replacement state"
                        )
            if not found:
                raise AttemptStateError(
                    "ambiguous retry attempt does not belong to this summary census"
                )
        for case in execution.release.cases:
            units = tuple(
                u
                for u in execution.release.prediction_units
                if u.case_id == case.case_id
            )
            documents = case_documents(execution, units)
            overhead = request_byte_count(
                case_request(
                    units, documents, summaries={d.document_id: "x" for d in documents}
                )
            )
            # Leave room for JSON escaping, and validate the actual assembled
            # request before it can reach Jev. Never truncate a paid summary.
            budget = (request_byte_budget - overhead) * 4 // (5 * len(documents))
            if budget < 500:
                raise ValueError(
                    f"too many questions/documents for useful summaries: {case.case_id}"
                )
            texts: dict[str, str] = {}
            for document in documents:
                key = _summary_key(
                    execution,
                    entry,
                    case_id=case.case_id,
                    document_id=document.document_id,
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
                        lease = authority.adopt_attempt(key)
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
                    texts[document.document_id] = prior.text
                    reused += 1
                    continue
                prompt = ARTIFACT_CANONICAL_JSON_V1.encode(
                    {
                        "document": dict(document.description),
                        "text": document.text,
                        "maximum_summary_utf8_bytes": budget,
                        "target_words": max(
                            50, budget // (12 if summary_profile == "short" else 9)
                        ),
                        **(
                            {
                                "brevity_instructions": (
                                    "Write a compact summary within the target words "
                                    "and maximum bytes. Compress repetition "
                                    "and quotations; "
                                    "retain each claim, defendant group, "
                                    "material ground "
                                    "and counterargument across the whole document. "
                                    "Do not include a preamble or repeat "
                                    "procedural boilerplate."
                                )
                            }
                            if summary_profile == "short"
                            else {}
                        ),
                    }
                ).decode("utf-8")
                if (
                    len(prompt.encode("utf-8")) + _SUMMARY_REQUEST_OUTPUT_TOKENS
                    > entry.context_limit
                ):
                    raise ValueError(
                        f"document exceeds conservative {summary_label} input budget: "
                        f"{document.document_id}"
                    )
                # The failed Grok run reported more output tokens than the
                # request setting. Reserve against the frozen registry ceiling
                # so accounting follows provider-reported usage safely.
                reservation_output_tokens = (
                    entry.max_output_tokens
                    if (entry.provider, entry.model_id) == _GROK_SUMMARY_ENTRY
                    else _SUMMARY_REQUEST_OUTPUT_TOKENS
                )
                reservation = conservative_reservation_microusd(
                    context_limit=len(prompt.encode("utf-8"))
                    + reservation_output_tokens,
                    max_output_tokens=reservation_output_tokens,
                    input_token_price=entry.input_token_price,
                    output_token_price=entry.output_token_price,
                    long_context_surcharge=entry.long_context_surcharge,
                )
                permit = None
                if key.logical_call_key == retry_logical_key:
                    assert retry_ambiguous_attempt_id is not None
                    permit = AdditionalAttemptPermit(
                        logical_call_key=key.logical_call_key,
                        prompt_sha256=hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                        journal_path_sha256=hashlib.sha256(
                            str(ledger_path.resolve()).encode("utf-8")
                        ).hexdigest(),
                        max_total_attempts=2,
                        reservation_cap_microusd=reservation,
                        acknowledged_ambiguous_attempt_id=retry_ambiguous_attempt_id,
                    )
                handler = ProviderSpendAttemptHandler(
                    authority=authority,
                    key=key,
                    reservation_microusd=reservation,
                    additional_attempt_permit=permit,
                )
                api_key_name = (
                    "OPENAI_API_KEY"
                    if (entry.provider, entry.model_id) == _LUNA_SUMMARY_ENTRY
                    else "AI_GATEWAY_API_KEY"
                )
                api_key = os.environ.get(api_key_name, "")
                if not api_key:
                    raise ValueError(
                        f"{api_key_name} is required for uncached summaries"
                    )
                agent = _summary_agent(entry, api_key=api_key)

                def call(
                    agent: Agent[None, str] = agent, prompt: str = prompt
                ) -> dict[str, object]:
                    # Receive response events while long reasoning requests run;
                    # a buffered response can lose its idle gateway connection.
                    with agent.run_stream_sync(
                        prompt, usage_limits=UsageLimits(request_limit=1)
                    ) as result:
                        summary_text = result.get_output()
                        # EOF alone is not a successful Responses API completion.
                        # Never save partial text or settle missing final usage.
                        details = result.response.provider_details or {}
                        if (
                            result.response.finish_reason != "stop"
                            or details.get("finish_reason") != "completed"
                        ):
                            raise ValueError(
                                "Summary stream ended without a completed response"
                            )
                        usage = result.usage
                    input_tokens = usage.input_tokens
                    output_tokens = usage.output_tokens
                    if (
                        type(input_tokens) is not int
                        or type(output_tokens) is not int
                        or input_tokens <= 0
                        or output_tokens <= 0
                    ):
                        raise ValueError(f"{summary_label} token usage is invalid")
                    return {
                        "text": summary_text,
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
                        raise ValueError(f"{summary_label} response payload is invalid")
                    summary = DocumentSummary(
                        document_id=document.document_id,
                        source_sha256=document.source_sha256,
                        text=text,
                        model=entry.model_id,
                        prompt_version=prompt_version,
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
                texts[document.document_id] = summary.text
                created += 1
            require_request_fits(case_request(units, documents, summaries=texts))
        spent = authority.snapshot()
    return {
        "created": created,
        "reused": reused,
        "spent_microusd": spent.committed_microusd,
    }
