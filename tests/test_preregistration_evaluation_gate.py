from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.protocol import (
    EvaluationGateMode,
    FrozenArtifactName,
    assert_evaluation_ready,
    build_preregistration_record,
    freeze_cycle,
    sha256_file,
    validate_evaluation_gate,
)

FREEZE_TIMESTAMP = datetime(2026, 5, 14, 12, 5, tzinfo=UTC)


def test_official_evaluation_gate_rejects_incomplete_protocol() -> None:
    record = {
        "cycle_id": "cycle_fixture",
        "claim_level": "official_descriptive",
    }

    result = validate_evaluation_gate(record)

    assert result.passed is False
    issue_paths = {issue.path for issue in result.issues}
    assert "public_registration.provider" in issue_paths
    assert "frozen_artifacts.manifest_sha256" in issue_paths
    with pytest.raises(ValueError, match=r"public_registration\.provider"):
        assert_evaluation_ready(record)


def test_official_evaluation_gate_passes_complete_fixture_bundle(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    record = build_preregistration_record(
        bundle,
        base_record=_official_protocol_record(),
    )

    result = validate_evaluation_gate(
        record,
        freeze_bundle=bundle,
        template_text=_template_text(),
    )

    assert result.passed is True
    assert_evaluation_ready(
        record,
        freeze_bundle=bundle,
        template_text=_template_text(),
    )


def test_official_evaluation_gate_detects_changed_frozen_labels(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    record = build_preregistration_record(
        bundle,
        base_record=_official_protocol_record(),
    )
    artifact_paths[FrozenArtifactName.LABELS].write_text(
        '{"unit_id":"unit-1","fully_dismissed":false}\n',
        encoding="utf-8",
    )

    result = validate_evaluation_gate(record, freeze_bundle=bundle)

    assert result.passed is False
    assert any(
        issue.path == "frozen_artifacts.labels_sha256"
        and issue.message == "frozen artifact changed after freeze"
        for issue in result.issues
    )
    with pytest.raises(ValueError, match="labels_sha256"):
        assert_evaluation_ready(record, freeze_bundle=bundle)


def test_rapid_evaluation_gate_allows_lighter_artifact_set(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    expected_hashes = {
        "manifest_sha256": sha256_file(artifact_paths[FrozenArtifactName.MANIFEST]),
        "units_sha256": sha256_file(artifact_paths[FrozenArtifactName.UNITS]),
        "scorer_sha256": sha256_file(artifact_paths[FrozenArtifactName.SCORER]),
    }
    record = {
        "cycle_id": "cycle_rapid_fixture",
        "claim_level": "rapid",
        "publication_claim_language": "rapid provisional fixture run",
        "anchors": {"model_release": "2026-05-14T09:00:00Z"},
        "eligibility_rules": ["decision_after_release"],
        "exclusion_rules": ["outcome_leakage"],
        "model_registry": {
            "path": str(artifact_paths[FrozenArtifactName.MODEL_REGISTRY]),
            "sha256": sha256_file(artifact_paths[FrozenArtifactName.MODEL_REGISTRY]),
        },
        "frozen_artifacts": expected_hashes,
    }

    result = validate_evaluation_gate(
        record,
        mode=EvaluationGateMode.RAPID,
        expected_hashes=expected_hashes,
    )

    assert result.passed is True


def test_aspredicted_identifier_is_accepted_for_official_gate(
    tmp_path: Path,
) -> None:
    artifact_paths = _artifact_paths(tmp_path)
    bundle = freeze_cycle(
        "cycle_fixture",
        artifact_paths,
        freeze_timestamp=FREEZE_TIMESTAMP,
    )
    base_record = _official_protocol_record()
    public_registration = base_record["public_registration"]
    assert isinstance(public_registration, dict)
    public_registration["provider"] = "aspredicted"
    public_registration["url"] = "ASPREDICTED-ABCD1"
    record = build_preregistration_record(bundle, base_record=base_record)

    result = validate_evaluation_gate(record, freeze_bundle=bundle)

    assert result.passed is True


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


def _official_protocol_record() -> dict[str, object]:
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
