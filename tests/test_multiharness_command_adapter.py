from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from legalforecast.multiharness import command_adapter as command_adapter_module
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterError,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    ContributorCredit,
    RunRequest,
    SandboxPolicy,
)

SHA256 = "sha256:" + "a" * 64
OTHER_SHA256 = "sha256:" + "b" * 64


def test_manifest_file_validation_and_capabilities_loading(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path)
    manifest_path = _write_manifest(tmp_path, command=(sys.executable, str(script)))

    adapter = CommandAdapter.from_manifest_file(manifest_path)
    capabilities = adapter.capabilities(tmp_path / "workspace")

    assert capabilities.adapter_id == "fixture-adapter"
    assert capabilities.supported_families == ("legalforecast_mtd",)
    receipt = _execution_receipt(tmp_path / "workspace")
    assert receipt["status"] == "completed"
    assert receipt["returncode"] == 0
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is False


def test_permission_denied_group_cleanup_preserves_success_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        termination_grace_seconds=0.01,
    )
    probe_count = 0

    def deny_group_signals(
        process_group_id: int,
        requested_signal: int,
    ) -> None:
        del process_group_id
        nonlocal probe_count
        if requested_signal != 0:
            raise PermissionError
        probe_count += 1
        if probe_count > 1:
            raise ProcessLookupError

    monkeypatch.setattr(command_adapter_module.os, "killpg", deny_group_signals)
    workspace = tmp_path / "workspace"

    capabilities = adapter.capabilities(workspace)

    assert capabilities.adapter_id == "fixture-adapter"
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "completed"
    assert receipt["returncode"] == 0
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is False


def test_zero_exit_fails_closed_when_only_forced_group_kill_is_delivered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        termination_grace_seconds=0.01,
    )
    forced_kill_delivered = False

    def deny_graceful_group_signal(
        process_group_id: int,
        requested_signal: int,
    ) -> None:
        del process_group_id
        nonlocal forced_kill_delivered
        if requested_signal == signal.SIGTERM:
            raise PermissionError
        if requested_signal == signal.SIGKILL:
            forced_kill_delivered = True
            return
        if forced_kill_delivered:
            raise ProcessLookupError

    monkeypatch.setattr(
        command_adapter_module.os,
        "killpg",
        deny_graceful_group_signal,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(
        CommandAdapterError,
        match="group-scoped cleanup was requested",
    ):
        adapter.capabilities(workspace)

    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "process_group_cleanup_requested"
    assert receipt["returncode"] == 0
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is True


def test_relative_command_resolution(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path / "bin")
    script.chmod(0o755)
    manifest_path = _write_manifest(tmp_path, command=("bin/fixture_adapter.py",))

    adapter = CommandAdapter.from_manifest_file(manifest_path)
    capabilities = adapter.capabilities(tmp_path / "workspace")

    assert capabilities.adapter_version == "0.1.0"


def test_command_adapter_run_invocation_and_private_log_handling(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path)
    manifest = _manifest(command=(sys.executable, str(script)))
    adapter = CommandAdapter(manifest=manifest)
    workspace = tmp_path / "workspace"

    result = adapter.run(_run_request(manifest), workspace)

    assert result.status == "succeeded"
    assert result.public_summary == {"summary": "ok"}
    assert "SECRET_STDOUT" not in json.dumps(result.to_record(), sort_keys=True)
    assert (workspace / "private-logs" / "run-stdout.log").read_text(
        encoding="utf-8"
    ).strip() == "SECRET_STDOUT"
    assert (workspace / "request.json").is_file()
    assert (workspace / "result.json").is_file()
    assert (workspace / "private-logs" / "run-result.raw.json").is_file()


def test_command_adapter_run_uses_declared_provider_environment_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(tmp_path, capture_environment=True)
    manifest = _manifest(command=(sys.executable, str(script)))
    adapter = CommandAdapter(manifest=manifest)
    workspace = tmp_path / "workspace"
    ambient_home = tmp_path / "ambient-home"
    ambient_home.mkdir()
    (ambient_home / ".provider-token").write_text(
        "ambient credential store",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(ambient_home))
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", "allowed-value")
    monkeypatch.setenv("FAKE_SECRET", "must-not-leak")

    adapter.run(
        _run_request(
            manifest,
            allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
        ),
        workspace,
    )

    captured = json.loads(
        (workspace / "private-logs" / "run-environment.json").read_text(
            encoding="utf-8"
        )
    )
    assert captured["DECLARED_PROVIDER_VALUE"] == "allowed-value"
    assert "FAKE_SECRET" not in captured
    assert captured["PATH"] == os.environ["PATH"]
    isolated_home = workspace / "private-logs" / "adapter-home"
    assert captured["HOME"] == str(isolated_home)
    assert captured["XDG_CACHE_HOME"] == str(isolated_home / ".cache")
    assert captured["XDG_CONFIG_HOME"] == str(isolated_home / ".config")
    assert captured["XDG_DATA_HOME"] == str(isolated_home / ".local" / "share")
    assert captured["XDG_STATE_HOME"] == str(isolated_home / ".local" / "state")
    assert isolated_home.is_dir()
    assert not (isolated_home / ".provider-token").exists()
    if "LC_CTYPE" in os.environ:
        assert captured.get("LC_CTYPE") == os.environ["LC_CTYPE"]
    assert set(captured).issubset(
        {
            "PATH",
            "HOME",
            "LC_CTYPE",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "DECLARED_PROVIDER_VALUE",
        }
    )
    capability_environment = json.loads(
        (workspace / "private-logs" / "capabilities-environment.json").read_text(
            encoding="utf-8"
        )
    )
    assert "DECLARED_PROVIDER_VALUE" not in capability_environment
    assert "FAKE_SECRET" not in capability_environment
    assert capability_environment["HOME"] == str(isolated_home)
    assert set(capability_environment).issubset(
        {
            "PATH",
            "HOME",
            "LC_CTYPE",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
        }
    )


def test_command_adapter_rejects_missing_declared_provider_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    monkeypatch.delenv("MISSING_PROVIDER_KEY", raising=False)

    with pytest.raises(CommandAdapterError, match="MISSING_PROVIDER_KEY"):
        adapter.run(
            _run_request(
                adapter.manifest,
                allowed_provider_env_vars=("MISSING_PROVIDER_KEY",),
            ),
            tmp_path / "workspace",
        )


def test_command_adapter_rejects_provider_value_in_public_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(
        tmp_path,
        public_summary_env_name="DECLARED_PROVIDER_VALUE",
    )
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    secret = "opaque-provider-value-7Jx9"
    monkeypatch.setenv("DECLARED_PROVIDER_VALUE", secret)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "result.json").write_text("stale public result", encoding="utf-8")

    with pytest.raises(ValueError, match="declared provider environment value") as exc:
        adapter.run(
            _run_request(
                adapter.manifest,
                allowed_provider_env_vars=("DECLARED_PROVIDER_VALUE",),
            ),
            workspace,
        )

    assert secret not in str(exc.value)
    assert not (workspace / "result.json").exists()
    private_result = workspace / "private-logs" / "run-result.raw.json"
    assert private_result.is_file()
    assert secret in private_result.read_text(encoding="utf-8")


def test_command_adapter_clears_stale_result_before_capability_probe(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path, fail=True)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result_path = workspace / "result.json"
    result_path.write_text("stale public result", encoding="utf-8")

    with pytest.raises(CommandAdapterError, match="capabilities failed"):
        adapter.run(_run_request(adapter.manifest), workspace)

    assert not result_path.exists()


def test_command_adapter_rejects_planted_home_symlink(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"
    private_logs = workspace / "private-logs"
    private_logs.mkdir(parents=True)
    ambient_home = tmp_path / "ambient-home"
    ambient_home.mkdir()
    (private_logs / "adapter-home").symlink_to(ambient_home, target_is_directory=True)

    with pytest.raises(CommandAdapterError, match="must not be symlinks"):
        adapter.capabilities(workspace)


def test_command_adapter_rejects_planted_home_subdirectory_symlink(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"
    adapter_home = workspace / "private-logs" / "adapter-home"
    adapter_home.mkdir(parents=True)
    ambient_home = tmp_path / "ambient-home"
    ambient_home.mkdir()
    (adapter_home / ".local").symlink_to(ambient_home, target_is_directory=True)

    with pytest.raises(CommandAdapterError, match="must not be symlinks"):
        adapter.capabilities(workspace)


def test_command_adapter_timeout_is_enforced(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path, sleep_seconds=1)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.01,
    )

    with pytest.raises(CommandAdapterError, match="timed out"):
        adapter.capabilities(tmp_path / "workspace")


def test_timeout_kills_ignored_signal_child_and_grandchild_and_bounds_logs(
    tmp_path: Path,
) -> None:
    script, pid_dir = _write_process_tree_script(
        tmp_path,
        behavior="sleep",
        output_bytes=4096,
    )
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.5,
        termination_grace_seconds=0.05,
        max_private_log_bytes=128,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="timed out"):
        adapter.capabilities(workspace)

    _assert_process_tree_stopped(pid_dir)
    stdout_path = workspace / "private-logs" / "capabilities-stdout.log"
    assert stdout_path.stat().st_size <= 128
    assert stdout_path.read_text(encoding="utf-8").endswith(
        "\n...[truncated by LegalForecastBench]...\n"
    )
    assert _execution_receipt(workspace) == {
        "schema_version": "legalforecast.multiharness.command_execution_log.v1",
        "phase": "capabilities",
        "status": "timed_out",
        "returncode": -signal.SIGKILL,
        "stdout_path": stdout_path.as_posix(),
        "stderr_path": (
            workspace / "private-logs" / "capabilities-stderr.log"
        ).as_posix(),
        "stdout_truncated": True,
        "stderr_truncated": False,
        "termination_requested": True,
        "forced_kill": True,
    }


def test_timeout_uses_graceful_termination_before_forced_kill(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path, sleep_seconds=60)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.05,
        termination_grace_seconds=0.5,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="timed out"):
        adapter.capabilities(workspace)

    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "timed_out"
    assert receipt["returncode"] == -signal.SIGTERM
    assert receipt["termination_requested"] is True
    assert receipt["forced_kill"] is False


def test_permission_denied_group_cleanup_preserves_timeout_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _write_adapter_script(tmp_path, sleep_seconds=60)
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.01,
        termination_grace_seconds=0.01,
    )
    real_killpg = os.killpg

    def deny_group_signals(
        process_group_id: int,
        requested_signal: int,
    ) -> None:
        if requested_signal == 0:
            real_killpg(process_group_id, requested_signal)
            return
        raise PermissionError

    monkeypatch.setattr(command_adapter_module.os, "killpg", deny_group_signals)
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="timed out"):
        adapter.capabilities(workspace)

    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "timed_out"
    assert receipt["returncode"] == -signal.SIGKILL
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is False


def test_nonzero_parent_crash_cleans_surviving_descendants(tmp_path: Path) -> None:
    script, pid_dir = _write_process_tree_script(tmp_path, behavior="crash")
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=2,
        termination_grace_seconds=0.05,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="exit code 23"):
        adapter.capabilities(workspace)

    _assert_process_tree_stopped(pid_dir)
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "failed"
    assert receipt["returncode"] == 23
    assert receipt["termination_requested"] is True
    assert receipt["forced_kill"] is True


def test_zero_exit_with_surviving_same_group_descendants_fails_closed(
    tmp_path: Path,
) -> None:
    script, pid_dir = _write_process_tree_script(tmp_path, behavior="exit_zero")
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=2,
        termination_grace_seconds=0.05,
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(
        CommandAdapterError,
        match="left processes in its original process group",
    ):
        adapter.capabilities(workspace)

    _assert_process_tree_stopped(pid_dir)
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "process_group_cleanup_requested"
    assert receipt["returncode"] == 0
    assert receipt["termination_requested"] is True


@pytest.mark.parametrize("cancellation_signal", [signal.SIGINT, signal.SIGTERM])
def test_user_cancellation_cleans_process_tree_and_writes_typed_receipt(
    tmp_path: Path,
    cancellation_signal: signal.Signals,
) -> None:
    script, pid_dir = _write_process_tree_script(tmp_path, behavior="sleep")
    manifest_path = _write_manifest(
        tmp_path,
        command=(sys.executable, str(script)),
    )
    workspace = tmp_path / "workspace"
    driver = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "from pathlib import Path",
                    "from legalforecast.multiharness.command_adapter import (",
                    "    CommandAdapter, CommandAdapterError,",
                    ")",
                    "adapter = CommandAdapter.from_manifest_file(",
                    f"    Path({str(manifest_path)!r}),",
                    "    timeout_seconds=10,",
                    "    termination_grace_seconds=0.05,",
                    ")",
                    "try:",
                    f"    adapter.capabilities(Path({str(workspace)!r}))",
                    "except CommandAdapterError as exc:",
                    "    print(str(exc))",
                    "    raise SystemExit(0 if 'was cancelled' in str(exc) else 3)",
                    "raise SystemExit(4)",
                ]
            ),
        ],
        cwd=Path.cwd(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_process_tree_start(pid_dir)
        time.sleep(0.05)
        os.kill(driver.pid, cancellation_signal)
        stdout, stderr = driver.communicate(timeout=3)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait(timeout=2)

    assert driver.returncode == 0, (stdout, stderr)
    assert stdout.strip() == "command adapter capabilities was cancelled"
    assert stderr == ""
    _assert_process_tree_stopped(pid_dir)
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "cancelled"
    assert receipt["returncode"] == -signal.SIGKILL
    assert receipt["forced_kill"] is True


def test_permission_denied_group_cleanup_preserves_cancellation_receipt(
    tmp_path: Path,
) -> None:
    adapter_pid_path = tmp_path / "adapter.pid"
    script = tmp_path / "sleep_adapter.py"
    script.write_text(
        "\n".join(
            [
                "import os, pathlib, time",
                f"pathlib.Path({str(adapter_pid_path)!r}).write_text(",
                "    str(os.getpid()), encoding='utf-8'",
                ")",
                "time.sleep(60)",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = _write_manifest(
        tmp_path,
        command=(sys.executable, str(script)),
    )
    workspace = tmp_path / "workspace"
    driver = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "from pathlib import Path",
                    "from legalforecast.multiharness import command_adapter as module",
                    "from legalforecast.multiharness.command_adapter import (",
                    "    CommandAdapter, CommandAdapterError,",
                    ")",
                    "real_killpg = module.os.killpg",
                    "def deny_group_signals(process_group_id, requested_signal):",
                    "    if requested_signal == 0:",
                    "        return real_killpg(process_group_id, requested_signal)",
                    "    raise PermissionError",
                    "module.os.killpg = deny_group_signals",
                    "adapter = CommandAdapter.from_manifest_file(",
                    f"    Path({str(manifest_path)!r}),",
                    "    timeout_seconds=10,",
                    "    termination_grace_seconds=0.01,",
                    ")",
                    "try:",
                    f"    adapter.capabilities(Path({str(workspace)!r}))",
                    "except CommandAdapterError as exc:",
                    "    print(str(exc))",
                    "    raise SystemExit(0 if 'was cancelled' in str(exc) else 3)",
                    "raise SystemExit(4)",
                ]
            ),
        ],
        cwd=Path.cwd(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not adapter_pid_path.is_file():
            time.sleep(0.01)
        assert adapter_pid_path.is_file()
        os.kill(driver.pid, signal.SIGTERM)
        stdout, stderr = driver.communicate(timeout=3)
    finally:
        if driver.poll() is None:
            driver.kill()
            driver.wait(timeout=2)

    assert driver.returncode == 0, (stdout, stderr)
    assert stdout.strip() == "command adapter capabilities was cancelled"
    assert stderr == ""
    adapter_pid = int(adapter_pid_path.read_text(encoding="utf-8"))
    assert not _pid_is_running(adapter_pid)
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "cancelled"
    assert receipt["returncode"] == -signal.SIGKILL
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is False


def test_process_tree_cleanup_is_repeatable(tmp_path: Path) -> None:
    script, pid_dir = _write_process_tree_script(tmp_path, behavior="sleep")
    adapter = CommandAdapter(
        manifest=_manifest(command=(sys.executable, str(script))),
        timeout_seconds=0.5,
        termination_grace_seconds=0.05,
    )
    workspace = tmp_path / "workspace"

    for _ in range(2):
        with pytest.raises(CommandAdapterError, match="timed out"):
            adapter.capabilities(workspace)
        _assert_process_tree_stopped(pid_dir)

    assert _execution_receipt(workspace)["status"] == "timed_out"


def test_launch_failure_writes_sanitized_typed_receipt(tmp_path: Path) -> None:
    adapter = CommandAdapter(
        manifest=_manifest(command=("/definitely/missing/fake-adapter",)),
    )
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="could not complete") as exc:
        adapter.capabilities(workspace)

    assert "/definitely/missing" not in str(exc.value)
    receipt = _execution_receipt(workspace)
    assert receipt["status"] == "launch_failed"
    assert receipt["returncode"] is None
    assert receipt["termination_requested"] is False
    assert receipt["forced_kill"] is False


def test_private_execution_logs_reject_planted_symlinks(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"
    private_logs = workspace / "private-logs"
    private_logs.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("must remain unchanged", encoding="utf-8")
    (private_logs / "capabilities-stdout.log").symlink_to(victim)

    with pytest.raises(CommandAdapterError, match="must not be symlinks"):
        adapter.capabilities(workspace)

    assert victim.read_text(encoding="utf-8") == "must remain unchanged"


def test_command_adapter_rejects_unsafe_result_artifacts(tmp_path: Path) -> None:
    script = _write_adapter_script(tmp_path, unsafe_artifact=True)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))

    with pytest.raises(ValueError, match="parent"):
        adapter.run(_run_request(adapter.manifest), tmp_path / "workspace")


def test_command_adapter_reports_nonzero_exit_without_public_logs(
    tmp_path: Path,
) -> None:
    script = _write_adapter_script(tmp_path, fail=True)
    adapter = CommandAdapter(manifest=_manifest(command=(sys.executable, str(script))))
    workspace = tmp_path / "workspace"

    with pytest.raises(CommandAdapterError, match="see private logs"):
        adapter.capabilities(workspace)

    assert (workspace / "private-logs" / "capabilities-stderr.log").read_text(
        encoding="utf-8"
    ).strip() == "SECRET_STDERR"


def _write_adapter_script(
    root: Path,
    *,
    sleep_seconds: float = 0,
    unsafe_artifact: bool = False,
    fail: bool = False,
    capture_environment: bool = False,
    public_summary_env_name: str | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    script = root / "fixture_adapter.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json, os, pathlib, sys, time",
                f"SLEEP_SECONDS = {sleep_seconds!r}",
                f"UNSAFE_ARTIFACT = {unsafe_artifact!r}",
                f"FAIL = {fail!r}",
                f"CAPTURE_ENVIRONMENT = {capture_environment!r}",
                f"PUBLIC_SUMMARY_ENV_NAME = {public_summary_env_name!r}",
                f"SHA256 = {SHA256!r}",
                f"OTHER_SHA256 = {OTHER_SHA256!r}",
                "CAP_SCHEMA = 'legalforecast.multiharness.adapter_capabilities.v1'",
                "RESULT_SCHEMA = 'legalforecast.multiharness.run_result.v1'",
                "if SLEEP_SECONDS:",
                "    time.sleep(SLEEP_SECONDS)",
                "parser = argparse.ArgumentParser()",
                "sub = parser.add_subparsers(dest='command', required=True)",
                "cap = sub.add_parser('capabilities')",
                "cap.add_argument('--output', required=True)",
                "run = sub.add_parser('run')",
                "run.add_argument('--request', required=True)",
                "run.add_argument('--output', required=True)",
                "run.add_argument('--workspace', required=True)",
                "args = parser.parse_args()",
                "if FAIL:",
                "    print('SECRET_STDERR', file=sys.stderr)",
                "    raise SystemExit(2)",
                "if args.command == 'capabilities':",
                "    if CAPTURE_ENVIRONMENT:",
                "        private_logs = pathlib.Path(args.output).parent",
                "        private_logs /= 'private-logs'",
                "        private_logs.mkdir(parents=True, exist_ok=True)",
                "        (private_logs / 'capabilities-environment.json').write_text(",
                "            json.dumps(dict(os.environ), sort_keys=True),",
                "            encoding='utf-8',",
                "        )",
                "    payload = {",
                "      'schema_version': CAP_SCHEMA,",
                "      'adapter_id': 'fixture-adapter',",
                "      'adapter_version': '0.1.0',",
                "      'supported_families': ['legalforecast_mtd'],",
                "      'supported_scoring_modes': ['lfb_brier'],",
                "      'supports_sandbox_policy': True,",
                "      'capabilities_sha256': SHA256,",
                "    }",
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(payload))",
                "else:",
                "    request = json.load(open(args.request, encoding='utf-8'))",
                "    if CAPTURE_ENVIRONMENT:",
                "        private_logs = pathlib.Path(args.workspace) / 'private-logs'",
                "        private_logs.mkdir(parents=True, exist_ok=True)",
                "        (private_logs / 'run-environment.json').write_text(",
                "            json.dumps(dict(os.environ), sort_keys=True),",
                "            encoding='utf-8',",
                "        )",
                "    if UNSAFE_ARTIFACT:",
                "        artifact_path = '../private.txt'",
                "    else:",
                "        artifact_path = 'artifacts/output.json'",
                "    payload = {",
                "      'schema_version': RESULT_SCHEMA,",
                "      'result_id': 'result-1',",
                "      'request_id': request['request_id'],",
                "      'status': 'succeeded',",
                "      'result_sha256': OTHER_SHA256,",
                "      'artifacts': [",
                "        {",
                "          'artifact_id': 'output',",
                "          'path': artifact_path,",
                "          'sha256': SHA256,",
                "          'media_type': 'application/json',",
                "          'public': False,",
                "        }",
                "      ],",
                "      'public_summary': {",
                "          'summary': (",
                "              os.environ.get(PUBLIC_SUMMARY_ENV_NAME, '')",
                "              if PUBLIC_SUMMARY_ENV_NAME",
                "              else 'ok'",
                "          ),",
                "      },",
                "    }",
                "    print('SECRET_STDOUT')",
                "    with open(args.output, 'w', encoding='utf-8') as handle:",
                "        handle.write(json.dumps(payload))",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_process_tree_script(
    root: Path,
    *,
    behavior: str,
    output_bytes: int = 0,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    pid_dir = root / "process-tree-pids"
    script = root / "process_tree_adapter.py"
    grandchild_code = "\n".join(
        [
            "import os, pathlib, signal, time",
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
            f"pathlib.Path({str(pid_dir / 'grandchild.pid')!r}).write_text(",
            "    str(os.getpid()), encoding='utf-8'",
            ")",
            "time.sleep(60)",
        ]
    )
    child_code = "\n".join(
        [
            "import os, pathlib, signal, subprocess, sys, time",
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
            f"pathlib.Path({str(pid_dir / 'child.pid')!r}).write_text(",
            "    str(os.getpid()), encoding='utf-8'",
            ")",
            f"subprocess.Popen([sys.executable, '-c', {grandchild_code!r}])",
            "time.sleep(60)",
        ]
    )
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import os, pathlib, signal, subprocess, sys, time",
                f"PID_DIR = pathlib.Path({str(pid_dir)!r})",
                "PID_DIR.mkdir(parents=True, exist_ok=True)",
                "for old_pid in PID_DIR.glob('*.pid'):",
                "    old_pid.unlink()",
                "(PID_DIR / 'parent.pid').write_text(",
                "    str(os.getpid()), encoding='utf-8'",
                ")",
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}])",
                "for _ in range(200):",
                "    if (PID_DIR / 'child.pid').is_file() and (",
                "        PID_DIR / 'grandchild.pid'",
                "    ).is_file():",
                "        break",
                "    time.sleep(0.005)",
                f"print('X' * {output_bytes} or 'partial output', flush=True)",
                "print('private failure detail', file=sys.stderr, flush=True)",
                "if " + repr(behavior) + " == 'crash':",
                "    raise SystemExit(23)",
                "if " + repr(behavior) + " == 'exit_zero':",
                "    raise SystemExit(0)",
                "time.sleep(60)",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, pid_dir


def _execution_receipt(workspace: Path) -> dict[str, object]:
    return json.loads(
        (workspace / "private-logs" / "capabilities-execution.json").read_text(
            encoding="utf-8"
        )
    )


def _assert_process_tree_stopped(pid_dir: Path) -> None:
    pid_paths = [
        pid_dir / "parent.pid",
        pid_dir / "child.pid",
        pid_dir / "grandchild.pid",
    ]
    assert all(path.is_file() for path in pid_paths)
    pids = [int(path.read_text(encoding="utf-8")) for path in pid_paths]
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and any(_pid_is_running(pid) for pid in pids):
        time.sleep(0.01)
    assert not [pid for pid in pids if _pid_is_running(pid)]


def _wait_for_process_tree_start(pid_dir: Path) -> None:
    pid_paths = [
        pid_dir / "parent.pid",
        pid_dir / "child.pid",
        pid_dir / "grandchild.pid",
    ]
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not all(path.is_file() for path in pid_paths):
        time.sleep(0.01)
    assert all(path.is_file() for path in pid_paths)


def _pid_is_running(pid: int) -> bool:
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        fields = stat_path.read_text(encoding="utf-8").split()
    except FileNotFoundError:
        return False
    return len(fields) < 3 or fields[2] != "Z"


def _write_manifest(tmp_path: Path, *, command: tuple[str, ...]) -> Path:
    path = tmp_path / "adapter.json"
    path.write_text(
        json.dumps(_manifest(command=command).to_record()),
        encoding="utf-8",
    )
    return path


def _manifest(*, command: tuple[str, ...]) -> AdapterManifest:
    return AdapterManifest(
        adapter_id="fixture-adapter",
        display_name="Fixture Adapter",
        adapter_version="0.1.0",
        command=command,
        contributors=(ContributorCredit(role="adapter_author", name="Fixture"),),
    )


def _run_request(
    manifest: AdapterManifest,
    *,
    allowed_provider_env_vars: tuple[str, ...] = (),
) -> RunRequest:
    return RunRequest(
        request_id="request-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="case-1",
            task_sha256=SHA256,
            metadata={"case_id": "case-1"},
        ),
        adapter=manifest,
        model_key="fixture/model",
        sandbox_policy=SandboxPolicy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=30,
            working_directory="/workspace",
            allowed_provider_env_vars=allowed_provider_env_vars,
        ),
        request_sha256=OTHER_SHA256,
    )
