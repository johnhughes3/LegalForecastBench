"""Real rootless containment with a local provider double, never paid proof."""

from __future__ import annotations

import inspect
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness import (
    ContainerHarnessSpec,
    ModelGatewayRequest,
    run_container_harness,
)
from legalforecast.multiharness.container_harness.images import resolve_rootless_backend
from legalforecast.multiharness.openclaw_worker import CAPABILITY_ENV

from test_container_model_gateway_topology_e2e import _image_id, _run, _wait_for_log
from test_multiharness_openclaw import request
from test_multiharness_openclaw_gateway import AnthropicFixture


@pytest.mark.skipif(
    os.environ.get("LFB_OPENCLAW_CONTAINER_E2E") != "1",
    reason="requires built pinned OpenClaw image and rootless Docker",
)
def test_pinned_worker_gateway_and_real_container_isolation(tmp_path: Path) -> None:
    backend, environment = resolve_rootless_backend("docker")
    image = _image_id(
        backend,
        os.environ.get("LFB_OPENCLAW_TEST_IMAGE", "lfb-openclaw:issue46-gateway"),
        environment,
    )
    token = secrets.token_hex(5)
    network, fixture = f"lfb-openclaw-{token}-fixture", f"lfb-openclaw-{token}-provider"
    run_id = f"openclaw-{token}"
    fixture_source = tmp_path / "fixture.py"
    fixture_source.write_text(
        "import json, threading\n"
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        + inspect.getsource(AnthropicFixture)
        + "\nf=AnthropicFixture('0.0.0.0',8081,True)\n"
        "print('fixture-ready',flush=True)\nf.thread.join()\n"
    )
    workspace = tmp_path / "worker"
    workspace.mkdir()
    original = request()
    req = replace(
        original,
        model_key="anthropic:claude-opus-5-5",
        sandbox_policy=replace(
            original.sandbox_policy, allowed_provider_env_vars=(), timeout_seconds=900
        ),
    )
    prompt = "BEGIN " + "x" * 45000 + " MIDDLE " + "y" * 45000 + " END"
    (workspace / "prompt.txt").write_text(prompt)
    (workspace / "openclaw-request.json").write_text(json.dumps(req.to_record()))
    (workspace / "openclaw-model.json").write_text(
        json.dumps(
            {
                "context_limit": 200000,
                "max_output_tokens": 2048,
                "reasoning_effort": "high",
            }
        )
    )
    spec = ContainerHarnessSpec(
        run_id=run_id,
        image=image,
        proxy_image=image,
        harness_argv=("run",),
        workspace=workspace,
        log_root=tmp_path / "logs",
        allow_hosts=("fixture-provider",),
        allow_ports=(8081,),
        egress_network=network,
        environment={CAPABILITY_ENV: "only-run-capability"},
        cli_name="openclaw",
        container_user="0:0",
        read_only_workspace_paths=(
            "prompt.txt",
            "openclaw-request.json",
            "openclaw-model.json",
        ),
        model_gateway=ModelGatewayRequest(
            upstream_base_url="http://fixture-provider:8081",
            model_key=req.model_key,
            run_capability="only-run-capability",
            upstream_api_key="provider-sentinel-only-gateway",
        ),
        timeout_seconds=900,
    )
    _run(backend, ("network", "create", network), environment)
    try:
        _run(
            backend,
            (
                "run",
                "--detach",
                "--name",
                fixture,
                "--network",
                network,
                "--network-alias",
                "fixture-provider",
                "--mount",
                f"type=bind,src={fixture_source},dst=/fixture.py,readonly",
                "--entrypoint",
                "/opt/legalforecast/.venv/bin/python",
                image,
                "/fixture.py",
            ),
            environment,
        )
        _wait_for_log(backend, fixture, "fixture-ready", environment)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                run_container_harness,
                spec,
                publication_directory=tmp_path / "published",
                backend="docker",
            )
            try:
                deadline = time.monotonic() + 30
                worker = ""
                while time.monotonic() < deadline and not future.done():
                    names = (
                        _run(
                            backend,
                            (
                                "ps",
                                "--format",
                                "{{.Names}}",
                                "--filter",
                                f"name=lfb-{run_id}-",
                            ),
                            environment,
                        )
                        .stdout.decode()
                        .splitlines()
                    )
                    worker = next(
                        (name for name in names if name.endswith("-harness")), ""
                    )
                    if worker:
                        break
                    time.sleep(0.1)
                assert worker, (
                    future.result() if future.done() else "worker did not start"
                )
                record = json.loads(
                    _run(backend, ("inspect", worker), environment).stdout
                )[0]
                assert record["HostConfig"]["ReadonlyRootfs"] is True
                assert record["HostConfig"]["CapDrop"] == ["ALL"]
                assert record["HostConfig"]["SecurityOpt"] == ["no-new-privileges"]
                networks = record["NetworkSettings"]["Networks"]
                assert len(networks) == 1 and network not in networks
                internal = next(iter(networks))
                assert (
                    json.loads(
                        _run(
                            backend, ("network", "inspect", internal), environment
                        ).stdout
                    )[0]["Internal"]
                    is True
                )
                assert "provider-sentinel" not in json.dumps(record)
                probe = """import os,socket
keys = ('ANTHROPIC_API_KEY','OPENAI_API_KEY','AWS_SECRET_ACCESS_KEY')
assert not any(k in os.environ for k in keys)
try:
 socket.create_connection(('1.1.1.1',443),timeout=1).close()
except OSError: pass
else: raise AssertionError('direct external socket allowed')
try:
 open('/workspace/prompt.txt','a').write('tamper')
except OSError: pass
else: raise AssertionError('prompt writable')
print('isolation-probes-passed')
"""
                assert (
                    b"isolation-probes-passed"
                    in _run(
                        backend,
                        (
                            "exec",
                            worker,
                            "/opt/legalforecast/.venv/bin/python",
                            "-c",
                            probe,
                        ),
                        environment,
                    ).stdout
                )
            finally:
                _run(
                    backend,
                    (
                        "exec",
                        fixture,
                        "/opt/legalforecast/.venv/bin/python",
                        "-c",
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/release').read()",
                    ),
                    environment,
                )
            result = future.result(timeout=150)
        assert result.exit_code == 0, (tmp_path / "logs").as_posix()
        assert not result.timed_out and result.gateway_usage is not None
        stats = json.loads(
            _run(
                backend,
                (
                    "exec",
                    fixture,
                    "/opt/legalforecast/.venv/bin/python",
                    "-c",
                    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/').read().decode())",
                ),
                environment,
            ).stdout
        )
        assert "".join(stats["pages"]) == prompt
        assert set(stats["headers"]) == {"provider-sentinel-only-gateway"}
        output = json.loads(
            (workspace / "private-logs/openclaw-forecast.json").read_text()
        )
        assert output["predictions"][0]["probability_fully_dismissed"] == 0.37
        assert (
            "provider-sentinel" not in (workspace / "openclaw-result.json").read_text()
        )
    finally:
        _run(backend, ("rm", "--force", fixture), environment, check=False)
        _run(backend, ("network", "rm", network), environment, check=False)
