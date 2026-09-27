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
from legalforecast.multiharness import runner as runner_module
from legalforecast.multiharness.adapters import AdapterPreparation
from legalforecast.multiharness.release_harness import score_multiharness_release
from legalforecast.multiharness.run_progress import ResumeRefusedError
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import PROVIDER_EGRESS_HOST_ONLY
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.solver_inputs import SolverInputStore
from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    TOOL_RESPONSE_SCHEMA_VERSION,
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.release import validate_release
from legalforecast.release.synthetic import issue_synthetic_release


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
            network_policy=PROVIDER_EGRESS_HOST_ONLY,
            timeout_seconds=60,
            memory_limit="512m",
            cpu_limit="1",
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
        normalized = forecast()
        normalized["predictions"] = [
            {"unit_id": unit, "probability_fully_dismissed": 0.7}
            for unit in config["required_unit_ids"]
        ]
        result = {
            "result": {
                "completed": True,
                "final_response": json.dumps(normalized),
                "served_model": None,
            },
            "model": config["model"],
            "session_id": config["session_id"],
            "tool_call_count": 1,
            "hermes_version": hermes_agent.HERMES_VERSION,
            "python_version": "3.13.15",
        }
        os.write(int(argv[-1]), json.dumps(result).encode())
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
        output = int(argv[-1])
        record = json.loads(os.pread(output, 16_777_216, 0))
        record[field] = value
        os.ftruncate(output, 0)
        os.pwrite(output, json.dumps(record).encode(), 0)
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


def test_workspace_symlinks_fail_before_runtime(tmp_path, runtime):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "private-logs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        hermes_agent.run(request(), tmp_path, tmp_path)
    assert runtime == []
    assert list(outside.iterdir()) == []


def test_release_runner_scores_and_resumes_hermes_evidence(
    tmp_path, runtime, monkeypatch
):
    # Runtime and container receipts are fixtures here; real Hermes tool dispatch
    # is independently exercised by the pinned-source tests below.
    class Adapter:
        manifest = request().adapter

        def capabilities(self, workspace):
            return hermes_agent.capabilities()

        def prepare(self, req, workspace):
            return AdapterPreparation(
                self.manifest, self.capabilities(workspace), workspace
            )

        def run(self, req, workspace):
            raise AssertionError("must use host tools")

        def run_with_tools(self, req, workspace, tools):
            return hermes_agent.run(req, workspace, tmp_path)

    receipt_digest = "sha256:" + "c" * 64

    class Session:
        def __init__(self, **kwargs):
            assert kwargs["solver_input_root"].is_dir()

        def finalize(self, result):
            assert result.status == "succeeded"
            return SimpleNamespace(receipt_sha256=receipt_digest)

        def abort(self):
            pass

    monkeypatch.setattr(runner_module, "_preflight_live_container", lambda _: None)
    monkeypatch.setattr(runner_module, "ContainerToolSession", Session)
    monkeypatch.setattr(
        runner_module, "validate_container_resume", lambda *a, **kw: receipt_digest
    )
    release = tmp_path / "release"
    issue_synthetic_release(release)
    solver = tmp_path / "solver"
    index = ReleaseLfbTaskLoader().load_forecast_release(
        release / "forecast-release.json",
        artifact_root=release,
        solver_input_root=solver,
    )
    config = MultiHarnessRunConfig(
        task_index=index,
        adapters=(Adapter(),),
        model_configs=(
            ModelConfig(model_key=request().model_key, adapter_id="hermes-agent"),
        ),
        sandbox_policy=replace(request().sandbox_policy, uid_gid="65532:65532"),
        output_dir=tmp_path / "run",
        selection=TaskSelection(task_ids=(index.tasks[0].task_id,)),
        solver_inputs=SolverInputStore.load(solver),
        container_execution="live_tools",
    )
    first = run_multi_harness(config)
    row = first.rows[0]
    release_forecast, labels = validate_release(
        release / "forecast-release.json",
        release / "labels-release.json",
        artifact_root=release,
    )
    score = score_multiharness_release(first, release_forecast, labels)["models"][0]
    assert score["unit_count"] == score["completed_unit_count"] == 1
    assert score["failed_unit_count"] == 0
    assert score["micro_brier"] == pytest.approx(0.7**2)
    assert row.lfb_record["parser_output"]["is_valid"] is True
    assert len(runtime) == 1
    artifacts = {artifact.artifact_id: artifact for artifact in row.result.artifacts}
    output = artifacts["release-forecast-output-private"]
    transcript = artifacts["release-harness-transcript-private"]
    bound = json.loads((row.workspace / transcript.path).read_bytes())
    assert bound["request_sha256"] == row.request.request_sha256
    assert bound["packet_sha256"] == row.task.metadata["packet_sha256"]
    assert bound["prompt_sha256"] == row.task.metadata["prompt_sha256"]
    assert bound["response_sha256"] == output.sha256
    assert "PRIVATE" not in json.dumps(row.to_record())
    second = run_multi_harness(replace(config, resume=True))
    assert second.rows[0].resumed is True
    assert second.rows[0].lfb_record == row.lfb_record
    assert (
        score_multiharness_release(second, release_forecast, labels)["models"][0]
        == score
    )
    assert len(runtime) == 1
    (row.workspace / transcript.path).write_text("{}")
    with pytest.raises(ResumeRefusedError):
        run_multi_harness(replace(config, resume=True))
    assert len(runtime) == 1


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_HERMES_CHECKOUT"),
    reason="set LEGALFORECAST_HERMES_CHECKOUT to installed pinned source",
)
@pytest.mark.parametrize("mode", ["sequential", "batched"])
def test_pinned_upstream_managed_conversation_with_sdk_fixtures(tmp_path, mode):
    checkout = Path(os.environ["LEGALFORECAST_HERMES_CHECKOUT"])
    interpreter = hermes_agent.validate_checkout(checkout)
    subprocess.run(
        [
            str(interpreter),
            str(Path(__file__).with_name("hermes_upstream_probe.py")),
            str(checkout),
            str(Path(hermes_runtime.__file__)),
            str(tmp_path),
            mode,
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
        "tool_request_schema": TOOL_REQUEST_SCHEMA_VERSION,
        "tool_response_schema": TOOL_RESPONSE_SCHEMA_VERSION,
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

        def __init__(self, **kwargs):
            self.tools = [{"function": {"name": "read_canonical_task"}}]
            self.start_turn = kwargs["step_callback"]

        def run_conversation(self, _prompt):
            offset = 0
            while True:
                self.start_turn()
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
        "tool_request_schema": TOOL_REQUEST_SCHEMA_VERSION,
        "tool_response_schema": TOOL_RESPONSE_SCHEMA_VERSION,
    }
    if consume_all:
        result = hermes_runtime.execute(config, Agent, registry, incoming, outgoing)
        assert result["tool_call_count"] == 1
        assert "".join(chunks) == original
        assert outgoing.getvalue().count("\n") == 1
    else:
        with pytest.raises(ValueError, match="complete canonical task"):
            hermes_runtime.execute(config, Agent, registry, incoming, outgoing)
