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
    verify_no_freeze_drift,
)
from legalforecast.protocol.freeze import build_arg_parser

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
