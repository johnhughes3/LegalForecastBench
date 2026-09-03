"""The zero-credential LFB fixture path from issue-fixture to a completed run.

GitHub #1051: the community guide indexed the synthetic forecast-release and
then ran the bundled fixture adapter, but every row failed because the command
adapter could not consume authenticated solver input. These tests walk the
documented commands so that path cannot rot back apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from legalforecast.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ADAPTER_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "adapters"
    / "openai-responses"
    / "fixture-adapter-manifest.json"
)


def test_issue_fixture_indexes_and_runs_with_bundled_fixture_adapter(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixture-run"
    index_path = tmp_path / "lfb-index.json"
    solver_root = tmp_path / "lfb-solver-input"
    run_dir = tmp_path / "run"

    assert main(["run", "issue-fixture", "--output-dir", str(fixture_dir)]) == 0
    release_root = fixture_dir / "release"
    assert (release_root / "forecast-release.json").is_file()

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "lfb",
                "--forecast-release",
                str(release_root / "forecast-release.json"),
                "--artifact-root",
                str(release_root),
                "--solver-input-root",
                str(solver_root),
                "--output",
                str(index_path),
            ]
        )
        == 0
    )
    index_record = _read_json(index_path)
    tasks = cast(list[dict[str, Any]], index_record["tasks"])
    assert len(tasks) == 3
    assert all(
        task["metadata"]["release_schema_version"]
        == "legalforecast.forecast-release.v1"
        for task in tasks
    )

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(index_path),
                "--solver-input-root",
                str(solver_root),
                "--adapter-manifest",
                str(FIXTURE_ADAPTER_MANIFEST),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(run_dir),
                "--run-id",
                "fixture-walkthrough",
            ]
        )
        == 0
    )
    rows = [
        json.loads(line)
        for line in (run_dir / "canonical-runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    assert len(rows) == 3
    assert {row["status"] for row in rows} == {"succeeded"}
    receipts = [
        json.loads(line)
        for line in (run_dir / "release-harness-receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    assert len(receipts) == 3
    assert {receipt["harness_track"] for receipt in receipts} == {"neutral"}
    assert all(receipt["result"]["parser_output"]["is_valid"] for receipt in receipts)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
