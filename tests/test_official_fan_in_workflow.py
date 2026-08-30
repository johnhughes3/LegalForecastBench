from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/fan-in-publish.yaml")
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_fan_in_is_a_single_protected_provider_free_labels_boundary() -> None:
    assert "name: Protected Labels Fan In" in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW
    assert "workflow_run:" not in WORKFLOW
    assert "fan-in-results:" in WORKFLOW
    assert "environment: legalforecastbench-official-eval-fan-in" in WORKFLOW
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "run-case:" not in WORKFLOW
    assert "finalize-shard:" not in WORKFLOW
    for provider_secret in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
    ):
        assert provider_secret not in WORKFLOW


def test_dispatch_contract_has_exact_source_run_and_locked_release_inputs() -> None:
    for input_name in (
        "release_sha:",
        "cycle_id:",
        "forecast_run_id:",
        "forecast_run_attempt:",
        "manifest_uri:",
        "forecast_release_uri:",
        "artifact_root_uri:",
        "model_registry_uri:",
        "labels_release_uri:",
        "model_key:",
        "publish:",
    ):
        assert input_name in WORKFLOW
    for retired_input in (
        "source_dispatch_run_id:",
        "source_dispatch_runs_json:",
        "freeze_bundle_path:",
        "supplementary_artifacts_dir:",
        "accepted_attempt_map:",
        "official-dispatch-provenance",
        "lfb-run-inputs-frozen",
    ):
        assert retired_input not in WORKFLOW


def test_source_attempt_is_bound_to_the_exact_main_workflow_path() -> None:
    validation = WORKFLOW[
        WORKFLOW.index(
            "- name: Validate exact forecast workflow attempt"
        ) : WORKFLOW.index("- name: Download exact durable forecast result artifact")
    ]
    assert "GITHUB_TOKEN: ${{ github.token }}" in validation
    assert "GITHUB_REPOSITORY_NAME: ${{ github.repository }}" in validation
    for required in (
        'run.get("id") == run_id',
        'run.get("run_attempt") == attempt',
        'run.get("head_sha") == expected_sha',
        'run.get("head_branch") == "main"',
        'run.get("event") == "workflow_dispatch"',
        'run.get("path") == ".github/workflows/run-benchmark.yaml"',
        'run.get("status") == "completed"',
        'run.get("conclusion") == "success"',
    ):
        assert required in validation


def test_forecast_artifact_is_durable_complete_and_cannot_transport_labels() -> None:
    download = WORKFLOW[
        WORKFLOW.index(
            "- name: Download exact durable forecast result artifact"
        ) : WORKFLOW.index("- name: Configure protected fan-in storage access")
    ]
    assert "official-forecast-results-{run_id}-{attempt}" in download
    assert "archive_download_url" in download
    assert "expired" in download
    assert "ledger/ledger.sqlite3" in download
    for required in (
        "forecast-run.json",
        "run-manifest.json",
        "forecast-release.json",
        "model-registry.json",
        "run-summary.json",
        "receipts",
        "is_symlink",
        "duplicate path",
        "unsafe path",
        "must not contain labels",
    ):
        assert required in download
    assert "official-dispatch-provenance" not in download


def test_labels_are_fetched_only_after_public_and_source_checks() -> None:
    fetch_start = WORKFLOW.index("- name: Fetch and bind locked releases")
    validation_end = WORKFLOW.index("- name: Validate exact forecast workflow attempt")
    fetch = WORKFLOW[fetch_start:]
    assert "LABELS_RELEASE_URI" in fetch
    assert 'fetch_locked "${LABELS_RELEASE_URI}"' in fetch
    assert (
        "This is the only step in the repository that reads the label locator." in fetch
    )
    assert validation_end < fetch_start
    assert 'fetch_locked "${LABELS_RELEASE_URI}"' not in WORKFLOW[:fetch_start]


def test_run_identity_and_receipt_coverage_are_bound_before_scoring() -> None:
    validation = WORKFLOW[
        WORKFLOW.index(
            "- name: Validate run identity, model registry"
        ) : WORKFLOW.index(
            "- name: Validate releases and score complete forecast receipts"
        )
    ]
    for required in (
        "legalforecast.forecast-run.v1",
        "workflow_run_id",
        "workflow_run_attempt",
        "run_identity_sha256",
        "model_registry_sha256",
        "repeat_count",
        "PRAGMA integrity_check",
        "SELECT status FROM runs",
        "completed",
        "required_unit_ids",
        "seen_units",
        "no durable forecast receipts",
    ):
        assert required in validation
    scoring = WORKFLOW[
        WORKFLOW.index(
            "- name: Validate releases and score complete forecast receipts"
        ) :
    ]
    assert "--model-registry" in scoring
    assert "--expected-run-identity" in scoring
    assert "--expected-model-registry-sha256" in scoring
    assert "--labels-release" in scoring
    assert "--frozen-model-registry" in scoring


def test_publish_is_create_once_and_uploads_only_sanitized_outputs() -> None:
    publish = WORKFLOW[WORKFLOW.index("- name: Publish verified report once") :]
    assert "inputs.publish" in publish
    assert "list-objects-v2" in publish
    assert "refusing to overwrite existing immutable report prefix" in publish
    assert "scores.json" in publish
    assert "unit-scores.jsonl" in publish
    assert "/tmp/lfb-report" in publish
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in publish
    assert "private" not in publish


def test_workflow_uses_immutable_action_pins_and_rejects_unsafe_locators() -> None:
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in WORKFLOW
    assert (
        "aws-actions/configure-aws-credentials@e6de054238d6b7531b4efff3b6587d9aade6a06c"
        in WORKFLOW
    )
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in WORKFLOW
    )
    assert '[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ ]]' in WORKFLOW
    assert 'git merge-base --is-ancestor "${RELEASE_SHA}" origin/main' in WORKFLOW
    assert "${locator}" in WORKFLOW
    assert "unsafe path" in WORKFLOW
    assert "artifact_root_uri must be a prefix ending in /" in WORKFLOW
    assert re.search(r"reports/\$\{CYCLE_ID\}/multi-ablation", WORKFLOW)
