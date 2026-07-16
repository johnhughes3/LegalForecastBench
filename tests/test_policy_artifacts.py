from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli import main
from legalforecast.protocol.freeze import cli_freeze
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    generate_execution_policy,
    generate_labeling_policy,
    require_dispatch_policy_match,
    verify_execution_policy,
    verify_labeling_policy,
    write_labeling_policy,
)

ROOT = Path(__file__).parents[1]
JUDGE_REGISTRY = ROOT / "model_registries/cycle-1-stage-b-judges-2026-07-12.json"


def test_labeling_policy_binds_registry_and_precommits_five_percent() -> None:
    artifact = _labeling_policy()

    verify_labeling_policy(artifact, judge_registry_path=JUDGE_REGISTRY)

    policy = cast(dict[str, object], artifact["policy"])
    audit = cast(dict[str, object], policy["label_audit"])
    assert audit["sample_fraction"] == 0.05
    assert audit["max_llm_error_rate"] == 0.05
    assert audit["max_human_disagreement_rate"] == 0.05
    seed_components = cast(list[str], audit["seed_components"])
    assert "labels_sha256" not in seed_components


def test_labeling_policy_rejects_different_judge_registry(tmp_path: Path) -> None:
    artifact = _labeling_policy()
    changed = tmp_path / "judges.json"
    changed.write_bytes(JUDGE_REGISTRY.read_bytes() + b"\n")

    with pytest.raises(PolicyArtifactError, match="judge registry bytes"):
        verify_labeling_policy(artifact, judge_registry_path=changed)


def test_labeling_policy_is_write_once(tmp_path: Path) -> None:
    path = tmp_path / "labeling-policy.json"
    artifact = _labeling_policy()
    write_labeling_policy(path, artifact)
    write_labeling_policy(path, artifact)
    changed = generate_labeling_policy(
        cycle_id="other-cycle",
        judge_registry_path=JUDGE_REGISTRY,
        published_at=datetime(2026, 7, 12, 20, tzinfo=UTC),
        threshold_source="Cycle 1 protocol decision, 2026-07-13",
    )

    with pytest.raises(PolicyArtifactError, match="different immutable content"):
        write_labeling_policy(path, changed)


def test_execution_policy_round_trip_and_rejects_late_precommitment() -> None:
    artifact = generate_execution_policy(_execution_decisions())
    assert (
        verify_execution_policy(artifact, expected_cycle_id="cycle-1")
        == artifact["policy_sha256"]
    )

    late = _execution_decisions()
    lifecycle = cast(dict[str, object], late["lifecycle"])
    lifecycle["labeling_policy_published_at"] = "2026-07-13T01:00:00Z"
    with pytest.raises(PolicyArtifactError, match="before labeling"):
        generate_execution_policy(late)


def test_dispatch_choices_must_match_frozen_execution_policy() -> None:
    artifact = generate_execution_policy(_execution_decisions())
    require_dispatch_policy_match(
        artifact, cycle_series="official", allow_no_baselines=True
    )

    with pytest.raises(PolicyArtifactError, match="allow_no_baselines"):
        require_dispatch_policy_match(
            artifact, cycle_series="official", allow_no_baselines=False
        )


@pytest.mark.parametrize(
    ("mode", "identity_fields"),
    (
        ("queue_max", ["cycle_id"]),
        ("orchestrator", ["cycle_id", "workflow_run_id"]),
    ),
)
def test_execution_policy_rejects_unimplemented_concurrency_modes(
    mode: str,
    identity_fields: list[str],
) -> None:
    decisions = _execution_decisions()
    concurrency = cast(dict[str, object], decisions["concurrency_policy"])
    concurrency["mode"] = mode
    concurrency["identity_fields"] = identity_fields

    with pytest.raises(PolicyArtifactError, match="must be shard_identity"):
        generate_execution_policy(decisions)


def test_policy_generator_and_verifier_clis_round_trip(tmp_path: Path) -> None:
    labeling_path = tmp_path / "labeling-policy.json"
    assert (
        cli_freeze(
            [
                "generate-labeling-policy",
                "cycle-1",
                "--judge-registry",
                str(JUDGE_REGISTRY),
                "--published-at",
                "2026-07-12T20:00:00Z",
                "--threshold-source",
                "Cycle 1 protocol decision, 2026-07-13",
                "--output",
                str(labeling_path),
            ]
        )
        == 0
    )
    assert (
        cli_freeze(
            [
                "verify-labeling-policy",
                "--artifact",
                str(labeling_path),
                "--judge-registry",
                str(JUDGE_REGISTRY),
                "--cycle-id",
                "cycle-1",
            ]
        )
        == 0
    )

    decisions_path = tmp_path / "execution-decisions.json"
    decisions_path.write_text(json.dumps(_execution_decisions()), encoding="utf-8")
    execution_path = tmp_path / "execution-policy.json"
    assert (
        cli_freeze(
            [
                "generate-execution-policy",
                "--decisions",
                str(decisions_path),
                "--output",
                str(execution_path),
            ]
        )
        == 0
    )
    assert (
        cli_freeze(
            [
                "verify-execution-policy",
                "--artifact",
                str(execution_path),
                "--cycle-id",
                "cycle-1",
            ]
        )
        == 0
    )


def test_acquisition_labeling_policy_is_byte_identical_and_never_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    acquisition_path = tmp_path / "acquisition-labeling-policy.json"
    freeze_path = tmp_path / "freeze-labeling-policy.json"
    arguments = [
        "cycle-1",
        "--judge-registry",
        str(JUDGE_REGISTRY),
        "--published-at",
        "2026-07-12T20:00:00Z",
        "--threshold-source",
        "Cycle 1 protocol decision, 2026-07-13",
    ]

    def forbidden_freeze_handler(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("acquisition policy generation invoked a freeze handler")

    monkeypatch.setattr(
        "legalforecast.protocol.freeze.cli_freeze", forbidden_freeze_handler
    )
    assert (
        main(
            [
                "acquisition",
                "generate-labeling-policy",
                *arguments,
                "--output",
                str(acquisition_path),
            ]
        )
        == 0
    )

    monkeypatch.undo()
    assert (
        cli_freeze(
            ["generate-labeling-policy", *arguments, "--output", str(freeze_path)]
        )
        == 0
    )
    assert acquisition_path.read_bytes() == freeze_path.read_bytes()

    assert (
        main(
            [
                "acquisition",
                "verify-labeling-policy",
                "--artifact",
                str(acquisition_path),
                "--judge-registry",
                str(JUDGE_REGISTRY),
                "--cycle-id",
                "cycle-1",
            ]
        )
        == 0
    )


def test_acquisition_labeling_policy_is_immutable(tmp_path: Path) -> None:
    output = tmp_path / "labeling-policy.json"
    base = [
        "acquisition",
        "generate-labeling-policy",
        "cycle-1",
        "--judge-registry",
        str(JUDGE_REGISTRY),
        "--published-at",
        "2026-07-12T20:00:00Z",
        "--threshold-source",
        "Cycle 1 protocol decision, 2026-07-13",
        "--output",
        str(output),
    ]

    assert main(base) == 0
    assert main(base) == 0
    changed = [
        (
            "different threshold source"
            if value == "Cycle 1 protocol decision, 2026-07-13"
            else value
        )
        for value in base
    ]
    assert main(changed) == 2


def _labeling_policy() -> dict[str, object]:
    return generate_labeling_policy(
        cycle_id="cycle-1",
        judge_registry_path=JUDGE_REGISTRY,
        published_at=datetime(2026, 7, 12, 20, tzinfo=UTC),
        threshold_source="Cycle 1 protocol decision, 2026-07-13",
    )


def _execution_decisions() -> dict[str, object]:
    return {
        "cycle_id": "cycle-1",
        "cycle_series": "official",
        "allow_no_baselines": True,
        "labeling_policy_sha256": "a" * 64,
        "cohort_policy_sha256": "b" * 64,
        "cohort_observation_manifest_sha256": "c" * 64,
        "lifecycle": {
            "labeling_policy_published_at": "2026-07-12T20:00:00Z",
            "production_labeling_started_at": "2026-07-13T00:00:00Z",
            "cohort_policy_published_at": "2026-07-12T19:00:00Z",
            "batch_002_started_at": "2026-07-12T21:00:00Z",
        },
        "shard_schedule": {
            "shard_count": 8,
            "dispatch_unit": "model_key_ablation",
            "shards": [
                {"model_key": f"fixture:model-{model}", "ablation": ablation}
                for model in ("a", "b", "c", "d")
                for ablation in ("full_packet", "metadata_only")
            ],
        },
        "concurrency_policy": {
            "mode": "shard_identity",
            "identity_fields": ["cycle_id", "model_key", "ablation"],
        },
        "receipt_policy": {
            "write_once_per_attempt": True,
            "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
            "result_commitment_required": True,
        },
        "attempt_policy": {
            "reservation_ledger_sha256": "d" * 64,
            "max_billable_attempts": 2,
        },
        "repeat_policy": {"case_ids": ["case-1", "case-2"], "count": 2},
        "cadence_counts": {
            "clean_motion_count_source": "frozen_manifest",
            "prediction_unit_count_source": "frozen_units",
            "reject_operator_mismatch": True,
        },
    }
