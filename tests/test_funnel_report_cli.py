from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legalforecast.cli import main


def test_funnel_report_cli_writes_reconciled_artifact(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    exclusions = tmp_path / "exclusions.jsonl"
    public = tmp_path / "public.json"
    output = tmp_path / "funnel.json"
    _write_json(
        discovery,
        {
            "processed_candidate_count": 2,
            "accepted_case_count": 1,
            "excluded_case_count": 1,
            "per_term": {
                "term": {
                    "request_count": 1,
                    "candidate_count": 2,
                    "terminal_status": "exhausted",
                }
            },
        },
    )
    exclusions.write_text(
        json.dumps(
            {
                "candidate_id": "candidate-1",
                "stage": "eligibility",
                "primary_exclusion_reason": "no_mtd",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        public,
        {
            "target_clean_cases": 25,
            "screened_case_count": 1,
            "planned_case_count": 1,
            "selected_case_count": 1,
        },
    )

    assert (
        main(
            [
                "acquisition",
                "funnel-report",
                "--discovery-summary",
                str(discovery),
                "--exclusions",
                str(exclusions),
                "--public-download-summary",
                str(public),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["funnel"]["strict_clean"] == 1
    assert report["plan_public_downloads_target"]["bound"] is False


def test_funnel_report_cli_fails_loudly_when_default_limit_bound(
    tmp_path: Path, capsys: Any
) -> None:
    discovery = tmp_path / "discovery.json"
    exclusions = tmp_path / "exclusions.jsonl"
    public = tmp_path / "public.json"
    _write_json(
        discovery,
        {
            "processed_candidate_count": 30,
            "accepted_case_count": 30,
            "excluded_case_count": 0,
            "per_term": {
                "term": {
                    "request_count": 1,
                    "candidate_count": 30,
                    "terminal_status": "exhausted",
                }
            },
        },
    )
    exclusions.write_text("", encoding="utf-8")
    _write_json(
        public,
        {
            "target_clean_cases": 25,
            "screened_case_count": 30,
            "planned_case_count": 25,
            "selected_case_count": 25,
        },
    )

    assert (
        main(
            [
                "acquisition",
                "funnel-report",
                "--discovery-summary",
                str(discovery),
                "--exclusions",
                str(exclusions),
                "--public-download-summary",
                str(public),
                "--output",
                str(tmp_path / "funnel.json"),
            ]
        )
        == 2
    )
    assert "target-clean-cases bound" in capsys.readouterr().err


def test_funnel_report_cli_accepts_canonical_firecrawl_artifacts(
    tmp_path: Path,
) -> None:
    screening = tmp_path / "screening.json"
    recap = tmp_path / "recap.json"
    exclusions = tmp_path / "exclusions.jsonl"
    public = tmp_path / "public.json"
    output = tmp_path / "funnel.json"
    _write_json(
        screening,
        {
            "schema_version": "legalforecast.firecrawl_screening_summary.v1",
            "cycle_hash": "cycle-1",
            "input_success_count": 1,
            "input_fetch_exclusion_count": 0,
            "accepted_case_count": 1,
            "excluded_case_count": 0,
            "reconciled": True,
            "snapshot_complete": True,
            "snapshot_saturated": True,
            "dry_run": False,
        },
    )
    _write_json(
        recap,
        {
            "schema_version": "legalforecast.recap_partial_checkpoint_summary.v1",
            "cycle_hash": "cycle-1",
            "terms": ["motion to dismiss"],
            "acquired_page_count": 100,
            "potential_candidate_count": 976,
            "checkpoint_only": True,
            "complete": False,
            "provider_completeness_status": "unproven",
        },
    )
    exclusions.write_text("", encoding="utf-8")
    _write_json(
        public,
        {
            "target_clean_cases": 150,
            "screened_case_count": 1,
            "planned_case_count": 1,
        },
    )

    assert (
        main(
            [
                "acquisition",
                "funnel-report",
                "--firecrawl-screening-summary",
                str(screening),
                "--recap-discovery-summary",
                str(recap),
                "--exclusions",
                str(exclusions),
                "--public-download-summary",
                str(public),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["source_mode"] == "canonical_firecrawl"


def test_funnel_report_cli_requires_recap_summary_in_firecrawl_mode(
    tmp_path: Path, capsys: Any
) -> None:
    screening = tmp_path / "screening.json"
    exclusions = tmp_path / "exclusions.jsonl"
    public = tmp_path / "public.json"
    _write_json(screening, {})
    exclusions.write_text("", encoding="utf-8")
    _write_json(public, {})

    assert (
        main(
            [
                "acquisition",
                "funnel-report",
                "--firecrawl-screening-summary",
                str(screening),
                "--exclusions",
                str(exclusions),
                "--public-download-summary",
                str(public),
                "--output",
                str(tmp_path / "funnel.json"),
            ]
        )
        == 2
    )
    assert "--recap-discovery-summary is required" in capsys.readouterr().err


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.write_text(json.dumps(record), encoding="utf-8")
