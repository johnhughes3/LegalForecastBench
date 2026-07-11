"""Response-side verification for live benchmark provider payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.evals.accounting import OutputValidityStatus
from legalforecast.evals.output_parser import ParserStatus, parse_model_output

RESPONSE_VERIFICATION_SCHEMA_VERSION = "legalforecast.response_verification.v1"
RESPONSE_VERIFICATION_SCHEMA_FIELD = "response_verification_schema_version"
RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD = "response_grounding_artifacts_detected"
RESPONSE_GROUNDING_ARTIFACT_PATHS_FIELD = "response_grounding_artifact_paths"
RESPONSE_FINISH_REASON_FIELD = "response_finish_reason"
RESPONSE_TRUNCATED_FIELD = "response_truncated"
RESPONSE_RETRYABLE_OPS_EVENT_FIELD = "response_retryable_ops_event"
RESPONSE_RETRYABLE_OPS_EVENT_REASON_FIELD = "response_retryable_ops_event_reason"
RESPONSE_CONTENT_FILTER_FIELD = "response_content_filter"

_NO_VALUE = "none"
_UNREPORTED_FINISH_REASON = "unreported"
_GROUNDING_ARTIFACT_KEYS = frozenset(
    {
        "groundingMetadata",
        "grounding_metadata",
        "groundingChunks",
        "grounding_chunks",
        "groundingSupports",
        "grounding_supports",
        "web_search_call",
        "web_search_calls",
        "server_tool_use",
    }
)
_GROUNDING_TYPE_VALUES = frozenset({"web_search_call", "server_tool_use"})
_FINISH_REASON_KEYS = frozenset(
    {
        "finish_reason",
        "finishReason",
        "stop_reason",
        "blockReason",
    }
)
_TRUNCATED_REASON_TOKENS = frozenset(
    {
        "length",
        "max_token",
        "max_tokens",
        "max_output_token",
        "max_output_tokens",
        "token_limit",
    }
)
_CONTENT_FILTER_REASON_TOKENS = frozenset(
    {
        "content_filter",
        "safety",
        "blocked",
        "blocklist",
        "prohibited_content",
    }
)


@dataclass(frozen=True, slots=True)
class ResponseVerification:
    """Response-side checks derived from the raw provider payload."""

    grounding_artifact_paths: tuple[str, ...]
    finish_reason: str | None = None
    truncated: bool = False
    content_filter: bool = False

    @property
    def grounding_artifacts_detected(self) -> bool:
        return bool(self.grounding_artifact_paths)

    @property
    def retryable_ops_event(self) -> bool:
        return self.truncated

    @property
    def retryable_ops_event_reason(self) -> str | None:
        if not self.retryable_ops_event:
            return None
        if self.finish_reason is None:
            return "response_truncated"
        return f"response_truncated:{self.finish_reason}"

    def to_metadata(self) -> dict[str, str]:
        """Return non-empty string metadata safe for SolverResponse."""

        return {
            RESPONSE_VERIFICATION_SCHEMA_FIELD: RESPONSE_VERIFICATION_SCHEMA_VERSION,
            RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD: _bool_text(
                self.grounding_artifacts_detected
            ),
            RESPONSE_GROUNDING_ARTIFACT_PATHS_FIELD: json.dumps(
                list(self.grounding_artifact_paths),
                separators=(",", ":"),
            ),
            RESPONSE_FINISH_REASON_FIELD: self.finish_reason
            or _UNREPORTED_FINISH_REASON,
            RESPONSE_TRUNCATED_FIELD: _bool_text(self.truncated),
            RESPONSE_RETRYABLE_OPS_EVENT_FIELD: _bool_text(self.retryable_ops_event),
            RESPONSE_RETRYABLE_OPS_EVENT_REASON_FIELD: (
                self.retryable_ops_event_reason or _NO_VALUE
            ),
            RESPONSE_CONTENT_FILTER_FIELD: _bool_text(self.content_filter),
        }


def verify_provider_response(
    payload: Mapping[str, object],
    *,
    provider: str,
) -> ResponseVerification:
    """Scan one provider response for prohibited grounding and finish status."""

    finish_reason = _finish_reason(payload, provider=provider)
    return ResponseVerification(
        grounding_artifact_paths=_grounding_artifact_paths(payload),
        finish_reason=finish_reason,
        truncated=_is_truncated_finish_reason(finish_reason),
        content_filter=_is_content_filter_finish_reason(finish_reason),
    )


def output_statuses_from_run_records(
    run_records: Sequence[Mapping[str, Any]],
) -> dict[str, OutputValidityStatus]:
    """Derive raw-output accounting status from parser and response metadata."""

    statuses: dict[str, OutputValidityStatus] = {}
    for record in run_records:
        raw_output = _required_str(record, "raw_output")
        required_unit_ids = _required_str_tuple(record, "required_unit_ids")
        parsed = parse_model_output(raw_output, required_unit_ids=required_unit_ids)
        metadata = _metadata(record)
        if _metadata_bool(metadata, RESPONSE_RETRYABLE_OPS_EVENT_FIELD):
            statuses[parsed.raw_output_sha256] = OutputValidityStatus(
                retryable_ops_event=True,
                retryable_ops_event_reason=(
                    _metadata_optional_reason(
                        metadata,
                        RESPONSE_RETRYABLE_OPS_EVENT_REASON_FIELD,
                    )
                    or "retryable_response_event"
                ),
            )
            continue
        if _metadata_bool(metadata, RESPONSE_CONTENT_FILTER_FIELD):
            statuses[parsed.raw_output_sha256] = OutputValidityStatus(
                invalid_output=True,
                content_filter=True,
                invalid_output_reason="content_filter",
            )
            continue
        first_issue = parsed.issues[0].code.value if parsed.issues else None
        statuses[parsed.raw_output_sha256] = OutputValidityStatus(
            invalid_output=parsed.invalid_output,
            refusal=parsed.status is ParserStatus.REFUSAL,
            content_filter=False,
            invalid_output_reason=first_issue if parsed.invalid_output else None,
        )
    return statuses


def response_verification_summary_from_run_records(
    run_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize response verification flags for a per-case run card."""

    grounding_paths: set[str] = set()
    finish_reasons: set[str] = set()
    grounding_count = 0
    truncated_count = 0
    retryable_count = 0
    content_filter_count = 0
    for record in run_records:
        metadata = _metadata(record)
        if _metadata_bool(metadata, RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD):
            grounding_count += 1
            grounding_paths.update(
                _metadata_str_list(
                    metadata,
                    RESPONSE_GROUNDING_ARTIFACT_PATHS_FIELD,
                )
            )
        finish_reason = _metadata_text(metadata, RESPONSE_FINISH_REASON_FIELD)
        if finish_reason is not None and finish_reason != _UNREPORTED_FINISH_REASON:
            finish_reasons.add(finish_reason)
        if _metadata_bool(metadata, RESPONSE_TRUNCATED_FIELD):
            truncated_count += 1
        if _metadata_bool(metadata, RESPONSE_RETRYABLE_OPS_EVENT_FIELD):
            retryable_count += 1
        if _metadata_bool(metadata, RESPONSE_CONTENT_FILTER_FIELD):
            content_filter_count += 1
    return {
        "schema_version": RESPONSE_VERIFICATION_SCHEMA_VERSION,
        "grounding_artifacts_detected": grounding_count > 0,
        "grounding_artifact_response_count": grounding_count,
        "grounding_artifact_paths": sorted(grounding_paths),
        "finish_reasons": sorted(finish_reasons),
        "truncated_response_count": truncated_count,
        "retryable_ops_event_count": retryable_count,
        "content_filter_count": content_filter_count,
    }


def _finish_reason(
    payload: Mapping[str, object],
    *,
    provider: str,
) -> str | None:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai":
        incomplete_reason = _openai_incomplete_reason(payload)
        if incomplete_reason is not None:
            return incomplete_reason
    return _first_string_value_for_keys(payload, _FINISH_REASON_KEYS)


def _openai_incomplete_reason(payload: Mapping[str, object]) -> str | None:
    if payload.get("status") != "incomplete":
        return None
    details = _mapping(payload.get("incomplete_details"))
    if details is None:
        return None
    reason = details.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def _grounding_artifact_paths(payload: Mapping[str, object]) -> tuple[str, ...]:
    paths: set[str] = set()
    _collect_grounding_artifact_paths(payload, "$", paths)
    return tuple(sorted(paths))


def _collect_grounding_artifact_paths(
    value: object,
    path: str,
    paths: set[str],
) -> None:
    if isinstance(value, Mapping):
        for raw_key, raw_child in cast(Mapping[object, object], value).items():
            key_path = _child_path(path, raw_key)
            if isinstance(raw_key, str):
                if raw_key in _GROUNDING_ARTIFACT_KEYS and _has_meaningful_value(
                    raw_child
                ):
                    paths.add(key_path)
                if (
                    raw_key == "type"
                    and isinstance(raw_child, str)
                    and raw_child in _GROUNDING_TYPE_VALUES
                ):
                    paths.add(f"{key_path}={raw_child}")
            _collect_grounding_artifact_paths(raw_child, key_path, paths)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, item in enumerate(cast(Sequence[object], value)):
            _collect_grounding_artifact_paths(item, f"{path}[{index}]", paths)


def _has_meaningful_value(value: object) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str | bytes):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(cast(Mapping[object, object], value))
    if isinstance(value, Sequence):
        return bool(cast(Sequence[object], value))
    return True


def _first_string_value_for_keys(
    value: object,
    keys: frozenset[str],
) -> str | None:
    if isinstance(value, Mapping):
        for raw_key, raw_child in cast(Mapping[object, object], value).items():
            if isinstance(raw_key, str) and raw_key in keys:
                if isinstance(raw_child, str) and raw_child.strip():
                    return raw_child.strip()
            nested = _first_string_value_for_keys(raw_child, keys)
            if nested is not None:
                return nested
        return None
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for item in cast(Sequence[object], value):
            nested = _first_string_value_for_keys(item, keys)
            if nested is not None:
                return nested
    return None


def _is_truncated_finish_reason(finish_reason: str | None) -> bool:
    if finish_reason is None:
        return False
    normalized = _normalized_reason(finish_reason)
    return normalized in _TRUNCATED_REASON_TOKENS or (
        "token" in normalized and ("max" in normalized or "limit" in normalized)
    )


def _is_content_filter_finish_reason(finish_reason: str | None) -> bool:
    if finish_reason is None:
        return False
    normalized = _normalized_reason(finish_reason)
    return normalized in _CONTENT_FILTER_REASON_TOKENS or any(
        token in normalized for token in _CONTENT_FILTER_REASON_TOKENS
    )


def _normalized_reason(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _metadata(record: Mapping[str, Any]) -> Mapping[str, str]:
    raw_metadata = record.get("metadata")
    if raw_metadata is None:
        return {}
    if not isinstance(raw_metadata, Mapping):
        raise ValueError("metadata must be an object")
    metadata = cast(Mapping[object, object], raw_metadata)
    normalized: dict[str, str] = {}
    for raw_key, raw_value in metadata.items():
        if not isinstance(raw_key, str):
            raise ValueError("metadata keys must be strings")
        if not isinstance(raw_value, str):
            raise ValueError(f"metadata[{raw_key}] must be a string")
        normalized[raw_key] = raw_value
    return normalized


def _metadata_bool(metadata: Mapping[str, str], field_name: str) -> bool:
    value = metadata.get(field_name)
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"metadata[{field_name}] must be true or false")


def _metadata_text(
    metadata: Mapping[str, str],
    field_name: str,
) -> str | None:
    value = metadata.get(field_name)
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError(f"metadata[{field_name}] must be non-empty")
    return text


def _metadata_optional_reason(
    metadata: Mapping[str, str],
    field_name: str,
) -> str | None:
    value = _metadata_text(metadata, field_name)
    if value is None or value == _NO_VALUE:
        return None
    return value


def _metadata_str_list(
    metadata: Mapping[str, str],
    field_name: str,
) -> tuple[str, ...]:
    value = metadata.get(field_name)
    if value is None:
        return ()
    loaded: object = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError(f"metadata[{field_name}] must be a JSON list")
    loaded_items = cast(list[object], loaded)
    items: list[str] = []
    for index, item in enumerate(loaded_items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"metadata[{field_name}][{index}] must be a non-empty string"
            )
        items.append(item)
    return tuple(items)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_str_tuple(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{field_name} must be a sequence")
    items: list[str] = []
    for index, item in enumerate(cast(Sequence[object], value)):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        items.append(item)
    if not items:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(items)


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None


def _child_path(parent: str, key: object) -> str:
    if isinstance(key, str) and key.replace("_", "").isalnum():
        return f"{parent}.{key}"
    return f"{parent}[{key!r}]"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
