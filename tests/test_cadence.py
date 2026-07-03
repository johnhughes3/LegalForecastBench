from __future__ import annotations

import json

import pytest
from legalforecast.reporting.cadence import (
    ClaimStrength,
    CycleClassification,
    CyclePowerInput,
    CycleSeries,
    classify_cycle_power,
)


def test_pilot_cycle_is_labeled_feasibility_only() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="pilot-1",
            series=CycleSeries.PILOT,
            clean_motion_count=50,
            prediction_unit_count=180,
        )
    )

    assert report.classification is CycleClassification.PILOT_ONLY
    assert report.claim_strength is ClaimStrength.FEASIBILITY_ONLY
    assert report.meets_pilot_target is True
    assert report.strong_ranking_claim_allowed is False
    json.dumps(report.to_record())


def test_rapid_cycle_is_provisional_even_when_motion_target_is_met() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="rapid-model-release",
            series=CycleSeries.RAPID,
            clean_motion_count=150,
            prediction_unit_count=620,
            elapsed_days=9,
        )
    )

    assert report.classification is CycleClassification.RAPID_PROVISIONAL
    assert report.claim_strength is ClaimStrength.PROVISIONAL_SIGNAL
    assert report.meets_rapid_target is True
    assert any("provisional" in warning for warning in report.warnings)


def test_rapid_cycle_can_finish_after_fourteen_days_with_descriptive_size() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="rapid-14-day",
            series=CycleSeries.RAPID,
            clean_motion_count=110,
            prediction_unit_count=430,
            elapsed_days=14,
        )
    )

    assert report.classification is CycleClassification.RAPID_PROVISIONAL
    assert report.meets_rapid_target is True


def test_official_cycle_needs_motion_and_unit_thresholds() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="official-descriptive",
            series=CycleSeries.OFFICIAL,
            clean_motion_count=100,
            prediction_unit_count=400,
            official_window_days=28,
        )
    )

    assert report.classification is CycleClassification.OFFICIAL_DESCRIPTIVE
    assert report.claim_strength is ClaimStrength.DESCRIPTIVE_ONLY
    assert report.meets_official_descriptive_threshold is True
    assert report.strong_ranking_claim_allowed is False
    assert any("too thin for strong ranking" in warning for warning in report.warnings)
    record = report.to_record()
    assert record["mde_analysis"]["method"] == "paired_normal_approximation"
    assert record["mde_analysis"]["required_motion_count_for_target_mde"] == 197
    assert record["mde_analysis"]["mde"] == pytest.approx(0.014007926)


def test_official_cycle_below_descriptive_threshold_is_preliminary() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="official-thin",
            series=CycleSeries.OFFICIAL,
            clean_motion_count=99,
            prediction_unit_count=700,
            official_window_days=28,
        )
    )

    assert report.classification is CycleClassification.PRELIMINARY
    assert report.meets_official_descriptive_threshold is False
    assert any("preliminary" in warning for warning in report.warnings)


def test_strong_ranking_minimum_warns_when_below_preferred_range() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="official-strong-minimum",
            series=CycleSeries.OFFICIAL,
            clean_motion_count=250,
            prediction_unit_count=1200,
            official_window_days=28,
        )
    )

    assert report.classification is CycleClassification.STRONG_RANKING
    assert report.claim_strength is ClaimStrength.STRONG_RANKING_MINIMUM
    assert report.strong_ranking_claim_allowed is True
    assert any("300-500" in warning for warning in report.warnings)


def test_mde_analysis_can_raise_strong_ranking_motion_requirement() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="official-high-variance",
            series=CycleSeries.OFFICIAL,
            clean_motion_count=250,
            prediction_unit_count=1200,
            official_window_days=28,
            paired_delta_sd=0.08,
        )
    )

    assert report.classification is CycleClassification.OFFICIAL_DESCRIPTIVE
    assert report.claim_strength is ClaimStrength.DESCRIPTIVE_ONLY
    assert report.strong_ranking_claim_allowed is False
    assert (
        report.mde_analysis.required_motion_count_for_target_mde
        > report.clean_motion_count
    )


def test_preferred_strong_ranking_cycle_has_no_thin_power_warning() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="official-strong-preferred",
            series=CycleSeries.OFFICIAL,
            clean_motion_count=325,
            prediction_unit_count=1500,
            official_window_days=28,
        )
    )

    assert report.classification is CycleClassification.STRONG_RANKING
    assert report.claim_strength is ClaimStrength.STRONG_RANKING_PREFERRED
    assert report.meets_strong_ranking_preferred is True
    assert not report.warnings


def test_annual_aggregate_at_five_hundred_motions_supports_paper_level_claims() -> None:
    report = classify_cycle_power(
        CyclePowerInput(
            cycle_id="annual-2026",
            series=CycleSeries.ANNUAL_AGGREGATE,
            clean_motion_count=520,
            prediction_unit_count=2500,
        )
    )

    assert report.classification is CycleClassification.ANNUAL_AGGREGATE
    assert report.claim_strength is ClaimStrength.PAPER_LEVEL
    assert report.meets_paper_level_threshold is True
