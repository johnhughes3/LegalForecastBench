"""Versioned JSON Lines protocol for host-owned container tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Self, cast

from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    TOOL_RESPONSE_SCHEMA_VERSION,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    optional_mapping,
    optional_str,
    require_schema_version,
    require_str,
    validate_safe_relative_path,
)

MAX_TOOL_MESSAGE_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """One bounded operation sent to a network-disabled tool container."""

    request_id: str
    operation: str
    arguments: Mapping[str, Any] = field(
        default_factory=lambda: cast(Mapping[str, Any], {})
    )
    input_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, "request_id")
        _require_identifier(self.operation, "operation")
        for index, path in enumerate(self.input_paths):
            validate_safe_relative_path(path, f"input_paths[{index}]")
        _validate_json_value(dict(self.arguments), "arguments")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": TOOL_REQUEST_SCHEMA_VERSION,
            "request_id": self.request_id,
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "input_paths": list(self.input_paths),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, TOOL_REQUEST_SCHEMA_VERSION)
        raw_paths = cast(object, record.get("input_paths", []))
        if not isinstance(raw_paths, list):
            raise MultiHarnessValidationError("input_paths must be an array of strings")
        paths: list[str] = []
        for raw_path in cast(list[object], raw_paths):
            if not isinstance(raw_path, str):
                raise MultiHarnessValidationError(
                    "input_paths must be an array of strings"
                )
            paths.append(raw_path)
        return cls(
            request_id=require_str(record, "request_id"),
            operation=require_str(record, "operation"),
            arguments=optional_mapping(record, "arguments") or {},
            input_paths=tuple(paths),
        )


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """One structured response returned by a tool container."""

    request_id: str
    status: str
    output: Mapping[str, Any] = field(
        default_factory=lambda: cast(Mapping[str, Any], {})
    )
    error_code: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, "request_id")
        if self.status not in {"succeeded", "failed"}:
            raise MultiHarnessValidationError("status must be succeeded or failed")
        if self.status == "succeeded" and self.error_code is not None:
            raise MultiHarnessValidationError(
                "successful tool responses must not include error_code"
            )
        if self.status == "failed" and self.error_code is None:
            raise MultiHarnessValidationError(
                "failed tool responses must include error_code"
            )
        if self.error_code is not None:
            _require_identifier(self.error_code, "error_code")
        _validate_json_value(dict(self.output), "output")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_id": self.request_id,
            "status": self.status,
            "output": dict(self.output),
        }
        if self.error_code is not None:
            record["error_code"] = self.error_code
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, TOOL_RESPONSE_SCHEMA_VERSION)
        return cls(
            request_id=require_str(record, "request_id"),
            status=require_str(record, "status"),
            output=optional_mapping(record, "output") or {},
            error_code=optional_str(record, "error_code"),
        )


def encode_tool_message(message: ToolRequest | ToolResponse) -> bytes:
    """Serialize one protocol message as a bounded UTF-8 JSON line."""

    encoded = (json.dumps(message.to_record(), sort_keys=True) + "\n").encode()
    if len(encoded) > MAX_TOOL_MESSAGE_BYTES:
        raise MultiHarnessValidationError("tool message exceeds maximum size")
    return encoded


def decode_tool_request(data: bytes) -> ToolRequest:
    """Decode exactly one bounded request line."""

    return ToolRequest.from_record(_decode_json_line(data))


def decode_tool_response(data: bytes) -> ToolResponse:
    """Decode exactly one bounded response line."""

    return ToolResponse.from_record(_decode_json_line(data))


def _decode_json_line(data: bytes) -> Mapping[str, Any]:
    if len(data) > MAX_TOOL_MESSAGE_BYTES:
        raise MultiHarnessValidationError("tool message exceeds maximum size")
    if not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise MultiHarnessValidationError("tool message must be exactly one JSON line")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MultiHarnessValidationError(
            "tool message must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise MultiHarnessValidationError("tool message must be a JSON object")
    return cast(Mapping[str, Any], value)


def _require_identifier(value: str, field_name: str) -> None:
    if not value.strip() or any(character.isspace() for character in value):
        raise MultiHarnessValidationError(
            f"{field_name} must be a non-empty identifier without whitespace"
        )


def _validate_json_value(value: Any, field_name: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise MultiHarnessValidationError(
            f"{field_name} must be JSON-compatible"
        ) from exc
