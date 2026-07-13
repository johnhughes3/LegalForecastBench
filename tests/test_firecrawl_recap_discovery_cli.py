from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import legalforecast.cli as cli_module
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_recap_discovery import (
    build_recap_search_url,
    parse_recap_search_url,
)


def test_discover_firecrawl_recap_uses_shared_budget_and_reports_potentials(
    tmp_path: Path,
) -> None:
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=date(2026, 6, 30),
        entry_date_filed_before=date(2026, 7, 12),
    )
    raw_html = (
        "<!doctype html><html><head><title>0 Results — CourtListener.com</title>"
        "</head><body></body></html>"
    )
    fixture = tmp_path / "firecrawl.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": 200,
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                            "sourceURL": source_url,
                        },
                    },
                },
                "headers": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "output"

    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(output_root),
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "recap-search-001",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--proxy",
                "auto",
                "--execute",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "checkpoints" / "batch-001-recap-summary.json").read_text()
    )
    assert summary["potential_candidate_count"] == 0
    assert summary["clean_corpus_count"] == 0
    assert summary["complete"] is True
    assert summary["saturated"] is True
    assert summary["pages_fetched"] == 1
    assert summary["credit_cap"] == 45_000
    assert summary["reserved_credits"] == 5
    assert summary["reported_credits"] == 1
    assert summary["remaining_authorization"] == 44_995
    assert summary["query_terms"] == ["motion to dismiss"]
    assert summary["courtlistener_query_plan_version"] == "phrase-precise-v1"
    assert summary["courtlistener_query_expressions"] == ['"motion to dismiss"']
    assert summary["eligibility_anchor"] == "2026-06-30"
    assert summary["search_window_start"] == "2026-06-30"
    assert summary["search_window_end"] == "2026-07-12"
    assert (
        output_root / "checkpoints" / "batch-001-recap-entries.jsonl"
    ).read_text() == ""
    assert (
        output_root / "checkpoints" / "batch-001-recap-dockets.jsonl"
    ).read_text() == ""


def test_discover_firecrawl_recap_accepts_judgment_on_pleadings_terms(
    tmp_path: Path,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(tmp_path / "output"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "recap-search-001",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--query-term",
                "order on motion for judgment on the pleadings",
                "--live-firecrawl",
            ]
        )
        == 0
    )


def _empty_firecrawl_fixture(path: Path, *, start: date, end: date) -> Path:
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=start,
        entry_date_filed_before=end,
    )
    path.write_text(
        json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": (
                            "<!doctype html><html><head><title>0 Results — "
                            "CourtListener.com</title></head><body></body></html>"
                        ),
                        "metadata": {
                            "statusCode": 200,
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                            "sourceURL": source_url,
                        },
                    },
                },
                "headers": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _target_error_firecrawl_fixture(path: Path, *, start: date, end: date) -> Path:
    source_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=start,
        entry_date_filed_before=end,
    )
    path.write_text(
        json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": "<html><body>upstream error</body></html>",
                        "metadata": {
                            "statusCode": 500,
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                            "sourceURL": source_url,
                        },
                    },
                },
                "headers": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _article(*, document_number: str) -> str:
    return (
        '<article><h3 class="bottom serif"><a href="/docket/12345/alpha-v-beta/" '
        'class="visitable">Alpha v. Beta</a></h3><div class="bottom">'
        '<div class="col-md-offset-half"><h4><a href="/docket/12345/'
        f'{document_number}/alpha-v-beta/" class="visitable">Order denying motion '
        f'to dismiss — Document #{document_number}</a></h4><div class="date-block">'
        '<span>Date Filed:</span><time datetime="2026-07-01">2026-07-01</time>'
        '</div><div class="inline-block"><span>Description:</span>'
        '<span class="meta-data-value">Order denying motion to dismiss</span>'
        "</div></div></div></article>"
    )


def _three_page_failure_fixtures(
    tmp_path: Path, *, start: date, end: date
) -> tuple[Path, Path]:
    page_one_url = build_recap_search_url(
        term="motion to dismiss",
        entry_date_filed_after=start,
        entry_date_filed_before=end,
    )
    page_two_url = f"{page_one_url}&page=2"
    page_three_url = f"{page_one_url}&page=3"
    page_one_html = (
        "<!doctype html><html><head><title>Search — 2 Results — "
        'CourtListener.com</title></head><body><main id="search-results">'
        f'{_article(document_number="27")}</main><div class="well">'
        '<div class="text-center large">Page 1 of 3</div>'
        f'<a href="?{urlsplit(page_two_url).query}" rel="next">Next</a>'
        "</div></body></html>"
    )
    page_two_html = (
        "<!doctype html><html><head><title>Search — 3 Results — "
        'CourtListener.com</title></head><body><main id="search-results">'
        f'{_article(document_number="28")}</main><div class="well">'
        '<div class="text-center large">Page 2 of 3</div>'
        f'<a href="?{urlsplit(page_three_url).query}" rel="next">Next</a>'
        "</div></body></html>"
    )
    page_three_html = (
        "<!doctype html><html><head><title>Search — 3 Results — "
        'CourtListener.com</title></head><body><main id="search-results">'
        f'{_article(document_number="29")}</main><div class="well">'
        '<div class="text-center large">Page 3 of 3</div></div></body></html>'
    )

    def response(source_url: str, raw_html: str, target_status: int) -> str:
        return json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": target_status,
                            "proxyUsed": "stealth",
                            "cacheState": "miss",
                            "creditsUsed": 5,
                            "sourceURL": source_url,
                        },
                    },
                },
                "headers": {},
            }
        )

    failed = tmp_path / "two-page-failed.jsonl"
    failed.write_text(
        response(page_one_url, page_one_html, 200)
        + "\n"
        + response(page_two_url, "<html><body>upstream error</body></html>", 500)
        + "\n",
        encoding="utf-8",
    )
    recovered = tmp_path / "two-page-recovered.jsonl"
    recovered.write_text(
        response(page_two_url, page_two_html, 200)
        + "\n"
        + response(page_three_url, page_three_html, 200)
        + "\n",
        encoding="utf-8",
    )
    return failed, recovered


def _discovery_args(
    tmp_path: Path,
    *,
    run_id: str,
    fixture: Path,
    credit_cap: int = 45_000,
    recovery_of: str | None = None,
) -> list[str]:
    args = [
        "acquisition",
        "discover-firecrawl-recap",
        "--output-root",
        str(tmp_path / "output"),
        "--cycle-store",
        str(tmp_path / "cycle.sqlite3"),
        "--batch-id",
        "batch-recovery",
        "--run-id",
        run_id,
        "--eligibility-anchor",
        "2026-06-30",
        "--search-window-start",
        "2026-07-01",
        "--search-window-end",
        "2026-07-01",
        "--query-term",
        "motion to dismiss",
        "--firecrawl-fixture",
        str(fixture),
        "--credit-cap",
        str(credit_cap),
        "--execute",
    ]
    if recovery_of is not None:
        args.extend(
            [
                "--recover-terminal-errors-from-run",
                recovery_of,
                "--proxy",
                "enhanced",
                "--force-browser",
            ]
        )
    return args


def test_terminal_error_recovery_uses_unique_enhanced_run_and_parent_pages(
    tmp_path: Path, capsys: Any
) -> None:
    start = date(2026, 7, 1)
    failed_fixture, recovered_fixture = _three_page_failure_fixtures(
        tmp_path, start=start, end=start
    )
    assert (
        main(_discovery_args(tmp_path, run_id="run-primary", fixture=failed_fixture))
        == 2
    )
    assert "retries were exhausted" in capsys.readouterr().err

    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-1",
                fixture=recovered_fixture,
                recovery_of="run-primary",
            )
        )
        == 0
    )

    summary_path = (
        tmp_path
        / "output"
        / "checkpoints"
        / "run-primary-recovery-1-recap-summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["complete"] is True
    assert summary["recovery_of_run_id"] == "run-primary"
    assert summary["recovery_terminal_target_count"] == 1
    assert summary["pages_fetched"] == 3
    assert summary["entry_count"] == 3
    assert summary["proxy"] == "enhanced"
    assert summary["force_browser"] is True
    assert summary["reserved_credits"] == 20
    assert summary["attempt_status_counts"] == {"succeeded": 1}
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        parent_targets = store.firecrawl_targets("run-primary")
        child_targets = store.firecrawl_targets("run-primary-recovery-1")
    assert [
        parse_recap_search_url(target.source_url).page for target in parent_targets
    ] == [
        1,
        2,
        3,
    ]
    assert [
        parse_recap_search_url(target.source_url).page for target in child_targets
    ] == [2]


def test_terminal_error_recovery_rejects_changed_parent_batch_config(
    tmp_path: Path, capsys: Any
) -> None:
    start = date(2026, 7, 1)
    failed_fixture = _target_error_firecrawl_fixture(
        tmp_path / "failed.jsonl", start=start, end=start
    )
    assert (
        main(_discovery_args(tmp_path, run_id="run-primary", fixture=failed_fixture))
        == 2
    )
    capsys.readouterr()
    recovery_fixture = _empty_firecrawl_fixture(
        tmp_path / "recovery.jsonl", start=start, end=start
    )
    changed = _discovery_args(
        tmp_path,
        run_id="run-primary-recovery-1",
        fixture=recovery_fixture,
        recovery_of="run-primary",
    )
    term_index = changed.index("motion to dismiss")
    changed[term_index] = "motion for judgment on the pleadings"
    assert main(changed) == 2
    assert "batch config mismatch" in capsys.readouterr().err


def test_terminal_error_recovery_shares_cycle_cap(tmp_path: Path, capsys: Any) -> None:
    start = date(2026, 7, 1)
    failed_fixture = _target_error_firecrawl_fixture(
        tmp_path / "failed.jsonl", start=start, end=start
    )
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary",
                fixture=failed_fixture,
                credit_cap=5,
            )
        )
        == 2
    )
    capsys.readouterr()
    recovery_fixture = _empty_firecrawl_fixture(
        tmp_path / "recovery.jsonl", start=start, end=start
    )
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-1",
                fixture=recovery_fixture,
                credit_cap=5,
                recovery_of="run-primary",
            )
        )
        == 2
    )
    assert "credit cap" in capsys.readouterr().err


def test_terminal_error_recovery_cannot_chain_fallback_runs(
    tmp_path: Path, capsys: Any
) -> None:
    start = date(2026, 7, 1)
    failed_fixture = _target_error_firecrawl_fixture(
        tmp_path / "failed.jsonl", start=start, end=start
    )
    assert (
        main(_discovery_args(tmp_path, run_id="run-primary", fixture=failed_fixture))
        == 2
    )
    capsys.readouterr()
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-1",
                fixture=failed_fixture,
                recovery_of="run-primary",
            )
        )
        == 2
    )
    capsys.readouterr()
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-2",
                fixture=failed_fixture,
                recovery_of="run-primary-recovery-1",
            )
        )
        == 2
    )
    assert "cannot recover a fallback run" in capsys.readouterr().err


def test_terminal_error_recovery_allows_only_one_child_per_parent(
    tmp_path: Path, capsys: Any
) -> None:
    start = date(2026, 7, 1)
    failed_fixture = _target_error_firecrawl_fixture(
        tmp_path / "failed.jsonl", start=start, end=start
    )
    assert (
        main(_discovery_args(tmp_path, run_id="run-primary", fixture=failed_fixture))
        == 2
    )
    capsys.readouterr()
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-1",
                fixture=failed_fixture,
                recovery_of="run-primary",
            )
        )
        == 2
    )
    capsys.readouterr()
    assert (
        main(
            _discovery_args(
                tmp_path,
                run_id="run-primary-recovery-2",
                fixture=failed_fixture,
                recovery_of="run-primary",
            )
        )
        == 2
    )
    assert "recovery already exists" in capsys.readouterr().err


def _run_daily_batch(
    tmp_path: Path,
    *,
    batch_id: str,
    run_id: str,
    start: date,
    end: date,
) -> dict[str, object]:
    fixture = _empty_firecrawl_fixture(
        tmp_path / f"{run_id}.jsonl", start=start, end=end
    )
    output_root = tmp_path / batch_id
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(output_root),
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                batch_id,
                "--run-id",
                run_id,
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                start.isoformat(),
                "--search-window-end",
                end.isoformat(),
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )
    return json.loads(
        (output_root / "checkpoints" / f"{batch_id}-recap-summary.json").read_text()
    )


def test_daily_batches_share_cycle_hash_but_freeze_distinct_window_digests(
    tmp_path: Path,
) -> None:
    first = _run_daily_batch(
        tmp_path,
        batch_id="batch-day-1",
        run_id="run-day-1",
        start=date(2026, 7, 1),
        end=date(2026, 7, 2),
    )
    overlapping = _run_daily_batch(
        tmp_path,
        batch_id="batch-day-2",
        run_id="run-day-2",
        start=date(2026, 7, 2),
        end=date(2026, 7, 3),
    )

    assert first["cycle_hash"] == overlapping["cycle_hash"]
    assert first["batch_digest"] != overlapping["batch_digest"]
    assert overlapping["search_window_start"] == "2026-07-02"


def test_distinct_runs_namespace_default_raw_artifacts_by_run_id(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    cycle_store = tmp_path / "cycle.sqlite3"
    start = date(2026, 7, 1)
    fixture = _empty_firecrawl_fixture(
        tmp_path / "same-page.jsonl", start=start, end=start
    )

    for batch_id, run_id in (
        ("batch-first", "run-first"),
        ("batch-second", "run-second"),
    ):
        assert (
            main(
                [
                    "acquisition",
                    "discover-firecrawl-recap",
                    "--output-root",
                    str(output_root),
                    "--cycle-store",
                    str(cycle_store),
                    "--batch-id",
                    batch_id,
                    "--run-id",
                    run_id,
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--search-window-start",
                    start.isoformat(),
                    "--search-window-end",
                    start.isoformat(),
                    "--query-term",
                    "motion to dismiss",
                    "--firecrawl-fixture",
                    str(fixture),
                    "--execute",
                ]
            )
            == 0
        )

    first_artifacts = list(
        (output_root / "raw-recap-search-html" / "run-first").glob("*.html")
    )
    second_artifacts = list(
        (output_root / "raw-recap-search-html" / "run-second").glob("*.html")
    )
    assert len(first_artifacts) == 1
    assert len(second_artifacts) == 1
    assert first_artifacts[0].name == second_artifacts[0].name


def test_explicit_raw_artifact_directory_is_not_namespaced(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    explicit_dir = tmp_path / "operator-selected-raw"
    start = date(2026, 7, 1)
    fixture = _empty_firecrawl_fixture(
        tmp_path / "explicit.jsonl", start=start, end=start
    )

    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(output_root),
                "--batch-id",
                "batch-explicit",
                "--run-id",
                "run-explicit",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                start.isoformat(),
                "--search-window-end",
                start.isoformat(),
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--raw-search-html-dir",
                str(explicit_dir),
                "--execute",
            ]
        )
        == 0
    )

    assert len(list(explicit_dir.glob("*.html"))) == 1
    assert not (explicit_dir / "run-explicit").exists()


def test_resume_rejects_changed_raw_artifact_directory(
    tmp_path: Path, capsys: Any
) -> None:
    output_root = tmp_path / "output"
    cycle_store = tmp_path / "cycle.sqlite3"
    start = date(2026, 7, 1)
    fixture = _empty_firecrawl_fixture(
        tmp_path / "resume.jsonl", start=start, end=start
    )

    def run_with_raw_dir(raw_dir: Path) -> int:
        return main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(output_root),
                "--cycle-store",
                str(cycle_store),
                "--batch-id",
                "batch-resume",
                "--run-id",
                "run-resume",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                start.isoformat(),
                "--search-window-end",
                start.isoformat(),
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--raw-search-html-dir",
                str(raw_dir),
                "--execute",
                "--resume",
            ]
        )

    assert run_with_raw_dir(tmp_path / "raw-first") == 0
    assert run_with_raw_dir(tmp_path / "raw-second") == 2
    assert "Firecrawl run config mismatch" in capsys.readouterr().err


def test_discover_firecrawl_recap_rejects_search_start_before_anchor(
    tmp_path: Path, capsys: Any
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(tmp_path / "output"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "run-001",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-29",
                "--search-window-end",
                "2026-07-01",
                "--query-term",
                "motion to dismiss",
                "--live-firecrawl",
            ]
        )
        == 2
    )
    assert (
        "--search-window-start cannot precede --eligibility-anchor"
        in capsys.readouterr().err
    )


def test_discover_firecrawl_recap_resume_rejects_changed_window(
    tmp_path: Path, capsys: Any
) -> None:
    _run_daily_batch(
        tmp_path,
        batch_id="batch-001",
        run_id="run-001",
        start=date(2026, 7, 1),
        end=date(2026, 7, 1),
    )
    fixture = _empty_firecrawl_fixture(
        tmp_path / "changed.jsonl",
        start=date(2026, 7, 2),
        end=date(2026, 7, 2),
    )
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(tmp_path / "changed-output"),
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "run-001",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-02",
                "--search-window-end",
                "2026-07-02",
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--execute",
                "--resume",
            ]
        )
        == 2
    )
    assert "batch config mismatch" in capsys.readouterr().err


def test_discover_firecrawl_recap_resume_rejects_changed_query_plan(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    _run_daily_batch(
        tmp_path,
        batch_id="batch-001",
        run_id="run-001",
        start=date(2026, 7, 1),
        end=date(2026, 7, 1),
    )
    fixture = _empty_firecrawl_fixture(
        tmp_path / "same-window.jsonl",
        start=date(2026, 7, 1),
        end=date(2026, 7, 1),
    )
    monkeypatch.setattr(
        cli_module, "COURTLISTENER_QUERY_PLAN_VERSION", "phrase-precise-v2"
    )
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(tmp_path / "changed-output"),
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "run-001",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-01",
                "--search-window-end",
                "2026-07-01",
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--execute",
                "--resume",
            ]
        )
        == 2
    )
    assert "batch config mismatch" in capsys.readouterr().err
