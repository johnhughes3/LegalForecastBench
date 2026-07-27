from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.labeling.provider_journal import load_provider_cycle_caps
from legalforecast.protocol.freeze import cli_freeze
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    execution_policy_runtime_binding,
    execution_repeat_policy_sha256,
    generate_execution_policy,
    generate_labeling_policy,
    require_dispatch_policy_match,
    require_repeat_case_coverage,
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


def test_repeat_policy_count_is_independent_of_selected_case_count() -> None:
    decisions = _execution_decisions()
    repeat_policy = cast(dict[str, object], decisions["repeat_policy"])
    repeat_policy["count"] = 3

    artifact = generate_execution_policy(decisions)

    assert verify_execution_policy(artifact) == artifact["policy_sha256"]


@pytest.mark.parametrize("count", (0, -1, True))
def test_repeat_policy_rejects_nonpositive_or_boolean_count(count: object) -> None:
    decisions = _execution_decisions()
    repeat_policy = cast(dict[str, object], decisions["repeat_policy"])
    repeat_policy["count"] = count

    with pytest.raises(PolicyArtifactError, match=r"repeat_policy\.count"):
        generate_execution_policy(decisions)


def test_repeat_policy_identity_is_order_independent() -> None:
    first = generate_execution_policy(_execution_decisions())
    reversed_decisions = _execution_decisions()
    repeat_policy = cast(dict[str, object], reversed_decisions["repeat_policy"])
    repeat_policy["case_ids"] = ["case-2", "case-1"]
    second = generate_execution_policy(reversed_decisions)

    assert execution_repeat_policy_sha256(first) == execution_repeat_policy_sha256(
        second
    )


def test_repeat_preflight_rejects_case_missing_from_requested_ablation() -> None:
    packets = [
        {"case_id": "case-1", "ablation": "full_packet"},
        {"case_id": "case-1", "ablation": "metadata_only"},
        {"case_id": "case-2", "ablation": "full_packet"},
    ]

    with pytest.raises(PolicyArtifactError, match=r"case-2.*metadata_only"):
        require_repeat_case_coverage(
            packets,
            repeat_case_ids=("case-1", "case-2"),
            requested_ablations=("full_packet", "metadata_only"),
        )


def test_receipt_policy_requires_run_and_attempt_identity() -> None:
    decisions = _execution_decisions()
    receipt_policy = cast(dict[str, object], decisions["receipt_policy"])
    receipt_policy["identity_fields"] = ["workflow_run_id"]

    with pytest.raises(PolicyArtifactError, match="immutable attempt"):
        generate_execution_policy(decisions)


def test_execution_policy_freezes_remote_authority_caps_and_breaker() -> None:
    artifact = generate_execution_policy(_execution_decisions())

    attempts = artifact["policy"]["attempt_policy"]
    assert attempts == {
        "authority_backend": "dynamodb",
        "authority_resource_identity_sha256": "e" * 64,
        "failure_threshold": 3,
        "failure_window_seconds": 300,
        "ledger_scope_fields": ["cycle_id", "provider", "account"],
        "max_billable_attempts": 2,
        "provider_account_caps": [
            {
                "account": "primary",
                "cap_microusd": 1_000_000_000,
                "provider": "openai",
            }
        ],
        "reservation_ledger_sha256": "d" * 64,
    }


def test_execution_policy_runtime_binding_derives_frozen_provider_account() -> None:
    decisions = _execution_decisions()
    decisions["attempt_policy"]["provider_account_caps"].append(
        {
            "provider": "google",
            "account": "gemini-primary",
            "cap_microusd": 500_000_000,
        }
    )
    artifact = generate_execution_policy(decisions)

    binding = execution_policy_runtime_binding(
        artifact,
        execution_policy_sha256="f" * 64,
        provider="OpenAI",
    )

    assert binding == {
        "schema_version": "legalforecast.execution_policy_runtime_binding.v1",
        "execution_policy_sha256": "f" * 64,
        "reservation_ledger_sha256": "d" * 64,
        "authority_backend": "dynamodb",
        "authority_resource_identity_sha256": "e" * 64,
        "ledger_scope_fields": ["cycle_id", "provider", "account"],
        "provider": "openai",
        "account": "primary",
        "cap_microusd": 1_000_000_000,
        "max_billable_attempts": 2,
        "failure_threshold": 3,
        "failure_window_seconds": 300,
    }
    google_binding = execution_policy_runtime_binding(
        artifact,
        execution_policy_sha256="f" * 64,
        provider="Google",
    )
    assert google_binding["account"] == "gemini-primary"
    assert google_binding["cap_microusd"] == 500_000_000


def test_execution_policy_runtime_binding_rejects_uncommitted_account() -> None:
    artifact = generate_execution_policy(_execution_decisions())

    with pytest.raises(
        PolicyArtifactError,
        match="account does not match expected provider account",
    ):
        execution_policy_runtime_binding(
            artifact,
            execution_policy_sha256="f" * 64,
            provider="openai",
            account="other-account",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("authority_backend", "sqlite", "authority_backend"),
        (
            "ledger_scope_fields",
            ["cycle_id", "provider", "account", "stage"],
            "share one ledger",
        ),
        ("provider_account_caps", [], "must not be empty"),
        ("failure_threshold", 0, "positive integer"),
        ("failure_window_seconds", 0, "positive integer"),
    ),
)
def test_execution_policy_rejects_mutable_or_non_shared_attempt_controls(
    field: str,
    value: object,
    message: str,
) -> None:
    decisions = _execution_decisions()
    decisions["attempt_policy"][field] = value

    with pytest.raises(PolicyArtifactError, match=message):
        generate_execution_policy(decisions)


def test_execution_policy_rejects_duplicate_provider_account_caps() -> None:
    decisions = _execution_decisions()
    caps = decisions["attempt_policy"]["provider_account_caps"]
    caps.append(dict(caps[0]))

    with pytest.raises(PolicyArtifactError, match="provider more than once"):
        generate_execution_policy(decisions)


def test_execution_policy_rejects_multiple_accounts_for_one_provider() -> None:
    decisions = _execution_decisions()
    caps = decisions["attempt_policy"]["provider_account_caps"]
    caps.append(
        {
            "provider": "openai",
            "account": "secondary",
            "cap_microusd": 500_000_000,
        }
    )

    with pytest.raises(PolicyArtifactError, match="provider more than once"):
        generate_execution_policy(decisions)


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


def test_execution_policy_rejects_casefold_colliding_shard_groups() -> None:
    decisions = _execution_decisions()
    schedule = cast(dict[str, object], decisions["shard_schedule"])
    shards = cast(list[dict[str, str]], schedule["shards"])
    for shard in shards:
        if shard["model_key"] == "fixture:model-b":
            shard["model_key"] = "fixture:MODEL-A"

    with pytest.raises(PolicyArtifactError, match="case-insensitive concurrency"):
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
    caps_path = tmp_path / "provider-cycle-caps.json"
    caps_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "cycle-1",
                "spend_authority": {
                    "backend": "dynamodb",
                    "resource_identity_sha256": "e" * 64,
                    "ledger_scope_fields": ["cycle_id", "provider", "account"],
                    "max_billable_attempts": 2,
                    "failure_threshold": 3,
                    "failure_window_seconds": 300,
                },
                "providers": [
                    {
                        "provider": "openai",
                        "account": "primary",
                        "cycle_reservation_cap_usd": "1000.00",
                        "external_spend_limit_usd": "1000.00",
                        "external_limit_scope": "test account",
                        "external_limit_source": "test fixture",
                        "verified_at": "2026-07-12T16:00:00Z",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    decisions = _execution_decisions()
    caps = load_provider_cycle_caps(caps_path)
    decisions["attempt_policy"] = caps.execution_attempt_policy(
        hashlib.sha256(caps_path.read_bytes()).hexdigest()
    )
    decisions_path = tmp_path / "execution-decisions.json"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    execution_path = tmp_path / "execution-policy.json"
    assert (
        cli_freeze(
            [
                "generate-execution-policy",
                "--decisions",
                str(decisions_path),
                "--provider-cycle-caps",
                str(caps_path),
                "--output",
                str(execution_path),
            ]
        )
        == 0
    )
    mismatched_caps_path = tmp_path / "mismatched-provider-cycle-caps.json"
    mismatched_caps = json.loads(caps_path.read_text(encoding="utf-8"))
    mismatched_caps["providers"][0]["account"] = "different-account"
    mismatched_caps_path.write_text(json.dumps(mismatched_caps), encoding="utf-8")
    assert (
        cli_freeze(
            [
                "generate-execution-policy",
                "--decisions",
                str(decisions_path),
                "--provider-cycle-caps",
                str(mismatched_caps_path),
                "--output",
                str(tmp_path / "mismatched-execution-policy.json"),
            ]
        )
        == 1
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


def _labeling_policy() -> dict[str, Any]:
    return generate_labeling_policy(
        cycle_id="cycle-1",
        judge_registry_path=JUDGE_REGISTRY,
        published_at=datetime(2026, 7, 12, 20, tzinfo=UTC),
        threshold_source="Cycle 1 protocol decision, 2026-07-13",
    )


def _execution_decisions() -> dict[str, Any]:
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
            "authority_backend": "dynamodb",
            "authority_resource_identity_sha256": "e" * 64,
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "provider_account_caps": [
                {
                    "provider": "openai",
                    "account": "primary",
                    "cap_microusd": 1_000_000_000,
                }
            ],
            "reservation_ledger_sha256": "d" * 64,
            "max_billable_attempts": 2,
            "failure_threshold": 3,
            "failure_window_seconds": 300,
        },
        "repeat_policy": {"case_ids": ["case-1", "case-2"], "count": 2},
        "cadence_counts": {
            "clean_motion_count_source": "frozen_manifest",
            "prediction_unit_count_source": "frozen_units",
            "reject_operator_mismatch": True,
        },
    }
