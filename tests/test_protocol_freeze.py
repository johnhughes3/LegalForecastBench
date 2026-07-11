from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.protocol import (
    FreezeProtocolError,
    FrozenArtifactName,
    MissingFreezeArtifactError,
    detect_freeze_drift,
    freeze_cycle,
    load_freeze_bundle,
    sha256_file,
    verify_freeze_bundle,
    verify_no_freeze_drift,
    write_hash_bundle,
)
from legalforecast.protocol.freeze import (
    amend_freeze_cycle,
    build_arg_parser,
    cli_freeze,
)

FREEZE_TIMESTAMP = datetime(2026, 5, 14, 12, 5, tzinfo=UTC)


def test_freeze_hashes_are_deterministic(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)

    first = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    second = freeze_cycle(
        "cycle_fixture",
        dict(reversed(tuple(artifact_paths.items()))),
        freeze_timestamp=FREEZE_TIMESTAMP,
    )

    assert first.frozen_artifact_hashes() == second.frozen_artifact_hashes()
    assert first.bundle_sha256 == second.bundle_sha256


def test_freeze_fails_when_required_artifact_is_missing(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    artifact_paths[FrozenArtifactName.LABELS].unlink()

    with pytest.raises(MissingFreezeArtifactError, match="freeze artifact missing"):
        freeze_cycle(
            "cycle_fixture",
            artifact_paths,
            freeze_timestamp=FREEZE_TIMESTAMP,
        )


def test_post_freeze_modification_is_detected(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )

    artifact_paths[FrozenArtifactName.PROMPT].write_text(
        "changed prompt",
        encoding="utf-8",
    )

    drift = detect_freeze_drift(bundle)
    assert [item.name for item in drift] == [FrozenArtifactName.PROMPT]
    assert drift[0].actual_sha256 != drift[0].expected_sha256
    with pytest.raises(FreezeProtocolError, match="prompt hash changed"):
        verify_no_freeze_drift(bundle)


def test_successful_freeze_writes_hash_bundle(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = tmp_path / "manifests" / "cycle_fixture.freeze.json"

    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
        bundle_output_path=bundle_path,
    )

    hash_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert hash_bundle["cycle_id"] == "cycle_fixture"
    assert hash_bundle["hash_bundle_sha256"] == bundle.bundle_sha256
    assert {artifact["name"] for artifact in hash_bundle["artifacts"]} == {
        name.value for name in FrozenArtifactName
    }


def test_freeze_cli_has_no_preregistration_options() -> None:
    help_text = build_arg_parser().format_help()

    assert "--base-protocol" not in help_text
    assert "--protocol-output" not in help_text
    assert "--exclusion-ledger EXCLUSION_LEDGER" in help_text


def test_freeze_cli_creates_nine_artifact_bundle(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = tmp_path / "cli.freeze.json"
    flags = {
        FrozenArtifactName.MANIFEST: "--manifest",
        FrozenArtifactName.UNITS: "--units",
        FrozenArtifactName.LABELS: "--labels",
        FrozenArtifactName.PROMPT: "--prompt",
        FrozenArtifactName.SCORER: "--scorer",
        FrozenArtifactName.HARNESS: "--harness",
        FrozenArtifactName.MODEL_REGISTRY: "--model-registry",
        FrozenArtifactName.BASELINES: "--baselines",
        FrozenArtifactName.EXCLUSION_LEDGER: "--exclusion-ledger",
    }
    artifact_args = [
        value
        for name, flag in flags.items()
        for value in (flag, str(artifact_paths[name]))
    ]

    result = cli_freeze(
        [
            "cycle_fixture",
            *artifact_args,
            "--timestamp",
            "2026-05-14T12:05:00Z",
            "--bundle-output",
            str(bundle_path),
        ]
    )

    assert result == 0
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert {artifact["name"] for artifact in bundle["artifacts"]} == {
        name.value for name in FrozenArtifactName
    }


def test_amendment_freeze_preserves_artifacts_and_records_parent(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(amended_registry, ("model-a", "model-b"))
    amended_path = tmp_path / "manifests" / "cycle_fixture.amendment.freeze.json"

    amended = amend_freeze_cycle(
        prior_path,
        amended_registry,
        root_path=tmp_path,
        freeze_timestamp=FREEZE_TIMESTAMP,
        bundle_output_path=amended_path,
    )

    prior = load_freeze_bundle(prior_path, root_path=tmp_path)
    assert amended.amends_bundle_sha256 == prior.bundle_sha256
    assert (
        amended.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256
        != prior.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256
    )
    for name in FrozenArtifactName:
        if name is not FrozenArtifactName.MODEL_REGISTRY:
            assert amended.artifact(name).sha256 == prior.artifact(name).sha256
    assert (
        verify_freeze_bundle(
            amended_path,
            cycle_id="cycle_fixture",
            root_path=tmp_path,
            amendment_bundle_paths=(prior_path,),
        ).bundle_sha256
        == amended.bundle_sha256
    )


def test_amendment_freeze_rejects_changed_existing_registry_entry(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(
        amended_registry,
        ("model-a", "model-b"),
        input_price_by_model={"model-a": 9.99},
    )

    with pytest.raises(FreezeProtocolError, match="existing registry entry changed"):
        amend_freeze_cycle(prior_path, amended_registry, root_path=tmp_path)


def test_amendment_freeze_requires_strict_registry_superset(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    unchanged_registry = tmp_path / "models-unchanged.json"
    _write_registry(unchanged_registry, ("model-a",))

    with pytest.raises(FreezeProtocolError, match="strict superset"):
        amend_freeze_cycle(prior_path, unchanged_registry, root_path=tmp_path)


def test_amendment_freeze_rejects_added_model_after_release_anchor(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(
        amended_registry,
        ("model-a", "model-b"),
        release_by_model={"model-b": "2026-05-15T00:00:00Z"},
    )

    with pytest.raises(FreezeProtocolError, match="raises release anchor"):
        amend_freeze_cycle(prior_path, amended_registry, root_path=tmp_path)


def test_verify_amendment_requires_committed_ancestor_bundle(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(amended_registry, ("model-a", "model-b"))
    amended_path = tmp_path / "manifests" / "cycle_fixture.amendment.freeze.json"
    amend_freeze_cycle(
        prior_path,
        amended_registry,
        root_path=tmp_path,
        bundle_output_path=amended_path,
    )

    with pytest.raises(FreezeProtocolError, match="ancestor bundle is missing"):
        verify_freeze_bundle(amended_path, root_path=tmp_path)


def test_verify_amendment_rejects_cycle_id_change(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(amended_registry, ("model-a", "model-b"))
    amended = amend_freeze_cycle(prior_path, amended_registry, root_path=tmp_path)
    invalid_path = tmp_path / "manifests" / "invalid-cycle.freeze.json"
    write_hash_bundle(
        invalid_path, replace(amended, cycle_id="other-cycle"), root_path=tmp_path
    )

    with pytest.raises(FreezeProtocolError, match="cycle_id must match"):
        verify_freeze_bundle(
            invalid_path,
            root_path=tmp_path,
            amendment_bundle_paths=(prior_path,),
        )


def test_verify_amendment_rejects_non_registry_artifact_change(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(amended_registry, ("model-a", "model-b"))
    amended = amend_freeze_cycle(prior_path, amended_registry, root_path=tmp_path)
    amended_prompt = tmp_path / "prompt-amended.md"
    amended_prompt.write_text("changed prompt", encoding="utf-8")
    invalid = replace(
        amended,
        artifacts=tuple(
            replace(
                artifact,
                path=amended_prompt,
                sha256=sha256_file(amended_prompt),
                size_bytes=amended_prompt.stat().st_size,
            )
            if artifact.name is FrozenArtifactName.PROMPT
            else artifact
            for artifact in amended.artifacts
        ),
    )
    invalid_path = tmp_path / "manifests" / "invalid-prompt.freeze.json"
    write_hash_bundle(invalid_path, invalid, root_path=tmp_path)

    with pytest.raises(FreezeProtocolError, match="prompt hash changed"):
        verify_freeze_bundle(
            invalid_path,
            root_path=tmp_path,
            amendment_bundle_paths=(prior_path,),
        )


def test_freeze_amend_cli_creates_verified_amendment(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    _write_registry(artifact_paths[FrozenArtifactName.MODEL_REGISTRY], ("model-a",))
    prior_path = _write_relative_bundle(tmp_path, artifact_paths)
    amended_registry = tmp_path / "models-amended.json"
    _write_registry(amended_registry, ("model-a", "model-b"))
    output_path = tmp_path / "manifests" / "cli-amendment.freeze.json"

    result = cli_freeze(
        [
            "amend",
            "--prior-bundle",
            str(prior_path),
            "--model-registry",
            str(amended_registry),
            "--root",
            str(tmp_path),
            "--timestamp",
            "2026-05-14T12:05:00Z",
            "--bundle-output",
            str(output_path),
        ]
    )

    assert result == 0
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert (
        record["amends_bundle_sha256"]
        == load_freeze_bundle(prior_path, root_path=tmp_path).bundle_sha256
    )


def test_verify_freeze_bundle_accepts_clean_relative_bundle(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)

    verified = verify_freeze_bundle(
        bundle_path,
        cycle_id="cycle_fixture",
        root_path=tmp_path,
    )

    assert {artifact.name for artifact in verified.artifacts} == set(FrozenArtifactName)


@pytest.mark.parametrize("artifact_name", tuple(FrozenArtifactName))
def test_verify_freeze_bundle_detects_drift_for_every_required_artifact(
    tmp_path: Path,
    artifact_name: FrozenArtifactName,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)
    with artifact_paths[artifact_name].open("ab") as handle:
        handle.write(b"x")

    with pytest.raises(
        FreezeProtocolError,
        match=f"{artifact_name.value} hash changed",
    ):
        verify_freeze_bundle(
            bundle_path,
            cycle_id="cycle_fixture",
            root_path=tmp_path,
        )


def test_load_freeze_bundle_rejects_bundle_hash_mismatch(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)
    record = json.loads(bundle_path.read_text(encoding="utf-8"))
    record["cycle_id"] = "tampered-cycle"
    bundle_path.write_text(
        f"{json.dumps(record, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )

    with pytest.raises(FreezeProtocolError, match="hash_bundle_sha256 mismatch"):
        load_freeze_bundle(bundle_path, root_path=tmp_path)


def test_verify_freeze_bundle_rejects_dispatch_cycle_mismatch(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)

    with pytest.raises(
        FreezeProtocolError,
        match="cycle_id does not match dispatch input",
    ):
        verify_freeze_bundle(
            bundle_path,
            cycle_id="different-cycle",
            root_path=tmp_path,
        )


def test_freeze_verify_cli_honors_workflow_local_overrides(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)
    overrides: list[str] = []
    for name in (
        FrozenArtifactName.MANIFEST,
        FrozenArtifactName.LABELS,
        FrozenArtifactName.MODEL_REGISTRY,
    ):
        downloaded = tmp_path / "downloads" / artifact_paths[name].name
        downloaded.parent.mkdir(exist_ok=True)
        downloaded.write_bytes(artifact_paths[name].read_bytes())
        artifact_paths[name].write_text("checkout copy drifted", encoding="utf-8")
        overrides.extend(("--artifact-path", f"{name.value}={downloaded}"))

    result = cli_freeze(
        [
            "verify",
            "--bundle",
            str(bundle_path),
            "--cycle-id",
            "cycle_fixture",
            "--root",
            str(tmp_path),
            *overrides,
        ]
    )

    assert result == 0


def test_workflow_verification_keeps_cycle_manifest_distinct_from_run_inputs(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = _write_relative_bundle(tmp_path, artifact_paths)
    downloaded_labels = tmp_path / "downloads" / "labels.jsonl"
    downloaded_registry = tmp_path / "downloads" / "models.json"
    downloaded_labels.parent.mkdir()
    downloaded_labels.write_bytes(
        artifact_paths[FrozenArtifactName.LABELS].read_bytes()
    )
    downloaded_registry.write_bytes(
        artifact_paths[FrozenArtifactName.MODEL_REGISTRY].read_bytes()
    )
    fanout_manifest = tmp_path / "downloads" / "run-inputs-frozen.json"
    fanout_manifest.write_text(
        json.dumps(
            {
                "cycle_id": "cycle_fixture",
                "labels_sha256": "a" * 64,
                "model_packets": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    verified = verify_freeze_bundle(
        bundle_path,
        cycle_id="cycle_fixture",
        root_path=tmp_path,
        artifact_path_overrides={
            FrozenArtifactName.LABELS: downloaded_labels,
            FrozenArtifactName.MODEL_REGISTRY: downloaded_registry,
        },
    )

    assert (
        verified.artifact(FrozenArtifactName.MANIFEST).path
        == artifact_paths[FrozenArtifactName.MANIFEST]
    )
    with pytest.raises(FreezeProtocolError, match="manifest hash changed"):
        verify_freeze_bundle(
            bundle_path,
            cycle_id="cycle_fixture",
            root_path=tmp_path,
            artifact_path_overrides={FrozenArtifactName.MANIFEST: fanout_manifest},
        )


def _artifact_paths(tmp_path: Path) -> dict[FrozenArtifactName, Path]:
    paths = {
        FrozenArtifactName.MANIFEST: tmp_path / "manifest.jsonl",
        FrozenArtifactName.UNITS: tmp_path / "units.jsonl",
        FrozenArtifactName.LABELS: tmp_path / "labels.jsonl",
        FrozenArtifactName.PROMPT: tmp_path / "prompt.md",
        FrozenArtifactName.SCORER: tmp_path / "scorer.py",
        FrozenArtifactName.HARNESS: tmp_path / "harness.txt",
        FrozenArtifactName.MODEL_REGISTRY: tmp_path / "models.json",
        FrozenArtifactName.BASELINES: tmp_path / "baselines.json",
        FrozenArtifactName.EXCLUSION_LEDGER: tmp_path / "exclusion-ledger.jsonl",
    }
    payloads = {
        FrozenArtifactName.MANIFEST: '{"candidate_id":"cand-1"}\n',
        FrozenArtifactName.UNITS: '{"unit_id":"unit-1"}\n',
        FrozenArtifactName.LABELS: '{"unit_id":"unit-1","fully_dismissed":true}\n',
        FrozenArtifactName.PROMPT: "Predict dismissal probability.",
        FrozenArtifactName.SCORER: "def score(): return 'micro_brier'\n",
        FrozenArtifactName.HARNESS: "legalforecast-mtd 0.1.0a1\n",
        FrozenArtifactName.MODEL_REGISTRY: (
            '[{"provider":"example","model_id":"model-a"}]\n'
        ),
        FrozenArtifactName.BASELINES: '{"baselines":["global_base_rate"]}\n',
        FrozenArtifactName.EXCLUSION_LEDGER: "",
    }
    for name, path in paths.items():
        path.write_text(payloads[name], encoding="utf-8")
    return paths


def _write_relative_bundle(
    tmp_path: Path,
    artifact_paths: dict[FrozenArtifactName, Path],
) -> Path:
    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    bundle_path = tmp_path / "manifests" / "cycle_fixture.freeze.json"
    write_hash_bundle(bundle_path, bundle, root_path=tmp_path)
    return bundle_path


def _write_registry(
    path: Path,
    model_ids: tuple[str, ...],
    *,
    input_price_by_model: dict[str, float] | None = None,
    release_by_model: dict[str, str] | None = None,
) -> None:
    prices = input_price_by_model or {}
    releases = release_by_model or {}
    records = [
        {
            "provider": "example",
            "model_id": model_id,
            "display_name": model_id,
            "model_version_or_snapshot": f"{model_id}-2026-05-14",
            "release_timestamp": releases.get(model_id, "2026-05-14T09:00:00Z"),
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": "not_disclosed",
            "provider_training_cutoff": None,
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "fixture",
            "input_token_price": prices.get(model_id, 0.25),
            "output_token_price": 1.0,
            "known_cutoff_publicity_caveats": [],
        }
        for model_id in model_ids
    ]
    path.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
