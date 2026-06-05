"""Host-owned Docker/Podman sandbox policy planning."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from legalforecast.multiharness.spec import SandboxPolicy

BACKEND_DOCKER = "docker"
BACKEND_PODMAN = "podman"
SUPPORTED_CONTAINER_BACKENDS = frozenset({BACKEND_DOCKER, BACKEND_PODMAN})
NETWORK_NONE = "none"
PROVIDER_EGRESS_HOST_ONLY = "provider_egress_host_only"


@dataclass(frozen=True, slots=True)
class SandboxMount:
    """One bind mount in a host-owned tool sandbox."""

    source: Path
    target: str
    mode: str = "ro"

    def __post_init__(self) -> None:
        _validate_host_path(self.source, "source")
        _validate_container_path(self.target, "target")
        if self.mode not in {"ro", "rw"}:
            raise ValueError("mode must be ro or rw")

    def to_record(self) -> dict[str, str]:
        return {
            "source": str(self.source),
            "target": self.target,
            "mode": self.mode,
        }


@dataclass(frozen=True, slots=True)
class ContainerRuntimePlan:
    """Dry-run argv for a Docker/Podman tool sandbox."""

    backend: str
    argv: tuple[str, ...]
    policy: SandboxPolicy
    warnings: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "argv": list(self.argv),
            "policy": self.policy.to_record(),
            "warnings": list(self.warnings),
        }


def sandbox_policy(
    *,
    policy_id: str,
    backend: str,
    image: str,
    mounts: tuple[SandboxMount, ...],
    working_directory: str = "/workspace",
    timeout_seconds: int = 300,
    network_policy: str = PROVIDER_EGRESS_HOST_ONLY,
    uid_gid: str | None = None,
    pids_limit: int | None = 256,
    memory_limit: str | None = "2g",
    cpu_limit: str | None = "1",
    allowed_provider_env_vars: tuple[str, ...] = (),
) -> SandboxPolicy:
    """Build a serializable sandbox policy from typed mount objects."""

    return SandboxPolicy(
        policy_id=policy_id,
        backend=backend,
        image=image,
        network_policy=network_policy,
        timeout_seconds=timeout_seconds,
        mounts=tuple(mount.to_record() for mount in mounts),
        working_directory=working_directory,
        uid_gid=uid_gid,
        cap_drop=("ALL",),
        no_new_privileges=True,
        pids_limit=pids_limit,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        allowed_provider_env_vars=allowed_provider_env_vars,
    )


def build_container_plan(policy: SandboxPolicy) -> ContainerRuntimePlan:
    """Return the Docker/Podman argv that would run a tool sandbox."""

    if policy.backend not in SUPPORTED_CONTAINER_BACKENDS:
        formatted = ", ".join(sorted(SUPPORTED_CONTAINER_BACKENDS))
        raise ValueError(f"backend must be one of: {formatted}")
    _validate_policy_paths(policy)
    argv: list[str] = [
        policy.backend,
        "run",
        "--rm",
        "--network=none",
    ]
    for cap in policy.cap_drop:
        argv.extend(("--cap-drop", cap))
    if policy.no_new_privileges:
        argv.extend(("--security-opt", "no-new-privileges"))
    if policy.uid_gid is not None:
        argv.extend(("--user", policy.uid_gid))
    if policy.pids_limit is not None:
        argv.extend(("--pids-limit", str(policy.pids_limit)))
    if policy.memory_limit is not None:
        argv.extend(("--memory", policy.memory_limit))
    if policy.cpu_limit is not None:
        argv.append(f"--cpus={policy.cpu_limit}")
    argv.extend(("--workdir", policy.working_directory))
    for mount in policy.mounts:
        argv.extend(("--mount", _mount_arg(mount)))
    argv.append(policy.image)
    return ContainerRuntimePlan(
        backend=policy.backend,
        argv=tuple(argv),
        policy=policy,
        warnings=_policy_warnings(policy),
    )


def require_container_backend(
    policy: SandboxPolicy,
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> None:
    """Fail before live scheduling when the declared backend is unavailable."""

    if policy.backend not in SUPPORTED_CONTAINER_BACKENDS:
        formatted = ", ".join(sorted(SUPPORTED_CONTAINER_BACKENDS))
        raise ValueError(f"backend must be one of: {formatted}")
    if resolver(policy.backend) is None:
        raise RuntimeError(f"container backend is not available: {policy.backend}")


def _mount_arg(record: Mapping[str, str]) -> str:
    source = record["source"]
    target = record["target"]
    mode = record["mode"]
    readonly = ",readonly" if mode == "ro" else ""
    return f"type=bind,src={source},dst={target}{readonly}"


def _policy_warnings(policy: SandboxPolicy) -> tuple[str, ...]:
    warnings: list[str] = []
    if policy.network_policy == PROVIDER_EGRESS_HOST_ONLY:
        warnings.append(
            "provider API calls are host-adapter only; tool container network is none"
        )
    if policy.allowed_provider_env_vars:
        warnings.append(
            "allowed provider env vars are recorded for host adapter processes only"
        )
    return tuple(warnings)


def _validate_policy_paths(policy: SandboxPolicy) -> None:
    _validate_container_path(policy.working_directory, "working_directory")
    for mount in policy.mounts:
        _validate_host_path(Path(mount["source"]), "mount.source")
        _validate_container_path(mount["target"], "mount.target")


def _validate_host_path(path: Path, field_name: str) -> None:
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be absolute")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} must not contain traversal segments")


def _validate_container_path(value: str, field_name: str) -> None:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute container path")
    if any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} must not contain traversal segments")
