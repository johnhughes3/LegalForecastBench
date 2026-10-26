from __future__ import annotations

import json
import os
import stat
import tomllib
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.claude_code import (
    ClaudeCodeCliAdapterError,
    build_claude_invocation_plan,
)
from legalforecast.multiharness.codex_cli import (
    CODEX_SANDBOX_MODE,
    CodexCliAdapterError,
    plan_contained_codex_exec,
)
from legalforecast.multiharness.community_subscription_sandbox import (
    CODEX_COMMUNITY_PERMISSION_PROFILE,
    _prepare_codex_daemon_runtime_directory,
    claude_plan,
    codex_plan,
)
from legalforecast.multiharness.local_cli_identity import (
    ExecutableIdentityPin,
    executable_pin_for,
)


def test_claude_policy_denies_auth_root_to_bash_and_builtin_file_tools(
    tmp_path: Path,
) -> None:
    auth_root, workspace = _roots(tmp_path)
    plan = build_claude_invocation_plan(
        prompt="Create the requested deliverable.",
        model="sonnet",
        required_unit_ids=(),
        workspace=workspace,
        output_schema_path=workspace / "schema.json",
        allowed_tools=("Read", "Bash", "Write", "Edit"),
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )

    configured = claude_plan(plan, auth_root=auth_root)

    settings = json.loads(configured.argv[configured.argv.index("--settings") + 1])
    assert settings["sandbox"] == {
        "allowUnsandboxedCommands": False,
        "enabled": True,
        "excludedCommands": [],
        "failIfUnavailable": True,
        "filesystem": {
            "denyRead": [str(auth_root)],
            "denyWrite": [str(auth_root)],
        },
    }
    absolute_rule = f"//{auth_root.as_posix().lstrip('/')}"
    assert settings["permissions"]["deny"] == [
        f"Read({absolute_rule})",
        f"Read({absolute_rule}/**)",
        f"Edit({absolute_rule})",
        f"Edit({absolute_rule}/**)",
    ]
    assert configured.argv.count("--settings") == 1
    assert "--safe-mode" in configured.argv


@pytest.mark.parametrize(
    "auth_dirname",
    ["auth[1]", "auth*", "auth?", "auth\\root", "auth(rule)", "auth!", "auth#"],
)
def test_claude_policy_rejects_literal_auth_roots_with_pattern_syntax(
    tmp_path: Path,
    auth_dirname: str,
) -> None:
    auth_root = tmp_path / auth_dirname
    workspace = tmp_path / "workspace"
    auth_root.mkdir()
    workspace.mkdir()
    plan = build_claude_invocation_plan(
        prompt="Create the requested deliverable.",
        model="sonnet",
        required_unit_ids=(),
        workspace=workspace,
        output_schema_path=workspace / "schema.json",
        allowed_tools=("Read", "Bash", "Write", "Edit"),
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )

    with pytest.raises(ClaudeCodeCliAdapterError, match="permission pattern syntax"):
        claude_plan(plan, auth_root=auth_root)

    assert "--settings" not in plan.argv


def test_codex_policy_is_named_and_toml_parseable(tmp_path: Path) -> None:
    auth_root, workspace = _roots(tmp_path)
    executable, executable_pin, search_path = _codex_executable(tmp_path)
    plan = plan_contained_codex_exec(
        prompt="Create the requested deliverable.",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )

    configured = codex_plan(
        plan,
        auth_root=auth_root,
        executable_pin=executable_pin,
        search_path=search_path,
    )

    assert "--sandbox" not in configured.argv
    assert "danger-full-access" not in configured.argv
    overrides = [
        configured.argv[index + 1]
        for index, value in enumerate(configured.argv)
        if value == "-c"
    ]
    parsed = tomllib.loads("\n".join(overrides))
    assert parsed["default_permissions"] == CODEX_COMMUNITY_PERMISSION_PROFILE
    filesystem = parsed["permissions"][CODEX_COMMUNITY_PERMISSION_PROFILE]["filesystem"]
    assert filesystem == {
        ":minimal": "read",
        ":workspace_roots": {".": "write"},
        str(executable): "read",
        str(auth_root): "deny",
    }
    assert str(executable.parent) not in filesystem
    assert configured.sandbox_identity == (
        f"permissions:{CODEX_COMMUNITY_PERMISSION_PROFILE}"
    )


def test_codex_daemon_runtime_directory_is_created_private(tmp_path: Path) -> None:
    runtime = _prepare_codex_daemon_runtime_directory(tmp_path, uid=os.getuid())

    metadata = runtime.stat(follow_symlinks=False)
    assert runtime == tmp_path / f"codex-daemon-{os.getuid()}"
    assert stat.S_ISDIR(metadata.st_mode)
    assert metadata.st_uid == os.getuid()
    assert stat.S_IMODE(metadata.st_mode) == 0o700


def test_codex_daemon_runtime_directory_accepts_valid_existing_directory(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / f"codex-daemon-{os.getuid()}"
    runtime.mkdir(mode=0o700)

    assert _prepare_codex_daemon_runtime_directory(tmp_path, uid=os.getuid()) == runtime


def test_codex_daemon_runtime_directory_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    runtime = tmp_path / f"codex-daemon-{os.getuid()}"
    runtime.symlink_to(target, target_is_directory=True)

    with pytest.raises(CodexCliAdapterError, match="must be a real"):
        _prepare_codex_daemon_runtime_directory(tmp_path, uid=os.getuid())


def test_codex_daemon_runtime_directory_rejects_wrong_owner(tmp_path: Path) -> None:
    other_uid = os.getuid() + 1
    runtime = tmp_path / f"codex-daemon-{other_uid}"
    runtime.mkdir(mode=0o700)

    with pytest.raises(CodexCliAdapterError, match="owned by the current UID"):
        _prepare_codex_daemon_runtime_directory(tmp_path, uid=other_uid)


def test_codex_daemon_runtime_directory_rejects_wrong_mode(tmp_path: Path) -> None:
    runtime = tmp_path / f"codex-daemon-{os.getuid()}"
    runtime.mkdir(mode=0o500)

    with pytest.raises(CodexCliAdapterError, match="mode 0700"):
        _prepare_codex_daemon_runtime_directory(tmp_path, uid=os.getuid())


def test_vendor_policy_requires_subscription_and_disjoint_absolute_roots(
    tmp_path: Path,
) -> None:
    auth_root, workspace = _roots(tmp_path)
    official = build_claude_invocation_plan(
        prompt="prompt",
        model="sonnet",
        required_unit_ids=(),
        workspace=workspace,
        output_schema_path=workspace / "schema.json",
        allowed_tools=("Read",),
        auth_profile=PUBLISHED_API_KEY,
    )
    with pytest.raises(ClaudeCodeCliAdapterError, match="contributor subscription"):
        claude_plan(official, auth_root=auth_root)

    codex = plan_contained_codex_exec(
        prompt="prompt",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    nested_auth = workspace / "auth"
    nested_auth.mkdir()
    _executable, executable_pin, search_path = _codex_executable(tmp_path)
    with pytest.raises(CodexCliAdapterError, match="must be disjoint"):
        codex_plan(
            codex,
            auth_root=nested_auth,
            executable_pin=executable_pin,
            search_path=search_path,
        )


def test_codex_policy_grants_resolved_pin_target_not_alias_or_siblings(
    tmp_path: Path,
) -> None:
    auth_root, workspace = _roots(tmp_path)
    executable, executable_pin, search_path = _codex_executable(
        tmp_path, through_symlink=True
    )
    alias = Path(search_path) / "codex"
    sibling = executable.with_name("unselected")
    sibling.write_text("not selected", encoding="utf-8")
    plan = plan_contained_codex_exec(
        prompt="prompt",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )

    configured = codex_plan(
        plan,
        auth_root=auth_root,
        executable_pin=executable_pin,
        search_path=search_path,
    )

    overrides = [
        configured.argv[index + 1]
        for index, value in enumerate(configured.argv)
        if value == "-c"
    ]
    filesystem = tomllib.loads("\n".join(overrides))["permissions"][
        CODEX_COMMUNITY_PERMISSION_PROFILE
    ]["filesystem"]
    assert filesystem[str(executable)] == "read"
    assert str(alias) not in filesystem
    assert str(executable.parent) not in filesystem
    assert str(sibling) not in filesystem


def test_codex_policy_rejects_digest_drift_and_auth_root_executable(
    tmp_path: Path,
) -> None:
    auth_root, workspace = _roots(tmp_path)
    executable, executable_pin, search_path = _codex_executable(tmp_path)
    plan = plan_contained_codex_exec(
        prompt="prompt",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )
    executable.write_text("drifted", encoding="utf-8")
    with pytest.raises(CodexCliAdapterError, match="identity could not be verified"):
        codex_plan(
            plan,
            auth_root=auth_root,
            executable_pin=executable_pin,
            search_path=search_path,
        )

    auth_executable = auth_root / "codex"
    auth_executable.write_text("auth-owned", encoding="utf-8")
    auth_executable.chmod(0o700)
    auth_pin = executable_pin_for(auth_executable, version="0.164.0")
    with pytest.raises(CodexCliAdapterError, match="outside the Codex auth root"):
        codex_plan(
            plan,
            auth_root=auth_root,
            executable_pin=auth_pin,
            search_path=str(auth_root),
        )


def test_official_plans_retain_existing_sandbox_configuration(
    tmp_path: Path,
) -> None:
    _auth_root, workspace = _roots(tmp_path)
    claude = build_claude_invocation_plan(
        prompt="prompt",
        model="sonnet",
        required_unit_ids=(),
        workspace=workspace,
        output_schema_path=workspace / "schema.json",
        allowed_tools=("Read",),
        auth_profile=PUBLISHED_API_KEY,
    )
    codex = plan_contained_codex_exec(
        prompt="prompt",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
    )

    assert "--settings" not in claude.argv
    sandbox_index = codex.argv.index("--sandbox")
    assert codex.argv[sandbox_index + 1] == CODEX_SANDBOX_MODE
    assert codex.sandbox_identity == CODEX_SANDBOX_MODE


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    auth_root = tmp_path / "auth"
    workspace = tmp_path / "workspace"
    auth_root.mkdir(mode=0o700)
    workspace.mkdir()
    return auth_root.resolve(), workspace.resolve()


def _codex_executable(
    tmp_path: Path, *, through_symlink: bool = False
) -> tuple[Path, ExecutableIdentityPin, str]:
    release = tmp_path / "native-release" / "codex"
    release.parent.mkdir(exist_ok=True)
    release.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    release.chmod(0o700)
    search_root = release.parent
    if through_symlink:
        search_root = tmp_path / "selected-bin"
        search_root.mkdir()
        (search_root / "codex").symlink_to(release)
    pin = executable_pin_for(release, version="0.164.0")
    return release.resolve(), pin, str(search_root)
