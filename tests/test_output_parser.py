from __future__ import annotations

import json

from legalforecast.evals.output_parser import (
    DEFAULT_MISSING_PROBABILITY,
    ParserIssueCode,
    ParserStatus,
    parse_model_output,
)
from legalforecast.testing import REQUIRED_MOCK_UNIT_IDS, get_mock_model_output


def test_parser_accepts_valid_structured_output_and_collects_rationale() -> None:
    raw_output = json.dumps(
        {
            "case_assessment": "Mixed dismissal risk.",
            "predictions": [
                {
                    "unit_id": REQUIRED_MOCK_UNIT_IDS[0],
                    "probability_fully_dismissed": 0.67,
                    "rationale": "Scienter allegations look vulnerable.",
                },
                {
                    "unit_id": REQUIRED_MOCK_UNIT_IDS[1],
                    "probability_fully_dismissed": 0.41,
                },
                {
                    "unit_id": REQUIRED_MOCK_UNIT_IDS[2],
                    "probability_fully_dismissed": 0.24,
                },
            ],
        }
    )

    parsed = parse_model_output(
        raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert parsed.status is ParserStatus.VALID
    assert parsed.is_valid is True
    assert parsed.prediction_for(REQUIRED_MOCK_UNIT_IDS[0]).rationale == (
        "Scienter allegations look vulnerable."
    )
    assert parsed.defaulted_unit_ids == ()
    json.dumps(parsed.to_record())


def test_parser_repairs_markdown_wrapped_json_deterministically() -> None:
    fixture = get_mock_model_output("mock_calibrated_predictions")
    raw_output = f"```json\n{fixture.raw_output}\n```"

    parsed = parse_model_output(
        raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert parsed.status is ParserStatus.REPAIRED_VALID
    assert parsed.is_valid is True
    assert parsed.repair_attempted is True
    assert parsed.repair_applied is True


def test_parser_marks_malformed_json_and_defaults_required_units() -> None:
    fixture = get_mock_model_output("mock_invalid_json_truncated")

    first = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )
    second = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert first.status is ParserStatus.INVALID_JSON
    assert first.invalid_output is True
    assert first.defaulted_unit_ids == REQUIRED_MOCK_UNIT_IDS
    assert {
        prediction.probability_fully_dismissed for prediction in first.predictions
    } == {DEFAULT_MISSING_PROBABILITY}
    assert first.to_record() == second.to_record()


def test_parser_detects_missing_unit_and_uses_prespecified_default() -> None:
    fixture = get_mock_model_output("mock_missing_unit_prediction")

    parsed = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    missing_prediction = parsed.prediction_for(REQUIRED_MOCK_UNIT_IDS[2])
    assert parsed.status is ParserStatus.MISSING_UNIT
    assert missing_prediction.defaulted is True
    assert missing_prediction.invalid_reason is ParserIssueCode.MISSING_REQUIRED_UNIT
    assert missing_prediction.probability_fully_dismissed == DEFAULT_MISSING_PROBABILITY


def test_parser_detects_extra_units_without_dropping_required_predictions() -> None:
    fixture = get_mock_model_output("mock_calibrated_predictions")
    payload = json.loads(fixture.raw_output)
    payload["predictions"].append(
        {
            "unit_id": "not_a_frozen_unit",
            "probability_fully_dismissed": 0.88,
        }
    )

    parsed = parse_model_output(
        json.dumps(payload),
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert parsed.status is ParserStatus.EXTRA_UNIT
    assert parsed.extra_predictions[0].unit_id == "not_a_frozen_unit"
    assert parsed.defaulted_unit_ids == ()
    assert [issue.code for issue in parsed.issues] == [ParserIssueCode.EXTRA_UNIT]


def test_parser_detects_duplicate_units_and_keeps_first_prediction() -> None:
    fixture = get_mock_model_output("mock_duplicate_unit_prediction")

    parsed = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert parsed.status is ParserStatus.DUPLICATE_UNIT
    prediction = parsed.prediction_for(REQUIRED_MOCK_UNIT_IDS[0])
    assert prediction.probability_fully_dismissed == 0.64
    assert any(issue.code is ParserIssueCode.DUPLICATE_UNIT for issue in parsed.issues)


def test_parser_rejects_string_probabilities_with_defaulted_unit_record() -> None:
    fixture = get_mock_model_output("mock_calibrated_predictions")
    payload = json.loads(fixture.raw_output)
    payload["predictions"][0]["probability_fully_dismissed"] = "0.67"

    parsed = parse_model_output(
        json.dumps(payload),
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    prediction = parsed.prediction_for(REQUIRED_MOCK_UNIT_IDS[0])
    assert parsed.status is ParserStatus.INVALID_PROBABILITY
    assert prediction.defaulted is True
    assert prediction.invalid_reason is ParserIssueCode.PROBABILITY_NOT_NUMBER


def test_parser_rejects_out_of_range_probabilities() -> None:
    fixture = get_mock_model_output("mock_out_of_range_probability")

    parsed = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    prediction = parsed.prediction_for(REQUIRED_MOCK_UNIT_IDS[0])
    assert parsed.status is ParserStatus.INVALID_PROBABILITY
    assert prediction.invalid_reason is ParserIssueCode.PROBABILITY_OUT_OF_RANGE
    assert prediction.probability_fully_dismissed == DEFAULT_MISSING_PROBABILITY


def test_parser_detects_plain_text_refusals() -> None:
    fixture = get_mock_model_output("mock_refusal_plain_text")

    parsed = parse_model_output(
        fixture.raw_output,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
    )

    assert parsed.status is ParserStatus.REFUSAL
    assert parsed.defaulted_unit_ids == REQUIRED_MOCK_UNIT_IDS
    assert parsed.issues[0].code is ParserIssueCode.MODEL_REFUSAL
