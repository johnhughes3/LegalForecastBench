"""Primary scoring metrics for LegalForecast-MTD."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParsedPrediction,
    ParserIssueCode,
    ParserStatus,
)
from legalforecast.labeling.label_outcomes import OutcomeLabel

DEFAULT_LOG_LOSS_EPSILON = 1e-15
DEFAULT_ECE_BINS = 10
DEFAULT_CASE_UNIT_CAP = 10
DEFAULT_FAMILY_UNIT_CAP = 10
DEFAULT_DOMINANCE_THRESHOLD = 0.40


class RobustnessDimension(StrEnum):
    """Robustness grouping dimensions reported with sensitivity metrics."""

    CASE = "case"
    RELATED_CASE_FAMILY = "related_case_family"
    MDL_FAMILY = "mdl_family"


@dataclass(frozen=True, slots=True)
class ScoringCase:
    """One parsed model output matched to locked labels for one motion/case."""

    case_id: str
    model_id: str
    parsed_output: ParsedModelOutput
    outcome_labels: tuple[OutcomeLabel, ...]
    candidate_id: str | None = None
    related_family_id: str | None = None
    mdl_family_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.model_id, "model_id")
        if self.candidate_id is not None:
            _require_non_empty(self.candidate_id, "candidate_id")
        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")
        if self.mdl_family_id is not None:
            _require_non_empty(self.mdl_family_id, "mdl_family_id")
        if not self.outcome_labels:
            raise ValueError("outcome_labels must not be empty")


@dataclass(frozen=True, slots=True)
class UnitScore:
    """Per-unit score and metadata row."""

    case_id: str
    model_id: str
    unit_id: str
    probability_fully_dismissed: float
    outcome: int
    brier: float
    log_loss: float
    parser_status: ParserStatus
    raw_output_sha256: str
    defaulted_prediction: bool = False
    invalid_reason: ParserIssueCode | None = None
    label_confidence: float | None = None
    candidate_id: str | None = None
    related_family_id: str | None = None
    mdl_family_id: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
            "model_id": self.model_id,
            "unit_id": self.unit_id,
            "probability_fully_dismissed": self.probability_fully_dismissed,
            "outcome": self.outcome,
            "brier": self.brier,
            "log_loss": self.log_loss,
            "parser_status": self.parser_status.value,
            "raw_output_sha256": self.raw_output_sha256,
            "defaulted_prediction": self.defaulted_prediction,
            "invalid_reason": (
                self.invalid_reason.value if self.invalid_reason is not None else None
            ),
            "label_confidence": self.label_confidence,
        }


@dataclass(frozen=True, slots=True)
class DominanceSensitivityReport:
    """Exclusion and capping alternatives for a dominant case or family."""

    dimension: RobustnessDimension
    bucket: str
    unit_count: int
    unit_share: float
    bucket_brier: float
    excluded_micro_brier: float | None
    capped_micro_brier: float
    unit_cap: int
    recommended_action: str = "report_excluded_and_capped_sensitivity"

    def __post_init__(self) -> None:
        _require_non_empty(self.bucket, "bucket")
        _require_positive_int(self.unit_count, "unit_count")
        _require_share(self.unit_share, "unit_share")
        _require_non_negative_float(self.bucket_brier, "bucket_brier")
        if self.excluded_micro_brier is not None:
            _require_non_negative_float(
                self.excluded_micro_brier,
                "excluded_micro_brier",
            )
        _require_non_negative_float(self.capped_micro_brier, "capped_micro_brier")
        _require_positive_int(self.unit_cap, "unit_cap")
        _require_non_empty(self.recommended_action, "recommended_action")

    def to_record(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "bucket": self.bucket,
            "unit_count": self.unit_count,
            "unit_share": self.unit_share,
            "bucket_brier": self.bucket_brier,
            "excluded_micro_brier": self.excluded_micro_brier,
            "capped_micro_brier": self.capped_micro_brier,
            "unit_cap": self.unit_cap,
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """Fixed-width calibration bin used for ECE reporting."""

    bin_index: int
    lower: float
    upper: float
    unit_count: int
    mean_probability: float | None
    observed_rate: float | None
    absolute_calibration_error: float | None

    def to_record(self) -> dict[str, Any]:
        return {
            "bin_index": self.bin_index,
            "lower": self.lower,
            "upper": self.upper,
            "unit_count": self.unit_count,
            "mean_probability": self.mean_probability,
            "observed_rate": self.observed_rate,
            "absolute_calibration_error": self.absolute_calibration_error,
        }


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    """Aggregate metrics for one model over one evaluation slice."""

    model_id: str
    case_count: int
    unit_count: int
    micro_brier: float
    macro_brier: float
    brier_skill_score: float
    log_loss: float
    ece: float
    capped_case_micro_brier: float
    related_family_capped_micro_brier: float
    mdl_family_capped_micro_brier: float
    case_unit_cap: int
    family_unit_cap: int
    dominance_threshold: float
    dominance_sensitivity_reports: tuple[DominanceSensitivityReport, ...]
    invalid_output_rate: float
    refusal_rate: float
    defaulted_prediction_rate: float
    base_rate: float
    base_rate_brier: float
    ece_bins: tuple[CalibrationBin, ...]
    unit_scores: tuple[UnitScore, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "case_count": self.case_count,
            "unit_count": self.unit_count,
            "micro_brier": self.micro_brier,
            "macro_brier": self.macro_brier,
            "brier_skill_score": self.brier_skill_score,
            "log_loss": self.log_loss,
            "ece": self.ece,
            "capped_case_micro_brier": self.capped_case_micro_brier,
            "related_family_capped_micro_brier": (
                self.related_family_capped_micro_brier
            ),
            "mdl_family_capped_micro_brier": self.mdl_family_capped_micro_brier,
            "case_unit_cap": self.case_unit_cap,
            "family_unit_cap": self.family_unit_cap,
            "dominance_threshold": self.dominance_threshold,
            "dominance_sensitivity_reports": [
                report.to_record() for report in self.dominance_sensitivity_reports
            ],
            "invalid_output_rate": self.invalid_output_rate,
            "refusal_rate": self.refusal_rate,
            "defaulted_prediction_rate": self.defaulted_prediction_rate,
            "base_rate": self.base_rate,
            "base_rate_brier": self.base_rate_brier,
            "ece_bins": [
                calibration_bin.to_record() for calibration_bin in self.ece_bins
            ],
            "unit_scores": [unit_score.to_record() for unit_score in self.unit_scores],
        }


def score_cases(
    cases: tuple[ScoringCase, ...],
    *,
    base_rate: float,
    log_loss_epsilon: float = DEFAULT_LOG_LOSS_EPSILON,
    ece_bin_count: int = DEFAULT_ECE_BINS,
    case_unit_cap: int = DEFAULT_CASE_UNIT_CAP,
    family_unit_cap: int = DEFAULT_FAMILY_UNIT_CAP,
    dominance_threshold: float = DEFAULT_DOMINANCE_THRESHOLD,
) -> ScoreSummary:
    """Score parsed model outputs against locked binary outcome labels."""

    if not cases:
        raise ValueError("cases must not be empty")
    _require_probability(base_rate, "base_rate")
    _require_log_loss_epsilon(log_loss_epsilon)
    if ece_bin_count <= 0:
        raise ValueError("ece_bin_count must be positive")
    _require_positive_int(case_unit_cap, "case_unit_cap")
    _require_positive_int(family_unit_cap, "family_unit_cap")
    _require_threshold(dominance_threshold)

    model_ids = {case.model_id for case in cases}
    if len(model_ids) != 1:
        raise ValueError("score_cases expects one model_id per summary")
    model_id = next(iter(model_ids))

    unit_scores: list[UnitScore] = []
    case_briers: list[float] = []
    invalid_case_count = 0
    refusal_case_count = 0
    for case in cases:
        labels = _labels_by_unit_id(case.outcome_labels)
        case_unit_scores = tuple(
            _score_unit(
                case=case,
                prediction=case.parsed_output.prediction_for(unit_id),
                label=labels[unit_id],
                log_loss_epsilon=log_loss_epsilon,
            )
            for unit_id in case.parsed_output.required_unit_ids
        )
        if not case_unit_scores:
            raise ValueError(f"case has no scorable units: {case.case_id}")
        unit_scores.extend(case_unit_scores)
        case_briers.append(_mean(score.brier for score in case_unit_scores))
        if case.parsed_output.invalid_output:
            invalid_case_count += 1
        if case.parsed_output.status is ParserStatus.REFUSAL:
            refusal_case_count += 1

    base_rate_brier = _mean(
        (base_rate - unit_score.outcome) ** 2 for unit_score in unit_scores
    )
    micro_brier = _mean(unit_score.brier for unit_score in unit_scores)
    ece_result = _ece(unit_scores, ece_bin_count)
    capped_case_micro_brier = _capped_group_micro_brier(
        unit_scores,
        _case_group_key,
        unit_cap=case_unit_cap,
    )
    related_family_capped_micro_brier = _capped_group_micro_brier(
        unit_scores,
        _related_family_capping_group_key,
        unit_cap=family_unit_cap,
    )
    mdl_family_capped_micro_brier = _capped_group_micro_brier(
        unit_scores,
        _mdl_family_capping_group_key,
        unit_cap=family_unit_cap,
    )
    return ScoreSummary(
        model_id=model_id,
        case_count=len(cases),
        unit_count=len(unit_scores),
        micro_brier=micro_brier,
        macro_brier=_mean(case_briers),
        brier_skill_score=_brier_skill_score(micro_brier, base_rate_brier),
        log_loss=_mean(unit_score.log_loss for unit_score in unit_scores),
        ece=ece_result.ece,
        capped_case_micro_brier=capped_case_micro_brier,
        related_family_capped_micro_brier=related_family_capped_micro_brier,
        mdl_family_capped_micro_brier=mdl_family_capped_micro_brier,
        case_unit_cap=case_unit_cap,
        family_unit_cap=family_unit_cap,
        dominance_threshold=dominance_threshold,
        dominance_sensitivity_reports=_dominance_sensitivity_reports(
            unit_scores,
            dominance_threshold=dominance_threshold,
            capped_case_micro_brier=capped_case_micro_brier,
            related_family_capped_micro_brier=related_family_capped_micro_brier,
            mdl_family_capped_micro_brier=mdl_family_capped_micro_brier,
            case_unit_cap=case_unit_cap,
            family_unit_cap=family_unit_cap,
        ),
        invalid_output_rate=invalid_case_count / len(cases),
        refusal_rate=refusal_case_count / len(cases),
        defaulted_prediction_rate=(
            sum(1 for unit_score in unit_scores if unit_score.defaulted_prediction)
            / len(unit_scores)
        ),
        base_rate=base_rate,
        base_rate_brier=base_rate_brier,
        ece_bins=ece_result.bins,
        unit_scores=tuple(unit_scores),
    )


def brier_score(probability: float, outcome: int) -> float:
    """Return the binary Brier score for one unit."""

    _require_probability(probability, "probability")
    _require_binary_outcome(outcome)
    return (probability - outcome) ** 2


def binary_log_loss(
    probability: float,
    outcome: int,
    *,
    epsilon: float = DEFAULT_LOG_LOSS_EPSILON,
) -> float:
    """Return clipped binary log loss for one unit."""

    _require_probability(probability, "probability")
    _require_binary_outcome(outcome)
    _require_log_loss_epsilon(epsilon)
    if outcome == 1:
        positive_probability = min(max(probability, epsilon), 1 - epsilon)
        return -math.log(positive_probability)
    negative_probability = min(max(1 - probability, epsilon), 1 - epsilon)
    return -math.log(negative_probability)


@dataclass(frozen=True, slots=True)
class EceResult:
    ece: float
    bins: tuple[CalibrationBin, ...]


def _score_unit(
    *,
    case: ScoringCase,
    prediction: ParsedPrediction,
    label: OutcomeLabel,
    log_loss_epsilon: float,
) -> UnitScore:
    outcome = label.primary_outcome
    if outcome is None:
        raise ValueError(f"ambiguous label cannot be scored: {label.unit_id}")
    probability = prediction.probability_fully_dismissed
    return UnitScore(
        case_id=case.case_id,
        candidate_id=case.candidate_id,
        related_family_id=case.related_family_id,
        mdl_family_id=case.mdl_family_id,
        model_id=case.model_id,
        unit_id=prediction.unit_id,
        probability_fully_dismissed=probability,
        outcome=outcome,
        brier=brier_score(probability, outcome),
        log_loss=binary_log_loss(
            probability,
            outcome,
            epsilon=log_loss_epsilon,
        ),
        parser_status=case.parsed_output.status,
        raw_output_sha256=case.parsed_output.raw_output_sha256,
        defaulted_prediction=prediction.defaulted,
        invalid_reason=prediction.invalid_reason,
        label_confidence=label.label_confidence,
    )


def _labels_by_unit_id(labels: tuple[OutcomeLabel, ...]) -> dict[str, OutcomeLabel]:
    indexed: dict[str, OutcomeLabel] = {}
    for label in labels:
        if label.unit_id in indexed:
            raise ValueError(f"duplicate outcome label: {label.unit_id}")
        if label.primary_outcome is None:
            raise ValueError(f"ambiguous label cannot be scored: {label.unit_id}")
        indexed[label.unit_id] = label
    return indexed


def _ece(unit_scores: list[UnitScore], bin_count: int) -> EceResult:
    bins: list[list[UnitScore]] = [[] for _ in range(bin_count)]
    for unit_score in unit_scores:
        index = min(
            int(unit_score.probability_fully_dismissed * bin_count),
            bin_count - 1,
        )
        bins[index].append(unit_score)

    calibration_bins: list[CalibrationBin] = []
    weighted_error = 0.0
    unit_count = len(unit_scores)
    for index, bin_scores in enumerate(bins):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        if not bin_scores:
            calibration_bins.append(
                CalibrationBin(
                    bin_index=index,
                    lower=lower,
                    upper=upper,
                    unit_count=0,
                    mean_probability=None,
                    observed_rate=None,
                    absolute_calibration_error=None,
                )
            )
            continue
        mean_probability = _mean(
            score.probability_fully_dismissed for score in bin_scores
        )
        observed_rate = _mean(score.outcome for score in bin_scores)
        absolute_error = abs(mean_probability - observed_rate)
        weighted_error += (len(bin_scores) / unit_count) * absolute_error
        calibration_bins.append(
            CalibrationBin(
                bin_index=index,
                lower=lower,
                upper=upper,
                unit_count=len(bin_scores),
                mean_probability=mean_probability,
                observed_rate=observed_rate,
                absolute_calibration_error=absolute_error,
            )
        )
    return EceResult(ece=weighted_error, bins=tuple(calibration_bins))


_GroupKey = tuple[RobustnessDimension, str]
_GroupKeyFn = Callable[[UnitScore], _GroupKey | None]


def _capped_group_micro_brier(
    unit_scores: Iterable[UnitScore],
    key_fn: _GroupKeyFn,
    *,
    unit_cap: int,
) -> float:
    """Average group mean Brier scores after capping each group by unit count."""

    groups = _groups_by(unit_scores, key_fn)
    if not groups:
        raise ValueError("cannot compute capped micro-Brier without groups")
    weighted_sum = 0.0
    effective_unit_count = 0
    for scores in groups.values():
        effective_weight = min(len(scores), unit_cap)
        weighted_sum += _mean(score.brier for score in scores) * effective_weight
        effective_unit_count += effective_weight
    return weighted_sum / effective_unit_count


def _dominance_sensitivity_reports(
    unit_scores: Iterable[UnitScore],
    *,
    dominance_threshold: float,
    capped_case_micro_brier: float,
    related_family_capped_micro_brier: float,
    mdl_family_capped_micro_brier: float,
    case_unit_cap: int,
    family_unit_cap: int,
) -> tuple[DominanceSensitivityReport, ...]:
    unit_score_tuple = tuple(unit_scores)
    dimension_configs = (
        (
            _case_group_key,
            case_unit_cap,
            capped_case_micro_brier,
        ),
        (
            _related_family_dominance_group_key,
            family_unit_cap,
            related_family_capped_micro_brier,
        ),
        (
            _mdl_family_dominance_group_key,
            family_unit_cap,
            mdl_family_capped_micro_brier,
        ),
    )

    reports: list[DominanceSensitivityReport] = []
    total_unit_count = len(unit_score_tuple)
    for key_fn, unit_cap, capped_micro_brier in dimension_configs:
        for (dimension, bucket), scores in sorted(
            _groups_by(unit_score_tuple, key_fn).items()
        ):
            unit_count = len(scores)
            unit_share = unit_count / total_unit_count
            if unit_share <= dominance_threshold:
                continue
            excluded_scores = tuple(
                score
                for score in unit_score_tuple
                if key_fn(score) != (dimension, bucket)
            )
            reports.append(
                DominanceSensitivityReport(
                    dimension=dimension,
                    bucket=bucket,
                    unit_count=unit_count,
                    unit_share=unit_share,
                    bucket_brier=_mean(score.brier for score in scores),
                    excluded_micro_brier=(
                        _mean(score.brier for score in excluded_scores)
                        if excluded_scores
                        else None
                    ),
                    capped_micro_brier=capped_micro_brier,
                    unit_cap=unit_cap,
                )
            )
    return tuple(reports)


def _groups_by(
    unit_scores: Iterable[UnitScore],
    key_fn: _GroupKeyFn,
) -> dict[_GroupKey, list[UnitScore]]:
    groups: dict[_GroupKey, list[UnitScore]] = {}
    for unit_score in unit_scores:
        key = key_fn(unit_score)
        if key is None:
            continue
        groups.setdefault(key, []).append(unit_score)
    return groups


def _case_group_key(unit_score: UnitScore) -> _GroupKey:
    return (RobustnessDimension.CASE, unit_score.case_id)


def _related_family_capping_group_key(unit_score: UnitScore) -> _GroupKey:
    if unit_score.related_family_id is None:
        return _case_group_key(unit_score)
    return (RobustnessDimension.RELATED_CASE_FAMILY, unit_score.related_family_id)


def _related_family_dominance_group_key(unit_score: UnitScore) -> _GroupKey | None:
    if unit_score.related_family_id is None:
        return None
    return (RobustnessDimension.RELATED_CASE_FAMILY, unit_score.related_family_id)


def _mdl_family_capping_group_key(unit_score: UnitScore) -> _GroupKey:
    if unit_score.mdl_family_id is None:
        return _case_group_key(unit_score)
    return (RobustnessDimension.MDL_FAMILY, unit_score.mdl_family_id)


def _mdl_family_dominance_group_key(unit_score: UnitScore) -> _GroupKey | None:
    if unit_score.mdl_family_id is None:
        return None
    return (RobustnessDimension.MDL_FAMILY, unit_score.mdl_family_id)


def _brier_skill_score(micro_brier: float, base_rate_brier: float) -> float:
    if base_rate_brier == 0:
        # Skill is undefined when the base-rate benchmark has no error. Keep the
        # artifact JSON portable rather than emitting -Infinity.
        return 0.0
    return 1 - (micro_brier / base_rate_brier)


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    if not materialized:
        raise ValueError("cannot take mean of empty values")
    return sum(materialized) / len(materialized)


def _require_probability(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be in [0, 1]")


def _require_binary_outcome(value: int) -> None:
    if value not in {0, 1}:
        raise ValueError("outcome must be 0 or 1")


def _require_log_loss_epsilon(value: float) -> None:
    if not 0 < value < 0.5:
        raise ValueError("log_loss_epsilon must be between 0 and 0.5")


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_non_negative_float(value: float, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_share(value: float, field_name: str) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")


def _require_threshold(value: float) -> None:
    if value <= 0 or value >= 1:
        raise ValueError("dominance_threshold must be greater than 0 and less than 1")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
