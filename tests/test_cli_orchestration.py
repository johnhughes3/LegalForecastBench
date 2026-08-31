from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import build_parser, main
from tests.test_static_result_sites import write_official_report_fixture


def test_cli_help_lists_only_supported_benchmark_commands() -> None:
    help_text = build_parser().format_help()

    for command in (
        "manifest",
        "release",
        "run",
        "score",
        "report",
        "publish",
        "multiharness",
    ):
        assert command in help_text

    for retired in (
        "discover",
        "retrieve",
        "acquisition",
        "fixture",
        "freeze",
        "eval",
    ):
        assert retired not in help_text


def test_publish_aggregate_help_uses_current_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["publish", "aggregate", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "--model-registry",
        "--baseline-training-examples",
        "--allow-no-baselines",
        "--deferred-ablation",
        "--paired-delta-sd",
    ):
        assert expected in help_text


def test_publish_site_renders_official_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    output_dir = tmp_path / "site"

    assert (
        main(
            [
                "publish",
                "site",
                "--official-artifacts-dir",
                str(official_dir),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert Path(summary["index"]).is_file()
    assert Path(summary["artifact_index"]).is_file()
