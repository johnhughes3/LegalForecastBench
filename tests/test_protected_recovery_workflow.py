"""Workflow fences for protected benchmark recovery and native reruns."""

import os
import subprocess
import textwrap
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_PATH = ROOT / ".github/workflows/recover-benchmark.yaml"
RUN_PATH = ROOT / ".github/workflows/run-benchmark.yaml"
RECOVERY = RECOVERY_PATH.read_text(encoding="utf-8")
RUN = RUN_PATH.read_text(encoding="utf-8")


def test_recovery_workflow_keeps_public_command_contract() -> None:
    for name in (
        "source_run_id",
        "source_run_attempt",
        "ref",
        "max_parallel",
        "execute",
    ):
        assert f"      {name}:\n" in RECOVERY
    assert "        default: main\n" in RECOVERY
    assert '        default: "8"\n' in RECOVERY
    assert "        default: false\n" in RECOVERY
    assert (
        "run-name: Recover benchmark ${{ inputs.source_run_id }} attempt "
        "${{ inputs.source_run_attempt }}"
    ) in RECOVERY
    assert "  cancel-in-progress: false" in RECOVERY
    assert "official-benchmark-recovery-${{ inputs.source_run_id }}-" in RECOVERY


def test_recovery_uses_existing_authority_without_provider_keys() -> None:
    assert "    environment: legalforecastbench-official-eval" in RECOVERY
    assert "      actions: write\n" in RECOVERY
    assert "      contents: read\n" in RECOVERY
    assert "      id-token: write\n" in RECOVERY
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in RECOVERY
    assert "LFB_PROVIDER_AUTHORITY_TABLE" in RECOVERY
    assert "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256" in RECOVERY
    assert "OPENAI_API_KEY" not in RECOVERY
    assert "ANTHROPIC_API_KEY" not in RECOVERY
    assert "GOOGLE_API_KEY" not in RECOVERY


def test_recovery_persists_plan_and_result_before_dispatch() -> None:
    plan = RECOVERY.index("Persist protected recovery plan before writes")
    apply = RECOVERY.index("Apply idempotent provider authority recovery")
    result = RECOVERY.index("Persist authority result before child dispatch")
    dispatch = RECOVERY.index("Dispatch canonical resumed benchmark")

    assert plan < apply < result < dispatch
    # Apply refreshes source-job cancellation proof before mutating spend state.
    assert "GH_TOKEN: ${{ github.token }}" in RECOVERY[apply:result]
    assert "protected-benchmark-recovery.py" in RECOVERY
    assert "--execute" in RECOVERY
    assert '"resume_sources"' in RECOVERY
    assert '"jev_summaries_uri": frozen.get("jev_summaries_uri", "")' in RECOVERY
    assert '"release_sha": os.environ["GITHUB_SHA"]' in RECOVERY
    assert "an exact child recovery run is already active" in RECOVERY
    assert "client.list_active_recovery_runs(repo)" in RECOVERY
    assert 'client.dispatch(repo, "run-benchmark.yaml", "main", inputs)' in RECOVERY
    assert 'for status in ("queued", "in_progress")' not in RECOVERY


def test_native_failed_job_rerun_reuses_successful_prepare_artifact_id() -> None:
    assert (
        "locked_inputs_artifact_id: ${{ steps.upload-inputs.outputs.artifact-id }}"
        in RUN
    )
    assert "id: upload-inputs" in RUN
    artifact_id_input = (
        "artifact-ids: ${{ needs.prepare-inputs.outputs.locked_inputs_artifact_id }}"
    )
    assert RUN.count(artifact_id_input) == 6
    assert (
        RUN.count(
            "name: locked-forecast-inputs-${{ github.run_id }}-attempt-"
            "${{ github.run_attempt }}"
        )
        == 1
    )


def test_recovered_child_title_binds_to_newest_resume_source() -> None:
    assert "Run benchmark recovery {0} attempt {1}" in RUN
    assert "fromJSON(inputs.resume_sources)[0].run_id" in RUN
    assert "fromJSON(inputs.resume_sources)[0].run_attempt" in RUN


def test_worker_restore_has_frozen_inputs_for_invalid_output_classification() -> None:
    workers = RUN.split("      - name: Restore prior completed cell state\n")
    assert len(workers) == 5
    for before, after in pairwise(workers):
        assert "      - name: Download outcome-blinded inputs\n" in before
        restore = after.split("      - name:", 1)[0]
        assert "LFB_FORECAST_INPUTS_ROOT: /tmp/lfb-forecast-inputs" in restore


def test_result_artifacts_request_github_maximum_retention() -> None:
    # Workflow artifacts are the only durable copy of per-unit predictions,
    # receipts, and transcripts; 90 days is GitHub's public-repository cap.
    workflows = ROOT / ".github/workflows"
    for name in (
        "run-benchmark.yaml",
        "fan-in-publish.yaml",
        "score-terminal-release.yaml",
    ):
        text = (workflows / name).read_text(encoding="utf-8")
        start = text.index("      artifact_retention_days:\n")
        assert '        default: "90"\n' in text[start : start + 200], name
    assert RECOVERY.count("retention-days: 90\n") == 2
    assert "retention-days: 14" not in RECOVERY
    assert '"artifact_retention_days": "90",' in RECOVERY


def test_plan_upload_requires_actual_output_and_failure_refusal_always_runs() -> None:
    upload = RECOVERY.split(
        "      - name: Persist protected recovery plan before writes", 1
    )[1].split("      - name: Refuse blocked authority plan", 1)[0]
    assert "always() && steps.authority-plan.outputs.plan_available == 'true'" in upload
    refusal = RECOVERY.split("      - name: Refuse blocked authority plan", 1)[1].split(
        "      - name: Apply idempotent", 1
    )[0]
    assert "always() && steps.authority-plan.outcome != 'success'" in refusal


@pytest.mark.parametrize(
    "status,writes_plan", [(1, False), (0, False), (0, True), (2, True)]
)
def test_authority_planning_never_reports_success_without_output(
    tmp_path: Path,
    status: int,
    writes_plan: bool,
) -> None:
    section = RECOVERY.split(
        "      - name: Build read-only provider authority plan", 1
    )[1].split("      - name: Persist protected recovery plan", 1)[0]
    script = textwrap.dedent(section.split("        run: |\n", 1)[1])
    output_path = tmp_path / "plan.json"
    script = script.replace("/tmp/lfb-protected-recovery-plan.json", str(output_path))
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("#!/bin/sh\nprintf '%s\\n' 'gh version test'\n")
    fake_gh.chmod(0o755)
    fake_uv = tmp_path / "uv"
    write = f"printf '%s' '{{}}' > '{output_path}'\n" if writes_plan else ""
    fake_uv.write_text(f"#!/bin/sh\n{write}exit {status}\n")
    fake_uv.chmod(0o755)
    step_output = tmp_path / "outputs"
    step_output.touch()
    environment = dict(
        os.environ,
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        GITHUB_OUTPUT=str(step_output),
        LFB_AWS_REGION="region",
        LFB_PROVIDER_AUTHORITY_TABLE="table",
        LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256="a" * 64,
    )
    result = subprocess.run(
        ["bash", "-c", script], env=environment, capture_output=True, text=True
    )
    assert result.returncode == (1 if status == 0 and not writes_plan else status)
    assert ("plan_available=true" in step_output.read_text()) is writes_plan
