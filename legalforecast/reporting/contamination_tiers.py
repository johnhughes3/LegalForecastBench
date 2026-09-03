"""Contamination-tier classification, sidecar, drift, and report markers.

Reporting overlay only. Reuses eligibility cutoff fields and the cohort
eligibility_anchor; does not define a new authenticated schema family.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_sha256_digest
from legalforecast._record_validation import require_non_empty
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    TrainingCutoffStatus,
)

SIDECAR_KIND = "contamination_tier_sidecar"
PRELIMINARY_MARKER = "*"
PRELIMINARY_CAVEAT = (
    "Preliminary (non-contamination-resistant) result: the evaluated model's "
    "recorded training cutoff does not predate this cohort's contamination "
    "boundary, so the model theoretically could have seen these cases in training."
)
_SHA256_PREFIX = "sha256:"


class ContaminationTier(StrEnum):
    """Published contamination claim for one (model, cohort) pair."""

    RESISTANT = "contamination_resistant"
    PRELIMINARY = "preliminary"


class ContaminationTierReason(StrEnum):
    """Why a (model, cohort) pair received its contamination tier."""

    KNOWN_CUTOFF_PREDATES_BOUNDARY = "known_cutoff_predates_boundary"
    KNOWN_CUTOFF_DOES_NOT_PREDATE_BOUNDARY = "known_cutoff_does_not_predate_boundary"
    CUTOFF_NOT_KNOWN = "cutoff_not_known"


class ContaminationDriftError(ValueError):
    """Raised when a paired contamination-drift metric cannot be formed."""


@dataclass(frozen=True, slots=True)
class ContaminationTierDecision:
    """Classifier output for one model against one cohort boundary."""

    tier: ContaminationTier
    reason: ContaminationTierReason


@dataclass(frozen=True, slots=True)
class ContaminationTierRow:
    """One sidecar row: the non-authoritative tier flag for a model."""

    model_id: str
    contamination_tier: ContaminationTier
    classification_reason: ContaminationTierReason
    provider_training_cutoff_status: TrainingCutoffStatus
    provider_training_cutoff: date | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.model_id, "model_id")
        if (
            self.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN
            and self.provider_training_cutoff is None
        ):
            raise ValueError(
                "provider_training_cutoff is required when cutoff status is known"
            )
        if (
            self.provider_training_cutoff_status is not TrainingCutoffStatus.KNOWN
            and self.provider_training_cutoff is not None
        ):
            raise ValueError(
                "provider_training_cutoff must be omitted when cutoff status is "
                "not known"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "classification_reason": self.classification_reason.value,
            "contamination_tier": self.contamination_tier.value,
            "model_id": self.model_id,
            "provider_training_cutoff": (
                self.provider_training_cutoff.isoformat()
                if self.provider_training_cutoff is not None
                else None
            ),
            "provider_training_cutoff_status": (
                self.provider_training_cutoff_status.value
            ),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContaminationTierRow:
        cutoff_status = TrainingCutoffStatus(
            _required_str(record, "provider_training_cutoff_status")
        )
        cutoff_raw = record.get("provider_training_cutoff")
        cutoff: date | None
        if cutoff_raw is None:
            cutoff = None
        elif isinstance(cutoff_raw, str) and cutoff_raw.strip():
            cutoff = date.fromisoformat(cutoff_raw)
        else:
            raise ValueError("provider_training_cutoff must be an ISO date or null")
        return cls(
            model_id=_required_str(record, "model_id"),
            contamination_tier=ContaminationTier(
                _required_str(record, "contamination_tier")
            ),
            classification_reason=ContaminationTierReason(
                _required_str(record, "classification_reason")
            ),
            provider_training_cutoff_status=cutoff_status,
            provider_training_cutoff=cutoff,
        )


@dataclass(frozen=True, slots=True)
class ContaminationTierSidecar:
    """Non-authoritative overlay keyed by a frozen result digest."""

    result_digest: str
    cohort_id: str
    contamination_boundary: date
    rows: tuple[ContaminationTierRow, ...]
    kind: str = SIDECAR_KIND
    authoritative: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.cohort_id, "cohort_id")
        if self.kind != SIDECAR_KIND:
            raise ValueError(
                f"unsupported contamination-tier sidecar kind: {self.kind}"
            )
        if self.authoritative:
            raise ValueError("contamination-tier sidecar must not be authoritative")
        if not is_sha256_digest(self.result_digest, allow_prefix=True):
            raise ValueError("result_digest must be a sha256: hex digest")
        if not self.result_digest.startswith(_SHA256_PREFIX):
            raise ValueError("result_digest must use the sha256: prefix")
        if not self.rows:
            raise ValueError("contamination-tier sidecar requires at least one row")
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in self.rows:
            if row.model_id in seen:
                duplicates.add(row.model_id)
            seen.add(row.model_id)
        if duplicates:
            raise ValueError(
                "duplicate contamination-tier sidecar model_id values: "
                f"{sorted(duplicates)}"
            )

    def tier_by_model_id(self) -> dict[str, ContaminationTier]:
        return {row.model_id: row.contamination_tier for row in self.rows}

    def to_record(self) -> dict[str, Any]:
        return {
            "authoritative": False,
            "cohort_id": self.cohort_id,
            "contamination_boundary": self.contamination_boundary.isoformat(),
            "kind": SIDECAR_KIND,
            "result_digest": self.result_digest,
            "rows": [row.to_record() for row in self.rows],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContaminationTierSidecar:
        if "schema_version" in record:
            raise ValueError(
                "contamination-tier sidecar must not declare a schema_version family"
            )
        raw_rows = record.get("rows")
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, str | bytes):
            raise ValueError("contamination-tier sidecar rows must be an array")
        row_values = cast(Sequence[object], raw_rows)
        rows = tuple(
            ContaminationTierRow.from_record(_mapping_record(item, index))
            for index, item in enumerate(row_values)
        )
        return cls(
            result_digest=_required_str(record, "result_digest"),
            cohort_id=_required_str(record, "cohort_id"),
            contamination_boundary=date.fromisoformat(
                _required_str(record, "contamination_boundary")
            ),
            rows=rows,
            kind=_required_str(record, "kind"),
            authoritative=_required_false(record, "authoritative"),
        )


@dataclass(frozen=True, slots=True)
class ModelCohortScore:
    """One published headline score for drift pairing."""

    model_id: str
    cohort_id: str
    contamination_tier: ContaminationTier
    micro_brier: float
    result_digest: str

    def __post_init__(self) -> None:
        require_non_empty(self.model_id, "model_id")
        require_non_empty(self.cohort_id, "cohort_id")
        if not is_sha256_digest(self.result_digest, allow_prefix=True):
            raise ValueError("result_digest must be a sha256: hex digest")
        if not _finite_number(self.micro_brier):
            raise ValueError("micro_brier must be a finite number")


@dataclass(frozen=True, slots=True)
class ContaminationDrift:
    """Paired preliminary vs contamination-resistant micro-Brier delta."""

    model_id: str
    preliminary_cohort_id: str
    resistant_cohort_id: str
    preliminary_micro_brier: float
    resistant_micro_brier: float
    resistant_minus_preliminary_micro_brier: float
    preliminary_result_digest: str
    resistant_result_digest: str

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "preliminary_cohort_id": self.preliminary_cohort_id,
            "preliminary_micro_brier": self.preliminary_micro_brier,
            "preliminary_result_digest": self.preliminary_result_digest,
            "resistant_cohort_id": self.resistant_cohort_id,
            "resistant_micro_brier": self.resistant_micro_brier,
            "resistant_minus_preliminary_micro_brier": (
                self.resistant_minus_preliminary_micro_brier
            ),
            "resistant_result_digest": self.resistant_result_digest,
        }


def classify_contamination_tier(
    *,
    provider_training_cutoff_status: TrainingCutoffStatus,
    provider_training_cutoff: date | None,
    contamination_boundary: date,
) -> ContaminationTierDecision:
    """Classify one model against one cohort contamination boundary."""

    if provider_training_cutoff_status is TrainingCutoffStatus.KNOWN:
        if provider_training_cutoff is None:
            raise ValueError(
                "provider_training_cutoff is required when cutoff status is known"
            )
        if provider_training_cutoff < contamination_boundary:
            return ContaminationTierDecision(
                tier=ContaminationTier.RESISTANT,
                reason=ContaminationTierReason.KNOWN_CUTOFF_PREDATES_BOUNDARY,
            )
        return ContaminationTierDecision(
            tier=ContaminationTier.PRELIMINARY,
            reason=ContaminationTierReason.KNOWN_CUTOFF_DOES_NOT_PREDATE_BOUNDARY,
        )
    if provider_training_cutoff is not None:
        raise ValueError(
            "provider_training_cutoff must be omitted when cutoff status is not known"
        )
    return ContaminationTierDecision(
        tier=ContaminationTier.PRELIMINARY,
        reason=ContaminationTierReason.CUTOFF_NOT_KNOWN,
    )


def classify_registry_entry(
    entry: ModelRegistryEntry,
    *,
    contamination_boundary: date,
) -> ContaminationTierDecision:
    """Classify a frozen registry entry against a cohort eligibility_anchor."""

    return classify_contamination_tier(
        provider_training_cutoff_status=entry.provider_training_cutoff_status,
        provider_training_cutoff=entry.provider_training_cutoff,
        contamination_boundary=contamination_boundary,
    )


def classify_leaderboard_models(
    model_ids: Sequence[str],
    *,
    registry: ModelRegistry,
    contamination_boundary: date,
) -> dict[str, ContaminationTier]:
    """Map evaluated leaderboard model ids onto contamination tiers."""

    by_model_id = {entry.model_id: entry for entry in registry.entries}
    by_registry_key = {entry.registry_key: entry for entry in registry.entries}
    by_display_name = {entry.display_name: entry for entry in registry.entries}
    tiers: dict[str, ContaminationTier] = {}
    for model_id in model_ids:
        require_non_empty(model_id, "model_id")
        entry = (
            by_model_id.get(model_id)
            or by_registry_key.get(model_id)
            or by_display_name.get(model_id)
        )
        if entry is None:
            raise ValueError(f"no registry entry for leaderboard model_id {model_id}")
        tiers[model_id] = classify_registry_entry(
            entry,
            contamination_boundary=contamination_boundary,
        ).tier
    return tiers


def frozen_result_digest(payload: bytes) -> str:
    """Return the sha256: key that binds a sidecar to already-frozen result bytes."""

    return _SHA256_PREFIX + hashlib.sha256(payload).hexdigest()


def build_contamination_tier_sidecar(
    *,
    result_digest: str,
    cohort_id: str,
    contamination_boundary: date,
    rows: Sequence[ContaminationTierRow],
) -> ContaminationTierSidecar:
    """Build a non-authoritative sidecar for one frozen result digest."""

    ordered = tuple(sorted(rows, key=lambda row: row.model_id))
    return ContaminationTierSidecar(
        result_digest=result_digest,
        cohort_id=cohort_id,
        contamination_boundary=contamination_boundary,
        rows=ordered,
    )


def sidecar_rows_from_registry(
    model_ids: Sequence[str],
    *,
    registry: ModelRegistry,
    contamination_boundary: date,
) -> tuple[ContaminationTierRow, ...]:
    """Build sidecar rows from registry cutoff fields for the named models."""

    by_model_id = {entry.model_id: entry for entry in registry.entries}
    by_registry_key = {entry.registry_key: entry for entry in registry.entries}
    by_display_name = {entry.display_name: entry for entry in registry.entries}
    rows: list[ContaminationTierRow] = []
    for model_id in model_ids:
        require_non_empty(model_id, "model_id")
        entry = (
            by_model_id.get(model_id)
            or by_registry_key.get(model_id)
            or by_display_name.get(model_id)
        )
        if entry is None:
            raise ValueError(f"no registry entry for leaderboard model_id {model_id}")
        decision = classify_registry_entry(
            entry,
            contamination_boundary=contamination_boundary,
        )
        rows.append(
            ContaminationTierRow(
                model_id=model_id,
                contamination_tier=decision.tier,
                classification_reason=decision.reason,
                provider_training_cutoff_status=entry.provider_training_cutoff_status,
                provider_training_cutoff=entry.provider_training_cutoff,
            )
        )
    return tuple(rows)


def write_contamination_tier_sidecar(
    path: Path,
    sidecar: ContaminationTierSidecar,
) -> None:
    """Write the sidecar as non-canonical reporting JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sidecar.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_contamination_tier_sidecar(
    path: Path,
    *,
    expected_digest: str,
) -> ContaminationTierSidecar:
    """Load a sidecar and fail closed unless it matches the frozen result digest."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("contamination-tier sidecar must be a JSON object")
    sidecar = ContaminationTierSidecar.from_record(cast(Mapping[str, Any], payload))
    if sidecar.result_digest != expected_digest:
        raise ValueError("contamination-tier sidecar result_digest does not match")
    return sidecar


def reported_model_label(
    model_id: str,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> str:
    """Return the public model label, with an asterisk iff the row is preliminary."""

    require_non_empty(model_id, "model_id")
    if contamination_tiers is None:
        return model_id
    tier = contamination_tiers.get(model_id)
    if tier is ContaminationTier.PRELIMINARY:
        return f"{model_id}{PRELIMINARY_MARKER}"
    return model_id


def preliminary_caveat_if_needed(
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> str | None:
    """Return the standard caveat when any annotated row is preliminary."""

    if contamination_tiers is None:
        return None
    if any(
        tier is ContaminationTier.PRELIMINARY for tier in contamination_tiers.values()
    ):
        return PRELIMINARY_CAVEAT
    return None


def compute_contamination_drift(
    first: ModelCohortScore,
    second: ModelCohortScore,
) -> ContaminationDrift:
    """Emit the paired delta when both contamination tiers exist for one model."""

    if first.model_id != second.model_id:
        raise ContaminationDriftError("contamination drift requires the same model_id")
    if first.cohort_id == second.cohort_id:
        raise ContaminationDriftError(
            "contamination drift requires two different cohort identities"
        )
    by_tier = {
        first.contamination_tier: first,
        second.contamination_tier: second,
    }
    if len(by_tier) != 2:
        raise ContaminationDriftError(
            "contamination drift requires one preliminary score and one "
            "contamination-resistant score"
        )
    preliminary = by_tier.get(ContaminationTier.PRELIMINARY)
    resistant = by_tier.get(ContaminationTier.RESISTANT)
    if preliminary is None or resistant is None:
        raise ContaminationDriftError(
            "contamination drift requires one preliminary score and one "
            "contamination-resistant score"
        )
    delta = resistant.micro_brier - preliminary.micro_brier
    return ContaminationDrift(
        model_id=first.model_id,
        preliminary_cohort_id=preliminary.cohort_id,
        resistant_cohort_id=resistant.cohort_id,
        preliminary_micro_brier=preliminary.micro_brier,
        resistant_micro_brier=resistant.micro_brier,
        resistant_minus_preliminary_micro_brier=delta,
        preliminary_result_digest=preliminary.result_digest,
        resistant_result_digest=resistant.result_digest,
    )


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_false(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if value is not False:
        raise ValueError(f"{field_name} must be false")
    return False


def _mapping_record(value: object, index: int) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"contamination-tier sidecar row {index} must be an object")
    return cast(Mapping[str, Any], value)


def _finite_number(value: float) -> bool:
    return isfinite(value)
