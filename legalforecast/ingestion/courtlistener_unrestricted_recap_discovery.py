"""Durable CourtListener RECAP discovery including unavailable documents.

The older typed ``type=r`` helper always sends ``available_only=on``.  That is
appropriate for a free-document frontier, but it hides otherwise eligible
dockets whose disposition or briefing is absent from RECAP.  This source uses
the raw CourtListener search surface and deliberately omits that parameter.

Only discovery metadata is handled here.  The shared scheduler and
``CycleAcquisitionStore`` provide atomic page checkpoints, and the existing
``seed-direct-search`` transfer remains responsible for source-bound REST
screening.  No PACER fetch or document purchase can occur in this module.
"""

from __future__ import annotations

import urllib.parse
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, cast

from legalforecast.ingestion.courtlistener_acquisition import (
    courtlistener_search_hit_id,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    DiscoveryPage,
    DiscoveryRunSummary,
    materialize_independent_term_sets,
)

UNRESTRICTED_RECAP_SEARCH_TERMS = (
    '"motion to dismiss" AND granted',
    '"motion to dismiss" AND denied',
)
UNRESTRICTED_RECAP_POLICY_SCHEMA = "legalforecast.courtlistener_unrestricted_recap.v1"
UNRESTRICTED_RECAP_PROVIDER = "courtlistener"
# CourtListener's v4 legal-search endpoint enforces a fixed 20-result page for
# ``type=r`` just as it does for ``type=o``.  Pin the observed provider contract
# so durable progress and rate projections describe the physical request shape.
UNRESTRICTED_RECAP_PAGE_SIZE = 20
UNRESTRICTED_RECAP_TOP_K_PER_TERM = 5_000
_SEARCH_ENDPOINT_PATH = "/api/rest/v4/search/"
_SEARCH_ORIGIN_HOST = "www.courtlistener.com"
_QUERY_EXPRESSION = "{term} AND entry_date_filed:[{start} TO {end}]"


class CourtListenerUnrestrictedRecapDiscoveryError(RuntimeError):
    """Raised when an unrestricted RECAP result cannot be preserved safely."""


class RequestPacer(Protocol):
    """Small pacing surface accepted without coupling to a concrete pacer."""

    def wait(self) -> None: ...


def build_unrestricted_recap_batch_config(
    *,
    search_window_start: date,
    search_window_end: date,
    auth_mode: str,
    query_terms: Sequence[str] = UNRESTRICTED_RECAP_SEARCH_TERMS,
    page_size: int = UNRESTRICTED_RECAP_PAGE_SIZE,
    top_k_per_term: int = UNRESTRICTED_RECAP_TOP_K_PER_TERM,
) -> dict[str, object]:
    """Return the source-bound config consumed by ``seed-direct-search``.

    The provider name, numeric candidate identities, window keys, and exhausted
    per-term progress deliberately match the transfer reader's contract.
    ``available_only`` is recorded as omitted so a resume cannot silently mix
    free-only and unrestricted result sets.
    """

    _validate_window(search_window_start, search_window_end)
    terms = _validated_terms(query_terms)
    if auth_mode not in {"authenticated", "anonymous"}:
        raise ValueError("auth_mode must be 'authenticated' or 'anonymous'")
    if page_size != UNRESTRICTED_RECAP_PAGE_SIZE:
        raise ValueError(
            "page_size must match CourtListener's fixed unrestricted RECAP "
            f"page size of {UNRESTRICTED_RECAP_PAGE_SIZE}"
        )
    if top_k_per_term <= 0:
        raise ValueError("top_k_per_term must be positive")
    if top_k_per_term % UNRESTRICTED_RECAP_PAGE_SIZE:
        raise ValueError(
            "top_k_per_term must be a multiple of CourtListener's fixed "
            f"page size {UNRESTRICTED_RECAP_PAGE_SIZE}"
        )
    return {
        "schema_version": UNRESTRICTED_RECAP_POLICY_SCHEMA,
        "provider": UNRESTRICTED_RECAP_PROVIDER,
        "search_type": "r",
        "query_field": "q",
        "query_terms": list(terms),
        "query_term_order_is_frozen": True,
        "query_expression": _QUERY_EXPRESSION,
        "search_window_start": search_window_start.isoformat(),
        "search_window_end": search_window_end.isoformat(),
        "order_by": "score desc",
        "available_only": "omitted",
        "search_page_size": page_size,
        "provider_page_size_is_fixed": True,
        "top_k_per_term": top_k_per_term,
        "auth_mode": auth_mode,
    }


@dataclass(frozen=True, slots=True)
class CourtListenerUnrestrictedRecapDiscoverySource:
    """One-page adapter for ``type=r`` search without ``available_only``."""

    client: CourtListenerClient
    search_window_start: date
    search_window_end: date
    pacer: RequestPacer | None = None
    auth_mode: str = "authenticated"

    def __post_init__(self) -> None:
        _validate_window(self.search_window_start, self.search_window_end)
        if self.auth_mode not in {"authenticated", "anonymous"}:
            raise ValueError("auth_mode must be 'authenticated' or 'anonymous'")

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        normalized_term = term.strip()
        if not normalized_term:
            raise ValueError("term is required")
        if page_size != UNRESTRICTED_RECAP_PAGE_SIZE:
            raise ValueError(
                "CourtListener unrestricted RECAP search page_size must be "
                f"exactly {UNRESTRICTED_RECAP_PAGE_SIZE}"
            )
        if self.pacer is not None:
            self.pacer.wait()
        params: dict[str, Any] = {
            "q": _windowed_query(
                normalized_term,
                self.search_window_start,
                self.search_window_end,
            ),
            "type": "r",
            "order_by": "score desc",
            "page_size": page_size,
        }
        # Do not add ``available_only`` here. Its absence is this source's
        # defining behavior and is frozen into the batch config above.
        page = self.client.search_raw(params, cursor=cursor)
        _validate_results_contract(page.raw, parsed_count=len(page.items))
        next_cursor = _strict_next_cursor(
            page.raw,
            parsed_cursor=page.next_cursor,
            expected_params=params,
        )
        hits: list[DiscoveryHit] = []
        for index, record in enumerate(page.items):
            docket_id = _positive_ascii_docket_id(record)
            hits.append(
                DiscoveryHit(
                    provider_hit_id=courtlistener_search_hit_id(
                        record,
                        term=normalized_term,
                        request_cursor=cursor,
                        index=index,
                    ),
                    candidate_id=docket_id,
                    # Preserve the provider result. Screening and provenance
                    # extraction happen only after the saturated source freezes.
                    payload=dict(record),
                )
            )
        return DiscoveryPage(
            hits=tuple(hits),
            next_cursor=next_cursor,
            exhausted=next_cursor is None,
        )


def run_unrestricted_recap_discovery(
    *,
    store: CycleAcquisitionStore,
    batch_id: str,
    client: CourtListenerClient,
    search_window_start: date,
    search_window_end: date,
    auth_mode: str,
    query_terms: Sequence[str] = UNRESTRICTED_RECAP_SEARCH_TERMS,
    page_size: int = UNRESTRICTED_RECAP_PAGE_SIZE,
    top_k_per_term: int = UNRESTRICTED_RECAP_TOP_K_PER_TERM,
    pacer: RequestPacer | None = None,
) -> DiscoveryRunSummary:
    """Freeze config and durably materialize the unrestricted result union."""

    config = build_unrestricted_recap_batch_config(
        search_window_start=search_window_start,
        search_window_end=search_window_end,
        auth_mode=auth_mode,
        query_terms=query_terms,
        page_size=page_size,
        top_k_per_term=top_k_per_term,
    )
    frozen_terms = tuple(cast(list[str], config["query_terms"]))
    store.ensure_batch(batch_id, config)
    source = CourtListenerUnrestrictedRecapDiscoverySource(
        client=client,
        search_window_start=search_window_start,
        search_window_end=search_window_end,
        pacer=pacer,
        auth_mode=auth_mode,
    )
    return materialize_independent_term_sets(
        source=source,
        store=store,
        batch_id=batch_id,
        query_terms=frozen_terms,
        top_k_per_term=top_k_per_term,
        page_size=page_size,
    )


def _windowed_query(term: str, start: date, end: date) -> str:
    return _QUERY_EXPRESSION.format(
        term=term,
        start=start.isoformat(),
        end=end.isoformat(),
    )


def _positive_ascii_docket_id(record: Mapping[str, Any]) -> str:
    value = record.get("docket_id")
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "every RECAP search result must include a positive ASCII integer docket_id"
        )
    normalized = str(value)
    if (
        not normalized
        or not normalized.isascii()
        or not normalized.isdigit()
        or int(normalized) <= 0
    ):
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "every RECAP search result must include a positive ASCII integer docket_id"
        )
    return normalized


def _validate_results_contract(
    payload: Mapping[str, Any], *, parsed_count: int
) -> None:
    if "results" not in payload or not isinstance(payload["results"], list):
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener search page must include an explicit results list"
        )
    raw_results = cast(list[object], payload["results"])
    if len(raw_results) != parsed_count:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener parsed result count contradicts the raw results list"
        )


def _strict_next_cursor(
    payload: Mapping[str, Any],
    *,
    parsed_cursor: str | None,
    expected_params: Mapping[str, Any],
) -> str | None:
    if "next" not in payload:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener search page must include explicit next pagination evidence"
        )
    raw_next = payload["next"]
    if raw_next is None:
        if parsed_cursor is not None:
            raise CourtListenerUnrestrictedRecapDiscoveryError(
                "CourtListener null next contradicts the parsed continuation cursor"
            )
        return None
    if not isinstance(raw_next, str) or not raw_next.strip():
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next must be an absolute HTTPS URL"
        )
    parsed = urllib.parse.urlsplit(raw_next)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next must be an absolute HTTPS URL"
        )
    if (
        parsed.hostname != _SEARCH_ORIGIN_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next must remain on the CourtListener origin"
        )
    if parsed.path != _SEARCH_ENDPOINT_PATH:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next must target the REST v4 search endpoint"
        )
    if parsed.fragment:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next URL must not include a fragment"
        )
    try:
        query_pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next query is invalid"
        ) from exc
    cursor_values = [value for key, value in query_pairs if key == "cursor"]
    if len(cursor_values) != 1 or not cursor_values[0]:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next must include exactly one non-empty cursor"
        )
    continuation_params = Counter(
        (key, value) for key, value in query_pairs if key != "cursor"
    )
    frozen_params = Counter(
        (str(key), str(value)) for key, value in expected_params.items()
    )
    if continuation_params != frozen_params:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next query changed frozen parameters"
        )
    cursor = cursor_values[0]
    if parsed_cursor != cursor:
        raise CourtListenerUnrestrictedRecapDiscoveryError(
            "CourtListener next cursor contradicts the client pagination cursor"
        )
    return cursor


def _validated_terms(query_terms: Sequence[str]) -> tuple[str, ...]:
    terms = tuple(term.strip() for term in query_terms)
    if not terms or any(not term for term in terms):
        raise ValueError("query_terms must include at least one non-empty term")
    if len(set(terms)) != len(terms):
        raise ValueError("query_terms must not contain duplicates")
    return terms


def _validate_window(start: date, end: date) -> None:
    if isinstance(start, datetime) or isinstance(end, datetime):
        raise TypeError("search window bounds must be dates, not datetimes")
    if start > end:
        raise ValueError("search_window_start must be on or before search_window_end")
