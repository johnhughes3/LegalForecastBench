"""Host-owned Docker/Podman sandbox policy planning."""

from __future__ import annotations

import os
import re
import shutil
import stat
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
LIVE_WORKING_DIRECTORY = "/workspace"
LIVE_INPUT_TARGET = f"{LIVE_WORKING_DIRECTORY}/input"
LIVE_OUTPUT_TARGET = f"{LIVE_WORKING_DIRECTORY}/output"
LIVE_TMPFS = "/tmp:rw,noexec,nosuid,nodev,size=64m"
LIVE_OUTPUT_TMPFS = f"{LIVE_OUTPUT_TARGET}:rw,noexec,nosuid,nodev,size=64m"
LIVE_SESSION_LABEL = "legalforecast.multiharness.session"

_CONTAINER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SESSION_TOKEN_RE = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST_PINNED_IMAGE_RE = re.compile(
    r"(?:[^@\s]+@)?sha256:[0-9a-f]{64}\Z",
)
_UID_GID_RE = re.compile(r"([0-9]+):([0-9]+)\Z")
_MEMORY_LIMIT_RE = re.compile(r"[1-9][0-9]*(?:[bkmgBKMG])?\Z")
_CPU_LIMIT_RE = re.compile(r"(?:[1-9][0-9]*(?:\.[0-9]+)?|0\.[0-9]*[1-9][0-9]*)\Z")


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


def validate_live_container_policy(policy: SandboxPolicy) -> None:
    """Reject a policy that cannot safely authorize live container execution."""

    if policy.backend not in SUPPORTED_CONTAINER_BACKENDS:
        formatted = ", ".join(sorted(SUPPORTED_CONTAINER_BACKENDS))
        raise ValueError(f"backend must be one of: {formatted}")
    if _DIGEST_PINNED_IMAGE_RE.fullmatch(policy.image) is None:
        raise ValueError(
            "live container image must be digest-pinned by sha256 digest or image ID"
        )
    if policy.network_policy not in {NETWORK_NONE, PROVIDER_EGRESS_HOST_ONLY}:
        raise ValueError(
            f"live network_policy must be {NETWORK_NONE} or {PROVIDER_EGRESS_HOST_ONLY}"
        )
    if (
        policy.allowed_provider_env_vars
        and policy.network_policy != PROVIDER_EGRESS_HOST_ONLY
    ):
        raise ValueError(
            "provider host environment allowlist requires "
            f"{PROVIDER_EGRESS_HOST_ONLY} network_policy"
        )
    if policy.mounts:
        raise ValueError(
            "live policy mounts must be empty; input and output mounts are host-owned"
        )
    if policy.working_directory != LIVE_WORKING_DIRECTORY:
        raise ValueError(f"live working_directory must be {LIVE_WORKING_DIRECTORY}")
    if policy.uid_gid is None:
        raise ValueError("live uid_gid is mandatory")
    uid_gid_match = _UID_GID_RE.fullmatch(policy.uid_gid)
    if uid_gid_match is None:
        raise ValueError("live uid_gid must have numeric UID:GID form")
    if any(int(value) == 0 for value in uid_gid_match.groups()):
        raise ValueError("live uid_gid must select a non-root UID and GID")
    if policy.cap_drop != ("ALL",):
        raise ValueError("live cap_drop must contain exactly ALL")
    if not policy.no_new_privileges:
        raise ValueError("live no_new_privileges must be enabled")
    if policy.pids_limit is None:
        raise ValueError("live pids_limit is mandatory")
    if policy.memory_limit is None:
        raise ValueError("live memory_limit is mandatory")
    if _MEMORY_LIMIT_RE.fullmatch(policy.memory_limit) is None:
        raise ValueError("live memory_limit must be a positive bounded value")
    if policy.cpu_limit is None:
        raise ValueError("live cpu_limit is mandatory")
    if _CPU_LIMIT_RE.fullmatch(policy.cpu_limit) is None:
        raise ValueError("live cpu_limit must be a positive bounded value")


def build_live_container_plan(
    policy: SandboxPolicy,
    *,
    input_root: Path,
    container_name: str,
    session_token: str,
    cidfile: Path,
    backend_path: Path | None = None,
) -> ContainerRuntimePlan:
    """Build fail-closed create argv for one live host-owned tool container."""

    validate_live_container_policy(policy)
    safe_input = _validate_live_mount_root(input_root, "input_root")
    if _CONTAINER_NAME_RE.fullmatch(container_name) is None:
        raise ValueError("container_name must be a safe Docker/Podman name")
    if _SESSION_TOKEN_RE.fullmatch(session_token) is None:
        raise ValueError("session_token must be 32 lowercase hexadecimal characters")
    safe_cidfile = _validate_cidfile(cidfile)
    if safe_cidfile.is_relative_to(safe_input):
        raise ValueError("cidfile must be outside input_root")
    resolved_backend = (
        validate_container_backend_path(backend_path)
        if backend_path is not None
        else resolve_container_backend(policy)
    )
    uid_gid = policy.uid_gid
    pids_limit = policy.pids_limit
    memory_limit = policy.memory_limit
    cpu_limit = policy.cpu_limit
    assert uid_gid is not None
    assert pids_limit is not None
    assert memory_limit is not None
    assert cpu_limit is not None

    argv = (
        str(resolved_backend),
        "create",
        "--rm",
        "--interactive",
        "--pull=never",
        "--name",
        container_name,
        "--label",
        f"{LIVE_SESSION_LABEL}={session_token}",
        "--cidfile",
        str(safe_cidfile),
        "--network=none",
        "--read-only",
        "--tmpfs",
        LIVE_TMPFS,
        "--tmpfs",
        LIVE_OUTPUT_TMPFS,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        uid_gid,
        "--pids-limit",
        str(pids_limit),
        "--memory",
        memory_limit,
        f"--cpus={cpu_limit}",
        "--workdir",
        LIVE_WORKING_DIRECTORY,
        "--mount",
        (f"type=bind,src={safe_input},dst={LIVE_INPUT_TARGET},readonly"),
        policy.image,
    )
    return ContainerRuntimePlan(
        backend=policy.backend,
        argv=argv,
        policy=policy,
    )


def live_container_public_plan(policy: SandboxPolicy) -> dict[str, Any]:
    """Return a deterministic host-path-free record of live isolation."""

    validate_live_container_policy(policy)
    return {
        "schema_version": "legalforecast.multiharness.live_container_plan.v1",
        "backend": policy.backend,
        "policy": policy.to_record(),
        "lifecycle": "create_then_attach",
        "image": policy.image,
        "pull_policy": "never",
        "network": "none",
        "root_filesystem": "read_only",
        "working_directory": LIVE_WORKING_DIRECTORY,
        "input": {
            "source": "canonical_task",
            "target": LIVE_INPUT_TARGET,
            "mode": "read_only_bind",
        },
        "output": {
            "target": LIVE_OUTPUT_TARGET,
            "mode": "bounded_tmpfs",
            "options": LIVE_OUTPUT_TMPFS.split(":", maxsplit=1)[1],
            "extraction_channel": "bounded_jsonl",
        },
        "temporary_filesystem": LIVE_TMPFS,
        "uid_gid": policy.uid_gid,
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "pids_limit": policy.pids_limit,
        "memory_limit": policy.memory_limit,
        "cpu_limit": policy.cpu_limit,
    }


def require_container_backend(
    policy: SandboxPolicy,
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> None:
    """Fail before live scheduling when the declared backend is unavailable."""

    resolve_container_backend(policy, resolver=resolver)


def resolve_container_backend(
    policy: SandboxPolicy,
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Resolve and validate the exact local backend executable."""

    if policy.backend not in SUPPORTED_CONTAINER_BACKENDS:
        formatted = ", ".join(sorted(SUPPORTED_CONTAINER_BACKENDS))
        raise ValueError(f"backend must be one of: {formatted}")
    resolved = resolver(policy.backend)
    if resolved is None:
        raise RuntimeError(f"container backend is not available: {policy.backend}")
    return validate_container_backend_path(Path(resolved))


def validate_container_backend_path(path: Path) -> Path:
    """Validate an immutable-enough absolute backend executable path."""

    if not path.is_absolute():
        raise ValueError("container backend executable must be absolute")
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise ValueError("container backend executable is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or not os.access(resolved, os.X_OK):
        raise ValueError("container backend executable must be an executable file")
    getuid = getattr(os, "getuid", None)
    allowed_owners = {0}
    if getuid is not None:
        allowed_owners.add(getuid())
    if metadata.st_uid not in allowed_owners or metadata.st_mode & 0o022:
        raise ValueError(
            "container backend executable must have trusted ownership and mode"
        )
    current = Path(resolved.anchor)
    for part in resolved.parts[1:-1]:
        current /= part
        parent_metadata = current.stat()
        if (
            parent_metadata.st_uid not in allowed_owners
            or parent_metadata.st_mode & 0o022
        ):
            raise ValueError(
                "container backend executable parents must have trusted ownership "
                "and mode"
            )
    return resolved


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
            "provider API calls are host-adapter only; planned tool container network "
            "is none, and this plan record alone is not execution evidence"
        )
    if policy.allowed_provider_env_vars:
        warnings.append("provider env allowlist applies to host adapter processes only")
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


def _validate_live_mount_root(path: Path, field_name: str) -> Path:
    _validate_host_path(path, field_name)
    if "," in str(path) or any(ord(character) < 32 for character in str(path)):
        raise ValueError(f"{field_name} contains unsafe mount-option characters")
    _reject_symlink_components(path, field_name)
    if not path.is_dir():
        raise ValueError(f"{field_name} must be an existing directory")
    resolved = path.resolve(strict=True)
    if resolved == Path("/"):
        raise ValueError(f"{field_name} must not be the filesystem root")
    if resolved == Path.home().resolve(strict=True):
        raise ValueError(f"{field_name} must not be the home directory")
    _validate_mount_tree(resolved, field_name)
    return resolved


def _reject_symlink_components(path: Path, field_name: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            raise ValueError(f"{field_name} must already exist") from None
        if stat.S_ISLNK(mode):
            raise ValueError(f"{field_name} must not contain symlink components")


def _validate_mount_tree(root: Path, field_name: str) -> None:
    for descendant in root.rglob("*"):
        mode = descendant.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"{field_name} must not contain symlinks")
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(
                f"{field_name} must contain only regular files and directories"
            )


def _validate_cidfile(path: Path) -> Path:
    _validate_host_path(path, "cidfile")
    if any(ord(character) < 32 for character in str(path)):
        raise ValueError("cidfile contains unsafe control characters")
    if path.exists() or path.is_symlink():
        raise ValueError("cidfile must not already exist")
    parent = path.parent
    _reject_symlink_components(parent, "cidfile parent")
    if not parent.is_dir():
        raise ValueError("cidfile parent must be an existing directory")
    resolved_parent = parent.resolve(strict=True)
    if resolved_parent in {Path("/"), Path.home().resolve(strict=True)}:
        raise ValueError("cidfile parent must not be root or the home directory")
    return resolved_parent / path.name
