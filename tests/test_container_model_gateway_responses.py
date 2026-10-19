from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.container_harness import model_gateway_responses_server
from legalforecast.multiharness.container_harness.model_gateway_responses import (
    OpenAIResponsesGateway,
    ResponsesGatewayPolicy,
    ResponsesUpstreamResponse,
    ResponsesUsage,
    openai_responses_registry_charge_extractor,
    parse_responses_usage,
)


@dataclass
class _FakeTransport:
    responses: list[ResponsesUpstreamResponse]

    def __post_init__(self) -> None:
        self.requests: list[tuple[bytes, Mapping[str, str]]] = []

    def request(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ResponsesUpstreamResponse:
        assert timeout_seconds > 0
        assert max_response_bytes > 0
        self.requests.append((body, headers))
        if not self.responses:
            raise AssertionError("unexpected upstream request")
        return self.responses.pop(0)


class _RecordingSpendController:
    def __init__(self) -> None:
        self.authorized: list[dict[str, object]] = []
        self.started: list[object] = []
        self.settled: list[dict[str, object]] = []
        self.failures: list[dict[str, object]] = []

    def authorize_request(
        self,
        *,
        request_id: str,
        body: bytes,
        model: str,
        max_tokens: int,
    ) -> object:
        lease = object()
        self.authorized.append(
            {
                "request_id": request_id,
                "body": body,
                "model": model,
                "max_tokens": max_tokens,
                "lease": lease,
            }
        )
        return lease

    def mark_transport_started(self, lease: object) -> None:
        self.started.append(lease)

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
        self.settled.append(
            {
                "lease": lease,
                "response_body": response_body,
                "response_status": response_status,
                "content_type": content_type,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )
        if response_status < 200 or response_status >= 300:
            self.record_failure(
                lease, failure_type="gateway_upstream_error", ambiguous=True
            )
        elif input_tokens is None or output_tokens is None:
            self.record_failure(
                lease, failure_type="gateway_usage_missing", ambiguous=True
            )
        return response_status == 200 and input_tokens is not None

    def record_failure(
        self, lease: object, *, failure_type: str, ambiguous: bool
    ) -> None:
        self.failures.append(
            {"lease": lease, "failure_type": failure_type, "ambiguous": ambiguous}
        )


def _policy(
    tmp_path: Path,
    *,
    max_input_tokens: int = 1_000_000,
    max_output_tokens: int = 128,
) -> ResponsesGatewayPolicy:
    return ResponsesGatewayPolicy(
        upstream_api_key="upstream-only",
        capability_token="run-capability",
        run_request_id="case-123",
        allowed_model_keys=frozenset({"openai:gpt-test"}),
        allowed_ingress_hosts=frozenset({"127.0.0.1"}),
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_total_input_tokens=max_input_tokens,
        max_total_output_tokens=max_output_tokens,
    )


def _request(*, model: str = "gpt-test", max_output_tokens: int = 8) -> bytes:
    return json.dumps(
        {
            "model": model,
            "input": [{"role": "user", "content": "hello"}],
            "max_output_tokens": max_output_tokens,
            "store": False,
            "stream": False,
        },
        separators=(",", ":"),
    ).encode()


def _response_body(*, input_tokens: int = 32, output_tokens: int = 7) -> bytes:
    return json.dumps(
        {
            "id": "resp-fixture",
            "object": "response",
            "status": "completed",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_tokens_details": {"cached_tokens": 12},
                "output_tokens_details": {"reasoning_tokens": 3},
            },
        },
        separators=(",", ":"),
    ).encode()


def _sse_body() -> bytes:
    return (
        b"event: response.output_text.delta\n"
        b'data: {"type":"response.output_text.delta","delta":"ok"}\n\n'
        b"event: response.completed\n"
        b'data: {"type":"response.completed","response":{"usage":{'
        b'"input_tokens":32,"output_tokens":7,"input_tokens_details":{'
        b'"cached_tokens":12},"output_tokens_details":{"reasoning_tokens":3}}}}\n\n'
        b"data: [DONE]\n\n"
    )


def test_nonstreaming_response_is_forwarded_byte_for_byte_and_hides_capability(
    tmp_path: Path,
) -> None:
    body = _response_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, body)]
    )
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    result = gateway.handle(
        _request(),
        authorization="Bearer run-capability",
        headers={"accept": "application/json"},
    )

    assert result.status_code == 200
    assert result.body == body
    assert result.headers["content-type"] == "application/json"
    assert transport.requests[0][1]["authorization"] == "Bearer upstream-only"
    assert "run-capability" not in transport.requests[0][1]["authorization"]


def test_streaming_response_preserves_exact_sse_and_settles_cache_usage(
    tmp_path: Path,
) -> None:
    body = _sse_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "text/event-stream"}, body)]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(
        _request(),
        authorization="Bearer run-capability",
        headers={"accept": "text/event-stream"},
    )

    assert result.status_code == 200
    assert result.body == body
    assert controller.settled[0]["response_body"] == body
    assert controller.settled[0]["content_type"] == "text/event-stream"
    assert controller.settled[0]["input_tokens"] == 32
    assert controller.settled[0]["output_tokens"] == 7
    usage = parse_responses_usage(body, "text/event-stream")
    assert usage == ResponsesUsage(32, 7, cache_read_tokens=12, reasoning_tokens=3)


def test_wrong_model_and_capability_are_rejected_before_upstream(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(_policy(tmp_path), transport=transport)

    wrong_model = gateway.handle(
        _request(model="gpt-other"), authorization="Bearer run-capability"
    )
    wrong_capability = gateway.handle(
        _request(), authorization="Bearer wrong-capability"
    )

    assert wrong_model.status_code == 400
    assert wrong_capability.status_code == 401
    assert transport.requests == []


def test_output_cap_is_rejected_before_reservation_or_upstream(tmp_path: Path) -> None:
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path, max_output_tokens=8), transport=transport
    )

    result = gateway.handle(
        _request(max_output_tokens=9), authorization="Bearer run-capability"
    )

    assert result.status_code == 429
    assert transport.requests == []


def test_input_cap_is_rejected_before_reservation_or_upstream(tmp_path: Path) -> None:
    transport = _FakeTransport([])
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path, max_input_tokens=1), transport=transport
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 429
    assert transport.requests == []


def test_upstream_failure_is_sanitized_and_recorded_as_ambiguous(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport(
        [
            ResponsesUpstreamResponse(
                500,
                {"content-type": "application/json"},
                b'{"error":{"message":"provider detail"}}',
            )
        ]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert b"provider detail" not in result.body
    assert controller.failures[0]["failure_type"] == "gateway_upstream_error"


def test_success_without_usage_fails_closed(tmp_path: Path) -> None:
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "application/json"}, b"{}")]
    )
    controller = _RecordingSpendController()
    gateway = OpenAIResponsesGateway(
        _policy(tmp_path), transport=transport, spend_controller=controller
    )

    result = gateway.handle(_request(), authorization="Bearer run-capability")

    assert result.status_code == 502
    assert controller.failures[0]["failure_type"] == "gateway_usage_missing"


def test_http_server_handles_native_responses_request_with_local_double(
    tmp_path: Path,
) -> None:
    body = _sse_body()
    transport = _FakeTransport(
        [ResponsesUpstreamResponse(200, {"content-type": "text/event-stream"}, body)]
    )
    server = model_gateway_responses_server.build_responses_gateway_server(
        _policy(tmp_path), transport=transport
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        request = _request()
        connection.request(
            "POST",
            "/v1/responses",
            body=request,
            headers={
                "Authorization": "Bearer run-capability",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        response = connection.getresponse()
        received = response.read()
        connection.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert response.status == 200
    assert received == body


def _openai_entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "openai",
            "model_id": "gpt-test",
            "display_name": "OpenAI test",
            "model_version_or_snapshot": "gpt-test",
            "provider_training_cutoff_status": "unknown",
            "max_output_tokens": 128,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1_000,
            "pricing_source": "fixture-pricing",
            "input_token_price": 1.0,
            "output_token_price": 5.0,
            "cache_read_token_price": 0.1,
            "cache_write_token_price": 1.25,
            "known_cutoff_publicity_caveats": [],
        }
    )


def test_openai_charge_extractor_prices_cached_input_and_reasoning_output() -> None:
    extractor = openai_responses_registry_charge_extractor(_openai_entry())

    actual_microusd = extractor(
        _response_body(input_tokens=32, output_tokens=7), 200, None
    )

    # 12 cached input at 0.1/M, 20 uncached input at 1/M, and 7 output at 5/M.
    assert actual_microusd == 57


def test_openai_charge_extractor_rejects_malformed_cache_dimensions() -> None:
    body = json.dumps(
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 2,
                "input_tokens_details": {"cached_tokens": 11},
            }
        }
    ).encode()
    extractor = openai_responses_registry_charge_extractor(_openai_entry())

    assert extractor(body, 200, "application/json") is None


def test_policy_rejects_non_openai_model_keys() -> None:
    with pytest.raises(ValueError, match="openai:model"):
        ResponsesGatewayPolicy(
            upstream_api_key="key",
            capability_token="cap",
            run_request_id="run",
            allowed_model_keys=frozenset({"anthropic:claude"}),
            allowed_ingress_hosts=frozenset({"127.0.0.1"}),
        )
