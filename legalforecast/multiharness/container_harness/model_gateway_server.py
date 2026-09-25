"""HTTP ingress for the bounded model gateway."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from .model_gateway_protocol import (
    MAX_HTTP_HEADER_BYTES,
    AnthropicModelGateway,
    GatewaySpendController,
    ModelGatewayPolicy,
    error_response,
    host_header_allowed,
    message_route_allowed,
)
from .model_gateway_types import GatewayResponse


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
            or not message_route_allowed(self.path)
            or not host_header_allowed(
                host_headers[0], server.gateway.policy.allowed_ingress_hosts
            )
        ):
            self._send(error_response(HTTPStatus.NOT_FOUND, "route not found"))
            return
        if self.headers.get_all("Transfer-Encoding"):
            self._send(
                error_response(HTTPStatus.BAD_REQUEST, "transfer encoding denied")
            )
            return
        authorization_headers = self.headers.get_all("Authorization") or []
        api_key_headers = self.headers.get_all("x-api-key") or []
        if len(authorization_headers) > 1 or len(api_key_headers) > 1:
            self._send(error_response(HTTPStatus.BAD_REQUEST, "ambiguous auth"))
            return
        content_lengths = self.headers.get_all("Content-Length") or []
        if len(content_lengths) != 1:
            self._send(error_response(HTTPStatus.BAD_REQUEST, "invalid content length"))
            return
        try:
            content_length = int(content_lengths[0])
        except ValueError:
            self._send(error_response(HTTPStatus.BAD_REQUEST, "invalid content length"))
            return
        if (
            content_length < 0
            or content_length > server.gateway.policy.max_request_bytes
        ):
            self._send(
                error_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request too large")
            )
            return
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._send(error_response(HTTPStatus.BAD_REQUEST, "truncated request"))
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
        self._send(error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_GET(self) -> None:
        self._send(error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

    def do_HEAD(self) -> None:
        self._send(error_response(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"))

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
    usage_evidence_path: Path | None = None,
    spend_controller: GatewaySpendController | None = None,
    request_id: str | None = None,
) -> ModelGatewayHTTPServer:
    """Build a server for one gateway without starting a background thread."""

    gateway = AnthropicModelGateway(
        policy,
        usage_evidence_path=usage_evidence_path,
        spend_controller=spend_controller,
        request_id=request_id,
    )
    return ModelGatewayHTTPServer((bind_host, port), gateway)
