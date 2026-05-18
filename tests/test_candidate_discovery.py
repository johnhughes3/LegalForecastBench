from __future__ import annotations

import pytest
from legalforecast.selection.candidate_discovery import (
    DocketEntryRecord,
    classify_docket_entry,
    discover_mtd_candidates,
    mtd_discovery_search_terms,
)


def _entry(
    case_id: str,
    docket_entry_id: str,
    text: str,
) -> DocketEntryRecord:
    return DocketEntryRecord(
        case_id=case_id,
        docket_entry_id=docket_entry_id,
        entry_text=text,
    )


def test_search_terms_include_dismissal_and_rule_12_queries() -> None:
    terms = set(mtd_discovery_search_terms())

    assert "motion to dismiss" in terms
    assert "dismissal of complaint" in terms
    assert "Rule 12" in terms
    assert "12(b)(6)" in terms
    assert "order granting motion to dismiss" in terms


@pytest.mark.parametrize(
    ("text", "expected_term"),
    [
        ("Defendant's motion to dismiss complaint", "motion to dismiss"),
        ("MTD filed by all defendants", "MTD"),
        ("Rule 12(b)(6) motion filed", "Rule 12"),
        ("Fed. R. Civ. P. 12(c) motion", "Fed. R. Civ. P. 12"),
        ("Motion to dismiss amended complaint", "dismiss amended complaint"),
    ],
)
def test_classify_docket_entry_records_mtd_triggers(
    text: str,
    expected_term: str,
) -> None:
    signals = classify_docket_entry(_entry("case-1", "entry-1", text))

    assert expected_term in signals.mtd_trigger_terms
    assert signals.is_qualifying_mtd_entry is True


def test_discover_candidate_records_case_level_trigger_diagnostics() -> None:
    candidates = discover_mtd_candidates(
        [
            _entry("case-1", "entry-12", "Motion to dismiss under Rule 12(b)(6)."),
            _entry(
                "case-1",
                "entry-35",
                "Order granting in part and denying in part motion to dismiss.",
            ),
        ]
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.case_id == "case-1"
    assert candidate.candidate_entry_ids == ("entry-12", "entry-35")
    assert candidate.qualifying_mtd_entry_ids == ("entry-12", "entry-35")
    assert "motion to dismiss" in candidate.mtd_trigger_terms
    assert "12(b)(6)" in candidate.mtd_trigger_terms
    assert "order granting in part and denying in part motion to dismiss" in (
        candidate.order_trigger_terms
    )


@pytest.mark.parametrize(
    "text",
    [
        "Notice of voluntary dismissal filed by plaintiff.",
        "Stipulation of dismissal as to defendant Smith.",
        "Dismissal for failure to prosecute.",
        "Clerk's judgment entered.",
        "Administrative closure.",
        "Motion to dismiss appeal.",
        "Motion to dismiss counterclaim only.",
        "Order of dismissal.",
    ],
)
def test_common_false_positives_do_not_create_candidates(text: str) -> None:
    candidates = discover_mtd_candidates([_entry("case-1", "entry-1", text)])

    assert candidates == ()


def test_false_positive_entry_is_kept_as_diagnostic_when_linked_to_mtd() -> None:
    candidates = discover_mtd_candidates(
        [
            _entry("case-1", "entry-10", "Motion to dismiss complaint filed."),
            _entry("case-1", "entry-11", "Notice of voluntary dismissal of Doe."),
        ]
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.has_linked_false_positive is True
    assert candidate.false_positive_entry_ids == ("entry-11",)
    assert "notice of voluntary dismissal" in candidate.false_positive_terms


def test_generic_dismissal_order_is_not_enough_without_linked_mtd() -> None:
    candidates = discover_mtd_candidates(
        [_entry("case-1", "entry-44", "Claims dismissed without prejudice.")]
    )

    assert candidates == ()


def test_generic_dismissal_order_links_to_qualifying_mtd_entry() -> None:
    candidates = discover_mtd_candidates(
        [
            _entry("case-1", "entry-20", "Defendant moves to dismiss complaint."),
            _entry("case-1", "entry-45", "Claims dismissed without prejudice."),
        ]
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.candidate_entry_ids == ("entry-20", "entry-45")
    assert "dismissed without prejudice" in candidate.order_trigger_terms


def test_mapping_input_accepts_case_dev_style_fields() -> None:
    candidates = discover_mtd_candidates(
        [
            {
                "caseId": "case-1",
                "docketEntryId": "entry-1",
                "text": "Rule 12(b)(1) and 12(b)(6) motion",
            }
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].case_id == "case-1"
    assert "12(b)(1)" in candidates[0].mtd_trigger_terms
    assert "12(b)(6)" in candidates[0].mtd_trigger_terms


def test_missing_mapping_fields_fail_with_actionable_error() -> None:
    with pytest.raises(ValueError, match="case_id"):
        discover_mtd_candidates([{"text": "Motion to dismiss"}])
