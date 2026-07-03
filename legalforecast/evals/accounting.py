"""Model-run accounting records for benchmark harness outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast._record_validation import (
    optional_str as _optional_str,
)
from legalforecast._record_validation import (
    require_non_empty as _require_non_empty,
)
from legalforecast._record_validation import (
    require_non_negative_float as _require_non_negative_float,
)
from legalforecast._record_validation import (
    require_non_negative_int as _require_non_negative_int,
)
from legalforecast._record_validation import (
    require_positive as _require_positive,
)
from legalforecast._record_validation import (
    required_float as _required_float,
)
from legalforecast._record_validation import (
    required_int as _required_int,
)
from legalforecast._record_validation import (
    required_str as _required_str,
)
from legalforecast.evals.inspect_task import InspectTaskRun


@dataclass(frozen=True, slots=True)
class OutputValidityStatus:
    """Parser/reliability status attached to a raw model output."""

    invalid_output: bool = False
    refusal: bool = False
    content_filter: bool = False
    invalid_output_reason: str | None = None

    def __post_init__(self) -> None:
        if self.invalid_output_reason is not None:
            _require_non_empty(self.invalid_output_reason, "invalid_output_reason")
            if not self.invalid_output:
                raise ValueError("invalid_output_reason requires invalid_output=True")
        if (self.refusal or self.content_filter) and not self.invalid_output:
            raise ValueError("refusal/content_filter requires invalid_output=True")

    def to_record(self) -> dict[str, Any]:
        return {
            "invalid_output": self.invalid_output,
            "refusal": self.refusal,
            "content_filter": self.content_filter,
            "invalid_output_reason": self.invalid_output_reason,
        }


@dataclass(frozen=True, slots=True)
class ModelRunAccountingRecord:
    """Complete operational accounting for one case/model run."""

    sample_id: str
    candidate_id: str
    case_id: str
    solver_id: str
    solver_kind: str
    provider: str
    model_id: str
    model_version_or_snapshot: str
    served_model_version: str | None
    evaluation_timestamp: datetime
    raw_output_sha256: str
    prediction_unit_count: int
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tool_call_count: int
    allowed_tool_call_count: int
    denied_tool_call_count: int
    latency_ms: float
    estimated_cost: float
    cost_per_case: float
    cost_per_prediction_unit: float
    invalid_output: bool
    refusal: bool
    content_filter: bool
    invalid_output_reason: str | None
    run_label: str | None = None
    ablation: str | None = None
    execution_backend: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "sample_id",
            "candidate_id",
            "case_id",
            "solver_id",
            "solver_kind",
            "provider",
            "model_id",
            "model_version_or_snapshot",
            "raw_output_sha256",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        if not self.raw_output_sha256.startswith("sha256:"):
            raise ValueError("raw_output_sha256 must use sha256: prefix")
        _require_aware_datetime(self.evaluation_timestamp, "evaluation_timestamp")
        _require_positive(self.prediction_unit_count, "prediction_unit_count")
        _require_non_negative_int(self.request_count, "request_count")
        _require_non_negative_int(self.prompt_tokens, "prompt_tokens")
        _require_non_negative_int(self.completion_tokens, "completion_tokens")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt + completion tokens")
        _require_non_negative_int(self.tool_call_count, "tool_call_count")
        _require_non_negative_int(
            self.allowed_tool_call_count,
            "allowed_tool_call_count",
        )
        _require_non_negative_int(
            self.denied_tool_call_count,
            "denied_tool_call_count",
        )
        if (
            self.allowed_tool_call_count + self.denied_tool_call_count
            != self.tool_call_count
        ):
            raise ValueError("allowed + denied tool calls must equal total tool calls")
        _require_non_negative_float(self.latency_ms, "latency_ms")
        _require_non_negative_float(self.estimated_cost, "estimated_cost")
        _require_non_negative_float(self.cost_per_case, "cost_per_case")
        _require_non_negative_float(
            self.cost_per_prediction_unit,
            "cost_per_prediction_unit",
        )
        if self.invalid_output_reason is not None:
            _require_non_empty(self.invalid_output_reason, "invalid_output_reason")
            if not self.invalid_output:
                raise ValueError("invalid_output_reason requires invalid_output=True")
        if self.served_model_version is not None:
            _require_non_empty(self.served_model_version, "served_model_version")
        if (self.refusal or self.content_filter) and not self.invalid_output:
            raise ValueError("refusal/content_filter requires invalid_output=True")
        if self.run_label is not None:
            _require_non_empty(self.run_label, "run_label")
        if self.ablation is not None:
            _require_non_empty(self.ablation, "ablation")
        if self.execution_backend is not None:
            _require_non_empty(self.execution_backend, "execution_backend")

    def to_record(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "solver_id": self.solver_id,
            "solver_kind": self.solver_kind,
            "provider": self.provider,
            "model_id": self.model_id,
            "model_version_or_snapshot": self.model_version_or_snapshot,
            "served_model_version": self.served_model_version,
            "evaluation_timestamp": _iso_datetime(self.evaluation_timestamp),
            "raw_output_sha256": self.raw_output_sha256,
            "prediction_unit_count": self.prediction_unit_count,
            "request_count": self.request_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_call_count": self.tool_call_count,
            "allowed_tool_call_count": self.allowed_tool_call_count,
            "denied_tool_call_count": self.denied_tool_call_count,
            "latency_ms": self.latency_ms,
            "estimated_cost": self.estimated_cost,
            "cost_per_case": self.cost_per_case,
            "cost_per_prediction_unit": self.cost_per_prediction_unit,
            "invalid_output": self.invalid_output,
            "refusal": self.refusal,
            "content_filter": self.content_filter,
            "invalid_output_reason": self.invalid_output_reason,
            "run_label": self.run_label,
            "ablation": self.ablation,
            "execution_backend": self.execution_backend,
        }


def accounting_result_key(record: Mapping[str, Any]) -> str:
    """Stable key for attaching latency/status facts to one harness result."""

    parts = [
        _required_str(record, "sample_id"),
        _required_str(record, "solver_id"),
        _optional_str(record, "run_label") or "default",
    ]
    return "::".join(parts)


def accounting_records_from_inspect_run(
    run: InspectTaskRun,
    *,
    evaluation_timestamp: datetime,
    latency_ms_by_result_key: Mapping[str, float] | None = None,
    output_status_by_raw_hash: Mapping[str, OutputValidityStatus] | None = None,
) -> tuple[ModelRunAccountingRecord, ...]:
    """Build complete accounting records from an Inspect-compatible run."""

    return accounting_records_from_harness_records(
        run.to_records(),
        evaluation_timestamp=evaluation_timestamp,
        latency_ms_by_result_key=latency_ms_by_result_key,
        output_status_by_raw_hash=output_status_by_raw_hash,
    )


def accounting_records_from_harness_records(
    records: Sequence[Mapping[str, Any]],
    *,
    evaluation_timestamp: datetime,
    latency_ms_by_result_key: Mapping[str, float] | None = None,
    output_status_by_raw_hash: Mapping[str, OutputValidityStatus] | None = None,
) -> tuple[ModelRunAccountingRecord, ...]:
    """Normalize raw harness records into complete accounting artifacts."""

    if not records:
        raise ValueError("at least one harness record is required")
    _require_aware_datetime(evaluation_timestamp, "evaluation_timestamp")
    normalized: list[ModelRunAccountingRecord] = []
    for record in records:
        result_key = accounting_result_key(record)
        raw_hash = _required_str(record, "raw_output_sha256")
        latency_ms = _latency_for_record(
            record,
            result_key=result_key,
            latency_ms_by_result_key=latency_ms_by_result_key,
        )
        status = (output_status_by_raw_hash or {}).get(
            raw_hash,
            OutputValidityStatus(),
        )
        tool_counts = _tool_call_counts(record)
        prediction_unit_count = _prediction_unit_count(record)
        estimated_cost = _required_float(record, "estimated_cost")
        normalized.append(
            ModelRunAccountingRecord(
                sample_id=_required_str(record, "sample_id"),
                candidate_id=_required_str(record, "candidate_id"),
                case_id=_required_str(record, "case_id"),
                solver_id=_required_str(record, "solver_id"),
                solver_kind=_required_str(record, "solver_kind"),
                provider=_provider(record),
                model_id=_model_id(record),
                model_version_or_snapshot=_model_version(record),
                served_model_version=_served_model_version(record),
                evaluation_timestamp=evaluation_timestamp.astimezone(UTC),
                raw_output_sha256=raw_hash,
                prediction_unit_count=prediction_unit_count,
                request_count=_required_int(record, "request_count"),
                prompt_tokens=_token_count(
                    record,
                    primary="prompt_tokens",
                    fallback="input_tokens",
                ),
                completion_tokens=_token_count(
                    record,
                    primary="completion_tokens",
                    fallback="output_tokens",
                ),
                total_tokens=_total_tokens(record),
                tool_call_count=tool_counts.total,
                allowed_tool_call_count=tool_counts.allowed,
                denied_tool_call_count=tool_counts.denied,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                cost_per_case=estimated_cost,
                cost_per_prediction_unit=estimated_cost / prediction_unit_count,
                invalid_output=status.invalid_output,
                refusal=status.refusal,
                content_filter=status.content_filter,
                invalid_output_reason=status.invalid_output_reason,
                run_label=_optional_str(record, "run_label"),
                ablation=_optional_str(record, "ablation"),
                execution_backend=_execution_backend(record),
            )
        )
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class _ToolCallCounts:
    total: int
    allowed: int
    denied: int


def _provider(record: Mapping[str, Any]) -> str:
    value = _optional_str(record, "provider") or _metadata_str(record, "provider")
    if value is not None:
        return value
    solver_id = _required_str(record, "solver_id")
    if ":" in solver_id:
        return solver_id.split(":", maxsplit=1)[0]
    return _required_str(record, "solver_kind")


def _model_id(record: Mapping[str, Any]) -> str:
    value = _optional_str(record, "model_id") or _metadata_str(record, "model_id")
    if value is not None:
        return value
    solver_id = _required_str(record, "solver_id")
    if ":" in solver_id:
        return solver_id.split(":", maxsplit=1)[1]
    return solver_id


def _model_version(record: Mapping[str, Any]) -> str:
    value = _optional_str(record, "model_version_or_snapshot") or _metadata_str(
        record,
        "model_version_or_snapshot",
    )
    if value is not None:
        return value
    if _required_str(record, "solver_kind") == "offline_mock":
        return "fixture"
    return "unknown"


def _served_model_version(record: Mapping[str, Any]) -> str | None:
    return _optional_str(record, "served_model_version") or _metadata_str(
        record,
        "served_model_version",
    )


def _execution_backend(record: Mapping[str, Any]) -> str:
    value = _optional_str(record, "execution_backend") or _metadata_str(
        record,
        "execution_backend",
    )
    if value is not None:
        return value
    if _required_str(record, "solver_kind") == "offline_mock":
        return "local_fixture"
    return "unknown"


def _latency_for_record(
    record: Mapping[str, Any],
    *,
    result_key: str,
    latency_ms_by_result_key: Mapping[str, float] | None,
) -> float:
    if latency_ms_by_result_key is not None and result_key in latency_ms_by_result_key:
        value = latency_ms_by_result_key[result_key]
        _require_non_negative_float(value, f"latency_ms[{result_key}]")
        return value
    value = record.get("latency_ms")
    if value is None:
        metadata_latency = _metadata_str(record, "latency_ms")
        value = metadata_latency if metadata_latency is not None else 0.0
    if isinstance(value, str):
        try:
            latency_ms = float(value)
        except ValueError as exc:
            raise ValueError("latency_ms must be a number") from exc
    elif isinstance(value, int | float) and not isinstance(value, bool):
        latency_ms = float(value)
    else:
        raise ValueError("latency_ms must be a number")
    _require_non_negative_float(latency_ms, "latency_ms")
    return latency_ms


def _tool_call_counts(record: Mapping[str, Any]) -> _ToolCallCounts:
    logs = _tool_logs(record)
    allowed = 0
    denied = 0
    for log in logs:
        status = _required_str(log, "status")
        if status == "allowed":
            allowed += 1
        elif status == "denied":
            denied += 1
        else:
            raise ValueError(f"unknown tool call status: {status}")
    return _ToolCallCounts(total=len(logs), allowed=allowed, denied=denied)


def _tool_logs(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    value = record.get("tool_call_logs", ())
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("tool_call_logs must be a sequence")
    items = cast(Sequence[object], value)
    logs: list[Mapping[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"tool_call_logs[{index}] must be an object")
        logs.append(cast(Mapping[str, Any], item))
    return tuple(logs)


def _prediction_unit_count(record: Mapping[str, Any]) -> int:
    value = record.get("prediction_unit_count")
    if value is not None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("prediction_unit_count must be an integer")
        _require_positive(value, "prediction_unit_count")
        return value
    required_unit_ids = record.get("required_unit_ids")
    if not isinstance(required_unit_ids, Sequence) or isinstance(
        required_unit_ids,
        str,
    ):
        raise ValueError("required_unit_ids must be a sequence")
    count = len(cast(Sequence[object], required_unit_ids))
    _require_positive(count, "prediction_unit_count")
    return count


def _token_count(record: Mapping[str, Any], *, primary: str, fallback: str) -> int:
    if primary in record:
        return _required_int(record, primary)
    return _required_int(record, fallback)


def _total_tokens(record: Mapping[str, Any]) -> int:
    if "total_tokens" in record:
        return _required_int(record, "total_tokens")
    if "estimated_total_tokens" in record:
        return _required_int(record, "estimated_total_tokens")
    return _token_count(record, primary="prompt_tokens", fallback="input_tokens") + (
        _token_count(record, primary="completion_tokens", fallback="output_tokens")
    )


def _metadata_str(record: Mapping[str, Any], field_name: str) -> str | None:
    metadata_value = record.get("metadata")
    if metadata_value is None:
        return None
    if not isinstance(metadata_value, Mapping):
        raise ValueError("metadata must be an object")
    metadata = cast(Mapping[str, object], metadata_value)
    value = metadata.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"metadata[{field_name}] must be a non-empty string")
    return value


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso_datetime(value: datetime) -> str:
    return format_utc_iso_z(value)
