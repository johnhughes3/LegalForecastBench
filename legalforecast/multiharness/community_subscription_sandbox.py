"""Vendor-native tool isolation for community subscription solvers."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path

from legalforecast.immutable_io import ImmutableIOError, ensure_private_directory
from legalforecast.multiharness.auth_profiles import CONTRIBUTOR_SUBSCRIPTION
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapterError,
    ClaudeInvocationPlan,
)
from legalforecast.multiharness.codex_cli import (
    CODEX_SANDBOX_MODE,
    CodexCliAdapterError,
    CodexCliInvocationPlan,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    LocalCliIdentityError,
    verify_executable_digest,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService

# Security ABI allowlist: new Claude versions require source review, not a semver floor.
CLAUDE_COMMUNITY_SANDBOX_POLICY_PROFILE = "claude_native_sandbox.v1"
CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION = "2.1.310 (Claude Code)"
CODEX_COMMUNITY_PERMISSION_PROFILE = "lfb_community_solver"
# Handwritten Read/Edit rules are not escaped by Claude; reject their pattern grammar.
_CLAUDE_PERMISSION_PATTERN_METACHARACTERS = frozenset("*?[]\\!#()")


def claude_plan(
    plan: ClaudeInvocationPlan,
    *,
    auth_root: Path,
) -> ClaudeInvocationPlan:
    """Deny the parent-owned auth root to Bash and built-in file tools."""

    if plan.auth_profile != CONTRIBUTOR_SUBSCRIPTION:
        raise ClaudeCodeCliAdapterError(
            "native tool sandbox configuration requires contributor subscription"
        )
    try:
        root = _absolute_directory(auth_root, label="Claude auth root")
    except ValueError as exc:
        raise ClaudeCodeCliAdapterError(str(exc)) from exc
    if _CLAUDE_PERMISSION_PATTERN_METACHARACTERS.intersection(root.as_posix()):
        raise ClaudeCodeCliAdapterError(
            "Claude auth root must not contain permission pattern syntax"
        )
    if "--settings" in plan.argv:
        raise ClaudeCodeCliAdapterError(
            "community Claude invocation must declare one owned settings object"
        )
    absolute_rule = f"//{root.as_posix().lstrip('/')}"
    settings: dict[str, object] = {
        "permissions": {
            "deny": [
                f"Read({absolute_rule})",
                f"Read({absolute_rule}/**)",
                f"Edit({absolute_rule})",
                f"Edit({absolute_rule}/**)",
            ]
        },
        "sandbox": {
            "allowUnsandboxedCommands": False,
            "enabled": True,
            "excludedCommands": [],
            "failIfUnavailable": True,
            "filesystem": {
                "denyRead": [str(root)],
                "denyWrite": [str(root)],
            },
        },
    }
    token = json.dumps(
        settings,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return replace(plan, argv=(*plan.argv, "--settings", token))


def codex_plan(
    plan: CodexCliInvocationPlan,
    *,
    auth_root: Path,
    executable_pin: ExecutableIdentityPin,
    search_path: str,
) -> CodexCliInvocationPlan:
    """Replace legacy sandbox mode with a named, auth-denying profile."""

    if plan.auth_profile != CONTRIBUTOR_SUBSCRIPTION:
        raise CodexCliAdapterError(
            "native tool sandbox configuration requires contributor subscription"
        )
    try:
        root = _absolute_directory(auth_root, label="Codex auth root")
        work = _absolute_directory(plan.working_directory, label="Codex role workspace")
    except ValueError as exc:
        raise CodexCliAdapterError(str(exc)) from exc
    if root == work or root.is_relative_to(work) or work.is_relative_to(root):
        raise CodexCliAdapterError(
            "Codex auth root and role workspace must be disjoint"
        )
    executable = _pinned_executable_file(
        plan,
        executable_pin=executable_pin,
        search_path=search_path,
    )
    if executable == root or executable.is_relative_to(root):
        raise CodexCliAdapterError(
            "community Codex executable must stay outside the Codex auth root"
        )
    argv = list(plan.argv)
    try:
        sandbox_index = argv.index("--sandbox")
    except ValueError as exc:
        raise CodexCliAdapterError(
            "community Codex invocation is missing its replaceable sandbox mode"
        ) from exc
    if (
        argv.count("--sandbox") != 1
        or sandbox_index + 1 >= len(argv)
        or argv[sandbox_index + 1] != CODEX_SANDBOX_MODE
    ):
        raise CodexCliAdapterError(
            "community Codex invocation must start from workspace-write"
        )
    del argv[sandbox_index : sandbox_index + 2]
    argv.extend(
        (
            "-c",
            f'default_permissions="{CODEX_COMMUNITY_PERMISSION_PROFILE}"',
            "-c",
            _codex_permissions_override(root, executable),
        )
    )
    if "danger-full-access" in argv:
        raise CodexCliAdapterError(
            "community Codex invocation must retain native filesystem permissions"
        )
    return replace(
        plan,
        argv=tuple(argv),
        sandbox_identity=f"permissions:{CODEX_COMMUNITY_PERMISSION_PROFILE}",
    )


def codex_daemon_runtime_directory() -> Path:
    """Prepare Codex's exact UID-scoped bubblewrap coordination directory."""

    return _prepare_codex_daemon_runtime_directory(Path("/tmp"), uid=os.getuid())


def _prepare_codex_daemon_runtime_directory(parent: Path, *, uid: int) -> Path:
    """Create or validate the owner-only directory required by Codex bwrap."""

    directory = parent / f"codex-daemon-{uid}"
    try:
        ensure_private_directory(directory)
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or directory_flag is None:
            raise OSError("safe directory admission requires O_NOFOLLOW")
        descriptor = os.open(
            directory,
            os.O_RDONLY | nofollow | directory_flag | getattr(os, "O_CLOEXEC", 0),
        )
    except (ImmutableIOError, OSError) as exc:
        raise CodexCliAdapterError(
            "Codex daemon runtime directory must be a real owner-only directory"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if metadata.st_uid != uid:
            raise CodexCliAdapterError(
                "Codex daemon runtime directory must be owned by the current UID"
            )
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise CodexCliAdapterError(
                "Codex daemon runtime directory must have mode 0700"
            )
    finally:
        os.close(descriptor)
    return directory


def codex_service_plan(
    plan: CodexCliInvocationPlan,
    auth_root: Path,
    service: LocalCliExecutionService,
    executable_pin: ExecutableIdentityPin | None = None,
) -> CodexCliInvocationPlan:
    """Apply the native policy using the exact pin selected for execution."""

    selected_pin = executable_pin or service.executable_pin
    if selected_pin is None:
        raise CodexCliAdapterError(
            "community Codex invocation requires an executable identity pin"
        )
    identity_env = service.parent_env or os.environ
    return codex_plan(
        plan,
        auth_root=auth_root,
        executable_pin=selected_pin,
        search_path=identity_env.get("PATH", "/usr/bin"),
    )


def _codex_permissions_override(auth_root: Path, executable: Path) -> str:
    quoted_root = json.dumps(str(auth_root), ensure_ascii=True)
    quoted_executable = json.dumps(str(executable), ensure_ascii=True)
    return (
        "permissions={"
        f"{CODEX_COMMUNITY_PERMISSION_PROFILE}="
        '{filesystem={":minimal"="read",'
        '":workspace_roots"={"."="write"},'
        f'{quoted_executable}="read",'
        f'{quoted_root}="deny"'
        "}}}"
    )


def _pinned_executable_file(
    plan: CodexCliInvocationPlan,
    *,
    executable_pin: ExecutableIdentityPin,
    search_path: str,
) -> Path:
    try:
        observed = verify_executable_digest(
            executable_pin,
            plan.argv,
            search_path=search_path,
        )
        selected_index = next(
            index
            for index, token in enumerate(plan.argv)
            if Path(token).name == executable_pin.basename
        )
        executable = Path(observed.resolved_argv[selected_index]).resolve(strict=True)
        if not executable.is_file() or executable.is_symlink():
            raise OSError("selected executable is not a regular file")
    except (LocalCliIdentityError, OSError, StopIteration) as exc:
        raise CodexCliAdapterError(
            "community Codex executable identity could not be verified"
        ) from exc
    return executable


def _absolute_directory(path: Path, *, label: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute() or candidate.is_symlink():
        raise ValueError(f"{label} must be an absolute non-symlink directory")
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise ValueError(f"{label} must be an existing directory")
    return resolved


__all__ = [
    "CLAUDE_COMMUNITY_SANDBOX_POLICY_PROFILE",
    "CLAUDE_COMMUNITY_SANDBOX_POLICY_VERSION",
    "CODEX_COMMUNITY_PERMISSION_PROFILE",
    "claude_plan",
    "codex_daemon_runtime_directory",
    "codex_plan",
    "codex_service_plan",
]
