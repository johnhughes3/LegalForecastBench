"""Artifact projection helpers for LFB-native multi-harness runs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.multiharness.spec import ArtifactRecord, RunRequest, RunResult
from legalforecast.multiharness.validation import validate_public_record

_REQUIRED_STRING_FIELDS = (
    "sample_id",
    "candidate_id",
    "case_id",
    "solver_id",
    "solver_kind",
    "run_label",
    "ablation",
    "raw_output",
    "raw_output_sha256",
    "execution_backend",
)
_OPTIONAL_STRING_FIELDS = ("related_family_id", "mdl_family_id")


@dataclass(frozen=True, slots=True)
class AdapterRunResult:
    """Projected adapter row plus its public multi-harness result record."""

    inspect_record: Mapping[str, Any]
    result: RunResult

    def to_private_record(self) -> dict[str, Any]:
        return {
            "inspect_record": _json_object_clone(self.inspect_record),
            "result": self.result.to_record(),
        }


def community_model_id(adapter_id: str, model_key: str) -> str:
    """Return the stable community model identity for one adapter/model pair."""

    _require_non_empty(adapter_id, "adapter_id")
    _require_non_empty(model_key, "model_key")
    return f"{adapter_id}:{model_key}"


def project_lfb_adapter_record(
    record: Mapping[str, Any],
    request: RunRequest,
    *,
    artifacts: Sequence[ArtifactRecord] = (),
    latency_ms: float | int | None = None,
) -> AdapterRunResult:
    """Project one private LFB adapter row into inspect and public result records."""

    _require_lfb_request(request)
    projected = _json_object_clone(record)
    _pin_inspect_fields(projected, request=request, latency_ms=latency_ms)
    return AdapterRunResult(
        inspect_record=projected,
        result=_run_result_from_projected_record(
            projected,
            request=request,
            artifacts=artifacts,
        ),
    )


def _pin_inspect_fields(
    record: dict[str, Any],
    *,
    request: RunRequest,
    latency_ms: float | int | None,
) -> None:
    for field_name in _REQUIRED_STRING_FIELDS:
        record[field_name] = _required_str(record, field_name)
    for field_name in _OPTIONAL_STRING_FIELDS:
        record[field_name] = _optional_str(record, field_name)

    raw_output = _required_str(record, "raw_output")
    raw_output_sha256 = _required_str(record, "raw_output_sha256")
    expected_hash = _sha256_text(raw_output)
    if raw_output_sha256 != expected_hash:
        raise ValueError("raw_output_sha256 does not match raw_output")

    required_unit_ids = _required_str_sequence(record, "required_unit_ids")
    request_count = _required_non_negative_int(record, "request_count")
    input_tokens = _token_count(
        record,
        primary="input_tokens",
        fallback="prompt_tokens",
    )
    output_tokens = _token_count(
        record,
        primary="output_tokens",
        fallback="completion_tokens",
    )
    total_tokens = _total_tokens(record, input_tokens, output_tokens)
    estimated_cost = _required_non_negative_float(record, "estimated_cost")
    tool_call_logs = _tool_call_logs(record)

    metadata = _metadata(record)
    provider = _optional_str(record, "provider") or metadata.get("provider")
    provider_model_id = _optional_str(record, "model_id") or metadata.get("model_id")
    provider_version = _optional_str(
        record,
        "model_version_or_snapshot",
    ) or metadata.get("model_version_or_snapshot")
    model_identity = community_model_id(
        request.adapter.adapter_id,
        request.model_key,
    )

    record["required_unit_ids"] = list(required_unit_ids)
    record["request_count"] = request_count
    record["input_tokens"] = input_tokens
    record["prompt_tokens"] = input_tokens
    record["output_tokens"] = output_tokens
    record["completion_tokens"] = output_tokens
    record["estimated_total_tokens"] = total_tokens
    record["total_tokens"] = total_tokens
    record["estimated_cost"] = estimated_cost
    record["tool_call_logs"] = [dict(log) for log in tool_call_logs]
    record["adapter_id"] = request.adapter.adapter_id
    record["adapter_version"] = request.adapter.adapter_version
    record["model_key"] = request.model_key
    record["community_model_id"] = model_identity
    record["provider"] = provider or request.adapter.adapter_id
    record["model_id"] = model_identity
    record["model_version_or_snapshot"] = (
        provider_version or request.adapter.adapter_version
    )

    if provider is not None:
        metadata["provider"] = provider
    if provider_model_id is not None:
        metadata["provider_model_id"] = provider_model_id
    if provider_version is not None:
        metadata["provider_model_version_or_snapshot"] = provider_version
    metadata.update(
        {
            "adapter_id": request.adapter.adapter_id,
            "adapter_version": request.adapter.adapter_version,
            "model_key": request.model_key,
            "community_model_id": model_identity,
            "model_id": model_identity,
            "execution_backend": _required_str(record, "execution_backend"),
        }
    )
    record["metadata"] = dict(sorted(metadata.items()))

    if latency_ms is not None:
        record["latency_ms"] = _non_negative_number(latency_ms, "latency_ms")
    elif "latency_ms" in record:
        record["latency_ms"] = _non_negative_number(record["latency_ms"], "latency_ms")


def _run_result_from_projected_record(
    record: Mapping[str, Any],
    *,
    request: RunRequest,
    artifacts: Sequence[ArtifactRecord],
) -> RunResult:
    public_summary = {
        "adapter_id": _required_str(record, "adapter_id"),
        "adapter_version": _required_str(record, "adapter_version"),
        "model_key": _required_str(record, "model_key"),
        "community_model_id": _required_str(record, "community_model_id"),
        "provider": _required_str(record, "provider"),
        "model_id": _required_str(record, "model_id"),
        "model_version_or_snapshot": _required_str(
            record,
            "model_version_or_snapshot",
        ),
        "sample_id": _required_str(record, "sample_id"),
        "candidate_id": _required_str(record, "candidate_id"),
        "case_id": _required_str(record, "case_id"),
        "related_family_id": _optional_str(record, "related_family_id"),
        "mdl_family_id": _optional_str(record, "mdl_family_id"),
        "solver_id": _required_str(record, "solver_id"),
        "solver_kind": _required_str(record, "solver_kind"),
        "run_label": _required_str(record, "run_label"),
        "ablation": _required_str(record, "ablation"),
        "raw_output_sha256": _required_str(record, "raw_output_sha256"),
        "required_unit_ids": list(_required_str_sequence(record, "required_unit_ids")),
        "request_count": _required_non_negative_int(record, "request_count"),
        "input_tokens": _required_non_negative_int(record, "input_tokens"),
        "prompt_tokens": _required_non_negative_int(record, "prompt_tokens"),
        "output_tokens": _required_non_negative_int(record, "output_tokens"),
        "completion_tokens": _required_non_negative_int(
            record,
            "completion_tokens",
        ),
        "estimated_total_tokens": _required_non_negative_int(
            record,
            "estimated_total_tokens",
        ),
        "total_tokens": _required_non_negative_int(record, "total_tokens"),
        "estimated_cost": _required_non_negative_float(record, "estimated_cost"),
        "tool_call_count": len(_tool_call_logs(record)),
        "execution_backend": _required_str(record, "execution_backend"),
    }
    if "latency_ms" in record:
        public_summary["latency_ms"] = _non_negative_number(
            record["latency_ms"],
            "latency_ms",
        )
    validate_public_record(public_summary, "lfb_result.public_summary")
    return RunResult(
        result_id=_result_id(request, record),
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_record_sha256(record),
        artifacts=tuple(artifacts),
        public_summary=public_summary,
    )


def _require_lfb_request(request: RunRequest) -> None:
    if request.task.family != "legalforecast_mtd":
        raise ValueError("LFB projection requires legalforecast_mtd task family")
    if request.task.scoring_mode != "lfb_brier":
        raise ValueError("LFB projection requires lfb_brier scoring mode")
    if request.adapter.adapter_id != request.adapter.adapter_id.strip():
        raise ValueError("adapter_id must not have surrounding whitespace")


def _json_object_clone(record: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(dict(record), sort_keys=True))
    if not isinstance(value, dict):
        raise TypeError("record must serialize to a JSON object")
    return cast(dict[str, Any], value)


def _metadata(record: Mapping[str, Any]) -> dict[str, str]:
    value = record.get("metadata")
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be an object")
    metadata: dict[str, str] = {}
    typed_value = cast(Mapping[object, object], value)
    for key, item in typed_value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("metadata keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"metadata[{key}] must be a non-empty string")
        metadata[key] = item
    return metadata


def _tool_call_logs(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    value = record.get("tool_call_logs")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError("tool_call_logs must be an array")
    logs: list[Mapping[str, Any]] = []
    items = cast(Sequence[object], value)
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"tool_call_logs[{index}] must be an object")
        logs.append(cast(Mapping[str, Any], item))
    return tuple(logs)


def _result_id(request: RunRequest, record: Mapping[str, Any]) -> str:
    parts = (
        request.request_id,
        _required_str(record, "sample_id"),
        _required_str(record, "solver_id"),
        _required_str(record, "run_label"),
    )
    return ":".join(parts)


def _token_count(record: Mapping[str, Any], *, primary: str, fallback: str) -> int:
    if primary in record:
        return _required_non_negative_int(record, primary)
    return _required_non_negative_int(record, fallback)


def _total_tokens(
    record: Mapping[str, Any],
    input_tokens: int,
    output_tokens: int,
) -> int:
    expected = input_tokens + output_tokens
    if "total_tokens" in record:
        total_tokens = _required_non_negative_int(record, "total_tokens")
    elif "estimated_total_tokens" in record:
        total_tokens = _required_non_negative_int(record, "estimated_total_tokens")
    else:
        total_tokens = expected
    if total_tokens != expected:
        raise ValueError("total_tokens must equal prompt + completion tokens")
    return total_tokens


def _required_str_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{field_name} must be an array")
    values: list[str] = []
    items = cast(Sequence[object], value)
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        values.append(item)
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")
    return tuple(values)


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _optional_str(record, field_name)
    if value is None:
        raise ValueError(f"{field_name} is required")
    return value


def _required_non_negative_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _required_non_negative_float(record: Mapping[str, Any], field_name: str) -> float:
    return _non_negative_number(record.get(field_name), field_name)


def _non_negative_number(value: object, field_name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number")
    float_value = float(value)
    if not math.isfinite(float_value):
        raise ValueError(f"{field_name} must be finite")
    return float_value


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
