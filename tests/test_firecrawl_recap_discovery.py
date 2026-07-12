from __future__ import annotations

from datetime import date
from urllib.parse import parse_qsl, urlsplit

import pytest
from legalforecast.ingestion.firecrawl_recap_discovery import (
    FROZEN_MTD_SEARCH_TERMS,
    RecapSearchCompletenessError,
    RecapSearchMarkupError,
    RecapSearchURLValidationError,
    build_recap_search_url,
    discover_recap_mtd_entries,
    parse_recap_search_html,
    parse_recap_search_url,
)

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 12)


class FixtureTransport:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    def fetch(self, *, source_url: str) -> str:
        self.requests.append(source_url)
        return self.pages[source_url]


def _search_html(
    *,
    articles: str,
    total_results: int,
    page: int = 1,
    total_pages: int = 1,
    next_href: str | None = None,
) -> str:
    pagination = ""
    if total_pages > 1:
        next_link = (
            f'<a href="{next_href}" rel="next" class="btn">Next</a>'
            if next_href is not None
            else ""
        )
        pagination = (
            '<div class="well"><div class="text-center large">'
            f"Page {page} of {total_pages}</div>{next_link}</div>"
        )
    title = f"Search Results for test — {total_results:,} Results — CourtListener.com"
    return (
        f"<!doctype html><html><head><title>{title}</title></head><body>"
        f'<main id="search-results">{articles}</main>{pagination}</body></html>'
    )


def _article(
    *,
    docket_id: str = "12345",
    document_number: str = "27",
    entry_date: str = "2026-07-02",
    description: str = "Order denying motion to dismiss",
    case_name: str = "Alpha v. Beta",
    minute_entry_id: str | None = None,
    unavailable: bool = False,
) -> str:
    if minute_entry_id is None:
        document_href = f"/docket/{docket_id}/{document_number}/alpha-v-beta/"
    else:
        document_href = (
            f"/docket/{docket_id}/alpha-v-beta/#minute-entry-{minute_entry_id}"
        )
    unavailable_icon = '<i class="fa fa-ban gray"></i>' if unavailable else ""
    docket_href = f"/docket/{docket_id}/alpha-v-beta/"
    return (
        '<article><h3 class="bottom serif">'
        f'<a href="{docket_href}" class="visitable">{case_name}</a>'
        '</h3><div class="bottom"><div class="col-md-offset-half"><h4>'
        f'<a href="{document_href}" class="visitable">'
        f"{description} — Document #{document_number}</a>{unavailable_icon}</h4>"
        '<div class="date-block"><span>Date Filed:</span>'
        f'<time datetime="{entry_date}">'
        f'{entry_date}</time></div><div class="inline-block">'
        '<span>Description:</span><span class="meta-data-value">'
        f"{description}</span></div></div></div></article>"
    )


def test_frozen_vocabulary_is_broad_literal_mtd_only() -> None:
    assert len(FROZEN_MTD_SEARCH_TERMS) >= 15
    assert "motion to dismiss" in FROZEN_MTD_SEARCH_TERMS
    assert "motions to dismiss" in FROZEN_MTD_SEARCH_TERMS
    assert "order dismissing amended complaint" in FROZEN_MTD_SEARCH_TERMS
    assert "report and recommendation motion to dismiss" in FROZEN_MTD_SEARCH_TERMS
    assert "memorandum opinion rule 12(b)(6)" in FROZEN_MTD_SEARCH_TERMS
    assert len(FROZEN_MTD_SEARCH_TERMS) == len(set(FROZEN_MTD_SEARCH_TERMS))
    assert all(
        "judgment on the pleadings" not in term for term in FROZEN_MTD_SEARCH_TERMS
    )


def test_builder_freezes_entry_date_window_and_parameter_order() -> None:
    url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )

    assert url == (
        "https://www.courtlistener.com/?type=r&q=motion+to+dismiss"
        "&entry_date_filed_after=06%2F30%2F2026"
        "&entry_date_filed_before=07%2F12%2F2026"
        "&order_by=entry_date_filed+desc"
    )
    assert parse_recap_search_url(url).page == 1

    page_two = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    assert page_two.endswith("&page=2")
    assert parse_recap_search_url(page_two).page == 2

    page_ten = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=10,
    )
    assert page_ten.endswith("&page=10")
    assert parse_recap_search_url(page_ten).page == 10


@pytest.mark.parametrize(
    "mutation",
    [
        "http://www.courtlistener.com/?type=r",
        "https://evil.example/?type=r",
        "https://www.courtlistener.com/search/?type=r",
        "https://user@www.courtlistener.com/?type=r",
        "https://www.courtlistener.com:443/?type=r",
        "https://www.courtlistener.com/?type=r#fragment",
    ],
)
def test_parser_rejects_noncanonical_origin_or_path(mutation: str) -> None:
    with pytest.raises(RecapSearchURLValidationError):
        parse_recap_search_url(mutation)


def test_parser_rejects_unknown_duplicate_or_noncanonical_query_parameters() -> None:
    valid = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    split = urlsplit(valid)
    params = parse_qsl(split.query, keep_blank_values=True)

    for query in (
        f"{split.query}&court=ca9",
        f"{split.query}&q=motion+to+dismiss",
        split.query.replace("type=r", "type=o"),
        split.query.replace("entry_date_filed+desc", "score+desc"),
        f"{split.query}&page=01",
        f"{split.query}&page=1",
    ):
        with pytest.raises(RecapSearchURLValidationError):
            parse_recap_search_url(f"https://www.courtlistener.com/?{query}")

    assert params[0] == ("type", "r")


def test_builder_rejects_unfrozen_term_or_inverted_window() -> None:
    with pytest.raises(ValueError, match="frozen MTD vocabulary"):
        build_recap_search_url(
            term="dismissed with prejudice",
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
        )
    with pytest.raises(ValueError, match="after must be on or before"):
        build_recap_search_url(
            term="motion to dismiss",
            entry_date_filed_after=WINDOW_END,
            entry_date_filed_before=ANCHOR,
        )


def test_parser_extracts_entry_and_verifiable_provenance() -> None:
    source_url = build_recap_search_url(
        term="motion to dismiss denied",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    html = _search_html(articles=_article(), total_results=1)

    page = parse_recap_search_html(html, source_url=source_url)

    assert page.total_results == 1
    assert page.total_pages == 1
    assert page.next_url is None
    assert page.complete is True
    assert len(page.hits) == 1
    hit = page.hits[0]
    assert hit.entry_key == "12345:document:27"
    assert hit.docket_id == "12345"
    assert hit.document_number == "27"
    assert hit.entry_date_filed == date(2026, 7, 2)
    assert hit.description == "Order denying motion to dismiss"
    assert hit.case_name == "Alpha v. Beta"
    assert hit.docket_url == "https://www.courtlistener.com/docket/12345/alpha-v-beta/"
    assert hit.document_url == (
        "https://www.courtlistener.com/docket/12345/27/alpha-v-beta/"
    )
    assert hit.provenance.query_term == "motion to dismiss denied"
    assert hit.provenance.search_url == source_url
    assert hit.provenance.page == 1
    assert hit.provenance.result_ordinal == 1
    assert hit.provenance.entry_ordinal == 1
    assert len(hit.provenance.raw_html_sha256) == 64


def test_parser_supports_numberless_minute_entries_and_availability() -> None:
    source_url = build_recap_search_url(
        term="minute order motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    html = _search_html(
        articles=_article(minute_entry_id="9988", unavailable=True),
        total_results=1,
    )

    hit = parse_recap_search_html(html, source_url=source_url).hits[0]

    assert hit.entry_key == "12345:entry:9988"
    assert hit.docket_entry_id == "9988"
    assert hit.is_available is False


def test_parser_accepts_courtlistener_iso_datetime_for_entry_date() -> None:
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    html = _search_html(
        articles=_article(entry_date="2026-07-02T00:00:00-04:00"),
        total_results=1,
    )

    hit = parse_recap_search_html(html, source_url=source_url).hits[0]

    assert hit.entry_date_filed == date(2026, 7, 2)


def test_parser_validates_deterministic_pagination() -> None:
    first_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    second_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    html = _search_html(
        articles=_article(),
        total_results=2,
        total_pages=2,
        next_href=f"?{urlsplit(second_url).query}",
    )

    page = parse_recap_search_html(html, source_url=first_url)

    assert page.total_pages == 2
    assert page.next_url == second_url
    assert page.complete is False


def _malformed_html_cases() -> tuple[str, ...]:
    return (
        _search_html(articles=_article(), total_results=1)[:-7],
        "<html><body>Access denied</body></html>",
        _search_html(articles="", total_results=1),
        _search_html(articles=_article(entry_date="2026-06-29"), total_results=1),
        _search_html(
            articles=_article(), total_results=2, total_pages=2, next_href=None
        ),
        _search_html(
            articles=_article(),
            total_results=2,
            total_pages=2,
            next_href="?type=r&q=motion+to+dismiss&page=2",
        ),
    )


@pytest.mark.parametrize("raw_html", _malformed_html_cases())
def test_parser_fails_closed_on_truncation_markup_or_pagination(
    raw_html: str,
) -> None:
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    with pytest.raises(RecapSearchMarkupError):
        parse_recap_search_html(raw_html, source_url=source_url)


def test_scheduler_paginates_every_term_then_dedupes_entries_and_dockets() -> None:
    terms = ("motion to dismiss", "motion to dismiss denied")
    term_one_page_one = build_recap_search_url(
        term=terms[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    term_one_page_two = build_recap_search_url(
        term=terms[0],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    term_two_page_one = build_recap_search_url(
        term=terms[1],
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    pages = {
        term_one_page_one: _search_html(
            articles=_article(document_number="27"),
            total_results=2,
            total_pages=2,
            next_href=f"?{urlsplit(term_one_page_two).query}",
        ),
        term_one_page_two: _search_html(
            articles=_article(document_number="28", entry_date="2026-07-03"),
            total_results=2,
            page=2,
            total_pages=2,
        ),
        term_two_page_one: _search_html(
            articles=_article(document_number="27"), total_results=1
        ),
    }
    transport = FixtureTransport(pages)

    result = discover_recap_mtd_entries(
        transport=transport,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        terms=terms,
    )

    assert transport.requests == [
        term_one_page_one,
        term_one_page_two,
        term_two_page_one,
    ]
    assert result.complete is True
    assert result.pages_fetched == 3
    assert result.raw_hit_count == 3
    assert result.duplicate_entry_count == 1
    assert [entry.entry_key for entry in result.entries] == [
        "12345:document:27",
        "12345:document:28",
    ]
    assert result.entries[0].matched_terms == terms
    assert len(result.entries[0].provenances) == 2
    assert len(result.dockets) == 1
    assert result.dockets[0].docket_id == "12345"
    assert result.dockets[0].entry_keys == (
        "12345:document:27",
        "12345:document:28",
    )


def test_scheduler_fails_closed_instead_of_returning_partial_at_page_cap() -> None:
    first_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    second_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    transport = FixtureTransport(
        {
            first_url: _search_html(
                articles=_article(),
                total_results=2,
                total_pages=2,
                next_href=f"?{urlsplit(second_url).query}",
            )
        }
    )

    with pytest.raises(RecapSearchCompletenessError, match="page cap"):
        discover_recap_mtd_entries(
            transport=transport,
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            terms=("motion to dismiss",),
            max_pages_per_term=1,
        )
