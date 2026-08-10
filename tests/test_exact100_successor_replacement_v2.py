# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false
from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_replacement_v2 import (
    CONFIG_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    Exact100SuccessorReplacementV2Error,
    _mint_verified_exact100_v2_base,
    project_exact100_successor_replacement_v2,
    require_verified_exact100_v2_base,
)
from legalforecast.ingestion.exact100_successor_semantic_repair import (
    _mint_verified_exact100_successor_semantic_repairs,
)
from legalforecast.ingestion.exact100_successor_wider_rank import (
    _mint_verified_exact100_successor_wider_rank,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    TerminalExclusionReason,
    _mint_terminal_evidence,
    verify_post_selection_terminal_exclusions,
)
from reportlab.pdfgen.canvas import Canvas


def test_v2_replaces_only_sealed_terminal_with_first_wider_candidate() -> None:
    inputs = _fixture()

    result = project_exact100_successor_replacement_v2(
        base=inputs["base"],
        terminal_exclusions=inputs["terminals"],
        semantic_repairs=inputs["repairs"],
        wider_rank=inputs["wider"],
    )
    assert len(result.selection) == 100
    assert result.selection[-1]["candidate_id"] == "x001"
    assert {row["candidate_id"] for row in result.selection} == {
        *(f"s{index:03d}" for index in range(1, 100)),
        "x001",
    }
    promoted = result.selection[-1]
    assert promoted["missing_required_document_count"] == 0
    assert promoted["projected_paid_cost_usd"] == "0.00"
    assert {row["document_role"] for row in promoted["documents"]} >= {
        "amended_complaint",
        "motion_to_dismiss_memorandum",
        "opposition",
        "decision",
    }
    assert result.config["schema_version"] == CONFIG_SCHEMA_VERSION
    assert result.state["schema_version"] == STATE_SCHEMA_VERSION
    assert result.state["terminal_candidate_ids"] == ["s000"]
    assert result.state["promoted_candidate_ids"] == ["x001"]
    assert result.promotions[0]["disposition_class"] == ("moot_non_merits_disposition")
    assert all(
        result.state[field] is False
        for field in (
            "provider_activity_requested",
            "provider_activity_executed",
            "courtlistener_activity_requested",
            "courtlistener_activity_executed",
            "pacer_activity_requested",
            "pacer_activity_executed",
            "recap_fetch_activity_requested",
            "recap_fetch_activity_executed",
            "paid_activity_requested",
            "paid_activity_executed",
            "model_activity_requested",
            "model_activity_executed",
            "evaluation_authorized",
            "freeze_authorized",
            "dispatch_authorized",
        )
    )


def test_v2_does_not_require_opposition_when_none_was_docketed() -> None:
    inputs = _fixture(include_opposition=False)

    result = project_exact100_successor_replacement_v2(
        base=inputs["base"],
        terminal_exclusions=inputs["terminals"],
        semantic_repairs=inputs["repairs"],
        wider_rank=inputs["wider"],
    )

    promoted = result.selection[-1]
    assert promoted["required_document_count"] == 3
    assert {row["document_role"] for row in promoted["documents"]} >= {
        "amended_complaint",
        "motion_to_dismiss_memorandum",
        "decision",
    }
    assert all(row["document_role"] != "opposition" for row in promoted["documents"])


def test_v2_rejects_semantic_repairs_for_different_source_bytes() -> None:
    inputs = _fixture()
    alternate_complaint = _pdf(
        (
            "Notice of Removal",
            "A true and correct copy of the first amended complaint is attached "
            "hereto as Exhibit B.",
            "Exhibit B",
            "Verified First Amended Complaint with changed bytes",
        )
    )
    alternate_motion = _pdf(
        (
            "Notice of Motion and Motion to Dismiss - Memorandum of Points and "
            "Authorities",
            "Memorandum of Points and Authorities Introduction",
            "Argument I. A different source requires dismissal",
        )
    )
    documents = (
        _promoted_document("x001-bundle", "complaint", alternate_complaint, 1),
        _promoted_document(
            "x001-opening",
            "motion_to_dismiss_notice",
            alternate_motion,
            20,
        ),
    )
    foreign_repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=documents,
        document_bytes_by_key={
            ("x001", "x001-bundle"): alternate_complaint,
            ("x001", "x001-opening"): alternate_motion,
        },
    )

    with pytest.raises(Exact100SuccessorReplacementV2Error, match="does not bind"):
        project_exact100_successor_replacement_v2(
            base=inputs["base"],
            terminal_exclusions=inputs["terminals"],
            semantic_repairs=foreign_repairs,
            wider_rank=inputs["wider"],
        )


def test_v2_rejects_missing_required_semantic_repairs() -> None:
    inputs = _fixture()
    empty_repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=(),
        document_bytes_by_key={},
    )

    with pytest.raises(
        Exact100SuccessorReplacementV2Error,
        match="does not contain every required semantic role",
    ):
        project_exact100_successor_replacement_v2(
            base=inputs["base"],
            terminal_exclusions=inputs["terminals"],
            semantic_repairs=empty_repairs,
            wider_rank=inputs["wider"],
        )


def test_v2_base_and_projection_fail_closed_on_evidence_drift() -> None:
    inputs = _fixture()
    base = inputs["base"]
    require_verified_exact100_v2_base(base)
    base.download_manifest[0]["sha256"] = "f" * 64
    with pytest.raises(Exact100SuccessorReplacementV2Error, match="not cleared"):
        require_verified_exact100_v2_base(base)

    inputs = _fixture()
    terminals = inputs["terminals"]
    object.__setattr__(terminals, "selection_sha256", "sha256:" + "0" * 64)
    with pytest.raises(Exact100SuccessorReplacementV2Error, match="different"):
        project_exact100_successor_replacement_v2(
            base=inputs["base"],
            terminal_exclusions=terminals,
            semantic_repairs=inputs["repairs"],
            wider_rank=inputs["wider"],
        )


def test_v2_base_rejects_retained_surface_mutation_after_mint() -> None:
    base = _fixture()["base"]
    base.case_relevance[1]["case_name"] = "mutated after verification"

    with pytest.raises(
        Exact100SuccessorReplacementV2Error,
        match="changed after authenticated replay",
    ):
        require_verified_exact100_v2_base(base)


def test_v2_base_accepts_only_evidence_complete_public_unknown_restrictions() -> None:
    inputs = _fixture()
    base = inputs["base"]
    evidence = [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    ]
    rows = [dict(row) for row in base.restriction_evidence]
    rows[0] = {
        **rows[0],
        "restriction_status": "unknown",
        "restriction_evidence": evidence,
    }
    _mint_verified_exact100_v2_base(
        predecessor_projection_bytes=base.predecessor_projection_bytes,
        selection_rows=base.selection,
        case_relevance_rows=base.case_relevance,
        download_manifest_rows=base.download_manifest,
        disclosure_rows=base.disclosure_clearance,
        restriction_rows=rows,
        core_filter_rows=base.core_filter_results,
        source_commitments=base.source_commitments,
    )

    rows[0]["restriction_evidence"] = evidence[:-1]
    with pytest.raises(Exact100SuccessorReplacementV2Error, match="not cleared"):
        _mint_verified_exact100_v2_base(
            predecessor_projection_bytes=base.predecessor_projection_bytes,
            selection_rows=base.selection,
            case_relevance_rows=base.case_relevance,
            download_manifest_rows=base.download_manifest,
            disclosure_rows=base.disclosure_clearance,
            restriction_rows=rows,
            core_filter_rows=base.core_filter_results,
            source_commitments=base.source_commitments,
        )


def test_semantic_repair_finds_embedded_complaint_within_bounded_horizon() -> None:
    page_texts = [""] * 96
    page_texts[0] = "Notice of Removal"
    page_texts[1] = (
        "A true and correct copy of the first amended complaint is attached "
        "hereto as Exhibit B."
    )
    page_texts[44] = "Exhibit B"
    page_texts[45] = "Verified First Amended Complaint"
    payload = _pdf(tuple(page_texts))
    document = _promoted_document("x001-bundle", "complaint", payload, 1)

    repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=(document,),
        document_bytes_by_key={("x001", "x001-bundle"): payload},
    )

    assert [row["derived_document_role"] for row in repairs.records] == [
        "amended_complaint"
    ]
    assert repairs.records[0]["evidence_cues"][-1]["page_number"] == 46


def test_semantic_repair_does_not_qualify_complaint_beyond_bounded_horizon() -> None:
    page_texts = [""] * 97
    page_texts[0] = "Notice of Removal"
    page_texts[1] = (
        "A true and correct copy of the first amended complaint is attached "
        "hereto as Exhibit B."
    )
    page_texts[94] = "Exhibit B"
    page_texts[96] = "Verified First Amended Complaint"
    payload = _pdf(tuple(page_texts))
    document = _promoted_document("x001-bundle", "complaint", payload, 1)

    repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=(document,),
        document_bytes_by_key={("x001", "x001-bundle"): payload},
    )

    assert repairs.records == ()


def test_semantic_repair_keeps_combined_mtd_scan_unbounded() -> None:
    page_texts = [""] * 100
    page_texts[0] = (
        "Notice of Motion and Motion to Dismiss - Memorandum of Points and Authorities"
    )
    page_texts[96] = "Memorandum of Points and Authorities Introduction"
    page_texts[99] = "Argument I. Dismissal is required"
    payload = _pdf(tuple(page_texts))
    document = _promoted_document(
        "x001-opening", "motion_to_dismiss_notice", payload, 20
    )

    repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=(document,),
        document_bytes_by_key={("x001", "x001-opening"): payload},
    )

    assert [row["derived_document_role"] for row in repairs.records] == [
        "motion_to_dismiss_memorandum"
    ]
    assert repairs.records[0]["evidence_cues"][-1]["page_number"] == 100


def _fixture(*, include_opposition: bool = True) -> dict[str, Any]:
    selected_ids = [f"s{index:03d}" for index in range(100)]
    selection = [_selection_row(candidate_id) for candidate_id in selected_ids]
    relevance = [_selection_row(candidate_id) for candidate_id in selected_ids]
    manifest = [_base_document(candidate_id) for candidate_id in selected_ids]
    clearance = [_clearance(row) for row in manifest]
    restriction = [_restriction(row) for row in manifest]
    core = [{"candidate_id": candidate_id} for candidate_id in selected_ids]
    base = _mint_verified_exact100_v2_base(
        predecessor_projection_bytes=b"authenticated projection\n",
        selection_rows=selection,
        case_relevance_rows=relevance,
        download_manifest_rows=manifest,
        disclosure_rows=clearance,
        restriction_rows=restriction,
        core_filter_rows=core,
        source_commitments={"root30": "a" * 64, "root32": "b" * 64},
    )
    terminal_evidence = _mint_terminal_evidence(
        candidate_id="s000",
        source_document_id="s000-decision",
        reason=TerminalExclusionReason.STIPULATED_INELIGIBLE,
        evidence_kind="target_document_eligibility_audit",
        evidence_commitments={"selection": _sha(base.selection_bytes)},
    )
    terminals = verify_post_selection_terminal_exclusions(
        selection_bytes=base.selection_bytes, evidence=(terminal_evidence,)
    )

    complaint = _pdf(
        (
            "Notice of Removal",
            "A true and correct copy of the first amended complaint is attached "
            "hereto as Exhibit B.",
            "Exhibit B",
            "Verified First Amended Complaint",
        )
    )
    motion = _pdf(
        (
            "Notice of Motion and Motion to Dismiss - Memorandum of Points and "
            "Authorities",
            "Memorandum of Points and Authorities Introduction",
            "Argument I. Dismissal is required",
        )
    )
    promoted_docs = [
        _promoted_document("x001-bundle", "complaint", complaint, 1),
        _promoted_document("x001-opening", "motion_to_dismiss_notice", motion, 20),
        *(
            [_promoted_document("x001-opposition", "opposition", b"opp", 25)]
            if include_opposition
            else []
        ),
        _promoted_document("x001-decision", "decision", b"decision", 39),
    ]
    repair_docs = promoted_docs[:2]
    repairs = _mint_verified_exact100_successor_semantic_repairs(
        document_records=repair_docs,
        document_bytes_by_key={
            ("x001", "x001-bundle"): complaint,
            ("x001", "x001-opening"): motion,
        },
    )
    final_rows: list[dict[str, Any]] = [
        {"candidate_id": f"courtlistener-docket-{candidate_id}", "accepted": True}
        for candidate_id in (*selected_ids, *(f"x{index:03d}" for index in range(53)))
    ]
    identity: list[dict[str, str]] = [
        {
            "snapshot_candidate_id": row["candidate_id"],
            "canonical_candidate_id": row["candidate_id"].removeprefix(
                "courtlistener-docket-"
            ),
            "snapshot_row_sha256": _record_sha(row),
        }
        for row in final_rows
    ]
    excluded_ids = [f"x{index:03d}" for index in range(53)]
    materialized = [
        {
            "candidate_id": candidate_id,
            "case_id": candidate_id,
            "case_name": f"Case {candidate_id}",
            "court": "test",
            "decision_date": "2026-07-07",
            "decision_entry_numbers": [39],
            "docket_number": "1:26-cv-00001",
            "documents": [],
            "exclusion_reasons": [],
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "0.00",
            "target_motion_entry_numbers": [20],
        }
        for candidate_id in excluded_ids
    ]
    evidence_candidates = ("x001", "x010")
    all_downloads = [
        *promoted_docs,
        *(
            _promoted_document(
                f"x010-{role}", role, role.encode(), index + 1, candidate_id="x010"
            )
            for index, role in enumerate(
                ("complaint", "motion_to_dismiss_memorandum", "opposition", "decision")
            )
        ),
    ]
    all_clearance = [_clearance(row) for row in all_downloads]
    all_restriction = [_restriction(row) for row in all_downloads]
    wider = _mint_verified_exact100_successor_wider_rank(
        final153_rows=final_rows,
        exact100_rows=selection,
        exclusion_rows=[
            {
                "candidate_id": candidate_id,
                "reason": "operative_complaint_not_found",
            }
            for candidate_id in excluded_ids
        ],
        materialized_selection_rows=materialized,
        case_relevance_rows=[
            {"candidate_id": candidate_id} for candidate_id in evidence_candidates
        ],
        download_manifest_rows=all_downloads,
        disclosure_rows=all_clearance,
        restriction_rows=all_restriction,
        core_filter_rows=[
            {"candidate_id": candidate_id} for candidate_id in evidence_candidates
        ],
        identity_mapping_rows=identity,
        semantic_repair_rows=repairs.records,
        source_commitments={"final153": "c" * 64, "documents": "d" * 64},
    )
    return {"base": base, "terminals": terminals, "repairs": repairs, "wider": wider}


def _selection_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "case_name": f"Case {candidate_id}",
        "documents": [
            {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-decision",
                "document_role": "decision",
                "contains_target_outcome": True,
                "model_visible": False,
                "setup_runner_label": "other_substantive",
            }
        ],
    }


def _base_document(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-decision",
        "document_role": "decision",
        "sha256": "e" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }


def _promoted_document(
    source_document_id: str,
    role: str,
    payload: bytes,
    entry: int,
    *,
    candidate_id: str = "x001",
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "document_role": role,
        "docket_entry_number": entry,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "free_or_purchased": "free",
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
    }


def _clearance(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": document["candidate_id"],
        "source_document_id": document["source_document_id"],
        "status": "cleared",
        "restriction_status": "public",
        "sha256": document["sha256"],
        "byte_count": document["byte_count"],
        "free_or_purchased": "free",
    }


def _restriction(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": document["candidate_id"],
        "source_document_id": document["source_document_id"],
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "is_private": None,
        "is_sealed": None,
    }


def _record_sha(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(row, error_type=ValueError, error_message="invalid")
    ).hexdigest()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _pdf(page_texts: tuple[str, ...]) -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    for text in page_texts:
        canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()
