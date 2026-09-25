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

import argparse
import json
import os
import stat
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import SplitResult, urlsplit

MAX_HTTP_HEADER_BYTES: Final[int] = 16 * 1024
DEFAULT_REQUEST_BYTES: Final[int] = 4 * 1024 * 1024
DEFAULT_RESPONSE_BYTES: Final[int] = 16 * 1024 * 1024
DEFAULT_UPSTREAM_TIMEOUT_SECONDS: Final[float] = 120.0
UPSTREAM_API_KEY_ENV: Final[str] = "LFB_MODEL_GATEWAY_UPSTREAM_API_KEY"
UPSTREAM_KEY_FILE_ENV: Final[str] = "LFB_MODEL_GATEWAY_UPSTREAM_KEY_FILE"
CAPABILITY_TOKEN_ENV: Final[str] = "LFB_MODEL_GATEWAY_CAPABILITY_TOKEN"
_WEB_TOOL_PREFIXES: Final[tuple[str, ...]] = (
    "web_search",
    "web_fetch",
    "websearch",
    "webfetch",
)
_CUSTOM_TOOL_KEYS: Final[frozenset[str]] = frozenset(
    {"name", "description", "input_schema", "cache_control"}
)
_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bind_host",
        "bind_port",
        "upstream_base_url",
        "allowed_models",
        "allowed_ingress_hosts",
        "max_request_bytes",
        "max_response_bytes",
        "max_requests",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_input_tokens",
        "max_total_output_tokens",
        "upstream_timeout_seconds",
    }
)
_ALLOWED_MESSAGE_QUERY: Final[frozenset[str]] = frozenset({"", "beta=true"})


class ModelGatewayError(ValueError):
    """Raised when a gateway policy or request contract is invalid."""


class GatewayBudgetExceeded(ModelGatewayError):
    """Raised when a request cannot fit inside the run's remaining budget."""


class GatewayAuthenticationError(ModelGatewayError):
    """Raised when the harness lacks the run capability."""


class GatewayUpstreamError(RuntimeError):
    """Raised when the fixed upstream cannot return a bounded response."""


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
    max_output_tokens: int = 32_000
    max_total_input_tokens: int = 1_000_000
    max_total_output_tokens: int = 32_000
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


@dataclass(frozen=True, slots=True)
class GatewayUsageSnapshot:
    """Thread-safe public usage state for one gateway."""

    request_count: int
    input_tokens: int
    output_tokens: int
    reserved_input_tokens: int
    reserved_output_tokens: int
    rejected_count: int


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    """A bounded response returned by the gateway protocol handler."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class _Reservation:
    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class GatewayUsage:
    """Account reservations and observed usage across concurrent requests."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _request_count: int = 0
    _input_tokens: int = 0
    _output_tokens: int = 0
    _reserved_input_tokens: int = 0
    _reserved_output_tokens: int = 0
    _rejected_count: int = 0

    def reserve(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        policy: ModelGatewayPolicy,
    ) -> _Reservation:
        """Reserve worst-case input/output usage before contacting upstream."""

        with self._lock:
            if self._request_count >= policy.max_requests:
                self._rejected_count += 1
                raise GatewayBudgetExceeded("request budget exhausted")
            if (
                self._input_tokens + self._reserved_input_tokens + input_tokens
                > policy.max_total_input_tokens
            ):
                self._rejected_count += 1
                raise GatewayBudgetExceeded("input-token budget exhausted")
            if (
                self._output_tokens + self._reserved_output_tokens + output_tokens
                > policy.max_total_output_tokens
            ):
                self._rejected_count += 1
                raise GatewayBudgetExceeded("output-token budget exhausted")
            self._request_count += 1
            self._reserved_input_tokens += input_tokens
            self._reserved_output_tokens += output_tokens
            return _Reservation(input_tokens, output_tokens)

    def settle(
        self,
        reservation: _Reservation,
        observed: _ObservedUsage | None,
    ) -> None:
        """Replace a reservation with observed usage, conservatively if absent."""

        input_tokens = (
            observed.input_tokens
            if observed is not None and observed.input_tokens is not None
            else reservation.input_tokens
        )
        output_tokens = (
            observed.output_tokens
            if observed is not None and observed.output_tokens is not None
            else reservation.output_tokens
        )
        with self._lock:
            self._reserved_input_tokens -= reservation.input_tokens
            self._reserved_output_tokens -= reservation.output_tokens
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens

    def snapshot(self) -> GatewayUsageSnapshot:
        """Return a consistent usage snapshot."""

        with self._lock:
            return GatewayUsageSnapshot(
                request_count=self._request_count,
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                reserved_input_tokens=self._reserved_input_tokens,
                reserved_output_tokens=self._reserved_output_tokens,
                rejected_count=self._rejected_count,
            )


@dataclass(frozen=True, slots=True)
class _ObservedUsage:
    input_tokens: int | None
    output_tokens: int | None


class AnthropicModelGateway:
    """Validate and forward the single supported Anthropic API operation."""

    def __init__(self, policy: ModelGatewayPolicy) -> None:
        self.policy = policy
        self.usage = GatewayUsage()
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
            if not _message_route_allowed(route):
                raise ModelGatewayError("route not allowlisted")
            self._authorize(authorization=authorization, api_key=api_key)
            payload = _decode_json_object(body, self.policy.max_request_bytes)
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
        except GatewayAuthenticationError as exc:
            return _error_response(HTTPStatus.UNAUTHORIZED, str(exc))
        except GatewayBudgetExceeded as exc:
            return _error_response(HTTPStatus.TOO_MANY_REQUESTS, str(exc))
        except ModelGatewayError as exc:
            return _error_response(HTTPStatus.BAD_REQUEST, str(exc))

        try:
            response_body, response_status, content_type = self._forward(
                body,
                headers or {},
                route,
            )
            if len(response_body) > self.policy.max_response_bytes:
                raise GatewayUpstreamError("upstream response exceeds response limit")
            observed = _usage_from_body(response_body, content_type)
            self.usage.settle(reservation, observed)
            if response_status < 200 or response_status >= 300:
                return _error_response(
                    HTTPStatus.BAD_GATEWAY, "upstream request failed"
                )
            response_headers = {
                "content-type": content_type or "application/json",
                "cache-control": "no-store",
            }
            return GatewayResponse(response_status, response_headers, response_body)
        except (GatewayUpstreamError, OSError, TimeoutError, ValueError):
            self.usage.settle(reservation, None)
            return _error_response(HTTPStatus.BAD_GATEWAY, "upstream request failed")

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


class ModelGatewayHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server carrying one immutable gateway instance."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        gateway: AnthropicModelGateway,
    ) -> None:
        self.gateway = gateway
        super().__init__(server_address, _GatewayRequestHandler)


class _GatewayRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(ModelGatewayHTTPServer, self.server)
        host_headers = self.headers.get_all("Host") or []
        if (
            len(host_headers) != 1
            or not _message_route_allowed(self.path)
            or not _host_header_allowed(
                host_headers[0], server.gateway.policy.allowed_ingress_hosts
            )
        ):
            self._send(_error_response(HTTPStatus.NOT_FOUND, "route not found"))
            return
        if self.headers.get_all("Transfer-Encoding"):
            self._send(
                _error_response(HTTPStatus.BAD_REQUEST, "transfer encoding denied")
            )
            return
        authorization_headers = self.headers.get_all("Authorization") or []
        api_key_headers = self.headers.get_all("x-api-key") or []
        if len(authorization_headers) > 1 or len(api_key_headers) > 1:
            self._send(_error_response(HTTPStatus.BAD_REQUEST, "ambiguous auth"))
            return
        content_lengths = self.headers.get_all("Content-Length") or []
        if len(content_lengths) != 1:
            self._send(
                _error_response(HTTPStatus.BAD_REQUEST, "invalid content length")
            )
            return
        try:
            content_length = int(content_lengths[0])
        except ValueError:
            self._send(
                _error_response(HTTPStatus.BAD_REQUEST, "invalid content length")
            )
            return
        if (
            content_length < 0
            or content_length > server.gateway.policy.max_request_bytes
        ):
            self._send(
                _error_response(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request too large"
                )
            )
            return
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._send(_error_response(HTTPStatus.BAD_REQUEST, "truncated request"))
            return
        response = server.gateway.handle(
            body,
            authorization=authorization_headers[0] if authorization_headers else None,
            api_key=api_key_headers[0] if api_key_headers else None,
            headers={
                key.lower(): value
                for key, value in self.headers.items()
                if len(value) <= MAX_HTTP_HEADER_BYTES
            },
            route=self.path,
        )
        self._send(response)

    def do_CONNECT(self) -> None:
        self._send(_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_GET(self) -> None:
        self._send(_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_HEAD(self) -> None:
        self._send(_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send(self, response: GatewayResponse) -> None:
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.send_header("content-length", str(len(response.body)))
        self.send_header("connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)


def build_model_gateway_server(
    policy: ModelGatewayPolicy,
    *,
    bind_host: str = "127.0.0.1",
    port: int = 0,
) -> ModelGatewayHTTPServer:
    """Build a server for one gateway without starting a background thread."""

    gateway = AnthropicModelGateway(policy)
    return ModelGatewayHTTPServer((bind_host, port), gateway)


@dataclass(frozen=True, slots=True)
class ModelGatewayLaunchConfig:
    """Resolved sidecar configuration with secrets supplied out of band."""

    policy: ModelGatewayPolicy
    bind_host: str
    bind_port: int


def load_model_gateway_launch_config(
    config_path: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> ModelGatewayLaunchConfig:
    """Load public policy from an owner-only file and secrets from sidecar env.

    The JSON file intentionally has no credential fields.  The upstream key
    is accepted only from one of the sidecar-only environment variables, and
    the per-run capability is accepted only from ``CAPABILITY_TOKEN_ENV``.
    Neither value is a command-line argument or a harness-controlled field.
    """

    _require_owner_only_file(config_path, "gateway policy")
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelGatewayError("gateway policy is not valid JSON") from exc
    if not isinstance(raw_config, dict):
        raise ModelGatewayError("gateway policy must be a JSON object")
    config = cast(dict[str, object], raw_config)
    if "upstream_api_key" in config or "capability_token" in config:
        raise ModelGatewayError("gateway policy must not contain credentials")
    unknown_keys = set(config) - _POLICY_KEYS
    if unknown_keys:
        raise ModelGatewayError("gateway policy contains unknown fields")

    env = os.environ if environment is None else environment
    upstream_api_key = _load_upstream_api_key(env)
    capability_token = env.get(CAPABILITY_TOKEN_ENV)
    if not capability_token:
        raise ModelGatewayError(
            f"{CAPABILITY_TOKEN_ENV} must be set for the gateway sidecar"
        )

    policy_values: dict[str, Any] = {
        "upstream_base_url": _config_string(config, "upstream_base_url"),
        "upstream_api_key": upstream_api_key,
        "capability_token": capability_token,
        "allowed_models": frozenset(_config_string_list(config, "allowed_models")),
        "allowed_ingress_hosts": frozenset(
            _config_string_list(config, "allowed_ingress_hosts")
        ),
    }
    for name in (
        "max_request_bytes",
        "max_response_bytes",
        "max_requests",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_input_tokens",
        "max_total_output_tokens",
    ):
        if name in config:
            policy_values[name] = _config_positive_int(config, name)
    if "upstream_timeout_seconds" in config:
        timeout = config["upstream_timeout_seconds"]
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ModelGatewayError(
                "gateway policy upstream_timeout_seconds must be positive"
            )
        policy_values["upstream_timeout_seconds"] = float(timeout)

    policy = ModelGatewayPolicy(**policy_values)
    bind_host = _config_string(config, "bind_host")
    bind_port = _config_positive_int(config, "bind_port")
    if bind_port > 65_535:
        raise ModelGatewayError("gateway policy bind_port is out of range")
    return ModelGatewayLaunchConfig(policy, bind_host, bind_port)


def main(argv: list[str] | None = None) -> int:
    """Run the sidecar from an owner-only policy mount.

    Example deployment command::

        python -m legalforecast.multiharness.container_harness.model_gateway \
          --config /run/legalforecast/model-gateway/policy.json

    Credentials are deliberately absent from the command line.  The sidecar
    environment supplies them through ``*_ENV`` variables above.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="owner-only JSON policy file; it contains no credentials",
    )
    args = parser.parse_args(argv)
    try:
        launch = load_model_gateway_launch_config(args.config)
        server = build_model_gateway_server(
            launch.policy,
            bind_host=launch.bind_host,
            port=launch.bind_port,
        )
    except (OSError, ModelGatewayError) as exc:
        parser.error(f"invalid gateway configuration: {exc}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _load_upstream_api_key(environment: Mapping[str, str]) -> str:
    env_key = environment.get(UPSTREAM_API_KEY_ENV)
    key_file_name = environment.get(UPSTREAM_KEY_FILE_ENV)
    if bool(env_key) == bool(key_file_name):
        raise ModelGatewayError(
            "set exactly one sidecar upstream-key source: "
            f"{UPSTREAM_API_KEY_ENV} or {UPSTREAM_KEY_FILE_ENV}"
        )
    if env_key is not None:
        return env_key
    assert key_file_name is not None
    key_file = Path(key_file_name)
    _require_owner_only_file(key_file, "upstream key")
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ModelGatewayError("upstream key file cannot be read") from exc
    if not key:
        raise ModelGatewayError("upstream key file is empty")
    return key


def _require_owner_only_file(path: Path, description: str) -> None:
    if path.is_symlink():
        raise ModelGatewayError(f"{description} file must not be a symlink")
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise ModelGatewayError(f"{description} file cannot be inspected") from exc
    if not path.is_file():
        raise ModelGatewayError(f"{description} file is not a regular file")
    if mode & 0o077:
        raise ModelGatewayError(f"{description} file must be owner-only")


def _config_string(config: Mapping[str, object], name: str) -> str:
    value = config.get(name)
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string")
    return value


def _config_string_list(config: Mapping[str, object], name: str) -> list[str]:
    value = config.get(name)
    if not isinstance(value, list):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string list")
    items = cast(list[object], value)
    if not items or any(
        not isinstance(item, str)
        or not item
        or any(character.isspace() for character in item)
        for item in items
    ):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string list")
    return cast(list[str], value)


def _config_positive_int(config: Mapping[str, object], name: str) -> int:
    value = config.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelGatewayError(f"gateway policy {name} must be a positive integer")
    return value


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


def _message_route_allowed(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        not parsed.scheme
        and not parsed.netloc
        and parsed.path == "/v1/messages"
        and parsed.query in _ALLOWED_MESSAGE_QUERY
        and not parsed.fragment
    )


def _host_header_allowed(
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


def _usage_from_body(body: bytes, content_type: str | None) -> _ObservedUsage | None:
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
        return _ObservedUsage(input_tokens, output_tokens)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _usage_from_object(payload)


def _usage_from_object(value: object) -> _ObservedUsage | None:
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
            return _ObservedUsage(input_tokens, output_tokens)
    return None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _error_response(status: HTTPStatus, reason: str) -> GatewayResponse:
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


__all__ = [
    "CAPABILITY_TOKEN_ENV",
    "UPSTREAM_API_KEY_ENV",
    "UPSTREAM_KEY_FILE_ENV",
    "AnthropicModelGateway",
    "GatewayAuthenticationError",
    "GatewayBudgetExceeded",
    "GatewayResponse",
    "GatewayUsage",
    "GatewayUsageSnapshot",
    "ModelGatewayError",
    "ModelGatewayHTTPServer",
    "ModelGatewayLaunchConfig",
    "ModelGatewayPolicy",
    "build_model_gateway_server",
    "load_model_gateway_launch_config",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
