from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationReceipt,
    EvaluationSpec,
    EvaluationTokenUsage,
    MonotonicTiming,
    TokenCount,
    build_evaluation_receipt,
    build_evaluation_spec,
)
from legalforecast.multiharness.scoring import (
    LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
    METRIC_DEFINITION_SCHEMA_VERSION,
    SCORE_ARTIFACT_SCHEMA_VERSION,
    MetricDefinition,
    ScoreArtifact,
    ScoreNormalizationError,
    build_harvey_lab_metric_definition,
    normalize_harvey_lab_score,
)


def _digest(character: str) -> str:
    return "sha256:" + character * 64


KEY = Ed25519PrivateKey.from_private_bytes(b"s" * 32)


def _spec(
    *,
    rubric: str = _digest("d"),
    criteria: str = _digest("e"),
    aggregation: str = _digest("f"),
    output_schema: str = _digest("c"),
) -> EvaluationSpec:
    return build_evaluation_spec(
        evaluation_id="harvey-lab-employment-v1",
        deliverable_manifest_sha256=_digest("1"),
        deliverable_tree_sha256=_digest("2"),
        task_sha256=_digest("3"),
        run_sha256=_digest("4"),
        config_sha256=_digest("5"),
        evaluator_repository="https://github.com/harveyai/harvey-labs",
        evaluator_commit="7" * 40,
        evaluator_tree="8" * 40,
        evaluator_file_manifest_sha256=_digest("a"),
        evaluator_image_digest=_digest("b"),
        wrapper_sha256=_digest("c"),
        private_material_sha256=_digest("d"),
        rubric_sha256=rubric,
        criteria_sha256=criteria,
        aggregation_sha256=aggregation,
        judge_requested_identity="anthropic/claude-sonnet-4-6",
        judge_settings_sha256=_digest("a"),
        judge_prompt_sha256=_digest("b"),
        judge_output_schema_sha256=output_schema,
        runtime_policy_sha256=_digest("6"),
        egress_policy_sha256=_digest("d"),
        resource_policy_sha256=_digest("e"),
        token_accounting_policy_sha256=_digest("f"),
    )


def _raw(verdicts: tuple[str, ...], **changes: object) -> bytes:
    n_passed = verdicts.count("pass")
    record: dict[str, object] = {
        "schema_version": LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
        "verdicts": [
            {"ordinal": index, "verdict": verdict}
            for index, verdict in enumerate(verdicts, start=1)
        ],
        "score": 1 if n_passed == len(verdicts) else 0,
        "n_passed": n_passed,
        "n_criteria": len(verdicts),
    }
    record.update(changes)
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _receipt(
    spec: EvaluationSpec, raw: bytes, *, status: str = "succeeded"
) -> EvaluationReceipt:
    unknown = TokenCount(None, "not_reported")
    return build_evaluation_receipt(
        spec=spec,
        signer=KEY.sign,
        measurement_id="measurement-001",
        evaluation_attempt_id="attempt-001",
        attempt_nonce="nonce-001",
        repeat_index=1,
        judge_resolved_identity="anthropic/claude-sonnet-4-6@2026-07-15",
        raw_result_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        raw_result_size_bytes=len(raw),
        raw_result_media_type="application/json",
        status=status,
        token_usage=EvaluationTokenUsage(
            source="provider_response",
            input_tokens=unknown,
            output_tokens=unknown,
            cache_read_tokens=unknown,
            cache_write_tokens=unknown,
            reasoning_tokens=unknown,
            total_tokens=unknown,
        ),
        cost=CostMeasurement(None, None, "unknown", None, "not_reported"),
        timing=MonotonicTiming(
            "clock-1",
            "2026-07-30T10:00:00Z",
            "2026-07-30T10:00:00.000001Z",
            1,
            1001,
            1000,
            0,
            1000,
        ),
        issuer_policy_sha256=_digest("8"),
        issuer_key_id="evaluation-key-1",
    )


def _metric(spec: EvaluationSpec) -> MetricDefinition:
    return build_harvey_lab_metric_definition(
        rubric_sha256=spec.rubric_sha256,
        criteria_sha256=spec.criteria_sha256,
        aggregation_sha256=spec.aggregation_sha256,
        output_schema_sha256=spec.judge_output_schema_sha256,
    )


def _score(
    verdicts: tuple[str, ...],
    *,
    spec: EvaluationSpec | None = None,
    raw_override: bytes | None = None,
    status: str = "succeeded",
    expected_metric_sha256: str | None = None,
) -> ScoreArtifact:
    bound_spec = spec or _spec()
    raw = raw_override or _raw(verdicts)
    receipt = _receipt(bound_spec, raw, status=status)
    metric = _metric(bound_spec)
    return normalize_harvey_lab_score(
        receipt=receipt,
        raw_result=raw,
        spec=bound_spec,
        metric=metric,
        expected_metric_definition_sha256=(
            expected_metric_sha256 or metric.definition_sha256
        ),
        expected_media_type="application/json",
        expected_spec_sha256=bound_spec.spec_sha256,
        expected_deliverable_manifest_sha256=(bound_spec.deliverable_manifest_sha256),
        expected_runtime_policy_sha256=bound_spec.runtime_policy_sha256,
        expected_issuer_policy_sha256=_digest("8"),
        expected_issuer_key_id="evaluation-key-1",
        issuer_public_key=KEY.public_key(),
        expected_measurement_id=receipt.measurement_id,
        expected_evaluation_attempt_id=receipt.evaluation_attempt_id,
        expected_attempt_nonce=receipt.attempt_nonce,
        expected_repeat_index=receipt.repeat_index,
    )


def test_pinned_lab_all_pass_is_exactly_one() -> None:
    score = _score(("pass",) * 23)
    assert score.schema_version == SCORE_ARTIFACT_SCHEMA_VERSION
    assert score.score_value == 1
    assert score.n_passed == score.n_criteria == 23


def test_any_failure_is_zero_and_counts_are_diagnostic_only() -> None:
    score = _score(("pass",) * 22 + ("fail",))
    assert score.score_value == 0
    assert (score.n_passed, score.n_criteria) == (22, 23)
    assert score.score_value != score.n_passed / score.n_criteria


def test_contracts_round_trip_and_score_is_aggregate_only() -> None:
    spec = _spec()
    metric = _metric(spec)
    score = _score(("pass",) * 23, spec=spec)
    assert metric.schema_version == METRIC_DEFINITION_SCHEMA_VERSION
    assert MetricDefinition.from_record(metric.to_record()) == metric
    assert ScoreArtifact.from_record(score.to_record()) == score
    rendered = str(score.to_record())
    for forbidden in (
        "verdict",
        "ordinal",
        "cost",
        "timing",
        "token",
        "uncertainty",
        "reasoning",
        "rubric_text",
    ):
        assert forbidden not in rendered


def test_metric_definition_is_externally_pinned_and_matches_spec() -> None:
    with pytest.raises(ScoreNormalizationError, match="authorized definition"):
        _score(("pass",) * 23, expected_metric_sha256=_digest("0"))


def test_failed_receipt_cannot_be_scored() -> None:
    with pytest.raises(ScoreNormalizationError, match="succeeded"):
        _score(("pass",) * 23, status="failed")


@pytest.mark.parametrize(
    "raw",
    (
        _raw(("pass",) * 22),
        _raw(("pass",) * 23, n_passed=22),
        _raw(("pass",) * 23, score=0),
        _raw(("pass",) * 23, extra="forbidden"),
        _raw(("pass",) * 23).replace(b'"score":1', b'"score":1,"score":1'),
        _raw(("pass",) * 22 + ("missing",)),
        json.dumps(
            {
                "schema_version": LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
                "verdicts": [
                    {"ordinal": 1, "verdict": "pass"},
                    {"ordinal": 1, "verdict": "pass"},
                ],
                "score": 1,
                "n_passed": 2,
                "n_criteria": 2,
            },
            separators=(",", ":"),
        ).encode(),
    ),
)
def test_raw_lab_parser_rejects_missing_inconsistent_unknown_or_duplicate(
    raw: bytes,
) -> None:
    with pytest.raises(ScoreNormalizationError):
        _score(("pass",) * 23, raw_override=raw)


@pytest.mark.parametrize(
    "second_spec",
    (
        _spec(rubric=_digest("1")),
        _spec(criteria=_digest("1")),
        _spec(aggregation=_digest("1")),
        _spec(output_schema=_digest("1")),
    ),
)
def test_governing_definition_changes_score_hash(
    second_spec: EvaluationSpec,
) -> None:
    first = _score(("pass",) * 23, spec=_spec())
    second = _score(("pass",) * 23, spec=second_spec)
    assert first.score_value == second.score_value == 1
    assert first.metric_definition_sha256 != second.metric_definition_sha256
    assert first.score_sha256 != second.score_sha256


def test_score_tampering_and_unknown_fields_fail() -> None:
    record = _score(("pass",) * 23).to_record()
    record["score_value"] = 0
    with pytest.raises(ValueError, match=r"score_value|score_sha256"):
        ScoreArtifact.from_record(record)
    record = _score(("pass",) * 23).to_record()
    record["observations"] = []
    with pytest.raises(ValueError, match="unexpected fields"):
        ScoreArtifact.from_record(record)
