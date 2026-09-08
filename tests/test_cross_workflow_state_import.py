from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github/scripts/restore-forecast-state.py"
_spec = importlib.util.spec_from_file_location("restore_forecast_state", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
_restore = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_restore)


def test_extract_artifacts_accepts_github_paginated_object_response(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "artifacts.json"
    artifact = {"id": 17, "name": "state", "created_at": "2026-09-08T00:00:00Z"}
    metadata.write_text(json.dumps([{"total_count": 1, "artifacts": [artifact]}]))

    assert _restore._extract_artifacts(metadata) == [artifact]


def test_extract_artifacts_accepts_flat_page_response(tmp_path: Path) -> None:
    metadata = tmp_path / "artifacts.json"
    artifact = {"id": 17, "name": "state", "created_at": "2026-09-08T00:00:00Z"}
    metadata.write_text(json.dumps([artifact]))

    assert _restore._extract_artifacts(metadata) == [artifact]


def test_source_identity_requires_the_canceled_benchmark_attempt() -> None:
    source = {
        "id": 34210437238,
        "run_attempt": 1,
        "path": ".github/workflows/run-benchmark.yaml",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "cancelled",
    }

    _restore._source_identity(source, "34210437238", 1)

    _restore._source_identity({**source, "conclusion": "success"}, "34210437238", 1)

    with pytest.raises(ValueError, match="terminal"):
        _restore._source_identity({**source, "status": "in_progress"}, "34210437238", 1)


def test_source_state_with_failure_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "state"
    (root / "receipts").mkdir(parents=True)
    state = {
        "provider": "openai",
        "cell_id": "cell",
        "run_id": "34210437238",
        "run_attempt": 1,
        "status": "failed",
    }
    (root / "state.json").write_text(json.dumps(state))
    with pytest.raises(_restore.IncompleteSourceState):
        _restore._validate_source_completed_state(
            root, "openai", "cell", "34210437238", 1
        )


def _write_state_archive(root: Path, *, run_id: str, cell_id: str) -> Path:
    (root / "receipts").mkdir(parents=True)
    state = {
        "provider": "openai",
        "cell_id": cell_id,
        "run_id": run_id,
        "run_attempt": 1,
        "status": "completed",
    }
    for name, value in (
        ("state.json", state),
        ("failure-summary.json", {"status": "completed"}),
        ("run-summary.json", {"status": "completed"}),
        ("receipts/receipt.json", {"cell_id": cell_id}),
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    (root / "ledger.sqlite3").write_bytes(b"ledger")
    archive = root.with_suffix(".zip")
    with _restore.zipfile.ZipFile(archive, "w") as bundle:
        for path in root.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(root).as_posix())
    return archive


def test_current_run_attempt_wins_over_external_source_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell_id = "cell"
    current_archive = _write_state_archive(
        tmp_path / "current", run_id="999999999", cell_id=cell_id
    )
    source_archive = _write_state_archive(
        tmp_path / "source", run_id="34210437238", cell_id=cell_id
    )
    current_metadata = tmp_path / "current-artifacts.json"
    current_metadata.write_text(
        json.dumps(
            [
                {
                    "artifacts": [
                        {
                            "id": 17,
                            "name": "locked-run-state-openai-cell-attempt-1",
                            "created_at": "2026-09-08T00:00:00Z",
                        }
                    ]
                }
            ]
        )
    )
    source_metadata = tmp_path / "source-artifacts.json"
    source_metadata.write_text(
        json.dumps(
            [
                {
                    "artifacts": [
                        {
                            "id": 23,
                            "name": "locked-run-state-openai-cell-attempt-1",
                            "created_at": "2026-09-08T00:00:00Z",
                        }
                    ]
                }
            ]
        )
    )
    source_run = tmp_path / "source-run.json"
    source_run.write_text(
        json.dumps(
            {
                "id": 34210437238,
                "run_attempt": 1,
                "path": ".github/workflows/run-benchmark.yaml",
                "event": "workflow_dispatch",
                "head_branch": "main",
                "status": "completed",
                "conclusion": "cancelled",
            }
        )
    )
    run_root = tmp_path / "run"
    (run_root / "receipts").mkdir(parents=True)
    (run_root / "state.json").write_text(json.dumps({"status": "initialized"}))
    (run_root / "failure-summary.json").write_text("{}")
    archives = {17: current_archive, 23: source_archive}
    downloaded: list[int] = []

    def fake_download(artifact_id: int, archive: Path) -> None:
        downloaded.append(artifact_id)
        shutil.copyfile(archives[artifact_id], archive)

    monkeypatch.setattr(_restore, "_download_artifact", fake_download)
    for name, value in {
        "PROVIDER": "openai",
        "CELL_ID": cell_id,
        "CELL_ID_SLUG": cell_id,
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_RUN_ID": "999999999",
        "GITHUB_REPOSITORY": "owner/repo",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "METADATA_PATH": str(current_metadata),
        "SOURCE_METADATA_PATH": str(source_metadata),
        "SOURCE_RUN_METADATA_PATH": str(source_run),
        "RESUME_SOURCE_RUN_ID": "34210437238",
        "RESUME_SOURCE_RUN_ATTEMPT": "1",
        "LFB_RUN_ROOT": str(run_root),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "runner").mkdir()

    _restore.restore()

    restored = json.loads((run_root / "state.json").read_text())
    assert downloaded == [17]
    assert restored["restored_from_run_id"] == "999999999"
