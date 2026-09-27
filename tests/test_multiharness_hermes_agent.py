"""Offline bridge tests; these do not establish provider execution."""

from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.multiharness import hermes_agent, hermes_runtime
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)


def request() -> RunRequest:
    return RunRequest(
        request_id="hermes-case-1",
        task=CanonicalTask(
            task_id="lfb:case-1",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="v1",
            source_id="case-1",
            task_sha256="sha256:" + "1" * 64,
            metadata={"required_unit_ids": ["count_i"]},
        ),
        adapter=AdapterManifest(
            adapter_id=hermes_agent.ADAPTER_ID,
            adapter_version="1.0.0",
            display_name="Hermes",
            command=("hermes-adapter",),
        ),
        model_key="openrouter:openai/test-model",
        sandbox_policy=SandboxPolicy(
            policy_id="test",
            backend="podman",
            image="test@sha256:" + "2" * 64,
            network_policy="provider-egress-host-only",
            timeout_seconds=60,
            allowed_provider_env_vars=("OPENROUTER_API_KEY",),
        ),
        request_sha256="sha256:" + "3" * 64,
    )


def forecast() -> dict[str, object]:
    return {
        "case_assessment": "PRIVATE analysis",
        "predictions": [
            {
                "unit_id": "count_i",
                "probability_fully_dismissed": 0.7,
                "rationale": "PRIVATE rationale",
            }
        ],
    }


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch):
    invocations = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-provider-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-inherit")
    monkeypatch.setenv("HERMES_HOME", "/must-not-inherit")
    monkeypatch.setattr(
        hermes_agent, "validate_checkout", lambda _: Path("/python3.13")
    )

    def invoke(argv, **kwargs):
        config = json.loads(Path(argv[-2]).read_text())
        invocations.append((config, kwargs))
        result = {
            "result": {
                "completed": True,
                "final_response": json.dumps(forecast()),
                "served_model": None,
            },
            "model": config["model"],
            "session_id": config["session_id"],
            "tool_call_count": 1,
            "hermes_version": hermes_agent.HERMES_VERSION,
            "python_version": "3.13.15",
        }
        Path(argv[-1]).write_text(json.dumps(result))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(hermes_agent.subprocess, "run", invoke)
    return invocations


def test_real_adapter_normalizes_forecast_and_isolates_each_attempt(tmp_path, runtime):
    first = hermes_agent.run(request(), tmp_path, tmp_path)
    second = hermes_agent.run(request(), tmp_path, tmp_path)
    assert first.status == second.status == "succeeded"
    assert first.public_summary["hermes_commit"] == hermes_agent.HERMES_COMMIT
    assert first.public_summary["tool_call_count"] == 1
    assert (
        first.public_summary["session_sha256"]
        != second.public_summary["session_sha256"]
    )
    assert all(not artifact.public for artifact in first.artifacts)
    assert "PRIVATE" not in json.dumps(first.to_record())
    assert "test-provider-secret" not in json.dumps(first.to_record())
    assert runtime[0][0]["working_directory"] != runtime[1][0]["working_directory"]
    environment = runtime[0][1]["env"]
    assert environment["OPENROUTER_API_KEY"] == "test-provider-secret"
    assert "ANTHROPIC_API_KEY" not in environment
    assert environment["HERMES_HOME"].startswith(str(tmp_path))
    assert environment["HERMES_SAFE_MODE"] == "1"
    profile = json.loads((Path(environment["HERMES_HOME"]) / "config.yaml").read_text())
    assert profile["memory"] == {"memory_enabled": False, "user_profile_enabled": False}
    assert profile["mcp_servers"] == {}


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "wrong"),
        ("session_id", "wrong"),
        ("tool_call_count", 0),
        ("hermes_version", "wrong"),
        ("python_version", "3.14.0"),
        ("result", {"completed": False}),
        ("result", {"completed": True, "final_response": "not JSON"}),
        (
            "result",
            {
                "completed": True,
                "final_response": json.dumps(
                    {
                        "case_assessment": "invalid",
                        "predictions": [
                            {
                                "unit_id": "count_i",
                                "probability_fully_dismissed": 2,
                            }
                        ],
                    }
                ),
            },
        ),
    ],
)
def test_wrong_provenance_and_malformed_outputs_fail(
    tmp_path, runtime, monkeypatch, field, value
):
    original = hermes_agent.subprocess.run

    def altered(argv, **kwargs):
        completed = original(argv, **kwargs)
        output = Path(argv[-1])
        record = json.loads(output.read_text())
        record[field] = value
        output.write_text(json.dumps(record))
        return completed

    monkeypatch.setattr(hermes_agent.subprocess, "run", altered)
    with pytest.raises(hermes_agent.HermesAdapterError):
        hermes_agent.run(request(), tmp_path, tmp_path)


def test_provider_grants_fail_before_runtime(tmp_path, runtime):
    original = request()
    unsafe = replace(
        original,
        sandbox_policy=replace(
            original.sandbox_policy,
            allowed_provider_env_vars=("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"),
        ),
    )
    with pytest.raises(hermes_agent.HermesAdapterError, match="only OPENROUTER"):
        hermes_agent.run(unsafe, tmp_path, tmp_path)
    assert runtime == []


def test_public_command_adapter_entrypoint(tmp_path, runtime):
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request().to_record()))
    output = tmp_path / "result.json"
    assert (
        hermes_agent.main(
            [
                "--hermes-checkout",
                str(tmp_path),
                "run-with-tools",
                "--request",
                str(request_path),
                "--workspace",
                str(tmp_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["status"] == "succeeded"


def test_checkout_rejects_wrong_pin_before_import(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    with pytest.raises(subprocess.CalledProcessError):
        hermes_agent.validate_checkout(tmp_path)


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_HERMES_CHECKOUT"),
    reason="set LEGALFORECAST_HERMES_CHECKOUT to installed pinned source",
)
def test_pinned_upstream_managed_conversation_with_sdk_fixtures(tmp_path):
    checkout = Path(os.environ["LEGALFORECAST_HERMES_CHECKOUT"])
    interpreter = hermes_agent.validate_checkout(checkout)
    subprocess.run(
        [
            str(interpreter),
            str(Path(__file__).with_name("hermes_upstream_probe.py")),
            str(checkout),
            str(Path(hermes_runtime.__file__)),
            str(tmp_path),
        ],
        check=True,
        timeout=60,
    )


class Registry:
    def register(self, **kwargs):
        self.registration = kwargs


@pytest.mark.parametrize(
    "wrong_response,extra_tool", [(False, False), (True, False), (False, True)]
)
def test_managed_runtime_tool_callback_uses_host_protocol(
    monkeypatch, wrong_response, extra_tool
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-secret")
    registry = Registry()
    output = io.StringIO()
    options = {}
    closed = []

    class Agent:
        model = "test-model"

        def __init__(self, **kwargs):
            options.update(kwargs)
            self.tools = [{"function": {"name": "read_canonical_task"}}]
            if extra_tool:
                self.tools.append({"function": {"name": "terminal"}})

        def run_conversation(self, prompt):
            assert "read_canonical_task" in prompt
            text = registry.registration["handler"]({})
            assert json.loads(text)["text"] == "PRIVATE canonical task"
            return {"completed": True, "final_response": json.dumps(forecast())}

        def close(self):
            closed.append(True)

    incoming = io.StringIO(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.tool_response.v1",
                "request_id": "wrong" if wrong_response else "case:hermes-tool:1",
                "status": "succeeded",
                "output": {"text": "PRIVATE canonical task"},
            }
        )
        + "\n"
    )
    config = {
        "request_id": "case",
        "model": "test-model",
        "session_id": "fresh",
        "required_unit_ids": ["count_i"],
        "working_directory": "/private",
        "solver_input_path": "solver-input/prompt.txt",
    }
    if wrong_response or extra_tool:
        with pytest.raises(ValueError):
            hermes_runtime.execute(config, Agent, registry, incoming, output)
    else:
        result = hermes_runtime.execute(config, Agent, registry, incoming, output)
        assert result["tool_call_count"] == 1
        message = json.loads(output.getvalue())
        assert message["operation"] == "read_text"
        assert message["input_paths"] == ["solver-input/prompt.txt"]
        assert "provider-secret" not in output.getvalue()
        assert options["enabled_toolsets"] == ["legalforecast"]
        assert options["skip_memory"] is options["skip_context_files"] is True
        assert options["max_iterations"] == 200
    assert closed == [True]


@pytest.mark.parametrize("consume_all", [True, False])
def test_large_canonical_task_requires_every_bounded_chunk(monkeypatch, consume_all):
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test")
    registry = Registry()
    # Keep the fixture within the existing one-MiB host protocol limit while
    # still exceeding Hermes' per-result and per-turn thresholds.
    original = "start " + '"' * 210000 + " end"
    incoming = io.StringIO(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.tool_response.v1",
                "request_id": "case:hermes-tool:1",
                "status": "succeeded",
                "output": {"text": original},
            }
        )
        + "\n"
    )
    outgoing = io.StringIO()
    chunks = []

    class Agent:
        model = "test"

        def __init__(self, **_kwargs):
            self.tools = [{"function": {"name": "read_canonical_task"}}]

        def run_conversation(self, _prompt):
            offset = 0
            while True:
                encoded = registry.registration["handler"]({"offset": offset})
                assert len(encoded) <= 7500
                chunk = json.loads(encoded)
                chunks.append(chunk["text"])
                offset = chunk["next_offset"]
                if chunk["complete"] or not consume_all:
                    break
            return {"completed": True, "final_response": json.dumps(forecast())}

        def close(self):
            pass

    config = {
        "request_id": "case",
        "model": "test",
        "session_id": "fresh",
        "required_unit_ids": ["count_i"],
        "working_directory": "/private",
        "solver_input_path": "prompt.txt",
    }
    if consume_all:
        result = hermes_runtime.execute(config, Agent, registry, incoming, outgoing)
        assert result["tool_call_count"] == 1
        assert "".join(chunks) == original
        assert outgoing.getvalue().count("\n") == 1
    else:
        with pytest.raises(ValueError, match="complete canonical task"):
            hermes_runtime.execute(config, Agent, registry, incoming, outgoing)
