from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/fan-in-publish.yaml")
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_fan_in_workflow_is_provider_free_and_role_scoped() -> None:
    assert "fan-in-results:" in WORKFLOW
    assert "run-case:" not in WORKFLOW
    assert "finalize-shard:" not in WORKFLOW
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in WORKFLOW
    assert "legalforecastbench-official-eval-fan-in" in WORKFLOW
    for provider_secret in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
    ):
        assert provider_secret not in WORKFLOW


def test_workflow_downloads_exact_cross_run_dispatch_artifact() -> None:
    assert "source_dispatch_run_id:" in WORKFLOW
    assert "source_dispatch_run_attempt:" in WORKFLOW
    assert "actions: read" in WORKFLOW
    assert (
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in WORKFLOW
    )
    assert (
        "official-dispatch-provenance-${{ inputs.source_dispatch_run_id }}-"
        "${{ inputs.source_dispatch_run_attempt }}" in WORKFLOW
    )
    assert "/tmp/lfb-source-dispatch/lfb-dispatch-release.json" in WORKFLOW
    assert "/tmp/lfb-source-dispatch/lfb-run-inputs-frozen.json" in WORKFLOW
    assert "--labels /tmp/lfb-source-dispatch/lfb-labels.jsonl" in WORKFLOW
    assert (
        "--model-registry /tmp/lfb-source-dispatch/lfb-model-registry.json" in WORKFLOW
    )
    assert '--source-dispatch-run-id "${SOURCE_DISPATCH_RUN_ID}"' in WORKFLOW
    assert '--source-dispatch-run-attempt "${SOURCE_DISPATCH_RUN_ATTEMPT}"' in WORKFLOW
    assert '--source-release-sha "${RELEASE_SHA}"' in WORKFLOW


def test_workflow_binds_source_dispatch_run_record_to_exact_attempt() -> None:
    validation = WORKFLOW[
        WORKFLOW.index(
            "- name: Validate source dispatch workflow run"
        ) : WORKFLOW.index("- name: Download exact frozen dispatch inputs")
    ]

    assert "GITHUB_TOKEN: ${{ github.token }}" in validation
    assert "GITHUB_REPOSITORY_NAME: ${{ github.repository }}" in validation
    assert 'run["id"] != int(source_dispatch_run_id)' in validation
    assert 'run["run_attempt"] != int(source_dispatch_run_attempt)' in validation
    assert 'f"attempts/{source_dispatch_run_attempt}"' in validation
    assert 'run["head_sha"] != expected_release_sha' in validation
    assert 'run["head_branch"] != "main"' in validation
    assert 'run["event"] != "workflow_dispatch"' in validation
    assert 'run["path"] != ".github/workflows/run-benchmark.yaml"' in validation
    assert 'run["status"] != "completed"' in validation
    assert 'run["conclusion"] != "success"' not in validation
    assert 'f"{attempt_path}/jobs?filter=all&per_page=100&page={page}"' in validation
    assert 'job.get("name") == "Build benchmark matrix"' in validation
    assert 'build_jobs[0].get("conclusion") != "success"' in validation
    assert "source dispatch workflow jobs response is incomplete" in validation


def test_workflow_binds_source_dispatch_artifact_to_requested_release() -> None:
    validation = WORKFLOW[
        WORKFLOW.index("- name: Validate frozen dispatch artifact") : WORKFLOW.index(
            "- name: Install uv"
        )
    ]

    assert "RELEASE_SHA: ${{ inputs.release_sha }}" in validation
    assert "SOURCE_DISPATCH_RUN_ID: ${{ inputs.source_dispatch_run_id }}" in validation
    assert (
        "SOURCE_DISPATCH_RUN_ATTEMPT: ${{ inputs.source_dispatch_run_attempt }}"
        in validation
    )
    assert '"legalforecast.dispatch_release.v2"' in validation
    assert 'release["workflow_run_id"] != source_dispatch_run_id' in validation
    assert (
        'release["workflow_run_attempt"] != source_dispatch_run_attempt' in validation
    )
    assert 'release["release_sha"] != expected_release_sha' in validation
    assert "source dispatch release provenance fields mismatch" in validation


def test_verify_only_and_publish_use_structurally_distinct_entrypoints() -> None:
    assert "legalforecast.publication.shard_fan_in \\\n" in WORKFLOW
    assert "--verify-only" in WORKFLOW
    assert "legalforecast.publication.shard_fan_in_publish \\\n" in WORKFLOW
    assert "--publish-root" in WORKFLOW
    assert '--publication-cycle-id "${CYCLE_ID}"' in WORKFLOW
    assert "aws s3 sync" not in WORKFLOW
    assert "per-case/${CYCLE_ID}" not in WORKFLOW


def test_publish_map_must_come_from_trusted_checkout() -> None:
    assert 'case "${ACCEPTED_MAP}" in' in WORKFLOW
    assert "manifests/*" in WORKFLOW
    assert "git ls-files --error-unmatch" in WORKFLOW
    assert "git diff --quiet HEAD" in WORKFLOW
    assert "git merge-base --is-ancestor" in WORKFLOW


def test_workflow_executes_only_the_requested_full_main_ancestor_sha() -> None:
    assert '[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ ]]' in WORKFLOW
    assert 'checked_out_sha="$(git rev-parse HEAD)"' in WORKFLOW
    assert '[[ "${checked_out_sha}" == "${RELEASE_SHA}" ]]' in WORKFLOW
    assert 'git merge-base --is-ancestor "${checked_out_sha}" origin/main' in WORKFLOW


def test_oidc_workflow_uses_immutable_action_pins_and_safe_shell_inputs() -> None:
    assert "astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78" in WORKFLOW
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in WORKFLOW
    )
    assert "uses: astral-sh/setup-uv@v" not in WORKFLOW
    assert "uses: actions/upload-artifact@v" not in WORKFLOW
    assert '[[ "${CYCLE_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]' in WORKFLOW
    assert "reports/${{ inputs.cycle_id }}" not in WORKFLOW
    assert "reports/${CYCLE_ID}/multi-ablation/" in WORKFLOW


def test_workflow_supplies_committed_freeze_ancestors() -> None:
    assert "find manifests -type f -name '*.freeze.json'" in WORKFLOW
    assert 'args+=(--amendment-bundle "${bundle_path}")' in WORKFLOW


def test_workflow_uploads_only_sanitized_verification_report() -> None:
    assert "tmp/official-fan-in/fan-in-report.json" in WORKFLOW
    assert "tmp/official-fan-in/aggregate" not in WORKFLOW
    assert "tmp/official-fan-in/per-case" not in WORKFLOW
