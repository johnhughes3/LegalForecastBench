"""Provider-free tests for retained package identity and completeness."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from legalforecast import artifact_restore as restore
from legalforecast import retained_package as retained
from legalforecast.retained_package import retained_pointer_key, validate_package


def package(*, invalid: bool = False, incomplete: bool = False) -> bytes:
    registry_digest = hashlib.sha256(b"{}").hexdigest()
    values: dict[str, object] = {
        "model-registry.json": {},
        "run-manifest.json": {"selected_cases": [{"case_id": "case"}]},
        "forecast-run.json": {
            "workflow_run_id": 123,
            "workflow_run_attempt": 1,
            "run_identity_sha256": "identity",
            "model_key": "model",
            "forecast_release_digest": "release",
            "model_registry_sha256": registry_digest,
            "repeat_count": 1,
        },
        "run-summary.json": {
            "workflow_run_id": 123,
            "workflow_run_attempt": 1,
            "run_identity_sha256": "identity",
            "status": "completed",
            "completed_cells": 1,
            "expected_cell_count": 1,
        },
        "forecast-release.json": {
            "release_digest": "release",
            "case_count": 1,
            "unit_count": 1,
            "cases": [{"case_id": "case"}],
            "prediction_units": [{"unit_id": "unit", "case_id": "case"}],
        },
    }
    if not incomplete:
        values["receipts/receipt.json"] = {
            "case_id": "case",
            "model_key": "model",
            "forecast_release_digest": "release",
            "run_identity_sha256": "identity",
            "model_registry_sha256": registry_digest,
            "required_unit_ids": ["unit"],
            "repeat_index": 1,
            "parser_output": {
                "is_valid": not invalid,
                "invalid_output": invalid,
                "defaulted_unit_ids": [],
                "required_unit_ids": ["unit"],
                "predictions": [
                    {
                        "unit_id": "unit",
                        "defaulted": False,
                        "invalid_reason": None,
                        "probability_fully_dismissed": 0.5,
                    }
                ],
            },
        }
    output = io.BytesIO()
    with ZipFile(output, "w") as bundle:
        for name, value in values.items():
            bundle.writestr(name, json.dumps(value))
    return output.getvalue()


def test_complete_retained_package() -> None:
    validate_package(package(), 123, 1)


@pytest.mark.parametrize("invalid,incomplete", [(True, False), (False, True)])
def test_invalid_or_incomplete_package_refused(invalid: bool, incomplete: bool) -> None:
    with pytest.raises(ValueError):
        validate_package(package(invalid=invalid, incomplete=incomplete), 123, 1)


def test_wrong_original_run_refused() -> None:
    with pytest.raises(ValueError, match="run/attempt"):
        validate_package(package(), 124, 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_identity_sha256", "other"),
        ("model_registry_sha256", "other"),
        ("required_unit_ids", ["other"]),
        ("repeat_index", 2),
    ],
)
def test_receipt_binding_refused(field: str, value: object) -> None:
    output = io.BytesIO()
    with ZipFile(io.BytesIO(package())) as original, ZipFile(output, "w") as changed:
        for name in original.namelist():
            payload = original.read(name)
            if name == "receipts/receipt.json":
                record = json.loads(payload)
                record[field] = value
                payload = json.dumps(record).encode()
            changed.writestr(name, payload)
    with pytest.raises(ValueError):
        validate_package(output.getvalue(), 123, 1)


def test_retained_source_uses_separate_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = package()
    digest = hashlib.sha256(payload).hexdigest()
    name = "official-forecast-results-123-1"
    prefix = "reports/github-artifacts/multi-ablation/owner/repo/"
    key = f"{prefix}retained-packages/{digest}.zip"
    pointer = {
        "source_type": "retained_draft_release_asset",
        "repository": "owner/repo",
        "source_run_id": 123,
        "source_attempt": 1,
        "name": name,
        "release_asset_id": 456,
        "digest": f"sha256:{digest}",
        "key": key,
    }

    def command(arguments: list[str]) -> object:
        artifacts: list[object] = []
        return [{"artifacts": artifacts}]

    def archives(*args: object, **kwargs: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(restore, "_json_command", command)
    monkeypatch.setattr(restore, "archived_artifacts", archives)

    def get_object(bucket: str, requested: str) -> bytes:
        assert bucket == "bucket"
        if requested == retained_pointer_key("owner/repo", 123, name):
            return json.dumps(pointer).encode()
        assert requested == key
        return payload

    monkeypatch.setattr(restore, "_get_s3", get_object)
    assert restore.restore_artifact("owner/repo", 123, name, bucket="bucket") == payload
    with pytest.raises(ValueError, match="found 0"):
        restore.restore_artifact(
            "owner/repo", 123, name, artifact_id=456, bucket="bucket"
        )


def cli_arguments(destination: Path, digest: str) -> list[str]:
    return [
        "retained-package",
        "--repository",
        "owner/repo",
        "--bucket",
        "results-bucket",
        "--asset-id",
        "456",
        "--sha256",
        digest,
        "--source-run-id",
        "123",
        "--source-attempt",
        "1",
        "--output-dir",
        str(destination),
    ]


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "published",
        "wrong_asset",
        "wrong_name",
        "metadata_denied",
        "download_denied",
        "wrong_digest",
    ],
)
def test_authenticated_draft_ingestion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    payload = package()
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        sys,
        "argv",
        cli_arguments(tmp_path, "0" * 64 if mode == "wrong_digest" else digest),
    )

    def metadata(arguments: list[str]) -> object:
        assert arguments[:2] == ["gh", "api"]
        if mode == "metadata_denied":
            raise subprocess.CalledProcessError(1, arguments)
        if arguments[-1].endswith("/assets/456"):
            return {
                "id": 456,
                "name": "other.zip"
                if mode == "wrong_name"
                else "official-forecast-results-123-1.zip",
            }
        assert "--paginate" in arguments and "--slurp" in arguments
        return [
            [
                {
                    "draft": mode != "published",
                    "assets": [{"id": 999 if mode == "wrong_asset" else 456}],
                }
            ]
        ]

    def download(
        arguments: list[str], *, check: bool, capture_output: bool
    ) -> subprocess.CompletedProcess[bytes]:
        assert check and capture_output
        assert arguments[-1] == "repos/owner/repo/releases/assets/456"
        assert "Accept: application/octet-stream" in arguments
        if mode == "download_denied":
            raise subprocess.CalledProcessError(1, arguments)
        return subprocess.CompletedProcess(arguments, 0, payload, b"")

    def no_upload(*args: object) -> None:
        pytest.fail("download validation must precede storage writes")

    monkeypatch.setattr(retained, "json_command", metadata)
    monkeypatch.setattr(retained.subprocess, "run", download)
    monkeypatch.setattr(retained, "upload_archive_object", no_upload)
    if mode in {"metadata_denied", "download_denied"}:
        with pytest.raises(subprocess.CalledProcessError):
            retained.main()
    elif mode != "valid":
        with pytest.raises(ValueError):
            retained.main()
    else:
        retained.main()
        assert (tmp_path / "retained-package.zip").read_bytes() == payload
        pointer = json.loads((tmp_path / "retained-package-pointer.json").read_bytes())
        assert pointer["source_type"] == "retained_draft_release_asset"
        assert pointer["release_asset_id"] == 456
        assert "artifact_id" not in pointer


@pytest.mark.parametrize(
    "mode", ["valid", "corrupt_zip", "corrupt_pointer", "read_denied"]
)
def test_upload_requires_both_storage_readbacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    payload = package()
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / "retained-package.zip").write_bytes(payload)
    monkeypatch.setattr(
        sys, "argv", [*cli_arguments(tmp_path, digest), "--upload-only"]
    )
    stored: dict[str, bytes] = {}
    readbacks: list[str] = []

    def upload(bucket: str, source: Path, key: str) -> None:
        assert bucket == "results-bucket"
        stored[key] = source.read_bytes()

    def readback(
        arguments: list[str], *, check: bool, stdout: int
    ) -> subprocess.CompletedProcess[bytes]:
        assert check and stdout == subprocess.DEVNULL
        assert arguments[:3] == ["aws", "s3api", "get-object"]
        key = arguments[arguments.index("--key") + 1]
        readbacks.append(key)
        if mode == "read_denied":
            raise subprocess.CalledProcessError(1, arguments)
        corrupt = (mode == "corrupt_zip" and key.endswith(".zip")) or (
            mode == "corrupt_pointer" and key.endswith(".json")
        )
        Path(arguments[-1]).write_bytes(b"corrupt" if corrupt else stored[key])
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    monkeypatch.setattr(retained, "upload_archive_object", upload)
    monkeypatch.setattr(retained.subprocess, "run", readback)
    if mode == "read_denied":
        with pytest.raises(subprocess.CalledProcessError):
            retained.main()
    elif mode != "valid":
        with pytest.raises(ValueError, match="readback"):
            retained.main()
    else:
        retained.main()
        assert len(stored) == len(readbacks) == 2
    if mode in {"corrupt_zip", "read_denied"}:
        assert len(stored) == 1  # An unverified ZIP must not get a lookup pointer.
