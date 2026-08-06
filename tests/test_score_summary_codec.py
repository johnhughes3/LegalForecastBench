from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest
from legalforecast.evals.output_parser import ParserIssueCode, ParserStatus
from legalforecast.evals.scorers import (
    CalibrationBin,
    DominanceSensitivityReport,
    RobustnessDimension,
    ScoreSummary,
    UnitScore,
)
from legalforecast.reporting.score_summary_codec import score_summary_from_record

JsonRecord = dict[str, Any]
Mutation = Callable[[JsonRecord], None]


def _remove_model_id(record: JsonRecord) -> None:
    record.pop("model_id")


def _replace_ece_bins(record: JsonRecord) -> None:
    record["ece_bins"] = "not-a-list"


def _replace_defaulted_prediction(record: JsonRecord) -> None:
    unit_scores = record["unit_scores"]
    assert isinstance(unit_scores, list)
    unit_score = cast(object, unit_scores[0])
    assert isinstance(unit_score, dict)
    cast(JsonRecord, unit_score)["defaulted_prediction"] = "false"


def test_score_summary_from_record_reconstructs_nested_summary() -> None:
    summary = _score_summary()

    assert score_summary_from_record(summary.to_record()) == summary


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_remove_model_id, "model_id is required"),
        (_replace_ece_bins, "ece_bins must be a list"),
        (_replace_defaulted_prediction, "defaulted_prediction must be a boolean"),
    ],
)
def test_score_summary_from_record_preserves_strict_record_errors(
    mutation: Mutation,
    message: str,
) -> None:
    record = _score_summary().to_record()
    mutation(record)

    with pytest.raises(ValueError, match=message):
        score_summary_from_record(record)


def _score_summary() -> ScoreSummary:
    return ScoreSummary(
        model_id="solver:test",
        case_count=1,
        unit_count=1,
        micro_brier=0.04,
        macro_brier=0.04,
        brier_skill_score=-0.25,
        log_loss=0.2,
        ece=0.1,
        capped_case_micro_brier=0.04,
        related_family_capped_micro_brier=0.04,
        mdl_family_capped_micro_brier=0.04,
        case_unit_cap=10,
        family_unit_cap=10,
        dominance_threshold=0.4,
        dominance_sensitivity_reports=(
            DominanceSensitivityReport(
                dimension=RobustnessDimension.CASE,
                bucket="case-1",
                unit_count=1,
                unit_share=1.0,
                bucket_brier=0.04,
                excluded_micro_brier=None,
                capped_micro_brier=0.04,
                unit_cap=10,
            ),
        ),
        invalid_output_rate=0.0,
        refusal_rate=0.0,
        defaulted_prediction_rate=1.0,
        base_rate=0.5,
        base_rate_brier=0.25,
        ece_bins=(
            CalibrationBin(
                bin_index=2,
                lower=0.2,
                upper=0.3,
                unit_count=1,
                mean_probability=0.2,
                observed_rate=0.0,
                absolute_calibration_error=0.2,
            ),
        ),
        unit_scores=(
            UnitScore(
                case_id="case-1",
                candidate_id="candidate-1",
                related_family_id="family-1",
                mdl_family_id=None,
                model_id="solver:test",
                unit_id="unit-1",
                probability_fully_dismissed=0.2,
                outcome=0,
                brier=0.04,
                log_loss=0.2,
                parser_status=ParserStatus.MISSING_UNIT,
                raw_output_sha256="sha256:" + "a" * 64,
                defaulted_prediction=True,
                invalid_reason=ParserIssueCode.MISSING_REQUIRED_UNIT,
                label_confidence=0.9,
            ),
        ),
    )
