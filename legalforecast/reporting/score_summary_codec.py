"""Strict record decoding for benchmark score summaries."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, cast

from legalforecast.evals.output_parser import ParserIssueCode, ParserStatus
from legalforecast.evals.scorers import (
    CalibrationBin,
    DominanceSensitivityReport,
    RobustnessDimension,
    ScoreSummary,
    UnitScore,
)

JsonRecord = dict[str, Any]


def score_summary_from_record(record: Mapping[str, Any]) -> ScoreSummary:
    """Decode one strict JSON-like record into a complete score summary."""

    return ScoreSummary(
        model_id=_required_str(record, "model_id"),
        case_count=_required_int(record, "case_count"),
        unit_count=_required_int(record, "unit_count"),
        micro_brier=_required_float(record, "micro_brier"),
        macro_brier=_required_float(record, "macro_brier"),
        brier_skill_score=_required_float(record, "brier_skill_score"),
        log_loss=_required_float(record, "log_loss"),
        ece=_required_float(record, "ece"),
        capped_case_micro_brier=_required_float(record, "capped_case_micro_brier"),
        related_family_capped_micro_brier=_required_float(
            record,
            "related_family_capped_micro_brier",
        ),
        mdl_family_capped_micro_brier=_required_float(
            record,
            "mdl_family_capped_micro_brier",
        ),
        case_unit_cap=_required_int(record, "case_unit_cap"),
        family_unit_cap=_required_int(record, "family_unit_cap"),
        dominance_threshold=_required_float(record, "dominance_threshold"),
        dominance_sensitivity_reports=tuple(
            _dominance_sensitivity_report(item)
            for item in _required_record_sequence(
                record,
                "dominance_sensitivity_reports",
            )
        ),
        invalid_output_rate=_required_float(record, "invalid_output_rate"),
        refusal_rate=_required_float(record, "refusal_rate"),
        defaulted_prediction_rate=_required_float(
            record,
            "defaulted_prediction_rate",
        ),
        base_rate=_required_float(record, "base_rate"),
        base_rate_brier=_required_float(record, "base_rate_brier"),
        ece_bins=tuple(
            _calibration_bin(item)
            for item in _required_record_sequence(record, "ece_bins")
        ),
        unit_scores=tuple(
            _unit_score(item)
            for item in _required_record_sequence(record, "unit_scores")
        ),
    )


def _dominance_sensitivity_report(
    record: Mapping[str, Any],
) -> DominanceSensitivityReport:
    return DominanceSensitivityReport(
        dimension=RobustnessDimension(_required_str(record, "dimension")),
        bucket=_required_str(record, "bucket"),
        unit_count=_required_int(record, "unit_count"),
        unit_share=_required_float(record, "unit_share"),
        bucket_brier=_required_float(record, "bucket_brier"),
        excluded_micro_brier=_optional_number(record, "excluded_micro_brier"),
        capped_micro_brier=_required_float(record, "capped_micro_brier"),
        unit_cap=_required_int(record, "unit_cap"),
        recommended_action=_required_str(record, "recommended_action"),
    )


def _calibration_bin(record: Mapping[str, Any]) -> CalibrationBin:
    return CalibrationBin(
        bin_index=_required_int(record, "bin_index"),
        lower=_required_float(record, "lower"),
        upper=_required_float(record, "upper"),
        unit_count=_required_int(record, "unit_count"),
        mean_probability=_optional_number(record, "mean_probability"),
        observed_rate=_optional_number(record, "observed_rate"),
        absolute_calibration_error=_optional_number(
            record,
            "absolute_calibration_error",
        ),
    )


def _unit_score(record: Mapping[str, Any]) -> UnitScore:
    invalid_reason = _optional_str(record, "invalid_reason")
    return UnitScore(
        case_id=_required_str(record, "case_id"),
        candidate_id=_optional_str(record, "candidate_id"),
        related_family_id=_optional_str(record, "related_family_id"),
        mdl_family_id=_optional_str(record, "mdl_family_id"),
        model_id=_required_str(record, "model_id"),
        unit_id=_required_str(record, "unit_id"),
        probability_fully_dismissed=_required_float(
            record,
            "probability_fully_dismissed",
        ),
        outcome=_required_int(record, "outcome"),
        brier=_required_float(record, "brier"),
        log_loss=_required_float(record, "log_loss"),
        parser_status=ParserStatus(_required_str(record, "parser_status")),
        raw_output_sha256=_required_str(record, "raw_output_sha256"),
        defaulted_prediction=_required_bool(record, "defaulted_prediction"),
        invalid_reason=(
            ParserIssueCode(invalid_reason) if invalid_reason is not None else None
        ),
        label_confidence=_optional_number(record, "label_confidence"),
    )


def _required_record_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[JsonRecord, ...]:
    value = _required(record, field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    return tuple(
        _mapping(item, f"{field_name} item") for item in cast(Sequence[object], value)
    )


def _mapping(value: object, field_name: str) -> JsonRecord:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return dict(cast(Mapping[str, Any], value))


def _required(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in record:
        raise ValueError(f"{field_name} is required")
    return record[field_name]


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _required(record, field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = _required(record, field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _required_float(record: Mapping[str, Any], field_name: str) -> float:
    value = _required(record, field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return _finite_float(float(value), field_name)


def _optional_number(record: Mapping[str, Any], field_name: str) -> float | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return _finite_float(float(value), field_name)


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = _required(record, field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _finite_float(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value
