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
from legalforecast.multiharness.container_harness import model_gateway_responses_server
from legalforecast.multiharness.container_harness.model_gateway_responses import (
    ResponsesUpstreamResponse,
)

from test_container_model_gateway_responses import _policy


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
        _policy(tmp_path), transport=transport
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
        "gpt-test",
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
