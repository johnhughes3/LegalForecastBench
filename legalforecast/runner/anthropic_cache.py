"""Cost reconstruction for native Anthropic five-minute prompt caching.

The native Anthropic adapter enables the provider's five-minute automatic
cache.  Anthropic reports cache reads and writes as separate usage dimensions,
while Pydantic AI normalizes ``input_tokens`` to include both dimensions.  The
helper in this module keeps that inclusive total intact and prices the three
input buckets exactly once.

The model table is deliberately local to this new execution contract.  Older
model registries remain immutable and do not gain fields retroactively.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from legalforecast.evals.model_registry import ModelRegistryEntry

AnthropicCacheTtl = Literal["5m"]

_PRICING_SOURCE: Final = (
    "https://platform.claude.com/docs/en/about-claude/pricing, "
    "Anthropic prompt-cache pricing checked 2026-09-12"
)


@dataclass(frozen=True, slots=True)
class _AnthropicCacheRate:
    """Verified five-minute cache rates for one exact Anthropic model ID."""

    input_token_price: float
    cache_read_token_price: float
    cache_write_token_price: float
    output_token_price: float
    ttl: AnthropicCacheTtl = "5m"


# These are the current first-party Anthropic rates in USD per million tokens.
# The cache flag used by the native adapter resolves ``True`` to the 5m TTL.
# Fable 5.1 is the held Anthropic model; Opus 5 and Sonnet 5 are the current
# document-tool execution models.
_RATES: Final[dict[str, _AnthropicCacheRate]] = {
    "claude-fable-5-1": _AnthropicCacheRate(
        input_token_price=10.0,
        cache_read_token_price=0.25,
        cache_write_token_price=12.5,
        output_token_price=50.0,
    ),
    "claude-opus-5": _AnthropicCacheRate(
        input_token_price=5.0,
        cache_read_token_price=0.5,
        cache_write_token_price=6.25,
        output_token_price=25.0,
    ),
    "claude-sonnet-5": _AnthropicCacheRate(
        input_token_price=2.0,
        cache_read_token_price=0.2,
        cache_write_token_price=2.5,
        output_token_price=10.0,
    ),
}


def anthropic_cache_cost(
    entry: ModelRegistryEntry,
    response_usages: Sequence[tuple[int, int]],
    cache_usages: Sequence[tuple[int, int]],
) -> tuple[float, dict[str, object]]:
    """Price normalized native Anthropic responses with the five-minute cache.

    ``response_usages`` contains inclusive ``(input_tokens, output_tokens)``
    pairs.  ``cache_usages`` contains disjoint ``(cache_read_tokens,
    cache_write_tokens)`` pairs for the same responses.  Because the input
    total includes both cache dimensions, the helper prices
    ``input - cache_read - cache_write`` at the base input rate and does not
    add reasoning tokens to output a second time.

    The returned metadata is suitable for serializing into a managed response
    payload.  It records the exact rates and source so a reconstructed amount
    is never presented as a provider-charged amount.
    """

    if entry.provider.strip().lower() != "anthropic":
        raise ValueError("Anthropic cache pricing requires an Anthropic registry entry")
    try:
        rates = _RATES[entry.model_id]
    except KeyError as exc:
        raise ValueError(
            f"no verified five-minute Anthropic cache rates for {entry.model_id}"
        ) from exc
    if len(response_usages) != len(cache_usages):
        raise ValueError("response and cache usage counts must have equal lengths")
    if entry.input_token_price != rates.input_token_price:
        raise ValueError(
            f"registry input rate for {entry.model_id} differs from the verified "
            "Anthropic cache pricing contract"
        )
    if entry.output_token_price != rates.output_token_price:
        raise ValueError(
            f"registry output rate for {entry.model_id} differs from the verified "
            "Anthropic cache pricing contract"
        )

    total_microusd = 0.0
    for response_index, (
        (input_tokens, output_tokens),
        (cache_read, cache_write),
    ) in enumerate(zip(response_usages, cache_usages, strict=True)):
        _require_non_negative(input_tokens, "input_tokens", response_index)
        _require_non_negative(output_tokens, "output_tokens", response_index)
        _require_non_negative(cache_read, "cache_read_tokens", response_index)
        _require_non_negative(cache_write, "cache_write_tokens", response_index)
        if cache_read + cache_write > input_tokens:
            raise ValueError(
                f"cache usage exceeds input usage for response {response_index}"
            )

        input_price = rates.input_token_price
        cache_read_price = rates.cache_read_token_price
        cache_write_price = rates.cache_write_token_price
        output_price = rates.output_token_price
        surcharge = entry.long_context_surcharge
        if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
            input_price *= surcharge.input_price_multiplier
            cache_read_price *= surcharge.input_price_multiplier
            cache_write_price *= surcharge.input_price_multiplier
            output_price *= surcharge.output_price_multiplier

        uncached_tokens = input_tokens - cache_read - cache_write
        total_microusd += (
            uncached_tokens * input_price
            + cache_read * cache_read_price
            + cache_write * cache_write_price
            + output_tokens * output_price
        )

    provenance = (
        f"{_PRICING_SOURCE}; model={entry.model_id}; ttl={rates.ttl}; "
        f"input={rates.input_token_price:g}/M; "
        f"cache_read={rates.cache_read_token_price:g}/M; "
        f"cache_write={rates.cache_write_token_price:g}/M; "
        f"output={rates.output_token_price:g}/M"
    )
    metadata: dict[str, object] = {
        "cost_basis": "estimated_from_pricing_snapshot",
        "cost_method": "anthropic_cache_aware_usage_reconstruction",
        "rate_provenance": provenance,
        "cache_pricing_provider": "anthropic",
        "cache_pricing_model": entry.model_id,
        "cache_pricing_ttl": rates.ttl,
        "cache_pricing_source": _PRICING_SOURCE,
        "input_token_price_usd_per_million": rates.input_token_price,
        "cache_read_token_price_usd_per_million": rates.cache_read_token_price,
        "cache_write_token_price_usd_per_million": rates.cache_write_token_price,
        "output_token_price_usd_per_million": rates.output_token_price,
    }
    return total_microusd / 1_000_000, metadata


def _require_non_negative(value: object, field_name: str, response_index: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"{field_name} must be a non-negative integer for response {response_index}"
        )


__all__ = ["AnthropicCacheTtl", "anthropic_cache_cost"]
