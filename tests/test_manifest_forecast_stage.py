from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.supplementary_mode import (
    SUPPLEMENTARY_BINDING_FIELDS,
)
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
_OFFICIAL_ANCHOR = "2026-06-26"
_CORPUS_DECISION_DATE = "2026-03-04"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _registry_records(
    models: tuple[tuple[str, str], ...],
    *,
    price: float = 1.25,
) -> list[dict[str, object]]:
    return [
        {
            "context_limit": 400000,
            "display_name": f"{provider} {model_id}",
            "input_token_price": price,
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


def _artifact(path: Path, payload: object) -> FrozenArtifact:
    _write_json(path, payload)
    return FrozenArtifact(
        name=FrozenArtifactName.MANIFEST,
        path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
    )


def _named(artifact: FrozenArtifact, name: FrozenArtifactName) -> FrozenArtifact:
    return FrozenArtifact(
        name=name,
        path=artifact.path,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
    )


def _fixture(
    tmp_path: Path,
    *,
    registry_models: tuple[tuple[str, str], ...] = _OFFICIAL_MODELS,
    registry_price: float = 1.25,
    supplementary: bool = False,
) -> tuple[ManifestForecastStageConfig, FreezeBundle]:
    """Build a candidate freeze plus the pinned official freeze it is judged against.

    The prompt artifact carries a real ``prompt_replay`` block committing the
    official registry, because that shared block -- byte-identical in a sibling
    freeze -- is what the staging classifier reads the official identity from.
    """

    output = tmp_path / "output"
    root = tmp_path / "artifacts"
    official_registry_path = root / "model_registry.json"
    official_registry = _artifact(
        official_registry_path, _registry_records(_OFFICIAL_MODELS)
    )
    candidate_registry_path = (
        official_registry_path
        if registry_models == _OFFICIAL_MODELS and registry_price == 1.25
        else root / "model_registry_candidate.json"
    )
    candidate_registry = _artifact(
        candidate_registry_path,
        _registry_records(registry_models, price=registry_price),
    )
    shared: dict[FrozenArtifactName, FrozenArtifact] = {}
    for artifact_name in FrozenArtifactName:
        if artifact_name is FrozenArtifactName.MODEL_REGISTRY:
            continue
        payload: object = {"cycle_id": "cycle-1", "artifact": artifact_name.value}
        if artifact_name is FrozenArtifactName.PROMPT:
            payload = {
                "cycle_id": "cycle-1",
                "prompt_replay": {
                    "evaluation_models": _evaluation_models(_OFFICIAL_MODELS),
                    "evaluation_release_anchor": _OFFICIAL_ANCHOR,
                    "model_registry_sha256": official_registry.sha256,
                },
            }
        shared[artifact_name] = _named(
            _artifact(root / f"{artifact_name.value}.json", payload), artifact_name
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
                    "decision_date": _CORPUS_DECISION_DATE,
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
            "evaluation_release_anchor": _OFFICIAL_ANCHOR,
        },
    )
    frozen_at = datetime.now(UTC)

    def _bundle(registry: FrozenArtifact) -> FreezeBundle:
        return FreezeBundle(
            cycle_id="cycle-1",
            freeze_timestamp=frozen_at,
            artifacts=(
                *shared.values(),
                _named(registry, FrozenArtifactName.MODEL_REGISTRY),
            ),
        )

    official_bundle = _bundle(official_registry)
    official_path = tmp_path / "official.freeze.json"
    write_hash_bundle(official_path, official_bundle)
    official_digest = hashlib.sha256(official_path.read_bytes()).hexdigest()

    bundle = _bundle(candidate_registry)
    if candidate_registry.path == official_registry.path:
        bundle_path = official_path
    else:
        bundle_path = tmp_path / "freeze.json"
        write_hash_bundle(bundle_path, bundle)
    return (
        ManifestForecastStageConfig(
            output_dir=output,
            freeze_bundle=bundle_path,
            artifact_root=root,
            manifest_digest="a" * 64,
            results_bucket="results-bucket",
            packet_bucket="packet-bucket",
            official_freeze_bundle=official_path,
            official_freeze_bundle_sha256=official_digest,
            dry_run=True,
            supplementary=supplementary,
        ),
        bundle,
    )


def _patch_verify(monkeypatch: pytest.MonkeyPatch, bundle: FreezeBundle) -> None:
    monkeypatch.setattr(
        "legalforecast.publication.manifest_forecast_stage.verify_freeze_bundle_bytes",
        lambda *args, **kwargs: bundle,
    )


def test_stage_manifest_forecast_builds_digest_keyed_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    _patch_verify(monkeypatch, bundle)

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

    Staging is create-once and no role can delete, so a supplementary freeze
    staged at the shared corpus prefix would leave unremovable foreign objects
    beside dispatched official shards.
    """

    config, bundle = _fixture(tmp_path, registry_models=_SUPPLEMENTARY_MODELS)
    _patch_verify(monkeypatch, bundle)

    with pytest.raises(ManifestForecastStageError) as excinfo:
        stage_manifest_forecast(config)

    message = str(excinfo.value)
    assert "stage-manifest-forecast refuses" in message
    assert config.official_freeze_bundle_sha256 in message
    # Never route the operator at the other prefix: following such a
    # recommendation is exactly how a sibling would reach the official one.
    assert "--supplementary" not in message


def test_official_freeze_is_refused_at_the_supplementary_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path, supplementary=True)
    _patch_verify(monkeypatch, bundle)

    with pytest.raises(
        ManifestForecastStageError, match="registry distinct from the official"
    ):
        stage_manifest_forecast(config)


def test_same_official_models_with_other_bytes_refused_in_both_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registry naming the official models with different bytes belongs nowhere.

    It is neither the pinned official freeze nor a post-anchor sibling, so
    routing it to either prefix would be wrong; both modes refuse it by name.
    """

    for supplementary in (False, True):
        config, bundle = _fixture(
            tmp_path / f"mode-{supplementary}",
            registry_price=2.5,
            supplementary=supplementary,
        )
        _patch_verify(monkeypatch, bundle)

        with pytest.raises(ManifestForecastStageError) as excinfo:
            stage_manifest_forecast(config)

        assert "belongs in no manifest-run prefix" in str(excinfo.value)


def test_official_mode_requires_the_candidate_to_be_the_pinned_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    _patch_verify(monkeypatch, bundle)
    other = tmp_path / "other.freeze.json"
    other.write_text(config.official_freeze_bundle.read_text(encoding="utf-8") + " ")
    drifted = ManifestForecastStageConfig(
        output_dir=config.output_dir,
        freeze_bundle=other,
        artifact_root=config.artifact_root,
        manifest_digest=config.manifest_digest,
        results_bucket=config.results_bucket,
        packet_bucket=config.packet_bucket,
        official_freeze_bundle=config.official_freeze_bundle,
        official_freeze_bundle_sha256=config.official_freeze_bundle_sha256,
        dry_run=True,
    )

    with pytest.raises(
        ManifestForecastStageError, match="not the pinned official freeze bundle"
    ):
        stage_manifest_forecast(drifted)


def test_staging_refuses_an_official_reference_that_fails_its_digest_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path, registry_models=_SUPPLEMENTARY_MODELS)
    _patch_verify(monkeypatch, bundle)
    unpinned = ManifestForecastStageConfig(
        output_dir=config.output_dir,
        freeze_bundle=config.freeze_bundle,
        artifact_root=config.artifact_root,
        manifest_digest=config.manifest_digest,
        results_bucket=config.results_bucket,
        packet_bucket=config.packet_bucket,
        official_freeze_bundle=config.official_freeze_bundle,
        official_freeze_bundle_sha256="b" * 64,
        dry_run=True,
        supplementary=True,
    )

    with pytest.raises(ManifestForecastStageError, match="digest pin"):
        stage_manifest_forecast(unpinned)


def test_staging_refuses_a_prompt_contract_without_prompt_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The classifier reads the official identity from the shared prompt bytes."""

    config, bundle = _fixture(tmp_path, registry_models=_SUPPLEMENTARY_MODELS)
    _patch_verify(monkeypatch, bundle)
    prompt = bundle.artifact(FrozenArtifactName.PROMPT).path
    _write_json(prompt, {"cycle_id": "cycle-1"})

    with pytest.raises(ManifestForecastStageError, match="missing prompt_replay"):
        stage_manifest_forecast(
            ManifestForecastStageConfig(
                output_dir=config.output_dir,
                freeze_bundle=config.freeze_bundle,
                artifact_root=config.artifact_root,
                manifest_digest=config.manifest_digest,
                results_bucket=config.results_bucket,
                packet_bucket=config.packet_bucket,
                official_freeze_bundle=config.official_freeze_bundle,
                official_freeze_bundle_sha256=config.official_freeze_bundle_sha256,
                dry_run=True,
                supplementary=True,
            )
        )


def test_supplementary_staging_keys_a_sibling_prefix_by_source_freeze_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(
        tmp_path, registry_models=_SUPPLEMENTARY_MODELS, supplementary=True
    )
    _patch_verify(monkeypatch, bundle)
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


def test_supplementary_stage_marker_records_the_shared_dispatch_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(
        tmp_path, registry_models=_SUPPLEMENTARY_MODELS, supplementary=True
    )
    _patch_verify(monkeypatch, bundle)
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
    # Staging rewrites relative artifact paths, so the staged bundle is a
    # different commitment from the source file that keys the prefix.
    assert record["staged_freeze_sha256"] != source_digest
    assert record["staged_freeze_bundle_sha256"] != record["staged_freeze_sha256"]
    binding = record["supplementary_binding"]
    assert isinstance(binding, dict)
    # The sidecar carries the identical structure the cost receipt and the
    # execution scope carry, from the one builder rather than a restatement.
    assert set(binding) == set(SUPPLEMENTARY_BINDING_FIELDS)
    assert binding["supplementary_model_keys"] == ["google:gemini-3.7-flash"]
    assert binding["official_freeze_bundle_sha256"] == (
        config.official_freeze_bundle_sha256
    )
    assert binding["official_evaluation_release_anchor"] == _OFFICIAL_ANCHOR
    assert binding["corpus_anchor"] == _CORPUS_DECISION_DATE
    # The prefix is keyed by the freeze file, not the registry: two sibling
    # freezes that share a registry but differ in caps or execution policy must
    # not land in one create-once prefix.
    assert binding["supplementary_model_registry_sha256"] not in result.prefix


def test_two_sibling_freezes_sharing_a_registry_get_distinct_prefixes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the prefix is keyed by the freeze file and not by the registry digest.

    A sibling freeze can be re-issued over the same corpus and the same model
    registry with a different execution policy or provider caps artifact — the
    supplementary lane materialized both separately. Keying on the registry
    digest would map those two freezes to one create-once prefix, where the
    second staging creates its differing artifact objects and then fails on
    freeze.json, leaving objects no role can delete. Keying on the freeze file
    makes every distinct freeze a distinct prefix.
    """

    first, bundle = _fixture(
        tmp_path / "a", registry_models=_SUPPLEMENTARY_MODELS, supplementary=True
    )
    _patch_verify(monkeypatch, bundle)
    first_result = stage_manifest_forecast(first)

    # Same registry bytes, different freeze bytes: a re-issued freeze.
    second_bundle_path = tmp_path / "a" / "freeze-reissued.json"
    second_bundle_path.write_text('{"reissued": true}\n', encoding="utf-8")
    second = ManifestForecastStageConfig(
        output_dir=first.output_dir,
        freeze_bundle=second_bundle_path,
        artifact_root=first.artifact_root,
        manifest_digest=first.manifest_digest,
        results_bucket=first.results_bucket,
        packet_bucket=first.packet_bucket,
        official_freeze_bundle=first.official_freeze_bundle,
        official_freeze_bundle_sha256=first.official_freeze_bundle_sha256,
        dry_run=True,
        supplementary=True,
    )
    second_result = stage_manifest_forecast(second)

    assert first_result.prefix != second_result.prefix
    first_keys = {item["key"] for item in first_result.stage_record["objects"]}
    second_keys = {item["key"] for item in second_result.stage_record["objects"]}
    shared = first_keys & second_keys
    # Only the shared packet-bucket keys overlap, and those are byte-identical
    # create-once no-ops by design.
    assert all(key.startswith("model-packets/") for key in shared)


def test_official_staging_writes_no_supplementary_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    _patch_verify(monkeypatch, bundle)

    result = stage_manifest_forecast(config)

    assert not any(
        item["key"].endswith("/supplementary-stage.json")
        for item in result.stage_record["objects"]
    )


def test_supplementary_staging_refuses_an_amendment_chain(tmp_path: Path) -> None:
    with pytest.raises(
        ManifestForecastStageError, match="refuses --amendment-bundle in"
    ):
        ManifestForecastStageConfig(
            output_dir=tmp_path,
            freeze_bundle=tmp_path / "freeze.json",
            artifact_root=tmp_path,
            manifest_digest="a" * 64,
            results_bucket="results-bucket",
            packet_bucket="packet-bucket",
            official_freeze_bundle=tmp_path / "official.freeze.json",
            official_freeze_bundle_sha256="b" * 64,
            amendment_bundles=(tmp_path / "parent.freeze.json",),
            supplementary=True,
        )


def test_stage_manifest_forecast_rejects_packet_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    _patch_verify(monkeypatch, bundle)
    packet = next((config.output_dir / "model-packets").rglob("*.json"))
    packet.write_text('{"case_id":"case-1","text":"drift"}\n', encoding="utf-8")

    with pytest.raises(ManifestForecastStageError, match="packet bytes differ"):
        stage_manifest_forecast(config)


def test_stage_manifest_forecast_rejects_packet_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, bundle = _fixture(tmp_path)
    _patch_verify(monkeypatch, bundle)
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

    (
        current_objects,
        staged_current_path,
        amendment_objects,
        staged_paths,
        staged_bundle_sha256,
    ) = _freeze_chain_objects(
        bundle=current,
        amendment_paths=(parent_path,),
        artifact_root=tmp_path / "artifacts",
        results_bucket="results-bucket",
        prefix="cycle-1/manifest-runs/" + "a" * 64,
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
        assert staged_bundle_sha256 == staged_current.bundle_sha256
    finally:
        for path in staged_paths:
            path.unlink(missing_ok=True)
