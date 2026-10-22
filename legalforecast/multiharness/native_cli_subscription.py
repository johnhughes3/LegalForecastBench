"""Vendor-supported local subscription detection for native community CLIs."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from legalforecast.multiharness.auth_profiles import (
    AuthProfileError,
    SubscriptionRuntimeAccess,
)

_STATUS_TIMEOUT_SECONDS: Final = 10.0
_STATUS_OUTPUT_LIMIT: Final = 65_536


class NativeCliSubscriptionPresence:
    """Confirm a Claude or Codex subscription through its supported status CLI.

    Only the vendor's configuration directory is projected into the contained
    child. The directory is referenced in place so login refreshes work; it is
    never copied into a run directory or included in public provenance.
    """

    def __init__(
        self,
        executable: str,
        *,
        timeout_seconds: float = _STATUS_TIMEOUT_SECONDS,
        expected_version: str | None = None,
    ) -> None:
        if executable not in {"claude", "codex"}:
            raise AuthProfileError("subscription presence supports claude or codex")
        if timeout_seconds <= 0:
            raise AuthProfileError("subscription status timeout must be positive")
        if expected_version is not None and not expected_version.strip():
            raise AuthProfileError(
                "expected subscription CLI version must not be blank"
            )
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._expected_version = expected_version
        self._verified: SubscriptionRuntimeAccess | None = None

    def prove(self, parent_env: Mapping[str, str]) -> SubscriptionRuntimeAccess:
        """Return narrow runtime access after the vendor reports subscription auth."""

        if self._verified is not None:
            return self._verified
        executable = shutil.which(
            self._executable, path=parent_env.get("PATH", "/usr/bin")
        )
        if executable is None:
            raise AuthProfileError(
                f"{self._executable} subscription CLI is not available on PATH"
            )
        home_value = parent_env.get("HOME")
        if not home_value:
            raise AuthProfileError("local subscription status requires HOME")
        home = Path(home_value).expanduser().resolve()
        config_name, config_root = self._config_root(parent_env, home)
        status_env = {
            "HOME": str(home),
            "PATH": parent_env.get("PATH", "/usr/bin"),
            config_name: str(config_root),
        }
        argv = (
            (executable, "auth", "status", "--json")
            if self._executable == "claude"
            else (executable, "login", "status")
        )
        try:
            with tempfile.TemporaryDirectory(prefix="lfb-subscription-status-") as cwd:
                if self._expected_version is not None:
                    self._verify_version(executable, status_env, cwd=Path(cwd))
                completed = subprocess.run(
                    argv,
                    cwd=cwd,
                    env=status_env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    check=False,
                    timeout=self._timeout_seconds,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuthProfileError(
                f"{self._executable} subscription status could not be verified"
            ) from exc
        if (
            completed.returncode != 0
            or len(completed.stdout) > _STATUS_OUTPUT_LIMIT
            or len(completed.stderr) > _STATUS_OUTPUT_LIMIT
        ):
            raise AuthProfileError(
                f"{self._executable} subscription login is absent; "
                "run the vendor login command"
            )
        if self._executable == "claude":
            self._verify_claude_status(completed.stdout)
        else:
            self._verify_codex_status(completed.stdout, completed.stderr)
        access = SubscriptionRuntimeAccess(
            environment=((config_name, str(config_root)),),
            read_paths=(config_root,),
            write_paths=(config_root,),
        )
        self._verified = access
        return access

    def _verify_version(
        self,
        executable: str,
        environment: Mapping[str, str],
        *,
        cwd: Path,
    ) -> None:
        try:
            completed = subprocess.run(
                (executable, "--version"),
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuthProfileError(
                f"{self._executable} version could not be verified"
            ) from exc
        try:
            observed = completed.stdout.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise AuthProfileError(
                f"{self._executable} version could not be verified"
            ) from exc
        if completed.returncode != 0 or observed != self._expected_version:
            raise AuthProfileError(
                f"{self._executable} version differs from the declared pin"
            )

    def _config_root(
        self, parent_env: Mapping[str, str], home: Path
    ) -> tuple[str, Path]:
        if self._executable == "claude":
            name = "CLAUDE_CONFIG_DIR"
            value = parent_env.get(name, str(home / ".claude"))
        else:
            name = "CODEX_HOME"
            value = parent_env.get(name, str(home / ".codex"))
        root = Path(value).expanduser().resolve()
        if root == home or not root.is_dir():
            raise AuthProfileError(
                f"{self._executable} subscription config directory is unavailable"
            )
        return name, root

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


__all__ = ["NativeCliSubscriptionPresence"]
