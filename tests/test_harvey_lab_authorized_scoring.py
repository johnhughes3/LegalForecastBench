from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    HarveyLabReceiptError,
    canonical_score_artifact_bytes,
    harvey_lab_issuer_policy_sha256,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.scoring import (
    LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
    MetricDefinition,
    build_harvey_lab_metric_definition,
)

GOLDEN_ALL_PASS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "harvey_lab"
    / "authorized-score-all-pass.golden.json"
)
GOLDEN_ONE_FAIL = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "harvey_lab"
    / "authorized-score-one-fail.golden.json"
)

KEY = Ed25519PrivateKey.from_private_bytes(b"L" * 32)


def _digest(character: str) -> str:
    return "sha256:" + character * 64


def _spec() -> EvaluationSpec:
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
        rubric_sha256=_digest("d"),
        criteria_sha256=_digest("e"),
        aggregation_sha256=_digest("f"),
        judge_requested_identity="anthropic/claude-sonnet-4-6",
        judge_settings_sha256=_digest("a"),
        judge_prompt_sha256=_digest("b"),
        judge_output_schema_sha256=_digest("c"),
        runtime_policy_sha256=_digest("6"),
        egress_policy_sha256=_digest("d"),
        resource_policy_sha256=_digest("e"),
        token_accounting_policy_sha256=_digest("f"),
    )


def _raw(verdicts: tuple[str, ...]) -> bytes:
    n_passed = verdicts.count("pass")
    record = {
        "schema_version": LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
        "verdicts": [
            {"ordinal": index, "verdict": verdict}
            for index, verdict in enumerate(verdicts, start=1)
        ],
        "score": 1 if n_passed == len(verdicts) else 0,
        "n_passed": n_passed,
        "n_criteria": len(verdicts),
    }
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _receipt(spec: EvaluationSpec, raw: bytes) -> EvaluationReceipt:
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
        status="succeeded",
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
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    )


def _metric(spec: EvaluationSpec) -> MetricDefinition:
    return build_harvey_lab_metric_definition(
        rubric_sha256=spec.rubric_sha256,
        criteria_sha256=spec.criteria_sha256,
        aggregation_sha256=spec.aggregation_sha256,
        output_schema_sha256=spec.judge_output_schema_sha256,
    )


def _score(verdicts: tuple[str, ...]):
    spec = _spec()
    raw = _raw(verdicts)
    receipt = _receipt(spec, raw)
    return verify_authorized_harvey_lab_receipt(
        receipt.to_record(),
        raw_result=raw,
        spec=spec,
        metric=_metric(spec),
        issuer_public_key=KEY.public_key(),
        expected_measurement_id=receipt.measurement_id,
        expected_evaluation_attempt_id=receipt.evaluation_attempt_id,
        expected_attempt_nonce=receipt.attempt_nonce,
        expected_repeat_index=receipt.repeat_index,
    )


def test_authorized_all_pass_is_exactly_one() -> None:
    score = _score(("pass",) * 23)
    assert score.score_value == 1
    assert score.n_passed == score.n_criteria == 23


def test_authorized_any_failure_is_zero() -> None:
    score = _score(("pass",) * 22 + ("fail",))
    assert score.score_value == 0
    assert score.n_passed == 22


def test_golden_all_pass_bytes_are_stable() -> None:
    score = _score(("pass",) * 23)
    actual = canonical_score_artifact_bytes(score)
    expected = GOLDEN_ALL_PASS.read_bytes()
    assert actual == expected
    assert actual.endswith(b"\n")
    again = canonical_score_artifact_bytes(_score(("pass",) * 23))
    assert again == actual


def test_golden_one_fail_bytes_are_stable() -> None:
    score = _score(("pass",) * 22 + ("fail",))
    actual = canonical_score_artifact_bytes(score)
    expected = GOLDEN_ONE_FAIL.read_bytes()
    assert actual == expected
    assert actual.endswith(b"\n")


def test_dropped_deliverable_binding_is_named() -> None:
    spec = _spec()
    raw = _raw(("pass",) * 23)
    record = _receipt(spec, raw).to_record()
    del record["deliverable_manifest_sha256"]
    with pytest.raises(HarveyLabReceiptError, match="deliverable_manifest_sha256"):
        verify_authorized_harvey_lab_receipt(
            record,
            raw_result=raw,
            spec=spec,
            metric=_metric(spec),
            issuer_public_key=KEY.public_key(),
            expected_measurement_id="measurement-001",
            expected_evaluation_attempt_id="attempt-001",
            expected_attempt_nonce="nonce-001",
            expected_repeat_index=1,
        )


def test_dropped_receipt_field_is_named() -> None:
    spec = _spec()
    raw = _raw(("pass",) * 23)
    record = _receipt(spec, raw).to_record()
    del record["issuer_key_id"]
    with pytest.raises(HarveyLabReceiptError, match="issuer_key_id") as caught:
        verify_authorized_harvey_lab_receipt(
            record,
            raw_result=raw,
            spec=spec,
            metric=_metric(spec),
            issuer_public_key=KEY.public_key(),
            expected_measurement_id="measurement-001",
            expected_evaluation_attempt_id="attempt-001",
            expected_attempt_nonce="nonce-001",
            expected_repeat_index=1,
        )
    assert "issuer_key_id" in str(caught.value)


def test_tampered_issuer_key_id_is_named() -> None:
    spec = _spec()
    raw = _raw(("pass",) * 23)
    record = _receipt(spec, raw).to_record()
    record["issuer_key_id"] = "other-key"
    with pytest.raises(HarveyLabReceiptError, match="issuer_key_id"):
        verify_authorized_harvey_lab_receipt(
            record,
            raw_result=raw,
            spec=spec,
            metric=_metric(spec),
            issuer_public_key=KEY.public_key(),
            expected_measurement_id="measurement-001",
            expected_evaluation_attempt_id="attempt-001",
            expected_attempt_nonce="nonce-001",
            expected_repeat_index=1,
        )


def test_wrong_issuer_policy_is_named() -> None:
    spec = _spec()
    raw = _raw(("pass",) * 23)
    record = _receipt(spec, raw).to_record()
    record["issuer_policy_sha256"] = _digest("0")
    with pytest.raises(HarveyLabReceiptError, match="issuer_policy_sha256"):
        verify_authorized_harvey_lab_receipt(
            record,
            raw_result=raw,
            spec=spec,
            metric=_metric(spec),
            issuer_public_key=KEY.public_key(),
            expected_measurement_id="measurement-001",
            expected_evaluation_attempt_id="attempt-001",
            expected_attempt_nonce="nonce-001",
            expected_repeat_index=1,
        )


def test_forged_signature_is_refused() -> None:
    spec = _spec()
    raw = _raw(("pass",) * 23)
    record = _receipt(spec, raw).to_record()
    attacker = Ed25519PrivateKey.from_private_bytes(b"A" * 32)
    with pytest.raises(HarveyLabReceiptError, match="signature"):
        verify_authorized_harvey_lab_receipt(
            record,
            raw_result=raw,
            spec=spec,
            metric=_metric(spec),
            issuer_public_key=attacker.public_key(),
            expected_measurement_id="measurement-001",
            expected_evaluation_attempt_id="attempt-001",
            expected_attempt_nonce="nonce-001",
            expected_repeat_index=1,
        )


def test_score_artifact_hides_private_verdicts() -> None:
    rendered = canonical_score_artifact_bytes(_score(("pass",) * 23)).decode()
    for forbidden in ("verdict", "ordinal", "reasoning", "rubric_text"):
        assert forbidden not in rendered
