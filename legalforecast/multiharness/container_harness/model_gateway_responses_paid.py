"""Frozen-registry pricing and protected settlement for Responses."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from pathlib import Path

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.paid_gateway_descriptor import CODEX_HARNESS_ID
from legalforecast.multiharness.protected_terminal_paid import (
    ProviderGatewaySpendController,
    build_protected_gateway_spend_controller,
)
from legalforecast.runner.managed_cost import (
    ManagedResponseUsage,
    _managed_response_cost,  # pyright: ignore[reportPrivateUsage]
)

from .model_gateway_paid import (
    ProtectedPaidGatewayConfig,
    load_paid_gateway_config,
    worst_case_request_microusd,
)
from .model_gateway_responses_protocol import (
    OPENAI_PROVIDER,
    parse_responses_usage,
)
from .model_gateway_types import ModelGatewayError


def openai_responses_registry_charge_extractor(
    entry: ModelRegistryEntry,
) -> Callable[[bytes, int, str | None], int | None]:
    """Build the existing protected-controller charge hook for OpenAI usage."""

    if entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError(
            "Responses gateway pricing requires an OpenAI registry entry"
        )

    def extract(
        response_body: bytes,
        response_status: int,
        content_type: str | None,
    ) -> int | None:
        if response_status < 200 or response_status >= 300:
            return None
        usage = parse_responses_usage(response_body, content_type)
        if (
            usage is None
            or usage.cache_read_tokens is None
            or usage.cache_write_tokens is None
        ):
            return None
        try:
            amount_usd = _managed_response_cost(
                entry,
                ManagedResponseUsage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=usage.cache_read_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                ),
            )
        except (TypeError, ValueError):
            return None
        if not math.isfinite(amount_usd) or amount_usd < 0:
            return None
        return math.ceil(amount_usd * 1_000_000)

    return extract


def priced_service_tiers_for_registry_entry(
    entry: ModelRegistryEntry,
) -> frozenset[str]:
    """Select the sole OpenAI tier represented by the frozen price source."""

    if entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError("Responses service tiers require an OpenAI model")
    if "flex" in entry.pricing_source.casefold():
        return frozenset({"flex"})
    return frozenset({"default"})


def build_paid_responses_gateway_controller(
    config: ProtectedPaidGatewayConfig,
) -> ProviderGatewaySpendController:
    """Reuse the protected authority with Responses-specific charge evidence."""

    if config.registry_entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError("paid Responses gateway requires an OpenAI model")
    return build_protected_gateway_spend_controller(
        config.spend,
        reservation_microusd=worst_case_request_microusd(config.registry_entry),
        charge_extractor=openai_responses_registry_charge_extractor(
            config.registry_entry
        ),
    )


def load_paid_responses_gateway_config(
    config_path: str | Path,
    *,
    model_registry_path: str | Path,
    environment: Mapping[str, str] | None = None,
) -> ProtectedPaidGatewayConfig:
    """Load the protected descriptor and require the Codex/OpenAI binding."""

    config = load_paid_gateway_config(
        config_path,
        model_registry_path=model_registry_path,
        environment=environment,
    )
    if config.registry_entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError("paid Responses gateway requires an OpenAI model")
    if config.harness_id != CODEX_HARNESS_ID:
        raise ModelGatewayError("paid Responses gateway requires a Codex descriptor")
    return config


__all__ = [
    "build_paid_responses_gateway_controller",
    "load_paid_responses_gateway_config",
    "openai_responses_registry_charge_extractor",
    "priced_service_tiers_for_registry_entry",
]
