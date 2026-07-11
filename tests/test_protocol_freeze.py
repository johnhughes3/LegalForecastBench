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
    load_freeze_bundle,
    verify_freeze_bundle,
    verify_no_freeze_drift,
    write_hash_bundle,
)
from legalforecast.protocol.freeze import build_arg_parser, cli_freeze

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
