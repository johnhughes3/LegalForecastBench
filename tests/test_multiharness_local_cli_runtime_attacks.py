"""Attack tests for contained local-CLI execution (leaks, timeouts, orphans)."""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.local_cli_environment import (
    InfisicalSandboxCredentialSource,
    expected_child_environment_names,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "canary",
    "AWS_SECRET_ACCESS_KEY": "ambient-aws-canary",
    "CANARY_AWS_KEY": "canary-aws-key-value",
    "OP_SERVICE_ACCOUNT_TOKEN": "canary-op-token-value",
    "SSH_AUTH_SOCK": "/tmp/ambient-ssh.sock",
    "HOME": "/private/operator-home",
    "PATH": os.environ.get("PATH", "/usr/bin"),
    "LC_CTYPE": "C.UTF-8",
}


def _polluted_parent_env() -> dict[str, str]:
    parent = dict(_CANARY_ENV)
    for index in range(20):
        parent[f"CANARY_RAND_{index:02d}"] = f"random-canary-{index:02d}"
    return parent


def test_unknown_profile_fails_closed_without_spawning(tmp_path: Path) -> None:
    sentinel = tmp_path / "spawned"
    script = tmp_path / "would-spawn.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    with pytest.raises(LocalCliRuntimeError, match="unknown") as exc:
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="missing-profile",
                manifest=_manifest(script, (FIXTURE_NONE,)),
                auth_profile="does-not-exist",
            ),
            tmp_path / "scratch",
            parent_env=_polluted_parent_env(),
        )
    assert not sentinel.exists()
    _assert_no_canaries(str(exc.value))


def test_empty_infisical_projection_does_not_spawn_or_partially_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = tmp_path / "spawned"
    script = tmp_path / "would-spawn.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "infisical-agent-sandbox"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o700)

    def _empty(argv: tuple[str, ...], **_kwargs: object) -> object:
        import subprocess

        return subprocess.CompletedProcess(argv, 0, stdout=b"{}\n", stderr=b"")

    monkeypatch.setattr(
        "legalforecast.multiharness.local_cli_environment.subprocess.run",
        _empty,
    )
    source = InfisicalSandboxCredentialSource(
        wrapper_path=wrapper,
        parent_env=_polluted_parent_env(),
    )
    with pytest.raises(LocalCliRuntimeError, match="unavailable") as exc:
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="empty-infisical",
                manifest=_manifest(
                    script,
                    (PUBLISHED_API_KEY,),
                    profile_env_vars=((PUBLISHED_API_KEY, ("ANTHROPIC_API_KEY",)),),
                ),
                auth_profile=PUBLISHED_API_KEY,
            ),
            tmp_path / "scratch",
            credential_source=source,
            parent_env=_polluted_parent_env(),
        )
    assert not sentinel.exists()
    _assert_no_canaries(str(exc.value))


def test_timeout_kills_hang_and_forked_grandchild(tmp_path: Path) -> None:
    hang_dir = tmp_path / "hang"
    hang = execute_local_cli(
        _fake_spec("hang", extra_args=("--mode", "hang")),
        hang_dir,
        parent_env=_polluted_parent_env(),
        termination_grace_seconds=0.2,
    )
    assert hang.status == "timed_out"
    assert hang.timed_out is True
    assert hang.duration_ms >= 1500
    hang_pids = json.loads((hang_dir / "pids.json").read_text(encoding="utf-8"))
    _assert_dead(hang_pids["pid"])
    _assert_dead(hang_pids["pgid"])

    fork_dir = tmp_path / "fork"
    forked = execute_local_cli(
        _fake_spec("fork", extra_args=("--mode", "fork-child")),
        fork_dir,
        parent_env=_polluted_parent_env(),
        termination_grace_seconds=0.2,
    )
    assert forked.status == "timed_out"
    fork_pids = json.loads((fork_dir / "pids.json").read_text(encoding="utf-8"))
    _assert_dead(fork_pids["pid"])
    _assert_dead(fork_pids["child_pid"])


def test_zero_exit_with_leftover_child_is_not_success(tmp_path: Path) -> None:
    workdir = tmp_path / "fork-exit"
    result = execute_local_cli(
        _fake_spec("fork-exit", extra_args=("--mode", "fork-and-exit")),
        workdir,
        parent_env=_polluted_parent_env(),
        termination_grace_seconds=0.2,
    )
    assert result.status == "process_group_cleanup_requested"
    assert result.exit_code == 0
    pids = json.loads((workdir / "pids.json").read_text(encoding="utf-8"))
    _assert_dead(pids["child_pid"])


def test_crash_preserves_exit_code_and_spew_records_truncation(
    tmp_path: Path,
) -> None:
    crashed = execute_local_cli(
        _fake_spec("crash", extra_args=("--mode", "crash")),
        tmp_path / "crash",
        parent_env=_polluted_parent_env(),
    )
    assert crashed.status == "nonzero"
    assert crashed.exit_code == 2
    assert crashed.stdout_truncated is False

    spewed = execute_local_cli(
        _fake_spec("spew", extra_args=("--mode", "spew"), timeout_seconds=30),
        tmp_path / "spew",
        parent_env=_polluted_parent_env(),
        max_capture_bytes=1_048_576,
    )
    assert spewed.status == "completed"
    assert spewed.stdout_truncated is True
    assert spewed.stderr_truncated is False
    assert len(spewed.stdout) == 1_048_576
    assert spewed.stdout.endswith(b"\n[truncated]\n")
    public = spewed.to_public_record()
    assert public["stdout_truncated"] is True
    assert public["stderr_truncated"] is False

    costly = execute_local_cli(
        _fake_spec(
            "spew-cost",
            extra_args=("--mode", "spew-then-cost"),
            timeout_seconds=10,
        ),
        tmp_path / "spew-cost",
        parent_env=_polluted_parent_env(),
        max_capture_bytes=1_048_576,
    )
    assert costly.stdout_truncated is True
    assert costly.cost_usd == 1.25


def test_eight_concurrent_tasks_stay_isolated(tmp_path: Path) -> None:
    payloads = [f"payload-task-{index:02d}-unique" for index in range(8)]

    def _run(index: int) -> tuple[int, bytes, str]:
        workdir = tmp_path / f"task-{index:02d}"
        result = execute_local_cli(
            LocalCliRunSpec(
                spec_id=f"task-{index:02d}",
                manifest=_manifest(_FAKE_CLI, (FIXTURE_NONE,)),
                auth_profile=FIXTURE_NONE,
                extra_args=("--mode", "succeed-json"),
                stdin_bytes=payloads[index].encode("utf-8"),
                timeout_seconds=10,
            ),
            workdir,
            parent_env=_polluted_parent_env(),
        )
        return index, result.stdout, result.cwd

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_run, index) for index in range(8)]
        results = [future.result() for future in as_completed(futures)]

    by_index = {index: (stdout, cwd) for index, stdout, cwd in results}
    workdirs = [cwd for _stdout, cwd in by_index.values()]
    assert len(set(workdirs)) == 8
    for index, payload in enumerate(payloads):
        stdout, cwd = by_index[index]
        assert payload.encode("utf-8") in stdout
        for other_index, other_payload in enumerate(payloads):
            if other_index == index:
                continue
            assert other_payload.encode("utf-8") not in stdout
        assert Path(cwd).is_dir()


def test_service_child_env_matches_allowlist_against_polluted_parent(
    tmp_path: Path,
) -> None:
    parent = _polluted_parent_env()
    result = execute_local_cli(
        _fake_spec("dump", extra_args=("--mode", "dump-env")),
        tmp_path / "dump",
        parent_env=parent,
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert result.status == "completed"
    assert result.cost_usd == 0.0 or result.cost_usd is None
    assert result.duration_ms > 0
    allowed = expected_child_environment_names(parent_env=parent)
    assert set(captured) == allowed
    for name, value in parent.items():
        if name in allowed:
            continue
        assert name not in captured
        assert value not in captured.values()
        assert value not in result.stdout.decode("utf-8")
        assert value not in json.dumps(result.to_public_record())


def test_succeed_json_records_duration_and_cost(tmp_path: Path) -> None:
    result = execute_local_cli(
        _fake_spec("ok", extra_args=("--mode", "succeed-json")),
        tmp_path / "ok",
        parent_env=_polluted_parent_env(),
    )
    assert result.status == "completed"
    assert result.duration_ms > 0
    assert result.cost_usd == 0.0
    public = result.to_public_record()
    assert public["duration_ms"] == result.duration_ms
    assert public["cost_usd"] == 0.0
    _assert_no_canaries(json.dumps(public))


def _fake_spec(
    spec_id: str,
    *,
    extra_args: tuple[str, ...],
    timeout_seconds: float = 2,
) -> LocalCliRunSpec:
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=_manifest(_FAKE_CLI, (FIXTURE_NONE,)),
        auth_profile=FIXTURE_NONE,
        extra_args=extra_args,
        timeout_seconds=timeout_seconds,
    )


def _manifest(
    script: Path,
    supported: tuple[str, ...],
    *,
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> LocalCliAdapterManifest:
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(script)),
        supported_auth_profiles=supported,
        profile_env_vars=profile_env_vars,
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _assert_dead(pid: int, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"pid {pid} is still alive")


def _assert_no_canaries(text: str) -> None:
    parent = _polluted_parent_env()
    skip = {parent["PATH"], parent["LC_CTYPE"]}
    for value in parent.values():
        if value in skip:
            continue
        assert value not in text
