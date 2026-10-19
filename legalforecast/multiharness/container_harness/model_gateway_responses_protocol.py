"""Strict local-tool request and terminal-usage rules for Responses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, cast

from .model_gateway_types import (
    GatewayBudgetExceeded,
    ModelGatewayError,
    ObservedUsage,
)

OPENAI_PROVIDER: Final[str] = "openai"
_LOCAL_TOOL_TYPES: Final[frozenset[str]] = frozenset(
    {"custom", "function", "namespace"}
)
_REMOTE_TOOL_TYPE_PREFIXES: Final[tuple[str, ...]] = (
    "computer",
    "file_search",
    "mcp",
    "web_search",
)
_TERMINAL_EVENT_KINDS: Final[
    dict[str, Literal["completed", "failed", "incomplete"]]
] = {
    "response.completed": "completed",
    "response.failed": "failed",
    "response.incomplete": "incomplete",
}


@dataclass(frozen=True, slots=True)
class ResponsesUsage:
    """Usage dimensions needed for settlement and cache-aware diagnostics."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None

    def as_observed(self) -> ObservedUsage:
        """Project provider usage onto the shared gateway accounting shape."""

        return ObservedUsage(self.input_tokens, self.output_tokens)


@dataclass(frozen=True, slots=True)
class ResponsesTerminal:
    """One unambiguous terminal Responses result and any reported usage."""

    kind: Literal["completed", "failed", "incomplete"]
    usage: ResponsesUsage | None
    service_tier: str | None


def validate_responses_request(
    payload: Mapping[str, object],
    *,
    allowed_models: frozenset[str],
    max_output_tokens: int,
    allowed_service_tiers: frozenset[str],
) -> tuple[str, int, str]:
    """Validate the bounded fields that select spend or remote capabilities."""

    raw_model = payload.get("model")
    if not isinstance(raw_model, str) or raw_model not in allowed_models:
        raise ModelGatewayError("model is not allowlisted")
    raw_max_output = payload.get("max_output_tokens", max_output_tokens)
    if type(raw_max_output) is not int or raw_max_output <= 0:
        raise ModelGatewayError("max_output_tokens must be a positive integer")
    if raw_max_output > max_output_tokens:
        raise GatewayBudgetExceeded("max_output_tokens exceeds per-request limit")
    stream = payload.get("stream")
    if stream is not None and type(stream) is not bool:
        raise ModelGatewayError("stream must be a boolean")
    if payload.get("store") is not False:
        raise ModelGatewayError("store=false is required")
    if len(allowed_service_tiers) != 1:
        raise ModelGatewayError("exactly one priced service_tier is required")
    priced_service_tier = next(iter(allowed_service_tiers))
    service_tier = payload.get("service_tier", priced_service_tier)
    if not isinstance(service_tier, str) or service_tier not in allowed_service_tiers:
        raise ModelGatewayError("service_tier is not priced by the locked registry")
    _validate_local_tools(payload.get("tools"))
    if _contains_remote_input_url(payload.get("input")):
        raise ModelGatewayError("remote input URLs are disabled")
    return raw_model, raw_max_output, service_tier


def parse_responses_usage(
    body: bytes,
    content_type: str | None,
) -> ResponsesUsage | None:
    """Extract usage from one unambiguous terminal Responses result."""

    terminal = parse_responses_terminal(body, content_type)
    return None if terminal is None else terminal.usage


def parse_responses_terminal(
    body: bytes,
    content_type: str | None,
) -> ResponsesTerminal | None:
    """Classify exactly one terminal result; ambiguity remains unknown."""

    if content_type is not None and content_type.lower().startswith(
        "text/event-stream"
    ):
        events = _sse_data_objects(body)
        if events is None:
            return None
        terminals: list[ResponsesTerminal] = []
        for raw_event in events:
            event_type = raw_event.get("type")
            if not isinstance(event_type, str):
                continue
            kind = _TERMINAL_EVENT_KINDS.get(event_type)
            if kind is None:
                continue
            response = raw_event.get("response")
            if not isinstance(response, Mapping):
                return None
            terminal = _terminal_from_response(
                cast(Mapping[str, object], response), kind=kind
            )
            if terminal is None:
                return None
            terminals.append(terminal)
        return terminals[0] if len(terminals) == 1 else None
    try:
        payload: object = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    response = cast(Mapping[str, object], payload)
    raw_status = response.get("status")
    if raw_status not in {"completed", "failed", "incomplete"}:
        return None
    return _terminal_from_response(response, kind=cast(str, raw_status))


def _usage_from_object(value: object) -> ResponsesUsage | None:
    if not isinstance(value, Mapping):
        return None
    payload = cast(Mapping[str, object], value)
    raw_usage_value = payload.get("usage")
    if not isinstance(raw_usage_value, Mapping):
        return None
    raw_usage = cast(Mapping[str, object], raw_usage_value)
    input_tokens = _nonnegative_int(raw_usage.get("input_tokens"))
    output_tokens = _nonnegative_int(raw_usage.get("output_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    raw_input_details_value = raw_usage.get("input_tokens_details")
    if raw_input_details_value is not None:
        if not isinstance(raw_input_details_value, Mapping):
            return None
        raw_input_details = cast(Mapping[str, object], raw_input_details_value)
        if "cached_tokens" in raw_input_details:
            cache_read_tokens = _nonnegative_int(raw_input_details.get("cached_tokens"))
            if cache_read_tokens is None:
                return None
        if "cache_write_tokens" in raw_input_details:
            cache_write_tokens = _nonnegative_int(
                raw_input_details.get("cache_write_tokens")
            )
            if cache_write_tokens is None:
                return None
        if (cache_read_tokens or 0) + (cache_write_tokens or 0) > input_tokens:
            return None
    reasoning_tokens: int | None = None
    raw_output_details_value = raw_usage.get("output_tokens_details")
    if raw_output_details_value is not None:
        if not isinstance(raw_output_details_value, Mapping):
            return None
        raw_output_details = cast(Mapping[str, object], raw_output_details_value)
        if "reasoning_tokens" in raw_output_details:
            reasoning_tokens = _nonnegative_int(
                raw_output_details.get("reasoning_tokens")
            )
            if reasoning_tokens is None:
                return None
    return ResponsesUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def _terminal_from_response(
    response: Mapping[str, object],
    *,
    kind: str,
) -> ResponsesTerminal | None:
    if kind not in {"completed", "failed", "incomplete"}:
        return None
    embedded_status = response.get("status")
    if embedded_status is not None and embedded_status != kind:
        return None
    return ResponsesTerminal(
        kind=cast(Literal["completed", "failed", "incomplete"], kind),
        usage=_usage_from_object(response),
        service_tier=_service_tier_from_response(response),
    )


def _service_tier_from_response(response: Mapping[str, object]) -> str | None:
    value = response.get("service_tier")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _sse_data_objects(body: bytes) -> tuple[Mapping[str, object], ...] | None:
    events: list[Mapping[str, object]] = []
    for line in body.splitlines():
        if not line.startswith(b"data:"):
            continue
        raw_data = line[5:].strip()
        if not raw_data or raw_data == b"[DONE]":
            continue
        try:
            event: object = json.loads(raw_data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(event, Mapping):
            return None
        events.append(cast(Mapping[str, object], event))
    return tuple(events)


def _validate_local_tools(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise ModelGatewayError("tools must be an array")
    for tool in cast(list[object], value):
        _validate_local_tool(tool, allow_namespace=True)


def _validate_local_tool(value: object, *, allow_namespace: bool) -> None:
    if not isinstance(value, Mapping):
        raise ModelGatewayError("tool definitions must be objects")
    tool = cast(Mapping[str, object], value)
    tool_type = tool.get("type")
    if not isinstance(tool_type, str):
        raise ModelGatewayError("tool type must be a string")
    normalized = tool_type.casefold()
    if any(normalized.startswith(prefix) for prefix in _REMOTE_TOOL_TYPE_PREFIXES):
        raise ModelGatewayError("hosted or remote tools are disabled")
    if normalized not in _LOCAL_TOOL_TYPES or (
        normalized == "namespace" and not allow_namespace
    ):
        raise ModelGatewayError("tool type is not an allowlisted local definition")
    name = tool.get("name")
    if not isinstance(name, str) or not name.strip() or "\n" in name or "\r" in name:
        raise ModelGatewayError("local tool name must be a nonempty single line")
    if normalized == "function":
        if not isinstance(tool.get("parameters"), Mapping):
            raise ModelGatewayError("function tool parameters must be an object")
        strict = tool.get("strict")
        if strict is not None and type(strict) is not bool:
            raise ModelGatewayError("function tool strict must be a boolean")
    elif normalized == "custom":
        format_value = tool.get("format")
        if format_value is not None and not isinstance(format_value, Mapping):
            raise ModelGatewayError("custom tool format must be an object")
    else:
        nested = tool.get("tools")
        if not isinstance(nested, list) or not nested:
            raise ModelGatewayError("namespace tools must be a nonempty array")
        for nested_tool in cast(list[object], nested):
            _validate_local_tool(nested_tool, allow_namespace=False)


def _contains_remote_input_url(value: object, *, field_name: str | None = None) -> bool:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return any(
            _contains_remote_input_url(item, field_name=str(name))
            for name, item in mapping.items()
        )
    if isinstance(value, list):
        return any(
            _contains_remote_input_url(item) for item in cast(list[object], value)
        )
    if not isinstance(value, str) or field_name is None:
        return False
    normalized = field_name.casefold()
    return (
        normalized == "url" or normalized.endswith("_url")
    ) and value.lower().startswith(("http://", "https://"))


def _nonnegative_int(value: object) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


__all__ = [
    "OPENAI_PROVIDER",
    "ResponsesTerminal",
    "ResponsesUsage",
    "parse_responses_terminal",
    "parse_responses_usage",
    "validate_responses_request",
]
