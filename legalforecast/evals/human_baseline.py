"""Human expertise ladder packets and scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.evals.inspect_task import InspectTaskSample
from legalforecast.evals.scorers import brier_score
from legalforecast.labeling.label_outcomes import OutcomeLabel
from legalforecast.labeling.lawyer_review import ReviewerExpertise

DEFAULT_HUMAN_TIME_LIMIT_MINUTES = 45


class CaseComplexityStratum(StrEnum):
    """Complexity buckets used for human-baseline reporting."""

    SIMPLE = "simple"
    MULTI_CLAIM = "multi_claim"
    MULTI_DEFENDANT = "multi_defendant"
    MIXED_DOCTRINE = "mixed_doctrine"
    COMPLEX = "complex"


@dataclass(frozen=True, slots=True)
class HumanForecastPacket:
    """Packet assignment shown to a human reviewer for forecasting."""

    packet_id: str
    candidate_id: str
    case_id: str
    unit_ids: tuple[str, ...]
    prompt_sha256: str
    time_limit_minutes: int = DEFAULT_HUMAN_TIME_LIMIT_MINUTES
    external_research_allowed: bool = False
    instructions: str = (
        "Use the supplied pre-decision packet only. For each prediction unit, "
        "enter a calibrated probability from 0 to 1 that the claim will be "
        "fully dismissed as to the defendant/group. Record confidence, minutes "
        "spent, and notes. Do not perform external research unless this packet "
        "explicitly allows it."
    )

    def __post_init__(self) -> None:
        _require_non_empty(self.packet_id, "packet_id")
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.prompt_sha256, "prompt_sha256")
        if not self.unit_ids:
            raise ValueError("unit_ids must not be empty")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("unit_ids must be unique")
        if self.time_limit_minutes <= 0:
            raise ValueError("time_limit_minutes must be positive")
        _require_non_empty(self.instructions, "instructions")

    @classmethod
    def from_inspect_sample(
        cls,
        sample: InspectTaskSample,
        *,
        time_limit_minutes: int = DEFAULT_HUMAN_TIME_LIMIT_MINUTES,
        external_research_allowed: bool = False,
    ) -> HumanForecastPacket:
        """Build a human packet from the same frozen sample used for models."""

        record = sample.to_record()
        prompt_sha256 = record["prompt_sha256"]
        if not isinstance(prompt_sha256, str):
            raise TypeError("sample prompt_sha256 must be a string")
        return cls(
            packet_id=sample.sample_id,
            candidate_id=sample.packet.candidate_id,
            case_id=sample.packet.case_id,
            unit_ids=sample.required_unit_ids,
            prompt_sha256=prompt_sha256,
            time_limit_minutes=time_limit_minutes,
            external_research_allowed=external_research_allowed,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "unit_ids": list(self.unit_ids),
            "prompt_sha256": self.prompt_sha256,
            "time_limit_minutes": self.time_limit_minutes,
            "external_research_allowed": self.external_research_allowed,
            "instructions": self.instructions,
        }


@dataclass(frozen=True, slots=True)
class HumanForecast:
    """One human probability forecast for one prediction unit."""

    packet_id: str
    case_id: str
    unit_id: str
    reviewer_id: str
    reviewer_expertise: ReviewerExpertise
    probability_fully_dismissed: float
    confidence: float
    minutes_spent: float
    complexity_stratum: CaseComplexityStratum
    notes: str
    external_research_used: bool = False

    def __post_init__(self) -> None:
        for field_name, value in (
            ("packet_id", self.packet_id),
            ("case_id", self.case_id),
            ("unit_id", self.unit_id),
            ("reviewer_id", self.reviewer_id),
            ("notes", self.notes),
        ):
            _require_non_empty(value, field_name)
        _require_probability(
            self.probability_fully_dismissed,
            "probability_fully_dismissed",
        )
        _require_probability(self.confidence, "confidence")
        if self.minutes_spent <= 0:
            raise ValueError("minutes_spent must be positive")

    def to_record(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "case_id": self.case_id,
            "unit_id": self.unit_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_expertise": self.reviewer_expertise.value,
            "probability_fully_dismissed": self.probability_fully_dismissed,
            "confidence": self.confidence,
            "minutes_spent": self.minutes_spent,
            "complexity_stratum": self.complexity_stratum.value,
            "notes": self.notes,
            "external_research_used": self.external_research_used,
        }


@dataclass(frozen=True, slots=True)
class HumanUnitScore:
    """Scored human forecast row."""

    packet_id: str
    case_id: str
    unit_id: str
    reviewer_id: str
    reviewer_expertise: ReviewerExpertise
    complexity_stratum: CaseComplexityStratum
    probability_fully_dismissed: float
    outcome: int
    brier: float
    confidence: float
    minutes_spent: float
    model_probability_fully_dismissed: float | None = None
    absolute_model_delta: float | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "case_id": self.case_id,
            "unit_id": self.unit_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_expertise": self.reviewer_expertise.value,
            "complexity_stratum": self.complexity_stratum.value,
            "probability_fully_dismissed": self.probability_fully_dismissed,
            "outcome": self.outcome,
            "brier": self.brier,
            "confidence": self.confidence,
            "minutes_spent": self.minutes_spent,
            "model_probability_fully_dismissed": (
                self.model_probability_fully_dismissed
            ),
            "absolute_model_delta": self.absolute_model_delta,
        }


@dataclass(frozen=True, slots=True)
class HumanBaselineSlice:
    """Aggregate human-baseline metrics for a reporting slice."""

    slice_id: str
    unit_count: int
    reviewer_count: int
    mean_brier: float
    mean_minutes_spent: float
    mean_confidence: float
    mean_absolute_model_delta: float | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "slice_id": self.slice_id,
            "unit_count": self.unit_count,
            "reviewer_count": self.reviewer_count,
            "mean_brier": self.mean_brier,
            "mean_minutes_spent": self.mean_minutes_spent,
            "mean_confidence": self.mean_confidence,
            "mean_absolute_model_delta": self.mean_absolute_model_delta,
        }


@dataclass(frozen=True, slots=True)
class HumanBaselineSummary:
    """Human expertise ladder scorecard."""

    overall: HumanBaselineSlice
    by_expertise: tuple[HumanBaselineSlice, ...]
    by_complexity: tuple[HumanBaselineSlice, ...]
    unit_scores: tuple[HumanUnitScore, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "overall": self.overall.to_record(),
            "by_expertise": [slice_.to_record() for slice_ in self.by_expertise],
            "by_complexity": [slice_.to_record() for slice_ in self.by_complexity],
            "unit_scores": [score.to_record() for score in self.unit_scores],
        }


def score_human_baseline(
    forecasts: Sequence[HumanForecast],
    labels_by_unit_id: Mapping[str, OutcomeLabel],
    *,
    model_probabilities_by_unit_id: Mapping[str, float] | None = None,
    external_research_allowed: bool = False,
) -> HumanBaselineSummary:
    """Score human forecasts against locked labels and optional model outputs."""

    if not forecasts:
        raise ValueError("forecasts must not be empty")
    _validate_unique_forecasts(forecasts)
    model_probabilities = dict(model_probabilities_by_unit_id or {})
    for probability in model_probabilities.values():
        _require_probability(probability, "model_probability")

    unit_scores = tuple(
        _score_forecast(
            forecast,
            labels_by_unit_id,
            model_probabilities,
            external_research_allowed=external_research_allowed,
        )
        for forecast in forecasts
    )
    return HumanBaselineSummary(
        overall=_slice("overall", unit_scores),
        by_expertise=tuple(
            _slice(expertise.value, _scores_for_expertise(unit_scores, expertise))
            for expertise in ReviewerExpertise
            if _scores_for_expertise(unit_scores, expertise)
        ),
        by_complexity=tuple(
            _slice(stratum.value, _scores_for_complexity(unit_scores, stratum))
            for stratum in CaseComplexityStratum
            if _scores_for_complexity(unit_scores, stratum)
        ),
        unit_scores=unit_scores,
    )


def _score_forecast(
    forecast: HumanForecast,
    labels_by_unit_id: Mapping[str, OutcomeLabel],
    model_probabilities: Mapping[str, float],
    *,
    external_research_allowed: bool,
) -> HumanUnitScore:
    if forecast.external_research_used and not external_research_allowed:
        raise ValueError("external research is not allowed for this human packet")
    label = labels_by_unit_id.get(forecast.unit_id)
    if label is None:
        raise ValueError(f"missing outcome label for unit: {forecast.unit_id}")
    outcome = label.primary_outcome
    if outcome is None:
        raise ValueError(f"ambiguous label cannot be scored: {forecast.unit_id}")
    model_probability = model_probabilities.get(forecast.unit_id)
    absolute_model_delta = (
        abs(forecast.probability_fully_dismissed - model_probability)
        if model_probability is not None
        else None
    )
    return HumanUnitScore(
        packet_id=forecast.packet_id,
        case_id=forecast.case_id,
        unit_id=forecast.unit_id,
        reviewer_id=forecast.reviewer_id,
        reviewer_expertise=forecast.reviewer_expertise,
        complexity_stratum=forecast.complexity_stratum,
        probability_fully_dismissed=forecast.probability_fully_dismissed,
        outcome=outcome,
        brier=brier_score(forecast.probability_fully_dismissed, outcome),
        confidence=forecast.confidence,
        minutes_spent=forecast.minutes_spent,
        model_probability_fully_dismissed=model_probability,
        absolute_model_delta=absolute_model_delta,
    )


def _slice(slice_id: str, scores: tuple[HumanUnitScore, ...]) -> HumanBaselineSlice:
    if not scores:
        raise ValueError("scores must not be empty")
    deltas = tuple(
        score.absolute_model_delta
        for score in scores
        if score.absolute_model_delta is not None
    )
    return HumanBaselineSlice(
        slice_id=slice_id,
        unit_count=len(scores),
        reviewer_count=len({score.reviewer_id for score in scores}),
        mean_brier=_mean(tuple(score.brier for score in scores)),
        mean_minutes_spent=_mean(tuple(score.minutes_spent for score in scores)),
        mean_confidence=_mean(tuple(score.confidence for score in scores)),
        mean_absolute_model_delta=_mean(deltas) if deltas else None,
    )


def _scores_for_expertise(
    scores: tuple[HumanUnitScore, ...],
    expertise: ReviewerExpertise,
) -> tuple[HumanUnitScore, ...]:
    return tuple(score for score in scores if score.reviewer_expertise is expertise)


def _scores_for_complexity(
    scores: tuple[HumanUnitScore, ...],
    stratum: CaseComplexityStratum,
) -> tuple[HumanUnitScore, ...]:
    return tuple(score for score in scores if score.complexity_stratum is stratum)


def _validate_unique_forecasts(forecasts: Sequence[HumanForecast]) -> None:
    keys = [
        (forecast.reviewer_id, forecast.case_id, forecast.unit_id)
        for forecast in forecasts
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate reviewer/case/unit human forecast")


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ValueError("cannot take mean of empty values")
    return sum(values) / len(values)


def _require_probability(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be in [0, 1]")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
