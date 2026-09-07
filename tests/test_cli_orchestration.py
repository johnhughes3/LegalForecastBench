from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli import build_parser, main
from tests.test_static_result_sites import write_official_report_fixture


def test_cli_help_lists_only_supported_benchmark_commands() -> None:
    parser = build_parser()
    command_names: set[str] = set()
    for action in parser._actions:
        if action.dest != "command":
            continue
        choices = getattr(action, "choices", None)
        if isinstance(choices, Mapping):
            choice_map = cast(Mapping[object, object], choices)
            command_names = {name for name in choice_map if isinstance(name, str)}
        break

    for command in (
        "manifest",
        "release",
        "run",
        "score",
        "report",
        "study",
        "publish",
        "multiharness",
    ):
        assert command in command_names

    for retired in (
        "discover",
        "retrieve",
        "acquisition",
        "fixture",
        "freeze",
        "eval",
    ):
        assert retired not in command_names


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
