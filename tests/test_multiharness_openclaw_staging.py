"""Create-only JSON staging refuses collisions without changing victim bytes."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness import openclaw_container as container
from legalforecast.multiharness import openclaw_worker as worker
from legalforecast.multiharness.openclaw import OpenClawError
from legalforecast.multiharness.openclaw_runtime import GatewayRuntimeConfig
from legalforecast.multiharness.release_runtime import (
    ReleaseHarnessError,
    release_bytes_sha256,
    write_release_json_create_only,
)
from legalforecast.multiharness.spec import RunRequest, RunResult

from test_multiharness_openclaw import request
from test_multiharness_openclaw_paid import _issued_options, _release_request
from test_paid_gateway_descriptor import _ENVIRONMENT


def _plant_collision(path: Path, victim: Path, attack: str) -> None:
    victim.write_bytes(b"existing bytes must survive")
    if attack == "symlink":
        path.symlink_to(victim)
    elif attack == "hardlink":
        os.link(victim, path)
    else:
        path.write_bytes(victim.read_bytes())


def test_host_refuses_request_timeout_different_from_container_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in _ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    options, descriptor = _issued_options(tmp_path)
    original = _release_request(descriptor)
    run_request = replace(
        original,
        sandbox_policy=replace(
            original.sandbox_policy, timeout_seconds=options.timeout_seconds + 1
        ),
    )
    workspace = tmp_path / "worker"
    with pytest.raises(OpenClawError, match="differs from its protected route"):
        container.OpenClawContainerAdapter(options).run_with_solver_input(
            run_request, workspace, tmp_path / "absent-solver"
        )
    assert not workspace.exists()


@pytest.mark.parametrize("filename", ["openclaw-request.json", "openclaw-model.json"])
@pytest.mark.parametrize("attack", ["symlink", "hardlink", "existing-file"])
def test_host_staging_collision_refuses_before_container_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str, attack: str
) -> None:
    for key, value in _ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    options, descriptor = _issued_options(tmp_path)
    adapter = container.OpenClawContainerAdapter(options)
    original = _release_request(descriptor)
    prompt = b"The blinded solver record."
    run_request = replace(
        original,
        task=replace(
            original.task,
            metadata={
                **original.task.metadata,
                "prompt_sha256": release_bytes_sha256(prompt),
            },
        ),
    )
    solver = tmp_path / "solver"
    solver.mkdir()
    (solver / "prompt.txt").write_bytes(prompt)
    workspace = tmp_path / "worker"
    workspace.mkdir()
    target = workspace / filename
    victim = tmp_path / "victim"
    _plant_collision(target, victim, attack)
    launched = False

    def forbidden_launch(*args: object, **kwargs: object) -> None:
        nonlocal launched
        launched = True
        raise AssertionError("colliding input must refuse before container launch")

    monkeypatch.setattr(container, "run_container_harness", forbidden_launch)
    try:
        with pytest.raises(ReleaseHarnessError, match="staging path is unavailable"):
            adapter.run_with_solver_input(run_request, workspace, solver)
    finally:
        assert victim.read_bytes() == b"existing bytes must survive"
        assert target.read_bytes() == b"existing bytes must survive"
        assert not launched


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "existing-file"])
def test_worker_result_collision_preserves_existing_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    attack: str,
) -> None:
    original = request()
    run_request = replace(
        original,
        model_key="anthropic:claude-opus-5-5",
        sandbox_policy=replace(original.sandbox_policy, allowed_provider_env_vars=()),
    )
    write_release_json_create_only(
        tmp_path / "openclaw-request.json", run_request.to_record()
    )
    write_release_json_create_only(
        tmp_path / "openclaw-model.json",
        {
            "context_limit": 200000,
            "max_output_tokens": 2048,
            "reasoning_effort": "high",
        },
    )
    monkeypatch.setenv(worker.CAPABILITY_ENV, "synthetic-run-capability")
    target = tmp_path / "openclaw-result.json"
    victim = tmp_path / "victim"
    _plant_collision(target, victim, attack)

    def completed_runtime(
        received: RunRequest,
        workspace: Path,
        transport: worker.StagedPromptTransport,
        *,
        gateway: GatewayRuntimeConfig,
    ) -> RunResult:
        assert received == run_request and workspace == tmp_path
        assert gateway.capability == "synthetic-run-capability"
        return RunResult(
            result_id="worker-result",
            request_id=received.request_id,
            status="succeeded",
            result_sha256="sha256:" + "5" * 64,
        )

    # Only the final staging branch is exercised: no actual runtime or provider.
    monkeypatch.setattr(worker, "run_openclaw", completed_runtime)
    try:
        with pytest.raises(ReleaseHarnessError, match="staging path is unavailable"):
            worker.execute(tmp_path)
    finally:
        assert victim.read_bytes() == b"existing bytes must survive"
        assert target.read_bytes() == b"existing bytes must survive"
    assert capsys.readouterr().out == ""
