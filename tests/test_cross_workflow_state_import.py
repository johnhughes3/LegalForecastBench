from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import BinaryIO

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github/scripts/restore-forecast-state.py"
_spec = importlib.util.spec_from_file_location("restore_forecast_state", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
_restore = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_restore)


def test_artifact_download_streams_binary_cli_output_to_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"PK\x03\x04\x00\xff\x1b[0m"
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    def run(command: list[str], *, stdout: BinaryIO, check: bool) -> None:
        assert command == [
            "gh",
            "api",
            "--allow-escape-sequences",
            "/repos/owner/repo/actions/artifacts/17/zip",
        ]
        assert check
        stdout.write(payload)

    monkeypatch.setattr(_restore.subprocess, "run", run)
    destination = tmp_path / "state.zip"
    _restore._download_artifact(17, destination)
    assert destination.read_bytes() == payload


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


def _write_state_archive(
    root: Path,
    *,
    run_id: str,
    cell_id: str,
    status: str = "completed",
    summary_status: str | None = None,
    transcript: bytes | None = None,
    transcript_name: str | None = None,
    include_receipt: bool = True,
) -> Path:
    (root / "receipts").mkdir(parents=True)
    state = {
        "provider": "openai",
        "cell_id": cell_id,
        "run_id": run_id,
        "run_attempt": 1,
        "status": status,
    }
    files = [
        ("state.json", state),
        ("failure-summary.json", {"status": summary_status or status}),
        ("run-summary.json", {"status": summary_status or status}),
    ]
    if include_receipt:
        files.append(("receipts/receipt.json", {"cell_id": cell_id}))
    for name, value in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    (root / "ledger.sqlite3").write_bytes(b"ledger")
    if transcript is not None:
        transcript_path = root / "transcripts" / (transcript_name or f"{cell_id}.json")
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_bytes(transcript)
    if status != "completed":
        (root / "runner-failure.log").write_text("provider job failed\n")
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
        "RESUME_SOURCES": json.dumps([{"run_id": "34210437238", "run_attempt": 1}]),
        "LFB_RUN_ROOT": str(run_root),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "runner").mkdir()

    _restore.restore()

    restored = json.loads((run_root / "state.json").read_text())
    assert downloaded == [17]
    assert restored["restored_from_run_id"] == "999999999"


def test_source_failure_skips_to_next_explicit_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell_id = "cell"
    failed_archive = _write_state_archive(
        tmp_path / "failed", run_id="111", cell_id=cell_id, status="failed"
    )
    completed_archive = _write_state_archive(
        tmp_path / "completed", run_id="222", cell_id=cell_id
    )
    current_metadata = tmp_path / "current-artifacts.json"
    current_metadata.write_text(json.dumps([{"total_count": 0, "artifacts": []}]))
    source_metadata = {
        "111": {
            "id": 111,
            "run_attempt": 1,
            "path": ".github/workflows/run-benchmark.yaml",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "failure",
        },
        "222": {
            "id": 222,
            "run_attempt": 1,
            "path": ".github/workflows/run-benchmark.yaml",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        },
    }
    source_artifacts = {
        "111": {
            "total_count": 1,
            "artifacts": [
                {
                    "id": 31,
                    "name": "locked-run-state-openai-cell-attempt-1",
                    "created_at": "2026-09-08T00:00:00Z",
                }
            ],
        },
        "222": {
            "total_count": 1,
            "artifacts": [
                {
                    "id": 47,
                    "name": "locked-run-state-openai-cell-attempt-1",
                    "created_at": "2026-09-08T00:00:00Z",
                }
            ],
        },
    }
    archives = {31: failed_archive, 47: completed_archive}
    downloaded: list[int] = []

    def fake_api(endpoint: str, *, paginate: bool = False) -> object:
        del paginate
        for run_id in source_metadata:
            if f"/runs/{run_id}/attempts/1" in endpoint:
                return source_metadata[run_id]
            if f"/runs/{run_id}/artifacts?" in endpoint:
                return [source_artifacts[run_id]]
        raise AssertionError(f"unexpected metadata endpoint: {endpoint}")

    def fake_download(artifact_id: int, archive: Path) -> None:
        downloaded.append(artifact_id)
        shutil.copyfile(archives[artifact_id], archive)

    monkeypatch.setattr(_restore, "_api_json", fake_api)
    monkeypatch.setattr(_restore, "_download_artifact", fake_download)
    for name, value in {
        "PROVIDER": "openai",
        "CELL_ID": cell_id,
        "CELL_ID_SLUG": cell_id,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "333",
        "GITHUB_REPOSITORY": "owner/repo",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "METADATA_PATH": str(current_metadata),
        "RESUME_SOURCES": json.dumps(
            [
                {"run_id": "111", "run_attempt": 1},
                {"run_id": "222", "run_attempt": 1},
            ]
        ),
        "LFB_RUN_ROOT": str(tmp_path / "run"),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "runner").mkdir()
    (tmp_path / "run").mkdir()

    _restore.restore()

    restored = json.loads((tmp_path / "run" / "state.json").read_text())
    assert downloaded == [31, 47]
    assert restored["restored_from_run_id"] == "222"
    assert restored["restored_from_attempt"] == 1


def test_failed_source_with_saved_transcript_is_selected_for_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell_id = "cell"
    source_archive = _write_state_archive(
        tmp_path / "source",
        run_id="222",
        cell_id=cell_id,
        status="failed",
        transcript=b'{"agent_status":"succeeded"}\n',
        include_receipt=False,
    )
    current_metadata = tmp_path / "current-artifacts.json"
    current_metadata.write_text(json.dumps([{"total_count": 0, "artifacts": []}]))

    def fake_api(endpoint: str, *, paginate: bool = False) -> object:
        del paginate
        if endpoint.endswith("/runs/222/attempts/1"):
            return {
                "id": 222,
                "run_attempt": 1,
                "path": ".github/workflows/run-benchmark.yaml",
                "event": "workflow_dispatch",
                "head_branch": "main",
                "status": "completed",
                "conclusion": "failure",
            }
        if endpoint.endswith("/runs/222/artifacts?per_page=100"):
            return [
                {
                    "id": 47,
                    "name": "locked-run-state-openai-cell-attempt-1",
                    "created_at": "2026-09-08T00:00:00Z",
                }
            ]
        raise AssertionError(f"unexpected metadata endpoint: {endpoint}")

    def fake_download(artifact_id: int, archive: Path) -> None:
        assert artifact_id == 47
        shutil.copyfile(source_archive, archive)

    monkeypatch.setattr(_restore, "_api_json", fake_api)
    monkeypatch.setattr(_restore, "_download_artifact", fake_download)
    run_root = tmp_path / "run"
    for name, value in {
        "PROVIDER": "openai",
        "CELL_ID": cell_id,
        "CELL_ID_SLUG": cell_id,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "333",
        "GITHUB_REPOSITORY": "owner/repo",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "METADATA_PATH": str(current_metadata),
        "RESUME_SOURCES": json.dumps([{"run_id": "222", "run_attempt": 1}]),
        "LFB_RUN_ROOT": str(run_root),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "runner").mkdir()
    run_root.mkdir()

    _restore.restore()

    assert (run_root / "transcripts" / f"{cell_id}.json").read_bytes() == (
        b'{"agent_status":"succeeded"}\n'
    )
    assert json.loads((run_root / "state.json").read_text())["status"] == "restored"


def test_restored_failed_source_with_saved_transcript_is_selected_for_recovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    _write_state_archive(
        root,
        run_id="222",
        cell_id="cell",
        status="restored",
        summary_status="failed",
        transcript=b'{"agent_status":"succeeded"}\n',
        include_receipt=False,
    )

    _restore._validate_source_completed_state(root, "openai", "cell", "222", 1)


def test_restored_source_with_completed_summaries_uses_durable_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    _write_state_archive(
        root,
        run_id="222",
        cell_id="cell",
        status="restored",
        summary_status="completed",
    )

    _restore._validate_source_completed_state(root, "openai", "cell", "222", 1)


def test_failed_source_without_saved_transcript_remains_incomplete(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    _write_state_archive(
        root,
        run_id="222",
        cell_id="cell",
        status="failed",
        include_receipt=False,
    )
    with pytest.raises(_restore.IncompleteSourceState):
        _restore._validate_source_completed_state(root, "openai", "cell", "222", 1)


def test_failed_source_with_partial_transcript_remains_incomplete(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    _write_state_archive(
        root,
        run_id="222",
        cell_id="cell",
        status="failed",
        transcript=b'{"agent_status":"failed","messages":[]}',
        include_receipt=False,
    )
    with pytest.raises(_restore.IncompleteSourceState):
        _restore._validate_source_completed_state(root, "openai", "cell", "222", 1)


def test_resume_copies_optional_transcript_bytes_without_parsing_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell_id = "cell"
    transcript = b'{"messages":[{"kind":"tool-result","content":"docs"}]}\n'
    source_archive = _write_state_archive(
        tmp_path / "source",
        run_id="222",
        cell_id=cell_id,
        transcript=transcript,
    )
    current_metadata = tmp_path / "current-artifacts.json"
    current_metadata.write_text(json.dumps([{"total_count": 0, "artifacts": []}]))
    source_metadata = {
        "id": 222,
        "run_attempt": 1,
        "path": ".github/workflows/run-benchmark.yaml",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
    }

    def fake_api(endpoint: str, *, paginate: bool = False) -> object:
        del paginate
        if endpoint.endswith("/runs/222/attempts/1"):
            return source_metadata
        if endpoint.endswith("/runs/222/artifacts?per_page=100"):
            return [
                {
                    "id": 47,
                    "name": "locked-run-state-openai-cell-attempt-1",
                    "created_at": "2026-09-08T00:00:00Z",
                }
            ]
        raise AssertionError(f"unexpected metadata endpoint: {endpoint}")

    def fake_download(artifact_id: int, archive: Path) -> None:
        assert artifact_id == 47
        shutil.copyfile(source_archive, archive)

    monkeypatch.setattr(_restore, "_api_json", fake_api)
    monkeypatch.setattr(_restore, "_download_artifact", fake_download)
    run_root = tmp_path / "run"
    for name, value in {
        "PROVIDER": "openai",
        "CELL_ID": cell_id,
        "CELL_ID_SLUG": cell_id,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "333",
        "GITHUB_REPOSITORY": "owner/repo",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "METADATA_PATH": str(current_metadata),
        "RESUME_SOURCES": json.dumps([{"run_id": "222", "run_attempt": 1}]),
        "LFB_RUN_ROOT": str(run_root),
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "runner").mkdir()
    run_root.mkdir()

    _restore.restore()

    assert (run_root / "transcripts" / f"{cell_id}.json").read_bytes() == transcript
    assert list((run_root / "receipts").glob("*.json"))


def test_legacy_single_resume_source_pair_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESUME_SOURCES", raising=False)
    monkeypatch.setenv("RESUME_SOURCE_RUN_ID", "34210437238")
    monkeypatch.setenv("RESUME_SOURCE_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_RUN_ID", "34216851710")

    assert _restore._resume_sources() == [("34210437238", 1)]
