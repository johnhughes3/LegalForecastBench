from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from http.client import IncompleteRead
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness import model_gateway_responses_server
from legalforecast.multiharness.container_harness.model_gateway_responses import (
    OpenAIResponsesGateway,
    ResponsesTerminal,
    ResponsesUpstreamResponse,
    ResponsesUsage,
    openai_responses_registry_charge_extractor,
    parse_responses_terminal,
    parse_responses_usage,
    priced_service_tiers_for_registry_entry,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
)

from test_container_model_gateway_responses import (
    _FakeTransport,
    _openai_entry,
    _policy,
    _RecordingSpendController,
    _request,
    _response_body,
    _sse_body,
)


def test_client_accounting_headers_are_not_forwarded(tmp_path: Path) -> None:
    body = _response_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, body)]
    )
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    result = gateway.handle(
        _request(),
        authorization="Bearer run-capability",
        headers={
            "openai-beta": "responses=v1",
            "openai-organization": "client-org",
            "openai-project": "client-project",
        },
    )

    assert result.status_code == 200
    forwarded = transport.requests[0][1]
    assert forwarded["openai-beta"] == "responses=v1"
    assert "openai-organization" not in forwarded
    assert "openai-project" not in forwarded


def test_local_codex_tool_definitions_are_allowed_recursively(tmp_path: Path) -> None:
    body = _response_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, body)]
    )
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)
    tools = [
        {
            "type": "function",
            "name": "exec_command",
            "description": "Run a local command",
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"],
            },
            "strict": False,
        },
        {
            "type": "custom",
            "name": "apply_patch",
            "format": {"type": "text"},
        },
        {
            "type": "namespace",
            "name": "workspace",
            "tools": [
                {
                    "type": "function",
                    "name": "read_file",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        },
    ]

    result = gateway.handle(
        _request(tools=tools), authorization="Bearer run-capability"
    )

    assert result.status_code == 200
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "tool_type",
    ["web_search", "web_search_preview", "file_search", "mcp", "computer"],
)
def test_hosted_and_remote_tools_are_rejected_before_upstream(
    tmp_path: Path, tool_type: str
) -> None:
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    result = gateway.handle(
        _request(tools=[{"type": tool_type, "name": "remote"}]),
        authorization="Bearer run-capability",
    )

    assert result.status_code == 400
    assert transport.requests == []


def test_unpriced_service_tier_and_remote_input_url_are_rejected(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    priority = gateway.handle(
        _request(service_tier="priority"), authorization="Bearer run-capability"
    )
    remote_input = gateway.handle(
        _request(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": "https://example.invalid/evidence.png",
                        }
                    ],
                }
            ]
        ),
        authorization="Bearer run-capability",
    )

    assert priority.status_code == 400
    assert remote_input.status_code == 400
    assert transport.requests == []


def test_flex_pricing_requires_explicit_flex_service_tier(tmp_path: Path) -> None:
    body = _response_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, body)]
    )
    policy = replace(_policy(tmp_path), allowed_service_tiers=frozenset({"flex"}))
    gateway = OpenAIResponsesGateway(policy, transport=transport)

    omitted = gateway.handle(_request(), authorization="Bearer run-capability")
    explicit = gateway.handle(
        _request(service_tier="flex"), authorization="Bearer run-capability"
    )

    assert omitted.status_code == 400
    assert explicit.status_code == 200
    assert len(transport.requests) == 1


def test_registry_price_source_selects_the_only_allowed_service_tier() -> None:
    standard = _openai_entry()
    flex = replace(standard, pricing_source="OpenAI Flex pricing")

    assert priced_service_tiers_for_registry_entry(standard) == frozenset({"default"})
    assert priced_service_tiers_for_registry_entry(flex) == frozenset({"flex"})


@pytest.mark.parametrize("store", [None, True])
def test_store_must_be_explicitly_false(tmp_path: Path, store: object) -> None:
    request = json.loads(_request())
    if store is None:
        request.pop("store")
    else:
        request["store"] = store
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    result = gateway.handle(
        json.dumps(request).encode(), authorization="Bearer run-capability"
    )

    assert result.status_code == 400
    assert transport.requests == []


@pytest.mark.parametrize("terminal_status", ["failed", "incomplete"])
def test_noncompleted_terminal_settles_known_usage_but_is_not_returned_as_success(
    tmp_path: Path, terminal_status: str
) -> None:
    body = _response_body(status=terminal_status)
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, body)]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert controller.settled[0]["input_tokens"] == 32
    assert controller.settled[0]["output_tokens"] == 7
    assert controller.failures == []
    assert gateway.usage.snapshot().observed_input_tokens == 32
    assert parse_responses_terminal(body, "application/json") == ResponsesTerminal(
        terminal_status,
        ResponsesUsage(
            32,
            7,
            cache_read_tokens=12,
            cache_write_tokens=4,
            reasoning_tokens=3,
        ),
    )


@pytest.mark.parametrize("terminal_status", ["failed", "incomplete"])
def test_noncompleted_sse_terminal_settles_usage_but_returns_gateway_error(
    tmp_path: Path, terminal_status: str
) -> None:
    response = json.loads(_response_body(status=terminal_status))
    event = {
        "type": f"response.{terminal_status}",
        "response": response,
    }
    body = (
        f"event: response.{terminal_status}\n"
        f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
        "data: [DONE]\n\n"
    ).encode()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "text/event-stream"}, body)]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert controller.settled[0]["input_tokens"] == 32
    assert controller.failures == []


def test_duplicate_or_conflicting_sse_terminals_are_ambiguous(tmp_path: Path) -> None:
    body = _sse_body().replace(
        b"data: [DONE]\n\n",
        _sse_body().split(b"event: response.completed\n", 1)[1],
    )
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "text/event-stream"}, body)]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert controller.failures[0]["failure_type"] == "gateway_usage_missing"
    assert gateway.usage.snapshot().observed_input_tokens is None


class _IncompleteTransport:
    def request(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ResponsesUpstreamResponse:
        del body, headers, timeout_seconds, max_response_bytes
        raise IncompleteRead(b'{"status":"completed"', 100)


def test_http_protocol_exception_retains_unknown_usage_and_is_sanitized(
    tmp_path: Path,
) -> None:
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path),
        transport=_IncompleteTransport(),
        spend_controller=controller,
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert controller.failures[0]["failure_type"] == "gateway_transport_error"
    assert gateway.usage.snapshot().observed_input_tokens is None


class _RejectingSpendController(_RecordingSpendController):
    def authorize_request(
        self,
        *,
        request_id: str,
        body: bytes,
        model: str,
        max_tokens: int,
    ) -> object:
        del request_id, body, model, max_tokens
        raise RuntimeError("authority unavailable")


def test_spend_authorization_refusal_rejects_local_reservation_pretransport(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport([])
    controller = _RejectingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 503
    assert transport.requests == []
    snapshot = gateway.usage.snapshot()
    assert snapshot.input_tokens == 0
    assert snapshot.output_tokens == 0
    assert snapshot.reserved_input_tokens == 0
    assert snapshot.reserved_output_tokens == 0
    assert snapshot.rejected_count == 1
    assert snapshot.observed_input_tokens is None


def test_openai_charge_extractor_keeps_unknown_cache_usage_unknown() -> None:
    body = json.dumps(
        {
            "status": "completed",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 2,
                "input_tokens_details": {"cached_tokens": 0},
            },
        }
    ).encode()
    extractor = openai_responses_registry_charge_extractor(_openai_entry())

    usage = parse_responses_usage(body, "application/json")
    assert usage is not None
    assert usage.cache_write_tokens is None
    assert extractor(body, 200, "application/json") is None


def test_server_startup_sanitizes_protected_config_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def refuse(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ProtectedTerminalPaidError("sensitive protected detail")

    monkeypatch.setattr(
        model_gateway_responses_server,
        "load_paid_responses_gateway_config",
        refuse,
    )

    exit_code = model_gateway_responses_server.main(
        [
            "--paid-config",
            str(tmp_path / "paid.json"),
            "--model-registry",
            str(tmp_path / "registry.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Responses gateway failed closed\n"
    assert "sensitive protected detail" not in captured.err
