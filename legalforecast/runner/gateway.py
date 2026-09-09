"""Vercel AI Gateway transport and response metadata checks."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import cast

from openai.types.responses import Response
from pydantic_ai import ModelProfile
from pydantic_ai.profiles import merge_profile
from pydantic_ai.providers.openai import OpenAIProvider

VERCEL_AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_GATEWAY_ROUTE_PROVIDERS = {
    "openai/gpt-5.6-sol": "openai",
    "moonshotai/kimi-k3": "deepinfra",
    "meta/muse-spark-1.3": "meta",
    "meta/muse-spark-1.3-contributor": "meta",
    "spacexai/grok-4.6": "xai",
}
_MUSE_GATEWAY_MODEL_IDS = frozenset(
    {"meta/muse-spark-1.3", "meta/muse-spark-1.3-contributor"}
)
_GATEWAY_MODEL_ALIASES = {
    # Gateway keeps the requested id in ``originalModelId`` but returns the
    # provider's canonical slug for Grok 4.6.  This is the one verified
    # served-identity alias; every other model remains exact-match only.
    "spacexai/grok-4.6": frozenset({"xai/grok-4.6"}),
}


def gateway_route_provider(model_id: str) -> str:
    """Return the provider allowlisted for one frozen Gateway model id."""

    try:
        return _GATEWAY_ROUTE_PROVIDERS[model_id.casefold()]
    except KeyError as exc:
        raise ValueError(
            f"Vercel AI Gateway model is not allowlisted: {model_id}"
        ) from exc


def gateway_model_is_allowlisted(model_id: str) -> bool:
    """Return whether a model id has a frozen Gateway route."""

    return model_id.casefold() in _GATEWAY_ROUTE_PROVIDERS


def gateway_normalize_model_identity(
    expected_model_id: str, observed_model_id: str
) -> str:
    """Return the frozen id for one exact Gateway served-model identity.

    Gateway's request identity remains strict.  A small explicit alias table
    accounts for providers that report their canonical slug in Responses
    metadata while Gateway retains the requested model id separately.
    """

    expected = expected_model_id.casefold()
    observed = observed_model_id.casefold()
    if observed == expected or observed in _GATEWAY_MODEL_ALIASES.get(expected, ()):
        return expected_model_id
    raise ValueError("Vercel AI Gateway response changed the served model")


def gateway_request_extra_body(model_id: str) -> dict[str, object]:
    """Return the OpenAI SDK body that prevents Gateway provider fallback."""

    return {
        "providerOptions": {"gateway": {"only": [gateway_route_provider(model_id)]}}
    }


def gateway_model_profile(provider: OpenAIProvider, model_id: str) -> ModelProfile:
    """Teach the OpenAI compatible adapter that a Gateway model reasons."""

    profile: dict[str, object] = {
        "supports_thinking": True,
        "thinking_always_enabled": True,
        "openai_supports_reasoning": True,
        "openai_reasoning_enabled_by_default": True,
        "openai_supports_reasoning_effort_none": False,
        "openai_supports_minimal_reasoning_effort": False,
    }
    if model_id.casefold() in _MUSE_GATEWAY_MODEL_IDS:
        # Muse's Gateway route accepts only the automatic tool-choice mode. Keep
        # this override scoped to the two verified Muse model ids; other routes
        # retain the OpenAI adapter default until their provider behavior is known.
        profile["openai_supports_tool_choice_required"] = False
    return merge_profile(
        provider.model_profile(model_id),
        cast(ModelProfile, profile),
    )


def gateway_response_metadata(response: Response) -> dict[str, str] | None:
    """Extract the Gateway routing/cost envelope retained by OpenAI's model."""

    extras = getattr(response, "model_extra", None)
    if not isinstance(extras, Mapping):
        return None
    typed_extras = cast(Mapping[str, object], extras)
    provider_metadata = typed_extras.get(
        "providerMetadata", typed_extras.get("provider_metadata")
    )
    if not isinstance(provider_metadata, Mapping):
        return None
    provider_metadata = cast(Mapping[str, object], provider_metadata)
    gateway = provider_metadata.get("gateway")
    if not isinstance(gateway, Mapping):
        return None
    gateway = cast(Mapping[str, object], gateway)
    routing = gateway.get("routing")
    if not isinstance(routing, Mapping):
        return None
    routing = cast(Mapping[str, object], routing)

    values: dict[str, str] = {}
    for output_name, source_names in (
        ("original_model_id", ("originalModelId", "original_model_id")),
        ("resolved_provider", ("resolvedProvider", "resolved_provider")),
        (
            "resolved_provider_api_model_id",
            ("resolvedProviderApiModelId", "resolved_provider_api_model_id"),
        ),
        ("canonical_slug", ("canonicalSlug", "canonical_slug")),
        ("final_provider", ("finalProvider", "final_provider")),
    ):
        value = _gateway_metadata_string(routing, source_names)
        if value is None:
            if output_name == "resolved_provider_api_model_id":
                # Gateway currently omits this field for some successful routes.
                # Preserve the omission so recovery can validate the fields the
                # service actually returned without inventing an API model id.
                continue
            return None
        values[output_name] = value
    for output_name, source_names in (
        ("model_attempt_count", ("modelAttemptCount", "model_attempt_count")),
        (
            "total_provider_attempt_count",
            ("totalProviderAttemptCount", "total_provider_attempt_count"),
        ),
    ):
        value = _gateway_metadata_string(routing, source_names)
        if value is None:
            return None
        values[output_name] = value
    for output_name, source_names in (
        ("generation_id", ("generationId", "generation_id")),
        # ``gatewayCost`` includes Gateway's provider allowlist surcharge.  The
        # inference ``cost`` field does not, so prefer the charged amount when
        # the service supplies it and retain the older field as a fallback.
        ("cost_usd", ("gatewayCost", "gateway_cost_usd", "cost", "cost_usd")),
        ("market_cost_usd", ("marketCost", "market_cost_usd")),
    ):
        value = _gateway_metadata_string(gateway, source_names)
        if value is None:
            return None
        values[output_name] = value
    return values


def _gateway_metadata_string(
    values: Mapping[str, object], names: Sequence[str]
) -> str | None:
    for name in names:
        value = values.get(name)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            if not math.isfinite(float(value)) or float(value) < 0:
                return None
            return str(value)
        if isinstance(value, str) and value:
            return value
    return None


def validate_gateway_metadata(
    metadata: Mapping[str, object],
    *,
    expected_model_id: str,
    expected_provider: str,
) -> Mapping[str, str]:
    """Validate one Gateway routing and usage record before publishing it."""

    required_fields = (
        "original_model_id",
        "resolved_provider",
        "canonical_slug",
        "final_provider",
        "generation_id",
        "cost_usd",
        "market_cost_usd",
        "model_attempt_count",
        "total_provider_attempt_count",
    )
    normalized: dict[str, str] = {}
    for field_name in required_fields:
        value = metadata.get(field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Vercel AI Gateway metadata field is invalid: {field_name}"
            )
        normalized[field_name] = value
    api_model_id = metadata.get("resolved_provider_api_model_id")
    if api_model_id is not None:
        if not isinstance(api_model_id, str) or not api_model_id:
            raise ValueError(
                "Vercel AI Gateway metadata field is invalid: "
                "resolved_provider_api_model_id"
            )
        normalized["resolved_provider_api_model_id"] = api_model_id
    for field_name in ("cost_usd", "market_cost_usd"):
        try:
            cost = float(normalized[field_name])
        except ValueError as exc:
            raise ValueError(
                f"Vercel AI Gateway metadata field is invalid: {field_name}"
            ) from exc
        if not math.isfinite(cost) or cost < 0:
            raise ValueError(
                f"Vercel AI Gateway metadata field is invalid: {field_name}"
            )
    for field_name in ("model_attempt_count", "total_provider_attempt_count"):
        value = normalized[field_name]
        if not value.isdigit() or int(value) < 1:
            raise ValueError(
                f"Vercel AI Gateway metadata field is invalid: {field_name}"
            )
    expected_model = expected_model_id.casefold()
    if normalized["original_model_id"].casefold() != expected_model:
        raise ValueError("Vercel AI Gateway response changed the requested model")
    try:
        gateway_normalize_model_identity(
            expected_model_id,
            normalized["canonical_slug"],
        )
    except ValueError as exc:
        raise ValueError(
            "Vercel AI Gateway response changed the canonical model"
        ) from exc
    if normalized["resolved_provider"].casefold() != expected_provider.casefold():
        raise ValueError(
            "Vercel AI Gateway response used an unexpected resolved provider route"
        )
    if normalized["final_provider"].casefold() != expected_provider.casefold():
        raise ValueError("Vercel AI Gateway response used an unexpected provider route")
    return normalized


def gateway_total_cost_usd(
    metadata_rows: Sequence[Mapping[str, object]],
) -> float:
    """Return the charged Gateway total from validated response metadata."""

    costs: list[float] = []
    for row in metadata_rows:
        value = row.get("cost_usd")
        if not isinstance(value, str):
            raise ValueError("Vercel AI Gateway metadata cost is missing")
        try:
            cost = float(value)
        except ValueError as exc:
            raise ValueError("Vercel AI Gateway metadata cost is invalid") from exc
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Vercel AI Gateway metadata cost is invalid")
        costs.append(cost)
    return math.fsum(costs)


__all__ = [
    "VERCEL_AI_GATEWAY_BASE_URL",
    "gateway_model_is_allowlisted",
    "gateway_model_profile",
    "gateway_normalize_model_identity",
    "gateway_request_extra_body",
    "gateway_response_metadata",
    "gateway_route_provider",
    "gateway_total_cost_usd",
    "validate_gateway_metadata",
]
