"""Archive fallback tests use saved ZIP bytes; they do not establish S3 coverage."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path
from zipfile import ZipFile

import pytest
from legalforecast import artifact_restore as restore
from legalforecast.artifact_archive import pointer_key
from legalforecast.runner.recovery_client import GhRecoveryClient, RecoveryError

REPO = "owner/bench"
RUN = 123
NAME = "locked-forecast-inputs-123-attempt-1"
ARTIFACT = 456
BUCKET = "results-bucket"


def _zip() -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as bundle:
        bundle.writestr("run-manifest.json", b"{}")
    return output.getvalue()


def _archive(
    monkeypatch: pytest.MonkeyPatch, *, corrupt: bool = False, duplicate: bool = False
) -> bytes:
    payload = _zip()
    key = pointer_key(REPO, RUN, NAME, ARTIFACT)
    object_key = (
        f"reports/github-artifacts/multi-ablation/{REPO}/artifacts/{ARTIFACT}.zip"
    )
    pointer: dict[str, object] = {
        "repository": REPO,
        "source_run_id": RUN,
        "name": NAME,
        "artifact_id": ARTIFACT,
        "key": object_key,
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
    }

    def command(arguments: list[str]) -> object:
        if arguments[0] == "gh":
            values: list[object] = []
            return [{"artifacts": values}]
        contents = [{"Key": key}]
        if duplicate:
            contents.append({"Key": key})
        return {"Contents": contents}

    def get_object(bucket: str, requested_key: str) -> bytes:
        assert bucket == BUCKET
        if requested_key == key:
            return json.dumps(pointer).encode()
        assert requested_key == object_key
        return b"corrupt" if corrupt else payload

    monkeypatch.setattr(restore, "_json_command", command)
    monkeypatch.setattr(restore, "_get_s3", get_object)
    return payload


def test_expired_and_omitted_artifact_restores_exact_saved_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _archive(monkeypatch)
    assert (
        restore.restore_artifact(REPO, RUN, NAME, artifact_id=ARTIFACT, bucket=BUCKET)
        == payload
    )
    assert (
        restore.restore_artifact(REPO, RUN, None, artifact_id=ARTIFACT, bucket=BUCKET)
        == payload
    )


@pytest.mark.parametrize("corrupt,duplicate", [(True, False), (False, True)])
def test_archive_refuses_corrupt_bytes_and_ambiguous_pointers(
    monkeypatch: pytest.MonkeyPatch, corrupt: bool, duplicate: bool
) -> None:
    _archive(monkeypatch, corrupt=corrupt, duplicate=duplicate)
    with pytest.raises(
        ValueError, match=r"digest mismatch|expected one archive pointer"
    ):
        restore.restore_artifact(REPO, RUN, NAME, bucket=BUCKET)


def test_archive_refuses_wrong_exact_artifact_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _archive(monkeypatch)
    with pytest.raises(ValueError, match="found 0"):
        restore.restore_artifact(REPO, RUN, NAME, artifact_id=999, bucket=BUCKET)


def test_local_restore_requires_explicit_archive_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def empty_listing(arguments: list[str]) -> object:
        values: list[object] = []
        return [{"artifacts": values}]

    monkeypatch.setattr(restore, "_json_command", empty_listing)
    with pytest.raises(ValueError, match="protected archive bucket"):
        restore.restore_artifact(REPO, RUN, NAME)


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    output = io.BytesIO()
    with ZipFile(output, "w") as bundle:
        bundle.writestr("../escape", b"bad")
    with pytest.raises(ValueError, match="unsafe"):
        restore.extract_artifact(output.getvalue(), tmp_path / "out")
    assert not (tmp_path / "escape").exists()


def test_protected_recovery_uses_verified_cache_even_after_github_omits_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _archive(monkeypatch)
    cache = tmp_path / "cache"
    restore.materialize_recovery_cache(REPO, RUN, BUCKET, cache)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("LFB_RECOVERY_ARCHIVE_DIR", str(cache))
    client = GhRecoveryClient()

    def empty_pages(endpoint: str) -> tuple[Mapping[str, object], ...]:
        values: list[object] = []
        return ({"artifacts": values},)

    monkeypatch.setattr(client, "_json_pages", empty_pages)
    assert client.list_artifacts(REPO, RUN)[0]["id"] == ARTIFACT
    assert client.list_artifacts(REPO, RUN)[0]["id"] == ARTIFACT
    assert client.download_artifact(REPO, ARTIFACT) == payload
    (cache / f"{ARTIFACT}.zip").write_bytes(b"changed")
    with pytest.raises(RecoveryError, match="digest mismatch"):
        client.download_artifact(REPO, ARTIFACT)


def test_local_recovery_does_not_inherit_operator_archive_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("LFB_RECOVERY_ARCHIVE_DIR", str(tmp_path))
    assert GhRecoveryClient().archive_dir is None


def test_restore_jobs_use_existing_fanin_environment_and_no_provider_credentials() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    for filename, job, next_job in (
        ("recover-benchmark.yaml", "restore-archive:", "recover:"),
        ("prepare-jev-summaries.yaml", "restore-inputs:", "prepare:"),
    ):
        workflow = (root / ".github/workflows" / filename).read_text()
        section = workflow.split(f"  {job}", 1)[1].split(f"  {next_job}", 1)[0]
        assert "environment: legalforecastbench-official-eval-fan-in" in section
        assert "legalforecast.artifact_restore" in section
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in section
        assert "retention-days: 1" in section
        assert "infisical" not in section.lower()
