"""Offline tests for vendor-native contributor subscription detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.native_cli_subscription import (
    NativeCliSubscriptionPresence,
)


@pytest.mark.parametrize(
    ("executable", "stdout", "stderr", "config_name", "config_dir"),
    [
        (
            "claude",
            b'{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}',
            b"",
            "CLAUDE_CONFIG_DIR",
            ".claude",
        ),
        (
            "codex",
            b"",
            b"Logged in using ChatGPT\n",
            "CODEX_HOME",
            ".codex",
        ),
    ],
)
def test_vendor_status_projects_only_the_exact_config_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executable: str,
    stdout: bytes,
    stderr: bytes,
    config_name: str,
    config_dir: str,
) -> None:
    home = tmp_path / "home"
    config = home / config_dir
    config.mkdir(parents=True)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: f"/usr/bin/{executable}",
    )
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def run_double(argv: tuple[str, ...], **kwargs: object):
        calls.append((argv, dict(kwargs["env"])))  # type: ignore[arg-type]
        return subprocess.CompletedProcess(argv, 0, stdout, stderr)

    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        run_double,
    )
    presence = NativeCliSubscriptionPresence(executable)
    access = presence.prove(
        {
            "HOME": str(home),
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "must-not-pass",
            "OPENAI_API_KEY": "must-not-pass",
        }
    )

    assert access.environment == ((config_name, str(config.resolve())),)
    assert access.read_paths == access.write_paths == (config.resolve(),)
    assert calls[0][1] == {
        "HOME": str(home.resolve()),
        "PATH": "/usr/bin",
        config_name: str(config.resolve()),
    }
    assert presence.prove({"HOME": "ignored", "PATH": "ignored"}) is access
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status",
    [
        b'{"loggedIn":true,"authMethod":"apiKey","subscriptionType":null}',
        b'{"loggedIn":false,"authMethod":"claude.ai","subscriptionType":"max"}',
    ],
)
def test_claude_status_rejects_non_subscription_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: bytes,
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: "/usr/bin/claude",
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, status, b""),
    )

    with pytest.raises(AuthProfileError, match=r"not logged in.*subscription"):
        NativeCliSubscriptionPresence("claude").prove(
            {"HOME": str(home), "PATH": "/usr/bin"}
        )


def test_codex_status_rejects_api_key_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: "/usr/bin/codex",
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, b"Logged in using an API key\n", b""
        ),
    )

    with pytest.raises(AuthProfileError, match="not logged in through ChatGPT"):
        NativeCliSubscriptionPresence("codex").prove(
            {"HOME": str(home), "PATH": "/usr/bin"}
        )


def test_declared_version_must_match_vendor_version_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.shutil.which",
        lambda _name, path: "/usr/bin/claude",
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.native_cli_subscription.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, b"2.1.999 (Claude Code)\n", b""
        ),
    )

    with pytest.raises(AuthProfileError, match="version differs"):
        NativeCliSubscriptionPresence(
            "claude",
            expected_version="2.1.233 (Claude Code)",
        ).prove({"HOME": str(home), "PATH": "/usr/bin"})
