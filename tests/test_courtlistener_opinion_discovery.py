"""Tests for CourtListener opinion-cluster discovery."""

from __future__ import annotations

import urllib.parse
from datetime import date
from typing import Any

import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.courtlistener_opinion_discovery import (
    FEDERAL_BANKRUPTCY_COURT_IDS,
    FEDERAL_DISTRICT_COURT_IDS,
    FEDERAL_TRIAL_COURT_IDS,
    OPINION_MTD_SEARCH_TERMS,
    OPINION_STATUS_FILTERS,
    OpinionApiDiscoveryError,
    OpinionApiDiscoverySource,
    build_opinion_batch_config,
)

START = date(2026, 6, 30)
END = date(2026, 7, 15)
TERM = '"motion to dismiss"'


def _params(term: str = TERM) -> dict[str, Any]:
    return {
        "type": "o",
        "q": term,
        "filed_after": START.isoformat(),
        "filed_before": END.isoformat(),
        "order_by": "dateFiled desc",
        "court": " ".join(FEDERAL_TRIAL_COURT_IDS),
        **{name: "on" for name in OPINION_STATUS_FILTERS},
    }


def _response(
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any],
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path="/search/",
        params=params or _params(),
        status_code=200,
        payload=payload,
    )


def _source(*responses: RecordedCourtListenerResponse) -> OpinionApiDiscoverySource:
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(responses),
    )
    return OpinionApiDiscoverySource(
        client=client,
        decision_window_start=START,
        decision_window_end=END,
    )


def _hit(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "cluster_id": 10026367,
        "docket_id": 70649963,
        "absolute_url": "/opinion/10026367/example-v-example/",
        "court_id": "txsd",
        "docketNumber": "4:26-cv-01234",
        "caseName": "Example v. Example",
        "dateFiled": "2026-07-10",
        "status": "Unpublished",
        "opinions": [
            {
                "id": 999,
                "snippet": "ORDER granting motion to dismiss",
                "download_url": "https://example.invalid/decision.pdf",
            }
        ],
        "snippet": "outcome text must not be retained",
    }
    record.update(overrides)
    return record


def _next_url(*, cursor: str = "next-cursor", **overrides: str) -> str:
    query = {key: str(value) for key, value in _params().items()}
    query.update(overrides)
    query["cursor"] = cursor
    return (
        "https://www.courtlistener.com/api/rest/v4/search/?"
        f"{urllib.parse.urlencode(query)}"
    )


def test_opinion_config_is_transfer_compatible_and_accepts_term_override() -> None:
    terms = ('"motion to dismiss"', '"Rule 12(c)"')
    config = build_opinion_batch_config(
        decision_window_start=START,
        decision_window_end=END,
        query_terms=terms,
        top_k_per_term=5_000,
    )

    assert config["provider"] == "courtlistener"
    assert config["search_type"] == "o"
    assert config["search_window_start"] == "2026-06-30"
    assert config["search_window_end"] == "2026-07-15"
    assert config["query_terms"] == list(terms)
    assert config["page_size"] == 20
    assert config["status_filters"] == list(OPINION_STATUS_FILTERS)
    assert config["court_ids"] == list(FEDERAL_TRIAL_COURT_IDS)


@pytest.mark.parametrize("terms", [(), ("",), ("same", "same")])
def test_opinion_config_rejects_invalid_term_overrides(terms: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="query terms"):
        build_opinion_batch_config(
            decision_window_start=START,
            decision_window_end=END,
            query_terms=terms,
        )


def test_frozen_terms_cover_district_rule_12_and_bankruptcy_analogue() -> None:
    assert OPINION_MTD_SEARCH_TERMS == (
        '"motion to dismiss"',
        '"Rule 12(b)(6)" OR "12(b)(6)"',
        '"judgment on the pleadings" OR "Rule 12(c)"',
        '"Rule 7012" OR "motion to dismiss adversary complaint"',
    )
    assert "nysd" in FEDERAL_TRIAL_COURT_IDS
    assert "nysb" in FEDERAL_TRIAL_COURT_IDS
    assert "nmid" in FEDERAL_TRIAL_COURT_IDS


def test_frozen_court_ids_map_northern_mariana_bankruptcy_to_valid_district() -> None:
    assert "mpb" in FEDERAL_BANKRUPTCY_COURT_IDS
    assert "nmid" in FEDERAL_DISTRICT_COURT_IDS
    assert "mpd" not in FEDERAL_DISTRICT_COURT_IDS
    assert "mpd" not in FEDERAL_TRIAL_COURT_IDS
    assert len(FEDERAL_TRIAL_COURT_IDS) == len(set(FEDERAL_TRIAL_COURT_IDS))


def test_fetch_page_uses_strict_opinion_request_and_retains_metadata_only() -> None:
    source = _source(_response(payload={"count": 1, "next": None, "results": [_hit()]}))

    page = source.fetch_page(term=TERM, cursor=None, page_size=20)

    assert page.next_cursor is None
    assert page.exhausted is True
    assert len(page.hits) == 1
    hit = page.hits[0]
    assert hit.provider_hit_id == "10026367"
    assert hit.candidate_id == "70649963"
    assert hit.payload == {
        "docket_id": "70649963",
        "court_id": "txsd",
        "docket_number": "4:26-cv-01234",
        "case_name": "Example v. Example",
        "provider": "courtlistener",
        "opinion_discovery_evidence": {
            "schema_version": "legalforecast.courtlistener_opinion_hit.v1",
            "cluster_id": "10026367",
            "absolute_url": "/opinion/10026367/example-v-example/",
            "date_filed": "2026-07-10",
            "status": "Unpublished",
            "sub_opinions": [
                {
                    "opinion_id": "999",
                    "absolute_url": None,
                    "download_url": "https://example.invalid/decision.pdf",
                    "local_path": None,
                }
            ],
        },
    }
    assert "decision_entry_evidence" not in hit.payload
    assert "opinions" not in hit.payload
    assert "snippet" not in hit.payload


def test_opinion_reference_retains_public_artifact_identity_without_text() -> None:
    source = _source(
        _response(
            payload={
                "count": 1,
                "next": None,
                "results": [
                    _hit(
                        opinions=[
                            {
                                "id": 11395231,
                                "absolute_url": "/api/rest/v4/opinions/11395231/",
                                "download_url": (
                                    "https://ecf.dcd.uscourts.gov/doc1/045111234567"
                                ),
                                "local_path": (
                                    "pdf/2026/07/14/"
                                    "bullock_v._phh_mortgage_services.pdf"
                                ),
                                "plain_text": "outcome text must not be retained",
                                "html_with_citations": "<p>outcome</p>",
                            }
                        ]
                    )
                ],
            }
        )
    )

    evidence = (
        source.fetch_page(term=TERM, cursor=None, page_size=20)
        .hits[0]
        .payload["opinion_discovery_evidence"]
    )

    assert evidence["sub_opinions"] == [
        {
            "opinion_id": "11395231",
            "absolute_url": "/api/rest/v4/opinions/11395231/",
            "download_url": "https://ecf.dcd.uscourts.gov/doc1/045111234567",
            "local_path": ("pdf/2026/07/14/bullock_v._phh_mortgage_services.pdf"),
        }
    ]
    assert "plain_text" not in str(evidence)
    assert "html_with_citations" not in str(evidence)


def test_fetch_page_extracts_and_validates_explicit_continuation() -> None:
    source = _source(
        _response(
            payload={
                "count": 21,
                "next": _next_url(),
                "previous": None,
                "results": [_hit()],
            }
        )
    )

    page = source.fetch_page(term=TERM, cursor=None, page_size=20)

    assert page.next_cursor == "next-cursor"
    assert page.exhausted is None


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"count": 0, "results": []}, "explicit next"),
        ({"count": 0, "next": None}, "explicit results"),
        (
            {
                "count": 0,
                "next": "https://attacker.invalid/api/rest/v4/search/?cursor=x",
                "results": [],
            },
            "continuation origin",
        ),
        (
            {
                "count": 0,
                "next": "https://www.courtlistener.com/api/rest/v4/dockets/?cursor=x",
                "results": [],
            },
            "continuation path",
        ),
        (
            {
                "count": 0,
                "next": _next_url(q="changed query"),
                "results": [],
            },
            "continuation query",
        ),
    ],
)
def test_fetch_page_rejects_unproven_pagination(
    payload: dict[str, Any], match: str
) -> None:
    source = _source(_response(payload=payload))

    with pytest.raises(OpinionApiDiscoveryError, match=match):
        source.fetch_page(term=TERM, cursor=None, page_size=20)


@pytest.mark.parametrize("page_size", [1, 19, 21, 100])
def test_fetch_page_requires_provider_fixed_page_size(page_size: int) -> None:
    source = _source()
    with pytest.raises(ValueError, match="exactly 20"):
        source.fetch_page(term=TERM, cursor=None, page_size=page_size)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"cluster_id": None}, "cluster_id"),
        ({"docket_id": "0"}, "docket_id"),
        ({"dateFiled": "2026-06-29"}, "outside frozen"),
        ({"court_id": "ca5"}, "federal trial court"),
        (
            {"absolute_url": "/opinion/99999999/example-v-example/"},
            "cluster id mismatch",
        ),
    ],
)
def test_fetch_page_fails_closed_on_invalid_hit_identity(
    overrides: dict[str, object], match: str
) -> None:
    source = _source(
        _response(payload={"count": 1, "next": None, "results": [_hit(**overrides)]})
    )

    with pytest.raises(OpinionApiDiscoveryError, match=match):
        source.fetch_page(term=TERM, cursor=None, page_size=20)
