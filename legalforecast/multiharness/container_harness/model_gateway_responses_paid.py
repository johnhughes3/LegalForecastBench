"""Frozen-registry pricing and protected settlement for Responses."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.protected_terminal_paid import (
    ProviderGatewaySpendController,
    build_protected_gateway_spend_controller,
)
from legalforecast.runner.managed_cost import (
    ManagedResponseUsage,
    _managed_response_cost,  # pyright: ignore[reportPrivateUsage]
)

from .model_gateway_paid import (
    CODEX_HARNESS_ID,
    ProtectedPaidGatewayConfig,
    load_paid_gateway_config,
    worst_case_request_microusd,
)
from .model_gateway_responses_protocol import (
    OPENAI_PROVIDER,
    parse_responses_terminal,
)
from .model_gateway_types import ModelGatewayError


@dataclass(frozen=True, slots=True)
class _OpenAIStandardPriceProfile:
    input_token_price: float
    output_token_price: float
    cache_read_token_price: float
    cache_write_token_price: float
    flex_supported: bool
    long_context_threshold: int | None = None
    long_context_input_multiplier: float | None = None
    long_context_output_multiplier: float | None = None


_OPENAI_STANDARD_PRICE_PROFILES: Final[dict[str, _OpenAIStandardPriceProfile]] = {
    "gpt-6.1-sol": _OpenAIStandardPriceProfile(
        2.0, 10.0, 0.1, 2.5, True, 272_000, 2.0, 1.5
    ),
    "gpt-6-sol": _OpenAIStandardPriceProfile(
        2.0, 10.0, 0.2, 2.5, True, 272_000, 2.0, 1.5
    ),
    "gpt-6-luna": _OpenAIStandardPriceProfile(
        0.1, 0.5, 0.01, 0.125, True, 272_000, 2.0, 1.5
    ),
    "gpt-4.1-2025-04-14": _OpenAIStandardPriceProfile(2.0, 8.0, 0.5, 2.0, False),
}


def openai_responses_registry_charge_extractor(
    entry: ModelRegistryEntry,
    *,
    expected_service_tier: str,
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
        terminal = parse_responses_terminal(response_body, content_type)
        if terminal is None or terminal.service_tier != expected_service_tier:
            return None
        usage = terminal.usage
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


def priced_service_tier_for_registry_entry(entry: ModelRegistryEntry) -> str:
    """Return the tier whose structured rates match the frozen registry entry."""

    if entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError("Responses service tiers require an OpenAI model")
    profile = _OPENAI_STANDARD_PRICE_PROFILES.get(entry.model_id)
    if profile is None:
        raise ModelGatewayError(
            "Responses registry entry has no supported structured price profile"
        )
    if _entry_matches_price_profile(entry, profile, price_multiplier=1.0):
        return "default"
    if profile.flex_supported and _entry_matches_price_profile(
        entry, profile, price_multiplier=0.5
    ):
        return "flex"
    raise ModelGatewayError(
        "Responses registry entry does not match a supported structured price profile"
    )


def _entry_matches_price_profile(
    entry: ModelRegistryEntry,
    profile: _OpenAIStandardPriceProfile,
    *,
    price_multiplier: float,
) -> bool:
    actual_prices = (
        entry.input_token_price,
        entry.output_token_price,
        entry.cache_read_token_price,
        entry.cache_write_token_price,
    )
    expected_prices = (
        profile.input_token_price * price_multiplier,
        profile.output_token_price * price_multiplier,
        profile.cache_read_token_price * price_multiplier,
        profile.cache_write_token_price * price_multiplier,
    )
    if any(
        actual is None
        or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        for actual, expected in zip(actual_prices, expected_prices, strict=True)
    ):
        return False
    surcharge = entry.long_context_surcharge
    if profile.long_context_threshold is None:
        return surcharge is None
    return surcharge is not None and (
        surcharge.threshold_input_tokens == profile.long_context_threshold
        and math.isclose(
            surcharge.input_price_multiplier,
            profile.long_context_input_multiplier or 0.0,
            rel_tol=0.0,
            abs_tol=0.0,
        )
        and math.isclose(
            surcharge.output_price_multiplier,
            profile.long_context_output_multiplier or 0.0,
            rel_tol=0.0,
            abs_tol=0.0,
        )
    )


def build_paid_responses_gateway_controller(
    config: ProtectedPaidGatewayConfig,
) -> ProviderGatewaySpendController:
    """Reuse the protected authority with Responses-specific charge evidence."""

    if config.registry_entry.provider.strip().lower() != OPENAI_PROVIDER:
        raise ModelGatewayError("paid Responses gateway requires an OpenAI model")
    service_tier = config.pricing_service_tier
    if service_tier is None:
        raise ModelGatewayError(
            "paid Responses gateway requires a structured pricing service tier"
        )
    return build_protected_gateway_spend_controller(
        config.spend,
        reservation_microusd=worst_case_request_microusd(config.registry_entry),
        charge_extractor=openai_responses_registry_charge_extractor(
            config.registry_entry,
            expected_service_tier=service_tier,
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
    expected_tier = priced_service_tier_for_registry_entry(config.registry_entry)
    if config.pricing_service_tier != expected_tier:
        raise ModelGatewayError(
            "paid Responses gateway pricing tier differs from the registry profile"
        )
    return config


__all__ = [
    "build_paid_responses_gateway_controller",
    "load_paid_responses_gateway_config",
    "openai_responses_registry_charge_extractor",
    "priced_service_tier_for_registry_entry",
]
