"""Typed knobs for one acquisition/selection cycle.

Every field is documented at its definition. Values are validated when a
``CycleConfig`` is constructed (including at import of the registered cycle
modules). This package is the blessed home for post-Cycle-1 knobs; it is not
authoritative for any frozen Cycle 1 path.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.config.errors import CycleConfigError

CYCLE_1_ID = "cycle-1"
CYCLE_2_ID = "cycle-2"

_CYCLE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_USD_QUANTUM = Decimal("0.01")
_SHARE_QUANTUM = Decimal("0.0001")
_MUTABLE_ALIAS_MARKERS = ("preview", "latest")


class DocumentNeedBucket(StrEnum):
    """Pass-1/pass-2 inclusion bucket for one docket entry."""

    CLEARLY_REQUIRED = "clearly_required"
    CONDITIONAL = "conditional"
    CLEARLY_NOT_REQUIRED = "clearly_not_required"


class SortDirection(StrEnum):
    """Sort direction for one ranking key."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


def usd(value: str) -> Decimal:
    """Parse a non-negative USD amount with cent precision."""

    return _decimal(value, quantum=_USD_QUANTUM, field_name="usd")


def usd_text(value: Decimal) -> str:
    """Render a validated USD amount as a two-decimal string."""

    quantized = _require_quantized(value, quantum=_USD_QUANTUM, field_name="usd")
    return format(quantized, "f")


@dataclass(frozen=True, slots=True)
class SelectorModel:
    """Exact callable identity for one selector (primary or alternate).

    ``registry_key`` is ``provider:model_id``, matching evaluation-registry
    entries. ``model_version_or_snapshot`` is the pinned callable ID, never a
    mutable ``latest`` alias.
    """

    provider: str
    model_id: str
    model_version_or_snapshot: str

    def __post_init__(self) -> None:
        _require_token(self.provider, "provider")
        _require_token(self.model_id, "model_id")
        _require_token(self.model_version_or_snapshot, "model_version_or_snapshot")
        _reject_mutable_alias(self.model_id, "model_id")
        _reject_mutable_alias(
            self.model_version_or_snapshot, "model_version_or_snapshot"
        )

    @property
    def registry_key(self) -> str:
        return f"{self.provider}:{self.model_id}"


@dataclass(frozen=True, slots=True)
class SelectorModelPolicy:
    """Ordered selector-model policy for one cycle.

    Selection entrypoints try ``primary`` first, then ``alternates`` in order.
    The registry preflight checks every identity in this policy against the
    same cycle config's evaluation-registry pin — no side-channel lookup.
    """

    primary: SelectorModel
    alternates: tuple[SelectorModel, ...]

    def __post_init__(self) -> None:
        keys = tuple(model.registry_key for model in self.all_models())
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise CycleConfigError(
                f"selector-model policy has duplicate registry keys: {duplicates}"
            )

    def all_models(self) -> tuple[SelectorModel, ...]:
        return (self.primary, *self.alternates)


@dataclass(frozen=True, slots=True)
class EvaluationRegistryPin:
    """Path (and optional raw SHA-256) of this cycle's evaluated-model registry.

    Both selector policy and this pin live on the same ``CycleConfig``. Preflight
    reads the registry only through this pin.
    """

    path: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.path, "evaluation_registry.path")
        if self.sha256 is not None and not is_lowercase_sha256(self.sha256):
            raise CycleConfigError(
                "evaluation_registry.sha256 must be a lowercase SHA-256 hex digest"
            )


@dataclass(frozen=True, slots=True)
class PerDocumentPriceCap:
    """PACER page price, per-document cap, and conservative reservation.

    Cycle 1 live paths keep reading their existing constants; this object
    documents those values for later cycles.
    """

    pacer_page_usd: Decimal
    pacer_document_cap_usd: Decimal
    reservation_usd: Decimal
    includes_pacer_fees: bool
    includes_service_fees: bool
    includes_rounding: bool

    def __post_init__(self) -> None:
        page = _require_usd(self.pacer_page_usd, "pacer_page_usd")
        cap = _require_usd(self.pacer_document_cap_usd, "pacer_document_cap_usd")
        reservation = _require_usd(self.reservation_usd, "reservation_usd")
        if page > cap:
            raise CycleConfigError(
                "pacer_page_usd must not exceed pacer_document_cap_usd"
            )
        if cap > reservation:
            raise CycleConfigError(
                "pacer_document_cap_usd must not exceed reservation_usd"
            )


@dataclass(frozen=True, slots=True)
class FreeFirstPolicy:
    """Whether paid acquisition may run only after free recovery is exhausted."""

    required: bool
    paid_only_after_free_exhausted: bool

    def __post_init__(self) -> None:
        if self.required and not self.paid_only_after_free_exhausted:
            raise CycleConfigError(
                "free-first policy cannot require free-first while allowing paid "
                "acquisition before free recovery is exhausted"
            )


@dataclass(frozen=True, slots=True)
class CohortPolicyPin:
    """Version pin for the cohort-policy schema this cycle will freeze.

    Cycle 1's live freeze still authenticates the committed policy artifact;
    this pin is documentary for Cycle 1 and the draft pin for later cycles.
    """

    schema_version: str
    provenance_path: str | None = None
    policy_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.schema_version, "cohort_policy.schema_version")
        if self.policy_sha256 is not None and not is_lowercase_sha256(
            self.policy_sha256
        ):
            raise CycleConfigError(
                "cohort_policy.policy_sha256 must be a lowercase SHA-256 hex digest"
            )


@dataclass(frozen=True, slots=True)
class DocumentNeedBucketDefinitions:
    """Inclusion-bucket semantics consumed by the document-need estimator (dn9.1)."""

    clearly_required: str
    conditional: str
    clearly_not_required: str

    def __post_init__(self) -> None:
        _require_token(self.clearly_required, "document_need_buckets.clearly_required")
        _require_token(self.conditional, "document_need_buckets.conditional")
        _require_token(
            self.clearly_not_required, "document_need_buckets.clearly_not_required"
        )

    def text_for(self, bucket: DocumentNeedBucket) -> str:
        if bucket is DocumentNeedBucket.CLEARLY_REQUIRED:
            return self.clearly_required
        if bucket is DocumentNeedBucket.CONDITIONAL:
            return self.conditional
        return self.clearly_not_required


@dataclass(frozen=True, slots=True)
class RankingSortKey:
    """One attribute in the deterministic ranking tuple."""

    attribute: str
    direction: SortDirection = SortDirection.ASCENDING

    def __post_init__(self) -> None:
        _require_token(self.attribute, "ranking.attribute")


@dataclass(frozen=True, slots=True)
class RankingTiebreakPolicy:
    """Ordered ranking keys plus the purchase/admission rule name.

    Post-Cycle-1 cheapest-first admission ranks by ``max_cost`` then documented
    tiebreaks. Cycle 1 documents the live ``missing_core_document_count`` /
    ``estimated_cost_usd`` / ``candidate_id`` key instead of becoming
    authoritative for that frozen path.
    """

    keys: tuple[RankingSortKey, ...]
    purchase_rule: str
    ranking_policy_version: str
    record_cost_rank_in_provenance: bool

    def __post_init__(self) -> None:
        if not self.keys:
            raise CycleConfigError("ranking.keys must contain at least one sort key")
        attributes = tuple(key.attribute for key in self.keys)
        duplicates = sorted({name for name in attributes if attributes.count(name) > 1})
        if duplicates:
            raise CycleConfigError(
                f"ranking.keys has duplicate attributes: {duplicates}"
            )
        _require_token(self.purchase_rule, "ranking.purchase_rule")
        _require_token(self.ranking_policy_version, "ranking.ranking_policy_version")


@dataclass(frozen=True, slots=True)
class StratificationPolicy:
    """Optional case-mix guardrail on cheapest-first admission.

    Off by default. When enabled, admission may not let the bottom cost-decile
    exceed ``bottom_decile_share_cap`` of the admitted set. John accepts or
    declines this at selection time (dn9.1).
    """

    enabled: bool
    bottom_decile_share_cap: Decimal

    def __post_init__(self) -> None:
        cap = _decimal_value(
            self.bottom_decile_share_cap,
            quantum=_SHARE_QUANTUM,
            field_name="stratification.bottom_decile_share_cap",
        )
        if cap < Decimal("0") or cap > Decimal("1"):
            raise CycleConfigError(
                "stratification.bottom_decile_share_cap must be in [0, 1]"
            )


@dataclass(frozen=True, slots=True)
class SpendCeiling:
    """Aggregate and per-case spend ceilings for one cycle.

    ``None`` means the ceiling is not yet committed (draft cycles). Cycle 1
    documents the live exact-100 figures without becoming the freeze authority.
    """

    hard_cap_usd: Decimal | None
    max_per_case_usd: Decimal | None

    def __post_init__(self) -> None:
        hard = _optional_usd(self.hard_cap_usd, "spend.hard_cap_usd")
        per_case = _optional_usd(self.max_per_case_usd, "spend.max_per_case_usd")
        if hard is not None and per_case is not None and per_case > hard:
            raise CycleConfigError("max_per_case_usd must not exceed hard_cap_usd")


@dataclass(frozen=True, slots=True)
class TypedConfirmationParams:
    """Typed-confirmation phrase parameters for purchase-authority decisions.

    Cycle 1's live phrase is built by
    ``PurchaseApprovalRequest.required_confirmation``; this records the shape
    so later cycles do not invent a second confirmation dialect.
    """

    decisions: tuple[str, ...]
    phrase_template: str
    session_scope_token: str

    def __post_init__(self) -> None:
        if not self.decisions:
            raise CycleConfigError("typed_confirmation.decisions must not be empty")
        seen: set[str] = set()
        for decision in self.decisions:
            token = _require_token(decision, "typed_confirmation.decision")
            if token != token.lower() or token in seen:
                raise CycleConfigError(
                    "typed_confirmation.decisions must be unique lowercase tokens"
                )
            seen.add(token)
        _require_token(self.phrase_template, "typed_confirmation.phrase_template")
        _require_token(
            self.session_scope_token, "typed_confirmation.session_scope_token"
        )


@dataclass(frozen=True, slots=True)
class RetryQueueLagTolerances:
    """Retry and RECAP Fetch queue-lag tolerances for one cycle."""

    recap_fetch_poll_attempts: int
    recap_fetch_poll_backoff_seconds: float
    courtlistener_request_budget_max_wait_seconds: float
    disclosure_review_max_attempts: int
    disclosure_review_failure_window_seconds: int
    live_model_retry_backoff_seconds: float

    def __post_init__(self) -> None:
        _require_positive_int(
            self.recap_fetch_poll_attempts, "retry.recap_fetch_poll_attempts"
        )
        _require_non_negative_float(
            self.recap_fetch_poll_backoff_seconds,
            "retry.recap_fetch_poll_backoff_seconds",
        )
        _require_non_negative_float(
            self.courtlistener_request_budget_max_wait_seconds,
            "retry.courtlistener_request_budget_max_wait_seconds",
        )
        _require_positive_int(
            self.disclosure_review_max_attempts, "retry.disclosure_review_max_attempts"
        )
        _require_positive_int(
            self.disclosure_review_failure_window_seconds,
            "retry.disclosure_review_failure_window_seconds",
        )
        _require_non_negative_float(
            self.live_model_retry_backoff_seconds,
            "retry.live_model_retry_backoff_seconds",
        )


@dataclass(frozen=True, slots=True)
class LegacyPointer:
    """Where a Cycle 1 live value actually lives (frozen paths stay there)."""

    knob: str
    location: str
    note: str

    def __post_init__(self) -> None:
        _require_token(self.knob, "pointer.knob")
        _require_token(self.location, "pointer.location")
        _require_token(self.note, "pointer.note")


@dataclass(frozen=True, slots=True)
class CycleConfig:
    """Declarative acquisition/selection config for exactly one cycle.

    ``activated`` is the live-path gate: ``load_activated_cycle`` refuses any
    config with ``activated=False``. Cycle 1 is legacy-pinned and not
    activated. Cycle 2 is a draft and not activated until ``dn9.2`` clears.
    """

    cycle_id: str
    activated: bool
    legacy_pinned: bool
    activation_blocker: str | None
    evaluation_registry: EvaluationRegistryPin
    selector_model_policy: SelectorModelPolicy
    per_document_price_cap: PerDocumentPriceCap
    free_first: FreeFirstPolicy
    cohort_policy: CohortPolicyPin
    document_need_buckets: DocumentNeedBucketDefinitions
    ranking: RankingTiebreakPolicy
    stratification: StratificationPolicy
    spend: SpendCeiling
    typed_confirmation: TypedConfirmationParams
    retry_queue_lag: RetryQueueLagTolerances
    pointers: tuple[LegacyPointer, ...] = ()
    eligibility_anchor: str | None = None
    acquisition_cycle_id: str | None = None

    def __post_init__(self) -> None:
        if _CYCLE_ID.fullmatch(self.cycle_id) is None:
            raise CycleConfigError(
                "cycle_id must be a lowercase identifier of hyphenated tokens"
            )
        if self.legacy_pinned and self.activated:
            raise CycleConfigError(
                f"{self.cycle_id} is legacy-pinned and cannot be activated; "
                "frozen Cycle 1 paths keep reading their existing constants"
            )
        if self.activated and self.activation_blocker:
            raise CycleConfigError(
                f"{self.cycle_id} cannot be activated while blocked: "
                f"{self.activation_blocker}"
            )
        if not self.activated and not self.activation_blocker:
            raise CycleConfigError(
                f"{self.cycle_id} is inert and must name an activation_blocker"
            )
        if self.activated and (
            self.spend.hard_cap_usd is None or self.spend.max_per_case_usd is None
        ):
            raise CycleConfigError(
                f"{self.cycle_id} cannot be activated until spend.hard_cap_usd "
                "and spend.max_per_case_usd are committed"
            )
        if self.eligibility_anchor is not None:
            _require_token(self.eligibility_anchor, "eligibility_anchor")
        if self.acquisition_cycle_id is not None:
            _require_token(self.acquisition_cycle_id, "acquisition_cycle_id")

    def as_public_record(self) -> Mapping[str, object]:
        """Return a JSON-friendly snapshot for docs and selection artifacts."""

        return {
            "cycle_id": self.cycle_id,
            "activated": self.activated,
            "legacy_pinned": self.legacy_pinned,
            "activation_blocker": self.activation_blocker,
            "eligibility_anchor": self.eligibility_anchor,
            "acquisition_cycle_id": self.acquisition_cycle_id,
            "evaluation_registry": {
                "path": self.evaluation_registry.path,
                "sha256": self.evaluation_registry.sha256,
            },
            "selector_model_policy": {
                "primary": _model_record(self.selector_model_policy.primary),
                "alternates": [
                    _model_record(model)
                    for model in self.selector_model_policy.alternates
                ],
            },
            "per_document_price_cap": {
                "pacer_page_usd": usd_text(self.per_document_price_cap.pacer_page_usd),
                "pacer_document_cap_usd": usd_text(
                    self.per_document_price_cap.pacer_document_cap_usd
                ),
                "reservation_usd": usd_text(
                    self.per_document_price_cap.reservation_usd
                ),
                "includes_pacer_fees": self.per_document_price_cap.includes_pacer_fees,
                "includes_service_fees": (
                    self.per_document_price_cap.includes_service_fees
                ),
                "includes_rounding": self.per_document_price_cap.includes_rounding,
            },
            "free_first": {
                "required": self.free_first.required,
                "paid_only_after_free_exhausted": (
                    self.free_first.paid_only_after_free_exhausted
                ),
            },
            "cohort_policy": {
                "schema_version": self.cohort_policy.schema_version,
                "provenance_path": self.cohort_policy.provenance_path,
                "policy_sha256": self.cohort_policy.policy_sha256,
            },
            "document_need_buckets": {
                "clearly_required": self.document_need_buckets.clearly_required,
                "conditional": self.document_need_buckets.conditional,
                "clearly_not_required": self.document_need_buckets.clearly_not_required,
            },
            "ranking": {
                "keys": [
                    {"attribute": key.attribute, "direction": key.direction.value}
                    for key in self.ranking.keys
                ],
                "purchase_rule": self.ranking.purchase_rule,
                "ranking_policy_version": self.ranking.ranking_policy_version,
                "record_cost_rank_in_provenance": (
                    self.ranking.record_cost_rank_in_provenance
                ),
            },
            "stratification": {
                "enabled": self.stratification.enabled,
                "bottom_decile_share_cap": format(
                    self.stratification.bottom_decile_share_cap, "f"
                ),
            },
            "spend": {
                "hard_cap_usd": _optional_usd_text(self.spend.hard_cap_usd),
                "max_per_case_usd": _optional_usd_text(self.spend.max_per_case_usd),
            },
            "typed_confirmation": {
                "decisions": list(self.typed_confirmation.decisions),
                "phrase_template": self.typed_confirmation.phrase_template,
                "session_scope_token": self.typed_confirmation.session_scope_token,
            },
            "retry_queue_lag": {
                "recap_fetch_poll_attempts": (
                    self.retry_queue_lag.recap_fetch_poll_attempts
                ),
                "recap_fetch_poll_backoff_seconds": (
                    self.retry_queue_lag.recap_fetch_poll_backoff_seconds
                ),
                "courtlistener_request_budget_max_wait_seconds": (
                    self.retry_queue_lag.courtlistener_request_budget_max_wait_seconds
                ),
                "disclosure_review_max_attempts": (
                    self.retry_queue_lag.disclosure_review_max_attempts
                ),
                "disclosure_review_failure_window_seconds": (
                    self.retry_queue_lag.disclosure_review_failure_window_seconds
                ),
                "live_model_retry_backoff_seconds": (
                    self.retry_queue_lag.live_model_retry_backoff_seconds
                ),
            },
        }


def _model_record(model: SelectorModel) -> dict[str, str]:
    return {
        "provider": model.provider,
        "model_id": model.model_id,
        "model_version_or_snapshot": model.model_version_or_snapshot,
        "registry_key": model.registry_key,
    }


def _require_token(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise CycleConfigError(f"{field_name} must be a non-empty string")
    return stripped


def _reject_mutable_alias(value: str, field_name: str) -> None:
    lowered = value.lower()
    if any(marker in lowered for marker in _MUTABLE_ALIAS_MARKERS):
        raise CycleConfigError(
            f"{field_name} must be a pinned callable ID, not a mutable "
            f"preview/latest alias: {value!r}"
        )


def _require_positive_int(value: int, field_name: str) -> int:
    if type(value) is not int or value < 1:
        raise CycleConfigError(f"{field_name} must be a positive integer")
    return value


def _require_non_negative_float(value: float, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise CycleConfigError(f"{field_name} must be a non-negative finite number")
    return number


def _decimal(value: str, *, quantum: Decimal, field_name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise CycleConfigError(f"{field_name} must be a decimal string") from exc
    return _require_quantized(parsed, quantum=quantum, field_name=field_name)


def _decimal_value(value: Decimal, *, quantum: Decimal, field_name: str) -> Decimal:
    return _require_quantized(value, quantum=quantum, field_name=field_name)


def _require_usd(value: Decimal, field_name: str) -> Decimal:
    amount = _require_quantized(value, quantum=_USD_QUANTUM, field_name=field_name)
    if amount < Decimal("0.00"):
        raise CycleConfigError(f"{field_name} must be non-negative")
    return amount


def _optional_usd(value: Decimal | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _require_usd(value, field_name)


def _optional_usd_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return usd_text(value)


def _require_quantized(value: Decimal, *, quantum: Decimal, field_name: str) -> Decimal:
    if not value.is_finite():
        raise CycleConfigError(f"{field_name} must be a finite decimal")
    if value != value.quantize(quantum):
        raise CycleConfigError(f"{field_name} must have precision {quantum}")
    return value
