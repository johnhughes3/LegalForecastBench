from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.multiharness.release_adapters import NeutralApiFixtureAdapter
from legalforecast.multiharness.release_harness import (
    release_record_sha256,
    score_multiharness_release,
)
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import SolverInputStore
from legalforecast.multiharness.spec import RunResult
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.release import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    LabelsDraft,
    PredictionUnitDraft,
    ScoringPolicy,
    UnitOutcome,
    issue_release,
    validate_release,
)
from legalforecast.release.synthetic import issue_synthetic_release


class CountingNeutralAdapter:
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
        return self.delegate.run_with_solver_input(
            request, workspace, solver_input_root
        )


def _issue_unequal_case_release(tmp_path: Path) -> tuple[Path, Path]:
    """Create two cases whose blinded tasks contain two units and one unit."""

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    cases = ("case-001", "case-002")
    documents = tuple(
        DocumentDraft(
            document_id=f"complaint-{case_id}",
            role="complaint",
            path=f"documents/{case_id}/complaint.txt",
        )
        for case_id in cases
    )
    for document in documents:
        path = artifact_root / document.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{document.path} visible source".encode())

    unit_specs = (
        ("unit-001", "case-001", "packets/unit-001.json", "prompts/case-001.txt"),
        ("unit-002", "case-001", "packets/unit-002.json", "prompts/case-001.txt"),
        ("unit-003", "case-002", "packets/unit-003.json", "prompts/case-002.txt"),
    )
    for case_id in cases:
        prompt_path = artifact_root / f"prompts/{case_id}.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_bytes(f"shared blinded prompt for {case_id}".encode())
    for unit_id, case_id, packet_path, _ in unit_specs:
        path = artifact_root / packet_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            ARTIFACT_CANONICAL_JSON_V1.encode(
                {
                    "case_id": case_id,
                    "claim_name": f"Claim {unit_id}",
                    "count": unit_id,
                    "decision_date": "2026-08-23",
                    "defendant_group": "defendants",
                    "model_visible_document_ids": [f"complaint-{case_id}"],
                    "policy_digest": "1" * 64,
                    "unit_id": unit_id,
                }
            )
        )

    issued = issue_release(
        ForecastDraft(
            release_id="unequal-case-batch-fixture-v1",
            policy_digest="1" * 64,
            code_version="fixture-code-v1",
            packet_builder_version="fixture-packet-v1",
            cases=tuple(
                CaseDraft(case_id=case_id, documents=(document,))
                for case_id, document in zip(cases, documents, strict=True)
            ),
            prediction_units=tuple(
                PredictionUnitDraft(
                    unit_id=unit_id,
                    case_id=case_id,
                    claim_name=f"Claim {unit_id}",
                    defendant_group="defendants",
                    count=unit_id,
                    should_score=True,
                    model_visible_document_ids=(f"complaint-{case_id}",),
                    packet_path=packet_path,
                    prompt_path=prompt_path,
                )
                for unit_id, case_id, packet_path, prompt_path in unit_specs
            ),
        ),
        LabelsDraft(
            release_id="unequal-case-batch-fixture-v1",
            scoring_policy=ScoringPolicy(policy_id="fixture-brier-v1"),
            unit_outcomes=tuple(
                UnitOutcome(unit_id=unit_id, outcome=outcome)
                for unit_id, outcome in (
                    ("unit-001", 0),
                    ("unit-002", 1),
                    ("unit-003", 0),
                )
            ),
        ),
        artifact_root=artifact_root,
    )
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "forecast-release.json").write_bytes(
        issued.payloads["forecast-release.json"]
    )
    (release_root / "labels-release.json").write_bytes(
        issued.payloads["labels-release.json"]
    )
    return release_root, artifact_root


def test_score_multiharness_release_includes_failed_units_and_equal_case_metric(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    forecast, labels = validate_release(
        release_root / "forecast-release.json",
        release_root / "labels-release.json",
        artifact_root=release_root,
    )
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    raw_output = json.dumps(
        {
            "case_assessment": "fixture",
            "predictions": [
                {"unit_id": "unit-001", "probability_fully_dismissed": 0.25}
            ],
        },
        separators=(",", ":"),
    )
    adapter = NeutralApiFixtureAdapter(raw_output=raw_output)
    config = MultiHarnessRunConfig(
        task_index=task_index,
        adapters=(adapter,),
        model_configs=(
            ModelConfig(adapter_id=adapter.manifest.adapter_id, model_key="fixture"),
        ),
        sandbox_policy=sandbox_policy(
            policy_id="release-score-fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
        ),
        output_dir=tmp_path / "run",
        selection=TaskSelection(task_ids=(task.task_id,)),
        solver_inputs=SolverInputStore.load(solver_root),
    )
    run = run_multi_harness(config)
    report = score_multiharness_release(run, forecast, labels)
    model = report["models"][0]
    assert model["unit_count"] == 1
    assert model["completed_unit_count"] == 1
    assert model["failed_unit_count"] == 0
    assert model["micro_brier"] == model["equal_case_brier"] == 0.25**2
    assert model["completion_rate"] == 1.0

    failed_result = RunResult(
        result_id="failed-result",
        request_id=run.rows[0].request.request_id,
        status="failed",
        result_sha256="sha256:" + "f" * 64,
        public_summary={
            "error_type": "TimeoutError",
            "error_message": "fixture timeout",
            "input_tokens": 12,
        },
    )
    failed_run = run.__class__(
        manifest=run.manifest,
        selection=run.selection,
        rows=(
            run.rows[0].__class__(
                row_id=run.rows[0].row_id,
                task=run.rows[0].task,
                adapter_manifest=run.rows[0].adapter_manifest,
                model_config=run.rows[0].model_config,
                request=run.rows[0].request,
                result=failed_result,
                workspace=run.rows[0].workspace,
                lfb_record=None,
                container_execution=run.rows[0].container_execution,
                container_receipt_sha256=None,
                selection_label=run.rows[0].selection_label,
                coverage_kind=run.rows[0].coverage_kind,
            ),
        ),
        output_dir=run.output_dir,
        interrupted=False,
    )
    failure_report = score_multiharness_release(failed_run, forecast, labels)
    failed_model = failure_report["models"][0]
    assert failed_model["unit_count"] == 1
    assert failed_model["completed_unit_count"] == 0
    assert failed_model["failed_unit_count"] == 1
    assert failed_model["micro_brier"] == failed_model["equal_case_brier"] == 1.0
    assert failed_model["failures"][0]["failure_kind"] == "TimeoutError"
    assert failed_model["failures"][0]["probability_fully_dismissed"] is None


def test_case_batch_scoring_handles_unequal_units_and_invalid_case_failure(
    tmp_path: Path,
) -> None:
    release_root, artifact_root = _issue_unequal_case_release(tmp_path)
    forecast, labels = validate_release(
        release_root / "forecast-release.json",
        release_root / "labels-release.json",
        artifact_root=artifact_root,
    )
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=artifact_root,
        solver_input_root=solver_root,
        case_batching=True,
    )
    assert [task.metadata["required_unit_ids"] for task in task_index.tasks] == [
        ["unit-001", "unit-002"],
        ["unit-003"],
    ]
    adapter = NeutralApiFixtureAdapter(
        raw_output=json.dumps(
            {
                "case_assessment": "fixture",
                "predictions": [
                    {
                        "unit_id": "unit-001",
                        "probability_fully_dismissed": 0.25,
                    },
                    {
                        "unit_id": "unit-002",
                        "probability_fully_dismissed": 0.75,
                    },
                ],
            },
            separators=(",", ":"),
        )
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id, model_key="fixture"
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="unequal-case-batch-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection.full(),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    report = score_multiharness_release(run, forecast, labels)
    model = report["models"][0]
    assert [row.result.status for row in run.rows] == ["succeeded", "failed"]
    assert model["unit_count"] == 3
    assert model["completed_unit_count"] == 2
    assert model["failed_unit_count"] == 1
    assert model["micro_brier"] == pytest.approx((0.25**2 + 0.25**2 + 1.0) / 3)
    assert model["equal_case_brier"] == pytest.approx((0.25**2 + 1.0) / 2)
    failure = model["failures"][0]
    assert failure["failure_kind"] == "InvalidForecastOutput"
    assert failure["probability_fully_dismissed"] is None
    assert failure["usage"]["estimated_cost"] == 0.0


def test_release_scoring_suppresses_headlines_for_partial_and_zero_rows(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    forecast, labels = validate_release(
        release_root / "forecast-release.json",
        release_root / "labels-release.json",
        artifact_root=release_root,
    )
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    adapter = NeutralApiFixtureAdapter(
        raw_output=json.dumps(
            {
                "case_assessment": "fixture",
                "predictions": [
                    {
                        "unit_id": "unit-001",
                        "probability_fully_dismissed": 0.25,
                    }
                ],
            },
            separators=(",", ":"),
        )
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id, model_key="fixture"
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="partial-score-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection.full(),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    partial = replace(run, rows=(run.rows[0],))
    partial_report = score_multiharness_release(partial, forecast, labels)
    partial_model = partial_report["models"][0]
    assert partial_report["selection"]["complete"] is False
    assert partial_report["headline_metrics_available"] is False
    assert partial_model["micro_brier"] is None
    assert partial_model["equal_case_brier"] is None
    assert partial_model["headline_metrics_suppressed_reason"] == (
        "selection_incomplete"
    )

    empty_report = score_multiharness_release(replace(run, rows=()), forecast, labels)
    assert empty_report["models"] == []
    assert empty_report["headline_metrics_available"] is False
    assert empty_report["headline_metrics_suppressed_reason"] == (
        "selection_incomplete"
    )


def test_release_scoring_groups_preprojection_failure_with_known_track(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    forecast, labels = validate_release(
        release_root / "forecast-release.json",
        release_root / "labels-release.json",
        artifact_root=release_root,
    )
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    selected_tasks = task_index.tasks[:2]
    adapter = NeutralApiFixtureAdapter(
        raw_output='{"case_assessment":"fixture","predictions":[{"unit_id":"unit-001","probability_fully_dismissed":0.25}]}'
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id, model_key="fixture"
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="preprojection-failure-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection(
                task_ids=tuple(task.task_id for task in selected_tasks)
            ),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    assert [row.result.status for row in run.rows] == ["succeeded", "failed"]
    failed_row = replace(
        run.rows[1],
        lfb_record=None,
        result=replace(
            run.rows[1].result,
            public_summary={
                "error_type": "TimeoutError",
                "error_message": "fixture timeout before projection",
                "input_tokens": 4,
                "output_tokens": 2,
                "estimated_cost": 0.001,
            },
        ),
    )
    mixed = replace(run, rows=(run.rows[0], failed_row))
    report = score_multiharness_release(mixed, forecast, labels)
    assert len(report["models"]) == 1
    model = report["models"][0]
    assert model["treatment_id"].startswith("neutral:")
    assert model["unit_count"] == 2
    assert model["failed_unit_count"] == 1
    assert model["micro_brier"] == model["equal_case_brier"] == 0.53125
    assert model["failures"][0]["failure_kind"] == "TimeoutError"
    assert model["failures"][0]["usage"] == {
        "input_tokens": 4,
        "output_tokens": 2,
        "estimated_cost": 0.001,
    }


def test_release_scoring_rejects_task_and_treatment_identity_drift(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    forecast, labels = validate_release(
        release_root / "forecast-release.json",
        release_root / "labels-release.json",
        artifact_root=release_root,
    )
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    task = task_index.tasks[0]
    adapter = NeutralApiFixtureAdapter(
        raw_output='{"case_assessment":"fixture","predictions":[{"unit_id":"unit-001","probability_fully_dismissed":0.25}]}'
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id, model_key="fixture"
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="identity-drift-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection(task_ids=(task.task_id,)),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    drifted_task = replace(
        task,
        metadata={**task.metadata, "forecast_release_digest": "sha256:" + "0" * 64},
    )
    drifted = replace(
        run,
        selection=replace(run.selection, tasks=(drifted_task,)),
        rows=(replace(run.rows[0], task=drifted_task),),
    )
    with pytest.raises(ValueError, match="forecast_release_digest"):
        score_multiharness_release(drifted, forecast, labels)

    forged_lfb = {**run.rows[0].lfb_record, "adapter_id": "forged-adapter"}
    forged = replace(run, rows=(replace(run.rows[0], lfb_record=forged_lfb),))
    with pytest.raises(ValueError, match="adapter_id"):
        score_multiharness_release(forged, forecast, labels)


def test_case_batch_release_projection_uses_one_case_receipt(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
        case_batching=True,
    )
    task = task_index.tasks[0]
    adapter = NeutralApiFixtureAdapter(
        raw_output=json.dumps(
            {
                "case_assessment": "fixture",
                "predictions": [
                    {
                        "unit_id": "unit-001",
                        "probability_fully_dismissed": 0.25,
                    }
                ],
            },
            separators=(",", ":"),
        )
    )
    adapter = replace(
        adapter,
        manifest=replace(adapter.manifest, adapter_id="claude-code-container"),
    )
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id,
                    model_key="fixture",
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="case-batch-projection",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            container_execution="headless_cli",
            selection=TaskSelection(task_ids=(task.task_id,)),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    assert run.rows[0].lfb_record is not None
    assert run.rows[0].to_record()["container_execution"] == {
        "mode": "headless_cli",
        "status": "succeeded",
    }
    assert run.rows[0].lfb_record["sample_id"] == "case-001"
    receipt = json.loads(
        (run.output_dir / "release-harness-receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert receipt["unit_id"] is None
    assert receipt["case_id"] == "case-001"
    assert receipt["result"]["parser_output"]["required_unit_ids"] == ["unit-001"]


@pytest.mark.parametrize(
    "raw_output",
    [
        "not-json",
        json.dumps(
            {
                "case_assessment": "fixture",
                "predictions": [],
            },
            separators=(",", ":"),
        ),
    ],
)
def test_invalid_release_forecast_is_failed_and_retryable(
    tmp_path: Path,
    raw_output: str,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    task_index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    adapter = CountingNeutralAdapter(raw_output)
    config = MultiHarnessRunConfig(
        task_index=task_index,
        adapters=(adapter,),
        model_configs=(
            ModelConfig(adapter_id=adapter.manifest.adapter_id, model_key="fixture"),
        ),
        sandbox_policy=sandbox_policy(
            policy_id="invalid-release-fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
        ),
        output_dir=tmp_path / "run",
        selection=TaskSelection(task_ids=(task_index.tasks[0].task_id,)),
        solver_inputs=SolverInputStore.load(solver_root),
    )

    first = run_multi_harness(config)
    assert first.rows[0].result.status == "failed"
    assert first.rows[0].result.public_summary["error_type"] == (
        "InvalidForecastOutput"
    )
    assert first.rows[0].result.public_summary["parser_status"]
    normalized_summary = dict(first.rows[0].result.public_summary)
    normalized_digest = normalized_summary.pop("normalized_result_sha256")
    assert normalized_summary["original_result_sha256"] == (
        first.rows[0].result.result_sha256
    )
    assert normalized_digest == release_record_sha256(
        {
            "result_id": first.rows[0].result.result_id,
            "request_id": first.rows[0].result.request_id,
            "status": "failed",
            "artifacts": [
                artifact.to_record() for artifact in first.rows[0].result.artifacts
            ],
            "public_summary": normalized_summary,
        }
    )
    progress = json.loads(
        (config.output_dir / "run-progress.json").read_text(encoding="utf-8")
    )
    assert progress["completed_row_ids"] == []

    resumed = run_multi_harness(replace(config, resume=True))
    assert adapter.calls == 2
    assert resumed.rows[0].result.status == "failed"


def test_invalid_unscoreable_release_forecast_keeps_census_projection(
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
    task = task_index.tasks[2]
    adapter = NeutralApiFixtureAdapter(raw_output="not-json")
    run = run_multi_harness(
        MultiHarnessRunConfig(
            task_index=task_index,
            adapters=(adapter,),
            model_configs=(
                ModelConfig(
                    adapter_id=adapter.manifest.adapter_id, model_key="fixture"
                ),
            ),
            sandbox_policy=sandbox_policy(
                policy_id="unscoreable-invalid-fixture",
                backend="docker",
                image="python:3.12-slim",
                mounts=(),
            ),
            output_dir=tmp_path / "run",
            selection=TaskSelection(task_ids=(task.task_id,)),
            solver_inputs=SolverInputStore.load(solver_root),
        )
    )
    row = run.rows[0]
    assert row.result.status == "failed"
    assert row.lfb_record is not None
    assert row.lfb_record["required_unit_ids"] == ["unit-003"]
    assert row.lfb_record["metadata"]["should_score"] == "false"
    assert row.lfb_record["parser_output"]["is_valid"] is False
    receipt = json.loads(
        (row.workspace / "release-harness-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["should_score"] is False
    assert receipt["result"]["parser_output"]["is_valid"] is False
    aggregate_receipts = tuple(
        json.loads(line)
        for line in (row.workspace.parent.parent / "release-harness-receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert aggregate_receipts[0]["should_score"] is False
