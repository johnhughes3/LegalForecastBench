from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)


def test_numbered_legacy_decision_screen_binds_by_entry_number() -> None:
    evidence = _evidence()
    evidence["mtd_decision_screen"]["decision_entries"][0].pop("row_id")

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id="courtlistener-docket-73330394",
    )


def test_unnumbered_actual_decision_is_accepted_when_selected_linked_and_earliest() -> (
    None
):
    evidence = _evidence_with_unnumbered_decision()
    evidence["first_written_mtd_disposition_date"] = "2026-07-01"

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id="courtlistener-docket-73330394",
    )


def test_unnumbered_actual_decision_must_be_linked() -> None:
    evidence = _evidence_with_unnumbered_decision()
    evidence["first_written_mtd_disposition_date"] = "2026-07-01"
    evidence["motion_linkage"]["links"][0]["disposition_entry_ids"].remove(
        "minute-entry-2"
    )

    with pytest.raises(
        StrictScreenEvidenceError,
        match="does not bind the selected and earliest screened MTD disposition",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id="courtlistener-docket-73330394",
        )


def test_later_unnumbered_actual_decision_need_not_be_benchmark_linked() -> None:
    evidence = _evidence_with_unnumbered_decision()
    unnumbered = evidence["selected_entries"][-1]
    unnumbered["filed_at"] = "2026-07-03"
    evidence["mtd_decision_screen"]["decision_entries"][-1]["filed_at"] = "2026-07-03"
    evidence["motion_linkage"]["links"][0]["disposition_entry_ids"].remove(
        "minute-entry-2"
    )

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id="courtlistener-docket-73330394",
    )


def test_later_same_day_timed_decision_need_not_be_benchmark_linked() -> None:
    evidence = _evidence()
    evidence["selected_entries"][1]["filed_at"] = "July 2, 2026, 9:52 a.m."
    evidence["mtd_decision_screen"]["decision_entries"][0]["filed_at"] = (
        "July 2, 2026, 9:52 a.m."
    )
    evidence["selected_entries"].append(
        {
            "row_id": "entry-13",
            "entry_number": "13",
            "filed_at": "July 2, 2026, 9:54 a.m.",
            "text": "Later written order on another dismissal issue.",
            "role": "decision",
            "restriction_markers": [],
            "documents": [],
        }
    )
    evidence["mtd_decision_screen"]["decision_entries"].append(
        {
            "row_id": "entry-13",
            "entry_number": "13",
            "filed_at": "July 2, 2026, 9:54 a.m.",
            "actual_mtd_decision": True,
            "exclusion_reasons": [],
        }
    )
    evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = 2

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id="courtlistener-docket-73330394",
    )


def test_first_written_date_must_equal_earliest_actual_screened_decision() -> None:
    evidence = _evidence_with_unnumbered_decision()

    with pytest.raises(
        StrictScreenEvidenceError,
        match="does not match the earliest screened MTD disposition",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id="courtlistener-docket-73330394",
        )


def test_anchor_entries_must_include_every_actual_screened_decision() -> None:
    evidence = _evidence()
    evidence["selected_entries"].append(
        {
            "row_id": "entry-11",
            "entry_number": "11",
            "filed_at": "2026-07-01",
            "text": "Earlier written order denying the motion to dismiss.",
            "role": "decision",
            "restriction_markers": [],
            "documents": [],
        }
    )
    evidence["mtd_decision_screen"]["decision_entries"].append(
        {
            "row_id": "entry-11",
            "entry_number": "11",
            "filed_at": "2026-07-01",
            "actual_mtd_decision": True,
            "exclusion_reasons": [],
        }
    )
    evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = 2
    evidence["mtd_decision_screen"]["anchor_disposition_entries"] = [
        {
            "row_id": "entry-12",
            "entry_number": "12",
            "filed_at": "2026-07-02",
        }
    ]

    with pytest.raises(
        StrictScreenEvidenceError,
        match="anchor screen omits an actual screened MTD decision",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id="courtlistener-docket-73330394",
        )


def test_earlier_generic_anchor_need_not_be_benchmark_linked() -> None:
    evidence = _evidence()
    evidence["selected_entries"].append(
        {
            "row_id": "entry-11",
            "entry_number": "11",
            "filed_at": "2026-07-01",
            "text": "Order on Motion to Dismiss.",
            "role": "decision",
            "restriction_markers": [],
            "documents": [],
        }
    )
    evidence["first_written_mtd_disposition_date"] = "2026-07-01"
    evidence["mtd_decision_screen"]["anchor_disposition_entries"] = [
        {
            "row_id": "entry-11",
            "entry_number": "11",
            "filed_at": "2026-07-01",
        },
        {
            "row_id": "entry-12",
            "entry_number": "12",
            "filed_at": "2026-07-02",
        },
    ]

    validate_strict_screen_evidence(
        evidence,
        expected_candidate_id="courtlistener-docket-73330394",
    )


def test_decision_row_id_and_entry_number_must_identify_the_same_selected_row() -> None:
    evidence = _evidence()
    evidence["mtd_decision_screen"]["decision_entries"][0]["row_id"] = "entry-5"

    with pytest.raises(
        StrictScreenEvidenceError,
        match="row ID and entry number disagree",
    ):
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id="courtlistener-docket-73330394",
        )


def _evidence_with_unnumbered_decision() -> dict[str, Any]:
    evidence = deepcopy(_evidence())
    evidence["selected_entries"].append(
        {
            "row_id": "minute-entry-2",
            "entry_number": None,
            "filed_at": "2026-07-01",
            "text": "Text Order terminating the motion to dismiss.",
            "role": "decision",
            "restriction_markers": [],
            "documents": [],
        }
    )
    evidence["mtd_decision_screen"]["decision_entries"].append(
        {
            "row_id": "minute-entry-2",
            "entry_number": None,
            "filed_at": "2026-07-01",
            "actual_mtd_decision": True,
            "exclusion_reasons": [],
        }
    )
    evidence["mtd_decision_screen"]["actual_mtd_decision_entry_count"] = 2
    evidence["motion_linkage"]["links"][0]["disposition_entry_ids"].append(
        "minute-entry-2"
    )
    return evidence


def _evidence() -> dict[str, Any]:
    candidate_id = "courtlistener-docket-73330394"
    docket_id = "73330394"
    return {
        "candidate_id": candidate_id,
        "candidate": {
            "docket_id": docket_id,
            "candidate_key": docket_id,
            "metadata": {
                "case_id": candidate_id,
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["12"],
        },
        "first_written_mtd_disposition_date": "2026-07-02",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            {
                "row_id": "entry-5",
                "entry_number": "5",
                "filed_at": "2026-06-30",
                "text": "Motion to dismiss.",
                "role": "mtd_notice",
                "restriction_markers": [],
                "documents": [],
            },
            {
                "row_id": "entry-12",
                "entry_number": "12",
                "filed_at": "2026-07-02",
                "text": "Order granting the motion to dismiss.",
                "role": "decision",
                "restriction_markers": [],
                "documents": [],
            },
        ],
        "mtd_decision_screen": {
            "status": "accepted_strict_civil_mtd_decision",
            "exclusion_reasons": [],
            "actual_mtd_decision_entry_count": 1,
            "decision_entries": [
                {
                    "row_id": "entry-12",
                    "entry_number": "12",
                    "filed_at": "2026-07-02",
                    "actual_mtd_decision": True,
                    "exclusion_reasons": [],
                }
            ],
        },
        "motion_linkage": {
            "candidate_id": docket_id,
            "case_id": candidate_id,
            "is_clean": True,
            "links": [
                {
                    "candidate_id": docket_id,
                    "case_id": candidate_id,
                    "motion_entry_ids": ["entry-5"],
                    "disposition_entry_ids": ["entry-12"],
                    "linkage_basis": ["fixture"],
                }
            ],
            "exclusion_entries": [],
        },
    }
