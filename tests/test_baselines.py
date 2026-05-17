from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from legalforecast.evals.baselines import (
    BaselineId,
    BaselineTrainingExample,
    BaselineUnitFeatures,
    fit_baseline_suite,
    required_llm_run_labels,
)


def test_global_and_court_nos_motion_baselines_emit_calibration_artifacts() -> None:
    suite = _suite()
    features = _features(
        unit_id="bench-1",
        case_id="case-bench",
        judge_id="judge-below-threshold",
    )

    predictions = suite.predict(features)
    global_prediction = predictions.prediction_for(BaselineId.GLOBAL_BASE_RATE)
    court_prediction = predictions.prediction_for(BaselineId.COURT_NOS_MOTION_BASE_RATE)

    assert global_prediction.probability_fully_dismissed == pytest.approx(0.56)
    assert court_prediction.probability_fully_dismissed == pytest.approx(23 / 40)
    assert court_prediction.fallback_level == "court_nos_motion"
    assert court_prediction.calibration.training_unit_count == 40
    assert court_prediction.calibration.positive_unit_count == 23
    assert court_prediction.calibration.training_period_start == date(2024, 1, 1)
    assert court_prediction.calibration.training_period_end == date(2025, 12, 31)
    json.dumps(predictions.to_records())


def test_judge_history_threshold_and_fallback_share_summary() -> None:
    suite = _suite()
    judge_prior = _features(
        unit_id="judge-prior",
        case_id="case-judge",
        judge_id="judge-threshold",
    )
    court_fallback = _features(
        unit_id="court-fallback",
        case_id="case-court",
        judge_id="judge-below-threshold",
    )
    global_fallback = _features(
        unit_id="global-fallback",
        case_id="case-global",
        court="E.D. Tex.",
        district="E.D. Tex.",
        circuit="5th",
        nos_macro_category="patent",
        motion_type="12(b)(1)",
        judge_id=None,
    )

    judge_prediction = suite.predict(judge_prior).prediction_for(
        BaselineId.JUDGE_HISTORY
    )
    court_prediction = suite.predict(court_fallback).prediction_for(
        BaselineId.JUDGE_HISTORY
    )
    global_prediction = suite.predict(global_fallback).prediction_for(
        BaselineId.JUDGE_HISTORY
    )
    summary = suite.judge_history_usage_summary(
        (judge_prior, court_fallback, global_fallback)
    )

    assert judge_prediction.fallback_level == "judge_history"
    assert judge_prediction.probability_fully_dismissed == pytest.approx(0.7)
    assert court_prediction.fallback_level == "court_nos_motion"
    assert global_prediction.fallback_level == "global"
    assert summary.judge_prior_share == pytest.approx(1 / 3)
    assert summary.court_or_district_fallback_share == pytest.approx(1 / 3)
    assert summary.global_fallback_share == pytest.approx(1 / 3)


def test_metadata_only_baseline_is_deterministic_and_feature_backed() -> None:
    suite = _suite()
    features = _features(
        unit_id="metadata",
        case_id="case-metadata",
        judge_id="judge-threshold",
        represented_party_status="all_represented",
        government_party_status="no_government_party",
        claim_count=3,
        defendant_count=2,
        motion_length_tokens=12_000,
        complaint_length_tokens=24_000,
        case_age_days=240,
        docket_entry_count=42,
    )

    first = suite.predict(features).prediction_for(BaselineId.METADATA_ONLY)
    second = suite.predict(features).prediction_for(BaselineId.METADATA_ONLY)
    feature_names = {feature for feature, _bucket in first.feature_keys}

    assert first.to_record() == second.to_record()
    assert first.fallback_level == "metadata_weighted"
    assert 0 <= first.probability_fully_dismissed <= 1
    assert {"court", "district", "judge_id", "motion_type"} <= feature_names
    assert first.calibration.bucket_key == ("metadata_only",)


def test_required_llm_run_labels_are_pre_registered_baselines() -> None:
    assert required_llm_run_labels() == (
        BaselineId.NO_BRIEF_LLM,
        BaselineId.FULL_PACKET_LLM,
    )


def test_baseline_suite_validates_training_period_and_examples() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        fit_baseline_suite(
            (),
            training_period_start=date(2024, 1, 1),
            training_period_end=date(2025, 12, 31),
        )

    with pytest.raises(ValueError, match="outside declared training period"):
        fit_baseline_suite(
            (
                BaselineTrainingExample(
                    features=_features(unit_id="late", case_id="late-case"),
                    fully_dismissed=True,
                    decision_date=date(2026, 1, 1),
                ),
            ),
            training_period_start=date(2024, 1, 1),
            training_period_end=date(2025, 12, 31),
        )


def _suite():
    return fit_baseline_suite(
        _training_examples(),
        training_period_start=date(2024, 1, 1),
        training_period_end=date(2025, 12, 31),
    )


def _training_examples() -> tuple[BaselineTrainingExample, ...]:
    examples: list[BaselineTrainingExample] = []
    start = date(2024, 1, 1)
    for index in range(30):
        examples.append(
            BaselineTrainingExample(
                features=_features(
                    unit_id=f"judge-threshold-{index}",
                    case_id=f"case-threshold-{index}",
                    judge_id="judge-threshold",
                    represented_party_status="all_represented",
                    government_party_status="no_government_party",
                    claim_count=3,
                    defendant_count=2,
                ),
                fully_dismissed=index < 21,
                decision_date=start + timedelta(days=index),
            )
        )
    for index in range(10):
        examples.append(
            BaselineTrainingExample(
                features=_features(
                    unit_id=f"judge-below-{index}",
                    case_id=f"case-below-{index}",
                    judge_id="judge-below-threshold",
                ),
                fully_dismissed=index < 2,
                decision_date=start + timedelta(days=60 + index),
            )
        )
    for index in range(5):
        examples.append(
            BaselineTrainingExample(
                features=_features(
                    unit_id=f"del-securities-{index}",
                    case_id=f"case-del-{index}",
                    court="D. Del.",
                    district="D. Del.",
                    circuit="3d",
                    nos_macro_category="securities",
                ),
                fully_dismissed=index == 0,
                decision_date=start + timedelta(days=90 + index),
            )
        )
    for index in range(5):
        examples.append(
            BaselineTrainingExample(
                features=_features(
                    unit_id=f"cal-contract-{index}",
                    case_id=f"case-cal-{index}",
                    court="N.D. Cal.",
                    district="N.D. Cal.",
                    circuit="9th",
                    motion_type="12(c)",
                ),
                fully_dismissed=index < 4,
                decision_date=start + timedelta(days=120 + index),
            )
        )
    return tuple(examples)


def _features(
    *,
    unit_id: str,
    case_id: str,
    court: str = "S.D.N.Y.",
    district: str = "S.D.N.Y.",
    circuit: str = "2d",
    nos_macro_category: str = "contract",
    motion_type: str = "12(b)(6)",
    judge_id: str | None = None,
    represented_party_status: str | None = None,
    government_party_status: str | None = None,
    claim_count: int | None = None,
    defendant_count: int | None = None,
    motion_length_tokens: int | None = None,
    complaint_length_tokens: int | None = None,
    case_age_days: int | None = None,
    docket_entry_count: int | None = None,
) -> BaselineUnitFeatures:
    return BaselineUnitFeatures(
        unit_id=unit_id,
        case_id=case_id,
        court=court,
        district=district,
        circuit=circuit,
        nos_macro_category=nos_macro_category,
        motion_type=motion_type,
        judge_id=judge_id,
        represented_party_status=represented_party_status,
        government_party_status=government_party_status,
        claim_count=claim_count,
        defendant_count=defendant_count,
        motion_length_tokens=motion_length_tokens,
        complaint_length_tokens=complaint_length_tokens,
        case_age_days=case_age_days,
        docket_entry_count=docket_entry_count,
    )
