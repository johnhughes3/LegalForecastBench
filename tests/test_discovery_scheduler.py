from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    DiscoveryPage,
    DiscoverySchedulerError,
    TermProgress,
    TermTerminalStatus,
    materialize_independent_term_sets,
)


@dataclass
class _PageSource:
    pages: Mapping[tuple[str, str | None], DiscoveryPage]

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, str | None, int]] = []

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        self.calls.append((term, cursor, page_size))
        return self.pages[(term, cursor)]


class _MemoryStore:
    def __init__(self, *, fail_next_commit: bool = False) -> None:
        self.progress: dict[tuple[str, str], TermProgress] = {}
        self.hits: dict[tuple[str, str], dict[str, DiscoveryHit]] = {}
        self.fail_next_commit = fail_next_commit

    def ensure_terms(self, batch_id: str, terms: Sequence[str]) -> None:
        for term in terms:
            self.progress.setdefault((batch_id, term), TermProgress(None, 0, None))
            self.hits.setdefault((batch_id, term), {})

    def term_progress(self, batch_id: str, term: str) -> TermProgress:
        return self.progress[(batch_id, term)]

    def commit_search_page(
        self,
        *,
        batch_id: str,
        term: str,
        request_cursor: str | None,
        hits: Sequence[DiscoveryHit],
        next_cursor: str | None,
        terminal_status: TermTerminalStatus | None,
    ) -> None:
        key = (batch_id, term)
        current = self.progress[key]
        assert current.cursor == request_cursor
        if self.fail_next_commit:
            self.fail_next_commit = False
            raise RuntimeError("simulated crash before transaction commit")
        committed = self.hits[key]
        for hit in hits:
            committed.setdefault(hit.provider_hit_id, hit)
        self.progress[key] = TermProgress(
            cursor=next_cursor,
            hit_count=len(committed),
            terminal_status=terminal_status,
        )

    def candidate_ids(self, batch_id: str) -> tuple[str, ...]:
        return tuple(
            hit.candidate_id
            for (candidate_batch_id, _), hits in self.hits.items()
            if candidate_batch_id == batch_id
            for hit in hits.values()
        )


def test_query_term_permutations_produce_identical_candidate_union() -> None:
    pages = {
        ("alpha", None): _page("alpha", ("case-1", "case-2"), exhausted=True),
        ("beta", None): _page("beta", ("case-2", "case-3"), exhausted=True),
    }

    results = []
    for terms in (("alpha", "beta"), ("beta", "alpha")):
        result = materialize_independent_term_sets(
            source=_PageSource(pages),
            store=_MemoryStore(),
            batch_id="batch-1",
            query_terms=terms,
            top_k_per_term=10,
            page_size=10,
        )
        results.append(result.candidate_ids)

    assert results == [
        ("case-1", "case-2", "case-3"),
        ("case-1", "case-2", "case-3"),
    ]


def test_each_term_receives_its_own_top_k_limit() -> None:
    source = _PageSource(
        {
            ("alpha", None): _page(
                "alpha",
                ("case-1", "case-2"),
                next_cursor="alpha-next",
            ),
            ("beta", None): _page(
                "beta",
                ("case-3", "case-4"),
                next_cursor="beta-next",
            ),
        }
    )

    result = materialize_independent_term_sets(
        source=source,
        store=_MemoryStore(),
        batch_id="batch-1",
        query_terms=("alpha", "beta"),
        top_k_per_term=2,
        page_size=50,
    )

    assert result.candidate_ids == ("case-1", "case-2", "case-3", "case-4")
    assert result.terminal_status_by_term == {
        "alpha": TermTerminalStatus.LIMIT_BOUND,
        "beta": TermTerminalStatus.LIMIT_BOUND,
    }
    assert result.complete is True
    assert result.saturated is False
    assert source.calls == [("alpha", None, 2), ("beta", None, 2)]


def test_failed_page_commit_replays_without_duplicates_or_skips() -> None:
    source = _PageSource(
        {("alpha", None): _page("alpha", ("case-1", "case-2"), exhausted=True)}
    )
    store = _MemoryStore(fail_next_commit=True)

    with pytest.raises(RuntimeError, match="simulated crash"):
        materialize_independent_term_sets(
            source=source,
            store=store,
            batch_id="batch-1",
            query_terms=("alpha",),
            top_k_per_term=10,
            page_size=10,
        )

    result = materialize_independent_term_sets(
        source=source,
        store=store,
        batch_id="batch-1",
        query_terms=("alpha",),
        top_k_per_term=10,
        page_size=10,
    )

    assert result.candidate_ids == ("case-1", "case-2")
    assert source.calls == [("alpha", None, 10), ("alpha", None, 10)]


def test_full_page_without_continuation_is_not_claimed_exhaustive() -> None:
    result = materialize_independent_term_sets(
        source=_PageSource({("alpha", None): _page("alpha", ("case-1", "case-2"))}),
        store=_MemoryStore(),
        batch_id="batch-1",
        query_terms=("alpha",),
        top_k_per_term=10,
        page_size=2,
    )

    assert result.complete is False
    assert result.saturated is False
    assert result.terminal_status_by_term == {
        "alpha": TermTerminalStatus.LIMIT_BOUND_UNPAGEABLE
    }


def test_underfilled_page_without_continuation_is_exhausted() -> None:
    result = materialize_independent_term_sets(
        source=_PageSource({("alpha", None): _page("alpha", ("case-1",))}),
        store=_MemoryStore(),
        batch_id="batch-1",
        query_terms=("alpha",),
        top_k_per_term=10,
        page_size=2,
    )

    assert result.saturated is True
    assert result.terminal_status_by_term == {"alpha": TermTerminalStatus.EXHAUSTED}


def test_non_advancing_cursor_fails_closed() -> None:
    source = _PageSource(
        {
            ("alpha", None): _page("alpha", ("case-1",), next_cursor="same-cursor"),
            ("alpha", "same-cursor"): _page(
                "alpha", ("case-2",), next_cursor="same-cursor"
            ),
        }
    )

    with pytest.raises(DiscoverySchedulerError, match="non-advancing cursor"):
        materialize_independent_term_sets(
            source=source,
            store=_MemoryStore(),
            batch_id="batch-1",
            query_terms=("alpha",),
            top_k_per_term=10,
            page_size=1,
        )


def _page(
    term: str,
    candidate_ids: tuple[str, ...],
    *,
    next_cursor: str | None = None,
    exhausted: bool | None = None,
) -> DiscoveryPage:
    return DiscoveryPage(
        hits=tuple(
            DiscoveryHit(
                provider_hit_id=f"{term}-hit-{index}",
                candidate_id=candidate_id,
                payload={"candidate_id": candidate_id},
            )
            for index, candidate_id in enumerate(candidate_ids, start=1)
        ),
        next_cursor=next_cursor,
        exhausted=exhausted,
    )
