"""Workflow fences for protected benchmark recovery and native reruns."""

from pathlib import Path

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
    assert "protected-benchmark-recovery.py" in RECOVERY
    assert "--execute" in RECOVERY
    assert '"resume_sources"' in RECOVERY
    assert '"release_sha": os.environ["GITHUB_SHA"]' in RECOVERY
    assert "an exact child recovery run is already active" in RECOVERY


def test_native_failed_job_rerun_reuses_successful_prepare_artifact_id() -> None:
    assert (
        "locked_inputs_artifact_id: ${{ steps.upload-inputs.outputs.artifact-id }}"
        in RUN
    )
    assert "id: upload-inputs" in RUN
    artifact_id_input = (
        "artifact-ids: ${{ needs.prepare-inputs.outputs.locked_inputs_artifact_id }}"
    )
    assert RUN.count(artifact_id_input) == 5
    assert (
        "name: locked-forecast-inputs-${{ github.run_id }}-attempt-"
        "${{ github.run_attempt }}"
    ) not in RUN


def test_recovered_child_title_binds_to_newest_resume_source() -> None:
    assert "Run benchmark recovery {0} attempt {1}" in RUN
    assert "fromJSON(inputs.resume_sources)[0].run_id" in RUN
    assert "fromJSON(inputs.resume_sources)[0].run_attempt" in RUN
