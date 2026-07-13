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
    UnitResolution,
)
from legalforecast.unitization.review import (
    UnitizationReviewError,
    canonical_sha256,
    require_finalized_envelopes,
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
    unitization_audit_records: Iterable[Mapping[str, Any]],
    unitization_review_records: Iterable[Mapping[str, Any]],
    unitization_adjudication_records: Iterable[Mapping[str, Any]],
    label_records: Iterable[Mapping[str, Any]],
    label_audit_records: Iterable[Mapping[str, Any]],
    lawyer_review_records: Iterable[Mapping[str, Any]],
    lawyer_review_audit_records: Iterable[Mapping[str, Any]],
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
    try:
        finalized_unit_records = require_finalized_envelopes(prediction_unit_records)
    except UnitizationReviewError as exc:
        raise CorpusReadinessError(str(exc)) from exc
    units_by_candidate, _unit_to_candidate = _index_units(finalized_unit_records)
    unitization_audits_by_candidate = _group_by_candidate(unitization_audit_records)
    unitization_reviews_by_candidate = _group_by_candidate(unitization_review_records)
    unitization_adjudications_by_candidate = _group_by_candidate(
        unitization_adjudication_records
    )
    labels_by_unit = _index_labels(label_records)
    audits_by_candidate = _group_by_candidate(label_audit_records)
    reviews_by_candidate = _group_by_candidate(lawyer_review_records)
    review_audits_by_candidate = _group_by_candidate(lawyer_review_audit_records)
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
        target_motion_numbers = _value_sequence(
            selection.get("target_motion_entry_numbers"),
            "target_motion_entry_numbers",
        )
        if len(target_motion_numbers) != 1:
            reasons.append("selected_target_motion_count_not_one")
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
        stage_a_reasons: list[str] = []
        if not units:
            reasons.append("stage_a_units_missing")
        elif not scorable_unit_ids:
            reasons.append("stage_a_no_scorable_units")
        candidate_unitization_audits = unitization_audits_by_candidate.get(
            candidate_id,
            (),
        )
        if not candidate_unitization_audits:
            stage_a_reasons.append("stage_a_unitization_audit_missing")
        elif any(
            audit.get("status") == "failed" for audit in candidate_unitization_audits
        ):
            stage_a_reasons.append("stage_a_unitization_failed")
        else:
            stage_a_reasons.extend(
                _finalized_chain_gate_reasons(
                    units=units,
                    adjudication_records=unitization_adjudications_by_candidate.get(
                        candidate_id, ()
                    ),
                )
            )
            stage_a_reasons.extend(
                _unitization_review_gate_reasons(
                    candidate_id=candidate_id,
                    audit_records=candidate_unitization_audits,
                    review_records=unitization_reviews_by_candidate.get(
                        candidate_id,
                        (),
                    ),
                    adjudication_records=unitization_adjudications_by_candidate.get(
                        candidate_id,
                        (),
                    ),
                )
            )
        reasons.extend(stage_a_reasons)
        if units and scorable_unit_ids and not stage_a_reasons:
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
        candidate_audits = tuple(
            audit
            for audit in audits_by_candidate.get(candidate_id, ())
            if audit.get("stage") in {None, "llm-label"}
        )
        candidate_review_audits = review_audits_by_candidate.get(candidate_id, ())
        if not candidate_audits:
            label_reasons.append("label_audit_missing")
        elif any(audit.get("status") == "failed" for audit in candidate_audits):
            label_reasons.append("labeling_failed")
        elif any(
            audit.get("status") not in {"succeeded", "adjudication_pending"}
            for audit in candidate_audits
        ):
            label_reasons.append("label_audit_incomplete")
        else:
            label_reasons.extend(
                _label_audit_gate_reasons(
                    candidate_id=candidate_id,
                    label_audit_records=candidate_audits,
                    lawyer_review_records=reviews_by_candidate.get(candidate_id, ()),
                    lawyer_review_audit_records=candidate_review_audits,
                )
            )
        if _has_pending_lawyer_review(
            reviews_by_candidate.get(candidate_id, ()),
            resolution_records=candidate_review_audits,
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


def _finalized_chain_gate_reasons(
    *,
    units: Sequence[Mapping[str, Any]],
    adjudication_records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    adjudications = {
        _optional_str(record, "adjudication_id"): record
        for record in adjudication_records
        if _optional_str(record, "adjudication_id") is not None
    }
    for unit in units:
        adjudication_id = _optional_str(unit, "adjudication_id")
        source_hashes = _value_sequence(
            unit.get("source_unit_sha256s"), "source_unit_sha256s"
        )
        if (
            not adjudication_id
            or not source_hashes
            or any(not isinstance(value, str) or not value for value in source_hashes)
        ):
            return ("stage_a_finalized_hash_chain_invalid",)
        if adjudication_id.startswith("automatic:"):
            if len(source_hashes) != 1 or adjudication_id != (
                f"automatic:{source_hashes[0]}"
            ):
                return ("stage_a_finalized_hash_chain_invalid",)
            continue
        adjudication = adjudications.get(adjudication_id)
        if adjudication is None or unit.get("adjudication_sha256") != canonical_sha256(
            adjudication
        ):
            return ("stage_a_finalized_hash_chain_invalid",)
    return ()


_RESOLVED_REVIEW_STATUSES = frozenset(
    {"adjudicated", "resolved", "complete", "succeeded"}
)


def _unitization_review_gate_reasons(
    *,
    candidate_id: str,
    audit_records: Sequence[Mapping[str, Any]],
    review_records: Sequence[Mapping[str, Any]],
    adjudication_records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    reviews_by_id = {
        _optional_str(record, "review_id"): record
        for record in review_records
        if _optional_str(record, "review_id") is not None
    }
    adjudications_by_id: dict[str, Mapping[str, Any]] = {}
    for record in adjudication_records:
        review_ids_value = record.get("review_ids")
        review_ids = (
            tuple(
                str(review_id)
                for review_id in cast(Sequence[object], review_ids_value)
                if isinstance(review_id, str) and review_id
            )
            if isinstance(review_ids_value, Sequence)
            and not isinstance(review_ids_value, str)
            else ()
        )
        legacy_review_id = _optional_str(record, "review_id")
        for review_id in review_ids or (
            (legacy_review_id,) if legacy_review_id else ()
        ):
            if review_id in adjudications_by_id:
                reasons.append("stage_a_review_adjudication_invalid")
            adjudications_by_id[review_id] = record
    expected_reviews: dict[str, tuple[str, str]] = {}
    for audit in audit_records:
        status = audit.get("status")
        review_items = _record_sequence(audit.get("review_items", ()), "review_items")
        if status not in {"succeeded", "adjudication_pending"}:
            reasons.append("stage_a_unitization_audit_incomplete")
        if status == "succeeded" and review_items:
            reasons.append("stage_a_unitization_audit_inconsistent")
        for item in review_items:
            unit_id = _required_str(item, "unit_id")
            expected_reviews[f"{candidate_id}:{unit_id}:stage-a-review"] = (
                unit_id,
                _required_str(item, "reason"),
            )
    missing = [
        review_id for review_id in expected_reviews if review_id not in reviews_by_id
    ]
    if missing:
        reasons.append("stage_a_review_queue_missing")
    if any(
        record.get("schema_version") != "legalforecast.unitization_review_queue.v1"
        or record.get("status") != "pending_adjudication"
        or _optional_str(record, "unit_id") != expected_reviews[review_id][0]
        or _optional_str(record, "route_reason") != expected_reviews[review_id][1]
        for review_id, record in reviews_by_id.items()
        if review_id in expected_reviews
    ):
        reasons.append("stage_a_review_queue_invalid")
    missing_adjudications = [
        review_id
        for review_id in expected_reviews
        if review_id not in adjudications_by_id
    ]
    if missing_adjudications:
        reasons.append("stage_a_review_pending")
    if any(
        record.get("disposition")
        not in {"ACCEPT", "AMEND", "SPLIT", "MERGE", "CANDIDATE-EXCLUSION"}
        or not _optional_str(record, "adjudicator_id")
        or not _optional_str(record, "adjudication_notes")
        for review_id, record in adjudications_by_id.items()
        if review_id in expected_reviews
    ):
        reasons.append("stage_a_review_adjudication_invalid")
    for review_id, adjudication in adjudications_by_id.items():
        review = reviews_by_id.get(review_id)
        if review is None:
            continue
        source_value = adjudication.get("source_unit_ids")
        source_values = (
            cast(Sequence[object], source_value)
            if isinstance(source_value, Sequence) and not isinstance(source_value, str)
            else ()
        )
        source_unit_ids = tuple(
            value for value in source_values if isinstance(value, str) and value
        )
        if (
            not source_unit_ids
            or len(source_unit_ids) != len(source_values)
            or len(set(source_unit_ids)) != len(source_unit_ids)
            or set(source_unit_ids)
            != {
                _optional_str(reviews_by_id[referenced_review_id], "unit_id")
                for (
                    referenced_review_id,
                    candidate_adjudication,
                ) in adjudications_by_id.items()
                if candidate_adjudication is adjudication
                and referenced_review_id in reviews_by_id
            }
        ):
            reasons.append("stage_a_review_adjudication_invalid")
            break
    return tuple(dict.fromkeys(reasons))


def _label_audit_gate_reasons(
    *,
    candidate_id: str,
    label_audit_records: Sequence[Mapping[str, Any]],
    lawyer_review_records: Sequence[Mapping[str, Any]],
    lawyer_review_audit_records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    queued_reviews_by_id = {
        _optional_str(record, "review_id"): record
        for record in lawyer_review_records
        if _optional_str(record, "review_id") is not None
    }
    for audit in label_audit_records:
        gate_value = audit.get("label_audit_gate")
        if not isinstance(gate_value, Mapping):
            reasons.append("label_audit_gate_missing")
            continue
        gate = cast(Mapping[str, Any], gate_value)
        if gate.get("required") is not True:
            reasons.append("label_audit_failed")
            continue
        status = gate.get("status")
        sample_value = gate.get("sample_unit_ids", ())
        if not isinstance(sample_value, Sequence) or isinstance(sample_value, str):
            reasons.append("label_audit_failed")
            continue
        sample_unit_ids = [
            str(unit_id)
            for unit_id in cast(Sequence[object], sample_value)
            if isinstance(unit_id, str) and unit_id
        ]
        if status == "no_unanimous_auto_labels" and not sample_unit_ids:
            continue
        if status == "passed":
            continue
        if status == "covered_by_cycle_level_plan":
            if not _has_passed_cycle_label_audit_gate(
                candidate_id=candidate_id,
                sample_unit_ids=sample_unit_ids,
                plan_sha256=_optional_str(gate, "cycle_label_audit_plan_sha256"),
                corpus_sha256=_optional_str(gate, "ensemble_corpus_sha256"),
                audit_records=lawyer_review_audit_records,
            ):
                reasons.append("label_audit_pending")
            continue
        if status == "awaiting_human_adjudicated_labels":
            expected_review_ids = {
                f"{candidate_id}:{unit_id}:label-audit" for unit_id in sample_unit_ids
            }
            if not expected_review_ids.issubset(queued_reviews_by_id):
                reasons.append("label_audit_review_queue_missing")
            if any(
                not _valid_label_audit_queue_record(queued_reviews_by_id[review_id])
                for review_id in expected_review_ids
                if review_id in queued_reviews_by_id
            ):
                reasons.append("label_audit_review_queue_invalid")
            passed = (
                _has_passed_cycle_label_audit_gate(
                    candidate_id=candidate_id,
                    sample_unit_ids=sample_unit_ids,
                    plan_sha256=_optional_str(gate, "cycle_label_audit_plan_sha256"),
                    corpus_sha256=_optional_str(gate, "ensemble_corpus_sha256"),
                    audit_records=lawyer_review_audit_records,
                )
                if gate.get("cycle_level") is True
                else _has_passed_label_audit_gate(
                    sample_unit_ids,
                    lawyer_review_audit_records,
                )
            )
            if not passed:
                reasons.append("label_audit_pending")
            continue
        reasons.append("label_audit_failed")
    return tuple(dict.fromkeys(reasons))


def _valid_label_audit_queue_record(record: Mapping[str, Any]) -> bool:
    packet_value = record.get("packet")
    if not isinstance(packet_value, Mapping):
        return False
    packet = cast(Mapping[str, Any], packet_value)
    materials_value = packet.get("materials")
    if not isinstance(materials_value, Sequence) or isinstance(materials_value, str):
        return False
    material_kinds: set[str] = set()
    for material_value in cast(Sequence[object], materials_value):
        if not isinstance(material_value, Mapping):
            continue
        material = cast(Mapping[str, Any], material_value)
        kind = material.get("kind")
        if isinstance(kind, str):
            material_kinds.add(kind)
    return (
        record.get("status") == "pending_adjudication"
        and record.get("route_reason") == "label_audit_sample"
        and packet.get("blind_reliability_study") is True
        and "ensemble" not in packet
        and {"unit_text", "decision_excerpt"}.issubset(material_kinds)
    )


def _has_passed_label_audit_gate(
    sample_unit_ids: Sequence[str],
    audit_records: Sequence[Mapping[str, Any]],
) -> bool:
    expected = set(sample_unit_ids)
    for record in audit_records:
        if (
            record.get("stage") != "label-audit-gate"
            or record.get("status") != "passed"
        ):
            continue
        sample_value = record.get("sample_unit_ids")
        if not isinstance(sample_value, Sequence) or isinstance(sample_value, str):
            continue
        actual = {
            unit_id
            for unit_id in cast(Sequence[object], sample_value)
            if isinstance(unit_id, str) and unit_id
        }
        if actual == expected:
            return True
    return False


def _has_passed_cycle_label_audit_gate(
    *,
    candidate_id: str,
    sample_unit_ids: Sequence[str],
    plan_sha256: str | None,
    corpus_sha256: str | None,
    audit_records: Sequence[Mapping[str, Any]],
) -> bool:
    if plan_sha256 is None or corpus_sha256 is None:
        return False
    expected = set(sample_unit_ids)
    for record in audit_records:
        sample_value = record.get("sample_unit_ids")
        if not isinstance(sample_value, Sequence) or isinstance(sample_value, str):
            continue
        actual = {
            unit_id
            for unit_id in cast(Sequence[object], sample_value)
            if isinstance(unit_id, str) and unit_id
        }
        if (
            record.get("schema_version") == "legalforecast.cycle_label_audit_gate.v1"
            and record.get("stage") == "label-audit-gate"
            and record.get("status") == "passed"
            and record.get("human_verified") is True
            and record.get("candidate_id") == candidate_id
            and record.get("cycle_label_audit_plan_sha256") == plan_sha256
            and record.get("ensemble_corpus_sha256") == corpus_sha256
            and actual == expected
        ):
            return True
    return False


def _has_pending_lawyer_review(
    review_records: Sequence[Mapping[str, Any]],
    *,
    resolution_records: Sequence[Mapping[str, Any]],
) -> bool:
    resolved_review_ids = {
        _optional_str(record, "review_id")
        for record in resolution_records
        if record.get("status") in _RESOLVED_REVIEW_STATUSES
        and _optional_str(record, "review_id") is not None
    }
    return any(
        record.get("status") not in _RESOLVED_REVIEW_STATUSES
        and _optional_str(record, "review_id") not in resolved_review_ids
        for record in review_records
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
        unit_resolution=UnitResolution(_required_str(record, "unit_resolution")),
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
        "case_type_stratum": Counter(),
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
            "case_type_stratum": _case_mix_value(
                packet_metadata.get("case_type_stratum"),
                packet.get("case_type_stratum"),
                selection.get("case_type_stratum"),
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


def _value_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise CorpusReadinessError(f"{field_name} must be a list")
    return tuple(cast(Sequence[object], value))


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
