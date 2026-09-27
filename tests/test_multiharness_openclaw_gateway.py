from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness.model_gateway import (
    ModelGatewayPolicy,
    build_model_gateway_server,
)
from legalforecast.multiharness.openclaw import OpenClawError
from legalforecast.multiharness.openclaw_runtime import (
    GatewayRuntimeConfig,
    build_config,
)
from legalforecast.multiharness.openclaw_worker import CAPABILITY_ENV, execute, main
from legalforecast.multiharness.spec import RunResult

from test_multiharness_openclaw import request


def test_gateway_config_uses_native_anthropic_and_only_run_capability() -> None:
    gateway = GatewayRuntimeConfig("run-capability", 200000, 2048)
    config = build_config("claude-opus-5-5", 9, gateway=gateway)
    provider = config["models"]["providers"]["anthropic"]
    assert provider["api"] == "anthropic-messages"
    assert provider["baseUrl"] == "http://lfb-model-gateway:8080"
    assert provider["apiKey"] == "run-capability"
    assert provider["models"][0]["maxTokens"] == 2048
    assert config["agents"]["defaults"]["model"] == {
        "primary": "anthropic/claude-opus-5-5",
        "fallbacks": [],
    }
    assert config["plugins"]["allow"] == ["anthropic", "lfb-container-tool"]
    assert "OPENAI_API_KEY" not in json.dumps(config)


@pytest.mark.parametrize(
    "capability,context,output", [("", 200000, 2048), ("x", 0, 10), ("x", 10, 0)]
)
def test_invalid_gateway_config_refused(
    capability: str, context: int, output: int
) -> None:
    with pytest.raises(OpenClawError):
        GatewayRuntimeConfig(capability, context, output)


class AnthropicFixture:
    """Local provider double: drives native tools, never returns canned success."""

    def __init__(
        self, host: str = "127.0.0.1", port: int = 0, hold: bool = False
    ) -> None:
        self.requests: list[dict] = []
        self.headers: list[str | None] = []
        self.pages: list[str] = []
        self.released = threading.Event()
        if not hold:
            self.released.set()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/release":
                    owner.released.set()
                output = json.dumps(
                    {
                        "requests": owner.requests,
                        "headers": owner.headers,
                        "pages": owner.pages,
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(output)))
                self.end_headers()
                self.wfile.write(output)

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(body)
                owner.headers.append(self.headers.get("x-api-key"))
                assert owner.released.wait(timeout=45), "fixture release timed out"
                assert [tool["name"] for tool in body["tools"]] == ["lfb_read_task"]
                results = [
                    block
                    for message in body["messages"]
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "tool_result"
                ]
                page = None
                if results:
                    content = results[-1]["content"]
                    text = (
                        content
                        if isinstance(content, str)
                        else "".join(item.get("text", "") for item in content)
                    )
                    page = json.loads(text)
                    if "content" in page:
                        owner.pages.append(page["content"])
                if page and page.get("complete"):
                    block = {"type": "text", "text": ""}
                    delta = {
                        "type": "text_delta",
                        "text": json.dumps(
                            {
                                "case_assessment": "Read complete fixture evidence.",
                                "predictions": [
                                    {
                                        "unit_id": "count-1",
                                        "probability_fully_dismissed": 0.37,
                                    }
                                ],
                            }
                        ),
                    }
                    stop = "end_turn"
                else:
                    block = {
                        "type": "tool_use",
                        "id": f"read_{len(owner.requests)}",
                        "name": "lfb_read_task",
                        "input": {},
                    }
                    delta = {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(
                            {
                                "page": page["next_page"] if page else 0,
                                "receipt": page["receipt"] if page else "",
                            }
                        ),
                    }
                    stop = "tool_use"
                events = [
                    {
                        "type": "message_start",
                        "message": {
                            "id": f"msg_{len(owner.requests)}",
                            "type": "message",
                            "role": "assistant",
                            "content": [],
                            "model": body["model"],
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": {
                                "input_tokens": 10,
                                "output_tokens": 0,
                                "cache_creation_input_tokens": 0,
                                "cache_read_input_tokens": 0,
                            },
                        },
                    },
                    {"type": "content_block_start", "index": 0, "content_block": block},
                    {"type": "content_block_delta", "index": 0, "delta": delta},
                    {"type": "content_block_stop", "index": 0},
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": stop, "stop_sequence": None},
                        "usage": {"output_tokens": 10},
                    },
                    {"type": "message_stop"},
                ]
                output = "".join(
                    f"event: {item['type']}\ndata: {json.dumps(item)}\n\n"
                    for item in events
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(output)))
                self.end_headers()
                self.wfile.write(output)

            def log_message(self, *_: object) -> None:
                pass

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.mark.skipif(
    os.environ.get("LEGALFORECAST_OPENCLAW_E2E") != "1",
    reason="installed OpenClaw integration, local provider double only",
)
def test_native_anthropic_loop_through_real_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream = AnthropicFixture()
    gateway = build_model_gateway_server(
        ModelGatewayPolicy(
            upstream_base_url=f"http://127.0.0.1:{upstream.server.server_port}",
            upstream_api_key="upstream-only-sentinel",
            capability_token="run-capability",
            allowed_models=frozenset({"claude-opus-5-5"}),
            allowed_ingress_hosts=frozenset({"127.0.0.1"}),
            max_requests=24,
        )
    )
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        "legalforecast.multiharness.openclaw_runtime.GATEWAY_BASE_URL",
        f"http://127.0.0.1:{gateway.server_port}",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-provider-must-not-leak")
    original = request()
    req = replace(
        original,
        model_key="anthropic:claude-opus-5-5",
        sandbox_policy=replace(
            original.sandbox_policy, allowed_provider_env_vars=(), timeout_seconds=120
        ),
    )
    prompt = "BEGIN " + "m" * 45000 + " MIDDLE " + "n" * 45000 + " END"
    (tmp_path / "prompt.txt").write_text(prompt)
    (tmp_path / "openclaw-request.json").write_text(json.dumps(req.to_record()))
    (tmp_path / "openclaw-model.json").write_text(
        json.dumps(
            {
                "context_limit": 200000,
                "max_output_tokens": 2048,
                "reasoning_effort": "high",
            }
        )
    )
    monkeypatch.setenv(CAPABILITY_ENV, "run-capability")
    try:
        execute(tmp_path)
        result = RunResult.from_record(
            json.loads((tmp_path / "openclaw-result.json").read_text())
        )
    except OpenClawError:
        pytest.fail((tmp_path / "private-logs/openclaw-stderr.log").read_text())
    finally:
        gateway.shutdown()
        gateway.server_close()
        thread.join(timeout=5)
        upstream.close()
    assert result.status == "succeeded"
    assert "".join(upstream.pages) == prompt
    assert len(upstream.requests) == len(upstream.pages) + 2
    assert set(upstream.headers) == {"upstream-only-sentinel"}
    assert "ambient-provider-must-not-leak" not in json.dumps(upstream.requests)
    assert result.public_summary["auth_mode"] == "protected-gateway-capability"
    assert result.public_summary["provider"] == "anthropic"
    assert gateway.gateway.usage.snapshot().rejected_count == 0
    output = json.loads((tmp_path / result.artifacts[0].path).read_text())
    assert output["predictions"][0]["probability_fully_dismissed"] == 0.37


def test_worker_rejects_arbitrary_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["openclaw", "--base-url", "https://other"])
    assert main() == 1
    assert "Contained OpenClaw failed" in capsys.readouterr().err
