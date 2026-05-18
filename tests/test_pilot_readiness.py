from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.reporting.pilot_readiness import (
    build_pilot_readiness_report,
    inspect_fixture_workflow,
    parse_case_dev_smoke_markdown,
    render_pilot_readiness_markdown,
)


def test_pilot_readiness_parses_blocked_case_dev_smoke_report() -> None:
    metrics = parse_case_dev_smoke_markdown(_blocked_smoke_report())

    assert metrics.total_hit_count == 144
    assert metrics.unique_candidate_count == 82
    assert metrics.clean_mtd_candidate_count == 0
    assert metrics.retrieval_attempt_count == 10
    assert metrics.docket_entry_listing_unavailable_count == 10
    assert metrics.request_count == 42


def test_pilot_readiness_rendering_keeps_failed_live_pilot_truthful(
    tmp_path: Path,
) -> None:
    fixture_dir = _fixture_output_dir(tmp_path)
    report = build_pilot_readiness_report(
        _blocked_smoke_report(),
        fixture_output_dir=fixture_dir,
        generated_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )

    markdown = render_pilot_readiness_markdown(report)

    assert "| Live clean packets produced | 0 |" in markdown
    assert "| Fixture E2E artifact path | passed |" in markdown
    assert "`docket_entry_listing_unavailable`" in markdown
    assert "not a key-permission problem" in markdown
    assert "not a required CourtListener dependency" in markdown
    assert "case.dev retrieval/export pilot" in markdown
    assert "Do not infer district, NOS, judge" in markdown


def test_pilot_readiness_reports_missing_fixture_artifacts(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "preregistration-validation.json").write_text(
        json.dumps({"passed": True}),
        encoding="utf-8",
    )

    status = inspect_fixture_workflow(fixture_dir)

    assert status.status == "missing"
    assert "candidate-manifest.jsonl" in status.missing_artifacts
    assert status.validation_passed is True


def test_pilot_readiness_rejects_missing_smoke_metrics() -> None:
    with pytest.raises(ValueError, match="smoke report"):
        parse_case_dev_smoke_markdown("# empty\n")


def _fixture_output_dir(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    for relative_path in (
        "candidate-manifest.jsonl",
        "packets.jsonl",
        "runs.jsonl",
    ):
        (fixture_dir / relative_path).write_text("", encoding="utf-8")
    for relative_path in (
        "scores.json",
        "report/leaderboard.json",
    ):
        path = fixture_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    (fixture_dir / "preregistration-validation.json").write_text(
        json.dumps({"passed": True}),
        encoding="utf-8",
    )
    (fixture_dir / "artifact-index.json").write_text(
        json.dumps({"artifact_count": 7}),
        encoding="utf-8",
    )
    return fixture_dir


def _blocked_smoke_report() -> str:
    return """# Phase 0 case.dev Smoke Report

## Run Configuration

- Generated at: 2026-05-14T19:05:37.526562Z

## Candidate Yield

- Total hit count: 144
- Unique candidate cases: 82
- Retrieved candidate cases: 0
- Clean MTD candidates: 0

## Missing Document Reasons

- docket_entry_listing_unavailable: 10

## Request And Cost Counts

- case.dev request count: 42
- Estimated case.dev cost: not configured

## Candidate Ledger

| Candidate ID | Case ID | Clean proxy | Missing reasons | Retrieval error |
| --- | --- | --- | --- | --- |
| case-dev-smoke-1 | 1 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-2 | 2 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-3 | 3 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-4 | 4 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-5 | 5 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-6 | 6 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-7 | 7 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-8 | 8 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-9 | 9 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-10 | 10 | no | docket_entry_listing_unavailable | unavailable |
"""
