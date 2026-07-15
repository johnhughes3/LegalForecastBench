from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from itertools import permutations
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.public_packet_planner import (
    plan_public_packet_downloads,
)

_REPLY_URL = "https://www.courtlistener.com/docket/123/10/example/"


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
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert selected.documents[-1].model_visible is False
    assert selected.documents[-1].contains_target_outcome is True
    for document in cast(list[dict[str, object]], selected.to_record()["documents"]):
        assert document["redaction_or_seal_status"] == "public"
        assert document["restriction_evidence"] == [
            "courtlistener_public_download_record_checked"
        ]
        assert document["is_sealed"] is None
        assert document["is_private"] is None
    assert plan.download_requests[0].source_url == (
        "https://storage.courtlistener.com/recap/complaint.pdf"
    )


def test_opinion_backed_decision_is_free_and_never_model_visible(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    decision = cast(list[dict[str, Any]], record["selected_entries"])[-1]
    [document] = cast(list[dict[str, Any]], decision["documents"])
    document.update(
        description="CourtListener Opinion 11395231 on Motion to Dismiss",
        href=(
            "https://storage.courtlistener.com/"
            "pdf/2026/07/14/bullock_v._phh_mortgage_services.pdf"
        ),
        action_label="Download PDF",
        pacer_only=False,
        freely_available=True,
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    decision_documents = [
        item
        for item in candidate.documents
        if item.document_role is DocumentRole.DECISION
    ]
    assert len(decision_documents) == 1
    assert decision_documents[0].model_visible is False
    assert decision_documents[0].contains_target_outcome is True
    assert candidate.missing_required_document_count == 0
    assert any(
        request.source_url.endswith("bullock_v._phh_mortgage_services.pdf")
        for request in plan.download_requests
    )


def test_unrestricted_reply_with_null_metadata_remains_public_and_selected(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    entries = cast(list[dict[str, object]], record["selected_entries"])
    entries.insert(2, _reply_entry())

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    [reply] = [
        document
        for document in candidate.to_record()["documents"]
        if document["document_role"] == "reply"
    ]
    assert reply["redaction_or_seal_status"] == "public"
    assert reply["restriction_evidence"] == [
        "courtlistener_public_download_record_checked"
    ]
    assert reply["is_sealed"] is None
    assert reply["is_private"] is None


@pytest.mark.parametrize("restriction_location", ("entry", "document"))
def test_restricted_optional_reply_is_omitted_without_excluding_case(
    tmp_path: Path,
    restriction_location: str,
) -> None:
    record = _screened_case_with_embedded_entries()
    entries = cast(list[dict[str, object]], record["selected_entries"])
    reply = _reply_entry()
    if restriction_location == "entry":
        reply["restriction_markers"] = ["field_issealed"]
    else:
        [document] = cast(list[dict[str, object]], reply["documents"])
        document["restriction_markers"] = ["field_issealed"]
    entries.insert(2, reply)

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert all(
        document.document_role is not DocumentRole.REPLY
        for document in candidate.documents
    )
    assert all(request.source_url != _REPLY_URL for request in plan.download_requests)
    assert plan.final_exclusions == ()


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
    assert pending.paid_gap_reasons == (
        "no_free_target_mtd_document",
        "no_free_mtd_memorandum",
    )
    assert pending.planning_status == "paid_recovery_required"
    assert [document.document_role for document in pending.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert len(plan.download_requests) == 3


def test_bare_mtd_notice_is_a_paid_memorandum_gap(tmp_path: Path) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = (
        "Motion to Dismiss"
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert candidate.paid_gap_reasons == ("no_free_mtd_memorandum",)
    assert candidate.missing_required_document_count == 1


def test_explicit_combined_motion_and_memorandum_satisfies_memorandum_slot(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    target["text"] = (
        "5 MOTION to Dismiss and Memorandum of Points and Authorities in "
        "Support filed by Defendant."
    )
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = "Dismiss"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert candidate.documents[1].document_role is DocumentRole.MTD_MEMORANDUM


def test_motion_description_without_combined_briefing_cue_remains_notice(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    target["text"] = "5 MOTION to Dismiss filed by Defendant."
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = "Dismiss"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [gap] = plan.paid_gap_cases
    assert gap.paid_gap_reasons == ("no_free_mtd_memorandum",)


def test_exact_frozen_target_uses_free_mtd_role_document_when_row_text_is_noisy(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    target["text"] = "5 Feb 1, 2026 Main Document Dismiss Download PDF"
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = "Dismiss"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert candidate.paid_gap_reasons == ("no_free_mtd_memorandum",)
    target_documents = [
        document
        for document in candidate.documents
        if document.docket_entry_number == 5
    ]
    assert [document.document_role for document in target_documents] == [
        DocumentRole.MTD_NOTICE
    ]


@pytest.mark.parametrize("description", ("Remand", "Proposed Order", "Exhibit A"))
def test_exact_frozen_target_rejects_non_mtd_document_roles(
    tmp_path: Path,
    description: str,
) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    target["text"] = f"5 Feb 1, 2026 Main Document {description} Download PDF"
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = description

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert candidate.paid_gap_reasons == (
        "no_free_target_mtd_document",
        "no_free_mtd_memorandum",
    )


def test_exact_target_document_rule_does_not_infer_entry_number(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    target = cast(list[dict[str, Any]], record["selected_entries"])[1]
    target["entry_number"] = None
    target["text"] = "Main Document Dismiss Download PDF"
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = "Dismiss"

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        allow_inferred_target_mtd=True,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert "no_free_target_mtd_document" in candidate.paid_gap_reasons


def test_exact_target_document_rule_does_not_use_adjacent_role_match(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    entries = cast(list[dict[str, Any]], record["selected_entries"])
    target = entries[1]
    target["text"] = "5 Feb 1, 2026 Main Document Exhibit Download PDF"
    cast(list[dict[str, Any]], target["documents"])[0]["description"] = "Exhibit A"
    adjacent = deepcopy(target)
    adjacent["row_id"] = "entry-6"
    adjacent["entry_number"] = "6"
    adjacent["text"] = "6 Feb 2, 2026 Main Document Dismiss Download PDF"
    cast(list[dict[str, Any]], adjacent["documents"])[0]["description"] = "Dismiss"
    entries.insert(2, adjacent)

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        allow_inferred_target_mtd=True,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert "no_free_target_mtd_document" in candidate.paid_gap_reasons


def test_planner_rejects_candidate_with_two_selected_target_motions(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    cast(dict[str, object], record["ai"])["target_motion_entry_numbers"] = [5, 6]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.final_exclusions
    assert candidate.exclusion_reasons == ("selected_target_motion_count_not_one",)


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
    target_document["description"] = (
        f"Memorandum in Support of Motion to Dismiss concerning {merits_phrase}"
    )

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


def test_embedded_restriction_markers_survive_snapshot_round_trip(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    selected_entries = cast(list[dict[str, Any]], record["selected_entries"])
    target_document = cast(list[dict[str, Any]], selected_entries[1]["documents"])[0]
    target_document["restriction_markers"] = ["field_issealed"]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [excluded] = plan.final_exclusions
    assert not plan.download_requests
    assert excluded.exclusion_reasons[0].startswith(
        "sealed_or_restricted_material:target_mtd_entry_5:field_issealed"
    )


def test_embedded_restriction_markers_fail_closed_when_malformed(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    selected_entries = cast(list[dict[str, Any]], record["selected_entries"])
    target_document = cast(list[dict[str, Any]], selected_entries[1]["documents"])[0]
    target_document["restriction_markers"] = "field_issealed"

    with pytest.raises(ValueError, match="restriction_markers must be a list"):
        plan_public_packet_downloads(
            (record,),
            raw_html_dir=tmp_path / "unused",
            target_clean_cases=1,
            use_embedded_entries=True,
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
    html = _docket_html().replace(
        "<p>Memorandum in Support of Motion to Dismiss</p>",
        "<p>Memorandum in Support of Motion to Dismiss - Under Seal</p>",
    )
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
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM


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
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.DECISION,
    ]
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/5/example/"
    )


def test_public_packet_planner_accepts_verified_raw_html_paths_from_multiple_roots(
    tmp_path: Path,
) -> None:
    first = deepcopy(_screened_case())
    second = deepcopy(_screened_case())
    cast(dict[str, Any], first["candidate"])["docket_id"] = "123"
    cast(dict[str, Any], second["candidate"])["docket_id"] = "456"
    first_path = tmp_path / "first" / "123.html"
    second_path = tmp_path / "second" / "456.html"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    first_path.write_text(_docket_html(), encoding="utf-8")
    second_path.write_text(_docket_html(), encoding="utf-8")

    plan = plan_public_packet_downloads(
        (first, second),
        raw_html_paths_by_candidate={"123": first_path, "456": second_path},
        target_clean_cases=2,
    )

    assert plan.selected_case_count == 2
    assert {candidate.candidate_id for candidate in plan.selected_cases} == {
        "123",
        "456",
    }


def test_public_packet_planner_rejects_directory_and_path_map_together(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="raw_html_dir and raw_html_paths_by_candidate are mutually exclusive",
    ):
        plan_public_packet_downloads(
            (_screened_case(),),
            raw_html_dir=tmp_path,
            raw_html_paths_by_candidate={"123": tmp_path / "123.html"},
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


@pytest.mark.parametrize("document_description", ("Memorandum", ""))
def test_public_packet_planner_links_free_support_memo_explicitly_referencing_target(
    tmp_path: Path,
    document_description: str,
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
                    "description": document_description,
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
                    "description": "Memorandum in Support of Motion to Dismiss",
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
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/6/example/"
    )


def test_public_packet_planner_does_not_link_adjacent_unreferenced_support_brief(
    tmp_path: Path,
) -> None:
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
            "text": "6 Feb 2, 2026 Brief in Support filed by Defendant.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Brief in Support",
                    "href": "https://www.courtlistener.com/docket/123/6/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                },
            ],
        },
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [gap] = plan.paid_gap_cases
    assert gap.paid_gap_reasons == (
        "no_free_target_mtd_document",
        "no_free_mtd_memorandum",
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

    [candidate] = plan.final_exclusions
    assert candidate.exclusion_reasons == ("selected_target_motion_count_not_one",)


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

    [candidate] = plan.final_exclusions
    assert candidate.exclusion_reasons == ("selected_target_motion_count_not_one",)


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


def test_public_packet_planner_requires_substantive_target_opposition(
    tmp_path: Path,
) -> None:
    record = _screened_case_with_embedded_entries()
    candidate = cast(dict[str, Any], record["candidate"])
    candidate["docket_id"] = "71280017"
    candidate["candidate_key"] = "71280017"
    candidate["url"] = "https://www.courtlistener.com/docket/71280017/example/"
    entries = cast(list[dict[str, Any]], record["selected_entries"])
    cast(dict[str, object], record["ai"])["target_motion_entry_numbers"] = [9]
    cast(dict[str, object], record["ai"])["decision_entry_numbers"] = [33]
    target = entries[1]
    target["entry_number"] = "9"
    target["row_id"] = "entry-9"
    decision = entries[-1]
    decision["entry_number"] = "33"
    decision["row_id"] = "entry-33"
    entries[1:1] = [
        _embedded_entry(
            16,
            "MOTION for Extension of Time to File Response re: 9 MOTION TO "
            "DISMISS FOR FAILURE TO STATE A CLAIM.",
        ),
        _embedded_entry(
            19,
            "RESPONSE in Opposition re 9 MOTION TO DISMISS FOR FAILURE TO "
            "STATE A CLAIM.",
        ),
        _embedded_entry(
            23,
            "MOTION for Extension of Time to File Response re: 9 MOTION TO "
            "DISMISS FOR FAILURE TO STATE A CLAIM.",
        ),
        _embedded_entry(
            26,
            "Second MOTION for Extension of Time to File Response re: 9 "
            "MOTION TO DISMISS FOR FAILURE TO STATE A CLAIM.",
        ),
    ]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert candidate.paid_gap_reasons == ("no_free_opposition",)
    assert candidate.required_document_count == 4
    assert candidate.missing_required_document_count == 1
    opposition_documents = [
        document
        for document in candidate.documents
        if document.document_role is DocumentRole.OPPOSITION
    ]
    assert opposition_documents == []


@pytest.mark.parametrize(
    "opposition_text",
    (
        "Opposition to Motion for Judgment on the Pleadings under Rule 12(c).",
        "Response to Defendant's Rule 12(b)(6) Motion.",
        "Response in Opposition to Motion to Dismiss, filed after the deadline.",
    ),
)
def test_public_packet_planner_preserves_rule_12_opposition_forms(
    tmp_path: Path,
    opposition_text: str,
) -> None:
    record = _screened_case_with_embedded_entries()
    entries = cast(list[dict[str, Any]], record["selected_entries"])
    entries.insert(2, _embedded_entry(8, opposition_text))

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.paid_gap_cases
    assert candidate.paid_gap_reasons == ("no_free_opposition",)
    assert candidate.required_document_count == 4


def _embedded_entry(entry_number: int, text: str) -> dict[str, object]:
    return {
        "row_id": f"entry-{entry_number}",
        "entry_number": str(entry_number),
        "filed_at": "Mar 1, 2026",
        "text": text,
        "documents": [
            {
                "kind": "Main Document",
                "description": text,
                "href": f"https://ecf.example.invalid/{entry_number}",
                "action_label": "Buy on PACER",
                "pacer_only": True,
            }
        ],
    }


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


def test_public_packet_planner_exact_mix_selection_avoids_greedy_false_shortfall(
    tmp_path: Path,
) -> None:
    records = (
        _case_mix_cost_record("100", court="Court A", nos="NOS X", missing=0),
        _case_mix_cost_record("200", court="Court A", nos="NOS Y", missing=1),
        _case_mix_cost_record("300", court="Court B", nos="NOS X", missing=1),
    )

    plan = plan_public_packet_downloads(
        records,
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=2,
        max_case_mix_share=0.5,
        use_embedded_entries=True,
    )

    # Cheapest-first greedy takes 100 and then blocks both remaining candidates:
    # 200 shares its court, while 300 shares its NOS bucket. The feasible exact
    # selection is 200 + 300, with one candidate in every capped bucket.
    assert [candidate.candidate_id for candidate in plan.planned_cases] == [
        "200",
        "300",
    ]
    assert plan.summary_record()["acquisition_candidate_shortfall"] == 0
    assert plan.summary_record()["projected_paid_cost_usd"] == "6.10"


def test_public_packet_planner_exact_mix_selection_minimizes_total_cost(
    tmp_path: Path,
) -> None:
    records = (
        _case_mix_cost_record("100", court="Court A", nos="NOS X", missing=0),
        _case_mix_cost_record("200", court="Court A", nos="NOS Y", missing=1),
        _case_mix_cost_record("300", court="Court B", nos="NOS X", missing=1),
        _case_mix_cost_record("400", court="Court B", nos="NOS Y", missing=3),
    )

    plan = plan_public_packet_downloads(
        records,
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=2,
        max_case_mix_share=0.5,
        use_embedded_entries=True,
    )

    # Greedy reaches the target with 100 + 400 for $9.15. The exact optimum is
    # 200 + 300 for $6.10, so feasibility alone is not a sufficient guarantee.
    assert [candidate.candidate_id for candidate in plan.planned_cases] == [
        "200",
        "300",
    ]
    assert plan.summary_record()["projected_paid_cost_usd"] == "6.10"


def test_public_packet_planner_exact_mix_selection_is_permutation_invariant(
    tmp_path: Path,
) -> None:
    records = (
        _case_mix_cost_record("100", court="Court A", nos="NOS X", missing=0),
        _case_mix_cost_record("200", court="Court A", nos="NOS Y", missing=1),
        _case_mix_cost_record("300", court="Court B", nos="NOS X", missing=1),
        _case_mix_cost_record("400", court="Court B", nos="NOS Y", missing=3),
    )
    observed: set[
        tuple[
            tuple[str, ...],
            str,
            str,
            int,
            str,
            tuple[str, ...],
            int,
            int,
            int,
            str,
            str,
            int,
        ]
    ] = set()

    for ordered_records in permutations(records):
        plan = plan_public_packet_downloads(
            ordered_records,
            raw_html_dir=tmp_path / "unused",
            target_clean_cases=2,
            max_case_mix_share=0.5,
            use_embedded_entries=True,
        )
        summary = plan.summary_record()
        optimizer = cast(dict[str, Any], summary["selection_optimizer"])
        assert isinstance(optimizer["ortools_version"], str)
        assert optimizer["ortools_version"]
        assert optimizer["null_bucket_policy"] == "uncapped"
        assert optimizer["null_bucket_counts"] == {
            "court": 0,
            "mdl_family_id": 4,
            "nos_macro_category": 0,
            "related_family_id": 4,
        }
        assert isinstance(optimizer["phases"], list)
        assert [phase["phase"] for phase in optimizer["phases"]] == [
            "cardinality",
            "cost",
            "missing_documents",
            "lexicographic",
        ]
        assert {phase["status"] for phase in optimizer["phases"]} == {"OPTIMAL"}
        observed.add(
            (
                tuple(candidate.candidate_id for candidate in plan.planned_cases),
                cast(str, summary["selection_protocol"]),
                cast(str, summary["optimizer_status"]),
                cast(int, summary["case_mix_max_per_bucket"]),
                cast(str, summary["max_case_mix_share"]),
                tuple(cast(list[str], optimizer["selected_candidate_ids"])),
                cast(int, optimizer["selected_count"]),
                cast(int, optimizer["total_cost_cents"]),
                cast(int, optimizer["total_missing_document_count"]),
                cast(str, optimizer["model_schema_version"]),
                cast(str, optimizer["model_sha256"]),
                cast(int, optimizer["num_search_workers"]),
            )
        )

    [signature] = observed
    assert signature[:9] == (
        ("200", "300"),
        "exact_case_mix_cp_sat_v1",
        "OPTIMAL",
        1,
        "0.5",
        ("200", "300"),
        2,
        610,
        2,
    )
    assert signature[9] == "legalforecast-case-mix-cp-sat-v1"
    assert len(signature[10]) == 64
    assert signature[11] == 1


def test_public_packet_planner_rejects_share_below_one_candidate_per_bucket(
    tmp_path: Path,
) -> None:
    records = (
        _case_mix_cost_record("100", court="Court A", nos="NOS X", missing=0),
        _case_mix_cost_record("200", court="Court B", nos="NOS Y", missing=0),
        _case_mix_cost_record("300", court="Court C", nos="NOS Z", missing=0),
    )

    with pytest.raises(
        ValueError,
        match=r"max_case_mix_share.*1 / target_clean_cases",
    ):
        plan_public_packet_downloads(
            records,
            raw_html_dir=tmp_path / "unused",
            target_clean_cases=3,
            max_case_mix_share=0.3,
            use_embedded_entries=True,
        )


def test_public_packet_planner_uses_context_independent_exact_share_floor(
    tmp_path: Path,
) -> None:
    share_just_below_one_third = Decimal(
        "0.333333333333333333333333333333333333333333333333333333333333"
    )

    with pytest.raises(
        ValueError,
        match=r"max_case_mix_share.*1 / target_clean_cases",
    ):
        plan_public_packet_downloads(
            (),
            raw_html_dir=tmp_path / "unused",
            target_clean_cases=3,
            max_case_mix_share=share_just_below_one_third,
            use_embedded_entries=True,
        )


def test_public_packet_planner_sorts_intrinsic_exclusions_canonically(
    tmp_path: Path,
) -> None:
    records = []
    for candidate_id in ("z-case", "a-case"):
        record = deepcopy(_screened_case_with_embedded_entries())
        candidate = cast(dict[str, Any], record["candidate"])
        metadata = cast(dict[str, Any], candidate["metadata"])
        candidate["docket_id"] = candidate_id
        candidate["candidate_key"] = candidate_id
        metadata["case_id"] = candidate_id
        metadata["is_private"] = True
        records.append(record)

    observed = set()
    for ordered_records in permutations(records):
        plan = plan_public_packet_downloads(
            ordered_records,
            raw_html_dir=tmp_path / "unused",
            target_clean_cases=1,
            use_embedded_entries=True,
        )
        observed.add(tuple(item.candidate_id for item in plan.final_exclusions))

    assert observed == {("a-case", "z-case")}


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


@pytest.mark.parametrize(
    ("entry_text", "description", "expected_role"),
    (
        (
            "1 TRANSFERREDCOMPLAINT against All Defendants filed by Plaintiff.",
            "",
            DocumentRole.COMPLAINT,
        ),
        (
            "1 PRO SE COMPLAINT against Defendant filed by Plaintiff.",
            "Complaint - Pro Se",
            DocumentRole.COMPLAINT,
        ),
        (
            "1 Petition (Removal/Transfer) Received From: County Court, "
            "filed by Plaintiff.",
            "Complaint (Removal/Transfer) - COURT USE ONLY",
            DocumentRole.COMPLAINT,
        ),
        (
            "1 Civil Case - Complaint, Amended filed by Plaintiff.",
            "Civil Case - Complaint, Amended",
            DocumentRole.AMENDED_COMPLAINT,
        ),
    ),
)
def test_public_packet_planner_accepts_strict_operative_pleading_variants(
    tmp_path: Path,
    entry_text: str,
    description: str,
    expected_role: DocumentRole,
) -> None:
    record = _screened_case_with_embedded_entries()
    complaint = cast(list[dict[str, Any]], record["selected_entries"])[0]
    complaint["text"] = entry_text
    cast(list[dict[str, Any]], complaint["documents"])[0]["description"] = description

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=tmp_path / "unused",
        target_clean_cases=1,
        use_embedded_entries=True,
    )

    [candidate] = plan.selected_cases
    assert candidate.documents[0].document_role is expected_role


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
                    "description": "Memorandum in Support of Motion to Dismiss",
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


def _reply_entry() -> dict[str, object]:
    return {
        "row_id": "entry-10",
        "entry_number": "10",
        "filed_at": "Mar 1, 2026",
        "text": "REPLY in support of Motion to Dismiss at ECF No. 5.",
        "is_sealed": None,
        "is_private": None,
        "documents": [
            {
                "kind": "Main Document",
                "description": "Reply in Support of Motion to Dismiss",
                "href": _REPLY_URL,
                "action_label": "Download PDF",
                "pacer_only": False,
                "freely_available": True,
                "is_sealed": None,
                "is_private": None,
            }
        ],
    }


def _case_mix_cost_record(
    candidate_id: str,
    *,
    court: str,
    nos: str,
    missing: int,
) -> dict[str, object]:
    """Build a viable embedded candidate with an exact missing-document cost."""

    record = deepcopy(_screened_case_with_embedded_entries())
    candidate = cast(dict[str, Any], record["candidate"])
    metadata = cast(dict[str, Any], candidate["metadata"])
    candidate["docket_id"] = candidate_id
    candidate["candidate_key"] = candidate_id
    candidate["url"] = f"https://www.courtlistener.com/docket/{candidate_id}/example/"
    metadata["case_id"] = candidate_id
    metadata["court"] = court
    metadata["nos_macro_category"] = nos

    entries = cast(list[dict[str, Any]], record["selected_entries"])
    if not 0 <= missing <= len(entries):
        raise ValueError("missing must be between zero and the required entry count")
    for entry in entries[:missing]:
        [document] = cast(list[dict[str, Any]], entry["documents"])
        entry_number = cast(str, entry["entry_number"])
        document.update(
            href=f"https://ecf.example.invalid/{candidate_id}/{entry_number}",
            action_label="Buy on PACER",
            pacer_only=True,
            freely_available=False,
        )
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
                <div class="col-xs-6">
                  <p>Memorandum in Support of Motion to Dismiss</p>
                </div>
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
                <div class="col-xs-6"><p>Memorandum in Support</p></div>
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
