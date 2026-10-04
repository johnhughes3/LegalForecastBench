"""Provider-free behavior tests for private experiment preservation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest
from legalforecast.retained_experiment import validate_experiment_zip


def test_experiment_accepts_complete_nonforecast_zip(tmp_path: Path) -> None:
    target = tmp_path / "experiment.zip"
    with ZipFile(target, "w") as archive:
        archive.writestr("comparison.md", "Private native experiment")
        archive.writestr("results/answer.json", "{}")
    validate_experiment_zip(target, hashlib.sha256(target.read_bytes()).hexdigest())


def test_selected_digest_must_match(tmp_path: Path) -> None:
    target = tmp_path / "experiment.zip"
    target.write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="differs"):
        validate_experiment_zip(target, "0" * 64)


def test_empty_zip_is_not_preserved(tmp_path: Path) -> None:
    target = tmp_path / "experiment.zip"
    with ZipFile(target, "w"):
        pass
    with pytest.raises(ValueError, match="empty or corrupt"):
        validate_experiment_zip(target, hashlib.sha256(target.read_bytes()).hexdigest())


@pytest.mark.parametrize("upload_only", [False, True])
def test_preservation_phases_keep_exact_key_and_verify_readback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, upload_only: bool
) -> None:
    import sys

    from legalforecast import retained_experiment as experiment

    target = tmp_path / "native-study.zip"
    with ZipFile(target, "w") as archive:
        archive.writestr("results/answer.json", "{}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    calls: list[tuple[str, str]] = []

    def download(repository: str, asset_id: int, name: str, path: Path) -> None:
        assert (repository, asset_id, name, path) == (
            "owner/repo",
            42,
            "native-study.zip",
            target,
        )
        calls.append(("download", name))

    def storage(bucket: str, path: Path, key: str) -> None:
        assert bucket == "results-bucket" and path == target
        calls.append(("upload", key))

    def readback(bucket: str, key: str, path: Path) -> None:
        assert bucket == "results-bucket" and path == target
        calls.append(("readback", key))

    monkeypatch.setattr(experiment, "download_draft_asset", download)
    monkeypatch.setattr(experiment, "upload_archive_object", storage)
    monkeypatch.setattr(experiment, "readback_archive_object", readback)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "preserve",
            "--repository",
            "owner/repo",
            "--bucket",
            "results-bucket",
            "--asset-id",
            "42",
            "--experiment",
            "native-study",
            "--sha256",
            digest,
            "--output-dir",
            str(tmp_path),
            *(["--upload-only"] if upload_only else []),
        ],
    )
    experiment.main()
    key = (
        "reports/retained-experiments/multi-ablation/owner/repo/native-study/"
        f"{digest}.zip"
    )
    assert calls == (
        [("upload", key), ("readback", key)]
        if upload_only
        else [("download", "native-study.zip")]
    )
