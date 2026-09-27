from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.harvey_tools import HarveyToolExecutor
from legalforecast.multiharness.openclaw import (
    ADAPTER_ID,
    OPENCLAW_COMMIT,
    OPENCLAW_VERSION,
    OpenClawError,
    normalize_result,
    offline_fixture,
)
from legalforecast.multiharness.openclaw_runtime import (
    build_config,
    run_openclaw,
    runtime_root,
    verify_runtime,
)
from legalforecast.multiharness.openclaw_tool import (
    PromptDelivery,
    bridge_read,
    prompt_pages,
)
from legalforecast.multiharness.runner import validate_provider_environment_scope
from legalforecast.multiharness.sandbox import PROVIDER_EGRESS_HOST_ONLY
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/adapters/openclaw-pinned/adapter-manifest.json"


def request() -> RunRequest:
    return RunRequest(
        request_id="openclaw-case-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="v1",
            source_id="case-1",
            task_sha256="sha256:" + "1" * 64,
            metadata={"required_unit_ids": ["count-1"]},
        ),
        adapter=AdapterManifest.from_record(json.loads(MANIFEST.read_text())),
        model_key="openai:gpt-test",
        sandbox_policy=SandboxPolicy(
            policy_id="host-tools",
            backend="podman",
            image="worker@sha256:" + "2" * 64,
            network_policy=PROVIDER_EGRESS_HOST_ONLY,
            timeout_seconds=30,
            allowed_provider_env_vars=("OPENAI_API_KEY",),
        ),
        request_sha256="sha256:" + "3" * 64,
    )


def envelope(probability: float = 0.73) -> dict[str, object]:
    return {
        "ok": True,
        "status": "ok",
        "provider": "openai",
        "model": "gpt-test",
        "final": json.dumps(
            {
                "case_assessment": "Assessment from staged evidence.",
                "predictions": [
                    {"unit_id": "count-1", "probability_fully_dismissed": probability}
                ],
            }
        ),
    }


def test_public_manifest_and_offline_conformance(tmp_path: Path) -> None:
    adapter = CommandAdapter.from_manifest_file(MANIFEST, timeout_seconds=30)
    assert adapter.capabilities(tmp_path / "caps").adapter_id == ADAPTER_ID
    report = run_adapter_conformance(
        adapter_manifest_path=MANIFEST,
        output_dir=tmp_path / "conformance",
        timeout_seconds=30,
    ).report
    assert report.status == "passed"
    assert report.checks["lfb_fixture_run"].startswith("passed:")


def test_normalization_retains_actual_predictions_privately(tmp_path: Path) -> None:
    result = normalize_result(
        request(), tmp_path, envelope(), tool_reads=2, prompt_complete=True
    )
    artifact = result.artifacts[0]
    assert artifact.public is False
    forecast = json.loads((tmp_path / artifact.path).read_text())
    assert forecast["predictions"][0]["probability_fully_dismissed"] == 0.73
    assert result.public_summary["openclaw_commit"] == OPENCLAW_COMMIT
    assert "Assessment" not in json.dumps(result.public_summary)
    assert (
        result.result_sha256
        != normalize_result(
            request(),
            tmp_path / "other",
            envelope(0.12),
            tool_reads=2,
            prompt_complete=True,
        ).result_sha256
    )


def test_normalization_retains_parser_accepted_fenced_forecast(tmp_path: Path) -> None:
    value = envelope()
    value["final"] = f"```json\n{value['final']}\n```"
    result = normalize_result(
        request(), tmp_path, value, tool_reads=2, prompt_complete=True
    )
    forecast = json.loads((tmp_path / result.artifacts[0].path).read_text())
    assert forecast["case_assessment"] == "Assessment from staged evidence."
    assert forecast["predictions"][0]["probability_fully_dismissed"] == 0.73


@pytest.mark.parametrize(
    "change",
    [
        {"ok": False},
        {"status": "timeout"},
        {"model": "other"},
        {"provider": "other"},
        {"final": "{}"},
        {"final": json.dumps({"case_assessment": "x", "predictions": []})},
    ],
)
def test_failed_drifted_or_defaulted_outputs_refused(
    tmp_path: Path, change: dict[str, object]
) -> None:
    with pytest.raises(OpenClawError):
        normalize_result(
            request(), tmp_path, envelope() | change, tool_reads=2, prompt_complete=True
        )
    assert not (tmp_path / "private-logs/openclaw-forecast.json").exists()


@pytest.mark.parametrize("reads,complete", [(0, False), (1, True), (20, False)])
def test_requires_complete_acknowledged_delivery(
    tmp_path: Path, reads: int, complete: bool
) -> None:
    with pytest.raises(OpenClawError, match="acknowledge every"):
        normalize_result(
            request(), tmp_path, envelope(), tool_reads=reads, prompt_complete=complete
        )


@pytest.mark.parametrize(
    "version,commit", [("0.0.0", OPENCLAW_COMMIT), (OPENCLAW_VERSION, "0" * 40)]
)
def test_runtime_version_and_provenance_mismatch_refused(
    tmp_path: Path, version: str, commit: str
) -> None:
    (tmp_path / "dist").mkdir()
    (tmp_path / "package.json").write_text(json.dumps({"version": version}))
    (tmp_path / "dist/build-info.json").write_text(
        json.dumps({"version": version, "commit": commit})
    )
    (tmp_path / "openclaw.mjs").write_text("throw Error('must not execute');")
    with pytest.raises(OpenClawError, match="mismatch"):
        verify_runtime(tmp_path)


def test_unavailable_runtime_and_nonfixture_ordinary_run_refused(
    tmp_path: Path,
) -> None:
    with pytest.raises(OpenClawError, match="unavailable"):
        verify_runtime(tmp_path)
    with pytest.raises(OpenClawError, match="conformance"):
        offline_fixture(request())


class Transport:
    """Run the same executor used by infra/tool-runtime/worker.py, offline."""

    def __init__(
        self, root: Path, prompt: str = "Public synthetic solver prompt"
    ) -> None:
        self.requests: list[ToolRequest] = []
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "prompt.txt").write_text(prompt)
        self.executor = HarveyToolExecutor(root)

    def execute(self, value: ToolRequest) -> ToolResponse:
        self.requests.append(value)
        return self.executor.execute(value, self.root)


def test_real_node_plugin_routes_only_the_host_read(tmp_path: Path) -> None:
    # Executes our actual plugin and socket transport, with a tiny API registration
    # double. It does not claim an OpenClaw model run or live provider proof.
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed for the actual plugin transport test")
    host, child = socket.socketpair()
    transport = Transport(tmp_path)
    delivery = PromptDelivery()
    failures: list[BaseException] = []
    worker = threading.Thread(
        target=bridge_read, args=(host, transport, "test", delivery, failures)
    )
    worker.start()
    plugin_uri = json.dumps(
        (ROOT / "legalforecast/multiharness/openclaw_plugin/index.mjs").as_uri()
    )
    source = (
        f"import plugin from {plugin_uri};\nconst fd = {child.fileno()};\n"
        + """
let tool;
plugin.register({pluginConfig: {descriptor: fd}, registerTool: value => {tool=value;}});
const result = await tool.execute('call', {page: 0, receipt: ''});
const page = JSON.parse(result.content[0].text);
const ack = await tool.execute('ack', {page: page.next_page, receipt: page.receipt});
let denied = false;
try { await tool.execute('second', {page: 0, receipt: ''}); } catch { denied = true; }
console.log(JSON.stringify({result, ack, denied}));
"""
    )
    try:
        completed = subprocess.run(
            [node, "--input-type=module", "-e", source],
            pass_fds=(child.fileno(),),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    finally:
        child.close()
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert failures == []
    assert delivery.complete
    assert delivery.tool_calls == 2
    record = json.loads(completed.stdout)
    assert record["denied"] is True
    assert "Public synthetic solver prompt" in record["result"]["content"][0]["text"]
    assert len(transport.requests) == 1
    assert json.loads(record["ack"]["content"][0]["text"]) == {"complete": True}
    assert transport.requests[0].operation == "read"
    assert transport.requests[0].input_paths == ("prompt.txt",)


def test_unsupported_tool_operation_never_reaches_host(tmp_path: Path) -> None:
    host, child = socket.socketpair()
    transport = Transport(tmp_path)
    failures: list[BaseException] = []
    try:
        child.sendall(b'{"operation":"exec","command":"curl example.com"}\n')
        bridge_read(host, transport, "test", PromptDelivery(), failures)
    finally:
        child.close()
    assert not transport.requests
    assert len(failures) == 1


@pytest.mark.skipif(
    os.environ.get("LEGALFORECAST_OPENCLAW_E2E") != "1",
    reason="opt-in installed OpenClaw runtime check",
)
def test_pinned_upstream_validates_config_and_loads_real_plugin(tmp_path: Path) -> None:
    entry = verify_runtime(runtime_root())
    config = tmp_path / "openclaw.json"
    config.write_text(json.dumps(build_config("gpt-6-luna", 9)))
    env = {
        "PATH": os.environ["PATH"],
        "OPENCLAW_HOME": str(tmp_path),
        "OPENCLAW_STATE_DIR": str(tmp_path / "state"),
        "OPENCLAW_CONFIG_PATH": str(config),
        "OPENCLAW_NO_RESPAWN": "1",
        "NODE_DISABLE_COMPILE_CACHE": "1",
    }
    for arguments in (
        ["config", "validate", "--json"],
        ["plugins", "inspect", "lfb-container-tool", "--runtime", "--json"],
    ):
        result = subprocess.run(
            ["node", str(entry), *arguments],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            "lfb-container-tool" in result.stdout
            or '"valid":true' in result.stdout.replace(" ", "")
        )


@pytest.mark.skipif(
    os.environ.get("LEGALFORECAST_OPENCLAW_E2E") != "1",
    reason="opt-in installed OpenClaw offline provider-double integration",
)
@pytest.mark.parametrize("stop_early", [False, True])
def test_real_openclaw_turn_with_local_provider_double(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_early: bool
) -> None:
    """Actual upstream loop + plugin + container protocol; NOT a provider smoke."""
    requests: list[dict[str, object]] = []
    prompt = (
        "BEGIN-SENTINEL\n"
        + "x" * 45000
        + "MIDDLE-SENTINEL"
        + "y" * 45000
        + "\nEND-SENTINEL"
    )
    seen_pages: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            tools = body.get("tools", [])
            assert [tool["function"]["name"] for tool in tools] == ["lfb_read_task"]
            messages = body["messages"]
            tool_messages = [
                message for message in messages if message["role"] == "tool"
            ]
            page = json.loads(tool_messages[-1]["content"]) if tool_messages else None
            if page and "content" in page:
                seen_pages.append(page["content"])
            if page and (page.get("complete") or stop_early):
                if not stop_early:
                    assert "".join(seen_pages) == prompt
                    assert all(
                        marker in json.dumps(tool_messages)
                        for marker in (
                            "BEGIN-SENTINEL",
                            "MIDDLE-SENTINEL",
                            "END-SENTINEL",
                        )
                    )
                delta = {"content": envelope()["final"]}
                finish = "stop"
            else:
                delta = {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": f"call_read_{len(requests)}",
                            "type": "function",
                            "function": {
                                "name": "lfb_read_task",
                                "arguments": json.dumps(
                                    {
                                        "page": page["next_page"] if page else 0,
                                        "receipt": page["receipt"] if page else "",
                                    }
                                ),
                            },
                        }
                    ]
                }
                finish = "tool_calls"
            chunk = {
                "id": "fixture",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-test",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            final = dict(
                chunk,
                choices=[{"index": 0, "delta": {}, "finish_reason": finish}],
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                },
            )
            output = (
                "data: "
                + json.dumps(chunk)
                + "\n\ndata: "
                + json.dumps(final)
                + "\n\ndata: [DONE]\n\n"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(output)))
            self.end_headers()
            self.wfile.write(output)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    original_config = build_config

    def fixture_config(model: str, descriptor: int) -> dict[str, object]:
        config = original_config(model, descriptor)
        config["models"] = {
            "providers": {
                "openai": {
                    "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                    "api": "openai-completions",
                    "models": [
                        {
                            "id": "gpt-test",
                            "name": "Offline provider double",
                            "reasoning": False,
                            "input": ["text"],
                            "contextWindow": 128000,
                            "maxTokens": 2048,
                        }
                    ],
                }
            }
        }
        return config

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(
        "legalforecast.multiharness.openclaw_runtime.build_config", fixture_config
    )
    transport = Transport(tmp_path / "staged", prompt)
    validate_provider_environment_scope(
        sandbox_policy=request().sandbox_policy, adapter_count=1, model_count=1
    )
    try:
        if stop_early:
            with pytest.raises(OpenClawError):
                run_openclaw(request(), tmp_path / "run", transport)
            assert not (tmp_path / "run/private-logs/openclaw-forecast.json").exists()
            return
        result = run_openclaw(request(), tmp_path / "run", transport)
    except OpenClawError:
        log = tmp_path / "run/private-logs/openclaw-stderr.log"
        pytest.fail(log.read_text() if log.exists() else "runtime failed before logs")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert result.status == "succeeded"
    assert len(requests) == len(prompt_pages(prompt)) + 2
    assert len(transport.requests) == 1
    assert "".join(seen_pages) == prompt
    assert result.public_summary["prompt_delivery_complete"] is True
    assert (
        json.loads((tmp_path / "run" / result.artifacts[0].path).read_text())[
            "predictions"
        ][0]["probability_fully_dismissed"]
        == 0.73
    )
