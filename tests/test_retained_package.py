"""Provider-free tests for retained package identity and completeness."""

from __future__ import annotations

import hashlib
import io
import json
from zipfile import ZipFile

import pytest
from legalforecast import artifact_restore as restore
from legalforecast.retained_package import retained_pointer_key, validate_package


def package(*, invalid: bool = False, incomplete: bool = False) -> bytes:
    values: dict[str, object] = {
        "forecast-run.json": {
            "workflow_run_id": 123,
            "workflow_run_attempt": 1,
            "run_identity_sha256": "identity",
            "model_key": "model",
            "forecast_release_digest": "release",
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
            "prediction_units": [{"unit_id": "unit"}],
        },
    }
    if not incomplete:
        values["receipts/receipt.json"] = {
            "case_id": "case",
            "model_key": "model",
            "forecast_release_digest": "release",
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
