"""Shared strict Anthropic JSON/SSE usage normalization for gateway accounting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class AnthropicGatewayUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


def anthropic_gateway_usage(
    body: bytes,
    content_type: str | None,
) -> AnthropicGatewayUsage | None:
    candidates: list[Mapping[str, object]]
    if content_type and content_type.lower().startswith("text/event-stream"):
        candidates = []
        for line in body.splitlines():
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == b"[DONE]":
                continue
            try:
                event = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            if not isinstance(event, Mapping):
                return None
            event_mapping = cast(Mapping[str, object], event)
            message = event_mapping.get("message")
            if isinstance(message, Mapping):
                message_mapping = cast(Mapping[str, object], message)
                usage = message_mapping.get("usage")
                if isinstance(usage, Mapping):
                    candidates.append(cast(Mapping[str, object], usage))
            usage = event_mapping.get("usage")
            if isinstance(usage, Mapping):
                candidates.append(cast(Mapping[str, object], usage))
    else:
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, Mapping):
            return None
        value_mapping = cast(Mapping[str, object], value)
        usage = value_mapping.get("usage")
        if not isinstance(usage, Mapping):
            message = value_mapping.get("message")
            if isinstance(message, Mapping):
                message_mapping = cast(Mapping[str, object], message)
                usage = message_mapping.get("usage")
            else:
                usage = None
        if not isinstance(usage, Mapping):
            return None
        candidates = [cast(Mapping[str, object], usage)]
    if not candidates:
        return None

    input_tokens = _consistent_usage_value(candidates, "input_tokens")
    cache_read_tokens = _consistent_usage_value(
        candidates,
        "cache_read_input_tokens",
    )
    cache_write_tokens = _consistent_usage_value(
        candidates,
        "cache_creation_input_tokens",
    )
    output_values: list[int] = []
    for candidate in candidates:
        if "output_tokens" not in candidate:
            continue
        value = _usage_value(candidate, "output_tokens")
        if value is None:
            return None
        output_values.append(value)
    output_tokens = output_values[-1] if output_values else None
    if (
        input_tokens is None
        or output_tokens is None
        or cache_read_tokens is None
        or cache_write_tokens is None
    ):
        return None
    return AnthropicGatewayUsage(
        # Anthropic reports ``input_tokens`` as the uncached portion.  The
        # managed cost helper expects its input dimension to include both
        # cache buckets, so normalize the provider response at this seam.
        input_tokens=input_tokens + cache_read_tokens + cache_write_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def _consistent_usage_value(
    candidates: list[Mapping[str, object]],
    field_name: str,
) -> int | None:
    values: list[int] = []
    for candidate in candidates:
        if field_name not in candidate:
            continue
        value = _usage_value(candidate, field_name)
        if value is None:
            return None
        values.append(value)
    if not values or any(value != values[0] for value in values[1:]):
        return None
    return values[0]


def _usage_value(candidate: Mapping[str, object], field_name: str) -> int | None:
    value = candidate.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
