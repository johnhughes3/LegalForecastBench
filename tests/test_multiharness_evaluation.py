from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.multiharness.evaluation import (
    EVALUATION_RECEIPT_SCHEMA_VERSION,
    EVALUATION_SIGNATURE_DOMAIN,
    EVALUATION_SPEC_SCHEMA_VERSION,
    CostMeasurement,
    CriterionCommitment,
    EvaluationBindingError,
    EvaluationReceipt,
    EvaluationSpec,
    EvaluationTokenUsage,
    MonotonicTiming,
    TokenCount,
    build_evaluation_receipt,
    build_evaluation_spec,
    criteria_commitment_sha256,
    verify_evaluation_receipt,
    verify_raw_evaluation_result,
)


def _digest(character: str) -> str:
    return "sha256:" + character * 64


DELIVERABLE = _digest("1")
TREE = _digest("2")
TASK = _digest("3")
RUN = _digest("4")
CONFIG = _digest("5")
POLICY = _digest("6")
RAW_RESULT_BYTES = b'{"criteria":[],"score":1}'
RAW_RESULT = "sha256:" + hashlib.sha256(RAW_RESULT_BYTES).hexdigest()
ISSUER_POLICY = _digest("8")
PRICING = _digest("9")
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"k" * 32)


def _spec() -> EvaluationSpec:
    return build_evaluation_spec(
        evaluation_id="harvey-lab-employment-v1",
        deliverable_manifest_sha256=DELIVERABLE,
        deliverable_tree_sha256=TREE,
        task_sha256=TASK,
        run_sha256=RUN,
        config_sha256=CONFIG,
        evaluator_repository="https://github.com/harveyai/harvey-labs",
        evaluator_commit="7" * 40,
        evaluator_tree="8" * 40,
        evaluator_file_manifest_sha256=_digest("a"),
        evaluator_image_digest=_digest("b"),
        wrapper_sha256=_digest("c"),
        private_material_sha256=_digest("d"),
        rubric_sha256=_digest("e"),
        criteria_sha256=_digest("f"),
        aggregation_sha256=_digest("0"),
        judge_requested_identity="anthropic/claude-sonnet-4-6",
        judge_settings_sha256=_digest("a"),
        judge_prompt_sha256=_digest("b"),
        judge_output_schema_sha256=_digest("c"),
        runtime_policy_sha256=POLICY,
        egress_policy_sha256=_digest("d"),
        resource_policy_sha256=_digest("e"),
        token_accounting_policy_sha256=_digest("f"),
    )


def _usage() -> EvaluationTokenUsage:
    return EvaluationTokenUsage(
        source="provider_response",
        input_tokens=TokenCount(value=800, unknown_reason=None),
        output_tokens=TokenCount(value=200, unknown_reason=None),
        cache_read_tokens=TokenCount(value=None, unknown_reason="not_reported"),
        cache_write_tokens=TokenCount(value=None, unknown_reason="not_reported"),
        reasoning_tokens=TokenCount(value=None, unknown_reason="not_reported"),
        total_tokens=TokenCount(value=1000, unknown_reason=None),
    )


def _cost() -> CostMeasurement:
    return CostMeasurement(
        amount_microusd=125_000,
        currency="USD",
        basis="estimated_from_pricing_snapshot",
        pricing_snapshot_sha256=PRICING,
        unknown_reason=None,
    )


def _timing() -> MonotonicTiming:
    return MonotonicTiming(
        clock_id="linux-clock-monotonic-raw",
        started_at_utc="2026-07-30T10:00:00+00:00Z".replace("+00:00Z", "Z"),
        ended_at_utc="2026-07-30T10:00:00.000015Z",
        started_monotonic_ns=10_000,
        ended_monotonic_ns=25_000,
        wall_elapsed_ns=15_000,
        queue_elapsed_ns=1_000,
        summed_call_elapsed_ns=22_000,
    )


def _receipt(
    *,
    measurement_id: str = "measurement-001",
    attempt_id: str = "eval-attempt-001",
    nonce: str = "nonce-001",
    repeat_index: int = 1,
    raw_result_sha256: str = RAW_RESULT,
) -> EvaluationReceipt:
    return build_evaluation_receipt(
        spec=_spec(),
        signer=PRIVATE_KEY.sign,
        measurement_id=measurement_id,
        evaluation_attempt_id=attempt_id,
        attempt_nonce=nonce,
        repeat_index=repeat_index,
        judge_resolved_identity="anthropic/claude-sonnet-4-6@2026-07-15",
        raw_result_sha256=raw_result_sha256,
        raw_result_size_bytes=len(RAW_RESULT_BYTES),
        raw_result_media_type="application/json",
        status="succeeded",
        token_usage=_usage(),
        cost=_cost(),
        timing=_timing(),
        issuer_policy_sha256=ISSUER_POLICY,
        issuer_key_id="evaluation-key-2026-07",
    )


def _verify(
    receipt: EvaluationReceipt,
    **overrides: object,
) -> EvaluationReceipt:
    arguments: dict[str, object] = {
        "spec": _spec(),
        "expected_spec_sha256": _spec().spec_sha256,
        "expected_deliverable_manifest_sha256": DELIVERABLE,
        "expected_runtime_policy_sha256": POLICY,
        "expected_issuer_policy_sha256": ISSUER_POLICY,
        "expected_issuer_key_id": "evaluation-key-2026-07",
        "issuer_public_key": PRIVATE_KEY.public_key(),
        "expected_measurement_id": receipt.measurement_id,
        "expected_evaluation_attempt_id": receipt.evaluation_attempt_id,
        "expected_attempt_nonce": receipt.attempt_nonce,
        "expected_repeat_index": receipt.repeat_index,
    }
    arguments.update(overrides)
    return verify_evaluation_receipt(receipt, **arguments)  # type: ignore[arg-type]


def _authorized_rebuild(
    receipt: EvaluationReceipt,
    **changes: object,
) -> EvaluationReceipt:
    record = receipt.to_record()
    record.pop("signature")
    record.pop("receipt_sha256")
    record.update(changes)
    canonical = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    record["receipt_sha256"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    signed = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    record["signature"] = base64.b64encode(
        PRIVATE_KEY.sign(EVALUATION_SIGNATURE_DOMAIN + signed)
    ).decode()
    return EvaluationReceipt.from_record(record)


def test_spec_and_signed_receipt_round_trip_with_exact_contract_bindings() -> None:
    spec = _spec()
    receipt = _receipt()

    assert spec.schema_version == EVALUATION_SPEC_SCHEMA_VERSION
    assert EvaluationSpec.from_record(spec.to_record()) == spec
    assert receipt.schema_version == EVALUATION_RECEIPT_SCHEMA_VERSION
    assert EvaluationReceipt.from_record(receipt.to_record()) == receipt
    assert _verify(receipt) == receipt
    assert receipt.deliverable_manifest_sha256 == DELIVERABLE
    assert receipt.deliverable_tree_sha256 == TREE
    assert (receipt.task_sha256, receipt.run_sha256, receipt.config_sha256) == (
        TASK,
        RUN,
        CONFIG,
    )
    assert receipt.raw_result_size_bytes == len(RAW_RESULT_BYTES)
    assert receipt.raw_result_media_type == "application/json"


@pytest.mark.parametrize(
    ("argument", "replacement"),
    (
        ("expected_deliverable_manifest_sha256", _digest("a")),
        ("expected_spec_sha256", _digest("f")),
        ("expected_runtime_policy_sha256", _digest("b")),
        ("expected_issuer_policy_sha256", _digest("c")),
        ("expected_issuer_key_id", "other-key"),
        ("expected_measurement_id", "measurement-002"),
        ("expected_evaluation_attempt_id", "eval-attempt-002"),
        ("expected_repeat_index", 2),
    ),
)
def test_verification_requires_external_exact_bindings(
    argument: str,
    replacement: object,
) -> None:
    with pytest.raises(EvaluationBindingError, match="does not match"):
        _verify(_receipt(), **{argument: replacement})


def test_embedded_key_identity_is_not_trusted_without_correct_external_key() -> None:
    attacker_key = Ed25519PrivateKey.from_private_bytes(b"x" * 32)
    with pytest.raises(EvaluationBindingError, match="signature"):
        _verify(_receipt(), issuer_public_key=attacker_key.public_key())


@pytest.mark.parametrize(
    ("field", "divergent"),
    (
        ("deliverable_manifest_sha256", _digest("a")),
        ("runtime_policy_sha256", _digest("b")),
    ),
)
def test_authorized_receipt_cannot_diverge_from_bound_spec(
    field: str,
    divergent: str,
) -> None:
    receipt = _authorized_rebuild(_receipt(), **{field: divergent})
    external_argument = (
        "expected_deliverable_manifest_sha256"
        if field == "deliverable_manifest_sha256"
        else "expected_runtime_policy_sha256"
    )
    with pytest.raises(EvaluationBindingError, match="evaluation spec"):
        _verify(receipt, **{external_argument: divergent})


def test_raw_result_verification_binds_exact_opaque_bytes_size_and_media() -> None:
    receipt = _receipt(
        raw_result_sha256="sha256:" + hashlib.sha256(RAW_RESULT_BYTES).hexdigest()
    )
    verify_raw_evaluation_result(
        receipt,
        RAW_RESULT_BYTES,
        expected_media_type="application/json",
    )
    with pytest.raises(EvaluationBindingError, match="size"):
        verify_raw_evaluation_result(
            receipt,
            RAW_RESULT_BYTES + b" ",
            expected_media_type="application/json",
        )
    with pytest.raises(EvaluationBindingError, match="media_type"):
        verify_raw_evaluation_result(
            receipt,
            RAW_RESULT_BYTES,
            expected_media_type="text/plain",
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("deliverable_manifest_sha256", _digest("a")),
        ("deliverable_tree_sha256", _digest("b")),
        ("task_sha256", _digest("c")),
        ("judge_prompt_sha256", _digest("d")),
        ("runtime_policy_sha256", _digest("e")),
        ("raw_result_sha256", _digest("f")),
        ("raw_result_size_bytes", 418),
        ("raw_result_media_type", "text/plain"),
        ("issuer_key_id", "other-key"),
    ),
)
def test_serialized_receipt_tampering_fails_deterministically(
    field: str,
    replacement: object,
) -> None:
    record = _receipt().to_record()
    record[field] = replacement
    with pytest.raises(ValueError, match="receipt_sha256"):
        EvaluationReceipt.from_record(record)


def test_nested_usage_cost_and_timing_tampering_fails() -> None:
    records = [_receipt().to_record() for _ in range(3)]
    records[0]["token_usage"] = _usage().to_record() | {
        "total_tokens": {"value": 999, "unknown_reason": None}
    }
    records[1]["cost"] = _cost().to_record() | {"amount_microusd": 1}
    records[2]["timing"] = _timing().to_record() | {"ended_monotonic_ns": 25_001}
    for index, record in enumerate(records):
        match = "receipt_sha256" if index < 2 else "wall_elapsed_ns"
        with pytest.raises(ValueError, match=match):
            EvaluationReceipt.from_record(record)


def test_fresh_stochastic_call_has_new_nonce_measurement_and_repeat() -> None:
    first = _receipt()
    second = _receipt(
        measurement_id="measurement-002",
        attempt_id="eval-attempt-002",
        nonce="nonce-002",
        repeat_index=2,
        raw_result_sha256=_digest("a"),
    )
    assert second.receipt_sha256 != first.receipt_sha256
    with pytest.raises(EvaluationBindingError, match="measurement_id"):
        _verify(second, expected_measurement_id=first.measurement_id)


def test_signature_tampering_fails_under_externally_pinned_key() -> None:
    record = _receipt().to_record()
    signature = str(record["signature"])
    record["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = EvaluationReceipt.from_record(record)
    with pytest.raises(EvaluationBindingError, match="signature"):
        _verify(tampered)


def test_explicit_replay_seam_rejects_consumed_measurement_or_repeat_slot() -> None:
    receipt = _receipt()
    with pytest.raises(EvaluationBindingError, match="consumed"):
        _verify(receipt, seen_measurement_ids={receipt.measurement_id})
    with pytest.raises(EvaluationBindingError, match="repeat slot"):
        _verify(
            receipt,
            occupied_repeat_slots={
                (receipt.evaluation_spec_sha256, receipt.repeat_index)
            },
        )
    # Archived verification intentionally remains valid without live replay state.
    assert _verify(receipt) == receipt


def test_unknown_token_counts_are_null_with_reason_and_bool_is_not_int() -> None:
    assert TokenCount(None, "provider_did_not_report").to_record()["value"] is None
    with pytest.raises(ValueError, match="unknown_reason"):
        TokenCount(None, None)
    with pytest.raises(ValueError, match="unknown_reason"):
        TokenCount(0, "not_reported")
    with pytest.raises(ValueError, match="integer"):
        TokenCount(True, None)  # type: ignore[arg-type]


def test_subscription_unallocable_cost_is_null_and_never_zero() -> None:
    unallocable = CostMeasurement(
        amount_microusd=None,
        currency=None,
        basis="subscription_unallocable",
        pricing_snapshot_sha256=None,
        unknown_reason="flat_subscription_has_no_per_call_allocation",
    )
    assert unallocable.to_record()["amount_microusd"] is None
    with pytest.raises(ValueError, match="must be null"):
        replace(unallocable, amount_microusd=0)
    with pytest.raises(ValueError, match="unknown_reason"):
        replace(unallocable, unknown_reason=None)


def test_zero_cost_is_allowed_only_as_authenticated_known_measurement() -> None:
    zero = CostMeasurement(
        amount_microusd=0,
        currency="USD",
        basis="provider_reported",
        pricing_snapshot_sha256=None,
        unknown_reason=None,
    )
    receipt = build_evaluation_receipt(
        **{
            key: value
            for key, value in {
                "spec": _spec(),
                "signer": PRIVATE_KEY.sign,
                "measurement_id": "measurement-zero",
                "evaluation_attempt_id": "attempt-zero",
                "attempt_nonce": "nonce-zero",
                "repeat_index": 1,
                "judge_resolved_identity": "provider/model@resolved",
                "raw_result_sha256": RAW_RESULT,
                "raw_result_size_bytes": 1,
                "raw_result_media_type": "application/json",
                "status": "succeeded",
                "token_usage": _usage(),
                "cost": zero,
                "timing": _timing(),
                "issuer_policy_sha256": ISSUER_POLICY,
                "issuer_key_id": "evaluation-key-2026-07",
            }.items()
        }
    )
    assert _verify(receipt, expected_measurement_id="measurement-zero") == receipt


def test_monotonic_and_utc_timing_are_exact_and_distinguish_call_sum() -> None:
    assert _timing().summed_call_elapsed_ns > _timing().wall_elapsed_ns
    with pytest.raises(ValueError, match="wall_elapsed_ns"):
        replace(_timing(), wall_elapsed_ns=15_001)
    with pytest.raises(ValueError, match="precede"):
        replace(_timing(), ended_monotonic_ns=9_999, wall_elapsed_ns=0)
    with pytest.raises(ValueError, match="UTC"):
        replace(_timing(), started_at_utc="2026-07-30T10:00:00+01:00")


def test_criterion_commitments_require_id_order_and_expose_no_private_text() -> None:
    ordered = (
        CriterionCommitment(1, _digest("a")),
        CriterionCommitment(2, _digest("b")),
    )
    digest = criteria_commitment_sha256(ordered)
    assert digest.startswith("sha256:")
    assert set(ordered[0].to_record()) == {"ordinal", "commitment_sha256"}
    with pytest.raises(ValueError, match="ordinals"):
        criteria_commitment_sha256(tuple(reversed(ordered)))
    with pytest.raises(ValueError, match="ordinals"):
        criteria_commitment_sha256((ordered[0], ordered[0]))


def test_nonce_is_externally_bound_and_replay_checked() -> None:
    receipt = _receipt()
    with pytest.raises(EvaluationBindingError, match="attempt_nonce"):
        _verify(receipt, expected_attempt_nonce="nonce-elsewhere")
    with pytest.raises(EvaluationBindingError, match="attempt_nonce"):
        _verify(receipt, seen_attempt_nonces={receipt.attempt_nonce})


def test_public_codes_reject_prose_paths_and_secret_like_reason_text() -> None:
    with pytest.raises(ValueError, match="supported token source"):
        replace(_usage(), source="../../private")
    with pytest.raises(ValueError, match="public-safe"):
        TokenCount(None, "provider error: secret=abc")


def test_unknown_fields_and_noncanonical_digests_fail_closed() -> None:
    spec_record = _spec().to_record()
    spec_record["surprise"] = True
    with pytest.raises(ValueError, match="unexpected fields"):
        EvaluationSpec.from_record(spec_record)
    bad = _spec().to_record()
    bad["task_sha256"] = "sha256:" + "A" * 64
    with pytest.raises(ValueError, match="lowercase"):
        EvaluationSpec.from_record(bad)
