"""Reviewer-facing mid-evaluator spend halt.

The independent 4.5.16 finding required a fake provider to stop at call 12 of
the 23 LAB criterion requests, with terminal evidence and no twelfth paid
call.  This test drives the production evaluator runner through the live
per-criterion spend boundary rather than calling SpendController.reserve
directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.multiharness.harvey_lab_production_runner import (
    ProductionHarveyLabEvaluatorRunner,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.spend import (
    SpendController,
    SpendDeniedError,
    SpendFailureClass,
    UsageObservation,
)
from legalforecast.multiharness.tier0_runner import (
    _OutstandingReservations,
    _PerCriterionEvaluatorSpendBoundary,
)
from tests.test_harvey_lab_production_runner import _run_spec
from tests.test_multiharness_spend import _bound_spec, _judge_cap, _policy, _pricing


def _halt_response(pricing_sha256: str) -> ProductionJudgeResponse:
    return ProductionJudgeResponse(
        verdict="pass",
        judge_resolved_identity="provider-a/model-a@resolved",
        usage=UsageObservation(
            basis="provider_reported",
            pricing_snapshot_sha256=pricing_sha256,
            input_tokens=10,
            output_tokens=5,
            reported_cost_usd="0.000012",
        ),
        raw_response=b"provider-response",
    )


def test_fake_provider_halts_before_judge_call_12_of_23(tmp_path: Path) -> None:
    pricing = _pricing()
    criteria = tuple(
        _judge_cap(
            f"criterion-{ordinal}",
            arm_id="arm-opaque-01",
            max_cost_usd="0.006000",
        )
        for ordinal in range(1, 24)
    )
    policy = _policy(
        experiment_cost="1.000000",
        experiment_requests=11,
        experiment_retries=2,
        judges=criteria,
    )
    controller = SpendController(policy, pricing)
    spec = _bound_spec(policy=policy, pricing=pricing)
    boundary = _PerCriterionEvaluatorSpendBoundary(
        controller=controller,
        spec=spec,
        arm=spec.arms[0],
        outstanding=_OutstandingReservations(),
    )
    run_spec, _scores_path = _run_spec(tmp_path)
    paid_calls: list[int] = []

    def provider(call: ProductionJudgeCall) -> ProductionJudgeResponse:
        paid_calls.append(call.request.ordinal)
        return _halt_response(pricing.snapshot_sha256)

    runner = ProductionHarveyLabEvaluatorRunner(
        provider_call=provider,
        attempt_writer=lambda _call, _response: None,
        pricing_snapshot=pricing,
        pricing_provider="provider-a",
        pricing_model="model-a",
        expected_judge_identity="provider-a/model-a@resolved",
    )

    with pytest.raises(SpendDeniedError) as raised:
        runner(LocalCliExecutionService(), run_spec, boundary)

    evidence = raised.value.evidence
    assert paid_calls == list(range(1, 12))
    assert evidence.criterion_id == "criterion-12"
    assert evidence.call_id.endswith("12-0")
    assert evidence.failure_class == SpendFailureClass.REQUEST_CAP
    assert evidence.terminal is True
    assert evidence.observed_cost_usd is None
    assert controller.terminal is True
    archive = controller.archive_record()
    assert archive["requests"] == 11
    assert archive["terminal"] is True
    assert archive["events"][-1]["call_id"] == evidence.call_id  # type: ignore[index]
    assert archive["events"][-1]["terminal"] is True  # type: ignore[index]


def test_production_response_refuses_fixture_identity_and_unknown_cost() -> None:
    pricing = _pricing()
    usage = UsageObservation(
        basis="provider_reported",
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        input_tokens=10,
        output_tokens=5,
        reported_cost_usd="0.000012",
    )
    with pytest.raises(ValueError, match="fixture judge identity"):
        ProductionJudgeResponse(
            verdict="pass",
            judge_resolved_identity="fixture/stub@local",
            usage=usage,
            raw_response=b"provider-response",
        )
    with pytest.raises(ValueError, match="allocable usage"):
        ProductionJudgeResponse(
            verdict="pass",
            judge_resolved_identity="provider-a/model-a@resolved",
            usage=UsageObservation.unknown("provider omitted cost"),
            raw_response=b"provider-response",
        )
