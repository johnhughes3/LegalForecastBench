"""A bounded OpenAI Responses protocol gateway for native Codex runs.

The official Codex Responses proxy establishes the correct wire seam: accept
only ``POST /v1/responses``, keep the provider key in the privileged proxy, and
forward the response bytes unchanged. This module adds the LFB-specific
boundaries that proxy does not provide: a fixed OpenAI origin, a per-run
capability, an exact OpenAI model allowlist, and the existing reservation and
durable spend-controller contract.

The gateway deliberately does not implement an agent loop or translate
Responses events. It buffers one bounded upstream body so usage can be
settled before the caller receives it, then returns the body and content type
unchanged. A streaming Responses body therefore remains an exact SSE stream
to Codex, with settlement occurring before delivery rather than after the
last event has already escaped the accounting boundary.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from pathlib import Path
from typing import Final, Protocol, cast
from urllib.parse import SplitResult, urlsplit

from .model_gateway_accounting import GatewayUsage
from .model_gateway_protocol import (
    GatewaySpendController,
    error_response,
)
from .model_gateway_responses_paid import (
    build_paid_responses_gateway_controller,
    load_paid_responses_gateway_config,
    openai_responses_registry_charge_extractor,
    priced_service_tiers_for_registry_entry,
)
from .model_gateway_responses_protocol import (
    OPENAI_PROVIDER,
    ResponsesTerminal,
    ResponsesUsage,
    parse_responses_terminal,
    parse_responses_usage,
    validate_responses_request,
)
from .model_gateway_types import (
    GatewayAuthenticationError,
    GatewayBudgetExceeded,
    GatewayEvidenceError,
    GatewayResponse,
    GatewayUpstreamError,
    ModelGatewayError,
    Reservation,
)

RESPONSES_ROUTE: Final[str] = "/v1/responses"
OPENAI_RESPONSES_URL: Final[str] = "https://api.openai.com/v1/responses"
MAX_HTTP_HEADER_BYTES: Final[int] = 16 * 1024
DEFAULT_REQUEST_BYTES: Final[int] = 4 * 1024 * 1024
DEFAULT_RESPONSE_BYTES: Final[int] = 16 * 1024 * 1024
DEFAULT_UPSTREAM_TIMEOUT_SECONDS: Final[float] = 120.0
_HOP_BY_HOP_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "connection",
        "content-length",
        "cookie",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "x-api-key",
    }
)


@dataclass(frozen=True, slots=True)
class ResponsesGatewayPolicy:
    """Immutable limits and identities for one native Responses run."""

    upstream_api_key: str
    capability_token: str
    run_request_id: str
    allowed_model_keys: frozenset[str]
    allowed_ingress_hosts: frozenset[str]
    allowed_service_tiers: frozenset[str] = frozenset({"default"})
    max_request_bytes: int = DEFAULT_REQUEST_BYTES
    max_response_bytes: int = DEFAULT_RESPONSE_BYTES
    max_requests: int = 64
    max_input_tokens: int = 1_000_000
    max_output_tokens: int = 128_000
    max_total_input_tokens: int = 1_000_000
    max_total_output_tokens: int = 128_000
    upstream_timeout_seconds: float = DEFAULT_UPSTREAM_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.upstream_api_key == "" or any(
            character in self.upstream_api_key for character in "\r\n"
        ):
            raise ModelGatewayError("upstream_api_key must be a nonempty header value")
        if self.capability_token == "" or any(
            character in self.capability_token for character in "\r\n"
        ):
            raise ModelGatewayError("capability_token must be a nonempty header value")
        _validate_single_line(self.run_request_id, "run_request_id")
        if not self.allowed_model_keys or any(
            not _is_openai_model_key(model_key) for model_key in self.allowed_model_keys
        ):
            raise ModelGatewayError(
                "allowed_model_keys must contain openai:model entries"
            )
        if not self.allowed_ingress_hosts or any(
            not host or any(character.isspace() for character in host)
            for host in self.allowed_ingress_hosts
        ):
            raise ModelGatewayError(
                "allowed_ingress_hosts must contain nonempty host names"
            )
        if not self.allowed_service_tiers or any(
            tier not in {"default", "flex"} for tier in self.allowed_service_tiers
        ):
            raise ModelGatewayError(
                "allowed_service_tiers must contain priced OpenAI tiers"
            )
        for name, value in (
            ("max_request_bytes", self.max_request_bytes),
            ("max_response_bytes", self.max_response_bytes),
            ("max_requests", self.max_requests),
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
            ("max_total_input_tokens", self.max_total_input_tokens),
            ("max_total_output_tokens", self.max_total_output_tokens),
        ):
            if type(value) is not int or value <= 0:
                raise ModelGatewayError(f"{name} must be a positive integer")
        if self.upstream_timeout_seconds <= 0:
            raise ModelGatewayError("upstream_timeout_seconds must be positive")

    @property
    def allowed_models(self) -> frozenset[str]:
        """Return the model IDs represented by the frozen provider keys."""

        return frozenset(
            model_key.split(":", 1)[1] for model_key in self.allowed_model_keys
        )


@dataclass(frozen=True, slots=True)
class ResponsesUpstreamResponse:
    """Bounded response bytes returned by the fixed upstream transport."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


class ResponsesUpstreamTransport(Protocol):
    """Transport seam used by the production HTTP client and offline tests."""

    def request(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ResponsesUpstreamResponse:
        """Forward one already-validated request to the fixed provider origin."""

        raise NotImplementedError


class OpenAIResponsesGateway:
    """Validate and forward one bounded OpenAI Responses request."""

    def __init__(
        self,
        policy: ResponsesGatewayPolicy,
        *,
        transport: ResponsesUpstreamTransport | None = None,
        usage_evidence_path: Path | None = None,
        spend_controller: GatewaySpendController | None = None,
    ) -> None:
        self.policy = policy
        self.usage = GatewayUsage(evidence_path=usage_evidence_path)
        self._transport = transport or FixedOpenAIResponsesTransport()
        self._spend_controller = spend_controller

    def handle(
        self,
        body: bytes,
        *,
        authorization: str | None = None,
        headers: Mapping[str, str] | None = None,
        route: str = RESPONSES_ROUTE,
    ) -> GatewayResponse:
        """Handle one authenticated ``POST /v1/responses`` request."""

        try:
            if not responses_route_allowed(route):
                raise ModelGatewayError("route not allowlisted")
            _authorize_capability(authorization, self.policy.capability_token)
            payload = _decode_json_object(body, self.policy.max_request_bytes)
            if len(body) > self.policy.max_input_tokens:
                raise GatewayBudgetExceeded("input-token limit exceeded")
            model, max_output_tokens = validate_responses_request(
                payload,
                allowed_models=self.policy.allowed_models,
                max_output_tokens=self.policy.max_output_tokens,
                allowed_service_tiers=self.policy.allowed_service_tiers,
            )
            reservation = self.usage.reserve(
                input_tokens=len(body),
                output_tokens=max_output_tokens,
                policy=self.policy,
            )
        except GatewayEvidenceError:
            return error_response(
                HTTPStatus.SERVICE_UNAVAILABLE, "usage accounting failed"
            )
        except GatewayAuthenticationError as exc:
            return error_response(HTTPStatus.UNAUTHORIZED, str(exc))
        except GatewayBudgetExceeded as exc:
            return error_response(HTTPStatus.TOO_MANY_REQUESTS, str(exc))
        except ModelGatewayError as exc:
            return error_response(HTTPStatus.BAD_REQUEST, str(exc))

        spend_lease: object | None = None
        if self._spend_controller is not None:
            try:
                spend_lease = self._spend_controller.authorize_request(
                    request_id=self.policy.run_request_id,
                    body=body,
                    model=model,
                    max_tokens=max_output_tokens,
                )
                if spend_lease is None:
                    raise RuntimeError("spend controller returned no lease")
            except Exception:
                self._reject_usage_after_authorization_failure(reservation)
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "spend authorization failed"
                )
            try:
                self._spend_controller.mark_transport_started(spend_lease)
            except Exception:
                self._settle_unknown(
                    reservation, spend_lease, "gateway_transport_start_error"
                )
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "spend authorization failed"
                )

        try:
            upstream = self._transport.request(
                body,
                _forward_headers(
                    headers or {}, upstream_api_key=self.policy.upstream_api_key
                ),
                timeout_seconds=self.policy.upstream_timeout_seconds,
                max_response_bytes=self.policy.max_response_bytes,
            )
            if len(upstream.body) > self.policy.max_response_bytes:
                raise GatewayUpstreamError("upstream response exceeds response limit")
            content_type = _safe_content_type(upstream.headers.get("content-type"))
            terminal = parse_responses_terminal(upstream.body, content_type)
            observed = None if terminal is None else terminal.usage
            if not self._settle_usage(reservation, observed, spend_lease):
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "usage accounting failed"
                )
            if self._spend_controller is not None and spend_lease is not None:
                try:
                    settled = self._spend_controller.settle_response(
                        spend_lease,
                        response_body=upstream.body,
                        response_status=upstream.status_code,
                        content_type=content_type,
                        input_tokens=(
                            None if observed is None else observed.input_tokens
                        ),
                        output_tokens=(
                            None if observed is None else observed.output_tokens
                        ),
                    )
                except Exception:
                    self._record_spend_failure(spend_lease, "gateway_settlement_error")
                    return error_response(
                        HTTPStatus.SERVICE_UNAVAILABLE, "spend settlement failed"
                    )
                if not settled:
                    return error_response(
                        HTTPStatus.BAD_GATEWAY,
                        "upstream charge evidence unavailable",
                    )
            if upstream.status_code < 200 or upstream.status_code >= 300:
                return error_response(HTTPStatus.BAD_GATEWAY, "upstream request failed")
            if terminal is not None and terminal.kind != "completed":
                return error_response(
                    HTTPStatus.BAD_GATEWAY, "upstream response did not complete"
                )
            if observed is None:
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "provider usage unavailable"
                )
            response_headers = {
                "content-type": content_type or "application/json",
                "cache-control": "no-store",
            }
            return GatewayResponse(
                upstream.status_code, response_headers, upstream.body
            )
        except (
            GatewayUpstreamError,
            HTTPException,
            OSError,
            TimeoutError,
            ValueError,
        ):
            self._settle_unknown(reservation, spend_lease, "gateway_transport_error")
            return error_response(HTTPStatus.BAD_GATEWAY, "upstream request failed")

    def _settle_usage(
        self,
        reservation: Reservation,
        observed: ResponsesUsage | None,
        spend_lease: object | None,
    ) -> bool:
        try:
            self.usage.settle(
                reservation,
                None if observed is None else observed.as_observed(),
            )
        except GatewayEvidenceError:
            self._record_spend_failure(spend_lease, "gateway_accounting_error")
            return False
        return True

    def _settle_unknown(
        self,
        reservation: Reservation,
        spend_lease: object | None,
        failure_type: str,
    ) -> None:
        try:
            self.usage.settle(reservation, None)
        except GatewayEvidenceError:
            self._record_spend_failure(spend_lease, "gateway_accounting_error")
        self._record_spend_failure(spend_lease, failure_type)

    def _reject_usage_after_authorization_failure(
        self, reservation: Reservation
    ) -> None:
        try:
            self.usage.reject(reservation)
        except GatewayEvidenceError:
            # No remote lease exists and no provider bytes were sent. The local
            # evidence failure is already fail-closed at the request boundary.
            pass

    def _record_spend_failure(self, lease: object | None, failure_type: str) -> None:
        if self._spend_controller is None or lease is None:
            return
        try:
            self._spend_controller.record_failure(
                lease,
                failure_type=failure_type,
                ambiguous=True,
            )
        except Exception:
            return


class FixedOpenAIResponsesTransport:
    """HTTP transport whose origin and route are fixed to the OpenAI API."""

    def request(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ResponsesUpstreamResponse:
        parsed = _parse_fixed_openai_url(OPENAI_RESPONSES_URL)
        connection: HTTPConnection | HTTPSConnection = HTTPSConnection(
            parsed.hostname or "api.openai.com",
            parsed.port or 443,
            timeout=timeout_seconds,
        )
        try:
            connection.request(
                "POST", RESPONSES_ROUTE, body=body, headers=dict(headers)
            )
            response = connection.getresponse()
            response_body = response.read(max_response_bytes + 1)
            return ResponsesUpstreamResponse(
                status_code=response.status,
                headers={
                    "content-type": response.getheader("content-type") or "",
                },
                body=response_body,
            )
        finally:
            connection.close()


def responses_route_allowed(value: str) -> bool:
    """Return true only for the exact native Responses route."""

    parsed = urlsplit(value)
    return (
        not parsed.scheme
        and not parsed.netloc
        and parsed.path == RESPONSES_ROUTE
        and not parsed.query
        and not parsed.fragment
    )


def _authorize_capability(authorization: str | None, capability_token: str) -> None:
    if authorization is None:
        raise GatewayAuthenticationError("invalid gateway authorization")
    scheme, separator, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or value != capability_token:
        raise GatewayAuthenticationError("invalid gateway authorization")


def _decode_json_object(body: bytes, max_bytes: int) -> Mapping[str, object]:
    if len(body) > max_bytes:
        raise ModelGatewayError("request body exceeds limit")
    try:
        payload: object = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelGatewayError("request body is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ModelGatewayError("request body must be a JSON object")
    return cast(Mapping[str, object], payload)


def _forward_headers(
    headers: Mapping[str, str], *, upstream_api_key: str
) -> dict[str, str]:
    forwarded = {
        "content-type": "application/json",
        "accept": headers.get("accept", "application/json")[:MAX_HTTP_HEADER_BYTES],
        "authorization": "Bearer " + upstream_api_key,
        "host": "api.openai.com",
        "connection": "close",
    }
    for name, value in headers.items():
        normalized = name.lower()
        if normalized in _HOP_BY_HOP_HEADERS:
            continue
        if len(value) > MAX_HTTP_HEADER_BYTES or "\r" in value or "\n" in value:
            continue
        if normalized in {"content-type", "accept"}:
            forwarded[normalized] = value
        elif normalized == "openai-beta":
            forwarded[normalized] = value
    return forwarded


def _parse_fixed_openai_url(value: str) -> SplitResult:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.openai.com"
        or parsed.port not in {None, 443}
        or parsed.path != RESPONSES_ROUTE
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ModelGatewayError("Responses upstream origin is not the fixed OpenAI API")
    return parsed


def _safe_content_type(value: str | None) -> str | None:
    if (
        value is None
        or len(value) > MAX_HTTP_HEADER_BYTES
        or "\r" in value
        or "\n" in value
    ):
        return None
    return value


def _is_openai_model_key(value: str) -> bool:
    provider, separator, model = value.partition(":")
    return provider == OPENAI_PROVIDER and bool(separator and model.strip())


def _validate_single_line(value: str, name: str) -> None:
    if (
        not value.strip()
        or len(value) > 256
        or any(character in value for character in "\r\n")
    ):
        raise ModelGatewayError(
            f"{name} must be a nonempty single-line value of at most 256 characters"
        )


__all__ = [
    "DEFAULT_REQUEST_BYTES",
    "DEFAULT_RESPONSE_BYTES",
    "OPENAI_PROVIDER",
    "OPENAI_RESPONSES_URL",
    "RESPONSES_ROUTE",
    "FixedOpenAIResponsesTransport",
    "OpenAIResponsesGateway",
    "ResponsesGatewayPolicy",
    "ResponsesTerminal",
    "ResponsesUpstreamResponse",
    "ResponsesUpstreamTransport",
    "ResponsesUsage",
    "build_paid_responses_gateway_controller",
    "load_paid_responses_gateway_config",
    "openai_responses_registry_charge_extractor",
    "parse_responses_terminal",
    "parse_responses_usage",
    "priced_service_tiers_for_registry_entry",
    "responses_route_allowed",
]
