"""Fail-closed CourtListener docket pagination over a caller-provided transport."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date
from itertools import pairwise
from urllib.parse import urlencode, urlsplit, urlunsplit

from legalforecast.ingestion.courtlistener_dates import (
    parse_courtlistener_filed_date as _parse_filed_date,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_courtlistener_entry_for_mtd_decision,
)

_COURTLISTENER_HOST = "www.courtlistener.com"
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[1-9][0-9]*)/(?P<slug>[^/]+)/?$")
_RELATED_ENTRY_REFERENCE = re.compile(
    r"\brelated\s+documents?(?:\s*\(\s*s\s*\))?\s*"
    r"(?:(?:no|nos)\.?\s*|#\s*|:\s*)?"
    r"(?P<numbers>[1-9][0-9]*(?:\s*(?:,|and)\s*[1-9][0-9]*)*)",
    re.IGNORECASE,
)


class CourtListenerDocketPaginationError(ValueError):
    """Raised when a paginated docket cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class CourtListenerDocketPageProvenance:
    """Immutable evidence tying merged rows to one retrieved source page."""

    page_number: int
    source_url: str
    sha256: str
    entry_row_ids: tuple[str, ...]
    has_next_page: bool


@dataclass(frozen=True, slots=True)
class CourtListenerDocketBundle:
    """Merged docket rows plus the exact page evidence used to build them."""

    docket_id: str
    base_url: str
    title: str | None
    entries: tuple[CourtListenerWebDocketEntry, ...]
    pages: tuple[CourtListenerDocketPageProvenance, ...]
    is_exhaustive: bool
    stopped_at_anchor_boundary: bool

    @property
    def complete_for_anchor_window(self) -> bool:
        """Return whether the bundle is complete for its requested window."""

        return self.is_exhaustive or self.stopped_at_anchor_boundary

    def as_docket_page(self) -> CourtListenerWebDocketPage:
        """Adapt the completed bundle for existing single-page consumers."""

        if not self.is_exhaustive:
            raise CourtListenerDocketPaginationError(
                "anchor-window bundle cannot masquerade as an exhaustive docket"
            )
        return CourtListenerWebDocketPage(
            docket_id=self.docket_id,
            source_url=canonical_courtlistener_docket_page_url(
                self.base_url,
                page_number=1,
            ),
            title=self.title,
            entries=self.entries,
            has_next_page=False,
        )


def canonical_courtlistener_docket_page_url(
    base_url: str,
    *,
    page_number: int,
) -> str:
    """Build a strict newest-first URL for one CourtListener docket page."""

    if page_number <= 0:
        raise CourtListenerDocketPaginationError("page_number must be positive")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != _COURTLISTENER_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise CourtListenerDocketPaginationError(
            "base_url must be a query-free canonical HTTPS CourtListener docket URL"
        )
    path_match = _DOCKET_PATH.fullmatch(parsed.path)
    if path_match is None:
        raise CourtListenerDocketPaginationError(
            "base_url must identify a numeric CourtListener docket and slug"
        )
    canonical_path = (
        f"/docket/{path_match.group('docket_id')}/{path_match.group('slug')}/"
    )
    return urlunsplit(
        (
            "https",
            _COURTLISTENER_HOST,
            canonical_path,
            urlencode((("order_by", "desc"), ("page", str(page_number)))),
            "",
        )
    )


def may_stop_at_anchor_boundary(
    pages: Iterable[CourtListenerWebDocketPage],
    *,
    anchor: date,
) -> bool:
    """Prove that unseen older pages cannot contain an on-anchor-or-newer row.

    The proof is deliberately conservative: every observed row needs a parseable
    date, the complete observed sequence must be non-increasing, and the oldest
    row must be strictly before the anchor. Any uncertainty requires exhaustion.
    """

    observed_pages = tuple(pages)
    filed_dates: list[date] = []
    for page in observed_pages:
        if not page.entries:
            return False
        for entry in page.entries:
            filed_date = _parse_filed_date(entry.filed_at)
            if filed_date is None:
                return False
            filed_dates.append(filed_date)
    if not filed_dates:
        return False
    if any(newer < older for newer, older in pairwise(filed_dates)):
        return False
    if filed_dates[-1] >= anchor:
        return False
    return not _unresolved_anchored_decision_references(
        observed_pages,
        anchor=anchor,
    )


def _unresolved_anchored_decision_references(
    pages: tuple[CourtListenerWebDocketPage, ...],
    *,
    anchor: date,
) -> set[int]:
    """Return exact older row references that require bounded pagination."""

    observed_numbers = {
        number
        for page in pages
        for entry in page.entries
        if (number := _positive_entry_number(entry.entry_number)) is not None
    }
    if not observed_numbers:
        return set()
    observed_floor = min(observed_numbers)
    referenced_numbers: set[int] = set()
    for page in pages:
        for entry in page.entries:
            filed_date = _parse_filed_date(entry.filed_at)
            if (
                filed_date is not None
                and filed_date >= anchor
                and screen_courtlistener_entry_for_mtd_decision(
                    entry
                ).actual_mtd_decision
            ):
                referenced_numbers.update(_related_entry_numbers(entry.text))
    return {
        number
        for number in referenced_numbers - observed_numbers
        if number < observed_floor
    }


def _positive_entry_number(value: str | None) -> int | None:
    if value is None or re.fullmatch(r"[1-9][0-9]*", value.strip()) is None:
        return None
    return int(value)


def _related_entry_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in _RELATED_ENTRY_REFERENCE.finditer(text):
        numbers.update(
            int(value) for value in re.findall(r"[1-9][0-9]*", match.group("numbers"))
        )
    return numbers


def paginate_courtlistener_docket(
    base_url: str,
    *,
    fetch: Callable[[str], str],
    max_pages: int,
    decision_anchor: date | None = None,
) -> CourtListenerDocketBundle:
    """Fetch and merge a CourtListener docket in strict newest-first order.

    The function returns only an exhausted docket or one with a proven anchor
    boundary. Fetch, parse, identity, repeated-content, and cap failures raise
    instead of exposing a partial bundle.
    """

    if max_pages <= 0:
        raise CourtListenerDocketPaginationError("max_pages must be positive")
    page_one_url = canonical_courtlistener_docket_page_url(
        base_url,
        page_number=1,
    )
    path_match = _DOCKET_PATH.fullmatch(urlsplit(page_one_url).path)
    if path_match is None:  # Defensive: page_one_url was constructed above.
        raise CourtListenerDocketPaginationError("canonical docket URL is invalid")
    docket_id = path_match.group("docket_id")
    canonical_base_url = urlunsplit(
        ("https", _COURTLISTENER_HOST, urlsplit(page_one_url).path, "", "")
    )

    parsed_pages: list[CourtListenerWebDocketPage] = []
    provenance: list[CourtListenerDocketPageProvenance] = []
    seen_urls: set[str] = set()
    seen_digests: set[str] = set()
    title: str | None = None

    for page_number in range(1, max_pages + 1):
        source_url = canonical_courtlistener_docket_page_url(
            canonical_base_url,
            page_number=page_number,
        )
        if source_url in seen_urls:
            raise CourtListenerDocketPaginationError("pagination_url_cycle")
        seen_urls.add(source_url)

        raw_html = fetch(source_url)
        digest = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
        if digest in seen_digests:
            raise CourtListenerDocketPaginationError("pagination_repeated_content")
        seen_digests.add(digest)

        page = parse_courtlistener_docket_html(
            raw_html,
            source_url=source_url,
            docket_id=docket_id,
        )
        if page.docket_id != docket_id:
            raise CourtListenerDocketPaginationError("pagination_docket_mismatch")
        if title is None:
            title = page.title
        elif page.title is not None and page.title != title:
            raise CourtListenerDocketPaginationError("pagination_title_mismatch")

        parsed_pages.append(page)
        provenance.append(
            CourtListenerDocketPageProvenance(
                page_number=page_number,
                source_url=source_url,
                sha256=digest,
                entry_row_ids=tuple(entry.row_id for entry in page.entries),
                has_next_page=page.has_next_page,
            )
        )

        if not page.has_next_page:
            return _bundle(
                docket_id=docket_id,
                base_url=canonical_base_url,
                title=title,
                parsed_pages=parsed_pages,
                provenance=provenance,
                is_exhaustive=True,
                stopped_at_anchor_boundary=False,
            )
        if decision_anchor is not None and may_stop_at_anchor_boundary(
            parsed_pages,
            anchor=decision_anchor,
        ):
            return _bundle(
                docket_id=docket_id,
                base_url=canonical_base_url,
                title=title,
                parsed_pages=parsed_pages,
                provenance=provenance,
                is_exhaustive=False,
                stopped_at_anchor_boundary=True,
            )

    raise CourtListenerDocketPaginationError(
        f"pagination_page_limit_reached: max_pages={max_pages}"
    )


def _bundle(
    *,
    docket_id: str,
    base_url: str,
    title: str | None,
    parsed_pages: Iterable[CourtListenerWebDocketPage],
    provenance: Iterable[CourtListenerDocketPageProvenance],
    is_exhaustive: bool,
    stopped_at_anchor_boundary: bool,
) -> CourtListenerDocketBundle:
    return CourtListenerDocketBundle(
        docket_id=docket_id,
        base_url=base_url,
        title=title,
        entries=_merge_entries(parsed_pages),
        pages=tuple(provenance),
        is_exhaustive=is_exhaustive,
        stopped_at_anchor_boundary=stopped_at_anchor_boundary,
    )


def _merge_entries(
    pages: Iterable[CourtListenerWebDocketPage],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    entries: list[CourtListenerWebDocketEntry] = []
    indexes: dict[str, int] = {}
    for page in pages:
        for entry in page.entries:
            existing_index = indexes.get(entry.row_id)
            if existing_index is None:
                indexes[entry.row_id] = len(entries)
                entries.append(_deduplicate_documents(entry))
                continue
            entries[existing_index] = _merge_duplicate_entry(
                entries[existing_index],
                entry,
            )
    return tuple(entries)


def _deduplicate_documents(
    entry: CourtListenerWebDocketEntry,
) -> CourtListenerWebDocketEntry:
    return replace(entry, documents=tuple(dict.fromkeys(entry.documents)))


def _merge_duplicate_entry(
    first: CourtListenerWebDocketEntry,
    second: CourtListenerWebDocketEntry,
) -> CourtListenerWebDocketEntry:
    if (
        first.entry_number != second.entry_number
        or first.filed_at != second.filed_at
        or first.text != second.text
    ):
        raise CourtListenerDocketPaginationError(
            f"pagination_duplicate_entry_conflict: row_id={first.row_id}"
        )
    return replace(
        first,
        documents=tuple(dict.fromkeys((*first.documents, *second.documents))),
        restriction_markers=tuple(
            sorted(set(first.restriction_markers) | set(second.restriction_markers))
        ),
    )
