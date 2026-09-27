"""Provider-free protected Hermes admission and settlement tests."""

from __future__ import annotations

import io
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.contracts import FORECAST_RELEASE_V1
from legalforecast.multiharness import (
    hermes_agent,
    hermes_paid,
    hermes_runtime,
    task_worker,
)
from legalforecast.multiharness.container_harness.model_gateway_protocol import (
    AnthropicModelGateway,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProviderGatewaySpendController,
    anthropic_registry_charge_extractor,
)
from legalforecast.multiharness.spec import RunResult
from legalforecast.multiharness.tool_protocol import (
    decode_tool_response,
)

from test_model_gateway_paid import _ENVIRONMENT, _files
from test_multiharness_hermes_agent import request
from test_multiharness_hermes_agent import runtime as _bridge_runtime
from test_protected_terminal_paid import _FakeAuthority

bridge_runtime = _bridge_runtime


def test_supported_release_cli_builds_protected_hermes_without_gateway_image(
    tmp_path, monkeypatch, admitted
):
    from legalforecast.cli import main
    from legalforecast.multiharness import terminal_release
    from legalforecast.release.synthetic import issue_synthetic_release

    release = tmp_path / "release"
    issue_synthetic_release(release)
    seen = []

    def execute(options, *, adapter):
        assert isinstance(adapter, hermes_paid.ProtectedHermesAdapter)
        assert options.harness == "hermes-agent"
        assert options.gateway_image_digest is None
        assert options.case_id == "case-001"
        seen.append(adapter.config)
        return SimpleNamespace(interrupted=False)

    monkeypatch.setattr(terminal_release, "execute_terminal_release_only", execute)
    assert (
        main(
            [
                "multiharness",
                "release-execute",
                "--harness",
                "hermes-agent",
                "--hermes-checkout",
                str(tmp_path),
                "--forecast-release",
                str(release / "forecast-release.json"),
                "--artifact-root",
                str(release),
                "--output-dir",
                str(tmp_path / "run"),
                "--image",
                "sha256:" + "a" * 64,
                "--case-id",
                "case-001",
                "--auth-profile",
                "published-api-key",
                "--model-key",
                admitted.config.model_key,
                "--max-budget-usd",
                "10",
                "--paid-config",
                str(tmp_path / "paid-gateway.json"),
                "--model-registry",
                str(tmp_path / "model-registry.json"),
            ]
        )
        == 0
    )
    assert seen == [admitted.config]


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    config_path, registry_path, _ = _files(tmp_path)
    record = json.loads(config_path.read_text())
    record["harness_id"] = "hermes-agent"
    config_path.write_text(json.dumps(record))
    for name, value in _ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "host-only-real-key-fixture")
    monkeypatch.setattr(hermes_paid, "validate_checkout", lambda _: Path("/python3.13"))
    return hermes_paid.build_protected_hermes_adapter(
        checkout=tmp_path,
        paid_config_path=config_path,
        model_registry_path=registry_path,
        model_key="anthropic:claude-sonnet-4-5",
        max_budget_usd=10,
        timeout_seconds=60,
    )


def paid_request(adapter):
    original = request()
    return replace(
        original,
        adapter=adapter.manifest,
        model_key=adapter.config.model_key,
        sandbox_policy=replace(original.sandbox_policy, allowed_provider_env_vars=()),
        task=replace(
            original.task,
            metadata={
                **original.task.metadata,
                "release_schema_version": str(FORECAST_RELEASE_V1),
                "packet_sha256": "sha256:" + "a" * 64,
                "prompt_sha256": "sha256:" + "b" * 64,
            },
        ),
    )


@pytest.mark.parametrize("change", ["model", "budget", "pin", "workflow"])
def test_admission_fails_before_credentials(tmp_path, monkeypatch, change):
    config, registry, _ = _files(tmp_path)
    for name, value in _ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def checkout(_):
        if change == "pin":
            raise ValueError("wrong pin")
        return tmp_path

    monkeypatch.setattr(hermes_paid, "validate_checkout", checkout)
    if change == "workflow":
        monkeypatch.delenv("LFB_PROTECTED_TERMINAL_RELEASE")
    with pytest.raises((ValueError, RuntimeError)):
        hermes_paid.build_protected_hermes_adapter(
            checkout=tmp_path,
            paid_config_path=config,
            model_registry_path=registry,
            model_key="anthropic:wrong"
            if change == "model"
            else "anthropic:claude-sonnet-4-5",
            max_budget_usd=9 if change == "budget" else 10,
            timeout_seconds=60,
        )


def test_gateway_runtime_projection_has_no_provider_credential(
    tmp_path, bridge_runtime, admitted, monkeypatch
):
    invoke = hermes_agent.subprocess.run

    def version_or_run(argv, **kwargs):
        if argv[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="Python 3.13.15\n")
        return invoke(argv, **kwargs)

    monkeypatch.setattr(hermes_agent.subprocess, "run", version_or_run)
    req = paid_request(admitted)
    result = hermes_agent.run(
        req,
        tmp_path,
        tmp_path,
        gateway={
            "request_sha256": req.request_sha256,
            "model_key": req.model_key,
            "base_url": "http://127.0.0.1:12345",
            "capability_token": "synthetic-capability",
            "max_output_tokens": 128000,
            "reasoning_config": {"effort": "high"},
        },
    )
    config, invocation = bridge_runtime[0]
    assert not any("API_KEY" in name for name in invocation["env"])
    assert "host-only-real-key-fixture" not in json.dumps(config)
    assert config["gateway"]["capability_token"] == "synthetic-capability"
    assert result.public_summary["provider"] == "anthropic"
    assert result.public_summary["auth_mode"] == "host-gateway"
    assert {a.artifact_id for a in result.artifacts} >= {
        "release-forecast-output-private",
        "release-harness-transcript-private",
    }


@pytest.mark.parametrize("failure", [None, "unknown_charge", "exhausted", "no_calls"])
def test_paid_wrapper_requires_durable_settlement(
    tmp_path, monkeypatch, admitted, failure
):
    forwarded = []

    class Authority(_FakeAuthority):
        def authorize_attempt(self, *args, **kwargs):
            if failure == "exhausted":
                raise ValueError("ceiling exhausted")
            return super().authorize_attempt(*args, **kwargs)

        def mark_transport_started(self, lease):
            pass

    authority = Authority()
    controller = ProviderGatewaySpendController(
        authority,
        admitted.config.spend,
        admitted.config.reservation_microusd,
        anthropic_registry_charge_extractor(admitted.config.registry_entry),
    )
    monkeypatch.setattr(
        hermes_paid, "build_paid_gateway_controller", lambda _: controller
    )

    def forward(self, body, headers, route):
        forwarded.append(json.loads(body))
        assert self.policy.upstream_api_key == "host-only-real-key-fixture"
        usage = {
            "input_tokens": 12,
            "output_tokens": 4,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        if failure == "unknown_charge":
            del usage["cache_read_input_tokens"]
        return json.dumps({"usage": usage}).encode(), 200, "application/json"

    monkeypatch.setattr(AnthropicModelGateway, "_forward", forward)

    def run(delegate, req, workspace, tools):
        route = json.loads(Path(delegate.manifest.command[-1]).read_bytes())
        assert "host-only-real-key-fixture" not in json.dumps(route)
        body = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "fixture"}],
            "tool_choice": {"type": "auto"},
        }
        if failure != "no_calls":
            for _ in range(2):
                call = urllib.request.Request(
                    route["base_url"] + "/v1/messages",
                    data=json.dumps(body).encode(),
                    headers={"x-api-key": route["capability_token"]},
                )
                try:
                    with urllib.request.urlopen(call, timeout=5) as response:
                        assert response.status == 200
                except urllib.error.HTTPError:
                    assert failure is not None
        # A fabricated successful child must not bypass missing/failed settlement.
        return RunResult(
            result_id="fixture",
            request_id=req.request_id,
            status="succeeded",
            result_sha256="sha256:" + "a" * 64,
        )

    monkeypatch.setattr(hermes_paid.CommandAdapter, "run_with_tools", run)
    if failure:
        with pytest.raises(ValueError, match="fully settle"):
            admitted.run_with_tools(paid_request(admitted), tmp_path, object())
        assert not (tmp_path / "private-logs/gateway/settlement.json").exists()
        if failure == "exhausted":
            assert forwarded == []
        if failure == "unknown_charge":
            assert len(authority.failures) == 2
            assert all(item["ambiguous"] for item in authority.failures)
    else:
        result = admitted.run_with_tools(paid_request(admitted), tmp_path, object())
        assert result.public_summary["provider_requests"] == 2
        assert result.public_summary["cost_microusd"] == 320
        assert len(authority.responses) == len(forwarded) == 2
        assert controller.settlement_totals() == (2, 320)
        artifact = result.artifacts[0]
        evidence = json.loads((tmp_path / artifact.path).read_bytes())
        assert evidence["request_sha256"] == paid_request(admitted).request_sha256
        assert evidence["settled_microusd"] == 320
        assert not artifact.public
        from legalforecast.multiharness.runner import _artifact_index

        # Run-wide rescanning must not promote private accounting to public.
        index = _artifact_index(tmp_path)
        accounting = [
            item
            for item in index
            if item["path"].endswith(("usage.json", "settlement.json"))
        ]
        assert len(accounting) == 2
        assert all(not item["public"] for item in accounting)
        assert all("private-logs" in item["path"].split("/") for item in accounting)
    assert not (tmp_path / "private-logs/gateway/route.json").exists()


@pytest.mark.parametrize("change", ["auth", "model", "task", "evaluator"])
def test_prepare_refuses_contract_drift(admitted, tmp_path, change):
    req = paid_request(admitted)
    if change == "auth":
        req = replace(req, sandbox_policy=request().sandbox_policy)
    elif change == "model":
        req = replace(req, model_key="anthropic:other")
    elif change == "task":
        req = replace(req, task=request().task)
    else:
        req = replace(req, task=replace(req.task, scoring_mode="contract_only"))
    with pytest.raises(ValueError, match="exact blinded release"):
        admitted.prepare(req, tmp_path)


@pytest.mark.parametrize(
    "target", ["prompt.txt", "../private.txt", "other.txt", "symlink"]
)
def test_task_worker_reads_only_regular_canonical_input(tmp_path, target):
    (tmp_path / "prompt.txt").write_text("PRIVATE canonical text")
    if target == "symlink":
        (tmp_path / "prompt.txt").unlink()
        (tmp_path / "other.txt").write_text("must not read")
        (tmp_path / "prompt.txt").symlink_to(tmp_path / "other.txt")
        target = "prompt.txt"
        expected = "failed"
    else:
        expected = "succeeded" if target == "prompt.txt" else "failed"
    # Malformed paths must be refused on the actual wire, before file access.
    payload = {
        "schema_version": "legalforecast.multiharness.tool_request.v1",
        "request_id": "test",
        "operation": "read_text",
        "arguments": {"encoding": "utf-8"},
        "input_paths": [target],
    }
    outgoing = io.BytesIO()
    assert (
        task_worker.serve(
            io.BytesIO(json.dumps(payload).encode() + b"\n"), outgoing, tmp_path
        )
        == 0
    )
    response = decode_tool_response(outgoing.getvalue())
    assert response.status == expected
    if expected == "succeeded":
        assert response.output["text"] == "PRIVATE canonical text"


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_HERMES_CHECKOUT"),
    reason="requires pinned Hermes with locked Anthropic extra",
)
def test_pinned_native_anthropic_wire_is_gateway_admissible(
    tmp_path, admitted, monkeypatch
):
    checkout = Path(os.environ["LEGALFORECAST_HERMES_CHECKOUT"])
    interpreter = hermes_agent.validate_checkout(checkout)
    probe_home = tmp_path / "probe"
    probe_home.mkdir()
    subprocess.run(
        [
            str(interpreter),
            str(Path(__file__).with_name("hermes_anthropic_probe.py")),
            str(checkout),
            str(Path(hermes_runtime.__file__)),
            str(probe_home),
        ],
        check=True,
        timeout=60,
    )
    wire = json.loads((probe_home / "wire.json").read_bytes())

    class Authority(_FakeAuthority):
        def mark_transport_started(self, lease):
            pass

    authority = Authority()
    controller = ProviderGatewaySpendController(
        authority,
        admitted.config.spend,
        admitted.config.reservation_microusd,
        anthropic_registry_charge_extractor(admitted.config.registry_entry),
    )
    from legalforecast.multiharness.container_harness.model_gateway_protocol import (
        ModelGatewayPolicy,
    )

    gateway = AnthropicModelGateway(
        ModelGatewayPolicy(
            upstream_base_url="https://api.anthropic.com:443",
            upstream_api_key="host-only-fixture",
            capability_token="synthetic-capability",
            allowed_models=frozenset({"claude-sonnet-4-5"}),
            allowed_ingress_hosts=frozenset({"127.0.0.1"}),
            max_total_output_tokens=256000,
        ),
        spend_controller=controller,
        request_id="offline-native",
    )
    for call in wire:
        monkeypatch.setattr(
            gateway,
            "_forward",
            lambda *_args, response=call["response"]: (
                response.encode(),
                200,
                "text/event-stream",
            ),
        )
        response = gateway.handle(
            json.dumps(call["body"]).encode(),
            api_key="synthetic-capability",
            headers=call["headers"],
        )
        assert response.status_code == 200
    assert len(authority.responses) == 4
    assert controller.settlement_totals() == (4, 640)


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_HERMES_TASK_IMAGE"),
    reason="requires locally built task worker image",
)
def test_real_task_container_reads_blinded_prompt_and_cleans_up(tmp_path):
    from legalforecast.multiharness.container_runtime import ContainerToolSession
    from legalforecast.multiharness.sandbox import sandbox_policy
    from legalforecast.multiharness.solver_inputs import SolverInputStore
    from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
    from legalforecast.multiharness.tool_protocol import ToolRequest
    from legalforecast.release.synthetic import issue_synthetic_release

    release = tmp_path / "release"
    issue_synthetic_release(release)
    inputs = tmp_path / "inputs"
    index = ReleaseLfbTaskLoader().load_forecast_release(
        release / "forecast-release.json",
        artifact_root=release,
        solver_input_root=inputs,
        case_batching=True,
    )
    store = SolverInputStore.load(inputs)
    task = index.tasks[0]
    policy = sandbox_policy(
        policy_id="hermes-container-probe",
        backend="docker",
        image=os.environ["LEGALFORECAST_HERMES_TASK_IMAGE"],
        mounts=(),
        network_policy="none",
        uid_gid="65532:65532",
        timeout_seconds=30,
    )
    req = replace(request(), task=task, sandbox_policy=policy)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    materialized_root = workspace / "solver-input"
    entry, _ = store.materialize(task, destination_root=materialized_root)
    session = ContainerToolSession(
        policy,
        req,
        workspace,
        solver_input_root=materialized_root,
        solver_input=entry,
        input_tree_sha256=entry.tree_sha256,
    )
    try:
        response = session.execute(
            ToolRequest(
                request_id="read",
                operation="read_text",
                arguments={"encoding": "utf-8"},
                input_paths=("prompt.txt",),
            ),
            workspace,
        )
        assert response.status == "succeeded"
        assert response.output["text"] == (materialized_root / "prompt.txt").read_text()
        from test_hermes_release_documents import assert_container_documents

        assert_container_documents(session, workspace, materialized_root)
        receipt = session.finalize(
            RunResult(
                result_id="fixture",
                request_id=req.request_id,
                status="succeeded",
                result_sha256="sha256:" + "e" * 64,
            )
        )
        assert receipt.cleanup_confirmed
    finally:
        session.abort()
