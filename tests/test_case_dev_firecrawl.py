from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_firecrawl import (
    CaseDevFirecrawlBatchError,
    CaseDevFirecrawlCandidate,
    acquire_case_dev_firecrawl_html,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlPaymentRequiredError,
    FirecrawlResponseError,
)


@dataclass
class _FakeFirecrawlSource:
    html_by_docket_id: dict[str, str] = field(default_factory=dict)
    error_by_docket_id: dict[str, Exception] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        self.requests.append((docket_id, source_url))
        error = self.error_by_docket_id.get(docket_id)
        if error is not None:
            raise error
        return self.html_by_docket_id[docket_id]


def test_bridge_dedupes_before_limit_and_writes_html_in_input_order(tmp_path) -> None:
    client, transport = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"101": _docket_html("A"), "202": _docket_html("B")}
    )

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {"case_id": "case-a", "candidate_id": "candidate-a"},
            {"case_id": "case-a", "candidate_id": "duplicate-a"},
            CaseDevFirecrawlCandidate(case_id="case-b", candidate_id=None),
            {"case_id": "case-c", "candidate_id": "over-limit"},
        ),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert [item.case_id for item in result.successes] == ["case-a", "case-b"]
    assert [item.candidate_id for item in result.successes] == ["candidate-a", None]
    assert [item.reason for item in result.exclusions] == ["candidate_limit_deferred"]
    assert result.unique_candidate_count == 3
    assert result.processed_candidate_count == 2
    assert result.scrape_count == 2
    assert (tmp_path / "101.html").read_text(encoding="utf-8") == _docket_html("A")
    assert (tmp_path / "202.html").read_text(encoding="utf-8") == _docket_html("B")
    assert [request[2]["docketId"] for request in transport.requests] == [
        "case-a",
        "case-b",
    ]
    assert [request[0] for request in source.requests] == ["101", "202"]


def test_bridge_ledgers_missing_or_malformed_url_without_scraping(tmp_path) -> None:
    client, _ = _client(
        _lookup("unknown", include_source_url=False),
        _lookup("../escape", include_source_url=False),
    )
    source = _FakeFirecrawlSource()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {"case_id": "unknown", "candidate_id": "missing"},
            {"case_id": "../escape", "candidate_id": "malformed"},
        ),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert result.successes == ()
    assert [item.reason for item in result.exclusions] == [
        "courtlistener_url_missing",
        "courtlistener_url_malformed",
    ]
    assert source.requests == []
    assert list(tmp_path.iterdir()) == []
    assert not (tmp_path.parent / "escape.html").exists()


def test_bridge_never_overwrites_an_existing_docket_file(tmp_path) -> None:
    destination = tmp_path / "101.html"
    destination.write_text("preserve me", encoding="utf-8")
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(html_by_docket_id={"101": "replacement"})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert result.successes == ()
    assert [item.reason for item in result.exclusions] == ["raw_html_path_exists"]
    assert destination.read_text(encoding="utf-8") == "preserve me"
    assert list(tmp_path.iterdir()) == [destination]


def test_bridge_ledgers_nonfatal_provider_response_without_error_text(tmp_path) -> None:
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(
        error_by_docket_id={
            "101": FirecrawlResponseError("secret-bearing upstream body")
        }
    )

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a", "candidate_id": "candidate-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    [exclusion] = result.exclusions
    assert exclusion.reason == "firecrawl_response_invalid"
    assert "secret" not in exclusion.reason
    assert exclusion.source_url is not None
    assert exclusion.docket_id == "101"


def test_bridge_ledgers_malformed_case_dev_response_and_continues(tmp_path) -> None:
    malformed = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "lookup", "docketId": "case-a"},
        status_code=200,
        payload={"id": "case-a"},
    )
    client, _ = _client(
        malformed,
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(html_by_docket_id={"202": _docket_html("B")})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert [item.reason for item in result.exclusions] == ["case_dev_response_invalid"]
    assert [item.case_id for item in result.successes] == ["case-b"]
    assert [request[0] for request in source.requests] == ["202"]


def test_bridge_propagates_fatal_firecrawl_failures_and_stops(tmp_path) -> None:
    client, _ = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"202": _docket_html("B")},
        error_by_docket_id={"101": FirecrawlPaymentRequiredError("credit details")},
    )

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
            raw_html_directory=tmp_path,
            max_candidates=2,
        )

    assert isinstance(raised.value.provider_error, FirecrawlPaymentRequiredError)
    assert [item.reason for item in raised.value.partial_result.exclusions] == [
        "firecrawl_provider_blocker",
        "provider_blocker_deferred",
    ]
    assert [request[0] for request in source.requests] == ["101"]
    assert client.request_count == 1


def test_bridge_fatal_error_checkpoints_earlier_successes(tmp_path) -> None:
    client, _ = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"101": _docket_html("A")},
        error_by_docket_id={"202": FirecrawlPaymentRequiredError("credit details")},
    )

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
            raw_html_directory=tmp_path,
            max_candidates=2,
        )

    partial = raised.value.partial_result
    assert [item.case_id for item in partial.successes] == ["case-a"]
    assert [item.reason for item in partial.exclusions] == [
        "firecrawl_provider_blocker"
    ]
    assert partial.processed_candidate_count == 2
    assert partial.scrape_count == 2
    assert (tmp_path / "101.html").read_text(encoding="utf-8") == _docket_html("A")


def test_bridge_ledgers_non_docket_html_without_persisting(tmp_path) -> None:
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(html_by_docket_id={"101": "<html>blocked</html>"})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert [item.reason for item in result.exclusions] == ["firecrawl_response_invalid"]
    assert list(tmp_path.iterdir()) == []


def test_bridge_propagates_fatal_case_dev_failure_before_scraping(tmp_path) -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "lookup", "docketId": "case-a"},
                status_code=401,
                payload={"error": "bad token"},
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport, max_retries=0)
    source = _FakeFirecrawlSource()

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"},),
            raw_html_directory=tmp_path,
            max_candidates=1,
        )

    assert isinstance(raised.value.provider_error, CaseDevAuthError)
    assert [item.reason for item in raised.value.partial_result.exclusions] == [
        "case_dev_provider_blocker"
    ]
    assert source.requests == []


@pytest.mark.parametrize("max_candidates", [0, -1])
def test_bridge_requires_positive_explicit_candidate_limit(
    tmp_path, max_candidates: int
) -> None:
    client, _ = _client()

    with pytest.raises(ValueError, match="max_candidates must be positive"):
        acquire_case_dev_firecrawl_html(
            client=client,
            source=_FakeFirecrawlSource(),
            candidates=(),
            raw_html_directory=tmp_path,
            max_candidates=max_candidates,
        )


def _config() -> CaseDevConfig:
    return CaseDevConfig(api_key=None, base_url="https://api.case.dev")


def _docket_html(label: str) -> str:
    return f"<html><div id='docket-entry-table'></div>{label}</html>"


def _client(
    *responses: RecordedCaseDevResponse,
) -> tuple[CaseDevClient, CaseDevFixtureTransport]:
    transport = CaseDevFixtureTransport(responses)
    return CaseDevClient(config=_config(), transport=transport), transport


def _lookup(
    case_id: str,
    *,
    courtlistener_docket_id: str | None = None,
    include_source_url: bool = True,
) -> RecordedCaseDevResponse:
    payload: dict[str, object] = {
        "id": case_id,
        "caseName": f"Fixture {case_id} v. Example",
    }
    if include_source_url:
        docket_id = courtlistener_docket_id or case_id
        payload["url"] = (
            f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
        )
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "lookup", "docketId": case_id},
        status_code=200,
        payload=payload,
    )
