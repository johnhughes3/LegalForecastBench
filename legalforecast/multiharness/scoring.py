"""Deterministic offline scoring of authorized evaluation receipts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self, cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast.multiharness.evaluation import (
    EvaluationReceipt,
    EvaluationSpec,
    verify_evaluation_result,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    validate_public_record,
)

METRIC_DEFINITION_SCHEMA_VERSION = "legalforecast.multiharness.metric_definition.v1"
SCORE_ARTIFACT_SCHEMA_VERSION = "legalforecast.multiharness.score_artifact.v1"
LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION = (
    "legalforecast.multiharness.harvey_lab_verdicts.v1"
)
HARVEY_LAB_NORMALIZER_ID = "legalforecast.harvey-lab-all-pass-normalizer.v1"

_OPAQUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")
_METRIC_FIELDS = frozenset(
    {
        "schema_version",
        "metric_id",
        "criterion_count",
        "raw_min",
        "raw_max",
        "direction",
        "unit",
        "weight_rule",
        "missingness_rule",
        "rounding_rule",
        "aggregation_rule",
        "rubric_sha256",
        "criteria_sha256",
        "aggregation_sha256",
        "output_schema_sha256",
        "raw_derivative_schema_version",
        "normalizer_id",
        "definition_sha256",
    }
)
_SCORE_FIELDS = frozenset(
    {
        "schema_version",
        "evaluation_receipt_sha256",
        "evaluation_spec_sha256",
        "raw_result_sha256",
        "metric_definition_sha256",
        "score_value",
        "unit",
        "n_passed",
        "n_criteria",
        "score_sha256",
    }
)


class ScoreNormalizationError(ValueError):
    """An authorized evaluation result cannot be normalized deterministically."""


@dataclass(frozen=True, slots=True)
class _CriterionObservation:
    ordinal: int
    verdict: str
    raw_value: int
    unit: str = "binary"
    weight: None = None


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """A complete deterministic scoring definition."""

    metric_id: str
    criterion_count: int
    raw_min: int
    raw_max: int
    direction: str
    unit: str
    weight_rule: str
    missingness_rule: str
    rounding_rule: str
    aggregation_rule: str
    rubric_sha256: str
    criteria_sha256: str
    aggregation_sha256: str
    output_schema_sha256: str
    raw_derivative_schema_version: str
    normalizer_id: str
    definition_sha256: str
    schema_version: str = METRIC_DEFINITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != METRIC_DEFINITION_SCHEMA_VERSION:
            raise ValueError("unsupported metric definition schema_version")
        _opaque(self.metric_id, "metric_id")
        if self.metric_id != "harvey-lab-binary-all-pass-v1":
            raise ValueError("metric_id must identify the pinned LAB v1 metric")
        _positive(self.criterion_count, "criterion_count")
        if self.criterion_count != 23:
            raise ValueError("criterion_count must be exactly 23")
        _integer(self.raw_min, "raw_min")
        _integer(self.raw_max, "raw_max")
        if self.raw_min >= self.raw_max:
            raise ValueError("raw_min must be less than raw_max")
        expected = {
            "direction": "higher_is_better",
            "unit": "binary",
            "weight_rule": "unweighted",
            "missingness_rule": "reject",
            "rounding_rule": "none",
            "aggregation_rule": "all_pass",
        }
        for name, required in expected.items():
            if getattr(self, name) != required:
                raise ValueError(f"{name} must be {required!r}")
        if (self.raw_min, self.raw_max) != (0, 1):
            raise ValueError("binary metric raw bounds must be exactly 0 and 1")
        if self.raw_derivative_schema_version != LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION:
            raise ValueError("raw_derivative_schema_version must identify LAB v1")
        if self.normalizer_id != HARVEY_LAB_NORMALIZER_ID:
            raise ValueError("normalizer_id must identify the pinned LAB v1 normalizer")
        for name in (
            "rubric_sha256",
            "criteria_sha256",
            "aggregation_sha256",
            "output_schema_sha256",
        ):
            _digest(cast(str, getattr(self, name)), name)
        if self.definition_sha256 != _hash(self._content_record()):
            raise ValueError("definition_sha256 does not match metric definition")
        _public(self.to_record(), "metric definition")

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "metric_id": self.metric_id,
            "criterion_count": self.criterion_count,
            "raw_min": self.raw_min,
            "raw_max": self.raw_max,
            "direction": self.direction,
            "unit": self.unit,
            "weight_rule": self.weight_rule,
            "missingness_rule": self.missingness_rule,
            "rounding_rule": self.rounding_rule,
            "aggregation_rule": self.aggregation_rule,
            "rubric_sha256": self.rubric_sha256,
            "criteria_sha256": self.criteria_sha256,
            "aggregation_sha256": self.aggregation_sha256,
            "output_schema_sha256": self.output_schema_sha256,
            "raw_derivative_schema_version": self.raw_derivative_schema_version,
            "normalizer_id": self.normalizer_id,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._content_record(), "definition_sha256": self.definition_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _exact(record, _METRIC_FIELDS, "metric definition")
        return cls(**dict(record))


@dataclass(frozen=True, slots=True)
class ScoreArtifact:
    """Deterministic score derived from one authorized evaluation receipt."""

    evaluation_receipt_sha256: str
    evaluation_spec_sha256: str
    raw_result_sha256: str
    metric_definition_sha256: str
    score_value: int
    unit: str
    n_passed: int
    n_criteria: int
    score_sha256: str
    schema_version: str = SCORE_ARTIFACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCORE_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported score artifact schema_version")
        for name in (
            "evaluation_receipt_sha256",
            "evaluation_spec_sha256",
            "raw_result_sha256",
            "metric_definition_sha256",
            "score_sha256",
        ):
            _digest(cast(str, getattr(self, name)), name)
        if self.unit != "binary":
            raise ValueError("score unit must be binary")
        _positive(self.n_criteria, "n_criteria")
        if self.n_criteria != 23:
            raise ValueError("n_criteria must be exactly 23")
        _non_negative(self.n_passed, "n_passed")
        if self.n_passed > self.n_criteria:
            raise ValueError("n_passed cannot exceed n_criteria")
        expected_score = 1 if self.n_passed == self.n_criteria else 0
        if self.score_value != expected_score or type(self.score_value) is not int:
            raise ValueError("score_value must be 1 iff every criterion passes")
        if self.score_sha256 != _hash(self._content_record()):
            raise ValueError("score_sha256 does not match score artifact")
        _public(self.to_record(), "score artifact")

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evaluation_receipt_sha256": self.evaluation_receipt_sha256,
            "evaluation_spec_sha256": self.evaluation_spec_sha256,
            "raw_result_sha256": self.raw_result_sha256,
            "metric_definition_sha256": self.metric_definition_sha256,
            "score_value": self.score_value,
            "unit": self.unit,
            "n_passed": self.n_passed,
            "n_criteria": self.n_criteria,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._content_record(), "score_sha256": self.score_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _exact(record, _SCORE_FIELDS, "score artifact")
        return cls(**dict(record))


def build_harvey_lab_metric_definition(
    *,
    rubric_sha256: str,
    criteria_sha256: str,
    aggregation_sha256: str,
    output_schema_sha256: str,
) -> MetricDefinition:
    """Build the exact pinned 23-criterion Harvey LAB all-pass metric."""

    content: dict[str, object] = {
        "schema_version": METRIC_DEFINITION_SCHEMA_VERSION,
        "metric_id": "harvey-lab-binary-all-pass-v1",
        "criterion_count": 23,
        "raw_min": 0,
        "raw_max": 1,
        "direction": "higher_is_better",
        "unit": "binary",
        "weight_rule": "unweighted",
        "missingness_rule": "reject",
        "rounding_rule": "none",
        "aggregation_rule": "all_pass",
        "rubric_sha256": rubric_sha256,
        "criteria_sha256": criteria_sha256,
        "aggregation_sha256": aggregation_sha256,
        "output_schema_sha256": output_schema_sha256,
        "raw_derivative_schema_version": LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
        "normalizer_id": HARVEY_LAB_NORMALIZER_ID,
    }
    return MetricDefinition(
        metric_id="harvey-lab-binary-all-pass-v1",
        criterion_count=23,
        raw_min=0,
        raw_max=1,
        direction="higher_is_better",
        unit="binary",
        weight_rule="unweighted",
        missingness_rule="reject",
        rounding_rule="none",
        aggregation_rule="all_pass",
        rubric_sha256=rubric_sha256,
        criteria_sha256=criteria_sha256,
        aggregation_sha256=aggregation_sha256,
        output_schema_sha256=output_schema_sha256,
        raw_derivative_schema_version=LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
        normalizer_id=HARVEY_LAB_NORMALIZER_ID,
        definition_sha256=_hash(content),
    )


def normalize_harvey_lab_score(
    *,
    receipt: EvaluationReceipt,
    raw_result: bytes,
    spec: EvaluationSpec,
    metric: MetricDefinition,
    expected_metric_definition_sha256: str,
    expected_media_type: str,
    expected_spec_sha256: str,
    expected_deliverable_manifest_sha256: str,
    expected_runtime_policy_sha256: str,
    expected_issuer_policy_sha256: str,
    expected_issuer_key_id: str,
    issuer_public_key: Ed25519PublicKey,
    expected_measurement_id: str,
    expected_evaluation_attempt_id: str,
    expected_attempt_nonce: str,
    expected_repeat_index: int,
    seen_measurement_ids: set[str] | None = None,
    seen_attempt_nonces: set[str] | None = None,
    occupied_repeat_slots: set[tuple[str, int]] | None = None,
) -> ScoreArtifact:
    """Verify and normalize one pinned LAB result entirely offline."""

    if expected_media_type != "application/json":
        raise ScoreNormalizationError(
            "LAB verdict derivative media type must be application/json"
        )
    try:
        canonical_spec = EvaluationSpec.from_record(spec.to_record())
        canonical_metric = MetricDefinition.from_record(metric.to_record())
        canonical_receipt = verify_evaluation_result(
            receipt,
            raw_result,
            expected_media_type=expected_media_type,
            spec=canonical_spec,
            expected_spec_sha256=expected_spec_sha256,
            expected_deliverable_manifest_sha256=(expected_deliverable_manifest_sha256),
            expected_runtime_policy_sha256=expected_runtime_policy_sha256,
            expected_issuer_policy_sha256=expected_issuer_policy_sha256,
            expected_issuer_key_id=expected_issuer_key_id,
            issuer_public_key=issuer_public_key,
            expected_measurement_id=expected_measurement_id,
            expected_evaluation_attempt_id=expected_evaluation_attempt_id,
            expected_attempt_nonce=expected_attempt_nonce,
            expected_repeat_index=expected_repeat_index,
            seen_measurement_ids=seen_measurement_ids,
            seen_attempt_nonces=seen_attempt_nonces,
            occupied_repeat_slots=occupied_repeat_slots,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ScoreNormalizationError(str(exc)) from exc
    _digest(expected_metric_definition_sha256, "expected_metric_definition_sha256")
    if canonical_metric.definition_sha256 != expected_metric_definition_sha256:
        raise ScoreNormalizationError(
            "metric does not match externally authorized definition"
        )
    if canonical_receipt.status != "succeeded":
        raise ScoreNormalizationError("only a succeeded evaluation may be scored")
    bindings = (
        ("rubric_sha256", canonical_metric.rubric_sha256, canonical_spec.rubric_sha256),
        (
            "criteria_sha256",
            canonical_metric.criteria_sha256,
            canonical_spec.criteria_sha256,
        ),
        (
            "aggregation_sha256",
            canonical_metric.aggregation_sha256,
            canonical_spec.aggregation_sha256,
        ),
        (
            "output_schema_sha256",
            canonical_metric.output_schema_sha256,
            canonical_spec.judge_output_schema_sha256,
        ),
    )
    for name, actual, expected in bindings:
        if actual != expected:
            raise ScoreNormalizationError(f"{name} does not match authorized receipt")
    try:
        observations, supplied_score, supplied_passed, supplied_count = (
            _parse_lab_verdicts(raw_result)
        )
    except (TypeError, ValueError) as exc:
        raise ScoreNormalizationError(str(exc)) from exc
    if len(observations) != canonical_metric.criterion_count:
        raise ScoreNormalizationError("verdict count does not match criterion_count")
    n_passed = sum(item.raw_value for item in observations)
    score_value = 1 if n_passed == len(observations) else 0
    if (
        supplied_count != len(observations)
        or supplied_passed != n_passed
        or supplied_score != score_value
    ):
        raise ScoreNormalizationError("raw score/count diagnostics are inconsistent")
    content: dict[str, object] = {
        "schema_version": SCORE_ARTIFACT_SCHEMA_VERSION,
        "evaluation_receipt_sha256": canonical_receipt.receipt_sha256,
        "evaluation_spec_sha256": canonical_receipt.evaluation_spec_sha256,
        "raw_result_sha256": canonical_receipt.raw_result_sha256,
        "metric_definition_sha256": canonical_metric.definition_sha256,
        "score_value": score_value,
        "unit": "binary",
        "n_passed": n_passed,
        "n_criteria": len(observations),
    }
    return ScoreArtifact(
        evaluation_receipt_sha256=canonical_receipt.receipt_sha256,
        evaluation_spec_sha256=canonical_receipt.evaluation_spec_sha256,
        raw_result_sha256=canonical_receipt.raw_result_sha256,
        metric_definition_sha256=canonical_metric.definition_sha256,
        score_value=score_value,
        unit="binary",
        n_passed=n_passed,
        n_criteria=len(observations),
        score_sha256=_hash(content),
    )


def _parse_lab_verdicts(
    raw_result: bytes,
) -> tuple[tuple[_CriterionObservation, ...], int, int, int]:
    try:
        decoded = json.loads(raw_result, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreNormalizationError(
            "raw verdict derivative must be UTF-8 JSON"
        ) from exc
    try:
        canonical_bytes = json.dumps(
            decoded,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ScoreNormalizationError(
            "raw verdict derivative is not canonical JSON"
        ) from exc
    if raw_result != canonical_bytes:
        raise ScoreNormalizationError(
            "raw verdict derivative must use exact canonical UTF-8 JSON bytes"
        )
    record = _mapping(decoded, "raw verdict derivative")
    _exact(
        record,
        frozenset({"schema_version", "verdicts", "score", "n_passed", "n_criteria"}),
        "raw verdict derivative",
    )
    if record.get("schema_version") != LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION:
        raise ScoreNormalizationError("unsupported raw verdict derivative schema")
    raw_verdicts = record.get("verdicts")
    if not isinstance(raw_verdicts, Sequence) or isinstance(raw_verdicts, str | bytes):
        raise ScoreNormalizationError("verdicts must be an array")
    observations: list[_CriterionObservation] = []
    for expected_ordinal, raw in enumerate(
        cast(Sequence[object], raw_verdicts), start=1
    ):
        item = _mapping(raw, "verdict")
        _exact(item, frozenset({"ordinal", "verdict"}), "verdict")
        if _required_positive(item, "ordinal") != expected_ordinal:
            raise ScoreNormalizationError(
                "verdicts require unique contiguous 1-based ordinals"
            )
        verdict = _required_string(item, "verdict")
        if verdict not in {"pass", "fail"}:
            raise ScoreNormalizationError("verdict must be pass or fail")
        observations.append(
            _CriterionObservation(
                ordinal=expected_ordinal,
                verdict=verdict,
                raw_value=1 if verdict == "pass" else 0,
            )
        )
    return (
        tuple(observations),
        _required_binary(record, "score"),
        _required_non_negative(record, "n_passed"),
        _required_positive(record, "n_criteria"),
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ScoreNormalizationError("raw verdict derivative has duplicate fields")
        record[key] = value
    return record


def _hash(record: Mapping[str, object]) -> str:
    payload = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _exact(
    record: Mapping[str, Any], expected: frozenset[str], field_name: str
) -> None:
    if frozenset(record) != expected:
        raise ValueError(f"{field_name} has unexpected fields")


def _digest(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{field_name} must be a canonical prefixed SHA-256")
    return value


def _opaque(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _OPAQUE_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a bounded opaque identifier")
    return value


def _integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field_name} must be an integer")
    return value


def _positive(value: object, field_name: str) -> int:
    result = _integer(value, field_name)
    if result <= 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def _non_negative(value: object, field_name: str) -> int:
    result = _integer(value, field_name)
    if result < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return result


def _required_positive(record: Mapping[str, Any], field_name: str) -> int:
    return _positive(record.get(field_name), field_name)


def _required_non_negative(record: Mapping[str, Any], field_name: str) -> int:
    return _non_negative(record.get(field_name), field_name)


def _required_binary(record: Mapping[str, Any], field_name: str) -> int:
    value = _integer(record.get(field_name), field_name)
    if value not in {0, 1}:
        raise ValueError(f"{field_name} must be binary")
    return value


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _public(record: Mapping[str, object], field_name: str) -> None:
    try:
        validate_public_record(record, field_name)
    except MultiHarnessValidationError as exc:
        raise ValueError(str(exc)) from exc
