"""Exclusion-ledger records and candidate audit exports."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

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
    DECISION_BEFORE_RELEASE_ANCHOR = "decision_before_release_anchor"
    MISSING_CORE_FILING = "missing_core_filing"
    AMBIGUOUS_ORDER = "ambiguous_order"
    OUTCOME_LEAKAGE = "outcome_leakage"
    DUPLICATE_RELATED_CASE_INFLATION = "duplicate_related_case_inflation"
    INSUFFICIENT_TEXT_QUALITY = "insufficient_text_quality"
    UNIT_MISSING_FROM_STAGE_A = "unit_missing_from_stage_a"
    UNCLEAN_LINKAGE = "unclean_linkage"
    LABEL_DIFFICULTY = "label_difficulty"
    PARSE_ERROR = "parse_error"
    JUDGE_DISAGREEMENT = "judge_disagreement"
    ADJUDICATION_PENDING = "adjudication_pending"
    AMBIGUOUS = "ambiguous"
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


def merge_exclusion_ledger_records(
    *record_groups: Iterable[Mapping[str, Any]],
) -> ExclusionLedger:
    """Consolidate split acquisition-stage exclusions by candidate.

    Production acquisition emits exclusions from several stages with slightly
    different record shapes. Nested canonical ledger entries take precedence
    over their enclosing audit failure, while public-packet selection drops are
    normalized here. The earliest-stage reason remains primary and every later
    reason is retained as secondary audit context.
    """

    normalized: list[ExclusionLedgerEntry] = []
    for group in record_groups:
        for record in group:
            normalized.extend(_normalized_exclusion_entries(record))

    by_candidate: dict[str, list[ExclusionLedgerEntry]] = {}
    for entry in normalized:
        by_candidate.setdefault(entry.candidate_id, []).append(entry)
    return ExclusionLedger(
        tuple(
            _merge_candidate_entries(entries)
            for _, entries in sorted(by_candidate.items())
        )
    )


def _normalized_exclusion_entries(
    record: Mapping[str, Any],
) -> tuple[ExclusionLedgerEntry, ...]:
    nested = record.get("exclusion_ledger_entries")
    if nested is not None:
        nested_entries = tuple(
            _entry_from_record(item)
            for item in _record_sequence(nested, "exclusion_ledger_entries")
        )
        if nested_entries:
            return nested_entries

    exclusion_reasons = record.get("exclusion_reasons")
    if exclusion_reasons is not None and record.get("selected") is False:
        reasons = _string_tuple(exclusion_reasons, "exclusion_reasons")
        primary = reasons[0] if reasons else "target_clean_case_cap_reached"
        return (
            ExclusionLedgerEntry(
                candidate_id=_required_record_str(record, "candidate_id"),
                case_id=_optional_record_str(record, "case_id")
                or _required_record_str(record, "candidate_id"),
                court=_optional_record_str(record, "court"),
                stage=ExclusionStage.EXTRACTION,
                reason=primary,
                secondary_reasons=reasons[1:],
                source_entry_ids=(),
                notes=f"Public packet planning excluded candidate: {primary}.",
            ),
        )

    if "primary_exclusion_reason" in record or "reason" in record:
        return (_entry_from_record(record),)

    if record.get("status") in {"adjudication_pending", "pending_adjudication"}:
        candidate_id = _required_record_str(record, "candidate_id")
        return (
            ExclusionLedgerEntry(
                candidate_id=candidate_id,
                case_id=_optional_record_str(record, "case_id") or candidate_id,
                stage=ExclusionStage.LABELING,
                reason=ExclusionReason.ADJUDICATION_PENDING.value,
                source_entry_ids=(),
                notes="Stage B label requires lawyer adjudication.",
            ),
        )

    if record.get("status") in {"failed", "timed_out"}:
        error_type = _optional_record_str(record, "error_type") or "stage_failed"
        parser_document_id = _optional_record_str(record, "source_document_id")
        if parser_document_id is not None and record.get("stage") is None:
            reason = ExclusionReason.PARSE_ERROR.value
            stage = ExclusionStage.EXTRACTION
        else:
            reason = (
                ExclusionReason.UNIT_MISSING_FROM_STAGE_A.value
                if error_type == "FrozenUnitWorkflowRequiredError"
                else _snake_case(error_type)
            )
            stage = _stage(record.get("stage"))
        candidate_id = _required_record_str(record, "candidate_id")
        return (
            ExclusionLedgerEntry(
                candidate_id=candidate_id,
                case_id=_optional_record_str(record, "case_id") or candidate_id,
                stage=stage,
                reason=reason,
                source_entry_ids=(),
                source_document_ids=(
                    (parser_document_id,) if parser_document_id is not None else ()
                ),
                notes=_optional_record_str(record, "error_message")
                or f"{error_type} during acquisition.",
            ),
        )
    return ()


def _entry_from_record(record: Mapping[str, Any]) -> ExclusionLedgerEntry:
    candidate_id = _required_record_str(record, "candidate_id")
    reason = _optional_record_str(record, "primary_exclusion_reason")
    reason = reason or _required_record_str(record, "reason")
    return ExclusionLedgerEntry(
        candidate_id=candidate_id,
        case_id=_optional_record_str(record, "case_id") or candidate_id,
        court=_optional_record_str(record, "court"),
        decision_date=_optional_date(record.get("decision_date")),
        stage=_stage(record.get("stage")),
        reason=reason,
        secondary_reasons=_string_tuple(
            record.get("secondary_exclusion_reasons", record.get("secondary_reasons")),
            "secondary_exclusion_reasons",
        ),
        source_entry_ids=_string_tuple(
            record.get("source_entry_ids"), "source_entry_ids"
        ),
        source_document_ids=_string_tuple(
            record.get("source_document_ids"), "source_document_ids"
        ),
        related_family_id=_optional_record_str(record, "related_family_id"),
        notes=_optional_record_str(record, "notes") or f"Excluded for {reason}.",
    )


_STAGE_ORDER = {stage: index for index, stage in enumerate(ExclusionStage)}


def _merge_candidate_entries(
    entries: Sequence[ExclusionLedgerEntry],
) -> ExclusionLedgerEntry:
    ordered = sorted(entries, key=lambda entry: _STAGE_ORDER[entry.stage])
    primary = ordered[0]
    case_ids = {entry.case_id for entry in ordered}
    case_ids.discard(primary.candidate_id)
    if len(case_ids) > 1:
        raise ValueError(
            f"conflicting case_id values for {primary.candidate_id}: {sorted(case_ids)}"
        )
    case_id = next(iter(case_ids), primary.candidate_id)
    secondary_reasons = _unique(
        reason
        for entry in ordered
        for reason in (
            *entry.secondary_reasons,
            *((entry.reason,) if entry is not primary else ()),
        )
        if reason != primary.reason
    )
    return ExclusionLedgerEntry(
        candidate_id=primary.candidate_id,
        case_id=case_id,
        court=next((entry.court for entry in ordered if entry.court), None),
        decision_date=next(
            (entry.decision_date for entry in ordered if entry.decision_date), None
        ),
        stage=primary.stage,
        reason=primary.reason,
        secondary_reasons=secondary_reasons,
        source_entry_ids=_unique(
            source_id for entry in ordered for source_id in entry.source_entry_ids
        ),
        source_document_ids=_unique(
            source_id for entry in ordered for source_id in entry.source_document_ids
        ),
        related_family_id=next(
            (entry.related_family_id for entry in ordered if entry.related_family_id),
            None,
        ),
        notes="; ".join(_unique(entry.notes for entry in ordered)),
    )


def _stage(value: object) -> ExclusionStage:
    aliases = {
        "plan-public-downloads": ExclusionStage.EXTRACTION,
        "parse-documents": ExclusionStage.EXTRACTION,
        "llm-unitize": ExclusionStage.UNITIZATION,
        "llm-label": ExclusionStage.LABELING,
    }
    if isinstance(value, str):
        if value in aliases:
            return aliases[value]
        try:
            return ExclusionStage(value)
        except ValueError:
            pass
    return ExclusionStage.ELIGIBILITY


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} must contain objects")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        strings.append(item)
    return tuple(strings)


def _required_record_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _optional_record_str(record, field_name)
    if value is None:
        raise ValueError(f"{field_name} is required")
    return value


def _optional_record_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("decision_date must be an ISO date")
    return date.fromisoformat(value)


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


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
