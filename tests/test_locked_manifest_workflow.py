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


def test_one_canonical_workflow_uses_locked_outcome_blinded_inputs() -> None:
    assert WORKFLOW_PATH.is_file()
    assert not LEGACY_WORKFLOW_PATH.exists()
    for input_name in (
        "manifest_uri:",
        "forecast_release_uri:",
        "artifact_root_uri:",
        "model_registry_uri:",
        "model_key:",
        "ceiling_microusd:",
        "repeat_count:",
    ):
        assert f"      {input_name}" in WORKFLOW
    assert "labels_release_uri" not in WORKFLOW
    assert "run_input_manifest_uri:" not in WORKFLOW
    assert "labels_uri:" not in WORKFLOW
    assert "run-benchmark-manifest.yaml" not in WORKFLOW


def test_prepare_materializes_only_forecast_release_declared_artifacts() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    assert "environment: legalforecastbench-official-eval-prepare-inputs" in prepare
    assert "LFB_GITHUB_PREPARE_INPUTS_ROLE_ARN" in prepare
    assert "LFB_AWS_REGION" in prepare
    assert "LFB_RESULTS_BUCKET" in prepare
    assert "ForecastRelease.model_validate" in prepare
    assert "declared: dict[str, tuple[str, int]]" in prepare
    assert "load_forecast_execution" in prepare
    assert "actual != set(declared)" in prepare
    assert "aws s3 sync" not in prepare
    assert "fetch_tree" not in prepare
    assert "cp -a" not in prepare
    assert "labels" not in prepare.lower()
    assert "Build dynamic logical-cell matrices" in prepare
    assert "model_registry" in prepare
    assert '"cell_id"' in prepare
    assert '"unit_id"' in prepare
    assert '"repeat_index"' in prepare
    assert '"ablation"' in prepare


def test_prepare_exports_real_provider_matrices_from_registry_and_release() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    for provider in ("openai", "anthropic", "gemini"):
        assert (
            f"{provider}_matrix: ${{{{ steps.matrix.outputs.{provider}_matrix }}}}"
            in prepare
        )
        assert (
            f"{provider}_count: ${{{{ steps.matrix.outputs.{provider}_count }}}}"
            in prepare
        )
    assert 'print(f"{provider}_matrix=' in prepare
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.openai_matrix) }}"
        in WORKFLOW
    )
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.anthropic_matrix) }}"
        in WORKFLOW
    )
    assert (
        "matrix: ${{ fromJSON(needs.prepare-inputs.outputs.gemini_matrix) }}"
        in WORKFLOW
    )
    assert "cell: [run]" not in WORKFLOW
    assert "model_key" in prepare
    assert "prediction_units" in prepare
    assert "derive_cell_id" in prepare
    assert "derive_run_identity_sha256" in prepare


def test_provider_jobs_are_secret_isolated_and_outcome_blinded() -> None:
    jobs = {
        "openai": _job("run-openai", "run-anthropic"),
        "anthropic": _job("run-anthropic", "run-gemini"),
        "gemini": _job("run-gemini"),
    }
    secrets = {
        "openai": "secrets.OPENAI_API_KEY",
        "anthropic": "secrets.ANTHROPIC_API_KEY",
        "gemini": "secrets.GEMINI_API_KEY",
    }
    forbidden_secrets = {
        "openai": ("secrets.ANTHROPIC_API_KEY", "secrets.GEMINI_API_KEY"),
        "anthropic": ("secrets.OPENAI_API_KEY", "secrets.GEMINI_API_KEY"),
        "gemini": ("secrets.OPENAI_API_KEY", "secrets.ANTHROPIC_API_KEY"),
    }
    for provider, job in jobs.items():
        assert job.count(secrets[provider]) == 1
        assert all(secret not in job for secret in forbidden_secrets[provider])
        assert "labels_release_uri" not in job
        assert "LABELS" not in job
        assert "--labels" not in job
        assert "--approval-reference" not in job
        assert "GITHUB_EVENT_PATH" not in job
        assert "cell_id" in job
        assert "unit_id" in job
        assert "repeat_index" in job
        assert "ablation" in job
        assert "if: ${{ always() }}" in job
        assert "ledger.sqlite3" in job
        assert "receipts" in job
        assert "if-no-files-found: error" in job
        assert "actions: read" in job
        assert "id-token: write" in job
        assert "PROVIDER_AUTHORITY_TABLE" in job
        assert (
            "max-parallel: ${{ fromJSON(needs.prepare-inputs.outputs.max_parallel) }}"
            in job
        )


def test_provider_jobs_execute_one_exact_cell_and_do_not_score() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        job = _job(name, next_name)
        assert '--cell-id "${CELL_ID}"' in job
        assert '--unit-id "${UNIT_ID}"' in job
        assert '--repeat-index "${REPEAT_INDEX}"' in job
        assert '--ablation "${ABLATION}"' in job
        assert "score" not in job.lower()
        assert "report" not in job.lower()
    assert "score-and-report:" not in WORKFLOW
    assert "legalforecast score" not in WORKFLOW
    assert "legalforecast report" not in WORKFLOW


def test_source_identity_concurrency_and_budget_gates_are_fail_closed() -> None:
    assert "concurrency:" in WORKFLOW
    assert "inputs.manifest_uri" in WORKFLOW
    assert "inputs.forecast_release_uri" in WORKFLOW
    assert "inputs.ceiling_microusd" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
    next_jobs = {
        "prepare-inputs": "run-openai",
        "run-openai": "run-anthropic",
        "run-anthropic": "run-gemini",
        "run-gemini": None,
    }
    for job_name, next_name in next_jobs.items():
        job = _job(job_name, next_name)
        # origin/main must be resolvable here, but not via a separate `git
        # fetch`: persist-credentials: false on the checkout step leaves no
        # token for a later step, so a bare fetch dies with "could not read
        # Username for 'https://github.com'" (legalforecastbench-2x9o).
        # fetch-depth: 0 makes the checkout itself fetch full history and
        # refs, including origin/main, under its own credentials.
        assert "fetch-depth: 0" in job
        assert "persist-credentials: false" in job
        assert "git fetch --no-tags --depth=1 origin main" not in job
        assert "git merge-base --is-ancestor origin/main HEAD" in job
        assert "git rev-parse HEAD" in job
    assert "CEILING_MICROUSD" in _job("prepare-inputs", "run-openai")
    assert '[[ "${CEILING_MICROUSD}" =~ ^[1-9][0-9]*$ ]]' in WORKFLOW
    assert '"max_parallel must be between 1 and 32"' in WORKFLOW
    assert (
        "repeat_count must be exactly 1 until repeated-sampling fan-in is supported"
        in WORKFLOW
    )


def test_prepare_rejects_repeats_before_any_provider_matrix() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    validate_start = prepare.index("Validate dispatch identity and bounded values")
    matrix_start = prepare.index("Build dynamic logical-cell matrices")
    assert validate_start < matrix_start
    validate = prepare[validate_start:matrix_start]
    matrix = prepare[matrix_start:]
    reject_message = (
        "repeat_count must be exactly 1 until repeated-sampling fan-in is supported"
    )
    assert '[[ "${REPEAT_COUNT}" == "1" ]]' in validate
    assert reject_message in validate
    assert '[[ "${PROVIDER}" == "openai" ]]' not in validate
    assert "if repeat_count != 1:" in matrix
    assert reject_message in matrix
    assert (
        'if [[ "${PROVIDER}" == "openai" ]] && (( REPEAT_COUNT > 1 ))' not in WORKFLOW
    )
    assert "OpenAI repeat samples are not supported" not in WORKFLOW


def test_restore_is_attempt_qualified_and_fail_closed() -> None:
    assert "GITHUB_RUN_ATTEMPT" in WORKFLOW
    assert (
        "locked-run-state-${{ matrix.provider }}-${{ matrix.cell_id_slug }}-"
        "attempt-${{ github.run_attempt }}" in WORKFLOW
    )
    assert "newest prior valid attempt" in WORKFLOW
    assert (
        "all prior state artifacts were corrupt; refusing a fresh duplicate call"
        in WORKFLOW
    )
    assert "gh api --paginate --slurp" in WORKFLOW
    assert (
        "prior state download/API failure; refusing a fresh duplicate call" in WORKFLOW
    )
    assert "if status != 0:" in WORKFLOW
    assert "CREATE TABLE runs(status TEXT NOT NULL)" in WORKFLOW
    assert "if-no-files-found: error" in WORKFLOW
    assert "continue-on-error" not in WORKFLOW
    assert "path: /tmp/lfb-run\n" not in WORKFLOW
    assert "/tmp/lfb-run/failure-summary.json" in WORKFLOW


def test_combined_forecast_result_matches_protected_fan_in_contract() -> None:
    combined = _job("persist-forecast-results")
    assert "needs: [prepare-inputs, run-openai, run-anthropic, run-gemini]" in combined
    assert "if: ${{ always() && needs.prepare-inputs.result == 'success' }}" in combined
    assert (
        "name: official-forecast-results-${{ github.run_id }}-${{ github.run_attempt }}"
        in combined
    )
    assert (
        "name: locked-forecast-inputs-${{ github.run_id }}-attempt-"
        "${{ github.run_attempt }}" in WORKFLOW
    )
    for path in (
        "forecast-run.json",
        "run-manifest.json",
        "forecast-release.json",
        "model-registry.json",
        "run-summary.json",
        "ledger/ledger.sqlite3",
        "receipts",
        "artifacts",
    ):
        assert f"/tmp/lfb-forecast-results/{path}" in combined
    assert "if-no-files-found: error" in combined
    assert "receipts/*.json" in combined or 'glob("*.json")' in combined
    assert "labels" not in combined.lower()
    assert "score" not in combined.lower()
    assert "report" not in combined.lower()


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
