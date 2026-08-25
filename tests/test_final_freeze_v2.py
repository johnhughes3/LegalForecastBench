from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.protocol.freeze import (
    FreezeProtocolError,
    FrozenArtifactName,
    cli_freeze,
    freeze_cycle,
    sha256_file,
    verify_freeze_bundle,
    write_hash_bundle_create_only,
)
from legalforecast.protocol.policy_artifacts import generate_execution_policy_v2

from test_protocol_freeze import FREEZE_TIMESTAMP, _artifact_paths


def test_freeze_cli_is_create_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle_path = tmp_path / "existing.freeze.json"
    original = b"do not replace\n"
    bundle_path.write_bytes(original)

    result = cli_freeze(
        [
            "cycle_fixture",
            *_artifact_args(artifact_paths),
            "--timestamp",
            "2026-05-14T12:05:00Z",
            "--bundle-output",
            str(bundle_path),
        ]
    )

    assert result == 1
    assert "output already exists" in capsys.readouterr().err
    assert bundle_path.read_bytes() == original


def test_create_only_writer_refuses_existing_symlink_without_mutating_target(
    tmp_path: Path,
) -> None:
    bundle = freeze_cycle(
        "cycle_fixture",
        _artifact_paths(tmp_path),
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    target = tmp_path / "target.json"
    target.write_text("unchanged\n", encoding="utf-8")
    output = tmp_path / "freeze.json"
    output.symlink_to(target)

    with pytest.raises(FreezeProtocolError, match="cannot create final freeze bundle"):
        write_hash_bundle_create_only(output, bundle)

    assert target.read_text(encoding="utf-8") == "unchanged\n"


def test_official_freeze_accepts_authenticated_execution_policy_v2(
    tmp_path: Path,
) -> None:
    artifact_paths = _v2_artifact_paths(tmp_path)
    bundle_path = tmp_path / "v2.freeze.json"

    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
        bundle_output_path=bundle_path,
    )

    assert bundle.artifact(FrozenArtifactName.LABELS).sha256 == sha256_file(
        artifact_paths[FrozenArtifactName.LABELS]
    )
    assert bundle.artifact(FrozenArtifactName.EXECUTION_POLICY).sha256 == sha256_file(
        artifact_paths[FrozenArtifactName.EXECUTION_POLICY]
    )
    assert verify_freeze_bundle(bundle_path).bundle_sha256 == bundle.bundle_sha256


def _v2_artifact_paths(tmp_path: Path) -> dict[FrozenArtifactName, Path]:
    artifact_paths = _artifact_paths(tmp_path)
    execution_path = artifact_paths[FrozenArtifactName.EXECUTION_POLICY]
    legacy = json.loads(execution_path.read_text(encoding="utf-8"))
    decisions = legacy["policy"]
    decisions["lifecycle"] = {
        "labeling_policy_published_at": "2026-05-12T12:00:00Z",
        "production_labeling_started_at": "2026-05-13T12:00:00Z",
    }
    execution_path.write_text(
        json.dumps(generate_execution_policy_v2(decisions)), encoding="utf-8"
    )
    return artifact_paths


def _artifact_args(artifact_paths: dict[FrozenArtifactName, Path]) -> list[str]:
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
        FrozenArtifactName.PROVIDER_CYCLE_CAPS: "--provider-cycle-caps",
        FrozenArtifactName.EXECUTION_POLICY: "--execution-policy",
        FrozenArtifactName.LABELING_POLICY: "--labeling-policy",
        FrozenArtifactName.COHORT_POLICY: "--cohort-policy",
    }
    return [
        value
        for name, flag in flags.items()
        for value in (flag, str(artifact_paths[name]))
    ]
