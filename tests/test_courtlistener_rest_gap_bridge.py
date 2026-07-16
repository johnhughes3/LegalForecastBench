from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import (
    _PACER_GAP_BRIDGE_SEMANTIC_REVISION,
    _bridge_checkpoint_requires_semantic_replay,
    main,
)
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.courtlistener_case_dev_bridge import (
    CourtListenerCaseDevBridgeError,
    bridge_public_plan_paid_gap_candidate_via_courtlistener,
    bridge_public_plan_paid_gaps_via_courtlistener,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerDocketEntry,
    CourtListenerFixtureTransport,
    CourtListenerResponseError,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads
from legalforecast.ingestion.recap_api_discovery import reconstruct_docket_page


def test_courtlistener_rest_bridge_emits_real_public_recap_id_for_plan() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    client = _client(*_clean_responses())

    selection, relevance = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=client,
        use_embedded_entries=True,
    )

    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert len(paid) == 1
    assert paid[0]["source_provider"] == "courtlistener+recap-fetch"
    assert paid[0]["source_document_id"] == "9005"
    assert paid[0]["courtlistener_docket_entry_id"] == "7005"
    assert paid[0]["is_sealed"] is False
    assert paid[0]["is_private"] is None
    assert paid[0]["redaction_or_seal_status"] == "public"
    assert paid[0]["restriction_evidence"] == [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_sealed_false",
    ]
    assert selection["identity_resolution"] == {
        "courtlistener_candidate_id": "123",
        "courtlistener_docket_id": "123",
        "matched_by": "direct_rest_exact_docket_court_caption_entries",
    }
    [paid_relevance] = [
        document
        for document in relevance["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert paid_relevance["is_private"] is None
    assert paid_relevance["restriction_evidence"] == paid[0]["restriction_evidence"]
    [result] = filter_core_documents((relevance,))
    assert result.purchase_document_ids == ("9005",)
    assert client.request_count == 3


def test_bridge_recovers_operative_complaint_from_complete_paginated_rest() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={
                "results": [_rest_entry(5, 7005, 9005, "MOTION to Dismiss")],
                "next": (
                    "https://www.courtlistener.com/api/rest/v4/"
                    "docket-entries/?cursor=older"
                ),
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "cursor": "older", "page_size": 100},
            payload={
                "results": [_rest_entry(1, 7001, 9001, "COMPLAINT filed")],
                "next": None,
            },
        ),
        _recap_document_response(1, 7001, 9001, "Complaint"),
        _recap_document_response(5, 7005, 9005, "Motion to Dismiss"),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    recovered = [
        (document["docket_entry_number"], document["document_role"])
        for document in selection["documents"]
        if document.get("resolved_from_paid_gap") is True
    ]
    assert recovered == [
        (1, "complaint"),
        (5, "motion_to_dismiss_memorandum"),
    ]


def test_bridge_uses_latest_unique_pre_mtd_rest_complaint() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    selected_entries.insert(
        0,
        _entry(
            1,
            "Initial filing",
            "Complaint",
            "https://ecf.nysd.uscourts.gov/doc1/complaint",
            pacer_only=True,
        ),
    )
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={
                "results": [
                    _rest_entry(1, 7001, 9001, "COMPLAINT filed"),
                    _rest_entry(3, 7003, 9003, "AMENDED COMPLAINT filed"),
                    _rest_entry(5, 7005, 9005, "MOTION to Dismiss"),
                ],
                "next": None,
            },
        ),
        _recap_document_response(3, 7003, 9003, "Amended Complaint"),
        _recap_document_response(5, 7005, 9005, "Motion to Dismiss"),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    complaint_documents = [
        document
        for document in selection["documents"]
        if document["document_role"] in {"complaint", "amended_complaint"}
    ]
    assert [
        (document["docket_entry_number"], document["document_role"])
        for document in complaint_documents
    ] == [(3, "amended_complaint")]


def test_bridge_falls_back_to_exhaustive_public_entry_for_missing_rest_role() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    selected_entries.insert(
        0,
        _entry(
            1,
            "Initial filing",
            "Complaint",
            "https://ecf.nysd.uscourts.gov/doc1/complaint",
            pacer_only=True,
        ),
    )
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={
                "results": [
                    _rest_entry(1, 7001, 9001, "Initial filing"),
                    _rest_entry(5, 7005, 9005, "MOTION to Dismiss"),
                ],
                "next": None,
            },
        ),
        _recap_document_response(1, 7001, 9001, "Complaint"),
        _recap_document_response(5, 7005, 9005, "Motion to Dismiss"),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    assert any(
        document["docket_entry_number"] == 1
        and document["document_role"] == "complaint"
        for document in selection["documents"]
    )


def test_bridge_rejects_contradictory_rest_entry_numbers_across_pages() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={
                "results": [_rest_entry(1, 7001, 9001, "COMPLAINT filed")],
                "next": (
                    "https://www.courtlistener.com/api/rest/v4/"
                    "docket-entries/?cursor=duplicate"
                ),
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "cursor": "duplicate", "page_size": 100},
            payload={
                "results": [_rest_entry(1, 7002, 9002, "COMPLAINT filed")],
                "next": None,
            },
        ),
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_rest_entry_number_conflict: 1",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_rejects_nonadvancing_rest_pagination_cursor() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    next_url = "https://www.courtlistener.com/api/rest/v4/docket-entries/?cursor=loop"
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={"results": [], "next": next_url},
        ),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "cursor": "loop", "page_size": 100},
            payload={"results": [], "next": next_url},
        ),
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_rest_pagination_cursor_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_rejects_contradictory_rest_entry_number_aliases() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    complaint = _rest_entry(1, 7001, 9001, "COMPLAINT filed")
    complaint["entryNumber"] = 2
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={"results": [complaint], "next": None},
        ),
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_rest_entry_number_alias_conflict: 7001",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_accepts_independent_rest_recap_sequence_number() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    complaint = _rest_entry(1, 7001, 9001, "COMPLAINT filed")
    complaint["recap_sequence_number"] = "2026-01-01.001"
    motion = _rest_entry(5, 7005, 9005, "MOTION to Dismiss")
    motion["recap_sequence_number"] = "2026-01-01.002"
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={"results": [complaint, motion], "next": None},
        ),
        _recap_document_response(1, 7001, 9001, "Complaint"),
        _recap_document_response(5, 7005, 9005, "Motion to Dismiss"),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    recovered = [
        document
        for document in selection["documents"]
        if document.get("document_role") == "complaint"
    ]
    assert len(recovered) == 1
    assert recovered[0]["docket_entry_number"] == 1


def test_rest_recap_sequence_number_does_not_become_entry_number() -> None:
    entry = _rest_entry(1, 7001, 9001, "COMPLAINT filed")
    entry.pop("entry_number")
    entry["recap_sequence_number"] = "2026-01-01.001"

    parsed = CourtListenerDocketEntry.from_record(entry)

    assert parsed.entry_number is None


def test_bridge_rejects_contradictory_rest_docket_aliases() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    complaint = _rest_entry(1, 7001, 9001, "COMPLAINT filed")
    complaint["docket_id"] = 999
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={"results": [complaint], "next": None},
        ),
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_rest_entry_docket_alias_conflict: 7001",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_accepts_equivalent_rest_docket_url_alias_with_query() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    complaint = _rest_entry(1, 7001, 9001, "COMPLAINT filed")
    complaint["docket_id"] = (
        "https://www.courtlistener.com/api/rest/v4/dockets/123/?format=json"
    )
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={
                "results": [
                    complaint,
                    _rest_entry(5, 7005, 9005, "MOTION to Dismiss"),
                ],
                "next": None,
            },
        ),
        _recap_document_response(1, 7001, 9001, "Complaint"),
        _recap_document_response(5, 7005, 9005, "Motion to Dismiss"),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


def test_bridge_keeps_ambiguous_removed_state_complaint_excluded() -> None:
    screened, gap, downloads = _complaint_gap_inputs()
    removal = _rest_entry(1, 7001, 9001, "NOTICE OF REMOVAL filed")
    removal["recap_documents"] = [
        {
            "id": 9001,
            "attachment_number": 1,
            "description": "Exhibit A - Complaint",
            "is_available": False,
            "is_sealed": False,
        },
        {
            "id": 9002,
            "attachment_number": 2,
            "description": "Exhibit B - Amended Complaint",
            "is_available": False,
            "is_sealed": False,
        },
    ]
    responses = (
        _docket_response(),
        _response(
            path="/docket-entries/",
            params={"docket": "123", "page_size": 100},
            payload={"results": [removal], "next": None},
        ),
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="operative_complaint_not_found",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_preserves_explicit_private_false() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload["is_private"] = False
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)

    selection, relevance = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    [selected] = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    [relevant] = [
        document
        for document in relevance["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert selected["is_private"] is False
    assert relevant["is_private"] is False


def test_actual_v4_discovery_shape_flows_to_paid_gap_bridge() -> None:
    docket_response = _response(
        path="/dockets/123/",
        payload={
            "id": 123,
            "court": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Fixture v. Example",
            "absolute_url": "/docket/123/example/",
        },
    )
    live_shape_entries = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload={
            "results": [
                {
                    "id": 7001,
                    "docket": 123,
                    "entry_number": 1,
                    "description": "COMPLAINT filed by Plaintiff.",
                    "date_filed": "2026-01-01",
                    "recap_documents": [
                        {
                            "id": 9001,
                            "description": "Complaint",
                            "filepath_local": "recap/complaint.pdf",
                            "is_available": True,
                            "is_sealed": False,
                        }
                    ],
                },
                {
                    "id": 7005,
                    "docket": 123,
                    "entry_number": 5,
                    "description": "MOTION to Dismiss filed by Defendant.",
                    "date_filed": "2026-02-01",
                    "recap_documents": [
                        {
                            "id": 9005,
                            "description": "Motion to Dismiss",
                            "is_available": False,
                            "is_sealed": False,
                        }
                    ],
                },
                {
                    "id": 7016,
                    "docket": 123,
                    "entry_number": 16,
                    "description": "ORDER on Motion to Dismiss.",
                    "date_filed": "2026-06-30",
                    "recap_documents": [
                        {
                            "id": 9016,
                            "description": "Order on Motion to Dismiss",
                            "filepath_local": "recap/decision.pdf",
                            "is_available": True,
                            "is_sealed": False,
                        }
                    ],
                },
            ],
            "next": None,
        },
    )
    reconstructed = reconstruct_docket_page(
        _authenticated_client(docket_response, live_shape_entries), "123"
    )
    assert [
        document.freely_available
        for entry in reconstructed.page.entries
        for document in entry.documents
    ] == [True, False, True]

    screened = _screened_case()
    screened["selected_entries"] = [
        {
            "row_id": entry.row_id,
            "entry_number": entry.entry_number,
            "filed_at": entry.filed_at,
            "text": entry.text,
            "documents": [
                {
                    "kind": document.kind,
                    "description": document.description,
                    "href": document.href,
                    "action_label": document.action_label,
                    "pacer_only": document.pacer_only,
                }
                for document in entry.documents
            ],
        }
        for entry in reconstructed.page.entries
    ]
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    recap_document_response = _response(
        path="/recap-documents/9005/",
        payload={
            "id": 9005,
            "docket_entry": 7005,
            "document_number": "5",
            "attachment_number": None,
            "description": "Motion to Dismiss",
            "is_available": False,
            "is_sealed": False,
        },
    )

    selection, relevance = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap.to_record(),
        free_download_records=downloads,
        client=_authenticated_client(
            docket_response, live_shape_entries, recap_document_response
        ),
        use_embedded_entries=True,
    )

    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [
        (document["source_document_id"], document["is_private"]) for document in paid
    ] == [("9005", None)]
    [filtered] = filter_core_documents((relevance,))
    assert filtered.purchase_document_ids == ("9005",)


def test_batch_bridge_excludes_exhausted_transient_and_continues() -> None:
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    plan = plan_public_packet_downloads(
        (first, second), use_embedded_entries=True, target_clean_cases=2
    )
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"{request.candidate_id}/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    rate_limit = _response(
        path="/dockets/123/",
        status_code=429,
        payload={"detail": "daily quota reached"},
    )
    client = _authenticated_client(
        rate_limit,
        rate_limit,
        rate_limit,
        *_clean_responses_for(
            candidate_id="456",
            docket_number="1:26-cv-00002",
            case_name="Second v. Example",
            docket_entry_id="7105",
            recap_document_id="9105",
        ),
    )

    result = bridge_public_plan_paid_gaps_via_courtlistener(
        (first, second),
        public_selection_records=(),
        paid_gap_records=(gap.to_record() for gap in plan.paid_gap_cases),
        free_download_records=downloads,
        client=client,
        use_embedded_entries=True,
    )

    assert [record["candidate_id"] for record in result.selection_records] == ["456"]
    [exclusion] = result.exclusions
    assert exclusion["candidate_id"] == "123"
    assert exclusion["exclusion_reasons"] == [
        "courtlistener_rest_rate_limit_retries_exhausted"
    ]


def test_bridge_matches_selected_memo_attachment_not_main_notice() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0]["kind"] = "Main Document"
    documents[0].update(
        {
            "href": "https://storage.courtlistener.com/recap/notice.pdf",
            "action_label": "Download PDF",
            "pacer_only": False,
        }
    )
    documents.append(
        {
            "kind": "Attachment 1",
            "description": "Memorandum in Support",
            "href": "https://ecf.nysd.uscourts.gov/doc1/67890",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    )
    responses = list(_clean_responses())
    entry_payload = dict(responses[1].payload)
    rest_entries = cast(list[dict[str, object]], entry_payload["results"])
    rest_entries[0]["recap_documents"] = [{"id": 9005}, {"id": 9006}]
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=entry_payload,
    )
    main_payload = dict(responses[2].payload)
    main_payload["is_available"] = True
    responses[2] = _response(path="/recap-documents/9005/", payload=main_payload)
    responses.append(
        _response(
            path="/recap-documents/9006/",
            payload={
                "id": 9006,
                "docket_entry": 7005,
                "document_number": "5",
                "attachment_number": 1,
                "description": "Memorandum in Support",
                "is_available": False,
                "is_sealed": False,
            },
        )
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [
        (document["source_document_id"], document["document_role"]) for document in paid
    ] == [("9006", "motion_to_dismiss_memorandum")]


def test_bridge_fails_closed_on_ambiguous_attachment_identity() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["documents"] = [
        {
            "kind": "Attachment",
            "description": "Memorandum in Support",
            "href": "https://ecf.nysd.uscourts.gov/doc1/67890",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    ]
    responses = list(_clean_responses())
    entry_payload = dict(responses[1].payload)
    rest_entries = cast(list[dict[str, object]], entry_payload["results"])
    rest_entries[0]["recap_documents"] = [{"id": 9006}, {"id": 9007}]
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=entry_payload,
    )
    responses[2] = _response(
        path="/recap-documents/9006/",
        payload={
            "id": 9006,
            "docket_entry": 7005,
            "document_number": "5",
            "attachment_number": 1,
            "description": "Memorandum in Support",
            "is_available": False,
            "is_sealed": False,
        },
    )
    responses.append(
        _response(
            path="/recap-documents/9007/",
            payload={
                "id": 9007,
                "docket_entry": 7005,
                "document_number": "5",
                "attachment_number": 2,
                "description": "Memorandum in Support",
                "is_available": False,
                "is_sealed": False,
            },
        )
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_recap_document_match_ambiguous",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_authenticated_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_pacer_gaps_cli_runs_noncharging_courtlistener_rest_mode(
    tmp_path: Path,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap])
    _write_jsonl(downloads_path, list(downloads))
    _write_jsonl(
        fixture_path,
        [
            {
                "method": response.method,
                "path": response.path,
                "params": dict(response.params),
                "status_code": response.status_code,
                "payload": dict(response.payload),
            }
            for response in _clean_responses()
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--courtlistener-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_path),
                "--paid-gaps",
                str(gaps_path),
                "--free-download-manifest",
                str(downloads_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [selection] = _read_jsonl(output_root / "public-packet-selection-reconciled.jsonl")
    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [document["source_document_id"] for document in paid] == ["9005"]
    summary = json.loads(
        (output_root / "run-cards" / "bridge-pacer-gaps.json").read_text()
    )
    assert summary["courtlistener_request_count"] == 3
    assert summary["paid_activity_executed"] is False


def test_bridge_replays_pre_storage_host_success_and_rejects_tamper(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap])
    _write_jsonl(downloads_path, list(downloads))
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload.update(
        {
            "is_available": True,
            "filepath_local": "recap/newly-free-motion.pdf",
        }
    )
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)
    _write_jsonl(
        fixture_path,
        [_recorded_response_record(response) for response in responses],
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--courtlistener-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_path),
        "--paid-gaps",
        str(gaps_path),
        "--free-download-manifest",
        str(downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 0
    requests_path = output_root / "pacer-gap-free-document-requests.jsonl"
    [request] = _read_jsonl(requests_path)
    assert request["source_document_id"] == "9005"
    assert request["source_url"] == (
        "https://storage.courtlistener.com/recap/newly-free-motion.pdf"
    )
    [selection] = _read_jsonl(output_root / "public-packet-selection-reconciled.jsonl")
    assert selection["planning_status"] == "free_recovery_required"
    bridge_summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert bridge_summary["free_download_request_count"] == 1
    assert bridge_summary["paid_document_count"] == 0
    assert bridge_summary["document_bytes_ready_case_count"] == 0
    assert bridge_summary["next_stage"] == "download-free"

    [checkpoint_path] = sorted(
        (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
    )
    checkpoint = _read_json(checkpoint_path)
    assert checkpoint["bridge_semantic_revision"] == (
        _PACER_GAP_BRIDGE_SEMANTIC_REVISION
    )
    current_checkpoint_bytes = checkpoint_path.read_bytes()
    _write_jsonl(fixture_path, [])
    assert main(command) == 0
    current_resumed = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert current_resumed["semantic_replay_candidate_count"] == 0
    assert current_resumed["resumed_terminal_candidate_count"] == 1
    assert current_resumed["courtlistener_request_count"] == 0
    assert checkpoint_path.read_bytes() == current_checkpoint_bytes

    checkpoint["bridge_semantic_revision"] = (
        "courtlistener-rest-recap-sequence-semantics-2026-07-16-v3"
    )
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    safe_prior_checkpoint_bytes = checkpoint_path.read_bytes()
    assert main(command) == 0
    safe_prior_resumed = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert safe_prior_resumed["semantic_replay_candidate_count"] == 0
    assert safe_prior_resumed["resumed_terminal_candidate_count"] == 1
    assert safe_prior_resumed["courtlistener_request_count"] == 0
    assert checkpoint_path.read_bytes() == safe_prior_checkpoint_bytes

    old_url = "https://www.courtlistener.com/recap/newly-free-motion.pdf"
    payload = checkpoint["payload"]
    selection_document = next(
        document
        for document in payload["selection_record"]["documents"]
        if document["source_document_id"] == "9005"
    )
    selection_document["source_url"] = old_url
    selection_document["source_url_or_reference"] = old_url
    relevance_document = next(
        document
        for document in payload["case_relevance_record"]["documents"]
        if document["source_document_id"] == "9005"
    )
    relevance_document["source_url_or_reference"] = old_url
    payload["free_download_requests"][0]["source_url"] = old_url
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    _write_jsonl(
        fixture_path,
        [_recorded_response_record(response) for response in responses],
    )
    assert main(command) == 0
    assert _read_jsonl(requests_path) == [request]
    replayed = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert replayed["semantic_replay_candidate_count"] == 1
    assert replayed["resumed_terminal_candidate_count"] == 0
    assert replayed["courtlistener_request_count"] == 3

    checkpoint = _read_json(checkpoint_path)
    checkpoint["payload"]["free_download_requests"][0]["source_url"] = (
        "https://example.com/tampered.pdf"
    )
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert main(command) == 2
    assert "free recovery request drifted" in capsys.readouterr().err


@pytest.mark.parametrize(
    "exclusion_reason",
    (
        "courtlistener_recap_already_available",
        "operative_complaint_not_found",
        "courtlistener_recap_document_match_not_found",
        "courtlistener_rest_entry_number_alias_conflict",
    ),
)
def test_bridge_replays_exclusions_with_superseded_semantics(
    tmp_path: Path,
    exclusion_reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap])
    _write_jsonl(downloads_path, list(downloads))
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload["is_available"] = True
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)
    _write_jsonl(
        fixture_path,
        [_recorded_response_record(response) for response in responses],
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--courtlistener-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_path),
        "--paid-gaps",
        str(gaps_path),
        "--free-download-manifest",
        str(downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 0
    [checkpoint_path] = sorted(
        (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
    )
    checkpoint = _read_json(checkpoint_path)
    assert checkpoint["outcome"] == "exclusion"
    checkpoint["payload"]["exclusion_record"]["exclusion_reasons"] = [exclusion_reason]
    checkpoint["payload"]["exclusion_record"]["primary_exclusion_reason"] = (
        exclusion_reason
    )
    if exclusion_reason == "courtlistener_rest_entry_number_alias_conflict":
        checkpoint["bridge_semantic_revision"] = (
            "courtlistener-rest-operative-complaint-recovery-2026-07-16-v2"
        )
    else:
        checkpoint.pop("bridge_semantic_revision", None)
    checkpoint_path.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    recap_payload["filepath_local"] = "recap/newly-free-motion.pdf"
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)
    _write_jsonl(
        fixture_path,
        [_recorded_response_record(response) for response in responses],
    )

    assert main(command) == 0
    [request] = _read_jsonl(output_root / "pacer-gap-free-document-requests.jsonl")
    assert request["source_document_id"] == "9005"
    summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert summary["semantic_replay_candidate_count"] == 1
    assert summary["resumed_terminal_candidate_count"] == 0
    assert summary["courtlistener_request_count"] == 3
    replayed = _read_json(checkpoint_path)
    assert replayed["bridge_semantic_revision"] == _PACER_GAP_BRIDGE_SEMANTIC_REVISION


def test_semantic_replay_requires_exact_consistent_legacy_exclusion() -> None:
    reason = "operative_complaint_not_found"
    checkpoint: dict[str, Any] = {
        "outcome": "exclusion",
        "payload": {
            "exclusion_record": {
                "primary_exclusion_reason": reason,
                "exclusion_reasons": [reason],
            }
        },
    }

    assert _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["payload"]["exclusion_record"]["exclusion_reasons"] = [
        reason,
        "courtlistener_rest_response_invalid",
    ]
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    checkpoint["payload"]["exclusion_record"]["exclusion_reasons"] = [reason]
    checkpoint["payload"]["exclusion_record"]["primary_exclusion_reason"] = (
        "courtlistener_rest_response_invalid"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    checkpoint["payload"]["exclusion_record"]["primary_exclusion_reason"] = reason
    checkpoint["bridge_semantic_revision"] = (
        "courtlistener-complaint-and-main-description-2026-07-15-v1"
    )
    assert _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    checkpoint["bridge_semantic_revision"] = _PACER_GAP_BRIDGE_SEMANTIC_REVISION
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    checkpoint.pop("bridge_semantic_revision")
    checkpoint["outcome"] = "success"
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="case.dev"
    )


def test_success_semantic_replay_requires_exact_stale_download_binding() -> None:
    stale_url = "https://www.courtlistener.com/recap/example.pdf"
    checkpoint: dict[str, Any] = {
        "bridge_semantic_revision": (
            "courtlistener-rest-recap-sequence-semantics-2026-07-16-v3"
        ),
        "outcome": "success",
        "payload": {"free_download_requests": [{"source_url": stale_url}]},
    }

    assert _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["payload"]["free_download_requests"][0]["source_url"] = (
        "https://storage.courtlistener.com/recap/example.pdf"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["payload"]["free_download_requests"][0]["source_url"] = (
        stale_url + "?download=1"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["payload"]["free_download_requests"][0]["source_url"] = stale_url
    checkpoint.pop("bridge_semantic_revision")
    assert _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["bridge_semantic_revision"] = _PACER_GAP_BRIDGE_SEMANTIC_REVISION
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="case.dev"
    )


def test_alias_conflict_semantic_replay_requires_exact_v2_revision() -> None:
    reason = "courtlistener_rest_entry_number_alias_conflict"
    checkpoint: dict[str, Any] = {
        "bridge_semantic_revision": (
            "courtlistener-rest-operative-complaint-recovery-2026-07-16-v2"
        ),
        "outcome": "exclusion",
        "payload": {
            "exclusion_record": {
                "primary_exclusion_reason": reason,
                "exclusion_reasons": [reason],
            }
        },
    }

    assert _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint["bridge_semantic_revision"] = (
        "courtlistener-complaint-and-main-description-2026-07-15-v1"
    )
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )

    checkpoint.pop("bridge_semantic_revision")
    assert not _bridge_checkpoint_requires_semantic_replay(
        checkpoint, bridge_provider="courtlistener_rest"
    )


@pytest.mark.parametrize(
    ("exclusion_reason", "semantic_revision", "expected_replay"),
    (
        ("courtlistener_recap_already_available", None, True),
        (
            "courtlistener_recap_already_available",
            "courtlistener-complaint-and-main-description-2026-07-15-v1",
            False,
        ),
        (
            "courtlistener_recap_already_available",
            "courtlistener-rest-operative-complaint-recovery-2026-07-16-v2",
            False,
        ),
        ("courtlistener_recap_document_match_not_found", None, True),
        (
            "courtlistener_recap_document_match_not_found",
            "courtlistener-complaint-and-main-description-2026-07-15-v1",
            False,
        ),
        (
            "courtlistener_recap_document_match_not_found",
            "courtlistener-rest-recap-sequence-semantics-2026-07-16-v3",
            False,
        ),
        ("operative_complaint_not_found", None, True),
        (
            "operative_complaint_not_found",
            "courtlistener-complaint-and-main-description-2026-07-15-v1",
            True,
        ),
        (
            "operative_complaint_not_found",
            "courtlistener-rest-operative-complaint-recovery-2026-07-16-v2",
            False,
        ),
        (
            "operative_complaint_not_found",
            "courtlistener-rest-recap-sequence-semantics-2026-07-16-v3",
            False,
        ),
        (
            "courtlistener_rest_entry_number_alias_conflict",
            "courtlistener-rest-operative-complaint-recovery-2026-07-16-v2",
            True,
        ),
        (
            "courtlistener_rest_entry_number_alias_conflict",
            "courtlistener-rest-recap-sequence-semantics-2026-07-16-v3",
            False,
        ),
        (
            "operative_complaint_not_found",
            "future-unrelated-semantic-revision",
            False,
        ),
    ),
)
def test_exclusion_semantic_replay_is_reason_and_revision_specific(
    exclusion_reason: str,
    semantic_revision: str | None,
    expected_replay: bool,
) -> None:
    checkpoint: dict[str, Any] = {
        "outcome": "exclusion",
        "payload": {
            "exclusion_record": {
                "primary_exclusion_reason": exclusion_reason,
                "exclusion_reasons": [exclusion_reason],
            }
        },
    }
    if semantic_revision is not None:
        checkpoint["bridge_semantic_revision"] = semantic_revision

    assert (
        _bridge_checkpoint_requires_semantic_replay(
            checkpoint, bridge_provider="courtlistener_rest"
        )
        is expected_replay
    )


def test_current_v4_poststate_has_zero_semantic_replay_candidates() -> None:
    exclusion_reasons = (
        "courtlistener_recap_already_available",
        "courtlistener_recap_document_match_not_found",
        "operative_complaint_not_found",
        "courtlistener_rest_entry_number_alias_conflict",
    )
    checkpoints: list[dict[str, Any]] = [
        {
            "bridge_semantic_revision": _PACER_GAP_BRIDGE_SEMANTIC_REVISION,
            "outcome": "success",
            "payload": {
                "free_download_requests": [
                    {
                        "source_url": (
                            "https://storage.courtlistener.com/recap/"
                            f"current-{index}.pdf"
                        )
                    }
                ]
            },
        }
        for index in range(98)
    ]
    checkpoints.extend(
        {
            "bridge_semantic_revision": _PACER_GAP_BRIDGE_SEMANTIC_REVISION,
            "outcome": "exclusion",
            "payload": {
                "exclusion_record": {
                    "primary_exclusion_reason": reason,
                    "exclusion_reasons": [reason],
                }
            },
        }
        for reason in (
            exclusion_reasons[index % len(exclusion_reasons)] for index in range(27)
        )
    )

    assert len(checkpoints) == 125
    assert not any(
        _bridge_checkpoint_requires_semantic_replay(
            checkpoint, bridge_provider="courtlistener_rest"
        )
        for checkpoint in checkpoints
    )


def test_semantic_replay_that_remains_excluded_runs_only_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    screened = _screened_case()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    complaint_entry = next(
        entry for entry in selected_entries if entry["entry_number"] == "1"
    )
    complaint_documents = cast(list[dict[str, object]], complaint_entry["documents"])
    complaint_documents[0].update(
        {
            "action_label": "Buy on PACER",
            "href": "https://ecf.nysd.uscourts.gov/doc1/complaint",
            "pacer_only": True,
        }
    )
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = [
        {
            **request.to_record(),
            "local_path": f"123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    ]
    complaint_entry["text"] = "1 NOTICE regarding another filing."
    complaint_documents[0]["description"] = "Notice (Other)"

    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap.to_record()])
    _write_jsonl(downloads_path, downloads)
    _write_jsonl(
        fixture_path,
        [_recorded_response_record(response) for response in _clean_responses()],
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--courtlistener-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_path),
        "--paid-gaps",
        str(gaps_path),
        "--free-download-manifest",
        str(downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 0
    [checkpoint_path] = sorted(
        (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
    )
    first = _read_json(checkpoint_path)
    assert first["outcome"] == "exclusion"
    assert first["payload"]["exclusion_record"]["primary_exclusion_reason"] == (
        "operative_complaint_not_found"
    )
    first.pop("bridge_semantic_revision")
    checkpoint_path.write_text(
        json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    assert main(command) == 0
    replayed = _read_json(checkpoint_path)
    assert replayed["outcome"] == "exclusion"
    assert replayed["payload"]["exclusion_record"]["primary_exclusion_reason"] == (
        "operative_complaint_not_found"
    )
    assert replayed["bridge_semantic_revision"] == _PACER_GAP_BRIDGE_SEMANTIC_REVISION
    replay_summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert replay_summary["semantic_replay_candidate_count"] == 1
    assert replay_summary["courtlistener_request_count"] == 2

    _write_jsonl(fixture_path, [])
    assert main(command) == 0
    resumed_summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert resumed_summary["semantic_replay_candidate_count"] == 0
    assert resumed_summary["resumed_terminal_candidate_count"] == 1
    assert resumed_summary["courtlistener_request_count"] == 0

    invalid = _read_json(checkpoint_path)
    invalid["bridge_semantic_revision"] = "unknown-or-newer-revision"
    checkpoint_path.write_text(
        json.dumps(invalid, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert main(command) == 2
    assert "PACER-gap bridge checkpoint is invalid" in capsys.readouterr().err


def test_courtlistener_rest_bridge_checkpoints_and_resumes_without_refetch(
    tmp_path: Path,
) -> None:
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    plan = plan_public_packet_downloads(
        (first, second), use_embedded_entries=True, target_clean_cases=2
    )
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [first, second])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap.to_record() for gap in plan.paid_gap_cases])
    _write_jsonl(
        downloads_path,
        [
            {
                **request.to_record(),
                "local_path": (
                    f"{request.candidate_id}/{request.source_document_id}.pdf"
                ),
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "GET",
        "path": "/dockets/456/",
        "params": {},
        "status_code": 429,
        "payload": {"detail": "daily quota reached"},
    }
    _write_jsonl(
        fixture_path,
        [
            *(_recorded_response_record(response) for response in _clean_responses()),
            rate_limit,
            rate_limit,
            rate_limit,
        ],
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--courtlistener-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_path),
        "--paid-gaps",
        str(gaps_path),
        "--free-download-manifest",
        str(downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 2
    checkpoints = [
        _read_json(path)
        for path in sorted(
            (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
        )
    ]
    assert [checkpoint["outcome"] for checkpoint in checkpoints] == [
        "success",
        "retryable",
    ]
    first_run = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert first_run["courtlistener_request_count"] == 6
    assert first_run["checkpoint_terminal_candidate_count"] == 1
    assert first_run["retryable_candidate_count"] == 1

    _write_jsonl(
        fixture_path,
        [
            _recorded_response_record(response)
            for response in _clean_responses_for(
                candidate_id="456",
                docket_number="1:26-cv-00002",
                case_name="Second v. Example",
                docket_entry_id="7456",
                recap_document_id="9456",
            )
        ],
    )

    assert main(command) == 0
    selections = _read_jsonl(output_root / "public-packet-selection-reconciled.jsonl")
    assert {selection["candidate_id"] for selection in selections} == {"123", "456"}
    resumed = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert resumed["courtlistener_request_count"] == 3
    assert resumed["resumed_terminal_candidate_count"] == 1
    assert resumed["checkpoint_terminal_candidate_count"] == 2
    assert resumed["retryable_candidate_count"] == 0


@pytest.mark.parametrize(
    ("docket_patch", "reason"),
    (
        ({"id": 999}, "courtlistener_direct_id_conflict"),
        ({"court": "cacd"}, "courtlistener_exact_match_not_found"),
        ({"docket_number": "9:99-cv-99999"}, "courtlistener_exact_match_not_found"),
        ({"case_name": "Wrong v. Caption"}, "courtlistener_caption_conflict"),
    ),
)
def test_courtlistener_rest_bridge_rejects_docket_identity_mismatch(
    docket_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[0].payload)
    payload.update(docket_patch)
    responses[0] = _response(path="/dockets/123/", payload=payload)

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    "source_url",
    (
        None,
        "https://www.courtlistener.com/api/rest/v4/dockets/123/",
    ),
)
def test_courtlistener_rest_bridge_accepts_source_without_web_docket_id(
    source_url: str | None,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    candidate = cast(dict[str, object], screened["candidate"])
    if source_url is None:
        candidate.pop("url")
    else:
        candidate["url"] = source_url

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*_clean_responses()),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


def test_courtlistener_rest_bridge_rejects_positive_source_id_mismatch() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    candidate = cast(dict[str, object], screened["candidate"])
    candidate["url"] = "https://www.courtlistener.com/docket/999/wrong/"

    with pytest.raises(
        CourtListenerCaseDevBridgeError, match="courtlistener_source_id_conflict"
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    ("entry_patch", "reason"),
    (
        ({"docket": 999}, "courtlistener_entry_docket_conflict"),
        ({"entry_number": 6}, "courtlistener_entry_not_found"),
        ({"description": "Unrelated filing"}, "courtlistener_entry_text_conflict"),
        ({"date_filed": "2026-01-02"}, "courtlistener_entry_date_conflict"),
    ),
)
def test_courtlistener_rest_bridge_rejects_entry_mismatch(
    entry_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = payload["results"]
    assert isinstance(results, list)
    entry = cast(object, results[0])
    assert isinstance(entry, dict)
    entry.update(entry_patch)
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    ("web_filed_at", "rest_filed_at"),
    (
        ("2026-01-01", "2026-01-01"),
        ("July 6, 2026, 12:22 p.m.", "2026-07-06"),
        ("Dec. 9, 2025, 3:38 p.m.", "2025-12-09"),
        ("Jul 1, 2026", "2026-07-01"),
    ),
)
def test_courtlistener_rest_bridge_accepts_real_web_date_formats(
    web_filed_at: str,
    rest_filed_at: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["filed_at"] = web_filed_at
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = cast(list[dict[str, object]], payload["results"])
    results[0]["date_filed"] = rest_filed_at
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


def test_courtlistener_rest_bridge_rejects_mismatched_real_web_date() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["filed_at"] = "Dec. 9, 2025, 3:38 p.m."
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = cast(list[dict[str, object]], payload["results"])
    results[0]["date_filed"] = "2025-12-10"
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_entry_date_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_accepts_ui_decorated_web_entry_text() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["filed_at"] = "Dec. 9, 2025, 3:38 p.m."
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0]["kind"] = "Main Doc \u00adument"
    motion["text"] = (
        "5 Dec. 9, 2025, 3:38 p.m. 5 Dec 9, 2025 "
        "MOTION to Dismiss filed by Defendant. Main Doc \u00adument "
        "Motion to Dismiss Buy on PACER 0 \U0001f64f Main Doc \u00adument "
        "Motion to Dismiss Buy on PACER"
    )
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = cast(list[dict[str, object]], payload["results"])
    results[0]["date_filed"] = "2025-12-09"
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


def test_courtlistener_rest_bridge_rejects_genuine_ui_decorated_text_mismatch() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0]["kind"] = "Main Document"
    motion["text"] = (
        "5 Dec. 9, 2025, 3:38 p.m. 5 Dec 9, 2025 "
        "NOTICE of hearing on an unrelated motion. Main Document "
        "Motion to Dismiss Buy on PACER"
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_entry_text_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_accepts_bodyless_ui_entry_from_document() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["filed_at"] = "June 5, 2026, 4:20 p.m."
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0]["kind"] = "Main Doc \u00adument"
    motion["text"] = (
        "5 June 5, 2026, 4:20 p.m. 5 Jun 5, 2026 "
        "Main Doc \u00adument Dismiss Buy on PACER"
    )
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = cast(list[dict[str, object]], payload["results"])
    results[0]["date_filed"] = "2026-06-05"
    documents[0]["description"] = "Dismiss"
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )
    recap_payload = dict(responses[2].payload)
    recap_payload["description"] = "Dismiss"
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


@pytest.mark.parametrize(
    "decorated_suffix",
    (
        "Main Document unrelated narrative Motion to Dismiss Buy on PACER",
        "Main Document Motion to Dismiss Buy on PACER unrelated trailing narrative",
    ),
    ids=("noncontiguous-card-fields", "trailing-narrative"),
)
def test_bridge_rejects_partially_explained_document_card_suffix(
    decorated_suffix: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0]["kind"] = "Main Document"
    motion["text"] = "5 Dec. 9, 2025, 3:38 p.m. 5 Dec 9, 2025 " + decorated_suffix

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_entry_text_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def test_bridge_accepts_bodyless_attachment_after_document_card() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0].update(
        {
            "kind": "Main Document",
            "description": "Notice of Motion",
            "href": "https://storage.courtlistener.com/recap/notice.pdf",
            "action_label": "Download PDF",
            "pacer_only": False,
        }
    )
    documents.append(
        {
            "kind": "Attachment 1",
            "description": "Motion to Dismiss",
            "href": "https://ecf.nysd.uscourts.gov/doc1/67890",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    )
    motion["text"] = (
        "5 Dec. 9, 2025, 3:38 p.m. 5 Dec 9, 2025 "
        "Main Document Notice of Motion Download PDF "
        "Attachment 1 Motion to Dismiss Buy on PACER"
    )
    motion["filed_at"] = "Dec. 9, 2025, 3:38 p.m."
    responses = list(_clean_responses())
    entry_payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    rest_entries = cast(list[dict[str, object]], entry_payload["results"])
    rest_entries[0]["date_filed"] = "2025-12-09"
    rest_entries[0]["recap_documents"] = [{"id": 9005}, {"id": 9006}]
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=entry_payload,
    )
    main_payload = dict(responses[2].payload)
    main_payload.update(
        {
            "description": "Notice of Motion",
            "is_available": True,
            "filepath_local": "recap/notice.pdf",
        }
    )
    responses[2] = _response(path="/recap-documents/9005/", payload=main_payload)
    responses.append(
        _response(
            path="/recap-documents/9006/",
            payload={
                "id": 9006,
                "docket_entry": 7005,
                "document_number": "5",
                "attachment_number": 1,
                "description": "Motion to Dismiss",
                "is_available": False,
                "is_sealed": False,
            },
        )
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_authenticated_client(*responses),
        use_embedded_entries=True,
    )

    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [document["source_document_id"] for document in paid] == ["9006"]


def test_courtlistener_rest_bridge_preserves_narrative_before_document_cards() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0].update(
        {
            "kind": "Main Document",
            "description": "Notice of Motion",
            "action_label": "Download PDF",
            "pacer_only": False,
        }
    )
    documents.append(
        {
            "kind": "Attachment 1",
            "description": "Motion to Dismiss",
            "href": "https://ecf.nysd.uscourts.gov/doc1/67890",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    )
    motion["text"] = (
        "5 Dec. 9, 2025, 3:38 p.m. 5 Dec 9, 2025 "
        "NOTICE of hearing on an unrelated motion. "
        "Main Document Notice of Motion Download PDF "
        "Attachment 1 Motion to Dismiss Buy on PACER"
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_entry_text_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_rejects_changed_genuine_leading_number() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    motion["text"] = "5 motions were filed before Defendant moved to dismiss."
    responses = list(_clean_responses())
    entry_payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    rest_entries = cast(list[dict[str, object]], entry_payload["results"])
    rest_entries[0]["description"] = (
        "Four motions were filed before Defendant moved to dismiss."
    )
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=entry_payload,
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_entry_text_conflict",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_preserves_sparse_unknown_seal_as_recoverable_paid_gap() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload.pop("docket_entry")
    recap_payload.pop("description")
    recap_payload["is_sealed"] = None
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)

    selection, relevance = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    [document] = [
        item
        for item in selection["documents"]
        if item.get("resolved_from_paid_gap") is True
    ]
    assert document["requires_paid_recovery"] is True
    assert document["is_sealed"] is None
    assert document["redaction_or_seal_status"] == "unknown"
    assert document["restriction_evidence"] == [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_sealed_unknown",
    ]
    [relevance_document] = [
        item
        for item in relevance["documents"]
        if item.get("resolved_from_paid_gap") is True
    ]
    assert relevance_document["redaction_or_seal_status"] == "unknown"


@pytest.mark.parametrize(
    ("detail_patch", "message"),
    (
        (
            {"docket_entry_id": 7999},
            "conflicting CourtListener docket entry reference aliases",
        ),
        (
            {"documentNumber": "6"},
            "conflicting CourtListener document number aliases",
        ),
    ),
    ids=("docket-entry", "document-number"),
)
def test_bridge_rejects_conflicting_recap_detail_aliases(
    detail_patch: dict[str, object],
    message: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload.update(detail_patch)
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)

    with pytest.raises(CourtListenerResponseError, match=message):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_bridge_accepts_equivalent_recap_detail_aliases() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    recap_payload = dict(responses[2].payload)
    recap_payload.update(
        {
            "docket_entry_id": (
                "https://www.courtlistener.com/api/rest/v4/docket-entries/7005/"
            ),
            "documentNumber": 5,
        }
    )
    responses[2] = _response(path="/recap-documents/9005/", payload=recap_payload)

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


@pytest.mark.parametrize(
    (
        "web_description",
        "recap_description",
        "attachment_number",
        "expected_error",
    ),
    (
        (
            "Judgment on the Pleadings",
            "Motion for Judgment on the Pleadings",
            None,
            None,
        ),
        ("Dismiss", "Motion to Dismiss", None, None),
        (
            "Judgment on the Pleadings",
            "Motion for Summary Judgment",
            None,
            "courtlistener_recap_document_match_not_found: 38",
        ),
        (
            "Judgment on the Pleadings",
            "Motion for Judgment on the Pleadings",
            1,
            "courtlistener_recap_document_match_not_found: 38",
        ),
        (
            "Motion to Dismiss",
            "Motion for Motion to Dismiss",
            None,
            "courtlistener_recap_document_match_not_found: 38",
        ),
        (
            "Motion for Judgment",
            "Motion to Motion for Judgment",
            None,
            "courtlistener_recap_document_match_not_found: 38",
        ),
    ),
    ids=(
        "motion-for-equivalent-main",
        "motion-to-equivalent-main",
        "genuine-conflict",
        "attachment-not-main",
        "cross-prefix-motion-for",
        "cross-prefix-motion-to",
    ),
)
def test_bridge_handles_nobriga_main_document_description_equivalence(
    web_description: str,
    recap_description: str,
    attachment_number: int | None,
    expected_error: str | None,
) -> None:
    screened = _screened_case_variant(
        candidate_id="69466572",
        docket_number="3:24-cv-01980",
        case_name="Nobriga v. Clear Blue Specialty Insurance Company",
    )
    candidate = cast(dict[str, object], screened["candidate"])
    metadata = cast(dict[str, object], candidate["metadata"])
    metadata["court"] = "ctd"
    ai = cast(dict[str, object], screened["ai"])
    ai.update(
        {
            "target_motion_entry_numbers": ["38"],
            "decision_entry_numbers": ["63"],
        }
    )
    screened["selected_entries"] = [
        _entry(
            1,
            "COMPLAINT filed by Plaintiff.",
            "Complaint",
            "https://storage.courtlistener.com/complaint.pdf",
            pacer_only=False,
        ),
        _entry(
            38,
            "Motion for Judgment on the Pleadings",
            web_description,
            "https://ecf.ctd.uscourts.gov/doc1/04109336810?caseid=162721",
            pacer_only=True,
        ),
        _entry(
            63,
            "ORDER granting ECF No. 38.",
            "Order on Motion for Judgment on the Pleadings",
            (
                "https://storage.courtlistener.com/recap/"
                "gov.uscourts.ctd.162721/gov.uscourts.ctd.162721.63.0.pdf"
            ),
            pacer_only=False,
        ),
    ]
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion_entry = next(
        entry for entry in selected_entries if entry["entry_number"] == "38"
    )
    motion_entry["filed_at"] = "Oct. 30, 2025, 10:43 a.m."
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"69466572/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    responses = (
        _response(
            path="/dockets/69466572/",
            payload={
                "id": 69466572,
                "court": "ctd",
                "docket_number": "3:24-cv-01980",
                "case_name": "Nobriga v. Clear Blue Specialty Insurance Company",
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": "69466572", "page_size": 100},
            payload={
                "results": [
                    {
                        "id": 70038,
                        "docket": 69466572,
                        "entry_number": 38,
                        "description": "Motion for Judgment on the Pleadings",
                        "date_filed": "2025-10-30",
                        "recap_documents": [{"id": 457180788}],
                    }
                ],
                "next": None,
            },
        ),
        _response(
            path="/recap-documents/457180788/",
            payload={
                "id": 457180788,
                "docket_entry": 70038,
                "document_number": "38",
                "attachment_number": attachment_number,
                "description": recap_description,
                "is_available": False,
                "is_sealed": False,
            },
        ),
    )

    if expected_error is not None:
        with pytest.raises(CourtListenerCaseDevBridgeError, match=expected_error):
            bridge_public_plan_paid_gap_candidate_via_courtlistener(
                screened,
                paid_gap_record=gap.to_record(),
                free_download_records=downloads,
                client=_client(*responses),
                use_embedded_entries=True,
            )
        return

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap.to_record(),
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    recovered = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [document["source_document_id"] for document in recovered] == ["457180788"]


def test_docket_71985792_reconciles_motion_to_main_description() -> None:
    screened = _screened_case_variant(
        candidate_id="71985792",
        docket_number="3:25-cv-10355",
        case_name=("Epidemic Sound, AB v. Meta Platforms, Inc., f/k/a Facebook, Inc."),
    )
    candidate = cast(dict[str, object], screened["candidate"])
    metadata = cast(dict[str, object], candidate["metadata"])
    metadata["court"] = "cand"
    ai = cast(dict[str, object], screened["ai"])
    ai.update(
        {
            "target_motion_entry_numbers": ["48"],
            "decision_entry_numbers": ["58"],
        }
    )
    motion_text = "MOTION to Dismiss Complaint filed by Meta Platforms, Inc."
    screened["selected_entries"] = [
        _entry(
            1,
            "COMPLAINT filed by Plaintiff.",
            "Complaint",
            "https://storage.courtlistener.com/complaint.pdf",
            pacer_only=False,
        ),
        _entry(
            48,
            motion_text,
            "Dismiss",
            "https://ecf.cand.uscourts.gov/doc1/035026975626?caseid=460656",
            pacer_only=True,
        ),
        _entry(
            58,
            "ORDER granting in part ECF No. 48.",
            "Order on Motion to Dismiss",
            "https://storage.courtlistener.com/recap/decision.pdf",
            pacer_only=False,
        ),
    ]
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"71985792/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    responses = (
        _response(
            path="/dockets/71985792/",
            payload={
                "id": 71985792,
                "court": "cand",
                "docket_number": "3:25-cv-10355",
                "case_name": (
                    "Epidemic Sound, AB v. Meta Platforms, Inc., f/k/a Facebook, Inc."
                ),
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": "71985792", "page_size": 100},
            payload={
                "results": [
                    {
                        "id": 70048,
                        "docket": 71985792,
                        "entry_number": 48,
                        "description": motion_text,
                        "date_filed": "2026-01-01",
                        "recap_documents": [
                            {"id": 475181725},
                            {"id": 475244563},
                        ],
                    }
                ],
                "next": None,
            },
        ),
        _response(
            path="/recap-documents/475181725/",
            payload={
                "id": 475181725,
                "docket_entry": 70048,
                "document_number": "48",
                "attachment_number": None,
                "description": "Motion to Dismiss",
                "is_available": False,
                "is_sealed": None,
            },
        ),
        _response(
            path="/recap-documents/475244563/",
            payload={
                "id": 475244563,
                "docket_entry": 70048,
                "document_number": "48",
                "attachment_number": 1,
                "description": "Proposed Order",
                "is_available": False,
                "is_sealed": None,
            },
        ),
    )

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap.to_record(),
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    recovered = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [document["source_document_id"] for document in recovered] == ["475181725"]
    assert recovered[0]["docket_entry_number"] == 48
    assert recovered[0]["is_sealed"] is None
    assert recovered[0]["redaction_or_seal_status"] == "unknown"


@pytest.mark.parametrize(
    ("document_patch", "reason"),
    (
        ({"id": 9999}, "courtlistener_recap_document_id_conflict"),
        ({"docket_entry": 7999}, "courtlistener_recap_entry_conflict"),
        (
            {"document_number": None},
            "courtlistener_recap_document_number_unproven",
        ),
        ({"is_sealed": True}, "restricted_core_document"),
        ({"is_private": True}, "restricted_core_document"),
        ({"is_available": True}, "courtlistener_recap_public_url_unproven"),
        ({"attachment_number": 1}, "courtlistener_recap_document_match_not_found"),
    ),
)
def test_courtlistener_rest_bridge_rejects_unproven_or_restricted_document(
    document_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload.update(document_patch)
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize("restricted_record", ("entry", "document"))
def test_courtlistener_rest_bridge_rejects_public_page_restriction_marker(
    restricted_record: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    if restricted_record == "entry":
        motion["restriction_markers"] = ["sealed"]
    else:
        documents = cast(list[dict[str, object]], motion["documents"])
        documents[0]["restriction_markers"] = ["sealed"]

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="restricted_core_document: 5",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_rejects_rest_entry_restriction_marker() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    entry_payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    rest_entries = cast(list[dict[str, object]], entry_payload["results"])
    rest_entries[0]["is_sealed"] = True
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=entry_payload,
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="restricted_core_document: 5",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_recovers_gap_that_became_public() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload.update(
        {
            "is_available": True,
            "filepath_local": "recap/newly-free-motion.pdf",
        }
    )
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    result = bridge_public_plan_paid_gaps_via_courtlistener(
        (screened,),
        public_selection_records=(),
        paid_gap_records=(gap,),
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    [selection] = result.selection_records
    recovered = [
        document
        for document in selection["documents"]
        if document.get("resolved_from_paid_gap") is True
    ]
    assert recovered == [
        {
            "availability_status": "available",
            "candidate_id": "123",
            "contains_target_outcome": False,
            "courtlistener_docket_entry_id": "7005",
            "description": "Motion to Dismiss",
            "docket_entry_number": 5,
            "document_role": "motion_to_dismiss_memorandum",
            "file_extension": "pdf",
            "is_predecision_material": True,
            "is_private": None,
            "is_sealed": False,
            "model_visible": True,
            "redaction_or_seal_status": "public",
            "requires_paid_recovery": False,
            "resolved_from_paid_gap": True,
            "restriction_evidence": [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_true",
                "courtlistener_rest_recap_document_is_sealed_false",
                "courtlistener_rest_public_download_url_allowlisted",
            ],
            "source_document_id": "9005",
            "source_provider": "courtlistener",
            "source_url": (
                "https://storage.courtlistener.com/recap/newly-free-motion.pdf"
            ),
            "source_url_or_reference": (
                "https://storage.courtlistener.com/recap/newly-free-motion.pdf"
            ),
        }
    ]
    assert selection["paid_recovery_required"] is False
    assert selection["planning_status"] == "free_recovery_required"
    assert selection["document_recovery_status"] == "free_recovery_required"
    assert result.paid_document_count == 0
    assert result.document_bytes_ready_case_count == 0
    assert [request.to_record() for request in result.free_download_requests] == [
        {
            "candidate_id": "123",
            "document_role": "motion_to_dismiss_memorandum",
            "docket_entry_number": 5,
            "file_extension": "pdf",
            "source_document_id": "9005",
            "source_provider": "courtlistener",
            "source_url": (
                "https://storage.courtlistener.com/recap/newly-free-motion.pdf"
            ),
        }
    ]


def test_bridge_downloads_public_url_with_unknown_seal_for_clearance() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload.update(
        {
            "is_available": True,
            "is_sealed": None,
            "filepath_local": "recap/newly-free-motion.pdf",
        }
    )
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    result = bridge_public_plan_paid_gaps_via_courtlistener(
        (screened,),
        public_selection_records=(),
        paid_gap_records=(gap,),
        free_download_records=downloads,
        client=_client(*responses),
        use_embedded_entries=True,
    )

    [selection] = result.selection_records
    [document] = [
        item
        for item in selection["documents"]
        if item.get("resolved_from_paid_gap") is True
    ]
    assert document["availability_status"] == "available"
    assert document["requires_paid_recovery"] is False
    assert document["redaction_or_seal_status"] == "unknown"
    assert document["is_sealed"] is None
    assert document["restriction_evidence"] == [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    ]
    assert len(result.free_download_requests) == 1


@pytest.mark.parametrize(
    "public_path",
    (
        None,
        "https://example.com/newly-free-motion.pdf",
        "http://www.courtlistener.com/recap/newly-free-motion.pdf",
        "https://www.courtlistener.com/",
        "https://www.courtlistener.com/api/rest/v4/recap-documents/9005/",
        "https://www.courtlistener.com/recap/newly free motion.pdf",
        "https://www.courtlistener.com/recap/newly-free-motion.pdf#fragment",
        "https://www.courtlistener.com/recap/newly-free-motion.pdf?download=1",
        "https://www.courtlistener.com/recap/newly-free-motion.pdf;download",
        "https://www.courtlistener.com/recap/../secret.pdf",
        "https://www.courtlistener.com/recap/%2e%2e/secret.pdf",
        "https://www.courtlistener.com/recap/%2525252e%2525252e/secret.pdf",
        "https://www.courtlistener.com/recap/foo\\..\\secret.pdf",
        "https://[::1/recap/newly-free-motion.pdf",
        "https://www.courtlistener.com\uff0fevil/recap/newly-free-motion.pdf",
        "https://storage.courtlistener.com/not-a-pdf",
    ),
)
def test_courtlistener_rest_bridge_rejects_unproven_public_download_url(
    public_path: str | None,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload["is_available"] = True
    if public_path is not None:
        payload["filepath_local"] = public_path
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="courtlistener_recap_public_url_unproven",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_rejects_malformed_private_flag() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload["is_private"] = "true"
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    with pytest.raises(
        CourtListenerResponseError,
        match="is_private must be boolean or null",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_rejects_web_document_that_became_free() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0].update(
        {
            "action_label": "Download PDF",
            "freely_available": True,
            "href": "https://storage.courtlistener.com/recap/newly-free.pdf",
            "pacer_only": False,
        }
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="paid_gap_public_document_conflict: 5",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def _paid_gap_inputs() -> tuple[
    dict[str, object], dict[str, object], tuple[dict[str, object], ...]
]:
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    return screened, gap.to_record(), downloads


def _complaint_gap_inputs() -> tuple[
    dict[str, object], dict[str, object], tuple[dict[str, object], ...]
]:
    screened = _screened_case()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    complaint = next(
        entry for entry in selected_entries if entry["entry_number"] == "1"
    )
    [complaint_document] = cast(list[dict[str, object]], complaint["documents"])
    complaint_document.update(
        {
            "href": "https://ecf.nysd.uscourts.gov/doc1/complaint",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    )
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    screened["selected_entries"] = [
        entry for entry in selected_entries if entry["entry_number"] != "1"
    ]
    return screened, gap.to_record(), downloads


def _docket_response() -> RecordedCourtListenerResponse:
    return _response(
        path="/dockets/123/",
        payload={
            "id": 123,
            "court": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Fixture v. Example",
        },
    )


def _rest_entry(
    entry_number: int,
    docket_entry_id: int,
    document_id: int,
    description: str,
) -> dict[str, object]:
    document_description = (
        "Amended Complaint"
        if "amended complaint" in description.casefold()
        else "Complaint"
        if "complaint" in description.casefold()
        else "Motion to Dismiss"
    )
    return {
        "id": docket_entry_id,
        "docket": 123,
        "entry_number": entry_number,
        "description": description,
        "date_filed": "2026-01-01",
        "recap_documents": [
            {
                "id": document_id,
                "attachment_number": None,
                "description": document_description,
                "is_available": False,
                "is_sealed": False,
            }
        ],
    }


def _recap_document_response(
    entry_number: int,
    docket_entry_id: int,
    document_id: int,
    description: str,
) -> RecordedCourtListenerResponse:
    return _response(
        path=f"/recap-documents/{document_id}/",
        payload={
            "id": document_id,
            "docket_entry": docket_entry_id,
            "document_number": str(entry_number),
            "attachment_number": None,
            "description": description,
            "is_available": False,
            "is_sealed": False,
        },
    )


def _clean_responses() -> tuple[RecordedCourtListenerResponse, ...]:
    return _clean_responses_for(
        candidate_id="123",
        docket_number="1:26-cv-00001",
        case_name="Fixture v. Example",
        docket_entry_id="7005",
        recap_document_id="9005",
    )


def _clean_responses_for(
    *,
    candidate_id: str,
    docket_number: str,
    case_name: str,
    docket_entry_id: str,
    recap_document_id: str,
) -> tuple[RecordedCourtListenerResponse, ...]:
    return (
        _response(
            path=f"/dockets/{candidate_id}/",
            payload={
                "id": int(candidate_id),
                "court": "nysd",
                "docket_number": docket_number,
                "case_name": case_name,
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": candidate_id, "page_size": 100},
            payload={
                "results": [
                    {
                        "id": int(docket_entry_id),
                        "docket": int(candidate_id),
                        "entry_number": 5,
                        "description": "MOTION to Dismiss filed by Defendant.",
                        "date_filed": "2026-01-01",
                        "recap_documents": [{"id": int(recap_document_id)}],
                    }
                ],
                "next": None,
            },
        ),
        _response(
            path=f"/recap-documents/{recap_document_id}/",
            payload={
                "id": int(recap_document_id),
                "docket_entry": int(docket_entry_id),
                "document_number": "5",
                "attachment_number": None,
                "description": "Motion to Dismiss",
                "is_available": False,
                "is_sealed": False,
            },
        ),
    )


def _client(*responses: RecordedCourtListenerResponse) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(responses),
    )


def _authenticated_client(
    *responses: RecordedCourtListenerResponse,
) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(api_token="fixture-token"),
        transport=CourtListenerFixtureTransport(responses),
    )


def _response(
    *,
    path: str,
    payload: dict[str, object],
    params: dict[str, object] | None = None,
    status_code: int = 200,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path=path,
        params={} if params is None else params,
        status_code=status_code,
        payload=payload,
    )


def _screened_case() -> dict[str, object]:
    return {
        "nature_of_suit": "440 Civil Rights",
        "nos_macro_category": "civil_rights",
        "candidate": {
            "docket_id": "123",
            "candidate_key": "123",
            "metadata": {
                "case_id": "123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _entry(
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _screened_case_variant(
    *, candidate_id: str, docket_number: str, case_name: str
) -> dict[str, object]:
    screened = copy.deepcopy(_screened_case())
    candidate = cast(object, screened["candidate"])
    assert isinstance(candidate, dict)
    candidate["docket_id"] = candidate_id
    candidate["candidate_key"] = candidate_id
    candidate["url"] = f"https://www.courtlistener.com/docket/{candidate_id}/example/"
    metadata = cast(object, candidate["metadata"])
    assert isinstance(metadata, dict)
    metadata["case_id"] = candidate_id
    metadata["docket_number"] = docket_number
    metadata["case_name"] = case_name
    return screened


def _write_jsonl(path: Path, records: list[object]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text().splitlines()
        if line
    ]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _recorded_response_record(
    response: RecordedCourtListenerResponse,
) -> dict[str, object]:
    return {
        "method": response.method,
        "path": response.path,
        "params": dict(response.params),
        "status_code": response.status_code,
        "payload": dict(response.payload),
    }


def _entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "main_document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }
