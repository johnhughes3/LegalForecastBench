"""Provider-free tests for the injected production LAB judge seam."""

from __future__ import annotations

import json
from pathlib import Path

from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
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


class _Boundary(HarveyLabJudgeRequestBoundary):
    def __init__(self) -> None:
        self.events: list[tuple[str, int, int]] = []

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


def test_production_runner_calls_provider_per_criterion_and_retains_retries(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    scores_path = tmp_path / "overlay" / "raw" / "scores.json"
    spec = RunSpec(
        spec_id="production-evaluator",
        argv=("harvey-lab-eval",),
        working_directory=tmp_path,
        stdin_bytes=json.dumps(
            {"scores_output_path": str(scores_path)}, separators=(",", ":")
        ).encode("utf-8"),
    )
    criteria = tuple({"id": f"criterion-{ordinal}"} for ordinal in range(1, 24))
    calls: list[ProductionJudgeCall] = []
    attempts: list[ProductionJudgeCall] = []
    first = True

    def provider(call: ProductionJudgeCall) -> ProductionJudgeResponse:
        nonlocal first
        calls.append(call)
        response = _response(pricing, retryable=first)
        first = False
        return response

    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=provider,
        criteria=criteria,
        attempt_writer=lambda call, _response: attempts.append(call),
        pricing_snapshot=pricing,
        pricing_provider="provider",
        pricing_model="judge-model",
        expected_judge_identity="provider/judge-model@resolved-1",
    )
    boundary = _Boundary()
    receipt = runner(LocalCliExecutionService(), spec, boundary)

    assert receipt.status == "succeeded"
    assert len(calls) == 24
    assert len(attempts) == 24
    assert calls[0].request == HarveyLabJudgeRequest(1, "criterion-1", 0)
    assert calls[1].request == HarveyLabJudgeRequest(1, "criterion-1", 1)
    assert len(boundary.events) == 48
    assert boundary.events[0] == ("before", 1, 0)
    assert boundary.events[1] == ("after", 1, 0)
    assert boundary.events[2] == ("before", 1, 1)
    assert boundary.events[3] == ("after", 1, 1)
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert scores["n_criteria"] == 23
    assert scores["n_passed"] == 23
    assert receipt.usage == {"input_tokens": 240, "output_tokens": 120}
