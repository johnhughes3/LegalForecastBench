"""Reconstruct published community metrics from hashed artifacts.

Bead ``LegalForecastBench-dm0g.4.1.12`` owns this path. Displayed figures are
never hand-entered: each one is a reconstruction of ScoreArtifact and
receipt-backed observations, traced to the artifact hashes that produced it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self, cast

from legalforecast.multiharness.scoring import ScoreArtifact
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_schema_version,
    require_str,
    validate_public_record,
    validate_sha256,
)
from legalforecast.publication.accounting import HarnessEfficiencyObservation

METRIC_TRACE_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative metric-trace sidecar
    "legalforecast.multiharness.metric_trace.v1"
)
PUBLISHED_METRICS_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative published-metrics sidecar
    "legalforecast.multiharness.published_metrics.v1"
)

REDUCE_IDENTITY = "identity"
REDUCE_MEAN = "mean"
REDUCE_SUM = "sum"
REDUCE_COUNT = "count"
_REDUCE_OPS = frozenset({REDUCE_IDENTITY, REDUCE_MEAN, REDUCE_SUM, REDUCE_COUNT})
_TRACE_REQUIRED = frozenset(
    {
        "schema_version",
        "field_name",
        "displayed_value",
        "source_artifact_sha256s",
        "source_field",
        "reduce",
    }
)
_METRICS_REQUIRED = frozenset(
    {
        "schema_version",
        "score_value",
        "score_unit",
        "selected_count",
        "solved_count",
        "evaluated_count",
        "coverage_percentage",
        "cost_usd",
        "cost_basis",
        "cost_unknown_reason",
        "token_total",
        "token_unknown_reason",
        "wall_elapsed_ms",
        "summed_elapsed_ms",
        "attempt_count",
        "failure_count",
        "traces",
    }
)


class MetricReconstructionError(MultiHarnessValidationError):
    """A displayed metric does not reconstruct from its hashed artifacts."""


@dataclass(frozen=True, slots=True)
class MetricTrace:
    """One displayed figure plus the hashed artifacts that reconstruct it."""

    field_name: str
    displayed_value: int | float | None
    source_artifact_sha256s: tuple[str, ...]
    source_field: str
    reduce: str = REDUCE_IDENTITY
    schema_version: str = METRIC_TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != METRIC_TRACE_SCHEMA_VERSION:
            raise MetricReconstructionError("unsupported metric trace schema_version")
        if not self.field_name.strip():
            raise MetricReconstructionError("field_name must be a non-empty string")
        if not self.source_field.strip():
            raise MetricReconstructionError("source_field must be a non-empty string")
        if self.reduce not in _REDUCE_OPS:
            raise MetricReconstructionError("reduce is not a supported reconstruction")
        if not self.source_artifact_sha256s:
            raise MetricReconstructionError(
                "metric traces require source artifact hashes"
            )
        if self.reduce == REDUCE_IDENTITY and len(self.source_artifact_sha256s) != 1:
            raise MetricReconstructionError(
                "identity reconstruction requires exactly one source artifact"
            )
        for digest in self.source_artifact_sha256s:
            validate_sha256(digest, "source_artifact_sha256s")
        if self.displayed_value is not None:
            _require_finite_number(self.displayed_value, "displayed_value")
        validate_public_record(self.to_record(), "metric_trace")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "field_name": self.field_name,
            "displayed_value": self.displayed_value,
            "source_artifact_sha256s": list(self.source_artifact_sha256s),
            "source_field": self.source_field,
            "reduce": self.reduce,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_TRACE_REQUIRED,
            field_name="metric trace",
        )
        require_schema_version(record, METRIC_TRACE_SCHEMA_VERSION)
        hashes = record.get("source_artifact_sha256s")
        if not isinstance(hashes, Sequence) or isinstance(hashes, str | bytes):
            raise MetricReconstructionError(
                "source_artifact_sha256s must be an array of digests"
            )
        digest_items = cast(Sequence[object], hashes)
        return cls(
            field_name=require_str(record, "field_name"),
            displayed_value=_optional_number(record, "displayed_value"),
            source_artifact_sha256s=tuple(str(item) for item in digest_items),
            source_field=require_str(record, "source_field"),
            reduce=require_str(record, "reduce"),
            schema_version=require_str(record, "schema_version"),
        )


@dataclass(frozen=True, slots=True)
class PublishedMetrics:
    """Peer-column metrics reconstructed from hashed artifacts."""

    selected_count: int
    solved_count: int
    evaluated_count: int
    coverage_percentage: float
    traces: tuple[MetricTrace, ...]
    score_value: float | None = None
    score_unit: str | None = None
    cost_usd: float | None = None
    cost_basis: str | None = None
    cost_unknown_reason: str | None = None
    token_total: int | None = None
    token_unknown_reason: str | None = None
    wall_elapsed_ms: int | None = None
    summed_elapsed_ms: int | None = None
    attempt_count: int | None = None
    failure_count: int | None = None
    schema_version: str = PUBLISHED_METRICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PUBLISHED_METRICS_SCHEMA_VERSION:
            raise MetricReconstructionError("unsupported published metrics schema")
        for name in ("selected_count", "solved_count", "evaluated_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise MetricReconstructionError(
                    f"{name} must be a non-negative integer"
                )
        if self.selected_count <= 0:
            raise MetricReconstructionError("selected_count must be positive")
        _require_finite_number(self.coverage_percentage, "coverage_percentage")
        if not self.traces:
            raise MetricReconstructionError(
                "published metrics require reconstruction traces"
            )
        traced = {trace.field_name for trace in self.traces}
        required = {
            "score_value",
            "coverage_percentage",
            "cost_usd",
            "token_total",
            "wall_elapsed_ms",
            "attempt_count",
            "failure_count",
        }
        missing = sorted(required.difference(traced))
        if missing:
            raise MetricReconstructionError(
                "published metrics missing traces for: " + ", ".join(missing)
            )
        for trace in self.traces:
            if not hasattr(self, trace.field_name):
                continue
            actual = getattr(self, trace.field_name)
            if not _values_match(actual, trace.displayed_value):
                raise MetricReconstructionError(
                    f"{trace.field_name} does not match its reconstruction trace"
                )
        validate_public_record(self.to_record(), "published_metrics")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "score_value": self.score_value,
            "score_unit": self.score_unit,
            "selected_count": self.selected_count,
            "solved_count": self.solved_count,
            "evaluated_count": self.evaluated_count,
            "coverage_percentage": self.coverage_percentage,
            "cost_usd": self.cost_usd,
            "cost_basis": self.cost_basis,
            "cost_unknown_reason": self.cost_unknown_reason,
            "token_total": self.token_total,
            "token_unknown_reason": self.token_unknown_reason,
            "wall_elapsed_ms": self.wall_elapsed_ms,
            "summed_elapsed_ms": self.summed_elapsed_ms,
            "attempt_count": self.attempt_count,
            "failure_count": self.failure_count,
            "traces": [trace.to_record() for trace in self.traces],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_METRICS_REQUIRED,
            field_name="published metrics",
        )
        require_schema_version(record, PUBLISHED_METRICS_SCHEMA_VERSION)
        traces_raw = record.get("traces")
        if not isinstance(traces_raw, Sequence) or isinstance(traces_raw, str | bytes):
            raise MetricReconstructionError("traces must be an array")
        trace_items = cast(Sequence[object], traces_raw)
        return cls(
            score_value=_optional_number(record, "score_value"),
            score_unit=_optional_text(record, "score_unit"),
            selected_count=_require_int(record, "selected_count"),
            solved_count=_require_int(record, "solved_count"),
            evaluated_count=_require_int(record, "evaluated_count"),
            coverage_percentage=_require_float(record, "coverage_percentage"),
            cost_usd=_optional_number(record, "cost_usd"),
            cost_basis=_optional_text(record, "cost_basis"),
            cost_unknown_reason=_optional_text(record, "cost_unknown_reason"),
            token_total=_optional_int(record, "token_total"),
            token_unknown_reason=_optional_text(record, "token_unknown_reason"),
            wall_elapsed_ms=_optional_int(record, "wall_elapsed_ms"),
            summed_elapsed_ms=_optional_int(record, "summed_elapsed_ms"),
            attempt_count=_optional_int(record, "attempt_count"),
            failure_count=_optional_int(record, "failure_count"),
            traces=tuple(
                MetricTrace.from_record(_mapping_item(item, "traces"))
                for item in trace_items
            ),
            schema_version=require_str(record, "schema_version"),
        )


def metrics_from_artifacts(
    *,
    scores: Sequence[ScoreArtifact],
    observation: HarnessEfficiencyObservation,
    selected_count: int,
    solved_count: int,
    evaluated_count: int,
    group_size: int,
    score_artifact_sha256s: Sequence[str],
    observation_sha256: str,
) -> PublishedMetrics:
    """Build peer-column metrics whose every figure traces to an artifact hash."""

    if group_size <= 0:
        raise MetricReconstructionError("group_size must be positive")
    score_value = None
    score_unit = None
    if scores:
        if len(score_artifact_sha256s) != len(scores):
            raise MetricReconstructionError(
                "each score artifact must have a canonical hash binding"
            )
        score_value = sum(score.score_value for score in scores) / len(scores)
        units = {score.unit for score in scores}
        if len(units) != 1:
            raise MetricReconstructionError("incompatible score units cannot be mixed")
        score_unit = next(iter(units))
    coverage = 100 * selected_count / group_size
    cost_usd = None
    if observation.combined_cost.amount_microusd is not None:
        cost_usd = observation.combined_cost.amount_microusd / 1_000_000
    traces = (
        MetricTrace(
            field_name="score_value",
            displayed_value=score_value,
            source_artifact_sha256s=tuple(score_artifact_sha256s)
            if scores
            else (observation_sha256,),
            source_field="score_value",
            reduce=REDUCE_MEAN if scores else REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="coverage_percentage",
            displayed_value=coverage,
            source_artifact_sha256s=(observation_sha256,),
            source_field="coverage_percentage",
            reduce=REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="cost_usd",
            displayed_value=cost_usd,
            source_artifact_sha256s=(observation_sha256,),
            source_field="cost_usd",
            reduce=REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="token_total",
            displayed_value=observation.total_tokens.value,
            source_artifact_sha256s=(observation_sha256,),
            source_field="total_tokens.value",
            reduce=REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="wall_elapsed_ms",
            displayed_value=observation.wall_elapsed_ms,
            source_artifact_sha256s=(observation_sha256,),
            source_field="wall_elapsed_ms",
            reduce=REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="attempt_count",
            displayed_value=observation.attempt_count,
            source_artifact_sha256s=(observation_sha256,),
            source_field="attempt_count",
            reduce=REDUCE_IDENTITY,
        ),
        MetricTrace(
            field_name="failure_count",
            displayed_value=observation.failure_count,
            source_artifact_sha256s=(observation_sha256,),
            source_field="failure_count",
            reduce=REDUCE_IDENTITY,
        ),
    )
    metrics = PublishedMetrics(
        score_value=score_value,
        score_unit=score_unit,
        selected_count=selected_count,
        solved_count=solved_count,
        evaluated_count=evaluated_count,
        coverage_percentage=coverage,
        cost_usd=cost_usd,
        cost_basis=observation.combined_cost.basis,
        cost_unknown_reason=observation.combined_cost.unknown_reason,
        token_total=observation.total_tokens.value,
        token_unknown_reason=observation.total_tokens.unknown_reason,
        wall_elapsed_ms=observation.wall_elapsed_ms,
        summed_elapsed_ms=observation.summed_call_elapsed_ms,
        attempt_count=observation.attempt_count,
        failure_count=observation.failure_count,
        traces=traces,
    )
    verify_metric_traces(
        metrics.traces,
        artifacts_by_hash=_reconstruction_artifacts(
            scores=scores,
            score_artifact_sha256s=score_artifact_sha256s,
            observation=observation,
            observation_sha256=observation_sha256,
            selected_count=selected_count,
            coverage_percentage=coverage,
        ),
    )
    return metrics


def verify_metric_traces(
    traces: Sequence[MetricTrace],
    *,
    artifacts_by_hash: Mapping[str, Mapping[str, Any]],
) -> None:
    """Recompute every displayed figure from its hashed source artifacts."""

    for trace in traces:
        values: list[float] = []
        for digest in trace.source_artifact_sha256s:
            try:
                artifact = artifacts_by_hash[digest]
            except KeyError as exc:
                raise MetricReconstructionError(
                    f"missing source artifact for {trace.field_name}: {digest}"
                ) from exc
            extracted = _lookup_field(artifact, trace.source_field)
            if extracted is None:
                if trace.displayed_value is not None:
                    raise MetricReconstructionError(
                        f"{trace.field_name} does not reconstruct from {digest}"
                    )
                continue
            values.append(_as_float(extracted, trace.field_name))
        reconstructed = _reduce(values, trace.reduce)
        if not _values_match(trace.displayed_value, reconstructed):
            raise MetricReconstructionError(
                f"{trace.field_name} does not reconstruct from hashed artifacts"
            )


def _reconstruction_artifacts(
    *,
    scores: Sequence[ScoreArtifact],
    score_artifact_sha256s: Sequence[str],
    observation: HarnessEfficiencyObservation,
    observation_sha256: str,
    selected_count: int,
    coverage_percentage: float,
) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {
        observation_sha256: {
            **observation.to_record(),
            "selected_count": selected_count,
            "coverage_percentage": coverage_percentage,
            "cost_usd": (
                None
                if observation.combined_cost.amount_microusd is None
                else observation.combined_cost.amount_microusd / 1_000_000
            ),
        }
    }
    for digest, score in zip(score_artifact_sha256s, scores, strict=False):
        artifacts[digest] = score.to_record()
    if not scores:
        artifacts[observation_sha256]["score_value"] = None
    return artifacts


def _lookup_field(record: Mapping[str, Any], path: str) -> object:
    current: object = record
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        typed = cast(Mapping[str, object], current)
        current = typed.get(part)
    return current


def _reduce(values: Sequence[float], reduce: str) -> float | None:
    if not values:
        return None
    if reduce == REDUCE_IDENTITY:
        return values[0]
    if reduce == REDUCE_SUM:
        return float(sum(values))
    if reduce == REDUCE_COUNT:
        return float(len(values))
    return float(sum(values) / len(values))


def _values_match(
    displayed: int | float | None, reconstructed: int | float | None
) -> bool:
    if displayed is None or reconstructed is None:
        return displayed is None and reconstructed is None
    return abs(float(displayed) - float(reconstructed)) < 1e-12


def _as_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MetricReconstructionError(f"{field_name} source field is not a number")
    return float(value)


def _require_finite_number(value: int | float, field_name: str) -> None:
    if isinstance(value, bool):
        raise MetricReconstructionError(f"{field_name} must be a number")
    if value != value:  # NaN
        raise MetricReconstructionError(f"{field_name} must be finite")


def _require_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or isinstance(value, bool):
        raise MetricReconstructionError(f"{field_name} must be an integer")
    return value


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if type(value) is not int or isinstance(value, bool):
        raise MetricReconstructionError(f"{field_name} must be an integer or null")
    return value


def _require_float(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MetricReconstructionError(f"{field_name} must be a number")
    return float(value)


def _optional_number(record: Mapping[str, Any], field_name: str) -> float | None:
    value = record.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MetricReconstructionError(f"{field_name} must be a number or null")
    return float(value)


def _optional_text(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MetricReconstructionError(f"{field_name} must be a string or null")
    return value


def _mapping_item(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MetricReconstructionError(f"{field_name} entries must be objects")
    return cast(Mapping[str, Any], value)
