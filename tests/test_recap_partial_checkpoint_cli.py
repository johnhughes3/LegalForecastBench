from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from legalforecast.cli import main
from legalforecast.ingestion.case_dev_recap_batch import (
    recap_discovered_docket_from_record,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_recap_discovery import build_recap_search_url

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 12)


def _partial_search_html(*, next_url: str) -> str:
    return (
        "<!doctype html><html><head><title>"
        "Search Results for test — 2 Results — CourtListener.com"
        '</title></head><body><main id="search-results"><article>'
        '<h3 class="bottom serif"><a href="/docket/70649963/case/" '
        'class="visitable">Example v. Example</a></h3><div class="bottom">'
        '<div class="col-md-offset-half"><h4><a '
        'href="/docket/70649963/14/case/" class="visitable">'
        "Order denying motion to dismiss — Document #14</a></h4>"
        '<div class="date-block"><span>Date Filed:</span>'
        '<time datetime="2026-07-02">2026-07-02</time></div>'
        '<div class="inline-block"><span>Description:</span>'
        '<span class="meta-data-value">Order denying motion to dismiss</span>'
        "</div></div></div></article></main>"
        '<div class="well"><div class="text-center large">Page 1 of 2</div>'
        f'<a href="{next_url}" rel="next" class="btn">Next</a></div>'
        "</body></html>"
    )


def _seed_partial_run(store_path: Path, artifact_path: Path) -> None:
    term = "motion to dismiss"
    source_url = build_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    next_url = build_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    raw_html = _partial_search_html(next_url=next_url)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
        store.ensure_batch("batch-001", {"terms": [term]})
        store.ensure_terms("batch-001", [term])
        store.ensure_firecrawl_run(
            "run-001",
            batch_id="batch-001",
            config={"proxy": "auto"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "run-001",
            target_id="search-page-001",
            target_kind="search",
            source_url=source_url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-001",
            target_id="search-page-001",
            page_number=1,
            request_url=source_url,
        )
        store.commit_firecrawl_artifact(
            attempt.attempt_id,
            artifact_path,
            raw_html.encode("utf-8"),
            reported_credits=5,
            proxy_used="stealth",
            target_http_status=200,
        )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_projects_durable_run_into_case_dev_compatible_partial_checkpoint(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    output_root = tmp_path / "output"
    _seed_partial_run(store_path, tmp_path / "raw" / "page-001.html")
    command = [
        "acquisition",
        "project-firecrawl-recap-checkpoint",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(store_path),
        "--run-id",
        "run-001",
        "--execute",
    ]

    assert main(command) == 0

    checkpoint_root = output_root / "checkpoints"
    pages_path = checkpoint_root / "run-001-partial-recap-pages.jsonl"
    entries_path = checkpoint_root / "run-001-partial-recap-entries.jsonl"
    dockets_path = checkpoint_root / "run-001-partial-recap-dockets.jsonl"
    summary_path = checkpoint_root / "run-001-partial-recap-summary.json"
    first_artifacts = {
        path: path.read_bytes()
        for path in (pages_path, entries_path, dockets_path, summary_path)
    }

    pages = _read_jsonl(pages_path)
    entries = _read_jsonl(entries_path)
    dockets = _read_jsonl(dockets_path)
    summary = json.loads(summary_path.read_text())
    assert len(pages) == len(entries) == len(dockets) == 1
    assert pages[0]["checkpoint_only"] is True
    assert entries[0]["complete"] is False
    assert dockets[0]["saturated"] is False
    assert dockets[0]["eligibility_status"] == "potential_unverified"
    converted = recap_discovered_docket_from_record(dockets[0])
    assert converted.docket_id == "70649963"
    assert summary["batch_id"] == "batch-001"
    assert summary["run_id"] == "run-001"
    assert summary["acquired_page_count"] == 1
    assert summary["potential_candidate_count"] == 1
    assert summary["clean_corpus_count"] == 0
    assert summary["reserved_credits"] == 5
    assert summary["reported_credits"] == 5
    assert summary["remaining_authorization"] == 44_995
    assert summary["store_projection_committed"] is True
    assert summary["checkpoint_only"] is True
    assert summary["complete"] is False
    assert summary["saturated"] is False
    assert summary["firecrawl_metered_activity_requested"] is False
    assert summary["pacer_paid_activity_requested"] is False
    with CycleAcquisitionStore(store_path) as store:
        assert store.candidate_ids("batch-001") == ("courtlistener-docket-70649963",)
        progress = store.term_progress("batch-001", "motion to dismiss")
        assert progress.cursor == "2"
        assert progress.terminal_status is None

    assert main(command) == 0
    assert {
        path: path.read_bytes()
        for path in (pages_path, entries_path, dockets_path, summary_path)
    } == first_artifacts


def test_partial_checkpoint_dry_run_does_not_require_or_mutate_store(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    store_path = tmp_path / "missing.sqlite3"

    assert (
        main(
            [
                "acquisition",
                "project-firecrawl-recap-checkpoint",
                "--output-root",
                str(output_root),
                "--cycle-store",
                str(store_path),
                "--run-id",
                "run-001",
            ]
        )
        == 0
    )

    assert not store_path.exists()
    summary = json.loads(
        (output_root / "checkpoints" / "run-001-partial-recap-summary.json").read_text()
    )
    assert summary["dry_run"] is True
    assert summary["store_projection_committed"] is False
    assert summary["checkpoint_only"] is True
    assert summary["complete"] is False
    assert summary["saturated"] is False
