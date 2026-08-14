"""Published metrics reconstruct from hashed artifacts."""

from __future__ import annotations

import json
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
from legalforecast.multiharness.scoring import ScoreArtifact
from legalforecast.publication.accounting import (
    observation_from_receipts,
    observation_sha256,
)
from legalforecast.publication.metric_propagation import (
    MetricReconstructionError,
    metrics_from_artifacts,
    verify_metric_traces,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"k" * 32)
SCORE_FIXTURE = (
    Path(__file__).parent / "fixtures/harvey_lab/authorized-score-all-pass.golden.json"
)


def _receipt(tmp_path: Path) -> ExecutionReceipt:
    spec = RunSpec(
        spec_id="fixture-spec",
        argv=("claude", "--print"),
        working_directory=tmp_path,
        timeout_seconds=30,
    )
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout='{"ok":true}',
        duration_ms=40,
        usage={"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
        cost_usd=0.125,
        status="succeeded",
        returncode=0,
    )
    task = derive_task_identity(
        task_id="lab.task-1",
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="harvey-lab-fixture",
        task_sha256=DIGEST_A,
    )
    solver = derive_solver_identity(
        provider="anthropic",
        requested_model="claude-opus-4",
        settings_sha256=DIGEST_B,
        served_model="claude-opus-4",
    )
    run = derive_run_identity(
        task=task,
        solver=solver,
        runtime_policy_sha256=DIGEST_C,
        config_sha256=DIGEST_D,
        temporal_block="cycle-1",
        order=0,
        repeat_index=0,
    )
    return receipt.with_identity_keys(task=task, solver=solver, run=run)


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


def test_metrics_trace_every_displayed_figure_to_an_artifact_hash(
    tmp_path: Path,
) -> None:
    observation = observation_from_receipts(
        (_receipt(tmp_path),),
        evaluation=_evaluation(),
    )
    score = ScoreArtifact.from_record(json.loads(SCORE_FIXTURE.read_text()))
    digest = observation_sha256(observation)
    metrics = metrics_from_artifacts(
        scores=(score,),
        observation=observation,
        selected_count=1,
        solved_count=1,
        evaluated_count=1,
        group_size=1,
        score_artifact_sha256s=(score.score_sha256,),
        observation_sha256=digest,
    )
    assert metrics.score_value == 1
    assert metrics.coverage_percentage == 100
    assert all(trace.source_artifact_sha256s for trace in metrics.traces)
    verify_metric_traces(
        metrics.traces,
        artifacts_by_hash={
            digest: {
                **observation.to_record(),
                "selected_count": 1,
                "coverage_percentage": 100,
                "cost_usd": metrics.cost_usd,
                "score_value": None,
            },
            score.score_sha256: score.to_record(),
        },
    )


def test_hand_edited_metric_fails_reconstruction(tmp_path: Path) -> None:
    observation = observation_from_receipts((_receipt(tmp_path),))
    digest = observation_sha256(observation)
    metrics = metrics_from_artifacts(
        scores=(),
        observation=observation,
        selected_count=1,
        solved_count=1,
        evaluated_count=1,
        group_size=1,
        score_artifact_sha256s=(),
        observation_sha256=digest,
    )
    mutated = []
    for trace in metrics.traces:
        if trace.field_name == "cost_usd":
            mutated.append(
                type(trace)(
                    field_name=trace.field_name,
                    displayed_value=999.0,
                    source_artifact_sha256s=trace.source_artifact_sha256s,
                    source_field=trace.source_field,
                    reduce=trace.reduce,
                    schema_version=trace.schema_version,
                )
            )
        else:
            mutated.append(trace)
    with pytest.raises(MetricReconstructionError, match="does not reconstruct"):
        verify_metric_traces(
            mutated,
            artifacts_by_hash={
                digest: {
                    **observation.to_record(),
                    "selected_count": 1,
                    "coverage_percentage": 100,
                    "score_value": None,
                }
            },
        )
