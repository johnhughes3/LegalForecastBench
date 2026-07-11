from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.corpus_readiness import (
    CorpusReadinessError,
    build_clean_corpus_readiness,
    require_clean_corpus_ready,
)


def _selection(candidate_id: str, case_id: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "case_id": case_id,
        "court": "S.D.N.Y.",
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
    return {
        "candidate_id": candidate_id,
        "prediction_units": [{"unit_id": unit_id, "should_score": True}],
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
        label_records=[_label("unit-clean")],
        label_audit_records=[
            {"candidate_id": "cand-clean", "status": "succeeded"},
            {"candidate_id": "cand-review", "status": "adjudication_pending"},
        ],
        lawyer_review_records=[
            {
                "candidate_id": "cand-review",
                "unit_id": "unit-review",
                "status": "pending_adjudication",
            }
        ],
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
        "label_audit_incomplete",
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
        label_records=[label],
        label_audit_records=[{"candidate_id": "cand-1", "status": "succeeded"}],
        lawyer_review_records=[],
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
        label_records=[_label("unit-1")],
        label_audit_records=[{"candidate_id": "cand-1", "status": "succeeded"}],
        lawyer_review_records=[],
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
        label_records=[label],
        label_audit_records=[{"candidate_id": "cand-1", "status": "succeeded"}],
        lawyer_review_records=[],
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
        label_records=[label],
        label_audit_records=[{"candidate_id": "cand-1", "status": "succeeded"}],
        lawyer_review_records=[],
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
        label_records=[_label("unit-1")],
        label_audit_records=[{"candidate_id": "cand-1", "status": "succeeded"}],
        lawyer_review_records=[],
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
