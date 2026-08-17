"""Allowlisted host environment and credential projection for local CLI solvers.

Child processes receive only runtime essentials, isolated HOME/XDG/scratch
directories, and credentials for the declared auth profile. Ambient shell
state, keyrings, sockets, and undeclared provider variables do not pass
through. Credential material is fetched through ``infisical-agent-sandbox``
only; fixture-none never contacts that wrapper.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast

from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    AuthProfileError,
    ResolvedAuthProfile,
    require_infisical_environment,
)
from legalforecast.multiharness.validation import validate_env_var_names

_PASSTHROUGH_RUNTIME_ENV_VARS = ("LC_CTYPE", "PATH")
_WRAPPER_LAUNCH_ENV_VARS = (
    "LC_CTYPE",
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TERM",
)
_MANAGED_RUNTIME_ENV_DIRS: Mapping[str, str] = {
    "HOME": "adapter-home",
    "XDG_CACHE_HOME": "adapter-home/.cache",
    "XDG_CONFIG_HOME": "adapter-home/.config",
    "XDG_DATA_HOME": "adapter-home/.local/share",
    "XDG_STATE_HOME": "adapter-home/.local/state",
    "TMPDIR": "tmp",
    "CLAUDE_CONFIG_DIR": "adapter-home/.claude",
    "CODEX_HOME": "adapter-home/.codex",
}
_RESERVED_RUNTIME_ENV_VARS = frozenset(
    (*_PASSTHROUGH_RUNTIME_ENV_VARS, *_MANAGED_RUNTIME_ENV_DIRS)
)
_INFISICAL_WRAPPER_NAME = "infisical-agent-sandbox"
_WRAPPER_FETCH_TIMEOUT_SECONDS = 30
_WRAPPER_MAX_OUTPUT_BYTES = 65_536


class CredentialSource(Protocol):
    """Fetch projected credential values for one resolved profile."""

    def fetch_projected_env(self, profile: ResolvedAuthProfile) -> Mapping[str, str]:
        """Return only the profile's projected environment names."""

        ...


class StaticCredentialSource:
    """Test double that never shells out to Infisical or 1Password."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def fetch_projected_env(self, profile: ResolvedAuthProfile) -> Mapping[str, str]:
        if profile.profile_id in {FIXTURE_NONE, CONTRIBUTOR_SUBSCRIPTION}:
            raise AuthProfileError(
                "fixture-none never reads credentials"
                if profile.profile_id == FIXTURE_NONE
                else "contributor-subscription never reads credentials"
            )
        missing = [
            name
            for name in profile.projected_env_vars
            if name not in self._values or not self._values[name]
        ]
        if missing:
            raise AuthProfileError("declared auth profile credentials are unavailable")
        extra = set(self._values).difference(profile.projected_env_vars)
        if extra:
            raise AuthProfileError(
                "credential source returned names outside the declared profile"
            )
        return {name: self._values[name] for name in profile.projected_env_vars}


class InfisicalSandboxCredentialSource:
    """Load declared profile secrets through ``infisical-agent-sandbox`` only."""

    def __init__(
        self,
        *,
        wrapper_path: Path | None = None,
        python_executable: str | None = None,
        parent_env: Mapping[str, str] | None = None,
        timeout_seconds: float = _WRAPPER_FETCH_TIMEOUT_SECONDS,
    ) -> None:
        self._wrapper_path = wrapper_path
        self._python_executable = python_executable or sys.executable
        self._parent_env = parent_env
        self._timeout_seconds = timeout_seconds

    def fetch_projected_env(self, profile: ResolvedAuthProfile) -> Mapping[str, str]:
        if profile.profile_id in {FIXTURE_NONE, CONTRIBUTOR_SUBSCRIPTION}:
            raise AuthProfileError(
                "fixture-none never reads credentials"
                if profile.profile_id == FIXTURE_NONE
                else "contributor-subscription never reads credentials"
            )
        if profile.infisical_path is None:
            raise AuthProfileError("credentialed profile is missing Infisical path")
        require_infisical_environment(profile.infisical_env)
        wrapper = self._resolved_wrapper()
        parent = os.environ if self._parent_env is None else self._parent_env
        argv = (
            str(wrapper),
            "run",
            "--env",
            profile.infisical_env,
            "--path",
            profile.infisical_path,
            "--json",
            "--",
            self._python_executable,
            "-m",
            "legalforecast.multiharness._infisical_env_extract",
            "--names",
            ",".join(profile.projected_env_vars),
        )
        _reject_bare_infisical_or_op(argv)
        try:
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
                env=_wrapper_launch_environment(parent),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuthProfileError(
                "declared auth profile credentials are unavailable"
            ) from exc
        if (
            completed.returncode != 0
            or len(completed.stdout) > _WRAPPER_MAX_OUTPUT_BYTES
        ):
            raise AuthProfileError("declared auth profile credentials are unavailable")
        try:
            decoded = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthProfileError(
                "declared auth profile credentials are unavailable"
            ) from exc
        if not isinstance(decoded, dict):
            raise AuthProfileError("declared auth profile credentials are unavailable")
        payload = cast(dict[object, object], decoded)
        values: dict[str, str] = {}
        for name in profile.projected_env_vars:
            raw = payload.get(name)
            if not isinstance(raw, str) or not raw:
                raise AuthProfileError(
                    "declared auth profile credentials are unavailable"
                )
            values[name] = raw
        if set(payload) - set(profile.projected_env_vars):
            raise AuthProfileError(
                "credential source returned names outside the declared profile"
            )
        _reject_ambient_fallback(values, parent)
        return values

    def _resolved_wrapper(self) -> Path:
        if self._wrapper_path is not None:
            return self._wrapper_path
        located = shutil.which(_INFISICAL_WRAPPER_NAME)
        if located is None:
            raise AuthProfileError("declared auth profile credentials are unavailable")
        return Path(located)


def fetch_named_infisical_secret(
    *,
    environment: str,
    path: str,
    name: str,
    wrapper_path: Path | None = None,
    python_executable: str | None = None,
    parent_env: Mapping[str, str] | None = None,
    timeout_seconds: float = _WRAPPER_FETCH_TIMEOUT_SECONDS,
) -> str:
    """Fetch one sanctioned Infisical secret through the reviewed wrapper.

    This is invoked only when a caller explicitly requests a named secret.
    It never reads host environment credentials and never uses the bare
    ``infisical`` CLI.
    """

    require_infisical_environment(environment)
    if not path.startswith("/agents/sandbox/legalforecastbench/"):
        raise AuthProfileError("Infisical path is outside the sanctioned namespace")
    validate_env_var_names((name,), "secret name")
    wrapper = wrapper_path
    if wrapper is None:
        located = shutil.which(_INFISICAL_WRAPPER_NAME)
        if located is None:
            raise AuthProfileError("declared auth profile credentials are unavailable")
        wrapper = Path(located)
    parent = os.environ if parent_env is None else parent_env
    argv = (
        str(wrapper),
        "run",
        "--env",
        environment,
        "--path",
        path,
        "--json",
        "--",
        python_executable or sys.executable,
        "-m",
        "legalforecast.multiharness._infisical_env_extract",
        "--names",
        name,
    )
    _reject_bare_infisical_or_op(argv)
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            env=_wrapper_launch_environment(parent),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthProfileError(
            "declared auth profile credentials are unavailable"
        ) from exc
    if completed.returncode != 0 or len(completed.stdout) > _WRAPPER_MAX_OUTPUT_BYTES:
        raise AuthProfileError("declared auth profile credentials are unavailable")
    try:
        decoded = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthProfileError(
            "declared auth profile credentials are unavailable"
        ) from exc
    if not isinstance(decoded, dict):
        raise AuthProfileError("declared auth profile credentials are unavailable")
    payload = cast(dict[object, object], decoded)
    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise AuthProfileError("declared auth profile credentials are unavailable")
    if set(payload) - {name}:
        raise AuthProfileError(
            "credential source returned names outside the declared profile"
        )
    _reject_ambient_fallback({name: raw}, parent)
    return raw


def project_profile_credentials(
    profile: ResolvedAuthProfile,
    *,
    credential_source: CredentialSource | None,
    parent_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return projected credentials for the declared profile only."""

    if profile.profile_id in {FIXTURE_NONE, CONTRIBUTOR_SUBSCRIPTION}:
        if credential_source is not None:
            raise AuthProfileError(
                "fixture-none never reads credentials"
                if profile.profile_id == FIXTURE_NONE
                else "contributor-subscription never reads credentials"
            )
        return {}
    if credential_source is None:
        raise AuthProfileError("declared auth profile credentials are unavailable")
    projected = dict(credential_source.fetch_projected_env(profile))
    expected = set(profile.projected_env_vars)
    if set(projected) != expected:
        raise AuthProfileError(
            "credential source returned names outside the declared profile"
        )
    parent = os.environ if parent_env is None else parent_env
    _reject_ambient_fallback(projected, parent)
    return projected


def build_local_cli_environment(
    profile: ResolvedAuthProfile,
    scratch_root: Path,
    *,
    projected_credentials: Mapping[str, str] | None = None,
    parent_env: Mapping[str, str] | None = None,
    extra_allowlist: Sequence[str] = (),
) -> dict[str, str]:
    """Build a solver environment that does not inherit ambient shell state."""

    parent = os.environ if parent_env is None else parent_env
    credentials = dict(projected_credentials or ())
    if profile.profile_id in {FIXTURE_NONE, CONTRIBUTOR_SUBSCRIPTION}:
        if credentials:
            raise AuthProfileError(
                "fixture-none never reads credentials"
                if profile.profile_id == FIXTURE_NONE
                else "contributor-subscription never exports credentials"
            )
    elif set(credentials) != set(profile.projected_env_vars):
        raise AuthProfileError(
            "projected credentials must match the declared profile exactly"
        )
    extra = _validated_extra_allowlist(extra_allowlist)
    overlap = extra.intersection(credentials)
    if overlap:
        raise AuthProfileError(
            "extra allowlist names collide with projected credentials"
        )
    reserved_projected = sorted(
        set(credentials).intersection(_RESERVED_RUNTIME_ENV_VARS)
    )
    if reserved_projected:
        formatted = ", ".join(reserved_projected)
        raise AuthProfileError(
            "projected credentials collide with host-managed runtime "
            f"variables: {formatted}"
        )
    _reject_ambient_fallback(credentials, parent)
    ensure_private_scratch_directory(scratch_root)

    environment: dict[str, str] = {}
    for name in _PASSTHROUGH_RUNTIME_ENV_VARS:
        value = parent.get(name)
        if value:
            environment[name] = value
    for name in extra:
        value = parent.get(name)
        if not value:
            raise AuthProfileError(
                f"allowlisted runtime environment variable {name} is not set"
            )
        environment[name] = value
    for name, relative_path in _MANAGED_RUNTIME_ENV_DIRS.items():
        environment[name] = str(
            _ensure_private_subdirectory(scratch_root, relative_path)
        )
    environment.update(credentials)
    _assert_no_undeclared_provider_names(
        environment,
        set(_RESERVED_RUNTIME_ENV_VARS) | set(credentials) | extra,
    )
    return environment


def expected_child_environment_names(
    *,
    parent_env: Mapping[str, str],
    projected_names: Sequence[str] = (),
    extra_allowlist: Sequence[str] = (),
) -> frozenset[str]:
    """Return the exact child env names the builder is allowed to emit."""

    names = set(_MANAGED_RUNTIME_ENV_DIRS)
    names.update(name for name in _PASSTHROUGH_RUNTIME_ENV_VARS if parent_env.get(name))
    names.update(projected_names)
    names.update(extra_allowlist)
    return frozenset(names)


def _validated_extra_allowlist(extra_allowlist: Sequence[str]) -> frozenset[str]:
    names = validate_env_var_names(extra_allowlist, "extra_allowlist")
    reserved = sorted(set(names).intersection(_RESERVED_RUNTIME_ENV_VARS))
    if reserved:
        formatted = ", ".join(reserved)
        raise AuthProfileError(
            f"extra allowlist contains host-managed runtime variables: {formatted}"
        )
    return frozenset(names)


def ensure_private_scratch_directory(path: Path) -> Path:
    """Create ``path`` as a private directory and refuse symlinks."""

    _ensure_private_directory(path)
    return path


def identity_probe_environment(
    scratch_root: Path,
    parent_env: Mapping[str, str],
) -> dict[str, str]:
    """Return a credential-free isolated env for version/capability probes."""

    ensure_private_scratch_directory(scratch_root)
    environment: dict[str, str] = {}
    for name in _PASSTHROUGH_RUNTIME_ENV_VARS:
        value = parent_env.get(name)
        if value:
            environment[name] = value
    environment.setdefault("PATH", "/usr/bin")
    environment.setdefault("LC_CTYPE", "C.UTF-8")
    for name, relative_path in _MANAGED_RUNTIME_ENV_DIRS.items():
        environment[name] = str(
            _ensure_private_subdirectory(scratch_root, relative_path)
        )
    return environment


def _wrapper_launch_environment(parent: Mapping[str, str]) -> dict[str, str]:
    environment = {
        name: parent[name] for name in _WRAPPER_LAUNCH_ENV_VARS if parent.get(name)
    }
    environment.setdefault("TERM", "dumb")
    return environment


def _reject_bare_infisical_or_op(argv: Sequence[str]) -> None:
    if not argv:
        raise AuthProfileError("declared auth profile credentials are unavailable")
    executable = Path(argv[0]).name
    if executable in {"infisical", "op"}:
        raise AuthProfileError("credential fetch must use infisical-agent-sandbox")
    if executable != _INFISICAL_WRAPPER_NAME:
        raise AuthProfileError("credential fetch must use infisical-agent-sandbox")


def _reject_ambient_fallback(
    projected: Mapping[str, str],
    parent: Mapping[str, str],
) -> None:
    for name, value in projected.items():
        ambient = parent.get(name)
        if ambient and _fingerprint(ambient) == _fingerprint(value):
            raise AuthProfileError(
                "declared auth profile cannot fall back to host environment credentials"
            )


def _assert_no_undeclared_provider_names(
    environment: Mapping[str, str],
    allowed: set[str],
) -> None:
    unexpected = sorted(name for name in environment if name not in allowed)
    if unexpected:
        raise AuthProfileError("child environment contains names outside the allowlist")


def _ensure_private_directory(path: Path) -> None:
    parent = path.parent
    if parent != path and not parent.exists():
        _ensure_private_directory(parent)
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        # Lost the create race; the nofollow open below is the authority.
        pass
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise AuthProfileError("CLI scratch paths require O_NOFOLLOW")
    flags = os.O_RDONLY | nofollow
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AuthProfileError("CLI scratch paths must not be symlinks") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise AuthProfileError("CLI scratch paths must be directories")
        os.fchmod(descriptor, 0o700)
    finally:
        os.close(descriptor)


def _ensure_private_subdirectory(root: Path, relative_path: str) -> Path:
    directory = root
    for part in Path(relative_path).parts:
        if part in {"", ".", ".."}:
            raise AuthProfileError("CLI scratch paths must be relative")
        directory /= part
        _ensure_private_directory(directory)
    return directory


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
