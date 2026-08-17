"""Provider-free tests for the Tier-0 spend-ceiling sidecar."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    harvey_lab_issuer_policy_sha256,
)
from legalforecast.multiharness.harvey_lab_evaluator import HarveyLabJudgeRequest
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
from legalforecast.multiharness.tier0_runner import (
    Tier0ArmSpec,
    Tier0ExecutableSpec,
    Tier0RunnerError,
    _OutstandingReservations,
    _PerCriterionEvaluatorSpendBoundary,
    _terminalize_outstanding,
    load_spend_artifacts,
)
from tests.test_harvey_lab_projection import FIXTURE_PIN

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
    arm_id: str = "arm-a",
    max_requests: int = 2,
    max_retries: int = 1,
    max_cost_usd: str = "0.003000",
) -> JudgeCriterionCeiling:
    return JudgeCriterionCeiling(
        arm_id=arm_id,
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
    experiment_requests: int = 8,
    experiment_retries: int = 4,
    experiment_parallelism: int = 1,
) -> SpendPolicy:
    return SpendPolicy(
        experiment_id="tier0-provider-free-test",
        executable_spec_sha256=SPEC,
        pricing_snapshot_sha256=_pricing().snapshot_sha256,
        experiment=ExperimentCeiling(
            max_cost_usd=experiment_cost,
            max_requests=experiment_requests,
            max_retries=experiment_retries,
            max_parallelism=experiment_parallelism,
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


def test_per_criterion_boundary_reserves_all_23_calls_and_enforces_caps() -> None:
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
        experiment_cost="0.069000",
        experiment_requests=25,
        experiment_retries=2,
        judges=criteria,
    )
    controller = SpendController(policy, pricing)
    spec = _bound_spec(policy=policy, pricing=pricing)
    outstanding = _OutstandingReservations()
    boundary = _PerCriterionEvaluatorSpendBoundary(
        controller=controller,
        spec=spec,
        arm=spec.arms[0],
        outstanding=outstanding,
    )

    reservations = []
    for ordinal in range(1, 24):
        request = HarveyLabJudgeRequest(ordinal, f"criterion-{ordinal}")
        reservation = boundary.before_judge_call(request)
        reservations.append(reservation)
        boundary.after_judge_call(request, reservation, _known_usage(pricing))

    assert len({item.call.call_id for item in reservations}) == 23
    assert [item.call.criterion_id for item in reservations] == [
        f"criterion-{ordinal}" for ordinal in range(1, 24)
    ]
    assert outstanding.snapshot() == ()
    assert controller.archive_record()["requests"] == 23

    cap_criteria = tuple(
        _judge_cap(
            f"criterion-{ordinal}",
            arm_id="arm-opaque-01",
            max_requests=3,
            max_retries=1,
            max_cost_usd="0.006000",
        )
        for ordinal in range(1, 24)
    )
    cap_policy = _policy(
        experiment_cost="0.009000",
        experiment_requests=4,
        experiment_retries=2,
        judges=cap_criteria,
    )
    cap_controller = SpendController(cap_policy, pricing)
    cap_boundary = _PerCriterionEvaluatorSpendBoundary(
        controller=cap_controller,
        spec=_bound_spec(policy=cap_policy, pricing=pricing),
        arm=spec.arms[0],
        outstanding=_OutstandingReservations(),
    )
    first = cap_boundary.before_judge_call(
        HarveyLabJudgeRequest(1, "criterion-1", attempt_index=0)
    )
    with pytest.raises(SpendDeniedError) as parallel:
        cap_boundary.before_judge_call(
            HarveyLabJudgeRequest(1, "criterion-1", attempt_index=1)
        )
    assert parallel.value.evidence.failure_class == SpendFailureClass.PARALLELISM_CAP
    cap_boundary.after_judge_call(
        HarveyLabJudgeRequest(1, "criterion-1", attempt_index=0),
        first,
        _known_usage(pricing),
    )

    retry = cap_boundary.before_judge_call(
        HarveyLabJudgeRequest(1, "criterion-1", attempt_index=1)
    )
    cap_boundary.after_judge_call(
        HarveyLabJudgeRequest(1, "criterion-1", attempt_index=1),
        retry,
        _known_usage(pricing),
    )
    with pytest.raises(SpendDeniedError) as retry_cap:
        cap_boundary.before_judge_call(
            HarveyLabJudgeRequest(1, "criterion-1", attempt_index=2)
        )
    assert retry_cap.value.evidence.failure_class == SpendFailureClass.RETRY_CAP


def test_per_criterion_boundary_hard_stops_before_the_next_request() -> None:
    pricing = _pricing()
    criteria = tuple(
        _judge_cap(
            f"criterion-{ordinal}",
            arm_id="arm-opaque-01",
            max_cost_usd="0.003000",
        )
        for ordinal in range(1, 24)
    )
    policy = _policy(
        experiment_cost="0.066000",
        experiment_requests=24,
        experiment_retries=1,
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
    invoked: list[str] = []
    for ordinal in range(1, 24):
        request = HarveyLabJudgeRequest(ordinal, f"criterion-{ordinal}")
        with pytest.raises(SpendDeniedError) if ordinal == 23 else nullcontext():
            reservation = boundary.before_judge_call(request)
            invoked.append(request.criterion_id)
            boundary.after_judge_call(request, reservation, _known_usage(pricing))
    assert len(invoked) == 22
    assert invoked[-1] == "criterion-22"
    assert controller.events[-1].call_id.endswith("23-0")
    assert controller.events[-1].terminal is True


def test_aggregate_judge_ceiling_is_rejected_by_the_evaluator_boundary() -> None:
    pricing = _pricing()
    policy = _policy(judges=(_judge_cap("aggregate", arm_id="arm-opaque-01"),))
    spec = _bound_spec(policy=policy, pricing=pricing)
    with pytest.raises(Tier0RunnerError, match="exactly 23"):
        _PerCriterionEvaluatorSpendBoundary(
            controller=SpendController(policy, pricing),
            spec=spec,
            arm=spec.arms[0],
            outstanding=_OutstandingReservations(),
        )


def test_raised_per_criterion_and_experiment_caps_change_policy_identity() -> None:
    criteria = tuple(
        _judge_cap(f"criterion-{ordinal}", arm_id="arm-opaque-01")
        for ordinal in range(1, 24)
    )
    baseline = _policy(judges=criteria, experiment_requests=23)
    raised_criterion = replace(criteria[0], max_cost_usd="0.006000")
    criterion_policy = _policy(
        judges=(raised_criterion, *criteria[1:]), experiment_requests=23
    )
    experiment_policy = _policy(
        judges=criteria, experiment_cost="0.069000", experiment_requests=23
    )
    assert baseline.policy_sha256 != criterion_policy.policy_sha256
    assert baseline.policy_sha256 != experiment_policy.policy_sha256


def test_policy_digest_changes_when_a_ceiling_is_raised() -> None:
    approved = _policy(judges=(_judge_cap(),))
    raised = _policy(solver_cost="9.000000", judges=(_judge_cap(),))
    assert approved.policy_sha256 != raised.policy_sha256
    assert approved.policy_sha256 == _policy(judges=(_judge_cap(),)).policy_sha256


def test_load_spend_artifacts_accepts_the_policy_the_spec_binds(tmp_path: Path) -> None:
    pricing = _pricing()
    policy = _policy(judges=(_judge_cap(),))
    spec_path = _write_spend_sidecars(tmp_path, policy=policy, pricing=pricing)
    spec = _bound_spec(policy=policy, pricing=pricing)
    loaded_policy, loaded_pricing = load_spend_artifacts(spec_path, spec)
    assert loaded_policy.policy_sha256 == policy.policy_sha256
    assert loaded_pricing.snapshot_sha256 == pricing.snapshot_sha256


def test_load_spend_artifacts_rejects_a_ceiling_raised_after_approval(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    approved = _policy(judges=(_judge_cap(),))
    spec = _bound_spec(policy=approved, pricing=pricing)
    raised = _policy(
        solver_cost="9.000000",
        experiment_cost="18.000000",
        judges=(_judge_cap(max_cost_usd="9.000000"),),
    )
    spec_path = _write_spend_sidecars(tmp_path, policy=raised, pricing=pricing)
    with pytest.raises(Tier0RunnerError, match="spend policy hash"):
        load_spend_artifacts(spec_path, spec)


def test_load_spend_artifacts_requires_the_spec_to_bind_the_policy(
    tmp_path: Path,
) -> None:
    pricing = _pricing()
    policy = _policy(judges=(_judge_cap(),))
    spec_path = _write_spend_sidecars(tmp_path, policy=policy, pricing=pricing)
    spec = replace(
        _bound_spec(policy=policy, pricing=pricing), spend_policy_sha256=None
    )
    with pytest.raises(Tier0RunnerError, match="must bind the spend policy hash"):
        load_spend_artifacts(spec_path, spec)


def test_outstanding_reservation_is_terminalized_as_unknown_cost() -> None:
    pricing = _pricing()
    controller = SpendController(_policy(judges=(_judge_cap(),)), pricing)
    reservation = controller.reserve(
        _call("judge-abandoned", surface="judge", criterion_id="criterion-1")
    )
    outstanding = {reservation.reservation_id: reservation}
    _terminalize_outstanding(controller, outstanding, "evaluator process failed")
    assert outstanding == {}
    assert controller.terminal
    evidence = controller.events[-1]
    assert evidence.decision == "settled"
    assert evidence.failure_class == SpendFailureClass.UNKNOWN_COST.value
    assert evidence.unknown_reason == "evaluator process failed"
    assert evidence.observed_cost_usd is None


def _bound_spec(
    *, policy: SpendPolicy, pricing: PricingSnapshot
) -> Tier0ExecutableSpec:
    digest = "sha256:" + "0" * 64
    spec = Tier0ExecutableSpec(
        experiment_id=policy.experiment_id,
        source_pin=FIXTURE_PIN,
        evaluator_command="evaluator",
        evaluator_wrapper_sha256=digest,
        issuer_key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        arms=(
            Tier0ArmSpec(
                arm_id="arm-opaque-01",
                adapter="claude-code-clean-native",
                auth_profile="fixture-none",
                requested_model="model-a",
                solver_executable="claude",
                solver_executable_sha256=digest,
                settings={},
            ),
            Tier0ArmSpec(
                arm_id="arm-opaque-02",
                adapter="harvey-lab",
                auth_profile="fixture-none",
                requested_model="model-a",
                solver_executable="native-thin",
                solver_executable_sha256=digest,
                command=("native-thin", "{sandbox_root}"),
                settings={},
            ),
        ),
    )
    return replace(
        spec,
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        spend_policy_sha256=policy.policy_sha256,
        artifact_sha256=policy.executable_spec_sha256,
    )


def _write_spend_sidecars(
    tmp_path: Path, *, policy: SpendPolicy, pricing: PricingSnapshot
) -> Path:
    spec_path = tmp_path / "tier0.executable-spec.json"
    write_json_object(spec_path, {})
    write_json_object(
        spec_path.with_name("tier0.executable-spec.pricing-snapshot.json"),
        pricing.to_record(),
    )
    write_json_object(
        spec_path.with_name("tier0.executable-spec.spend-policy.json"),
        policy.to_record(),
    )
    return spec_path
