from __future__ import annotations

import json
import socket
from collections.abc import Generator
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, cast

import pytest
from legalforecast.multiharness.container_harness.egress_proxy import (
    AllowlistConnectProxy,
    EgressAllowlist,
)
from legalforecast.multiharness.container_harness.model_gateway import (
    ModelGatewayHTTPServer,
    ModelGatewayPolicy,
    build_model_gateway_server,
)
from legalforecast.multiharness.container_harness.model_gateway_types import (
    ModelGatewayError,
)


class _FakeUpstream:
    def __init__(self) -> None:
        self.requests: list[bytes] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                owner.requests.append(self.rfile.read(length))
                body = json.dumps(
                    {"usage": {"input_tokens": 7, "output_tokens": 2}},
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self) -> int:
        return cast(tuple[str, int], self.server.server_address)[1]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def upstream() -> Generator[_FakeUpstream]:
    server = _FakeUpstream()
    try:
        yield server
    finally:
        server.close()


@contextmanager
def _gateway(
    policy: ModelGatewayPolicy,
) -> Generator[ModelGatewayHTTPServer]:
    server = build_model_gateway_server(policy)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _policy(**overrides: Any) -> ModelGatewayPolicy:
    values: dict[str, Any] = {
        "upstream_base_url": "http://localhost:1",
        "upstream_api_key": "provider-sentinel-never-in-harness",
        "capability_token": "run-capability-sentinel",
        "allowed_models": frozenset({"claude-fixture"}),
        "allowed_ingress_hosts": frozenset({"127.0.0.1"}),
        "max_request_bytes": 32_768,
        "max_response_bytes": 32_768,
        "max_requests": 8,
        "max_input_tokens": 32_768,
        "max_output_tokens": 128,
        "max_total_input_tokens": 32_768,
        "max_total_output_tokens": 256,
        "upstream_timeout_seconds": 2.0,
    }
    values.update(overrides)
    return ModelGatewayPolicy(**values)


def _message_body() -> bytes:
    return json.dumps(
        {
            "model": "claude-fixture",
            "max_tokens": 4,
            "messages": [{"role": "user", "content": "forecast"}],
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _request(server: ModelGatewayHTTPServer, body: bytes) -> tuple[int, bytes]:
    host, port = cast(tuple[str, int], server.server_address)
    connection = HTTPConnection(host, port, timeout=5)
    try:
        connection.request(
            "POST",
            "/v1/messages",
            body=body,
            headers={
                "content-length": str(len(body)),
                "x-api-key": "run-capability-sentinel",
            },
        )
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_fixed_proxy_tunnels_the_gateway_request(
    upstream: _FakeUpstream,
) -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"], ports=[upstream.port])
    with AllowlistConnectProxy(allowlist) as proxy:
        policy = _policy(
            upstream_base_url=f"http://localhost:{upstream.port}",
            proxy_base_url=f"http://127.0.0.1:{proxy.port}",
        )
        with _gateway(policy) as gateway:
            status, response_body = _request(gateway, _message_body())

    assert status == 200
    assert json.loads(response_body)["usage"] == {
        "input_tokens": 7,
        "output_tokens": 2,
    }
    assert upstream.requests == [_message_body()]
    assert proxy.evidence.allowed_hosts() == ("localhost",)
    assert proxy.evidence.refused() == ()


def test_refused_proxy_target_does_not_fall_back_to_direct_upstream(
    upstream: _FakeUpstream,
) -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["other.example"])
    with AllowlistConnectProxy(allowlist) as proxy:
        policy = _policy(
            upstream_base_url=f"http://localhost:{upstream.port}",
            proxy_base_url=f"http://127.0.0.1:{proxy.port}",
        )
        with _gateway(policy) as gateway:
            status, _ = _request(gateway, _message_body())

    assert status == 502
    assert upstream.requests == []
    assert len(proxy.evidence.refused()) == 1
    assert proxy.evidence.refused()[0].host == "localhost"


def test_unreachable_configured_proxy_fails_closed_without_direct_fallback(
    upstream: _FakeUpstream,
) -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    proxy_port = int(probe.getsockname()[1])
    probe.close()
    policy = _policy(
        upstream_base_url=f"http://localhost:{upstream.port}",
        proxy_base_url=f"http://127.0.0.1:{proxy_port}",
    )
    with _gateway(policy) as gateway:
        status, _ = _request(gateway, _message_body())

    assert status == 502
    assert upstream.requests == []


@pytest.mark.parametrize(
    "proxy_base_url",
    (
        "https://127.0.0.1:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:8080/path",
        "http://user:password@127.0.0.1:8080",
        "http://127.0.0.1:8080?target=provider",
        "http://127.0.0.1:8080#target",
    ),
)
def test_proxy_origin_must_be_plain_http_without_delegated_target(
    proxy_base_url: str,
) -> None:
    with pytest.raises(ModelGatewayError, match="proxy_base_url"):
        _policy(proxy_base_url=proxy_base_url)
