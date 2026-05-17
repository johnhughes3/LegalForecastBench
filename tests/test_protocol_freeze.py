from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.protocol import (
    FreezeProtocolError,
    FrozenArtifactName,
    MissingFreezeArtifactError,
    detect_freeze_drift,
    freeze_cycle,
    load_preregistration,
    validate_preregistration_record,
    verify_no_freeze_drift,
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


def test_successful_freeze_writes_protocol_and_hash_bundle(tmp_path: Path) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    protocol_path = tmp_path / "protocols" / "cycle_fixture.preregistration.yaml"
    bundle_path = tmp_path / "manifests" / "cycle_fixture.freeze.json"

    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
        base_protocol_record=_base_protocol_record(),
        protocol_output_path=protocol_path,
        bundle_output_path=bundle_path,
    )

    protocol_record = load_preregistration(protocol_path)
    assert protocol_record["freeze_timestamp"] == "2026-05-14T12:05:00Z"
    assert protocol_record["frozen_artifacts"] == bundle.frozen_artifact_hashes()
    assert (
        protocol_record["model_registry"]["sha256"]
        == bundle.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256
    )

    validation = validate_preregistration_record(
        protocol_record,
        expected_hashes=bundle.frozen_artifact_hashes(),
        template_text=_template_text(),
    )
    assert validation.passed is True

    hash_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert hash_bundle["cycle_id"] == "cycle_fixture"
    assert hash_bundle["hash_bundle_sha256"] == bundle.bundle_sha256
    assert {artifact["name"] for artifact in hash_bundle["artifacts"]} == {
        name.value for name in FrozenArtifactName
    }


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
    }
    for name, path in paths.items():
        path.write_text(payloads[name], encoding="utf-8")
    return paths


def _base_protocol_record() -> dict[str, object]:
    return {
        "cycle_id": "cycle_fixture",
        "claim_level": "official_descriptive",
        "public_registration": {
            "provider": "osf",
            "url": "https://osf.io/abcd1/",
            "timestamp": "2026-05-14T12:00:00Z",
        },
        "freeze_timestamp": "",
        "anchors": {
            "model_release": "2026-05-14T09:00:00Z",
            "decision_window_start": "2026-05-14",
            "decision_window_end": "2026-06-14",
            "candidate_source_provider": "case.dev",
        },
        "metrics": {"primary": "micro_brier"},
        "inference": {
            "method": "paired_clustered_bootstrap",
            "bootstrap_replicates": 5000,
        },
        "model_registry": {
            "path": "",
            "sha256": "",
            "models": ["example:model-a"],
        },
        "baselines": {
            "path": "",
            "sha256": "",
        },
        "frozen_artifacts": {
            "manifest_sha256": "",
            "units_sha256": "",
            "labels_sha256": "",
            "prompt_sha256": "",
            "scorer_sha256": "",
            "harness_sha256": "",
        },
    }


def _template_text() -> str:
    return """
Cycle ID
Public registration provider
Candidate manifest
Prediction units
Outcome labels
Model registry SHA-256
Case-mix diagnostics
"""
