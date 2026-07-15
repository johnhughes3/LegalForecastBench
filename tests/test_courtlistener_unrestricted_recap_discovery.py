"""Focused tests for unrestricted CourtListener ``type=r`` discovery."""

from __future__ import annotations

import urllib.parse
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
from legalforecast.ingestion.courtlistener_unrestricted_recap_discovery import (
    UNRESTRICTED_RECAP_SEARCH_TERMS,
    CourtListenerUnrestrictedRecapDiscoveryError,
    CourtListenerUnrestrictedRecapDiscoverySource,
    build_unrestricted_recap_batch_config,
    run_unrestricted_recap_discovery,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import DiscoveryRunSummary
from legalforecast.ingestion.recap_api_batch_driver import (
    read_saturated_direct_search_leads,
)


def _response(
    *,
    params: dict[str, Any],
    payload: dict[str, Any],
    status_code: int = 200,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path="/search/",
        params=params,
        status_code=status_code,
        payload=payload,
    )


def _params(term: str, *, cursor: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "q": (f"{term} AND entry_date_filed:[2026-06-30 TO 2026-07-15]"),
        "type": "r",
        "order_by": "score desc",
        "page_size": 20,
    }
    if cursor is not None:
        params["cursor"] = cursor
    return params


def _next_url(
    term: str,
    *,
    cursor: str = "cursor-2",
    query_pairs: list[tuple[str, str]] | None = None,
) -> str:
    pairs = query_pairs or [(key, str(value)) for key, value in _params(term).items()]
    return (
        "https://www.courtlistener.com/api/rest/v4/search/?"
        f"{urllib.parse.urlencode([*pairs, ('cursor', cursor)])}"
    )


def _client(
    responses: tuple[RecordedCourtListenerResponse, ...],
) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(api_token="fixture-token"),
        transport=CourtListenerFixtureTransport(responses),
        max_retries=0,
    )


def _source(
    responses: tuple[RecordedCourtListenerResponse, ...],
) -> CourtListenerUnrestrictedRecapDiscoverySource:
    return CourtListenerUnrestrictedRecapDiscoverySource(
        client=_client(responses),
        search_window_start=date(2026, 6, 30),
        search_window_end=date(2026, 7, 15),
        auth_mode="authenticated",
    )


def _store(path: Path) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(path)
    store.ensure_cycle({"schema_version": "test", "eligibility_anchor": "2026-06-30"})
    return store


def test_terms_and_source_config_are_frozen_for_unavailable_recap_results() -> None:
    assert UNRESTRICTED_RECAP_SEARCH_TERMS == (
        '"motion to dismiss" AND granted',
        '"motion to dismiss" AND denied',
    )
    config = build_unrestricted_recap_batch_config(
        search_window_start=date(2026, 6, 30),
        search_window_end=date(2026, 7, 15),
        auth_mode="authenticated",
    )
    assert config == {
        "schema_version": "legalforecast.courtlistener_unrestricted_recap.v1",
        "provider": "courtlistener",
        "search_type": "r",
        "query_field": "q",
        "query_terms": list(UNRESTRICTED_RECAP_SEARCH_TERMS),
        "query_term_order_is_frozen": True,
        "query_expression": "{term} AND entry_date_filed:[{start} TO {end}]",
        "search_window_start": "2026-06-30",
        "search_window_end": "2026-07-15",
        "order_by": "score desc",
        "available_only": "omitted",
        "search_page_size": 20,
        "provider_page_size_is_fixed": True,
        "top_k_per_term": 5000,
        "auth_mode": "authenticated",
    }


def test_search_omits_available_only_and_preserves_exact_provider_result() -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    record = {
        "docket_id": 71234567,
        "court_id": "nysd",
        "docketNumber": "1:26-cv-00123",
        "caseName": "Alpha LLC v. Beta Inc.",
        "recap_documents": [
            {
                "id": 998,
                "entry_number": 22,
                "description": "ORDER granting motion to dismiss",
                "is_available": False,
            }
        ],
        "arbitrary_provider_field": {"retained": [True, None, "exact"]},
    }
    source = _source(
        (_response(params=_params(term), payload={"results": [record], "next": None}),)
    )

    page = source.fetch_page(term=term, cursor=None, page_size=20)

    assert page.exhausted is True
    assert page.next_cursor is None
    assert len(page.hits) == 1
    assert page.hits[0].candidate_id == "71234567"
    assert page.hits[0].payload == record
    assert "available_only" not in _params(term)


@pytest.mark.parametrize("page_size", [1, 19, 21, 100])
def test_search_requires_observed_fixed_provider_page_size(page_size: int) -> None:
    source = _source(())

    with pytest.raises(ValueError, match="exactly 20"):
        source.fetch_page(
            term=UNRESTRICTED_RECAP_SEARCH_TERMS[0], cursor=None, page_size=page_size
        )


def test_config_requires_top_k_multiple_of_fixed_page_size() -> None:
    with pytest.raises(ValueError, match="multiple"):
        build_unrestricted_recap_batch_config(
            search_window_start=date(2026, 6, 30),
            search_window_end=date(2026, 7, 15),
            auth_mode="authenticated",
            top_k_per_term=21,
        )


def test_durable_run_resumes_after_committed_page_and_is_idempotent(
    tmp_path: Path,
) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    next_url = _next_url(term)
    client = _client(
        (
            _response(
                params=_params(term),
                payload={"results": [{"docket_id": 101}], "next": next_url},
            ),
            _response(
                params=_params(term, cursor="cursor-2"),
                payload={"detail": "rate limited"},
                status_code=429,
            ),
            _response(
                params=_params(term, cursor="cursor-2"),
                payload={"results": [{"docket_id": 102}], "next": None},
            ),
        )
    )
    with _store(tmp_path / "cycle.sqlite3") as store:

        def run() -> DiscoveryRunSummary:
            return run_unrestricted_recap_discovery(
                store=store,
                batch_id="unrestricted-r",
                client=client,
                search_window_start=date(2026, 6, 30),
                search_window_end=date(2026, 7, 15),
                auth_mode="authenticated",
                query_terms=(term,),
            )

        with pytest.raises(CourtListenerRateLimitError):
            run()
        assert store.candidate_ids("unrestricted-r") == ("101",)
        assert store.term_progress("unrestricted-r", term).cursor == "cursor-2"

        resumed = run()
        repeated = run()

        assert resumed.saturated is True
        assert repeated == resumed
        assert store.candidate_ids("unrestricted-r") == ("101", "102")
        assert store.batch_config("unrestricted-r")["provider"] == "courtlistener"
    assert client.request_count == 3


def test_saturated_output_is_source_bound_transfer_compatible(tmp_path: Path) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[1]
    record = {
        "docket_id": 71234567,
        "court_id": "nysd",
        "docketNumber": "1:26-cv-00123",
        "caseName": "Alpha LLC v. Beta Inc.",
        "recap_documents": [
            {
                "id": 998,
                "entry_number": 22,
                "description": "ORDER denying motion to dismiss",
                "is_available": False,
            }
        ],
    }
    path = tmp_path / "cycle.sqlite3"
    client = _client(
        (_response(params=_params(term), payload={"results": [record], "next": None}),)
    )
    with _store(path) as store:
        result = run_unrestricted_recap_discovery(
            store=store,
            batch_id="unrestricted-r",
            client=client,
            search_window_start=date(2026, 6, 30),
            search_window_end=date(2026, 7, 15),
            auth_mode="authenticated",
            query_terms=(term,),
        )
        assert result.saturated is True

    source = read_saturated_direct_search_leads(
        path,
        source_batch_id="unrestricted-r",
    )
    assert [lead.docket_id for lead in source.leads] == ["71234567"]
    assert source.search_window_start == date(2026, 6, 30)
    assert source.search_window_end == date(2026, 7, 15)
    assert source.leads[0].decision_entry_evidence == {
        "id": 998,
        "docket_entry_id": None,
        "entry_number": 22,
        "document_number": None,
        "description": "ORDER denying motion to dismiss",
        "entry_date_filed": None,
        "absolute_url": None,
    }


def test_run_uses_terms_normalized_into_frozen_config(tmp_path: Path) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    client = _client(
        (_response(params=_params(term), payload={"results": [], "next": None}),)
    )
    with _store(tmp_path / "cycle.sqlite3") as store:
        result = run_unrestricted_recap_discovery(
            store=store,
            batch_id="normalized-terms",
            client=client,
            search_window_start=date(2026, 6, 30),
            search_window_end=date(2026, 7, 15),
            auth_mode="authenticated",
            query_terms=(f"  {term}  ",),
        )

        assert result.saturated is True
        assert store.batch_config("normalized-terms")["query_terms"] == [term]
        assert store.term_progress("normalized-terms", term).terminal_status == (
            "exhausted"
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"next": None}, "explicit results list"),
        ({"results": []}, "explicit next"),
        ({"results": [], "next": "cursor-2"}, "absolute HTTPS URL"),
        (
            {
                "results": [],
                "next": "https://evil.example/api/rest/v4/search/?cursor=x",
            },
            "CourtListener origin",
        ),
        (
            {
                "results": [],
                "next": "https://www.courtlistener.com/wrong/?cursor=x",
            },
            "search endpoint",
        ),
        (
            {
                "results": [],
                "next": (
                    "https://www.courtlistener.com/api/rest/v4/search/"
                    "?cursor=x&cursor=y"
                ),
            },
            "exactly one",
        ),
        (
            {
                "results": [],
                "next": (
                    "https://www.courtlistener.com/api/rest/v4/search/"
                    "?cursor=x#fragment"
                ),
            },
            "fragment",
        ),
    ],
)
def test_pagination_fails_closed(payload: dict[str, Any], message: str) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    source = _source((_response(params=_params(term), payload=payload),))

    with pytest.raises(CourtListenerUnrestrictedRecapDiscoveryError, match=message):
        source.fetch_page(term=term, cursor=None, page_size=20)


def test_pagination_accepts_reordered_exact_frozen_parameter_multiset() -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    frozen_pairs = [(key, str(value)) for key, value in reversed(_params(term).items())]
    source = _source(
        (
            _response(
                params=_params(term),
                payload={
                    "results": [],
                    "next": _next_url(term, query_pairs=frozen_pairs),
                },
            ),
        )
    )

    page = source.fetch_page(term=term, cursor=None, page_size=20)

    assert page.next_cursor == "cursor-2"
    assert page.exhausted is False


@pytest.mark.parametrize(
    "query_pairs",
    [
        [("type", "r"), ("order_by", "score desc"), ("page_size", "20")],
        [
            ("q", "changed query"),
            ("type", "r"),
            ("order_by", "score desc"),
            ("page_size", "20"),
        ],
        [
            *_params(UNRESTRICTED_RECAP_SEARCH_TERMS[0]).items(),
            ("q", _params(UNRESTRICTED_RECAP_SEARCH_TERMS[0])["q"]),
        ],
        [
            ("q", _params(UNRESTRICTED_RECAP_SEARCH_TERMS[0])["q"]),
            ("type", "r"),
            ("type", "r"),
            ("order_by", "score desc"),
            ("page_size", "20"),
        ],
        [
            ("q", _params(UNRESTRICTED_RECAP_SEARCH_TERMS[0])["q"]),
            ("type", "r"),
            ("order_by", "score desc"),
            ("page_size", "100"),
        ],
    ],
    ids=(
        "missing-q",
        "changed-q",
        "duplicate-q",
        "duplicate-type",
        "changed-page-size",
    ),
)
def test_pagination_rejects_drift_or_duplicates_in_frozen_parameters(
    query_pairs: list[tuple[str, str]],
) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    source = _source(
        (
            _response(
                params=_params(term),
                payload={
                    "results": [],
                    "next": _next_url(term, query_pairs=query_pairs),
                },
            ),
        )
    )

    with pytest.raises(
        CourtListenerUnrestrictedRecapDiscoveryError,
        match="changed frozen parameters",
    ):
        source.fetch_page(term=term, cursor=None, page_size=20)


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"docket_id": None},
        {"docket_id": True},
        {"docket_id": 0},
        {"docket_id": -1},
        {"docket_id": "abc"},
        {"docket_id": "\uff11\uff12\uff13"},
    ],
)
def test_malformed_docket_identity_fails_entire_page(record: dict[str, Any]) -> None:
    term = UNRESTRICTED_RECAP_SEARCH_TERMS[0]
    source = _source(
        (_response(params=_params(term), payload={"results": [record], "next": None}),)
    )

    with pytest.raises(
        CourtListenerUnrestrictedRecapDiscoveryError,
        match="positive ASCII integer docket_id",
    ):
        source.fetch_page(term=term, cursor=None, page_size=20)


def test_config_rejects_inverted_window_and_datetime_bounds() -> None:
    with pytest.raises(ValueError, match="on or before"):
        build_unrestricted_recap_batch_config(
            search_window_start=date(2026, 7, 15),
            search_window_end=date(2026, 6, 30),
            auth_mode="authenticated",
        )
