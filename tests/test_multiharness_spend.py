"""Provider-free tests for the Tier-0 spend-ceiling sidecar."""

from __future__ import annotations

from dataclasses import replace

import pytest
from legalforecast.multiharness.spend import (
    ExperimentCeiling,
    InvocationBudget,
    JudgeCriterionCeiling,
    PaidCall,
    PricingRate,
    PricingSnapshot,
    SolverCeiling,
    SpendConfigurationError,
    SpendController,
    SpendDeniedError,
    SpendFailureClass,
    SpendPolicy,
    SpendSettlementError,
    UsageObservation,
)

SPEC = "sha256:" + "a" * 64


def _pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_id="synthetic-pricing-2026-08-17",
        as_of_date="2026-08-17",
        rates=(
            PricingRate(
                provider="provider-a",
                model="model-a",
                input_microusd_per_token=10,
                output_microusd_per_token=20,
            ),
        ),
    )


def _solver_cap(max_cost_usd: str = "0.003000") -> SolverCeiling:
    return SolverCeiling(
        arm_id="arm-a",
        provider="provider-a",
        model="model-a",
        max_cost_usd=max_cost_usd,
        max_requests=2,
        max_retries=1,
        max_parallelism=1,
        max_input_tokens=100,
        max_output_tokens=100,
        invocation_budget=InvocationBudget(
            mode="adapter_argument",
            argument_name="--max-budget-usd",
            argument_value_usd=max_cost_usd,
            advertised_budget_usd="9.000000",
        ),
    )


def _judge_cap(
    criterion_id: str = "criterion-1",
    *,
    max_requests: int = 2,
    max_retries: int = 1,
    max_cost_usd: str = "0.003000",
) -> JudgeCriterionCeiling:
    return JudgeCriterionCeiling(
        arm_id="arm-a",
        criterion_id=criterion_id,
        provider="provider-a",
        model="model-a",
        max_cost_usd=max_cost_usd,
        max_requests=max_requests,
        max_retries=max_retries,
        max_parallelism=1,
        max_input_tokens=100,
        max_output_tokens=100,
        invocation_budget=InvocationBudget(
            mode="controller_reservation",
            advertised_budget_usd="0.000001",
        ),
    )


def _policy(
    *,
    solver_cost: str = "0.003000",
    experiment_cost: str = "0.006000",
    solver: SolverCeiling | None = None,
    judges: tuple[JudgeCriterionCeiling, ...] = (),
) -> SpendPolicy:
    return SpendPolicy(
        experiment_id="tier0-provider-free-test",
        executable_spec_sha256=SPEC,
        pricing_snapshot_sha256=_pricing().snapshot_sha256,
        experiment=ExperimentCeiling(
            max_cost_usd=experiment_cost,
            max_requests=8,
            max_retries=4,
            max_parallelism=1,
        ),
        solver_ceilings=(solver or _solver_cap(solver_cost),),
        judge_ceilings=judges,
    )


def _call(
    call_id: str,
    *,
    arm_id: str = "arm-a",
    surface: str = "solver",
    attempt_index: int = 0,
    criterion_id: str | None = None,
) -> PaidCall:
    return PaidCall(
        call_id=call_id,
        surface=surface,  # type: ignore[arg-type]
        arm_id=arm_id,
        provider="provider-a",
        model="model-a",
        executable_spec_sha256=SPEC,
        pricing_snapshot_sha256=_pricing().snapshot_sha256,
        attempt_index=attempt_index,
        criterion_id=criterion_id,
    )


def _known_usage(pricing: PricingSnapshot) -> UsageObservation:
    return UsageObservation(
        basis="provider_reported",
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        input_tokens=100,
        output_tokens=100,
    )


def _maxed_usage(pricing: PricingSnapshot) -> UsageObservation:
    return UsageObservation(
        basis="provider_reported",
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        input_tokens=100,
        output_tokens=100,
        reported_cost_usd="0.003000",
    )


def test_policy_and_archive_bind_exact_spec_budget_and_dated_pricing() -> None:
    pricing = _pricing()
    policy = _policy(judges=(_judge_cap(),))
    controller = SpendController(policy, pricing)

    archive = controller.archive_record()
    assert archive["executable_spec_sha256"] == SPEC
    assert archive["pricing_snapshot"]["snapshot_sha256"] == pricing.snapshot_sha256  # type: ignore[index]
    policy_record = archive["policy"]
    assert isinstance(policy_record, dict)
    assert policy_record["experiment"]["max_cost_usd"] == "0.006000"  # type: ignore[index]
    assert (
        policy_record["solver_ceilings"][0]["invocation_budget"]["argument_name"]
        == "--max-budget-usd"
    )  # type: ignore[index]


def test_solver_dollar_ceiling_denies_before_next_paid_request() -> None:
    pricing = _pricing()
    controller = SpendController(_policy(), pricing)
    first = controller.reserve(_call("solver-1"))
    controller.settle(first, _maxed_usage(pricing))

    with pytest.raises(SpendDeniedError) as raised:
        controller.reserve(_call("solver-2"))
    assert raised.value.evidence.failure_class == SpendFailureClass.OVER_BUDGET
    assert raised.value.evidence.terminal is True
    assert raised.value.evidence.observed_cost_usd is None
    assert controller.archive_record()["events"][-1]["terminal"] is True  # type: ignore[index]


def test_raising_a_cap_changes_where_the_run_halts() -> None:
    pricing = _pricing()
    baseline = SpendController(_policy(solver_cost="0.003000"), pricing)
    first = baseline.reserve(_call("baseline-1"))
    baseline.settle(first, _maxed_usage(pricing))
    with pytest.raises(SpendDeniedError):
        baseline.reserve(_call("baseline-2"))

    raised = SpendController(_policy(solver_cost="0.006000"), pricing)
    first = raised.reserve(_call("raised-1"))
    raised.settle(first, _maxed_usage(pricing))
    second = raised.reserve(_call("raised-2"))
    assert second.sequence == 2


def test_stripped_pricing_snapshot_refuses_before_credentials() -> None:
    with pytest.raises(SpendConfigurationError, match="pricing snapshot"):
        SpendController(_policy(), None)


def test_missing_provider_model_rate_refuses_before_credentials() -> None:
    pricing = PricingSnapshot(
        snapshot_id="different-models",
        as_of_date="2026-08-17",
        rates=(PricingRate("provider-a", "other-model", 10, 20),),
    )
    policy = replace(_policy(), pricing_snapshot_sha256=pricing.snapshot_sha256)
    with pytest.raises(SpendConfigurationError, match="no auditable rate"):
        SpendController(policy, pricing)


def test_judge_caps_include_retries_and_stop_before_the_third_attempt() -> None:
    pricing = _pricing()
    policy = _policy(
        judges=(
            _judge_cap(
                max_requests=3,
                max_retries=1,
                max_cost_usd="0.009000",
            ),
        )
    )
    controller = SpendController(policy, pricing)
    first = controller.reserve(
        _call("judge-1", surface="judge", criterion_id="criterion-1")
    )
    controller.settle(first, _known_usage(pricing))
    retry = controller.reserve(
        _call(
            "judge-retry",
            surface="judge",
            criterion_id="criterion-1",
            attempt_index=1,
        )
    )
    controller.settle(retry, _known_usage(pricing))
    with pytest.raises(SpendDeniedError) as raised:
        controller.reserve(
            _call(
                "judge-third",
                surface="judge",
                criterion_id="criterion-1",
                attempt_index=2,
            )
        )
    assert raised.value.evidence.failure_class == SpendFailureClass.RETRY_CAP
    assert raised.value.evidence.terminal is True


def test_parallelism_cap_denies_while_a_paid_call_is_in_flight() -> None:
    pricing = _pricing()
    controller = SpendController(_policy(solver_cost="0.006000"), pricing)
    first = controller.reserve(_call("in-flight"))
    with pytest.raises(SpendDeniedError) as raised:
        controller.reserve(_call("parallel"))
    assert raised.value.evidence.failure_class == SpendFailureClass.PARALLELISM_CAP
    assert raised.value.evidence.terminal is False
    controller.settle(first, _known_usage(pricing))
    next_call = controller.reserve(_call("after-release"))
    assert next_call.sequence == 2


def test_experiment_wide_hard_stop_prevents_next_arm_request() -> None:
    pricing = _pricing()
    arm_a = _solver_cap("0.006000")
    arm_b = replace(arm_a, arm_id="arm-b")
    policy = replace(
        _policy(solver_cost="0.006000", experiment_cost="0.003000"),
        solver_ceilings=(arm_a, arm_b),
    )
    controller = SpendController(policy, pricing)
    first = controller.reserve(_call("arm-a-call", arm_id="arm-a"))
    controller.settle(first, _maxed_usage(pricing))
    with pytest.raises(SpendDeniedError) as raised:
        controller.reserve(_call("arm-b-call", arm_id="arm-b"))
    assert raised.value.evidence.failure_class == SpendFailureClass.OVER_BUDGET
    assert raised.value.evidence.terminal is True


def test_pricing_without_auditable_token_fields_is_rejected() -> None:
    with pytest.raises(SpendConfigurationError, match="input_tokens"):
        PricingRate(
            provider="provider-a",
            model="model-a",
            input_microusd_per_token=10,
            output_microusd_per_token=20,
            usage_fields=("total_tokens",),
        )


@pytest.mark.parametrize(
    "observation",
    [
        UsageObservation.unknown("solver timed out"),
        UsageObservation.unknown(
            "flat subscription has no allocation", subscription=True
        ),
    ],
)
def test_timeout_and_subscription_costs_are_nonnumeric_terminal_stops(
    observation: UsageObservation,
) -> None:
    pricing = _pricing()
    controller = SpendController(_policy(), pricing)
    reservation = controller.reserve(_call("unknown-cost"))
    with pytest.raises(SpendSettlementError):
        controller.settle(reservation, observation)
    archive = controller.archive_record()
    assert archive["spent_usd"] is None
    assert archive["cost_unknown_reason"] == observation.unknown_reason
    with pytest.raises(SpendDeniedError) as raised:
        controller.reserve(_call("must-not-run"))
    assert raised.value.evidence.terminal is True
    assert raised.value.evidence.observed_cost_usd is None


def test_advertised_budget_without_invocation_enforcement_is_not_a_ceiling() -> None:
    pricing = _pricing()
    # Judge paths use controller reservation.  The tiny advertised value is
    # intentionally ignored; the actual cap is the policy's exact value.
    controller = SpendController(
        _policy(judges=(_judge_cap(max_cost_usd="0.003000"),)), pricing
    )
    reservation = controller.reserve(
        _call("judge-advertised-only", surface="judge", criterion_id="criterion-1")
    )
    assert reservation.max_cost_usd == "0.003000"


def test_solver_without_supported_invocation_cap_fails_closed() -> None:
    with pytest.raises(SpendConfigurationError, match="enforced budget"):
        _solver_cap_with_mode("controller_reservation")


def _solver_cap_with_mode(mode: str) -> SolverCeiling:
    return SolverCeiling(
        arm_id="arm-a",
        provider="provider-a",
        model="model-a",
        max_cost_usd="0.003000",
        max_requests=1,
        max_retries=0,
        max_parallelism=1,
        max_input_tokens=100,
        max_output_tokens=100,
        invocation_budget=InvocationBudget(mode=mode),  # type: ignore[arg-type]
    )
