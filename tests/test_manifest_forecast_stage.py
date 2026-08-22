from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FrozenArtifact,
    FrozenArtifactName,
    load_freeze_bundle,
    write_hash_bundle,
)
from legalforecast.publication.manifest_forecast_stage import (
    ManifestForecastStageConfig,
    ManifestForecastStageError,
    _freeze_chain_objects,
    stage_manifest_forecast,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[ManifestForecastStageConfig, FreezeBundle]:
    output = tmp_path / "output"
    root = tmp_path / "artifacts"
    artifacts: list[FrozenArtifact] = []
    for artifact_name in FrozenArtifactName:
        artifact = root / f"{artifact_name.value}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps({"cycle_id": "cycle-1", "artifact": artifact_name.value}) + "\n",
            encoding="utf-8",
        )
        artifacts.append(
            FrozenArtifact(
                name=artifact_name,
                path=artifact,
                sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                size_bytes=artifact.stat().st_size,
            )
        )
    packet = output / "model-packets" / "cycle-1" / "case-1" / "full_packet.json"
    _write_json(packet, {"case_id": "case-1", "text": "blind"})
    packet_digest = hashlib.sha256(packet.read_bytes()).hexdigest()
    _write_json(
        output / "run-inputs.json",
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "packet_object_key": (
                        "model-packets/cycle-1/case-1/full_packet.json"
                    ),
                    "packet_sha256": packet_digest,
                }
            ],
        },
    )
    _write_json(
        output / "manifest-mode-run-record.json",
        {"manifest_sha256": "a" * 64},
    )
    bundle = FreezeBundle(
        cycle_id="cycle-1",
        freeze_timestamp=datetime.now(UTC),
        artifacts=tuple(artifacts),
    )
    bundle_path = tmp_path / "freeze.json"
    bundle_path.write_text("{}\n", encoding="utf-8")
    return (
        ManifestForecastStageConfig(
            output_dir=output,
            freeze_bundle=bundle_path,
            artifact_root=root,
            manifest_digest="a" * 64,
            results_bucket="results-bucket",
            packet_bucket="packet-bucket",
            dry_run=True,
        ),
        bundle,
    )


def test_stage_manifest_forecast_builds_digest_keyed_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )

    result = stage_manifest_forecast(config)

    assert result.prefix == f"cycle-1/manifest-runs/{'a' * 64}"
    assert result.packet_count == 1
    assert result.freeze_bundle_uri.endswith("/freeze.json")
    assert result.run_input_manifest_uri.endswith("/run-inputs.json")
    assert all(item["sha256"] for item in result.stage_record["objects"])


def test_stage_manifest_forecast_rejects_packet_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )
    packet = next((config.output_dir / "model-packets").rglob("*.json"))
    packet.write_text('{"case_id":"case-1","text":"drift"}\n', encoding="utf-8")

    with pytest.raises(ManifestForecastStageError, match="packet bytes differ"):
        stage_manifest_forecast(config)


def test_stage_manifest_forecast_rejects_packet_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )
    run_inputs_path = config.output_dir / "run-inputs.json"
    run_inputs = json.loads(run_inputs_path.read_text(encoding="utf-8"))
    run_inputs["model_packets"][0]["packet_object_key"] = (
        "model-packets/../outside.json"
    )
    _write_json(run_inputs_path, run_inputs)

    with pytest.raises(ManifestForecastStageError, match="unsafe S3 key"):
        stage_manifest_forecast(config)


def test_freeze_chain_rewrites_amendment_pointer_and_stages_ancestor(
    tmp_path: Path,
) -> None:
    _config, parent = _fixture(tmp_path)
    current = FreezeBundle(
        cycle_id=parent.cycle_id,
        freeze_timestamp=parent.freeze_timestamp,
        artifacts=parent.artifacts,
        amends_bundle_sha256=parent.bundle_sha256,
    )
    parent_path = tmp_path / "parent.freeze.json"
    write_hash_bundle(parent_path, parent)

    current_objects, staged_current_path, amendment_objects, staged_paths = (
        _freeze_chain_objects(
            bundle=current,
            amendment_paths=(parent_path,),
            artifact_root=tmp_path / "artifacts",
            results_bucket="results-bucket",
            prefix="cycle-1/manifest-runs/" + "a" * 64,
        )
    )
    try:
        staged_current = load_freeze_bundle(staged_current_path)
        staged_parent_path = next(
            obj.path for obj in amendment_objects if obj.key.endswith(".freeze.json")
        )
        staged_parent = load_freeze_bundle(staged_parent_path)

        assert staged_current.amends_bundle_sha256 == staged_parent.bundle_sha256
        assert staged_current.amends_bundle_sha256 != parent.bundle_sha256
        assert current_objects
        assert len(staged_paths) == 2
    finally:
        for path in staged_paths:
            path.unlink(missing_ok=True)
