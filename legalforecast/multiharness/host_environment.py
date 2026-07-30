"""Restricted environments for host-side multi-harness subprocesses."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

_PASSTHROUGH_RUNTIME_ENV_VARS = ("LC_CTYPE", "PATH")
_MANAGED_RUNTIME_ENV_DIRS: Mapping[str, str] = {
    "HOME": "adapter-home",
    "XDG_CACHE_HOME": "adapter-home/.cache",
    "XDG_CONFIG_HOME": "adapter-home/.config",
    "XDG_DATA_HOME": "adapter-home/.local/share",
    "XDG_STATE_HOME": "adapter-home/.local/state",
}
_RESERVED_RUNTIME_ENV_VARS = frozenset(
    (*_PASSTHROUGH_RUNTIME_ENV_VARS, *_MANAGED_RUNTIME_ENV_DIRS)
)


class HostEnvironmentError(RuntimeError):
    """Raised when a restricted host-subprocess environment is invalid."""


def build_container_backend_environment() -> dict[str, str]:
    """Build a value-free environment for a local rootless container backend."""

    environment = {
        name: os.environ[name]
        for name in _PASSTHROUGH_RUNTIME_ENV_VARS
        if name in os.environ
    }
    runtime_value = os.environ.get("XDG_RUNTIME_DIR")
    runtime_directory: Path | None = None
    if runtime_value:
        runtime_directory = _validated_runtime_directory(Path(runtime_value))
        environment["XDG_RUNTIME_DIR"] = str(runtime_directory)

    docker_host = os.environ.get("DOCKER_HOST")
    if docker_host:
        if runtime_directory is None:
            raise HostEnvironmentError(
                "DOCKER_HOST requires a validated XDG_RUNTIME_DIR"
            )
        environment["DOCKER_HOST"] = _validated_local_docker_host(
            docker_host,
            runtime_directory,
        )
    return environment


def require_rootless_container_daemon(
    backend_path: Path,
    backend: str,
    environment: Mapping[str, str],
) -> None:
    """Fail unless the selected Docker/Podman daemon is local and rootless."""

    if backend == "docker":
        argv = (
            str(backend_path),
            "info",
            "--format",
            "{{json .SecurityOptions}}",
        )
        value = _bounded_backend_output(argv, environment)
        try:
            decoded = cast(object, json.loads(value))
        except json.JSONDecodeError as exc:
            raise HostEnvironmentError(
                "container backend rootless preflight returned invalid data"
            ) from exc
        if not isinstance(decoded, list):
            raise HostEnvironmentError("Docker backend must be rootless")
        options = cast(list[object], decoded)
        if not any(
            isinstance(option, str) and "rootless" in option for option in options
        ):
            raise HostEnvironmentError("Docker backend must be rootless")
        return
    if backend == "podman":
        argv = (
            str(backend_path),
            "info",
            "--format",
            "{{.Host.Security.Rootless}}",
        )
        if _bounded_backend_output(argv, environment).strip().lower() != "true":
            raise HostEnvironmentError("Podman backend must be rootless")
        return
    raise HostEnvironmentError("unsupported container backend")


def require_local_pinned_container_image(
    backend_path: Path,
    image: str,
    environment: Mapping[str, str],
) -> None:
    """Fail unless the exact pinned image reference already exists locally."""

    completed = _run_backend_preflight(
        (
            str(backend_path),
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            image,
        ),
        environment,
    )
    image_id = completed.stdout.decode("ascii", errors="strict").strip()
    if not image_id.startswith("sha256:") or len(image_id) != 71:
        raise HostEnvironmentError(
            "local pinned container image preflight returned invalid identity"
        )
    if image.startswith("sha256:") and image_id != image:
        raise HostEnvironmentError("local image ID does not match pinned image")


def build_host_subprocess_environment(
    private_logs: Path,
    allowed_provider_env_vars: Sequence[str] = (),
) -> dict[str, str]:
    """Build runtime essentials plus explicit provider grants and isolated homes."""

    provider_values = require_provider_environment_values(allowed_provider_env_vars)
    _ensure_private_directory(private_logs)
    environment = {
        name: os.environ[name]
        for name in _PASSTHROUGH_RUNTIME_ENV_VARS
        if name in os.environ
    }
    environment.update(provider_values)
    for name, relative_path in _MANAGED_RUNTIME_ENV_DIRS.items():
        directory = _ensure_private_subdirectory(private_logs, relative_path)
        environment[name] = str(directory)
    return environment


def require_provider_environment_values(
    allowed_provider_env_vars: Sequence[str],
) -> dict[str, str]:
    """Return declared provider values or fail without exposing their contents."""

    reserved = sorted(
        set(allowed_provider_env_vars).intersection(_RESERVED_RUNTIME_ENV_VARS)
    )
    if reserved:
        formatted = ", ".join(reserved)
        raise HostEnvironmentError(
            "allowed_provider_env_vars contains host-managed runtime variables: "
            f"{formatted}"
        )
    missing = sorted(
        name
        for name in allowed_provider_env_vars
        if name not in os.environ or not os.environ[name]
    )
    if missing:
        formatted = ", ".join(missing)
        raise HostEnvironmentError(
            f"declared provider environment variables are not set or empty: {formatted}"
        )
    return {name: os.environ[name] for name in allowed_provider_env_vars}


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise HostEnvironmentError("host subprocess home paths must not be symlinks")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise HostEnvironmentError("host subprocess home paths must be directories")
    path.chmod(0o700)


def _ensure_private_subdirectory(root: Path, relative_path: str) -> Path:
    directory = root
    for part in Path(relative_path).parts:
        if part in {"", ".", ".."}:
            raise HostEnvironmentError("host subprocess home paths must be relative")
        directory /= part
        _ensure_private_directory(directory)
    return directory


def _validated_runtime_directory(path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise HostEnvironmentError(
            "XDG_RUNTIME_DIR must be an absolute non-symlink directory"
        )
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise HostEnvironmentError("XDG_RUNTIME_DIR is not available") from exc
    if resolved != path or not stat.S_ISDIR(metadata.st_mode):
        raise HostEnvironmentError(
            "XDG_RUNTIME_DIR must not traverse symlinks and must be a directory"
        )
    getuid = getattr(os, "getuid", None)
    if getuid is not None and metadata.st_uid != getuid():
        raise HostEnvironmentError(
            "XDG_RUNTIME_DIR must be owned by the current operator"
        )
    if metadata.st_mode & 0o022:
        raise HostEnvironmentError(
            "XDG_RUNTIME_DIR must not be group or world writable"
        )
    return resolved


def _validated_local_docker_host(value: str, runtime_directory: Path) -> str:
    prefix = "unix://"
    if not value.startswith(prefix):
        raise HostEnvironmentError("DOCKER_HOST must use a local Unix socket")
    socket_path = Path(value.removeprefix(prefix))
    if not socket_path.is_absolute() or socket_path.is_symlink():
        raise HostEnvironmentError(
            "DOCKER_HOST must name an absolute non-symlink Unix socket"
        )
    try:
        resolved = socket_path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise HostEnvironmentError("DOCKER_HOST socket is not available") from exc
    if (
        resolved != socket_path
        or not resolved.is_relative_to(runtime_directory)
        or not stat.S_ISSOCK(metadata.st_mode)
    ):
        raise HostEnvironmentError(
            "DOCKER_HOST must be a Unix socket beneath XDG_RUNTIME_DIR"
        )
    getuid = getattr(os, "getuid", None)
    if getuid is not None and metadata.st_uid != getuid():
        raise HostEnvironmentError(
            "DOCKER_HOST socket must be owned by the current operator"
        )
    if metadata.st_mode & 0o002:
        raise HostEnvironmentError("DOCKER_HOST socket must not be world writable")
    return f"{prefix}{resolved}"


def _bounded_backend_output(
    argv: tuple[str, ...],
    environment: Mapping[str, str],
) -> str:
    completed = _run_backend_preflight(argv, environment)
    try:
        return completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HostEnvironmentError(
            "container backend preflight returned invalid output"
        ) from exc


def _run_backend_preflight(
    argv: tuple[str, ...],
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostEnvironmentError("container backend preflight failed") from exc
    if completed.returncode != 0 or len(completed.stdout) > 65_536:
        raise HostEnvironmentError("container backend preflight failed")
    return completed
