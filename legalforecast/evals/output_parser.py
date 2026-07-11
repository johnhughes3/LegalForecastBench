"""Strict parser for structured model outputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from json import JSONDecodeError
from typing import Any, cast

DEFAULT_MISSING_PROBABILITY = 0.5


class ParserStatus(StrEnum):
    """Top-level parser outcome for one raw model response."""

    VALID = "valid"
    REPAIRED_VALID = "repaired_valid"
    INVALID_JSON = "invalid_json"
    REFUSAL = "refusal"
    MISSING_UNIT = "missing_unit"
    EXTRA_UNIT = "extra_unit"
    DUPLICATE_UNIT = "duplicate_unit"
    INVALID_PROBABILITY = "invalid_probability"
    INVALID_SCHEMA = "invalid_schema"


class ParserIssueCode(StrEnum):
    """Machine-readable parser issue codes."""

    JSON_DECODE_ERROR = "json_decode_error"
    MODEL_REFUSAL = "model_refusal"
    ROOT_NOT_OBJECT = "root_not_object"
    CASE_ASSESSMENT_MISSING = "case_assessment_missing"
    PREDICTIONS_MISSING = "predictions_missing"
    PREDICTION_NOT_OBJECT = "prediction_not_object"
    UNIT_ID_MISSING = "unit_id_missing"
    EXTRA_UNIT = "extra_unit"
    DUPLICATE_UNIT = "duplicate_unit"
    MISSING_REQUIRED_UNIT = "missing_required_unit"
    PROBABILITY_MISSING = "probability_missing"
    PROBABILITY_NOT_NUMBER = "probability_not_number"
    PROBABILITY_OUT_OF_RANGE = "probability_out_of_range"


@dataclass(frozen=True, slots=True)
class ParserIssue:
    """One deterministic validation issue emitted by the output parser."""

    code: ParserIssueCode
    message: str
    unit_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.message, "message")
        if self.unit_id is not None:
            _require_non_empty(self.unit_id, "unit_id")

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "unit_id": self.unit_id,
        }


@dataclass(frozen=True, slots=True)
class ParsedPrediction:
    """One required-unit prediction after deterministic parser normalization."""

    unit_id: str
    probability_fully_dismissed: float
    rationale: str | None = None
    defaulted: bool = False
    invalid_reason: ParserIssueCode | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_probability(
            self.probability_fully_dismissed,
            "probability_fully_dismissed",
        )
        if self.rationale is not None:
            _require_non_empty(self.rationale, "rationale")
        if self.defaulted and self.invalid_reason is None:
            raise ValueError("defaulted predictions require invalid_reason")
        if not self.defaulted and self.invalid_reason is not None:
            raise ValueError("non-defaulted predictions must not set invalid_reason")

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "probability_fully_dismissed": self.probability_fully_dismissed,
            "rationale": self.rationale,
            "defaulted": self.defaulted,
            "invalid_reason": (
                self.invalid_reason.value if self.invalid_reason is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ExtraPrediction:
    """Prediction for a unit ID outside the required frozen unit set."""

    unit_id: str
    probability_fully_dismissed: float | None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        if self.probability_fully_dismissed is not None:
            _require_probability(
                self.probability_fully_dismissed,
                "probability_fully_dismissed",
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "probability_fully_dismissed": self.probability_fully_dismissed,
        }


@dataclass(frozen=True, slots=True)
class ParsedModelOutput:
    """Structured parser artifact consumed by scoring and reporting."""

    status: ParserStatus
    raw_output_sha256: str
    required_unit_ids: tuple[str, ...]
    predictions: tuple[ParsedPrediction, ...]
    issues: tuple[ParserIssue, ...]
    case_assessment: str | None = None
    extra_predictions: tuple[ExtraPrediction, ...] = ()
    repair_attempted: bool = False
    repair_applied: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.raw_output_sha256, "raw_output_sha256")
        if not self.raw_output_sha256.startswith("sha256:"):
            raise ValueError("raw_output_sha256 must use sha256: prefix")
        if not self.required_unit_ids:
            raise ValueError("required_unit_ids must not be empty")
        if len(self.required_unit_ids) != len(set(self.required_unit_ids)):
            raise ValueError("required_unit_ids must be unique")
        for unit_id in self.required_unit_ids:
            _require_non_empty(unit_id, "required_unit_ids")
        if len(self.predictions) != len(self.required_unit_ids):
            raise ValueError("predictions must include one record per required unit")
        if tuple(prediction.unit_id for prediction in self.predictions) != (
            self.required_unit_ids
        ):
            raise ValueError("predictions must follow required_unit_ids order")
        if self.repair_applied and not self.repair_attempted:
            raise ValueError("repair_applied requires repair_attempted")

    @property
    def is_valid(self) -> bool:
        return self.status in {ParserStatus.VALID, ParserStatus.REPAIRED_VALID}

    @property
    def invalid_output(self) -> bool:
        return not self.is_valid

    @property
    def defaulted_unit_ids(self) -> tuple[str, ...]:
        return tuple(
            prediction.unit_id
            for prediction in self.predictions
            if prediction.defaulted
        )

    def prediction_for(self, unit_id: str) -> ParsedPrediction:
        for prediction in self.predictions:
            if prediction.unit_id == unit_id:
                return prediction
        raise KeyError(unit_id)

    def to_record(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "invalid_output": self.invalid_output,
            "raw_output_sha256": self.raw_output_sha256,
            "case_assessment": self.case_assessment,
            "required_unit_ids": list(self.required_unit_ids),
            "predictions": [prediction.to_record() for prediction in self.predictions],
            "defaulted_unit_ids": list(self.defaulted_unit_ids),
            "extra_predictions": [
                prediction.to_record() for prediction in self.extra_predictions
            ],
            "issues": [issue.to_record() for issue in self.issues],
            "repair_attempted": self.repair_attempted,
            "repair_applied": self.repair_applied,
        }


@dataclass(frozen=True, slots=True)
class DecodeResult:
    payload: Mapping[str, Any] | None
    repair_attempted: bool
    repair_applied: bool
    error_message: str | None = None


def parse_model_output(
    raw_output: str,
    *,
    required_unit_ids: Sequence[str],
    missing_default_probability: float = DEFAULT_MISSING_PROBABILITY,
) -> ParsedModelOutput:
    """Parse model JSON into one deterministic record per required unit."""

    required_units = _validate_required_unit_ids(required_unit_ids)
    _require_probability(missing_default_probability, "missing_default_probability")
    raw_hash = _sha256_prefixed(raw_output)

    decoded = _decode_json_with_repair(raw_output)
    if decoded.payload is None and _looks_like_refusal(raw_output):
        return _invalid_output(
            status=ParserStatus.REFUSAL,
            raw_output_sha256=raw_hash,
            required_unit_ids=required_units,
            issue=ParserIssue(
                code=ParserIssueCode.MODEL_REFUSAL,
                message="Model response appears to refuse the task.",
            ),
            missing_default_probability=missing_default_probability,
            repair_attempted=decoded.repair_attempted,
            repair_applied=False,
        )

    if decoded.payload is None:
        return _invalid_output(
            status=ParserStatus.INVALID_JSON,
            raw_output_sha256=raw_hash,
            required_unit_ids=required_units,
            issue=ParserIssue(
                code=ParserIssueCode.JSON_DECODE_ERROR,
                message=decoded.error_message or "Model output is not valid JSON.",
            ),
            missing_default_probability=missing_default_probability,
            repair_attempted=decoded.repair_attempted,
            repair_applied=decoded.repair_applied,
        )

    return _parse_payload(
        decoded.payload,
        raw_output_sha256=raw_hash,
        required_unit_ids=required_units,
        missing_default_probability=missing_default_probability,
        repair_attempted=decoded.repair_attempted,
        repair_applied=decoded.repair_applied,
    )


def _parse_payload(
    payload: Mapping[str, Any],
    *,
    raw_output_sha256: str,
    required_unit_ids: tuple[str, ...],
    missing_default_probability: float,
    repair_attempted: bool,
    repair_applied: bool,
) -> ParsedModelOutput:
    issues: list[ParserIssue] = []
    parsed_by_unit: dict[str, ParsedPrediction] = {}
    extra_predictions: list[ExtraPrediction] = []

    case_assessment = payload.get("case_assessment")
    if not isinstance(case_assessment, str) or not case_assessment.strip():
        issues.append(
            ParserIssue(
                code=ParserIssueCode.CASE_ASSESSMENT_MISSING,
                message="case_assessment must be a non-empty string.",
            )
        )
        normalized_case_assessment: str | None = None
    else:
        normalized_case_assessment = case_assessment

    raw_predictions = payload.get("predictions")
    if not isinstance(raw_predictions, list):
        issues.append(
            ParserIssue(
                code=ParserIssueCode.PREDICTIONS_MISSING,
                message="predictions must be a list.",
            )
        )
        raw_prediction_items: list[Any] = []
    else:
        raw_prediction_items = cast(list[Any], raw_predictions)

    required_set = set(required_unit_ids)
    for index, raw_prediction in enumerate(raw_prediction_items):
        if not isinstance(raw_prediction, Mapping):
            issues.append(
                ParserIssue(
                    code=ParserIssueCode.PREDICTION_NOT_OBJECT,
                    message=f"prediction at index {index} must be an object.",
                )
            )
            continue
        prediction = cast(Mapping[str, Any], raw_prediction)
        unit_id = prediction.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id.strip():
            issues.append(
                ParserIssue(
                    code=ParserIssueCode.UNIT_ID_MISSING,
                    message=f"prediction at index {index} needs unit_id.",
                )
            )
            continue
        if unit_id not in required_set:
            probability = _optional_probability(prediction)
            extra_predictions.append(
                ExtraPrediction(
                    unit_id=unit_id,
                    probability_fully_dismissed=probability,
                )
            )
            issues.append(
                ParserIssue(
                    code=ParserIssueCode.EXTRA_UNIT,
                    message="Prediction references a unit outside the frozen set.",
                    unit_id=unit_id,
                )
            )
            continue
        if unit_id in parsed_by_unit:
            issues.append(
                ParserIssue(
                    code=ParserIssueCode.DUPLICATE_UNIT,
                    message="Duplicate prediction for required unit.",
                    unit_id=unit_id,
                )
            )
            continue

        probability_result = _required_probability(prediction, unit_id=unit_id)
        if isinstance(probability_result, ParserIssue):
            issues.append(probability_result)
            parsed_by_unit[unit_id] = _default_prediction(
                unit_id,
                probability=missing_default_probability,
                reason=probability_result.code,
            )
            continue

        parsed_by_unit[unit_id] = ParsedPrediction(
            unit_id=unit_id,
            probability_fully_dismissed=probability_result,
            rationale=_optional_rationale(prediction),
        )

    for unit_id in required_unit_ids:
        if unit_id not in parsed_by_unit:
            issues.append(
                ParserIssue(
                    code=ParserIssueCode.MISSING_REQUIRED_UNIT,
                    message="Required prediction unit is missing.",
                    unit_id=unit_id,
                )
            )
            parsed_by_unit[unit_id] = _default_prediction(
                unit_id,
                probability=missing_default_probability,
                reason=ParserIssueCode.MISSING_REQUIRED_UNIT,
            )

    predictions = tuple(parsed_by_unit[unit_id] for unit_id in required_unit_ids)
    status = _status_from_issues(
        issues,
        repair_applied=repair_applied,
    )
    return ParsedModelOutput(
        status=status,
        raw_output_sha256=raw_output_sha256,
        required_unit_ids=required_unit_ids,
        predictions=predictions,
        issues=tuple(issues),
        case_assessment=normalized_case_assessment,
        extra_predictions=tuple(extra_predictions),
        repair_attempted=repair_attempted,
        repair_applied=repair_applied,
    )


def _status_from_issues(
    issues: Sequence[ParserIssue],
    *,
    repair_applied: bool,
) -> ParserStatus:
    codes = {issue.code for issue in issues}
    if ParserIssueCode.DUPLICATE_UNIT in codes:
        return ParserStatus.DUPLICATE_UNIT
    if ParserIssueCode.MISSING_REQUIRED_UNIT in codes:
        return ParserStatus.MISSING_UNIT
    if codes.intersection(
        {
            ParserIssueCode.PROBABILITY_MISSING,
            ParserIssueCode.PROBABILITY_NOT_NUMBER,
            ParserIssueCode.PROBABILITY_OUT_OF_RANGE,
        }
    ):
        return ParserStatus.INVALID_PROBABILITY
    if ParserIssueCode.EXTRA_UNIT in codes:
        return ParserStatus.EXTRA_UNIT
    if codes:
        return ParserStatus.INVALID_SCHEMA
    if repair_applied:
        return ParserStatus.REPAIRED_VALID
    return ParserStatus.VALID


def _invalid_output(
    *,
    status: ParserStatus,
    raw_output_sha256: str,
    required_unit_ids: tuple[str, ...],
    issue: ParserIssue,
    missing_default_probability: float,
    repair_attempted: bool = False,
    repair_applied: bool = False,
) -> ParsedModelOutput:
    return ParsedModelOutput(
        status=status,
        raw_output_sha256=raw_output_sha256,
        required_unit_ids=required_unit_ids,
        predictions=tuple(
            _default_prediction(
                unit_id,
                probability=missing_default_probability,
                reason=issue.code,
            )
            for unit_id in required_unit_ids
        ),
        issues=(issue,),
        repair_attempted=repair_attempted,
        repair_applied=repair_applied,
    )


def _decode_json_with_repair(raw_output: str) -> DecodeResult:
    candidates = [raw_output]
    stripped = _strip_markdown_fence(raw_output)
    if stripped != raw_output:
        candidates.append(stripped)
    extracted = _extract_balanced_json_object(stripped)
    if extracted is not None and extracted not in candidates:
        candidates.append(extracted)

    last_error: str | None = None
    for index, candidate in enumerate(candidates):
        try:
            value: Any = json.loads(candidate)
        except JSONDecodeError as exc:
            last_error = exc.msg
            continue
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            items = cast(Sequence[Any], value)
            if len(items) == 1 and isinstance(items[0], Mapping):
                return DecodeResult(
                    payload=cast(Mapping[str, Any], items[0]),
                    repair_attempted=True,
                    repair_applied=True,
                )
        if not isinstance(value, Mapping):
            return DecodeResult(
                payload=None,
                repair_attempted=index > 0,
                repair_applied=False,
                error_message="JSON root must be an object.",
            )
        return DecodeResult(
            payload=cast(Mapping[str, Any], value),
            repair_attempted=index > 0,
            repair_applied=index > 0,
        )
    return DecodeResult(
        payload=None,
        repair_attempted=len(candidates) > 1,
        repair_applied=False,
        error_message=last_error,
    )


def _strip_markdown_fence(raw_output: str) -> str:
    stripped = raw_output.strip()
    if not stripped.startswith("```"):
        return raw_output
    lines = stripped.splitlines()
    if len(lines) < 2 or not lines[-1].strip().startswith("```"):
        return raw_output
    return "\n".join(lines[1:-1]).strip()


def _extract_balanced_json_object(raw_output: str) -> str | None:
    start = raw_output.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(raw_output[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw_output[start : index + 1]
    return None


def _required_probability(
    prediction: Mapping[str, Any],
    *,
    unit_id: str,
) -> float | ParserIssue:
    if "probability_fully_dismissed" not in prediction:
        return ParserIssue(
            code=ParserIssueCode.PROBABILITY_MISSING,
            message="probability_fully_dismissed is required.",
            unit_id=unit_id,
        )
    value = prediction["probability_fully_dismissed"]
    if not isinstance(value, int | float) or isinstance(value, bool):
        return ParserIssue(
            code=ParserIssueCode.PROBABILITY_NOT_NUMBER,
            message="probability_fully_dismissed must be a number.",
            unit_id=unit_id,
        )
    probability = float(value)
    if not 0 <= probability <= 1:
        return ParserIssue(
            code=ParserIssueCode.PROBABILITY_OUT_OF_RANGE,
            message="probability_fully_dismissed must be in [0, 1].",
            unit_id=unit_id,
        )
    return probability


def _optional_probability(prediction: Mapping[str, Any]) -> float | None:
    value = prediction.get("probability_fully_dismissed")
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    probability = float(value)
    if not 0 <= probability <= 1:
        return None
    return probability


def _optional_rationale(prediction: Mapping[str, Any]) -> str | None:
    for key in ("rationale", "reasoning", "explanation"):
        value = prediction.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _default_prediction(
    unit_id: str,
    *,
    probability: float,
    reason: ParserIssueCode,
) -> ParsedPrediction:
    return ParsedPrediction(
        unit_id=unit_id,
        probability_fully_dismissed=probability,
        defaulted=True,
        invalid_reason=reason,
    )


def _looks_like_refusal(raw_output: str) -> bool:
    normalized = raw_output.strip().lower()
    if normalized.startswith("{") or normalized.startswith("["):
        return False
    refusal_markers = (
        "i cannot",
        "i can't",
        "cannot provide",
        "can't provide",
        "unable to provide",
        "i am unable",
    )
    return any(marker in normalized for marker in refusal_markers)


def _validate_required_unit_ids(required_unit_ids: Sequence[str]) -> tuple[str, ...]:
    units = tuple(required_unit_ids)
    if not units:
        raise ValueError("required_unit_ids must not be empty")
    if len(units) != len(set(units)):
        raise ValueError("required_unit_ids must be unique")
    for unit_id in units:
        _require_non_empty(unit_id, "required_unit_ids")
    return units


def _sha256_prefixed(value: str) -> str:
    encoded = value.encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_probability(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be in [0, 1]")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
