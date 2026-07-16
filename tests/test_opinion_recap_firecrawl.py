from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    FirecrawlBudgetExceededError,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlConfig,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
    FirecrawlScrapeResult,
    FirecrawlURLValidationError,
)
from legalforecast.ingestion.opinion_recap_firecrawl import (
    BudgetedOpinionRecapFirecrawlResolver,
    OpinionRecapFirecrawlPageSource,
    OpinionRecapFirecrawlSearchError,
    build_opinion_recap_search_url,
    canonicalize_opinion_recap_search_url,
    parse_opinion_recap_search_html,
)


def _html(
    *,
    page: int = 1,
    pages: int = 1,
    total_results: int = 1,
    include_pagination: bool = True,
    docket_id: str = "71878956",
    docket_number: str = "Civil Action No. 2025-3820",
    case_name: str = "Bullock v. Phh Mortgage Services",
) -> str:
    pagination = ""
    if include_pagination:
        next_link = (
            '<a rel="next" href="?type=r&amp;q=%22Bullock+v.+Phh%22&amp;'
            'court=dcd&amp;order_by=score+desc&amp;page=2">Next</a>'
            if page < pages
            else ""
        )
        pagination = f'<div class="pagination">Page {page} of {pages}{next_link}</div>'
    title = f"Search Results for test — {total_results} Results — CourtListener.com"
    return f"""<html><head><title>{title}</title></head>
<body><article><h3><a href="https://www.courtlistener.com/docket/{docket_id}/bullock-v-phh/">
{case_name} (D.D.C. 2025)</a></h3>
<div><span class="meta-data-header">Docket Number:</span>
<span class="meta-data-value select-all">{docket_number}</span></div>
<h4><a href="https://www.courtlistener.com/docket/{docket_id}/8/bullock-v-phh/">Opinion</a></h4>
</article>{pagination}</body></html>"""


def test_opinion_search_url_is_exact_court_scoped_and_canonical() -> None:
    url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd", page=2
    )

    assert url == (
        "https://www.courtlistener.com/?type=r&q=%22Bullock+v.+Phh%22&"
        "court=dcd&order_by=score+desc&page=2"
    )
    assert canonicalize_opinion_recap_search_url(url) == url
    assert canonicalize_opinion_recap_search_url(url.replace("&page=2", "&page=1")) == (
        "https://www.courtlistener.com/?type=r&q=%22Bullock+v.+Phh%22&"
        "court=dcd&order_by=score+desc"
    )


def test_opinion_page_source_rejects_nonsearch_url_before_transport() -> None:
    url = build_opinion_recap_search_url(query='"Bullock v. Phh"', court_id="dcd")
    transport = FirecrawlFixtureTransport(
        [
            FirecrawlHTTPResponse(
                status_code=200,
                payload={
                    "success": True,
                    "data": {
                        "rawHtml": _html(),
                        "metadata": {
                            "statusCode": 200,
                            "proxyUsed": "basic",
                            "creditsUsed": 1,
                            "sourceURL": url,
                        },
                    },
                },
            )
        ]
    )
    source = OpinionRecapFirecrawlPageSource(
        FirecrawlConfig(api_key="fixture"), transport=transport
    )

    assert source.scrape_url(source_url=url).resolved_url == url
    with pytest.raises(FirecrawlURLValidationError, match="allowlisted"):
        source.scrape_url(source_url="https://www.courtlistener.com/docket/1/test/")

    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "url",
    (
        "https://www.courtlistener.com/?type=r&q=Bullock&court=dcd&order_by=score+desc",
        "https://www.courtlistener.com/?type=r&q=%22Bullock%E2%80%8b%22&court=dcd&order_by=score+desc",
        "https://www.courtlistener.com/?type=r&q=%22Bullock%22&court=ca9&order_by=score+desc",
        "https://www.courtlistener.com/?type=r&q=%22Bullock%22&court=dcd&order_by=score+desc&available_only=on",
        "https://evil.example/?type=r&q=%22Bullock%22&court=dcd&order_by=score+desc",
    ),
)
def test_opinion_search_url_rejects_non_exact_or_non_trial_searches(url: str) -> None:
    with pytest.raises(OpinionRecapFirecrawlSearchError):
        canonicalize_opinion_recap_search_url(url)


def test_opinion_search_parser_emits_docket_identity_and_next_page() -> None:
    source_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd"
    )

    page = parse_opinion_recap_search_html(_html(pages=2), source_url=source_url)

    assert page.total_results == 1
    assert page.next_url == build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd", page=2
    )
    assert page.candidates[0].docket_id == "71878956"
    assert page.candidates[0].court_id == "dcd"
    assert page.candidates[0].docket_number == "Civil Action No. 2025-3820"
    assert page.candidates[0].case_name == "Bullock v. Phh Mortgage Services"


def test_opinion_search_parser_requires_explicit_pagination_proof() -> None:
    source_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd"
    )

    with pytest.raises(OpinionRecapFirecrawlSearchError, match="pagination"):
        parse_opinion_recap_search_html(
            _html(total_results=2, include_pagination=False), source_url=source_url
        )


def test_opinion_search_parser_accepts_count_reconciled_single_page() -> None:
    source_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd"
    )

    page = parse_opinion_recap_search_html(
        _html(include_pagination=False), source_url=source_url
    )

    assert page.total_pages == 1
    assert page.next_url is None


def test_opinion_search_parser_rejects_missing_cards_on_terminal_page() -> None:
    source_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd"
    )

    with pytest.raises(OpinionRecapFirecrawlSearchError, match="result count"):
        parse_opinion_recap_search_html(_html(total_results=2), source_url=source_url)


class _FixtureSource:
    def __init__(self, result: FirecrawlScrapeResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls.append(source_url)
        return self.result


class _FixtureSequenceSource:
    def __init__(self, outcomes: list[FirecrawlScrapeResult | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls.append(source_url)
        outcome = self.outcomes[len(self.calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _result(url: str, html: str) -> FirecrawlScrapeResult:
    return FirecrawlScrapeResult(
        source_url=url,
        docket_id=None,
        raw_html=html,
        target_status_code=200,
        proxy_requested="basic",
        proxy_used="basic",
        cache_state="miss",
        credits_used=1.0,
        raw={"success": True},
        resolved_url=url,
    )


def test_budgeted_resolver_commits_search_artifact_and_credit(tmp_path: Path) -> None:
    url = build_opinion_recap_search_url(query='"Bullock v. Phh"', court_id="dcd")
    html = _html()
    source = _FixtureSource(
        FirecrawlScrapeResult(
            source_url=url,
            docket_id=None,
            raw_html=html,
            target_status_code=200,
            proxy_requested="basic",
            proxy_used="basic",
            cache_state="miss",
            credits_used=1.0,
            raw={"success": True},
            resolved_url=url,
        )
    )
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("source", {"provider": "courtlistener"})

    resolver = BudgetedOpinionRecapFirecrawlResolver(
        store_path=store_path,
        source_batch_id="source",
        output_batch_id="resolved",
        run_id="opinion-firecrawl",
        artifact_dir=tmp_path / "raw",
        source=source,
        credit_cap=10,
        max_attempts=1,
        max_pages_per_lead=25,
    )
    results = resolver.search(
        source_candidate_id="73614335",
        source_ordinal=3,
        query='"Bullock v. Phh"',
        court_id="dcd",
    )

    assert [item.docket_id for item in results.candidates] == ["71878956"]
    assert results.page_count == 1
    assert results.reported_credits == 1
    with CycleAcquisitionStore(store_path) as store:
        [attempt] = store.firecrawl_attempts("opinion-firecrawl")
        assert attempt.status == "succeeded"
        assert Path(attempt.artifact_path or "").read_text() == html


def test_budgeted_resolver_exhausts_multiple_pages_under_one_credit_cap(
    tmp_path: Path,
) -> None:
    first_url = build_opinion_recap_search_url(query='"Bullock v. Phh"', court_id="dcd")
    second_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd", page=2
    )
    source = _FixtureSequenceSource(
        [
            _result(first_url, _html(pages=2, total_results=2)),
            _result(
                second_url,
                _html(
                    page=2,
                    pages=2,
                    total_results=2,
                    docket_id="71878957",
                    docket_number="Civil Action No. 2025-3821",
                    case_name="Bullock v. Alternate Mortgage Services",
                ),
            ),
        ]
    )
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("source", {"provider": "courtlistener"})
    resolver = BudgetedOpinionRecapFirecrawlResolver(
        store_path=store_path,
        source_batch_id="source",
        output_batch_id="resolved",
        run_id="opinion-firecrawl",
        artifact_dir=tmp_path / "raw",
        source=source,
        credit_cap=2,
        max_attempts=1,
        max_pages_per_lead=2,
    )

    results = resolver.search(
        source_candidate_id="73614335",
        source_ordinal=3,
        query='"Bullock v. Phh"',
        court_id="dcd",
    )

    assert [item.docket_id for item in results.candidates] == [
        "71878956",
        "71878957",
    ]
    assert results.page_count == 2
    assert results.reserved_credits == results.reported_credits == 2
    assert source.calls == [first_url, second_url]


def test_budgeted_resolver_refuses_second_page_before_exceeding_credit_cap(
    tmp_path: Path,
) -> None:
    first_url = build_opinion_recap_search_url(query='"Bullock v. Phh"', court_id="dcd")
    second_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd", page=2
    )
    source = _FixtureSequenceSource(
        [
            _result(first_url, _html(pages=2, total_results=2)),
            _result(
                second_url,
                _html(
                    page=2,
                    pages=2,
                    total_results=2,
                    docket_id="71878957",
                ),
            ),
        ]
    )
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("source", {"provider": "courtlistener"})
    resolver = BudgetedOpinionRecapFirecrawlResolver(
        store_path=store_path,
        source_batch_id="source",
        output_batch_id="resolved",
        run_id="opinion-firecrawl",
        artifact_dir=tmp_path / "raw",
        source=source,
        credit_cap=1,
        max_attempts=1,
        max_pages_per_lead=2,
    )

    with pytest.raises(FirecrawlBudgetExceededError, match="credit cap"):
        resolver.search(
            source_candidate_id="73614335",
            source_ordinal=3,
            query='"Bullock v. Phh"',
            court_id="dcd",
        )

    assert source.calls == [first_url]


def test_budgeted_resolver_resumes_verified_page_after_interruption(
    tmp_path: Path,
) -> None:
    first_url = build_opinion_recap_search_url(query='"Bullock v. Phh"', court_id="dcd")
    second_url = build_opinion_recap_search_url(
        query='"Bullock v. Phh"', court_id="dcd", page=2
    )
    second_result = _result(
        second_url,
        _html(
            page=2,
            pages=2,
            total_results=2,
            docket_id="71878957",
            docket_number="Civil Action No. 2025-3821",
            case_name="Bullock v. Alternate Mortgage Services",
        ),
    )
    source = _FixtureSequenceSource(
        [
            _result(first_url, _html(pages=2, total_results=2)),
            RuntimeError("fixture interruption"),
            second_result,
        ]
    )
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("source", {"provider": "courtlistener"})
    resolver = BudgetedOpinionRecapFirecrawlResolver(
        store_path=store_path,
        source_batch_id="source",
        output_batch_id="resolved",
        run_id="opinion-firecrawl",
        artifact_dir=tmp_path / "raw",
        source=source,
        credit_cap=3,
        max_attempts=3,
        max_pages_per_lead=2,
    )

    with pytest.raises(RuntimeError, match="fixture interruption"):
        resolver.search(
            source_candidate_id="73614335",
            source_ordinal=3,
            query='"Bullock v. Phh"',
            court_id="dcd",
        )

    results = resolver.search(
        source_candidate_id="73614335",
        source_ordinal=3,
        query='"Bullock v. Phh"',
        court_id="dcd",
    )

    assert [item.docket_id for item in results.candidates] == [
        "71878956",
        "71878957",
    ]
    assert source.calls == [first_url, second_url, second_url]
    assert results.reserved_credits == 3
    assert results.reported_credits == 2
