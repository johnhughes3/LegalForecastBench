from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, cast

import pytest
from legalforecast.multiharness.container_harness.model_gateway import (
    ModelGatewayHTTPServer,
    ModelGatewayPolicy,
    build_model_gateway_server,
)


class _FakeUpstream:
    def __init__(
        self,
        *,
        body: bytes,
        content_type: str = "application/json",
        status_code: int = 200,
    ) -> None:
        self.requests: list[tuple[str, dict[str, str], bytes]] = []
        self._body = body
        self._content_type = content_type
        self._status_code = status_code
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                owner.requests.append(
                    (
                        self.path,
                        {name.lower(): value for name, value in self.headers.items()},
                        body,
                    )
                )
                self.send_response(owner._status_code)
                self.send_header("content-type", owner._content_type)
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
def _upstream(
    *,
    body: bytes,
    content_type: str = "application/json",
    status_code: int = 200,
) -> Generator[_FakeUpstream]:
    server = _FakeUpstream(
        body=body,
        content_type=content_type,
        status_code=status_code,
    )
    try:
        yield server
    finally:
        server.close()


@contextmanager
def _gateway(
    policy: ModelGatewayPolicy,
    *,
    usage_evidence_path: Path | None = None,
) -> Generator[ModelGatewayHTTPServer]:
    server = build_model_gateway_server(
        policy,
        usage_evidence_path=usage_evidence_path,
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
        "max_request_bytes": 32_768,
        "max_response_bytes": 32_768,
        "max_requests": 8,
        "max_input_tokens": 32_768,
        "max_output_tokens": 128,
        "max_total_input_tokens": 32_768,
        "max_total_output_tokens": 256,
        "upstream_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return ModelGatewayPolicy(**values)


def _message_body(**overrides: Any) -> bytes:
    value: dict[str, Any] = {
        "model": "claude-fixture",
        "max_tokens": 4,
        "messages": [{"role": "user", "content": "forecast"}],
    }
    value.update(overrides)
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _request(
    server: ModelGatewayHTTPServer,
    *,
    method: str = "POST",
    path: str = "/v1/messages",
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    host, port = cast(tuple[str, int], server.server_address)
    connection = HTTPConnection(host, port, timeout=5)
    try:
        request_headers = {"content-length": str(len(body))}
        request_headers.update(headers or {})
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _success_response() -> bytes:
    return json.dumps(
        {
            "id": "msg_fixture",
            "type": "message",
            "role": "assistant",
            "content": [],
            "usage": {"input_tokens": 7, "output_tokens": 2},
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_forwards_only_messages_and_injects_provider_key_at_upstream() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        body = _message_body(
            tools=[
                {
                    "name": "Bash",
                    "description": "run local commands",
                    "input_schema": {"type": "object"},
                }
            ]
        )
        with _gateway(policy) as gateway:
            status, response_body = _request(
                gateway,
                path="/v1/messages?beta=true",
                body=body,
                headers={
                    "x-api-key": policy.capability_token,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": (
                        "effort-2025-11-24,unapproved-premium-routing-beta"
                    ),
                    "authorization": "Bearer " + policy.capability_token,
                },
            )

        assert status == 200
        assert json.loads(response_body)["id"] == "msg_fixture"
        assert len(upstream.requests) == 1
        path, headers, forwarded_body = upstream.requests[0]
        assert path == "/v1/messages?beta=true"
        assert headers["x-api-key"] == policy.upstream_api_key
        assert headers.get("authorization") is None
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["anthropic-beta"] == "effort-2025-11-24"
        assert forwarded_body == body


def test_web_tool_request_never_reaches_upstream() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, response_body = _request(
                gateway,
                body=_message_body(
                    tools=[{"type": "web_search_20250305", "name": "lookup"}]
                ),
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 400
        assert b"provider-side web tools" in response_body
        assert upstream.requests == []


@pytest.mark.parametrize(
    "body",
    (
        _message_body(service_tier="priority"),
        _message_body(speed="fast"),
        _message_body(inference_geo="us"),
        _message_body(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "forecast",
                            "cache_control": {
                                "type": "ephemeral",
                                "ttl": "1h",
                            },
                        }
                    ],
                }
            ]
        ),
        _message_body(
            system=[
                {
                    "type": "text",
                    "text": "system",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                }
            ]
        ),
        _message_body(
            tools=[
                {
                    "name": "Bash",
                    "description": "run local commands",
                    "input_schema": {"type": "object"},
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                }
            ]
        ),
    ),
)
def test_paid_pricing_options_never_reach_upstream(body: bytes) -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, _ = _request(
                gateway,
                body=body,
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 400
        assert upstream.requests == []


def test_approved_cache_control_values_reach_upstream_unchanged() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        body = _message_body(
            system=[
                {
                    "type": "text",
                    "text": "system",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[
                {
                    "name": "Bash",
                    "description": "run local commands",
                    "input_schema": {"type": "object"},
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
        )
        with _gateway(policy) as gateway:
            status, _ = _request(
                gateway,
                body=body,
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 200
        assert upstream.requests[0][2] == body


@pytest.mark.parametrize(
    "remote_field",
    (
        "mcp_servers",
        "mcp_config",
        "connectors",
        "remote_tools",
        "server_tools",
        "web_search_options",
        "web_fetch_options",
        "mcpServers",
    ),
)
def test_top_level_remote_tool_fields_never_reach_upstream(
    remote_field: str,
) -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, response_body = _request(
                gateway,
                body=_message_body(**{remote_field: {"url": "https://example.test"}}),
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 400
        assert b"remote provider tools" in response_body
        assert upstream.requests == []


@pytest.mark.parametrize(
    "tools",
    (
        "not-an-array",
        [1],
        [{"description": "missing name and type"}],
        [{"name": 42}],
        [{"name": "Bash", "description": "missing schema"}],
        [
            {
                "name": "Bash",
                "description": "unknown field",
                "input_schema": {"type": "object"},
                "future_field": True,
            }
        ],
        [
            {
                "name": "advisor",
                "type": "advisor_20260301",
                "defer_loading": True,
            }
        ],
    ),
)
def test_malformed_tools_fail_closed(tools: object) -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, _ = _request(
                gateway,
                body=_message_body(tools=tools),
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 400
        assert upstream.requests == []


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    (
        ({}, 401),
        ({"x-api-key": "wrong"}, 401),
        ({"authorization": "Basic run-capability-sentinel"}, 401),
        (
            {
                "x-api-key": "run-capability-sentinel",
                "authorization": "Bearer wrong",
            },
            401,
        ),
    ),
)
def test_requires_the_run_capability(
    headers: dict[str, str], expected_status: int
) -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, _ = _request(
                gateway,
                body=_message_body(),
                headers=headers,
            )

        assert status == expected_status
        assert upstream.requests == []


def test_direct_external_style_routes_and_connect_are_not_a_proxy() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            route_status, _ = _request(
                gateway,
                method="POST",
                path="/anything-else",
                body=_message_body(),
                headers={"x-api-key": policy.capability_token},
            )
            absolute_route_status, _ = _request(
                gateway,
                method="POST",
                path="http://other.example/v1/messages",
                body=_message_body(),
                headers={"x-api-key": policy.capability_token},
            )
            connect_status, _ = _request(
                gateway,
                method="CONNECT",
                path="example.com:443",
                headers={"x-api-key": policy.capability_token},
            )

        assert route_status == 404
        assert absolute_route_status == 404
        assert connect_status == 405
        assert upstream.requests == []


def test_transfer_encoding_is_rejected_before_upstream() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            transfer_status, _ = _request(
                gateway,
                body=_message_body(),
                headers={
                    "x-api-key": policy.capability_token,
                    "transfer-encoding": "chunked",
                },
            )

        assert transfer_status == 400
        assert upstream.requests == []


def test_unrecognized_ingress_host_is_rejected_before_auth_or_upstream() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, _ = _request(
                gateway,
                body=_message_body(),
                headers={
                    "Host": "attacker.example:443",
                    "x-api-key": policy.capability_token,
                },
            )

        assert status == 404
        assert upstream.requests == []


def test_model_and_request_limits_fail_before_upstream() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream, max_input_tokens=10, max_output_tokens=2)
        with _gateway(policy) as gateway:
            unknown_model_status, _ = _request(
                gateway,
                body=_message_body(model="unapproved"),
                headers={"x-api-key": policy.capability_token},
            )
            input_status, _ = _request(
                gateway,
                body=_message_body(),
                headers={"x-api-key": policy.capability_token},
            )
            output_status, _ = _request(
                gateway,
                body=_message_body(max_tokens=3),
                headers={"x-api-key": policy.capability_token},
            )

        assert unknown_model_status == 400
        assert input_status == 429
        assert output_status == 429
        assert upstream.requests == []


def test_budget_accounts_all_accepted_calls_and_rejects_the_next() -> None:
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream, max_requests=1, max_total_output_tokens=4)
        with _gateway(policy) as gateway:
            first_status, _ = _request(
                gateway,
                body=_message_body(max_tokens=4),
                headers={"x-api-key": policy.capability_token},
            )
            second_status, second_body = _request(
                gateway,
                body=_message_body(max_tokens=1),
                headers={"x-api-key": policy.capability_token},
            )
            usage = gateway.gateway.usage.snapshot()

        assert first_status == 200
        assert second_status == 429
        assert b"request budget exhausted" in second_body
        assert len(upstream.requests) == 1
        assert usage.request_count == 1
        assert usage.reserved_input_tokens == 0
        assert usage.reserved_output_tokens == 0
        assert usage.rejected_count == 1
        assert usage.output_tokens == 2


def test_stream_usage_is_observed_without_changing_sse_body() -> None:
    body = (
        b'data: {"type":"message_start","message":{"usage":{"input_tokens":3}}}\n\n'
        b'data: {"type":"message_delta","usage":{"output_tokens":2}}\n\n'
        b"data: [DONE]\n\n"
    )
    with _upstream(body=body, content_type="text/event-stream") as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, response_body = _request(
                gateway,
                body=_message_body(stream=True),
                headers={"x-api-key": policy.capability_token},
            )
            usage = gateway.gateway.usage.snapshot()

        assert status == 200
        assert response_body == body
        assert usage.input_tokens == 3
        assert usage.output_tokens == 2
        assert usage.observed_input_tokens == 3
        assert usage.observed_output_tokens == 2


def test_usage_evidence_is_atomic_and_separates_observed_from_accounted(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "usage.json"
    with _upstream(body=_success_response()) as upstream:
        policy = _policy(upstream, max_requests=1)
        with _gateway(policy, usage_evidence_path=evidence_path) as gateway:
            first_status, _ = _request(
                gateway,
                body=_message_body(max_tokens=4),
                headers={"x-api-key": policy.capability_token},
            )
            second_status, _ = _request(
                gateway,
                body=_message_body(max_tokens=4),
                headers={"x-api-key": policy.capability_token},
            )

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert first_status == 200
    assert second_status == 429
    assert evidence == {
        "accounted_input_tokens": 7,
        "accounted_output_tokens": 2,
        "observed_input_tokens": 7,
        "observed_output_tokens": 2,
        "rejected_count": 1,
        "request_count": 1,
        "reserved_input_tokens": 0,
        "reserved_output_tokens": 0,
        "schema_version": 1,
    }
    assert evidence_path.stat().st_mode & 0o077 == 0


def test_usage_evidence_keeps_observed_usage_unknown_on_ambiguous_response(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "usage.json"
    with _upstream(body=b'{"ok":true}') as upstream:
        policy = _policy(upstream, max_requests=1)
        with _gateway(policy, usage_evidence_path=evidence_path) as gateway:
            status, _ = _request(
                gateway,
                body=_message_body(max_tokens=4),
                headers={"x-api-key": policy.capability_token},
            )

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert status == 200
    assert evidence["accounted_input_tokens"] == len(_message_body(max_tokens=4))
    assert evidence["accounted_output_tokens"] == 4
    assert evidence["observed_input_tokens"] is None
    assert evidence["observed_output_tokens"] is None


def test_provider_error_body_is_not_returned_to_harness() -> None:
    with _upstream(
        body=b'{"error":"provider-sentinel-never-in-harness"}',
        status_code=500,
    ) as upstream:
        policy = _policy(upstream)
        with _gateway(policy) as gateway:
            status, response_body = _request(
                gateway,
                body=_message_body(),
                headers={"x-api-key": policy.capability_token},
            )

        assert status == 502
        assert b"provider-sentinel" not in response_body
        assert len(upstream.requests) == 1
