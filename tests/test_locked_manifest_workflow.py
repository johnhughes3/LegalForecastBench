from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/run-benchmark.yaml"
LEGACY_WORKFLOW_PATH = ROOT / ".github/workflows/run-benchmark-manifest.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_one_canonical_workflow_uses_locked_public_contract_inputs() -> None:
    assert WORKFLOW_PATH.is_file()
    assert not LEGACY_WORKFLOW_PATH.exists()
    for input_name in (
        "manifest_uri:",
        "forecast_release_uri:",
        "labels_release_uri:",
        "artifact_root_uri:",
        "model_registry_uri:",
        "model_key:",
        "ceiling_microusd:",
    ):
        assert f"      {input_name}" in WORKFLOW
    for old_name in ("run_input_manifest_uri:", "labels_uri:", "model_keys:"):
        assert old_name not in WORKFLOW
    assert "run-benchmark-manifest.yaml" not in WORKFLOW


def test_prepare_materializes_only_forecast_release_declared_artifacts() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    assert "ForecastRelease.model_validate" in prepare
    assert "declared: dict[str, tuple[str, int]]" in prepare
    assert "load_forecast_execution" in prepare
    assert "actual != set(declared)" in prepare
    assert "aws s3 sync" not in prepare
    assert "fetch_tree" not in prepare
    assert "cp -a" not in prepare
    assert "--labels" not in prepare
    assert "labels-release" not in prepare


def test_provider_jobs_are_secret_isolated_and_outcome_blinded() -> None:
    jobs = {
        "openai": _job("run-openai", "run-anthropic"),
        "anthropic": _job("run-anthropic", "run-gemini"),
        "gemini": _job("run-gemini", "score-and-report"),
    }
    secrets = {
        "openai": "secrets.OPENAI_API_KEY",
        "anthropic": "secrets.ANTHROPIC_API_KEY",
        "gemini": "secrets.GEMINI_API_KEY",
    }
    for provider, job in jobs.items():
        assert job.count(secrets[provider]) == 1
        assert "secrets." in job
        assert "labels_release_uri" not in job
        assert "labels-release" not in job
        assert "LABELS" not in job
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in job
        assert "--labels" not in job
        assert "--artifact-root /tmp/lfb-forecast-inputs/artifacts" in job
        assert "--manifest /tmp/lfb-forecast-inputs/run-manifest.json" in job
        assert "--forecast /tmp/lfb-forecast-inputs/forecast-release.json" in job
        assert "--approval-reference" not in job
        assert "workflow-run-" not in job
        assert "if: ${{ always() }}" in job
        assert "ledger.sqlite3" in job
        assert "receipts" in job
        assert "max-parallel: ${{ fromJSON(inputs.max_parallel) }}" in job
    assert "secrets.OPENAI_API_KEY" not in jobs["anthropic"]
    assert "secrets.GEMINI_API_KEY" not in jobs["anthropic"]
    assert "secrets.OPENAI_API_KEY" not in jobs["gemini"]
    assert "secrets.ANTHROPIC_API_KEY" not in jobs["gemini"]


def test_source_identity_concurrency_and_budget_gates_are_fail_closed() -> None:
    assert "concurrency:" in WORKFLOW
    assert "inputs.manifest_uri" in WORKFLOW
    assert "inputs.forecast_release_uri" in WORKFLOW
    assert "inputs.model_key" in WORKFLOW
    assert "inputs.ceiling_microusd" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
    next_jobs = {
        "prepare-inputs": "run-openai",
        "run-openai": "run-anthropic",
        "run-anthropic": "run-gemini",
        "run-gemini": "score-and-report",
        "score-and-report": None,
    }
    for job_name, next_name in next_jobs.items():
        job = _job(job_name, next_name)
        assert "git fetch --no-tags --depth=1 origin main" in job
        assert "git merge-base --is-ancestor origin/main HEAD" in job
        assert "git rev-parse HEAD" in job
    assert "CEILING_MICROUSD" in _job("prepare-inputs", "run-openai")
    assert '[[ "${CEILING_MICROUSD}" =~ ^[1-9][0-9]*$ ]]' in WORKFLOW
    assert '"max_parallel must be between 1 and 8"' in WORKFLOW


def test_only_fan_in_reads_labels_and_publishes_score_report() -> None:
    fan_in = _job("score-and-report")
    assert "environment: legalforecastbench-official-eval-fan-in" in fan_in
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in fan_in
    assert "Fetch labels release only at fan-in" in fan_in
    assert "labels-release.json" in fan_in
    assert "--labels-release" in fan_in
    assert "legalforecast score" in fan_in
    assert "legalforecast report" in fan_in
    assert "if: ${{ always() }}" in fan_in
    for provider, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        provider_job = _job(provider, next_name)
        assert "labels-release" not in provider_job


def test_workflow_actions_are_immutable_sha_pins() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in references)
    assert all("#" in line for line in WORKFLOW.splitlines() if "uses:" in line)


def test_workflow_does_not_fabricate_approval_references() -> None:
    assert "approval-reference" not in WORKFLOW
    assert "workflow-run-" not in WORKFLOW
