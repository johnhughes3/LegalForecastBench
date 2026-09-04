"""Fail-closed forecast rows for the tools-on harness lane.

Trunk ``claude_code.py`` already maps ``not parsed.is_valid`` to
``SCHEMA_VIOLATION``. The halted stack did not: invalid JSON was defaulted
to 0.5 and recorded as ``status=succeeded`` with ``failure_class=none``.
This module is the measurement contract so that shape cannot be scored.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from legalforecast.evals.output_parser import (
    ParserStatus,
    parse_model_output,
    public_parser_record,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass


class HarnessLaneForecastError(ValueError):
    """Raised when an invalid forecast is treated as a scored success."""


@dataclass(frozen=True, slots=True)
class HarnessForecastRow:
    """One canonical harness-lane row after parser classification."""

    status: str
    failure_class: str
    parser_output: Mapping[str, object]
    scored: bool

    def to_canonical_record(self) -> dict[str, object]:
        return {
            "status": self.status,
            "public_summary": {"failure_class": self.failure_class},
            "parser_output": dict(self.parser_output),
            "scored": self.scored,
        }


def classify_harness_forecast(
    raw_output: str,
    *,
    required_unit_ids: Sequence[str],
) -> HarnessForecastRow:
    """Parse one forecast and refuse to score invalid JSON as success."""

    parsed = parse_model_output(raw_output, required_unit_ids=required_unit_ids)
    public = public_parser_record(parsed)
    if parsed.status is ParserStatus.REFUSAL:
        row = HarnessForecastRow(
            status="failed",
            failure_class=LocalCliFailureClass.REFUSAL.value,
            parser_output=public,
            scored=False,
        )
    elif not parsed.is_valid:
        row = HarnessForecastRow(
            status="failed",
            failure_class=LocalCliFailureClass.SCHEMA_VIOLATION.value,
            parser_output=public,
            scored=False,
        )
    else:
        row = HarnessForecastRow(
            status="succeeded",
            failure_class="none",
            parser_output=public,
            scored=True,
        )
    require_honest_canonical_row(row.to_canonical_record())
    return row


def require_honest_canonical_row(record: Mapping[str, object]) -> None:
    """Refuse the halted stack's invalid-output + succeeded shape."""

    status = record.get("status")
    if not isinstance(status, str) or not status.strip():
        raise HarnessLaneForecastError("canonical row status is missing")
    parser = _mapping(record.get("parser_output"), "parser_output", required=True)
    invalid = parser.get("is_valid") is False or parser.get("invalid_output") is True
    scored = record.get("scored")
    if invalid and status == "succeeded":
        raise HarnessLaneForecastError("invalid forecast cannot be a succeeded row")
    if invalid and scored is True:
        raise HarnessLaneForecastError("invalid forecast cannot enter a scored success")
    if status == "succeeded" and _has_defaulted_prediction(parser):
        raise HarnessLaneForecastError(
            "defaulted probability cannot enter a scored success"
        )


def _mapping(
    value: object,
    field_name: str,
    *,
    required: bool,
) -> Mapping[str, object]:
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise HarnessLaneForecastError(f"canonical row {field_name} is missing")
    return cast(Mapping[str, object], value)


def _has_defaulted_prediction(parser: Mapping[str, object]) -> bool:
    defaulted_ids = parser.get("defaulted_unit_ids")
    if isinstance(defaulted_ids, list):
        typed_ids = cast(list[object], defaulted_ids)
        if typed_ids:
            return True
    predictions = parser.get("predictions")
    if not isinstance(predictions, list):
        return False
    for item in cast(list[object], predictions):
        if isinstance(item, Mapping):
            prediction = cast(Mapping[str, object], item)
            if prediction.get("defaulted") is True:
                return True
    return False
