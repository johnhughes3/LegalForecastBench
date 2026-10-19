"""Provider-free tests for the native LAB shared-gateway seam."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from legalforecast.multiharness.container_harness.model_gateway_protocol import (
    ModelGatewayPolicy,
)
from legalforecast.multiharness.harvey_lab.core_bridge import run_lab_core
from legalforecast.multiharness.harvey_lab.gateway import LabCoreGateway
from tests.test_harvey_lab_core import RecordingRuntime, _request, _runtime


class _FakeUpstream(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"] or "0")
        self.rfile.read(length)
        response = json.dumps(
            {
                "id": "msg_fixture",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *_args: object) -> None:
        del format
        return


class _RecordingSpendController:
    def __init__(self) -> None:
        self.settled = 0
        self.failures = 0

    def authorize_request(
        self, *, request_id: str, body: bytes, model: str, max_tokens: int
    ) -> object:
        assert request_id == "native-lab-test"
        assert body and model == "claude-sonnet-4-6" and max_tokens == 32
        return object()

    def mark_transport_started(self, lease: object) -> None:
        assert lease is not None

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
        assert lease is not None
        assert response_body and response_status == 200
        assert content_type == "application/json"
        assert (input_tokens, output_tokens) == (7, 3)
        self.settled += 1
        return True

    def record_failure(
        self, lease: object, *, failure_type: str, ambiguous: bool
    ) -> None:
        assert lease is not None and failure_type and ambiguous
        self.failures += 1

    def settlement_totals(self) -> tuple[int, int]:
        return self.settled, self.settled * 19


class _GatewayRecordingRuntime(RecordingRuntime):
    model = "claude-sonnet-4-6"
    judge_model = "claude-sonnet-4-6"

    def invoke(
        self,
        module: str,
        arguments: tuple[str, ...],
        *,
        private_root: Path,
        lab_root: Path,
        phase: str,
        timeout: float,
        provider_env: tuple[str, ...] = (),
        environment_overrides: dict[str, str] | None = None,
    ) -> None:
        assert environment_overrides is not None
        connection = HTTPConnection(
            "127.0.0.1",
            int(environment_overrides["ANTHROPIC_BASE_URL"].rsplit(":", 1)[1]),
        )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": module}],
            }
        ).encode()
        connection.request(
            "POST",
            "/v1/messages",
            body=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": environment_overrides["ANTHROPIC_API_KEY"],
            },
        )
        response = connection.getresponse()
        assert response.status == 200
        response.read()
        connection.close()
        super().invoke(
            module,
            arguments,
            private_root=private_root,
            lab_root=lab_root,
            phase=phase,
            timeout=timeout,
            provider_env=provider_env,
        )


def test_native_lab_gateway_routes_capability_and_settles_usage(
    tmp_path: Path,
) -> None:
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        controller = _RecordingSpendController()
        gateway = LabCoreGateway(
            policy=ModelGatewayPolicy(
                upstream_base_url=f"http://127.0.0.1:{upstream.server_port}",
                upstream_api_key="upstream-secret",
                capability_token="run-capability",
                allowed_models=frozenset({"claude-sonnet-4-6"}),
                allowed_ingress_hosts=frozenset({"127.0.0.1"}),
                max_requests=2,
                max_input_tokens=10_000,
                max_output_tokens=32,
                max_total_input_tokens=10_000,
                max_total_output_tokens=64,
            ),
            request_id="native-lab-test",
            spend_controller=controller,
        )
        with gateway.serve(tmp_path) as session:
            import http.client

            body = json.dumps(
                {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 32,
                    "messages": [{"role": "user", "content": "hello"}],
                }
            ).encode()
            connection = http.client.HTTPConnection(
                "127.0.0.1", session.server.server_port
            )
            connection.request(
                "POST",
                "/v1/messages",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": session.environment["ANTHROPIC_API_KEY"],
                },
            )
            response = connection.getresponse()
            assert response.status == 200
            response.read()
            connection.close()

            assert "upstream-secret" not in session.environment.values()
            settled = session.require_settled()
            assert settled == {
                "request_count": 1,
                "input_tokens": 7,
                "output_tokens": 3,
                "rejected_count": 0,
                "settled_requests": 1,
                "settled_microusd": 19,
            }
        assert controller.failures == 0
        assert (tmp_path / "gateway" / "usage.json").is_file()
        assert (
            "upstream-secret" not in (tmp_path / "gateway" / "usage.json").read_text()
        )
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)


def test_native_lab_bridge_uses_gateway_for_both_pinned_phases(
    tmp_path: Path,
) -> None:
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        controller = _RecordingSpendController()
        gateway = LabCoreGateway(
            policy=ModelGatewayPolicy(
                upstream_base_url=f"http://127.0.0.1:{upstream.server_port}",
                upstream_api_key="upstream-secret",
                capability_token="run-capability",
                allowed_models=frozenset({"claude-sonnet-4-6"}),
                allowed_ingress_hosts=frozenset({"127.0.0.1"}),
                max_requests=4,
                max_input_tokens=10_000,
                max_output_tokens=32,
                max_total_input_tokens=10_000,
                max_total_output_tokens=128,
            ),
            request_id="native-lab-test",
            spend_controller=controller,
        )
        fixture = _runtime(tmp_path)
        runtime = _GatewayRecordingRuntime(fixture.source_root, fixture.python)
        runtime.calls = []
        runtime.sabotage = ""
        request = replace(
            _request(),
            model="claude-sonnet-4-6",
            judge_model="claude-sonnet-4-6",
            gateway=gateway,
        )
        result = run_lab_core(runtime, request, tmp_path / "run")
        assert [module for module, _argv in runtime.calls] == [
            "lab_core.harness.run",
            "lab_core.evaluation.run_eval",
        ]
        assert result["gateway"] == {
            "request_count": 2,
            "input_tokens": 14,
            "output_tokens": 6,
            "rejected_count": 0,
            "settled_requests": 2,
            "settled_microusd": 38,
        }
        assert controller.failures == 0
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)
