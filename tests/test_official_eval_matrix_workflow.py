from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/official-eval-matrix.yaml").read_text(
    encoding="utf-8"
)


def test_official_eval_matrix_workflow_is_manual_and_protected() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "Official evaluation is allowed only from refs/heads/main." in WORKFLOW
    for input_name in (
        "cycle_id:",
        "run_input_manifest_uri:",
        "ablation:",
        "model_registry_uri:",
        "model_keys:",
        "max_parallel:",
        "dry_run:",
        "artifact_retention_days:",
    ):
        assert input_name in WORKFLOW
    assert "solver_id:" not in WORKFLOW
    assert "mock_output:" not in WORKFLOW


def test_official_eval_matrix_workflow_builds_bounded_case_matrix() -> None:
    assert "matrix: ${{ fromJSON(needs.build-matrix.outputs.matrix) }}" in WORKFLOW
    assert (
        "max-parallel: ${{ fromJSON(needs.build-matrix.outputs.max_parallel) }}"
        in WORKFLOW
    )
    assert "fail-fast: false" in WORKFLOW
    assert 'MATRIX_LIMIT: "256"' in WORKFLOW
    assert "duplicate packet row for ablation" in WORKFLOW
    assert "model_keys missing from registry" in WORKFLOW
    assert "run-input manifest produced an empty matrix" in WORKFLOW
    assert 'packet_object_key.startswith("model-packets/")' in WORKFLOW
    assert '"model_key": model_key' in WORKFLOW
    assert '"model_key_slug": re.sub' in WORKFLOW
    assert "model_count: ${{ steps.matrix.outputs.model_count }}" in WORKFLOW


def test_official_eval_matrix_workflow_uses_oidc_only_in_protected_jobs() -> None:
    assert WORKFLOW.count("id-token: write") == 2
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in WORKFLOW
    assert (
        "aws-actions/configure-aws-credentials@00943011d9042930efac3dcd3a170e4273319bc8"
        in WORKFLOW
    )
    assert "role-session-name: lfb-official-matrix-${{ github.run_id }}" in WORKFLOW
    assert (
        "role-session-name: lfb-official-case-${{ github.run_id }}-${{ "
        "strategy.job-index }}" in WORKFLOW
    )


def test_official_eval_matrix_workflow_invokes_isolated_runner_once_per_row() -> None:
    assert "uv run legalforecast eval run-case" in WORKFLOW
    assert 'run_input_manifest_for_cli="${RUN_INPUT_MANIFEST_URI}"' in WORKFLOW
    assert 'model_registry_for_cli="${MODEL_REGISTRY_URI}"' in WORKFLOW
    assert (
        'run_input_manifest_for_cli="s3://${LFB_RESULTS_BUCKET}/${RUN_INPUT_MANIFEST_URI}"'
        in WORKFLOW
    )
    assert (
        'model_registry_for_cli="s3://${LFB_RESULTS_BUCKET}/${MODEL_REGISTRY_URI}"'
        in WORKFLOW
    )
    assert '--manifest "${run_input_manifest_for_cli}"' in WORKFLOW
    assert '--packet-store-root "s3://${LFB_PACKET_BUCKET}"' in WORKFLOW
    assert '--results-store-root "s3://${LFB_RESULTS_BUCKET}"' in WORKFLOW
    assert '--case-id "${CASE_ID}"' in WORKFLOW
    assert '--ablation "${ABLATION}"' in WORKFLOW
    assert "--backend live" in WORKFLOW
    assert '--model-registry "${model_registry_for_cli}"' in WORKFLOW
    assert '--model-key "${MODEL_KEY}"' in WORKFLOW
    assert "CASE_ID: ${{ matrix.case_id }}" in WORKFLOW
    assert "ABLATION: ${{ matrix.ablation }}" in WORKFLOW
    assert "MODEL_KEY: ${{ matrix.model_key }}" in WORKFLOW
    assert "MODEL_KEY_SLUG: ${{ matrix.model_key_slug }}" in WORKFLOW
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in WORKFLOW
    assert "ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}" in WORKFLOW
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in WORKFLOW
    assert "LFB_ANTHROPIC_RUNTIME: ${{ vars.LFB_ANTHROPIC_RUNTIME }}" in WORKFLOW
    assert (
        "LFB_ANTHROPIC_BEDROCK_MODEL_ID: "
        "${{ vars.LFB_ANTHROPIC_BEDROCK_MODEL_ID }}" in WORKFLOW
    )
    assert "bedrock|aws-bedrock|aws_bedrock)" in WORKFLOW
    assert "required_env+=(AWS_REGION)" in WORKFLOW


def test_official_eval_matrix_workflow_has_dry_run_and_retention_controls() -> None:
    assert "Dry run: would evaluate" in WORKFLOW
    assert "if: ${{ inputs.dry_run }}" in WORKFLOW
    assert "if: ${{ !inputs.dry_run }}" in WORKFLOW
    assert "actions/upload-artifact@v4" in WORKFLOW
    assert (
        "retention-days: ${{ "
        "fromJSON(needs.build-matrix.outputs.artifact_retention_days) }}" in WORKFLOW
    )


def test_official_eval_matrix_workflow_rejects_private_manifest_prefixes() -> None:
    for private_prefix in (
        "source-documents/*",
        "extracted-text/*",
        "audit-bundles/*",
        "withdrawn/*",
        "quarantine/*",
    ):
        assert private_prefix in WORKFLOW
    assert (
        "run_input_manifest_uri must not point at private packet prefixes." in WORKFLOW
    )
    assert "model_registry_uri must not point at private packet prefixes." in WORKFLOW
