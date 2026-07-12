"""Provider-neutral, order-neutral discovery scheduling primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class DiscoverySchedulerError(RuntimeError):
    """Raised when provider pagination cannot be resumed safely."""


class TermTerminalStatus(StrEnum):
    """Why one independently bounded search term stopped."""

    EXHAUSTED = "exhausted"
    LIMIT_BOUND = "limit_bound"
    LIMIT_BOUND_UNPAGEABLE = "limit_bound_unpageable"


@dataclass(frozen=True, slots=True)
class DiscoveryHit:
    """One provider hit with a stable candidate identity."""

    provider_hit_id: str
    candidate_id: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.provider_hit_id.strip():
            raise ValueError("provider_hit_id is required")
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")


@dataclass(frozen=True, slots=True)
class DiscoveryPage:
    """One provider page and its documented continuation evidence."""

    hits: tuple[DiscoveryHit, ...]
    next_cursor: str | None
    exhausted: bool | None = None

    def __post_init__(self) -> None:
        if self.next_cursor is not None and not self.next_cursor.strip():
            raise ValueError("next_cursor must be non-empty when present")
        if self.exhausted is True and self.next_cursor is not None:
            raise ValueError("an exhausted page cannot include next_cursor")


@dataclass(frozen=True, slots=True)
class TermProgress:
    """Durable progress for one query term."""

    cursor: str | None
    hit_count: int
    terminal_status: TermTerminalStatus | None


@dataclass(frozen=True, slots=True)
class DiscoveryRunSummary:
    """Bounded discovery result with explicit completeness semantics."""

    candidate_ids: tuple[str, ...]
    terminal_status_by_term: Mapping[str, TermTerminalStatus]

    @property
    def complete(self) -> bool:
        return bool(self.terminal_status_by_term) and all(
            status
            in {
                TermTerminalStatus.EXHAUSTED,
                TermTerminalStatus.LIMIT_BOUND,
            }
            for status in self.terminal_status_by_term.values()
        )

    @property
    def saturated(self) -> bool:
        return self.complete and all(
            status == TermTerminalStatus.EXHAUSTED
            for status in self.terminal_status_by_term.values()
        )


class DiscoveryPageSource(Protocol):
    """Provider adapter used by the scheduler."""

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage: ...


class DiscoveryProgressStore(Protocol):
    """Durable page transaction surface required by the scheduler."""

    def ensure_terms(self, batch_id: str, terms: Sequence[str]) -> None: ...

    def term_progress(self, batch_id: str, term: str) -> TermProgress: ...

    def commit_search_page(
        self,
        *,
        batch_id: str,
        term: str,
        request_cursor: str | None,
        hits: Sequence[DiscoveryHit],
        next_cursor: str | None,
        terminal_status: TermTerminalStatus | None,
    ) -> TermProgress: ...

    def candidate_ids(self, batch_id: str) -> tuple[str, ...]: ...


def materialize_independent_term_sets(
    *,
    source: DiscoveryPageSource,
    store: DiscoveryProgressStore,
    batch_id: str,
    query_terms: Sequence[str],
    top_k_per_term: int,
    page_size: int,
) -> DiscoveryRunSummary:
    """Materialize each term's own top-K and return their stable union.

    Search terms never share a global processed or accepted counter. A page's
    continuation is committed only alongside every hit returned on that page,
    so replay after a failed transaction is safe and cannot skip candidates.
    """

    terms = _validated_terms(query_terms)
    if not batch_id.strip():
        raise ValueError("batch_id is required")
    if top_k_per_term <= 0:
        raise ValueError("top_k_per_term must be positive")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    store.ensure_terms(batch_id, terms)

    for term in terms:
        _materialize_term(
            source=source,
            store=store,
            batch_id=batch_id,
            term=term,
            top_k=top_k_per_term,
            page_size=page_size,
        )

    terminal_status_by_term: dict[str, TermTerminalStatus] = {}
    for term in terms:
        status = store.term_progress(batch_id, term).terminal_status
        if status is None:
            raise DiscoverySchedulerError(
                f"query term did not reach a bounded terminal state: {term}"
            )
        terminal_status_by_term[term] = status
    return DiscoveryRunSummary(
        candidate_ids=tuple(sorted(set(store.candidate_ids(batch_id)))),
        terminal_status_by_term=terminal_status_by_term,
    )


def _materialize_term(
    *,
    source: DiscoveryPageSource,
    store: DiscoveryProgressStore,
    batch_id: str,
    term: str,
    top_k: int,
    page_size: int,
) -> None:
    seen_cursors: set[str] = set()
    while True:
        progress = store.term_progress(batch_id, term)
        if progress.terminal_status is not None:
            return
        remaining = top_k - progress.hit_count
        if remaining <= 0:
            raise DiscoverySchedulerError(
                f"query term reached its limit without a terminal state: {term}"
            )
        if progress.cursor is not None:
            if progress.cursor in seen_cursors:
                raise DiscoverySchedulerError(
                    f"query term repeated a cursor without progress: {term}"
                )
            seen_cursors.add(progress.cursor)
        requested_page_size = min(page_size, remaining)
        page = source.fetch_page(
            term=term,
            cursor=progress.cursor,
            page_size=requested_page_size,
        )
        if len(page.hits) > requested_page_size:
            raise DiscoverySchedulerError(
                f"provider returned more hits than requested for query term: {term}"
            )
        if page.next_cursor is not None and page.next_cursor == progress.cursor:
            raise DiscoverySchedulerError(
                f"query term returned a non-advancing cursor: {term}"
            )
        new_count = progress.hit_count + len(page.hits)
        terminal_status = _terminal_status(
            page=page,
            requested_page_size=requested_page_size,
            new_count=new_count,
            top_k=top_k,
        )
        store.commit_search_page(
            batch_id=batch_id,
            term=term,
            request_cursor=progress.cursor,
            hits=page.hits,
            next_cursor=None if terminal_status is not None else page.next_cursor,
            terminal_status=terminal_status,
        )
        if terminal_status is not None:
            return


def _terminal_status(
    *,
    page: DiscoveryPage,
    requested_page_size: int,
    new_count: int,
    top_k: int,
) -> TermTerminalStatus | None:
    if page.exhausted is True:
        return TermTerminalStatus.EXHAUSTED
    if page.next_cursor is not None:
        return TermTerminalStatus.LIMIT_BOUND if new_count >= top_k else None
    if len(page.hits) < requested_page_size:
        return TermTerminalStatus.EXHAUSTED
    if new_count >= top_k:
        return TermTerminalStatus.LIMIT_BOUND_UNPAGEABLE
    return TermTerminalStatus.LIMIT_BOUND_UNPAGEABLE


def _validated_terms(query_terms: Sequence[str]) -> tuple[str, ...]:
    terms = tuple(term.strip() for term in query_terms)
    if not terms or any(not term for term in terms):
        raise ValueError("query_terms must include at least one non-empty term")
    if len(set(terms)) != len(terms):
        raise ValueError("query_terms must not contain duplicates")
    return terms
