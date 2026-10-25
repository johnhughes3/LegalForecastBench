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
            (config / ".claude.json.lock").mkdir(exist_ok=True)
            if len(calls) == 1:
                _claude_runtime_bookkeeping(config)
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
    (config / ".claude.json.lock").mkdir(exist_ok=True)
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


def test_claude_vendor_lock_must_be_empty_directory(tmp_path: Path) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    lock = config / ".claude.json.lock"
    lock.mkdir()
    (lock / "history.jsonl").write_text("history")
    with pytest.raises(AuthProfileError, match="empty non-symlink directory"):
        validate_auth_only_config_root("claude", config, role="solver")


def test_codex_accepts_only_native_login_log_and_empty_arg0_directory(
    tmp_path: Path,
) -> None:
    config = _auth_root(tmp_path, "codex-role", "auth.json")
    log = config / "log"
    log.mkdir(mode=0o775)
    (log / "codex-login.log").write_text("synthetic")
    (log / "codex-login.log").chmod(0o600)
    (config / "tmp" / "arg0-linux").mkdir(mode=0o700, parents=True)
    assert validate_auth_only_config_root("codex", config, role="solver") == config
    (config / "tmp" / "arg0-linux" / "history.jsonl").touch()
    with pytest.raises(AuthProfileError, match="empty"):
        validate_auth_only_config_root("codex", config, role="solver")


@pytest.mark.parametrize("entry", ["config.toml", "history.jsonl", "plugins"])
def test_codex_vendor_allowance_does_not_admit_user_configuration(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "codex-role", "auth.json")
    (config / entry).touch()
    with pytest.raises(AuthProfileError, match="only its vendor auth file"):
        validate_auth_only_config_root("codex", config, role="solver")


@pytest.mark.parametrize(
    "entry", ["log", "log/codex-login.log", "tmp", "tmp/arg0-linux"]
)
def test_codex_vendor_state_cannot_link_outside_role_root(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "codex-role", "auth.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = config / entry
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(AuthProfileError, match="symlink"):
        validate_auth_only_config_root("codex", config, role="solver")


_UUID_A = "11111111-1111-4111-8111-111111111111"
_UUID_B = "22222222-2222-4222-8222-222222222222"


def _claude_runtime_bookkeeping(config: Path) -> None:
    cleanup = config / ".last-cleanup"
    cleanup.write_text("synthetic")
    cleanup.chmod(0o664)
    (config / "sessions").mkdir(mode=0o700)
    telemetry = config / "telemetry"
    telemetry.mkdir(mode=0o775)
    (telemetry / f"1p_failed_events.{_UUID_A}.{_UUID_B}.json").write_text("{}")
    catalog = config / "cache" / "model-catalog"
    catalog.mkdir(mode=0o775, parents=True)
    (catalog / f"{_UUID_A}-{_UUID_B}-cc.json").write_text("{}")


def test_claude_runtime_bookkeeping_allows_repeat_metadata_validation(
    tmp_path: Path,
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    validate_auth_only_config_root("claude", config, role="solver")
    _claude_runtime_bookkeeping(config)
    for _attempt in range(2):
        assert validate_auth_only_config_root("claude", config, role="solver") == config


@pytest.mark.parametrize(
    "entry",
    [
        "settings.json",
        "history.jsonl",
        "plugins",
        "telemetry/history.jsonl",
        "cache/settings.json",
        "cache/model-catalog/settings.json",
        "sessions/history.jsonl",
    ],
)
def test_claude_runtime_bookkeeping_rejects_configuration_or_history(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    _claude_runtime_bookkeeping(config)
    (config / entry).touch()
    with pytest.raises(AuthProfileError):
        validate_auth_only_config_root("claude", config, role="solver")


@pytest.mark.parametrize(
    "entry",
    [
        ".last-cleanup",
        "sessions",
        "telemetry",
        "cache",
        "cache/model-catalog",
        f"telemetry/1p_failed_events.{_UUID_A}.{_UUID_B}.json",
        f"cache/model-catalog/{_UUID_A}-{_UUID_B}-cc.json",
    ],
)
def test_claude_runtime_bookkeeping_cannot_link_outside_role_root(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    target = config / entry
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(tmp_path / "outside")
    with pytest.raises(AuthProfileError):
        validate_auth_only_config_root("claude", config, role="solver")


@pytest.mark.parametrize(
    "entry", ["sessions", "telemetry", "cache", "cache/model-catalog"]
)
def test_claude_runtime_metadata_directory_cannot_be_a_file(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    target = config / entry
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("synthetic")
    with pytest.raises(AuthProfileError, match="non-symlink directory"):
        validate_auth_only_config_root("claude", config, role="solver")


@pytest.mark.parametrize(
    "entry",
    [
        ".last-cleanup",
        f"telemetry/1p_failed_events.{_UUID_A}.{_UUID_B}.json",
        f"cache/model-catalog/{_UUID_A}-{_UUID_B}-cc.json",
    ],
)
def test_claude_runtime_metadata_file_cannot_hide_a_directory(
    tmp_path: Path, entry: str
) -> None:
    config = _auth_root(tmp_path, "role", ".credentials.json")
    target = config / entry
    target.mkdir(parents=True)
    (target / "history.jsonl").write_text("synthetic")
    with pytest.raises(AuthProfileError, match="regular"):
        validate_auth_only_config_root("claude", config, role="solver")
