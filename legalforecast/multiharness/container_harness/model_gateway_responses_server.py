"""HTTP ingress and protected launcher for the bounded Responses gateway."""

from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from .model_gateway_paid import ProtectedPaidGatewayConfig
from .model_gateway_protocol import (
    MAX_HTTP_HEADER_BYTES,
    GatewaySpendController,
    host_header_allowed,
)
from .model_gateway_responses import (
    DEFAULT_REQUEST_BYTES,
    DEFAULT_RESPONSE_BYTES,
    OPENAI_PROVIDER,
    OpenAIResponsesGateway,
    ResponsesGatewayPolicy,
    ResponsesUpstreamTransport,
    build_paid_responses_gateway_controller,
    load_paid_responses_gateway_config,
    responses_route_allowed,
)
from .model_gateway_types import GatewayResponse, ModelGatewayError


class ResponsesGatewayHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server carrying one immutable Responses gateway."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        gateway: OpenAIResponsesGateway,
    ) -> None:
        self.gateway = gateway
        super().__init__(server_address, _ResponsesGatewayRequestHandler)


class _ResponsesGatewayRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(ResponsesGatewayHTTPServer, self.server)
        host_headers = self.headers.get_all("Host") or []
        if (
            len(host_headers) != 1
            or not responses_route_allowed(self.path)
            or not host_header_allowed(
                host_headers[0], server.gateway.policy.allowed_ingress_hosts
            )
        ):
            self._send(_error(HTTPStatus.NOT_FOUND, "route not found"))
            return
        if self.headers.get_all("Transfer-Encoding"):
            self._send(_error(HTTPStatus.BAD_REQUEST, "transfer encoding denied"))
            return
        authorization_headers = self.headers.get_all("Authorization") or []
        api_key_headers = self.headers.get_all("x-api-key") or []
        if api_key_headers:
            self._send(_error(HTTPStatus.BAD_REQUEST, "unsupported api-key header"))
            return
        if len(authorization_headers) != 1:
            self._send(_error(HTTPStatus.UNAUTHORIZED, "invalid gateway authorization"))
            return
        content_lengths = self.headers.get_all("Content-Length") or []
        if len(content_lengths) != 1:
            self._send(_error(HTTPStatus.BAD_REQUEST, "invalid content length"))
            return
        try:
            content_length = int(content_lengths[0])
        except ValueError:
            self._send(_error(HTTPStatus.BAD_REQUEST, "invalid content length"))
            return
        if (
            content_length < 0
            or content_length > server.gateway.policy.max_request_bytes
        ):
            self._send(_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request too large"))
            return
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._send(_error(HTTPStatus.BAD_REQUEST, "truncated request"))
            return
        response = server.gateway.handle(
            body,
            authorization=authorization_headers[0],
            headers={
                key.lower(): value
                for key, value in self.headers.items()
                if len(value) <= MAX_HTTP_HEADER_BYTES
            },
            route=self.path,
        )
        self._send(response)

    def do_CONNECT(self) -> None:
        self._send(_error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_GET(self) -> None:
        self._send(_error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_HEAD(self) -> None:
        self._send(_error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

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


def build_responses_gateway_server(
    policy: ResponsesGatewayPolicy,
    *,
    bind_host: str = "127.0.0.1",
    port: int = 0,
    transport: ResponsesUpstreamTransport | None = None,
    usage_evidence_path: Path | None = None,
    spend_controller: GatewaySpendController | None = None,
) -> ResponsesGatewayHTTPServer:
    """Build a Responses gateway without starting a background thread."""

    gateway = OpenAIResponsesGateway(
        policy,
        transport=transport,
        usage_evidence_path=usage_evidence_path,
        spend_controller=spend_controller,
    )
    return ResponsesGatewayHTTPServer((bind_host, port), gateway)


def build_paid_responses_gateway_policy(
    paid_config: ProtectedPaidGatewayConfig,
    *,
    upstream_api_key: str,
    capability_token: str,
    run_request_id: str,
) -> ResponsesGatewayPolicy:
    """Build the immutable policy from one production-loaded descriptor."""

    pricing_service_tier = paid_config.pricing_service_tier
    if pricing_service_tier is None:
        raise ModelGatewayError(
            "paid Responses gateway requires a structured pricing service tier"
        )
    model_keys = (paid_config.model_key,)
    if any(not key.startswith(f"{OPENAI_PROVIDER}:") for key in model_keys):
        raise ModelGatewayError("--model-key must use the openai:model namespace")
    max_requests = paid_config.max_requests
    max_input_tokens = paid_config.registry_entry.context_limit
    max_output_tokens = paid_config.registry_entry.max_output_tokens
    return ResponsesGatewayPolicy(
        upstream_api_key=upstream_api_key,
        capability_token=capability_token,
        run_request_id=run_request_id,
        allowed_model_keys=frozenset(model_keys),
        allowed_ingress_hosts=frozenset({"127.0.0.1"}),
        allowed_service_tiers=frozenset({pricing_service_tier}),
        max_request_bytes=DEFAULT_REQUEST_BYTES,
        max_response_bytes=DEFAULT_RESPONSE_BYTES,
        max_requests=max_requests,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_total_input_tokens=max_requests * max_input_tokens,
        max_total_output_tokens=max_requests * max_output_tokens,
    )


def main(argv: list[str] | None = None) -> int:
    """Launch the protected gateway; provider values never appear in argv."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-key", action="append", help="allowlisted openai:model key"
    )
    parser.add_argument("--paid-config", type=Path)
    parser.add_argument("--model-registry", type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--server-info", type=Path)
    parser.add_argument("--usage-evidence", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.paid_config is None or args.model_registry is None:
            raise ModelGatewayError(
                "paid config and model registry are required for durable settlement"
            )
        paid_config = load_paid_responses_gateway_config(
            args.paid_config,
            model_registry_path=args.model_registry,
        )
        spend_controller: GatewaySpendController = (
            build_paid_responses_gateway_controller(paid_config)
        )
        if args.model_key is not None and tuple(args.model_key) != (
            paid_config.model_key,
        ):
            raise ModelGatewayError("--model-key does not match paid gateway config")
        upstream_api_key = _required_environment("LFB_RESPONSES_UPSTREAM_API_KEY")
        capability_token = _required_environment("LFB_RESPONSES_CAPABILITY_TOKEN")
        run_request_id = _required_environment("LFB_RESPONSES_REQUEST_ID")
        policy = build_paid_responses_gateway_policy(
            paid_config,
            upstream_api_key=upstream_api_key,
            capability_token=capability_token,
            run_request_id=run_request_id,
        )
        server = build_responses_gateway_server(
            policy,
            port=args.port,
            usage_evidence_path=args.usage_evidence,
            spend_controller=spend_controller,
        )
    except (OSError, RuntimeError, ValueError):
        print("Responses gateway failed closed", file=sys.stderr)
        return 1

    try:
        if args.server_info is not None:
            _write_server_info(args.server_info, int(server.server_address[1]))
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value:
        raise ModelGatewayError(f"{name} is unavailable")
    return value


def _write_server_info(path: Path, port: int) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise ModelGatewayError("server-info must be an absolute create-only path")
    if not path.parent.is_dir():
        raise ModelGatewayError("server-info parent directory is unavailable")
    payload = (
        json.dumps({"port": port, "pid": os.getpid()}, separators=(",", ":")) + "\n"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = -1
            output.write(payload)
    except Exception:
        if descriptor != -1:
            os.close(descriptor)
        raise


def _error(status: HTTPStatus, reason: str) -> GatewayResponse:
    from .model_gateway_protocol import error_response

    return error_response(status, reason)


__all__ = [
    "ResponsesGatewayHTTPServer",
    "build_paid_responses_gateway_policy",
    "build_responses_gateway_server",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
