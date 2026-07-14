from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from legalforecast.ingestion import firecrawl_recap_decision_discovery
from legalforecast.ingestion.firecrawl_recap_decision_discovery import (
    DECISION_FIRST_RECAP_SEARCH_TERMS,
    DecisionRecapSearchCompletenessError,
    DecisionRecapSearchMarkupError,
    DecisionRecapSearchURLValidationError,
    build_decision_recap_search_url,
    discover_decision_recap_entries,
    parse_decision_recap_search_html,
    parse_decision_recap_search_url,
)
from legalforecast.ingestion.recap_api_discovery import (
    DECISION_FIRST_RECAP_API_SEARCH_TERMS,
)

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 13)
FIXTURES = Path(__file__).parent / "fixtures" / "courtlistener"


def _article(*, docket_id: str = "12345", document_number: str = "27") -> str:
    return (
        '<article><h3 class="bottom serif"><a href="/docket/'
        f'{docket_id}/alpha-v-beta/" class="visitable">Alpha v. Beta</a></h3>'
        '<div class="bottom"><div class="col-md-offset-half"><h4><a href="/docket/'
        f'{docket_id}/{document_number}/alpha-v-beta/" class="visitable">ORDER '
        f"granting motion to dismiss — Document #{document_number}</a></h4>"
        '<div class="date-block"><span>Date Filed:</span>'
        '<time datetime="2026-07-02">2026-07-02</time></div></div></div></article>'
    )


def _page(
    *,
    page: int = 1,
    pages: int = 1,
    next_url: str | None = None,
    total_results: int = 1,
    article: str | None = None,
) -> str:
    pagination = ""
    if pages > 1:
        next_link = f'<a href="{next_url}" rel="next">Next</a>' if next_url else ""
        pagination = (
            '<div class="well"><div class="text-center large">'
            f"Page {page} of {pages}</div>{next_link}</div>"
        )
    return (
        "<!doctype html><html><head><title>Search — "
        f"{total_results} Results — CourtListener.com</title></head><body>"
        f'<main id="search-results">{_article() if article is None else article}'
        f"</main>{pagination}</body></html>"
    )


def test_decision_terms_are_the_existing_frozen_eight_without_api_dependency() -> None:
    assert DECISION_FIRST_RECAP_SEARCH_TERMS == DECISION_FIRST_RECAP_API_SEARCH_TERMS
    assert DECISION_FIRST_RECAP_SEARCH_TERMS == (
        'order AND granting AND "motion to dismiss"',
        'order AND denying AND "motion to dismiss"',
        '"motion to dismiss" AND "granted in part"',
        '"order on motion to dismiss"',
        '"memorandum opinion" AND "motion to dismiss"',
        '"report and recommendation" AND "motion to dismiss"',
        'order AND (granting OR denying) AND "judgment on the pleadings"',
        'order AND (granting OR denying) AND "12(b)(6)"',
    )
    source = inspect.getsource(firecrawl_recap_decision_discovery)
    assert "courtlistener_client" not in source
    assert "recap_api_discovery" not in source
    assert "COURTLISTENER_API_TOKEN" not in source


def test_type_r_preset_url_is_phrase_precise_canonical_and_date_anchored() -> None:
    term = DECISION_FIRST_RECAP_SEARCH_TERMS[0]
    url = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    assert url == (
        "https://www.courtlistener.com/?type=r"
        "&q=order+AND+granting+AND+%22motion+to+dismiss%22"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F13%2F2026"
        "&order_by=entry_date_filed+desc"
    )
    assert parse_qs(urlsplit(url).query)["q"] == [term]
    assert parse_decision_recap_search_url(url).term == term


def test_type_r_preset_rejects_api_type_query_drift_and_unknown_terms() -> None:
    url = build_decision_recap_search_url(
        term=DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    for changed in (
        url.replace("type=r", "type=rd"),
        url.replace("order+AND+granting", "order+granting"),
        f"{url}&court=ca9",
        f"{url}&page=01",
    ):
        with pytest.raises(DecisionRecapSearchURLValidationError):
            parse_decision_recap_search_url(changed)


def test_type_r_html_extracts_stable_document_and_docket_identity() -> None:
    url = build_decision_recap_search_url(
        term=DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    parsed = parse_decision_recap_search_html(_page(), source_url=url)
    assert parsed.hits[0].entry_key == "12345:document:27"
    assert parsed.hits[0].docket_id == "12345"
    assert parsed.hits[0].document_number == "27"
    assert parsed.hits[0].provenance.query_term == DECISION_FIRST_RECAP_SEARCH_TERMS[0]
    assert len(parsed.hits[0].provenance.raw_html_sha256) == 64


def test_type_r_pagination_advances_exactly_and_exhausts() -> None:
    term = DECISION_FIRST_RECAP_SEARCH_TERMS[0]
    first = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    second = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    pages = {
        first: _page(page=1, pages=2, next_url=second, total_results=2),
        second: _page(page=2, pages=2, total_results=2),
    }

    class Transport:
        def __init__(self) -> None:
            self.requests: list[str] = []

        def fetch(self, *, source_url: str) -> str:
            self.requests.append(source_url)
            return pages[source_url]

    transport = Transport()
    result = discover_decision_recap_entries(
        transport=transport,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        terms=(term,),
        max_pages_per_term=2,
    )
    assert transport.requests == [first, second]
    assert result.pages_fetched == 2
    assert len(result.entries) == 1
    assert result.duplicate_entry_count == 1


def test_type_r_discovery_reconciles_declared_counts_across_all_pages() -> None:
    term = DECISION_FIRST_RECAP_SEARCH_TERMS[0]
    first = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    second = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    pages = {
        first: _page(page=1, pages=2, next_url=second, total_results=3),
        second: _page(page=2, pages=2, total_results=3),
    }

    class Transport:
        def fetch(self, *, source_url: str) -> str:
            return pages[source_url]

    with pytest.raises(DecisionRecapSearchCompletenessError, match="do not reconcile"):
        discover_decision_recap_entries(
            transport=Transport(),
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            terms=(term,),
            max_pages_per_term=2,
        )


def test_type_r_attachment_identity_does_not_collapse_distinct_files() -> None:
    url = build_decision_recap_search_url(
        term=DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    first = _article().replace(
        "/docket/12345/27/alpha-v-beta/", "/docket/12345/27/100/alpha-v-beta/"
    )
    second = _article().replace(
        "/docket/12345/27/alpha-v-beta/", "/docket/12345/27/2/alpha-v-beta/"
    )
    html = _page(total_results=2, article=first + second)

    class Transport:
        def fetch(self, *, source_url: str) -> str:
            assert source_url == url
            return html

    discovered = discover_decision_recap_entries(
        transport=Transport(),
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        terms=(DECISION_FIRST_RECAP_SEARCH_TERMS[0],),
        max_pages_per_term=1,
    )
    assert [entry.entry_key for entry in discovered.entries] == [
        "12345:document:27:attachment:2",
        "12345:document:27:attachment:100",
    ]


def test_type_r_html_fails_closed_for_truncation_or_identity_mismatch() -> None:
    url = build_decision_recap_search_url(
        term=DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    with pytest.raises(DecisionRecapSearchMarkupError, match="truncated"):
        parse_decision_recap_search_html("<html><body>", source_url=url)
    mismatched = _page().replace(
        "/docket/12345/27/alpha-v-beta/", "/docket/99999/27/alpha-v-beta/"
    )
    with pytest.raises(DecisionRecapSearchMarkupError, match="different docket"):
        parse_decision_recap_search_html(mismatched, source_url=url)


def test_captured_type_rd_web_error_is_rejected_fail_closed() -> None:
    url = build_decision_recap_search_url(
        term=DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    captured = (FIXTURES / "type-rd-error-2026-07-13.html").read_text()
    with pytest.raises(DecisionRecapSearchMarkupError, match="result count"):
        parse_decision_recap_search_html(captured, source_url=url)
