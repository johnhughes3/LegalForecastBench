"""Transport-contract tests for opaque artifact preservation, without live services."""

import json
import subprocess
from pathlib import Path
from typing import Any, cast

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
        if "rate_limit" in argv:
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"remaining": 1000, "reset": 9999999999})
            )
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
        "reports/github-artifacts/multi-ablation/owner/repo/by-run/42/same-name/1.json",
        "reports/github-artifacts/multi-ablation/owner/repo/by-run/42/same-name/3.json",
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
        if "rate_limit" in argv:
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"remaining": 1000, "reset": 9999999999})
            )
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


def test_split_phases_have_no_cross_service_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _transport(monkeypatch)
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "123-4", tmp_path, download_only=True
        )
        == 0
    )
    assert all(argv[0] == "gh" for argv, _ in calls)
    calls.clear()
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "123-4", tmp_path, upload_only=True
        )
        == 0
    )
    assert all(argv[0] == "bash" for argv, _ in calls)


def test_upload_rejects_different_phase_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _transport(monkeypatch)
    archive.archive_artifacts(
        "owner/repo", "test-bucket", "123-4", tmp_path, download_only=True
    )
    calls.clear()
    with pytest.raises(ValueError, match="identity mismatch"):
        archive.archive_artifacts(
            "owner/other", "test-bucket", "123-4", tmp_path, upload_only=True
        )
    assert calls == []


def test_quota_waits_until_reset_then_downloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _transport(monkeypatch)
    original_run = archive.subprocess.run
    quotas = iter(
        [
            {"remaining": 1000, "reset": 200},
            {"remaining": 10, "reset": 105},
            {"remaining": 11, "reset": 200},
            {"remaining": 100, "reset": 200},
        ]
    )
    sleeps: list[float] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rate_limit" in argv:
            return subprocess.CompletedProcess(argv, 0, json.dumps(next(quotas)))
        return cast(subprocess.CompletedProcess[str], original_run(argv, **kwargs))

    monkeypatch.setattr(archive.subprocess, "run", run)
    monkeypatch.setattr(archive.time, "time", lambda: 100)
    monkeypatch.setattr(archive.time, "monotonic", lambda: 100)
    monkeypatch.setattr(archive.time, "sleep", sleeps.append)
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "123-4", tmp_path, download_only=True
        )
        == 0
    )
    assert sleeps == [6]
    assert (tmp_path / "1.zip").exists() and (tmp_path / "3.zip").exists()


def test_invalid_reset_preserves_partial_state_for_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _transport(monkeypatch)
    original_run = archive.subprocess.run
    quotas = iter([1000, 0])

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rate_limit" in argv:
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"remaining": next(quotas), "reset": 10000})
            )
        return cast(subprocess.CompletedProcess[str], original_run(argv, **kwargs))

    monkeypatch.setattr(archive.subprocess, "run", run)
    monkeypatch.setattr(archive.time, "time", lambda: 100)
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "123-4", tmp_path, download_only=True
        )
        == 1
    )
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "123-4", tmp_path, upload_only=True
        )
        == 1
    )
    index = json.loads((tmp_path / "archive-index.json").read_text())
    assert index["failed_count"] == 2
    assert index["copied_count"] == 0


def test_source_run_scope_lists_one_run_and_writes_stable_pointers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _transport(monkeypatch)
    uploaded: dict[str, bytes] = {}

    def upload(bucket: str, source: Path, key: str) -> None:
        uploaded[key] = source.read_bytes()

    monkeypatch.setattr(archive, "_upload", upload)
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "9-1", tmp_path, source_run_id=42
        )
        == 0
    )
    listing = next(argv for argv, _ in calls if "--paginate" in argv)
    assert listing[-1] == "repos/owner/repo/actions/runs/42/artifacts?per_page=100"
    key = archive.pointer_key("owner/repo", 42, "same-name", 1)
    pointer = json.loads(uploaded[key])
    assert pointer["key"].endswith("artifacts/1.zip")
    assert pointer["source_run_id"] == 42
    first = uploaded[key]
    # A re-run must reproduce identical pointer bytes for the create-once helper.
    assert (
        archive.archive_artifacts(
            "owner/repo", "test-bucket", "9-2", tmp_path / "again", source_run_id=42
        )
        == 0
    )
    assert uploaded[key] == first
    index = json.loads(
        uploaded["reports/github-artifacts/multi-ablation/owner/repo/runs/9-1.json"]
    )
    assert index["source_run_id"] == 42


def test_digest_mismatch_fails_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _transport(monkeypatch)
    original = archive._snapshot  # pyright: ignore[reportPrivateUsage]

    def snapshot(
        repository: str, source_run_id: int | None = None
    ) -> list[dict[str, object]]:
        artifacts = original(repository, source_run_id)
        artifacts[0]["digest"] = "sha256:" + "0" * 64
        return artifacts

    monkeypatch.setattr(archive, "_snapshot", snapshot)

    def upload(bucket: str, source: Path, key: str) -> None:
        return None

    monkeypatch.setattr(archive, "_upload", upload)
    assert (
        archive.archive_artifacts("owner/repo", "test-bucket", "123-5", tmp_path) == 1
    )
    index = json.loads((tmp_path / "archive-index.json").read_text())
    assert index["results"][0]["error"] == "ValueError"
    assert index["results"][1]["status"] == "copied"


def test_s3_denial_is_printed_to_the_job_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            1, argv, stderr="An error occurred (AccessDenied) when calling PutObject"
        )

    monkeypatch.setattr(archive.subprocess, "run", run)
    source = tmp_path / "x.zip"
    source.write_bytes(b"zip")
    with pytest.raises(subprocess.CalledProcessError):
        archive._upload("test-bucket", source, "k")  # pyright: ignore[reportPrivateUsage]
    assert "AccessDenied" in capsys.readouterr().err
