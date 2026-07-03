"""Exclusion-ledger records and candidate audit exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from legalforecast.selection.contamination_filters import OutcomeLeakageFilterResult


class ExclusionStage(StrEnum):
    DISCOVERY = "discovery"
    RETRIEVAL = "retrieval"
    EXTRACTION = "extraction"
    MOTION_LINKAGE = "motion_linkage"
    ELIGIBILITY = "eligibility"
    UNITIZATION = "unitization"
    LABELING = "labeling"
    CASE_MIX = "case_mix"
    LEAKAGE = "leakage"


class ExclusionReason(StrEnum):
    AMBIGUOUS_MOTION_TO_ORDER_LINKAGE = "ambiguous_motion_to_order_linkage"
    MISSING_CORE_FILING = "missing_core_filing"
    AMBIGUOUS_ORDER = "ambiguous_order"
    OUTCOME_LEAKAGE = "outcome_leakage"
    DUPLICATE_RELATED_CASE_INFLATION = "duplicate_related_case_inflation"
    INSUFFICIENT_TEXT_QUALITY = "insufficient_text_quality"
    UNIT_MISSING_FROM_STAGE_A = "unit_missing_from_stage_a"
    UNCLEAN_LINKAGE = "unclean_linkage"
    LABEL_DIFFICULTY = "label_difficulty"
    CONFLICT_OF_INTEREST = "conflict_of_interest"


@dataclass(frozen=True, slots=True)
class ExclusionLedgerEntry:
    """One durable primary reason a candidate was excluded."""

    candidate_id: str
    case_id: str
    stage: ExclusionStage
    reason: str
    source_entry_ids: tuple[str, ...]
    notes: str
    court: str | None = None
    decision_date: date | None = None
    secondary_reasons: tuple[str, ...] = ()
    source_document_ids: tuple[str, ...] = ()
    related_family_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.reason, "reason")
        _require_non_empty(self.notes, "notes")
        if self.court is not None:
            _require_non_empty(self.court, "court")
        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")
        _require_non_empty_values(self.source_entry_ids, "source_entry_ids")
        _require_non_empty_values(self.source_document_ids, "source_document_ids")
        _require_non_empty_values(self.secondary_reasons, "secondary_reasons")
        if self.reason in self.secondary_reasons:
            raise ValueError("primary reason must not be repeated as secondary")

    @classmethod
    def from_outcome_leakage(
        cls,
        *,
        candidate_id: str,
        case_id: str,
        leakage_result: OutcomeLeakageFilterResult,
        court: str | None = None,
        decision_date: date | None = None,
    ) -> ExclusionLedgerEntry:
        """Convert hard outcome-leakage findings into a primary ledger entry."""

        if not leakage_result.findings:
            raise ValueError("leakage_result must include at least one finding")
        return cls(
            candidate_id=candidate_id,
            case_id=case_id,
            court=court,
            decision_date=decision_date,
            stage=ExclusionStage.LEAKAGE,
            reason=ExclusionReason.OUTCOME_LEAKAGE.value,
            secondary_reasons=tuple(
                finding.leakage_type.value for finding in leakage_result.findings
            ),
            source_entry_ids=tuple(
                finding.source_id for finding in leakage_result.findings
            ),
            related_family_id=_first_related_family_id(leakage_result),
            notes="; ".join(finding.reason for finding in leakage_result.findings),
        )

    @property
    def primary_exclusion_reason(self) -> str:
        return self.reason

    def to_record(self) -> dict[str, Any]:
        decision_date = self.decision_date.isoformat() if self.decision_date else None
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "decision_date": decision_date,
            "stage": self.stage.value,
            "primary_exclusion_reason": self.primary_exclusion_reason,
            "reason": self.reason,
            "secondary_exclusion_reasons": list(self.secondary_reasons),
            "source_entry_ids": list(self.source_entry_ids),
            "source_document_ids": list(self.source_document_ids),
            "related_family_id": self.related_family_id,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ExclusionLedger:
    """Candidate-level exclusion ledger with one primary entry per candidate."""

    entries: tuple[ExclusionLedgerEntry, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.candidate_id in seen:
                raise ValueError(
                    "each excluded candidate must have exactly one primary entry"
                )
            seen.add(entry.candidate_id)

    def add(self, entry: ExclusionLedgerEntry) -> ExclusionLedger:
        return ExclusionLedger((*self.entries, entry))

    def to_records(self) -> list[dict[str, Any]]:
        return [entry.to_record() for entry in self.entries]

    def to_jsonl(self) -> str:
        return "\n".join(
            json.dumps(record, sort_keys=True) for record in self.to_records()
        )

    def write_jsonl(self, path: str | Path) -> Path:
        output_path = Path(path)
        payload = self.to_jsonl()
        if payload:
            payload = f"{payload}\n"
        output_path.write_text(payload, encoding="utf-8")
        return output_path


def _first_related_family_id(
    leakage_result: OutcomeLeakageFilterResult,
) -> str | None:
    for finding in leakage_result.findings:
        if finding.related_family_id is not None:
            return finding.related_family_id
    return None


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_empty_values(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_non_empty(value, field_name)
