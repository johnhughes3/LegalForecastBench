"""Restricted environments for host-side multi-harness subprocesses."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

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
