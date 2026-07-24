"""Tests for the batch-002 RECAP API driver (discover / observe / seed)."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import legalforecast.ingestion.recap_api_batch_driver as recap_api_batch_driver
import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    DIRECT_SEARCH_CYCLE_REBIND_PROVENANCE_SCHEMA,
    DIRECT_SEARCH_CYCLE_REBIND_TERM,
    DIRECT_SEARCH_NOVEL_TRANSFER_TERM,
    DIRECT_SEARCH_PRIORITY_TRANCHE_TERM,
    DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA,
    DIRECT_SEARCH_TRANSFER_TERM,
    Batch001Lead,
    RecapApiBatchDriverError,
    materialize_direct_search_priority_tranche,
    read_batch_001_enrichment_failure_leads,
    read_saturated_direct_search_leads,
    read_verified_priority_dedupe_snapshots,
    rebind_direct_search_leads,
    run_discover,
    run_observe,
    seed_batch_001_leads,
    seed_direct_search_leads,
    seed_novel_direct_search_leads,
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


def test_run_observe_explicitly_refreshes_only_selected_refreshable_reason(
    tmp_path: Path,
) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        stale = store.record_observation(
            "courtlistener-docket-555",
            batch_id="batch-002",
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={"reason": "no_target_motion"},
            observed_at="2026-07-01T00:00:00+00:00",
        )
        skipped = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client([]),
            eligibility_anchor=date(2026, 6, 30),
        )
        assert skipped.observed == 0
        assert skipped.skipped_already_observed == 1

        refreshed = run_observe(
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
                                "description": (
                                    "ORDER granting defendant's motion to dismiss "
                                    "the complaint"
                                ),
                                "date_filed": "2026-07-05",
                            },
                        ],
                    ),
                ]
            ),
            eligibility_anchor=date(2026, 6, 30),
            refresh_reason_codes=("strict_clean_screen_failed",),
            refresh_campaign_cutoff="2026-07-10T00:00:00+00:00",
        )
        assert refreshed.observed == 1
        current = store.current_observation("courtlistener-docket-555")
        assert current is not None and current.state == "accepted"
        assert current.supersedes_observation_id == stale.observation_id
    finally:
        store.close()


def test_run_observe_revalidates_named_accepted_candidate(tmp_path: Path) -> None:
    store = _fresh_store(tmp_path)
    try:
        _seed_one_candidate(store, 555)
        stale = store.record_observation(
            "courtlistener-docket-555",
            batch_id="batch-002",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screening_kernel": "before-correction"},
            observed_at="2026-07-01T00:00:00+00:00",
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
                                "description": (
                                    "ORDER granting defendant's motion to dismiss "
                                    "the complaint"
                                ),
                                "date_filed": "2026-07-05",
                            },
                        ],
                    ),
                ]
            ),
            eligibility_anchor=date(2026, 6, 30),
            revalidate_candidate_ids=("courtlistener-docket-555",),
            refresh_campaign_cutoff="2026-07-10T00:00:00+00:00",
            limit=1,
        )

        assert tally.observed == 1
        current = store.current_observation("courtlistener-docket-555")
        assert current is not None and current.state == "accepted"
        assert current.observation_id != stale.observation_id
        assert current.supersedes_observation_id == stale.observation_id
    finally:
        store.close()


def test_limited_refresh_campaign_advances_past_already_refreshed_candidate(
    tmp_path: Path,
) -> None:
    store = _fresh_store(tmp_path)
    responses = _empty_search_responses()
    responses[0] = _search_response(
        term=_TERMS[0],
        results=[
            {
                "id": 9001 + docket_id,
                "docket_id": docket_id,
                "entry_number": "20",
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": f"1:26-cv-{docket_id:05d}",
                "caseName": "Acme Corp v. Roe",
            }
            for docket_id in (555, 556)
        ],
    )
    run_discover(
        store,
        batch_id="batch-002",
        client=_anonymous_client(responses),
        decision_window_start=date(2026, 6, 30),
        decision_window_end=date(2026, 7, 12),
    )
    try:
        for docket_id in (555, 556):
            store.record_observation(
                f"courtlistener-docket-{docket_id}",
                batch_id="batch-002",
                state="excluded",
                reason_code="strict_clean_screen_failed",
                evidence={"reason": "old-kernel"},
                observed_at="2026-07-01T00:00:00+00:00",
            )
        cutoff = "2026-07-10T00:00:00+00:00"
        observed_ids: list[int] = []
        for docket_id in (556, 555):
            client = _token_client(
                [
                    _docket_response(docket_id),
                    _entries_response(
                        docket_id=docket_id,
                        results=[
                            _motion_entry(docket_id),
                            {
                                "id": 8000 + docket_id,
                                "docket": docket_id,
                                "entry_number": 40,
                                "description": (
                                    "ORDER granting defendant's motion to dismiss "
                                    "the complaint"
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
                limit=1,
                refresh_reason_codes=("strict_clean_screen_failed",),
                refresh_campaign_cutoff=cutoff,
            )
            assert tally.observed == 1
            assert client.request_count == 2
            observed_ids.append(docket_id)

        final = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client([]),
            eligibility_anchor=date(2026, 6, 30),
            limit=1,
            refresh_reason_codes=("strict_clean_screen_failed",),
            refresh_campaign_cutoff=cutoff,
        )
        assert final.observed == 0
        assert final.skipped_already_observed == 2
        assert observed_ids == [556, 555]
    finally:
        store.close()


def test_run_observe_prioritizes_cheaper_recent_candidates_deterministically(
    tmp_path: Path,
) -> None:
    store = _fresh_store(tmp_path)
    responses = _empty_search_responses()
    responses[0] = _search_response(
        term=_TERMS[0],
        results=[
            {
                "id": 9001,
                "docket_id": 999,
                "entry_number": "650",
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-06",
                "court_id": "nysd",
                "docketNumber": "1:20-cv-00001",
                "caseName": "Old Corp v. Roe",
            },
            {
                "id": 9002,
                "docket_id": 555,
                "entry_number": "20",
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00002",
                "caseName": "Small Corp v. Roe",
            },
            {
                "id": 9003,
                "docket_id": 777,
                "entry_number": "20",
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-06",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00003",
                "caseName": "Recent Corp v. Roe",
            },
        ],
    )
    run_discover(
        store,
        batch_id="batch-002",
        client=_anonymous_client(responses),
        decision_window_start=date(2026, 6, 30),
        decision_window_end=date(2026, 7, 12),
    )
    try:
        tally = run_observe(
            store,
            batch_id="batch-002",
            client=_token_client(
                [
                    _docket_response(777),
                    _entries_response(
                        docket_id=777,
                        results=[
                            _motion_entry(777),
                            {
                                "id": 7002,
                                "docket": 777,
                                "entry_number": 40,
                                "description": (
                                    "ORDER granting defendant's motion to dismiss "
                                    "the complaint"
                                ),
                                "date_filed": "2026-07-06",
                            },
                        ],
                    ),
                ]
            ),
            eligibility_anchor=date(2026, 6, 30),
            limit=1,
        )
        assert tally.observed == 1
        assert store.current_observation("courtlistener-docket-777") is not None
        assert store.current_observation("courtlistener-docket-555") is None
        assert store.current_observation("courtlistener-docket-999") is None
    finally:
        store.close()


def test_run_observe_prioritizes_frozen_clean_signal_and_free_evidence_before_cost(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    template = next(lead for lead in source.leads if lead.docket_id == "200")

    def lead(
        docket_id: int,
        *,
        entry_number: int,
        description: str,
        is_available: bool,
    ) -> recap_api_batch_driver.DirectSearchLead:
        evidence: dict[str, object] = {
            "entry_number": entry_number,
            "description": description,
            "entry_date_filed": "2026-07-06",
            "is_available": is_available,
        }
        return replace(
            template,
            docket_id=str(docket_id),
            court_id="nysd",
            docket_number=f"1:26-cv-{docket_id:05d}",
            case_name=f"Candidate {docket_id} v. Roe",
            decision_entry_evidence=evidence,
            priority_decision_evidence=evidence,
        )

    cheap_generic = lead(
        555,
        entry_number=5,
        description="Motion to Dismiss",
        is_available=False,
    )
    costly_clean_free = lead(
        777,
        entry_number=500,
        description="ORDER granting defendant's motion to dismiss",
        is_available=True,
    )
    leads = (cheap_generic, costly_clean_free)
    candidate_set_sha256 = recap_api_batch_driver._lead_set_sha256(leads)
    lineage = dict(source.source_lineage_commitments or {})
    lineage.pop("source_lineage_commitment_sha256")
    lineage.update(
        {
            "source_candidate_count": len(leads),
            "source_candidate_set_sha256": candidate_set_sha256,
            "selected_candidate_count": len(leads),
            "selected_candidate_set_sha256": candidate_set_sha256,
        }
    )
    lineage["source_lineage_commitment_sha256"] = (
        recap_api_batch_driver._canonical_record_sha256(lineage)
    )
    priority_source = replace(
        source,
        leads=leads,
        source_candidate_set_sha256=candidate_set_sha256,
        source_lineage_commitments=lineage,
    )

    batch_id = "priority-observe"
    store = CycleAcquisitionStore(path)
    try:
        materialize_direct_search_priority_tranche(
            store,
            batch_id=batch_id,
            source=priority_source,
            tranche_size=2,
        )
        client = _token_client(
            [
                _docket_response(777),
                _entries_response(
                    docket_id=777,
                    results=[
                        _motion_entry(777),
                        {
                            "id": 7002,
                            "docket": 777,
                            "entry_number": 500,
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
            batch_id=batch_id,
            client=client,
            eligibility_anchor=date(2026, 6, 30),
            limit=1,
        )
        assert tally.observed == 1
        assert store.current_observation("courtlistener-docket-777") is not None
        assert store.current_observation("courtlistener-docket-555") is None
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


# ---------------------------------------------------------------------------
# seed-direct-search.
# ---------------------------------------------------------------------------


def _build_saturated_direct_search_store(
    tmp_path: Path,
    *,
    second_term_exhausted: bool = True,
    mismatched_docket_id: bool = False,
    nonnumeric_candidate_id: bool = False,
) -> Path:
    """Build a small CourtListener-authoritative direct-search source."""

    path = tmp_path / "direct-search.sqlite3"
    store = CycleAcquisitionStore(path)
    store.ensure_cycle({"schema_version": "test", "eligibility_anchor": "2026-06-30"})
    terms = ("motion to dismiss", "judgment on the pleadings")
    store.ensure_batch(
        "direct-search",
        {
            "provider": "courtlistener",
            "search_window_start": "2026-07-11",
            "search_window_end": "2026-07-15",
            "query_terms": list(terms),
            "search_page_size": 100,
        },
    )
    store.ensure_terms("direct-search", terms)
    candidate_id = "not-numeric" if nonnumeric_candidate_id else "200"
    store.commit_search_page(
        "direct-search",
        terms[0],
        None,
        [
            {
                "provider_hit_id": "hit-200-high",
                "candidate_id": candidate_id,
                "payload": {
                    "docket_id": "201" if mismatched_docket_id else candidate_id,
                    "court_id": "nysd",
                    "docket_number": "1:26-cv-00200",
                    "case_name": "Alpha LLC v. Beta Inc.",
                    "opinion_resolution_evidence": {
                        "schema_version": "legalforecast.opinion_recap_resolution.v1",
                        "source_opinion": {"candidate_id": "900"},
                        "resolved_recap": {"docket_id": candidate_id},
                    },
                    "recap_documents": [
                        {
                            "id": 8200,
                            "docket_entry_id": 7200,
                            "entry_number": 70,
                            "document_number": "70",
                            "description": "ORDER granting motion to dismiss",
                            "entry_date_filed": "2026-07-14",
                            "absolute_url": "/api/rest/v4/recap-documents/8200/",
                            "is_available": True,
                        }
                    ],
                },
            },
            {
                "provider_hit_id": "hit-300-criminal",
                "candidate_id": "300",
                "payload": {
                    "docket_id": "300",
                    "court_id": "nysd",
                    "docket_number": "1:26-cr-00300",
                    "case_name": "United States v. Roe",
                    "recap_documents": [],
                },
            },
        ],
        next_cursor=None,
        terminal_status="exhausted",
    )
    store.commit_search_page(
        "direct-search",
        terms[1],
        None,
        [
            {
                # A second hit for docket 200 carries the lower triggering entry.
                # Transfer must aggregate across terms, not keep the first row.
                "provider_hit_id": "hit-200-low",
                "candidate_id": "200",
                "payload": {
                    "docket_id": "200",
                    "court_id": "nysd",
                    "docket_number": "1:26-cv-00200",
                    "case_name": "Alpha LLC v. Beta Inc.",
                    "recap_documents": [
                        {
                            "id": 8100,
                            "docket_entry_id": 7100,
                            "entry_number": 19,
                            "document_number": "19",
                            "description": "Motion to dismiss",
                            "entry_date_filed": "2026-07-13",
                            "absolute_url": "/api/rest/v4/recap-documents/8100/",
                        },
                        {
                            # Invalid/non-positive ordinals cannot displace the
                            # minimum valid evidence.
                            "id": 8000,
                            "entry_number": 0,
                        },
                    ],
                },
            },
            {
                "provider_hit_id": "hit-400-large",
                "candidate_id": "400",
                "payload": {
                    "docket_id": "400",
                    "court_id": "cand",
                    "docket_number": "3:26-cv-00400",
                    "case_name": "Gamma Corp. v. Delta LLC",
                    "recap_documents": [
                        {
                            "id": 8400,
                            "docket_entry_id": 7400,
                            "entry_number": 501,
                            "document_number": "501",
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-07-15",
                            "absolute_url": "/api/rest/v4/recap-documents/8400/",
                        }
                    ],
                },
            },
        ],
        next_cursor=None if second_term_exhausted else "next-page",
        terminal_status="exhausted" if second_term_exhausted else None,
    )
    store.close()
    return path


def _build_saturated_opinion_search_store(tmp_path: Path) -> Path:
    """Build an opinion-search source whose bankruptcy summary is inconclusive."""

    path = tmp_path / "opinion-search.sqlite3"
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        term = '"Rule 7012" OR "motion to dismiss adversary complaint"'
        store.ensure_batch(
            "opinion-search",
            {
                "provider": "courtlistener",
                "search_type": "o",
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-15",
                "query_terms": [term],
                "page_size": 20,
            },
        )
        store.ensure_terms("opinion-search", (term,))
        store.commit_search_page(
            "opinion-search",
            term,
            None,
            [
                {
                    "provider_hit_id": "10026367",
                    "candidate_id": "70649963",
                    "payload": {
                        "docket_id": "70649963",
                        "court_id": "nysb",
                        # Opinion summaries can expose a court-local number and
                        # an estate-style cluster caption even when the linked
                        # authoritative docket is an adversary proceeding.
                        "docket_number": "26-01028",
                        "case_name": "In re Example Debtor",
                        "opinion_discovery_evidence": {
                            "cluster_id": "10026367",
                            "absolute_url": "/opinion/10026367/example/",
                            "date_filed": "2026-07-10",
                        },
                    },
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _build_prior_screening_snapshot(
    tmp_path: Path,
    *,
    name: str,
    candidate_ids: tuple[str, ...],
    cross_cycle: bool = False,
    complete: bool = True,
) -> tuple[Path, str]:
    store_path = tmp_path / f"{name}.sqlite3"
    output_root = tmp_path / f"{name}-snapshots"
    with CycleAcquisitionStore(store_path) as store:
        policy: dict[str, object] = {
            "schema_version": "test",
            "eligibility_anchor": "2026-06-30",
        }
        if cross_cycle:
            policy["historical_cycle_marker"] = name
        store.ensure_cycle(policy)
        store.ensure_batch(name, {"provider": "courtlistener", "name": name})
        store.ensure_terms(name, ("screen",))
        store.commit_search_page(
            name,
            "screen",
            None,
            [
                {
                    "provider_hit_id": f"{name}-{candidate_id}",
                    "candidate_id": candidate_id,
                    "payload": {"candidate_id": candidate_id},
                }
                for candidate_id in candidate_ids
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        for candidate_id in candidate_ids:
            store.record_observation(
                candidate_id,
                batch_id=name,
                state="excluded",
                reason_code="decision_before_release_anchor",
                evidence={
                    "candidate_id": candidate_id,
                    "decision_date": "2026-06-29",
                },
            )
        snapshot = store.export_snapshot(
            output_root,
            snapshot_id=f"{name}-snapshot",
            batch_id=name,
            complete=complete,
        )
    manifest_hash = hashlib.sha256(
        (snapshot / "manifest.json").read_bytes()
    ).hexdigest()
    return snapshot, manifest_hash


def test_read_saturated_direct_search_aggregates_minimum_entry_evidence(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)

    source = read_saturated_direct_search_leads(path, source_batch_id="direct-search")

    assert source.source_search_type is None
    assert source.source_batch_id == "direct-search"
    assert source.search_window_start == date(2026, 7, 11)
    assert source.search_window_end == date(2026, 7, 15)
    assert [lead.docket_id for lead in source.leads] == ["200", "300", "400"]
    assert len(source.source_candidate_set_sha256) == 64
    lead_200 = source.leads[0]
    assert lead_200.candidate_id == "courtlistener-docket-200"
    assert lead_200.source_provider_hit_id == "hit-200-low"
    assert lead_200.source_query_term == "judgment on the pleadings"
    assert lead_200.decision_entry_evidence == {
        "id": 8100,
        "docket_entry_id": 7100,
        "entry_number": 19,
        "document_number": "19",
        "description": "Motion to dismiss",
        "entry_date_filed": "2026-07-13",
        "absolute_url": "/api/rest/v4/recap-documents/8100/",
    }
    assert lead_200.priority_decision_evidence == {
        "id": 8200,
        "docket_entry_id": 7200,
        "entry_number": 70,
        "document_number": "70",
        "description": "ORDER granting motion to dismiss",
        "entry_date_filed": "2026-07-14",
        "absolute_url": "/api/rest/v4/recap-documents/8200/",
        "is_available": True,
    }
    assert source.leads[1].decision_entry_evidence is None
    assert source.leads[2].decision_entry_evidence is not None
    assert source.leads[2].decision_entry_evidence["entry_number"] == 501


@pytest.mark.parametrize(
    ("description", "expected"),
    (
        ("MOTION to Dismiss", (2, "generic_motion_or_brief")),
        (
            "MOTION for Judgment on the Pleadings under Rule 12(c)",
            (2, "generic_motion_or_brief"),
        ),
        (
            "Memorandum in Support of Motion to Dismiss",
            (2, "generic_motion_or_brief"),
        ),
        (
            "Proposed Order Granting Motion to Dismiss",
            (2, "generic_motion_or_brief"),
        ),
        (
            "Standing Order Regarding Motions to Dismiss",
            (2, "generic_motion_or_brief"),
        ),
        (
            "ORDER granting motion 12 to extend the discovery deadline",
            (2, "generic_motion_or_brief"),
        ),
        (
            "ORDER granting motion for protective order. Motion to Dismiss "
            "remains pending.",
            (2, "generic_motion_or_brief"),
        ),
        (
            "ORDER: Motion to Enlarge Page Limits for briefing is GRANTED. "
            "Defendants may file an Omnibus Motion to Dismiss.",
            (2, "generic_motion_or_brief"),
        ),
        (
            "REPLY to response to Motion to Dismiss (Exhibit: prior Court Order)",
            (2, "generic_motion_or_brief"),
        ),
        (
            "The motion to transfer is granted, and the Court leaves for the "
            "transferee court the pending motion to dismiss.",
            (2, "generic_motion_or_brief"),
        ),
        (
            "Plaintiff is hereby NOTIFIED that Defendant filed a motion to "
            "dismiss that, if granted, could result in dismissal.",
            (2, "generic_motion_or_brief"),
        ),
        (
            "ORDER granting Motion for Judgment on the Pleadings under Rule 12(c)",
            (0, "action_linked_disposition_or_substantive_recommendation"),
        ),
        (
            "ORDER dismissing Count I under Rule 12(b)(6)",
            (0, "action_linked_disposition_or_substantive_recommendation"),
        ),
        (
            "ORDER dismissing adversary complaint under Rule 7012",
            (0, "action_linked_disposition_or_substantive_recommendation"),
        ),
        (
            "REPORT AND RECOMMENDATION re Motion to Dismiss",
            (0, "action_linked_disposition_or_substantive_recommendation"),
        ),
        (
            "Order on Motion to Dismiss",
            (1, "anchored_adjudicative_event"),
        ),
    ),
)
def test_priority_signal_distinguishes_decisions_from_filing_descriptions(
    description: str,
    expected: tuple[int, str],
) -> None:
    assert (
        recap_api_batch_driver._priority_signal_for_evidence(
            {"description": description}
        )
        == expected
    )


def test_priority_evidence_prefers_actual_order_over_newer_motion() -> None:
    actual_order = {
        "entry_number": 40,
        "description": "ORDER granting motion to dismiss",
        "entry_date_filed": "2026-07-12",
        "is_available": True,
    }
    newer_motion = {
        "entry_number": 50,
        "description": "MOTION to Dismiss",
        "entry_date_filed": "2026-07-15",
        "is_available": True,
    }

    selected = min(
        (newer_motion, actual_order),
        key=lambda evidence: recap_api_batch_driver._priority_evidence_sort_key(
            evidence,
            window_start=date(2026, 7, 11),
            window_end=date(2026, 7, 15),
            eligibility_anchor="2026-06-30",
        ),
    )

    assert selected is actual_order


def test_priority_ranking_defers_known_structural_exclusions_without_dropping_them(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    civil = next(lead for lead in source.leads if lead.docket_id == "200")
    criminal = replace(
        next(lead for lead in source.leads if lead.docket_id == "300"),
        priority_decision_evidence={
            "entry_number": 90,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-15",
            "is_available": True,
        },
    )
    adversary = replace(
        next(lead for lead in source.leads if lead.docket_id == "400"),
        court_id="nysb",
        docket_number="6:26-ap-00400",
        case_name="Trustee v. Defendant LLC",
        priority_decision_evidence={
            "entry_number": 80,
            "description": "ORDER dismissing adversary complaint under Rule 7012",
            "entry_date_filed": "2026-07-15",
            "is_available": True,
        },
    )
    bankruptcy_main = replace(
        adversary,
        docket_id="500",
        docket_number="6:26-bk-00500",
        case_name="In re Example Debtor",
        priority_decision_evidence={
            "entry_number": 100,
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-15",
            "is_available": True,
        },
    )
    rank_source = replace(
        source,
        leads=(civil, criminal, adversary, bankruptcy_main),
    )

    ranked, records = recap_api_batch_driver._rank_direct_search_leads(rank_source)

    assert tuple(lead.docket_id for lead in ranked) == ("400", "200", "300", "500")
    assert {lead.docket_id for lead in ranked} == {"200", "300", "400", "500"}
    by_candidate = {row["candidate_id"]: row for row in records}
    assert (
        by_candidate["courtlistener-docket-400"]["prescreen_exclusion_reason"] is None
    )
    assert by_candidate["courtlistener-docket-400"]["structural_rank"] == 0
    assert (
        by_candidate["courtlistener-docket-300"]["prescreen_exclusion_reason"]
        == "criminal_case"
    )
    assert by_candidate["courtlistener-docket-300"]["structural_rank"] == 1
    assert (
        by_candidate["courtlistener-docket-500"]["prescreen_exclusion_reason"]
        == "bankruptcy_court"
    )
    assert by_candidate["courtlistener-docket-500"]["structural_rank"] == 1


def test_priority_ranking_demotes_obvious_low_yield_metadata_without_excluding(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    template = next(lead for lead in source.leads if lead.docket_id == "200")

    def lead(
        docket_id: int,
        *,
        case_name: str = "Alpha LLC v. Beta Inc.",
        court_id: str = "nysd",
        docket_number: str | None = None,
        description: str = "ORDER granting motion to dismiss",
    ) -> recap_api_batch_driver.DirectSearchLead:
        return replace(
            template,
            docket_id=str(docket_id),
            case_name=case_name,
            court_id=court_id,
            docket_number=docket_number or f"1:26-cv-{docket_id:05d}",
            priority_decision_evidence={
                "entry_number": 50,
                "description": description,
                "entry_date_filed": "2026-07-15",
                "is_available": True,
            },
        )

    retained = (
        lead(
            101,
            description=(
                "ORDER granting Motion for Judgment on the Pleadings under Rule 12(c)"
            ),
        ),
        lead(
            102,
            case_name="Trustee v. Defendant LLC",
            court_id="nysb",
            docket_number="6:26-ap-00102",
            description="ORDER dismissing adversary complaint under Rule 7012",
        ),
        lead(
            103,
            case_name="(PS) Smith v. Correctional Officer Jones",
            court_id="caed",
            description="ORDER granting motion to dismiss prisoner civil complaint",
        ),
        lead(
            104,
            description=(
                "ORDER granting motion to dismiss for lack of "
                "subject-matter jurisdiction"
            ),
        ),
    )
    demoted = (
        lead(201, case_name="(HC) Can Xol v. Warden"),
        lead(202, case_name="Ozturk v. Hyde", court_id="ca2"),
        lead(203, description="[Proposed] Order Granting Motion to Dismiss"),
        lead(
            204,
            description=(
                "ORDER approving stipulated voluntary dismissal and denying "
                "motion to dismiss as moot"
            ),
        ),
        lead(
            205,
            description=(
                "ORDER denying motion to dismiss as moot after amended complaint"
            ),
        ),
        lead(
            206,
            description=(
                "ORDER transferring case and denying pending motion to dismiss as moot"
            ),
        ),
        lead(
            207,
            description=(
                "ORDER under Rule 25 substituting successor and denying motion "
                "to dismiss with leave to refile"
            ),
        ),
        lead(
            208,
            case_name="United States v. Roe",
            docket_number="1:26-cr-00208",
        ),
        lead(
            209,
            case_name="In re Example Debtor",
            court_id="nysb",
            docket_number="1:26-bk-00209",
        ),
    )
    rank_source = replace(source, leads=(*demoted, *retained))

    ranked, records = recap_api_batch_driver._rank_direct_search_leads(rank_source)

    retained_ids = {lead.candidate_id for lead in retained}
    demoted_ids = {lead.candidate_id for lead in demoted}
    assert {lead.candidate_id for lead in ranked[: len(retained)]} == retained_ids
    assert {lead.candidate_id for lead in ranked[len(retained) :]} == demoted_ids
    assert {lead.candidate_id for lead in ranked} == retained_ids | demoted_ids
    assert len(ranked) == len(retained) + len(demoted)

    by_candidate = {row["candidate_id"]: row for row in records}
    assert {
        by_candidate[candidate_id]["clean_yield_demotion_rank"]
        for candidate_id in retained_ids
    } == {0}
    assert {
        by_candidate[candidate_id]["clean_yield_demotion_rank"]
        for candidate_id in demoted_ids
    } == {1}
    assert (
        by_candidate["courtlistener-docket-102"]["clean_yield_demotion_reason"]
        == "none"
    )
    assert (
        by_candidate["courtlistener-docket-103"]["clean_yield_demotion_reason"]
        == "none"
    )
    assert (
        by_candidate["courtlistener-docket-201"]["clean_yield_demotion_reason"]
        == "habeas_or_detention_metadata"
    )
    assert (
        by_candidate["courtlistener-docket-202"]["clean_yield_demotion_reason"]
        == "appellate_metadata"
    )
    assert (
        by_candidate["courtlistener-docket-208"]["clean_yield_demotion_reason"]
        == "criminal_metadata"
    )
    assert (
        by_candidate["courtlistener-docket-209"]["clean_yield_demotion_reason"]
        == "main_bankruptcy_metadata"
    )


def _priority_novel_source(
    tmp_path: Path, path: Path
) -> recap_api_batch_driver.DirectSearchSeedSource:
    raw_source = read_saturated_direct_search_leads(
        path, source_batch_id="direct-search"
    )
    snapshot, manifest_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="priority-prior",
        candidate_ids=("courtlistener-docket-999",),
    )
    prior = read_verified_priority_dedupe_snapshots(
        (snapshot,), expected_manifest_sha256=(manifest_hash,)
    )
    with CycleAcquisitionStore(path) as store:
        seed_novel_direct_search_leads(
            store,
            batch_id="priority-novel-source",
            source=raw_source,
            prior_snapshots=prior,
        )
    return read_saturated_direct_search_leads(
        path, source_batch_id="priority-novel-source"
    )


def test_priority_tranches_rank_only_and_preserve_exact_deferred_frontier(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)

    with CycleAcquisitionStore(path) as store:
        first = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-1",
            source=source,
            tranche_size=1,
        )
        again = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-1",
            source=source,
            tranche_size=1,
        )

    assert first.selected_candidate_ids == ("courtlistener-docket-200",)
    assert first.deferred_candidate_ids == (
        "courtlistener-docket-400",
        "courtlistener-docket-300",
    )
    assert first.selected_count + first.deferred_count == len(source.leads)
    assert first.frontier["deferred_disposition"] == "unscreened_not_excluded"
    assert first.frontier["global_source_saturated"] is False
    assert (
        first.frontier["strict_screen_is_sole_eligibility_and_exclusion_authority"]
        is True
    )
    ranking_rows = cast(list[dict[str, object]], first.frontier["ranking_records"])
    lead_200_rank = next(
        row for row in ranking_rows if row["candidate_id"] == "courtlistener-docket-200"
    )
    assert lead_200_rank["entry_number"] == 70
    assert lead_200_rank["is_available"] is True
    assert lead_200_rank["signal_reason"] == (
        "action_linked_disposition_or_substantive_recommendation"
    )
    assert first.frontier["source_candidate_set_sha256"] == (
        source.source_candidate_set_sha256
    )
    assert again.already_seeded is True
    assert again.frontier_sha256 == first.frontier_sha256
    with CycleAcquisitionStore(path) as store:
        config = store.batch_config("priority-1")
        assert config["provisional_frontier"] is True
        assert config["final_cohort_eligible"] is False
        assert config["full_source_terminal"] is False
        assert store.current_observation("courtlistener-docket-300") is None

    with CycleAcquisitionStore(path) as store:
        second = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-2",
            source=source,
            tranche_size=1,
            predecessor_frontier=first.frontier,
        )
    assert second.selected_candidate_ids == ("courtlistener-docket-400",)
    assert second.deferred_candidate_ids == ("courtlistener-docket-300",)
    assert second.cumulative_selected_count == 2
    with CycleAcquisitionStore(path) as store:
        terminal = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-3",
            source=source,
            tranche_size=1,
            predecessor_frontier=second.frontier,
        )
    assert terminal.deferred_count == 0
    assert terminal.frontier["ranking_frontier_exhausted"] is True
    assert terminal.frontier["global_source_saturated"] is False


def test_priority_tranche_reuses_exact_batch_local_terminal_observation(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    reused_candidate_id = "courtlistener-docket-200"
    with CycleAcquisitionStore(path) as store:
        store.record_observation(
            reused_candidate_id,
            batch_id=source.source_batch_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                "candidate_id": reused_candidate_id,
                "screen": {"eligible": True},
            },
            observed_at="2026-07-24T13:55:00+00:00",
        )
        first = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-reuse",
            source=source,
            tranche_size=1,
        )
        resumed = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-reuse",
            source=source,
            tranche_size=1,
        )
        client = _token_client([])
        tally = run_observe(
            store,
            batch_id="priority-reuse",
            client=client,
            eligibility_anchor=date(2026, 6, 30),
            limit=1,
        )
        config = store.batch_config("priority-reuse")

    assert first.selected_candidate_ids == (reused_candidate_id,)
    assert first.selected_count + first.deferred_count == len(source.leads)
    assert first.reused_observation_candidate_ids == (reused_candidate_id,)
    assert first.reused_observation_count == 1
    assert len(first.reused_observation_commitment_sha256) == 64
    assert first.frontier["reused_observation_candidate_ids"] == [reused_candidate_id]
    assert first.frontier["reused_observation_count"] == 1
    assert first.frontier["reused_observation_commitment_sha256"] == (
        first.reused_observation_commitment_sha256
    )
    assert config["reused_observation_candidate_ids"] == [reused_candidate_id]
    assert config["reused_observation_count"] == 1
    assert config["reused_observation_commitment_sha256"] == (
        first.reused_observation_commitment_sha256
    )
    assert resumed.already_seeded is True
    assert resumed.frontier_sha256 == first.frontier_sha256
    assert (
        resumed.reused_observation_commitment_sha256
        == first.reused_observation_commitment_sha256
    )
    assert tally.observed == 0
    assert tally.skipped_already_observed == 1
    assert client.request_count == 0


def test_priority_tranche_reuses_terminal_from_bound_priority_lineage(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    candidate_id = "courtlistener-docket-200"
    with CycleAcquisitionStore(path) as store:
        materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-earlier",
            source=source,
            tranche_size=1,
        )
        earlier = store.record_observation(
            candidate_id,
            batch_id="priority-earlier",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"candidate_id": candidate_id, "screen": {"eligible": True}},
        )
        later = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-later",
            source=source,
            tranche_size=1,
        )
        copied = store.batch_terminal_observation("priority-later", candidate_id)

    assert later.reused_observation_candidate_ids == (candidate_id,)
    assert copied is not None
    assert copied.supersedes_observation_id == earlier.observation_id


def test_priority_tranche_fails_closed_if_reused_observation_drifts(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    reused_candidate_id = "courtlistener-docket-200"
    with CycleAcquisitionStore(path) as store:
        store.record_observation(
            reused_candidate_id,
            batch_id=source.source_batch_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                "candidate_id": reused_candidate_id,
                "screen": {"eligible": True},
            },
            observed_at="2026-07-24T13:55:00+00:00",
        )
        materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-reuse-drift",
            source=source,
            tranche_size=1,
        )
        store.record_observation(
            reused_candidate_id,
            batch_id=source.source_batch_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={
                "candidate_id": reused_candidate_id,
                "screen": {"eligible": True, "revision": 2},
            },
            observed_at="2026-07-24T14:00:00+00:00",
        )

        with pytest.raises(
            (RecapApiBatchDriverError, ConfigMismatchError),
            match=r"(reused observation|batch config|commitment)",
        ):
            materialize_direct_search_priority_tranche(
                store,
                batch_id="priority-reuse-drift",
                source=source,
                tranche_size=1,
            )


def test_priority_tranche_rejects_downstream_accepted_observation(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    candidate_id = "courtlistener-docket-200"
    with CycleAcquisitionStore(path) as store:
        strict = store.record_observation(
            candidate_id,
            batch_id=source.source_batch_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"candidate_id": candidate_id, "screen": {"eligible": True}},
        )
        store.record_observation(
            candidate_id,
            batch_id=source.source_batch_id,
            state="accepted",
            reason_code="required_documents_complete",
            evidence={
                "candidate_id": candidate_id,
                "source_observation_id": strict.observation_id,
            },
        )
        with pytest.raises(
            RecapApiBatchDriverError,
            match="not a strict clean-screen terminal",
        ):
            materialize_direct_search_priority_tranche(
                store,
                batch_id="priority-downstream-reuse",
                source=source,
                tranche_size=1,
            )


def test_priority_tranche_rejects_wrong_lineage_observation(tmp_path: Path) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    candidate_id = "courtlistener-docket-200"
    with CycleAcquisitionStore(path) as store:
        source_hit = next(
            hit
            for hit in store.candidate_discovery_hits(source.source_batch_id)
            if hit.candidate_id == candidate_id
        )
        store.ensure_batch("unrelated-batch", {"provider": "test"})
        store.ensure_terms("unrelated-batch", ("test",))
        store.commit_search_page(
            "unrelated-batch",
            "test",
            None,
            (
                {
                    "provider_hit_id": "unrelated-200",
                    "candidate_id": candidate_id,
                    "payload": source_hit.payload,
                },
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            candidate_id,
            batch_id="unrelated-batch",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"candidate_id": candidate_id, "screen": {"eligible": True}},
        )
        with pytest.raises(
            RecapApiBatchDriverError,
            match=r"outside.*source lineage",
        ):
            materialize_direct_search_priority_tranche(
                store,
                batch_id="priority-wrong-lineage",
                source=source,
                tranche_size=1,
            )


def test_run_observe_rejects_priority_evidence_drift_before_transport(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    with CycleAcquisitionStore(path) as store:
        result = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-drift",
            source=source,
            tranche_size=1,
        )
    selected_id = result.selected_candidate_ids[0]

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT payload_json FROM discovery_hits
            WHERE batch_id = ? AND candidate_id = ?
            """,
            ("priority-drift", selected_id),
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row[0]))
        payload["priority_decision_evidence"]["description"] = (
            "[Proposed] Order Granting Motion to Dismiss"
        )
        connection.execute(
            """
            UPDATE discovery_hits SET payload_json = ?
            WHERE batch_id = ? AND candidate_id = ?
            """,
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "priority-drift",
                selected_id,
            ),
        )

    with CycleAcquisitionStore(path) as store:
        docket_id = int(selected_id.removeprefix("courtlistener-docket-"))
        client = _token_client(
            [
                _docket_response(docket_id),
                _entries_response(
                    docket_id=docket_id,
                    results=[
                        _motion_entry(docket_id),
                        {
                            "id": 9000 + docket_id,
                            "docket": docket_id,
                            "entry_number": 70,
                            "description": "ORDER granting motion to dismiss",
                            "date_filed": "2026-07-14",
                        },
                    ],
                ),
            ]
        )
        error: RecapApiBatchDriverError | None = None
        try:
            run_observe(
                store,
                batch_id="priority-drift",
                client=client,
                eligibility_anchor=date(2026, 6, 30),
                limit=1,
            )
        except RecapApiBatchDriverError as exc:
            error = exc
        assert client.request_count == 0
        assert error is not None
        assert re.search(
            r"priority.*(?:commitment|provenance|drift)",
            str(error),
        )


def test_run_observe_rejects_rehashed_priority_rank_drift_before_transport(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    with CycleAcquisitionStore(path) as store:
        result = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-rank-drift",
            source=source,
            tranche_size=1,
        )
    selected_id = result.selected_candidate_ids[0]

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT payload_json FROM discovery_hits
            WHERE batch_id = ? AND candidate_id = ?
            """,
            ("priority-rank-drift", selected_id),
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row[0]))
        provenance = payload["priority_dedupe_provenance"]
        provenance["ranking_record"]["signal_rank"] = 99
        provenance["ranking_record_sha256"] = (
            recap_api_batch_driver._canonical_record_sha256(
                provenance["ranking_record"]
            )
        )
        connection.execute(
            """
            UPDATE discovery_hits SET payload_json = ?
            WHERE batch_id = ? AND candidate_id = ?
            """,
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "priority-rank-drift",
                selected_id,
            ),
        )

    with CycleAcquisitionStore(path) as store:
        client = _token_client([])
        with pytest.raises(
            RecapApiBatchDriverError,
            match=r"priority.*ranking record.*invalid",
        ):
            run_observe(
                store,
                batch_id="priority-rank-drift",
                client=client,
                eligibility_anchor=date(2026, 6, 30),
                limit=1,
            )
        assert client.request_count == 0


def test_priority_tranche_rejects_stale_or_mutated_frontier(tmp_path: Path) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = _priority_novel_source(tmp_path, path)
    with CycleAcquisitionStore(path) as store:
        first = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-1",
            source=source,
            tranche_size=1,
        )
        mutated = dict(first.frontier)
        mutated["ranking_policy_sha256"] = "0" * 64
        with pytest.raises(RecapApiBatchDriverError, match=r"ranking policy|frontier"):
            materialize_direct_search_priority_tranche(
                store,
                batch_id="priority-2",
                source=source,
                tranche_size=1,
                predecessor_frontier=mutated,
            )

    with CycleAcquisitionStore(path) as store:
        progress = store.term_progress(
            "priority-1", DIRECT_SEARCH_PRIORITY_TRANCHE_TERM
        )
        assert progress.terminal_status == "exhausted"


def test_priority_tranche_rejects_source_without_manifest_pinned_dedupe(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(path, source_batch_id="direct-search")
    with CycleAcquisitionStore(path) as store:
        with pytest.raises(RecapApiBatchDriverError, match="manifest-pinned novel"):
            materialize_direct_search_priority_tranche(
                store,
                batch_id="priority-raw-source",
                source=source,
                tranche_size=1,
            )
        with pytest.raises(KeyError):
            store.batch_config("priority-raw-source")


def test_priority_tranche_accepts_rebind_then_manifest_pinned_novel_source(
    tmp_path: Path,
) -> None:
    old_path = _build_saturated_direct_search_store(tmp_path)
    old_source = read_saturated_direct_search_leads(
        old_path, source_batch_id="direct-search"
    )
    current_path = tmp_path / "current-cycle.sqlite3"
    with CycleAcquisitionStore(current_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "test",
                "eligibility_anchor": "2026-06-30",
                "current_screening_policy": True,
            }
        )
        rebind_direct_search_leads(
            store,
            batch_id="current-cycle-rebind",
            source=old_source,
        )
    rebound = read_saturated_direct_search_leads(
        current_path, source_batch_id="current-cycle-rebind"
    )
    assert rebound.source_candidate_set_sha256 == old_source.source_candidate_set_sha256

    snapshot, manifest_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="rebind-prior",
        candidate_ids=("courtlistener-docket-999",),
    )
    prior = read_verified_priority_dedupe_snapshots(
        (snapshot,), expected_manifest_sha256=(manifest_hash,)
    )
    with CycleAcquisitionStore(current_path) as store:
        seed_novel_direct_search_leads(
            store,
            batch_id="current-cycle-novel",
            source=rebound,
            prior_snapshots=prior,
        )
    novel = read_saturated_direct_search_leads(
        current_path, source_batch_id="current-cycle-novel"
    )
    with CycleAcquisitionStore(current_path) as store:
        result = materialize_direct_search_priority_tranche(
            store,
            batch_id="priority-1",
            source=novel,
            tranche_size=2,
        )
    assert result.selected_count == 2
    assert result.deferred_count == 1


def test_seed_opinion_bankruptcy_lead_defers_to_authoritative_docket(
    tmp_path: Path,
) -> None:
    path = _build_saturated_opinion_search_store(tmp_path)
    source = read_saturated_direct_search_leads(path, source_batch_id="opinion-search")

    assert source.source_search_type == "o"
    with CycleAcquisitionStore(path) as store:
        seed_direct_search_leads(
            store,
            batch_id="opinion-rest-screen",
            source=source,
        )
        config = store.batch_config("opinion-rest-screen")
        assert config["source_search_type"] == "o"
        payload = store.candidate_discovery_hits("opinion-rest-screen")[0].payload

    assert payload["court_id"] == "nysb"
    assert payload["prescreen_exclusion_reason"] is None


def test_seed_direct_search_freezes_lineage_canonicalizes_and_prescreens(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(path, source_batch_id="direct-search")

    with CycleAcquisitionStore(path) as store:
        first = seed_direct_search_leads(
            store,
            batch_id="rest-screen",
            source=source,
            page_size=2,
        )
        assert first.leads_selected == 3
        assert first.leads_seeded == 3
        assert first.already_seeded is False
        assert store.candidate_ids("rest-screen") == (
            "courtlistener-docket-200",
            "courtlistener-docket-300",
            "courtlistener-docket-400",
        )
        config = store.batch_config("rest-screen")
        assert config["discovery_mode"] == DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA
        assert config["source_batch_id"] == "direct-search"
        assert config["source_batch_digest"] == source.source_batch_digest
        assert (
            config["source_candidate_set_sha256"] == source.source_candidate_set_sha256
        )
        assert config["decision_window_start"] == "2026-07-11"
        assert config["decision_window_end"] == "2026-07-15"

        hits = {
            hit.candidate_id: hit.payload
            for hit in store.candidate_discovery_hits("rest-screen")
        }
        transferred = hits["courtlistener-docket-200"]
        assert transferred["docket_id"] == "200"
        assert transferred["decision_entry_evidence"]["entry_number"] == 19
        provenance = transferred["direct_search_provenance"]
        assert provenance["schema_version"] == (
            DIRECT_SEARCH_TRANSFER_PROVENANCE_SCHEMA
        )
        assert provenance["source_batch_id"] == "direct-search"
        assert provenance["source_provider_hit_id"] == "hit-200-low"
        assert (
            provenance["source_candidate_set_sha256"]
            == source.source_candidate_set_sha256
        )
        assert "source_cycle_hash" not in provenance
        assert "target_cycle_hash" not in provenance
        assert hits["courtlistener-docket-300"]["prescreen_exclusion_reason"] == (
            "criminal_case"
        )

        transcript = store.search_page_transcript("rest-screen")
        assert [len(cast(list[object], page["hits"])) for page in transcript] == [2, 1]
        assert [page["request_cursor"] for page in transcript] == [None, "2"]
        assert transcript[-1]["terminal_status"] == "exhausted"
        assert all(page["term"] == DIRECT_SEARCH_TRANSFER_TERM for page in transcript)

        repeated = seed_direct_search_leads(
            store,
            batch_id="rest-screen",
            source=source,
            page_size=2,
        )
        assert repeated.leads_seeded == 0
        assert repeated.already_seeded is True

        assert store.search_page_transcript("rest-screen") == transcript


def test_rebind_direct_search_transfers_identical_leads_across_frozen_cycles(
    tmp_path: Path,
) -> None:
    source_path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(
        source_path, source_batch_id="direct-search"
    )
    target_path = tmp_path / "current-cycle.sqlite3"
    with CycleAcquisitionStore(target_path) as target:
        target.ensure_cycle(
            {
                "schema_version": "test-current",
                "eligibility_anchor": "2026-06-30",
            }
        )
        result = rebind_direct_search_leads(
            target,
            batch_id="current-rest-screen",
            source=source,
            page_size=2,
        )
        assert result.source_cycle_hash == source.source_cycle_hash
        assert result.target_cycle_hash == target.cycle_hash
        assert result.source_cycle_hash != result.target_cycle_hash
        assert result.source_candidate_set_sha256 == (
            source.source_candidate_set_sha256
        )
        assert result.leads_selected == 3
        assert result.leads_seeded == 3

        config = target.batch_config("current-rest-screen")
        assert config["discovery_mode"] == (
            DIRECT_SEARCH_CYCLE_REBIND_PROVENANCE_SCHEMA
        )
        assert config["source_cycle_hash"] == source.source_cycle_hash
        assert config["target_cycle_hash"] == target.cycle_hash
        assert config["source_candidate_set_sha256"] == (
            source.source_candidate_set_sha256
        )
        assert config["provider_activity_requested"] is False
        assert config["provider_activity_executed"] is False

        hits = {
            hit.candidate_id: hit.payload
            for hit in target.candidate_discovery_hits("current-rest-screen")
        }
        provenance = hits["courtlistener-docket-200"]["direct_search_provenance"]
        assert provenance["schema_version"] == (
            DIRECT_SEARCH_CYCLE_REBIND_PROVENANCE_SCHEMA
        )
        assert provenance["source_cycle_hash"] == source.source_cycle_hash
        assert provenance["target_cycle_hash"] == target.cycle_hash
        assert hits["courtlistener-docket-200"]["decision_entry_evidence"] == (
            source.leads[0].decision_entry_evidence
        )
        assert hits["courtlistener-docket-200"]["opinion_resolution_evidence"] == (
            source.leads[0].opinion_resolution_evidence
        )
        assert all(
            page["term"] == DIRECT_SEARCH_CYCLE_REBIND_TERM
            for page in target.search_page_transcript("current-rest-screen")
        )


def test_rebind_direct_search_rejects_same_cycle_as_misleading(
    tmp_path: Path,
) -> None:
    source_path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(
        source_path, source_batch_id="direct-search"
    )
    with CycleAcquisitionStore(source_path) as store:
        with pytest.raises(RecapApiBatchDriverError, match="already matches"):
            rebind_direct_search_leads(
                store,
                batch_id="not-a-rebind",
                source=source,
            )


def test_seed_direct_search_resumes_after_a_committed_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(path, source_batch_id="direct-search")
    original_commit = CycleAcquisitionStore.commit_search_page
    committed = 0

    def interrupt_after_first_commit(
        store: CycleAcquisitionStore, *args: Any, **kwargs: Any
    ) -> Any:
        nonlocal committed
        result = original_commit(store, *args, **kwargs)
        committed += 1
        if committed == 1:
            raise RuntimeError("simulated interruption after durable commit")
        return result

    with CycleAcquisitionStore(path) as store:
        monkeypatch.setattr(
            CycleAcquisitionStore, "commit_search_page", interrupt_after_first_commit
        )
        with pytest.raises(RuntimeError, match="simulated interruption"):
            seed_direct_search_leads(
                store,
                batch_id="rest-screen-resume",
                source=source,
                page_size=2,
            )
        assert (
            store.term_progress(
                "rest-screen-resume", DIRECT_SEARCH_TRANSFER_TERM
            ).hit_count
            == 2
        )

        monkeypatch.setattr(
            CycleAcquisitionStore, "commit_search_page", original_commit
        )
        resumed = seed_direct_search_leads(
            store,
            batch_id="rest-screen-resume",
            source=source,
            page_size=2,
        )
        assert resumed.leads_seeded == 1
        assert resumed.already_seeded is False
        assert store.candidate_ids("rest-screen-resume") == (
            "courtlistener-docket-200",
            "courtlistener-docket-300",
            "courtlistener-docket-400",
        )
        assert [
            len(cast(list[object], page["hits"]))
            for page in store.search_page_transcript("rest-screen-resume")
        ] == [2, 1]


def test_read_saturated_direct_search_rejects_incomplete_source(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path, second_term_exhausted=False)
    with pytest.raises(RecapApiBatchDriverError, match="not fully exhausted"):
        read_saturated_direct_search_leads(path, source_batch_id="direct-search")


@pytest.mark.parametrize(
    ("builder_kwargs", "message"),
    [
        ({"nonnumeric_candidate_id": True}, "not numeric"),
        ({"mismatched_docket_id": True}, "docket id mismatch"),
    ],
)
def test_read_saturated_direct_search_rejects_bad_candidate_identity(
    tmp_path: Path,
    builder_kwargs: dict[str, bool],
    message: str,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path, **builder_kwargs)
    with pytest.raises(RecapApiBatchDriverError, match=message):
        read_saturated_direct_search_leads(path, source_batch_id="direct-search")


def test_seed_direct_search_rejects_source_target_batch_collision(
    tmp_path: Path,
) -> None:
    path = _build_saturated_direct_search_store(tmp_path)
    source = read_saturated_direct_search_leads(path, source_batch_id="direct-search")
    with CycleAcquisitionStore(path) as store:
        with pytest.raises(
            RecapApiBatchDriverError, match="source and target batch ids must differ"
        ):
            seed_direct_search_leads(
                store,
                batch_id="direct-search",
                source=source,
            )


def test_seed_novel_direct_search_commits_full_partition_and_cross_cycle_semantics(
    tmp_path: Path,
) -> None:
    source_path = _build_saturated_direct_search_store(tmp_path)
    same_cycle_path, same_cycle_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="same-cycle",
        candidate_ids=("courtlistener-docket-200", "unrelated-candidate"),
    )
    cross_cycle_path, cross_cycle_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="cross-cycle",
        candidate_ids=("courtlistener-docket-300",),
        cross_cycle=True,
    )
    source = read_saturated_direct_search_leads(
        source_path, source_batch_id="direct-search"
    )
    prior = read_verified_priority_dedupe_snapshots(
        (same_cycle_path, cross_cycle_path),
        expected_manifest_sha256=(same_cycle_hash, cross_cycle_hash),
    )

    with CycleAcquisitionStore(source_path) as store:
        result = seed_novel_direct_search_leads(
            store,
            batch_id="novel-rest-screen",
            source=source,
            prior_snapshots=prior,
        )
        assert result.leads_selected == 1
        assert result.leads_excluded_from_target == 2
        assert result.cross_cycle_snapshot_count == 1
        assert result.leads_seeded == 1
        assert store.candidate_ids("novel-rest-screen") == ("courtlistener-docket-400",)
        config = store.batch_config("novel-rest-screen")
        assert config["source_candidate_count"] == 3
        assert config["source_candidate_set_sha256"] == (
            source.source_candidate_set_sha256
        )
        assert config["selection_semantics"] == "priority_dedupe_only"
        assert config["prior_outcomes_authoritative"] is False
        assert config["cross_cycle_snapshot_count"] == 1
        assert config["selected_candidate_count"] == 1
        assert config["excluded_from_target_candidate_count"] == 2
        assert len(cast(list[object], config["prior_snapshots"])) == 2
        assert all(
            "snapshot_manifest_sha256" in cast(dict[str, object], record)
            and "cycle_hash" in cast(dict[str, object], record)
            and "batch_digest" in cast(dict[str, object], record)
            for record in cast(list[object], config["prior_snapshots"])
        )
        hit = store.candidate_discovery_hits("novel-rest-screen")[0]
        provenance = hit.payload["priority_dedupe_provenance"]
        assert provenance["prior_outcomes_authoritative"] is False
        assert provenance["selected_candidate_set_sha256"] == (
            result.selected_candidate_set_sha256
        )
        assert (
            store.term_progress(
                "novel-rest-screen", DIRECT_SEARCH_NOVEL_TRANSFER_TERM
            ).terminal_status
            == "exhausted"
        )

        repeated = seed_novel_direct_search_leads(
            store,
            batch_id="novel-rest-screen",
            source=source,
            prior_snapshots=tuple(reversed(prior)),
        )
        assert repeated.prior_snapshot_commitment_sha256 == (
            result.prior_snapshot_commitment_sha256
        )
        assert repeated.leads_seeded == 0
        assert repeated.already_seeded is True

        store.record_observation(
            "courtlistener-docket-400",
            batch_id="novel-rest-screen",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={
                "candidate_id": "courtlistener-docket-400",
                "decision_date": "2026-06-29",
            },
        )
        after_same_target_observation = seed_novel_direct_search_leads(
            store,
            batch_id="novel-rest-screen",
            source=source,
            prior_snapshots=prior,
        )
        assert after_same_target_observation.leads_seeded == 0
        assert after_same_target_observation.already_seeded is True


def test_verified_priority_dedupe_snapshots_reject_tamper_and_partial(
    tmp_path: Path,
) -> None:
    snapshot, manifest_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="tamper",
        candidate_ids=("courtlistener-docket-200",),
    )
    (snapshot / "candidates.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RecapApiBatchDriverError, match="commitment mismatch"):
        read_verified_priority_dedupe_snapshots(
            (snapshot,), expected_manifest_sha256=(manifest_hash,)
        )

    partial, partial_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="partial",
        candidate_ids=("courtlistener-docket-300",),
        complete=False,
    )
    with pytest.raises(RecapApiBatchDriverError, match="snapshot is not complete"):
        read_verified_priority_dedupe_snapshots(
            (partial,), expected_manifest_sha256=(partial_hash,)
        )


def test_verified_priority_dedupe_snapshot_rechecks_exact_parsed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, manifest_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="toctou",
        candidate_ids=("courtlistener-docket-200",),
    )
    original_verify = recap_api_batch_driver.verify_snapshot

    def verify_then_mutate(*args: Any, **kwargs: Any) -> Any:
        manifest = original_verify(*args, **kwargs)
        (snapshot / "candidates.jsonl").write_text(
            '{"candidate_id":"courtlistener-docket-999"}\n',
            encoding="utf-8",
        )
        return manifest

    monkeypatch.setattr(
        recap_api_batch_driver,
        "verify_snapshot",
        verify_then_mutate,
    )

    with pytest.raises(RecapApiBatchDriverError, match="changed after verification"):
        read_verified_priority_dedupe_snapshots(
            (snapshot,), expected_manifest_sha256=(manifest_hash,)
        )


def test_verified_priority_dedupe_snapshots_require_exact_ordered_hashes(
    tmp_path: Path,
) -> None:
    first, first_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="first",
        candidate_ids=("courtlistener-docket-200",),
    )
    second, second_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="second",
        candidate_ids=("courtlistener-docket-300",),
    )
    with pytest.raises(RecapApiBatchDriverError, match="SHA-256 mismatch"):
        read_verified_priority_dedupe_snapshots(
            (first, second),
            expected_manifest_sha256=(second_hash, first_hash),
        )
    with pytest.raises(RecapApiBatchDriverError, match="each prior snapshot"):
        read_verified_priority_dedupe_snapshots(
            (first, second), expected_manifest_sha256=(first_hash,)
        )


def test_seed_novel_direct_search_preserves_source_target_cycle_gate(
    tmp_path: Path,
) -> None:
    source_path = _build_saturated_direct_search_store(tmp_path)
    prior_path, prior_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="prior",
        candidate_ids=("courtlistener-docket-200",),
        cross_cycle=True,
    )
    source = read_saturated_direct_search_leads(
        source_path, source_batch_id="direct-search"
    )
    prior = read_verified_priority_dedupe_snapshots(
        (prior_path,), expected_manifest_sha256=(prior_hash,)
    )
    target_path = tmp_path / "different-target.sqlite3"
    with CycleAcquisitionStore(target_path) as target:
        target.ensure_cycle(
            {
                "schema_version": "test",
                "eligibility_anchor": "2026-06-30",
                "different_target": True,
            }
        )
        with pytest.raises(RecapApiBatchDriverError, match="cycle identities differ"):
            seed_novel_direct_search_leads(
                target,
                batch_id="novel-rest-screen",
                source=source,
                prior_snapshots=prior,
            )
        with pytest.raises(KeyError):
            target.batch_config("novel-rest-screen")


def test_seed_novel_direct_search_rejects_preexisting_observation_before_write(
    tmp_path: Path,
) -> None:
    source_path = _build_saturated_direct_search_store(tmp_path)
    prior_path, prior_hash = _build_prior_screening_snapshot(
        tmp_path,
        name="prior-seen",
        candidate_ids=(
            "courtlistener-docket-200",
            "courtlistener-docket-300",
        ),
    )
    source = read_saturated_direct_search_leads(
        source_path, source_batch_id="direct-search"
    )
    prior = read_verified_priority_dedupe_snapshots(
        (prior_path,), expected_manifest_sha256=(prior_hash,)
    )
    with CycleAcquisitionStore(source_path) as store:
        store.ensure_batch("older-screen", {"provider": "courtlistener"})
        store.ensure_terms("older-screen", ("screen",))
        store.commit_search_page(
            "older-screen",
            "screen",
            None,
            [
                {
                    "provider_hit_id": "older-400",
                    "candidate_id": "courtlistener-docket-400",
                    "payload": {"candidate_id": "courtlistener-docket-400"},
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "courtlistener-docket-400",
            batch_id="older-screen",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={
                "candidate_id": "courtlistener-docket-400",
                "decision_date": "2026-06-29",
            },
        )

        with pytest.raises(
            RecapApiBatchDriverError, match="already have canonical observations"
        ):
            seed_novel_direct_search_leads(
                store,
                batch_id="novel-rest-screen",
                source=source,
                prior_snapshots=prior,
            )
        with pytest.raises(KeyError):
            store.batch_config("novel-rest-screen")
