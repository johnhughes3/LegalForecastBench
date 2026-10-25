"""Offline tests for role-isolated native subscription detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.native_cli_subscription import (
    NativeCliSubscriptionPresence,
    validate_auth_only_config_root,
    validate_role_config_separation,
)


def _auth_root(tmp_path: Path, name: str, filename: str) -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    auth = root / filename
    auth.write_bytes(b"synthetic-auth-not-read")
    auth.chmod(0o600)
    return root


@pytest.mark.parametrize(
    ("executable", "stdout", "stderr", "config_name", "auth_file"),
    [
        (
            "claude",
            b'{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}',
            b"",
            "CLAUDE_CONFIG_DIR",
            ".credentials.json",
        ),
        (
            "codex",
            b"",
            b"Logged in using ChatGPT\n",
            "CODEX_HOME",
            "auth.json",
        ),
    ],
)
def test_vendor_status_projects_only_explicit_role_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executable: str,
    stdout: bytes,
    stderr: bytes,
    config_name: str,
    auth_file: str,
) -> None:
    config = _auth_root(tmp_path, "role-auth", auth_file)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: f"/usr/bin/{executable}",
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.wrap_argv_for_contributor_boundary",
        lambda argv, **_kwargs: (argv, {}),
    )
    calls: list[dict[str, str]] = []

    def run_double(argv: tuple[str, ...], **kwargs: object):
        calls.append(dict(kwargs["env"]))  # type: ignore[arg-type]
        if executable == "claude":
            (config / ".claude.json").write_text("{}")
            (config / ".claude.json.lock").write_text("")
        return subprocess.CompletedProcess(argv, 0, stdout, stderr)

    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        run_double,
    )
    presence = NativeCliSubscriptionPresence(
        executable, config_root=config, role="solver"
    )
    access = presence.prove(
        {
            "HOME": str(tmp_path / "host-home"),
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "must-not-pass",
        }
    )

    assert access.environment == ((config_name, str(config.resolve())),)
    assert access.read_paths == access.write_paths == (config.resolve(),)
    assert calls[0][config_name] == str(config.resolve())
    assert calls[0]["HOME"] != str(tmp_path / "host-home")
    assert set(calls[0]) == {"HOME", "PATH", config_name}
    # Revalidate every use; a judge never inherits cached solver presence.
    presence.prove({"PATH": "/usr/bin"})
    assert len(calls) == 2


@pytest.mark.parametrize("extra", ["history.jsonl", "settings.json", "plugins"])
def test_auth_only_config_rejects_histories_settings_and_plugins(
    tmp_path: Path, extra: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    path = config / extra
    if extra == "plugins":
        path.mkdir()
    else:
        path.write_text("synthetic", encoding="utf-8")

    with pytest.raises(AuthProfileError, match="only its vendor auth file"):
        validate_auth_only_config_root("claude", config, role="solver")


def test_role_configs_must_be_disjoint_from_each_other_and_private_paths(
    tmp_path: Path,
) -> None:
    solver = _auth_root(tmp_path, "solver", ".credentials.json")
    judge = _auth_root(tmp_path, "judge", ".credentials.json")
    protected = tmp_path / "private"
    protected.mkdir()
    assert validate_role_config_separation(
        solver, judge, forbidden_paths=(protected,)
    ) == (solver.resolve(), judge.resolve())

    with pytest.raises(AuthProfileError, match="must be disjoint"):
        validate_role_config_separation(solver, solver, forbidden_paths=(protected,))
    with pytest.raises(AuthProfileError, match="benchmark paths"):
        validate_role_config_separation(solver, judge, forbidden_paths=(judge.parent,))


def test_auth_only_config_rejects_symlinked_root(tmp_path: Path) -> None:
    target = _auth_root(tmp_path, "target", ".credentials.json")
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)

    with pytest.raises(AuthProfileError, match="absolute non-symlink"):
        validate_auth_only_config_root("claude", linked, role="solver")


def test_claude_status_rejects_non_subscription_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: "/usr/bin/claude",
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.wrap_argv_for_contributor_boundary",
        lambda argv, **_kwargs: (argv, {}),
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            b'{"loggedIn":true,"authMethod":"apiKey","subscriptionType":null}',
            b"",
        ),
    )

    with pytest.raises(AuthProfileError, match=r"not logged in.*subscription"):
        NativeCliSubscriptionPresence("claude", config_root=config, role="judge").prove(
            {"PATH": "/usr/bin"}
        )


def test_claude_accepts_vendor_status_state_but_not_history(tmp_path: Path) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    (config / ".claude.json").write_text("{}")
    (config / ".claude.json.lock").write_text("")
    backups = config / "backups"
    backups.mkdir()
    (backups / ".claude.json.backup.1792894746105").write_text("{}")
    assert validate_auth_only_config_root("claude", config, role="solver") == config
    (backups / "history.jsonl").write_text("history")
    with pytest.raises(AuthProfileError, match="vendor"):
        validate_auth_only_config_root("claude", config, role="solver")


@pytest.mark.parametrize("linked_entry", [".claude.json", "backups"])
def test_vendor_state_cannot_link_outside_role_root(
    tmp_path: Path, linked_entry: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    (config / linked_entry).symlink_to(outside, target_is_directory=True)
    with pytest.raises(AuthProfileError, match=r"regular|symlink"):
        validate_auth_only_config_root("claude", config, role="solver")


def test_claude_backup_symlinks_are_rejected(tmp_path: Path) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    backups = config / "backups"
    backups.mkdir()
    target = tmp_path / "outside"
    target.write_text("not-readable")
    (backups / ".claude.json.backup.1792894746105").symlink_to(target)
    with pytest.raises(AuthProfileError, match=r"regular|symlink"):
        validate_auth_only_config_root("claude", config, role="solver")
