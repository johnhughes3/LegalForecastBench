"""Bounded Luna one-shot comparison over the Jev summary packet."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping
from typing import Protocol, cast
from urllib.request import Request

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, AgentRetries, NativeOutput
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.live_model_solver import (
    LiveModelProviderError,
    LiveModelTransport,
    SolverResponse,
    _estimated_cost,  # pyright: ignore[reportPrivateUsage]
    default_live_model_transport,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.response_verification import verify_provider_response


class _LunaCaseInput(Protocol):
    """Small input surface shared by the Jev dispatcher and comparator."""

    @property
    def request(self) -> Mapping[str, object]: ...

    @property
    def unit_ids(self) -> tuple[str, ...]: ...


class _LunaPrediction(BaseModel):
    """One structured probability returned by the summary comparator."""

    unit_id: str = Field(min_length=1)
    probability_fully_dismissed: float = Field(ge=0.0, le=1.0)


class _LunaEnvelope(BaseModel):
    """The native structured output for one bounded Luna request."""

    predictions: tuple[_LunaPrediction, ...] = Field(min_length=1)


def is_luna_comparator(entry: ModelRegistryEntry) -> bool:
    """Return whether an entry is the bounded Luna summary comparator."""

    return (
        entry.provider == "openai"
        and entry.model_id == "gpt-5.6-luna"
        and entry.jev_input_mode == "luna_summaries"
    )


def _sdk_call(
    body: bytes,
    values: Mapping[str, str],
    entry: ModelRegistryEntry,
) -> Mapping[str, object]:
    """Make exactly one native structured PydanticAI request for Luna."""

    request = json.loads(body)
    if not isinstance(request, dict):
        raise ValueError("Luna comparator request must be an object")
    request = cast(dict[str, object], request)
    raw_state = request.get("state")
    raw_questions = request.get("questions")
    if not isinstance(raw_state, dict) or not isinstance(raw_questions, dict):
        raise ValueError("Luna comparator request must contain state and questions")
    state = cast(dict[str, object], raw_state)
    questions = cast(dict[str, object], raw_questions)
    api_key = values.get("OPENAI_API_KEY", "")
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is required")
    effort = entry.reasoning_effort
    if effort is None:
        raise ValueError("Luna comparator registry must pin reasoning_effort")
    packet: dict[str, object] = {"state": state, "questions": questions}
    prompt = (
        "Use the exact Jev state and case questions below. Return one estimated "
        "probability for every original prediction unit id, with "
        "probability_fully_dismissed between 0 and 1. Do not add rationale or "
        "use tools.\n\n" + ARTIFACT_CANONICAL_JSON_V1.encode(packet).decode("utf-8")
    )
    agent = Agent(
        OpenAIResponsesModel(
            entry.model_id,
            provider=OpenAIProvider(
                openai_client=AsyncOpenAI(api_key=api_key, max_retries=0)
            ),
        ),
        output_type=NativeOutput(_LunaEnvelope),
        instructions=(
            "The state and questions are the complete pre-decision record. "
            "Answer every question exactly once in the original unit ids."
        ),
        retries=AgentRetries(output=0, tools=0),
        model_settings=OpenAIResponsesModelSettings(
            max_tokens=entry.max_output_tokens,
            timeout=900,
            openai_service_tier="flex",
            openai_reasoning_effort=effort.value,
        ),
    )
    try:
        result = agent.run_sync(prompt, usage_limits=UsageLimits(request_limit=1))
    except BaseException as exc:
        raise LiveModelProviderError(
            "Luna comparator PydanticAI request failed",
            retryable=False,
        ) from exc
    usage = result.usage
    if usage.requests != 1:
        raise ValueError("Luna comparator must make exactly one model request")
    output = result.output
    response = result.response
    served_model = response.model_name
    if not isinstance(served_model, str) or not served_model.strip():
        raise ValueError("Luna comparator response omitted the served model")
    if served_model != entry.model_id:
        raise ValueError(
            "Luna comparator response model differs from the frozen registry: "
            f"expected {entry.model_id!r}, got {served_model!r}"
        )
    usage_fields = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "input_audio_tokens",
        "output_audio_tokens",
        "requests",
        "tool_calls",
    )
    usage_record: dict[str, object] = {
        field_name: getattr(usage, field_name)
        for field_name in usage_fields
        if isinstance(getattr(usage, field_name, None), int)
    }
    if usage.cost is not None:
        usage_record["sdk_cost_usd"] = str(usage.cost)
    provider_metadata: dict[str, object] = {
        "sdk": "pydantic_ai",
        "request_limit": "1",
        "retries": "0",
        "reasoning_effort": effort.value,
        "provider_name": response.provider_name,
        "provider_url": response.provider_url,
        "provider_response_id": response.provider_response_id,
        "provider_details": response.provider_details or {},
    }
    return {
        "model": served_model,
        "predictions": [
            prediction.model_dump(mode="json") for prediction in output.predictions
        ],
        "usage": usage_record,
        "providerMetadata": provider_metadata,
        "_jev_request_count": 1,
    }


def _payload_predictions(
    payload: Mapping[str, object], unit_ids: tuple[str, ...]
) -> list[dict[str, object]]:
    values = payload.get("predictions")
    if not isinstance(values, list):
        raise ValueError("Luna comparator predictions must be an array")
    predictions: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_value in cast(list[object], values):
        if not isinstance(raw_value, dict):
            raise ValueError("Luna comparator prediction must be an object")
        value = cast(dict[str, object], raw_value)
        unit_id = value.get("unit_id")
        probability = value.get("probability_fully_dismissed")
        if (
            not isinstance(unit_id, str)
            or not unit_id
            or unit_id in seen
            or unit_id not in unit_ids
            or isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability))
            or not 0 <= float(probability) <= 1
        ):
            raise ValueError("Luna comparator returned invalid unit probabilities")
        seen.add(unit_id)
        predictions.append(
            {
                "unit_id": unit_id,
                "probability_fully_dismissed": probability,
            }
        )
    if seen != set(unit_ids):
        raise ValueError(
            "Luna comparator must return exactly one probability for every unit"
        )
    return predictions


def complete_luna_cell(
    entry: ModelRegistryEntry,
    *,
    handler: ProviderSpendAttemptHandler,
    case: _LunaCaseInput,
    transport: LiveModelTransport,
    request_body_observer: Callable[[bytes], None],
    environ: Mapping[str, str] | None,
    registry_sha256: str,
) -> SolverResponse:
    """Run one no-tools Luna comparator request and settle its spend attempt."""

    values = environ if environ is not None else os.environ
    if (
        handler.replayable_response is None
        and transport is default_live_model_transport
        and not values.get("OPENAI_API_KEY", "").strip()
    ):
        raise ValueError("OPENAI_API_KEY is required")
    request = dict(case.request)
    request.pop("providerOptions", None)
    request["model"] = entry.model_id
    if entry.reasoning_effort is None:
        raise ValueError("Luna comparator registry must pin reasoning_effort")
    request["reasoning_effort"] = entry.reasoning_effort.value
    body = ARTIFACT_CANONICAL_JSON_V1.encode(request)
    provider_metadata: dict[str, object] = {}

    def call() -> Mapping[str, object]:
        if transport is default_live_model_transport:
            payload = _sdk_call(body, values, entry)
            provider = payload.get("providerMetadata")
            if isinstance(provider, dict):
                provider_metadata.update(cast(dict[str, object], provider))
            return payload
        return transport(
            Request("https://api.openai.com/v1/responses", data=body),
            120.0,
        )

    def reserved_call() -> Mapping[str, object]:
        request_body_observer(body)
        # This comparator deliberately has no rate-limit retry loop: the
        # condition is exactly one PydanticAI/provider request.
        return call()

    payload = handler.run_attempt(1, reserved_call)
    ordinal = handler.durable_attempt_ordinal(1)
    try:
        request_count = payload.get("_jev_request_count", 1)
        if request_count != 1:
            raise ValueError("Luna comparator request count must be exactly one")
        predictions = _payload_predictions(payload, case.unit_ids)
        raw_usage = payload.get("usage")
        if not isinstance(raw_usage, dict):
            raise ValueError("Luna comparator response is missing usage")
        usage = cast(dict[str, object], raw_usage)
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
        ):
            raise ValueError("Luna comparator token usage is invalid")
        if payload.get("model") != entry.model_id:
            raise ValueError("Luna response model differs from the frozen registry")
        raw_output = ARTIFACT_CANONICAL_JSON_V1.encode(
            {
                "case_assessment": (
                    "Luna estimated probabilities from the Jev summary packet; "
                    "no generated rationale."
                ),
                "predictions": predictions,
            }
        ).decode("utf-8")
        cost = _estimated_cost(
            entry,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        served_model = payload.get("model")
        if not isinstance(served_model, str) or not served_model.strip():
            raise ValueError("Luna response omitted the served model")
        verification = verify_provider_response(payload, provider=entry.provider)
        effort = entry.reasoning_effort.value
        cache_read_tokens = usage.get("cache_read_tokens", 0)
        cache_write_tokens = usage.get("cache_write_tokens", 0)
        has_cache_tokens = (
            isinstance(cache_read_tokens, int) and cache_read_tokens > 0
        ) or (isinstance(cache_write_tokens, int) and cache_write_tokens > 0)
        if has_cache_tokens:
            cost_method = "uncached_usage_estimate_missing_cache_rate"
        else:
            cost_method = "uncached_usage_estimate"
        observed_tier = "unreported"
        raw_provider_metadata = provider_metadata or payload.get("providerMetadata", {})
        if isinstance(raw_provider_metadata, dict):
            raw_provider_dict = cast(dict[str, object], raw_provider_metadata)
            raw_details = raw_provider_dict.get("provider_details")
            if isinstance(raw_details, dict):
                raw_details_dict = cast(dict[str, object], raw_details)
                if isinstance(raw_details_dict.get("service_tier"), str):
                    observed_tier = cast(str, raw_details_dict["service_tier"])
        metadata = {
            "provider": entry.provider,
            "model": entry.model_id,
            "served_model_version": served_model,
            "model_registry_sha256": registry_sha256,
            "execution_backend": "pydantic_ai",
            "execution_condition": f"luna_summary_comparator_reasoning_{effort}",
            "provider_attempt_count": "1",
            "rate_limit_rejections": "0",
            "requested_reasoning_effort": effort,
            "cost_basis": "estimated_from_pricing_snapshot",
            "cost_method": cost_method,
            "rate_provenance": entry.pricing_source,
            "service_tier": observed_tier,
            "requested_service_tier": "flex",
            "response_usage_details": json.dumps([usage], sort_keys=True),
            "provider_metadata": json.dumps(
                raw_provider_metadata,
                sort_keys=True,
                default=str,
            ),
            **verification.to_metadata(),
        }
    except BaseException as exc:
        handler.record_post_response_failure(ordinal, failure_type=type(exc).__name__)
        raise
    handler.settle_attempt(
        ordinal,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        actual_cost_usd=cost,
        raw_output=raw_output,
    )
    return SolverResponse(raw_output, 1, input_tokens, output_tokens, cost, metadata)
