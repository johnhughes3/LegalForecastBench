from __future__ import annotations

import json
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
    claude_plan,
    codex_plan,
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
    plan = plan_contained_codex_exec(
        prompt="Create the requested deliverable.",
        model="gpt-fixture",
        workspace=workspace,
        timeout_seconds=30,
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
    )

    configured = codex_plan(plan, auth_root=auth_root)

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
        str(auth_root): "deny",
    }
    assert configured.sandbox_identity == (
        f"permissions:{CODEX_COMMUNITY_PERMISSION_PROFILE}"
    )


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
    with pytest.raises(CodexCliAdapterError, match="must be disjoint"):
        codex_plan(codex, auth_root=nested_auth)


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
