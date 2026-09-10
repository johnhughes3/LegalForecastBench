"""Provider response usage normalization for the managed runner."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import cast

from pydantic_ai import ModelResponse

from legalforecast.runner.ledger import RunValidationError
from legalforecast.runner.managed_cost import (
    ManagedResponseUsage,
    ManagedToolAgentError,
)


def _response_thoughts_tokens(response: ModelResponse) -> int:
    """Return Gemini reasoning tokens retained in PydanticAI usage details."""

    value = cast(object, response.usage.details.get("thoughts_tokens", 0))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManagedToolAgentError(
            "provider response has invalid thoughts token usage"
        )
    return value


def _response_reasoning_tokens(response: ModelResponse) -> int | None:
    """Normalize provider reasoning dimensions without counting them twice."""

    details = response.usage.details
    values = [
        _optional_usage_detail_int(details, field_name)
        for field_name in ("reasoning_tokens", "thoughts_tokens", "thinking_tokens")
    ]
    reported = {value for value in values if value is not None}
    if len(reported) > 1:
        raise ManagedToolAgentError(
            "provider response reports conflicting reasoning token fields"
        )
    return next(iter(reported), None)


def _optional_usage_detail_int(
    details: Mapping[str, object], field_name: str
) -> int | None:
    value = details.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManagedToolAgentError(f"provider response has invalid {field_name} usage")
    return value


def _managed_response_usage(response: ModelResponse) -> ManagedResponseUsage:
    """Project one SDK response onto the shared normalized usage shape."""

    usage = response.usage
    return ManagedResponseUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=_optional_usage_field(usage, "cache_read_tokens"),
        cache_write_tokens=_optional_usage_field(usage, "cache_write_tokens"),
        reasoning_tokens=_response_reasoning_tokens(response),
    )


def _optional_usage_field(usage: object, field_name: str) -> int | None:
    value = getattr(usage, field_name, None)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"provider response has invalid {field_name} usage")
    return value


def _managed_optional_response_usage_details(
    payload: Mapping[str, object],
) -> tuple[ManagedResponseUsage, ...]:
    """Read optional normalized usage rows from a replay payload."""

    raw = payload.get("response_usage_details")
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise RunValidationError("managed response usage details are invalid")
    details: list[ManagedResponseUsage] = []
    for row in cast(Sequence[object], raw):
        if not isinstance(row, Mapping):
            raise RunValidationError("managed response usage detail is invalid")
        row = cast(Mapping[str, object], row)
        try:
            details.append(
                ManagedResponseUsage(
                    input_tokens=_required_int(row, "input_tokens"),
                    output_tokens=_required_int(row, "output_tokens"),
                    cache_read_tokens=_managed_optional_nullable_int(
                        row, "cache_read_tokens"
                    ),
                    cache_write_tokens=_managed_optional_nullable_int(
                        row, "cache_write_tokens"
                    ),
                    reasoning_tokens=_managed_optional_nullable_int(
                        row, "reasoning_tokens"
                    ),
                )
            )
        except ValueError as exc:
            raise RunValidationError(
                "managed response usage detail is invalid"
            ) from exc
    return tuple(details)


def _managed_optional_nullable_int(
    payload: Mapping[str, object], field_name: str
) -> int | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"managed response field is invalid: {field_name}")
    return value


def _managed_optional_str(payload: Mapping[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


def _managed_required_str(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


def _required_int(
    payload: Mapping[str, object], field_name: str, *, positive: bool = False
) -> int:
    value = payload.get(field_name)
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


def _managed_required_float(payload: Mapping[str, object], field_name: str) -> float:
    value = payload.get(field_name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return float(value)


def _managed_optional_int(payload: Mapping[str, object], field_name: str) -> int:
    """Read an optional non-negative integer for replay compatibility."""

    value = payload.get(field_name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RunValidationError(f"managed response field is invalid: {field_name}")
    return value


# Public aliases let the runner import these helpers without private-import
# diagnostics while the underscored names preserve existing module callers.
managed_optional_int = _managed_optional_int
managed_optional_response_usage_details = _managed_optional_response_usage_details
managed_optional_str = _managed_optional_str
managed_required_float = _managed_required_float
managed_required_int = _required_int
managed_required_str = _managed_required_str
managed_response_usage = _managed_response_usage
response_thoughts_tokens = _response_thoughts_tokens
