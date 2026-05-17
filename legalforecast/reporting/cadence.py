"""Cycle power and cadence classification for benchmark reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

PILOT_MOTION_TARGET = 50
RAPID_MOTION_TARGET = 150
RAPID_MIN_ELAPSED_DAYS = 14
OFFICIAL_DESCRIPTIVE_MOTIONS = 100
OFFICIAL_DESCRIPTIVE_UNITS = 400
STRONG_RANKING_MIN_MOTIONS = 250
STRONG_RANKING_PREFERRED_MOTIONS = 300
PAPER_LEVEL_MOTIONS = 500


class CycleSeries(StrEnum):
    """Intended cycle cadence."""

    PILOT = "pilot"
    RAPID = "rapid"
    OFFICIAL = "official"
    ANNUAL_AGGREGATE = "annual_aggregate"


class CycleClassification(StrEnum):
    """Report label assigned to a benchmark cycle."""

    PILOT_ONLY = "pilot_only"
    RAPID_PROVISIONAL = "rapid_provisional"
    PRELIMINARY = "preliminary"
    OFFICIAL_DESCRIPTIVE = "official_descriptive"
    STRONG_RANKING = "strong_ranking"
    ANNUAL_AGGREGATE = "annual_aggregate"


class ClaimStrength(StrEnum):
    """Maximum claim strength supported by the cycle."""

    FEASIBILITY_ONLY = "feasibility_only"
    PROVISIONAL_SIGNAL = "provisional_signal"
    DESCRIPTIVE_ONLY = "descriptive_only"
    STRONG_RANKING_MINIMUM = "strong_ranking_minimum"
    STRONG_RANKING_PREFERRED = "strong_ranking_preferred"
    PAPER_LEVEL = "paper_level"


@dataclass(frozen=True, slots=True)
class CyclePowerInput:
    """Observed sample size and cadence facts for one benchmark cycle."""

    cycle_id: str
    series: CycleSeries
    clean_motion_count: int
    prediction_unit_count: int
    elapsed_days: int | None = None
    official_window_days: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_non_negative(self.clean_motion_count, "clean_motion_count")
        _require_non_negative(self.prediction_unit_count, "prediction_unit_count")
        if self.elapsed_days is not None:
            _require_non_negative(self.elapsed_days, "elapsed_days")
        if self.official_window_days is not None:
            _require_positive(self.official_window_days, "official_window_days")


@dataclass(frozen=True, slots=True)
class CyclePowerReport:
    """Machine-readable report label and power warnings."""

    cycle_id: str
    series: CycleSeries
    classification: CycleClassification
    claim_strength: ClaimStrength
    clean_motion_count: int
    prediction_unit_count: int
    meets_pilot_target: bool
    meets_rapid_target: bool
    meets_official_descriptive_threshold: bool
    meets_strong_ranking_minimum: bool
    meets_strong_ranking_preferred: bool
    meets_paper_level_threshold: bool
    warnings: tuple[str, ...] = ()

    @property
    def strong_ranking_claim_allowed(self) -> bool:
        return self.meets_strong_ranking_minimum

    def to_record(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "series": self.series.value,
            "classification": self.classification.value,
            "claim_strength": self.claim_strength.value,
            "clean_motion_count": self.clean_motion_count,
            "prediction_unit_count": self.prediction_unit_count,
            "meets_pilot_target": self.meets_pilot_target,
            "meets_rapid_target": self.meets_rapid_target,
            "meets_official_descriptive_threshold": (
                self.meets_official_descriptive_threshold
            ),
            "meets_strong_ranking_minimum": self.meets_strong_ranking_minimum,
            "meets_strong_ranking_preferred": self.meets_strong_ranking_preferred,
            "meets_paper_level_threshold": self.meets_paper_level_threshold,
            "strong_ranking_claim_allowed": self.strong_ranking_claim_allowed,
            "warnings": list(self.warnings),
        }


def classify_cycle_power(cycle: CyclePowerInput) -> CyclePowerReport:
    """Classify a cycle under the plan's sample-size/cadence thresholds."""

    meets_pilot = cycle.clean_motion_count >= PILOT_MOTION_TARGET
    meets_rapid = _meets_rapid_target(cycle)
    meets_descriptive = (
        cycle.clean_motion_count >= OFFICIAL_DESCRIPTIVE_MOTIONS
        and cycle.prediction_unit_count >= OFFICIAL_DESCRIPTIVE_UNITS
    )
    meets_strong_minimum = cycle.clean_motion_count >= STRONG_RANKING_MIN_MOTIONS
    meets_strong_preferred = (
        cycle.clean_motion_count >= STRONG_RANKING_PREFERRED_MOTIONS
    )
    meets_paper_level = cycle.clean_motion_count >= PAPER_LEVEL_MOTIONS

    classification = _classification(
        cycle,
        meets_descriptive=meets_descriptive,
        meets_strong_minimum=meets_strong_minimum,
    )
    claim_strength = _claim_strength(
        cycle,
        classification=classification,
        meets_descriptive=meets_descriptive,
        meets_strong_minimum=meets_strong_minimum,
        meets_strong_preferred=meets_strong_preferred,
        meets_paper_level=meets_paper_level,
    )
    warnings = _warnings(
        cycle,
        classification=classification,
        meets_pilot=meets_pilot,
        meets_rapid=meets_rapid,
        meets_descriptive=meets_descriptive,
        meets_strong_minimum=meets_strong_minimum,
        meets_strong_preferred=meets_strong_preferred,
    )
    return CyclePowerReport(
        cycle_id=cycle.cycle_id,
        series=cycle.series,
        classification=classification,
        claim_strength=claim_strength,
        clean_motion_count=cycle.clean_motion_count,
        prediction_unit_count=cycle.prediction_unit_count,
        meets_pilot_target=meets_pilot,
        meets_rapid_target=meets_rapid,
        meets_official_descriptive_threshold=meets_descriptive,
        meets_strong_ranking_minimum=meets_strong_minimum,
        meets_strong_ranking_preferred=meets_strong_preferred,
        meets_paper_level_threshold=meets_paper_level,
        warnings=warnings,
    )


def _meets_rapid_target(cycle: CyclePowerInput) -> bool:
    if cycle.series is not CycleSeries.RAPID:
        return False
    if cycle.clean_motion_count >= RAPID_MOTION_TARGET:
        return True
    return (
        cycle.elapsed_days is not None
        and cycle.elapsed_days >= RAPID_MIN_ELAPSED_DAYS
        and cycle.clean_motion_count >= OFFICIAL_DESCRIPTIVE_MOTIONS
    )


def _classification(
    cycle: CyclePowerInput,
    *,
    meets_descriptive: bool,
    meets_strong_minimum: bool,
) -> CycleClassification:
    if cycle.series is CycleSeries.PILOT:
        return CycleClassification.PILOT_ONLY
    if cycle.series is CycleSeries.RAPID:
        return CycleClassification.RAPID_PROVISIONAL
    if cycle.series is CycleSeries.ANNUAL_AGGREGATE:
        return CycleClassification.ANNUAL_AGGREGATE
    if meets_strong_minimum:
        return CycleClassification.STRONG_RANKING
    if meets_descriptive:
        return CycleClassification.OFFICIAL_DESCRIPTIVE
    return CycleClassification.PRELIMINARY


def _claim_strength(
    cycle: CyclePowerInput,
    *,
    classification: CycleClassification,
    meets_descriptive: bool,
    meets_strong_minimum: bool,
    meets_strong_preferred: bool,
    meets_paper_level: bool,
) -> ClaimStrength:
    if classification is CycleClassification.PILOT_ONLY:
        return ClaimStrength.FEASIBILITY_ONLY
    if classification is CycleClassification.RAPID_PROVISIONAL:
        return ClaimStrength.PROVISIONAL_SIGNAL
    if cycle.series is CycleSeries.ANNUAL_AGGREGATE and meets_paper_level:
        return ClaimStrength.PAPER_LEVEL
    if meets_strong_preferred:
        return ClaimStrength.STRONG_RANKING_PREFERRED
    if meets_strong_minimum:
        return ClaimStrength.STRONG_RANKING_MINIMUM
    if meets_descriptive:
        return ClaimStrength.DESCRIPTIVE_ONLY
    return ClaimStrength.FEASIBILITY_ONLY


def _warnings(
    cycle: CyclePowerInput,
    *,
    classification: CycleClassification,
    meets_pilot: bool,
    meets_rapid: bool,
    meets_descriptive: bool,
    meets_strong_minimum: bool,
    meets_strong_preferred: bool,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if cycle.series is CycleSeries.PILOT and not meets_pilot:
        warnings.append("pilot cycle has fewer than 50 clean motions")
    if cycle.series is CycleSeries.RAPID and not meets_rapid:
        warnings.append(
            "rapid provisional cycle has not reached 150 clean motions or "
            "the 14-day minimum with at least 100 clean motions"
        )
    if cycle.series is CycleSeries.OFFICIAL and not meets_descriptive:
        warnings.append(
            "official cycle is preliminary because it has fewer than "
            "100 clean motions or fewer than 400 prediction units"
        )
    if (
        classification
        in {
            CycleClassification.OFFICIAL_DESCRIPTIVE,
            CycleClassification.PRELIMINARY,
            CycleClassification.RAPID_PROVISIONAL,
        }
        and not meets_strong_minimum
    ):
        warnings.append(
            "motion-level power is too thin for strong ranking claims; "
            "use descriptive or provisional language"
        )
    if meets_strong_minimum and not meets_strong_preferred:
        warnings.append(
            "strong-ranking minimum is met, but the preferred target is "
            "300-500 clean motions"
        )
    return tuple(warnings)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
