from __future__ import annotations

import shutil
import sys
import threading
import time
import types
from pathlib import Path

import pytest
from legalforecast.release import ForecastRelease, issue_synthetic_release

from test_locked_manifest_workflow import prepare_inline_script


class _FakeS3Body:
    def __init__(self, payload: bytes, client: _FakeS3Client) -> None:
        self._payload = payload
        self._client = client

    def read(self) -> bytes:
        with self._client.lock:
            self._client.active_reads += 1
            self._client.max_active_reads = max(
                self._client.max_active_reads, self._client.active_reads
            )
        try:
            time.sleep(0.005)
            return self._payload
        finally:
            with self._client.lock:
                self._client.active_reads -= 1

    def close(self) -> None:
        with self._client.lock:
            self._client.closed_bodies += 1


class _FakeS3Client:
    def __init__(self, source_root: Path, corrupt_relative: str | None) -> None:
        self._source_root = source_root
        self._corrupt_relative = corrupt_relative
        self.lock = threading.Lock()
        self.active_reads = 0
        self.max_active_reads = 0
        self.closed_bodies = 0
        self.requested_keys: list[tuple[str, str]] = []

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, _FakeS3Body]:
        relative = Key.removeprefix("prefix/")
        payload = (
            b"corrupted declared artifact\n"
            if relative == self._corrupt_relative
            else (self._source_root / relative).read_bytes()
        )
        with self.lock:
            self.requested_keys.append((Bucket, Key))
        return {"Body": _FakeS3Body(payload, self)}


def _run_prepare_inline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_name: str,
    corrupt_relative: str | None,
) -> tuple[Path, _FakeS3Client, set[str]]:
    source_root = tmp_path / run_name / "source"
    issue_synthetic_release(source_root)
    release = ForecastRelease.model_validate_json(
        (source_root / "forecast-release.json").read_bytes()
    )
    declared = {
        *(document.path for case in release.cases for document in case.documents),
        *(unit.packet_path for unit in release.prediction_units),
        *(unit.prompt_path for unit in release.prediction_units),
    }
    locked_root = tmp_path / run_name / "locked"
    (locked_root / "artifacts").mkdir(parents=True)
    shutil.copyfile(
        source_root / "forecast-release.json", locked_root / "forecast-release.json"
    )
    client = _FakeS3Client(source_root, corrupt_relative)
    fake_boto3 = types.ModuleType("boto3")

    def client_factory(service: str) -> _FakeS3Client:
        assert service == "s3"
        return client

    fake_boto3.__dict__["client"] = client_factory
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("LFB_ARTIFACT_ROOT_URI", "s3://bucket/prefix")
    rendered = prepare_inline_script().replace(
        'Path("/tmp/lfb-locked-inputs")', f"Path({str(locked_root)!r})"
    )
    exec(compile(rendered, "run-benchmark-prepare", "exec"), {})
    return locked_root, client, declared


def test_prepare_s3_downloader_reuses_client_and_refuses_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked_root, client, declared = _run_prepare_inline(
        tmp_path, monkeypatch, run_name="success", corrupt_relative=None
    )
    assert client.max_active_reads > 1
    assert len(client.requested_keys) == len(declared)
    assert client.closed_bodies == len(client.requested_keys)
    assert {key.removeprefix("prefix/") for _, key in client.requested_keys} == declared
    actual = {
        path.relative_to(locked_root / "artifacts").as_posix()
        for path in (locked_root / "artifacts").rglob("*")
        if path.is_file()
    }
    assert actual == declared

    with pytest.raises(SystemExit, match="declared artifact commitment mismatch"):
        _run_prepare_inline(
            tmp_path,
            monkeypatch,
            run_name="corrupt",
            corrupt_relative=sorted(declared)[0],
        )
