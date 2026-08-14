"""Receipt-backed harness efficiency and accounting observations.

Bead ``LegalForecastBench-dm0g.4.1.16`` owns these published observations.
They bind to the existing ``RunSpec`` / ``ExecutionReceipt`` pair and to
``EvaluationReceipt`` token/cost/timing fields. This module does not invent a
second receipt family.

Unknown usage is null with a reason. Subscription-unallocable cost is never
``$0``. Cache, reasoning, and retry dimensions are not added on top of a
provider-reported total. Parallel summed call time is allowed to differ from
wall-clock. Cost ratios require compatible bases and currencies. A single
repeat publishes observed values only — never faux variance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any, Self

from legalforecast.contracts import ARTIFACT_PREFIXED_SHA256_V1, SchemaIdentifier
from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationReceipt,
    TokenCount,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_mapping,
    require_schema_version,
    require_str,
    validate_public_record,
    validate_sha256,
)

HARNESS_EFFICIENCY_OBSERVATION_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative efficiency observation sidecar
    "legalforecast.multiharness.harness_efficiency_observation.v1"
)
OBSERVATION_KIND = "harness_efficiency_observation"
UNKNOWN_NOT_REPORTED = "not_reported"
UNKNOWN_SUBSCRIPTION = "flat_subscription_has_no_per_call_allocation"
KNOWN_COST_BASES = frozenset(
    {"metered", "provider_reported", "estimated_from_pricing_snapshot"}
)
NULL_COST_BASES = frozenset({"subscription_unallocable", "unknown"})
COMPATIBLE_RATIO_BASES = frozenset({"metered", "provider_reported"})
_SOLVE_TOTAL_KEY = "total_tokens"
_SOLVE_INPUT_KEY = "input_tokens"
_SOLVE_OUTPUT_KEY = "output_tokens"
_DIMENSION_KEYS = frozenset(
    {"cache_read_tokens", "cache_write_tokens", "reasoning_tokens"}
)
_OBSERVATION_REQUIRED = frozenset(
    {
        "schema_version",
        "kind",
        "run_identity_key",
        "execution_receipt_sha256",
        "solve_tokens",
        "eval_tokens",
        "total_tokens",
        "solve_cost",
        "eval_cost",
        "combined_cost",
        "wall_elapsed_ms",
        "summed_call_elapsed_ms",
        "attempt_count",
        "retry_count",
        "failure_count",
    }
)
_OBSERVATION_OPTIONAL = frozenset(
    {"evaluation_receipt_sha256", "deliverable_manifest_sha256"}
)

ACCOUNTING_DEFINITIONS: dict[str, str] = {
    "solve_tokens": (
        "Provider-reported solver tokens from ExecutionReceipt.usage. When "
        "total_tokens is present it is used as-is. Otherwise input_tokens plus "
        "output_tokens. Cache-read, cache-write, and reasoning tokens are "
        "dimensions and are never added on top of a reported total."
    ),
    "eval_tokens": (
        "Evaluator tokens from EvaluationReceipt.token_usage.total_tokens. "
        "Missing totals stay null with unknown_reason; zeroes are never inferred."
    ),
    "total_tokens": (
        "Solve tokens plus eval tokens when both are known. Null with reason "
        "when either side is unknown. Retry receipts are counted once per "
        "receipt_id."
    ),
    "solve_cost": (
        "ExecutionReceipt.cost_usd converted to micro-USD with basis "
        "provider_reported. Null cost is unknown, never $0. "
        "subscription_unallocable cannot carry an amount."
    ),
    "eval_cost": (
        "EvaluationReceipt.cost, including its basis, currency, and "
        "pricing_snapshot_sha256. subscription_unallocable remains null."
    ),
    "combined_cost": (
        "Sum of solve and eval costs only when bases and currencies are "
        "compatible. Ratios are refused across estimated vs metered bases or "
        "across currencies. subscription_unallocable never enters a ratio as $0."
    ),
    "wall_elapsed_ms": (
        "Process wall-clock from ExecutionReceipt.duration_ms. Parallel work "
        "does not inflate this clock."
    ),
    "summed_call_elapsed_ms": (
        "Sum of per-call monotonic elapsed time from "
        "EvaluationReceipt.timing.summed_call_elapsed_ns, converted to "
        "milliseconds. This may differ from wall_elapsed_ms."
    ),
    "attempt_count": "Number of unique ExecutionReceipt receipt_ids observed.",
    "retry_count": (
        "Attempts beyond the first unique receipt. Retries contribute to "
        "attempt_count once each and are not double-counted in token totals."
    ),
    "failure_count": "Receipts whose status is not succeeded.",
}


class AccountingError(MultiHarnessValidationError):
    """An efficiency observation violated an accounting rule."""


@dataclass(frozen=True, slots=True)
class HarnessEfficiencyObservation:
    """One published, receipt-backed efficiency observation."""

    run_identity_key: str
    execution_receipt_sha256: str
    solve_tokens: TokenCount
    eval_tokens: TokenCount
    total_tokens: TokenCount
    solve_cost: CostMeasurement
    eval_cost: CostMeasurement
    combined_cost: CostMeasurement
    wall_elapsed_ms: int
    summed_call_elapsed_ms: int | None
    attempt_count: int
    retry_count: int
    failure_count: int
    evaluation_receipt_sha256: str | None = None
    deliverable_manifest_sha256: str | None = None
    schema_version: str = HARNESS_EFFICIENCY_OBSERVATION_SCHEMA_VERSION
    kind: str = OBSERVATION_KIND

    def __post_init__(self) -> None:
        if self.schema_version != HARNESS_EFFICIENCY_OBSERVATION_SCHEMA_VERSION:
            raise AccountingError("unsupported efficiency observation schema_version")
        if self.kind != OBSERVATION_KIND:
            raise AccountingError("unsupported efficiency observation kind")
        _require_identity_key(self.run_identity_key)
        validate_sha256(self.execution_receipt_sha256, "execution_receipt_sha256")
        if self.evaluation_receipt_sha256 is not None:
            validate_sha256(
                self.evaluation_receipt_sha256,
                "evaluation_receipt_sha256",
            )
        if self.deliverable_manifest_sha256 is not None:
            validate_sha256(
                self.deliverable_manifest_sha256,
                "deliverable_manifest_sha256",
            )
        _require_non_negative_int(self.wall_elapsed_ms, "wall_elapsed_ms")
        if self.summed_call_elapsed_ms is not None:
            _require_non_negative_int(
                self.summed_call_elapsed_ms,
                "summed_call_elapsed_ms",
            )
        _require_positive_int(self.attempt_count, "attempt_count")
        _require_non_negative_int(self.retry_count, "retry_count")
        _require_non_negative_int(self.failure_count, "failure_count")
        if self.retry_count >= self.attempt_count:
            raise AccountingError("retry_count must be smaller than attempt_count")
        if self.failure_count > self.attempt_count:
            raise AccountingError("failure_count cannot exceed attempt_count")
        _reject_subscription_zero(self.solve_cost)
        _reject_subscription_zero(self.eval_cost)
        _reject_subscription_zero(self.combined_cost)
        validate_public_record(self.to_record(), "harness_efficiency_observation")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "run_identity_key": self.run_identity_key,
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "solve_tokens": self.solve_tokens.to_record(),
            "eval_tokens": self.eval_tokens.to_record(),
            "total_tokens": self.total_tokens.to_record(),
            "solve_cost": self.solve_cost.to_record(),
            "eval_cost": self.eval_cost.to_record(),
            "combined_cost": self.combined_cost.to_record(),
            "wall_elapsed_ms": self.wall_elapsed_ms,
            "summed_call_elapsed_ms": self.summed_call_elapsed_ms,
            "attempt_count": self.attempt_count,
            "retry_count": self.retry_count,
            "failure_count": self.failure_count,
        }
        if self.evaluation_receipt_sha256 is not None:
            record["evaluation_receipt_sha256"] = self.evaluation_receipt_sha256
        if self.deliverable_manifest_sha256 is not None:
            record["deliverable_manifest_sha256"] = self.deliverable_manifest_sha256
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_OBSERVATION_REQUIRED,
            optional=_OBSERVATION_OPTIONAL,
            field_name="harness efficiency observation",
        )
        require_schema_version(record, HARNESS_EFFICIENCY_OBSERVATION_SCHEMA_VERSION)
        return cls(
            run_identity_key=require_str(record, "run_identity_key"),
            execution_receipt_sha256=require_str(record, "execution_receipt_sha256"),
            evaluation_receipt_sha256=_optional_digest(
                record,
                "evaluation_receipt_sha256",
            ),
            deliverable_manifest_sha256=_optional_digest(
                record,
                "deliverable_manifest_sha256",
            ),
            solve_tokens=TokenCount.from_record(
                require_mapping(record, "solve_tokens")
            ),
            eval_tokens=TokenCount.from_record(require_mapping(record, "eval_tokens")),
            total_tokens=TokenCount.from_record(
                require_mapping(record, "total_tokens")
            ),
            solve_cost=CostMeasurement.from_record(
                require_mapping(record, "solve_cost")
            ),
            eval_cost=CostMeasurement.from_record(require_mapping(record, "eval_cost")),
            combined_cost=CostMeasurement.from_record(
                require_mapping(record, "combined_cost")
            ),
            wall_elapsed_ms=_require_record_int(record, "wall_elapsed_ms"),
            summed_call_elapsed_ms=_optional_record_int(
                record,
                "summed_call_elapsed_ms",
            ),
            attempt_count=_require_record_int(record, "attempt_count"),
            retry_count=_require_record_int(record, "retry_count"),
            failure_count=_require_record_int(record, "failure_count"),
            schema_version=require_str(record, "schema_version"),
            kind=require_str(record, "kind"),
        )


def observation_sha256(observation: HarnessEfficiencyObservation) -> str:
    """Content-address the published observation with the artifact digest profile."""

    domain = SchemaIdentifier(HARNESS_EFFICIENCY_OBSERVATION_SCHEMA_VERSION)
    return str(
        ARTIFACT_PREFIXED_SHA256_V1.commit(
            observation.to_record(),
            domain=domain,
        ).digest
    )


def observation_from_receipts(
    receipts: Sequence[ExecutionReceipt],
    *,
    evaluation: EvaluationReceipt | None = None,
    cost_basis: str | None = None,
) -> HarnessEfficiencyObservation:
    """Build a published observation from one run's receipts."""

    unique = _unique_receipts(receipts)
    if not unique:
        raise AccountingError("efficiency observations require at least one receipt")
    run_keys = {receipt.run_identity_key for receipt in unique}
    if None in run_keys or len(run_keys) != 1:
        raise AccountingError(
            "efficiency observations require a single bound run_identity_key"
        )
    run_identity_key = next(iter(run_keys))
    assert run_identity_key is not None
    primary = unique[0]
    deliverable_hashes = {
        receipt.deliverable_manifest_sha256
        for receipt in unique
        if receipt.deliverable_manifest_sha256 is not None
    }
    deliverable_hash = (
        next(iter(deliverable_hashes)) if len(deliverable_hashes) == 1 else None
    )
    solve_tokens = combine_solve_tokens(unique)
    eval_tokens = (
        evaluation.token_usage.total_tokens
        if evaluation is not None
        else TokenCount(value=None, unknown_reason=UNKNOWN_NOT_REPORTED)
    )
    solve_cost = solve_cost_from_receipts(unique, cost_basis=cost_basis)
    eval_cost = evaluation.cost if evaluation is not None else _unknown_cost()
    summed_ms = None
    eval_hash = None
    if evaluation is not None:
        summed_ms = _ns_to_ms(evaluation.timing.summed_call_elapsed_ns)
        eval_hash = evaluation.receipt_sha256
    return HarnessEfficiencyObservation(
        run_identity_key=run_identity_key,
        execution_receipt_sha256=primary.public_sha256(),
        evaluation_receipt_sha256=eval_hash,
        deliverable_manifest_sha256=deliverable_hash,
        solve_tokens=solve_tokens,
        eval_tokens=eval_tokens,
        total_tokens=combine_token_counts(solve_tokens, eval_tokens),
        solve_cost=solve_cost,
        eval_cost=eval_cost,
        combined_cost=combine_costs(solve_cost, eval_cost),
        wall_elapsed_ms=sum(receipt.duration_ms for receipt in unique),
        summed_call_elapsed_ms=summed_ms,
        attempt_count=len(unique),
        retry_count=max(len(unique) - 1, 0),
        failure_count=sum(1 for receipt in unique if receipt.status != "succeeded"),
    )


def billed_solve_tokens(usage: Mapping[str, int]) -> TokenCount:
    """Return billed solver tokens without adding cache or reasoning on top."""

    if _SOLVE_TOTAL_KEY in usage:
        return TokenCount(value=usage[_SOLVE_TOTAL_KEY], unknown_reason=None)
    input_tokens = usage.get(_SOLVE_INPUT_KEY)
    output_tokens = usage.get(_SOLVE_OUTPUT_KEY)
    if input_tokens is None or output_tokens is None:
        if any(key in usage for key in _DIMENSION_KEYS):
            return TokenCount(value=None, unknown_reason=UNKNOWN_NOT_REPORTED)
        if not usage:
            return TokenCount(value=None, unknown_reason=UNKNOWN_NOT_REPORTED)
        return TokenCount(value=None, unknown_reason=UNKNOWN_NOT_REPORTED)
    return TokenCount(value=input_tokens + output_tokens, unknown_reason=None)


def combine_solve_tokens(receipts: Sequence[ExecutionReceipt]) -> TokenCount:
    """Sum billed solver tokens once per receipt_id."""

    total = 0
    for receipt in _unique_receipts(receipts):
        billed = billed_solve_tokens(receipt.usage)
        if billed.value is None:
            return TokenCount(value=None, unknown_reason=billed.unknown_reason)
        total += billed.value
    if not receipts:
        return TokenCount(value=None, unknown_reason=UNKNOWN_NOT_REPORTED)
    return TokenCount(value=total, unknown_reason=None)


def combine_token_counts(first: TokenCount, second: TokenCount) -> TokenCount:
    """Add two token counts, staying null if either side is unknown."""

    if first.value is None:
        return TokenCount(value=None, unknown_reason=first.unknown_reason)
    if second.value is None:
        return TokenCount(value=None, unknown_reason=second.unknown_reason)
    return TokenCount(value=first.value + second.value, unknown_reason=None)


def solve_cost_from_receipts(
    receipts: Sequence[ExecutionReceipt],
    *,
    cost_basis: str | None = None,
) -> CostMeasurement:
    """Publish solver cost without turning subscription-unallocable into $0."""

    basis = cost_basis or "provider_reported"
    if basis == "subscription_unallocable":
        amounts = [receipt.cost_usd for receipt in _unique_receipts(receipts)]
        if any(amount == 0 for amount in amounts):
            raise AccountingError(
                "subscription-unallocable cost must be null, never $0"
            )
        if any(amount is not None for amount in amounts):
            raise AccountingError(
                "subscription-unallocable cost must be null, never $0"
            )
        return CostMeasurement(
            amount_microusd=None,
            currency=None,
            basis="subscription_unallocable",
            pricing_snapshot_sha256=None,
            unknown_reason=UNKNOWN_SUBSCRIPTION,
        )
    micro_total = 0
    for receipt in _unique_receipts(receipts):
        if receipt.cost_usd is None:
            return _unknown_cost()
        micro_total += _usd_to_microusd(receipt.cost_usd)
    return CostMeasurement(
        amount_microusd=micro_total,
        currency="USD",
        basis=basis if basis in KNOWN_COST_BASES else "provider_reported",
        pricing_snapshot_sha256=None,
        unknown_reason=None,
    )


def combine_costs(first: CostMeasurement, second: CostMeasurement) -> CostMeasurement:
    """Sum costs only when bases and currencies are compatible."""

    if first.basis in NULL_COST_BASES:
        return first
    if second.basis in NULL_COST_BASES:
        return second
    require_compatible_cost_bases(first, second)
    assert first.amount_microusd is not None
    assert second.amount_microusd is not None
    basis = first.basis if first.basis == second.basis else "provider_reported"
    snapshot = first.pricing_snapshot_sha256
    if first.pricing_snapshot_sha256 != second.pricing_snapshot_sha256:
        snapshot = None
        if "estimated_from_pricing_snapshot" in {first.basis, second.basis}:
            basis = "provider_reported"
    return CostMeasurement(
        amount_microusd=first.amount_microusd + second.amount_microusd,
        currency=first.currency,
        basis=basis,
        pricing_snapshot_sha256=snapshot,
        unknown_reason=None,
    )


def require_compatible_cost_bases(
    first: CostMeasurement,
    second: CostMeasurement,
) -> None:
    """Refuse ratios or sums that mix incompatible cost bases or currencies."""

    if first.basis in NULL_COST_BASES or second.basis in NULL_COST_BASES:
        raise AccountingError(
            "cost ratios require known amounts; subscription-unallocable is never $0"
        )
    if first.currency != second.currency:
        raise AccountingError("cost ratios require a shared currency")
    bases = {first.basis, second.basis}
    if bases <= COMPATIBLE_RATIO_BASES:
        return
    if len(bases) == 1 and next(iter(bases)) in KNOWN_COST_BASES:
        return
    raise AccountingError(
        "cost ratios require compatible bases; estimated and metered costs "
        "cannot be mixed"
    )


def cost_ratio(numerator: CostMeasurement, denominator: CostMeasurement) -> Decimal:
    """Return numerator/denominator when both costs are ratio-compatible."""

    require_compatible_cost_bases(numerator, denominator)
    assert numerator.amount_microusd is not None
    assert denominator.amount_microusd is not None
    if denominator.amount_microusd == 0:
        raise AccountingError("cost ratio denominator must be a positive known amount")
    return Decimal(numerator.amount_microusd) / Decimal(denominator.amount_microusd)


def published_spread(
    values: Sequence[float],
    *,
    repeat_count: int,
) -> float | None:
    """Return sample stddev only when repeats exist. n=1 has no faux variance."""

    if repeat_count < 2 or len(values) < 2:
        return None
    mean = sum(values) / len(values)
    squared = sum((value - mean) ** 2 for value in values)
    return (squared / (len(values) - 1)) ** 0.5


def refuse_faux_variance(*, repeat_count: int, published_stddev: float | None) -> None:
    """Reject a published spread for a single observed repeat."""

    if repeat_count < 2 and published_stddev is not None:
        raise AccountingError("n=1 observations have no faux variance")


def clocks_may_differ(wall_elapsed_ms: int, summed_call_elapsed_ms: int | None) -> bool:
    """Wall-clock and summed call time are different accounting clocks."""

    if summed_call_elapsed_ms is None:
        return True
    return wall_elapsed_ms != summed_call_elapsed_ms


def refuse_collapsed_clocks(
    *,
    wall_elapsed_ms: int,
    summed_call_elapsed_ms: int | None,
    claimed_equal: bool,
) -> None:
    """Refuse a claim that wall-clock equals summed parallel time when they differ."""

    if claimed_equal and clocks_may_differ(wall_elapsed_ms, summed_call_elapsed_ms):
        if summed_call_elapsed_ms is None or wall_elapsed_ms != summed_call_elapsed_ms:
            raise AccountingError(
                "wall-clock and summed call time are distinct clocks and must "
                "not be published as equal"
            )


def _unique_receipts(
    receipts: Sequence[ExecutionReceipt],
) -> tuple[ExecutionReceipt, ...]:
    unique: list[ExecutionReceipt] = []
    seen: set[str] = set()
    for receipt in receipts:
        if receipt.receipt_id in seen:
            continue
        seen.add(receipt.receipt_id)
        unique.append(receipt)
    return tuple(unique)


def _unknown_cost() -> CostMeasurement:
    return CostMeasurement(
        amount_microusd=None,
        currency=None,
        basis="unknown",
        pricing_snapshot_sha256=None,
        unknown_reason=UNKNOWN_NOT_REPORTED,
    )


def _usd_to_microusd(amount: float) -> int:
    try:
        micro = (Decimal(str(amount)) * Decimal(1_000_000)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_EVEN,
        )
    except (InvalidOperation, ValueError) as exc:
        raise AccountingError("cost_usd must be a finite dollar amount") from exc
    if micro < 0:
        raise AccountingError("cost_usd must be non-negative")
    return int(micro)


def _ns_to_ms(value: int) -> int:
    return value // 1_000_000


def _reject_subscription_zero(cost: CostMeasurement) -> None:
    if cost.basis == "subscription_unallocable" and cost.amount_microusd is not None:
        raise AccountingError("subscription-unallocable cost must be null, never $0")


def _require_identity_key(value: str) -> None:
    if not value.startswith("sha256:") or len(value) != 71:
        raise AccountingError("run_identity_key must be a canonical prefixed SHA-256")
    validate_sha256(value, "run_identity_key")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise AccountingError(f"{field_name} must be a non-negative integer")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise AccountingError(f"{field_name} must be a positive integer")


def _require_record_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or isinstance(value, bool):
        raise AccountingError(f"{field_name} must be an integer")
    return value


def _optional_record_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if type(value) is not int or isinstance(value, bool):
        raise AccountingError(f"{field_name} must be an integer or null")
    return value


def _optional_digest(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AccountingError(f"{field_name} must be a digest or null")
    return value
