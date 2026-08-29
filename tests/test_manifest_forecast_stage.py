from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.model_registry import load_model_registry_bytes
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

_OFFICIAL_MODELS = (("openai", "gpt-5.6-luna"), ("anthropic", "claude-opus-4-8"))
_SUPPLEMENTARY_MODELS = (("google", "gemini-3.7-flash"),)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _registry_records(
    models: tuple[tuple[str, str], ...],
) -> list[dict[str, object]]:
    return [
        {
            "context_limit": 400000,
            "display_name": f"{provider} {model_id}",
            "input_token_price": 1.25,
            "known_cutoff_publicity_caveats": [],
            "max_output_tokens": 128000,
            "model_id": model_id,
            "model_version_or_snapshot": model_id,
            "network_disabled": True,
            "output_token_price": 10.0,
            "pricing_source": "https://example.invalid/pricing",
            "provider": provider,
            "provider_training_cutoff": None,
            "provider_training_cutoff_status": "unknown",
            "release_timestamp": "2026-06-01T00:00:00Z",
            "release_timestamp_source": "https://example.invalid/release",
            "search_disabled": True,
            "tool_policy": "no_tools",
        }
        for provider, model_id in models
    ]


def _evaluation_models(
    models: tuple[tuple[str, str], ...],
) -> list[dict[str, str]]:
    payload = json.dumps(_registry_records(models), sort_keys=True).encode("utf-8")
    return registry_record(load_model_registry_bytes(payload).entries)


def _fixture(
    tmp_path: Path,
    *,
    registry_models: tuple[tuple[str, str], ...] = _OFFICIAL_MODELS,
    supplementary: bool = False,
) -> tuple[ManifestForecastStageConfig, FreezeBundle]:
    output = tmp_path / "output"
    root = tmp_path / "artifacts"
    artifacts: list[FrozenArtifact] = []
    for artifact_name in FrozenArtifactName:
        artifact = root / f"{artifact_name.value}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        payload: object = {"cycle_id": "cycle-1", "artifact": artifact_name.value}
        if artifact_name is FrozenArtifactName.MODEL_REGISTRY:
            payload = _registry_records(registry_models)
        artifact.write_text(
            json.dumps(payload, sort_keys=True) + "\n",
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
        {
            "manifest_sha256": "a" * 64,
            "evaluation_models": _evaluation_models(_OFFICIAL_MODELS),
        },
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
            supplementary=supplementary,
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


def test_supplementary_freeze_is_refused_at_the_official_manifest_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The near miss this guard exists for.

    Staging is create-once and neither OIDC role can delete, so a supplementary
    freeze staged at the shared corpus prefix would leave unremovable foreign
    objects beside dispatched official shards.
    """

    config, bundle = _fixture(tmp_path, registry_models=_SUPPLEMENTARY_MODELS)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )

    with pytest.raises(ManifestForecastStageError) as excinfo:
        stage_manifest_forecast(config)

    message = str(excinfo.value)
    assert "stage-manifest-forecast refuses" in message
    assert "google:gemini-3.7-flash" in message
    assert "openai:gpt-5.6-luna" in message
    assert "--supplementary" in message


def test_official_freeze_is_refused_at_the_supplementary_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path, supplementary=True)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )

    with pytest.raises(
        ManifestForecastStageError, match="refuses --supplementary for a freeze"
    ):
        stage_manifest_forecast(config)


def test_supplementary_staging_keys_a_sibling_prefix_by_source_freeze_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(
        tmp_path, registry_models=_SUPPLEMENTARY_MODELS, supplementary=True
    )
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )
    source_digest = hashlib.sha256(config.freeze_bundle.read_bytes()).hexdigest()

    result = stage_manifest_forecast(config)

    official_prefix = f"cycle-1/manifest-runs/{'a' * 64}"
    assert result.prefix == (
        f"cycle-1/manifest-runs/supplementary/{'a' * 64}/{source_digest}"
    )
    assert not result.prefix.startswith(f"{official_prefix}/")
    results_keys = [
        item["key"]
        for item in result.stage_record["objects"]
        if item["bucket"] == config.results_bucket
    ]
    assert results_keys
    assert not any(key.startswith(f"{official_prefix}/") for key in results_keys)
    assert all(key.startswith(f"{result.prefix}/") for key in results_keys)
    # The packet bucket keeps the established shared model-packets/ keys.
    assert [
        item["key"]
        for item in result.stage_record["objects"]
        if item["bucket"] == config.packet_bucket
    ] == ["model-packets/cycle-1/case-1/full_packet.json"]


def test_supplementary_stage_marker_records_both_freeze_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(
        tmp_path, registry_models=_SUPPLEMENTARY_MODELS, supplementary=True
    )
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )
    source_digest = hashlib.sha256(config.freeze_bundle.read_bytes()).hexdigest()
    captured: dict[str, object] = {}

    def _capture(objects: object) -> None:
        for obj in objects:  # type: ignore[union-attr]
            if obj.key.endswith("/supplementary-stage.json"):
                captured["record"] = json.loads(obj.path.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage._verify_source_snapshots",
        _capture,
    )

    result = stage_manifest_forecast(config)

    record = captured["record"]
    assert isinstance(record, dict)
    assert record["source_freeze_sha256"] == source_digest
    assert record["prefix"] == result.prefix
    assert record["model_keys"] == ["google:gemini-3.7-flash"]
    # Staging rewrites relative artifact paths, so the staged bundle is a
    # different commitment from the source file that keys the prefix.
    assert record["staged_freeze_sha256"] != source_digest
    assert record["staged_freeze_bundle_sha256"] != record["staged_freeze_sha256"]


def test_official_staging_writes_no_supplementary_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )

    result = stage_manifest_forecast(config)

    assert not any(
        item["key"].endswith("/supplementary-stage.json")
        for item in result.stage_record["objects"]
    )


def test_supplementary_staging_refuses_an_amendment_chain(tmp_path: Path) -> None:
    with pytest.raises(
        ManifestForecastStageError, match="refuses --supplementary with"
    ):
        ManifestForecastStageConfig(
            output_dir=tmp_path,
            freeze_bundle=tmp_path / "freeze.json",
            artifact_root=tmp_path,
            manifest_digest="a" * 64,
            results_bucket="results-bucket",
            packet_bucket="packet-bucket",
            amendment_bundles=(tmp_path / "parent.freeze.json",),
            supplementary=True,
        )


def test_staging_refuses_a_run_record_without_evaluation_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle",
        lambda *args, **kwargs: bundle,
    )
    _write_json(
        config.output_dir / "manifest-mode-run-record.json",
        {"manifest_sha256": "a" * 64},
    )

    with pytest.raises(ManifestForecastStageError, match="has no evaluation_models"):
        stage_manifest_forecast(config)


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
