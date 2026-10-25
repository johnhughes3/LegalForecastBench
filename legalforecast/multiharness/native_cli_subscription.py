"""Vendor-supported, role-isolated subscription access for native CLIs."""

from __future__ import annotations

import json
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

from legalforecast.multiharness.auth_profiles import (
    AuthProfileError,
    SubscriptionRuntimeAccess,
)
from legalforecast.multiharness.contributor_boundary import (
    ContributorBoundaryError,
    wrap_argv_for_contributor_boundary,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    LocalCliIdentityError,
    verify_executable_digest,
)

_STATUS_TIMEOUT_SECONDS: Final = 10.0
_STATUS_OUTPUT_LIMIT: Final = 65_536
_AUTH_FILES: Final[Mapping[str, frozenset[str]]] = {
    "claude": frozenset({".credentials.json"}),
    "codex": frozenset({"auth.json"}),
}


class NativeCliSubscriptionPresence:
    """Verify one explicitly prepared, auth-only native CLI config directory."""

    def __init__(
        self,
        executable: str,
        *,
        config_root: Path,
        role: str,
        timeout_seconds: float = _STATUS_TIMEOUT_SECONDS,
        executable_pin: ExecutableIdentityPin | None = None,
    ) -> None:
        if executable not in _AUTH_FILES:
            raise AuthProfileError("subscription presence supports claude or codex")
        if role not in {"solver", "judge"}:
            raise AuthProfileError("subscription role must be solver or judge")
        if timeout_seconds <= 0:
            raise AuthProfileError("subscription status timeout must be positive")
        self._executable = executable
        self._config_root = config_root.expanduser()
        self._role = role
        self._timeout_seconds = timeout_seconds
        self._executable_pin = executable_pin if executable == "codex" else None

    def prove(self, parent_env: Mapping[str, str]) -> SubscriptionRuntimeAccess:
        """Return role-local runtime access after contained vendor status."""

        config_root = validate_auth_only_config_root(
            self._executable,
            self._config_root,
            role=self._role,
            codex_pin=self._executable_pin,
            codex_search_path=parent_env.get("PATH", "/usr/bin"),
        )
        executable = shutil.which(
            self._executable, path=parent_env.get("PATH", "/usr/bin")
        )
        if executable is None:
            raise AuthProfileError(
                f"{self._executable} subscription CLI is not available on PATH"
            )
        config_name = (
            "CLAUDE_CONFIG_DIR" if self._executable == "claude" else "CODEX_HOME"
        )
        argv = (
            (executable, "auth", "status", "--json")
            if self._executable == "claude"
            else (executable, "login", "status")
        )
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"lfb-{self._role}-subscription-status-"
            ) as temporary:
                scratch = Path(temporary).resolve()
                home = scratch / "home"
                home.mkdir(mode=0o700)
                wrapped, _identity = wrap_argv_for_contributor_boundary(
                    argv,
                    scratch_root=scratch,
                    extra_read_paths=(config_root,),
                    extra_write_paths=(config_root,),
                )
                completed = subprocess.run(
                    wrapped,
                    cwd=scratch,
                    env={
                        "HOME": str(home),
                        "PATH": parent_env.get("PATH", "/usr/bin"),
                        config_name: str(config_root),
                    },
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    check=False,
                    timeout=self._timeout_seconds,
                )
        except (ContributorBoundaryError, OSError, subprocess.TimeoutExpired) as exc:
            raise AuthProfileError(
                f"{self._executable} {self._role} subscription status "
                "could not be verified"
            ) from exc
        if (
            completed.returncode != 0
            or len(completed.stdout) > _STATUS_OUTPUT_LIMIT
            or len(completed.stderr) > _STATUS_OUTPUT_LIMIT
        ):
            raise AuthProfileError(
                f"{self._executable} {self._role} subscription login is absent; "
                "run the documented role-specific vendor login command"
            )
        if self._executable == "claude":
            self._verify_claude_status(completed.stdout)
        else:
            self._verify_codex_status(completed.stdout, completed.stderr)
        validate_auth_only_config_root(
            self._executable,
            config_root,
            role=self._role,
            codex_pin=self._executable_pin,
            codex_search_path=parent_env.get("PATH", "/usr/bin"),
        )
        return SubscriptionRuntimeAccess(
            environment=((config_name, str(config_root)),),
            read_paths=(config_root,),
            write_paths=(config_root,),
        )

    @staticmethod
    def _verify_claude_status(stdout: bytes) -> None:
        try:
            decoded = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthProfileError("claude auth status returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise AuthProfileError("claude auth status returned invalid JSON")
        status = cast(dict[str, object], decoded)
        subscription = status.get("subscriptionType")
        if (
            status.get("loggedIn") is not True
            or status.get("authMethod") != "claude.ai"
            or not isinstance(subscription, str)
            or not subscription.strip()
        ):
            raise AuthProfileError(
                "claude is not logged in through a Claude subscription"
            )

    @staticmethod
    def _verify_codex_status(stdout: bytes, stderr: bytes) -> None:
        text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
        lines = {line.strip() for line in text.splitlines() if line.strip()}
        if "Logged in using ChatGPT" not in lines:
            raise AuthProfileError("codex is not logged in through ChatGPT")


def validate_auth_only_config_root(
    executable: str,
    config_root: Path,
    *,
    role: str,
    codex_pin: ExecutableIdentityPin | None = None,
    codex_search_path: str = "/usr/bin",
) -> Path:
    """Validate an auth-only role root without opening its credential file."""

    candidate = config_root.expanduser()
    if not candidate.is_absolute() or candidate.is_symlink():
        raise AuthProfileError(
            f"{executable} {role} config must be an absolute non-symlink path"
        )
    root = candidate.resolve()
    if not root.is_dir():
        raise AuthProfileError(f"{executable} {role} config must be a real directory")
    try:
        root_mode = stat.S_IMODE(root.stat(follow_symlinks=False).st_mode)
        entries = tuple(root.iterdir())
    except OSError as exc:
        raise AuthProfileError(
            f"{executable} {role} config could not be inspected"
        ) from exc
    if root_mode & 0o077:
        raise AuthProfileError(f"{executable} {role} config must be owner-only")
    allowed = _AUTH_FILES.get(executable)
    if allowed is None:
        raise AuthProfileError("subscription presence supports claude or codex")
    names = {entry.name for entry in entries}
    state_names: set[str] = (
        {".claude.json", ".claude.json.lock", "backups"}
        if executable == "claude"
        else {"log", "tmp"}
    )
    if not set(allowed).issubset(names) or names - set(allowed) - state_names:
        raise AuthProfileError(
            f"{executable} {role} config must contain only its vendor auth file"
        )
    for entry in entries:
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise AuthProfileError(
                f"{executable} {role} auth metadata could not be inspected"
            ) from exc
        if executable == "codex" and entry.name in {"log", "tmp"}:
            _validate_codex_login_state(entry, codex_pin, codex_search_path)
            continue
        if entry.name == ".claude.json.lock" and executable == "claude":
            if (
                entry.is_symlink()
                or not stat.S_ISDIR(metadata.st_mode)
                or any(entry.iterdir())
            ):
                raise AuthProfileError(
                    "Claude vendor lock must be an empty non-symlink directory"
                )
            continue
        if entry.name == "backups" and executable == "claude":
            _validate_claude_backups(entry)
            continue
        if not stat.S_ISREG(metadata.st_mode) or entry.is_symlink():
            raise AuthProfileError(
                f"{executable} {role} auth entry must be a regular file"
            )
        if entry.name in allowed and stat.S_IMODE(metadata.st_mode) & 0o077:
            raise AuthProfileError(f"{executable} {role} auth file must be owner-only")
    return root


def _validate_codex_login_state(
    directory: Path, pin: ExecutableIdentityPin | None, search_path: str
) -> None:
    """Allow native login logs and pinned arg0 aliases made by native status.

    The owner-only role root protects the vendor's group-readable directories.
    No user configuration or arbitrary temporary contents are accepted.
    """

    if directory.is_symlink() or not directory.is_dir():
        raise AuthProfileError("Codex vendor state must be a non-symlink directory")
    allowed = "codex-login.log" if directory.name == "log" else "arg0-linux"
    for entry in directory.iterdir():
        if entry.name != allowed:
            raise AuthProfileError("Codex login state must contain only vendor state")
        metadata = entry.stat(follow_symlinks=False)
        if entry.is_symlink():
            raise AuthProfileError("Codex login state must not contain symlinks")
        if directory.name == "log":
            if not stat.S_ISREG(metadata.st_mode):
                raise AuthProfileError("Codex login log must be a regular file")
        else:
            _validate_codex_arg0(entry, pin, search_path)


_CODEX_HELPERS = frozenset({"applypatch", "apply_patch", "codex-linux-sandbox"})


def _validate_codex_arg0(
    directory: Path, pin: ExecutableIdentityPin | None, search_path: str
) -> None:
    """Permit native aliases only to the selected, digest-verified Codex bytes."""

    if directory.is_symlink() or not directory.is_dir():
        raise AuthProfileError("Codex arg0 state must be a non-symlink directory")
    children = tuple(directory.iterdir())
    if not children:
        return
    if pin is None or pin.basename != "codex":
        raise AuthProfileError("nonempty Codex arg0 state requires a pinned executable")
    try:
        identity = verify_executable_digest(pin, ("codex",), search_path=search_path)
        executable = Path(identity.resolved_argv[0]).resolve(strict=True)
    except (LocalCliIdentityError, OSError) as exc:
        raise AuthProfileError(
            "Codex helper executable identity could not be verified"
        ) from exc
    for child in children:
        if (
            child.is_symlink()
            or not child.is_dir()
            or re.fullmatch(r"codex-arg0[A-Za-z0-9]{6}", child.name) is None
        ):
            raise AuthProfileError(
                "Codex arg0 must contain only native helper directories"
            )
        entries = tuple(child.iterdir())
        if {entry.name for entry in entries} != {".lock", *_CODEX_HELPERS}:
            raise AuthProfileError("Codex helper directory contains unexpected entries")
        for entry in entries:
            if entry.name == ".lock":
                if entry.is_symlink() or not stat.S_ISREG(
                    entry.stat(follow_symlinks=False).st_mode
                ):
                    raise AuthProfileError("Codex helper lock must be a regular file")
            elif not entry.is_symlink() or entry.readlink() != executable:
                raise AuthProfileError(
                    "Codex helper must link directly to the pinned executable"
                )


def _validate_claude_backups(directory: Path) -> None:
    """Allow only the regular state backups created by native auth status.

    Claude writes these even when no account is logged in. The owner-only
    parent protects state files; credentials still require owner-only mode.
    Safe mode and strict MCP suppress customizations during model execution.
    """

    if directory.is_symlink() or not directory.is_dir():
        raise AuthProfileError("Claude vendor backups must be a non-symlink directory")
    for entry in directory.iterdir():
        if re.fullmatch(r"\.claude\.json\.backup\.[0-9]+", entry.name) is None:
            raise AuthProfileError("Claude backups must contain only vendor state")
        if entry.is_symlink() or not stat.S_ISREG(
            entry.stat(follow_symlinks=False).st_mode
        ):
            raise AuthProfileError(
                "Claude vendor backup must be a regular non-symlink file"
            )


def validate_role_config_separation(
    solver_root: Path,
    judge_root: Path,
    *,
    forbidden_paths: Sequence[Path],
    solver_executable: str = "claude",
    codex_pin: ExecutableIdentityPin | None = None,
    codex_search_path: str = "/usr/bin",
) -> tuple[Path, Path]:
    """Reject shared/nested role roots and overlap with benchmark paths."""

    solver = validate_auth_only_config_root(
        solver_executable,
        solver_root,
        role="solver",
        codex_pin=codex_pin,
        codex_search_path=codex_search_path,
    )
    judge = validate_auth_only_config_root("claude", judge_root, role="judge")
    if _paths_overlap(solver, judge):
        raise AuthProfileError("solver and judge config directories must be disjoint")
    for protected in forbidden_paths:
        resolved = protected.expanduser().resolve()
        if _paths_overlap(solver, resolved) or _paths_overlap(judge, resolved):
            raise AuthProfileError(
                "subscription config directories must not overlap benchmark paths"
            )
    return solver, judge


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


__all__ = [
    "NativeCliSubscriptionPresence",
    "validate_auth_only_config_root",
    "validate_role_config_separation",
]
