"""Prove a contributor's own local harness login by artifact presence only.

The ``contributor-subscription`` profile runs a harness CLI under the
contributor's *own* interactive login. Nothing here fetches, reads, copies,
hashes, or exports that login: the prover checks that the harness state
directory and its login artifact exist, are regular, are non-empty, and are
owned by the current user. It never calls ``open()`` on an artifact, not even
to validate JSON shape, and it never falls back to an API key in the
environment.

Every refusal raises :class:`~legalforecast.multiharness.auth_profiles.AuthProfileError`
with a message built only from the harness basename and its login hint. Host
paths are deliberately absent, and an underlying ``OSError`` is suppressed
with ``raise ... from None``, because a failed run's message is redacted into
a public receipt and an ``OSError`` string embeds the host path that produced
it.

Granting the child read *and* write to the contributor's real harness state
directory (see :meth:`LocalLoginPresence.boundary_write_paths`) is a
deliberate, community-class-only decision: these CLIs rewrite refresh tokens,
session state, and lock files in place, so a read-only grant turns into an
opaque mid-run failure. It is sound only because the contributor owns the
machine the login already lives on. Official runs cannot select this profile.

``child_env_overrides`` exists because the local-CLI runtime redirects ``HOME``
and the per-harness config-dir variables into a scratch tree; a subscription
run must point the child back at the one directory holding its login, and only
that directory is granted by the boundary paths.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from legalforecast.multiharness.auth_profiles import (
    AuthProfileError,
    refuse_noninteractive_environment,
)

_CONFIG_DIR_OPEN_FLAGS: Final = (
    os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC
)


@dataclass(frozen=True, slots=True)
class HarnessLoginDescriptor:
    """Where one harness CLI keeps the login state a run must not touch.

    ``credential_relative_paths`` are resolved against the config directory
    with a directory file descriptor, so each must stay relative and free of
    parent segments. ``login_hint`` is the only remediation text a refusal may
    quote, and ``extra_child_env`` carries per-harness settings a subscription
    run needs (autoupdaters and memory features that would otherwise write
    outside the granted directory).
    """

    executable_basename: str
    config_dir_env_var: str | None
    home_relative_config_dir: str
    credential_relative_paths: tuple[str, ...]
    login_hint: str
    extra_child_env: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Refuse a descriptor whose artifact paths cannot be checked safely."""

        if not self.credential_relative_paths:
            raise AuthProfileError(
                f"{self.executable_basename!r} declares no local-login artifact"
            )
        for relative in self.credential_relative_paths:
            path = Path(relative)
            if not relative or path.is_absolute() or ".." in path.parts:
                raise AuthProfileError(
                    f"{self.executable_basename!r} declares a local-login "
                    "artifact outside its own config directory"
                )


# Sourced from the 2026-08-31 live harness characterization. ``claude`` also
# writes ~/.claude.json, but that file sits in HOME rather than the config
# directory and does not move under CLAUDE_CONFIG_DIR, so .credentials.json is
# the one artifact this prover treats as the login. ``agy`` has no config-dir
# environment variable at all, which is why its child override is HOME.
_DESCRIPTORS: Final[tuple[HarnessLoginDescriptor, ...]] = (
    HarnessLoginDescriptor(
        executable_basename="claude",
        config_dir_env_var="CLAUDE_CONFIG_DIR",
        home_relative_config_dir=".claude",
        credential_relative_paths=(".credentials.json",),
        login_hint="run 'claude' and complete the interactive login",
    ),
    HarnessLoginDescriptor(
        executable_basename="codex",
        config_dir_env_var="CODEX_HOME",
        home_relative_config_dir=".codex",
        credential_relative_paths=("auth.json",),
        login_hint="run 'codex login'",
    ),
    HarnessLoginDescriptor(
        executable_basename="grok",
        config_dir_env_var="GROK_HOME",
        home_relative_config_dir=".grok",
        credential_relative_paths=("auth.json",),
        login_hint="run 'grok login'",
        extra_child_env=(("GROK_DISABLE_AUTOUPDATER", "1"), ("GROK_MEMORY", "0")),
    ),
    HarnessLoginDescriptor(
        executable_basename="kimi",
        config_dir_env_var="KIMI_CODE_HOME",
        home_relative_config_dir=".kimi-code",
        credential_relative_paths=("credentials/kimi-code.json",),
        login_hint="run 'kimi login'",
        extra_child_env=(("KIMI_CODE_NO_AUTO_UPDATE", "1"),),
    ),
    HarnessLoginDescriptor(
        executable_basename="agy",
        config_dir_env_var=None,
        home_relative_config_dir=".gemini",
        credential_relative_paths=("antigravity-cli/antigravity-oauth-token",),
        login_hint="run 'agy' and complete the interactive Antigravity login",
    ),
)

HARNESS_LOGIN_DESCRIPTORS: Final[Mapping[str, HarnessLoginDescriptor]] = (
    MappingProxyType(
        {descriptor.executable_basename: descriptor for descriptor in _DESCRIPTORS}
    )
)


def descriptor_for_executable(basename: str) -> HarnessLoginDescriptor:
    """Return one harness's login layout, or refuse an undeclared harness."""

    descriptor = HARNESS_LOGIN_DESCRIPTORS.get(basename)
    if descriptor is None:
        declared = ", ".join(sorted(HARNESS_LOGIN_DESCRIPTORS))
        raise AuthProfileError(
            f"contributor-subscription has no local-login layout for "
            f"{basename!r}; declared harnesses: {declared}"
        )
    return descriptor


@dataclass(frozen=True, slots=True)
class LocalLoginPresence:
    """Prove one harness's contributor login without reading its bytes."""

    descriptor: HarnessLoginDescriptor

    def prove(self, parent_env: Mapping[str, str]) -> None:
        """Accept the contributor's own login for this harness or fail closed."""

        refuse_noninteractive_environment(parent_env)
        config_dir = self.config_dir(parent_env)
        try:
            config_fd = os.open(config_dir, _CONFIG_DIR_OPEN_FLAGS)
        except OSError:
            # from None: an OSError message embeds the host path, and this
            # message reaches a public failed receipt.
            raise self._absent_error() from None
        try:
            self._require_owned_directory(config_fd)
            for relative in self.descriptor.credential_relative_paths:
                self._require_owned_nonempty_file(relative, config_fd)
        finally:
            os.close(config_fd)

    def config_dir(self, parent_env: Mapping[str, str]) -> Path:
        """Return the directory this harness keeps its login state in."""

        env_var = self.descriptor.config_dir_env_var
        if env_var is not None:
            override = str(parent_env.get(env_var, "")).strip()
            if override:
                return self._require_absolute(override, env_var)
        return self._home(parent_env) / self.descriptor.home_relative_config_dir

    def boundary_read_paths(self, parent_env: Mapping[str, str]) -> tuple[Path, ...]:
        """Return the paths the child must be able to read outside scratch."""

        return (self.config_dir(parent_env),)

    def boundary_write_paths(self, parent_env: Mapping[str, str]) -> tuple[Path, ...]:
        """Return the paths the child must be able to write outside scratch.

        Identical to the read grant on purpose: a harness refreshes its token
        and rewrites session and lock files inside this directory mid-run.
        """

        return (self.config_dir(parent_env),)

    def child_env_overrides(self, parent_env: Mapping[str, str]) -> Mapping[str, str]:
        """Return the environment the child needs to find its own login."""

        overrides: dict[str, str] = dict(self.descriptor.extra_child_env)
        env_var = self.descriptor.config_dir_env_var
        if env_var is None:
            overrides["HOME"] = str(self._home(parent_env))
        else:
            overrides[env_var] = str(self.config_dir(parent_env))
        return overrides

    def _home(self, parent_env: Mapping[str, str]) -> Path:
        home = str(parent_env.get("HOME", "")).strip()
        if not home:
            raise self._absent_error()
        return self._require_absolute(home, "HOME")

    def _require_absolute(self, value: str, env_var: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            raise AuthProfileError(
                f"contributor-subscription cannot locate the login for "
                f"{self.descriptor.executable_basename!r}: {env_var} must be an "
                "absolute path"
            )
        return path

    def _require_owned_directory(self, config_fd: int) -> None:
        try:
            info = os.fstat(config_fd)
        except OSError:
            raise self._absent_error() from None
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise self._absent_error()

    def _require_owned_nonempty_file(self, relative: str, config_fd: int) -> None:
        try:
            # lstat only. The artifact is never opened, read, hashed, or
            # copied, and a symlink fails S_ISREG rather than being followed.
            info = os.lstat(relative, dir_fd=config_fd)
        except OSError:
            raise self._absent_error() from None
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_size <= 0
        ):
            raise self._absent_error()

    def _absent_error(self) -> AuthProfileError:
        descriptor = self.descriptor
        return AuthProfileError(
            f"contributor-subscription local login is absent for "
            f"{descriptor.executable_basename!r}; {descriptor.login_hint} on "
            "this host. No fallback."
        )


def local_login_presence_for(basename: str) -> LocalLoginPresence:
    """Return the presence prover for one declared harness executable."""

    return LocalLoginPresence(descriptor=descriptor_for_executable(basename))
