from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import cast

import pytest
from legalforecast.ingestion.corpus_readiness import (
    CorpusReadinessError,
    CorpusReadinessReport,
    build_clean_corpus_readiness,
    require_clean_corpus_ready,
)


def _selection(candidate_id: str, case_id: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "case_id": case_id,
        "court": "S.D.N.Y.",
        "target_motion_entry_numbers": [5],
        "documents": [
            {"source_document_id": f"{candidate_id}-complaint"},
            {"source_document_id": f"{candidate_id}-decision"},
        ],
    }


def _parsers(candidate_id: str) -> list[dict[str, object]]:
    return [
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-complaint",
            "status": "succeeded",
        },
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-decision",
            "status": "succeeded",
        },
    ]


def _unit(candidate_id: str, unit_id: str) -> dict[str, object]:
    source_hash = "1" * 64
    return {
        "schema_version": "legalforecast.finalized_prediction_units.v1",
        "status": "finalized",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "raw_prediction_units_sha256": "2" * 64,
        "prediction_units": [
            {
                "unit_id": unit_id,
                "should_score": True,
                "source_unit_sha256s": [source_hash],
                "adjudication_id": f"automatic:{source_hash}",
                "adjudication_sha256": None,
                "disposition": "ACCEPT",
            }
        ],
        "exclusion": None,
    }


def _unitization_audit(candidate_id: str) -> dict[str, object]:
    return {
        "stage": "llm-unitize",
        "candidate_id": candidate_id,
        "status": "succeeded",
        "review_items": [],
    }


def _label_audit(candidate_id: str) -> dict[str, object]:
    return {
        "stage": "llm-label",
        "candidate_id": candidate_id,
        "status": "succeeded",
        "label_audit_gate": {
            "required": True,
            "status": "no_unanimous_auto_labels",
            "sample_unit_ids": [],
        },
    }


def _label(unit_id: str) -> dict[str, object]:
    return {
        "unit_id": unit_id,
        "fully_dismissed": True,
        "amendment_class": "dismissed_without_express_amendment_opportunity",
        "ambiguous": False,
        "label_confidence": 0.95,
        "first_written_disposition_id": "decision-1",
        "first_written_disposition_date": "2026-06-30",
        "first_written_disposition_locked": True,
        "supporting_citations": [
            {"document_id": "decision-1", "excerpt": "Count I is dismissed."}
        ],
    }


def _decision_texts(candidate_id: str) -> dict[tuple[str, str], str]:
    return {(candidate_id, "decision-1"): "The Court rules. Count I is dismissed."}


def _single_candidate_report(
    *,
    unitization_audits: Sequence[Mapping[str, object]] | None = None,
    unitization_reviews: Sequence[Mapping[str, object]] | None = None,
    unitization_adjudications: Sequence[Mapping[str, object]] | None = None,
    label_audits: Sequence[Mapping[str, object]] | None = None,
    lawyer_reviews: Sequence[Mapping[str, object]] | None = None,
    lawyer_review_audits: Sequence[Mapping[str, object]] | None = None,
) -> CorpusReadinessReport:
    return build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=(
            unitization_audits
            if unitization_audits is not None
            else [_unitization_audit("cand-1")]
        ),
        unitization_review_records=unitization_reviews or [],
        unitization_adjudication_records=unitization_adjudications or [],
        label_records=[_label("unit-1")],
        label_audit_records=(
            label_audits if label_audits is not None else [_label_audit("cand-1")]
        ),
        lawyer_review_records=lawyer_reviews or [],
        lawyer_review_audit_records=lawyer_review_audits or [],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )


def test_stage_a_review_items_fail_closed_until_queue_is_adjudicated() -> None:
    audit = {
        "stage": "llm-unitize",
        "candidate_id": "cand-1",
        "status": "adjudication_pending",
        "review_items": [
            {
                "unit_id": "unit-1",
                "reason": "low_confidence",
                "notes": "Blinded review required.",
                "source_document_ids": ["cand-1-complaint"],
            }
        ],
    }
    queue_row = {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "candidate_id": "cand-1",
        "unit_id": "unit-1",
        "review_id": "cand-1:unit-1:stage-a-review",
        "status": "pending_adjudication",
        "route_reason": "low_confidence",
    }

    pending = _single_candidate_report(
        unitization_audits=[audit],
        unitization_reviews=[queue_row],
    )
    assert pending.clean_count == 0
    assert pending.funnel["unitized_complete"] == 0
    assert pending.exclusion_reasons["cand-1"] == ("stage_a_review_pending",)

    resolved = _single_candidate_report(
        unitization_audits=[audit],
        unitization_reviews=[queue_row],
        unitization_adjudications=[
            {
                "schema_version": "legalforecast.unitization_adjudication.v1",
                "adjudication_id": "adj-cand-1",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "review_ids": ["cand-1:unit-1:stage-a-review"],
                "source_unit_ids": ["unit-1"],
                "disposition": "ACCEPT",
                "adjudicator_id": "john-hughes",
                "adjudication_notes": "Frozen unit is sufficiently clear.",
            }
        ],
    )
    assert resolved.clean_candidate_ids == ("cand-1",)


def test_stage_a_review_rejects_adjudication_source_mismatch() -> None:
    audit = {
        "stage": "llm-unitize",
        "candidate_id": "cand-1",
        "status": "adjudication_pending",
        "review_items": [
            {"unit_id": "unit-1", "reason": "low_confidence", "notes": "Review."}
        ],
    }
    review = {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "candidate_id": "cand-1",
        "unit_id": "unit-1",
        "review_id": "cand-1:unit-1:stage-a-review",
        "status": "pending_adjudication",
        "route_reason": "low_confidence",
    }
    adjudication = {
        "adjudication_id": "adj-cand-1",
        "candidate_id": "cand-1",
        "review_ids": ["cand-1:unit-1:stage-a-review"],
        "source_unit_ids": ["other-unit"],
        "disposition": "ACCEPT",
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Reviewed.",
    }

    report = _single_candidate_report(
        unitization_audits=[audit],
        unitization_reviews=[review],
        unitization_adjudications=[adjudication],
    )

    assert "stage_a_review_adjudication_invalid" in report.exclusion_reasons["cand-1"]


def test_readiness_rejects_multiple_automatic_source_hashes() -> None:
    unit = _unit("cand-1", "unit-1")
    prediction_unit = cast(list[dict[str, object]], unit["prediction_units"])[0]
    prediction_unit["source_unit_sha256s"] = ["1" * 64, "2" * 64]

    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[unit],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[_label("unit-1")],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert "stage_a_finalized_hash_chain_invalid" in report.exclusion_reasons["cand-1"]


def test_readiness_rejects_two_selected_target_motions() -> None:
    selection = _selection("cand-1", "case-1")
    selection["target_motion_entry_numbers"] = [5, 6]
    report = build_clean_corpus_readiness(
        selection_records=[selection],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[_label("unit-1")],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.exclusion_reasons["cand-1"] == (
        "selected_target_motion_count_not_one",
    )


def test_required_stage_b_label_audit_fails_closed_until_passed() -> None:
    label_audit = {
        "stage": "llm-label",
        "candidate_id": "cand-1",
        "status": "adjudication_pending",
        "label_audit_gate": {
            "required": True,
            "status": "awaiting_human_adjudicated_labels",
            "sample_unit_ids": ["unit-1"],
        },
    }
    queue_row = {
        "candidate_id": "cand-1",
        "unit_id": "unit-1",
        "review_id": "cand-1:unit-1:label-audit",
        "status": "pending_adjudication",
        "route_reason": "label_audit_sample",
        "packet": {
            "blind_reliability_study": True,
            "materials": [
                {"kind": "unit_text"},
                {"kind": "decision_excerpt"},
            ],
        },
    }

    pending = _single_candidate_report(
        label_audits=[label_audit],
        lawyer_reviews=[queue_row],
    )
    assert pending.clean_count == 0
    assert pending.exclusion_reasons["cand-1"] == (
        "label_audit_pending",
        "lawyer_review_pending",
    )

    passed = _single_candidate_report(
        label_audits=[label_audit],
        lawyer_reviews=[queue_row],
        lawyer_review_audits=[
            {
                "stage": "lawyer-review-resume",
                "candidate_id": "cand-1",
                "review_id": "cand-1:unit-1:label-audit",
                "status": "succeeded",
            },
            {
                "stage": "label-audit-gate",
                "candidate_id": "cand-1",
                "status": "passed",
                "sample_unit_ids": ["unit-1"],
            },
        ],
    )
    assert passed.clean_candidate_ids == ("cand-1",)


def test_clean_corpus_readiness_joins_all_fail_closed_gates() -> None:
    selections = [
        _selection("cand-clean", "case-clean"),
        _selection("cand-review", "case-review"),
    ]
    parsers = [*_parsers("cand-clean"), *_parsers("cand-review")]
    units = [
        _unit("cand-clean", "unit-clean"),
        _unit("cand-review", "unit-review"),
    ]
    report = build_clean_corpus_readiness(
        selection_records=selections,
        parser_records=parsers,
        prediction_unit_records=units,
        unitization_audit_records=[
            _unitization_audit("cand-clean"),
            _unitization_audit("cand-review"),
        ],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[_label("unit-clean")],
        label_audit_records=[
            _label_audit("cand-clean"),
            {
                "stage": "llm-label",
                "candidate_id": "cand-review",
                "status": "adjudication_pending",
                "label_audit_gate": {
                    "required": True,
                    "status": "awaiting_human_adjudicated_labels",
                    "sample_unit_ids": ["unit-review"],
                },
            },
        ],
        lawyer_review_records=[
            {
                "candidate_id": "cand-review",
                "unit_id": "unit-review",
                "review_id": "cand-review:unit-review:label-audit",
                "status": "pending_adjudication",
                "route_reason": "label_audit_sample",
                "packet": {
                    "blind_reliability_study": True,
                    "materials": [
                        {"kind": "unit_text"},
                        {"kind": "decision_excerpt"},
                    ],
                },
            }
        ],
        lawyer_review_audit_records=[],
        packet_build_records=[
            {"candidate_id": "cand-clean"},
            {"candidate_id": "cand-review"},
        ],
        packet_records=[
            {
                "candidate_id": "cand-clean",
                "court": "S.D.N.Y.",
                "metadata": {"nos_macro_category": "contract"},
            },
            {
                "candidate_id": "cand-review",
                "court": "D. Del.",
                "metadata": {"nos_macro_category": "securities"},
            },
        ],
        exclusion_records=[],
        decision_text_by_candidate_and_document={
            **_decision_texts("cand-clean"),
            **_decision_texts("cand-review"),
        },
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.clean_candidate_ids == ("cand-clean",)
    assert report.clean_count == 1
    assert report.meets_target is True
    assert report.funnel["selected"] == 2
    assert report.funnel["labeled_complete"] == 1
    assert report.case_mix["court"] == {"S.D.N.Y.": 1}
    assert report.case_mix["nature_of_suit"] == {"unknown": 1}
    assert report.case_mix["nos_macro_category"] == {"contract": 1}
    assert report.case_mix["related_family_id"] == {"none": 1}
    assert report.case_mix["mdl_family_id"] == {"none": 1}
    assert all(
        sum(buckets.values()) == report.clean_count
        for buckets in report.case_mix.values()
    )
    assert report.exclusion_reasons["cand-review"] == (
        "stage_b_labels_incomplete",
        "label_audit_pending",
        "lawyer_review_pending",
    )


def test_clean_corpus_readiness_rejects_nonverbatim_or_preanchor_labels() -> None:
    label = _label("unit-1")
    label["first_written_disposition_date"] = "2026-06-29"
    label["supporting_citations"] = [
        {"document_id": "decision-1", "excerpt": "Count I is dismissed."},
        {"document_id": "decision-1", "excerpt": "Count II is dismissed."},
    ]
    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[label],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.clean_count == 0
    assert report.exclusion_reasons["cand-1"] == (
        "first_written_disposition_before_anchor",
        "stage_b_label_excerpt_not_verbatim",
    )
    with pytest.raises(CorpusReadinessError, match="requires 1 clean motions; found 0"):
        require_clean_corpus_ready(report)


def test_clean_corpus_readiness_honors_consolidated_exclusion_ledger() -> None:
    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[_label("unit-1")],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[
            {
                "candidate_id": "cand-1",
                "primary_exclusion_reason": "outcome_leakage",
            }
        ],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.clean_count == 0
    assert report.exclusion_reasons["cand-1"] == ("outcome_leakage",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fully_dismissed", None),
        ("amendment_class", "not_fully_dismissed"),
        ("label_confidence", 1.1),
        ("supporting_citations", []),
        ("first_written_disposition_locked", False),
        ("first_written_disposition_date", ""),
    ],
)
def test_clean_corpus_readiness_validates_canonical_outcome_label_schema(
    field: str,
    value: object,
) -> None:
    label = _label("unit-1")
    label[field] = value

    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[label],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.exclusion_reasons["cand-1"] == ("stage_b_label_schema_invalid",)


def test_clean_corpus_readiness_requires_citations_from_locked_disposition() -> None:
    label = _label("unit-1")
    label["supporting_citations"] = [
        {"document_id": "decision-1", "excerpt": "Count I is dismissed."},
        {"document_id": "later-decision", "excerpt": "Count I is dismissed."},
    ]

    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[label],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document=_decision_texts("cand-1"),
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.exclusion_reasons["cand-1"] == (
        "stage_b_citation_not_locked_disposition",
    )


def test_clean_corpus_readiness_requires_supplied_locked_disposition_text() -> None:
    report = build_clean_corpus_readiness(
        selection_records=[_selection("cand-1", "case-1")],
        parser_records=_parsers("cand-1"),
        prediction_unit_records=[_unit("cand-1", "unit-1")],
        unitization_audit_records=[_unitization_audit("cand-1")],
        unitization_review_records=[],
        unitization_adjudication_records=[],
        label_records=[_label("unit-1")],
        label_audit_records=[_label_audit("cand-1")],
        lawyer_review_records=[],
        lawyer_review_audit_records=[],
        packet_build_records=[{"candidate_id": "cand-1"}],
        packet_records=[{"candidate_id": "cand-1"}],
        exclusion_records=[],
        decision_text_by_candidate_and_document={},
        decision_filed_on_or_after=date(2026, 6, 30),
        required_clean_count=1,
    )

    assert report.exclusion_reasons["cand-1"] == (
        "first_written_disposition_text_missing",
    )
