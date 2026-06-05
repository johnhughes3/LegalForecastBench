from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from legalforecast.multiharness.sandbox import (
    BACKEND_DOCKER,
    BACKEND_PODMAN,
    PROVIDER_EGRESS_HOST_ONLY,
    SandboxMount,
    build_container_plan,
    require_container_backend,
    sandbox_policy,
)


def test_docker_plan_defaults_to_network_disabled_and_hardening(
    tmp_path: Path,
) -> None:
    policy = sandbox_policy(
        policy_id="fixture",
        backend=BACKEND_DOCKER,
        image="python:3.12-slim",
        mounts=(
            SandboxMount(tmp_path / "workspace", "/workspace", "rw"),
            SandboxMount(tmp_path / "documents", "/workspace/documents", "ro"),
        ),
        uid_gid="1000:1000",
        allowed_provider_env_vars=("OPENAI_API_KEY",),
    )

    plan = build_container_plan(policy)

    assert plan.argv[:4] == ("docker", "run", "--rm", "--network=none")
    assert ("--cap-drop", "ALL") in _pairs(plan.argv)
    assert ("--security-opt", "no-new-privileges") in _pairs(plan.argv)
    assert ("--user", "1000:1000") in _pairs(plan.argv)
    assert "--cpus=1" in plan.argv
    assert "python:3.12-slim" == plan.argv[-1]
    assert all("OPENAI_API_KEY" not in arg for arg in plan.argv)
    assert plan.policy.network_policy == PROVIDER_EGRESS_HOST_ONLY
    assert plan.warnings


def test_podman_plan_uses_declared_backend(tmp_path: Path) -> None:
    policy = sandbox_policy(
        policy_id="fixture",
        backend=BACKEND_PODMAN,
        image="python:3.12-slim",
        mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
    )

    plan = build_container_plan(policy)

    assert plan.backend == "podman"
    assert plan.argv[0] == "podman"
    assert any(
        arg.startswith(f"type=bind,src={tmp_path / 'workspace'}") for arg in plan.argv
    )


def test_provider_egress_policy_keeps_tool_container_network_disabled(
    tmp_path: Path,
) -> None:
    policy = sandbox_policy(
        policy_id="provider-host-only",
        backend=BACKEND_DOCKER,
        image="python:3.12-slim",
        mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
        network_policy=PROVIDER_EGRESS_HOST_ONLY,
        allowed_provider_env_vars=("ANTHROPIC_API_KEY",),
    )

    plan = build_container_plan(policy)

    assert "--network=none" in plan.argv
    assert all("ANTHROPIC_API_KEY" not in arg for arg in plan.argv)
    assert "host-adapter only" in " ".join(plan.warnings)


def test_mount_safety_rejects_relative_and_traversal_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        SandboxMount(Path("relative"), "/workspace")

    with pytest.raises(ValueError, match="traversal"):
        SandboxMount(tmp_path / "workspace", "/workspace/../secret")


def test_timeout_and_resource_limits_validate(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        sandbox_policy(
            policy_id="bad-timeout",
            backend=BACKEND_DOCKER,
            image="python:3.12-slim",
            mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
            timeout_seconds=0,
        )

    with pytest.raises(ValueError, match="pids_limit"):
        sandbox_policy(
            policy_id="bad-pids",
            backend=BACKEND_DOCKER,
            image="python:3.12-slim",
            mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
            pids_limit=0,
        )


def test_missing_container_backend_fails_before_live_scheduling(
    tmp_path: Path,
) -> None:
    policy = sandbox_policy(
        policy_id="fixture",
        backend=BACKEND_DOCKER,
        image="python:3.12-slim",
        mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
    )

    with pytest.raises(RuntimeError, match="not available"):
        require_container_backend(policy, resolver=lambda _: None)


def test_sandbox_plan_does_not_require_backend_installed(tmp_path: Path) -> None:
    policy = sandbox_policy(
        policy_id="fixture",
        backend=BACKEND_DOCKER,
        image="python:3.12-slim",
        mounts=(SandboxMount(tmp_path / "workspace", "/workspace", "rw"),),
    )

    plan = build_container_plan(policy)

    assert plan.argv[0] == "docker"


def _pairs(values: tuple[str, ...]) -> set[tuple[str, str]]:
    return set(pairwise(values))
