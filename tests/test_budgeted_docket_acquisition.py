from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from types import SimpleNamespace

from legalforecast.ingestion.budgeted_docket_acquisition import (
    acquire_ranked_dockets,
)
from legalforecast.ingestion.budgeted_firecrawl import FirecrawlTargetSpec


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
    return f"""
    <html><head><title>Fixture {docket_id}</title></head><body>
      <div id="docket-entry-table">
        <div id="entry-{docket_id}-{page_number}" class="docket-row">
          <span class="date-filed">July {10 - page_number}, 2026</span>
          <span class="document-number">{page_number}</span>
          <p class="description">Motion to dismiss fixture entry.</p>
        </div>
      </div>
      {next_link}
    </body></html>
    """
