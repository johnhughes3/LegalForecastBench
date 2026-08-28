from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")
PROVIDER_WORKFLOW = (
    ROOT / ".github/actions/official-provider-cell/action.yml"
).read_text(encoding="utf-8")
BUILD_MATRIX_JOB = WORKFLOW[
    WORKFLOW.index("  build-matrix:") : WORKFLOW.index("  run-openai:")
]
RUN_CASE_JOB = PROVIDER_WORKFLOW
FINALIZE_SHARD_JOB = WORKFLOW[
    WORKFLOW.index("  finalize-shard:") : WORKFLOW.index("  aggregate-results:")
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
        "shard_only:",
        "model_registry_uri:",
        "model_keys:",
        "freeze_bundle_path:",
        "prior_dispatches_json:",
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


def test_default_release_is_stable_across_workflow_reruns() -> None:
    validation = BUILD_MATRIX_JOB[
        BUILD_MATRIX_JOB.index(
            "- name: Validate dispatch request"
        ) : BUILD_MATRIX_JOB.index("- name: Configure AWS OIDC credentials")
    ]

    assert (
        'release_sha="$(git rev-parse --verify "${GITHUB_SHA}^{commit}")"' in validation
    )
    assert (
        'release_sha="$(git rev-parse --verify "origin/main^{commit}")"'
        not in validation
    )


def test_official_eval_matrix_workflow_builds_bounded_case_matrix() -> None:
    for provider in ("openai", "anthropic", "gemini"):
        assert (
            f"matrix: ${{{{ fromJSON(needs.build-matrix.outputs.{provider}_matrix) }}}}"
            in WORKFLOW
        )
        assert (
            f"{provider}_count: ${{{{ steps.matrix.outputs.{provider}_count }}}}"
            in WORKFLOW
        )
    assert (
        "max-parallel: ${{ fromJSON(needs.build-matrix.outputs.max_parallel) }}"
        in WORKFLOW
    )
    assert "fail-fast: false" in WORKFLOW
    assert "MATRIX_LIMIT: ${{ inputs.shard_only && '256' || '800' }}" in WORKFLOW
    assert "ABLATIONS: ${{ inputs.ablations }}" in WORKFLOW
    assert "SHARD_ONLY: ${{ inputs.shard_only }}" in WORKFLOW
    assert (
        "shard_only=true requires exactly one model-key and one ablation; "
        "each official shard must contain 100 rows under the 256-row limit." in WORKFLOW
    )
    assert '"matrix_row_count": 100' in WORKFLOW
    assert '"shard_matrix_row_count": 100' in WORKFLOW
    assert '"packet_count": 200' in WORKFLOW
    assert '"matrix_limit": 256' in WORKFLOW
    assert "issue_manifest_cost_projection_from_workflow_environment" in WORKFLOW
    assert "/tmp/lfb-manifest-cost-projection.json" in WORKFLOW
    assert "def packet_input_tokens" not in BUILD_MATRIX_JOB
    assert "def projected_cost_for_row" not in BUILD_MATRIX_JOB
    assert "model_count: ${{ steps.matrix.outputs.model_count }}" in WORKFLOW
    assert (
        "projected_model_cost_usd: ${{ steps.matrix.outputs.projected_model_cost_usd }}"
        in WORKFLOW
    )


def test_openai_repeat_samples_fail_before_provider_matrix_emission() -> None:
    projector = (
        ROOT / "legalforecast/evals/corpus_manifest/cost_projector.py"
    ).read_text(encoding="utf-8")
    assert "repeat_count > 1" in projector
    assert 'provider_lane(model_key) == "openai"' in projector
    assert "OpenAI repeat samples are not supported in one provider-cell shard" in (
        projector
    )


def test_cycle_mutation_intent_brackets_every_result_writer() -> None:
    assert "  begin-cycle-mutation:" not in WORKFLOW
    assert "  finish-cycle-mutation:" not in WORKFLOW
    run_begin = RUN_CASE_JOB.index("- name: Begin per-case cycle mutation")
    run_evaluate = RUN_CASE_JOB.index("- name: Run isolated case evaluation")
    run_finish = RUN_CASE_JOB.index("- name: Finish per-case cycle mutation")
    assert run_begin < run_evaluate < run_finish
    assert 'writer_id="${GITHUB_RUN_ID}-case-${PROVIDER}-${CELL_INDEX}"' in RUN_CASE_JOB
    assert "legalforecast.publication.cycle_closure begin" in RUN_CASE_JOB
    assert "legalforecast.publication.cycle_closure finish" in RUN_CASE_JOB
    assert RUN_CASE_JOB.count('--run-attempt "${GITHUB_RUN_ATTEMPT}"') == 2
    assert "--attempt" not in RUN_CASE_JOB
    assert "always() && inputs.dry_run != 'true'" in RUN_CASE_JOB
    assert "steps.begin_cycle_mutation.outcome == 'success'" in RUN_CASE_JOB
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in RUN_CASE_JOB

    receipt_begin = FINALIZE_SHARD_JOB.index(
        "- name: Begin shard-receipt cycle mutation"
    )
    receipt_write = FINALIZE_SHARD_JOB.index(
        "- name: Verify exact result versions and write receipt once"
    )
    receipt_finish = FINALIZE_SHARD_JOB.index(
        "- name: Finish shard-receipt cycle mutation"
    )
    assert receipt_begin < receipt_write < receipt_finish
    assert '"${GITHUB_RUN_ID}-finalize-shard"' in FINALIZE_SHARD_JOB
    assert "legalforecast.publication.cycle_closure begin" in FINALIZE_SHARD_JOB
    assert "legalforecast.publication.cycle_closure finish" in FINALIZE_SHARD_JOB
    assert FINALIZE_SHARD_JOB.count('--run-attempt "${GITHUB_RUN_ATTEMPT}"') == 2
    assert "--attempt" not in FINALIZE_SHARD_JOB
    assert "always() && steps.begin_shard_receipt_mutation.outcome == 'success'" in (
        FINALIZE_SHARD_JOB
    )


def test_shard_only_dispatch_gates_aggregation_and_records_provenance() -> None:
    provenance_step = BUILD_MATRIX_JOB[
        BUILD_MATRIX_JOB.index(
            "- name: Validate staged dispatch and build provenance"
        ) : BUILD_MATRIX_JOB.index("- name: Build matrix JSON")
    ]
    assert "SHARD_ONLY: ${{ inputs.shard_only }}" in BUILD_MATRIX_JOB
    shard_input = WORKFLOW.split("      shard_only:", maxsplit=1)[1].split(
        "      model_registry_uri:", maxsplit=1
    )[0]
    assert "default: false" in shard_input
    assert "SHARD_ONLY_INPUT: ${{ inputs.shard_only }}" in BUILD_MATRIX_JOB
    assert (
        "Non-dry-run official evaluation requires shard_only=true; "
        "canonical aggregation occurs only through immutable shard receipts "
        "and provider-free fan-in." in BUILD_MATRIX_JOB
    )
    assert "ABLATIONS: ${{ inputs.ablations }}" in BUILD_MATRIX_JOB
    assert 'ablation_args+=(--requested-ablation "${ablation}")' in BUILD_MATRIX_JOB
    assert (
        'repeat_case_args+=(--requested-repeat-case-id "${case_id}")'
        in BUILD_MATRIX_JOB
    )
    assert '--requested-repeat-count "${REPEAT_COUNT}"' in BUILD_MATRIX_JOB
    assert '"${repeat_case_args[@]}"' in BUILD_MATRIX_JOB
    assert 'key="${raw_key}"' in provenance_step
    assert 'ablation="${raw_ablation}"' in provenance_step
    assert 'key="${raw_key//[[:space:]]/}"' not in provenance_step
    assert 'ablation="${raw_ablation//[[:space:]]/}"' not in provenance_step
    assert "shard_args+=(--shard-only)" in BUILD_MATRIX_JOB
    assert '"${ablation_args[@]}"' in BUILD_MATRIX_JOB
    assert '"${shard_args[@]}"' in BUILD_MATRIX_JOB
    assert "!inputs.dry_run && !inputs.shard_only && always()" in AGGREGATE_RESULTS_JOB
    assert "RELEASE_SHA: ${{ steps.validate.outputs.release_sha }}" in provenance_step
    assert 'Path("/tmp/lfb-dispatch-release.json")' in provenance_step
    assert '"schema_version": "legalforecast.dispatch_release.v2"' in provenance_step
    assert '"workflow_run_id": os.environ["WORKFLOW_RUN_ID"]' in provenance_step
    assert (
        '"workflow_run_attempt": int(os.environ["WORKFLOW_RUN_ATTEMPT"])'
        in provenance_step
    )
    assert (
        "dispatch_run_attempt: ${{ steps.dispatch.outputs.workflow_run_attempt }}"
        in BUILD_MATRIX_JOB
    )
    assert (
        "workflow_run_attempt={os.environ['WORKFLOW_RUN_ATTEMPT']}" in provenance_step
    )
    assert '"release_sha": os.environ["RELEASE_SHA"]' in provenance_step
    assert "/tmp/lfb-dispatch-release.json" in BUILD_MATRIX_JOB


def test_finalize_shard_requires_every_matrix_cell_and_writes_once() -> None:
    for provider in ("openai", "anthropic", "gemini"):
        assert f"- run-{provider}" in FINALIZE_SHARD_JOB
        assert f"needs.run-{provider}.result == 'success'" in FINALIZE_SHARD_JOB
    assert "environment: legalforecastbench-official-eval-fan-in" in FINALIZE_SHARD_JOB
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in FINALIZE_SHARD_JOB
    assert "ANTHROPIC_API_KEY" not in FINALIZE_SHARD_JOB
    assert "OPENAI_API_KEY" not in FINALIZE_SHARD_JOB
    assert "pattern: official-eval-completion-*" in FINALIZE_SHARD_JOB
    assert (
        "name: official-dispatch-provenance-${{ github.run_id }}-"
        "${{ needs.build-matrix.outputs.dispatch_run_attempt }}" in FINALIZE_SHARD_JOB
    )
    assert "legalforecast.publication.shard_receipt" in FINALIZE_SHARD_JOB
    assert (
        "--run-input-manifest /tmp/lfb-shard-inputs/lfb-run-inputs-frozen.json"
        in FINALIZE_SHARD_JOB
    )
    assert "--frozen-manifest" not in FINALIZE_SHARD_JOB
    assert '--workflow-run-id "${GITHUB_RUN_ID}"' in FINALIZE_SHARD_JOB
    assert '--workflow-run-attempt "${GITHUB_RUN_ATTEMPT}"' in FINALIZE_SHARD_JOB
    assert (
        '--source-dispatch-run-attempt "${SOURCE_DISPATCH_RUN_ATTEMPT}"'
        in FINALIZE_SHARD_JOB
    )
    assert '--source-release-sha "${SOURCE_RELEASE_SHA}"' in FINALIZE_SHARD_JOB
    assert '--receipt-root "s3://${LFB_RESULTS_BUCKET}"' in FINALIZE_SHARD_JOB
    assert "if-no-files-found: error" in RUN_CASE_JOB
    assert "if: ${{ success() && inputs.dry_run != 'true' }}" in RUN_CASE_JOB
    provenance_source = (
        ROOT / "legalforecast" / "publication" / "dispatch_provenance.py"
    ).read_text(encoding="utf-8")
    assert "_load_execution_policy(" in provenance_source
    assert 'execution_policy["concurrency_policy"]' in provenance_source
    assert "_shard_concurrency_group_from_policy(" in provenance_source
    assert '"dispatch_mode": "shard_only"' in provenance_source
    assert '--workflow-ref "${WORKFLOW_REF}"' in BUILD_MATRIX_JOB
    assert '--concurrency-group "${CONCURRENCY_GROUP}"' in BUILD_MATRIX_JOB
    assert (
        "- name: Upload dispatch provenance\n"
        "        uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in BUILD_MATRIX_JOB
    )


def test_official_eval_actions_use_immutable_commit_pins() -> None:
    action_references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)",
        WORKFLOW + PROVIDER_WORKFLOW,
        flags=re.MULTILINE,
    )

    assert action_references
    assert all(
        re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in action_references
    )


def test_run_case_uses_transported_frozen_execution_policy() -> None:
    assert "execution_policy_path: ${{ steps.dispatch.outputs" not in BUILD_MATRIX_JOB
    assert 'output.write(f"execution_policy_path=' not in BUILD_MATRIX_JOB
    freeze_open = BUILD_MATRIX_JOB.index(
        'with open(os.environ["FREEZE_COMMITMENT_PATH"], encoding="utf-8")'
    )
    transport_policy = BUILD_MATRIX_JOB[
        BUILD_MATRIX_JOB.rindex(
            "python - <<'PY'", 0, freeze_open
        ) : BUILD_MATRIX_JOB.index("- name: Build matrix JSON")
    ]
    assert "from pathlib import Path" in transport_policy
    assert 'target = Path("/tmp/lfb-execution-policy.json")' in transport_policy
    assert "target.write_bytes(source.read_bytes())" in transport_policy
    assert (
        "/tmp/lfb-execution-policy.json"
        in BUILD_MATRIX_JOB[
            BUILD_MATRIX_JOB.index("- name: Upload dispatch provenance") :
        ]
    )

    checkout = RUN_CASE_JOB.index("- name: Checkout trusted release")
    download = RUN_CASE_JOB.index("- name: Download frozen dispatch inputs")
    evaluate = RUN_CASE_JOB.index("- name: Run isolated case evaluation")
    assert checkout < download < evaluate
    assert "if: ${{ inputs.dry_run != 'true' }}" in RUN_CASE_JOB[download:evaluate]
    assert (
        "name: official-dispatch-provenance-${{ github.run_id }}-"
        "${{ inputs.dispatch_run_attempt }}" in RUN_CASE_JOB[download:evaluate]
    )
    assert "path: /tmp/lfb-provider-cell-inputs" in RUN_CASE_JOB[download:evaluate]
    stable_policy_path = "/tmp/lfb-provider-cell-inputs/lfb-execution-policy.json"
    assert stable_policy_path in RUN_CASE_JOB
    assert (
        "EXPECTED_EXECUTION_POLICY_SHA256: "
        "${{ inputs.execution_policy_sha256 }}" in RUN_CASE_JOB
    )
    assert (
        '--expected-execution-policy-sha256 "${EXPECTED_EXECUTION_POLICY_SHA256}"'
        in RUN_CASE_JOB
    )
    assert "needs.build-matrix.outputs.execution_policy_path" not in WORKFLOW


def test_declared_shards_have_distinct_concurrency_groups() -> None:
    group_match = re.search(r"(?m)^  group: (?P<expression>.+)$", WORKFLOW)
    assert group_match is not None
    expression = group_match.group("expression")
    model_identity_expression = (
        "${{ inputs.shard_only && inputs.model_keys || 'full-matrix' }}"
    )
    ablation_identity_expression = (
        "${{ inputs.shard_only && inputs.ablations || 'full-matrix' }}"
    )
    assert "${{ inputs.cycle_id }}" in expression
    assert model_identity_expression in expression
    assert ablation_identity_expression in expression
    assert f"CONCURRENCY_GROUP: {expression}" in BUILD_MATRIX_JOB

    def render_group(model_key: str, ablation: str) -> str:
        return (
            expression.replace("${{ inputs.cycle_id }}", "cycle-1")
            .replace("${{ github.ref }}", "refs/heads/main")
            .replace(model_identity_expression, model_key)
            .replace(ablation_identity_expression, ablation)
        )

    groups = [
        render_group(f"fixture:model-{model}", ablation)
        for model in "abcd"
        for ablation in ("full_packet", "metadata_only")
    ]
    assert len(groups) == 8
    assert len({group.casefold() for group in groups}) == 8
    assert "cancel-in-progress: false" in WORKFLOW

    # GitHub concurrency groups are case-insensitive and retain only one pending
    # run. Model both running and replaceable pending slots; distinct frozen
    # shards must all start instead of replacing one another.
    running_run_by_group: dict[str, str] = {}
    pending_run_by_group: dict[str, str] = {}
    expected_run_ids = {f"run-{index}" for index in range(len(groups))}
    for index, group in enumerate(groups):
        group_key = group.casefold()
        run_id = f"run-{index}"
        if group_key not in running_run_by_group:
            running_run_by_group[group_key] = run_id
        else:
            pending_run_by_group[group_key] = run_id
    assert set(running_run_by_group.values()) == expected_run_ids
    assert pending_run_by_group == {}
    assert {running_run_by_group[groups[index].casefold()] for index in (0, 1)} == {
        "run-0",
        "run-1",
    }

    non_shard_group = (
        expression.replace("${{ inputs.cycle_id }}", "cycle-1")
        .replace("${{ github.ref }}", "refs/heads/main")
        .replace(model_identity_expression, "full-matrix")
        .replace(ablation_identity_expression, "full-matrix")
    )
    assert "fixture:model-a" not in non_shard_group
    assert non_shard_group.endswith("-full-matrix-full-matrix")


def test_amendment_dispatch_is_new_models_only_and_aggregation_unions_runs() -> None:
    provenance_step = BUILD_MATRIX_JOB.index(
        "- name: Validate staged dispatch and build provenance"
    )
    matrix_step = BUILD_MATRIX_JOB.index("- name: Build matrix JSON")
    assert provenance_step < matrix_step
    assert (
        "uv run python -m legalforecast.publication.dispatch_provenance"
        in BUILD_MATRIX_JOB
    )
    assert '--current-freeze-bundle "${FREEZE_COMMITMENT_PATH}"' in BUILD_MATRIX_JOB
    assert '--current-model-registry "${MODEL_REGISTRY_PATH}"' in BUILD_MATRIX_JOB
    assert 'model_key_args+=(--requested-model-key "${key}")' in BUILD_MATRIX_JOB
    assert '--prior-dispatches-json "${PRIOR_DISPATCHES_JSON}"' in BUILD_MATRIX_JOB
    assert "requested model keys must exactly equal models introduced" in (
        ROOT / "legalforecast" / "publication" / "dispatch_provenance.py"
    ).read_text(encoding="utf-8")

    durable_step = AGGREGATE_RESULTS_JOB.index(
        "- name: Download durable union of per-case artifacts"
    )
    aggregate_step = AGGREGATE_RESULTS_JOB.index("- name: Aggregate official bundle")
    assert durable_step < aggregate_step
    assert '"s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}/"' in AGGREGATE_RESULTS_JOB
    assert "--dispatch-provenance /tmp/lfb-dispatch-provenance.json" in (
        AGGREGATE_RESULTS_JOB
    )
    aggregate_script = AGGREGATE_RESULTS_JOB[aggregate_step:]
    assert "model_key_args" not in aggregate_script
    assert '"s3://${LFB_RESULTS_BUCKET}/reports/${CYCLE_ID}/multi-ablation/"' not in (
        aggregate_script
    )
    assert "withdraw" not in aggregate_script.lower()


def test_official_eval_matrix_workflow_freezes_labels_before_fanout() -> None:
    download_step = BUILD_MATRIX_JOB.index("- name: Download labels")
    freeze_step = BUILD_MATRIX_JOB.index(
        "- name: Freeze labels into run-input manifest"
    )
    verify_step = BUILD_MATRIX_JOB.index("- name: Verify labels frozen before scoring")
    matrix_step = BUILD_MATRIX_JOB.index("- name: Build matrix JSON")

    assert download_step < freeze_step < verify_step < matrix_step
    commitment_step = BUILD_MATRIX_JOB.index("- name: Verify pre-run freeze commitment")
    assert verify_step < commitment_step < matrix_step
    install_uv_step = BUILD_MATRIX_JOB.index("- name: Install uv")
    assert install_uv_step < commitment_step
    assert (
        "uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78"
        in BUILD_MATRIX_JOB
    )
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
    assert "uv run python -m legalforecast.protocol.freeze verify" in BUILD_MATRIX_JOB
    assert '--bundle "${FREEZE_COMMITMENT_PATH}"' in BUILD_MATRIX_JOB
    assert '--cycle-id "${CYCLE_ID}"' in BUILD_MATRIX_JOB
    assert '--root "${FREEZE_ROOT}"' in BUILD_MATRIX_JOB
    assert "Download immutable manifest-run bundle" in BUILD_MATRIX_JOB
    assert "manifest-run S3 prefix did not contain freeze.json" in BUILD_MATRIX_JOB
    assert 'find "${FREEZE_ROOT}/amendments"' in BUILD_MATRIX_JOB
    assert "--amendment-bundle" in BUILD_MATRIX_JOB
    assert "--candidate-freeze-bundle" in BUILD_MATRIX_JOB
    assert "id: verify_freeze" in BUILD_MATRIX_JOB
    assert (
        "freeze_bundle_sha256: ${{ steps.verify_freeze.outputs.freeze_bundle_sha256 }}"
        in BUILD_MATRIX_JOB
    )
    assert 'sha256sum "${FREEZE_COMMITMENT_PATH}"' in BUILD_MATRIX_JOB
    assert '--artifact-path "manifest=' not in BUILD_MATRIX_JOB
    assert (
        "RUN_INPUT_MANIFEST_PATH:" not in BUILD_MATRIX_JOB[commitment_step:matrix_step]
    )
    assert '--artifact-path "labels=${LABELS_PATH}"' in BUILD_MATRIX_JOB
    assert '--artifact-path "model_registry=${MODEL_REGISTRY_PATH}"' in BUILD_MATRIX_JOB
    assert 'amendment_args+=(--amendment-bundle "${bundle_path}")' in BUILD_MATRIX_JOB
    assert '"${amendment_args[@]}"' in BUILD_MATRIX_JOB


def test_official_eval_matrix_workflow_rebuilds_frozen_manifest_for_aggregate() -> None:
    download_step = AGGREGATE_RESULTS_JOB.index("- name: Download aggregate inputs")
    rebuild_step = AGGREGATE_RESULTS_JOB.index(
        "- name: Rebuild and verify frozen run-input manifest"
    )
    artifacts_step = AGGREGATE_RESULTS_JOB.index(
        "- name: Download durable union of per-case artifacts"
    )
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
    projector = (
        ROOT / "legalforecast/evals/corpus_manifest/cost_projector.py"
    ).read_text(encoding="utf-8")
    workflow_adapter = (
        ROOT / "legalforecast/evals/corpus_manifest/cost_projector_workflow.py"
    ).read_text(encoding="utf-8")
    assert (
        "max_projected_model_cost_usd must be a non-negative decimal amount."
        in WORKFLOW
    )
    assert (
        "MAX_PROJECTED_MODEL_COST_USD: "
        "${{ inputs.max_projected_model_cost_usd }}" in WORKFLOW
    )
    assert "PRICE_UNITS_PER_TOKEN" not in BUILD_MATRIX_JOB
    assert "def packet_input_tokens" not in BUILD_MATRIX_JOB
    assert "def projected_cost_for_row" not in BUILD_MATRIX_JOB
    assert "projected model cost $" in projector
    assert "required for live runs" in WORKFLOW
    assert "early-warning ceiling" in projector
    assert "not a provider " in workflow_adapter
    assert "or account cap" in workflow_adapter
    assert (
        "Non-dry-run official evaluation requires "
        "max_projected_model_cost_usd" in WORKFLOW
    )


def test_official_eval_matrix_transports_raw_freeze_commitment_to_each_cell() -> None:
    for provider in ("openai", "anthropic", "gemini"):
        start = WORKFLOW.index(f"  run-{provider}:")
        end = WORKFLOW.find("\n  run-", start + 1)
        if end == -1:
            end = WORKFLOW.index("\n  finalize-shard:", start)
        job = WORKFLOW[start:end]
        assert (
            "freeze_bundle_sha256: ${{ needs.build-matrix.outputs."
            "freeze_bundle_sha256 }}" in job
        )


def test_manifest_cost_projection_requires_immutable_manifest_run_uri() -> None:
    freeze_input = WORKFLOW.split("      freeze_bundle_path:", maxsplit=1)[1].split(
        "      prior_dispatches_json:", maxsplit=1
    )[0]
    assert "immutable" in freeze_input
    assert "manifest-run root" in freeze_input
    assert "committed manifests/*.freeze.json" not in freeze_input
    assert 'freeze_bundle_path="manifests/${CYCLE_ID_INPUT}.freeze.json"' not in (
        BUILD_MATRIX_JOB
    )
    assert (
        "freeze_bundle_path is required; use an immutable s3://.../cycle-1/"
        in BUILD_MATRIX_JOB
    )
    assert (
        "committed manifests/*.freeze.json paths do not provide an authenticated "
        "manifest-run root" in BUILD_MATRIX_JOB
    )
    assert 'freeze_root="/tmp/lfb-manifest-run"' in BUILD_MATRIX_JOB
    assert "issue_manifest_cost_projection_from_workflow_environment" in WORKFLOW


def test_official_eval_matrix_workflow_flags_long_context_surcharge_packets() -> None:
    projector = (
        ROOT / "legalforecast/evals/corpus_manifest/cost_projector.py"
    ).read_text(encoding="utf-8")
    workflow_adapter = (
        ROOT / "legalforecast/evals/corpus_manifest/cost_projector_workflow.py"
    ).read_text(encoding="utf-8")
    assert "LONG_CONTEXT_SURCHARGE_THRESHOLD_TOKENS" in projector
    assert "272_000" in projector
    assert "Long-context surcharge packet warning" in workflow_adapter
    assert "GITHUB_STEP_SUMMARY" in workflow_adapter
    assert "long_context_surcharge_packet_count" in WORKFLOW
    assert "long_context_surcharge_packets_json" in WORKFLOW


def test_official_eval_matrix_workflow_marks_repeat_sampling_subset() -> None:
    assert "repeat_count must be an integer from 1 through 10." in WORKFLOW
    assert "REPEAT_SAMPLE_CASE_IDS: ${{ inputs.repeat_sample_case_ids }}" in WORKFLOW
    assert "REPEAT_COUNT: ${{ inputs.repeat_count }}" in WORKFLOW
    assert "issue_manifest_cost_projection_from_workflow_environment" in WORKFLOW
    assert '--repeat-count "${REPEAT_COUNT}"' in RUN_CASE_JOB
    assert "repeat_count: ${{ matrix.repeat_count }}" in WORKFLOW


def test_official_eval_provider_credentials_are_isolated_by_environment() -> None:
    assert "DRY_RUN_INPUT: ${{ inputs.dry_run }}" in WORKFLOW
    assert "secrets." not in BUILD_MATRIX_JOB
    assert 'if [[ "${DRY_RUN_INPUT}" != "true"' in WORKFLOW
    assert "missing_provider_values" not in BUILD_MATRIX_JOB
    assert "LFB_PROVIDER_AUTHORITY_TABLE" not in BUILD_MATRIX_JOB
    assert "LFB_PROVIDER_ACCOUNT_ALIAS" not in BUILD_MATRIX_JOB
    assert "secrets." not in PROVIDER_WORKFLOW
    assert "secrets: inherit" not in WORKFLOW
    assert "secrets: inherit" not in PROVIDER_WORKFLOW
    assert WORKFLOW.count("environment: legalforecastbench-official-eval") >= 4
    assert WORKFLOW.count("environment_name: legalforecastbench-official-eval") == 3
    assert WORKFLOW.count("secrets.OPENAI_API_KEY") == 1
    assert WORKFLOW.count("secrets.AI_GATEWAY_API_KEY") == 1
    assert WORKFLOW.count("secrets.ANTHROPIC_API_KEY") == 1
    assert WORKFLOW.count("secrets.GEMINI_API_KEY") == 1
    assert "openai_api_key: ${{ secrets.OPENAI_API_KEY }}" in WORKFLOW
    assert "ai_gateway_api_key: ${{ secrets.AI_GATEWAY_API_KEY }}" in WORKFLOW
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in WORKFLOW
    assert "gemini_api_key: ${{ secrets.GEMINI_API_KEY }}" in WORKFLOW
    for env_name, input_name in (
        ("OPENAI_API_KEY", "openai_api_key"),
        ("AI_GATEWAY_API_KEY", "ai_gateway_api_key"),
        ("ANTHROPIC_API_KEY", "anthropic_api_key"),
        ("GEMINI_API_KEY", "gemini_api_key"),
    ):
        assert (
            PROVIDER_WORKFLOW.count(f"{env_name}: ${{{{ inputs.{input_name} }}}}") == 2
        )
    assert "&& secrets." not in WORKFLOW


def test_official_eval_matrix_workflow_uses_oidc_only_in_protected_jobs() -> None:
    assert WORKFLOW.count("id-token: write") == 6
    assert PROVIDER_WORKFLOW.count("id-token: write") == 0
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN: ${{ vars." in WORKFLOW
    assert "secrets.LFB_GITHUB_PACKET_READ_ROLE_ARN" not in WORKFLOW
    assert "secrets.LFB_GITHUB_PACKET_READ_ROLE_ARN" not in PROVIDER_WORKFLOW
    configure_aws_pins = re.findall(
        r"uses: aws-actions/configure-aws-credentials@([0-9a-f]{40})(?=\s|$)",
        WORKFLOW + PROVIDER_WORKFLOW,
    )
    assert (
        len(configure_aws_pins)
        == (WORKFLOW + PROVIDER_WORKFLOW).count(
            "uses: aws-actions/configure-aws-credentials@"
        )
        == 6
    )
    assert len(set(configure_aws_pins)) == 1
    assert "role-session-name: lfb-official-matrix-${{ github.run_id }}" in WORKFLOW
    for phase in ("begin", "eval", "finish"):
        assert (
            f"role-session-name: lfb-cell-{phase}-${{{{ inputs.provider }}}}-"
            "${{ github.run_id }}-${{ github.run_attempt }}" in PROVIDER_WORKFLOW
        )
    assert "role-session-name: lfb-official-aggregate-${{ github.run_id }}" in WORKFLOW
    assert (
        "role-session-name: lfb-finalize-shard-${{ github.run_id }}-${{ "
        "github.run_attempt }}" in WORKFLOW
    )


def test_official_eval_matrix_workflow_invokes_isolated_runner_once_per_row() -> None:
    assert "uv run legalforecast eval run-case" in PROVIDER_WORKFLOW
    assert "RUN_INPUT_MANIFEST_URI: ${{ inputs.run_input_manifest_uri }}" not in (
        RUN_CASE_JOB
    )
    assert "MODEL_REGISTRY_URI: ${{ inputs.model_registry_uri }}" not in RUN_CASE_JOB
    assert (
        "--manifest /tmp/lfb-provider-cell-inputs/lfb-run-inputs-frozen.json"
        in RUN_CASE_JOB
    )
    assert '--packet-store-root "s3://${LFB_PACKET_BUCKET}"' in RUN_CASE_JOB
    assert (
        '--results-store-root "s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}"'
        in RUN_CASE_JOB
    )
    assert '--case-id "${CASE_ID}"' in RUN_CASE_JOB
    assert '--ablation "${ABLATION}"' in RUN_CASE_JOB
    assert "--backend live" in RUN_CASE_JOB
    assert "--no-docket-tool" in RUN_CASE_JOB
    assert (
        "--model-registry /tmp/lfb-provider-cell-inputs/lfb-model-registry.json"
        in RUN_CASE_JOB
    )
    assert '--model-key "${MODEL_KEY}"' in RUN_CASE_JOB
    assert (
        '--expected-packet-object-key "${EXPECTED_PACKET_OBJECT_KEY}"' in RUN_CASE_JOB
    )
    assert '--expected-packet-sha256 "${EXPECTED_PACKET_SHA256}"' in RUN_CASE_JOB
    assert (
        '--provider-authority-table "${LFB_PROVIDER_AUTHORITY_TABLE}"' in RUN_CASE_JOB
    )
    assert "--provider-account" not in RUN_CASE_JOB
    assert '--provider-authority-region "${AWS_REGION}"' in RUN_CASE_JOB
    assert (
        "RESUME_EXISTING_RESULTS: ${{ inputs.resume_existing_results }}" in RUN_CASE_JOB
    )
    assert "resume_args+=(--resume-existing)" in RUN_CASE_JOB
    assert '"${resume_args[@]}"' in RUN_CASE_JOB
    assert "case_id: ${{ matrix.case_id }}" in WORKFLOW
    assert "ablation: ${{ matrix.ablation }}" in WORKFLOW
    assert "model_key: ${{ matrix.model_key }}" in WORKFLOW
    assert "model_key_slug: ${{ matrix.model_key_slug }}" in WORKFLOW
    assert "EXPECTED_PACKET_OBJECT_KEY: ${{ inputs.packet_object_key }}" in RUN_CASE_JOB
    assert "EXPECTED_PACKET_SHA256: ${{ inputs.packet_sha256 }}" in RUN_CASE_JOB
    assert "LFB_PROVIDER_AUTHORITY_TABLE: ${{ vars." in WORKFLOW
    assert "LFB_PROVIDER_ACCOUNT_ALIAS" not in RUN_CASE_JOB
    assert 'LFB_PROVIDER_API_KEY="${OPENAI_API_KEY:-}"' in RUN_CASE_JOB
    assert '"${LFB_PROVIDER_API_KEY}" == "false"' in RUN_CASE_JOB
    assert '"${LFB_PROVIDER_API_KEY}" == "true"' in RUN_CASE_JOB
    assert "- name: Validate provider credential" in RUN_CASE_JOB
    assert RUN_CASE_JOB.index(
        "- name: Validate provider credential"
    ) < RUN_CASE_JOB.index("- name: Begin per-case cycle mutation")
    assert "secrets.AI_GATEWAY_API_KEY" in WORKFLOW
    assert "OPENAI_TRANSPORT_CONTRACT_VERSION" in RUN_CASE_JOB
    assert "vercel-sol-flex-v1" in RUN_CASE_JOB
    assert '"$(date -u +%F)" < "2026-09-19"' in RUN_CASE_JOB
    assert "LFB_ANTHROPIC_RUNTIME: ${{ vars.LFB_ANTHROPIC_RUNTIME }}" in WORKFLOW
    assert (
        "LFB_ANTHROPIC_BEDROCK_MODEL_ID: "
        "${{ vars.LFB_ANTHROPIC_BEDROCK_MODEL_ID }}" in WORKFLOW
    )
    assert "bedrock|aws-bedrock|aws_bedrock)" in PROVIDER_WORKFLOW
    assert "export OPENAI_API_KEY=" in RUN_CASE_JOB
    assert "export ANTHROPIC_API_KEY=" in RUN_CASE_JOB
    assert "export GEMINI_API_KEY=" in RUN_CASE_JOB


def test_official_eval_matrix_workflow_aggregates_after_matrix_success() -> None:
    assert "aggregate-results:" in WORKFLOW
    for provider in ("openai", "anthropic", "gemini"):
        assert f"needs.run-{provider}.result == 'success'" in WORKFLOW
    assert (
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in WORKFLOW
    )
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
    # Secure-gate materializes YAML defaults into the dispatch payload. The
    # deployed run-benchmark input contract rejects an empty URI, so this
    # optional field must not declare default: "". Omitting the input still
    # leaves the GitHub Actions value empty.
    baseline_input = WORKFLOW[
        WORKFLOW.index("      baseline_training_examples_uri:") : WORKFLOW.index(
            "      elapsed_days:"
        )
    ]
    assert 'default: ""' not in baseline_input
    assert "required: false" in baseline_input
    assert (
        "optional_args+=(--baseline-training-examples /tmp/lfb-baseline-training.jsonl)"
        in WORKFLOW
    )
    assert '--deferred-ablation "judge_removed"' in WORKFLOW
    assert "--dispatch-provenance /tmp/lfb-dispatch-provenance.json" in WORKFLOW
    assert 'model_key_args+=(--model-key "${key}")' not in AGGREGATE_RESULTS_JOB
    assert (
        '--ablation "${ABLATION}"'
        not in WORKFLOW[WORKFLOW.index("aggregate-results:") :]
    )
    assert "Publish aggregate bundle to S3" not in AGGREGATE_RESULTS_JOB
    assert (
        '"s3://${LFB_RESULTS_BUCKET}/reports/${CYCLE_ID}/multi-ablation/"'
        not in AGGREGATE_RESULTS_JOB
    )
    assert (
        "official-aggregate-${{ inputs.cycle_id }}-"
        "${{ github.run_attempt }}-multi-ablation" in WORKFLOW
    )


def test_official_eval_matrix_workflow_has_dry_run_and_retention_controls() -> None:
    assert "Dry run: validated the frozen provider lane" in PROVIDER_WORKFLOW
    assert "if: ${{ inputs.dry_run == 'true' }}" in PROVIDER_WORKFLOW
    assert "if: ${{ inputs.dry_run != 'true' }}" in PROVIDER_WORKFLOW
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        in WORKFLOW + PROVIDER_WORKFLOW
    )
    assert "overwrite: true" not in WORKFLOW
    assert "retention-days: ${{ inputs.artifact_retention_days }}" in PROVIDER_WORKFLOW


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
