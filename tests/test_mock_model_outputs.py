from __future__ import annotations

import json

import pytest
from legalforecast.testing import (
    BASE_RATE_PROBABILITY,
    REQUIRED_MOCK_UNIT_IDS,
    ExpectedParserOutcome,
    MockOutputScenario,
    get_mock_model_output,
    iter_mock_model_outputs,
    mock_model_output_ids,
)


def test_mock_outputs_cover_required_offline_scenarios() -> None:
    covered = {fixture.scenario for fixture in iter_mock_model_outputs()}

    assert covered == set(MockOutputScenario)


def test_mock_outputs_have_stable_ids_and_hashes() -> None:
    fixture_ids = mock_model_output_ids()
    hashes = {fixture.raw_output_hash for fixture in iter_mock_model_outputs()}

    assert len(fixture_ids) == len(set(fixture_ids))
    assert len(hashes) == len(fixture_ids)
    assert all(raw_hash.startswith("sha256:") for raw_hash in hashes)


def test_valid_mock_outputs_follow_model_output_contract() -> None:
    valid_fixtures = [
        fixture
        for fixture in iter_mock_model_outputs()
        if fixture.expected_parser_outcome is ExpectedParserOutcome.VALID
    ]

    assert valid_fixtures
    for fixture in valid_fixtures:
        decoded = fixture.decode_json_output()

        assert fixture.is_strict_parser_valid is True
        assert isinstance(decoded["case_assessment"], str)
        assert [prediction["unit_id"] for prediction in decoded["predictions"]] == list(
            REQUIRED_MOCK_UNIT_IDS
        )


def test_always_base_rate_fixture_uses_frozen_base_rate() -> None:
    fixture = get_mock_model_output("mock_always_base_rate_predictions")

    assert fixture.scenario is MockOutputScenario.ALWAYS_BASE_RATE
    assert {
        prediction.probability_fully_dismissed
        for prediction in fixture.expected_predictions
    } == {BASE_RATE_PROBABILITY}


def test_invalid_json_and_refusal_fixtures_preserve_raw_failures() -> None:
    invalid = get_mock_model_output("mock_invalid_json_truncated")
    refusal = get_mock_model_output("mock_refusal_plain_text")

    with pytest.raises(json.JSONDecodeError):
        invalid.decode_json_output()
    with pytest.raises(json.JSONDecodeError):
        refusal.decode_json_output()

    assert invalid.expected_parser_outcome is ExpectedParserOutcome.INVALID_JSON
    assert refusal.expected_parser_outcome is ExpectedParserOutcome.REFUSAL
    assert refusal.expected_refusal is True


def test_missing_and_duplicate_unit_fixtures_are_machine_checkable() -> None:
    missing = get_mock_model_output("mock_missing_unit_prediction")
    duplicate = get_mock_model_output("mock_duplicate_unit_prediction")

    assert missing.expected_missing_unit_ids == (REQUIRED_MOCK_UNIT_IDS[2],)
    assert missing.expected_parser_outcome is ExpectedParserOutcome.MISSING_UNIT

    duplicate_unit_ids = [
        prediction.unit_id for prediction in duplicate.expected_predictions
    ]
    assert duplicate_unit_ids.count(REQUIRED_MOCK_UNIT_IDS[0]) == 2
    assert duplicate.expected_parser_outcome is ExpectedParserOutcome.DUPLICATE_UNIT


def test_out_of_range_probability_fixture_preserves_invalid_value() -> None:
    fixture = get_mock_model_output("mock_out_of_range_probability")

    assert fixture.expected_parser_outcome is (
        ExpectedParserOutcome.OUT_OF_RANGE_PROBABILITY
    )
    assert any(
        prediction.probability_fully_dismissed > 1
        for prediction in fixture.expected_predictions
    )


def test_tool_abuse_fixture_records_run_accounting() -> None:
    fixture = get_mock_model_output("mock_tool_abuse_unauthorized_search")

    assert fixture.expected_parser_outcome is ExpectedParserOutcome.UNAUTHORIZED_TOOL
    assert fixture.observed_tool_call_count == 1
    assert fixture.request_count == 2
    assert (
        fixture.estimated_total_tokens == fixture.input_tokens + fixture.output_tokens
    )
    assert fixture.estimated_cost > 0
    assert fixture.observed_tool_calls[0].allowed is False


def test_mock_output_records_are_json_serializable() -> None:
    record = get_mock_model_output("mock_calibrated_predictions").to_record()

    encoded = json.dumps(record, sort_keys=True)

    assert "mock_calibrated_predictions" in encoded
    assert (
        record["raw_output_hash"]
        == get_mock_model_output("mock_calibrated_predictions").raw_output_hash
    )
