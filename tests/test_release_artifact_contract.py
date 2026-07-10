from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from legalforecast.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_e2e_artifact_index_is_release_safe(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture-run"

    assert main(["fixture", "e2e", "--output-dir", str(output_dir)]) == 0

    manifest = _read_json(output_dir / "artifact-manifest.json")
    index = _read_json(output_dir / "artifact-index.json")

    manifest_paths = _string_set(manifest["artifacts"])
    artifact_records = _record_list(index["artifacts"])
    indexed_paths = {str(record["path"]) for record in artifact_records}

    assert index["artifact_count"] == len(artifact_records)
    assert "artifact-index.json" in manifest_paths
    assert "artifact-index.json" not in indexed_paths
    assert indexed_paths.issubset(manifest_paths)
    assert {
        "candidate-manifest.jsonl",
        "manifests/cycle_fixture_e2e.freeze.json",
        "report/leaderboard.json",
        "report/leaderboard.md",
    } <= indexed_paths

    categories = {str(record["category"]) for record in artifact_records}
    assert {
        "diagnostics",
        "evaluation",
        "freeze_bundle",
        "leaderboard_report",
        "manifest",
        "workflow",
    } <= categories

    for record in artifact_records:
        relative_path = Path(str(record["path"]))
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts

        artifact_path = output_dir / relative_path
        assert artifact_path.is_file()
        assert record["size_bytes"] == artifact_path.stat().st_size
        assert record["sha256"] == _sha256_file(artifact_path)


def _read_json(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return record


def _record_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError("artifact index must contain a list of objects")
    return value


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssertionError("artifact manifest must contain a list of strings")
    return set(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
