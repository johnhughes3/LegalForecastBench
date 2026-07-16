"""Strict, budgeted Firecrawl fallback for opinion-to-RECAP identity search."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlPageSource,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_opinion_discovery import (
    FEDERAL_TRIAL_COURT_IDS,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlCourtListenerHTMLSource,
    FirecrawlURLValidationError,
)

OPINION_RECAP_FIRECRAWL_POLICY_SCHEMA = (
    "legalforecast.opinion_recap_firecrawl_policy.v1"
)
OPINION_RECAP_FIRECRAWL_RUN_SCHEMA = "legalforecast.opinion_recap_firecrawl_run.v1"
_ORIGIN = "https://www.courtlistener.com"
_ALLOWED_KEYS = frozenset({"type", "q", "court", "order_by", "page"})
_REQUIRED_KEYS = _ALLOWED_KEYS - {"page"}
_QUERY = re.compile(r'^"[^"\\\x00-\x1f\x7f]{2,496}"$')
_DOCKET_LINK = re.compile(r"^/docket/(?P<docket_id>[1-9][0-9]*)/[^/?#]+/$")
_RESULT_COUNT = re.compile(
    r"(?:^|\s|—)(?P<count>[0-9][0-9,]*)\s+Results?(?:\s|—|$)", re.I
)
_PAGE_COUNT = re.compile(
    r"Page\s+(?P<page>[0-9][0-9,]*)\s+of\s+(?P<pages>[0-9][0-9,]*)",
    re.I,
)
_CASE_NAME_AND_COURT = re.compile(r"^(?P<case_name>.+)\s+\([^()]+\s+[0-9]{4}\)$")


class OpinionRecapFirecrawlSearchError(FirecrawlURLValidationError):
    """Raised when a target, page, pagination proof, or artifact is invalid."""


class OpinionRecapFirecrawlPageSource(FirecrawlCourtListenerHTMLSource):
    """Firecrawl source restricted to exact, court-scoped RECAP searches."""

    def _canonicalize_source_url(self, source_url: str) -> str:
        return canonicalize_opinion_recap_search_url(source_url)


@dataclass(frozen=True, slots=True)
class OpinionRecapFirecrawlCandidate:
    docket_id: str
    court_id: str
    docket_number: str
    case_name: str
    raw: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class OpinionRecapFirecrawlSearchPage:
    candidates: tuple[OpinionRecapFirecrawlCandidate, ...]
    total_results: int
    total_pages: int
    page: int
    next_url: str | None
    raw_html_sha256: str


@dataclass(frozen=True, slots=True)
class OpinionRecapFirecrawlResults:
    candidates: tuple[OpinionRecapFirecrawlCandidate, ...]
    response_sha256: str
    page_count: int
    reserved_credits: int
    reported_credits: int


@dataclass(frozen=True, slots=True)
class _OpinionSearchTarget:
    query: str
    court_id: str
    page: int


class OpinionRecapFirecrawlResolver(Protocol):
    """Resolver seam used by the opinion-to-RECAP orchestration."""

    @property
    def policy(self) -> Mapping[str, object]: ...

    def search(
        self,
        *,
        source_candidate_id: str,
        source_ordinal: int,
        query: str,
        court_id: str,
    ) -> OpinionRecapFirecrawlResults: ...


def build_opinion_recap_search_url(*, query: str, court_id: str, page: int = 1) -> str:
    """Build one exact-caption, source-court-constrained RECAP search URL."""

    _validate_query(query)
    _validate_court_id(court_id)
    if isinstance(page, bool) or page <= 0:
        raise OpinionRecapFirecrawlSearchError("page must be a positive integer")
    pairs = [
        ("type", "r"),
        ("q", query),
        ("court", court_id),
        ("order_by", "score desc"),
    ]
    if page > 1:
        pairs.append(("page", str(page)))
    return f"{_ORIGIN}/?{urlencode(pairs)}"


def canonicalize_opinion_recap_search_url(source_url: str) -> str:
    """Validate and canonicalize the narrow public resolver-search target."""

    split = urlsplit(source_url)
    if (
        split.scheme != "https"
        or split.hostname != "www.courtlistener.com"
        or split.netloc != "www.courtlistener.com"
        or split.path != "/"
        or split.fragment
    ):
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver URL must be canonical HTTPS CourtListener search"
        )
    try:
        pairs = parse_qsl(
            split.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=5,
        )
    except ValueError as exc:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver search query is malformed"
        ) from exc
    keys = [key for key, _value in pairs]
    values = dict(pairs)
    expected_keys = set(_REQUIRED_KEYS)
    if "page" in values:
        expected_keys.add("page")
    if len(keys) != len(set(keys)) or set(values) != expected_keys:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver search has duplicate, missing, or unknown parameters"
        )
    if values["type"] != "r" or values["order_by"] != "score desc":
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver must use score-ordered RECAP search"
        )
    _validate_query(values["q"])
    _validate_court_id(values["court"])
    raw_page = values.get("page")
    if raw_page is None:
        page = 1
    elif re.fullmatch(r"[1-9][0-9]*", raw_page) is None:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver page must be a positive canonical integer"
        )
    else:
        page = int(raw_page)
    return build_opinion_recap_search_url(
        query=values["q"], court_id=values["court"], page=page
    )


def parse_opinion_recap_search_html(
    raw_html: str, *, source_url: str
) -> OpinionRecapFirecrawlSearchPage:
    """Parse one CourtListener result page and require completeness evidence."""

    target_url = canonicalize_opinion_recap_search_url(source_url)
    target = _target_values(target_url)
    if not raw_html.strip() or re.search(r"</html>\s*$", raw_html, re.I) is None:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver search HTML is empty or truncated"
        )
    parser = _OpinionSearchHTMLParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except OpinionRecapFirecrawlSearchError:
        raise
    except Exception as exc:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver search HTML parsing failed"
        ) from exc
    title = _normalized_text(parser.title)
    count_match = _RESULT_COUNT.search(title)
    if count_match is None:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver result count is missing from the page title"
        )
    total_results = _comma_int(count_match.group("count"), "result count")
    if total_results == 0 and parser.articles:
        raise OpinionRecapFirecrawlSearchError(
            "zero-result opinion search unexpectedly contains result cards"
        )
    if total_results > 0 and not parser.articles:
        raise OpinionRecapFirecrawlSearchError(
            "nonzero opinion search contains no result cards"
        )
    page_match = _PAGE_COUNT.search(_normalized_text(parser.pagination))
    if page_match is None:
        if target.page != 1 or total_results != len(parser.articles):
            raise OpinionRecapFirecrawlSearchError(
                "opinion resolver page lacks explicit pagination proof"
            )
        displayed_page = 1
        total_pages = 1
    else:
        displayed_page = _comma_int(page_match.group("page"), "page number")
        total_pages = _comma_int(page_match.group("pages"), "page count")
        if displayed_page != target.page or total_pages < displayed_page:
            raise OpinionRecapFirecrawlSearchError(
                "opinion resolver pagination marker is inconsistent"
            )
    if len(parser.next_hrefs) > 1:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver page has multiple next-page links"
        )
    next_url: str | None = None
    if displayed_page < total_pages:
        expected = build_opinion_recap_search_url(
            query=target.query,
            court_id=target.court_id,
            page=displayed_page + 1,
        )
        if len(parser.next_hrefs) != 1:
            raise OpinionRecapFirecrawlSearchError(
                "opinion resolver page is missing its next-page link"
            )
        candidate = canonicalize_opinion_recap_search_url(
            urljoin(f"{_ORIGIN}/", parser.next_hrefs[0])
        )
        if candidate != expected:
            raise OpinionRecapFirecrawlSearchError(
                "opinion resolver next-page link changes the frozen search"
            )
        next_url = expected
    elif parser.next_hrefs:
        raise OpinionRecapFirecrawlSearchError(
            "terminal opinion resolver page unexpectedly has a next-page link"
        )
    candidates = tuple(
        _article_candidate(article, court_id=target.court_id)
        for article in parser.articles
    )
    if total_pages == 1 and len(candidates) != total_results:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver cards do not reconcile to the declared result count"
        )
    if len({item.docket_id for item in candidates}) != len(candidates):
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver page contains duplicate RECAP docket IDs"
        )
    return OpinionRecapFirecrawlSearchPage(
        candidates=candidates,
        total_results=total_results,
        total_pages=total_pages,
        page=displayed_page,
        next_url=next_url,
        raw_html_sha256=hashlib.sha256(raw_html.encode()).hexdigest(),
    )


class BudgetedOpinionRecapFirecrawlResolver:
    """Exhaust exact public HTML searches through the shared credit scheduler."""

    def __init__(
        self,
        *,
        store_path: str | Path,
        source_batch_id: str,
        output_batch_id: str,
        run_id: str,
        artifact_dir: str | Path,
        source: FirecrawlPageSource,
        credit_cap: int,
        max_attempts: int,
        max_pages_per_lead: int,
    ) -> None:
        if max_pages_per_lead <= 0:
            raise ValueError("max_pages_per_lead must be positive")
        self.store_path = Path(store_path)
        self.source_batch_id = source_batch_id
        self.output_batch_id = output_batch_id
        self.run_id = run_id
        self.artifact_dir = Path(artifact_dir)
        self.source = source
        self.credit_cap = credit_cap
        self.max_attempts = max_attempts
        self.max_pages_per_lead = max_pages_per_lead
        self._policy = {
            "schema_version": OPINION_RECAP_FIRECRAWL_POLICY_SCHEMA,
            "provider": "courtlistener_html_via_firecrawl",
            "provider_query_contract": "quoted_exact_case_name_v1",
            "court_constraint": "frozen_source_court_id_v1",
            "available_only": "omitted",
            "proxy": "basic",
            "reserved_credits_per_attempt": 1,
            "credit_cap": credit_cap,
            "max_attempts": max_attempts,
            "max_pages_per_lead": max_pages_per_lead,
            "paid_activity_allowed": False,
        }
        self._ensure_run()

    @property
    def policy(self) -> Mapping[str, object]:
        return dict(self._policy)

    def search(
        self,
        *,
        source_candidate_id: str,
        source_ordinal: int,
        query: str,
        court_id: str,
    ) -> OpinionRecapFirecrawlResults:
        if not source_candidate_id.isascii() or not source_candidate_id.isdigit():
            raise OpinionRecapFirecrawlSearchError(
                "source candidate ID must be numeric"
            )
        if source_ordinal < 0:
            raise OpinionRecapFirecrawlSearchError(
                "source ordinal must be non-negative"
            )
        candidates: list[OpinionRecapFirecrawlCandidate] = []
        page_hashes: list[str] = []
        seen_docket_ids: set[str] = set()
        total_results: int | None = None
        total_pages: int | None = None
        with CycleAcquisitionStore(self.store_path) as store:
            scheduler = BudgetedFirecrawlScheduler(
                store=store,
                source=self.source,
                run_id=self.run_id,
                artifact_dir=self.artifact_dir,
                max_attempts=self.max_attempts,
                max_workers=1,
                artifact_validator=_validate_search_artifact,
                semantic_failure_quarantine_dir=(
                    self.artifact_dir / "semantic-invalid"
                ),
            )
            next_url: str | None = build_opinion_recap_search_url(
                query=query, court_id=court_id
            )
            for page_number in range(1, self.max_pages_per_lead + 1):
                if next_url is None:
                    break
                target = FirecrawlTargetSpec(
                    target_id=(
                        f"opinion-recap:{source_candidate_id}:page:{page_number}"
                    ),
                    target_kind="search",
                    source_url=next_url,
                    page_number=page_number,
                    ordinal=(
                        source_ordinal * self.max_pages_per_lead + page_number - 1
                    ),
                )
                run_result = scheduler.run((target,))
                if len(run_result.pages) != 1:
                    raise OpinionRecapFirecrawlSearchError(
                        "Firecrawl search target did not produce one verified page"
                    )
                page_record = run_result.pages[0]
                page = parse_opinion_recap_search_html(
                    page_record.raw_html, source_url=next_url
                )
                if page.page != page_number:
                    raise OpinionRecapFirecrawlSearchError(
                        "Firecrawl opinion pagination is not contiguous"
                    )
                if total_results is None:
                    total_results = page.total_results
                    total_pages = page.total_pages
                elif (
                    page.total_results != total_results
                    or page.total_pages != total_pages
                ):
                    raise OpinionRecapFirecrawlSearchError(
                        "Firecrawl opinion result count changed during pagination"
                    )
                for candidate in page.candidates:
                    if candidate.docket_id in seen_docket_ids:
                        raise OpinionRecapFirecrawlSearchError(
                            "Firecrawl opinion search repeated a RECAP docket ID"
                        )
                    seen_docket_ids.add(candidate.docket_id)
                    candidates.append(candidate)
                page_hashes.append(page.raw_html_sha256)
                next_url = page.next_url
            else:
                if next_url is not None:
                    raise OpinionRecapFirecrawlSearchError(
                        "Firecrawl opinion pagination exceeded the per-lead limit"
                    )
            if next_url is not None or total_results is None or total_pages is None:
                raise OpinionRecapFirecrawlSearchError(
                    "Firecrawl opinion search exhaustion is unproven"
                )
            if len(candidates) != total_results:
                raise OpinionRecapFirecrawlSearchError(
                    "Firecrawl opinion cards do not reconcile to the declared "
                    "result count"
                )
            summary = store.firecrawl_run_summary(self.run_id)
        return OpinionRecapFirecrawlResults(
            candidates=tuple(candidates),
            response_sha256=hashlib.sha256("\n".join(page_hashes).encode()).hexdigest(),
            page_count=len(page_hashes),
            reserved_credits=_summary_count(summary, "run_reserved_credits"),
            reported_credits=_summary_count(summary, "run_reported_credits"),
        )

    def _ensure_run(self) -> None:
        support_batch_id = f"{self.output_batch_id}-firecrawl-fallback-support"
        with CycleAcquisitionStore(self.store_path) as store:
            source_digest = store.batch_digest(self.source_batch_id)
            support_config = {
                **self._policy,
                "source_batch_id": self.source_batch_id,
                "source_batch_digest": source_digest,
                "output_batch_id": self.output_batch_id,
            }
            store.ensure_batch(support_batch_id, support_config)
            store.ensure_firecrawl_run(
                self.run_id,
                batch_id=support_batch_id,
                config={
                    "schema_version": OPINION_RECAP_FIRECRAWL_RUN_SCHEMA,
                    **support_config,
                },
                credit_cap=self.credit_cap,
                reserved_credits_per_attempt=1,
            )


@dataclass(slots=True)
class _Article:
    docket_href: str | None = None
    docket_text: str = ""
    docket_number: str | None = None


class _OpinionSearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.pagination = ""
        self.next_hrefs: list[str] = []
        self.articles: list[_Article] = []
        self._article: _Article | None = None
        self._in_title = False
        self._in_h3 = False
        self._capture_docket = False
        self._capture_pagination_depth = 0
        self._capture_header = False
        self._capture_value = False
        self._header = ""
        self._value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "title":
            self._in_title = True
        elif tag == "article":
            if self._article is not None:
                raise OpinionRecapFirecrawlSearchError(
                    "nested opinion resolver result cards are invalid"
                )
            self._article = _Article()
        elif tag == "h3" and self._article is not None:
            self._in_h3 = True
        elif tag == "a":
            if self._in_h3 and self._article is not None:
                self._capture_docket = True
                self._article.docket_href = attributes.get("href")
            if attributes.get("rel") == "next":
                href = attributes.get("href")
                if href is not None:
                    self.next_hrefs.append(href)
        elif tag == "div" and "pagination" in classes:
            self._capture_pagination_depth = 1
        elif self._capture_pagination_depth and tag == "div":
            self._capture_pagination_depth += 1
        elif tag == "span" and self._article is not None:
            if "meta-data-header" in classes:
                self._capture_header = True
                self._header = ""
            elif "meta-data-value" in classes:
                self._capture_value = True
                self._value = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "a":
            self._capture_docket = False
        elif tag == "h3":
            self._in_h3 = False
        elif tag == "span" and self._capture_header:
            self._capture_header = False
        elif tag == "span" and self._capture_value:
            self._capture_value = False
            if (
                self._article is not None
                and _normalized_text(self._header).casefold() == "docket number:"
            ):
                self._article.docket_number = _normalized_text(self._value)
        elif tag == "div" and self._capture_pagination_depth:
            self._capture_pagination_depth -= 1
        elif tag == "article":
            if self._article is None:
                raise OpinionRecapFirecrawlSearchError(
                    "unmatched opinion resolver result card"
                )
            self.articles.append(self._article)
            self._article = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._capture_pagination_depth:
            self.pagination += data
        if self._capture_docket and self._article is not None:
            self._article.docket_text += data
        if self._capture_header:
            self._header += data
        if self._capture_value:
            self._value += data


def _article_candidate(
    article: _Article, *, court_id: str
) -> OpinionRecapFirecrawlCandidate:
    if article.docket_href is None or not article.docket_number:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver result lacks docket link or docket number"
        )
    split = urlsplit(urljoin(f"{_ORIGIN}/", article.docket_href))
    if (
        split.scheme != "https"
        or split.netloc != "www.courtlistener.com"
        or split.query
        or split.fragment
    ):
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver docket link is not allowlisted"
        )
    match = _DOCKET_LINK.fullmatch(split.path)
    if match is None:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver docket link has an unknown shape"
        )
    caption = _normalized_text(article.docket_text)
    caption_match = _CASE_NAME_AND_COURT.fullmatch(caption)
    if caption_match is None:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver result lacks an explicit court/year caption"
        )
    case_name = _normalized_text(caption_match.group("case_name"))
    if not case_name:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver result lacks a case name"
        )
    docket_id = match.group("docket_id")
    raw = {
        "docket_id": docket_id,
        "court_id": court_id,
        "docket_number": article.docket_number,
        "case_name": case_name,
        "court_identity_evidence": {
            "method": "frozen_source_court_search_constraint_v1",
            "court_id": court_id,
        },
    }
    return OpinionRecapFirecrawlCandidate(
        docket_id=docket_id,
        court_id=court_id,
        docket_number=article.docket_number,
        case_name=case_name,
        raw=raw,
    )


def _target_values(url: str) -> _OpinionSearchTarget:
    values = dict(parse_qsl(urlsplit(url).query, strict_parsing=True))
    return _OpinionSearchTarget(
        query=values["q"],
        court_id=values["court"],
        page=int(values.get("page", "1")),
    )


def _validate_search_artifact(raw_html: str, source_url: str) -> None:
    parse_opinion_recap_search_html(raw_html, source_url=source_url)


def _summary_count(summary: Mapping[str, object], field: str) -> int:
    value = summary.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OpinionRecapFirecrawlSearchError(
            f"Firecrawl run summary has invalid {field}"
        )
    return value


def _validate_query(query: str) -> None:
    if (
        _QUERY.fullmatch(query) is None
        or len(query) > 500
        or any(unicodedata.category(character).startswith("C") for character in query)
    ):
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver query must be one bounded exact quoted phrase"
        )


def _validate_court_id(court_id: str) -> None:
    if court_id not in FEDERAL_TRIAL_COURT_IDS:
        raise OpinionRecapFirecrawlSearchError(
            "opinion resolver court must be a frozen federal trial court"
        )


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _comma_int(value: str, label: str) -> int:
    if re.fullmatch(r"[0-9][0-9,]*", value) is None:
        raise OpinionRecapFirecrawlSearchError(f"invalid {label}")
    return int(value.replace(",", ""))
