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
    assert RECOVERY.count("retention-days: 90\n") == 3
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


@pytest.mark.parametrize("identified", [True, False])
@pytest.mark.parametrize("case_id", ["", "66996622"])
def test_child_dispatch_persists_exact_identity_or_unresolved_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identified: bool, case_id: str
) -> None:
    import json
    from collections.abc import Mapping

    from legalforecast.runner import recovery
    from legalforecast.runner.recovery_client import dispatched_workflow_record

    section = RECOVERY.split("      - name: Dispatch canonical resumed benchmark", 1)[
        1
    ].split("      - name: Persist exact child dispatch identity", 1)[0]
    script = textwrap.dedent(
        section.split("          uv run python - <<'PY'\n", 1)[1].rsplit(
            "          PY", 1
        )[0]
    )
    plan_path = tmp_path / "plan.json"
    result_path = tmp_path / "dispatch.json"
    script = script.replace(
        "/tmp/lfb-source-recovery-plan.json", str(plan_path)
    ).replace("/tmp/lfb-child-dispatch.json", str(result_path))
    plan_path.write_text(
        json.dumps(
            {
                "source": {"run_id": 123, "run_attempt": 2},
                "frozen_identity": {
                    "manifest_uri": "manifest",
                    "forecast_release_uri": "forecast",
                    "artifact_root_uri": "artifacts",
                    "model_registry_uri": "registry",
                    "model_key": "provider:model",
                    "terminal_case_id": case_id,
                    "ceiling_microusd": 100,
                    "account": "account",
                    "repeat_count": 1,
                },
                "recovery": {"resume_sources": [{"run_id": 123, "run_attempt": 2}]},
            }
        )
    )
    calls: list[tuple[str, str, str]] = []

    class Client:
        def list_active_recovery_runs(self, repo: str) -> list[Mapping[str, object]]:
            return []

        def dispatch(
            self, repo: str, workflow: str, ref: str, inputs: Mapping[str, str]
        ) -> Mapping[str, object]:
            calls.append((repo, workflow, ref))
            assert inputs["terminal_case_id"] == case_id
            assert inputs["ceiling_microusd"] == "100"
            return dispatched_workflow_record(
                repo,
                workflow,
                ref,
                f"https://github.com/{repo}/actions/runs/456" if identified else "",
            )

    monkeypatch.setattr(recovery, "GhRecoveryClient", Client)
    for key, value in {
        "GITHUB_REPOSITORY": "owner/bench",
        "GITHUB_RUN_ID": "333",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "MAX_PARALLEL": "8",
    }.items():
        monkeypatch.setenv(key, value)
    exec(compile(script, "protected dispatch step", "exec"), {})
    record = json.loads(result_path.read_text())
    assert calls == [("owner/bench", "run-benchmark.yaml", "main")]
    assert record["dispatched"] is True
    assert record["run_id"] == (456 if identified else None)
    assert record["source_run_id"] == 123 and record["source_run_attempt"] == 2
    assert record["recovery_run_id"] == 333 and record["recovery_run_attempt"] == 1
    upload = RECOVERY.split("      - name: Persist exact child dispatch identity", 1)[1]
    assert "path: /tmp/lfb-child-dispatch.json" in upload
    assert (
        "name: recovery-child-dispatch-${{ github.run_id }}-${{ github.run_attempt }}"
        in upload
    )
    assert "if-no-files-found: error" in upload
