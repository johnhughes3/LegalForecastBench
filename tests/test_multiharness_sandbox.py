from __future__ import annotations

import os
from itertools import pairwise
from pathlib import Path

import pytest
from legalforecast.multiharness.sandbox import (
    BACKEND_DOCKER,
    BACKEND_PODMAN,
    PROVIDER_EGRESS_HOST_ONLY,
    ContainerRuntimePlan,
    SandboxMount,
    build_container_plan,
    build_live_container_plan,
    live_container_public_plan,
    require_container_backend,
    resolve_container_backend,
    sandbox_policy,
    validate_container_backend_path,
)
from legalforecast.multiharness.spec import SandboxPolicy

PINNED_IMAGE = (
    "ghcr.io/johnhughes3/legalforecast-tool"
    "@sha256:0123456789abcdef0123456789abcdef"
    "0123456789abcdef0123456789abcdef"
)
BACKEND_PATH = Path("/usr/bin/true")
SESSION_TOKEN = "a" * 32


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


def test_live_container_create_plan_has_fixed_bounded_hardening(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "task.json").write_text("{}\n", encoding="utf-8")

    plan = _live_plan(tmp_path, input_root=input_root)

    assert plan.argv[:5] == (
        str(BACKEND_PATH),
        "create",
        "--rm",
        "--interactive",
        "--pull=never",
    )
    assert ("--name", "lfb-tool-fixture") in _pairs(plan.argv)
    assert (
        "--label",
        f"legalforecast.multiharness.session={SESSION_TOKEN}",
    ) in _pairs(plan.argv)
    assert "--network=none" in plan.argv
    assert "--read-only" in plan.argv
    assert (
        "--tmpfs",
        "/workspace/output:rw,noexec,nosuid,nodev,size=64m",
    ) in _pairs(plan.argv)
    assert ("--cap-drop", "ALL") in _pairs(plan.argv)
    assert ("--security-opt", "no-new-privileges") in _pairs(plan.argv)
    assert ("--user", "65532:65532") in _pairs(plan.argv)
    assert ("--pids-limit", "64") in _pairs(plan.argv)
    assert ("--memory", "512m") in _pairs(plan.argv)
    assert "--cpus=1" in plan.argv
    mounts = [
        plan.argv[index + 1]
        for index, value in enumerate(plan.argv)
        if value == "--mount"
    ]
    assert mounts == [f"type=bind,src={input_root},dst=/workspace/input,readonly"]
    assert plan.argv[-1] == PINNED_IMAGE


def test_live_public_plan_is_stable_and_host_path_free(tmp_path: Path) -> None:
    first = live_container_public_plan(_live_policy())
    second = live_container_public_plan(_live_policy())

    assert first == second
    serialized = repr(first)
    assert str(tmp_path) not in serialized
    assert first["lifecycle"] == "create_then_attach"
    assert first["policy"] == _live_policy().to_record()
    assert first["output"]["mode"] == "bounded_tmpfs"  # type: ignore[index]


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"image": "python:3.12-slim"}, "digest-pinned"),
        ({"mounts": ({"source": "/tmp", "target": "/host", "mode": "rw"},)}, "mounts"),
        ({"network_policy": "bridge"}, "network_policy"),
        ({"uid_gid": "0:0"}, "non-root"),
        ({"cap_drop": ()}, "cap_drop"),
        ({"no_new_privileges": False}, "no_new_privileges"),
        ({"pids_limit": None}, "pids_limit"),
        ({"memory_limit": None}, "memory_limit"),
        ({"cpu_limit": None}, "cpu_limit"),
    ),
)
def test_live_container_plan_rejects_weak_policy(
    tmp_path: Path,
    override: dict[str, object],
    message: str,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()

    with pytest.raises(ValueError, match=message):
        _live_plan(tmp_path, input_root=input_root, policy=_live_policy(**override))


@pytest.mark.parametrize(
    ("name", "token", "message"),
    (
        ("-option", SESSION_TOKEN, "container_name"),
        ("fixture", "short", "session_token"),
    ),
)
def test_live_container_plan_rejects_unsafe_identity(
    tmp_path: Path,
    name: str,
    token: str,
    message: str,
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()

    with pytest.raises(ValueError, match=message):
        build_live_container_plan(
            _live_policy(),
            input_root=input_root,
            container_name=name,
            session_token=token,
            cidfile=tmp_path / "container.cid",
            backend_path=BACKEND_PATH,
        )


def test_live_container_plan_rejects_unsafe_input_tree(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    regular = input_root / "task.json"
    regular.write_text("{}\n", encoding="utf-8")
    (input_root / "linked").symlink_to(regular)

    with pytest.raises(ValueError, match="symlink"):
        _live_plan(tmp_path, input_root=input_root)

    (input_root / "linked").unlink()
    os.mkfifo(input_root / "fixture.fifo")
    with pytest.raises(ValueError, match="regular files"):
        _live_plan(tmp_path, input_root=input_root)


def test_backend_resolution_rejects_untrusted_executable_mode(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "docker"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o777)

    with pytest.raises(ValueError, match="trusted ownership"):
        validate_container_backend_path(executable)


def test_backend_resolution_returns_absolute_validated_path() -> None:
    policy = _live_policy()

    assert (
        resolve_container_backend(
            policy,
            resolver=lambda _name: str(BACKEND_PATH),
        )
        == BACKEND_PATH
    )


def _pairs(values: tuple[str, ...]) -> set[tuple[str, str]]:
    return set(pairwise(values))


def _live_policy(**overrides: object) -> SandboxPolicy:
    values: dict[str, object] = {
        "policy_id": "live-fixture",
        "backend": BACKEND_DOCKER,
        "image": PINNED_IMAGE,
        "network_policy": PROVIDER_EGRESS_HOST_ONLY,
        "timeout_seconds": 30,
        "mounts": (),
        "working_directory": "/workspace",
        "uid_gid": "65532:65532",
        "cap_drop": ("ALL",),
        "no_new_privileges": True,
        "pids_limit": 64,
        "memory_limit": "512m",
        "cpu_limit": "1",
        "allowed_provider_env_vars": (),
    }
    values.update(overrides)
    return SandboxPolicy(**values)  # type: ignore[arg-type]


def _live_plan(
    tmp_path: Path,
    *,
    input_root: Path,
    policy: SandboxPolicy | None = None,
) -> ContainerRuntimePlan:
    return build_live_container_plan(
        policy or _live_policy(),
        input_root=input_root,
        container_name="lfb-tool-fixture",
        session_token=SESSION_TOKEN,
        cidfile=tmp_path / "container.cid",
        backend_path=BACKEND_PATH,
    )
