from __future__ import annotations

import json
import math

import pytest
from legalforecast.evals.output_parser import (
    DEFAULT_MISSING_PROBABILITY,
    parse_model_output,
)
from legalforecast.evals.scorers import (
    DEFAULT_LOG_LOSS_EPSILON,
    ScoringCase,
    binary_log_loss,
    brier_score,
    score_cases,
)
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.testing import REQUIRED_MOCK_UNIT_IDS, get_mock_model_output


def test_score_cases_computes_micro_macro_and_skill_score() -> None:
    parsed = parse_model_output(
        get_mock_model_output("mock_calibrated_predictions").raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )
    labels = (
        _label(REQUIRED_MOCK_UNIT_IDS[0], True),
        _label(REQUIRED_MOCK_UNIT_IDS[1], False),
        _label(REQUIRED_MOCK_UNIT_IDS[2], False),
    )

    summary = score_cases(
        (
            ScoringCase(
                case_id="case-1",
                candidate_id="cand-1",
                model_id="model-a",
                parsed_output=parsed,
                outcome_labels=labels,
            ),
        ),
        base_rate=0.5,
    )

    expected_briers = ((0.67 - 1) ** 2, 0.41**2, 0.24**2)
    expected_micro = sum(expected_briers) / 3
    assert summary.case_count == 1
    assert summary.unit_count == 3
    assert summary.micro_brier == pytest.approx(expected_micro)
    assert summary.macro_brier == pytest.approx(expected_micro)
    assert summary.base_rate_brier == pytest.approx(0.25)
    assert summary.brier_skill_score == pytest.approx(1 - expected_micro / 0.25)
    assert summary.unit_scores[0].candidate_id == "cand-1"
    assert summary.unit_scores[0].label_confidence == pytest.approx(0.97)
    json.dumps(summary.to_record())


def test_macro_brier_averages_case_scores_not_units() -> None:
    first = _parsed(
        [
            (REQUIRED_MOCK_UNIT_IDS[0], 0.0),
            (REQUIRED_MOCK_UNIT_IDS[1], 1.0),
            (REQUIRED_MOCK_UNIT_IDS[2], 1.0),
        ]
    )
    second = _parsed([(REQUIRED_MOCK_UNIT_IDS[0], 0.0)])

    summary = score_cases(
        (
            ScoringCase(
                case_id="case-1",
                model_id="model-a",
                parsed_output=first,
                outcome_labels=(
                    _label(REQUIRED_MOCK_UNIT_IDS[0], True),
                    _label(REQUIRED_MOCK_UNIT_IDS[1], False),
                    _label(REQUIRED_MOCK_UNIT_IDS[2], False),
                ),
            ),
            ScoringCase(
                case_id="case-2",
                model_id="model-a",
                parsed_output=second,
                outcome_labels=(_label(REQUIRED_MOCK_UNIT_IDS[0], False),),
            ),
        ),
        base_rate=0.5,
    )

    assert summary.micro_brier == pytest.approx(3 / 4)
    assert summary.macro_brier == pytest.approx(0.5)


def test_capped_case_metric_prevents_silent_mega_case_dominance() -> None:
    mega_units = tuple(f"mega-{index}" for index in range(20))

    summary = score_cases(
        (
            ScoringCase(
                case_id="mega-case",
                model_id="model-a",
                parsed_output=_parsed([(unit_id, 1.0) for unit_id in mega_units]),
                outcome_labels=tuple(_label(unit_id, False) for unit_id in mega_units),
            ),
            ScoringCase(
                case_id="ordinary-case",
                model_id="model-a",
                parsed_output=_parsed([("ordinary-unit", 0.0)]),
                outcome_labels=(_label("ordinary-unit", False),),
            ),
        ),
        base_rate=0.5,
        case_unit_cap=2,
        dominance_threshold=0.5,
    )

    record = summary.to_record()
    case_reports = [
        report
        for report in record["dominance_sensitivity_reports"]
        if report["dimension"] == "case"
    ]

    assert summary.micro_brier == pytest.approx(20 / 21)
    assert summary.capped_case_micro_brier == pytest.approx(2 / 3)
    assert case_reports == [
        {
            "dimension": "case",
            "bucket": "mega-case",
            "unit_count": 20,
            "unit_share": pytest.approx(20 / 21),
            "bucket_brier": 1.0,
            "excluded_micro_brier": 0.0,
            "capped_micro_brier": pytest.approx(2 / 3),
            "unit_cap": 2,
            "recommended_action": "report_excluded_and_capped_sensitivity",
        }
    ]


def test_related_and_mdl_family_caps_report_stable_alternative_scores() -> None:
    first_family_units = tuple(f"family-a-{index}" for index in range(4))
    second_family_units = tuple(f"family-b-{index}" for index in range(4))

    summary = score_cases(
        (
            ScoringCase(
                case_id="related-case-1",
                model_id="model-a",
                parsed_output=_parsed(
                    [(unit_id, 1.0) for unit_id in first_family_units]
                ),
                outcome_labels=tuple(
                    _label(unit_id, False) for unit_id in first_family_units
                ),
                related_family_id="family-a",
                mdl_family_id="mdl-a",
            ),
            ScoringCase(
                case_id="related-case-2",
                model_id="model-a",
                parsed_output=_parsed(
                    [(unit_id, 1.0) for unit_id in second_family_units]
                ),
                outcome_labels=tuple(
                    _label(unit_id, False) for unit_id in second_family_units
                ),
                related_family_id="family-a",
                mdl_family_id="mdl-a",
            ),
            ScoringCase(
                case_id="unrelated-case",
                model_id="model-a",
                parsed_output=_parsed([("unrelated-unit", 0.0)]),
                outcome_labels=(_label("unrelated-unit", False),),
            ),
        ),
        base_rate=0.5,
        family_unit_cap=2,
        dominance_threshold=0.5,
    )

    record = summary.to_record()
    reports_by_dimension = {
        report["dimension"]: report
        for report in record["dominance_sensitivity_reports"]
    }

    assert summary.micro_brier == pytest.approx(8 / 9)
    assert summary.related_family_capped_micro_brier == pytest.approx(2 / 3)
    assert summary.mdl_family_capped_micro_brier == pytest.approx(2 / 3)
    assert reports_by_dimension["related_case_family"]["bucket"] == "family-a"
    assert reports_by_dimension["related_case_family"]["excluded_micro_brier"] == 0
    assert reports_by_dimension["related_case_family"]["capped_micro_brier"] == (
        pytest.approx(2 / 3)
    )
    assert reports_by_dimension["mdl_family"]["bucket"] == "mdl-a"
    assert reports_by_dimension["mdl_family"]["capped_micro_brier"] == pytest.approx(
        2 / 3
    )
    assert summary.unit_scores[0].mdl_family_id == "mdl-a"
    assert record["unit_scores"][0]["mdl_family_id"] == "mdl-a"


def test_invalid_and_refusal_outputs_count_once_per_case_and_default_units() -> None:
    parsed = parse_model_output(
        get_mock_model_output("mock_refusal_plain_text").raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    summary = score_cases(
        (
            ScoringCase(
                case_id="case-1",
                model_id="model-a",
                parsed_output=parsed,
                outcome_labels=(
                    _label(REQUIRED_MOCK_UNIT_IDS[0], True),
                    _label(REQUIRED_MOCK_UNIT_IDS[1], False),
                    _label(REQUIRED_MOCK_UNIT_IDS[2], False),
                ),
            ),
        ),
        base_rate=0.5,
    )

    assert summary.invalid_output_rate == 1
    assert summary.refusal_rate == 1
    assert summary.defaulted_prediction_rate == 1
    assert {
        unit_score.probability_fully_dismissed for unit_score in summary.unit_scores
    } == {DEFAULT_MISSING_PROBABILITY}
    assert all(
        unit_score.invalid_reason is not None for unit_score in summary.unit_scores
    )


def test_log_loss_is_clipped_for_extreme_probabilities() -> None:
    assert brier_score(0.25, 1) == pytest.approx(0.5625)
    assert binary_log_loss(0.0, 1) == pytest.approx(-math.log(DEFAULT_LOG_LOSS_EPSILON))
    assert binary_log_loss(1.0, 0) == pytest.approx(-math.log(DEFAULT_LOG_LOSS_EPSILON))


def test_ece_uses_fixed_equal_width_bins() -> None:
    parsed = _parsed(
        [
            (REQUIRED_MOCK_UNIT_IDS[0], 0.05),
            (REQUIRED_MOCK_UNIT_IDS[1], 0.15),
            (REQUIRED_MOCK_UNIT_IDS[2], 0.95),
        ]
    )

    summary = score_cases(
        (
            ScoringCase(
                case_id="case-1",
                model_id="model-a",
                parsed_output=parsed,
                outcome_labels=(
                    _label(REQUIRED_MOCK_UNIT_IDS[0], False),
                    _label(REQUIRED_MOCK_UNIT_IDS[1], False),
                    _label(REQUIRED_MOCK_UNIT_IDS[2], True),
                ),
            ),
        ),
        base_rate=0.5,
        ece_bin_count=2,
    )

    assert summary.ece == pytest.approx((2 / 3) * 0.1 + (1 / 3) * 0.05)
    assert summary.ece_bins[0].unit_count == 2
    assert summary.ece_bins[0].mean_probability == pytest.approx(0.1)
    assert summary.ece_bins[1].unit_count == 1
    assert summary.ece_bins[1].observed_rate == 1


def test_score_cases_rejects_ambiguous_labels() -> None:
    parsed = _parsed([(REQUIRED_MOCK_UNIT_IDS[0], 0.5)])

    with pytest.raises(ValueError, match="ambiguous label"):
        score_cases(
            (
                ScoringCase(
                    case_id="case-1",
                    model_id="model-a",
                    parsed_output=parsed,
                    outcome_labels=(_ambiguous_label(REQUIRED_MOCK_UNIT_IDS[0]),),
                ),
            ),
            base_rate=0.5,
        )


def _parsed(predictions: list[tuple[str, float]]):
    return parse_model_output(
        json.dumps(
            {
                "case_assessment": "Fixture prediction.",
                "predictions": [
                    {
                        "unit_id": unit_id,
                        "probability_fully_dismissed": probability,
                    }
                    for unit_id, probability in predictions
                ],
            }
        ),
        required_unit_ids=tuple(unit_id for unit_id, _probability in predictions),
    )


def _label(unit_id: str, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.97,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )


def _ambiguous_label(unit_id: str) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=None,
        amendment_class=AmendmentClass.AMBIGUOUS,
        ambiguous=True,
        label_confidence=0.4,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )
