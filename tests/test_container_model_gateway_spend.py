from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, cast

from legalforecast.multiharness.container_harness.model_gateway import (
    GatewaySpendController,
    ModelGatewayHTTPServer,
    ModelGatewayPolicy,
    build_model_gateway_server,
)


class _FakeUpstream:
    def __init__(self, body: bytes) -> None:
        self.requests: list[bytes] = []
        self._body = body
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                owner.requests.append(self.rfile.read(length))
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(owner._body)))
                self.end_headers()
                self.wfile.write(owner._body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        host, port = cast(tuple[str, int], self.server.server_address)
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@contextmanager
def _upstream() -> Generator[_FakeUpstream]:
    upstream = _FakeUpstream(_success_response())
    try:
        yield upstream
    finally:
        upstream.close()


@contextmanager
def _gateway(
    policy: ModelGatewayPolicy,
    controller: GatewaySpendController,
) -> Generator[ModelGatewayHTTPServer]:
    server = build_model_gateway_server(
        policy,
        spend_controller=controller,
        request_id="run-case-1",
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _policy(upstream: _FakeUpstream, **overrides: Any) -> ModelGatewayPolicy:
    values: dict[str, Any] = {
        "upstream_base_url": upstream.base_url,
        "upstream_api_key": "provider-sentinel-never-in-harness",
        "capability_token": "run-capability-sentinel",
        "allowed_models": frozenset({"claude-fixture"}),
        "allowed_ingress_hosts": frozenset({"127.0.0.1"}),
        "max_requests": 4,
        "max_input_tokens": 32_768,
        "max_output_tokens": 128,
        "max_total_input_tokens": 32_768,
        "max_total_output_tokens": 256,
        "upstream_timeout_seconds": 1.0,
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


def _success_response() -> bytes:
    return json.dumps(
        {"usage": {"input_tokens": 7, "output_tokens": 2}},
        separators=(",", ":"),
    ).encode("utf-8")


def _request(
    server: ModelGatewayHTTPServer,
    body: bytes,
) -> tuple[int, bytes]:
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


class _FakeSpendController:
    def __init__(
        self,
        *,
        authorize_error: Exception | None = None,
        transport_start_error: Exception | None = None,
        settle_result: bool = True,
        settle_error: Exception | None = None,
    ) -> None:
        self.authorize_error = authorize_error
        self.transport_start_error = transport_start_error
        self.settle_result = settle_result
        self.settle_error = settle_error
        self.authorize_calls: list[tuple[str, bytes, str, int]] = []
        self.settle_calls: list[
            tuple[object, bytes, int, str | None, int | None, int | None]
        ] = []
        self.failure_calls: list[tuple[object, str, bool]] = []
        self.transport_started_calls: list[object] = []

    def authorize_request(
        self,
        *,
        request_id: str,
        body: bytes,
        model: str,
        max_tokens: int,
    ) -> object:
        self.authorize_calls.append((request_id, body, model, max_tokens))
        if self.authorize_error is not None:
            raise self.authorize_error
        return object()

    def mark_transport_started(self, lease: object) -> None:
        self.transport_started_calls.append(lease)
        if self.transport_start_error is not None:
            raise self.transport_start_error

    def settle_response(
        self,
        lease: object,
        *,
        response_body: bytes,
        response_status: int,
        content_type: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        self.settle_calls.append(
            (
                lease,
                response_body,
                response_status,
                content_type,
                input_tokens,
                output_tokens,
            )
        )
        if self.settle_error is not None:
            raise self.settle_error
        return self.settle_result

    def record_failure(
        self,
        lease: object,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        self.failure_calls.append((lease, failure_type, ambiguous))


def test_paid_controller_authorizes_and_settles_each_request_with_run_id() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream, max_requests=2)
        controller = _FakeSpendController()
        body = _message_body()
        with _gateway(policy, controller) as gateway:
            first_status, _ = _request(gateway, body)
            second_status, _ = _request(gateway, body)

    assert first_status == 200
    assert second_status == 200
    assert [call[0] for call in controller.authorize_calls] == [
        "run-case-1",
        "run-case-1",
    ]
    assert all(call[2:] == ("claude-fixture", 4) for call in controller.authorize_calls)
    assert [call[2:] for call in controller.settle_calls] == [
        (200, "application/json", 7, 2),
        (200, "application/json", 7, 2),
    ]
    assert len(controller.transport_started_calls) == 2
    assert controller.failure_calls == []


def test_paid_authorization_failure_blocks_upstream_and_settles_reservation() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream)
        controller = _FakeSpendController(authorize_error=RuntimeError("denied"))
        with _gateway(policy, controller) as gateway:
            status, response_body = _request(gateway, _message_body())
            usage = gateway.gateway.usage.snapshot()

    assert status == 503
    assert b"spend authorization failed" in response_body
    assert upstream.requests == []
    assert usage.request_count == 1
    assert usage.reserved_input_tokens == 0
    assert usage.reserved_output_tokens == 0
    assert controller.settle_calls == []
    assert controller.failure_calls == []


def test_transport_marker_failure_blocks_upstream_and_retains_spend_failure() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream)
        controller = _FakeSpendController(
            transport_start_error=RuntimeError("marker unavailable")
        )
        with _gateway(policy, controller) as gateway:
            status, response_body = _request(gateway, _message_body())
            usage = gateway.gateway.usage.snapshot()

    assert status == 503
    assert b"spend authorization failed" in response_body
    assert upstream.requests == []
    assert len(controller.transport_started_calls) == 1
    assert len(controller.failure_calls) == 1
    assert controller.failure_calls[0][1:] == (
        "gateway_transport_start_error",
        True,
    )
    assert usage.request_count == 1
    assert usage.reserved_input_tokens == 0
    assert usage.reserved_output_tokens == 0


def test_paid_settlement_failure_does_not_return_provider_success() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream)
        controller = _FakeSpendController(settle_result=False)
        with _gateway(policy, controller) as gateway:
            status, response_body = _request(gateway, _message_body())

    assert status == 502
    assert b"charge evidence unavailable" in response_body
    assert len(upstream.requests) == 1
    assert len(controller.settle_calls) == 1


def test_paid_settlement_exception_is_recorded_as_ambiguous() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream)
        controller = _FakeSpendController(settle_error=RuntimeError("ledger down"))
        with _gateway(policy, controller) as gateway:
            status, _ = _request(gateway, _message_body())

    assert status == 503
    assert [(failure[1], failure[2]) for failure in controller.failure_calls] == [
        ("gateway_settlement_error", True)
    ]


def test_paid_transport_failure_is_recorded_as_ambiguous() -> None:
    with _upstream() as upstream:
        policy = _policy(upstream)
        upstream.close()
        controller = _FakeSpendController()
        with _gateway(policy, controller) as gateway:
            status, _ = _request(gateway, _message_body())

    assert status == 502
    assert [(failure[1], failure[2]) for failure in controller.failure_calls] == [
        ("gateway_transport_error", True)
    ]
