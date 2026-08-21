from __future__ import annotations

import hashlib
import re
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "official-provider-cell.yaml").read_text(
    encoding="utf-8"
)
DISPATCHER = (ROOT / ".github" / "workflows" / "run-benchmark.yaml").read_text(
    encoding="utf-8"
)
S3_VALIDATION = (
    ROOT / ".github" / "workflows" / "official-s3-access-validation.yaml"
).read_text(encoding="utf-8")


def test_dispatcher_partitions_the_matrix_into_exact_provider_lanes() -> None:
    assert 'for provider in ("openai", "anthropic", "gemini")' in DISPATCHER
    assert 'if provider_lane(row["model_key"]) == provider' in DISPATCHER
    assert 'if provider in {"google", "gemini"}:' in DISPATCHER
    for provider in ("openai", "anthropic", "gemini"):
        assert f"  run-{provider}:" in DISPATCHER
        assert (
            f"matrix: ${{{{ fromJSON(needs.build-matrix.outputs.{provider}_matrix) }}}}"
            in DISPATCHER
        )
        assert "environment_name: legalforecastbench-official-eval" in DISPATCHER
        assert "uses: ./.github/workflows/official-provider-cell.yaml" in DISPATCHER


def test_dry_run_never_enters_a_provider_bearing_environment() -> None:
    boundaries = {
        "openai": "  run-anthropic:",
        "anthropic": "  run-gemini:",
        "gemini": "  finalize-shard:",
    }
    for provider, next_job in boundaries.items():
        job = DISPATCHER[
            DISPATCHER.index(f"  run-{provider}:") : DISPATCHER.index(next_job)
        ]
        assert (
            f"if: ${{{{ !inputs.dry_run && "
            f"needs.build-matrix.outputs.{provider}_count != '0' }}}}" in job
        )
        assert "environment_name: legalforecastbench-official-eval" in job
    build_matrix = DISPATCHER[
        DISPATCHER.index("  build-matrix:") : DISPATCHER.index("  run-openai:")
    ]
    assert "if: ${{ !inputs.dry_run" not in build_matrix
    assert "Build matrix JSON" in build_matrix


def test_case_id_slug_is_safe_deterministic_and_collision_resistant() -> None:
    function_source = (
        "def safe_case_id_slug"
        + DISPATCHER.split("          def safe_case_id_slug", maxsplit=1)[1].split(
            "          def packet_input_tokens", maxsplit=1
        )[0]
    )
    namespace: dict[str, object] = {"hashlib": hashlib, "re": re}
    exec(textwrap.dedent(function_source), namespace)
    slugger = cast(Callable[[str], str], namespace["safe_case_id_slug"])

    malicious = "../../Case: *?[artifact]\\name\n"
    slug = slugger(malicious)
    assert slug == slugger(malicious)
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}-[0-9a-f]{12}", slug)
    assert ".." not in slug
    assert not any(character in slug for character in "/\\:*?[]\n")
    assert slugger("same/prefix") != slugger("same:prefix")
    assert slugger("..") != slugger("/")
    matrix_row_source = DISPATCHER[
        DISPATCHER.index("                  include.append(") : DISPATCHER.index(
            "          limit = int(os.environ", DISPATCHER.index("include.append(")
        )
    ]
    assert '"case_id": case_id' in matrix_row_source
    assert '"case_id_slug": safe_case_id_slug(case_id)' in matrix_row_source
    assert "CASE_ID: ${{ inputs.case_id }}" in WORKFLOW
    assert "case_id_slug: ${{ matrix.case_id_slug }}" in DISPATCHER
    assert "CASE_ID_SLUG: ${{ inputs.case_id_slug }}" in WORKFLOW
    assert "${CASE_ID_SLUG}" in WORKFLOW
    assert "${CASE_ID}/" not in WORKFLOW


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
    ):
        assert pair in boundary
    assert "openai:openai:*" in boundary
    assert "anthropic:anthropic:*" in boundary
    assert "gemini:gemini:*|gemini:google:*" in boundary
    assert WORKFLOW.index("- name: Validate provider-cell boundary") < WORKFLOW.index(
        "LFB_PROVIDER_API_KEY"
    )


def test_provider_secret_is_generic_step_scoped_and_never_inherited() -> None:
    assert WORKFLOW.count("secrets.OPENAI_API_KEY") == 1
    assert WORKFLOW.count("secrets.ANTHROPIC_API_KEY") == 1
    assert WORKFLOW.count("secrets.GEMINI_API_KEY") == 1
    assert "secrets: inherit" not in WORKFLOW
    assert "secrets: inherit" not in DISPATCHER
    assert "secrets.OPENAI_API_KEY" not in DISPATCHER
    assert "secrets.ANTHROPIC_API_KEY" not in DISPATCHER
    assert "secrets.GEMINI_API_KEY" not in DISPATCHER
    provider_step = WORKFLOW[
        WORKFLOW.index("- name: Run isolated case evaluation") : WORKFLOW.index(
            "- name: Finish per-case cycle mutation"
        )
    ]
    selector = (
        "LFB_PROVIDER_API_KEY: ${{ inputs.provider == 'openai' && "
        "secrets.OPENAI_API_KEY || inputs.provider == 'anthropic' && "
        '!contains(fromJSON(\'["bedrock","aws-bedrock","aws_bedrock"]\'), '
        "vars.LFB_ANTHROPIC_RUNTIME) && secrets.ANTHROPIC_API_KEY || "
        "inputs.provider == 'gemini' && secrets.GEMINI_API_KEY }}"
    )
    assert provider_step.count(selector) == 1
    assert "export OPENAI_API_KEY=" in provider_step
    assert "export ANTHROPIC_API_KEY=" in provider_step
    assert "export GEMINI_API_KEY=" in provider_step


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
    assert '--workflow-run-id "${GITHUB_RUN_ID}"' in WORKFLOW
    assert '--workflow-run-attempt "${GITHUB_RUN_ATTEMPT}"' in WORKFLOW
    begin = WORKFLOW.index("- name: Begin per-case cycle mutation")
    evaluate = WORKFLOW.index("- name: Run isolated case evaluation")
    finish = WORKFLOW.index("- name: Finish per-case cycle mutation")
    assert begin < evaluate < finish
    assert WORKFLOW.count("legalforecast.publication.cycle_closure") == 2
    assert 'writer_id="${GITHUB_RUN_ID}-case-${PROVIDER}-${CELL_INDEX}"' in WORKFLOW


def test_provider_cell_aws_session_covers_job_deadline() -> None:
    iam = (ROOT / "infra" / "official-eval" / "iam.tf").read_text(encoding="utf-8")
    assert "timeout-minutes: 55" in WORKFLOW
    assert "max_session_duration = 3600" in iam
    assert "role-duration-seconds:" not in WORKFLOW


def test_provider_cell_rejects_openai_repeat_samples_before_authority() -> None:
    boundary = WORKFLOW[
        WORKFLOW.index("- name: Validate provider-cell boundary") : WORKFLOW.index(
            "- name: Checkout trusted release"
        )
    ]
    assert "REPEAT_COUNT: ${{ inputs.repeat_count }}" in boundary
    assert "OpenAI repeat samples are not supported in one provider cell" in boundary
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


def test_provider_workflow_actions_are_immutable() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in references)


def test_official_workflow_actions_are_full_sha_pinned_with_provenance_comments() -> (
    None
):
    """Keep the exact three provider-smoke workflows immutable and reviewable."""

    for workflow_name, workflow in (
        ("run-benchmark.yaml", DISPATCHER),
        ("official-provider-cell.yaml", WORKFLOW),
        ("official-s3-access-validation.yaml", S3_VALIDATION),
    ):
        references = re.findall(
            r"^(?P<indent>\s*)uses:\s+(?P<action>[^@\s]+)@(?P<revision>[^\s#]+)"
            r"(?P<comment>\s+#\s+[^\n]+)?$",
            workflow,
            flags=re.MULTILINE,
        )
        assert references, workflow_name
        for reference in references:
            action = reference[1]
            revision = reference[2]
            comment = reference[3]
            if action.startswith("./"):
                continue
            assert re.fullmatch(r"[0-9a-f]{40}", revision), (
                workflow_name,
                action,
                revision,
            )
            assert comment.strip(), (workflow_name, action, revision)
