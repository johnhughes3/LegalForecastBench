"""Provider-free tests for the injected production LAB judge seam."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from legalforecast.multiharness.deliverables import artifact_tree_sha256
from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
    harvey_lab_private_material_sha256,
    harvey_lab_private_material_snapshot,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionHarveyLabEvaluatorRunner,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import (
    PricingRate,
    PricingSnapshot,
    UsageObservation,
)
from tests.test_tier0_operator_half import DELIVERABLE_BASENAME, _docx_bytes


class _Boundary(HarveyLabJudgeRequestBoundary):
    def __init__(self, events: list[tuple[str, int, int]] | None = None) -> None:
        self.events = events if events is not None else []

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        self.events.append(("before", request.ordinal, request.attempt_index))
        return request

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        assert reservation is request
        assert isinstance(observation, UsageObservation)
        self.events.append(("after", request.ordinal, request.attempt_index))


def _pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_id="production-runner-test",
        as_of_date="2026-08-17",
        rates=(
            PricingRate(
                provider="provider",
                model="judge-model",
                input_microusd_per_token=1,
                output_microusd_per_token=2,
            ),
        ),
    )


def _response(
    pricing: PricingSnapshot, *, retryable: bool = False
) -> ProductionJudgeResponse:
    return ProductionJudgeResponse(
        verdict=None if retryable else "pass",
        judge_resolved_identity="provider/judge-model@resolved-1",
        usage=UsageObservation(
            basis="provider_reported",
            pricing_snapshot_sha256=pricing.snapshot_sha256,
            input_tokens=10,
            output_tokens=5,
            reported_cost_usd="0.000012",
        ),
        raw_response=b"provider-response",
        retryable=retryable,
    )


def _run_spec(
    tmp_path: Path,
    *,
    deliverables: Mapping[str, bytes] | None = None,
    expected_basenames: tuple[str, ...] | None = None,
    criterion_count: int = 23,
    criteria: list[dict[str, object]] | None = None,
) -> tuple[RunSpec, Path]:
    scores_path = tmp_path / "overlay" / "raw" / "scores.json"
    private_path = tmp_path / "overlay" / "private" / "task.json"
    private_path.parent.mkdir(parents=True)
    # The runner authenticates the candidate deliverable before any provider
    # call, so a spec without one is refused rather than graded.
    payloads = dict(
        deliverables or {DELIVERABLE_BASENAME: _docx_bytes("Candidate memo body.")}
    )
    deliverable_root = tmp_path / "overlay" / "output"
    deliverable_root.mkdir(parents=True)
    deliverable_paths: list[Path] = []
    for relative, payload in sorted(payloads.items()):
        path = deliverable_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        deliverable_paths.append(path)
    private_path.write_text(
        json.dumps(
            {
                "id": "task",
                "criteria": criteria
                if criteria is not None
                else [
                    {"id": f"criterion-{ordinal}", "text": f"rule-{ordinal}"}
                    for ordinal in range(1, criterion_count + 1)
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    spec = RunSpec(
        spec_id="production-evaluator",
        argv=("harvey-lab-eval",),
        working_directory=tmp_path,
        stdin_bytes=json.dumps(
            {
                "scores_output_path": str(scores_path),
                "private_task_json_path": str(private_path),
                "private_material_sha256": harvey_lab_private_material_sha256(
                    private_path.parent
                ),
                "deliverable_paths": [str(path) for path in deliverable_paths],
                "deliverable_root": str(deliverable_root),
                "expected_deliverable_basenames": list(
                    expected_basenames
                    if expected_basenames is not None
                    else tuple(sorted(payloads))
                ),
                "deliverable_tree_sha256": artifact_tree_sha256(payloads),
            },
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    return spec, scores_path


def test_production_runner_calls_provider_per_criterion_and_retains_retries(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    spec, scores_path = _run_spec(tmp_path)
    calls: list[ProductionJudgeCall] = []
    attempts: list[ProductionJudgeCall] = []
    events: list[tuple[str, int, int]] = []
    first = True

    def provider(call: ProductionJudgeCall) -> ProductionJudgeResponse:
        nonlocal first
        calls.append(call)
        response = _response(pricing, retryable=first)
        first = False
        return response

    def retain(call: ProductionJudgeCall, _response: ProductionJudgeResponse) -> None:
        attempts.append(call)
        events.append(("retained", call.request.ordinal, call.request.attempt_index))

    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=provider,
        attempt_writer=retain,
        pricing_snapshot=pricing,
        pricing_provider="provider",
        pricing_model="judge-model",
        expected_judge_identity="provider/judge-model@resolved-1",
    )
    boundary = _Boundary(events)
    receipt = runner(LocalCliExecutionService(), spec, boundary)

    assert receipt.status == "succeeded"
    assert len(calls) == 24
    assert len(attempts) == 24
    assert calls[0].request == HarveyLabJudgeRequest(1, "criterion-1", 0)
    assert calls[1].request == HarveyLabJudgeRequest(1, "criterion-1", 1)
    assert len(boundary.events) == 72
    assert boundary.events[0] == ("before", 1, 0)
    assert boundary.events[1] == ("retained", 1, 0)
    assert boundary.events[2] == ("after", 1, 0)
    assert boundary.events[3] == ("before", 1, 1)
    assert boundary.events[4] == ("retained", 1, 1)
    assert boundary.events[5] == ("after", 1, 1)
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert scores["n_criteria"] == 23
    assert scores["n_passed"] == 23
    assert receipt.usage == {"input_tokens": 240, "output_tokens": 120}


def test_production_runner_authenticates_multi_output_and_task_cardinality(
    tmp_path: Path,
) -> None:
    spec, scores_path = _run_spec(
        tmp_path,
        deliverables={
            "analysis.docx": _docx_bytes("Analysis body."),
            "memo.docx": _docx_bytes("Memo body."),
        },
        criterion_count=2,
    )
    calls: list[ProductionJudgeCall] = []
    pricing = _pricing()
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda call: (calls.append(call), _response(pricing))[1],
        attempt_writer=lambda _call, _response: None,
    )

    runner(LocalCliExecutionService(), spec, _Boundary())

    assert len(calls) == 2
    assert calls[0].deliverable.artifact_paths == (
        "analysis.docx",
        "memo.docx",
    )
    assert "Analysis body." in calls[0].deliverable.text
    assert "Memo body." in calls[0].deliverable.text
    assert json.loads(scores_path.read_text(encoding="utf-8"))["n_criteria"] == 2


def test_production_runner_gives_each_criterion_only_its_declared_deliverable(
    tmp_path: Path,
) -> None:
    spec, _ = _run_spec(
        tmp_path,
        deliverables={
            "analysis.docx": _docx_bytes("Correct analysis."),
            "misleading.docx": _docx_bytes("Misleading contrary answer."),
        },
        criteria=[
            {
                "id": "analysis-only",
                "text": "grade the analysis",
                "deliverables": ["analysis.docx"],
            },
            {
                "id": "fallback-all",
                "text": "grade the whole work product",
                "deliverables": [],
            },
        ],
    )
    calls: list[ProductionJudgeCall] = []
    pricing = _pricing()

    ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda call: (calls.append(call), _response(pricing))[1],
        attempt_writer=lambda _call, _response: None,
    )(LocalCliExecutionService(), spec, _Boundary())

    assert calls[0].deliverable.artifact_paths == ("analysis.docx",)
    assert "Correct analysis." in calls[0].deliverable.text
    assert "Misleading contrary answer." not in calls[0].deliverable.text
    assert calls[1].deliverable.artifact_paths == (
        "analysis.docx",
        "misleading.docx",
    )
    assert "Misleading contrary answer." in calls[1].deliverable.text


def test_production_runner_refuses_bad_later_criterion_before_any_provider_call(
    tmp_path: Path,
) -> None:
    spec, _ = _run_spec(
        tmp_path,
        deliverables={"analysis.docx": _docx_bytes("Correct analysis.")},
        criteria=[
            {
                "id": "valid-first",
                "text": "valid",
                "deliverables": ["analysis.docx"],
            },
            {
                "id": "invalid-second",
                "text": "invalid",
                "deliverables": ["not-produced.docx"],
            },
        ],
    )
    calls: list[ProductionJudgeCall] = []
    pricing = _pricing()
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda call: (calls.append(call), _response(pricing))[1],
        attempt_writer=lambda _call, _response: None,
    )

    with pytest.raises(ValueError, match="unknown deliverable"):
        runner(LocalCliExecutionService(), spec, _Boundary())
    assert calls == []


def test_production_runner_accepts_score_all_outputs_contract(tmp_path: Path) -> None:
    spec, _ = _run_spec(
        tmp_path,
        deliverables={
            "issues.docx": _docx_bytes("Issues body."),
            "redline.docx": _docx_bytes("Redline body."),
        },
        expected_basenames=(),
        criterion_count=1,
    )
    calls: list[ProductionJudgeCall] = []
    pricing = _pricing()

    ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda call: (calls.append(call), _response(pricing))[1],
        attempt_writer=lambda _call, _response: None,
    )(LocalCliExecutionService(), spec, _Boundary())

    assert calls[0].deliverable.artifact_paths == (
        "issues.docx",
        "redline.docx",
    )


def test_production_runner_rejects_tampered_private_criteria_before_provider(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    spec, _ = _run_spec(tmp_path)
    input_record = json.loads(spec.stdin_bytes)
    Path(input_record["private_task_json_path"]).write_text(
        json.dumps(
            {
                "id": "task",
                "criteria": [
                    {"id": f"criterion-{ordinal}", "text": "tampered"}
                    for ordinal in range(1, 24)
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[ProductionJudgeCall] = []
    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda call: (calls.append(call), _response(pricing))[1],
        attempt_writer=lambda _call, _response: None,
    )

    with pytest.raises(ValueError, match="does not match the pinned digest"):
        runner(LocalCliExecutionService(), spec, _Boundary())
    assert calls == []


def test_production_runner_parses_the_same_bytes_used_for_private_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pricing = _pricing()
    spec, _ = _run_spec(tmp_path)
    input_record = json.loads(spec.stdin_bytes)
    private_path = Path(input_record["private_task_json_path"])
    calls: list[ProductionJudgeCall] = []

    def snapshot_then_mutate(root: Path) -> tuple[str, Mapping[str, bytes]]:
        digest, files = harvey_lab_private_material_snapshot(root)
        private_path.write_text(
            json.dumps(
                {
                    "id": "task",
                    "criteria": [
                        {"id": f"criterion-{ordinal}", "text": "tampered"}
                        for ordinal in range(1, 24)
                    ],
                }
            ),
            encoding="utf-8",
        )
        return digest, files

    monkeypatch.setattr(
        "legalforecast.multiharness.harvey_lab_production_runner.harvey_lab_private_material_snapshot",
        snapshot_then_mutate,
    )

    def provider(call: ProductionJudgeCall) -> ProductionJudgeResponse:
        calls.append(call)
        assert call.criterion["text"] == f"rule-{call.request.ordinal}"
        return _response(pricing)

    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=provider,
        attempt_writer=lambda _call, _response: None,
    )
    runner(LocalCliExecutionService(), spec, _Boundary())
    assert len(calls) == 23


def test_production_runner_does_not_settle_unretained_response(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    spec, _ = _run_spec(tmp_path)
    boundary = _Boundary()

    def fail_retention(
        _call: ProductionJudgeCall, _response: ProductionJudgeResponse
    ) -> None:
        raise OSError("archive unavailable")

    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=lambda _call: _response(pricing),
        attempt_writer=fail_retention,
    )

    with pytest.raises(OSError, match="archive unavailable"):
        runner(LocalCliExecutionService(), spec, boundary)
    assert boundary.events == [("before", 1, 0)]
