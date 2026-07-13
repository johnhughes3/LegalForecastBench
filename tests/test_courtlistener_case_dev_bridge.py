from __future__ import annotations

import copy

import pytest
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevConfig,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.courtlistener_case_dev_bridge import (
    CourtListenerCaseDevBridgeError,
    bridge_courtlistener_case_dev_documents,
    bridge_public_plan_paid_gaps,
    merge_download_manifest_records,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads


def test_bridge_uses_authoritative_case_dev_ids_and_keeps_free_first() -> None:
    result = bridge_courtlistener_case_dev_documents(
        (_screened_case(),),
        client=_client(
            _search_response(_case_dev_docket()),
            _lookup_response(),
        ),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    assert result.selected_case_count == 1
    assert result.exclusions == ()
    [selection] = result.selection_records
    assert selection["candidate_id"] == "cl-123"
    assert selection["case_id"] == "case-dev-777"
    assert selection["nature_of_suit"] == "440 Civil Rights"
    assert selection["nos_macro_category"] == "civil_rights"
    assert selection["related_family_id"] == "family-1"
    assert selection["mdl_family_id"] == "mdl-999"
    assert [document["source_document_id"] for document in selection["documents"]] == [
        "case-dev-complaint",
        "case-dev-mtd",
        "case-dev-decision",
    ]
    assert [
        request.source_document_id for request in result.free_download_requests
    ] == [
        "case-dev-complaint",
        "case-dev-decision",
    ]
    assert [
        request.docket_entry_number for request in result.free_download_requests
    ] == [
        1,
        16,
    ]

    [relevance] = result.case_relevance_records
    documents = relevance["documents"]
    assert [document["source_document_id"] for document in documents] == [
        "case-dev-complaint",
        "case-dev-mtd",
        "case-dev-decision",
    ]
    assert [document["requires_paid_recovery"] for document in documents] == [
        False,
        True,
        False,
    ]
    [core_filter] = filter_core_documents(result.case_relevance_records)
    assert core_filter.purchase_document_ids == ("case-dev-mtd",)


def test_bridge_fails_closed_on_ambiguous_exact_docket_match() -> None:
    duplicate = {
        **_case_dev_docket(),
        "id": "case-dev-888",
    }
    result = bridge_courtlistener_case_dev_documents(
        (_screened_case(),),
        client=_client(_search_response(_case_dev_docket(), duplicate)),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    assert result.selection_records == ()
    [exclusion] = result.exclusions
    assert exclusion["candidate_id"] == "cl-123"
    assert exclusion["exclusion_reasons"] == ["case_dev_exact_match_ambiguous"]


def test_bridge_fails_closed_on_caption_conflict() -> None:
    conflicting = {
        **_case_dev_docket(),
        "caseName": "Different Plaintiff v. Different Defendant",
    }
    result = bridge_courtlistener_case_dev_documents(
        (_screened_case(),),
        client=_client(_search_response(conflicting)),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    assert result.selection_records == ()
    [exclusion] = result.exclusions
    assert exclusion["exclusion_reasons"] == ["case_dev_caption_conflict"]


def test_bridge_continues_after_bounded_case_dev_server_failure() -> None:
    failed = copy.deepcopy(_screened_case())
    failed_candidate = failed["candidate"]
    assert isinstance(failed_candidate, dict)
    failed_candidate["docket_id"] = "cl-failed"
    failed_candidate["candidate_key"] = "cl-failed"
    failed_metadata = failed_candidate["metadata"]
    assert isinstance(failed_metadata, dict)
    failed_metadata["case_id"] = "cl-failed"
    failed_metadata["docket_number"] = "1:26-cv-00000"
    server_failure = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": "1:26-cv-00000", "limit": 20},
        status_code=503,
        payload={"error": "temporary upstream failure"},
    )
    max_retries = 2
    transport = CaseDevFixtureTransport(
        (
            *((server_failure,) * (max_retries + 1)),
            _search_response(_case_dev_docket()),
            _lookup_response(),
        )
    )
    client = CaseDevClient(
        config=CaseDevConfig(api_key=None),
        transport=transport,
        max_retries=max_retries,
    )

    result = bridge_courtlistener_case_dev_documents(
        (failed, _screened_case()),
        client=client,
        use_embedded_entries=True,
        target_clean_cases=2,
    )

    assert [record["candidate_id"] for record in result.selection_records] == ["cl-123"]
    [exclusion] = result.exclusions
    assert exclusion["candidate_id"] == "cl-failed"
    assert exclusion["exclusion_reasons"] == ["case_dev_server_error_retries_exhausted"]
    assert client.request_count == max_retries + 3
    assert all(
        "live" not in params and "acknowledgePacerFees" not in params
        for _, _, params in transport.requests
    )


def test_bridge_fails_closed_on_restricted_core_document() -> None:
    lookup = _lookup_response()
    docket = lookup.payload["docket"]
    assert isinstance(docket, dict)
    entries = docket["entries"]
    assert isinstance(entries, list)
    motion = entries[1]
    assert isinstance(motion, dict)
    documents = motion["documents"]
    assert isinstance(documents, list)
    document = documents[0]
    assert isinstance(document, dict)
    document["isSealed"] = True
    result = bridge_courtlistener_case_dev_documents(
        (_screened_case(),),
        client=_client(_search_response(_case_dev_docket()), lookup),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    assert result.selection_records == ()
    [exclusion] = result.exclusions
    assert exclusion["exclusion_reasons"] == ["restricted_core_document"]


def test_bridge_fails_closed_on_textual_restriction_cue() -> None:
    lookup = _lookup_response()
    docket = lookup.payload["docket"]
    assert isinstance(docket, dict)
    entries = docket["entries"]
    assert isinstance(entries, list)
    motion = entries[1]
    assert isinstance(motion, dict)
    documents = motion["documents"]
    assert isinstance(documents, list)
    document = documents[0]
    assert isinstance(document, dict)
    document["description"] = "Motion memorandum filed under seal"

    result = bridge_courtlistener_case_dev_documents(
        (_screened_case(),),
        client=_client(_search_response(_case_dev_docket()), lookup),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    assert result.selection_records == ()
    [exclusion] = result.exclusions
    assert exclusion["exclusion_reasons"] == ["restricted_core_document"]


def test_bridge_prefers_pacer_main_motion_over_free_proposed_order() -> None:
    screened = _screened_case()
    entries = screened["selected_entries"]
    assert isinstance(entries, list)
    target = entries[1]
    assert isinstance(target, dict)
    documents = target["documents"]
    assert isinstance(documents, list)
    documents.append(
        {
            "kind": "Attachment 1",
            "description": "Text of Proposed Order",
            "href": "https://storage.courtlistener.com/proposed-order.pdf",
            "action_label": "Download PDF",
            "pacer_only": False,
        }
    )

    result = bridge_courtlistener_case_dev_documents(
        (screened,),
        client=_client(
            _search_response(_case_dev_docket()),
            _lookup_response(),
        ),
        use_embedded_entries=True,
        target_clean_cases=1,
    )

    [selection] = result.selection_records
    motion = selection["documents"][1]
    assert motion["source_document_id"] == "case-dev-mtd"
    assert motion["requires_paid_recovery"] is True
    assert [
        request.source_document_id for request in result.free_download_requests
    ] == [
        "case-dev-complaint",
        "case-dev-decision",
    ]


def test_public_first_bridge_routes_only_paid_gap_and_retains_free_ids() -> None:
    screened = _screened_case()
    public_plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    assert public_plan.selected_cases == ()
    [gap] = public_plan.paid_gap_cases
    gap_record = gap.to_record()
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"cl-123/courtlistener/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in public_plan.download_requests
    )

    paid_only_lookup = _lookup_response()
    paid_only_docket = paid_only_lookup.payload["docket"]
    assert isinstance(paid_only_docket, dict)
    paid_only_docket["entries"] = [
        _case_dev_entry(5, "Motion to Dismiss", "case-dev-mtd")
    ]
    result = bridge_public_plan_paid_gaps(
        (screened,),
        public_selection_records=(),
        paid_gap_records=(gap_record,),
        free_download_records=downloads,
        client=_client(_search_response(_case_dev_docket()), paid_only_lookup),
        use_embedded_entries=True,
    )

    assert result.exclusions == ()
    assert result.free_download_requests == ()
    [selection] = result.selection_records
    assert selection["planning_status"] == "selected_after_paid_recovery"
    assert [document["source_document_id"] for document in selection["documents"]] == [
        "entry-1-complaint",
        "entry-16-decision",
        "case-dev-mtd",
    ]
    [relevance] = result.case_relevance_records
    [core_filter] = filter_core_documents((relevance,))
    assert core_filter.purchase_document_ids == ("case-dev-mtd",)
    assert core_filter.exclusion_reasons == ()


def test_public_first_bridge_ledgers_exhausted_case_dev_server_failure() -> None:
    screened = _screened_case()
    public_plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = public_plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"cl-123/courtlistener/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in public_plan.download_requests
    )
    server_failure = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": "1:26-cv-00001", "limit": 20},
        status_code=503,
        payload={"error": "temporary upstream failure"},
    )
    max_retries = 2
    transport = CaseDevFixtureTransport((server_failure,) * (max_retries + 1))
    client = CaseDevClient(
        config=CaseDevConfig(api_key=None),
        transport=transport,
        max_retries=max_retries,
    )

    result = bridge_public_plan_paid_gaps(
        (screened,),
        public_selection_records=(),
        paid_gap_records=(gap.to_record(),),
        free_download_records=downloads,
        client=client,
        use_embedded_entries=True,
    )

    assert result.selection_records == ()
    [exclusion] = result.exclusions
    assert exclusion["candidate_id"] == "cl-123"
    assert exclusion["exclusion_reasons"] == ["case_dev_server_error_retries_exhausted"]
    assert client.request_count == max_retries + 1
    assert all(
        "live" not in params and "acknowledgePacerFees" not in params
        for _, _, params in transport.requests
    )


def test_public_first_bridge_emits_relevance_for_fully_free_and_paid_gap() -> None:
    free_screened = _screened_case()
    free_entries = free_screened["selected_entries"]
    assert isinstance(free_entries, list)
    motion = free_entries[1]
    assert isinstance(motion, dict)
    motion_documents = motion["documents"]
    assert isinstance(motion_documents, list)
    motion_document = motion_documents[0]
    assert isinstance(motion_document, dict)
    motion_document.update(
        {
            "description": "Memorandum in Support of Motion to Dismiss",
            "href": "https://storage.courtlistener.com/motion.pdf",
            "action_label": "Download PDF",
            "pacer_only": False,
        }
    )
    paid_screened = _screened_case()
    paid_candidate = paid_screened["candidate"]
    assert isinstance(paid_candidate, dict)
    paid_candidate["docket_id"] = "cl-456"
    paid_candidate["candidate_key"] = "cl-456"

    free_plan = plan_public_packet_downloads(
        (free_screened,), use_embedded_entries=True, target_clean_cases=1
    )
    paid_plan = plan_public_packet_downloads(
        (paid_screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [public_selection] = free_plan.selected_cases
    [paid_gap] = paid_plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"{request.candidate_id}/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in (*free_plan.download_requests, *paid_plan.download_requests)
    )
    result = bridge_public_plan_paid_gaps(
        (free_screened, paid_screened),
        public_selection_records=(public_selection.to_record(),),
        paid_gap_records=(paid_gap.to_record(),),
        free_download_records=downloads,
        client=_client(_search_response(_case_dev_docket()), _lookup_response()),
        use_embedded_entries=True,
    )

    assert {record["candidate_id"] for record in result.selection_records} == {
        "cl-123",
        "cl-456",
    }
    assert {record["candidate_id"] for record in result.case_relevance_records} == {
        "cl-123",
        "cl-456",
    }
    filters = {
        record.candidate_id: record
        for record in filter_core_documents(result.case_relevance_records)
    }
    assert filters["cl-123"].purchase_document_ids == ()
    assert filters["cl-123"].exclusion_reasons == ()
    assert filters["cl-456"].purchase_document_ids == ("case-dev-mtd",)
    assert filters["cl-456"].exclusion_reasons == ()


def test_public_first_bridge_recovers_only_target_linked_opposition() -> None:
    screened = _screened_case()
    entries = screened["selected_entries"]
    assert isinstance(entries, list)
    entries.insert(
        0,
        _courtlistener_entry(
            3,
            "OPPOSITION to an unrelated motion.",
            "Opposition to unrelated motion",
            "https://ecf.nysd.uscourts.gov/doc1/unrelated",
            pacer_only=True,
        ),
    )
    entries.insert(
        3,
        _courtlistener_entry(
            8,
            "OPPOSITION to Motion to Dismiss at Docket 5.",
            "Opposition to Motion to Dismiss",
            "https://ecf.nysd.uscourts.gov/doc1/opposition",
            pacer_only=True,
        ),
    )
    public_plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = public_plan.paid_gap_cases
    assert "no_free_opposition" in gap.paid_gap_reasons
    lookup = _lookup_response()
    docket = lookup.payload["docket"]
    assert isinstance(docket, dict)
    docket["entries"] = [
        _case_dev_entry(3, "Opposition to unrelated motion", "case-dev-unrelated"),
        _case_dev_entry(5, "Memorandum in Support", "case-dev-mtd"),
        _case_dev_entry(8, "Opposition to Motion to Dismiss", "case-dev-opposition"),
    ]
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"cl-123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in public_plan.download_requests
    )

    result = bridge_public_plan_paid_gaps(
        (screened,),
        public_selection_records=(),
        paid_gap_records=(gap.to_record(),),
        free_download_records=downloads,
        client=_client(_search_response(_case_dev_docket()), lookup),
        use_embedded_entries=True,
    )

    assert result.exclusions == ()
    [relevance] = result.case_relevance_records
    paid_ids = {
        document["source_document_id"]
        for document in relevance["documents"]
        if document["requires_paid_recovery"] is True
    }
    assert paid_ids == {"case-dev-mtd", "case-dev-opposition"}


def test_public_first_bridge_requires_completed_free_manifest() -> None:
    screened = _screened_case()
    public_plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    gap_record = public_plan.paid_gap_cases[0].to_record()

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="free_download_manifest_incomplete",
    ):
        bridge_public_plan_paid_gaps(
            (screened,),
            public_selection_records=(),
            paid_gap_records=(gap_record,),
            free_download_records=(),
            client=_client(),
            use_embedded_entries=True,
        )


def test_manifest_merge_rejects_conflicting_candidate_document_keys() -> None:
    free = {
        "candidate_id": "cl-123",
        "source_document_id": "doc-1",
        "local_path": "cl-123/courtlistener/doc-1.pdf",
        "sha256": "1" * 64,
    }
    purchased = {
        **free,
        "local_path": "cl-123/case-dev-pacer/doc-1.pdf",
        "sha256": "2" * 64,
    }

    assert merge_download_manifest_records(((free,), (free,))) == (free,)
    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="download_manifest_conflict",
    ):
        merge_download_manifest_records(((free,), (purchased,)))


def _client(*responses: RecordedCaseDevResponse) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None),
        transport=CaseDevFixtureTransport(responses),
    )


def _search_response(*dockets: dict[str, object]) -> RecordedCaseDevResponse:
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": "1:26-cv-00001", "limit": 20},
        status_code=200,
        payload={"dockets": list(dockets)},
    )


def _lookup_response() -> RecordedCaseDevResponse:
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "lookup",
            "docketId": "case-dev-777",
            "includeEntries": True,
            "limit": 500,
        },
        status_code=200,
        payload={
            "docket": {
                **_case_dev_docket(),
                "entries": [
                    _case_dev_entry(1, "Complaint", "case-dev-complaint"),
                    _case_dev_entry(5, "Motion to Dismiss", "case-dev-mtd"),
                    _case_dev_entry(
                        16,
                        "Order on Motion to Dismiss",
                        "case-dev-decision",
                    ),
                ],
            }
        },
    )


def _case_dev_docket() -> dict[str, object]:
    return {
        "id": "case-dev-777",
        "courtId": "nysd",
        "docketNumber": "1:26-cv-00001",
        "caseName": "Fixture v. Example",
    }


def _case_dev_entry(
    entry_number: int,
    description: str,
    document_id: str,
) -> dict[str, object]:
    return {
        "id": f"case-dev-entry-{entry_number}",
        "entryNumber": entry_number,
        "date": "2026-01-01",
        "description": description,
        "documents": [
            {
                "id": document_id,
                "description": description,
                "type": "main_document",
            }
        ],
    }


def _screened_case() -> dict[str, object]:
    return {
        "nature_of_suit": "440 Civil Rights",
        "nos_macro_category": "civil_rights",
        "mdl_family_id": "mdl-999",
        "candidate": {
            "docket_id": "cl-123",
            "candidate_key": "cl-123",
            "metadata": {
                "case_id": "cl-123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
                "related_family_id": "family-1",
            },
            "url": "https://www.courtlistener.com/docket/cl-123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _courtlistener_entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _courtlistener_entry(
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _courtlistener_entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _courtlistener_entry(
    entry_number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{entry_number}",
        "entry_number": str(entry_number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }
