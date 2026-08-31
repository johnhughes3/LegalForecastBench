"""Legacy Cycle 1 dispatch lane: provider-cell wiring and credential fences.

``run-benchmark.yaml`` is the locked-manifest lane (#1019) and its tests live in
``test_official_provider_workflow.py``.  This file covers the separate legacy
lane restored as ``run-benchmark-legacy.yaml`` (#1029), which the r4 Cycle 1
repair run dispatches and which alone still drives the composite
``official-provider-cell`` action.  Both files exist so the legacy lane retires
as one deletion -- workflow plus these tests -- when ``legalforecastbench-y7hk``
closes.  Nothing here asserts anything about the locked-manifest lane.
"""

from __future__ import annotations

import re
from pathlib import Path

from legalforecast.evals.corpus_manifest.cost_projector import (
    PROVIDER_LANES,
    provider_lane,
)
from legalforecast.evals.openai_compatible_provider import (
    DEEPINFRA_API_KEY_ENV,
    XAI_API_KEY_ENV,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT / ".github" / "actions" / "official-provider-cell" / "action.yml"
).read_text(encoding="utf-8")
DISPATCHER = (ROOT / ".github" / "workflows" / "run-benchmark-legacy.yaml").read_text(
    encoding="utf-8"
)


def test_dispatcher_partitions_the_matrix_into_exact_provider_lanes() -> None:
    assert PROVIDER_LANES == ("openai", "anthropic", "gemini")
    assert provider_lane("google:model") == "gemini"
    assert provider_lane("gemini:model") == "gemini"
    assert "issue_manifest_cost_projection_from_workflow_environment" in DISPATCHER
    for provider in ("openai", "anthropic", "gemini"):
        assert f"  run-{provider}:" in DISPATCHER
        assert (
            f"matrix: ${{{{ fromJSON(needs.build-matrix.outputs.{provider}_matrix) }}}}"
            in DISPATCHER
        )
        assert "environment_name: legalforecastbench-official-eval" in DISPATCHER
        assert "uses: ./.github/actions/official-provider-cell" in DISPATCHER


def test_supplementary_lanes_are_wired_but_inert_until_the_receipt_card_is_minted() -> (
    None
):
    """The xai and deepinfra cells exist; the projector cannot feed them yet.

    The key path -- action inputs, job, environment binding, secret -- is what
    this PR builds. The lane itself is not minted: ``PROVIDER_LANES`` is still
    the official three because a lane's ``<lane>_count`` / ``<lane>_matrix``
    fields belong to a cost-projection receipt card frozen under Cycle 1 change
    control (bead ``legalforecastbench-s9b9``). So build-matrix resolves these
    outputs to the empty string, and the guard must treat empty as "skip".

    Without the emptiness half, ``'' != '0'`` is true, the job starts, and
    ``fromJSON('')`` fails **every** official dispatch. That is the regression
    this test exists to prevent, so it is asserted rather than left to review.
    """

    for provider in ("xai", "deepinfra"):
        assert f"  run-{provider}:" in DISPATCHER
        assert (
            f"matrix: ${{{{ fromJSON(needs.build-matrix.outputs.{provider}_matrix) }}}}"
            in DISPATCHER
        )
        assert (
            f"{provider}_count: ${{{{ steps.matrix.outputs.{provider}_count }}}}"
            in DISPATCHER
        )
        assert (
            f"{provider}_matrix: ${{{{ steps.matrix.outputs.{provider}_matrix }}}}"
            in DISPATCHER
        )
        assert f"needs.build-matrix.outputs.{provider}_count != '' &&" in DISPATCHER
        assert f"needs.build-matrix.outputs.{provider}_count != '0' }}}}" in DISPATCHER
        # A lane that runs cells the fan-in does not wait for would publish a
        # shard receipt missing them, so both aggregators must gate on it.
        assert DISPATCHER.count(f"      - run-{provider}\n") == 2
        assert (
            DISPATCHER.count(
                f"(needs.run-{provider}.result == 'success' || "
                f"needs.run-{provider}.result == 'skipped')"
            )
            == 2
        )
    # The lane is genuinely not minted: if this flips, the guards above are no
    # longer describing reality and the emptiness half becomes dead weight.
    assert "xai" not in PROVIDER_LANES
    assert "deepinfra" not in PROVIDER_LANES


def test_dry_run_never_enters_a_provider_bearing_environment() -> None:
    boundaries = {
        "openai": "  run-anthropic:",
        "anthropic": "  run-gemini:",
        "gemini": "  run-xai:",
    }
    for provider, next_job in boundaries.items():
        job = DISPATCHER[
            DISPATCHER.index(f"  run-{provider}:") : DISPATCHER.index(next_job)
        ]
        assert (
            f"if: ${{{{ !inputs.dry_run && "
            f"needs.build-matrix.outputs.{provider}_count != '0' }}}}" in job
        )
        assert "environment: legalforecastbench-official-eval" in job
        assert "environment_name: legalforecastbench-official-eval" in job
    # The supplementary lanes carry the same dry-run and environment guards.
    # Their if-expression is folded across lines and carries the extra
    # emptiness test, so it is matched separately rather than by the loop.
    supplementary_boundaries = {
        "xai": "  run-deepinfra:",
        "deepinfra": "  finalize-shard:",
    }
    for provider, next_job in supplementary_boundaries.items():
        job = DISPATCHER[
            DISPATCHER.index(f"  run-{provider}:") : DISPATCHER.index(next_job)
        ]
        assert "${{ !inputs.dry_run && " in job
        assert f"needs.build-matrix.outputs.{provider}_count != '' &&" in job
        assert f"needs.build-matrix.outputs.{provider}_count != '0' }}}}" in job
        assert "environment: legalforecastbench-official-eval" in job
        assert "environment_name: legalforecastbench-official-eval" in job
    build_matrix = DISPATCHER[
        DISPATCHER.index("  build-matrix:") : DISPATCHER.index("  run-openai:")
    ]
    assert "if: ${{ !inputs.dry_run" not in build_matrix
    assert "Build matrix JSON" in build_matrix


def test_provider_environment_and_model_pair_are_closed_before_secrets() -> None:
    boundary = WORKFLOW[
        WORKFLOW.index("- name: Validate provider-cell boundary") : WORKFLOW.index(
            "- name: Checkout trusted release"
        )
    ]
    for pair in (
        "openai:legalforecastbench-official-eval",
        "anthropic:legalforecastbench-official-eval",
        "gemini:legalforecastbench-official-eval",
        "xai:legalforecastbench-official-eval",
        "deepinfra:legalforecastbench-official-eval",
    ):
        assert pair in boundary
    assert "openai:openai:*" in boundary
    assert "anthropic:anthropic:*" in boundary
    assert "gemini:gemini:*|gemini:google:*" in boundary
    # deepinfra:deepinfra:* covers every model on that shared host, Kimi K3 and
    # GLM 5.3 alike; the registry key's provider half is the boundary, not the
    # vendor namespace inside the model id.
    assert "xai:xai:*|deepinfra:deepinfra:*" in boundary
    assert WORKFLOW.index("- name: Validate provider-cell boundary") < WORKFLOW.index(
        "LFB_PROVIDER_API_KEY"
    )


def test_provider_secret_is_generic_step_scoped_and_never_inherited() -> None:
    assert "secrets." not in WORKFLOW
    assert "secrets: inherit" not in WORKFLOW
    assert "secrets: inherit" not in DISPATCHER
    openai_job = DISPATCHER[
        DISPATCHER.index("  run-openai:") : DISPATCHER.index("  run-anthropic:")
    ]
    anthropic_job = DISPATCHER[
        DISPATCHER.index("  run-anthropic:") : DISPATCHER.index("  run-gemini:")
    ]
    gemini_job = DISPATCHER[
        DISPATCHER.index("  run-gemini:") : DISPATCHER.index("  run-xai:")
    ]
    xai_job = DISPATCHER[
        DISPATCHER.index("  run-xai:") : DISPATCHER.index("  run-deepinfra:")
    ]
    deepinfra_job = DISPATCHER[
        DISPATCHER.index("  run-deepinfra:") : DISPATCHER.index("  finalize-shard:")
    ]
    assert openai_job.count("secrets.OPENAI_API_KEY") == 1
    assert openai_job.count("secrets.AI_GATEWAY_API_KEY") == 1
    assert "secrets.ANTHROPIC_API_KEY" not in openai_job
    assert "secrets.GEMINI_API_KEY" not in openai_job
    assert anthropic_job.count("secrets.ANTHROPIC_API_KEY") == 1
    assert "secrets.OPENAI_API_KEY" not in anthropic_job
    assert gemini_job.count("secrets.GEMINI_API_KEY") == 1
    assert "secrets.OPENAI_API_KEY" not in gemini_job
    assert xai_job.count("secrets.XAI_API_KEY") == 1
    assert deepinfra_job.count("secrets.DEEPINFRA_API_KEY") == 1
    # Each supplementary lane carries exactly its own provider's key and no
    # other lane's, so a mis-set secret cannot silently fund a second provider.
    for foreign in (
        "secrets.OPENAI_API_KEY",
        "secrets.ANTHROPIC_API_KEY",
        "secrets.GEMINI_API_KEY",
        "secrets.AI_GATEWAY_API_KEY",
    ):
        assert foreign not in xai_job
        assert foreign not in deepinfra_job
    assert "secrets.DEEPINFRA_API_KEY" not in xai_job
    assert "secrets.XAI_API_KEY" not in deepinfra_job
    assert "openai_api_key: ${{ secrets.OPENAI_API_KEY }}" in openai_job
    assert "ai_gateway_api_key: ${{ secrets.AI_GATEWAY_API_KEY }}" in openai_job
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in anthropic_job
    assert "gemini_api_key: ${{ secrets.GEMINI_API_KEY }}" in gemini_job
    assert "xai_api_key: ${{ secrets.XAI_API_KEY }}" in xai_job
    assert "deepinfra_api_key: ${{ secrets.DEEPINFRA_API_KEY }}" in deepinfra_job
    for job in (openai_job, anthropic_job, gemini_job, xai_job, deepinfra_job):
        assert not re.search(
            r"uses: ./\.github/actions/official-provider-cell\s+env:", job
        )
    assert "&& secrets." not in DISPATCHER
    credential_step = WORKFLOW[
        WORKFLOW.index("- name: Validate provider credential") : WORKFLOW.index(
            "- name: Configure AWS authority for cycle begin"
        )
    ]
    provider_step = WORKFLOW[
        WORKFLOW.index("- name: Run isolated case evaluation") : WORKFLOW.index(
            "- name: Finish per-case cycle mutation"
        )
    ]
    input_bindings = {
        "AI_GATEWAY_API_KEY": "ai_gateway_api_key",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "DEEPINFRA_API_KEY": "deepinfra_api_key",
        "GEMINI_API_KEY": "gemini_api_key",
        "OPENAI_API_KEY": "openai_api_key",
        "XAI_API_KEY": "xai_api_key",
    }
    for env_name, input_name in input_bindings.items():
        assert f'{input_name}:\n    required: false\n    default: ""' in WORKFLOW
        expected_binding = f"{env_name}: ${{{{ inputs.{input_name} }}}}"
        assert expected_binding in credential_step
        assert expected_binding in provider_step
    action_steps = re.findall(
        r"^  - name: .*?(?=^  - name: |\Z)", WORKFLOW, flags=re.MULTILINE | re.DOTALL
    )
    uses_steps = [
        step for step in action_steps if re.search(r"^    uses:", step, re.MULTILINE)
    ]
    assert uses_steps
    for step in uses_steps:
        assert not any(env_name in step for env_name in input_bindings)
    assert 'LFB_PROVIDER_API_KEY="${OPENAI_API_KEY:-}"' in credential_step
    assert 'LFB_PROVIDER_API_KEY="${OPENAI_API_KEY:-}"' in provider_step
    assert '"${LFB_PROVIDER_API_KEY}" == "false"' in credential_step
    assert '"${LFB_PROVIDER_API_KEY}" == "true"' in credential_step
    assert "before cycle mutation." in credential_step
    selection_step = WORKFLOW[
        WORKFLOW.index("- name: Select OpenAI transport") : WORKFLOW.index(
            "- name: Validate provider credential"
        )
    ]
    assert "secrets." not in selection_step
    assert "OPENAI_TRANSPORT_CONTRACT_VERSION" in selection_step
    assert "vercel-sol-flex-v1" in selection_step
    assert "Selected release does not support the Vercel Sol transport contract." in (
        selection_step
    )
    assert "inputs.model_key == 'openai:gpt-5.6-sol'" not in provider_step
    assert '"$(date -u +%F)" < "2026-09-19"' in provider_step
    assert "OpenAI transport selection expired before launch." in provider_step
    assert "export OPENAI_API_KEY=" in provider_step
    assert "export ANTHROPIC_API_KEY=" in provider_step
    assert "export GEMINI_API_KEY=" in provider_step
    # These two names are read by the OpenAI-compatible adapter's
    # XAI_API_KEY_ENV / DEEPINFRA_API_KEY_ENV constants. Exporting anything
    # else would leave the cell credential-less at request time rather than
    # failing here, so the exact spelling is pinned on both sides.
    assert f"export {XAI_API_KEY_ENV}=" in provider_step
    assert f"export {DEEPINFRA_API_KEY_ENV}=" in provider_step


def test_provider_cell_preserves_frozen_dispatch_and_cycle_bindings() -> None:
    assert (
        "official-dispatch-provenance-${{ github.run_id }}-"
        "${{ inputs.dispatch_run_attempt }}" in WORKFLOW
    )
    assert "downloaded execution policy differs from matrix commitment" in WORKFLOW
    assert "dispatch provenance execution-policy commitment differs" in WORKFLOW
    assert "--expected-execution-policy-sha256" in WORKFLOW
    assert "--provider-account" not in WORKFLOW
    assert "LFB_PROVIDER_ACCOUNT_ALIAS" not in WORKFLOW
    assert "freeze_bundle_sha256:" in WORKFLOW
    assert "FREEZE_BUNDLE_SHA256: ${{ inputs.freeze_bundle_sha256 }}" in WORKFLOW
    assert "freeze_bundle_sha256 must be lowercase SHA-256." in WORKFLOW
    assert (
        "EXPECTED_FREEZE_BUNDLE_SHA256: ${{ inputs.freeze_bundle_sha256 }}" in WORKFLOW
    )
    assert "expected_freeze_bundle_sha256=os.environ[" in WORKFLOW
    assert '--workflow-run-id "${GITHUB_RUN_ID}"' in WORKFLOW
    assert '--workflow-run-attempt "${GITHUB_RUN_ATTEMPT}"' in WORKFLOW
    transport = WORKFLOW.index("- name: Select OpenAI transport")
    credential = WORKFLOW.index("- name: Validate provider credential")
    begin = WORKFLOW.index("- name: Begin per-case cycle mutation")
    evaluate = WORKFLOW.index("- name: Run isolated case evaluation")
    finish = WORKFLOW.index("- name: Finish per-case cycle mutation")
    assert transport < credential < begin < evaluate < finish
    assert WORKFLOW.count("legalforecast.publication.cycle_closure") == 2
    assert 'writer_id="${GITHUB_RUN_ID}-case-${PROVIDER}-${CELL_INDEX}"' in WORKFLOW


def test_provider_cell_refreshes_one_hour_aws_sessions_for_three_hour_deadline() -> (
    None
):
    iam = (ROOT / "infra" / "official-eval" / "iam.tf").read_text(encoding="utf-8")
    timeout_match = re.search(
        r"(?m)^    timeout-minutes: (180)$",
        DISPATCHER[DISPATCHER.index("  run-openai:") :],
    )
    role_duration_matches = re.findall(
        r"(?m)^      role-duration-seconds: (\d+)$", WORKFLOW
    )
    cell_role = iam[
        iam.index('resource "aws_iam_role" "cell"') : iam.index(
            'resource "aws_iam_role_policy" "cell_storage"'
        )
    ]
    max_session_match = re.search(r"(?m)^  max_session_duration = (\d+)$", cell_role)

    assert timeout_match is not None
    assert max_session_match is not None
    timeout_seconds = int(timeout_match.group(1)) * 60
    role_duration_seconds = [int(value) for value in role_duration_matches]
    max_session_seconds = int(max_session_match.group(1))
    assert timeout_seconds == 10800
    assert role_duration_seconds == [3600, 3600, 3600]
    assert max_session_seconds == 3600
    assert WORKFLOW.count("aws-actions/configure-aws-credentials@") == 3
    assert "Configure AWS authority for cycle begin" in WORKFLOW
    assert "Refresh AWS authority for case evaluation" in WORKFLOW
    assert "Refresh AWS authority for cycle finish" in WORKFLOW


def test_provider_cell_rejects_repeat_samples_for_every_provider_before_authority() -> (
    None
):
    boundary = WORKFLOW[
        WORKFLOW.index("- name: Validate provider-cell boundary") : WORKFLOW.index(
            "- name: Checkout trusted release"
        )
    ]
    assert "REPEAT_COUNT: ${{ inputs.repeat_count }}" in boundary
    assert 'if ! [[ "${REPEAT_COUNT}" =~ ^[1-9][0-9]*$ ]]; then' in boundary
    assert "if (( REPEAT_COUNT > 1 )); then" in boundary
    assert "Repeat samples are not supported in one provider cell" in boundary
    assert '[[ "${PROVIDER}" == "openai" ]]' not in boundary
    assert "Configure packet-read and result-write AWS authority" not in boundary


def test_runs_transport_stays_private_without_weakening_receipt_finalization() -> None:
    stage = WORKFLOW[WORKFLOW.index("- name: Stage receipt-only completion artifact") :]
    assert "cell-completion.json accounting.jsonl metrics.json" in stage
    assert "runs.jsonl must remain only in private versioned S3" in stage
    assert "path: tmp/official-eval-completion" in stage
    assert "official-eval-completion-${{ inputs.provider }}" in stage
    assert "pattern: official-eval-completion-*" in DISPATCHER
    assert "legalforecast.publication.shard_receipt" in DISPATCHER
    receipt_source = (
        ROOT / "legalforecast" / "publication" / "shard_receipt.py"
    ).read_text(encoding="utf-8")
    assert '_RESULT_NAMES = ("accounting", "metrics", "runs")' in receipt_source
    assert "verify_committed_objects(receipt)" in receipt_source
    assert "--version-id" in receipt_source


def test_legacy_lane_binds_one_protected_environment_and_key_per_provider_cell() -> (
    None
):
    """Exact counts, carried over from the deleted matrix-workflow coverage.

    Five provider cells name the evaluation environment once each -- openai,
    anthropic, gemini, and the supplementary xai and deepinfra lanes.  All five
    bind the same environment deliberately: the supplementary lane is the
    official pipeline with an inverted anchor gate, so a second
    credential-bearing environment would only be a second boundary to keep
    correct.  The OIDC count is build-matrix, those five cells, finalize-shard,
    and aggregate-results, asserted exactly so a job that acquires OIDC without
    a protected environment fails here rather than at dispatch.
    """

    assert DISPATCHER.count("environment_name: legalforecastbench-official-eval") == 5
    assert DISPATCHER.count("id-token: write") == 8
    assert DISPATCHER.count("secrets.OPENAI_API_KEY") == 1
    assert DISPATCHER.count("secrets.AI_GATEWAY_API_KEY") == 1
    assert DISPATCHER.count("secrets.ANTHROPIC_API_KEY") == 1
    assert DISPATCHER.count("secrets.GEMINI_API_KEY") == 1
    assert DISPATCHER.count("secrets.XAI_API_KEY") == 1
    # One DeepInfra key serves both models hosted there (Kimi K3, GLM 5.3).
    assert DISPATCHER.count("secrets.DEEPINFRA_API_KEY") == 1


def test_legacy_lane_action_references_are_full_sha_pinned() -> None:
    for name, text in (
        ("run-benchmark-legacy.yaml", DISPATCHER),
        ("action.yml", WORKFLOW),
    ):
        references = re.findall(
            r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", text, flags=re.MULTILINE
        )
        assert references, name
        for action, revision in references:
            if action.startswith("./"):
                continue
            assert re.fullmatch(r"[0-9a-f]{40}", revision), (name, action, revision)
