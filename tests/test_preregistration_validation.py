from __future__ import annotations

import json

from legalforecast.cli import main
from legalforecast.evals import ModelRegistry
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.protocol.preregistration import (
    artifact_hash_for_record,
    load_preregistration,
    validate_preregistration_record,
)
from legalforecast.selection import TrainingCutoffStatus


def test_valid_preregistration_record_passes_registry_and_hash_checks() -> None:
    record = _protocol_record()

    result = validate_preregistration_record(
        record,
        model_registry=_model_registry(),
        expected_hashes=record["frozen_artifacts"],
        template_text=_template_text(),
    )

    assert result.passed is True
    assert result.issues == ()


def test_missing_registration_and_freeze_hashes_fail_clearly() -> None:
    record = _protocol_record()
    record["public_registration"]["url"] = ""
    record["frozen_artifacts"]["labels_sha256"] = ""

    result = validate_preregistration_record(
        record,
        model_registry=_model_registry(),
        expected_hashes=_protocol_record()["frozen_artifacts"],
        template_text=_template_text(),
    )

    messages = [issue.to_record() for issue in result.issues]
    assert {
        "path": "public_registration.url",
        "message": "required field is missing or empty",
    } in messages
    assert {
        "path": "frozen_artifacts.labels_sha256",
        "message": "required field is missing or empty",
    } in messages
    assert any(
        issue["message"] == "must be a lowercase SHA-256 hash" for issue in messages
    )


def test_mismatched_model_registry_entry_and_artifact_hash_are_reported() -> None:
    record = _protocol_record()
    record["model_registry"]["models"] = ["example:missing-model"]
    record["frozen_artifacts"]["manifest_sha256"] = "0" * 64

    result = validate_preregistration_record(
        record,
        model_registry=_model_registry(),
        expected_hashes=_protocol_record()["frozen_artifacts"],
        template_text=_template_text(),
    )

    assert any(
        "model registry entry not found" in issue.message for issue in result.issues
    )
    assert any(
        issue.message == "hash does not match frozen artifact"
        for issue in result.issues
    )


def test_template_field_drift_is_detected() -> None:
    result = validate_preregistration_record(
        _protocol_record(),
        model_registry=_model_registry(),
        expected_hashes=_protocol_record()["frozen_artifacts"],
        template_text=_template_text().replace("Candidate manifest", "Candidate list"),
    )

    assert any(
        issue.path == "docs/preregistration_template.md" for issue in result.issues
    )


def test_json_and_yaml_preregistration_files_load_and_cli_fails_on_invalid(
    tmp_path,
) -> None:
    json_path = tmp_path / "cycle.preregistration.json"
    json_path.write_text(json.dumps(_protocol_record()), encoding="utf-8")
    yaml_path = tmp_path / "cycle.preregistration.yaml"
    yaml_path.write_text(
        """
cycle_id: cycle_2026_05
claim_level: official_descriptive
public_registration:
  provider: osf
  url: https://osf.io/abcd1/
  timestamp: 2026-05-14T12:00:00Z
freeze_timestamp: 2026-05-14T12:05:00Z
anchors:
  model_release: 2026-05-14T09:00:00Z
  decision_window_start: 2026-05-14
  decision_window_end: 2026-06-14
  candidate_source_provider: case.dev
metrics:
  primary: micro_brier
inference:
  method: paired_clustered_bootstrap
  bootstrap_replicates: 5000
model_registry:
  path: artifacts/models.json
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
frozen_artifacts:
  manifest_sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  units_sha256: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
  labels_sha256: dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
  prompt_sha256: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
  scorer_sha256: ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
  harness_sha256: 1111111111111111111111111111111111111111111111111111111111111111
""",
        encoding="utf-8",
    )
    invalid_path = tmp_path / "invalid.preregistration.json"
    invalid_path.write_text("{}", encoding="utf-8")

    assert load_preregistration(json_path)["cycle_id"] == "cycle_2026_05"
    assert load_preregistration(yaml_path)["anchors"]["candidate_source_provider"] == (
        "case.dev"
    )
    assert main(["validate-preregistration", str(invalid_path)]) == 1


def _protocol_record() -> dict[str, object]:
    hashes = {
        name: artifact_hash_for_record({"artifact": name})
        for name in (
            "manifest_sha256",
            "units_sha256",
            "labels_sha256",
            "prompt_sha256",
            "scorer_sha256",
            "harness_sha256",
        )
    }
    return {
        "cycle_id": "cycle_2026_05",
        "claim_level": "official_descriptive",
        "public_registration": {
            "provider": "osf",
            "url": "https://osf.io/abcd1/",
            "timestamp": "2026-05-14T12:00:00Z",
        },
        "freeze_timestamp": "2026-05-14T12:05:00Z",
        "anchors": {
            "model_release": "2026-05-14T09:00:00Z",
            "decision_window_start": "2026-05-14",
            "decision_window_end": "2026-06-14",
            "candidate_source_provider": "case.dev",
        },
        "eligibility_rules": ["post_release_decision"],
        "exclusion_rules": ["outcome_leakage"],
        "contamination_filters": ["related_case_publicity"],
        "unitization_rules": ["frozen_unit_repair_or_exclude"],
        "labeling_rules": ["first_written_disposition_lock"],
        "metrics": {"primary": "micro_brier"},
        "inference": {
            "method": "paired_clustered_bootstrap",
            "bootstrap_replicates": 5000,
        },
        "model_registry": {
            "path": "artifacts/models.json",
            "sha256": artifact_hash_for_record({"models": ["example:model-a"]}),
            "models": ["example:model-a"],
        },
        "frozen_artifacts": hashes,
    }


def _model_registry() -> ModelRegistry:
    return ModelRegistry(
        (
            ModelRegistryEntry.from_record(
                {
                    "provider": "example",
                    "model_id": "model-a",
                    "display_name": "Model A",
                    "model_version_or_snapshot": "2026-05-14",
                    "provider_training_cutoff_status": (
                        TrainingCutoffStatus.UNKNOWN.value
                    ),
                    "temperature": 0,
                    "top_p": 1,
                    "max_output_tokens": 4096,
                    "network_disabled": True,
                    "search_disabled": True,
                    "tool_policy": "no_tools",
                    "context_limit": 200000,
                    "pricing_source": "fixture",
                    "input_token_price": 0,
                    "output_token_price": 0,
                }
            ),
        )
    )


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
