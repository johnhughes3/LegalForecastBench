"""Transport-contract tests for opaque artifact preservation, without live services."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from legalforecast import artifact_archive as archive


def _artifact(identifier: int, expired: bool = False) -> dict[str, object]:
    return {
        "id": identifier,
        "name": "same-name",
        "expired": expired,
        "workflow_run": {"id": 42},
    }


def _transport(
    monkeypatch: pytest.MonkeyPatch, fail: int | None = None
) -> list[tuple[list[str], dict[str, Any]]]:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if "--paginate" in argv:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    [
                        {
                            "total_count": 3,
                            "artifacts": [_artifact(1), _artifact(2, expired=True)],
                        },
                        {"total_count": 3, "artifacts": [_artifact(3)]},
                    ]
                ),
            )
        if argv[0] == "gh":
            if argv[-1].endswith(f"/{fail}/zip"):
                raise subprocess.CalledProcessError(
                    410, argv, stderr=b"artifact unavailable"
                )
            kwargs["stdout"].write(b"opaque-zip-bytes")
        return subprocess.CompletedProcess(argv, 0, "")

    monkeypatch.setattr(archive.subprocess, "run", run)
    return calls


def test_all_pages_distinct_ids_and_expiration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _transport(monkeypatch)
    assert (
        archive.archive_artifacts("owner/repo", "test-bucket", "123-1", tmp_path) == 0
    )
    index = json.loads((tmp_path / "archive-index.json").read_text())
    assert index["listed_count"] == 3
    assert index["available_count"] == index["copied_count"] == 2
    assert index["skipped_expired_count"] == 1
    assert [r["artifact"]["id"] for r in index["results"]] == [1, 3]
    assert index["status"] == "complete"
    uploads = [argv for argv, _ in calls if argv[0] == "bash"]
    assert uploads[0][-1].endswith("runs/123-1-snapshot.json")
    assert {argv[-1] for argv in uploads[1:-1]} == {
        "reports/github-artifacts/multi-ablation/owner/repo/artifacts/1.zip",
        "reports/github-artifacts/multi-ablation/owner/repo/artifacts/3.zip",
    }
    assert uploads[-1][-1].endswith("runs/123-1.json")
    assert all("timeout" in kwargs for _, kwargs in calls)
    assert all(argv[0] in {"gh", "bash"} for argv, _ in calls)
    assert (tmp_path / "1.zip").read_bytes() == b"opaque-zip-bytes"
    assert not (tmp_path / "2.zip").exists()


def test_failure_continues_and_records_partial_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _transport(monkeypatch, fail=1)
    assert (
        archive.archive_artifacts("owner/repo", "test-bucket", "123-2", tmp_path) == 1
    )
    index = json.loads((tmp_path / "archive-index.json").read_text())
    assert index["status"] == "partial"
    assert index["failed_count"] == index["copied_count"] == 1
    assert index["results"][0]["status"] == "failed"
    assert index["results"][0]["error"] == "command exited 410"
    assert index["results"][1]["status"] == "copied"
    assert calls[-1][0][-1].endswith("runs/123-2.json")


@pytest.mark.parametrize(
    ("repository", "bucket", "archive_id", "workers"),
    [
        ("../repo", "test-bucket", "1-1", 4),
        ("owner/repo;cmd", "test-bucket", "1-1", 4),
        ("owner/repo", "--bucket", "1-1", 4),
        ("owner/repo", "test-bucket", "../bad", 4),
        ("owner/repo", "test-bucket", "1-1", 9),
    ],
)
def test_invalid_inputs_fail_before_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    repository: str,
    bucket: str,
    archive_id: str,
    workers: int,
) -> None:
    calls = _transport(monkeypatch)
    with pytest.raises(ValueError):
        archive.archive_artifacts(repository, bucket, archive_id, tmp_path, workers)
    assert calls == []


@pytest.mark.parametrize(
    "pages",
    [
        [{"total_count": 2, "artifacts": [_artifact(1)]}],
        [
            {"total_count": 2, "artifacts": [_artifact(1)]},
            {"total_count": 3, "artifacts": [_artifact(3)]},
        ],
        [{"total_count": 2, "artifacts": [_artifact(1), _artifact(1)]}],
    ],
)
def test_incomplete_or_unstable_census_is_rejected(
    monkeypatch: pytest.MonkeyPatch, pages: list[dict[str, object]], tmp_path: Path
) -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, json.dumps(pages))

    monkeypatch.setattr(archive.subprocess, "run", run)
    with pytest.raises(ValueError):
        archive.archive_artifacts("owner/repo", "test-bucket", "123-1", tmp_path)


def test_upload_failure_is_partial_and_snapshot_has_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _transport(monkeypatch)
    uploaded: dict[str, bytes] = {}

    def upload(bucket: str, source: Path, key: str) -> None:
        if key.endswith("artifacts/1.zip"):
            raise subprocess.CalledProcessError(1, ["bash"], stderr="secret-signed-url")
        uploaded[key] = source.read_bytes()

    monkeypatch.setattr(archive, "_upload", upload)
    assert (
        archive.archive_artifacts("owner/repo", "test-bucket", "123-3", tmp_path) == 1
    )
    prefix = "reports/github-artifacts/multi-ablation/owner/repo/"
    snapshot = json.loads(uploaded[prefix + "runs/123-3-snapshot.json"])
    assert [item["id"] for item in snapshot["available"]] == [1, 3]
    final = uploaded[prefix + "runs/123-3.json"]
    assert b"secret-signed-url" not in final
    assert json.loads(final)["copied_count"] == 1
