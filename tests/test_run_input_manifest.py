from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.publication.run_input_manifest import (
    RunInputManifestError,
    freeze_run_input_labels,
    main,
)


def test_freeze_run_input_labels_records_hash_in_produced_manifest(
    tmp_path: Path,
) -> None:
    source_manifest = tmp_path / "cycle.run-inputs.json"
    frozen_manifest = tmp_path / "cycle.run-inputs.frozen.json"
    labels_path = tmp_path / "cycle.labels.jsonl"
    source_record = {
        "schema_version": "legalforecast-private-store-export-v1",
        "cycle_id": "cycle-fixture",
        "generated_at": "2026-05-18T00:00:00Z",
        "model_packets": [
            {
                "case_id": "case-1",
                "packet_object_key": "model-packets/cycle-fixture/case-1/full.json",
            }
        ],
    }
    source_manifest.write_text(
        json.dumps(source_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")

    result = freeze_run_input_labels(
        source_manifest,
        labels_path=labels_path,
        output_path=frozen_manifest,
    )

    expected_sha256 = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    produced = json.loads(frozen_manifest.read_text(encoding="utf-8"))
    original = json.loads(source_manifest.read_text(encoding="utf-8"))
    assert result.labels_sha256 == expected_sha256
    assert result.output_path == frozen_manifest
    assert produced == {**source_record, "labels_sha256": expected_sha256}
    assert "labels_sha256" not in original


def test_freeze_run_input_labels_is_idempotent_for_same_labels(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    labels_sha256 = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": labels_sha256,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = freeze_run_input_labels(
        manifest_path,
        labels_path=labels_path,
        output_path=manifest_path,
    )

    assert result.labels_sha256 == labels_sha256
    assert (
        json.loads(manifest_path.read_text(encoding="utf-8"))["labels_sha256"]
        == labels_sha256
    )


def test_freeze_run_input_labels_refuses_to_replace_existing_commitment(
    tmp_path: Path,
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": "0" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="refusing to replace"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=tmp_path / "frozen.json",
        )


def test_freeze_run_input_labels_rejects_invalid_existing_commitment(
    tmp_path: Path,
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="lowercase SHA-256"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=tmp_path / "frozen.json",
        )


def test_freeze_run_input_labels_refuses_to_overwrite_labels(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps({"cycle_id": "cycle-fixture", "model_packets": []}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="must not overwrite"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=labels_path,
        )

    assert labels_path.read_text(encoding="utf-8") == '{"unit_id":"unit-1"}\n'


def test_freeze_labels_cli_writes_manifest_and_reports_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps({"cycle_id": "cycle-fixture", "model_packets": []}) + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "run-inputs.frozen.json"

    status = main(
        (
            "freeze-labels",
            "--manifest",
            str(manifest_path),
            "--labels",
            str(labels_path),
            "--output",
            str(output_path),
        )
    )

    stdout = json.loads(capsys.readouterr().out)
    produced = json.loads(output_path.read_text(encoding="utf-8"))
    assert status == 0
    assert stdout == {
        "labels_sha256": produced["labels_sha256"],
        "output": str(output_path),
    }
