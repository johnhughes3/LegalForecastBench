"""Hostile native whole-process E2E against contributor-grade containment.

synthetic: true — probes run tests/fixtures/local_cli_fake_cli.py as a
contained subprocess. No live provider spend.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_binding import bind_official_run_auth_profile
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    FIXTURE_NONE,
    LOCAL_CLI_SUBSCRIPTION_CATEGORY,
    AuthProfileError,
    FixtureSubscriptionPresence,
)
from legalforecast.multiharness.claude_code import claude_code_local_manifest
from legalforecast.multiharness.contributor_boundary import (
    CONTRIBUTOR_NATIVE_BOUNDARY,
    HOSTILE_DENIED,
    HOSTILE_QUARANTINED,
    LINUX_LANDLOCK_FS_SCOPE,
    classify_hostile_probe,
)
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_redaction import (
    PRIVATE_EXECUTION_DIR,
    LocalCliRedactionError,
    verify_execution_artifacts,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliExecutionResult,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    "AWS_SECRET_ACCESS_KEY": "ambient-aws-canary",
    "CLAUDE_CODE_OAUTH_TOKEN": "ambient-subscription-canary",
    "SSH_AUTH_SOCK": "/tmp/ambient-ssh.sock",
    "HOME": "/private/operator-home",
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "LC_CTYPE": "C.UTF-8",
}


def _polluted_parent_env() -> dict[str, str]:
    parent = dict(_CANARY_ENV)
    for index in range(8):
        parent[f"CANARY_RAND_{index:02d}"] = f"random-canary-{index:02d}"
    return parent


def _assert_no_canaries(text: str) -> None:
    skip = {_CANARY_ENV["PATH"], _CANARY_ENV["LC_CTYPE"]}
    for value in _polluted_parent_env().values():
        if value in skip:
            continue
        assert value not in text


def _manifest(supported: tuple[str, ...]) -> LocalCliAdapterManifest:
    path = _FAKE_CLI.resolve()
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(path)),
        executable=executable_pin_for(path, version="0.1.0"),
        supported_auth_profiles=supported,
        version_probe_args=("--mode", "version"),
    )


def _subscription_spec(
    spec_id: str,
    extra_args: tuple[str, ...],
    *,
    filesystem_scope: str | None = LINUX_LANDLOCK_FS_SCOPE,
    timeout_seconds: float = 5,
) -> LocalCliRunSpec:
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=_manifest((CONTRIBUTOR_SUBSCRIPTION,)),
        auth_profile=CONTRIBUTOR_SUBSCRIPTION,
        extra_args=extra_args,
        timeout_seconds=timeout_seconds,
        filesystem_scope=filesystem_scope,
    )


def _run_subscription(
    spec: LocalCliRunSpec,
    scratch: Path,
) -> LocalCliExecutionResult:
    return execute_local_cli(
        spec,
        scratch,
        parent_env=_polluted_parent_env(),
        subscription_presence=FixtureSubscriptionPresence(),
        termination_grace_seconds=0.2,
    )


def test_subscription_without_presence_or_scope_refuses(tmp_path: Path) -> None:
    with pytest.raises(LocalCliRuntimeError, match="absent"):
        execute_local_cli(
            _subscription_spec("no-presence", ("--mode", "succeed-json")),
            tmp_path / "scratch-a",
            parent_env=_polluted_parent_env(),
        )
    with pytest.raises(LocalCliRuntimeError, match=r"linux_landlock_fs\.v1"):
        execute_local_cli(
            _subscription_spec(
                "no-scope",
                ("--mode", "succeed-json"),
                filesystem_scope=None,
            ),
            tmp_path / "scratch-b",
            parent_env=_polluted_parent_env(),
            subscription_presence=FixtureSubscriptionPresence(),
        )
    with pytest.raises(LocalCliRuntimeError, match="never reads credentials"):
        execute_local_cli(
            _subscription_spec("credentialed", ("--mode", "succeed-json")),
            tmp_path / "scratch-c",
            parent_env=_polluted_parent_env(),
            subscription_presence=FixtureSubscriptionPresence(),
            credential_source=StaticCredentialSource(
                {"CLAUDE_CODE_OAUTH_TOKEN": "must-not-project"}
            ),
        )


def test_hostile_env_exfiltration_is_absent_from_child(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    result = _run_subscription(
        _subscription_spec("dump", ("--mode", "dump-env")),
        scratch,
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert result.status == "completed"
    assert result.boundary_identity is not None
    assert result.boundary_identity["policy_id"] == CONTRIBUTOR_NATIVE_BOUNDARY
    public = json.dumps(result.to_public_record())
    assert LOCAL_CLI_SUBSCRIPTION_CATEGORY in public
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured
    assert "OPENAI_API_KEY" not in captured
    assert "ANTHROPIC_API_KEY" not in captured
    assert captured.get("HOME", "").startswith(str(scratch.resolve()))
    _assert_no_canaries(result.stdout.decode("utf-8"))
    _assert_no_canaries(public)


def test_hostile_out_of_scope_write_is_denied(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "pwned.txt"
    result = _run_subscription(
        _subscription_spec(
            "write-out",
            ("--mode", "write-probe", "--path", str(target), "--payload", "pwned"),
        ),
        scratch,
    )
    assert result.exit_code != 0
    assert not target.exists()
    record = json.loads(result.stdout.decode("utf-8"))
    assert record["ok"] is False
    assert (
        classify_hostile_probe(
            in_scope=False,
            denied=not target.exists(),
            tampered=False,
        )
        == HOSTILE_DENIED
    )


def test_mutation_control_without_filesystem_scope_write_succeeds(
    tmp_path: Path,
) -> None:
    """Load-bearing control: disable Landlock and the write probe succeeds."""

    scratch = tmp_path / "scratch"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "pwned.txt"
    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="write-control",
            manifest=_manifest((FIXTURE_NONE,)),
            auth_profile=FIXTURE_NONE,
            extra_args=(
                "--mode",
                "write-probe",
                "--path",
                str(target),
                "--payload",
                "pwned",
            ),
            timeout_seconds=5,
        ),
        scratch,
        parent_env=_polluted_parent_env(),
    )
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == "pwned"


def test_hostile_orphan_is_reaped(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    result = _run_subscription(
        _subscription_spec(
            "fork-exit",
            ("--mode", "fork-and-exit"),
            timeout_seconds=2,
        ),
        scratch,
    )
    assert result.status == "process_group_cleanup_requested"
    pids = json.loads((scratch / "pids.json").read_text(encoding="utf-8"))
    _assert_dead(pids["child_pid"])


def test_hostile_receipt_tamper_is_quarantined(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    result = _run_subscription(
        _subscription_spec("ok", ("--mode", "succeed-json")),
        scratch,
    )
    assert result.status == "completed"
    receipt = scratch / PRIVATE_EXECUTION_DIR / "receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["status"] = "forged-success"
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(LocalCliRedactionError, match="digest mismatch"):
        verify_execution_artifacts(scratch)
    assert (
        classify_hostile_probe(
            in_scope=True,
            denied=False,
            tampered=True,
        )
        == HOSTILE_QUARANTINED
    )


def test_official_run_cannot_select_contributor_subscription() -> None:
    with pytest.raises(AuthProfileError, match="official"):
        bind_official_run_auth_profile(
            claude_code_local_manifest(), CONTRIBUTOR_SUBSCRIPTION
        )


def _assert_dead(pid: int, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            time.sleep(0.05)
            continue
        time.sleep(0.05)
    raise AssertionError(f"pid {pid} is still alive")
