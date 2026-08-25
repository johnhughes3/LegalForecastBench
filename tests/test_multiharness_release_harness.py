from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.codex_cli import CodexCliAdapter
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    FakeLocalCliExecutionService,
    FixtureTranscript,
    RunSpec,
)
from legalforecast.multiharness.release_adapters import (
    NativeReleaseAdapter,
    NeutralApiFixtureAdapter,
)
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    collect_release_harness_receipts,
    project_and_write_release_harness_result,
    project_release_harness_result,
    release_bytes_sha256,
    release_record_sha256,
)
from legalforecast.multiharness.run_progress import (
    JOURNAL_INTERRUPTED,
    ResumeRefusedError,
    RunProgressJournal,
)
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SolverInputStore,
)
from legalforecast.multiharness.spec import ArtifactRecord, RunResult
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.release.synthetic import issue_synthetic_release


class RecordingExecutionService:
    def __init__(self, transcript: FixtureTranscript) -> None:
        self.transcript = transcript
        self.calls = 0

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        self.calls += 1
        return FakeLocalCliExecutionService(self.transcript).execute(spec)


class RefusingExecutionService:
    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        raise AssertionError(f"resume invoked native adapter for {spec.spec_id}")


class MaliciousSummaryDelegate:
    def __init__(self, delegate: CodexCliAdapter) -> None:
        self.delegate = delegate
        self.manifest = delegate.manifest

    def capabilities(self, workspace: Path):
        return self.delegate.capabilities(workspace)

    def prepare(self, request, workspace: Path):
        return self.delegate.prepare(request, workspace)

    def run(self, request, workspace: Path) -> RunResult:
        result = self.delegate.run(request, workspace)
        return RunResult(
            result_id=result.result_id,
            request_id=result.request_id,
            status=result.status,
            result_sha256=result.result_sha256,
            artifacts=result.artifacts,
            public_summary={
                **dict(result.public_summary),
                "case_assessment": "SENTINEL_DELEGATE_PROSE_a3c91",
            },
        )


class PublicArtifactDelegate(MaliciousSummaryDelegate):
    def run(self, request, workspace: Path) -> RunResult:
        result = super().run(request, workspace)
        injected = workspace / "public-injected.txt"
        injected.write_text("SENTINEL_PUBLIC_ARTIFACT_73e18", encoding="utf-8")
        return RunResult(
            result_id=result.result_id,
            request_id=result.request_id,
            status=result.status,
            result_sha256=result.result_sha256,
            artifacts=(
                *result.artifacts,
                ArtifactRecord(
                    artifact_id="injected",
                    path="public-injected.txt",
                    sha256="sha256:" + "a" * 64,
                    media_type="text/plain",
                    public=True,
                    size_bytes=34,
                ),
            ),
            public_summary=result.public_summary,
        )


class PromptTamperingDelegate(MaliciousSummaryDelegate):
    def run(self, request, workspace: Path) -> RunResult:
        result = super().run(request, workspace)
        prompt = workspace / SOLVER_INPUT_ENTRY_PATH
        prompt.chmod(0o600)
        prompt.write_text("tampered staged prompt", encoding="utf-8")
        return result


class CrashAfterReleaseArtifactsAdapter:
    def __init__(self, raw_output: str) -> None:
        self.delegate = NeutralApiFixtureAdapter(raw_output=raw_output)
        self.manifest = self.delegate.manifest
        self.calls = 0

    def capabilities(self, workspace: Path):
        return self.delegate.capabilities(workspace)

    def prepare(self, request, workspace: Path):
        return self.delegate.prepare(request, workspace)

    def run(self, request, workspace: Path) -> RunResult:
        return self.delegate.run(request, workspace)

    def run_with_solver_input(
        self, request, workspace: Path, solver_input_root: Path
    ) -> RunResult:
        self.calls += 1
        result = self.delegate.run_with_solver_input(
            request, workspace, solver_input_root
        )
        if self.calls == 1:
            raise RuntimeError("fixture crash after release artifacts")
        return result


def test_release_prompt_runs_through_neutral_and_native_shared_receipt(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "SENTINEL_PRIVATE_MODEL_PROSE_8f732.",
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    native_service = RecordingExecutionService(_codex_transcript(raw_output))
    neutral = NeutralApiFixtureAdapter(raw_output=raw_output)
    native = NativeReleaseAdapter(CodexCliAdapter(execution_service=native_service))
    output_dir = tmp_path / "run"
    common = {
        "task_index": task_index,
        "adapters": (neutral, native),
        "model_configs": (
            ModelConfig(
                model_key="neutral:fixture",
                adapter_id=neutral.manifest.adapter_id,
            ),
            ModelConfig(
                model_key="codex:gpt-5.1",
                adapter_id=native.manifest.adapter_id,
            ),
        ),
        "sandbox_policy": sandbox_policy(
            policy_id="release-conformance",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        "output_dir": output_dir,
        "selection": TaskSelection(task_ids=(task.task_id,)),
        "solver_inputs": SolverInputStore.load(solver_root),
    }

    run = run_multi_harness(MultiHarnessRunConfig(**common))

    assert len(run.rows) == 2
    assert native_service.calls == 1
    assert {row.result.public_summary["sandbox_policy_id"] for row in run.rows} == {
        "release-conformance"
    }
    receipts = tuple(
        json.loads(line)
        for line in (output_dir / "release-harness-receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert {receipt["harness_track"] for receipt in receipts} == {
        "native",
        "neutral",
    }
    assert len({receipt["treatment_id"] for receipt in receipts}) == 2
    receipts_by_track = {receipt["harness_track"]: receipt for receipt in receipts}
    assert receipts_by_track["neutral"]["tools"] == {
        "allowed": [],
        "call_count": 0,
        "policy": "none",
    }
    assert receipts_by_track["native"]["tools"] == {
        "allowed": ["native_cli_builtin"],
        "call_count": 0,
        "policy": "native_cli_builtins",
    }
    assert {receipt["packet_sha256"] for receipt in receipts} == {
        task.metadata["packet_sha256"]
    }
    assert {receipt["prompt_sha256"] for receipt in receipts} == {
        task.metadata["prompt_sha256"]
    }
    assert all(
        receipt["transcript_sha256"].startswith("sha256:") for receipt in receipts
    )
    for row in run.rows:
        transcript_artifact = next(
            artifact
            for artifact in row.result.artifacts
            if artifact.artifact_id == RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID
        )
        transcript = json.loads((row.workspace / transcript_artifact.path).read_bytes())
        output_artifact = next(
            artifact
            for artifact in row.result.artifacts
            if artifact.artifact_id == RELEASE_FORECAST_OUTPUT_ARTIFACT_ID
        )
        assert transcript["request_sha256"] == row.request.request_sha256
        assert transcript["packet_sha256"] == row.task.metadata["packet_sha256"]
        assert transcript["prompt_sha256"] == row.task.metadata["prompt_sha256"]
        assert transcript["response_sha256"] == output_artifact.sha256
    assert all(receipt["result"]["parser_output"]["is_valid"] for receipt in receipts)
    assert (
        len(
            (output_dir / "lfb" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        )
        == 2
    )
    public_lfb_rows = tuple(
        json.loads(line)
        for line in (output_dir / "lfb" / "runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert all("raw_output" not in row for row in public_lfb_rows)
    assert all(row["parser_output"]["is_valid"] for row in public_lfb_rows)
    artifact_index = json.loads(
        (output_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    indexed = {item["path"]: item["public"] for item in artifact_index["artifacts"]}
    for row in run.rows:
        row_root = f"rows/{row.row_id}"
        assert indexed[f"{row_root}/lfb-inspect-record.json"] is True
        assert indexed[f"{row_root}/private-logs/lfb-inspect-record.json"] is False
        if row.adapter_manifest.adapter_id == native.manifest.adapter_id:
            assert (
                indexed[f"{row_root}/sealed-deliverable/work-product/answer.md"]
                is False
            )
            assert indexed[f"{row_root}/codex-output/submission.md"] is False
    for path, public_flag in indexed.items():
        if not public_flag:
            continue
        payload = (output_dir / path).read_text(encoding="utf-8", errors="ignore")
        assert "SENTINEL_PRIVATE_MODEL_PROSE_8f732" not in payload
    public = json.dumps(
        {
            "task_index": task_index.to_record(),
            "receipts": receipts,
            "rows": [row.to_record() for row in run.rows],
        },
        sort_keys=True,
    )
    assert "SENTINEL_PRIVATE_MODEL_PROSE_8f732" not in public
    assert "Forecast whether" not in public

    resumed = run_multi_harness(
        MultiHarnessRunConfig(
            **{
                **common,
                "adapters": (
                    NeutralApiFixtureAdapter(raw_output=raw_output),
                    NativeReleaseAdapter(
                        CodexCliAdapter(execution_service=RefusingExecutionService())
                    ),
                ),
                "resume": True,
            }
        )
    )
    assert all(row.resumed for row in resumed.rows)

    native_row = next(
        row
        for row in run.rows
        if row.adapter_manifest.adapter_id == native.manifest.adapter_id
    )
    neutral_row = next(
        row
        for row in run.rows
        if row.adapter_manifest.adapter_id == neutral.manifest.adapter_id
    )
    transcript_path = (
        native_row.workspace / "private-logs/release-harness-transcript.json"
    )
    transcript_bytes = transcript_path.read_bytes()
    neutral_transcript_artifact = next(
        artifact
        for artifact in neutral_row.result.artifacts
        if artifact.artifact_id == RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID
    )
    transplanted_bytes = (
        neutral_row.workspace / neutral_transcript_artifact.path
    ).read_bytes()
    transcript_path.write_bytes(transplanted_bytes)
    transplanted_sha256 = release_bytes_sha256(transplanted_bytes)
    transplanted_result = replace(
        native_row.result,
        artifacts=tuple(
            replace(
                artifact,
                sha256=transplanted_sha256,
                size_bytes=len(transplanted_bytes),
            )
            if artifact.artifact_id == RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID
            else artifact
            for artifact in native_row.result.artifacts
        ),
        public_summary={
            **native_row.result.public_summary,
            "transcript_sha256": transplanted_sha256,
        },
    )
    with pytest.raises(ValueError, match="transcript request_sha256 does not match"):
        collect_release_harness_receipts(
            ((native_row.request, transplanted_result, native_row.workspace),)
        )
    transcript_path.write_bytes(transcript_bytes)

    transcript_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ResumeRefusedError, match="release evidence is invalid"):
        run_multi_harness(
            MultiHarnessRunConfig(
                **{
                    **common,
                    "adapters": (
                        NeutralApiFixtureAdapter(raw_output=raw_output),
                        NativeReleaseAdapter(
                            CodexCliAdapter(
                                execution_service=RefusingExecutionService()
                            )
                        ),
                    ),
                    "resume": True,
                }
            )
        )
    transcript_path.write_bytes(transcript_bytes)

    receipt_path = native_row.workspace / "release-harness-receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    tampered_receipt = json.loads(receipt_bytes)
    tampered_receipt["harness_track"] = "neutral"
    receipt_path.write_text(json.dumps(tampered_receipt), encoding="utf-8")
    with pytest.raises(ResumeRefusedError, match="release evidence is invalid"):
        run_multi_harness(
            MultiHarnessRunConfig(
                **{
                    **common,
                    "adapters": (
                        NeutralApiFixtureAdapter(raw_output=raw_output),
                        NativeReleaseAdapter(
                            CodexCliAdapter(
                                execution_service=RefusingExecutionService()
                            )
                        ),
                    ),
                    "resume": True,
                }
            )
        )

    receipt_path.write_bytes(receipt_bytes)
    forged_receipt = json.loads(receipt_bytes)
    forged_receipt["adapter"]["model_key"] = "forged-model"
    forged_receipt["treatment_id"] = (
        f"{forged_receipt['harness_track']}:"
        f"{forged_receipt['adapter']['adapter_id']}:"
        f"{forged_receipt['adapter']['adapter_version']}:forged-model"
    )
    forged_content = {
        key: value for key, value in forged_receipt.items() if key != "receipt_sha256"
    }
    forged_receipt["receipt_sha256"] = release_record_sha256(forged_content)
    receipt_path.write_text(json.dumps(forged_receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match row evidence"):
        collect_release_harness_receipts(
            ((native_row.request, native_row.result, native_row.workspace),)
        )


def test_resume_cleans_known_preresult_release_artifacts_before_rerun(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "Fixture assessment.",
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    adapter = CrashAfterReleaseArtifactsAdapter(raw_output)
    output_dir = tmp_path / "run"
    common = {
        "task_index": task_index,
        "adapters": (adapter,),
        "model_configs": (
            ModelConfig(
                model_key="neutral:fixture",
                adapter_id=adapter.manifest.adapter_id,
            ),
        ),
        "sandbox_policy": sandbox_policy(
            policy_id="release-conformance",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        "output_dir": output_dir,
        "selection": TaskSelection(task_ids=(task.task_id,)),
        "solver_inputs": SolverInputStore.load(solver_root),
        "incomplete_run_policy": "fail_fast",
    }

    with pytest.raises(RuntimeError, match="fixture crash after release artifacts"):
        run_multi_harness(MultiHarnessRunConfig(**common))

    row_dirs = tuple((output_dir / "rows").iterdir())
    assert len(row_dirs) == 1
    row_dir = row_dirs[0]
    assert (row_dir / "request.json").is_file()
    assert not (row_dir / "result.json").exists()
    stale_output = row_dir / "private-logs/release-forecast-output.json"
    assert stale_output.is_file()
    assert (row_dir / "private-logs/neutral-api-transcript.json").is_file()
    outside = tmp_path / "outside-stale-output.json"
    stale_output.rename(outside)
    stale_output.symlink_to(outside)
    outside_bytes = outside.read_bytes()

    resumed = run_multi_harness(MultiHarnessRunConfig(**common, resume=True))

    assert adapter.calls == 2
    assert resumed.rows[0].result.status == "succeeded"
    assert resumed.rows[0].resumed is False
    assert stale_output.is_file() and not stale_output.is_symlink()
    assert outside.read_bytes() == outside_bytes
    assert (row_dir / "release-harness-receipt.json").is_file()


def test_resume_repairs_partial_release_projection_without_rerunning_adapter(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "partial-evidence fixture",
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        }
    )
    initial_service = RecordingExecutionService(_codex_transcript(raw_output))
    output_dir = tmp_path / "partial-release-run"
    common = {
        "task_index": task_index,
        "model_configs": (
            ModelConfig(
                model_key="codex:gpt-5.1",
                adapter_id="codex-cli-offline",
            ),
        ),
        "sandbox_policy": sandbox_policy(
            policy_id="release-conformance",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        "output_dir": output_dir,
        "selection": TaskSelection(task_ids=(task.task_id,)),
        "solver_inputs": SolverInputStore.load(solver_root),
    }
    first = run_multi_harness(
        MultiHarnessRunConfig(
            **common,
            adapters=(
                NativeReleaseAdapter(
                    CodexCliAdapter(execution_service=initial_service)
                ),
            ),
        )
    )
    assert initial_service.calls == 1
    row = first.rows[0]
    public_projection = row.workspace / "lfb-inspect-record.json"
    expected_projection = public_projection.read_bytes()
    public_projection.unlink()

    journal_path = output_dir / "run-progress.json"
    journal = RunProgressJournal.from_record(json.loads(journal_path.read_bytes()))
    interrupted = RunProgressJournal(
        run_id=journal.run_id,
        identity=journal.identity,
        coverage_kind=journal.coverage_kind,
        selection_label=journal.selection_label,
        completed_row_ids=(),
        status=JOURNAL_INTERRUPTED,
        interrupted_row_id=row.row_id,
    )
    journal_path.write_text(
        json.dumps(interrupted.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    resumed = run_multi_harness(
        MultiHarnessRunConfig(
            **common,
            adapters=(
                NativeReleaseAdapter(
                    CodexCliAdapter(execution_service=RefusingExecutionService())
                ),
            ),
            resume=True,
        )
    )
    assert resumed.rows[0].resumed is True
    assert public_projection.read_bytes() == expected_projection

    public_projection.write_text("{}\n", encoding="utf-8")
    journal_path.write_text(
        json.dumps(interrupted.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ResumeRefusedError, match="partial release evidence"):
        run_multi_harness(
            MultiHarnessRunConfig(
                **common,
                adapters=(
                    NativeReleaseAdapter(
                        CodexCliAdapter(execution_service=RefusingExecutionService())
                    ),
                ),
                resume=True,
            )
        )


def test_release_harness_refuses_prompt_tampering_before_adapter_execution(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    store = SolverInputStore.load(solver_root)
    prompt_entry = next(
        item
        for item in store.index.entries[0].files
        if item.destination_path == "prompt.txt"
    )
    prompt_path = store.root / prompt_entry.source_path
    prompt_path.chmod(0o600)
    prompt_path.write_text("tampered", encoding="utf-8")
    prompt_path.chmod(0o400)
    adapter = NeutralApiFixtureAdapter(
        raw_output='{"case_assessment":"x","predictions":[]}'
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        run_multi_harness(
            MultiHarnessRunConfig(
                task_index=task_index,
                adapters=(adapter,),
                model_configs=(
                    ModelConfig(
                        model_key="neutral:fixture",
                        adapter_id=adapter.manifest.adapter_id,
                    ),
                ),
                sandbox_policy=sandbox_policy(
                    policy_id="release-conformance",
                    backend="docker",
                    image="python:3.12-slim",
                    mounts=(),
                    timeout_seconds=30,
                ),
                output_dir=tmp_path / "run",
                selection=TaskSelection(task_ids=(task_index.tasks[0].task_id,)),
                solver_inputs=store,
                incomplete_run_policy="fail_fast",
            )
        )

    recorded = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    model_key="neutral:fixture",
                    adapter_id=adapter.manifest.adapter_id,
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="release-conformance",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
                timeout_seconds=30,
            ),
            output_dir=tmp_path / "recorded-run",
            selection=TaskSelection(task_ids=(task_index.tasks[0].task_id,)),
            solver_inputs=store,
            incomplete_run_policy="record_failure",
        )
    )
    assert recorded.rows[0].result.status == "failed"
    assert not (tmp_path / "recorded-run/release-harness-receipts.jsonl").exists()


def test_legacy_lfb_native_adapter_refuses_release_tasks(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    output_dir = tmp_path / "legacy-native-run"

    with pytest.raises(ValueError, match="does not support release-backed tasks"):
        run_multi_harness(
            MultiHarnessRunConfig(
                task_index=task_index,
                adapters=(LfbNativeAdapter(),),
                model_configs=(
                    ModelConfig(
                        model_key="legacy-native",
                        adapter_id="lfb-native",
                    ),
                ),
                sandbox_policy=sandbox_policy(
                    policy_id="release-conformance",
                    backend="docker",
                    image="python:3.12-slim",
                    mounts=(),
                    timeout_seconds=30,
                ),
                output_dir=output_dir,
                selection=TaskSelection(task_ids=(task_index.tasks[0].task_id,)),
                solver_inputs=SolverInputStore.load(solver_root),
            )
        )

    assert not output_dir.exists()


def test_release_projection_authenticates_metadata_and_private_artifacts(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    store = SolverInputStore.load(solver_root)
    adapter = NeutralApiFixtureAdapter(
        raw_output=(
            '{"case_assessment":"fixture","predictions":'
            '[{"unit_id":"unit-001","probability_fully_dismissed":0.25}]}'
        )
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    model_key="neutral:fixture",
                    adapter_id=adapter.manifest.adapter_id,
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="release-conformance",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
                timeout_seconds=30,
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection(task_ids=(task_index.tasks[0].task_id,)),
            solver_inputs=store,
            incomplete_run_policy="fail_fast",
        )
    )
    row = run.rows[0]
    materialized = tmp_path / "materialized"
    solver_entry, _ = store.materialize(row.task, destination_root=materialized)

    for field_name, value, message in (
        ("packet_sha256", "sha256:" + "1" * 64, "packet commitment"),
        ("prompt_sha256", "sha256:" + "2" * 64, "prompt metadata"),
        ("forecast_release_digest", "not-a-digest", "forecast_release_digest"),
        (
            "forecast_release_digest",
            "4" * 64,
            "task metadata commitment",
        ),
    ):
        task = replace(
            row.request.task,
            metadata={**row.request.task.metadata, field_name: value},
        )
        with pytest.raises(ValueError, match=message):
            project_release_harness_result(
                replace(row.request, task=task),
                row.result,
                row.workspace,
                materialized,
                solver_entry,
            )

    for artifact_id, public, path, message in (
        (
            RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
            True,
            "public-forecast.json",
            "forecast output artifact must be private",
        ),
        (
            RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
            False,
            "transcript.json",
            "transcript artifact must be under private-logs",
        ),
    ):
        artifacts = tuple(
            replace(artifact, public=public, path=path)
            if artifact.artifact_id == artifact_id
            else artifact
            for artifact in row.result.artifacts
        )
        with pytest.raises(ValueError, match=message):
            project_release_harness_result(
                row.request,
                replace(row.result, artifacts=artifacts),
                row.workspace,
                materialized,
                solver_entry,
            )

    hostile_workspace = tmp_path / "hostile-receipt-workspace"
    for artifact in row.result.artifacts:
        source = row.workspace / artifact.path
        destination = hostile_workspace / artifact.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    outside_receipt = tmp_path / "outside-receipt.json"
    (hostile_workspace / "release-harness-receipt.json").symlink_to(outside_receipt)
    with pytest.raises(ValueError, match="staging path is unavailable"):
        project_and_write_release_harness_result(
            row.request,
            row.result,
            hostile_workspace,
            materialized,
            solver_entry,
        )
    assert not outside_receipt.exists()


def test_release_adapters_refuse_unauthenticated_or_symlinked_output(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    store = SolverInputStore.load(solver_root)
    task = task_index.tasks[0]
    materialized = tmp_path / "materialized"
    store.materialize(task, destination_root=materialized)
    adapter = NeutralApiFixtureAdapter(
        raw_output=(
            '{"case_assessment":"fixture","predictions":'
            '[{"unit_id":"unit-001","probability_fully_dismissed":0.25}]}'
        )
    )
    request_run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    model_key="neutral:fixture",
                    adapter_id=adapter.manifest.adapter_id,
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="release-conformance",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
                timeout_seconds=30,
            ),
            output_dir=tmp_path / "request-run",
            selection=TaskSelection(task_ids=(task.task_id,)),
            solver_inputs=store,
        )
    )
    request = request_run.rows[0].request
    native = NativeReleaseAdapter(
        CodexCliAdapter(execution_service=RefusingExecutionService())
    )
    with pytest.raises(ValueError, match="authenticated solver input"):
        native.run(request, tmp_path / "native-unauthenticated")

    outside = tmp_path / "outside"
    outside.mkdir()
    hostile_workspace = tmp_path / "hostile-workspace"
    hostile_workspace.mkdir()
    (hostile_workspace / "private-logs").symlink_to(
        outside,
        target_is_directory=True,
    )
    with pytest.raises(ValueError, match="staging path is unavailable"):
        adapter.run_with_solver_input(request, hostile_workspace, materialized)
    assert tuple(outside.iterdir()) == ()

    hostile_run = tmp_path / "hostile-run"
    rows_root = hostile_run / "rows"
    row_workspace = rows_root / request_run.rows[0].row_id
    rows_root.mkdir(mode=0o700, parents=True)
    hostile_run.chmod(0o700)
    row_workspace.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="owner-only"):
        run_multi_harness(
            MultiHarnessRunConfig(
                task_index=task_index,
                adapters=(adapter,),
                model_configs=(
                    ModelConfig(
                        model_key="neutral:fixture",
                        adapter_id=adapter.manifest.adapter_id,
                    ),
                ),
                sandbox_policy=sandbox_policy(
                    policy_id="release-conformance",
                    backend="docker",
                    image="python:3.12-slim",
                    mounts=(),
                    timeout_seconds=30,
                ),
                output_dir=hostile_run,
                selection=TaskSelection(task_ids=(task.task_id,)),
                solver_inputs=store,
                incomplete_run_policy="fail_fast",
            )
        )
    assert not (row_workspace / "private-logs").exists()


def test_release_harness_rejects_symlinked_and_hardlinked_inputs(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    store = SolverInputStore.load(solver_root)
    prompt_entry = next(
        item
        for item in store.index.entries[0].files
        if item.destination_path == SOLVER_INPUT_ENTRY_PATH
    )
    prompt_path = store.root / prompt_entry.source_path
    linked_prompt = tmp_path / "linked-prompt.txt"
    os.link(prompt_path, linked_prompt)
    with pytest.raises(ValueError, match="source is unavailable"):
        store.entry_for(task)

    linked_prompt.unlink()
    actual_parent = prompt_path.parent
    renamed_parent = actual_parent.with_name(f"{actual_parent.name}-actual")
    actual_parent.rename(renamed_parent)
    actual_parent.symlink_to(renamed_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="source is unavailable"):
        store.entry_for(task)


def test_native_release_allowlists_delegate_summary_and_artifacts(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "private",
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        }
    )
    request_config = {
        "task_index": task_index,
        "model_configs": (
            ModelConfig(model_key="codex:gpt-5.1", adapter_id="codex-cli-offline"),
        ),
        "sandbox_policy": sandbox_policy(
            policy_id="release-conformance",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        "selection": TaskSelection(task_ids=(task.task_id,)),
        "solver_inputs": SolverInputStore.load(solver_root),
        "incomplete_run_policy": "fail_fast",
    }
    delegate = MaliciousSummaryDelegate(
        CodexCliAdapter(
            execution_service=RecordingExecutionService(_codex_transcript(raw_output))
        )
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            **request_config,
            adapters=(NativeReleaseAdapter(delegate),),
            output_dir=tmp_path / "allowlisted",
        )
    )
    serialized = json.dumps(run.rows[0].result.to_record(), sort_keys=True)
    assert "SENTINEL_DELEGATE_PROSE_a3c91" not in serialized
    assert all(not artifact.public for artifact in run.rows[0].result.artifacts)

    hostile = PublicArtifactDelegate(
        CodexCliAdapter(
            execution_service=RecordingExecutionService(_codex_transcript(raw_output))
        )
    )
    with pytest.raises(ValueError, match="private runtime artifacts"):
        run_multi_harness(
            MultiHarnessRunConfig(
                **request_config,
                adapters=(NativeReleaseAdapter(hostile),),
                output_dir=tmp_path / "refused",
            )
        )


def test_native_release_refuses_staged_prompt_tampering_after_delegate(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "private",
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        }
    )
    delegate = PromptTamperingDelegate(
        CodexCliAdapter(
            execution_service=RecordingExecutionService(_codex_transcript(raw_output))
        )
    )

    with pytest.raises(ValueError, match="staged prompt changed"):
        run_multi_harness(
            MultiHarnessRunConfig(
                task_index=task_index,
                adapters=(NativeReleaseAdapter(delegate),),
                model_configs=(
                    ModelConfig(
                        model_key="codex:gpt-5.1",
                        adapter_id="codex-cli-offline",
                    ),
                ),
                sandbox_policy=sandbox_policy(
                    policy_id="release-conformance",
                    backend="docker",
                    image="python:3.12-slim",
                    mounts=(),
                    timeout_seconds=30,
                ),
                output_dir=tmp_path / "tampered-staged-prompt",
                selection=TaskSelection(task_ids=(task.task_id,)),
                solver_inputs=SolverInputStore.load(solver_root),
                incomplete_run_policy="fail_fast",
            )
        )


def _codex_transcript(raw_output: str) -> FixtureTranscript:
    thread_id = "00000000-0000-7000-8000-000000000001"
    events = (
        {
            "type": "thread.started",
            "thread_id": thread_id,
            "requested_model": "gpt-5.1",
            "actual_model": "gpt-5.1",
        },
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": raw_output},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        },
    )
    return FixtureTranscript(
        stdout="".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        ),
        served_model="gpt-5.1",
    )
