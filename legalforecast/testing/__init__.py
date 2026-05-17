"""Testing helpers and synthetic benchmark fixtures."""

from legalforecast.testing.golden_fixtures import (
    REQUIRED_PIPELINE_LOG_FIELDS,
    FixtureDocketEntry,
    FixtureDocument,
    FixtureEdgeCase,
    GoldenCase,
    get_golden_case,
    golden_case_ids,
    iter_golden_cases,
    pipeline_log_context,
)
from legalforecast.testing.mock_model_outputs import (
    BASE_RATE_PROBABILITY,
    REQUIRED_MOCK_UNIT_IDS,
    ExpectedParserOutcome,
    MockModelOutputFixture,
    MockOutputScenario,
    MockPrediction,
    MockToolCall,
    get_mock_model_output,
    iter_mock_model_outputs,
    mock_model_output_ids,
)

__all__ = [
    "BASE_RATE_PROBABILITY",
    "REQUIRED_MOCK_UNIT_IDS",
    "REQUIRED_PIPELINE_LOG_FIELDS",
    "ExpectedParserOutcome",
    "FixtureDocketEntry",
    "FixtureDocument",
    "FixtureEdgeCase",
    "GoldenCase",
    "MockModelOutputFixture",
    "MockOutputScenario",
    "MockPrediction",
    "MockToolCall",
    "get_golden_case",
    "get_mock_model_output",
    "golden_case_ids",
    "iter_golden_cases",
    "iter_mock_model_outputs",
    "mock_model_output_ids",
    "pipeline_log_context",
]
