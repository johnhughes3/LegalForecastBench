"""Frozen-unit repair and exclusion workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)
from legalforecast.unitization.construct_units import (
    StageAConstructionInput,
    StageAConstructionResult,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    construct_stage_a_units,
)
from legalforecast.unitization.schemas import PredictionUnit


class FrozenUnitStatus(StrEnum):
    FROZEN_CLEAN = "frozen_clean"
    REPAIRED = "repaired"
    EXCLUDED = "excluded"


class UnitRepairMethod(StrEnum):
    BLINDED_PREDECISION_ADJUDICATOR = "blinded_predecision_adjudicator"


class UnitRepairReason(StrEnum):
    MATERIAL_UNIT_MISSING_FROM_STAGE_A = "material_unit_missing_from_stage_a"


@dataclass(frozen=True, slots=True)
class BlindedUnitRepairRequest:
    """Repair request visible only to a pre-decision unitization adjudicator."""

    candidate_id: str
    case_id: str
    frozen_units: tuple[PredictionUnit, ...]
    predecision_source_documents: tuple[StageASourceDocument, ...]
    repair_unit_seeds: tuple[StageAUnitSeed, ...]
    missing_unit_description: str
    decision_source_ids: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if not self.frozen_units:
            raise ValueError("frozen_units must not be empty")
        if not self.repair_unit_seeds:
            raise ValueError("repair_unit_seeds must not be empty")
        _require_non_empty(self.missing_unit_description, "missing_unit_description")
        if self.notes is not None:
            _require_non_empty(self.notes, "notes")
        if self.decision_source_ids:
            raise ValueError("blinded repair must not receive decision materials")
        _validate_predecision_sources(self.predecision_source_documents)

    def stage_a_input(self) -> StageAConstructionInput:
        return StageAConstructionInput(
            candidate_id=self.candidate_id,
            case_id=self.case_id,
            source_documents=self.predecision_source_documents,
            unit_seeds=self.repair_unit_seeds,
            metadata={
                "repair_reason": (
                    UnitRepairReason.MATERIAL_UNIT_MISSING_FROM_STAGE_A.value
                )
            },
        )


@dataclass(frozen=True, slots=True)
class FrozenUnitRepairResult:
    """Manifest-facing status after frozen-unit review."""

    candidate_id: str
    case_id: str
    status: FrozenUnitStatus
    units: tuple[PredictionUnit, ...]
    unit_missing_from_stage_a: bool = False
    unitization_repaired: bool = False
    repair_method: UnitRepairMethod | None = None
    repair_reason: UnitRepairReason | None = None
    repair_notes: str | None = None
    exclusion_entry: ExclusionLedgerEntry | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if not self.units and self.status is not FrozenUnitStatus.EXCLUDED:
            raise ValueError("non-excluded repair results must include units")
        if self.status is FrozenUnitStatus.REPAIRED:
            if not self.unit_missing_from_stage_a or not self.unitization_repaired:
                raise ValueError("repaired results must set repair flags")
            if self.repair_method is None or self.repair_reason is None:
                raise ValueError("repaired results require method and reason")
        if self.status is FrozenUnitStatus.EXCLUDED and self.exclusion_entry is None:
            raise ValueError("excluded results require an exclusion_entry")
        if self.status is FrozenUnitStatus.FROZEN_CLEAN:
            if self.unit_missing_from_stage_a or self.unitization_repaired:
                raise ValueError("clean frozen results must not set repair flags")

    @property
    def is_scored(self) -> bool:
        return self.status is not FrozenUnitStatus.EXCLUDED

    def to_manifest_fields(self) -> dict[str, Any]:
        return {
            "frozen_unit_status": self.status.value,
            "unit_missing_from_stage_a": self.unit_missing_from_stage_a,
            "unitization_repaired": self.unitization_repaired,
            "repair_method": (
                self.repair_method.value if self.repair_method is not None else None
            ),
            "repair_reason": (
                self.repair_reason.value if self.repair_reason is not None else None
            ),
            "repair_notes": self.repair_notes,
            "is_scored": self.is_scored,
            "unit_ids": [unit.unit_id for unit in self.units],
            "exclusion": (
                self.exclusion_entry.to_record()
                if self.exclusion_entry is not None
                else None
            ),
        }


def freeze_stage_a_units(result: StageAConstructionResult) -> FrozenUnitRepairResult:
    """Mark Stage A units as frozen before any decision-stage labeling."""

    return FrozenUnitRepairResult(
        candidate_id=result.candidate_id,
        case_id=result.case_id,
        status=FrozenUnitStatus.FROZEN_CLEAN,
        units=result.units,
    )


def repair_frozen_units(
    request: BlindedUnitRepairRequest,
) -> FrozenUnitRepairResult:
    """Repair missing Stage A units using only pre-decision source materials."""

    repair_result = construct_stage_a_units(request.stage_a_input())
    units = (*request.frozen_units, *repair_result.units)
    _require_unique_unit_ids(units)
    return FrozenUnitRepairResult(
        candidate_id=request.candidate_id,
        case_id=request.case_id,
        status=FrozenUnitStatus.REPAIRED,
        units=units,
        unit_missing_from_stage_a=True,
        unitization_repaired=True,
        repair_method=UnitRepairMethod.BLINDED_PREDECISION_ADJUDICATOR,
        repair_reason=UnitRepairReason.MATERIAL_UNIT_MISSING_FROM_STAGE_A,
        repair_notes=request.notes or request.missing_unit_description,
    )


def exclude_for_missing_stage_a_unit(
    *,
    candidate_id: str,
    case_id: str,
    frozen_units: tuple[PredictionUnit, ...],
    source_entry_ids: tuple[str, ...],
    source_document_ids: tuple[str, ...],
    notes: str,
    court: str | None = None,
    decision_date: date | None = None,
) -> FrozenUnitRepairResult:
    """Exclude a case when missing units cannot be repaired blind."""

    exclusion = ExclusionLedgerEntry(
        candidate_id=candidate_id,
        case_id=case_id,
        court=court,
        decision_date=decision_date,
        stage=ExclusionStage.UNITIZATION,
        reason=ExclusionReason.UNIT_MISSING_FROM_STAGE_A.value,
        source_entry_ids=source_entry_ids,
        source_document_ids=source_document_ids,
        notes=notes,
    )
    return FrozenUnitRepairResult(
        candidate_id=candidate_id,
        case_id=case_id,
        status=FrozenUnitStatus.EXCLUDED,
        units=frozen_units,
        unit_missing_from_stage_a=True,
        exclusion_entry=exclusion,
        repair_reason=UnitRepairReason.MATERIAL_UNIT_MISSING_FROM_STAGE_A,
        repair_notes=notes,
    )


def _validate_predecision_sources(
    source_documents: tuple[StageASourceDocument, ...],
) -> None:
    if not source_documents:
        raise ValueError("predecision_source_documents must not be empty")
    for document in source_documents:
        if document.role in {StageADocumentRole.DECISION, StageADocumentRole.ORDER}:
            raise ValueError("blinded repair must receive only pre-decision materials")
        if not document.is_predecision_material or document.contains_target_outcome:
            raise ValueError("blinded repair must receive only pre-decision materials")


def _require_unique_unit_ids(units: tuple[PredictionUnit, ...]) -> None:
    seen: set[str] = set()
    for unit in units:
        if unit.unit_id in seen:
            raise ValueError(f"duplicate unit_id after repair: {unit.unit_id}")
        seen.add(unit.unit_id)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
