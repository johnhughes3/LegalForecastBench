from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import legalforecast.ingestion.courtlistener_acquisition as acquisition_module
import pytest
from legalforecast.ingestion.courtlistener_acquisition import (
    discover_courtlistener_mtd_candidates,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerRateLimitError,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, DiscoveryPage


def _store(tmp_path: Path) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle(
        {
            "policy_schema": "legalforecast.cycle_acquisition_policy.v1",
            "eligibility_anchor": "2026-06-30",
        }
    )
    store.ensure_batch(
        "durable-batch",
        {
            "provider": "courtlistener",
            "window": ["2026-07-11", "2026-07-15"],
        },
    )
    return store


def _page(*candidate_ids: str, next_cursor: str | None) -> DiscoveryPage:
    return DiscoveryPage(
        hits=tuple(
            DiscoveryHit(
                provider_hit_id=f"hit-{candidate_id}",
                candidate_id=candidate_id,
                payload={"id": candidate_id, "docket_id": candidate_id},
            )
            for candidate_id in candidate_ids
        ),
        next_cursor=next_cursor,
        exhausted=next_cursor is None,
    )


def test_durable_discovery_resumes_search_and_candidate_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_calls: list[str | None] = []
    screen_calls: list[str] = []
    interrupt_second_page = True

    def fetch_page(
        _self: object,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        nonlocal interrupt_second_page
        assert term == "motion to dismiss"
        assert page_size == 2
        fetch_calls.append(cursor)
        if cursor is None:
            return _page("101", "102", next_cursor="next-page")
        assert cursor == "next-page"
        if interrupt_second_page:
            interrupt_second_page = False
            raise CourtListenerRateLimitError("injected daily limit")
        return _page("103", next_cursor=None)

    def screen_candidate(**kwargs: Any) -> tuple[dict[str, object], None]:
        candidate_id = cast(str, kwargs["docket_id"])
        screen_calls.append(candidate_id)
        return (
            {
                "candidate": {
                    "docket_id": candidate_id,
                    "metadata": {"case_id": candidate_id},
                },
                "first_written_mtd_disposition_date": "2026-07-14",
            },
            None,
        )

    monkeypatch.setattr(
        acquisition_module._DurableCourtListenerSearchSource,
        "fetch_page",
        fetch_page,
    )
    monkeypatch.setattr(acquisition_module, "_screen_candidate", screen_candidate)

    with _store(tmp_path) as store:
        kwargs = {
            "client": cast(CourtListenerClient, object()),
            "html_source": cast(
                acquisition_module.CourtListenerDocketHTMLSource, object()
            ),
            "raw_html_dir": tmp_path / "raw",
            "decision_filed_on_or_after": date(2026, 6, 30),
            "search_window_start": date(2026, 7, 11),
            "search_window_end": date(2026, 7, 15),
            "query_terms": ("motion to dismiss",),
            "target_clean_cases": 100,
            "max_candidates": 10,
            "search_page_size": 2,
            "progress_store": store,
            "batch_id": "durable-batch",
        }
        with pytest.raises(CourtListenerRateLimitError, match="daily limit"):
            discover_courtlistener_mtd_candidates(**kwargs)

        resumed = discover_courtlistener_mtd_candidates(**kwargs)
        repeated = discover_courtlistener_mtd_candidates(**kwargs)

    assert fetch_calls == [None, "next-page", "next-page"]
    assert screen_calls == ["101", "102", "103"]
    assert repeated.screened_cases == resumed.screened_cases
    assert repeated.search_pages == resumed.search_pages
    assert [page["request_cursor"] for page in resumed.search_pages] == [
        None,
        "next-page",
    ]
    assert resumed.search_pages[-1]["terminal_status"] == "exhausted"
    assert resumed.summary["durable_rest_checkpointing"] is True
    assert resumed.summary["discovery_saturated"] is True


def test_durable_discovery_no_resume_refuses_existing_progress(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("durable-batch", ("motion to dismiss",))
        store.commit_search_page(
            "durable-batch",
            "motion to dismiss",
            None,
            (_page("101", next_cursor=None).hits[0],),
            next_cursor=None,
            terminal_status="exhausted",
        )
        with pytest.raises(
            RuntimeError,
            match="durable CourtListener progress exists",
        ):
            discover_courtlistener_mtd_candidates(
                client=cast(CourtListenerClient, object()),
                html_source=cast(
                    acquisition_module.CourtListenerDocketHTMLSource, object()
                ),
                raw_html_dir=tmp_path / "raw",
                decision_filed_on_or_after=date(2026, 6, 30),
                search_window_start=date(2026, 7, 11),
                search_window_end=date(2026, 7, 15),
                query_terms=("motion to dismiss",),
                target_clean_cases=100,
                max_candidates=10,
                search_page_size=2,
                resume=False,
                progress_store=store,
                batch_id="durable-batch",
            )
