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
        "solver_id:",
        "max_parallel:",
        "dry_run:",
        "artifact_retention_days:",
    ):
        assert input_name in WORKFLOW


def test_official_eval_matrix_workflow_builds_bounded_case_matrix() -> None:
    assert "matrix: ${{ fromJSON(needs.build-matrix.outputs.matrix) }}" in WORKFLOW
    assert (
        "max-parallel: ${{ fromJSON(needs.build-matrix.outputs.max_parallel) }}"
        in WORKFLOW
    )
    assert "fail-fast: false" in WORKFLOW
    assert 'MATRIX_LIMIT: "256"' in WORKFLOW
    assert "duplicate case_id for ablation" in WORKFLOW
    assert "run-input manifest produced an empty matrix" in WORKFLOW
    assert 'packet_object_key.startswith("model-packets/")' in WORKFLOW


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
    assert '--manifest "${RUN_INPUT_MANIFEST_URI}"' in WORKFLOW
    assert '--packet-store-root "s3://${LFB_PACKET_BUCKET}"' in WORKFLOW
    assert '--results-store-root "s3://${LFB_RESULTS_BUCKET}"' in WORKFLOW
    assert '--case-id "${CASE_ID}"' in WORKFLOW
    assert '--ablation "${ABLATION}"' in WORKFLOW
    assert "CASE_ID: ${{ matrix.case_id }}" in WORKFLOW
    assert "ABLATION: ${{ matrix.ablation }}" in WORKFLOW


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
