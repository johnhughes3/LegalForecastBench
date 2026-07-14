"""Tests for decision-first RECAP API discovery and docket reconstruction."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    CourtListenerRateLimitError,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    TermTerminalStatus,
    materialize_independent_term_sets,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    MtdDocketScreenStatus,
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.recap_api_discovery import (
    DECISION_FIRST_RECAP_API_SEARCH_TERMS,
    PRESCREEN_BANKRUPTCY_REASON,
    PRESCREEN_CRIMINAL_REASON,
    RECAP_API_PROVIDER,
    REST_DOCKET_ENTRY_SOFT_CAP,
    REST_DOCKET_PAGE_HARD_CAP,
    RecapApiDiscoverySource,
    RecapApiResponseError,
    RecapDecisionHit,
    RecapDocketContradictionError,
    RecapDocketReconstructionError,
    RecapDocketTooLargeError,
    RecapReconstructionAuthError,
    RequestPacer,
    build_recap_api_batch_config,
    candidate_docket_id,
    observe_prescreened_reason,
    observe_recap_api_candidate,
    pacer_for_client,
    prescreen_recap_candidate,
    reconstruct_docket_page,
    resolve_auth_mode,
)


def _response(
    *,
    path: str,
    params: dict[str, Any] | None = None,
    status_code: int = 200,
    payload: dict[str, Any] | None = None,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path=path,
        params=params or {},
        status_code=status_code,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Frozen vocabulary and batch config.
# ---------------------------------------------------------------------------


def test_decision_first_terms_are_frozen_and_ordered() -> None:
    assert DECISION_FIRST_RECAP_API_SEARCH_TERMS == (
        'order AND granting AND "motion to dismiss"',
        'order AND denying AND "motion to dismiss"',
        '"motion to dismiss" AND "granted in part"',
        '"order on motion to dismiss"',
        '"memorandum opinion" AND "motion to dismiss"',
        '"report and recommendation" AND "motion to dismiss"',
        'order AND (granting OR denying) AND "judgment on the pleadings"',
        'order AND (granting OR denying) AND "12(b)(6)"',
    )
    assert len(set(DECISION_FIRST_RECAP_API_SEARCH_TERMS)) == 8


def test_batch_config_is_stable_and_uses_frozen_terms() -> None:
    config = build_recap_api_batch_config(
        decision_window_start=date(2026, 6, 30),
        decision_window_end=date(2026, 7, 12),
        auth_mode="anonymous",
    )
    assert config["provider"] == RECAP_API_PROVIDER
    assert config["query_terms"] == list(DECISION_FIRST_RECAP_API_SEARCH_TERMS)
    assert config["decision_window_start"] == "2026-06-30"
    assert config["query_term_order_is_frozen"] is True
    assert config["order_by"] == "entry_date_filed desc"


def test_batch_config_digest_differs_from_batch_001(tmp_path: Path) -> None:
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        batch_001 = {
            "provider": "courtlistener-recap-web-via-firecrawl",
            "query_terms": ["motion to dismiss"],
        }
        digest_001 = store.ensure_batch("batch-001", batch_001)
        digest_002 = store.ensure_batch(
            "batch-002",
            build_recap_api_batch_config(
                decision_window_start=date(2026, 6, 30),
                decision_window_end=date(2026, 7, 12),
                auth_mode="anonymous",
            ),
        )
        assert digest_001 != digest_002


def test_batch_config_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match="on or before"):
        build_recap_api_batch_config(
            decision_window_start=date(2026, 7, 12),
            decision_window_end=date(2026, 6, 30),
            auth_mode="anonymous",
        )


# ---------------------------------------------------------------------------
# Cheap pre-screen.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("court_id", "docket_number", "case_name", "expected"),
    [
        ("nysb", "1:26-bk-00001", "In re Debtor", PRESCREEN_BANKRUPTCY_REASON),
        ("nysb", "1:26-ap-00001", "Trustee v. Roe", None),
        ("nysb", None, None, None),
        ("cacd", "2:26-cr-00123", "United States v. Roe", PRESCREEN_CRIMINAL_REASON),
        ("nysd", "1:26-cv-00001", "United States v. Roe", PRESCREEN_CRIMINAL_REASON),
        ("nysd", "1:26-cv-00001", "USA v. Roe", PRESCREEN_CRIMINAL_REASON),
        ("nysd", "1:26-cv-00001", "Acme Corp v. Roe", None),
        (None, None, None, None),
    ],
)
def test_prescreen_reasons(
    court_id: str | None,
    docket_number: str | None,
    case_name: str | None,
    expected: str | None,
) -> None:
    assert (
        prescreen_recap_candidate(
            court_id=court_id, docket_number=docket_number, case_name=case_name
        )
        == expected
    )


# ---------------------------------------------------------------------------
# Discovery hit parsing and payload evidence.
# ---------------------------------------------------------------------------


def test_hit_from_record_extracts_decision_evidence() -> None:
    hit = RecapDecisionHit.from_record(
        {
            "id": 9001,
            "docket_id": 555,
            "docket_entry_id": 7001,
            "entry_number": 42,
            "document_number": 40,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
            "absolute_url": "/docket/555/acme-corp-v-roe/",
        }
    )
    assert hit.candidate_id == "courtlistener-docket-555"
    payload = hit.candidate_payload(query_term="q", auth_mode="anonymous")
    assert payload["prescreen_exclusion_reason"] is None
    evidence = payload["decision_entry_evidence"]
    assert evidence["docket_entry_id"] == "7001"
    assert evidence["entry_date_filed"] == "2026-07-05"
    assert evidence["description"] == "ORDER granting motion to dismiss"


def test_hit_from_record_requires_docket_and_document_id() -> None:
    with pytest.raises(RecapApiResponseError, match="docket_id"):
        RecapDecisionHit.from_record({"id": 1})
    with pytest.raises(RecapApiResponseError, match="missing id"):
        RecapDecisionHit.from_record({"docket_id": 7})


def _search_source(
    responses: tuple[RecordedCourtListenerResponse, ...],
) -> RecapApiDiscoverySource:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(responses),
    )
    return RecapApiDiscoverySource(
        client=client,
        entry_date_filed_after=date(2026, 6, 30),
        auth_mode="anonymous",
    )


def test_fetch_page_parses_hits_and_exhaustion() -> None:
    source = _search_source(
        (
            _response(
                path="/search/",
                params={
                    "type": "rd",
                    "description": "order AND granting",
                    "entry_date_filed_after": "2026-06-30",
                    "order_by": "entry_date_filed desc",
                    "page_size": 100,
                },
                payload={
                    "results": [
                        {
                            "id": 9001,
                            "docket_id": 555,
                            "description": "ORDER granting motion to dismiss",
                            "entry_date_filed": "2026-07-05",
                            "court_id": "nysd",
                            "docketNumber": "1:26-cv-00001",
                            "caseName": "Acme Corp v. Roe",
                        },
                        {
                            "id": 9002,
                            "docket_id": 555,
                            "description": "Second doc same docket",
                            "entry_date_filed": "2026-07-05",
                            "court_id": "nysd",
                            "docketNumber": "1:26-cv-00001",
                            "caseName": "Acme Corp v. Roe",
                        },
                    ],
                    "next": None,
                },
            ),
        )
    )
    page = source.fetch_page(term="order AND granting", cursor=None, page_size=100)
    assert page.next_cursor is None
    assert page.exhausted is True
    assert {hit.candidate_id for hit in page.hits} == {"courtlistener-docket-555"}
    assert {hit.provider_hit_id for hit in page.hits} == {"9001", "9002"}


def test_scheduler_dedupes_hits_to_docket_candidates(tmp_path: Path) -> None:
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle({"schema_version": "test"})
        store.ensure_batch(
            "batch-002",
            build_recap_api_batch_config(
                decision_window_start=date(2026, 6, 30),
                decision_window_end=date(2026, 7, 12),
                auth_mode="anonymous",
            ),
        )
        source = _search_source(
            (
                _response(
                    path="/search/",
                    params={
                        "type": "rd",
                        "description": 'order AND granting AND "motion to dismiss"',
                        "entry_date_filed_after": "2026-06-30",
                        "order_by": "entry_date_filed desc",
                        "page_size": 100,
                    },
                    payload={
                        "results": [
                            {
                                "id": 9001,
                                "docket_id": 555,
                                "description": "ORDER granting motion to dismiss",
                                "entry_date_filed": "2026-07-05",
                                "court_id": "nysd",
                                "docketNumber": "1:26-cv-00001",
                                "caseName": "Acme Corp v. Roe",
                            },
                            {
                                "id": 9002,
                                "docket_id": 555,
                                "description": "another decision doc",
                                "entry_date_filed": "2026-07-04",
                                "court_id": "nysd",
                                "docketNumber": "1:26-cv-00001",
                                "caseName": "Acme Corp v. Roe",
                            },
                        ],
                        "next": None,
                    },
                ),
            )
        )
        summary = materialize_independent_term_sets(
            source=source,
            store=store,
            batch_id="batch-002",
            query_terms=('order AND granting AND "motion to dismiss"',),
            top_k_per_term=5_000,
            page_size=100,
        )
        assert summary.candidate_ids == ("courtlistener-docket-555",)
        assert summary.saturated is True
        assert all(
            status is TermTerminalStatus.EXHAUSTED
            for status in summary.terminal_status_by_term.values()
        )


def test_fetch_page_fails_closed_on_rate_limit() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _response(
                    path="/search/",
                    params={
                        "type": "rd",
                        "description": "q",
                        "entry_date_filed_after": "2026-06-30",
                        "order_by": "entry_date_filed desc",
                        "page_size": 100,
                    },
                    status_code=429,
                    payload={"detail": "throttled"},
                ),
            )
        ),
        max_retries=0,
    )
    source = RecapApiDiscoverySource(
        client=client,
        entry_date_filed_after=date(2026, 6, 30),
        auth_mode="anonymous",
    )
    with pytest.raises(CourtListenerRateLimitError):
        source.fetch_page(term="q", cursor=None, page_size=100)


# ---------------------------------------------------------------------------
# Docket reconstruction with completeness proof.
# ---------------------------------------------------------------------------


def _docket_response(docket_id: int) -> RecordedCourtListenerResponse:
    return _response(
        path=f"/dockets/{docket_id}/",
        payload={
            "id": docket_id,
            "court": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Acme Corp v. Roe",
            "date_filed": "2026-05-01",
            "absolute_url": f"https://www.courtlistener.com/docket/{docket_id}/",
        },
    )


def _entries_response(
    *,
    cursor: str | None,
    results: list[dict[str, Any]],
    next_cursor: str | None,
) -> RecordedCourtListenerResponse:
    params: dict[str, Any] = {"docket": "555", "page_size": 100}
    if cursor is not None:
        params["cursor"] = cursor
    return _response(
        path="/docket-entries/",
        params=params,
        payload={"results": results, "next": next_cursor},
    )


def _client(
    responses: tuple[RecordedCourtListenerResponse, ...],
) -> CourtListenerClient:
    # Reconstruction hits token-required CourtListener endpoints, so the
    # reconstruction client always carries a token.
    return CourtListenerClient(
        config=CourtListenerConfig(api_token="test-token"),
        transport=CourtListenerFixtureTransport(responses),
    )


def test_reconstruct_fails_closed_without_token() -> None:
    client = CourtListenerClient(
        config=CourtListenerConfig(api_token=None),
        transport=CourtListenerFixtureTransport(()),
    )
    with pytest.raises(RecapReconstructionAuthError, match="COURTLISTENER_API_TOKEN"):
        reconstruct_docket_page(client, "555")


def test_reconstruct_docket_produces_screenable_page() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 12,
                        "description": "COMPLAINT filed",
                        "date_filed": "2026-05-01",
                    },
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": (
                            "ORDER granting defendant's motion to dismiss the "
                            "complaint with prejudice"
                        ),
                        "date_filed": "2026-07-05",
                    },
                ],
                next_cursor="cursor-2",
            ),
            _entries_response(
                cursor="cursor-2",
                results=[
                    {
                        "id": 7003,
                        "docket": 555,
                        "entry_number": 41,
                        "description": "JUDGMENT entered",
                        "date_filed": "2026-07-06",
                    }
                ],
                next_cursor=None,
            ),
        )
    )
    reconstructed = reconstruct_docket_page(client, "555")
    assert reconstructed.proof.complete is True
    assert reconstructed.proof.pages_fetched == 2
    assert reconstructed.proof.entry_count == 3
    assert reconstructed.page.has_next_page is False
    # The reconstructed page must be accepted by the unmodified strict screen,
    # which proves the "Month DD, YYYY" date rendering is screen-compatible.
    screen = screen_courtlistener_docket_for_mtd_decision(
        reconstructed.page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    assert screen.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION
    assert screen.has_actual_mtd_decision is True


def test_reconstruct_retains_blank_description_entry_without_hiding_decision() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 39,
                        "description": "",
                        "date_filed": "2026-07-04",
                    },
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": "ORDER granting motion to dismiss",
                        "date_filed": "2026-07-05",
                    },
                ],
                next_cursor=None,
            ),
        )
    )

    reconstructed = reconstruct_docket_page(client, "555")
    screen = screen_courtlistener_docket_for_mtd_decision(
        reconstructed.page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert reconstructed.proof.entry_count == 2
    assert reconstructed.page.entries[0].text == ""
    assert screen.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION


def test_reconstruct_normalizes_docket_id() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(cursor=None, results=[], next_cursor=None),
        )
    )
    reconstructed = reconstruct_docket_page(client, " 555 ")
    assert reconstructed.docket.docket_id == "555"
    assert reconstructed.proof.docket_id == "555"


def test_reconstruct_excludes_decision_before_anchor() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": "ORDER granting motion to dismiss",
                        "date_filed": "2026-06-15",
                    }
                ],
                next_cursor=None,
            ),
        )
    )
    reconstructed = reconstruct_docket_page(client, "555")
    screen = screen_courtlistener_docket_for_mtd_decision(
        reconstructed.page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    assert screen.status is MtdDocketScreenStatus.EXCLUDED
    assert "mtd_decision_outside_date_window" in screen.exclusion_reasons


def test_reconstruct_fails_closed_on_duplicate_entries() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": "ORDER",
                        "date_filed": "2026-07-05",
                    }
                ],
                next_cursor="cursor-2",
            ),
            _entries_response(
                cursor="cursor-2",
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": "ORDER",
                        "date_filed": "2026-07-05",
                    }
                ],
                next_cursor=None,
            ),
        )
    )
    with pytest.raises(RecapDocketReconstructionError, match="duplicate"):
        reconstruct_docket_page(client, "555")


def test_reconstruct_fails_closed_on_conflicting_duplicate_entry_numbers() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 4,
                        "description": "Corporate disclosure statement",
                        "date_filed": "2026-06-01",
                    },
                    {
                        "id": 7999,
                        "docket": 555,
                        "entry_number": 4,
                        "description": "Criminal defense counsel appearance",
                        "date_filed": "2025-12-24",
                    },
                ],
                next_cursor=None,
            ),
        )
    )

    with pytest.raises(RecapDocketContradictionError, match="entry number 4"):
        reconstruct_docket_page(client, "555")


def test_reconstruct_detects_conflicting_entry_numbers_across_pages() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 4,
                        "description": "Corporate disclosure statement",
                        "date_filed": "2026-06-01",
                    }
                ],
                next_cursor="cursor-2",
            ),
            _entries_response(
                cursor="cursor-2",
                results=[
                    {
                        "id": 7999,
                        "docket": 555,
                        "entry_number": 4,
                        "description": "Criminal defense counsel appearance",
                        "date_filed": "2025-12-24",
                    }
                ],
                next_cursor=None,
            ),
        )
    )

    with pytest.raises(RecapDocketContradictionError, match="entry number 4"):
        reconstruct_docket_page(client, "555")


def test_reconstruct_allows_duplicate_recap_sequence_numbers() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": None,
                        "recap_sequence_number": "2026-07-13.001",
                        "description": "Clerk reassignment notice",
                        "date_filed": "2026-07-13",
                    },
                    {
                        "id": 7999,
                        "docket": 555,
                        "entry_number": None,
                        "recap_sequence_number": "2026-07-13.001",
                        "description": "Case reassigned",
                        "date_filed": "2026-07-13",
                    },
                ],
                next_cursor=None,
            ),
        )
    )

    reconstructed = reconstruct_docket_page(client, "555")

    assert reconstructed.proof.entry_count == 2


def test_reconstruct_fails_closed_on_non_advancing_cursor() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": "ORDER",
                        "date_filed": "2026-07-05",
                    }
                ],
                next_cursor="cursor-2",
            ),
            _entries_response(
                cursor="cursor-2",
                results=[
                    {
                        "id": 7003,
                        "docket": 555,
                        "entry_number": 41,
                        "description": "ORDER",
                        "date_filed": "2026-07-05",
                    }
                ],
                next_cursor="cursor-2",
            ),
        )
    )
    with pytest.raises(RecapDocketReconstructionError, match="did not advance"):
        reconstruct_docket_page(client, "555")


def test_reconstruct_handles_hyperlinked_docket_foreign_keys() -> None:
    # CourtListener v4 renders the docket foreign key on /docket-entries/ as a
    # hyperlinked resource URL, not a bare id. Reconstruction must extract the id
    # and still recognize the entry as belonging to the requested docket.
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7002,
                        "docket": (
                            "https://www.courtlistener.com/api/rest/v4/dockets/555/"
                        ),
                        "entry_number": 40,
                        "description": (
                            "ORDER granting defendant's motion to dismiss the complaint"
                        ),
                        "date_filed": "2026-07-05",
                    }
                ],
                next_cursor=None,
            ),
        )
    )
    reconstructed = reconstruct_docket_page(client, "555")
    assert reconstructed.proof.complete is True
    assert reconstructed.proof.entry_count == 1
    screen = screen_courtlistener_docket_for_mtd_decision(
        reconstructed.page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    assert screen.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION


def test_reconstruct_sorts_out_of_order_entries_without_failing() -> None:
    # The API may return entries newest-first (or otherwise out of sequence). A
    # complete fetch (cursor exhausted, no duplicate ids) must reconstruct into
    # ascending docket order rather than fail as a false non-monotonic sequence.
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7003,
                        "docket": 555,
                        "entry_number": 41,
                        "description": "JUDGMENT entered",
                        "date_filed": "2026-07-06",
                    },
                    {
                        "id": 7002,
                        "docket": 555,
                        "entry_number": 40,
                        "description": (
                            "ORDER granting defendant's motion to dismiss the complaint"
                        ),
                        "date_filed": "2026-07-05",
                    },
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 12,
                        "description": "COMPLAINT filed",
                        "date_filed": "2026-05-01",
                    },
                ],
                next_cursor=None,
            ),
        )
    )
    reconstructed = reconstruct_docket_page(client, "555")
    assert reconstructed.proof.complete is True
    assert reconstructed.proof.entry_numbers_monotonic is True
    assert [entry.entry_number for entry in reconstructed.page.entries] == [
        "12",
        "40",
        "41",
    ]


def test_observe_enforces_frozen_decision_window_end(tmp_path: Path) -> None:
    # The in-window search hit surfaced the docket, but its only MTD disposition
    # is filed after the frozen window closes; the upper bound must keep it out of
    # the accepted pool rather than admit an out-of-window decision.
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-20",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    try:
        recon_client = _client(
            (
                _docket_response(555),
                _entries_response(
                    cursor=None,
                    results=[
                        {
                            "id": 7001,
                            "docket": 555,
                            "entry_number": 20,
                            "description": "Motion to dismiss the complaint",
                            "date_filed": "2026-06-20",
                            "recap_documents": [
                                {
                                    "id": 8001,
                                    "document_number": "20",
                                    "attachment_number": None,
                                    "description": "Motion to dismiss",
                                    "filepath_local": (
                                        "https://storage.courtlistener.com/"
                                        "recap/motion.pdf"
                                    ),
                                    "is_available": True,
                                    "is_sealed": False,
                                    "is_private": False,
                                    "redaction_or_seal_status": "public",
                                    "pacer_doc_id": "02004678901",
                                }
                            ],
                        },
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": (
                                "ORDER granting defendant's motion to dismiss the "
                                "complaint"
                            ),
                            "date_filed": "2026-07-20",
                        },
                    ],
                    next_cursor=None,
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
        assert observation.state == "excluded"
        assert observation.reason_code == "strict_clean_screen_failed"
        assert observation.evidence["decision_window_end"] == "2026-07-12"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Pacer and helpers.
# ---------------------------------------------------------------------------


def test_pacer_waits_when_requests_are_too_close() -> None:
    now = [100.0]
    slept: list[float] = []
    pacer = RequestPacer(
        min_interval_seconds=3.0,
        clock=lambda: now[0],
        sleep=lambda seconds: slept.append(seconds),
    )
    pacer.wait()  # first request: no wait
    pacer.wait()  # immediately after: must wait the full interval
    assert slept == [3.0]


def test_pacer_for_client_uses_anonymous_spacing() -> None:
    anon = CourtListenerClient(
        config=CourtListenerConfig(api_token=None),
        transport=CourtListenerFixtureTransport(()),
    )
    authed = CourtListenerClient(
        config=CourtListenerConfig(api_token="secret"),
        transport=CourtListenerFixtureTransport(()),
    )
    assert resolve_auth_mode(anon) == "anonymous"
    assert resolve_auth_mode(authed) == "authenticated"
    assert pacer_for_client(anon).min_interval_seconds == 3.0
    assert pacer_for_client(authed).min_interval_seconds == 0.0


def test_candidate_helpers() -> None:
    payload = RecapDecisionHit.from_record(
        {"id": 1, "docket_id": 555, "court_id": "nysb", "caseName": "In re X"}
    ).candidate_payload(query_term="q", auth_mode="anonymous")
    assert candidate_docket_id(payload) == "555"
    assert observe_prescreened_reason(payload) == PRESCREEN_BANKRUPTCY_REASON


# ---------------------------------------------------------------------------
# Observation orchestration (discovery -> reconstruct -> screen -> store).
# ---------------------------------------------------------------------------


def _seeded_store(
    tmp_path: Path, hit: dict[str, Any]
) -> tuple[CycleAcquisitionStore, dict[str, Any]]:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle({"schema_version": "test"})
    term = 'order AND granting AND "motion to dismiss"'
    store.ensure_batch(
        "batch-002",
        build_recap_api_batch_config(
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
            auth_mode="anonymous",
        ),
    )
    source = _search_source(
        (
            _response(
                path="/search/",
                params={
                    "type": "rd",
                    "description": term,
                    "entry_date_filed_after": "2026-06-30",
                    "order_by": "entry_date_filed desc",
                    "page_size": 100,
                },
                payload={"results": [hit], "next": None},
            ),
        )
    )
    materialize_independent_term_sets(
        source=source,
        store=store,
        batch_id="batch-002",
        query_terms=(term,),
        top_k_per_term=5_000,
        page_size=100,
    )
    payload = dict(store.candidate_discovery_hits("batch-002")[0].payload)
    return store, payload


def test_observe_accepts_clean_in_window_decision(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    with store:
        recon_client = _client(
            (
                _docket_response(555),
                _entries_response(
                    cursor=None,
                    results=[
                        {
                            "id": 7001,
                            "docket": 555,
                            "entry_number": 20,
                            "description": "Motion to dismiss the complaint",
                            "date_filed": "2026-06-20",
                            "recap_documents": [
                                {
                                    "id": 8001,
                                    "document_number": "20",
                                    "attachment_number": None,
                                    "description": "Motion to dismiss",
                                    "filepath_local": (
                                        "https://storage.courtlistener.com/"
                                        "recap/motion.pdf"
                                    ),
                                    "is_available": True,
                                    "is_sealed": False,
                                    "is_private": False,
                                    "redaction_or_seal_status": "public",
                                    "pacer_doc_id": "02004678901",
                                }
                            ],
                        },
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": (
                                "ORDER granting defendant's motion to dismiss the "
                                "complaint"
                            ),
                            "date_filed": "2026-07-05",
                        },
                    ],
                    next_cursor=None,
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert observation.state == "accepted"
        assert observation.reason_code == "strict_clean_screen_passed"
        assert observation.evidence["first_mtd_decision_date"] == "2026-07-05"
        assert observation.evidence["mtd_decision_entries"] == [
            {
                "row_id": "entry-40",
                "entry_number": "40",
                "filed_at": "July 5, 2026",
                "filed_date": "2026-07-05",
            }
        ]
        assert observation.evidence["eligibility_anchor"] == "2026-06-30"
        assert observation.evidence["ai"] == {
            "target_motion_entry_numbers": ["20"],
            "decision_entry_numbers": ["40"],
        }
        selected_entries = observation.evidence["selected_entries"]
        assert isinstance(selected_entries, list)
        assert selected_entries[0]["documents"][0] == {
            "kind": "main",
            "description": "Motion to dismiss",
            "href": "https://storage.courtlistener.com/recap/motion.pdf",
            "action_label": "Download PDF",
            "pacer_only": False,
            "freely_available": True,
            "restriction_markers": [],
        }
        current = store.current_observation("courtlistener-docket-555")
        assert current is not None and current.state == "accepted"


def test_observe_links_explicitly_referenced_terse_rest_mtd_label(
    tmp_path: Path,
) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-02",
            "court_id": "azd",
            "docketNumber": "3:26-cv-08039",
            "caseName": "Kearns v. Schuster",
        },
    )
    with store:
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=_client(
                (
                    _docket_response(555),
                    _entries_response(
                        cursor=None,
                        results=[
                            {
                                "id": 7001,
                                "docket": 555,
                                "entry_number": 6,
                                "description": "Dismiss for Failure to State a Claim",
                                "date_filed": "2026-05-27",
                                "recap_documents": [
                                    {
                                        "id": 8001,
                                        "document_number": "6",
                                        "attachment_number": None,
                                        "description": (
                                            "Dismiss for Failure to State a Claim"
                                        ),
                                        "is_available": False,
                                        "is_sealed": None,
                                        "pacer_doc_id": "025030920190",
                                    }
                                ],
                            },
                            {
                                "id": 7002,
                                "docket": 555,
                                "entry_number": 8,
                                "description": (
                                    "ORDER summarily granting Defendant's motion to "
                                    "dismiss (Doc. 6)"
                                ),
                                "date_filed": "2026-07-02",
                            },
                        ],
                        next_cursor=None,
                    ),
                )
            ),
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "accepted"
        assert observation.reason_code == "strict_clean_screen_passed"
        assert observation.evidence["ai"] == {
            "target_motion_entry_numbers": ["6"],
            "decision_entry_numbers": ["8"],
        }


def test_observe_rejects_procedural_order_that_leaves_mtd_pending(
    tmp_path: Path,
) -> None:
    decision_text = (
        "ORDER granting Defendants' Motion to Exceed Page Limit for Defendants' "
        "Motion to Dismiss (Doc. 9). Defendants' Motion to Dismiss (Doc. 8) is "
        "considered within the page limit. IT IS FURTHER ORDERED granting the "
        "parties' Stipulation of Time to File Response to Motion to Dismiss "
        "(Doc. 13). Plaintiff's Response to Defendants' Motion to Dismiss "
        "(Doc. 8) shall be filed no later than July 17, 2026."
    )
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": decision_text,
            "entry_date_filed": "2026-07-13",
            "court_id": "azd",
            "docketNumber": "2:26-cv-01234",
            "caseName": "Lageman v. Phoenix",
        },
    )
    with store:
        stale_acceptance = store.record_observation(
            "courtlistener-docket-555",
            batch_id="batch-002",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screening_kernel": "before-procedural-order-correction"},
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=_client(
                (
                    _docket_response(555),
                    _entries_response(
                        cursor=None,
                        results=[
                            {
                                "id": 6997,
                                "docket": 555,
                                "entry_number": 1,
                                "description": "Notice of Removal",
                                "date_filed": "2026-04-22",
                            },
                            {
                                "id": 6998,
                                "docket": 555,
                                "entry_number": 2,
                                "description": "Proposed Order",
                                "date_filed": "2026-04-24",
                            },
                            {
                                "id": 6999,
                                "docket": 555,
                                "entry_number": 3,
                                "description": "Summons Issued",
                                "date_filed": "2026-05-01",
                            },
                            {
                                "id": 7000,
                                "docket": 555,
                                "entry_number": 4,
                                "description": "Service Executed",
                                "date_filed": "2026-05-12",
                            },
                            {
                                "id": 7001,
                                "docket": 555,
                                "entry_number": 8,
                                "description": "First Motion to Dismiss Case",
                                "date_filed": "2026-06-26",
                            },
                            {
                                "id": 7002,
                                "docket": 555,
                                "entry_number": 14,
                                "description": decision_text,
                                "date_filed": "2026-07-13",
                            },
                        ],
                        next_cursor=None,
                    ),
                )
            ),
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "excluded"
        assert observation.reason_code == "procedural_or_standing_order"
        screen = observation.evidence["screen"]
        assert isinstance(screen, dict)
        assert "procedural_or_standing_order" in screen["exclusion_reasons"]
        current = store.current_observation("courtlistener-docket-555")
        assert current is not None
        assert current.observation_id == observation.observation_id
        assert current.supersedes_observation_id == stale_acceptance.observation_id


def test_observe_supersedes_acceptance_on_contradictory_provider_entries(
    tmp_path: Path,
) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "MEMORANDUM OPINION granting motion to dismiss",
            "entry_date_filed": "2026-07-01",
            "court_id": "dcd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Brown v. Alphasense",
        },
    )
    with store:
        stale_acceptance = store.record_observation(
            "courtlistener-docket-555",
            batch_id="batch-002",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screening_kernel": "before-provider-contradiction-gate"},
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=_client(
                (
                    _docket_response(555),
                    _entries_response(
                        cursor=None,
                        results=[
                            {
                                "id": 7002,
                                "docket": 555,
                                "entry_number": 4,
                                "description": "Corporate disclosure statement",
                                "date_filed": "2026-06-01",
                            },
                            {
                                "id": 7999,
                                "docket": 555,
                                "entry_number": 4,
                                "description": "Criminal counsel appearance",
                                "date_filed": "2025-12-24",
                            },
                        ],
                        next_cursor=None,
                    ),
                )
            ),
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "excluded"
        assert observation.reason_code == "invalid_civil_case_metadata"
        assert observation.evidence["provider_contradiction"] is True
        assert (
            observation.evidence["exclusion_detail"]
            == "contradictory_docket_entry_metadata"
        )
        current = store.current_observation("courtlistener-docket-555")
        assert current is not None
        assert current.observation_id == observation.observation_id
        assert current.supersedes_observation_id == stale_acceptance.observation_id


def test_reconstruction_does_not_infer_public_access_from_availability() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 20,
                        "description": "Motion to dismiss",
                        "date_filed": "2026-06-20",
                        "recap_documents": [
                            {
                                "id": 8001,
                                "description": "Motion to dismiss",
                                "filepath_local": (
                                    "https://storage.courtlistener.com/recap/motion.pdf"
                                ),
                                "is_available": True,
                            }
                        ],
                    }
                ],
                next_cursor=None,
            ),
        )
    )

    reconstructed = reconstruct_docket_page(client, "555")

    [document] = reconstructed.page.entries[0].documents
    assert document.href is None
    assert document.pacer_only is True
    assert document.freely_available is False


def test_reconstruction_accepts_actual_v4_free_recap_document_shape() -> None:
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 20,
                        "description": "Motion to dismiss",
                        "date_filed": "2026-06-20",
                        "recap_documents": [
                            {
                                "id": 8001,
                                "description": "Motion to dismiss",
                                "filepath_local": (
                                    "recap/gov.uscourts.nysd.123456.20.0.pdf"
                                ),
                                "is_available": True,
                                "is_sealed": False,
                            }
                        ],
                    }
                ],
                next_cursor=None,
            ),
        )
    )

    reconstructed = reconstruct_docket_page(client, "555")

    [document] = reconstructed.page.entries[0].documents
    assert document.href == (
        "https://www.courtlistener.com/recap/gov.uscourts.nysd.123456.20.0.pdf"
    )
    assert document.pacer_only is False
    assert document.freely_available is True


@pytest.mark.parametrize(
    "document_overrides",
    (
        {"is_sealed": True},
        {"is_private": True},
        {"is_private": "true"},
        {"is_private": 1},
        {"filepath_local": "https://evil.example/recap/motion.pdf"},
    ),
    ids=(
        "sealed",
        "private",
        "malformed-private-string",
        "malformed-private-integer",
        "unallowlisted-url",
    ),
)
def test_reconstruction_rejects_restricted_or_unallowlisted_free_document(
    document_overrides: dict[str, object],
) -> None:
    document = {
        "id": 8001,
        "description": "Motion to dismiss",
        "filepath_local": "recap/gov.uscourts.nysd.123456.20.0.pdf",
        "is_available": True,
        "is_sealed": False,
        **document_overrides,
    }
    client = _client(
        (
            _docket_response(555),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "entry_number": 20,
                        "description": "Motion to dismiss",
                        "date_filed": "2026-06-20",
                        "recap_documents": [document],
                    }
                ],
                next_cursor=None,
            ),
        )
    )

    reconstructed = reconstruct_docket_page(client, "555")

    [reconstructed_document] = reconstructed.page.entries[0].documents
    assert reconstructed_document.href is None
    assert reconstructed_document.pacer_only is True
    assert reconstructed_document.freely_available is False


def test_observe_excludes_bankruptcy_without_fetch(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER on motion to dismiss case",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysb",
            "docketNumber": "1:26-bk-00001",
            "caseName": "In re Debtor",
        },
    )
    with store:
        # An empty reconstruction client proves no docket fetch is attempted.
        recon_client = _client(())
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert observation.state == "excluded"
        assert observation.reason_code == PRESCREEN_BANKRUPTCY_REASON


def test_observe_soft_skips_docket_proven_above_entry_cap(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_number": REST_DOCKET_ENTRY_SOFT_CAP + 1,
            "entry_date_filed": "2026-07-05",
        },
    )
    with store:
        recon_client = _client(())
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "excluded"
        assert observation.reason_code == "oversized_docket_soft_skip"
        assert observation.evidence["entry_number_lower_bound"] == 501
        assert observation.evidence["sampling_exclusion"] is True
        assert recon_client.request_count == 0


def test_reconstruction_fails_closed_at_page_cap(tmp_path: Path) -> None:
    del tmp_path
    client = _client(
        (
            _response(
                path="/dockets/555/",
                payload={"id": 555, "case_name": "Acme Corp v. Roe"},
            ),
            _entries_response(
                cursor=None,
                results=[
                    {
                        "id": 7001,
                        "docket": 555,
                        "description": "Complaint",
                    }
                ],
                next_cursor="more",
            ),
        )
    )

    with pytest.raises(RecapDocketTooLargeError, match="1-page"):
        reconstruct_docket_page(client, "555", max_pages=1)

    assert client.request_count == 2


def test_observe_soft_skips_after_rest_page_cap(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    responses = [_docket_response(555)]
    for page_index in range(REST_DOCKET_PAGE_HARD_CAP):
        cursor = None if page_index == 0 else f"cursor-{page_index}"
        responses.append(
            _entries_response(
                cursor=cursor,
                results=[
                    {
                        "id": 7000 + page_index,
                        "docket": 555,
                        "entry_number": page_index + 1,
                        "description": "Docket entry",
                        "date_filed": "2026-06-20",
                    }
                ],
                next_cursor=f"cursor-{page_index + 1}",
            )
        )

    with store:
        client = _client(tuple(responses))
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=client,
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "excluded"
        assert observation.reason_code == "oversized_docket_soft_skip"
        assert (
            observation.evidence["rest_docket_page_hard_cap"]
            == REST_DOCKET_PAGE_HARD_CAP
        )
        assert observation.evidence["sampling_exclusion"] is True
        assert client.request_count == REST_DOCKET_PAGE_HARD_CAP + 1


def test_observe_records_unavailable_entry_page_as_candidate_local_transient(
    tmp_path: Path,
) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    client = _client(
        (
            _docket_response(555),
            _response(
                path="/docket-entries/",
                params={"docket": "555", "page_size": 100},
                status_code=404,
                payload={"detail": "entry page unavailable"},
            ),
        )
    )

    with store:
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=client,
            eligibility_anchor=date(2026, 6, 30),
        )

    assert observation.state == "transient_failure"
    assert observation.reason_code == "courtlistener_docket_unavailable"
    assert observation.evidence["entry_reconstruction_started"] is True
    assert client.request_count == 2


def test_observe_excludes_first_disposition_before_anchor(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    with store:
        recon_client = _client(
            (
                _docket_response(555),
                _entries_response(
                    cursor=None,
                    results=[
                        {
                            "id": 7001,
                            "docket": 555,
                            "entry_number": 20,
                            "description": "ORDER granting motion to dismiss",
                            "date_filed": "2026-06-15",
                        },
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": "ORDER granting renewed motion to dismiss",
                            "date_filed": "2026-07-05",
                        },
                    ],
                    next_cursor=None,
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert observation.state == "excluded"
        assert observation.reason_code == "decision_before_release_anchor"


@pytest.mark.parametrize(
    "results",
    (
        [
            {
                "id": 7001,
                "docket": 555,
                "entry_number": 20,
                "description": "Order on Motion to Dismiss",
                "date_filed": "2026-06-15",
            },
            {
                "id": 7002,
                "docket": 555,
                "entry_number": 40,
                "description": "ORDER granting renewed motion to dismiss",
                "date_filed": "2026-07-05",
            },
        ],
        [
            {
                "id": 7001,
                "docket": 555,
                "entry_number": 18,
                "description": "Motion to Dismiss",
                "date_filed": "2026-01-05",
            },
            {
                "id": 7002,
                "docket": 555,
                "entry_number": 31,
                "description": "Report & Recommendation",
                "date_filed": "2026-01-29",
            },
            {
                "id": 7003,
                "docket": 555,
                "entry_number": 33,
                "description": (
                    "MEMORANDUM ORDER adopting 31 Report & Recommendation; "
                    "granting 18 Motion to Dismiss"
                ),
                "date_filed": "2026-07-09",
            },
        ],
    ),
)
def test_observe_excludes_preanchor_generic_order_or_adopted_recommendation(
    tmp_path: Path,
    results: list[dict[str, object]],
) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    with store:
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=_client(
                (
                    _docket_response(555),
                    _entries_response(
                        cursor=None,
                        results=results,
                        next_cursor=None,
                    ),
                )
            ),
            eligibility_anchor=date(2026, 6, 30),
        )

    assert observation.state == "excluded"
    assert observation.reason_code == "decision_before_release_anchor"
    assert observation.evidence["first_mtd_decision_date"] < "2026-06-30"
    assert observation.evidence["mtd_anchor_disposition_entries"]


def test_observe_rejects_candidate_id_docket_id_mismatch(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
        },
    )
    payload["candidate_id"] = "courtlistener-docket-999"
    with store, pytest.raises(RecapApiResponseError, match="does not match"):
        observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=_client(()),
            eligibility_anchor=date(2026, 6, 30),
        )


def test_observe_fails_closed_on_undated_mtd_disposition(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
            "court_id": "nysd",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Acme Corp v. Roe",
        },
    )
    with store:
        recon_client = _client(
            (
                _docket_response(555),
                _entries_response(
                    cursor=None,
                    results=[
                        {
                            "id": 7001,
                            "docket": 555,
                            "entry_number": 20,
                            "description": "ORDER granting motion to dismiss",
                            "date_filed": None,
                        },
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": "ORDER granting renewed motion to dismiss",
                            "date_filed": "2026-07-05",
                        },
                    ],
                    next_cursor=None,
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert observation.state == "transient_failure"
        assert observation.reason_code == "parse_failure"
        assert observation.evidence["unparseable_mtd_decision_entries"] == [
            {
                "row_id": "entry-20",
                "entry_number": "20",
                "filed_at": None,
                "filed_date": None,
            }
        ]


def test_observe_prescreens_authoritative_bankruptcy_metadata(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
        },
    )
    with store:
        recon_client = _client(
            (
                _response(
                    path="/dockets/555/",
                    payload={
                        "id": 555,
                        "court": "nysb",
                        "docket_number": "1:26-bk-00001",
                        "case_name": "In re Debtor",
                        "date_filed": "2026-05-01",
                    },
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert observation.state == "excluded"
        assert observation.reason_code == PRESCREEN_BANKRUPTCY_REASON
        assert observation.evidence["authoritative_docket_metadata"] == {
            "court_id": "nysb",
            "docket_number": "1:26-bk-00001",
            "case_name": "In re Debtor",
        }
        assert observation.evidence["entry_reconstruction_skipped"] is True
        assert recon_client.request_count == 1


def test_observe_retains_authoritative_bankruptcy_adversary(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
        },
    )
    with store:
        recon_client = _client(
            (
                _response(
                    path="/dockets/555/",
                    payload={
                        "id": 555,
                        "court": "nysb",
                        "docket_number": "1:26-ap-00001",
                        "case_name": "Trustee v. Roe",
                        "date_filed": "2026-05-01",
                    },
                ),
                _entries_response(
                    cursor=None,
                    results=[
                        {
                            "id": 7001,
                            "docket": 555,
                            "entry_number": 1,
                            "description": "Adversary complaint filed by Trustee",
                            "date_filed": "2026-05-01",
                        },
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 10,
                            "description": (
                                "Motion to dismiss Count I of the adversary "
                                "complaint under Fed. R. Bankr. P. 7012"
                            ),
                            "date_filed": "2026-05-20",
                        },
                        {
                            "id": 7003,
                            "docket": 555,
                            "entry_number": 20,
                            "description": (
                                "ORDER granting motion to dismiss Count I of the "
                                "adversary complaint under Rule 7012"
                            ),
                            "date_filed": "2026-07-05",
                        },
                    ],
                    next_cursor=None,
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "accepted"
        assert observation.reason_code == "strict_clean_screen_passed"
        screen = observation.evidence["screen"]
        assert isinstance(screen, dict)
        assert screen["case_type_stratum"] == "bankruptcy_adversary"
        assert recon_client.request_count == 2


def test_observe_authoritative_criminal_metadata_skips_entries(tmp_path: Path) -> None:
    store, payload = _seeded_store(
        tmp_path,
        {
            "id": 9001,
            "docket_id": 555,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-05",
        },
    )
    with store:
        recon_client = _client(
            (
                _response(
                    path="/dockets/555/",
                    payload={
                        "id": 555,
                        "court": "cacd",
                        "docket_number": "5:13-cr-00015",
                        "case_name": "United States v. Roe",
                    },
                ),
            )
        )
        observation = observe_recap_api_candidate(
            store,
            "batch-002",
            payload,
            client=recon_client,
            eligibility_anchor=date(2026, 6, 30),
        )

        assert observation.state == "excluded"
        assert observation.reason_code == PRESCREEN_CRIMINAL_REASON
        assert observation.evidence["entry_reconstruction_skipped"] is True
        assert recon_client.request_count == 1
