from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from legalforecast.ingestion.budgeted_docket_acquisition import (
    acquire_ranked_dockets,
    materialize_selected_slice_batch,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.firecrawl_source import FirecrawlScrapeResult


def test_ranked_dockets_are_paginated_in_budgeted_page_waves() -> None:
    records = [_record("20", 0), _record("10", 1)]
    scheduler = _Scheduler(
        {
            ("20", 1): _page("20", 1, has_next=True),
            ("10", 1): _page("10", 1, has_next=False),
            ("20", 2): _page("20", 2, has_next=False),
        }
    )

    result = acquire_ranked_dockets(
        records=records,
        scheduler=scheduler,  # type: ignore[arg-type]
        limit=2,
        max_pages_per_docket=3,
        decision_anchor=date(2026, 6, 30),
    )

    assert scheduler.waves == [[("20", 1), ("10", 1)], [("20", 2)]]
    assert [bundle.docket_id for bundle in result.bundles] == ["20", "10"]
    assert [len(bundle.pages) for bundle in result.bundles] == [2, 1]
    assert result.failed_docket_ids == ()
    assert result.credit_summary == {"reserved_credits": 15}

    rendered = render_complete_docket_html(result.bundles[0])
    reparsed = parse_courtlistener_docket_html(
        rendered,
        source_url=result.bundles[0].base_url,
        docket_id="20",
    )
    assert len(reparsed.entries) == 2
    assert reparsed.entries[0].documents[0].pacer_only is True


def test_ranked_docket_continuation_pages_have_run_unique_ordinals(
    tmp_path: Path,
) -> None:
    records = [_record("20", 0), _record("10", 1)]

    class _Source:
        def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
            docket_id = source_url.split("/docket/", 1)[1].split("/", 1)[0]
            page_number = int(source_url.rsplit("page=", 1)[1])
            return FirecrawlScrapeResult(
                source_url=source_url,
                docket_id=docket_id,
                raw_html=_page(
                    docket_id,
                    page_number,
                    has_next=docket_id == "20" and page_number == 1,
                ),
                target_status_code=200,
                proxy_requested="auto",
                proxy_used="stealth",
                cache_state="miss",
                credits_used=1.0,
                raw={"success": True},
                resolved_url=source_url,
            )

    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("batch-001", {"terms": ["motion to dismiss"]})
        store.ensure_firecrawl_run(
            "run-001",
            batch_id="batch-001",
            config={"proxy": "auto", "max_attempts": 3},
            credit_cap=100,
            reserved_credits_per_attempt=5,
        )
        scheduler = BudgetedFirecrawlScheduler(
            store=store,
            source=_Source(),
            run_id="run-001",
            artifact_dir=tmp_path / "raw",
        )

        result = acquire_ranked_dockets(
            records=records,
            scheduler=scheduler,
            limit=2,
            max_pages_per_docket=3,
            decision_anchor=date(2026, 6, 30),
        )

        assert [bundle.docket_id for bundle in result.bundles] == ["20", "10"]
        assert [target.ordinal for target in store.firecrawl_targets("run-001")] == [
            0,
            1,
            2,
        ]


def test_failed_docket_is_not_exposed_as_partial_screening_input() -> None:
    scheduler = _Scheduler({("20", 1): _page("20", 1, has_next=False)})

    result = acquire_ranked_dockets(
        records=[_record("20", 0), _record("10", 1)],
        scheduler=scheduler,  # type: ignore[arg-type]
        limit=2,
        max_pages_per_docket=2,
        decision_anchor=date(2026, 6, 30),
    )

    assert [bundle.docket_id for bundle in result.bundles] == ["20"]
    assert result.failed_docket_ids == ("10",)
    assert result.failures[0].as_record()["case_id"] == "courtlistener-docket-10"


def test_reconstruction_failure_is_isolated_without_discarding_other_dockets() -> None:
    first_page = _page("10", 1, has_next=True)
    conflicting_page = _page("10", 2, has_next=False).replace(
        "Fixture 10", "Conflicting title", 1
    )
    scheduler = _Scheduler(
        {
            ("20", 1): _page("20", 1, has_next=False),
            ("10", 1): first_page,
            ("10", 2): conflicting_page,
        }
    )

    result = acquire_ranked_dockets(
        records=[_record("20", 0), _record("10", 1)],
        scheduler=scheduler,  # type: ignore[arg-type]
        limit=2,
        max_pages_per_docket=2,
        decision_anchor=date(2026, 6, 30),
    )

    assert [bundle.docket_id for bundle in result.bundles] == ["20"]
    assert result.failed_docket_ids == ("10",)
    assert [failure.as_record() for failure in result.failures] == [
        {
            "case_id": "courtlistener-docket-10",
            "candidate_id": "courtlistener-docket-10",
            "docket_id": "10",
            "reason": "docket_reconstruction_failed",
            "failure_stage": "complete_docket_reconstruction",
            "failure_reason": "pagination_title_mismatch",
        }
    ]


def test_resumed_malformed_success_is_excluded_without_provider_refetch(
    tmp_path: Path,
) -> None:
    records = [_record("20", 0), _record("10", 1)]
    pages = {
        "20": _page("20", 1, has_next=False),
        "10": "<html><body>successful scrape without a docket table</body></html>",
    }

    class _NoCallSource:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
            self.calls.append(source_url)
            raise AssertionError("durable successful artifacts must not be refetched")

    source = _NoCallSource()
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("batch-001", {"terms": ["motion to dismiss"]})
        store.ensure_firecrawl_run(
            "run-001",
            batch_id="batch-001",
            config={"proxy": "auto", "max_attempts": 3},
            credit_cap=100,
            reserved_credits_per_attempt=5,
        )
        for ordinal, docket_id in enumerate(("20", "10")):
            source_url = (
                f"https://www.courtlistener.com/docket/{docket_id}/fixture-case/"
                "?order_by=desc&page=1"
            )
            target_id = (
                "docket-" + hashlib.sha256(f"{docket_id}:1".encode()).hexdigest()[:24]
            )
            store.ensure_firecrawl_target(
                "run-001",
                target_id=target_id,
                target_kind="docket",
                source_url=source_url,
                ordinal=ordinal,
            )
            attempt = store.authorize_firecrawl_attempt(
                "run-001",
                target_id=target_id,
                page_number=1,
                request_url=source_url,
            )
            store.commit_firecrawl_artifact(
                attempt.attempt_id,
                tmp_path / f"{docket_id}.html",
                pages[docket_id].encode(),
                reported_credits=1,
                proxy_used="enhanced",
                target_http_status=200,
            )

        result = acquire_ranked_dockets(
            records=records,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id="run-001",
                artifact_dir=tmp_path / "raw",
            ),
            limit=2,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

    assert source.calls == []
    assert [bundle.docket_id for bundle in result.bundles] == ["20"]
    assert [failure.as_record() for failure in result.failures] == [
        {
            "case_id": "courtlistener-docket-10",
            "candidate_id": "courtlistener-docket-10",
            "docket_id": "10",
            "reason": "docket_reconstruction_failed",
            "failure_stage": "complete_docket_reconstruction",
            "failure_reason": (
                "invalid_docket_page_artifact:"
                "CourtListener docket-entry table not found"
            ),
        }
    ]
    assert len(result.bundles) + len(result.failures) == len(records)


def test_complete_renderer_preserves_restriction_evidence() -> None:
    scheduler = _Scheduler({("20", 1): _page("20", 1, has_next=False)})
    result = acquire_ranked_dockets(
        records=[_record("20", 0)],
        scheduler=scheduler,  # type: ignore[arg-type]
        limit=1,
        max_pages_per_docket=2,
        decision_anchor=date(2026, 6, 30),
    )
    bundle = result.bundles[0]
    restricted = replace(bundle.entries[0], restriction_markers=("field_issealed",))
    rendered = render_complete_docket_html(replace(bundle, entries=(restricted,)))

    reparsed = parse_courtlistener_docket_html(
        rendered,
        source_url=bundle.base_url,
        docket_id=bundle.docket_id,
    )

    assert reparsed.entries[0].restricted is True


def test_selected_slice_is_terminal_without_claiming_parent_saturation(
    tmp_path: Path,
) -> None:
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle({"schema_version": "test-cycle.v1"})
        store.ensure_batch("partial-parent", {"source": "partial-recap"})
        store.ensure_terms("partial-parent", ("motion to dismiss",))
        store.commit_search_page(
            "partial-parent",
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="hit-20",
                    candidate_id="courtlistener-docket-20",
                    payload={"docket_id": "20"},
                ),
            ),
            next_cursor="page-2",
            terminal_status=None,
        )

        targets = materialize_selected_slice_batch(
            store=store,
            parent_batch_id="partial-parent",
            selected_batch_id="batch-001-selected",
            records=[_record("20", 0)],
            limit=1,
        )

        assert targets[0].candidate_id == "courtlistener-docket-20"
        assert (
            store.term_progress("partial-parent", "motion to dismiss").terminal_status
            is None
        )
        assert (
            store.term_progress(
                "batch-001-selected", "selected-ranked-slice"
            ).terminal_status
            is TermTerminalStatus.EXHAUSTED
        )


class _Scheduler:
    def __init__(self, responses: dict[tuple[str, int], str]) -> None:
        self.responses = responses
        self.waves: list[list[tuple[str, int]]] = []

    def run(self, targets: Sequence[FirecrawlTargetSpec]) -> SimpleNamespace:
        specs = list(targets)
        wave: list[tuple[str, int]] = []
        pages: list[SimpleNamespace] = []
        for spec in specs:
            docket_id = spec.source_url.split("/docket/", 1)[1].split("/", 1)[0]
            key = (docket_id, spec.page_number)
            wave.append(key)
            raw_html = self.responses.get(key)
            if raw_html is not None:
                pages.append(
                    SimpleNamespace(
                        target_id=spec.target_id,
                        source_url=spec.source_url,
                        raw_html=raw_html,
                    )
                )
        self.waves.append(wave)
        return SimpleNamespace(
            pages=tuple(pages),
            summary={"reserved_credits": sum(len(wave) for wave in self.waves) * 5},
        )


def _record(docket_id: str, rank: int) -> dict[str, object]:
    return {
        "identity": {
            "courtlistener_docket_id": docket_id,
            "courtlistener_url": (
                f"https://www.courtlistener.com/docket/{docket_id}/fixture-case/"
            ),
        },
        "ranking_key": [rank, 3, docket_id],
    }


def _page(docket_id: str, page_number: int, *, has_next: bool) -> str:
    next_link = (
        f'<a rel="next" href="?order_by=desc&amp;page={page_number + 1}">Next</a>'
        if has_next
        else ""
    )
    filed_at = f"July {10 - page_number}, 2026"
    pacer_url = f"https://ecf.example/doc-{page_number}"
    return f"""
    <html><head><title>Fixture {docket_id}</title></head><body>
      <div id="docket-entry-table">
        <div id="entry-{docket_id}-{page_number}" class="row">
          <div class="col-xs-1">{page_number}</div>
          <div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>
          <div class="col-xs-8">Motion to dismiss fixture entry.
            <div class="row recap-documents"><div>Main Document</div>
              <div>Motion to Dismiss</div>
              <a class="open_buy_pacer_modal" href="{pacer_url}">Buy on PACER</a>
            </div>
          </div>
        </div>
      </div>
      {next_link}
    </body></html>
    """
