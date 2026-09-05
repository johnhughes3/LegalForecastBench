"""Authorized Harvey LAB receipt verification and deterministic scoring.

Wraps the 4.1.8/4.1.9 evaluation and score contracts with a pinned issuer
policy. Missing or extra receipt fields are refused by name. Normalization is
a pure function of the authorized raw verdict bytes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast.contracts.schemas import HARVEY_LAB_EVALUATOR_ISSUER_POLICY_V2
from legalforecast.multiharness.evaluation import (
    EVALUATION_RECEIPT_SCHEMA_VERSION,
    EvaluationBindingError,
    EvaluationReceipt,
    EvaluationSpec,
    verify_evaluation_result,
)
from legalforecast.multiharness.scoring import (
    HARVEY_LAB_NORMALIZER_ID,
    MetricDefinition,
    ScoreArtifact,
    ScoreNormalizationError,
    normalize_harvey_lab_score,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
)

HARVEY_LAB_EVALUATOR_ISSUER_POLICY_ID = (
    # contract-ratchet: allow LAB issuer policy until contracts registry
    "legalforecast.harvey-lab-evaluator-issuer.v2"
)
HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID = "harvey-lab-evaluator-v1"
HARVEY_LAB_EVALUATOR_ISSUER_POLICY_SCHEMA_VERSION = str(
    HARVEY_LAB_EVALUATOR_ISSUER_POLICY_V2
)

_RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "measurement_id",
        "evaluation_attempt_id",
        "attempt_nonce",
        "repeat_index",
        "evaluation_spec_sha256",
        "deliverable_manifest_sha256",
        "deliverable_tree_sha256",
        "task_sha256",
        "run_sha256",
        "config_sha256",
        "judge_requested_identity",
        "judge_resolved_identity",
        "judge_settings_sha256",
        "judge_prompt_sha256",
        "judge_output_schema_sha256",
        "runtime_policy_sha256",
        "egress_policy_sha256",
        "resource_policy_sha256",
        "token_accounting_policy_sha256",
        "raw_result_sha256",
        "raw_result_size_bytes",
        "raw_result_media_type",
        "status",
        "token_usage",
        "cost",
        "timing",
        "issuer_policy_sha256",
        "issuer_key_id",
        "receipt_sha256",
        "signature",
    }
)


class HarveyLabReceiptError(ValueError):
    """An evaluator receipt was not authorized or could not be normalized."""


def harvey_lab_authorized_issuer_policy() -> dict[str, object]:
    """Return the pinned LAB evaluator issuer policy (no key material)."""

    return {
        "schema_version": HARVEY_LAB_EVALUATOR_ISSUER_POLICY_SCHEMA_VERSION,
        "issuer_id": HARVEY_LAB_EVALUATOR_ISSUER_POLICY_ID,
        "algorithm": "Ed25519",
        "key_id": HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
        "normalizer_id": HARVEY_LAB_NORMALIZER_ID,
        "metric_id": "harvey-lab-binary-all-pass-v1",
        "criterion_count_rule": "authenticated_private_task",
    }


# contract-ratchet: allow non-persisted LAB issuer policy hash
def harvey_lab_issuer_policy_sha256() -> str:
    """Return the canonical hash of the pinned LAB issuer policy."""

    payload = json.dumps(
        harvey_lab_authorized_issuer_policy(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_score_artifact_bytes(score: ScoreArtifact) -> bytes:
    """Return the exact canonical UTF-8 JSON bytes of one score artifact."""

    return (
        json.dumps(
            score.to_record(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def verify_authorized_harvey_lab_receipt(
    record: Mapping[str, Any],
    *,
    raw_result: bytes,
    spec: EvaluationSpec,
    metric: MetricDefinition,
    issuer_public_key: Ed25519PublicKey,
    expected_measurement_id: str,
    expected_evaluation_attempt_id: str,
    expected_attempt_nonce: str,
    expected_repeat_index: int,
    expected_deliverable_manifest_sha256: str | None = None,
    expected_runtime_policy_sha256: str | None = None,
    seen_measurement_ids: set[str] | None = None,
    seen_attempt_nonces: set[str] | None = None,
    occupied_repeat_slots: set[tuple[str, int]] | None = None,
) -> ScoreArtifact:
    """Verify one authorized LAB receipt and normalize it offline.

    Dropped or extra top-level receipt fields are refused by name. A tampered
    binding is refused by naming that field. CI needs no provider credentials.
    """

    try:
        require_known_fields(
            record,
            required=_RECEIPT_REQUIRED_FIELDS,
            field_name="evaluation receipt",
        )
    except MultiHarnessValidationError as exc:
        raise HarveyLabReceiptError(str(exc)) from exc
    schema_version = record.get("schema_version")
    if schema_version != EVALUATION_RECEIPT_SCHEMA_VERSION:
        raise HarveyLabReceiptError(
            "schema_version does not match the authorized evaluation receipt"
        )
    issuer_policy = record.get("issuer_policy_sha256")
    if issuer_policy != harvey_lab_issuer_policy_sha256():
        raise HarveyLabReceiptError(
            "issuer_policy_sha256 does not match the authorized LAB issuer policy"
        )
    issuer_key_id = record.get("issuer_key_id")
    if issuer_key_id != HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID:
        raise HarveyLabReceiptError(
            "issuer_key_id does not match the authorized LAB issuer"
        )
    try:
        receipt = EvaluationReceipt.from_record(record)
    except (AttributeError, TypeError, ValueError) as exc:
        message = str(exc)
        if "receipt_sha256" in message:
            raise HarveyLabReceiptError(
                "receipt_sha256 does not match evaluation receipt content"
            ) from exc
        raise HarveyLabReceiptError(message) from exc
    expected_deliverable = (
        expected_deliverable_manifest_sha256 or spec.deliverable_manifest_sha256
    )
    expected_runtime = expected_runtime_policy_sha256 or spec.runtime_policy_sha256
    try:
        verified = verify_evaluation_result(
            receipt,
            raw_result,
            expected_media_type="application/json",
            spec=spec,
            expected_spec_sha256=spec.spec_sha256,
            expected_deliverable_manifest_sha256=expected_deliverable,
            expected_runtime_policy_sha256=expected_runtime,
            expected_issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
            expected_issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
            issuer_public_key=issuer_public_key,
            expected_measurement_id=expected_measurement_id,
            expected_evaluation_attempt_id=expected_evaluation_attempt_id,
            expected_attempt_nonce=expected_attempt_nonce,
            expected_repeat_index=expected_repeat_index,
            seen_measurement_ids=seen_measurement_ids,
            seen_attempt_nonces=seen_attempt_nonces,
            occupied_repeat_slots=occupied_repeat_slots,
        )
        return normalize_harvey_lab_score(
            receipt=verified,
            raw_result=raw_result,
            spec=spec,
            metric=metric,
            expected_metric_definition_sha256=metric.definition_sha256,
            expected_media_type="application/json",
            expected_spec_sha256=spec.spec_sha256,
            expected_deliverable_manifest_sha256=expected_deliverable,
            expected_runtime_policy_sha256=expected_runtime,
            expected_issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
            expected_issuer_key_id=HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
            issuer_public_key=issuer_public_key,
            expected_measurement_id=expected_measurement_id,
            expected_evaluation_attempt_id=expected_evaluation_attempt_id,
            expected_attempt_nonce=expected_attempt_nonce,
            expected_repeat_index=expected_repeat_index,
            seen_measurement_ids=seen_measurement_ids,
            seen_attempt_nonces=seen_attempt_nonces,
            occupied_repeat_slots=occupied_repeat_slots,
        )
    except EvaluationBindingError as exc:
        raise HarveyLabReceiptError(str(exc)) from exc
    except ScoreNormalizationError as exc:
        raise HarveyLabReceiptError(str(exc)) from exc
