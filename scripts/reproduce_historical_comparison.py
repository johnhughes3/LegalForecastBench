"""Recompute the separate historical appendix without providers or private records.

Usage: uv run python scripts/reproduce_historical_comparison.py INPUT_JSON OUTPUT_JSON
The extract retains original units and nullable outcomes; invalid cases are excluded.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParsedPrediction,
    ParserStatus,
)
from legalforecast.evals.scorers import ScoringCase, score_cases
from pydantic import BaseModel, ConfigDict, Field


class ExtractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Label(ExtractModel):
    case_id: str
    unit_id: str
    outcome: int | None = Field(ge=0, le=1)


class Prediction(ExtractModel):
    unit_id: str
    probability_fully_dismissed: float = Field(ge=0, le=1, allow_inf_nan=False)


class Case(ExtractModel):
    case_id: str
    raw_output_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    required_unit_ids: list[str]
    status: Literal["valid", "missing_unit"]
    predictions: list[Prediction]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)


class Condition(ExtractModel):
    model_id: str
    execution_backend: Literal["inspect_ai"]
    condition: Literal["full_packet"]
    reasoning_effort: Literal["high"]
    service_tier: Literal["flex", "provider_default"]
    requests_per_case: Literal[1]
    recorded_tool_calls: Literal[0]
    run_id: str
    run_attempt: int = Field(ge=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    cases: list[Case]


class Extract(ExtractModel):
    cohort: str
    source_labels_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    labels: list[Label]
    conditions: list[Condition]


@dataclass(frozen=True)
class ScoreOutcome:
    unit_id: str
    primary_outcome: int | None
    label_confidence: float | None = None


def reproduce(source: Path, output: Path) -> None:
    """Validate original case/unit coverage and score valid cases only."""
    data = Extract.model_validate_json(source.read_text())
    labels_by_case: defaultdict[str, list[Label]] = defaultdict(list)
    for label in data.labels:
        labels_by_case[label.case_id].append(label)
    if len(data.labels) != len({label.unit_id for label in data.labels}):
        raise ValueError("duplicate outcome unit")
    if len(labels_by_case) != 100 or len(data.labels) != 425:
        raise ValueError("historical cohort must contain 100 cases and 425 units")
    if len({c.model_id for c in data.conditions}) != len(data.conditions):
        raise ValueError("duplicate model condition")
    results: list[dict[str, object]] = []
    for condition in data.conditions:
        if len(condition.cases) != 100 or {c.case_id for c in condition.cases} != set(
            labels_by_case
        ):
            raise ValueError("condition must contain each original case exactly once")
        cases: list[ScoringCase] = []
        failures: list[dict[str, object]] = []
        accepted_cost = 0.0
        accepted_units = 0
        for case in condition.cases:
            required = tuple(case.required_unit_ids)
            labels = labels_by_case[case.case_id]
            if len(required) != len(set(required)) or set(required) != {
                label.unit_id for label in labels
            }:
                raise ValueError("case units differ from original labels")
            predictions = {p.unit_id: p for p in case.predictions}
            if len(predictions) != len(case.predictions) or not set(
                predictions
            ).issubset(required):
                raise ValueError("duplicate or unknown prediction unit")
            missing = sorted(set(required) - predictions.keys())
            if case.status == "missing_unit":
                if not missing:
                    raise ValueError("failed case has no missing prediction")
                failures.append(
                    {
                        "case_id": case.case_id,
                        "status": case.status,
                        "missing_unit_ids": missing,
                    }
                )
                continue
            if missing:
                raise ValueError("valid case is missing predictions")
            parsed = ParsedModelOutput(
                status=ParserStatus.VALID,
                raw_output_sha256=case.raw_output_sha256,
                required_unit_ids=required,
                predictions=tuple(
                    ParsedPrediction(
                        unit_id=u,
                        probability_fully_dismissed=predictions[
                            u
                        ].probability_fully_dismissed,
                    )
                    for u in required
                ),
                issues=(),
            )
            cases.append(
                ScoringCase(
                    case_id=case.case_id,
                    model_id=condition.model_id,
                    parsed_output=parsed,
                    outcome_labels=tuple(
                        ScoreOutcome(label.unit_id, label.outcome) for label in labels
                    ),
                )
            )
            accepted_cost += case.estimated_cost_usd
            accepted_units += len(required)
        outcomes = [label.outcome for label in data.labels if label.outcome is not None]
        scores = score_cases(tuple(cases), base_rate=sum(outcomes) / len(outcomes))
        results.append(
            {
                "model_id": condition.model_id,
                "run_id": condition.run_id,
                "attempted_cases": len(condition.cases),
                "accepted_cases": len(cases),
                "accepted_units": accepted_units,
                "scored_cases": scores.case_count,
                "scored_units": scores.unit_count,
                "dropped_labelled_units": sum(
                    label.outcome is not None for label in data.labels
                )
                - scores.unit_count,
                "micro_brier": scores.micro_brier,
                "equal_case_brier": scores.macro_brier,
                "failed_cases": failures,
                "estimated_all_execution_cost_usd": sum(
                    c.estimated_cost_usd for c in condition.cases
                ),
                "estimated_accepted_case_cost_usd": accepted_cost,
                "input_tokens": sum(c.input_tokens for c in condition.cases),
                "output_tokens": sum(c.output_tokens for c in condition.cases),
                "usage_case_coverage": len(condition.cases),
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "cohort": data.cohort,
                "available_cases": 100,
                "available_units": 425,
                "labelled_units": sum(
                    label.outcome is not None for label in data.labels
                ),
                "null_outcome_units": sum(
                    label.outcome is None for label in data.labels
                ),
                "conditions": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    reproduce(args.input_json, args.output_json)
