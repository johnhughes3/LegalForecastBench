"""Provider-free proof that the pinned Claude CLI uses the gateway tool path.

Run explicitly with ``LFB_RUN_CLAUDE_GATEWAY_E2E=1``. The test talks only to a
local fake Anthropic server; it skips when the pinned Claude binary is absent.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness.container_harness.model_gateway import (
    ModelGatewayPolicy,
    build_model_gateway_server,
)


class _ClaudeFixture:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.paths: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                content_length = int(self.headers["content-length"])
                payload = cast(
                    dict[str, Any], json.loads(self.rfile.read(content_length))
                )
                owner.requests.append(payload)
                owner.paths.append(self.path)
                if len(owner.requests) == 1:
                    events = owner._tool_use_events(payload)
                else:
                    events = owner._forecast_events(payload)
                body = b"".join(
                    f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()
                    for event in events
                )
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        host, port = cast(tuple[str, int], self.server.server_address)
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _message_start(
        self, payload: dict[str, Any], message_id: str
    ) -> dict[str, Any]:
        return {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": payload["model"],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 3,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 0,
                },
            },
        }

    def _tool_use_events(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            self._message_start(payload, "msg_fixture_tool"),
            {"type": "ping"},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "tool_use",
                    "id": "toolu_fixture",
                    "name": "Bash",
                    "input": {},
                },
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": json.dumps(
                        {"command": "cat case.txt"}, separators=(",", ":")
                    ),
                },
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ]

    def _forecast_events(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            self._message_start(payload, "msg_fixture_forecast"),
            {"type": "ping"},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": '{"prediction":0.73}'},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 3},
            },
            {"type": "message_stop"},
        ]


def _run_claude(
    command: list[str], *, cwd: Path, environment: dict[str, str]
) -> tuple[int, str, str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        raise AssertionError(f"Claude fixture run timed out: {stderr[-1000:]}") from exc
    return process.returncode, stdout, stderr


def test_pinned_claude_reads_case_with_bash_and_returns_forecast() -> None:
    if os.environ.get("LFB_RUN_CLAUDE_GATEWAY_E2E") != "1":
        pytest.skip("set LFB_RUN_CLAUDE_GATEWAY_E2E=1 to run the local Claude fixture")
    claude = shutil.which("claude")
    if claude is None:
        pytest.skip("pinned Claude CLI is not installed")
    version = subprocess.run(
        [claude, "--version"], capture_output=True, text=True, check=True
    )
    if "2.1.282" not in version.stdout + version.stderr:
        pytest.skip("Claude CLI is not pinned to 2.1.282")

    fixture = _ClaudeFixture()
    gateway = None
    try:
        host, port = cast(tuple[str, int], fixture.server.server_address)
        policy = ModelGatewayPolicy(
            upstream_base_url=f"http://{host}:{port}",
            upstream_api_key="provider-sentinel",
            capability_token="run-capability",
            allowed_models=frozenset({"claude-opus-5-5"}),
            allowed_ingress_hosts=frozenset({"127.0.0.1"}),
            max_requests=8,
            max_output_tokens=128_000,
            max_total_output_tokens=256_000,
        )
        gateway = build_model_gateway_server(policy)
        threading.Thread(target=gateway.serve_forever, daemon=True).start()
        gateway_host, gateway_port = cast(tuple[str, int], gateway.server_address)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("ANTHROPIC_")
            and key
            not in {
                "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX",
                "CLAUDE_CODE_USE_FOUNDRY",
            }
        }
        environment.update(
            {
                "ANTHROPIC_API_KEY": "run-capability",
                "ANTHROPIC_BASE_URL": f"http://{gateway_host}:{gateway_port}",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            }
        )
        command = [
            claude,
            "--bare",
            "--restricted",
            "--allowedTools",
            "Bash",
            "--disallowedTools",
            "WebSearch",
            "WebFetch",
            "mcp__*",
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--tools",
            "Bash",
            "--model",
            "claude-opus-5-5",
            "--json-schema",
            '{"type":"object","properties":{"prediction":{"type":"number"}},"required":["prediction"],"additionalProperties":false}',
            "-p",
            "Read case.txt with Bash, then return only the structured forecast JSON.",
            "--output-format",
            "json",
            "--no-session-persistence",
        ]
        with tempfile.TemporaryDirectory(prefix="claude-gateway-case-") as directory:
            case_dir = Path(directory)
            (case_dir / "case.txt").write_text("outcome=granted\n", encoding="utf-8")
            return_code, stdout, stderr = _run_claude(
                command, cwd=case_dir, environment=environment
            )

        assert return_code == 0, stderr
        envelope = json.loads(stdout)
        assert envelope["type"] == "result"
        assert envelope["is_error"] is False
        assert json.loads(envelope["result"]) == {"prediction": 0.73}
        assert len(fixture.requests) == 3
        assert fixture.paths == ["/v1/messages?beta=true"] * 3
        assert all(
            tool["name"] in {"Bash", "StructuredOutput"}
            for request in fixture.requests
            for tool in request.get("tools", [])
        )
        assert any(
            item.get("type") == "tool_result"
            and item.get("content") == "outcome=granted"
            for request in fixture.requests
            for message in request["messages"]
            if message.get("role") == "user"
            and isinstance(message.get("content"), list)
            for item in message["content"]
        )
        usage = gateway.gateway.usage.snapshot()
        assert usage.request_count == 3
        assert usage.rejected_count == 0
        assert usage.observed_input_tokens is not None
        assert usage.observed_output_tokens is not None
    finally:
        if gateway is not None:
            gateway.shutdown()
            gateway.server_close()
        fixture.close()
