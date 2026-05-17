"""Deterministic offline model-output fixtures for harness and scorer tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

REQUIRED_MOCK_UNIT_IDS = (
    "count_1_section_10b_issuer",
    "count_2_section_20a_officers",
    "count_3_section_11_underwriters",
)
BASE_RATE_PROBABILITY = 0.42


class MockOutputScenario(StrEnum):
    """Offline model behaviors that parser, scorer, and accounting tests need."""

    CALIBRATED = "calibrated"
    OVERCONFIDENT = "overconfident"
    ALWAYS_BASE_RATE = "always_base_rate"
    INVALID_JSON = "invalid_json"
    MISSING_UNIT = "missing_unit"
    DUPLICATE_UNIT = "duplicate_unit"
    OUT_OF_RANGE_PROBABILITY = "out_of_range_probability"
    REFUSAL = "refusal"
    TOOL_ABUSE = "tool_abuse"


class ExpectedParserOutcome(StrEnum):
    """Expected strict parser/accounting outcome for a raw model response."""

    VALID = "valid"
    INVALID_JSON = "invalid_json"
    MISSING_UNIT = "missing_unit"
    DUPLICATE_UNIT = "duplicate_unit"
    OUT_OF_RANGE_PROBABILITY = "out_of_range_probability"
    REFUSAL = "refusal"
    UNAUTHORIZED_TOOL = "unauthorized_tool"


@dataclass(frozen=True, slots=True)
class MockPrediction:
    """One raw prediction in the structured model-output contract."""

    unit_id: str
    probability_fully_dismissed: float

    def __post_init__(self) -> None:
        if not self.unit_id.strip():
            raise ValueError("unit_id is required")

    def to_record(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "probability_fully_dismissed": self.probability_fully_dismissed,
        }


@dataclass(frozen=True, slots=True)
class MockToolCall:
    """Tool-call accounting fixture observed during a mock model run."""

    tool_name: str
    arguments: Mapping[str, object]
    allowed: bool

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("tool_name is required")

    def to_record(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "allowed": self.allowed,
        }


@dataclass(frozen=True, slots=True)
class MockModelOutputFixture:
    """Raw model output plus expected parser and run-accounting facts."""

    fixture_id: str
    scenario: MockOutputScenario
    required_unit_ids: tuple[str, ...]
    raw_output: str
    expected_parser_outcome: ExpectedParserOutcome
    expected_predictions: tuple[MockPrediction, ...] = ()
    expected_missing_unit_ids: tuple[str, ...] = ()
    expected_invalid_reason: str | None = None
    expected_refusal: bool = False
    observed_tool_calls: tuple[MockToolCall, ...] = ()
    request_count: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id is required")
        if not self.required_unit_ids:
            raise ValueError("required_unit_ids must not be empty")
        if any(not unit_id.strip() for unit_id in self.required_unit_ids):
            raise ValueError("required_unit_ids must be non-empty strings")
        if not self.raw_output.strip():
            raise ValueError("raw_output is required")
        if self.request_count < 0:
            raise ValueError("request_count cannot be negative")
        if self.input_tokens < 0:
            raise ValueError("input_tokens cannot be negative")
        if self.output_tokens < 0:
            raise ValueError("output_tokens cannot be negative")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")
        if self.expected_refusal and (
            self.expected_parser_outcome is not ExpectedParserOutcome.REFUSAL
        ):
            raise ValueError("expected_refusal requires refusal parser outcome")

        known_units = set(self.required_unit_ids)
        unknown_missing = set(self.expected_missing_unit_ids) - known_units
        if unknown_missing:
            raise ValueError(f"unknown missing unit IDs: {sorted(unknown_missing)}")

    @property
    def raw_output_hash(self) -> str:
        encoded = self.raw_output.encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @property
    def observed_tool_call_count(self) -> int:
        return len(self.observed_tool_calls)

    @property
    def estimated_total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_strict_parser_valid(self) -> bool:
        return self.expected_parser_outcome is ExpectedParserOutcome.VALID

    def decode_json_output(self) -> Mapping[str, object]:
        """Decode the raw output exactly as the future strict parser will."""

        value: object = json.loads(self.raw_output)
        if not isinstance(value, Mapping):
            raise ValueError("model output must decode to a JSON object")
        return cast(Mapping[str, object], value)

    def to_record(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "scenario": self.scenario.value,
            "required_unit_ids": list(self.required_unit_ids),
            "raw_output": self.raw_output,
            "raw_output_hash": self.raw_output_hash,
            "expected_parser_outcome": self.expected_parser_outcome.value,
            "expected_predictions": [
                prediction.to_record() for prediction in self.expected_predictions
            ],
            "expected_missing_unit_ids": list(self.expected_missing_unit_ids),
            "expected_invalid_reason": self.expected_invalid_reason,
            "expected_refusal": self.expected_refusal,
            "observed_tool_calls": [
                tool_call.to_record() for tool_call in self.observed_tool_calls
            ],
            "request_count": self.request_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "estimated_cost": self.estimated_cost,
        }


def _case_output(
    predictions: tuple[MockPrediction, ...],
    *,
    case_assessment: str,
) -> str:
    payload = {
        "case_assessment": case_assessment,
        "predictions": [prediction.to_record() for prediction in predictions],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _prediction(unit_id: str, probability: float) -> MockPrediction:
    return MockPrediction(
        unit_id=unit_id,
        probability_fully_dismissed=probability,
    )


_CALIBRATED_PREDICTIONS = (
    _prediction(REQUIRED_MOCK_UNIT_IDS[0], 0.67),
    _prediction(REQUIRED_MOCK_UNIT_IDS[1], 0.41),
    _prediction(REQUIRED_MOCK_UNIT_IDS[2], 0.24),
)
_OVERCONFIDENT_PREDICTIONS = (
    _prediction(REQUIRED_MOCK_UNIT_IDS[0], 0.98),
    _prediction(REQUIRED_MOCK_UNIT_IDS[1], 0.02),
    _prediction(REQUIRED_MOCK_UNIT_IDS[2], 0.99),
)
_BASE_RATE_PREDICTIONS = tuple(
    _prediction(unit_id, BASE_RATE_PROBABILITY) for unit_id in REQUIRED_MOCK_UNIT_IDS
)
_MISSING_UNIT_PREDICTIONS = _CALIBRATED_PREDICTIONS[:2]
_DUPLICATE_UNIT_PREDICTIONS = (
    _prediction(REQUIRED_MOCK_UNIT_IDS[0], 0.64),
    _prediction(REQUIRED_MOCK_UNIT_IDS[0], 0.71),
    _prediction(REQUIRED_MOCK_UNIT_IDS[1], 0.43),
    _prediction(REQUIRED_MOCK_UNIT_IDS[2], 0.20),
)
_OUT_OF_RANGE_PREDICTIONS = (
    _prediction(REQUIRED_MOCK_UNIT_IDS[0], 1.12),
    _prediction(REQUIRED_MOCK_UNIT_IDS[1], 0.39),
    _prediction(REQUIRED_MOCK_UNIT_IDS[2], 0.18),
)

_MOCK_MODEL_OUTPUTS: tuple[MockModelOutputFixture, ...] = (
    MockModelOutputFixture(
        fixture_id="mock_calibrated_predictions",
        scenario=MockOutputScenario.CALIBRATED,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _CALIBRATED_PREDICTIONS,
            case_assessment="Mixed dismissal risk with stronger scienter defense.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.VALID,
        expected_predictions=_CALIBRATED_PREDICTIONS,
        input_tokens=1850,
        output_tokens=164,
        estimated_cost=0.0137,
    ),
    MockModelOutputFixture(
        fixture_id="mock_overconfident_predictions",
        scenario=MockOutputScenario.OVERCONFIDENT,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _OVERCONFIDENT_PREDICTIONS,
            case_assessment="Same packet, deliberately sharp probabilities.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.VALID,
        expected_predictions=_OVERCONFIDENT_PREDICTIONS,
        input_tokens=1850,
        output_tokens=151,
        estimated_cost=0.0131,
    ),
    MockModelOutputFixture(
        fixture_id="mock_always_base_rate_predictions",
        scenario=MockOutputScenario.ALWAYS_BASE_RATE,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _BASE_RATE_PREDICTIONS,
            case_assessment="Applies only the frozen empirical base rate.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.VALID,
        expected_predictions=_BASE_RATE_PREDICTIONS,
        input_tokens=1850,
        output_tokens=141,
        estimated_cost=0.0128,
    ),
    MockModelOutputFixture(
        fixture_id="mock_invalid_json_truncated",
        scenario=MockOutputScenario.INVALID_JSON,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output='{"case_assessment":"truncated","predictions":[',
        expected_parser_outcome=ExpectedParserOutcome.INVALID_JSON,
        expected_invalid_reason="json_decode_error",
        input_tokens=1850,
        output_tokens=12,
        estimated_cost=0.0114,
    ),
    MockModelOutputFixture(
        fixture_id="mock_missing_unit_prediction",
        scenario=MockOutputScenario.MISSING_UNIT,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _MISSING_UNIT_PREDICTIONS,
            case_assessment="Omitted the underwriter unit from the response.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.MISSING_UNIT,
        expected_predictions=_MISSING_UNIT_PREDICTIONS,
        expected_missing_unit_ids=(REQUIRED_MOCK_UNIT_IDS[2],),
        expected_invalid_reason="missing_required_unit",
        input_tokens=1850,
        output_tokens=127,
        estimated_cost=0.0125,
    ),
    MockModelOutputFixture(
        fixture_id="mock_duplicate_unit_prediction",
        scenario=MockOutputScenario.DUPLICATE_UNIT,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _DUPLICATE_UNIT_PREDICTIONS,
            case_assessment="Duplicated the issuer unit with conflicting values.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.DUPLICATE_UNIT,
        expected_predictions=_DUPLICATE_UNIT_PREDICTIONS,
        expected_invalid_reason="duplicate_unit_prediction",
        input_tokens=1850,
        output_tokens=179,
        estimated_cost=0.0140,
    ),
    MockModelOutputFixture(
        fixture_id="mock_out_of_range_probability",
        scenario=MockOutputScenario.OUT_OF_RANGE_PROBABILITY,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _OUT_OF_RANGE_PREDICTIONS,
            case_assessment="Uses an invalid probability above one.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.OUT_OF_RANGE_PROBABILITY,
        expected_predictions=_OUT_OF_RANGE_PREDICTIONS,
        expected_invalid_reason="probability_out_of_range",
        input_tokens=1850,
        output_tokens=137,
        estimated_cost=0.0127,
    ),
    MockModelOutputFixture(
        fixture_id="mock_refusal_plain_text",
        scenario=MockOutputScenario.REFUSAL,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=(
            "I cannot provide a prediction about legal outcomes for this case."
        ),
        expected_parser_outcome=ExpectedParserOutcome.REFUSAL,
        expected_invalid_reason="model_refusal",
        expected_refusal=True,
        input_tokens=1850,
        output_tokens=15,
        estimated_cost=0.0115,
    ),
    MockModelOutputFixture(
        fixture_id="mock_tool_abuse_unauthorized_search",
        scenario=MockOutputScenario.TOOL_ABUSE,
        required_unit_ids=REQUIRED_MOCK_UNIT_IDS,
        raw_output=_case_output(
            _CALIBRATED_PREDICTIONS,
            case_assessment="Predictions after an unauthorized external search.",
        ),
        expected_parser_outcome=ExpectedParserOutcome.UNAUTHORIZED_TOOL,
        expected_predictions=_CALIBRATED_PREDICTIONS,
        expected_invalid_reason="unauthorized_tool_call",
        observed_tool_calls=(
            MockToolCall(
                tool_name="web_search",
                arguments={"query": "Keller Prime Ledger motion dismiss outcome"},
                allowed=False,
            ),
        ),
        request_count=2,
        input_tokens=1850,
        output_tokens=166,
        estimated_cost=0.0142,
    ),
)

_MOCK_MODEL_OUTPUTS_BY_ID = {
    fixture.fixture_id: fixture for fixture in _MOCK_MODEL_OUTPUTS
}


def iter_mock_model_outputs() -> tuple[MockModelOutputFixture, ...]:
    """Return deterministic mock model outputs in stable order."""

    return _MOCK_MODEL_OUTPUTS


def mock_model_output_ids() -> tuple[str, ...]:
    """Return stable mock-output fixture identifiers."""

    return tuple(fixture.fixture_id for fixture in _MOCK_MODEL_OUTPUTS)


def get_mock_model_output(fixture_id: str) -> MockModelOutputFixture:
    """Return a mock model-output fixture by ID."""

    try:
        return _MOCK_MODEL_OUTPUTS_BY_ID[fixture_id]
    except KeyError as exc:
        known = ", ".join(mock_model_output_ids())
        message = f"Unknown mock model-output fixture {fixture_id!r}; known: {known}"
        raise KeyError(message) from exc
