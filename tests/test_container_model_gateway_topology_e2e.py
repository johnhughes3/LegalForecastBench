"""Live rootless-Docker proof of the model-gateway/relay network topology.

The test is opt-in because it needs a local image with Python and a rootless
Docker daemon. A fake Anthropic SSE endpoint stands in for the model provider.
The harness makes a permitted structured request through the gateway, while a
direct socket probe from both the harness and gateway must fail. The gateway
and harness share only the internal network; the relay is the only benchmark
control-plane container attached to the endpoint network.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    resolve_rootless_backend,
)

_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CAPABILITY = "fixture-gateway-capability"
_GATEWAY_KEY = "fixture-gateway-key-only"
_FIXTURE_PORT = 8081


def _gateway_script() -> str:
    return textwrap.dedent(
        """
        import os
        import socket

        from legalforecast.multiharness.container_harness import (
            model_gateway_protocol,
            model_gateway_server,
        )

        probe_host = os.environ["LFB_DIRECT_PROBE_HOST"]
        probe_port = int(os.environ["LFB_DIRECT_PROBE_PORT"])
        try:
            socket.create_connection((probe_host, probe_port), timeout=1).close()
        except OSError:
            print("gateway-direct=denied", flush=True)
        else:
            print("gateway-direct=connected", flush=True)
            raise SystemExit("gateway obtained a direct external socket")

        policy = model_gateway_protocol.ModelGatewayPolicy(
            upstream_base_url=os.environ["LFB_FIXTURE_UPSTREAM_URL"],
            proxy_base_url=os.environ["LFB_FIXTURE_PROXY_URL"],
            upstream_api_key=os.environ["LFB_FIXTURE_GATEWAY_KEY"],
            capability_token=os.environ["LFB_FIXTURE_CAPABILITY"],
            allowed_models=frozenset({"claude-fixture"}),
            allowed_ingress_hosts=frozenset({"gateway"}),
            max_request_bytes=32_768,
            max_response_bytes=32_768,
            max_requests=4,
            max_input_tokens=32_768,
            max_output_tokens=128,
            max_total_input_tokens=32_768,
            max_total_output_tokens=256,
            upstream_timeout_seconds=5,
        )
        server = model_gateway_server.build_model_gateway_server(
            policy,
            bind_host="0.0.0.0",
            port=8080,
        )
        print("gateway-ready", flush=True)
        server.serve_forever()
        """
    ).strip()


def _fixture_script() -> str:
    """Return a deterministic Anthropic SSE fixture used inside Docker."""

    return textwrap.dedent(
        """
        import json
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from pathlib import Path

        log = Path("/tmp/fixture-requests.jsonl")

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["content-length"])
                raw = self.rfile.read(length)
                payload = json.loads(raw)
                has_tool_result = any(
                    isinstance(item, dict) and item.get("type") == "tool_result"
                    for message in payload.get("messages", [])
                    for item in (
                        message.get("content", [])
                        if isinstance(message.get("content"), list)
                        else []
                    )
                )
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({
                        "tool_result": has_tool_result,
                        "model": payload.get("model"),
                        "upstream_key": self.headers.get("x-api-key"),
                    }) + "\\n")
                print(
                    f"fixture-request tool-result={has_tool_result}", flush=True
                )
                start = {
                    "type": "message_start",
                    "message": {
                        "id": "fixture-message",
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
                if not has_tool_result:
                    command = (
                        "cat /workspace/prompt.txt /workspace/documents/opinion.txt"
                    )
                    events = [
                        start,
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
                                    {"command": command}, separators=(",", ":")
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
                else:
                    result = {
                        "case_assessment": "fixture evidence read",
                        "predictions": [{
                            "unit_id": "unit-001",
                            "probability_fully_dismissed": 0.25,
                        }],
                    }
                    events = [
                        start,
                        {"type": "ping"},
                        {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        },
                        {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta",
                                "text": json.dumps(result, separators=(",", ":")),
                            },
                        },
                        {"type": "content_block_stop", "index": 0},
                        {
                            "type": "message_delta",
                            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": 3},
                        },
                        {"type": "message_stop"},
                    ]
                body = b"".join(
                    f"event: {event['type']}\\ndata: {json.dumps(event)}\\n\\n".encode()
                    for event in events
                )
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        print("fixture-ready", flush=True)
        ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
        """
    ).strip()


def _harness_script() -> str:
    return textwrap.dedent(
        """
        import json
        import os
        import socket
        import time
        from http.client import HTTPConnection

        body = json.dumps({
            "model": "claude-fixture",
            "max_tokens": 64,
            "messages": [
                {"role": "user", "content": "fixture"},
                {"role": "assistant", "content": [{
                    "type": "tool_use", "id": "toolu_fixture", "name": "Bash",
                    "input": {"command": "cat /workspace/prompt.txt"},
                }]},
                {"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": "toolu_fixture",
                    "content": "fixture evidence",
                }]},
            ],
        }, separators=(",", ":")).encode()
        connection = HTTPConnection("gateway", 8080, timeout=5)
        connection.request(
            "POST",
            "/v1/messages",
            body=body,
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "x-api-key": os.environ["LFB_FIXTURE_CAPABILITY"],
            },
        )
        response = connection.getresponse()
        response_body = response.read()
        connection.close()
        try:
            socket.create_connection(
                ("direct-probe", int(os.environ["LFB_DIRECT_PROBE_PORT"])),
                timeout=1,
            ).close()
        except OSError:
            direct_denied = True
        else:
            direct_denied = False
        response_text = response_body.decode("utf-8", errors="replace")
        key_absent = "LFB_FIXTURE_GATEWAY_KEY" not in os.environ
        if response.status != 200 or "fixture evidence read" not in response_text:
            raise SystemExit(f"unexpected gateway response: {response.status}")
        if not direct_denied:
            raise SystemExit("harness obtained a direct external socket")
        if not key_absent:
            raise SystemExit("gateway key reached the harness environment")
        print("harness-result=success direct=denied key=absent", flush=True)
        time.sleep(5)
        """
    ).strip()


def _stage_gateway_package(tmp_path: Path, repo_root: Path) -> Path:
    """Stage only the gateway modules, avoiding the repo's Python 3.14 imports."""

    package_root = tmp_path / "package"
    module_root = package_root / "legalforecast/multiharness/container_harness"
    module_root.mkdir(parents=True)
    for init_path in (
        package_root / "legalforecast/__init__.py",
        package_root / "legalforecast/multiharness/__init__.py",
        module_root / "__init__.py",
    ):
        init_path.write_text("", encoding="utf-8")
    source_root = repo_root / "legalforecast/multiharness/container_harness"
    for module_name in (
        "model_gateway_accounting.py",
        "model_gateway_protocol.py",
        "model_gateway_server.py",
        "model_gateway_types.py",
    ):
        shutil.copyfile(source_root / module_name, module_root / module_name)
    return package_root


def _run(
    backend: Path,
    arguments: Sequence[str],
    environment: Mapping[str, str],
    *,
    check: bool = True,
    timeout: float = 30,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        (str(backend), *arguments),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=dict(environment),
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")[-2_000:]
        raise AssertionError(f"container command failed {arguments[:3]}: {stderr}")
    return completed


def _image_id(
    backend: Path,
    image: str,
    environment: Mapping[str, str],
) -> str:
    result = _run(
        backend,
        ("image", "inspect", "--format", "{{.Id}}", image),
        environment,
    )
    resolved = result.stdout.decode("ascii").strip()
    if _IMAGE_ID.fullmatch(resolved) is None:
        raise AssertionError("fixture image did not resolve to a content digest")
    return resolved


def _network_containers(
    backend: Path,
    network: str,
    environment: Mapping[str, str],
) -> set[str]:
    record = _inspect_record(backend, ("network", "inspect", network), environment)
    containers = record.get("Containers")
    assert isinstance(containers, dict)
    typed_containers = cast(Mapping[str, Mapping[str, Any]], containers)
    return {
        str(value.get("Name"))
        for value in typed_containers.values()
        if isinstance(value.get("Name"), str)
    }


def _container_networks(
    backend: Path,
    container: str,
    environment: Mapping[str, str],
) -> set[str]:
    record = _inspect_record(backend, ("inspect", container), environment)
    settings = record.get("NetworkSettings")
    assert isinstance(settings, dict)
    networks = cast(Mapping[str, Any], settings).get("Networks")
    assert isinstance(networks, dict)
    typed_networks = cast(Mapping[str, Any], networks)
    return set(typed_networks)


def _inspect_record(
    backend: Path,
    arguments: Sequence[str],
    environment: Mapping[str, str],
) -> Mapping[str, Any]:
    result = _run(backend, arguments, environment)
    decoded = cast(object, json.loads(result.stdout))
    assert isinstance(decoded, list)
    records = cast(list[object], decoded)
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, dict)
    return cast(Mapping[str, Any], record)


def _wait_for_log(
    backend: Path,
    container: str,
    marker: str,
    environment: Mapping[str, str],
) -> str:
    deadline = time.monotonic() + 30
    latest = ""
    while time.monotonic() < deadline:
        result = _run(backend, ("logs", container), environment, check=False)
        latest = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        if marker in latest:
            return latest
        state = _run(
            backend,
            ("inspect", "--format", "{{.State.Running}}", container),
            environment,
            check=False,
        )
        if state.returncode == 0 and state.stdout.strip() == b"false":
            raise AssertionError(f"{container} exited before {marker!r}: {latest}")
        time.sleep(0.2)
    raise AssertionError(f"{container} did not emit {marker!r}: {latest}")


def test_rootless_relay_topology_routes_fixture_without_gateway_egress(
    tmp_path: Path,
) -> None:
    if os.environ.get("LEGALFORECAST_GATEWAY_TOPOLOGY_E2E") != "1":
        pytest.skip(
            "set LEGALFORECAST_GATEWAY_TOPOLOGY_E2E=1 for the rootless Docker "
            "relay topology test"
        )
    if os.environ.get("LEGALFORECAST_GATEWAY_TOPOLOGY_BACKEND", "docker") != "docker":
        pytest.fail("the relay topology E2E currently requires rootless Docker")
    image = os.environ.get("LEGALFORECAST_GATEWAY_TOPOLOGY_IMAGE") or os.environ.get(
        "LEGALFORECAST_CONTAINER_E2E_IMAGE"
    )
    if not image:
        pytest.fail("LEGALFORECAST_GATEWAY_TOPOLOGY_IMAGE must name a local image")
    try:
        backend, backend_environment = resolve_rootless_backend("docker")
    except ContainerImageError as exc:
        pytest.fail(str(exc))
    resolved_image = _image_id(backend, image, backend_environment)

    token = os.urandom(8).hex()
    internal_network = f"lfb-gateway-topology-{token}-internal"
    egress_network = f"lfb-gateway-topology-{token}-egress"
    fixture = f"lfb-gateway-topology-{token}-fixture"
    relay = f"lfb-gateway-topology-{token}-relay"
    gateway = f"lfb-gateway-topology-{token}-gateway"
    harness = f"lfb-gateway-topology-{token}-harness"
    repo_root = Path(__file__).resolve().parents[1]
    gateway_source = tmp_path / "gateway.py"
    harness_source = tmp_path / "harness.py"
    fixture_source = tmp_path / "fixture.py"
    gateway_source.write_text(_gateway_script() + "\n", encoding="utf-8")
    harness_source.write_text(_harness_script() + "\n", encoding="utf-8")
    fixture_source.write_text(_fixture_script() + "\n", encoding="utf-8")
    egress_source = (
        repo_root / "legalforecast/multiharness/container_harness/egress_proxy.py"
    )
    gateway_package = _stage_gateway_package(tmp_path, repo_root)
    environment = dict(backend_environment)
    environment.update(
        {
            "LFB_FIXTURE_CAPABILITY": _CAPABILITY,
            "LFB_FIXTURE_GATEWAY_KEY": _GATEWAY_KEY,
            "LFB_FIXTURE_UPSTREAM_URL": f"http://fixture-provider:{_FIXTURE_PORT}",
            "LFB_FIXTURE_PROXY_URL": "http://relay:3128",
            "LFB_DIRECT_PROBE_HOST": "direct-probe",
            "LFB_DIRECT_PROBE_PORT": str(_FIXTURE_PORT),
        }
    )
    try:
        _run(
            backend,
            ("network", "create", "--internal", internal_network),
            environment,
        )
        _run(backend, ("network", "create", egress_network), environment)
        _run(
            backend,
            (
                "run",
                "--detach",
                "--name",
                fixture,
                "--network",
                egress_network,
                "--network-alias",
                "fixture-provider",
                "--pull=never",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=16m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={fixture_source},dst=/tmp/fixture.py,readonly",
                "--entrypoint",
                "python3",
                resolved_image,
                "/tmp/fixture.py",
            ),
            environment,
        )
        _wait_for_log(backend, fixture, "fixture-ready", environment)
        _run(
            backend,
            (
                "run",
                "--detach",
                "--name",
                relay,
                "--network",
                internal_network,
                "--network-alias",
                "relay",
                "--pull=never",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=16m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={egress_source},dst=/opt/egress_proxy.py,readonly",
                "--entrypoint",
                "python3",
                resolved_image,
                "/opt/egress_proxy.py",
                "--bind",
                "0.0.0.0",
                "--port",
                "3128",
                "--allow-host",
                "fixture-provider",
                "--allow-port",
                str(_FIXTURE_PORT),
            ),
            environment,
        )
        _run(backend, ("network", "connect", egress_network, relay), environment)
        _wait_for_log(backend, relay, "3128", environment)

        _run(
            backend,
            (
                "run",
                "--detach",
                "--name",
                gateway,
                "--network",
                internal_network,
                "--network-alias",
                "gateway",
                "--add-host",
                "direct-probe:host-gateway",
                "--pull=never",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=16m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={gateway_package},dst=/src,readonly",
                "--mount",
                f"type=bind,src={gateway_source},dst=/tmp/gateway.py,readonly",
                "--env",
                "PYTHONPATH=/src",
                "--env",
                "LFB_FIXTURE_CAPABILITY",
                "--env",
                "LFB_FIXTURE_GATEWAY_KEY",
                "--env",
                "LFB_FIXTURE_UPSTREAM_URL",
                "--env",
                "LFB_FIXTURE_PROXY_URL",
                "--env",
                "LFB_DIRECT_PROBE_HOST",
                "--env",
                "LFB_DIRECT_PROBE_PORT",
                "--entrypoint",
                "python3",
                resolved_image,
                "/tmp/gateway.py",
            ),
            environment,
        )
        gateway_logs = _wait_for_log(backend, gateway, "gateway-ready", environment)
        assert "gateway-direct=denied" in gateway_logs

        assert _container_networks(backend, relay, environment) == {
            internal_network,
            egress_network,
        }
        assert _container_networks(backend, gateway, environment) == {internal_network}
        # The fixture endpoint is intentionally a peer on this network; among
        # benchmark control-plane containers, only the relay has egress.
        assert _network_containers(backend, egress_network, environment) == {
            fixture,
            relay,
        }
        assert _network_containers(backend, internal_network, environment) == {
            relay,
            gateway,
        }

        _run(
            backend,
            (
                "run",
                "--detach",
                "--name",
                harness,
                "--network",
                internal_network,
                "--add-host",
                "direct-probe:host-gateway",
                "--pull=never",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=16m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={harness_source},dst=/tmp/harness.py,readonly",
                "--env",
                "LFB_FIXTURE_CAPABILITY",
                "--env",
                "LFB_DIRECT_PROBE_PORT",
                "--entrypoint",
                "python3",
                resolved_image,
                "/tmp/harness.py",
            ),
            environment,
        )
        _wait_for_log(backend, harness, "harness-result=success", environment)
        assert _network_containers(backend, egress_network, environment) == {
            fixture,
            relay,
        }
        assert _network_containers(backend, internal_network, environment) == {
            relay,
            gateway,
            harness,
        }
        _run(backend, ("wait", harness), environment, timeout=15)
        fixture_logs = _run(backend, ("logs", fixture), environment).stdout.decode(
            "utf-8", errors="replace"
        )
        assert "fixture-ready" in fixture_logs
        assert "fixture-request tool-result=True" in fixture_logs
    finally:
        for container in (harness, gateway, relay, fixture):
            _run(backend, ("rm", "--force", container), environment, check=False)
        for network in (internal_network, egress_network):
            _run(backend, ("network", "rm", network), environment, check=False)
