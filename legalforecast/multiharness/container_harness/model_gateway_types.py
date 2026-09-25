"""Shared errors and immutable values for the model gateway."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class ModelGatewayError(ValueError):
    """Raised when a gateway policy or request contract is invalid."""


class GatewayBudgetExceeded(ModelGatewayError):
    """Raised when a request cannot fit inside the run's remaining budget."""


class GatewayAuthenticationError(ModelGatewayError):
    """Raised when the harness lacks the run capability."""


class GatewayUpstreamError(RuntimeError):
    """Raised when the fixed upstream cannot return a bounded response."""


class GatewayEvidenceError(RuntimeError):
    """Raised when durable usage evidence cannot be updated."""


@dataclass(frozen=True, slots=True)
class GatewayUsageSnapshot:
    """Thread-safe public usage state for one gateway."""

    request_count: int
    input_tokens: int
    output_tokens: int
    reserved_input_tokens: int
    reserved_output_tokens: int
    rejected_count: int
    observed_input_tokens: int | None
    observed_output_tokens: int | None


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """A bounded response returned by the gateway protocol handler."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class Reservation:
    """Worst-case accounting reservation for one accepted request."""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class ObservedUsage:
    """Usage reported by an upstream response, with missing dimensions unknown."""

    input_tokens: int | None
    output_tokens: int | None


__all__ = [
    "GatewayAuthenticationError",
    "GatewayBudgetExceeded",
    "GatewayEvidenceError",
    "GatewayResponse",
    "GatewayUpstreamError",
    "GatewayUsageSnapshot",
    "ModelGatewayError",
    "ObservedUsage",
    "Reservation",
]
