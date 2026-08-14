from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationTokenUsage,
    MonotonicTiming,
    TokenCount,
    build_evaluation_receipt,
    build_evaluation_spec,
)
from legalforecast.multiharness.identity import (
    derive_run_identity,
    derive_solver_identity,
    derive_task_identity,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.publication.accounting import (
    ACCOUNTING_DEFINITIONS,
    AccountingError,
    HarnessEfficiencyObservation,
    billed_solve_tokens,
    clocks_may_differ,
    combine_costs,
    combine_solve_tokens,
    cost_ratio,
    observation_from_receipts,
    published_spread,
    refuse_collapsed_clocks,
    refuse_faux_variance,
    require_compatible_cost_bases,
    solve_cost_from_receipts,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"k" * 32)


def _task():
    return derive_task_identity(
        task_id="lab.task-1",
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="harvey-lab-fixture",
        task_sha256=DIGEST_A,
    )


def _solver():
    return derive_solver_identity(
        provider="anthropic",
        requested_model="claude-opus-4",
        settings_sha256=DIGEST_B,
        served_model="claude-opus-4",
    )


def _run(*, repeat_index: int = 0):
    return derive_run_identity(
        task=_task(),
        solver=_solver(),
        runtime_policy_sha256=DIGEST_C,
        config_sha256=DIGEST_D,
        temporal_block="cycle-1",
        order=0,
        repeat_index=repeat_index,
    )


def _receipt(
    tmp_path: Path,
    *,
    spec_id: str = "fixture-spec",
    duration_ms: int = 40,
    usage: dict[str, int] | None = None,
    cost_usd: float | None = 0.125,
    status: str = "succeeded",
    repeat_index: int = 0,
) -> ExecutionReceipt:
    spec = RunSpec(
        spec_id=spec_id,
        argv=("claude", "--print"),
        working_directory=tmp_path,
        timeout_seconds=30,
    )
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout='{"ok":true}',
        duration_ms=duration_ms,
        usage=usage or {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
        cost_usd=cost_usd,
        status=status,
        returncode=0 if status == "succeeded" else 1,
    )
    run = _run(repeat_index=repeat_index)
    return receipt.with_identity_keys(task=_task(), solver=_solver(), run=run)


def _evaluation():
    spec = build_evaluation_spec(
        evaluation_id="harvey-lab-employment-v1",
        deliverable_manifest_sha256=DIGEST_A,
        deliverable_tree_sha256=DIGEST_B,
        task_sha256=DIGEST_C,
        run_sha256=DIGEST_D,
        config_sha256=DIGEST_A,
        evaluator_repository="https://github.com/harveyai/harvey-labs",
        evaluator_commit="7" * 40,
        evaluator_tree="8" * 40,
        evaluator_file_manifest_sha256=DIGEST_B,
        evaluator_image_digest=DIGEST_C,
        wrapper_sha256=DIGEST_D,
        private_material_sha256=DIGEST_A,
        rubric_sha256=DIGEST_B,
        criteria_sha256=DIGEST_C,
        aggregation_sha256=DIGEST_D,
        judge_requested_identity="anthropic/claude-sonnet-4-6",
        judge_settings_sha256=DIGEST_A,
        judge_prompt_sha256=DIGEST_B,
        judge_output_schema_sha256=DIGEST_C,
        runtime_policy_sha256=DIGEST_D,
        egress_policy_sha256=DIGEST_A,
        resource_policy_sha256=DIGEST_B,
        token_accounting_policy_sha256=DIGEST_C,
    )
    return build_evaluation_receipt(
        spec=spec,
        signer=PRIVATE_KEY.sign,
        measurement_id="measurement-001",
        evaluation_attempt_id="eval-attempt-001",
        attempt_nonce="nonce-001",
        repeat_index=1,
        judge_resolved_identity="anthropic/claude-sonnet-4-6@resolved",
        raw_result_sha256=DIGEST_D,
        raw_result_size_bytes=12,
        raw_result_media_type="application/json",
        status="succeeded",
        token_usage=EvaluationTokenUsage(
            source="provider_response",
            input_tokens=TokenCount(value=50, unknown_reason=None),
            output_tokens=TokenCount(value=10, unknown_reason=None),
            cache_read_tokens=TokenCount(value=None, unknown_reason="not_reported"),
            cache_write_tokens=TokenCount(value=None, unknown_reason="not_reported"),
            reasoning_tokens=TokenCount(value=None, unknown_reason="not_reported"),
            total_tokens=TokenCount(value=60, unknown_reason=None),
        ),
        cost=CostMeasurement(
            amount_microusd=25_000,
            currency="USD",
            basis="provider_reported",
            pricing_snapshot_sha256=None,
            unknown_reason=None,
        ),
        timing=MonotonicTiming(
            clock_id="linux-clock-monotonic-raw",
            started_at_utc="2026-07-30T10:00:00Z",
            ended_at_utc="2026-07-30T10:00:01Z",
            started_monotonic_ns=0,
            ended_monotonic_ns=1_000_000_000,
            wall_elapsed_ns=1_000_000_000,
            queue_elapsed_ns=0,
            summed_call_elapsed_ns=1_500_000_000,
        ),
        issuer_policy_sha256=DIGEST_A,
        issuer_key_id="issuer-1",
    )


def test_unknown_usage_is_null_with_reason() -> None:
    billed = billed_solve_tokens({})
    assert billed.value is None
    assert billed.unknown_reason == "not_reported"


def test_cache_and_reasoning_are_not_added_on_top_of_total() -> None:
    billed = billed_solve_tokens(
        {
            "input_tokens": 80,
            "output_tokens": 20,
            "cache_read_tokens": 400,
            "reasoning_tokens": 15,
            "total_tokens": 100,
        }
    )
    assert billed.value == 100


def test_retries_are_counted_once_per_receipt_id(tmp_path: Path) -> None:
    first = _receipt(tmp_path, spec_id="attempt-1")
    duplicate = first
    second = _receipt(tmp_path, spec_id="attempt-2", usage={"total_tokens": 30})
    combined = combine_solve_tokens((first, duplicate, second))
    assert combined.value == 130


def test_subscription_unallocable_cost_is_never_zero(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path, cost_usd=None)
    cost = solve_cost_from_receipts((receipt,), cost_basis="subscription_unallocable")
    assert cost.amount_microusd is None
    assert cost.basis == "subscription_unallocable"
    with pytest.raises(AccountingError, match="never \\$0"):
        solve_cost_from_receipts(
            (_receipt(tmp_path, cost_usd=0.0),),
            cost_basis="subscription_unallocable",
        )


def test_wall_clock_differs_from_summed_call_time(tmp_path: Path) -> None:
    observation = observation_from_receipts(
        (_receipt(tmp_path, duration_ms=40),),
        evaluation=_evaluation(),
    )
    assert observation.wall_elapsed_ms == 40
    assert observation.summed_call_elapsed_ms == 1500
    assert clocks_may_differ(
        observation.wall_elapsed_ms,
        observation.summed_call_elapsed_ms,
    )
    with pytest.raises(AccountingError, match="distinct clocks"):
        refuse_collapsed_clocks(
            wall_elapsed_ms=observation.wall_elapsed_ms,
            summed_call_elapsed_ms=observation.summed_call_elapsed_ms,
            claimed_equal=True,
        )


def test_cost_ratios_require_compatible_bases() -> None:
    metered = CostMeasurement(
        amount_microusd=1000,
        currency="USD",
        basis="metered",
        pricing_snapshot_sha256=None,
        unknown_reason=None,
    )
    estimated = CostMeasurement(
        amount_microusd=2000,
        currency="USD",
        basis="estimated_from_pricing_snapshot",
        pricing_snapshot_sha256=DIGEST_A,
        unknown_reason=None,
    )
    unallocable = CostMeasurement(
        amount_microusd=None,
        currency=None,
        basis="subscription_unallocable",
        pricing_snapshot_sha256=None,
        unknown_reason="flat_subscription_has_no_per_call_allocation",
    )
    with pytest.raises(AccountingError, match="compatible bases"):
        require_compatible_cost_bases(metered, estimated)
    with pytest.raises(AccountingError, match="never \\$0"):
        require_compatible_cost_bases(metered, unallocable)
    assert float(
        cost_ratio(metered, replace(metered, amount_microusd=2000))
    ) == pytest.approx(0.5)


def test_n1_has_no_faux_variance() -> None:
    assert published_spread((0.1,), repeat_count=1) is None
    with pytest.raises(AccountingError, match="faux variance"):
        refuse_faux_variance(repeat_count=1, published_stddev=0.01)
    spread = published_spread((0.1, 0.3), repeat_count=2)
    assert spread is not None
    assert spread > 0


def test_observation_round_trips_and_binds_receipt_hashes(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    evaluation = _evaluation()
    observation = observation_from_receipts((receipt,), evaluation=evaluation)
    restored = HarnessEfficiencyObservation.from_record(observation.to_record())
    assert restored == observation
    assert observation.execution_receipt_sha256 == receipt.public_sha256()
    assert observation.evaluation_receipt_sha256 == evaluation.receipt_sha256
    assert observation.total_tokens.value == 160
    assert observation.combined_cost.amount_microusd == 150_000
    assert set(ACCOUNTING_DEFINITIONS) >= {
        "solve_tokens",
        "wall_elapsed_ms",
        "summed_call_elapsed_ms",
    }


def test_combine_costs_keeps_subscription_null() -> None:
    known = CostMeasurement(
        amount_microusd=1000,
        currency="USD",
        basis="provider_reported",
        pricing_snapshot_sha256=None,
        unknown_reason=None,
    )
    unallocable = CostMeasurement(
        amount_microusd=None,
        currency=None,
        basis="subscription_unallocable",
        pricing_snapshot_sha256=None,
        unknown_reason="flat_subscription_has_no_per_call_allocation",
    )
    combined = combine_costs(known, unallocable)
    assert combined.amount_microusd is None
    assert combined.basis == "subscription_unallocable"
