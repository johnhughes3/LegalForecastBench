from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    model_registry_entry_sha256,
)
from legalforecast.multiharness.container_harness import model_gateway_responses_server
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    PAID_GATEWAY_CONFIG_SCHEMA,
    PAID_GATEWAY_WORKFLOW_MARKER,
)
from legalforecast.multiharness.container_harness.model_gateway_responses import (
    OpenAIResponsesGateway,
    ResponsesGatewayPolicy,
    ResponsesUpstreamResponse,
    load_paid_responses_gateway_config,
)

from test_container_model_gateway_responses import _request, _response_body

_ENVIRONMENT = {
    "GITHUB_ACTIONS": "true",
    "LFB_PROTECTED_TERMINAL_RELEASE": "1",
    "LFB_PROVIDER_AUTHORITY_TABLE": "provider-spend",
    "LFB_AWS_REGION": "us-east-1",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256": "c" * 64,
}


def _production_loaded_policy(tmp_path: Path) -> ResponsesGatewayPolicy:
    registry_path = (
        Path(__file__).parents[1]
        / "model_registries/cycle-1-agentic-gpt-6.1-sol-high-2026-09-29.json"
    )
    registry = load_model_registry(registry_path)
    entry = registry.entries[0]
    config_path = tmp_path / "paid-gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": PAID_GATEWAY_CONFIG_SCHEMA,
                "workflow_marker": PAID_GATEWAY_WORKFLOW_MARKER,
                "cycle_id": "cycle-1",
                "account": "official",
                "model_key": entry.registry_key,
                "ceiling_microusd": 50_000_000,
                "max_requests": 8,
                "authority_identity_sha256": "a" * 64,
                "reservation_ledger_sha256": "b" * 64,
                "provider_authority_table": "provider-spend",
                "provider_authority_region": "us-east-1",
                "provider_authority_resource_identity_sha256": "c" * 64,
                "model_registry_sha256": registry.source_sha256,
                "model_registry_entry_sha256": model_registry_entry_sha256(entry),
                "harness_id": "codex",
                "pricing_service_tier": "default",
            }
        ),
        encoding="utf-8",
    )
    paid_config = load_paid_responses_gateway_config(
        config_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )
    return model_gateway_responses_server.build_paid_responses_gateway_policy(
        paid_config,
        upstream_api_key="upstream-only",
        capability_token="run-capability",
        run_request_id="case-123",
    )


def test_production_loaded_registry_injects_explicit_standard_tier(
    tmp_path: Path,
) -> None:
    body = _response_body(service_tier="default")
    transport = _CodexLoopTransport([])
    transport_response = ResponsesUpstreamResponse(
        200, {"content-type": "application/json"}, body
    )

    class OneResponseTransport:
        def request(
            self,
            request_body: bytes,
            headers: Mapping[str, str],
            *,
            timeout_seconds: float,
            max_response_bytes: int,
        ) -> ResponsesUpstreamResponse:
            del headers, timeout_seconds, max_response_bytes
            transport.requests.append(json.loads(request_body))
            return transport_response

    gateway = OpenAIResponsesGateway(
        _production_loaded_policy(tmp_path), transport=OneResponseTransport()
    )

    result = gateway.handle(
        _request(model="gpt-6.1-sol"), authorization="Bearer run-capability"
    )

    assert result.status_code == 200
    assert transport.requests[0]["service_tier"] == "default"


@dataclass
class _CodexLoopTransport:
    requests: list[dict[str, object]]

    def request(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ResponsesUpstreamResponse:
        del headers, timeout_seconds, max_response_bytes
        payload = json.loads(body)
        assert isinstance(payload, dict)
        self.requests.append(payload)
        response_id = f"local-{len(self.requests)}"
        if len(self.requests) == 1:
            tools = payload.get("tools")
            assert isinstance(tools, list)
            names = [
                tool.get("name")
                for tool in tools
                if isinstance(tool, dict) and isinstance(tool.get("name"), str)
            ]
            tool_name = "exec_command" if "exec_command" in names else "shell_command"
            assert tool_name in names
            output_item: dict[str, object] = {
                "type": "function_call",
                "call_id": "call-read",
                "name": tool_name,
                "arguments": json.dumps(
                    {"cmd": "cat input.txt"}
                    if tool_name == "exec_command"
                    else {"command": "cat input.txt"},
                    separators=(",", ":"),
                ),
            }
        else:
            request_input = payload.get("input")
            assert isinstance(request_input, list)
            assert any(
                isinstance(item, dict)
                and item.get("type") == "function_call_output"
                and item.get("call_id") == "call-read"
                for item in request_input
            )
            output_item = {
                "type": "message",
                "role": "assistant",
                "id": "message-final",
                "content": [{"type": "output_text", "text": "NATIVE_LOOP_OK"}],
            }
        response = {
            "id": response_id,
            "status": "completed",
            "service_tier": "default",
            "usage": {
                "input_tokens": 1,
                "input_tokens_details": {
                    "cached_tokens": 0,
                    "cache_write_tokens": 0,
                },
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 2,
            },
        }
        events = [
            {"type": "response.created", "response": {"id": response_id}},
            {"type": "response.output_item.done", "item": output_item},
            {"type": "response.completed", "response": response},
        ]
        stream = b"".join(
            (
                f"event: {event['type']}\n"
                f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
            ).encode()
            for event in events
        )
        return ResponsesUpstreamResponse(
            200, {"content-type": "text/event-stream"}, stream
        )


def test_real_pinned_codex_owns_tool_loop_through_local_gateway(
    tmp_path: Path,
) -> None:
    """Run the exact checked-in Codex pin without credentials or provider spend."""

    binary_value = os.environ.get("LEGALFORECAST_CODEX_0147_BIN")
    if not binary_value:
        pytest.skip("set LEGALFORECAST_CODEX_0147_BIN for pinned offline integration")
    binary = Path(binary_value).resolve()
    manifest = json.loads(
        (
            Path(__file__).parents[1]
            / "examples/adapters/codex-cli/local-cli-manifest.json"
        ).read_text(encoding="utf-8")
    )
    expected = manifest["executable"]
    assert expected["version"] == "codex-cli 0.147.0"
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == expected["sha256"]
    version = subprocess.run(
        [str(binary), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == expected["version"]

    transport = _CodexLoopTransport([])
    server = model_gateway_responses_server.build_responses_gateway_server(
        _production_loaded_policy(tmp_path), transport=transport
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("PINNED_CODEX_INPUT\n", encoding="utf-8")
    isolated_home = tmp_path / "home"
    isolated_codex_home = tmp_path / "codex-home"
    isolated_home.mkdir()
    isolated_codex_home.mkdir()
    port = int(server.server_address[1])
    provider = (
        'model_providers.lfb_stub={name="lfb-loopback-stub",'
        f'base_url="http://127.0.0.1:{port}/v1",'
        'env_key="LFB_RESPONSES_CAPABILITY_TOKEN",wire_api="responses",'
        "requires_openai_auth=false,supports_websockets=false,"
        "request_max_retries=0,stream_max_retries=0}"
    )
    command = [
        str(binary),
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--skip-git-repo-check",
        "--sandbox",
        "danger-full-access",
        "--model",
        "gpt-6.1-sol",
        "-C",
        str(workspace),
        "-c",
        provider,
        "-c",
        'model_provider="lfb_stub"',
        "-c",
        'web_search="disabled"',
        "-c",
        'approval_policy="never"',
        "Read input.txt with your local shell tool, then report the result.",
    ]
    environment = {
        "CODEX_HOME": str(isolated_codex_home),
        "HOME": str(isolated_home),
        "LFB_RESPONSES_CAPABILITY_TOKEN": "run-capability",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert len(transport.requests) == 2
    first_request = transport.requests[0]
    assert first_request["store"] is False
    assert first_request["service_tier"] == "default"
    tools = first_request["tools"]
    assert isinstance(tools, list)
    assert {
        tool["type"] for tool in tools if isinstance(tool, dict) and "type" in tool
    } <= {"custom", "function", "namespace"}
    second_input = transport.requests[1]["input"]
    assert isinstance(second_input, list)
    assert any(
        isinstance(item, dict) and item.get("type") == "function_call_output"
        for item in second_input
    )
    assert "NATIVE_LOOP_OK" in completed.stdout
    assert "OPENAI_API_KEY" not in environment
