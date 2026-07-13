"""Decision-first CourtListener ``type=r`` preset through Firecrawl HTML.

This module deliberately depends only on the shared frozen vocabulary and the
transport-neutral RECAP HTML parser.  It does not import the CourtListener API
client, inspect direct-provider authentication, or perform docket reconstruction.
Its docket JSONL is the canonical input to free Case.dev ``includeEntries``
enrichment and the unchanged strict acquisition screen.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit

from legalforecast.ingestion.decision_first_terms import (
    DECISION_FIRST_RECAP_SEARCH_TERMS,
)
from legalforecast.ingestion.firecrawl_recap_discovery import (
    COURTLISTENER_RECAP_SEARCH_URL,
    RecapDiscoveryRun,
    RecapSearchCompletenessError,
    RecapSearchHTMLTransport,
    RecapSearchMarkupError,
    RecapSearchPage,
    RecapSearchTarget,
    RecapSearchURLValidationError,
    discover_recap_entries_with_plan,
    parse_recap_search_date,
    parse_recap_search_html_with_plan,
    validate_recap_search_window,
)

DECISION_FIRST_RECAP_QUERY_PLAN_VERSION = "decision-first-r-phrase-precise-v1"
DECISION_FIRST_RECAP_MAX_AUTHORIZED_CREDITS = 12_000
DECISION_FIRST_RECAP_MAX_PAGES_PER_TERM = 100
FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS = 7_320
FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS = 9_000
FROZEN_COMBINED_FIRECRAWL_CREDIT_CEILING = 45_000

DecisionRecapSearchMarkupError = RecapSearchMarkupError
DecisionRecapSearchCompletenessError = RecapSearchCompletenessError
DecisionRecapSearchURLValidationError = RecapSearchURLValidationError

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


def build_decision_recap_search_url(
    *,
    term: str,
    entry_date_filed_after: date,
    entry_date_filed_before: date,
    page: int = 1,
) -> str:
    """Build a canonical phrase-precise CourtListener decision-document URL."""

    _validate_decision_term(term)
    validate_recap_search_window(entry_date_filed_after, entry_date_filed_before)
    if type(page) is not int or page <= 0:
        raise ValueError("page must be a positive integer")
    params: list[tuple[str, str]] = [
        ("type", "r"),
        ("q", decision_recap_query_expression(term)),
        ("entry_date_filed_after", entry_date_filed_after.strftime("%m/%d/%Y")),
        ("entry_date_filed_before", entry_date_filed_before.strftime("%m/%d/%Y")),
        ("order_by", "entry_date_filed desc"),
    ]
    if page > 1:
        params.append(("page", str(page)))
    return f"{COURTLISTENER_RECAP_SEARCH_URL}?{urlencode(params)}"


def parse_decision_recap_search_url(source_url: str) -> RecapSearchTarget:
    """Validate one ``type=r`` URL against the exact frozen eight-term preset."""

    split = urlsplit(source_url)
    if (
        split.scheme != "https"
        or split.hostname != "www.courtlistener.com"
        or split.netloc != "www.courtlistener.com"
        or split.path != "/"
        or split.fragment
    ):
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP search URL must be canonical CourtListener HTTPS"
        )
    try:
        pairs = parse_qsl(split.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP search query is malformed"
        ) from exc
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP query keys must be unique"
        )
    key_set = set(keys)
    if not _REQUIRED_QUERY_KEYS.issubset(key_set) or not key_set.issubset(
        _ALLOWED_QUERY_KEYS
    ):
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP query must use the frozen parameter allowlist"
        )
    values = dict(pairs)
    if values["type"] != "r":
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP search type must be r"
        )
    term = values["q"]
    try:
        _validate_decision_term(term)
    except ValueError as exc:
        raise DecisionRecapSearchURLValidationError(str(exc)) from exc
    if values["order_by"] != "entry_date_filed desc":
        raise DecisionRecapSearchURLValidationError(
            "decision RECAP search must be newest-entry-first"
        )
    after = parse_recap_search_date(
        values["entry_date_filed_after"], key="entry_date_filed_after"
    )
    before = parse_recap_search_date(
        values["entry_date_filed_before"], key="entry_date_filed_before"
    )
    try:
        validate_recap_search_window(after, before)
    except ValueError as exc:
        raise DecisionRecapSearchURLValidationError(str(exc)) from exc
    raw_page = values.get("page")
    page = 1
    if raw_page is not None:
        if not re.fullmatch(r"[1-9][0-9]*", raw_page) or int(raw_page) < 2:
            raise DecisionRecapSearchURLValidationError(
                "page must be a canonical integer greater than one"
            )
        page = int(raw_page)
    canonical = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=after,
        entry_date_filed_before=before,
        page=page,
    )
    return RecapSearchTarget(
        term=term,
        entry_date_filed_after=after,
        entry_date_filed_before=before,
        page=page,
        url=canonical,
    )


def parse_decision_recap_search_html(
    raw_html: str,
    *,
    source_url: str,
) -> RecapSearchPage:
    """Parse type=r HTML with the shared fail-closed identity extractor."""

    return parse_recap_search_html_with_plan(
        raw_html,
        source_url=source_url,
        parse_search_url=parse_decision_recap_search_url,
        build_search_url=build_decision_recap_search_url,
    )


def decision_recap_query_expression(term: str) -> str:
    """Return one exact frozen boolean/phrase expression without rewriting it."""

    _validate_decision_term(term)
    return term


def discover_decision_recap_entries(
    *,
    transport: RecapSearchHTMLTransport,
    entry_date_filed_after: date,
    entry_date_filed_before: date,
    terms: Sequence[str] = DECISION_FIRST_RECAP_SEARCH_TERMS,
    max_pages_per_term: int = 100,
) -> RecapDiscoveryRun:
    """Exhaust the bounded decision-first HTML plan and return docket IDs."""

    return discover_recap_entries_with_plan(
        transport=transport,
        entry_date_filed_after=entry_date_filed_after,
        entry_date_filed_before=entry_date_filed_before,
        terms=terms,
        max_pages_per_term=max_pages_per_term,
        validate_terms=_validated_decision_terms,
        build_search_url=build_decision_recap_search_url,
        parse_search_html=parse_decision_recap_search_html,
        reconcile_declared_counts=True,
    )


def decision_rescue_worst_case_credits(
    *, terms: Sequence[str], max_pages_per_term: int, max_attempts_per_page: int
) -> int:
    """Return the scheduler's hard five-credit worst-case authorization."""

    _validated_decision_terms(terms)
    if type(max_pages_per_term) is not int or max_pages_per_term <= 0:
        raise ValueError("max_pages_per_term must be positive")
    if type(max_attempts_per_page) is not int or max_attempts_per_page <= 0:
        raise ValueError("max_attempts_per_page must be positive")
    return len(terms) * max_pages_per_term * max_attempts_per_page * 5


def _validated_decision_terms(terms: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(terms)
    if not normalized:
        raise ValueError("at least one frozen decision-first term is required")
    if len(normalized) != len(set(normalized)):
        raise ValueError("decision-first terms must be unique")
    for term in normalized:
        _validate_decision_term(term)
    return normalized


def _validate_decision_term(term: str) -> None:
    if term not in DECISION_FIRST_RECAP_SEARCH_TERMS:
        raise ValueError("term is not in the frozen decision-first vocabulary")
