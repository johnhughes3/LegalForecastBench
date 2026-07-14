from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from legalforecast.cli import main
from legalforecast.ingestion.case_dev_recap_batch import (
    recap_discovered_docket_from_record,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_recap_decision_discovery import (
    DECISION_FIRST_RECAP_QUERY_PLAN_VERSION,
    DECISION_FIRST_RECAP_SEARCH_TERMS,
    build_decision_recap_search_url,
)
from legalforecast.ingestion.firecrawl_recap_discovery import build_recap_search_url

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 12)


def _partial_search_html(
    *,
    next_url: str | None,
    page_number: int = 1,
) -> str:
    next_link = (
        f'<a href="{next_url}" rel="next" class="btn">Next</a>'
        if next_url is not None
        else ""
    )
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
        '<div class="well"><div class="text-center large">'
        f"Page {page_number} of 2</div>{next_link}</div>"
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
        store.ensure_cycle({"eligibility_anchor": "2026-06-30"})
        store.ensure_batch(
            "batch-001",
            {
                "terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-12",
            },
        )
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


def _seed_decision_partial_run(store_path: Path, artifact_path: Path) -> None:
    term = DECISION_FIRST_RECAP_SEARCH_TERMS[0]
    source_url = build_decision_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    raw_html = _partial_search_html(next_url=None).replace("Page 1 of 2", "Page 1 of 1")
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"eligibility_anchor": "2026-06-30"})
        store.ensure_batch(
            "batch-decisions",
            {
                "query_terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-12",
                "courtlistener_query_plan_version": (
                    DECISION_FIRST_RECAP_QUERY_PLAN_VERSION
                ),
                "courtlistener_search_type": "r",
            },
        )
        store.ensure_terms("batch-decisions", [term])
        store.ensure_firecrawl_run(
            "run-decisions",
            batch_id="batch-decisions",
            config={"proxy": "auto"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "run-decisions",
            target_id="decision-page-001",
            target_kind="search",
            source_url=source_url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-decisions",
            target_id="decision-page-001",
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


def _seed_repeated_hit_across_pages(store_path: Path, artifact_root: Path) -> None:
    term = "motion to dismiss"
    source_urls = tuple(
        build_recap_search_url(
            term=term,
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            **({} if page_number == 1 else {"page": page_number}),
        )
        for page_number in (1, 2)
    )
    raw_pages = (
        _partial_search_html(next_url=source_urls[1], page_number=1),
        _partial_search_html(next_url=None, page_number=2),
    )
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"eligibility_anchor": "2026-06-30"})
        store.ensure_batch(
            "batch-001",
            {
                "terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-12",
            },
        )
        store.ensure_terms("batch-001", [term])
        store.ensure_firecrawl_run(
            "run-001",
            batch_id="batch-001",
            config={"proxy": "auto"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        for ordinal, (source_url, raw_html) in enumerate(
            zip(source_urls, raw_pages, strict=True)
        ):
            page_number = ordinal + 1
            target_id = f"search-page-{page_number:03d}"
            store.ensure_firecrawl_target(
                "run-001",
                target_id=target_id,
                target_kind="search",
                source_url=source_url,
                ordinal=ordinal,
            )
            attempt = store.authorize_firecrawl_attempt(
                "run-001",
                target_id=target_id,
                page_number=page_number,
                request_url=source_url,
            )
            store.commit_firecrawl_artifact(
                attempt.attempt_id,
                artifact_root / f"page-{page_number:03d}.html",
                raw_html.encode("utf-8"),
                reported_credits=5,
                proxy_used="stealth",
                target_http_status=200,
            )


def _seed_split_pages_across_runs(store_path: Path, artifact_root: Path) -> None:
    _seed_partial_run(store_path, artifact_root / "run-001-page-001.html")
    term = "motion to dismiss"
    source_url = build_recap_search_url(
        term=term,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=2,
    )
    raw_html = _partial_search_html(next_url=None, page_number=2)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_firecrawl_run(
            "run-002",
            batch_id="batch-001",
            config={"proxy": "enhanced"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "run-002",
            target_id="search-page-002",
            target_kind="search",
            source_url=source_url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-002",
            target_id="search-page-002",
            page_number=2,
            request_url=source_url,
        )
        store.commit_firecrawl_artifact(
            attempt.attempt_id,
            artifact_root / "run-002-page-002.html",
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
    assert summary["eligibility_anchor"] == "2026-06-30"
    assert summary["search_window_start"] == "2026-06-30"
    assert summary["search_window_end"] == "2026-07-12"
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


def test_projects_frozen_decision_first_run_with_its_canonical_urls(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    output_root = tmp_path / "output"
    _seed_decision_partial_run(store_path, tmp_path / "raw" / "page-001.html")

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
                "run-decisions",
                "--execute",
            ]
        )
        == 0
    )

    checkpoint_root = output_root / "checkpoints"
    entries = _read_jsonl(checkpoint_root / "run-decisions-partial-recap-entries.jsonl")
    summary = json.loads(
        (checkpoint_root / "run-decisions-partial-recap-summary.json").read_text()
    )
    assert [entry["docket_id"] for entry in entries] == ["70649963"]
    assert summary["terms"] == [DECISION_FIRST_RECAP_SEARCH_TERMS[0]]


def test_repeated_cross_page_hit_commits_once_and_replays_exactly(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    output_root = tmp_path / "output"
    _seed_repeated_hit_across_pages(store_path, tmp_path / "raw")
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
    output_paths = (
        checkpoint_root / "run-001-partial-recap-pages.jsonl",
        checkpoint_root / "run-001-partial-recap-entries.jsonl",
        checkpoint_root / "run-001-partial-recap-dockets.jsonl",
        checkpoint_root / "run-001-partial-recap-summary.json",
    )
    first_artifacts = {path: path.read_bytes() for path in output_paths}
    entries = _read_jsonl(output_paths[1])
    dockets = _read_jsonl(output_paths[2])
    summary = json.loads(output_paths[3].read_text())

    assert len(entries) == len(dockets) == 1
    assert summary["acquired_page_count"] == 2
    assert summary["raw_hit_count"] == 2
    assert summary["unique_entry_count"] == 1
    assert summary["duplicate_entry_count"] == 1
    with CycleAcquisitionStore(store_path) as store:
        progress = store.term_progress("batch-001", "motion to dismiss")
        assert progress.hit_count == 2
        assert progress.terminal_status == "exhausted"

    assert main(command) == 0
    assert {path: path.read_bytes() for path in output_paths} == first_artifacts


def test_unions_verified_pages_across_bounded_same_batch_runs(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    output_root = tmp_path / "output"
    _seed_split_pages_across_runs(store_path, tmp_path / "raw")

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
                "--run-id",
                "run-002",
                "--execute",
            ]
        )
        == 0
    )

    summaries = list(
        (output_root / "checkpoints").glob("run-001-union-*-partial-recap-summary.json")
    )
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["run_ids"] == ["run-001", "run-002"]
    assert summary["acquired_page_count"] == 2
    assert summary["checkpoint_only"] is True
    assert summary["complete"] is False
    assert set(summary["source_run_credit_summaries"]) == {"run-001", "run-002"}
    with CycleAcquisitionStore(store_path) as store:
        progress = store.term_progress("batch-001", "motion to dismiss")
    assert progress.terminal_status == "exhausted"


def test_union_rejects_conflicting_verified_bytes_for_same_search_url(
    tmp_path: Path, capsys: Any
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
    )
    _seed_partial_run(store_path, tmp_path / "raw" / "run-001.html")
    conflicting_html = _partial_search_html(
        next_url=build_recap_search_url(
            term="motion to dismiss",
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            page=2,
        )
    ).replace("Example v. Example", "Changed v. Example")
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_firecrawl_run(
            "run-002",
            batch_id="batch-001",
            config={"proxy": "enhanced"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "run-002",
            target_id="search-page-001",
            target_kind="search",
            source_url=source_url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-002",
            target_id="search-page-001",
            page_number=1,
            request_url=source_url,
        )
        store.commit_firecrawl_artifact(
            attempt.attempt_id,
            tmp_path / "raw" / "run-002.html",
            conflicting_html.encode("utf-8"),
            reported_credits=5,
            proxy_used="stealth",
            target_http_status=200,
        )

    assert (
        main(
            [
                "acquisition",
                "project-firecrawl-recap-checkpoint",
                "--output-root",
                str(tmp_path / "output"),
                "--cycle-store",
                str(store_path),
                "--run-id",
                "run-001",
                "--run-id",
                "run-002",
                "--execute",
            ]
        )
        == 2
    )
    assert "conflicting verified bytes" in capsys.readouterr().err


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
