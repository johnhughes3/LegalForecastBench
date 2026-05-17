"""Cost and quality Pareto reporting helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_PARETO_OBJECTIVES = (
    "micro_brier",
    "cost_per_case",
    "mean_tool_calls_per_case",
    "invalid_output_rate",
)


@dataclass(frozen=True, slots=True)
class ParetoPoint:
    """Model-level point for quality/cost/tool Pareto reporting."""

    model_id: str
    micro_brier: float
    cost_per_case: float | None = None
    mean_tool_calls_per_case: float | None = None
    latency_ms: float | None = None
    invalid_output_rate: float | None = None

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        _require_non_negative(self.micro_brier, "micro_brier")
        for field_name in (
            "cost_per_case",
            "mean_tool_calls_per_case",
            "latency_ms",
            "invalid_output_rate",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative(value, field_name)

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "micro_brier": self.micro_brier,
            "cost_per_case": self.cost_per_case,
            "mean_tool_calls_per_case": self.mean_tool_calls_per_case,
            "latency_ms": self.latency_ms,
            "invalid_output_rate": self.invalid_output_rate,
        }


def pareto_frontier(
    points: Sequence[ParetoPoint],
    *,
    dimensions: Sequence[str] = ("micro_brier", "cost_per_case"),
) -> tuple[ParetoPoint, ...]:
    """Return non-dominated Pareto points for the selected dimensions."""

    records = pareto_frontier_records(
        tuple(point.to_record() for point in points),
        objective_fields=dimensions,
    )
    frontier_ids = {_required_str(record, "model_id") for record in records}
    return tuple(point for point in points if point.model_id in frontier_ids)


def pareto_records(
    points: Sequence[ParetoPoint],
    *,
    dimensions: Sequence[str] = ("micro_brier", "cost_per_case"),
) -> list[dict[str, Any]]:
    """Return JSON-serializable Pareto frontier records."""

    return [
        point.to_record() for point in pareto_frontier(points, dimensions=dimensions)
    ]


def pareto_frontier_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    objective_fields: Sequence[str] = DEFAULT_PARETO_OBJECTIVES,
) -> list[dict[str, Any]]:
    """Return non-dominated rows across lower-is-better objective fields."""

    if not rows:
        raise ValueError("rows must not be empty")
    if not objective_fields:
        raise ValueError("objective_fields must not be empty")

    candidates = [row for row in rows if _has_numeric_objectives(row, objective_fields)]
    frontier: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if any(
            _dominates(other, candidate, objective_fields)
            for other in candidates
            if other is not candidate
        ):
            continue
        frontier.append(candidate)

    return [
        dict(row)
        for row in sorted(
            frontier,
            key=lambda item: tuple(float(item[field]) for field in objective_fields),
        )
    ]


def _dominates(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    objective_fields: Sequence[str],
) -> bool:
    left_values = tuple(float(left[field]) for field in objective_fields)
    right_values = tuple(float(right[field]) for field in objective_fields)
    return all(
        left_value <= right_value
        for left_value, right_value in zip(left_values, right_values, strict=True)
    ) and any(
        left_value < right_value
        for left_value, right_value in zip(left_values, right_values, strict=True)
    )


def _has_numeric_objectives(
    row: Mapping[str, Any],
    objective_fields: Sequence[str],
) -> bool:
    for field in objective_fields:
        value = row.get(field)
        if not isinstance(value, int | float) or isinstance(value, bool):
            return False
    return True


def _require_non_negative(value: float, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
