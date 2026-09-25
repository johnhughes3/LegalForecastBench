"""A bounded Anthropic-compatible gateway for one tools-on container run.

The gateway is deliberately a small protocol proxy rather than a generic HTTP
or CONNECT proxy.  The untrusted harness receives only a per-run capability;
the provider API key stays in this process.  Only ``POST /v1/messages`` is
accepted, the upstream origin is fixed when the gateway is constructed, and
request and response bodies are bounded before they are forwarded or returned.

This module does not make provider calls by itself.  ``AnthropicModelGateway``
can be hosted by :func:`build_model_gateway_server` next to a container, while
tests use a local fake upstream.  A production caller must put the gateway on
the harness-only network and give the gateway process its upstream key through
the existing secret boundary.

The capability is not a secret-provider credential.  A Bash tool in the same
container can reuse it, so every accepted request consumes the same request and
token budget.  Callers that require one primary CLI process must additionally
reject unexpected request counts; this gateway cannot identify sibling
processes sharing the container network.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import SplitResult, urlsplit

from .model_gateway_accounting import GatewayUsage
from .model_gateway_types import (
    GatewayAuthenticationError,
    GatewayBudgetExceeded,
    GatewayEvidenceError,
    GatewayResponse,
    GatewayUpstreamError,
    ModelGatewayError,
    ObservedUsage,
)

MAX_HTTP_HEADER_BYTES: Final[int] = 16 * 1024
DEFAULT_REQUEST_BYTES: Final[int] = 4 * 1024 * 1024
DEFAULT_RESPONSE_BYTES: Final[int] = 16 * 1024 * 1024
DEFAULT_UPSTREAM_TIMEOUT_SECONDS: Final[float] = 120.0
_WEB_TOOL_PREFIXES: Final[tuple[str, ...]] = (
    "web_search",
    "web_fetch",
    "websearch",
    "webfetch",
)
_REMOTE_TOOL_FIELD_PREFIXES: Final[tuple[str, ...]] = (
    "mcp",
    "connector",
    "remote_tool",
    "server_tool",
    "web_search",
    "web_fetch",
)
_CUSTOM_TOOL_KEYS: Final[frozenset[str]] = frozenset(
    {"name", "description", "input_schema", "cache_control"}
)
_ALLOWED_MESSAGE_QUERY: Final[frozenset[str]] = frozenset({"", "beta=true"})


@dataclass(frozen=True, slots=True)
class ModelGatewayPolicy:
    """Immutable policy for one gateway and one harness run.

    ``upstream_base_url`` is parsed once and the request path is always
    ``/v1/messages`` (with Claude's observed ``?beta=true`` query accepted).
    A client cannot select another host, scheme, or path.
    ``capability_token`` is the value the harness may receive as its synthetic
    ``ANTHROPIC_API_KEY``; ``upstream_api_key`` is never forwarded to the
    harness and is injected only on the fixed upstream request.
    """

    upstream_base_url: str
    upstream_api_key: str
    capability_token: str
    allowed_models: frozenset[str]
    allowed_ingress_hosts: frozenset[str]
    max_request_bytes: int = DEFAULT_REQUEST_BYTES
    max_response_bytes: int = DEFAULT_RESPONSE_BYTES
    max_requests: int = 64
    max_input_tokens: int = 1_000_000
    max_output_tokens: int = 128_000
    max_total_input_tokens: int = 1_000_000
    max_total_output_tokens: int = 128_000
    upstream_timeout_seconds: float = DEFAULT_UPSTREAM_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        parsed = _parse_upstream_url(self.upstream_base_url)
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ModelGatewayError(
                "upstream_base_url must not contain credentials, query, or fragment"
            )
        if (
            not self.upstream_api_key
            or "\r" in self.upstream_api_key
            or "\n" in self.upstream_api_key
        ):
            raise ModelGatewayError("upstream_api_key must be a nonempty header value")
        if (
            not self.capability_token
            or "\r" in self.capability_token
            or "\n" in self.capability_token
        ):
            raise ModelGatewayError("capability_token must be a nonempty header value")
        if not self.allowed_models or any(
            not model or any(character.isspace() for character in model)
            for model in self.allowed_models
        ):
            raise ModelGatewayError("allowed_models must contain nonempty model names")
        if not self.allowed_ingress_hosts or any(
            not host or any(character.isspace() for character in host)
            for host in self.allowed_ingress_hosts
        ):
            raise ModelGatewayError(
                "allowed_ingress_hosts must contain nonempty host names"
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
            if isinstance(value, bool) or value <= 0:
                raise ModelGatewayError(f"{name} must be a positive integer")
        if self.upstream_timeout_seconds <= 0:
            raise ModelGatewayError("upstream_timeout_seconds must be positive")


class AnthropicModelGateway:
    """Validate and forward the single supported Anthropic API operation."""

    def __init__(
        self,
        policy: ModelGatewayPolicy,
        *,
        usage_evidence_path: Path | None = None,
    ) -> None:
        self.policy = policy
        self.usage = GatewayUsage(evidence_path=usage_evidence_path)
        self._upstream = _parse_upstream_url(policy.upstream_base_url)
        upstream_host = self._upstream.hostname
        if upstream_host is None:
            raise ModelGatewayError("upstream_base_url has no hostname")
        self._upstream_host: str = upstream_host
        self._upstream_port = self._upstream.port

    def handle(
        self,
        body: bytes,
        *,
        authorization: str | None = None,
        api_key: str | None = None,
        headers: Mapping[str, str] | None = None,
        route: str = "/v1/messages",
    ) -> GatewayResponse:
        """Handle one authenticated ``POST /v1/messages`` body.

        The HTTP server calls this after enforcing method, route, and
        ``Content-Length``.  The method is public so provider-free tests and a
        future container adapter can exercise the policy without a network.
        """

        try:
            if not message_route_allowed(route):
                raise ModelGatewayError("route not allowlisted")
            self._authorize(authorization=authorization, api_key=api_key)
            payload = _decode_json_object(body, self.policy.max_request_bytes)
            _validate_request_fields(payload)
            model = payload.get("model")
            if not isinstance(model, str) or model not in self.policy.allowed_models:
                raise ModelGatewayError("model is not allowlisted")
            max_tokens = payload.get("max_tokens")
            if (
                not isinstance(max_tokens, int)
                or isinstance(max_tokens, bool)
                or max_tokens <= 0
            ):
                raise ModelGatewayError("max_tokens must be a positive integer")
            if max_tokens > self.policy.max_output_tokens:
                raise GatewayBudgetExceeded("max_tokens exceeds per-request limit")
            _validate_tools(payload.get("tools"))
            estimated_input = len(body)
            if estimated_input > self.policy.max_input_tokens:
                raise GatewayBudgetExceeded("input-token limit exceeded")
            reservation = self.usage.reserve(
                input_tokens=estimated_input,
                output_tokens=max_tokens,
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

        try:
            response_body, response_status, content_type = self._forward(
                body,
                headers or {},
                route,
            )
            if len(response_body) > self.policy.max_response_bytes:
                raise GatewayUpstreamError("upstream response exceeds response limit")
            observed = _usage_from_body(response_body, content_type)
            try:
                self.usage.settle(reservation, observed)
            except GatewayEvidenceError:
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "usage accounting failed"
                )
            if response_status < 200 or response_status >= 300:
                return error_response(HTTPStatus.BAD_GATEWAY, "upstream request failed")
            response_headers = {
                "content-type": content_type or "application/json",
                "cache-control": "no-store",
            }
            return GatewayResponse(response_status, response_headers, response_body)
        except (GatewayUpstreamError, OSError, TimeoutError, ValueError):
            try:
                self.usage.settle(reservation, None)
            except GatewayEvidenceError:
                return error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, "usage accounting failed"
                )
            return error_response(HTTPStatus.BAD_GATEWAY, "upstream request failed")

    def _authorize(self, *, authorization: str | None, api_key: str | None) -> None:
        candidates: list[str] = []
        if authorization is not None:
            scheme, separator, value = authorization.partition(" ")
            if scheme.lower() != "bearer" or not separator or not value:
                raise GatewayAuthenticationError("invalid gateway authorization")
            candidates.append(value)
        if api_key is not None:
            candidates.append(api_key)
        if not candidates or any(
            value != self.policy.capability_token for value in candidates
        ):
            raise GatewayAuthenticationError("invalid gateway authorization")

    def _forward(
        self,
        body: bytes,
        headers: Mapping[str, str],
        route: str,
    ) -> tuple[bytes, int, str | None]:
        connection: HTTPConnection | HTTPSConnection
        if self._upstream.scheme == "https":
            connection = HTTPSConnection(
                self._upstream_host,
                self._upstream_port,
                timeout=self.policy.upstream_timeout_seconds,
            )
        else:
            connection = HTTPConnection(
                self._upstream_host,
                self._upstream_port,
                timeout=self.policy.upstream_timeout_seconds,
            )
        forwarded: dict[str, str] = {
            "content-type": "application/json",
            "content-length": str(len(body)),
            "accept": headers.get("accept", "application/json")[:MAX_HTTP_HEADER_BYTES],
            "x-api-key": self.policy.upstream_api_key,
            "connection": "close",
        }
        for name in ("anthropic-version", "anthropic-beta"):
            value = headers.get(name)
            if value:
                forwarded[name] = value[:MAX_HTTP_HEADER_BYTES]
        try:
            connection.request("POST", route, body=body, headers=forwarded)
            response = connection.getresponse()
            response_body = response.read(self.policy.max_response_bytes + 1)
            return (
                response_body,
                response.status,
                _safe_content_type(response.getheader("content-type")),
            )
        finally:
            connection.close()


def _safe_content_type(value: str | None) -> str | None:
    if (
        value is None
        or len(value) > MAX_HTTP_HEADER_BYTES
        or "\r" in value
        or "\n" in value
    ):
        return None
    return value


def _parse_upstream_url(value: str) -> SplitResult:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ModelGatewayError("upstream_base_url is malformed") from exc
    if parsed.scheme not in {"http", "https"} or hostname is None:
        raise ModelGatewayError("upstream_base_url must use http or https")
    if parsed.path not in {"", "/"} or port is None:
        raise ModelGatewayError(
            "upstream_base_url must specify an origin with an explicit port"
        )
    return parsed


def _decode_json_object(body: bytes, max_bytes: int) -> dict[str, Any]:
    if len(body) > max_bytes:
        raise ModelGatewayError("request body exceeds limit")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelGatewayError("request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ModelGatewayError("request body must be a JSON object")
    return cast(dict[str, Any], payload)


def _validate_request_fields(payload: Mapping[str, object]) -> None:
    """Reject top-level fields that can delegate work to remote providers."""

    for raw_name in payload:
        normalized_name = raw_name.lower().replace("-", "_")
        compact_name = normalized_name.replace("_", "")
        if normalized_name.startswith(
            _REMOTE_TOOL_FIELD_PREFIXES
        ) or compact_name.startswith(
            ("mcp", "connector", "remotetool", "servertool", "websearch", "webfetch")
        ):
            raise ModelGatewayError("remote provider tools are disabled")


def _validate_tools(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise ModelGatewayError("tools must be a JSON array")
    for raw_item in cast(list[object], value):
        if not isinstance(raw_item, dict):
            raise ModelGatewayError("tools entries must be JSON objects")
        item = cast(dict[str, object], raw_item)
        name = item.get("name")
        for key in ("name", "type", "tool_name", "tool_type"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.lower().startswith(
                _WEB_TOOL_PREFIXES
            ):
                raise ModelGatewayError("provider-side web tools are disabled")
        if any(key.lower().startswith(_WEB_TOOL_PREFIXES) for key in item):
            raise ModelGatewayError("provider-side web tools are disabled")
        if set(item) - _CUSTOM_TOOL_KEYS:
            raise ModelGatewayError("unknown tool fields are not allowed")
        if not isinstance(name, str) or not name:
            raise ModelGatewayError("tool name must be a nonempty string")
        description = item.get("description")
        if not isinstance(description, str) or not description:
            raise ModelGatewayError("tool description must be a nonempty string")
        schema = item.get("input_schema")
        if not isinstance(schema, dict):
            raise ModelGatewayError("tool input_schema must be an object schema")
        schema_object = cast(dict[str, object], schema)
        if schema_object.get("type") != "object":
            raise ModelGatewayError("tool input_schema must be an object schema")
        cache_control = item.get("cache_control")
        if cache_control is not None and not isinstance(cache_control, dict):
            raise ModelGatewayError("tool cache_control must be an object")


def message_route_allowed(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        not parsed.scheme
        and not parsed.netloc
        and parsed.path == "/v1/messages"
        and parsed.query in _ALLOWED_MESSAGE_QUERY
        and not parsed.fragment
    )


def host_header_allowed(
    value: str | None,
    allowed_hosts: frozenset[str],
) -> bool:
    if value is None or "," in value:
        return False
    try:
        parsed = urlsplit("//" + value)
        hostname = parsed.hostname
        if (
            hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return False
        port = parsed.port
        if port is not None and port < 1:
            return False
    except ValueError:
        return False
    return hostname.rstrip(".").lower() in {
        host.rstrip(".").lower() for host in allowed_hosts
    }


def _usage_from_body(body: bytes, content_type: str | None) -> ObservedUsage | None:
    if content_type and content_type.lower().startswith("text/event-stream"):
        input_tokens: int | None = None
        output_tokens: int | None = None
        for line in body.splitlines():
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == b"[DONE]":
                continue
            try:
                event = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            observed = _usage_from_object(event)
            if observed is not None:
                if observed.input_tokens is not None:
                    input_tokens = observed.input_tokens
                if observed.output_tokens is not None:
                    output_tokens = observed.output_tokens
        if input_tokens is None and output_tokens is None:
            return None
        return ObservedUsage(input_tokens, output_tokens)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _usage_from_object(payload)


def _usage_from_object(value: object) -> ObservedUsage | None:
    if not isinstance(value, dict):
        return None
    value_object = cast(dict[str, object], value)
    candidates: list[object] = [value_object.get("usage")]
    message = value_object.get("message")
    if isinstance(message, dict):
        candidates.append(cast(dict[str, object], message).get("usage"))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_object = cast(dict[str, object], candidate)
        input_tokens = _nonnegative_int(candidate_object.get("input_tokens"))
        output_tokens = _nonnegative_int(candidate_object.get("output_tokens"))
        if input_tokens is not None or output_tokens is not None:
            return ObservedUsage(input_tokens, output_tokens)
    return None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def error_response(status: HTTPStatus, reason: str) -> GatewayResponse:
    # Keep error bodies code-only.  Validation details must not echo request
    # content, upstream responses, or credentials into a harness transcript.
    body = json.dumps(
        {"type": "error", "error": {"type": "gateway_error", "message": reason}},
        separators=(",", ":"),
    ).encode("utf-8")
    return GatewayResponse(
        int(status),
        {"content-type": "application/json", "cache-control": "no-store"},
        body,
    )
