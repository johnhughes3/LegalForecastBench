"""Usage normalization and cost evidence for managed provider runs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol, cast

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.runner.gateway import gateway_total_cost_usd
from legalforecast.runner.ledger import RunValidationError


class ManagedToolAgentError(RuntimeError):
    """The managed official agent did not produce a publishable result."""


class _ManagedCostResult(Protocol):
    """Result attributes needed to calculate cost without a runner import cycle."""

    @property
    def response_usages(self) -> Sequence[tuple[int, int]]: ...

    @property
    def response_usage_details(self) -> Sequence[ManagedResponseUsage]: ...

    @property
    def gateway_response_metadata(self) -> Sequence[Mapping[str, str]]: ...


@dataclass(frozen=True, slots=True)
class ManagedResponseUsage:
    """Normalized usage for one provider response.

    ``input_tokens`` is the provider total and therefore includes cached
    input.  Cache counts are optional so recovery can retain the fact that an
    older transcript did not report them instead of silently turning absence
    into zero.  ``output_tokens`` already includes provider reasoning where
    the adapter reports it that way; ``reasoning_tokens`` is retained as a
    dimension and is never added to output again.
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("input_tokens", "output_tokens"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        for field_name in (
            "cache_read_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer")
        if (
            self.cache_read_tokens is not None
            and self.cache_write_tokens is not None
            and self.cache_read_tokens + self.cache_write_tokens > self.input_tokens
        ):
            raise ValueError("cached input tokens exceed input tokens")

    def to_record(self) -> dict[str, int]:
        """Encode reported dimensions without inventing omitted fields."""

        record = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
        for field_name in (
            "cache_read_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        ):
            value = getattr(self, field_name)
            if value is not None:
                record[field_name] = value
        return record


@dataclass(frozen=True, slots=True)
class ManagedCostEvidence:
    """Cost amount and evidence class retained for one managed session."""

    amount_usd: float
    basis: str
    method: str
    rate_provenance: str


def _managed_estimated_cost(
    entry: ModelRegistryEntry,
    *,
    response_usages: Sequence[tuple[int, int]],
    response_usage_details: Sequence[ManagedResponseUsage] = (),
) -> float:
    """Estimate direct-provider cost from normalized response usage.

    ``response_usages`` remains the two-column legacy input for old durable
    payloads.  New runs pass ``response_usage_details`` so cached input can be
    priced separately when the frozen registry carries an authoritative rate.
    Missing historical cache fields are deliberately left missing and fall
    back to the old uncached estimate; they are never inferred from totals.
    """

    if response_usage_details:
        if len(response_usage_details) != len(response_usages):
            raise ManagedToolAgentError(
                "managed response usage dimensions do not match response count"
            )
        return sum(
            _managed_response_cost(entry, usage) for usage in response_usage_details
        )
    total = 0.0
    for usage in response_usages:
        input_tokens, output_tokens = usage
        input_price = entry.input_token_price
        output_price = entry.output_token_price
        surcharge = entry.long_context_surcharge
        if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
            input_price *= surcharge.input_price_multiplier
            output_price *= surcharge.output_price_multiplier
        total += (input_tokens * input_price) + (output_tokens * output_price)
    return total / 1_000_000


def _managed_token_cost(
    entry: ModelRegistryEntry,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Return scalar-rate cost in USD for one response."""

    input_price = entry.input_token_price
    output_price = entry.output_token_price
    surcharge = entry.long_context_surcharge
    if surcharge is not None and input_tokens > surcharge.threshold_input_tokens:
        input_price *= surcharge.input_price_multiplier
        output_price *= surcharge.output_price_multiplier
    return ((input_tokens * input_price) + (output_tokens * output_price)) / 1_000_000


def _managed_response_cost(
    entry: ModelRegistryEntry,
    usage: ManagedResponseUsage,
) -> float:
    """Return one response's cache-aware or conservative fallback estimate."""

    if (
        usage.cache_read_tokens is None
        or usage.cache_write_tokens is None
        or (usage.cache_read_tokens > 0 and entry.cache_read_token_price is None)
        or (usage.cache_write_tokens > 0 and entry.cache_write_token_price is None)
    ):
        # The provider supplied an incomplete usage/rate pair. Charging all
        # input at the ordinary rate is conservative, but remains explicitly
        # an estimate through ``_managed_cost_evidence``.
        return _managed_token_cost(
            entry,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    uncached_tokens = (
        usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    )
    input_price = entry.input_token_price
    cache_read_price = entry.cache_read_token_price or 0.0
    cache_write_price = entry.cache_write_token_price or 0.0
    output_price = entry.output_token_price
    surcharge = entry.long_context_surcharge
    if surcharge is not None and usage.input_tokens > surcharge.threshold_input_tokens:
        multiplier = surcharge.input_price_multiplier
        input_price *= multiplier
        cache_read_price *= multiplier
        cache_write_price *= multiplier
        output_price *= surcharge.output_price_multiplier
    return (
        uncached_tokens * input_price
        + usage.cache_read_tokens * cache_read_price
        + usage.cache_write_tokens * cache_write_price
        + usage.output_tokens * output_price
    ) / 1_000_000


def _managed_cost_evidence(
    entry: ModelRegistryEntry,
    *,
    result: _ManagedCostResult,
) -> ManagedCostEvidence:
    """Classify a managed cost as charged, reconstructed, or estimated."""

    provider = entry.provider.strip().lower()
    if provider == "vercel_ai_gateway":
        if not result.gateway_response_metadata:
            raise ManagedToolAgentError(
                "managed Gateway response omitted response metadata"
            )
        try:
            amount_usd = gateway_total_cost_usd(result.gateway_response_metadata)
        except ValueError as exc:
            raise ManagedToolAgentError(str(exc)) from exc
        return ManagedCostEvidence(
            amount_usd=amount_usd,
            basis="provider_reported",
            method="gateway_reported_charge",
            rate_provenance="gateway_response_metadata",
        )

    amount_usd = _managed_estimated_cost(
        entry,
        response_usages=result.response_usages,
        response_usage_details=result.response_usage_details,
    )
    details = result.response_usage_details
    complete_cache_counts = bool(details) and all(
        usage.cache_read_tokens is not None and usage.cache_write_tokens is not None
        for usage in details
    )
    has_cached_tokens = any(
        (usage.cache_read_tokens or 0) > 0 or (usage.cache_write_tokens or 0) > 0
        for usage in details
    )
    cache_rates_known = all(
        (usage.cache_read_tokens == 0 or entry.cache_read_token_price is not None)
        and (usage.cache_write_tokens == 0 or entry.cache_write_token_price is not None)
        for usage in details
    )
    if complete_cache_counts and not has_cached_tokens:
        method = "uncached_usage_estimate"
    elif complete_cache_counts and cache_rates_known:
        method = "cache_aware_usage_reconstruction"
    elif details and not complete_cache_counts:
        method = "uncached_usage_estimate_missing_cache_usage"
    elif details and has_cached_tokens:
        method = "uncached_usage_estimate_missing_cache_rate"
    else:
        method = "legacy_uncached_usage_estimate"
    return ManagedCostEvidence(
        amount_usd=amount_usd,
        basis="estimated_from_pricing_snapshot",
        method=method,
        rate_provenance=entry.pricing_source,
    )


def _managed_result_cost_evidence(
    entry: ModelRegistryEntry,
    *,
    result: _ManagedCostResult,
) -> ManagedCostEvidence:
    """Return the authoritative cost evidence for one managed result."""

    return _managed_cost_evidence(entry, result=result)


# Kept as a private compatibility shim for recovery and older integrations.
def _managed_result_cost(  # pyright: ignore[reportUnusedFunction]
    entry: ModelRegistryEntry,
    *,
    result: _ManagedCostResult,
) -> float:
    """Return the amount from the managed result's cost evidence."""

    return _managed_result_cost_evidence(entry, result=result).amount_usd


def _managed_payload_cost_evidence(
    entry: ModelRegistryEntry,
    *,
    estimated_cost: float,
    usage_details: tuple[ManagedResponseUsage, ...],
    gateway_metadata: tuple[Mapping[str, str], ...],
    cost_basis: str | None,
    cost_method: str | None,
    rate_provenance: str | None,
    raw_output: str,
    request_count: int,
    input_tokens: int,
    output_tokens: int,
    served_model: str,
    finish_reason: str,
    service_tier: str,
    thoughts_tokens: int,
) -> ManagedCostEvidence:
    """Validate new cost evidence while accepting old replay payloads."""

    if usage_details:
        if sum(usage.input_tokens for usage in usage_details) != input_tokens:
            raise RunValidationError(
                "managed response usage input total differs from normalized rows"
            )
        if sum(usage.output_tokens for usage in usage_details) != output_tokens:
            raise RunValidationError(
                "managed response usage output total differs from normalized rows"
            )
        result = cast(
            _ManagedCostResult,
            SimpleNamespace(
                response_usages=tuple(
                    (usage.input_tokens, usage.output_tokens) for usage in usage_details
                ),
                response_usage_details=usage_details,
                gateway_response_metadata=gateway_metadata,
            ),
        )
        expected = _managed_result_cost_evidence(entry, result=result)
        if not math.isclose(
            estimated_cost,
            expected.amount_usd,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RunValidationError(
                "managed response cost differs from normalized usage evidence"
            )
        if cost_basis is not None and cost_basis != expected.basis:
            raise RunValidationError("managed response cost basis is invalid")
        if cost_method is not None and cost_method != expected.method:
            raise RunValidationError("managed response cost method is invalid")
        if rate_provenance is not None and rate_provenance != expected.rate_provenance:
            raise RunValidationError("managed response rate provenance is invalid")
        return expected

    provider = entry.provider.strip().lower()
    if provider == "vercel_ai_gateway":
        expected = ManagedCostEvidence(
            amount_usd=estimated_cost,
            basis="provider_reported",
            method="gateway_reported_charge",
            rate_provenance="gateway_response_metadata",
        )
    else:
        expected = ManagedCostEvidence(
            amount_usd=estimated_cost,
            basis="estimated_from_pricing_snapshot",
            method="legacy_uncached_usage_estimate",
            rate_provenance=entry.pricing_source,
        )
    for supplied, expected_value, label in (
        (cost_basis, expected.basis, "cost basis"),
        (cost_method, expected.method, "cost method"),
        (rate_provenance, expected.rate_provenance, "rate provenance"),
    ):
        if supplied is not None and supplied != expected_value:
            raise RunValidationError(f"managed response {label} is invalid")
    return expected


managed_estimated_cost = _managed_estimated_cost
managed_payload_cost_evidence = _managed_payload_cost_evidence
managed_result_cost = _managed_result_cost
managed_result_cost_evidence = _managed_result_cost_evidence
