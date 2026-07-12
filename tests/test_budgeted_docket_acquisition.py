from __future__ import annotations

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
from legalforecast.ingestion.budgeted_firecrawl import FirecrawlTargetSpec
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
)


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
