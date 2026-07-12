from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.public_packet_planner import (
    plan_public_packet_downloads,
)


def test_public_packet_planner_selects_free_core_packet_documents(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(_docket_html(), encoding="utf-8")

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    assert plan.download_request_count == 4
    selected = plan.selected_cases[0]
    assert selected.exclusion_reasons == ()
    assert selected.decision_date == "2026-06-30"
    assert selected.to_record()["decision_date"] == "2026-06-30"
    assert [document.document_role for document in selected.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert selected.documents[-1].model_visible is False
    assert selected.documents[-1].contains_target_outcome is True
    assert plan.download_requests[0].source_url == (
        "https://storage.courtlistener.com/recap/complaint.pdf"
    )


def test_public_packet_planner_reports_public_document_shortfall(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html(include_motion=False),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 0
    assert plan.summary_record()["shortfall"] == 25
    assert len(plan.paid_gap_cases) == 1
    assert plan.final_exclusions == ()
    pending = plan.paid_gap_cases[0]
    assert pending.exclusion_reasons == ()
    assert pending.paid_gap_reasons == ("no_free_target_mtd_document",)
    assert pending.planning_status == "paid_recovery_required"
    assert [document.document_role for document in pending.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert len(plan.download_requests) == 3


@pytest.mark.parametrize("marker", ("sealed", "under seal", "restricted", "private"))
def test_public_packet_planner_excludes_restricted_core_document_text(
    tmp_path: Path,
    marker: str,
) -> None:
    record = _screened_case_with_embedded_entries()
    selected_entries = cast(list[dict[str, Any]], record["selected_entries"])
    target_document = cast(list[dict[str, Any]], selected_entries[1]["documents"])[0]
    restriction_text = marker if marker == "under seal" else f"{marker} document"
    target_document["description"] = f"Motion to Dismiss - {restriction_text}"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [excluded] = plan.final_exclusions
    assert not plan.download_requests
    assert excluded.paid_recovery_required is False
    assert excluded.exclusion_reasons[0].startswith(
        "sealed_or_restricted_material:target_mtd_entry_5:"
    )


@pytest.mark.parametrize(
    "merits_phrase",
    (
        "private right of action",
        "private securities litigation",
        "restricted stock",
        "sealed bid",
        "sealed instrument",
    ),
)
def test_public_packet_planner_does_not_treat_merits_prose_as_access_restriction(
    tmp_path: Path,
    merits_phrase: str,
) -> None:
    record = _screened_case_with_embedded_entries()
    selected_entries = cast(list[dict[str, Any]], record["selected_entries"])
    target_document = cast(list[dict[str, Any]], selected_entries[1]["documents"])[0]
    target_document["description"] = f"Motion to Dismiss concerning {merits_phrase}"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    assert len(plan.selected_cases) == 1
    assert plan.final_exclusions == ()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("is_sealed", True),
        ("is_private", True),
        ("is_restricted", True),
        ("availability_status", "restricted"),
        ("redaction_or_seal_status", "under_seal"),
        ("visibility", "private"),
    ),
)
def test_public_packet_planner_excludes_explicit_restricted_document_status(
    tmp_path: Path,
    field_name: str,
    field_value: object,
) -> None:
    record = _screened_case_with_embedded_entries()
    selected_entries = cast(list[dict[str, Any]], record["selected_entries"])
    target_document = cast(list[dict[str, Any]], selected_entries[1]["documents"])[0]
    target_document[field_name] = field_value

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [excluded] = plan.final_exclusions
    assert not plan.download_requests
    assert excluded.exclusion_reasons[0].startswith(
        "sealed_or_restricted_material:target_mtd_entry_5:"
    )


def test_public_packet_planner_excludes_explicit_restricted_candidate_status(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    candidate = cast(dict[str, Any], record["candidate"])
    metadata = cast(dict[str, Any], candidate["metadata"])
    metadata["is_private"] = True

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [excluded] = plan.final_exclusions
    assert not plan.download_requests
    assert excluded.exclusion_reasons == (
        "sealed_or_restricted_material:candidate:field_isprivate",
    )


def test_public_packet_planner_excludes_restricted_raw_html_document(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    html = _docket_html().replace("<p>Dismiss</p>", "<p>Dismiss - Under Seal</p>")
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=1,
    )

    [excluded] = plan.final_exclusions
    assert not plan.download_requests
    assert excluded.exclusion_reasons[0].startswith(
        "sealed_or_restricted_material:target_mtd_entry_5:"
    )


def test_public_packet_planner_excludes_missing_first_disposition_date(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(_docket_html(), encoding="utf-8")
    record = _screened_case()
    del record["first_written_mtd_disposition_date"]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 0
    assert plan.candidate_plans[0].exclusion_reasons == (
        "first_written_mtd_disposition_date_missing",
    )


def test_public_packet_planner_uses_role_matched_free_documents(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html_with_procedural_false_positives(),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    planned_roles = [
        (document.document_role, document.description)
        for document in selected.documents
    ]
    assert planned_roles == [
        (DocumentRole.COMPLAINT, "Complaint"),
        (DocumentRole.MTD_MEMORANDUM, "Memorandum of Law"),
        (DocumentRole.DECISION, "Order on Motion to Dismiss"),
    ]
    assert selected.documents[0].source_url == (
        "https://storage.courtlistener.com/recap/complaint.pdf"
    )
    assert selected.documents[1].source_url == (
        "https://storage.courtlistener.com/recap/mtd-memo.pdf"
    )


def test_public_packet_planner_prefers_removal_complaint_attachment(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html_with_notice_removal_complaint_attachment(),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[0].document_role is DocumentRole.COMPLAINT
    assert selected.documents[0].description == "Exhibit A-E"
    assert selected.documents[0].source_url == (
        "https://storage.courtlistener.com/recap/removal-exhibit-a-e.pdf"
    )


def test_public_packet_planner_accepts_judgment_on_pleadings_target(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    html = (
        _docket_html()
        .replace(
            "MOTION to Dismiss filed by Defendant.",
            "MOTION for Judgment on the Pleadings filed by Defendant.",
        )
        .replace(
            "Dismiss</p>",
            "Judgment on the Pleadings</p>",
            1,
        )
    )
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_NOTICE
    assert selected.documents[1].description == "Judgment on the Pleadings"


def test_public_packet_planner_can_use_embedded_selected_entries(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"

    plan = plan_public_packet_downloads(
        (_screened_case_with_embedded_entries(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert [document.document_role for document in selected.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ]
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/5/example/"
    )


def test_public_packet_planner_accepts_exact_target_mtd_memorandum_when_role_is_noisy(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"

    record = _screened_case_with_embedded_entries()
    target_entry = record["selected_entries"][1]
    assert isinstance(target_entry, dict)
    target_entry["text"] = (
        "5 Feb 1, 2026 Notice of manual filing of MOTION to Dismiss by "
        "Defendant. Text of Proposed Order."
    )
    target_entry["documents"] = [
        {
            "kind": "Main Document",
            "description": "Dismiss for Failure to State a Claim",
            "href": "https://ecf.example.invalid/doc1",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        },
        {
            "kind": "Att 1 attachment",
            "description": "Memorandum",
            "href": "https://www.courtlistener.com/docket/123/5/1/example/",
            "action_label": "Download PDF",
            "pacer_only": False,
        },
        {
            "kind": "Att 2 attachment",
            "description": "Text of Proposed Order",
            "href": "https://ecf.example.invalid/doc2",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        },
    ]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/5/1/example/"
    )


def test_public_packet_planner_prefers_free_support_memo_for_pacer_only_target(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    record = _screened_case_with_embedded_entries()
    target_entry = record["selected_entries"][1]
    assert isinstance(target_entry, dict)
    target_entry["documents"] = [
        {
            "kind": "Main Document",
            "description": "Dismiss",
            "href": "https://ecf.example.invalid/doc1",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    ]
    record["selected_entries"].insert(
        2,
        {
            "row_id": "entry-6",
            "entry_number": "6",
            "filed_at": "Feb 2, 2026",
            "text": "6 Feb 2, 2026 Memorandum in Support re 5 MOTION to Dismiss.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Memorandum",
                    "href": "https://www.courtlistener.com/docket/123/6/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                },
            ],
        },
    )
    record["selected_entries"].insert(
        3,
        {
            "row_id": "entry-7",
            "entry_number": "7",
            "filed_at": "Feb 3, 2026",
            "text": "7 Feb 3, 2026 MOTION to Dismiss unrelated crossclaim.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/7/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                },
            ],
        },
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        allow_inferred_target_mtd=True,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/6/example/"
    )


def test_public_packet_planner_combines_exact_and_inferred_target_documents(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    record["ai"]["target_motion_entry_numbers"] = ["5", "6"]
    record["selected_entries"].extend(
        [
            {
                "row_id": "entry-6",
                "entry_number": "6",
                "filed_at": "Feb 2, 2026",
                "text": "6 Feb 2, 2026 MOTION to Dismiss filed by Defendant.",
                "documents": [
                    {
                        "kind": "Main Document",
                        "description": "Dismiss",
                        "href": "https://ecf.example.invalid/mtd-6",
                        "action_label": "Buy on PACER",
                        "pacer_only": True,
                    }
                ],
            },
            {
                "row_id": "entry-7",
                "entry_number": "7",
                "filed_at": "Feb 3, 2026",
                "text": "7 Feb 3, 2026 Memorandum in Support re 6 Motion to Dismiss.",
                "documents": [
                    {
                        "kind": "Main Document",
                        "description": "Memorandum",
                        "href": "https://www.courtlistener.com/docket/123/7/example/",
                        "action_label": "Download PDF",
                        "pacer_only": False,
                    }
                ],
            },
        ]
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        allow_inferred_target_mtd=True,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    target_documents = [
        document
        for document in candidate.documents
        if document.document_role
        in {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}
    ]
    assert [document.docket_entry_number for document in target_documents] == [5, 7]
    assert candidate.missing_required_document_count == 0


def test_public_packet_planner_ranks_full_pool_by_exact_required_document_cost(
    tmp_path: Path,
) -> None:
    expensive = _screened_case_with_embedded_entries()
    expensive["candidate"]["docket_id"] = "200"
    expensive["candidate"]["candidate_key"] = "200"
    expensive["candidate"]["metadata"]["case_id"] = "200"
    complaint = expensive["selected_entries"][0]
    complaint["documents"][0].update(
        href="https://ecf.example.invalid/complaint",
        action_label="Buy on PACER",
        pacer_only=True,
        freely_available=False,
    )
    cheap = deepcopy(_screened_case_with_embedded_entries())
    cheap["candidate"]["docket_id"] = "100"
    cheap["candidate"]["candidate_key"] = "100"
    cheap["candidate"]["metadata"]["case_id"] = "100"

    plan = plan_public_packet_downloads(
        (expensive, cheap),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    assert [candidate.candidate_id for candidate in plan.planned_cases] == ["100"]
    assert plan.planned_cases[0].cost_rank == 1
    reserve = next(
        candidate
        for candidate in plan.final_exclusions
        if candidate.candidate_id == "200"
    )
    assert reserve.exclusion_reasons == ("higher_projected_acquisition_cost",)
    assert reserve.cost_rank == 2
    assert reserve.missing_required_document_count == 1
    assert reserve.projected_paid_cost_usd == "3.05"


def test_public_packet_planner_costs_every_linked_required_entry_once(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    record["ai"] = {
        "target_motion_entry_numbers": ["5", "6"],
        "decision_entry_numbers": ["16", "17"],
    }
    record["selected_entries"].extend(
        [
            {
                "row_id": "entry-6",
                "entry_number": "6",
                "filed_at": "Feb 2, 2026",
                "text": "6 Feb 2, 2026 MOTION to Dismiss filed by Defendant.",
                "documents": [
                    {
                        "kind": "Main Document",
                        "description": "Dismiss",
                        "href": "https://ecf.example.invalid/mtd-6",
                        "action_label": "Buy on PACER",
                        "pacer_only": True,
                    }
                ],
            },
            {
                "row_id": "entry-17",
                "entry_number": "17",
                "filed_at": "May 9, 2026",
                "text": "17 May 9, 2026 ORDER on Motion to Dismiss.",
                "documents": [
                    {
                        "kind": "Main Document",
                        "description": "Order on Motion to Dismiss",
                        "href": "https://ecf.example.invalid/order-17",
                        "action_label": "Buy on PACER",
                        "pacer_only": True,
                    }
                ],
            },
            {
                "row_id": "entry-12",
                "entry_number": "12",
                "filed_at": "Mar 1, 2026",
                "text": (
                    "12 Mar 1, 2026 Response in Opposition re 5 Motion to Dismiss."
                ),
                "documents": [
                    {
                        "kind": "Main Document",
                        "description": "Opposition",
                        "href": "https://ecf.example.invalid/opposition",
                        "action_label": "Buy on PACER",
                        "pacer_only": True,
                    }
                ],
            },
        ]
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.planned_cases
    assert candidate.required_document_count == 6
    assert candidate.free_required_document_count == 3
    assert candidate.missing_required_document_count == 3
    assert candidate.projected_paid_cost_usd == "9.15"
    assert candidate.paid_gap_reasons == (
        "no_free_target_mtd_document:6",
        "no_free_decision_document:17",
        "no_free_opposition_document",
    )
    assert plan.summary_record()["projected_paid_cost_usd"] == "9.15"


def test_public_packet_planner_deduplicates_linked_entry_numbers(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    record["ai"] = {
        "target_motion_entry_numbers": ["5", "5"],
        "decision_entry_numbers": ["16", "16"],
    }

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert candidate.target_motion_entry_numbers == (5,)
    assert candidate.decision_entry_numbers == (16,)
    assert candidate.required_document_count == 3
    assert candidate.missing_required_document_count == 0


def test_public_packet_planner_ignores_opposition_explicitly_tied_to_other_motion(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    record["selected_entries"].append(
        {
            "row_id": "entry-12",
            "entry_number": "12",
            "filed_at": "Mar 1, 2026",
            "text": "12 Response in Opposition re 99 Motion to Dismiss.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Opposition",
                    "href": "https://ecf.example.invalid/opposition-99",
                    "action_label": "Buy on PACER",
                    "pacer_only": True,
                }
            ],
        }
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert candidate.required_document_count == 3
    assert candidate.paid_gap_reasons == ()


def test_public_packet_planner_applies_mix_caps_after_cost_ranking(
    tmp_path: Path,
) -> None:
    records = []
    for candidate_id, court in (
        ("100", "Court A"),
        ("200", "Court A"),
        ("300", "Court B"),
    ):
        record = deepcopy(_screened_case_with_embedded_entries())
        record["candidate"]["docket_id"] = candidate_id
        record["candidate"]["candidate_key"] = candidate_id
        record["candidate"]["metadata"]["case_id"] = candidate_id
        record["candidate"]["metadata"]["court"] = court
        records.append(record)

    plan = plan_public_packet_downloads(
        records,
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=2,
        max_case_mix_share=0.5,
        use_embedded_entries=True,
    )

    assert [candidate.candidate_id for candidate in plan.planned_cases] == [
        "100",
        "300",
    ]
    reserve = next(
        candidate
        for candidate in plan.final_exclusions
        if candidate.candidate_id == "200"
    )
    assert reserve.exclusion_reasons == ("case_mix_cap_reached:court:Court A",)


def test_public_packet_planner_uses_complaint_before_earliest_target_motion(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    record["selected_entries"].append(
        {
            "row_id": "entry-10",
            "entry_number": "10",
            "filed_at": "Mar 1, 2026",
            "text": "10 Mar 1, 2026 AMENDED COMPLAINT filed by Plaintiff.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "First Amended Complaint",
                    "href": "https://www.courtlistener.com/docket/123/10/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                }
            ],
        }
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert candidate.documents[0].docket_entry_number == 1


def _screened_case() -> dict[str, object]:
    return {
        "first_written_mtd_disposition_date": "2026-06-30",
        "candidate": {
            "docket_id": "123",
            "candidate_key": "123",
            "metadata": {
                "case_id": "123",
                "case_name": "Example v. Defendant",
                "court": "District Court, D. Example",
                "docket_number": "1:26-cv-1",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
    }


def _screened_case_with_embedded_entries() -> dict[str, object]:
    record = _screened_case()
    record["selected_entries"] = [
        {
            "row_id": "entry-1",
            "entry_number": "1",
            "filed_at": "Jan 1, 2026",
            "text": "1 Jan 1, 2026 COMPLAINT filed by Plaintiff.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Complaint",
                    "href": "https://www.courtlistener.com/docket/123/1/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
        {
            "row_id": "entry-5",
            "entry_number": "5",
            "filed_at": "Feb 1, 2026",
            "text": "5 Feb 1, 2026 MOTION to Dismiss filed by Defendant.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/5/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
        {
            "row_id": "entry-16",
            "entry_number": "16",
            "filed_at": "May 8, 2026",
            "text": "16 May 8, 2026 ORDER on Motion to Dismiss.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Order on Motion to Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/16/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
    ]
    return record


def _docket_html(*, include_motion: bool = True) -> str:
    motion = (
        """
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        """
        if include_motion
        else ""
    )
    return f"""
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>COMPLAINT filed by Plaintiff.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Complaint</p></div>
                <a href="https://storage.courtlistener.com/recap/complaint.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          {motion}
          <div class="row even" id="entry-8">
            <div class="col-xs-1 text-center"><p>8</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 15, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>Opposition to Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Opposition to Motion</p></div>
                <a href="https://storage.courtlistener.com/recap/opp.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _docket_html_with_procedural_false_positives() -> str:
    return """
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>COMPLAINT filed by Plaintiff.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Complaint</p></div>
                <a href="https://storage.courtlistener.com/recap/complaint.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-2">
            <div class="col-xs-1 text-center"><p>2</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 2, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>STANDING ORDER upon filing of the complaint.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6">
                  <p>Initial Order upon Filing of Complaint - form only</p>
                </div>
                <a href="https://storage.courtlistener.com/recap/initial-order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Motion to Dismiss</p></div>
                <a href="https://ecf.example.invalid/doc1">Buy on PACER</a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Att 1 achment</p></div>
                <div class="col-xs-6"><p>Declaration</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd-decl.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Att 2 achment</p></div>
                <div class="col-xs-6"><p>Memorandum of Law</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd-memo.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-9">
            <div class="col-xs-1 text-center"><p>9</p></div>
            <div class="col-xs-3 col-sm-2"><p>Mar 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>Exhibit mentioning facts alleged in the amended complaint.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6">
                  <p>Exhibit 3: Timeline (Alleged in the Amended Complaint)</p>
                </div>
                <a href="https://storage.courtlistener.com/recap/timeline.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _docket_html_with_notice_removal_complaint_attachment() -> str:
    return """
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>NOTICE OF REMOVAL from state court. (Attachments: # 1 Exhibit A-E)
              Exhibit A: Complaint and all accompanying documents.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Notice of Removal</p></div>
                <a href="https://storage.courtlistener.com/recap/removal-main.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Attachment 1</p></div>
                <div class="col-xs-6"><p>Exhibit A-E</p></div>
                <a href="https://storage.courtlistener.com/recap/removal-exhibit-a-e.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Attachment 2</p></div>
                <div class="col-xs-6"><p>Civil Cover Sheet</p></div>
                <a href="https://storage.courtlistener.com/recap/cover-sheet.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
