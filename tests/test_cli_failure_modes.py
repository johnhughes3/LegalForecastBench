from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.cli import main


def test_missing_input_file_reports_concise_cli_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_path = tmp_path / "missing-docket-entries.jsonl"

    exit_code = main(
        [
            "discover",
            "--input",
            str(missing_path),
            "--output",
            str(tmp_path / "candidates.jsonl"),
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().err == f"legalforecast: missing file: {missing_path}\n"


def test_live_retrieve_fails_closed_without_fixture_or_live(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text("", encoding="utf-8")

    exit_code = main(
        [
            "retrieve",
            "--candidates",
            str(candidates_path),
            "--output",
            str(tmp_path / "retrievals.jsonl"),
        ]
    )

    assert exit_code == 2
    assert (
        "retrieve requires --case-dev-fixture for offline runs or --live "
        "with CASE_DEV_API_KEY configured"
    ) in capsys.readouterr().err


def test_case_dev_smoke_dry_run_never_requires_live_credentials(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "smoke.md"

    assert (
        main(
            [
                "case-dev-smoke",
                "--output",
                str(output_path),
                "--dry-run",
            ]
        )
        == 0
    )

    report = output_path.read_text(encoding="utf-8")
    assert "Phase 0 case.dev Smoke Report" in report
    assert "No live or fixture requests were executed" in report
