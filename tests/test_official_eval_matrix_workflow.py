from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")
BUILD_MATRIX_JOB = WORKFLOW[
    WORKFLOW.index("  build-matrix:") : WORKFLOW.index("  run-case:")
]
RUN_CASE_JOB = WORKFLOW[
    WORKFLOW.index("  run-case:") : WORKFLOW.index("  aggregate-results:")
]
AGGREGATE_RESULTS_JOB = WORKFLOW[WORKFLOW.index("  aggregate-results:") :]


def test_official_eval_matrix_workflow_is_manual_and_protected() -> None:
    assert WORKFLOW.startswith("name: Run Benchmark\n")
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "Official evaluation is allowed only from refs/heads/main." in WORKFLOW
    for input_name in (
        "cycle_id:",
        "run_input_manifest_uri:",
        "labels_uri:",
        "ablations:",
        "model_registry_uri:",
        "model_keys:",
        "cycle_series:",
        "clean_motion_count:",
        "prediction_unit_count:",
        "elapsed_days:",
        "official_window_days:",
        "repeat_sample_case_ids:",
        "repeat_count:",
        "max_parallel:",
        "dry_run:",
        "resume_existing_results:",
        "artifact_retention_days:",
        "max_projected_model_cost_usd:",
    ):
        assert input_name in WORKFLOW
    assert "solver_id:" not in WORKFLOW
    assert "mock_output:" not in WORKFLOW


def test_official_eval_matrix_workflow_defaults_to_current_review_release() -> None:
    cycle_id = "pilot-2026-05-18-review-scored-12-corrected"

    assert f"default: {cycle_id}" in WORKFLOW
    assert f"default: manifests/{cycle_id}.run-inputs.json" in WORKFLOW
    assert f"default: manifests/{cycle_id}.labels.jsonl" in WORKFLOW
    assert f"default: manifests/{cycle_id}.model-registry.json" in WORKFLOW
    assert "default: full_packet,metadata_only" in WORKFLOW


def test_official_eval_matrix_workflow_builds_bounded_case_matrix() -> None:
    assert "run-benchmark-${{ inputs.cycle_id }}-${{ github.ref }}" in WORKFLOW
    assert "matrix: ${{ fromJSON(needs.build-matrix.outputs.matrix) }}" in WORKFLOW
    assert (
        "max-parallel: ${{ fromJSON(needs.build-matrix.outputs.max_parallel) }}"
        in WORKFLOW
    )
    assert "fail-fast: false" in WORKFLOW
    assert 'MATRIX_LIMIT: "256"' in WORKFLOW
    assert "ABLATIONS: ${{ inputs.ablations }}" in WORKFLOW
    assert "requested_ablations = [" in WORKFLOW
    assert "requested_ablation_set = set(requested_ablations)" in WORKFLOW
    assert "duplicate packet row for ablation" in WORKFLOW
    assert "model_keys missing from registry" in WORKFLOW
    assert "run-input manifest produced an empty matrix" in WORKFLOW
    assert 'packet_object_key.startswith("model-packets/")' in WORKFLOW
    assert 'packet.get("packet_sha256")' in BUILD_MATRIX_JOB
    assert '"packet_sha256": packet_sha256' in BUILD_MATRIX_JOB
    assert '"model_key": model_key' in WORKFLOW
    assert '"model_key_slug": re.sub' in WORKFLOW
    assert "model_count: ${{ steps.matrix.outputs.model_count }}" in WORKFLOW
    assert (
        "projected_model_cost_usd: ${{ steps.matrix.outputs.projected_model_cost_usd }}"
        in WORKFLOW
    )


def test_official_eval_matrix_workflow_freezes_labels_before_fanout() -> None:
    download_step = BUILD_MATRIX_JOB.index("- name: Download labels")
    freeze_step = BUILD_MATRIX_JOB.index(
        "- name: Freeze labels into run-input manifest"
    )
    verify_step = BUILD_MATRIX_JOB.index("- name: Verify labels frozen before scoring")
    matrix_step = BUILD_MATRIX_JOB.index("- name: Build matrix JSON")

    assert download_step < freeze_step < verify_step < matrix_step
    assert "uses: astral-sh/setup-uv" not in BUILD_MATRIX_JOB
    assert "legalforecast.publication.run_input_manifest" not in BUILD_MATRIX_JOB
    assert "id: freeze_labels" in BUILD_MATRIX_JOB
    assert 'frozen_manifest["labels_sha256"] = labels_sha256' in BUILD_MATRIX_JOB
    assert (
        "frozen_manifest_sha256: "
        "${{ steps.freeze_labels.outputs.frozen_manifest_sha256 }}" in BUILD_MATRIX_JOB
    )
    assert (
        "labels_sha256: ${{ steps.freeze_labels.outputs.labels_sha256 }}"
        in BUILD_MATRIX_JOB
    )
    assert 'output.write(f"labels_sha256={labels_sha256}\\n")' in BUILD_MATRIX_JOB
    assert 'f"frozen_manifest_sha256={frozen_manifest_sha256}\\n"' in BUILD_MATRIX_JOB
    assert "official-run-input-manifest" not in WORKFLOW


def test_official_eval_matrix_workflow_rebuilds_frozen_manifest_for_aggregate() -> None:
    download_step = AGGREGATE_RESULTS_JOB.index("- name: Download aggregate inputs")
    rebuild_step = AGGREGATE_RESULTS_JOB.index(
        "- name: Rebuild and verify frozen run-input manifest"
    )
    artifacts_step = AGGREGATE_RESULTS_JOB.index("- name: Download per-case artifacts")
    aggregate_step = AGGREGATE_RESULTS_JOB.index("- name: Aggregate official bundle")

    assert download_step < rebuild_step < artifacts_step < aggregate_step
    assert (
        "EXPECTED_LABELS_SHA256: "
        "${{ needs.build-matrix.outputs.labels_sha256 }}" in AGGREGATE_RESULTS_JOB
    )
    assert (
        "EXPECTED_FROZEN_MANIFEST_SHA256: "
        "${{ needs.build-matrix.outputs.frozen_manifest_sha256 }}"
        in AGGREGATE_RESULTS_JOB
    )
    assert (
        'download_input "${RUN_INPUT_MANIFEST_URI}" '
        "/tmp/lfb-run-inputs-original.json" in AGGREGATE_RESULTS_JOB
    )
    assert (
        "labels changed after matrix construction; refusing aggregation"
        in AGGREGATE_RESULTS_JOB
    )
    assert "if frozen_manifest_sha256 != expected_manifest:" in AGGREGATE_RESULTS_JOB
    assert (
        "run-input manifest changed after matrix construction" in AGGREGATE_RESULTS_JOB
    )
    assert "frozen_path.write_bytes(frozen_bytes)" in AGGREGATE_RESULTS_JOB
    assert "name: Download frozen run-input manifest" not in AGGREGATE_RESULTS_JOB
    assert "/tmp/lfb-frozen-run-input" not in AGGREGATE_RESULTS_JOB


def test_official_eval_matrix_workflow_preflights_projected_model_cost() -> None:
    assert (
        "max_projected_model_cost_usd must be a non-negative decimal amount."
        in WORKFLOW
    )
    assert (
        "MAX_PROJECTED_MODEL_COST_USD: "
        "${{ inputs.max_projected_model_cost_usd }}" in WORKFLOW
    )
    assert "PRICE_UNITS_PER_TOKEN = 1_000_000" in WORKFLOW
    assert "def packet_input_tokens(packet):" in WORKFLOW
    assert '"packet_size_bytes"' in WORKFLOW
    assert "def projected_cost_for_row" in WORKFLOW
    assert (
        "projected_model_cost += row_repeat_count * projected_cost_for_row" in WORKFLOW
    )
    assert "projected model cost $" in WORKFLOW
    assert (
        'output.write(f"projected_model_cost_usd={projected_model_cost:.6f}' in WORKFLOW
    )


def test_official_eval_matrix_workflow_marks_repeat_sampling_subset() -> None:
    assert "repeat_count must be an integer from 1 through 10." in WORKFLOW
    assert "REPEAT_SAMPLE_CASE_IDS: ${{ inputs.repeat_sample_case_ids }}" in WORKFLOW
    assert "REPEAT_COUNT: ${{ inputs.repeat_count }}" in WORKFLOW
    assert "repeat_sample_case_ids = {" in WORKFLOW
    assert (
        "row_repeat_count = (\n"
        "                  repeat_count if case_id in repeat_sample_case_ids else 1\n"
        "              )" in WORKFLOW
    )
    assert '"repeat_count": row_repeat_count' in WORKFLOW
    assert '--repeat-count "${REPEAT_COUNT}"' in WORKFLOW
    assert "REPEAT_COUNT: ${{ matrix.repeat_count }}" in WORKFLOW


def test_official_eval_matrix_workflow_preflights_live_provider_credentials() -> None:
    assert "DRY_RUN_INPUT: ${{ inputs.dry_run }}" in WORKFLOW
    assert "HAS_OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY != '' }}" in WORKFLOW
    assert "HAS_ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY != '' }}" in WORKFLOW
    assert "HAS_GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY != '' }}" in WORKFLOW
    assert 'if [[ "${DRY_RUN_INPUT}" != "true" ]]; then' in WORKFLOW
    assert "missing_provider_values=()" in WORKFLOW
    assert 'missing_provider_values+=("OPENAI_API_KEY")' in WORKFLOW
    assert 'missing_provider_values+=("GEMINI_API_KEY")' in WORKFLOW
    assert 'missing_provider_values+=("ANTHROPIC_API_KEY")' in WORKFLOW
    assert 'missing_provider_values+=("LFB_ANTHROPIC_BEDROCK_MODEL_ID")' in WORKFLOW
    assert (
        "Non-dry-run official evaluation is missing provider credentials/settings:"
        in WORKFLOW
    )


def test_official_eval_matrix_workflow_uses_oidc_only_in_protected_jobs() -> None:
    assert WORKFLOW.count("id-token: write") == 3
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN: ${{ vars." in WORKFLOW
    assert "secrets.LFB_GITHUB_PACKET_READ_ROLE_ARN" not in WORKFLOW
    assert (
        "aws-actions/configure-aws-credentials@d979d5b3a71173a29b74b5b88418bfda9437d885"
        in WORKFLOW
    )
    assert "role-session-name: lfb-official-matrix-${{ github.run_id }}" in WORKFLOW
    assert (
        "role-session-name: lfb-official-case-${{ github.run_id }}-${{ "
        "strategy.job-index }}" in WORKFLOW
    )
    assert "role-session-name: lfb-official-aggregate-${{ github.run_id }}" in WORKFLOW


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
    assert (
        '--results-store-root "s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}"'
        in WORKFLOW
    )
    assert '--case-id "${CASE_ID}"' in WORKFLOW
    assert '--ablation "${ABLATION}"' in WORKFLOW
    assert "--backend live" in WORKFLOW
    assert '--model-registry "${model_registry_for_cli}"' in WORKFLOW
    assert '--model-key "${MODEL_KEY}"' in WORKFLOW
    assert '--expected-packet-object-key "${EXPECTED_PACKET_OBJECT_KEY}"' in WORKFLOW
    assert '--expected-packet-sha256 "${EXPECTED_PACKET_SHA256}"' in WORKFLOW
    assert "RESUME_EXISTING_RESULTS: ${{ inputs.resume_existing_results }}" in WORKFLOW
    assert "resume_args+=(--resume-existing)" in WORKFLOW
    assert '"${resume_args[@]}"' in WORKFLOW
    assert "CASE_ID: ${{ matrix.case_id }}" in WORKFLOW
    assert "ABLATION: ${{ matrix.ablation }}" in WORKFLOW
    assert "MODEL_KEY: ${{ matrix.model_key }}" in WORKFLOW
    assert "MODEL_KEY_SLUG: ${{ matrix.model_key_slug }}" in WORKFLOW
    assert "EXPECTED_PACKET_OBJECT_KEY: ${{ matrix.packet_object_key }}" in RUN_CASE_JOB
    assert "EXPECTED_PACKET_SHA256: ${{ matrix.packet_sha256 }}" in RUN_CASE_JOB
    assert (
        "required_env=(LFB_PACKET_BUCKET LFB_RESULTS_BUCKET RUN_INPUT_MANIFEST_URI "
        "MODEL_REGISTRY_URI MODEL_KEY EXPECTED_PACKET_OBJECT_KEY "
        "EXPECTED_PACKET_SHA256)" in RUN_CASE_JOB
    )
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


def test_official_eval_matrix_workflow_aggregates_after_matrix_success() -> None:
    assert "aggregate-results:" in WORKFLOW
    assert "needs.run-case.result == 'success'" in WORKFLOW
    assert "actions/download-artifact@v7" in WORKFLOW
    assert "pattern: official-eval-*" in WORKFLOW
    assert "uv run python -m legalforecast.publication.official_aggregate" in WORKFLOW
    assert "--per-case-dir /tmp/lfb-per-case-artifacts" in WORKFLOW
    assert "/tmp/lfb-run-inputs-requested-ablations.json" in WORKFLOW
    assert 'manifest["model_packets"] = filtered_packets' in WORKFLOW
    assert (
        "--run-input-manifest /tmp/lfb-run-inputs-requested-ablations.json" in WORKFLOW
    )
    assert "--model-registry /tmp/lfb-model-registry.json" in WORKFLOW
    assert "--labels /tmp/lfb-labels.jsonl" in WORKFLOW
    # The baseline bypass is a dispatch-time choice, not a hardcoded flag: the
    # workflow declares an allow_no_baselines input (default true for run-1) and
    # the aggregate step only forwards --allow-no-baselines when that input is set.
    assert "allow_no_baselines:" in WORKFLOW
    assert "ALLOW_NO_BASELINES: ${{ inputs.allow_no_baselines }}" in WORKFLOW
    assert 'if [[ "${ALLOW_NO_BASELINES}" == "true" ]]; then' in WORKFLOW
    assert "optional_args+=(--allow-no-baselines)" in WORKFLOW
    # The hardcoded, unconditional flag must be gone.
    assert "\n            --allow-no-baselines \\\n" not in WORKFLOW
    # A frozen baseline corpus can be supplied at dispatch without a workflow edit.
    assert "baseline_training_examples_uri:" in WORKFLOW
    assert (
        "BASELINE_TRAINING_EXAMPLES_URI: ${{ inputs.baseline_training_examples_uri }}"
        in WORKFLOW
    )
    assert (
        "optional_args+=(--baseline-training-examples /tmp/lfb-baseline-training.jsonl)"
        in WORKFLOW
    )
    assert '--deferred-ablation "judge_removed"' in WORKFLOW
    assert 'model_key_args+=(--model-key "${key}")' in WORKFLOW
    assert (
        '--ablation "${ABLATION}"'
        not in WORKFLOW[WORKFLOW.index("aggregate-results:") :]
    )
    assert (
        "aws s3 sync \\\n            tmp/official-aggregate/public \\\n"
        '            "s3://${LFB_RESULTS_BUCKET}/reports/${CYCLE_ID}/multi-ablation/"'
        in WORKFLOW
    )
    assert "official-aggregate-${{ inputs.cycle_id }}-multi-ablation" in WORKFLOW


def test_official_eval_matrix_workflow_has_dry_run_and_retention_controls() -> None:
    assert "Dry run: would evaluate" in WORKFLOW
    assert "if: ${{ inputs.dry_run }}" in WORKFLOW
    assert "if: ${{ !inputs.dry_run }}" in WORKFLOW
    assert "actions/upload-artifact@v7" in WORKFLOW
    assert "overwrite: true" in WORKFLOW
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
    assert "labels_uri must not point at private packet prefixes." in WORKFLOW
    assert "model_registry_uri must not point at private packet prefixes." in WORKFLOW
