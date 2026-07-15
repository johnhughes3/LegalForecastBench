from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_recap_enrichment import (
    CaseDevRecapEnrichmentError,
    enrich_recap_docket_with_case_dev,
    rank_case_dev_recap_enrichments,
)
from legalforecast.ingestion.firecrawl_recap_discovery import RecapDiscoveredDocket


def test_enrichment_exhausts_free_entry_pages_and_keeps_availability_distinct() -> None:
    client, transport = _client(
        _lookup(
            entries=(
                _entry(
                    "entry-1",
                    1,
                    "Complaint",
                    _document(
                        "doc-1",
                        pdf_url="https://storage.courtlistener.com/complaint.pdf",
                        is_available=True,
                    ),
                ),
                _entry(
                    "entry-5",
                    5,
                    "Motion to Dismiss",
                    _document(
                        "doc-5",
                        pdf_url="https://storage.courtlistener.com/mtd.pdf",
                        is_available=False,
                    ),
                ),
            ),
            next_offset=2,
            limit=3,
        ),
        _lookup(
            entries=(
                _entry(
                    "entry-8",
                    8,
                    "Opposition to Motion to Dismiss",
                    _document(
                        "doc-8",
                        pdf_url="https://storage.courtlistener.com/opposition.pdf",
                        is_available=True,
                    ),
                ),
                _entry(
                    "entry-10",
                    10,
                    "Order denying Motion to Dismiss",
                    _document("doc-10", pdf_url=None, is_available=True),
                ),
            ),
            cursor="2",
            limit=3,
        ),
    )

    enriched = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery(),
        page_size=3,
        max_pages=4,
    )

    assert enriched.courtlistener_docket_id == "101"
    assert enriched.case_dev_id == "101"
    assert enriched.case_dev_url == (
        "https://www.courtlistener.com/api/rest/v4/dockets/101/"
    )
    assert enriched.pages_fetched == 2
    assert enriched.required_document_count == 4
    assert enriched.actual_free_required_document_count == 2
    assert enriched.missing_required_document_count == 2
    by_id = {document.document_id: document for document in enriched.documents}
    assert by_id["doc-1"].pdf_url_present is True
    assert by_id["doc-1"].is_available is True
    assert by_id["doc-1"].actually_free is True
    assert by_id["doc-5"].pdf_url_present is True
    assert by_id["doc-5"].is_available is False
    assert by_id["doc-5"].actually_free is False
    assert by_id["doc-10"].pdf_url_present is False
    assert by_id["doc-10"].is_available is True
    assert by_id["doc-10"].actually_free is False
    assert [request[2] for request in transport.requests] == [
        {
            "type": "lookup",
            "docketId": "101",
            "includeEntries": True,
            "limit": 3,
        },
        {
            "type": "lookup",
            "docketId": "101",
            "includeEntries": True,
            "offset": 2,
            "limit": 3,
        },
    ]
    assert all(
        "live" not in params and "acknowledgePacerFees" not in params
        for _method, _path, params in transport.requests
    )


def test_pdf_url_without_boolean_availability_fails_closed_as_missing() -> None:
    client, _transport = _client(
        _lookup(
            entries=(
                _entry(
                    "entry-1",
                    1,
                    "Complaint",
                    _document(
                        "doc-1",
                        pdf_url="https://storage.courtlistener.com/complaint.pdf",
                    ),
                ),
            ),
            limit=5,
        )
    )

    enriched = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery(),
        page_size=5,
    )

    [document] = enriched.documents
    assert document.pdf_url_present is True
    assert document.is_available is None
    assert document.actually_free is False
    assert document.availability_reason == "availability_unknown"
    assert enriched.missing_required_document_count == 3


def test_multiple_documents_without_unique_main_are_not_assumed_free() -> None:
    client, _transport = _client(
        _lookup(
            entries=(
                _entry(
                    "entry-5",
                    5,
                    "Motion to Dismiss",
                    _document(
                        "doc-5-a",
                        pdf_url="https://storage.courtlistener.com/a.pdf",
                        is_available=True,
                        kind="attachment",
                    ),
                    _document(
                        "doc-5-b",
                        pdf_url="https://storage.courtlistener.com/b.pdf",
                        is_available=True,
                        kind="attachment",
                    ),
                ),
            ),
            limit=5,
        )
    )

    enriched = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery(),
        page_size=5,
    )

    motion_slot = next(slot for slot in enriched.required_documents if slot.entry_id)
    assert motion_slot.selected_document_id is None
    assert motion_slot.satisfied is False
    assert motion_slot.missing_reason == "main_document_ambiguous"


def test_entry_restriction_overrides_available_pdf_evidence() -> None:
    restricted_entry = _entry(
        "entry-1",
        1,
        "Complaint",
        _document(
            "doc-1",
            pdf_url="https://storage.courtlistener.com/complaint.pdf",
            is_available=True,
        ),
    )
    restricted_entry["isSealed"] = True
    client, _transport = _client(_lookup(entries=(restricted_entry,), limit=5))

    enriched = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery(),
        page_size=5,
    )

    [document] = enriched.documents
    assert document.pdf_url_present is True
    assert document.is_available is True
    assert document.actually_free is False
    assert document.availability_reason == "restricted"


def test_missing_mandatory_roles_each_add_one_missing_slot() -> None:
    client, _transport = _client(_lookup(entries=(), limit=5))

    enriched = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery(),
        page_size=5,
    )

    assert enriched.required_document_count == 3
    assert enriched.missing_required_document_count == 3
    assert [slot.requirement for slot in enriched.required_documents] == [
        "operative_complaint",
        "motion_to_dismiss",
        "decision",
    ]


def test_ranking_uses_missing_required_count_then_stable_docket_identity() -> None:
    cheap_client, _transport = _client(
        _lookup(
            docket_id="102",
            entries=(
                _entry(
                    "entry-1",
                    1,
                    "Complaint",
                    _document(
                        "doc-1",
                        pdf_url="https://storage.courtlistener.com/complaint.pdf",
                        is_available=True,
                    ),
                ),
            ),
            limit=5,
        )
    )
    costly_client, _transport = _client(_lookup(entries=(), limit=5))
    cheap = enrich_recap_docket_with_case_dev(
        client=cheap_client,
        discovery=_discovery("102"),
        page_size=5,
    )
    costly = enrich_recap_docket_with_case_dev(
        client=costly_client,
        discovery=_discovery("101"),
        page_size=5,
    )

    ranked = rank_case_dev_recap_enrichments((costly, cheap))

    assert [item.courtlistener_docket_id for item in ranked] == ["102", "101"]
    assert ranked[0].missing_required_document_count == 2
    assert ranked[1].missing_required_document_count == 3


def test_ranking_prioritizes_explicit_district_12c_over_cheaper_bankruptcy() -> None:
    district_client, _ = _client(
        _lookup(
            docket_id="201",
            court_id="nysd",
            docket_number="1:26-cv-00001",
            entries=(
                _entry(
                    "entry-9",
                    9,
                    "Memorandum and Order denying Rule 12(c) judgment on the pleadings",
                    _document("district-decision"),
                ),
            ),
            limit=5,
        )
    )
    bankruptcy_client, _ = _client(
        _lookup(
            docket_id="202",
            court_id="nysb",
            docket_number="1:26-bk-00001",
            entries=tuple(
                _entry(
                    f"entry-{number}",
                    number,
                    description,
                    _document(
                        f"free-{number}",
                        pdf_url=f"https://storage.courtlistener.com/{number}.pdf",
                        is_available=True,
                    ),
                )
                for number, description in (
                    (1, "Complaint"),
                    (2, "Motion to Dismiss"),
                    (3, "Order granting Motion to Dismiss"),
                )
            ),
            limit=5,
        )
    )
    district = enrich_recap_docket_with_case_dev(
        client=district_client, discovery=_discovery("201"), page_size=5
    )
    bankruptcy = enrich_recap_docket_with_case_dev(
        client=bankruptcy_client, discovery=_discovery("202"), page_size=5
    )

    ranked = rank_case_dev_recap_enrichments((bankruptcy, district))

    assert [item.courtlistener_docket_id for item in ranked] == ["201", "202"]
    assert district.structural_priority == (0, "federal_civil_district_metadata")
    assert district.decision_signal_priority == (
        0,
        "explicit_mtd_or_12c_disposition",
    )
    assert bankruptcy.missing_required_document_count == 0
    assert bankruptcy.structural_priority == (
        2,
        "hard_structural_exclusion_metadata",
    )


def test_ranking_prioritizes_linked_post_anchor_merits_disposition() -> None:
    valid_client, _ = _client(
        _lookup(
            docket_id="401",
            court_id="nysd",
            docket_number="1:26-cv-00401",
            entries=(
                _entry("entry-1", 1, "Complaint", filed_at="2026-06-01"),
                _entry(
                    "entry-2",
                    2,
                    "Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-10",
                ),
                _entry(
                    "entry-3",
                    3,
                    "Order granting Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-07-02",
                ),
            ),
            limit=10,
        )
    )
    unlinked_client, _ = _client(
        _lookup(
            docket_id="402",
            court_id="nysd",
            docket_number="1:26-cv-00402",
            entries=(
                _entry("entry-1", 1, "Complaint", filed_at="2026-06-01"),
                _entry(
                    "entry-3",
                    3,
                    "Order granting Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-07-02",
                ),
            ),
            limit=10,
        )
    )
    pre_anchor_client, _ = _client(
        _lookup(
            docket_id="403",
            court_id="nysd",
            docket_number="1:26-cv-00403",
            entries=(
                _entry(
                    "entry-2",
                    2,
                    "Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-10",
                ),
                _entry(
                    "entry-3",
                    3,
                    "Order denying Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-29",
                ),
            ),
            limit=10,
        )
    )
    procedural_client, _ = _client(
        _lookup(
            docket_id="404",
            court_id="nysd",
            docket_number="1:26-cv-00404",
            entries=(
                _entry(
                    "entry-2",
                    2,
                    "Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-10",
                ),
                _entry(
                    "entry-3",
                    3,
                    "Order governing Motions to Dismiss and setting briefing",
                    filed_at="2026-07-02",
                ),
            ),
            limit=10,
        )
    )
    anchor = date(2026, 6, 30)
    valid = enrich_recap_docket_with_case_dev(
        client=valid_client,
        discovery=_discovery("401"),
        page_size=10,
        eligibility_anchor=anchor,
    )
    unlinked = enrich_recap_docket_with_case_dev(
        client=unlinked_client,
        discovery=_discovery("402"),
        page_size=10,
        eligibility_anchor=anchor,
    )
    pre_anchor = enrich_recap_docket_with_case_dev(
        client=pre_anchor_client,
        discovery=_discovery("403"),
        page_size=10,
        eligibility_anchor=anchor,
    )
    procedural = enrich_recap_docket_with_case_dev(
        client=procedural_client,
        discovery=_discovery("404"),
        page_size=10,
        eligibility_anchor=anchor,
    )

    assert valid.eligibility_priority == (
        0,
        "strict_post_anchor_mtd_with_observed_target_motion",
    )
    assert unlinked.eligibility_priority == (
        1,
        "strict_post_anchor_mtd_target_motion_unproven",
    )
    assert pre_anchor.eligibility_priority == (
        4,
        "first_written_mtd_disposition_before_anchor",
    )
    assert procedural.eligibility_priority == (
        5,
        "procedural_or_standing_order",
    )
    assert [
        item.courtlistener_docket_id
        for item in rank_case_dev_recap_enrichments(
            (procedural, pre_anchor, unlinked, valid)
        )
    ] == ["401", "402", "403", "404"]
    record = valid.to_record()
    assert record["eligibility_anchor"] == "2026-06-30"
    assert record["eligibility_priority_tier"] == 0
    assert record["entries"][2]["filed_at"] == "2026-07-02"
    assert record["eligibility_screen"]["status"] == (
        "accepted_strict_civil_mtd_decision"
    )


def test_rule_12c_merits_motion_remains_top_eligibility_tier() -> None:
    client, _ = _client(
        _lookup(
            docket_id="405",
            court_id="nysd",
            docket_number="1:26-cv-00405",
            entries=(
                _entry(
                    "entry-2",
                    2,
                    "Motion for judgment on the pleadings under Rule 12(c)",
                    filed_at="2026-06-10",
                ),
                _entry(
                    "entry-3",
                    3,
                    "Memorandum and Order granting Defendant's Rule 12(c) "
                    "Motion for Judgment on the Pleadings",
                    filed_at="2026-07-03",
                ),
            ),
            limit=10,
        )
    )

    enrichment = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery("405"),
        page_size=10,
        eligibility_anchor=date(2026, 6, 30),
    )

    assert enrichment.eligibility_priority == (
        0,
        "strict_post_anchor_mtd_with_observed_target_motion",
    )


def test_moot_disposition_is_retained_but_demoted_for_scheduling() -> None:
    client, _ = _client(
        _lookup(
            docket_id="406",
            court_id="nysd",
            docket_number="1:26-cv-00406",
            entries=(
                _entry(
                    "entry-2",
                    2,
                    "Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-10",
                ),
                _entry(
                    "entry-3",
                    3,
                    "Order denying Motion to Dismiss as moot",
                    filed_at="2026-07-03",
                ),
            ),
            limit=10,
        )
    )

    enrichment = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery("406"),
        page_size=10,
        eligibility_anchor=date(2026, 6, 30),
    )

    assert enrichment.eligibility_screen.anchor_disposition_entries
    assert enrichment.eligibility_priority == (
        3,
        "post_anchor_non_merits_or_moot_disposition",
    )
    assert enrichment.decision_signal_priority == (
        2,
        "post_anchor_non_merits_or_moot_disposition",
    )


def test_missing_disposition_date_is_unknown_not_top_ranked() -> None:
    decision = _entry(
        "entry-3",
        3,
        "Order granting Motion to Dismiss under Rule 12(b)(6)",
    )
    decision.pop("date")
    client, _ = _client(
        _lookup(
            docket_id="407",
            court_id="nysd",
            docket_number="1:26-cv-00407",
            entries=(
                _entry(
                    "entry-2",
                    2,
                    "Motion to Dismiss under Rule 12(b)(6)",
                    filed_at="2026-06-10",
                ),
                decision,
            ),
            limit=10,
        )
    )

    enrichment = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery("407"),
        page_size=10,
        eligibility_anchor=date(2026, 6, 30),
    )

    assert enrichment.eligibility_priority == (
        2,
        "first_written_mtd_disposition_date_unproven",
    )


def test_ranking_retains_bankruptcy_adversary_with_local_docket_number() -> None:
    client, _ = _client(
        _lookup(
            docket_id="203",
            court_id="nysb",
            docket_number="26-01028",
            case_name="Higgins v. Celsius Network LLC",
            entries=(),
            limit=5,
        )
    )

    enrichment = enrich_recap_docket_with_case_dev(
        client=client,
        discovery=_discovery("203"),
        page_size=5,
    )

    assert enrichment.structural_priority == (
        0,
        "bankruptcy_adversary_metadata",
    )


def test_unknown_metadata_is_retained_ahead_of_hard_structural_exclusion() -> None:
    unknown_client, _ = _client(_lookup(docket_id="301", entries=(), limit=5))
    bankruptcy_client, _ = _client(
        _lookup(
            docket_id="302",
            court_id="nysb",
            docket_number="1:26-bk-00001",
            entries=(),
            limit=5,
        )
    )
    unknown = enrich_recap_docket_with_case_dev(
        client=unknown_client, discovery=_discovery("301"), page_size=5
    )
    bankruptcy = enrich_recap_docket_with_case_dev(
        client=bankruptcy_client, discovery=_discovery("302"), page_size=5
    )

    forward = rank_case_dev_recap_enrichments((bankruptcy, unknown))
    reverse = rank_case_dev_recap_enrichments((unknown, bankruptcy))

    assert [item.courtlistener_docket_id for item in forward] == ["301", "302"]
    assert forward == reverse
    assert unknown.structural_priority == (1, "metadata_incomplete_or_unknown")


def test_case_dev_id_must_match_discovered_courtlistener_docket() -> None:
    client, _transport = _client(
        _lookup(
            docket_id="999",
            requested_docket_id="101",
            entries=(),
            limit=5,
        )
    )

    with pytest.raises(CaseDevRecapEnrichmentError, match="case_dev_id_mismatch"):
        enrich_recap_docket_with_case_dev(
            client=client,
            discovery=_discovery(),
            page_size=5,
        )


def test_case_dev_url_must_match_discovered_courtlistener_docket() -> None:
    client, _transport = _client(
        _lookup(docket_id="101", url_docket_id="999", entries=(), limit=5)
    )

    with pytest.raises(CaseDevRecapEnrichmentError, match="case_dev_url_mismatch"):
        enrich_recap_docket_with_case_dev(
            client=client,
            discovery=_discovery(),
            page_size=5,
        )


def test_full_page_without_continuation_is_not_treated_as_exhausted() -> None:
    client, _transport = _client(
        _lookup(
            entries=(
                _entry("entry-1", 1, "Complaint"),
                _entry("entry-2", 2, "Notice"),
            ),
            limit=2,
        )
    )

    with pytest.raises(CaseDevRecapEnrichmentError, match="exhaustion_unproven"):
        enrich_recap_docket_with_case_dev(
            client=client,
            discovery=_discovery(),
            page_size=2,
        )


def test_repeated_continuation_fails_closed() -> None:
    client, _transport = _client(
        _lookup(entries=(), next_offset=2, limit=5),
        _lookup(entries=(), next_offset=2, cursor="2", limit=5),
    )

    with pytest.raises(CaseDevRecapEnrichmentError, match="continuation_cycle"):
        enrich_recap_docket_with_case_dev(
            client=client,
            discovery=_discovery(),
            page_size=5,
        )


def test_page_cap_fails_instead_of_returning_partial_inventory() -> None:
    client, _transport = _client(
        _lookup(entries=(), next_offset=2, limit=5),
    )

    with pytest.raises(CaseDevRecapEnrichmentError, match="page_limit"):
        enrich_recap_docket_with_case_dev(
            client=client,
            discovery=_discovery(),
            page_size=5,
            max_pages=1,
        )


def _client(
    *responses: RecordedCaseDevResponse,
) -> tuple[CaseDevClient, CaseDevFixtureTransport]:
    transport = CaseDevFixtureTransport(responses)
    return CaseDevClient(
        config=CaseDevConfig(api_key=None), transport=transport
    ), transport


def test_enrichment_merges_repeated_entry_rows_with_distinct_documents() -> None:
    client, _ = _client(
        _lookup(
            entries=(
                _entry("entry-1", 1, "Complaint", _document("doc-1")),
                _entry("entry-1", 1, "Complaint", _document("doc-2")),
            ),
            limit=100,
        )
    )

    enriched = enrich_recap_docket_with_case_dev(
        client=client, discovery=_discovery(), page_size=100, max_pages=2
    )

    assert enriched.docket_entry_count == 1
    assert {document.document_id for document in enriched.documents} == {
        "doc-1",
        "doc-2",
    }


def test_enrichment_rejects_repeated_entry_rows_with_semantic_conflict() -> None:
    conflicting = _entry("entry-1", 2, "Complaint", _document("doc-2"))
    client, _ = _client(
        _lookup(
            entries=(
                _entry("entry-1", 1, "Complaint", _document("doc-1")),
                conflicting,
            ),
            limit=100,
        )
    )

    with pytest.raises(
        CaseDevRecapEnrichmentError,
        match="case_dev_duplicate_entry_irreconcilable",
    ):
        enrich_recap_docket_with_case_dev(
            client=client, discovery=_discovery(), page_size=100, max_pages=2
        )


def test_enrichment_preserves_distinct_same_number_rows_without_provider_ids() -> None:
    first = _entry("unused", 7, "First event", _document("doc-7"))
    second = _entry("unused", 7, "Second event", _document("doc-8"))
    first.pop("id")
    second.pop("id")
    client, _ = _client(_lookup(entries=(first, second), limit=100))

    enriched = enrich_recap_docket_with_case_dev(
        client=client, discovery=_discovery(), page_size=100, max_pages=2
    )

    assert enriched.docket_entry_count == 2
    assert len({document.docket_entry_id for document in enriched.documents}) == 2
    assert {document.document_id for document in enriched.documents} == {
        "doc-7",
        "doc-8",
    }


def test_enrichment_merges_same_no_id_event_repeated_per_document() -> None:
    first = _entry("unused", 7, "Same event", _document("doc-7"))
    second = _entry("unused", 7, "Same event", _document("doc-8"))
    first.pop("id")
    second.pop("id")
    client, _ = _client(_lookup(entries=(first, second), limit=100))

    enriched = enrich_recap_docket_with_case_dev(
        client=client, discovery=_discovery(), page_size=100, max_pages=2
    )

    assert enriched.docket_entry_count == 1
    assert {document.document_id for document in enriched.documents} == {
        "doc-7",
        "doc-8",
    }


def test_enrichment_merges_document_fallback_text_for_explicit_entry_id() -> None:
    first = _entry("entry-7", 7, "unused", _document("doc-7"))
    second = _entry("entry-7", 7, "unused", _document("doc-8"))
    first["description"] = None
    second["description"] = None
    client, _ = _client(_lookup(entries=(first, second), limit=100))

    enriched = enrich_recap_docket_with_case_dev(
        client=client, discovery=_discovery(), page_size=100, max_pages=2
    )

    assert enriched.docket_entry_count == 1
    assert {document.document_id for document in enriched.documents} == {
        "doc-7",
        "doc-8",
    }


def _discovery(docket_id: str = "101") -> RecapDiscoveredDocket:
    return RecapDiscoveredDocket(
        docket_id=docket_id,
        docket_url=(
            f"https://www.courtlistener.com/docket/{docket_id}/fixture-v-example/"
        ),
        entry_keys=(f"{docket_id}:10",),
        matched_terms=("motion to dismiss",),
    )


def _lookup(
    *,
    entries: tuple[dict[str, object], ...],
    limit: int,
    docket_id: str = "101",
    requested_docket_id: str | None = None,
    url_docket_id: str | None = None,
    cursor: str | None = None,
    next_offset: int | None = None,
    court_id: str | None = None,
    docket_number: str | None = None,
    case_name: str | None = None,
) -> RecordedCaseDevResponse:
    params: dict[str, object] = {
        "type": "lookup",
        "docketId": requested_docket_id or docket_id,
        "includeEntries": True,
        "limit": limit,
    }
    if cursor is not None:
        params["offset"] = int(cursor)
    docket: dict[str, object] = {
        "id": docket_id,
        "url": (
            "https://www.courtlistener.com/api/rest/v4/dockets/"
            f"{url_docket_id or docket_id}/"
        ),
        "entries": list(entries),
    }
    if court_id is not None:
        docket["courtId"] = court_id
    if docket_number is not None:
        docket["docketNumber"] = docket_number
    if case_name is not None:
        docket["caseName"] = case_name
    payload: dict[str, object] = {"docket": docket}
    if next_offset is not None:
        payload["nextOffset"] = next_offset
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params=params,
        status_code=200,
        payload=payload,
    )


def _entry(
    entry_id: str,
    entry_number: int,
    description: str,
    *documents: dict[str, object],
    filed_at: str = date(2026, 7, 1).isoformat(),
) -> dict[str, object]:
    return {
        "id": entry_id,
        "entryNumber": entry_number,
        "date": filed_at,
        "description": description,
        "documents": list(documents),
    }


def _document(
    document_id: str,
    *,
    pdf_url: str | None = None,
    is_available: bool | None = None,
    kind: str = "main_document",
) -> dict[str, object]:
    record: dict[str, object] = {
        "id": document_id,
        "description": document_id,
        "type": kind,
    }
    if pdf_url is not None:
        record["pdfUrl"] = pdf_url
    if is_available is not None:
        record["isAvailable"] = is_available
    return record
