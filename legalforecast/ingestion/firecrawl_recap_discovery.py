"""Anchored CourtListener RECAP entry discovery over scraped search HTML.

This module is deliberately transport-neutral: callers provide a Firecrawl-backed
``RecapSearchHTMLTransport`` whose budget policy lives outside the discovery
logic.  Everything here is pure and deterministic apart from that one transport
call.  Search URLs use CourtListener's RECAP-specific *entry* filing date fields,
not the docket-level ``filed_after`` and ``filed_before`` fields.

The parser fails closed.  It requires a complete HTML document, a recognizable
CourtListener result count, internally consistent pagination, strict docket and
document links, and an entry date inside the requested inclusive window.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

COURTLISTENER_RECAP_SEARCH_ORIGIN = "https://www.courtlistener.com"
COURTLISTENER_RECAP_SEARCH_URL = f"{COURTLISTENER_RECAP_SEARCH_ORIGIN}/"

# This vocabulary is a versioned acquisition input.  Additions require an
# intentional code change and artifact snapshot. Rule 12(c) and judgment-on-
# the-pleadings formulations are included because they can renew or
# alternatively frame a motion to dismiss and are eligible when every other
# corpus gate is satisfied.
FROZEN_MTD_SEARCH_TERMS: tuple[str, ...] = (
    "motion to dismiss",
    "motions to dismiss",
    "motion to dismiss granted",
    "motion to dismiss denied",
    "motion to dismiss granted in part",
    "motion to dismiss denied in part",
    "ruling on motion to dismiss",
    "order on motion to dismiss",
    "minute order motion to dismiss",
    "text order motion to dismiss",
    "order dismissing complaint",
    "order dismissing amended complaint",
    "report and recommendation motion to dismiss",
    "findings and recommendation motion to dismiss",
    "order adopting report and recommendation motion to dismiss",
    "memorandum opinion rule 12(b)(6)",
    "order rule 12(b)(6)",
    "order rule 12(b)(1)",
    "order rule 12(b)(2)",
    "motion for judgment on the pleadings",
    "order on motion for judgment on the pleadings",
    "order rule 12(c)",
    "motion to dismiss adversary complaint",
    "order dismissing adversary complaint",
    "report and recommendation motion to dismiss adversary complaint",
    "order rule 7012",
    "memorandum opinion rule 7012",
    "order adopting report and recommendation rule 7012",
)

# CourtListener does not treat an unquoted multiword query as one legal phrase.
# The vocabulary above remains the stable logical identity in provenance; this
# versioned compiler controls only the provider query expression.
COURTLISTENER_QUERY_PLAN_VERSION = "phrase-precise-v2"
_COURTLISTENER_QUERY_EXPRESSIONS: dict[str, str] = {
    "motion to dismiss": '"motion to dismiss"',
    "motions to dismiss": '"motions to dismiss"',
    "motion to dismiss granted": '"motion to dismiss" AND granted',
    "motion to dismiss denied": '"motion to dismiss" AND denied',
    "motion to dismiss granted in part": '"motion to dismiss" AND "granted in part"',
    "motion to dismiss denied in part": '"motion to dismiss" AND "denied in part"',
    "ruling on motion to dismiss": '"motion to dismiss" AND ruling',
    "order on motion to dismiss": '"motion to dismiss" AND order',
    "minute order motion to dismiss": '"motion to dismiss" AND "minute order"',
    "text order motion to dismiss": '"motion to dismiss" AND "text order"',
    "order dismissing complaint": '"dismissing complaint" AND order',
    "order dismissing amended complaint": '"dismissing amended complaint" AND order',
    "report and recommendation motion to dismiss": (
        '"motion to dismiss" AND "report and recommendation"'
    ),
    "findings and recommendation motion to dismiss": (
        '"motion to dismiss" AND "findings and recommendation"'
    ),
    "order adopting report and recommendation motion to dismiss": (
        '"motion to dismiss" AND "report and recommendation" AND adopting'
    ),
    "memorandum opinion rule 12(b)(6)": '"rule 12(b)(6)" AND "memorandum opinion"',
    "order rule 12(b)(6)": '"rule 12(b)(6)" AND order',
    "order rule 12(b)(1)": '"rule 12(b)(1)" AND order',
    "order rule 12(b)(2)": '"rule 12(b)(2)" AND order',
    "motion for judgment on the pleadings": '"motion for judgment on the pleadings"',
    "order on motion for judgment on the pleadings": (
        '"motion for judgment on the pleadings" AND order'
    ),
    "order rule 12(c)": '"rule 12(c)" AND order',
    "motion to dismiss adversary complaint": (
        '"motion to dismiss" AND "adversary complaint"'
    ),
    "order dismissing adversary complaint": (
        '"dismissing adversary complaint" AND order'
    ),
    "report and recommendation motion to dismiss adversary complaint": (
        '"motion to dismiss" AND "adversary complaint" AND "report and recommendation"'
    ),
    "order rule 7012": '"rule 7012" AND order',
    "memorandum opinion rule 7012": '"rule 7012" AND "memorandum opinion"',
    "order adopting report and recommendation rule 7012": (
        '"rule 7012" AND "report and recommendation" AND adopting'
    ),
}
if tuple(_COURTLISTENER_QUERY_EXPRESSIONS) != FROZEN_MTD_SEARCH_TERMS:
    raise RuntimeError(
        "CourtListener query plan must exactly cover the ordered frozen vocabulary"
    )
if len(set(_COURTLISTENER_QUERY_EXPRESSIONS.values())) != len(
    _COURTLISTENER_QUERY_EXPRESSIONS
):
    raise RuntimeError("CourtListener query expressions must be unique")

_ALLOWED_QUERY_KEYS = frozenset(
    {
        "type",
        "q",
        "entry_date_filed_after",
        "entry_date_filed_before",
        "order_by",
        "page",
    }
)
_REQUIRED_QUERY_KEYS = _ALLOWED_QUERY_KEYS - {"page"}
_DOCKET_LINK = re.compile(r"^/docket/(?P<docket_id>[1-9][0-9]*)/[^/?#]+/$")
_DOCUMENT_LINK = re.compile(
    r"^/docket/(?P<docket_id>[1-9][0-9]*)/"
    r"(?P<document_number>[^/?#]+)/"
    r"(?:(?P<attachment_number>[1-9][0-9]*)/)?[^/?#]+/$"
)
_MINUTE_ENTRY_FRAGMENT = re.compile(r"^minute-entry-(?P<entry_id>[1-9][0-9]*)$")
_TITLE_RESULT_COUNT = re.compile(
    r"(?:^|\s|—)(?P<count>[0-9][0-9,]*)\s+Results?(?:\s|—|$)", re.I
)
_PAGE_INDICATOR = re.compile(
    r"^Page\s+(?P<page>[0-9][0-9,]*)\s+of\s+"
    r"(?P<pages>[0-9][0-9,]*)$",
    re.I,
)
_DOCUMENT_LABEL = re.compile(r"\s*(?:—|-)\s*Document\s*#.*$", re.I)


class RecapSearchError(RuntimeError):
    """Base class for anchored RECAP discovery failures."""


class RecapSearchURLValidationError(RecapSearchError):
    """Raised when a search or result URL escapes the frozen allowlist."""


class RecapSearchMarkupError(RecapSearchError):
    """Raised when scraped CourtListener HTML cannot be proven complete."""


class RecapSearchCompletenessError(RecapSearchError):
    """Raised instead of returning a partial discovery run."""


@dataclass(frozen=True, slots=True)
class RecapSearchTarget:
    """Canonical CourtListener RECAP search-page identity."""

    term: str
    entry_date_filed_after: date
    entry_date_filed_before: date
    page: int
    url: str


@dataclass(frozen=True, slots=True)
class RecapSearchProvenance:
    """Evidence locating one hit in one immutable raw search response."""

    query_term: str
    search_url: str
    page: int
    result_ordinal: int
    entry_ordinal: int
    raw_html_sha256: str


@dataclass(frozen=True, slots=True)
class RecapSearchHit:
    """One anchored docket entry emitted by one RECAP search page."""

    entry_key: str
    docket_id: str
    docket_entry_id: str | None
    document_number: str | None
    attachment_number: int | None
    docket_url: str
    document_url: str
    entry_date_filed: date
    case_name: str
    description: str
    is_available: bool
    provenance: RecapSearchProvenance


@dataclass(frozen=True, slots=True)
class RecapSearchPage:
    """A validated page with explicit continuation evidence."""

    target: RecapSearchTarget
    hits: tuple[RecapSearchHit, ...]
    total_results: int
    total_pages: int
    next_url: str | None
    result_card_count: int | None = None

    @property
    def complete(self) -> bool:
        return self.next_url is None


@dataclass(frozen=True, slots=True)
class RecapDiscoveredEntry:
    """Entry-level union across terms and pages."""

    entry_key: str
    docket_id: str
    docket_entry_id: str | None
    document_number: str | None
    attachment_number: int | None
    docket_url: str
    document_url: str
    entry_date_filed: date
    case_name: str
    description: str
    is_available: bool
    matched_terms: tuple[str, ...]
    provenances: tuple[RecapSearchProvenance, ...]


@dataclass(frozen=True, slots=True)
class RecapDiscoveredDocket:
    """Docket-level union retained alongside the entry-level corpus."""

    docket_id: str
    docket_url: str
    entry_keys: tuple[str, ...]
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecapDiscoveryRun:
    """Complete, deterministic result of all requested vocabulary terms."""

    entries: tuple[RecapDiscoveredEntry, ...]
    dockets: tuple[RecapDiscoveredDocket, ...]
    terms: tuple[str, ...]
    pages_fetched: int
    raw_hit_count: int
    duplicate_entry_count: int
    complete: bool = True


class RecapSearchHTMLTransport(Protocol):
    """Firecrawl adapter seam; implementations enforce the shared credit cap."""

    def fetch(self, *, source_url: str) -> str: ...


def courtlistener_query_expression(term: str) -> str:
    """Compile one frozen logical term to its precise provider query."""

    _validate_term(term)
    return _COURTLISTENER_QUERY_EXPRESSIONS[term]


def build_recap_search_url(
    *,
    term: str,
    entry_date_filed_after: date,
    entry_date_filed_before: date,
    page: int = 1,
) -> str:
    """Build one canonical, entry-date-anchored CourtListener RECAP URL."""

    _validate_term(term)
    _validate_window(entry_date_filed_after, entry_date_filed_before)
    if type(page) is not int or page <= 0:
        raise ValueError("page must be a positive integer")
    params: list[tuple[str, str]] = [
        ("type", "r"),
        ("q", courtlistener_query_expression(term)),
        ("entry_date_filed_after", entry_date_filed_after.strftime("%m/%d/%Y")),
        ("entry_date_filed_before", entry_date_filed_before.strftime("%m/%d/%Y")),
        ("order_by", "entry_date_filed desc"),
    ]
    if page > 1:
        params.append(("page", str(page)))
    return f"{COURTLISTENER_RECAP_SEARCH_URL}?{urlencode(params)}"


def parse_recap_search_url(source_url: str) -> RecapSearchTarget:
    """Validate and normalize an allowlisted CourtListener RECAP search URL."""

    split = urlsplit(source_url)
    if (
        split.scheme != "https"
        or split.hostname != "www.courtlistener.com"
        or split.netloc != "www.courtlistener.com"
        or split.path != "/"
        or split.fragment
    ):
        raise RecapSearchURLValidationError(
            "RECAP search URL must be canonical HTTPS www.courtlistener.com/"
        )
    pairs = parse_qsl(split.query, keep_blank_values=True, strict_parsing=True)
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        raise RecapSearchURLValidationError("RECAP search query keys must be unique")
    key_set = set(keys)
    if not _REQUIRED_QUERY_KEYS.issubset(key_set) or not key_set.issubset(
        _ALLOWED_QUERY_KEYS
    ):
        raise RecapSearchURLValidationError(
            "RECAP search query must use the exact frozen parameter allowlist"
        )
    values = dict(pairs)
    if values["type"] != "r":
        raise RecapSearchURLValidationError("RECAP search type must be r")
    expression = values["q"]
    try:
        term = next(
            logical_term
            for logical_term, query_expression in (
                _COURTLISTENER_QUERY_EXPRESSIONS.items()
            )
            if query_expression == expression
        )
    except StopIteration as exc:
        raise RecapSearchURLValidationError(
            "RECAP search query is not in the frozen CourtListener query plan"
        ) from exc
    if values["order_by"] != "entry_date_filed desc":
        raise RecapSearchURLValidationError(
            "RECAP search must order by newest docket entry first"
        )
    entry_date_filed_after = _parse_search_date(
        values["entry_date_filed_after"], key="entry_date_filed_after"
    )
    entry_date_filed_before = _parse_search_date(
        values["entry_date_filed_before"], key="entry_date_filed_before"
    )
    try:
        _validate_window(entry_date_filed_after, entry_date_filed_before)
    except ValueError as exc:
        raise RecapSearchURLValidationError(str(exc)) from exc
    raw_page = values.get("page")
    page = 1
    if raw_page is not None:
        if not re.fullmatch(r"[1-9][0-9]*", raw_page) or int(raw_page) < 2:
            raise RecapSearchURLValidationError(
                "page must be a canonical integer greater than one"
            )
        page = int(raw_page)
    canonical = build_recap_search_url(
        term=term,
        entry_date_filed_after=entry_date_filed_after,
        entry_date_filed_before=entry_date_filed_before,
        page=page,
    )
    return RecapSearchTarget(
        term=term,
        entry_date_filed_after=entry_date_filed_after,
        entry_date_filed_before=entry_date_filed_before,
        page=page,
        url=canonical,
    )


def parse_recap_search_html(
    raw_html: str,
    *,
    source_url: str,
) -> RecapSearchPage:
    """Parse one search page and reject any unprovable/truncated response."""

    return parse_recap_search_html_with_plan(
        raw_html,
        source_url=source_url,
        parse_search_url=parse_recap_search_url,
        build_search_url=build_recap_search_url,
    )


def parse_recap_search_html_with_plan(
    raw_html: str,
    *,
    source_url: str,
    parse_search_url: Callable[[str], RecapSearchTarget],
    build_search_url: Callable[..., str],
) -> RecapSearchPage:
    """Shared fail-closed parser for allowlisted RECAP HTML search plans."""

    target = parse_search_url(source_url)
    if not raw_html.strip() or not re.search(r"</html>\s*$", raw_html, re.I):
        raise RecapSearchMarkupError("RECAP search HTML is empty or truncated")
    parser = _RecapResultHTMLParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except RecapSearchMarkupError:
        raise
    except Exception as exc:
        raise RecapSearchMarkupError("RECAP search HTML parsing failed") from exc
    if not parser.closed_html or not parser.closed_body:
        raise RecapSearchMarkupError("RECAP search HTML lacks closing document tags")
    title = _normalized_text(parser.title_text)
    title_match = _TITLE_RESULT_COUNT.search(title)
    if title_match is None:
        raise RecapSearchMarkupError(
            "RECAP search result count is missing from the page title"
        )
    total_results = _comma_int(title_match.group("count"), label="result count")
    article_builders = parser.articles
    if total_results == 0:
        if article_builders:
            raise RecapSearchMarkupError(
                "zero-result page unexpectedly contains results"
            )
    elif not article_builders:
        raise RecapSearchMarkupError("nonzero RECAP page contains no result articles")

    total_pages, next_url = _validated_pagination(
        parser=parser,
        target=target,
        total_results=total_results,
        article_count=len(article_builders),
        parse_search_url=parse_search_url,
        build_search_url=build_search_url,
    )
    raw_html_sha256 = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    hits: list[RecapSearchHit] = []
    for result_ordinal, article in enumerate(article_builders, start=1):
        hits.extend(
            _article_hits(
                article,
                target=target,
                result_ordinal=result_ordinal,
                raw_html_sha256=raw_html_sha256,
            )
        )
    if total_results > 0 and not hits:
        raise RecapSearchMarkupError("RECAP result articles contain no entry hits")
    return RecapSearchPage(
        target=target,
        hits=tuple(hits),
        total_results=total_results,
        total_pages=total_pages,
        result_card_count=len(article_builders),
        next_url=next_url,
    )


def discover_recap_mtd_entries(
    *,
    transport: RecapSearchHTMLTransport,
    entry_date_filed_after: date,
    entry_date_filed_before: date,
    terms: Sequence[str] = FROZEN_MTD_SEARCH_TERMS,
    max_pages_per_term: int = 1_000,
) -> RecapDiscoveryRun:
    """Exhaust every term, then return stable entry- and docket-level unions."""

    return discover_recap_entries_with_plan(
        transport=transport,
        entry_date_filed_after=entry_date_filed_after,
        entry_date_filed_before=entry_date_filed_before,
        terms=terms,
        max_pages_per_term=max_pages_per_term,
        validate_terms=_validated_terms,
        build_search_url=build_recap_search_url,
        parse_search_html=parse_recap_search_html,
    )


def discover_recap_entries_with_plan(
    *,
    transport: RecapSearchHTMLTransport,
    entry_date_filed_after: date,
    entry_date_filed_before: date,
    terms: Sequence[str],
    max_pages_per_term: int,
    validate_terms: Callable[[Sequence[str]], tuple[str, ...]],
    build_search_url: Callable[..., str],
    parse_search_html: Callable[..., RecapSearchPage],
    reconcile_declared_counts: bool = False,
) -> RecapDiscoveryRun:
    """Exhaust a frozen RECAP HTML query plan and return stable unions."""

    _validate_window(entry_date_filed_after, entry_date_filed_before)
    validated_terms = validate_terms(terms)
    if type(max_pages_per_term) is not int or max_pages_per_term <= 0:
        raise ValueError("max_pages_per_term must be positive")
    raw_hits: list[RecapSearchHit] = []
    pages_fetched = 0
    for term in validated_terms:
        next_url: str | None = build_search_url(
            term=term,
            entry_date_filed_after=entry_date_filed_after,
            entry_date_filed_before=entry_date_filed_before,
        )
        seen_urls: set[str] = set()
        pages_for_term = 0
        declared_total_results: int | None = None
        declared_total_pages: int | None = None
        accumulated_result_cards = 0
        while next_url is not None:
            if next_url in seen_urls:
                raise RecapSearchCompletenessError(
                    f"RECAP pagination repeated a URL for term: {term}"
                )
            if pages_for_term >= max_pages_per_term:
                raise RecapSearchCompletenessError(
                    f"RECAP search reached the page cap before exhaustion: {term}"
                )
            seen_urls.add(next_url)
            raw_html = transport.fetch(source_url=next_url)
            page = parse_search_html(raw_html, source_url=next_url)
            if declared_total_results is None:
                declared_total_results = page.total_results
                declared_total_pages = page.total_pages
            elif reconcile_declared_counts and (
                page.total_results != declared_total_results
                or page.total_pages != declared_total_pages
            ):
                raise RecapSearchCompletenessError(
                    f"RECAP result or page count changed during pagination: {term}"
                )
            if reconcile_declared_counts and page.result_card_count is None:
                raise RecapSearchCompletenessError(
                    f"RECAP result-card count is unavailable: {term}"
                )
            accumulated_result_cards += page.result_card_count or 0
            raw_hits.extend(page.hits)
            next_url = page.next_url
            pages_for_term += 1
            pages_fetched += 1
        assert declared_total_results is not None
        assert declared_total_pages is not None
        if reconcile_declared_counts and pages_for_term != declared_total_pages:
            raise RecapSearchCompletenessError(
                f"RECAP pagination did not visit every declared page: {term}"
            )
        if (
            reconcile_declared_counts
            and accumulated_result_cards != declared_total_results
        ):
            raise RecapSearchCompletenessError(
                "RECAP result cards do not reconcile to the declared result count: "
                f"{term}"
            )

    entries = _dedupe_entries(raw_hits, term_order=validated_terms)
    dockets = _dedupe_dockets(entries, term_order=validated_terms)
    return RecapDiscoveryRun(
        entries=entries,
        dockets=dockets,
        terms=validated_terms,
        pages_fetched=pages_fetched,
        raw_hit_count=len(raw_hits),
        duplicate_entry_count=len(raw_hits) - len(entries),
    )


@dataclass(slots=True)
class _EntryBuilder:
    link_href: str | None = None
    link_text: str = ""
    entry_date: str | None = None
    unavailable: bool = False


@dataclass(slots=True)
class _ArticleBuilder:
    docket_href: str | None = None
    docket_text: str = ""
    entries: list[_EntryBuilder] | None = None

    def __post_init__(self) -> None:
        if self.entries is None:
            self.entries = []


class _RecapResultHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_text = ""
        self.pagination_text = ""
        self.next_hrefs: list[str] = []
        self.articles: list[_ArticleBuilder] = []
        self.closed_html = False
        self.closed_body = False
        self._in_title = False
        self._in_pagination = False
        self._article: _ArticleBuilder | None = None
        self._in_h3 = False
        self._in_h4 = False
        self._capture_docket_anchor = False
        self._capture_entry_anchor = False
        self._entry: _EntryBuilder | None = None
        self._entry_div_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = frozenset(values.get("class", "").split())
        if tag == "title":
            self._in_title = True
        if tag == "article":
            if self._article is not None:
                raise RecapSearchMarkupError("nested RECAP result articles")
            self._article = _ArticleBuilder()
        elif self._article is not None and tag == "h3":
            self._in_h3 = True
        elif (
            self._article is not None
            and tag == "div"
            and "col-md-offset-half" in classes
        ):
            if self._entry is not None:
                raise RecapSearchMarkupError("nested RECAP entry result containers")
            self._entry = _EntryBuilder()
            self._entry_div_depth = 1
        elif self._entry is not None and tag == "div":
            self._entry_div_depth += 1
        if self._entry is not None and tag == "h4":
            self._in_h4 = True
        if tag == "a":
            rel = frozenset(values.get("rel", "").split())
            if "next" in rel:
                self.next_hrefs.append(values.get("href", ""))
            if self._in_h3 and self._article is not None:
                if self._article.docket_href is not None:
                    raise RecapSearchMarkupError(
                        "result has multiple docket title links"
                    )
                self._article.docket_href = values.get("href", "")
                self._capture_docket_anchor = True
            elif self._in_h4 and self._entry is not None:
                if self._entry.link_href is not None:
                    raise RecapSearchMarkupError("entry heading has multiple links")
                self._entry.link_href = values.get("href", "")
                self._capture_entry_anchor = True
        if self._entry is not None and tag == "time" and "datetime" in values:
            if self._entry.entry_date is not None:
                raise RecapSearchMarkupError("entry has multiple filed dates")
            self._entry.entry_date = values["datetime"]
        if (
            self._entry is not None
            and tag == "i"
            and {"fa", "fa-ban"}.issubset(classes)
        ):
            self._entry.unavailable = True
        if tag == "div" and {"text-center", "large"}.issubset(classes):
            self._in_pagination = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "html":
            self.closed_html = True
        elif tag == "body":
            self.closed_body = True
        elif tag == "title":
            self._in_title = False
        elif tag == "a":
            self._capture_docket_anchor = False
            self._capture_entry_anchor = False
        elif tag == "h3":
            self._in_h3 = False
        elif tag == "h4":
            self._in_h4 = False
        elif tag == "div" and self._entry is not None:
            self._entry_div_depth -= 1
            if self._entry_div_depth == 0:
                if self._entry.link_href is not None:
                    assert self._article is not None
                    assert self._article.entries is not None
                    self._article.entries.append(self._entry)
                self._entry = None
        if tag == "div" and self._in_pagination:
            self._in_pagination = False
        if tag == "article":
            if self._article is None:
                raise RecapSearchMarkupError("unmatched result article close tag")
            self.articles.append(self._article)
            self._article = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data
        if self._in_pagination:
            self.pagination_text += data
        if self._capture_docket_anchor and self._article is not None:
            self._article.docket_text += data
        if self._capture_entry_anchor and self._entry is not None:
            self._entry.link_text += data


def _validated_pagination(
    *,
    parser: _RecapResultHTMLParser,
    target: RecapSearchTarget,
    total_results: int,
    article_count: int,
    parse_search_url: Callable[[str], RecapSearchTarget],
    build_search_url: Callable[..., str],
) -> tuple[int, str | None]:
    page_text = _normalized_text(parser.pagination_text)
    if page_text:
        match = _PAGE_INDICATOR.fullmatch(page_text)
        if match is None:
            raise RecapSearchMarkupError("RECAP pagination marker is malformed")
        displayed_page = _comma_int(match.group("page"), label="page number")
        total_pages = _comma_int(match.group("pages"), label="page count")
        if displayed_page != target.page or total_pages < displayed_page:
            raise RecapSearchMarkupError("RECAP pagination marker is inconsistent")
    else:
        total_pages = 1
        if target.page != 1 or total_results > article_count:
            raise RecapSearchMarkupError(
                "RECAP page lacks pagination evidence required for completeness"
            )
    if len(parser.next_hrefs) > 1:
        raise RecapSearchMarkupError("RECAP page has multiple next-page links")
    expected_next: str | None = None
    if target.page < total_pages:
        expected_next = build_search_url(
            term=target.term,
            entry_date_filed_after=target.entry_date_filed_after,
            entry_date_filed_before=target.entry_date_filed_before,
            page=target.page + 1,
        )
        if len(parser.next_hrefs) != 1:
            raise RecapSearchMarkupError("RECAP page is missing its next-page link")
        href = parser.next_hrefs[0]
        candidate = urljoin(COURTLISTENER_RECAP_SEARCH_URL, href)
        try:
            normalized_next = parse_search_url(candidate).url
        except (RecapSearchURLValidationError, ValueError) as exc:
            raise RecapSearchMarkupError(
                "RECAP next-page link escapes the frozen search"
            ) from exc
        if normalized_next != expected_next:
            raise RecapSearchMarkupError(
                "RECAP next-page link does not advance the same search by one page"
            )
    elif parser.next_hrefs:
        raise RecapSearchMarkupError("terminal RECAP page unexpectedly has a next link")
    return total_pages, expected_next


def _article_hits(
    article: _ArticleBuilder,
    *,
    target: RecapSearchTarget,
    result_ordinal: int,
    raw_html_sha256: str,
) -> list[RecapSearchHit]:
    if article.docket_href is None:
        raise RecapSearchMarkupError("RECAP result lacks a docket link")
    docket_url, docket_id = _validated_docket_link(article.docket_href)
    assert article.entries is not None
    if not article.entries:
        raise RecapSearchMarkupError("RECAP result lacks docket-entry links")
    case_name = _normalized_text(article.docket_text)
    if not case_name:
        raise RecapSearchMarkupError("RECAP result lacks a case name")
    hits: list[RecapSearchHit] = []
    for entry_ordinal, entry in enumerate(article.entries, start=1):
        if entry.link_href is None or entry.entry_date is None:
            raise RecapSearchMarkupError("RECAP entry lacks its link or filed date")
        (
            document_url,
            link_docket_id,
            entry_key,
            docket_entry_id,
            document_number,
            attachment_number,
        ) = _validated_entry_link(entry.link_href)
        if link_docket_id != docket_id:
            raise RecapSearchMarkupError("entry link points at a different docket")
        entry_date_filed = _parse_entry_date(entry.entry_date)
        if not (
            target.entry_date_filed_after
            <= entry_date_filed
            <= target.entry_date_filed_before
        ):
            raise RecapSearchMarkupError(
                "RECAP returned an entry outside the inclusive anchor window"
            )
        description = _DOCUMENT_LABEL.sub("", _normalized_text(entry.link_text))
        hits.append(
            RecapSearchHit(
                entry_key=entry_key,
                docket_id=docket_id,
                docket_entry_id=docket_entry_id,
                document_number=document_number,
                attachment_number=attachment_number,
                docket_url=docket_url,
                document_url=document_url,
                entry_date_filed=entry_date_filed,
                case_name=case_name,
                description=description,
                is_available=not entry.unavailable,
                provenance=RecapSearchProvenance(
                    query_term=target.term,
                    search_url=target.url,
                    page=target.page,
                    result_ordinal=result_ordinal,
                    entry_ordinal=entry_ordinal,
                    raw_html_sha256=raw_html_sha256,
                ),
            )
        )
    return hits


def _validated_docket_link(href: str) -> tuple[str, str]:
    url = urljoin(COURTLISTENER_RECAP_SEARCH_URL, href)
    split = urlsplit(url)
    if (
        split.scheme != "https"
        or split.netloc != "www.courtlistener.com"
        or split.query
        or split.fragment
    ):
        raise RecapSearchMarkupError("result docket link is not allowlisted")
    match = _DOCKET_LINK.fullmatch(split.path)
    if match is None:
        raise RecapSearchMarkupError("result docket link has an unknown shape")
    return url, match.group("docket_id")


def _validated_entry_link(
    href: str,
) -> tuple[str, str, str, str | None, str | None, int | None]:
    url = urljoin(COURTLISTENER_RECAP_SEARCH_URL, href)
    split = urlsplit(url)
    if (
        split.scheme != "https"
        or split.netloc != "www.courtlistener.com"
        or split.query
    ):
        raise RecapSearchMarkupError("result entry link is not allowlisted")
    minute_match = _MINUTE_ENTRY_FRAGMENT.fullmatch(split.fragment)
    if minute_match is not None:
        docket_match = _DOCKET_LINK.fullmatch(split.path)
        if docket_match is None:
            raise RecapSearchMarkupError("minute-entry link has an unknown shape")
        docket_id = docket_match.group("docket_id")
        entry_id = minute_match.group("entry_id")
        return url, docket_id, f"{docket_id}:entry:{entry_id}", entry_id, None, None
    if split.fragment:
        raise RecapSearchMarkupError("result entry link has an unknown fragment")
    document_match = _DOCUMENT_LINK.fullmatch(split.path)
    if document_match is None:
        raise RecapSearchMarkupError("document link has an unknown shape")
    docket_id = document_match.group("docket_id")
    document_number = document_match.group("document_number")
    raw_attachment_number = document_match.group("attachment_number")
    attachment_number = (
        int(raw_attachment_number) if raw_attachment_number is not None else None
    )
    return (
        url,
        docket_id,
        f"{docket_id}:document:{document_number}",
        None,
        document_number,
        attachment_number,
    )


def _dedupe_entries(
    hits: Sequence[RecapSearchHit], *, term_order: Sequence[str]
) -> tuple[RecapDiscoveredEntry, ...]:
    by_key: dict[str, list[RecapSearchHit]] = {}
    for hit in hits:
        dedupe_key = hit.entry_key
        if hit.attachment_number is not None:
            dedupe_key = f"{dedupe_key}:attachment:{hit.attachment_number}"
        by_key.setdefault(dedupe_key, []).append(hit)
    term_rank = {term: index for index, term in enumerate(term_order)}
    entries: list[RecapDiscoveredEntry] = []
    for entry_key in sorted(
        by_key,
        key=lambda key: _hit_identity_sort_key(by_key[key][0]),
    ):
        grouped_hits = by_key[entry_key]
        canonical = grouped_hits[0]
        for other in grouped_hits[1:]:
            if (
                other.docket_id != canonical.docket_id
                or other.entry_date_filed != canonical.entry_date_filed
                or other.document_number != canonical.document_number
                or other.docket_entry_id != canonical.docket_entry_id
                or other.attachment_number != canonical.attachment_number
                or other.document_url != canonical.document_url
            ):
                raise RecapSearchCompletenessError(
                    f"conflicting duplicate RECAP entry identity: {entry_key}"
                )
        matched_terms = tuple(
            sorted(
                {hit.provenance.query_term for hit in grouped_hits},
                key=term_rank.__getitem__,
            )
        )
        provenances = tuple(
            sorted(
                {hit.provenance for hit in grouped_hits},
                key=lambda item: (
                    term_rank[item.query_term],
                    item.page,
                    item.result_ordinal,
                    item.entry_ordinal,
                    item.raw_html_sha256,
                ),
            )
        )
        entries.append(
            RecapDiscoveredEntry(
                entry_key=entry_key,
                docket_id=canonical.docket_id,
                docket_entry_id=canonical.docket_entry_id,
                document_number=canonical.document_number,
                attachment_number=canonical.attachment_number,
                docket_url=canonical.docket_url,
                document_url=canonical.document_url,
                entry_date_filed=canonical.entry_date_filed,
                case_name=canonical.case_name,
                description=canonical.description,
                is_available=any(hit.is_available for hit in grouped_hits),
                matched_terms=matched_terms,
                provenances=provenances,
            )
        )
    return tuple(entries)


def _dedupe_dockets(
    entries: Sequence[RecapDiscoveredEntry], *, term_order: Sequence[str]
) -> tuple[RecapDiscoveredDocket, ...]:
    by_docket: dict[str, list[RecapDiscoveredEntry]] = {}
    for entry in entries:
        by_docket.setdefault(entry.docket_id, []).append(entry)
    term_rank = {term: index for index, term in enumerate(term_order)}
    dockets: list[RecapDiscoveredDocket] = []
    for docket_id in sorted(by_docket, key=_numeric_text_sort_key):
        docket_entries = by_docket[docket_id]
        docket_urls = {entry.docket_url for entry in docket_entries}
        if len(docket_urls) != 1:
            raise RecapSearchCompletenessError(
                f"conflicting URLs for RECAP docket: {docket_id}"
            )
        matched_terms = tuple(
            sorted(
                {term for entry in docket_entries for term in entry.matched_terms},
                key=term_rank.__getitem__,
            )
        )
        dockets.append(
            RecapDiscoveredDocket(
                docket_id=docket_id,
                docket_url=next(iter(docket_urls)),
                entry_keys=tuple(entry.entry_key for entry in docket_entries),
                matched_terms=matched_terms,
            )
        )
    return tuple(dockets)


def _validated_terms(terms: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(terms)
    if not normalized:
        raise ValueError("at least one frozen MTD search term is required")
    if len(normalized) != len(set(normalized)):
        raise ValueError("MTD search terms must be unique")
    for term in normalized:
        _validate_term(term)
    return normalized


def _validate_term(term: str) -> None:
    if term not in FROZEN_MTD_SEARCH_TERMS:
        raise ValueError("term is not in the frozen MTD vocabulary")


def _validate_window(after: date, before: date) -> None:
    if isinstance(after, datetime) or isinstance(before, datetime):
        raise TypeError("entry filing bounds must be dates, not datetimes")
    if after > before:
        raise ValueError("entry_date_filed_after must be on or before the before bound")


def _parse_search_date(raw: str, *, key: str) -> date:
    if not re.fullmatch(r"[0-1][0-9]/[0-3][0-9]/[0-9]{4}", raw):
        raise RecapSearchURLValidationError(f"{key} must use MM/DD/YYYY")
    try:
        parsed = datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError as exc:
        raise RecapSearchURLValidationError(f"{key} is not a valid date") from exc
    if parsed.strftime("%m/%d/%Y") != raw:
        raise RecapSearchURLValidationError(f"{key} must be canonical MM/DD/YYYY")
    return parsed


def _parse_entry_date(raw: str) -> date:
    """Normalize CourtListener's date or ISO datetime template value."""

    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[^\s]+)?", raw):
        raise RecapSearchMarkupError("entry filed date is not ISO-8601")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise RecapSearchMarkupError("entry filed date is not ISO-8601") from exc


def _normalized_text(raw: str) -> str:
    return " ".join(raw.split())


def _comma_int(raw: str, *, label: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)", raw):
        raise RecapSearchMarkupError(f"RECAP {label} is not canonical")
    return int(raw.replace(",", ""))


def _numeric_text_sort_key(raw: str) -> tuple[int, str]:
    return int(raw), raw


def _hit_identity_sort_key(
    hit: RecapSearchHit,
) -> tuple[int, str, tuple[int, str], tuple[int, int]]:
    if hit.docket_entry_id is not None:
        identity_type = "entry"
        identity_value = hit.docket_entry_id
    elif hit.document_number is not None:
        identity_type = "document"
        identity_value = hit.document_number
    else:  # pragma: no cover - parser-created hits always have one identity
        identity_type = ""
        identity_value = hit.entry_key
    attachment_key = (
        (0, 0) if hit.attachment_number is None else (1, hit.attachment_number)
    )
    return (
        int(hit.docket_id),
        identity_type,
        _numericish_sort_key(identity_value),
        attachment_key,
    )


def _numericish_sort_key(raw: str) -> tuple[int, str]:
    try:
        return int(raw), raw
    except ValueError:
        return 2**63 - 1, raw


def parse_recap_search_date(raw: str, *, key: str) -> date:
    """Public composition seam for alternate allowlisted HTML query plans."""

    return _parse_search_date(raw, key=key)


def validate_recap_search_window(after: date, before: date) -> None:
    """Validate shared inclusive RECAP entry-date bounds."""

    _validate_window(after, before)
