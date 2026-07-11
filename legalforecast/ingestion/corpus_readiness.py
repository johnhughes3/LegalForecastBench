"""Fail-closed clean-corpus readiness checks for production acquisition."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from legalforecast.labeling.label_outcomes import (
    AmendmentClass,
    LaterProceduralChange,
    OutcomeCitation,
    OutcomeLabel,
    StageBDecisionText,
)


class CorpusReadinessError(ValueError):
    """Raised when a corpus has not met its required clean-motion count."""


@dataclass(frozen=True, slots=True)
class CorpusReadinessReport:
    """Joined acquisition-gate result and case-mix summary."""

    required_clean_count: int
    clean_candidate_ids: tuple[str, ...]
    excluded_candidate_ids: tuple[str, ...]
    exclusion_reasons: Mapping[str, tuple[str, ...]]
    funnel: Mapping[str, int]
    case_mix: Mapping[str, Mapping[str, int]]

    @property
    def clean_count(self) -> int:
        return len(self.clean_candidate_ids)

    @property
    def meets_target(self) -> bool:
        return self.clean_count >= self.required_clean_count

    def to_record(self) -> dict[str, Any]:
        return {
            "required_clean_count": self.required_clean_count,
            "clean_count": self.clean_count,
            "meets_target": self.meets_target,
            "clean_candidate_ids": list(self.clean_candidate_ids),
            "excluded_candidate_ids": list(self.excluded_candidate_ids),
            "exclusion_reasons": {
                candidate_id: list(reasons)
                for candidate_id, reasons in sorted(self.exclusion_reasons.items())
            },
            "funnel": dict(self.funnel),
            "case_mix": {
                dimension: dict(sorted(buckets.items()))
                for dimension, buckets in sorted(self.case_mix.items())
            },
        }


def build_clean_corpus_readiness(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    label_records: Iterable[Mapping[str, Any]],
    label_audit_records: Iterable[Mapping[str, Any]],
    lawyer_review_records: Iterable[Mapping[str, Any]],
    packet_build_records: Iterable[Mapping[str, Any]],
    packet_records: Iterable[Mapping[str, Any]],
    exclusion_records: Iterable[Mapping[str, Any]],
    decision_text_by_candidate_and_document: Mapping[tuple[str, str], str],
    decision_filed_on_or_after: date,
    required_clean_count: int,
) -> CorpusReadinessReport:
    """Join every production artifact required to count a clean motion."""

    if required_clean_count <= 0:
        raise CorpusReadinessError("required_clean_count must be positive")
    selections = _index_unique(selection_records, "selection")
    parsers = _index_parser_records(parser_records)
    units_by_candidate, _unit_to_candidate = _index_units(prediction_unit_records)
    labels_by_unit = _index_labels(label_records)
    audits_by_candidate = _group_by_candidate(label_audit_records)
    reviews_by_candidate = _group_by_candidate(lawyer_review_records)
    packet_build = _index_unique(packet_build_records, "packet-build input")
    packets = _index_unique(packet_records, "built packet")
    excluded = _exclusions_by_candidate(exclusion_records)

    reasons_by_candidate: dict[str, tuple[str, ...]] = {}
    parsed_complete: set[str] = set()
    unitized_complete: set[str] = set()
    labeled_complete: set[str] = set()
    clean: list[str] = []
    for candidate_id, selection in selections.items():
        reasons: list[str] = list(excluded.get(candidate_id, ()))
        required_documents = {
            _required_str(document, "source_document_id")
            for document in _record_sequence(selection.get("documents"), "documents")
        }
        if not required_documents:
            reasons.append("required_documents_missing")
        elif all(
            parsers.get((candidate_id, document_id), {}).get("status") == "succeeded"
            for document_id in required_documents
        ):
            parsed_complete.add(candidate_id)
        else:
            reasons.append("required_document_parse_incomplete")

        units = units_by_candidate.get(candidate_id, ())
        scorable_unit_ids = tuple(
            _required_str(unit, "unit_id")
            for unit in units
            if unit.get("should_score") is True
        )
        if not units:
            reasons.append("stage_a_units_missing")
        elif not scorable_unit_ids:
            reasons.append("stage_a_no_scorable_units")
        else:
            unitized_complete.add(candidate_id)

        label_reasons: list[str] = []
        if scorable_unit_ids and not all(
            unit_id in labels_by_unit for unit_id in scorable_unit_ids
        ):
            label_reasons.append("stage_b_labels_incomplete")
        for unit_id in scorable_unit_ids:
            label = labels_by_unit.get(unit_id)
            if label is not None:
                label_reasons.extend(
                    _label_gate_reasons(
                        label,
                        candidate_id=candidate_id,
                        decision_text_by_candidate_and_document=decision_text_by_candidate_and_document,
                        decision_filed_on_or_after=decision_filed_on_or_after,
                    )
                )
        candidate_audits = audits_by_candidate.get(candidate_id, ())
        if not candidate_audits:
            label_reasons.append("label_audit_missing")
        elif any(audit.get("status") == "failed" for audit in candidate_audits):
            label_reasons.append("labeling_failed")
        elif any(audit.get("status") != "succeeded" for audit in candidate_audits):
            label_reasons.append("label_audit_incomplete")
        if any(
            review.get("status") not in {"adjudicated", "resolved", "complete"}
            for review in reviews_by_candidate.get(candidate_id, ())
        ):
            label_reasons.append("lawyer_review_pending")
        if scorable_unit_ids and not label_reasons:
            labeled_complete.add(candidate_id)
        reasons.extend(label_reasons)

        if candidate_id not in packet_build:
            reasons.append("packet_build_input_missing")
        if candidate_id not in packets:
            reasons.append("built_packet_missing")
        unique_reasons = tuple(dict.fromkeys(reasons))
        if unique_reasons:
            reasons_by_candidate[candidate_id] = unique_reasons
        else:
            clean.append(candidate_id)

    clean_ids = tuple(sorted(clean))
    excluded_ids = tuple(sorted(set(selections) - set(clean_ids)))
    funnel = {
        "selected": len(selections),
        "parsed_complete": len(parsed_complete),
        "unitized_complete": len(unitized_complete),
        "labeled_complete": len(labeled_complete),
        "packet_inputs": len(set(selections) & set(packet_build)),
        "packets_built": len(set(selections) & set(packets)),
        "excluded": len(excluded_ids),
        "clean": len(clean_ids),
    }
    return CorpusReadinessReport(
        required_clean_count=required_clean_count,
        clean_candidate_ids=clean_ids,
        excluded_candidate_ids=excluded_ids,
        exclusion_reasons=reasons_by_candidate,
        funnel=funnel,
        case_mix=_case_mix(clean_ids, selections=selections, packets=packets),
    )


def require_clean_corpus_ready(report: CorpusReadinessReport) -> None:
    """Fail unless the joined corpus meets its configured clean-motion target."""

    if not report.meets_target:
        raise CorpusReadinessError(
            f"corpus requires {report.required_clean_count} clean motions; "
            f"found {report.clean_count}"
        )


def _label_gate_reasons(
    label: Mapping[str, Any],
    *,
    candidate_id: str,
    decision_text_by_candidate_and_document: Mapping[tuple[str, str], str],
    decision_filed_on_or_after: date,
) -> tuple[str, ...]:
    try:
        canonical_label = _canonical_outcome_label(label)
    except (CorpusReadinessError, TypeError, ValueError):
        return ("stage_b_label_schema_invalid",)

    reasons: list[str] = []
    if canonical_label.ambiguous:
        reasons.append("stage_b_label_ambiguous")
    try:
        parsed_date = date.fromisoformat(canonical_label.first_written_disposition_date)
    except ValueError:
        parsed_date = None
    if parsed_date is None:
        reasons.append("first_written_disposition_date_missing")
    elif parsed_date < decision_filed_on_or_after:
        reasons.append("first_written_disposition_before_anchor")
    citations = canonical_label.supporting_citations
    if any(
        citation.document_id != canonical_label.first_written_disposition_id
        for citation in citations
    ):
        reasons.append("stage_b_citation_not_locked_disposition")
        return tuple(reasons)

    decision_text = decision_text_by_candidate_and_document.get(
        (candidate_id, canonical_label.first_written_disposition_id)
    )
    if not isinstance(decision_text, str) or not decision_text.strip():
        reasons.append("first_written_disposition_text_missing")
        return tuple(reasons)

    canonical_decision_text = StageBDecisionText(
        document_id=canonical_label.first_written_disposition_id,
        entered_date=canonical_label.first_written_disposition_date,
        text=decision_text,
    )
    if any(citation.excerpt is None for citation in citations):
        reasons.append("stage_b_label_excerpt_missing")
    elif any(
        not canonical_decision_text.contains_excerpt(cast(str, citation.excerpt))
        for citation in citations
    ):
        reasons.append("stage_b_label_excerpt_not_verbatim")
    return tuple(reasons)


def _canonical_outcome_label(record: Mapping[str, Any]) -> OutcomeLabel:
    """Parse a persisted label through the canonical Stage B domain schema."""

    return OutcomeLabel(
        unit_id=_required_str(record, "unit_id"),
        fully_dismissed=_optional_bool(record, "fully_dismissed"),
        amendment_class=AmendmentClass(_required_str(record, "amendment_class")),
        ambiguous=_required_bool(record, "ambiguous"),
        label_confidence=_required_float(record, "label_confidence"),
        supporting_citations=tuple(
            _canonical_outcome_citation(citation)
            for citation in _record_sequence(
                record.get("supporting_citations"), "supporting_citations"
            )
        ),
        first_written_disposition_id=_required_str(
            record, "first_written_disposition_id"
        ),
        first_written_disposition_date=_required_str(
            record, "first_written_disposition_date"
        ),
        first_written_disposition_locked=_required_bool(
            record, "first_written_disposition_locked"
        ),
        later_procedural_changes=tuple(
            LaterProceduralChange(value)
            for value in _optional_str_sequence(
                record.get("later_procedural_changes"),
                "later_procedural_changes",
            )
        ),
        notes=_optional_str(record, "notes"),
    )


def _canonical_outcome_citation(record: Mapping[str, Any]) -> OutcomeCitation:
    return OutcomeCitation(
        document_id=_required_str(record, "document_id"),
        page=_optional_positive_int(record, "page"),
        paragraph=_optional_positive_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _index_parser_records(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        if key in indexed:
            raise CorpusReadinessError(f"duplicate parser record: {key}")
        indexed[key] = record
    return indexed


def _index_units(
    records: Iterable[Mapping[str, Any]],
) -> tuple[
    dict[str, tuple[Mapping[str, Any], ...]],
    dict[str, str],
]:
    by_candidate: dict[str, tuple[Mapping[str, Any], ...]] = {}
    unit_to_candidate: dict[str, str] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in by_candidate:
            raise CorpusReadinessError(f"duplicate unit record: {candidate_id}")
        units = _record_sequence(record.get("prediction_units"), "prediction_units")
        by_candidate[candidate_id] = units
        for unit in units:
            unit_id = _required_str(unit, "unit_id")
            if unit_id in unit_to_candidate:
                raise CorpusReadinessError(f"duplicate prediction unit: {unit_id}")
            unit_to_candidate[unit_id] = candidate_id
    return by_candidate, unit_to_candidate


def _index_labels(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        unit_id = _required_str(record, "unit_id")
        if unit_id in indexed:
            raise CorpusReadinessError(f"duplicate label: {unit_id}")
        indexed[unit_id] = record
    return indexed


def _index_unique(
    records: Iterable[Mapping[str, Any]], label: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in indexed:
            raise CorpusReadinessError(f"duplicate {label}: {candidate_id}")
        indexed[candidate_id] = record
    return indexed


def _group_by_candidate(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        if isinstance(candidate_id, str) and candidate_id.strip():
            grouped.setdefault(candidate_id, []).append(record)
    return {key: tuple(value) for key, value in grouped.items()}


def _exclusions_by_candidate(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    excluded: dict[str, list[str]] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        reason = record.get("primary_exclusion_reason", record.get("reason"))
        if not isinstance(reason, str) or not reason.strip():
            raise CorpusReadinessError("exclusion reason is required")
        excluded.setdefault(candidate_id, []).append(reason)
    return {key: tuple(dict.fromkeys(value)) for key, value in excluded.items()}


def _case_mix(
    clean_candidate_ids: Sequence[str],
    *,
    selections: Mapping[str, Mapping[str, Any]],
    packets: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    dimensions: dict[str, Counter[str]] = {
        "court": Counter(),
        "nature_of_suit": Counter(),
        "nos_macro_category": Counter(),
        "related_family_id": Counter(),
        "mdl_family_id": Counter(),
    }
    for candidate_id in clean_candidate_ids:
        selection = selections[candidate_id]
        packet = packets[candidate_id]
        metadata = packet.get("metadata")
        packet_metadata: Mapping[str, Any] = (
            cast(Mapping[str, Any], metadata) if isinstance(metadata, Mapping) else {}
        )
        values = {
            "court": _case_mix_value(packet.get("court"), selection.get("court")),
            "nature_of_suit": _case_mix_value(
                packet_metadata.get("nature_of_suit"),
                packet.get("nature_of_suit"),
                selection.get("nature_of_suit"),
            ),
            "nos_macro_category": _case_mix_value(
                packet_metadata.get("nos_macro_category"),
                packet.get("nos_macro_category"),
                selection.get("nos_macro_category"),
            ),
            "related_family_id": _case_mix_value(
                packet.get("related_family_id"),
                packet_metadata.get("related_family_id"),
                selection.get("related_family_id"),
            ),
            "mdl_family_id": _case_mix_value(
                packet.get("mdl_family_id"),
                packet_metadata.get("mdl_family_id"),
                selection.get("mdl_family_id"),
            ),
        }
        for dimension, value in values.items():
            missing_bucket = (
                "none"
                if dimension in {"related_family_id", "mdl_family_id"}
                else "unknown"
            )
            dimensions[dimension][value or missing_bucket] += 1
    case_mix = {dimension: dict(counter) for dimension, counter in dimensions.items()}
    if any(
        sum(buckets.values()) != len(clean_candidate_ids)
        for buckets in case_mix.values()
    ):
        raise CorpusReadinessError("case-mix dimensions must reconcile to clean_count")
    return case_mix


def _case_mix_value(*values: object) -> str | None:
    return next(
        (value.strip() for value in values if isinstance(value, str) and value.strip()),
        None,
    )


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise CorpusReadinessError(f"{field_name} must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise CorpusReadinessError(f"{field_name} must contain objects")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise CorpusReadinessError(f"{field_name} is required")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise CorpusReadinessError(f"{field_name} must be a boolean")
    return value


def _optional_bool(record: Mapping[str, Any], field_name: str) -> bool | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise CorpusReadinessError(f"{field_name} must be a boolean or null")
    return value


def _required_float(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CorpusReadinessError(f"{field_name} must be numeric")
    return float(value)


def _optional_positive_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CorpusReadinessError(f"{field_name} must be a positive integer or null")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CorpusReadinessError(f"{field_name} must be a non-empty string or null")
    return value


def _optional_str_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise CorpusReadinessError(f"{field_name} must be a list")
    items: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise CorpusReadinessError(f"{field_name} must contain non-empty strings")
        items.append(item)
    return tuple(items)
