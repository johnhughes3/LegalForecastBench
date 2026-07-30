"""Canonical, signed contracts for isolated evaluator observations."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

EVALUATION_SPEC_SCHEMA_VERSION = "legalforecast.multiharness.evaluation_spec.v1"
EVALUATION_RECEIPT_SCHEMA_VERSION = "legalforecast.multiharness.evaluation_receipt.v1"
EVALUATION_SIGNATURE_DOMAIN = b"LegalForecastBench EvaluationReceipt v1\x00"

_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_MEDIA_TYPE_RE = re.compile(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+\Z")
_STATUSES = frozenset({"succeeded", "failed"})
_KNOWN_COST_BASES = frozenset(
    {"metered", "provider_reported", "estimated_from_pricing_snapshot"}
)
_NULL_COST_BASES = frozenset({"subscription_unallocable", "unknown"})
_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "evaluation_id",
        "deliverable_manifest_sha256",
        "deliverable_tree_sha256",
        "task_sha256",
        "run_sha256",
        "config_sha256",
        "evaluator_repository",
        "evaluator_commit",
        "evaluator_tree",
        "evaluator_file_manifest_sha256",
        "evaluator_image_digest",
        "wrapper_sha256",
        "private_material_sha256",
        "rubric_sha256",
        "criteria_sha256",
        "aggregation_sha256",
        "judge_requested_identity",
        "judge_settings_sha256",
        "judge_prompt_sha256",
        "judge_output_schema_sha256",
        "runtime_policy_sha256",
        "egress_policy_sha256",
        "resource_policy_sha256",
        "spec_sha256",
    }
)
_CRITERION_FIELDS = frozenset({"criterion_id", "commitment_sha256"})
_TOKEN_COUNT_FIELDS = frozenset({"value", "unknown_reason"})
_TOKEN_USAGE_FIELDS = frozenset(
    {
        "source",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "reasoning_tokens",
        "total_tokens",
    }
)
_COST_FIELDS = frozenset(
    {
        "amount_microusd",
        "currency",
        "basis",
        "pricing_snapshot_sha256",
        "unknown_reason",
    }
)
_TIMING_FIELDS = frozenset(
    {
        "clock_id",
        "started_at_utc",
        "ended_at_utc",
        "started_monotonic_ns",
        "ended_monotonic_ns",
        "wall_elapsed_ns",
        "queue_elapsed_ns",
        "summed_call_elapsed_ns",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "measurement_id",
        "evaluation_attempt_id",
        "attempt_nonce",
        "repeat_index",
        "attempt_number",
        "retry_count",
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


class EvaluationBindingError(ValueError):
    """An evaluation record failed integrity, trust, or replay checks."""


@dataclass(frozen=True, slots=True)
class CriterionCommitment:
    """Private-safe commitment to one criterion, identified without its text."""

    criterion_id: str
    commitment_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.criterion_id, "criterion_id")
        _require_digest(self.commitment_sha256, "commitment_sha256")

    def to_record(self) -> dict[str, str]:
        return {
            "criterion_id": self.criterion_id,
            "commitment_sha256": self.commitment_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _CRITERION_FIELDS, "criterion commitment")
        return cls(
            criterion_id=_required_string(record, "criterion_id"),
            commitment_sha256=_required_string(record, "commitment_sha256"),
        )


@dataclass(frozen=True, slots=True)
class TokenCount:
    """One authoritative token dimension, or explicit missingness."""

    value: int | None
    unknown_reason: str | None

    def __post_init__(self) -> None:
        if self.value is None:
            _require_non_empty(self.unknown_reason, "unknown_reason")
        else:
            _require_non_negative_int_value(self.value, "value")
            if self.unknown_reason is not None:
                raise ValueError("unknown_reason must be null when value is known")

    def to_record(self) -> dict[str, object]:
        return {"value": self.value, "unknown_reason": self.unknown_reason}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TOKEN_COUNT_FIELDS, "token count")
        return cls(
            value=_optional_non_negative_int(record, "value"),
            unknown_reason=_optional_string(record, "unknown_reason"),
        )


@dataclass(frozen=True, slots=True)
class EvaluationTokenUsage:
    """Per-evaluation token accounting without inferred zeroes."""

    source: str
    input_tokens: TokenCount
    output_tokens: TokenCount
    cached_input_tokens: TokenCount
    reasoning_tokens: TokenCount
    total_tokens: TokenCount

    def __post_init__(self) -> None:
        _require_non_empty(self.source, "source")

    def to_record(self) -> dict[str, object]:
        return {
            "source": self.source,
            "input_tokens": self.input_tokens.to_record(),
            "output_tokens": self.output_tokens.to_record(),
            "cached_input_tokens": self.cached_input_tokens.to_record(),
            "reasoning_tokens": self.reasoning_tokens.to_record(),
            "total_tokens": self.total_tokens.to_record(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TOKEN_USAGE_FIELDS, "token usage")
        return cls(
            source=_required_string(record, "source"),
            input_tokens=TokenCount.from_record(
                _required_mapping(record.get("input_tokens"), "input_tokens")
            ),
            output_tokens=TokenCount.from_record(
                _required_mapping(record.get("output_tokens"), "output_tokens")
            ),
            cached_input_tokens=TokenCount.from_record(
                _required_mapping(
                    record.get("cached_input_tokens"), "cached_input_tokens"
                )
            ),
            reasoning_tokens=TokenCount.from_record(
                _required_mapping(record.get("reasoning_tokens"), "reasoning_tokens")
            ),
            total_tokens=TokenCount.from_record(
                _required_mapping(record.get("total_tokens"), "total_tokens")
            ),
        )


@dataclass(frozen=True, slots=True)
class CostMeasurement:
    """Per-evaluation cost and its authoritative accounting basis."""

    amount_microusd: int | None
    currency: str | None
    basis: str
    pricing_snapshot_sha256: str | None
    unknown_reason: str | None

    def __post_init__(self) -> None:
        if self.basis in _KNOWN_COST_BASES:
            _require_non_negative_int_value(self.amount_microusd, "amount_microusd")
            if self.currency != "USD":
                raise ValueError("currency must be 'USD' when cost is known")
            if self.unknown_reason is not None:
                raise ValueError(
                    "unknown_reason must be null when amount_microusd is known"
                )
            if self.basis == "estimated_from_pricing_snapshot":
                _require_digest(
                    self.pricing_snapshot_sha256,
                    "pricing_snapshot_sha256",
                )
            elif self.pricing_snapshot_sha256 is not None:
                _require_digest(
                    self.pricing_snapshot_sha256,
                    "pricing_snapshot_sha256",
                )
            return
        if self.basis not in _NULL_COST_BASES:
            raise ValueError("basis is not a supported cost basis")
        if self.amount_microusd is not None:
            raise ValueError(f"amount_microusd must be null for {self.basis} cost")
        if self.currency is not None:
            raise ValueError(f"currency must be null for {self.basis} cost")
        if self.pricing_snapshot_sha256 is not None:
            raise ValueError(
                f"pricing_snapshot_sha256 must be null for {self.basis} cost"
            )
        _require_non_empty(self.unknown_reason, "unknown_reason")

    def to_record(self) -> dict[str, object]:
        return {
            "amount_microusd": self.amount_microusd,
            "currency": self.currency,
            "basis": self.basis,
            "pricing_snapshot_sha256": self.pricing_snapshot_sha256,
            "unknown_reason": self.unknown_reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _COST_FIELDS, "cost")
        return cls(
            amount_microusd=_optional_non_negative_int(record, "amount_microusd"),
            currency=_optional_string(record, "currency"),
            basis=_required_string(record, "basis"),
            pricing_snapshot_sha256=_optional_string(record, "pricing_snapshot_sha256"),
            unknown_reason=_optional_string(record, "unknown_reason"),
        )


@dataclass(frozen=True, slots=True)
class MonotonicTiming:
    """UTC chronology plus monotonic evaluation accounting."""

    clock_id: str
    started_at_utc: str
    ended_at_utc: str
    started_monotonic_ns: int
    ended_monotonic_ns: int
    wall_elapsed_ns: int
    queue_elapsed_ns: int
    summed_call_elapsed_ns: int

    def __post_init__(self) -> None:
        _require_non_empty(self.clock_id, "clock_id")
        started = _parse_utc(self.started_at_utc, "started_at_utc")
        ended = _parse_utc(self.ended_at_utc, "ended_at_utc")
        if ended < started:
            raise ValueError("ended_at_utc must not precede started_at_utc")
        for name in (
            "started_monotonic_ns",
            "ended_monotonic_ns",
            "wall_elapsed_ns",
            "queue_elapsed_ns",
            "summed_call_elapsed_ns",
        ):
            _require_non_negative_int_value(getattr(self, name), name)
        if self.ended_monotonic_ns < self.started_monotonic_ns:
            raise ValueError("ended_monotonic_ns must not precede started_monotonic_ns")
        if self.wall_elapsed_ns != (
            self.ended_monotonic_ns - self.started_monotonic_ns
        ):
            raise ValueError(
                "wall_elapsed_ns must equal the monotonic endpoint difference"
            )
        if self.queue_elapsed_ns > self.wall_elapsed_ns:
            raise ValueError("queue_elapsed_ns cannot exceed wall_elapsed_ns")

    def to_record(self) -> dict[str, object]:
        return {
            "clock_id": self.clock_id,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "started_monotonic_ns": self.started_monotonic_ns,
            "ended_monotonic_ns": self.ended_monotonic_ns,
            "wall_elapsed_ns": self.wall_elapsed_ns,
            "queue_elapsed_ns": self.queue_elapsed_ns,
            "summed_call_elapsed_ns": self.summed_call_elapsed_ns,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TIMING_FIELDS, "timing")
        return cls(
            clock_id=_required_string(record, "clock_id"),
            started_at_utc=_required_string(record, "started_at_utc"),
            ended_at_utc=_required_string(record, "ended_at_utc"),
            started_monotonic_ns=_required_non_negative_int(
                record, "started_monotonic_ns"
            ),
            ended_monotonic_ns=_required_non_negative_int(record, "ended_monotonic_ns"),
            wall_elapsed_ns=_required_non_negative_int(record, "wall_elapsed_ns"),
            queue_elapsed_ns=_required_non_negative_int(record, "queue_elapsed_ns"),
            summed_call_elapsed_ns=_required_non_negative_int(
                record, "summed_call_elapsed_ns"
            ),
        )


@dataclass(frozen=True, slots=True)
class EvaluationSpec:
    """Precommitted evaluator inputs, implementation, judge, and policy."""

    evaluation_id: str
    deliverable_manifest_sha256: str
    deliverable_tree_sha256: str
    task_sha256: str
    run_sha256: str
    config_sha256: str
    evaluator_repository: str
    evaluator_commit: str
    evaluator_tree: str
    evaluator_file_manifest_sha256: str
    evaluator_image_digest: str
    wrapper_sha256: str
    private_material_sha256: str
    rubric_sha256: str
    criteria_sha256: str
    aggregation_sha256: str
    judge_requested_identity: str
    judge_settings_sha256: str
    judge_prompt_sha256: str
    judge_output_schema_sha256: str
    runtime_policy_sha256: str
    egress_policy_sha256: str
    resource_policy_sha256: str
    spec_sha256: str
    schema_version: str = EVALUATION_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_SPEC_SCHEMA_VERSION:
            raise ValueError("unsupported evaluation spec schema_version")
        for name in (
            "evaluation_id",
            "evaluator_repository",
            "judge_requested_identity",
        ):
            _require_non_empty(cast(str, getattr(self, name)), name)
        for name in (
            "deliverable_manifest_sha256",
            "deliverable_tree_sha256",
            "task_sha256",
            "run_sha256",
            "config_sha256",
            "evaluator_file_manifest_sha256",
            "evaluator_image_digest",
            "wrapper_sha256",
            "private_material_sha256",
            "rubric_sha256",
            "criteria_sha256",
            "aggregation_sha256",
            "judge_settings_sha256",
            "judge_prompt_sha256",
            "judge_output_schema_sha256",
            "runtime_policy_sha256",
            "egress_policy_sha256",
            "resource_policy_sha256",
            "spec_sha256",
        ):
            _require_digest(cast(str, getattr(self, name)), name)
        _require_git_sha(self.evaluator_commit, "evaluator_commit")
        _require_git_sha(self.evaluator_tree, "evaluator_tree")
        if self.spec_sha256 != _record_sha256(self._content_record()):
            raise ValueError("spec_sha256 does not match evaluation spec content")

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "deliverable_manifest_sha256": self.deliverable_manifest_sha256,
            "deliverable_tree_sha256": self.deliverable_tree_sha256,
            "task_sha256": self.task_sha256,
            "run_sha256": self.run_sha256,
            "config_sha256": self.config_sha256,
            "evaluator_repository": self.evaluator_repository,
            "evaluator_commit": self.evaluator_commit,
            "evaluator_tree": self.evaluator_tree,
            "evaluator_file_manifest_sha256": (self.evaluator_file_manifest_sha256),
            "evaluator_image_digest": self.evaluator_image_digest,
            "wrapper_sha256": self.wrapper_sha256,
            "private_material_sha256": self.private_material_sha256,
            "rubric_sha256": self.rubric_sha256,
            "criteria_sha256": self.criteria_sha256,
            "aggregation_sha256": self.aggregation_sha256,
            "judge_requested_identity": self.judge_requested_identity,
            "judge_settings_sha256": self.judge_settings_sha256,
            "judge_prompt_sha256": self.judge_prompt_sha256,
            "judge_output_schema_sha256": self.judge_output_schema_sha256,
            "runtime_policy_sha256": self.runtime_policy_sha256,
            "egress_policy_sha256": self.egress_policy_sha256,
            "resource_policy_sha256": self.resource_policy_sha256,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._content_record(), "spec_sha256": self.spec_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _SPEC_FIELDS, "evaluation spec")
        return cls(**dict(record))


@dataclass(frozen=True, slots=True)
class EvaluationReceipt:
    """One signed, non-reusable stochastic evaluation measurement."""

    measurement_id: str
    evaluation_attempt_id: str
    attempt_nonce: str
    repeat_index: int
    attempt_number: int
    retry_count: int
    evaluation_spec_sha256: str
    deliverable_manifest_sha256: str
    deliverable_tree_sha256: str
    task_sha256: str
    run_sha256: str
    config_sha256: str
    judge_requested_identity: str
    judge_resolved_identity: str
    judge_settings_sha256: str
    judge_prompt_sha256: str
    judge_output_schema_sha256: str
    runtime_policy_sha256: str
    egress_policy_sha256: str
    resource_policy_sha256: str
    raw_result_sha256: str
    raw_result_size_bytes: int
    raw_result_media_type: str
    status: str
    token_usage: EvaluationTokenUsage
    cost: CostMeasurement
    timing: MonotonicTiming
    issuer_policy_sha256: str
    issuer_key_id: str
    receipt_sha256: str
    signature: str
    schema_version: str = EVALUATION_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported evaluation receipt schema_version")
        for name in (
            "measurement_id",
            "evaluation_attempt_id",
            "attempt_nonce",
            "judge_requested_identity",
            "judge_resolved_identity",
            "issuer_key_id",
        ):
            _require_non_empty(cast(str, getattr(self, name)), name)
        for name in (
            "evaluation_spec_sha256",
            "deliverable_manifest_sha256",
            "deliverable_tree_sha256",
            "task_sha256",
            "run_sha256",
            "config_sha256",
            "judge_settings_sha256",
            "judge_prompt_sha256",
            "judge_output_schema_sha256",
            "runtime_policy_sha256",
            "egress_policy_sha256",
            "resource_policy_sha256",
            "raw_result_sha256",
            "issuer_policy_sha256",
            "receipt_sha256",
        ):
            _require_digest(cast(str, getattr(self, name)), name)
        for name in ("repeat_index", "attempt_number"):
            _require_positive_int_value(getattr(self, name), name)
        _require_non_negative_int_value(self.retry_count, "retry_count")
        if self.retry_count >= self.attempt_number:
            raise ValueError("retry_count must be less than attempt_number")
        _require_non_negative_int_value(
            self.raw_result_size_bytes, "raw_result_size_bytes"
        )
        if _MEDIA_TYPE_RE.fullmatch(self.raw_result_media_type) is None:
            raise ValueError("raw_result_media_type must be lowercase type/subtype")
        if self.status not in _STATUSES:
            raise ValueError("status must be 'succeeded' or 'failed'")
        if self.receipt_sha256 != _record_sha256(self._content_record()):
            raise ValueError("receipt_sha256 does not match evaluation receipt content")
        _decode_signature(self.signature)

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "evaluation_attempt_id": self.evaluation_attempt_id,
            "attempt_nonce": self.attempt_nonce,
            "repeat_index": self.repeat_index,
            "attempt_number": self.attempt_number,
            "retry_count": self.retry_count,
            "evaluation_spec_sha256": self.evaluation_spec_sha256,
            "deliverable_manifest_sha256": self.deliverable_manifest_sha256,
            "deliverable_tree_sha256": self.deliverable_tree_sha256,
            "task_sha256": self.task_sha256,
            "run_sha256": self.run_sha256,
            "config_sha256": self.config_sha256,
            "judge_requested_identity": self.judge_requested_identity,
            "judge_resolved_identity": self.judge_resolved_identity,
            "judge_settings_sha256": self.judge_settings_sha256,
            "judge_prompt_sha256": self.judge_prompt_sha256,
            "judge_output_schema_sha256": self.judge_output_schema_sha256,
            "runtime_policy_sha256": self.runtime_policy_sha256,
            "egress_policy_sha256": self.egress_policy_sha256,
            "resource_policy_sha256": self.resource_policy_sha256,
            "raw_result_sha256": self.raw_result_sha256,
            "raw_result_size_bytes": self.raw_result_size_bytes,
            "raw_result_media_type": self.raw_result_media_type,
            "status": self.status,
            "token_usage": self.token_usage.to_record(),
            "cost": self.cost.to_record(),
            "timing": self.timing.to_record(),
            "issuer_policy_sha256": self.issuer_policy_sha256,
            "issuer_key_id": self.issuer_key_id,
        }

    def _signed_record(self) -> dict[str, object]:
        return {**self._content_record(), "receipt_sha256": self.receipt_sha256}

    def to_record(self) -> dict[str, object]:
        return {**self._signed_record(), "signature": self.signature}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _RECEIPT_FIELDS, "evaluation receipt")
        values = dict(record)
        values["token_usage"] = EvaluationTokenUsage.from_record(
            _required_mapping(record.get("token_usage"), "token_usage")
        )
        values["cost"] = CostMeasurement.from_record(
            _required_mapping(record.get("cost"), "cost")
        )
        values["timing"] = MonotonicTiming.from_record(
            _required_mapping(record.get("timing"), "timing")
        )
        return cls(**values)


def build_evaluation_spec(**fields: object) -> EvaluationSpec:
    """Build a content-addressed pre-execution evaluation specification."""

    content = {"schema_version": EVALUATION_SPEC_SCHEMA_VERSION, **fields}
    return EvaluationSpec(
        **cast(dict[str, Any], fields),
        spec_sha256=_record_sha256(content),
    )


def criteria_commitment_sha256(
    criteria: Sequence[CriterionCommitment],
) -> str:
    """Hash criterion commitments in canonical criterion-ID order.

    The commitment records intentionally contain no rubric text, evaluator
    paths, reasoning, or transcript content.
    """

    canonical = tuple(
        CriterionCommitment.from_record(criterion.to_record()) for criterion in criteria
    )
    criterion_ids = tuple(criterion.criterion_id for criterion in canonical)
    if len(set(criterion_ids)) != len(criterion_ids):
        raise ValueError("criterion commitments contain duplicate criterion IDs")
    if canonical != tuple(sorted(canonical, key=lambda item: item.criterion_id)):
        raise ValueError("criterion commitments must be ordered by criterion_id")
    return _record_sha256(
        {"criteria": [criterion.to_record() for criterion in canonical]}
    )


def build_evaluation_receipt(
    *,
    spec: EvaluationSpec,
    signer: Callable[[bytes], bytes],
    measurement_id: str,
    evaluation_attempt_id: str,
    attempt_nonce: str,
    repeat_index: int,
    attempt_number: int,
    retry_count: int,
    judge_resolved_identity: str,
    raw_result_sha256: str,
    raw_result_size_bytes: int,
    raw_result_media_type: str,
    status: str,
    token_usage: EvaluationTokenUsage,
    cost: CostMeasurement,
    timing: MonotonicTiming,
    issuer_policy_sha256: str,
    issuer_key_id: str,
) -> EvaluationReceipt:
    """Build and externally sign one receipt; this never invokes a judge."""

    canonical_spec = EvaluationSpec.from_record(spec.to_record())
    content: dict[str, object] = {
        "schema_version": EVALUATION_RECEIPT_SCHEMA_VERSION,
        "measurement_id": measurement_id,
        "evaluation_attempt_id": evaluation_attempt_id,
        "attempt_nonce": attempt_nonce,
        "repeat_index": repeat_index,
        "attempt_number": attempt_number,
        "retry_count": retry_count,
        "evaluation_spec_sha256": canonical_spec.spec_sha256,
        "deliverable_manifest_sha256": (canonical_spec.deliverable_manifest_sha256),
        "deliverable_tree_sha256": canonical_spec.deliverable_tree_sha256,
        "task_sha256": canonical_spec.task_sha256,
        "run_sha256": canonical_spec.run_sha256,
        "config_sha256": canonical_spec.config_sha256,
        "judge_requested_identity": canonical_spec.judge_requested_identity,
        "judge_resolved_identity": judge_resolved_identity,
        "judge_settings_sha256": canonical_spec.judge_settings_sha256,
        "judge_prompt_sha256": canonical_spec.judge_prompt_sha256,
        "judge_output_schema_sha256": canonical_spec.judge_output_schema_sha256,
        "runtime_policy_sha256": canonical_spec.runtime_policy_sha256,
        "egress_policy_sha256": canonical_spec.egress_policy_sha256,
        "resource_policy_sha256": canonical_spec.resource_policy_sha256,
        "raw_result_sha256": raw_result_sha256,
        "raw_result_size_bytes": raw_result_size_bytes,
        "raw_result_media_type": raw_result_media_type,
        "status": status,
        "token_usage": token_usage.to_record(),
        "cost": cost.to_record(),
        "timing": timing.to_record(),
        "issuer_policy_sha256": issuer_policy_sha256,
        "issuer_key_id": issuer_key_id,
    }
    receipt_sha256 = _record_sha256(content)
    signed_record = {**content, "receipt_sha256": receipt_sha256}
    signature_bytes = signer(_signature_payload(signed_record))
    if len(signature_bytes) != 64:
        raise ValueError("signer must return a 64-byte Ed25519 signature")
    record = {
        **signed_record,
        "signature": base64.b64encode(signature_bytes).decode("ascii"),
    }
    return EvaluationReceipt.from_record(record)


def verify_evaluation_receipt(
    receipt: EvaluationReceipt,
    *,
    spec: EvaluationSpec,
    expected_spec_sha256: str,
    expected_deliverable_manifest_sha256: str,
    expected_runtime_policy_sha256: str,
    expected_issuer_policy_sha256: str,
    expected_issuer_key_id: str,
    issuer_public_key: Ed25519PublicKey,
    expected_measurement_id: str,
    expected_evaluation_attempt_id: str,
    expected_repeat_index: int,
    seen_measurement_ids: Set[str] | None = None,
    occupied_repeat_slots: Set[tuple[str, int]] | None = None,
) -> EvaluationReceipt:
    """Verify integrity, external trust, exact bindings, and optional replay state.

    Omitting the replay sets permits archival verification without expiring a
    valid receipt. Supplying them lets a caller reject already-consumed
    measurements or repeat slots. This function performs no network or judge
    operation and never mutates the caller's replay sets.
    """

    try:
        canonical_receipt = EvaluationReceipt.from_record(receipt.to_record())
        canonical_spec = EvaluationSpec.from_record(spec.to_record())
    except (AttributeError, TypeError, ValueError) as exc:
        raise EvaluationBindingError(str(exc)) from exc
    expected_bindings: tuple[tuple[str, object, object], ...] = (
        (
            "spec_sha256",
            canonical_spec.spec_sha256,
            expected_spec_sha256,
        ),
        (
            "evaluation_spec_sha256",
            canonical_receipt.evaluation_spec_sha256,
            canonical_spec.spec_sha256,
        ),
        (
            "issuer_policy_sha256",
            canonical_receipt.issuer_policy_sha256,
            expected_issuer_policy_sha256,
        ),
        (
            "issuer_key_id",
            canonical_receipt.issuer_key_id,
            expected_issuer_key_id,
        ),
        (
            "measurement_id",
            canonical_receipt.measurement_id,
            expected_measurement_id,
        ),
        (
            "evaluation_attempt_id",
            canonical_receipt.evaluation_attempt_id,
            expected_evaluation_attempt_id,
        ),
        (
            "repeat_index",
            canonical_receipt.repeat_index,
            expected_repeat_index,
        ),
    )
    for name, actual, expected in expected_bindings:
        if actual != expected:
            raise EvaluationBindingError(f"{name} does not match expected binding")
    spec_receipt_bindings = (
        "deliverable_manifest_sha256",
        "deliverable_tree_sha256",
        "task_sha256",
        "run_sha256",
        "config_sha256",
        "judge_requested_identity",
        "judge_settings_sha256",
        "judge_prompt_sha256",
        "judge_output_schema_sha256",
        "runtime_policy_sha256",
        "egress_policy_sha256",
        "resource_policy_sha256",
    )
    for name in spec_receipt_bindings:
        if getattr(canonical_receipt, name) != getattr(canonical_spec, name):
            raise EvaluationBindingError(f"{name} does not match evaluation spec")
    external_spec_bindings = (
        (
            "deliverable_manifest_sha256",
            canonical_spec.deliverable_manifest_sha256,
            expected_deliverable_manifest_sha256,
        ),
        (
            "runtime_policy_sha256",
            canonical_spec.runtime_policy_sha256,
            expected_runtime_policy_sha256,
        ),
    )
    for name, actual, expected in external_spec_bindings:
        if actual != expected:
            raise EvaluationBindingError(f"{name} does not match expected binding")
    signed_record = canonical_receipt.to_record()
    signed_record.pop("signature")
    try:
        issuer_public_key.verify(
            _decode_signature(canonical_receipt.signature),
            _signature_payload(signed_record),
        )
    except InvalidSignature as exc:
        raise EvaluationBindingError("evaluation receipt signature is invalid") from exc
    if (
        seen_measurement_ids is not None
        and canonical_receipt.measurement_id in seen_measurement_ids
    ):
        raise EvaluationBindingError("measurement_id has already been consumed")
    repeat_slot = (
        canonical_receipt.evaluation_spec_sha256,
        canonical_receipt.repeat_index,
    )
    if occupied_repeat_slots is not None and repeat_slot in occupied_repeat_slots:
        raise EvaluationBindingError("evaluation repeat slot is already occupied")
    return canonical_receipt


def verify_raw_evaluation_result(
    receipt: EvaluationReceipt,
    raw_result: bytes,
    *,
    expected_media_type: str,
) -> None:
    """Verify exact raw-result bytes without parsing or exposing their content."""

    canonical_receipt = EvaluationReceipt.from_record(receipt.to_record())
    if canonical_receipt.raw_result_media_type != expected_media_type:
        raise EvaluationBindingError(
            "raw_result_media_type does not match expected binding"
        )
    if len(raw_result) != canonical_receipt.raw_result_size_bytes:
        raise EvaluationBindingError(
            "raw result size does not match evaluation receipt"
        )
    actual = "sha256:" + hashlib.sha256(raw_result).hexdigest()
    if actual != canonical_receipt.raw_result_sha256:
        raise EvaluationBindingError(
            "raw result hash does not match evaluation receipt"
        )


def _signature_payload(record: Mapping[str, object]) -> bytes:
    return EVALUATION_SIGNATURE_DOMAIN + _canonical_json(record)


def _record_sha256(record: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(record)).hexdigest()


def _canonical_json(record: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("record must contain canonical JSON values") from exc


def _decode_signature(value: str) -> bytes:
    _require_non_empty(value, "signature")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("signature must be canonical base64") from exc
    if len(decoded) != 64 or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("signature must encode exactly 64 Ed25519 bytes")
    return decoded


def _parse_utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC3339 UTC timestamp") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise ValueError(f"{field_name} must use canonical RFC3339 UTC form")
    return parsed


def _require_exact_fields(
    record: Mapping[str, Any], expected: frozenset[str], field_name: str
) -> None:
    if frozenset(record) != expected:
        raise ValueError(f"{field_name} has unexpected fields")


def _require_non_empty(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_digest(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(
            f"{field_name} must be a canonical prefixed lowercase SHA-256 digest"
        )
    return value


def _require_git_sha(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _GIT_SHA_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase 40-character Git SHA")
    return value


def _require_non_negative_int_value(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _require_positive_int_value(value: object, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    _require_non_empty(value, field_name)
    return cast(str, value)


def _optional_string(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    _require_non_empty(value, field_name)
    return cast(str, value)


def _required_non_negative_int(record: Mapping[str, Any], field_name: str) -> int:
    return _require_non_negative_int_value(record.get(field_name), field_name)


def _optional_non_negative_int(
    record: Mapping[str, Any], field_name: str
) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    return _require_non_negative_int_value(value, field_name)


def _required_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)
