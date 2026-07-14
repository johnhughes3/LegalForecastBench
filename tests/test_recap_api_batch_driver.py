"""Tests for the batch-002 RECAP API driver (discover / observe / seed)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.recap_api_batch_driver import (
    Batch001Lead,
    RecapApiBatchDriverError,
    read_batch_001_enrichment_failure_leads,
    run_discover,
    run_observe,
    seed_batch_001_leads,
)
from legalforecast.ingestion.recap_api_discovery import (
    RecapReconstructionAuthError,
    RequestPacer,
)

_TERMS = (
    'order AND granting AND "motion to dismiss"',
    'order AND denying AND "motion to dismiss"',
    '"motion to dismiss" AND "granted in part"',
    '"order on motion to dismiss"',
    '"memorandum opinion" AND "motion to dismiss"',
    '"report and recommendation" AND "motion to dismiss"',
    'order AND (granting OR denying) AND "judgment on the pleadings"',
    'order AND (granting OR denying) AND "12(b)(6)"',
)


# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------


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


def _search_response(
    *, term: str, results: list[dict[str, Any]]
) -> RecordedCourtListenerResponse:
    return _response(
        path="/search/",
        params={
            "type": "rd",
            "description": term,
            "entry_date_filed_after": "2026-06-30",
            "entry_date_filed_before": "2026-07-12",
            "order_by": "entry_date_filed desc",
            "page_size": 100,
        },
        payload={"results": results, "next": None},
    )


def _empty_search_responses() -> list[RecordedCourtListenerResponse]:
    return [_search_response(term=term, results=[]) for term in _TERMS]


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
    docket_id: int,
    results: list[dict[str, Any]],
) -> RecordedCourtListenerResponse:
    return _response(
        path="/docket-entries/",
        params={"docket": str(docket_id), "page_size": 100},
        payload={"results": results, "next": None},
    )


def _motion_entry(docket_id: int, *, entry_id: int = 7001) -> dict[str, Any]:
    return {
        "id": entry_id,
        "docket": docket_id,
        "entry_number": 20,
        "description": "Motion to dismiss the complaint",
        "date_filed": "2026-06-20",
    }


def _anonymous_client(
    responses: list[RecordedCourtListenerResponse],
) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(tuple(responses)),
    )


def _token_client(
    responses: list[RecordedCourtListenerResponse],
) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(api_token="test-token"),
        transport=CourtListenerFixtureTransport(tuple(responses)),
    )


def _fresh_store(tmp_path: Path, name: str = "cycle.sqlite3") -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / name)
    store.ensure_cycle({"schema_version": "test", "eligibility_anchor": "2026-06-30"})
    return store


# ---------------------------------------------------------------------------
# discover.
# ---------------------------------------------------------------------------


def test_run_discover_funnel_dedupes_and_counts_prescreen(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    granting = _TERMS[0]
    responses = _empty_search_responses()
    # Replace the first term's response with three hits: two share a docket
    # (dedupe to one candidate), one is a bankruptcy court (pre-screen excluded).
    responses[0] = _search_response(
        term=granting,
        results=[
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
                "description": "second decision doc same docket",
                "entry_date_filed": "2026-07-04",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            },
            {
                "id": 9003,
                "docket_id": 777,
                "description": "ORDER on motion to dismiss",
                "entry_date_filed": "2026-07-03",
                "court_id": "nysb",
                "docketNumber": "1:26-bk-00007",
                "caseName": "In re Debtor",
            },
        ],
    )
    client = _anonymous_client(responses)
    try:
        funnel = run_discover(
            store,
            batch_id="batch-002",
            client=client,
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
    finally:
        store.close()

    assert funnel.terms_total == 8
    assert funnel.terms_terminal == 8
    assert funnel.complete is True
    assert funnel.saturated is True
    # Two docket candidates (555 and 777); three raw hits on the first term.
    assert funnel.distinct_candidates == 2
    assert funnel.total_hits == 3
    assert funnel.prescreen_exclusions_by_reason == {"bankruptcy_court": 1}
    first_row = next(row for row in funnel.per_term if row.term == granting)
    assert first_row.hit_count == 3
    assert first_row.terminal_status == "exhausted"


def test_run_discover_resumes_without_double_counting(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    responses = _empty_search_responses()
    responses[0] = _search_response(
        term=_TERMS[0],
        results=[
            {
                "id": 9001,
                "docket_id": 555,
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            }
        ],
    )
    try:
        run_discover(
            store,
            batch_id="batch-002",
            client=_anonymous_client(responses),
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
        # Re-running with a client that would error on any wire call proves the
        # terms are already terminal and no further fetch happens.
        funnel = run_discover(
            store,
            batch_id="batch-002",
            client=_anonymous_client([]),
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
    finally:
        store.close()
    assert funnel.distinct_candidates == 1
    assert funnel.total_hits == 1


# ---------------------------------------------------------------------------
# observe.
# ---------------------------------------------------------------------------


def _seed_one_candidate(store: CycleAcquisitionStore, docket_id: int) -> None:
    responses = _empty_search_responses()
    responses[0] = _search_response(
        term=_TERMS[0],
        results=[
            {
                "id": 9001,
                "docket_id": docket_id,
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            }
        ],
    )
    run_discover(
        store,
        batch_id="batch-002",
        client=_anonymous_client(responses),
        decision_window_start=date(2026, 6, 30),
        decision_window_end=date(2026, 7, 12),
    )


def test_run_observe_fails_closed_without_token(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        # Anonymous client (no token) must fail closed before any network call.
        with pytest.raises(
            RecapReconstructionAuthError, match="COURTLISTENER_API_TOKEN"
        ):
            run_observe(
                store,
                batch_id="batch-002",
                client=_anonymous_client([]),
                eligibility_anchor=date(2026, 6, 30),
            )
    finally:
        store.close()


def test_run_observe_rejects_anchor_mismatching_frozen_policy(
    tmp_path: Path,
) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        with pytest.raises(
            RecapApiBatchDriverError, match="eligibility anchor mismatch"
        ):
            run_observe(
                store,
                batch_id="batch-002",
                client=_token_client([]),
                eligibility_anchor=date(2026, 7, 1),
            )
    finally:
        store.close()


def test_run_observe_accepts_and_is_resumable(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        client = _token_client(
            [
                _docket_response(555),
                _entries_response(
                    docket_id=555,
                    results=[
                        _motion_entry(555),
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
                ),
            ]
        )
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert tally.observed == 1
        assert tally.eligible == 1
        assert tally.skipped_already_observed == 0

        current = store.current_observation("courtlistener-docket-555")
        assert current is not None and current.state == "accepted"

        # Re-running with an empty client proves the observed candidate is
        # skipped and no second reconstruction is attempted.
        resume = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client([]),
            eligibility_anchor=date(2026, 6, 30),
        )
        assert resume.observed == 0
        assert resume.skipped_already_observed == 1
        assert resume.considered == 1
    finally:
        store.close()


def test_run_observe_enforces_frozen_window_end_from_config(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        # The docket's only MTD disposition is filed after the frozen window end
        # (2026-07-12), so run_observe -- which reads the upper bound from the
        # frozen batch config -- must not accept it.
        client = _token_client(
            [
                _docket_response(555),
                _entries_response(
                    docket_id=555,
                    results=[
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": (
                                "ORDER granting defendant's motion to dismiss"
                            ),
                            "date_filed": "2026-07-20",
                        }
                    ],
                ),
            ]
        )
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=client,
            eligibility_anchor=date(2026, 6, 30),
        )
    finally:
        store.close()
    assert tally.observed == 1
    assert tally.eligible == 0
    assert sum(tally.excluded_by_reason.values()) == 1


def test_run_observe_excludes_prescreened_bankruptcy(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    responses = _empty_search_responses()
    responses[0] = _search_response(
        term=_TERMS[0],
        results=[
            {
                "id": 9001,
                "docket_id": 900,
                "description": "ORDER on motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysb",
                "docketNumber": "1:26-bk-00001",
                "caseName": "In re Debtor",
            }
        ],
    )
    try:
        run_discover(
            store,
            batch_id="batch-002",
            client=_anonymous_client(responses),
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
        # Empty reconstruction client proves the pre-screen excludes with no fetch.
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client([]),
            eligibility_anchor=date(2026, 6, 30),
        )
    finally:
        store.close()
    assert tally.observed == 1
    assert tally.eligible == 0
    assert tally.excluded_by_reason == {"bankruptcy_court": 1}


def test_run_observe_prefers_api_discovery_payload_over_seed_payload(
    tmp_path: Path,
) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        seed_batch_001_leads(
            store,
            batch_id="batch-002",
            leads=(
                Batch001Lead(
                    candidate_id="courtlistener-docket-555",
                    docket_id="555",
                    source_first_batch_id="batch-001",
                    case_name="United States v. Roe",
                    docket_number="1:26-cr-00001",
                    court_id="nysd",
                ),
            ),
        )
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client(
                [
                    _docket_response(555),
                    _entries_response(
                        docket_id=555,
                        results=[
                            _motion_entry(555),
                            {
                                "id": 7002,
                                "docket": 555,
                                "entry_number": 40,
                                "description": "ORDER granting motion to dismiss",
                                "date_filed": "2026-07-05",
                            },
                        ],
                    ),
                ]
            ),
            eligibility_anchor=date(2026, 6, 30),
        )
    finally:
        store.close()

    assert tally.eligible == 1
    assert tally.excluded_by_reason == {}


# ---------------------------------------------------------------------------
# seed-batch-001-leads.
# ---------------------------------------------------------------------------


def _build_batch_001_store(tmp_path: Path) -> Path:
    """Build a batch-001-shaped store: one enriched (observed) + two failures."""

    path = tmp_path / "batch-001.sqlite3"
    store = CycleAcquisitionStore(path)
    store.ensure_cycle({"schema_version": "test"})
    store.ensure_batch("batch-001", {"provider": "firecrawl", "batch": "001"})
    term = "motion to dismiss"
    store.ensure_terms("batch-001", (term,))
    store.commit_search_page(
        "batch-001",
        term,
        None,
        [
            {
                "provider_hit_id": "hit-enriched",
                "candidate_id": "courtlistener-docket-100",
                "payload": {
                    "docket_id": "100",
                    "case_name": "Enriched v. Success",
                },
            },
            {
                "provider_hit_id": "hit-fail-a",
                "candidate_id": "courtlistener-docket-200",
                "payload": {
                    "docket_id": "200",
                    "case_name": "Failed v. Enrichment",
                },
            },
            {
                "provider_hit_id": "hit-fail-b",
                "candidate_id": "courtlistener-docket-300",
                "payload": {
                    "docket_id": "300",
                    "case_name": "United States v. Roe",
                },
            },
        ],
        next_cursor=None,
        terminal_status="exhausted",
    )
    # Only docket 100 was successfully enriched + screened -> current observation.
    # Dockets 200 and 300 failed Case.dev enrichment -> no observation (NULL).
    store.record_observation(
        "courtlistener-docket-100",
        batch_id="batch-001",
        state="excluded",
        reason_code="strict_clean_screen_failed",
        evidence={"note": "enriched then screened out"},
    )
    store.close()
    return path


def test_read_batch_001_failures_selects_unresolved_candidates(tmp_path: Path) -> None:
    source = _build_batch_001_store(tmp_path)
    leads = read_batch_001_enrichment_failure_leads(source)
    assert [lead.docket_id for lead in leads] == ["200", "300"]
    assert all(lead.source_first_batch_id == "batch-001" for lead in leads)
    assert leads[0].candidate_id == "courtlistener-docket-200"


def test_read_batch_001_failures_uses_candidate_first_batch_payload(
    tmp_path: Path,
) -> None:
    source = _build_batch_001_store(tmp_path)
    with CycleAcquisitionStore(source) as store:
        store.ensure_batch("batch-002", {"provider": "other", "batch": "002"})
        store.ensure_terms("batch-002", ("other term",))
        store.commit_search_page(
            "batch-002",
            "other term",
            None,
            [
                {
                    "provider_hit_id": "wrong-batch-hit",
                    "candidate_id": "courtlistener-docket-200",
                    "payload": {
                        "docket_id": "999",
                        "case_name": "Wrong Batch v. Payload",
                    },
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )

    leads = read_batch_001_enrichment_failure_leads(source, source_batch_id="batch-001")
    lead = next(
        lead for lead in leads if lead.candidate_id == "courtlistener-docket-200"
    )
    assert lead.docket_id == "200"
    assert lead.case_name == "Failed v. Enrichment"


def test_read_batch_001_failures_missing_store(tmp_path: Path) -> None:
    with pytest.raises(RecapApiBatchDriverError, match="not found"):
        read_batch_001_enrichment_failure_leads(tmp_path / "nope.sqlite3")


def test_seed_batch_001_leads_is_idempotent_and_observable(tmp_path: Path) -> None:
    source = _build_batch_001_store(tmp_path)
    leads = read_batch_001_enrichment_failure_leads(source)

    store = _fresh_store(tmp_path, "batch-002.sqlite3")
    try:
        # discover must run first to attach the batch config.
        run_discover(
            store,
            batch_id="batch-002",
            client=_anonymous_client(_empty_search_responses()),
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
        first = seed_batch_001_leads(store, batch_id="batch-002", leads=leads)
        assert first.leads_seeded == 2
        assert first.already_seeded is False

        # Idempotent: re-seeding adds nothing.
        second = seed_batch_001_leads(store, batch_id="batch-002", leads=leads)
        assert second.leads_seeded == 0
        assert second.already_seeded is True

        # Provenance is recorded on the seeded hit payloads.
        hits = {
            hit.candidate_id: hit.payload
            for hit in store.candidate_discovery_hits("batch-002")
        }
        prov = hits["courtlistener-docket-200"]["reobservation_provenance"]
        assert prov["failure_class"] == "case_dev_enrichment_failure"
        assert prov["source_first_batch_id"] == "batch-001"

        # docket 300 (United States v.) pre-screens as criminal without a fetch;
        # docket 200 reconstructs. observe covers both seeded leads.
        client = _token_client(
            [
                _docket_response(200),
                _entries_response(
                    docket_id=200,
                    results=[
                        _motion_entry(200, entry_id=8000),
                        {
                            "id": 8001,
                            "docket": 200,
                            "entry_number": 12,
                            "description": (
                                "ORDER granting defendant's motion to dismiss"
                            ),
                            "date_filed": "2026-07-06",
                        },
                    ],
                ),
            ]
        )
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=client,
            eligibility_anchor=date(2026, 6, 30),
        )
        assert tally.observed == 2
        assert tally.eligible == 1
        assert tally.excluded_by_reason == {"criminal_case": 1}
    finally:
        store.close()


def test_empty_seed_does_not_prevent_corrected_rerun(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path, "batch-002.sqlite3")
    try:
        run_discover(
            store,
            batch_id="batch-002",
            client=_anonymous_client(_empty_search_responses()),
            decision_window_start=date(2026, 6, 30),
            decision_window_end=date(2026, 7, 12),
        )
        empty = seed_batch_001_leads(store, batch_id="batch-002", leads=())
        assert empty.leads_seeded == 0
        assert empty.already_seeded is False
        assert (
            store.term_progress(
                "batch-002", "batch-001-case-dev-reobservation"
            ).terminal_status
            is None
        )

        corrected = seed_batch_001_leads(
            store,
            batch_id="batch-002",
            leads=(
                Batch001Lead(
                    candidate_id="courtlistener-docket-555",
                    docket_id="555",
                    source_first_batch_id="batch-001",
                    case_name="Acme Corp v. Roe",
                    docket_number="1:26-cv-00001",
                    court_id="nysd",
                ),
            ),
        )
        assert corrected.leads_seeded == 1
        assert corrected.already_seeded is False
    finally:
        store.close()


def test_seed_requires_attached_batch(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path, "batch-002.sqlite3")
    try:
        with pytest.raises(KeyError):
            seed_batch_001_leads(
                store,
                batch_id="batch-002",
                leads=(
                    Batch001Lead(
                        candidate_id="courtlistener-docket-1",
                        docket_id="1",
                        source_first_batch_id="batch-001",
                        case_name=None,
                        docket_number=None,
                        court_id=None,
                    ),
                ),
            )
    finally:
        store.close()


def test_observe_paces_with_injected_clock(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        slept: list[float] = []
        pacer = RequestPacer(
            min_interval_seconds=1.0,
            clock=lambda: 0.0,
            sleep=slept.append,
        )
        client = _token_client(
            [
                _docket_response(555),
                _entries_response(
                    docket_id=555,
                    results=[
                        {
                            "id": 7002,
                            "docket": 555,
                            "entry_number": 40,
                            "description": "ORDER granting motion to dismiss",
                            "date_filed": "2026-07-05",
                        }
                    ],
                ),
            ]
        )
        run_observe(
            store,
            batch_id="batch-002",
            client=client,
            eligibility_anchor=date(2026, 6, 30),
            pacer=pacer,
        )
        # The pacer waited between the docket fetch and the entries fetch.
        assert slept and all(s == 1.0 for s in slept)
    finally:
        store.close()
