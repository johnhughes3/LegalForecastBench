from __future__ import annotations

import ast
import json
import os
import stat
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.local_cli_contracts import RunSpec
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliExecutionResult,
    LocalCliExecutionService,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
    execution_receipt_from_runtime,
)
from legalforecast.multiharness.local_cli_scheduler import (
    ORDERING_SERIAL,
    NullScheduler,
    ScheduledSpec,
    SchedulingEvidence,
    unevaluated_scheduling,
)
from legalforecast.multiharness.spec import LINUX_SYSTEMD_SCOPE_CONTAINMENT

_RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "legalforecast"
    / "multiharness"
    / "local_cli_runtime.py"
)
_CANARY_ENV = {
    "OPENAI_API_KEY": "ambient-openai-canary",
    "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    "AWS_SECRET_ACCESS_KEY": "ambient-aws-canary",
    "SSH_AUTH_SOCK": "/tmp/ambient-ssh.sock",
    "HOME": "/private/operator-home",
    "PATH": "/usr/bin",
    "LC_CTYPE": "C.UTF-8",
}


def test_runtime_module_does_not_import_publication_envelopes() -> None:
    tree = ast.parse(_RUNTIME_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    blocked = {
        "legalforecast.contracts",
        "legalforecast.multiharness.community",
        "legalforecast.ingestion",
        "legalforecast.labeling",
        "legalforecast.cli",
    }
    assert not any(
        name in blocked or any(name.startswith(f"{prefix}.") for prefix in blocked)
        for name in imported
    )


def test_spec_identity_is_reproducible_and_resume_mismatch_fails(
    tmp_path: Path,
) -> None:
    spec = _spec(
        tmp_path,
        script=_write_script(tmp_path, "print('ok')"),
        auth_profile=FIXTURE_NONE,
    )
    first = spec.spec_sha256()
    second = spec.spec_sha256()
    assert first == second
    assert first.startswith("sha256:")
    mismatched = LocalCliRunSpec(
        spec_id=spec.spec_id,
        manifest=spec.manifest,
        auth_profile=spec.auth_profile,
        extra_args=spec.extra_args,
        timeout_seconds=spec.timeout_seconds,
        resume_of_spec_sha256="sha256:" + "a" * 64,
    )
    with pytest.raises(LocalCliRuntimeError, match="resume token"):
        execute_local_cli(mismatched, tmp_path / "scratch", parent_env=_CANARY_ENV)


def test_fixture_cli_does_not_inherit_ambient_environment(tmp_path: Path) -> None:
    script = _write_script(
        tmp_path,
        "import json, os, sys; json.dump(dict(os.environ), sys.stdout)",
    )
    result = execute_local_cli(
        _spec(tmp_path, script=script, auth_profile=FIXTURE_NONE),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert result.status == "completed"
    assert result.exit_code == 0
    assert "OPENAI_API_KEY" not in captured
    assert "ANTHROPIC_API_KEY" not in captured
    assert "AWS_SECRET_ACCESS_KEY" not in captured
    assert "SSH_AUTH_SOCK" not in captured
    assert captured["HOME"].endswith("adapter-home")
    assert result.cwd == str((tmp_path / "scratch").resolve())
    public = result.to_public_record()
    assert "stdout" not in public
    assert public["auth_profile"] == FIXTURE_NONE


def test_published_api_key_is_projected_and_redacted_from_public_receipt(
    tmp_path: Path,
) -> None:
    secret = "projected-openai-key-7Jx9"
    script = _write_script(
        tmp_path,
        "import json, os, sys; json.dump(dict(os.environ), sys.stdout)",
    )
    result = execute_local_cli(
        _spec(
            tmp_path,
            script=script,
            auth_profile=PUBLISHED_API_KEY,
            supported=(PUBLISHED_API_KEY,),
            profile_env_vars=((PUBLISHED_API_KEY, ("OPENAI_API_KEY",)),),
        ),
        tmp_path / "scratch",
        credential_source=StaticCredentialSource({"OPENAI_API_KEY": secret}),
        parent_env=_CANARY_ENV,
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert captured["OPENAI_API_KEY"] == secret
    assert "ANTHROPIC_API_KEY" not in captured
    public = json.dumps(result.to_public_record())
    assert secret not in public
    assert "OPENAI_API_KEY" not in public


def test_fake_claude_and_codex_streams_cover_success_malformed_timeout_and_partial(
    tmp_path: Path,
) -> None:
    claude = _write_script(
        tmp_path,
        """
import json, sys
content = [{"type": "text", "text": "ok"}]
payload = {"type": "assistant", "message": {"content": content}}
print(json.dumps(payload))
print(json.dumps({"type": "result", "subtype": "success"}))
""",
        name="fake-claude.py",
    )
    success = execute_local_cli(
        _spec(tmp_path, script=claude, auth_profile=FIXTURE_NONE),
        tmp_path / "claude-ok",
        parent_env=_CANARY_ENV,
    )
    assert success.status == "completed"
    assert b'"type": "result"' in success.stdout

    mixed = _write_script(
        tmp_path,
        "print('not-json'); print('{\"type\":\"item\"}')",
        name="fake-codex-mixed.py",
    )
    malformed = execute_local_cli(
        _spec(tmp_path, script=mixed, auth_profile=FIXTURE_NONE),
        tmp_path / "codex-mixed",
        parent_env=_CANARY_ENV,
    )
    assert malformed.status == "completed"
    assert b"not-json" in malformed.stdout
    assert b'"type":"item"' in malformed.stdout

    sleeper = _write_script(
        tmp_path,
        "import time; time.sleep(30)",
        name="fake-claude-hang.py",
    )
    timed_out = execute_local_cli(
        LocalCliRunSpec(
            spec_id="timeout",
            manifest=_manifest(sleeper, (FIXTURE_NONE,)),
            auth_profile=FIXTURE_NONE,
            timeout_seconds=0.2,
        ),
        tmp_path / "timeout",
        parent_env=_CANARY_ENV,
        termination_grace_seconds=0.1,
    )
    assert timed_out.status == "timed_out"
    assert timed_out.timed_out is True

    partial = _write_script(
        tmp_path,
        'print(\'{"type":"partial"}\'); raise SystemExit(2)',
        name="fake-codex-partial.py",
    )
    nonzero = execute_local_cli(
        _spec(tmp_path, script=partial, auth_profile=FIXTURE_NONE),
        tmp_path / "partial",
        parent_env=_CANARY_ENV,
    )
    assert nonzero.status == "nonzero"
    assert nonzero.exit_code == 2
    assert b'"type":"partial"' in nonzero.stdout


def test_scheduler_hooks_run_without_implementing_sequencing(tmp_path: Path) -> None:
    events: list[str] = []

    class Recorder(NullScheduler):
        def before_execute(self, spec: ScheduledSpec) -> None:
            events.append(f"before:{spec.spec_id}")

        def after_execute(
            self,
            spec: ScheduledSpec,
            result: object,
        ) -> SchedulingEvidence:
            status = getattr(result, "status", "unknown")
            events.append(f"after:{spec.spec_id}:{status}")
            return super().after_execute(spec, result)

    script = _write_script(tmp_path, "print('ok')")
    result = execute_local_cli(
        _spec(tmp_path, script=script, auth_profile=FIXTURE_NONE),
        tmp_path / "scratch",
        scheduler=Recorder(),
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    assert events == ["before:run-1", "after:run-1:completed"]


def test_stdin_task_input_is_delivered(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "import sys; sys.stdout.write(sys.stdin.read())")
    spec = LocalCliRunSpec(
        spec_id="stdin",
        manifest=_manifest(script, (FIXTURE_NONE,)),
        auth_profile=FIXTURE_NONE,
        stdin_bytes=b'{"task":"fixture"}',
    )
    result = execute_local_cli(spec, tmp_path / "scratch", parent_env=_CANARY_ENV)
    assert result.stdout == b'{"task":"fixture"}'


def test_missing_profile_stops_before_spawn(tmp_path: Path) -> None:
    class ExplodingSource(StaticCredentialSource):
        def fetch_projected_env(self, profile: object) -> dict[str, str]:
            raise AssertionError("credential fetch must not run")

    with pytest.raises(LocalCliRuntimeError, match="canonical profile ID"):
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="missing",
                manifest=_manifest(
                    _write_script(tmp_path, "print('should-not-run')"),
                    (PUBLISHED_API_KEY,),
                    profile_env_vars=((PUBLISHED_API_KEY, ("OPENAI_API_KEY",)),),
                ),
                auth_profile="",
            ),
            tmp_path / "scratch",
            credential_source=ExplodingSource({"OPENAI_API_KEY": "secret"}),
            parent_env=_CANARY_ENV,
        )


def test_systemd_containment_is_refused(tmp_path: Path) -> None:
    script = _write_script(tmp_path, "print('should-not-run')")
    with pytest.raises(LocalCliRuntimeError, match="posix_process_group"):
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="systemd",
                manifest=_manifest(script, (FIXTURE_NONE,)),
                auth_profile=FIXTURE_NONE,
                host_process_containment=LINUX_SYSTEMD_SCOPE_CONTAINMENT,
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )


def _spec(
    tmp_path: Path,
    *,
    script: Path,
    auth_profile: str,
    supported: tuple[str, ...] | None = None,
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> LocalCliRunSpec:
    del tmp_path
    profiles = supported if supported is not None else (auth_profile,)
    return LocalCliRunSpec(
        spec_id="run-1",
        manifest=_manifest(script, profiles, profile_env_vars=profile_env_vars),
        auth_profile=auth_profile,
    )


def _manifest(
    script: Path,
    supported: tuple[str, ...],
    *,
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> LocalCliAdapterManifest:
    path = script.resolve()
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(path)),
        executable=executable_pin_for(path, version="0.1.0"),
        supported_auth_profiles=supported,
        profile_env_vars=profile_env_vars,
        version_probe_args=_version_probe_args(path),
    )


def test_run_spec_service_binds_receipt_identity_without_ambient_env(
    tmp_path: Path,
) -> None:
    bindir = tmp_path / "bin"
    _write_path_cli(
        bindir / "claude",
        "import json, os, sys; json.dump({'ok': True}, sys.stdout)",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    spec = RunSpec(
        spec_id="run-spec-1",
        argv=("claude", "-p", "prompt"),
        working_directory=workspace,
        timeout_seconds=5,
    )
    parent = dict(_CANARY_ENV)
    parent["PATH"] = f"{bindir}{os.pathsep}/usr/bin"
    receipt = LocalCliExecutionService(parent_env=parent).execute(spec)

    assert receipt.spec_sha256 == spec.spec_sha256
    assert receipt.status == "succeeded"
    assert receipt.executable_name == "claude"
    assert receipt.failure_class is None
    assert '"ok":true' in receipt.stdout.replace(" ", "")
    assert "ambient-openai-canary" not in receipt.stdout
    public = receipt.to_public_record()
    assert "stdout" not in public
    assert "ANTHROPIC_API_KEY" not in str(public)


def test_run_spec_service_delivers_stdin_and_maps_timeout_and_nonzero(
    tmp_path: Path,
) -> None:
    bindir = tmp_path / "bin"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    parent = dict(_CANARY_ENV)
    parent["PATH"] = f"{bindir}{os.pathsep}/usr/bin"
    _write_path_cli(
        bindir / "echo-cli",
        "import sys; sys.stdout.write(sys.stdin.read())",
    )
    echoed = LocalCliExecutionService(parent_env=parent).execute(
        RunSpec(
            spec_id="stdin-1",
            argv=("echo-cli",),
            working_directory=workspace,
            stdin_bytes=b'{"task":"fixture"}',
            timeout_seconds=5,
        )
    )
    assert echoed.status == "succeeded"
    assert echoed.stdout == '{"task":"fixture"}'
    assert echoed.failure_class is None

    _write_path_cli(bindir / "hang-cli", "import time; time.sleep(30)")
    timed_out = LocalCliExecutionService(
        parent_env=parent,
        termination_grace_seconds=0.2,
    ).execute(
        RunSpec(
            spec_id="hang-1",
            argv=("hang-cli",),
            working_directory=workspace,
            timeout_seconds=0.4,
        )
    )
    assert timed_out.status == "timeout"
    assert timed_out.failure_class is None

    _write_path_cli(bindir / "fail-cli", "raise SystemExit(2)")
    failed = LocalCliExecutionService(parent_env=parent).execute(
        RunSpec(
            spec_id="fail-1",
            argv=("fail-cli",),
            working_directory=workspace,
            timeout_seconds=5,
        )
    )
    assert failed.status == "failed"
    assert failed.returncode == 2
    assert failed.failure_class is None


def test_run_spec_service_preserves_empty_argv_tokens(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    parent = dict(_CANARY_ENV)
    parent["PATH"] = f"{bindir}{os.pathsep}/usr/bin"
    _write_path_cli(
        bindir / "claude",
        "import json, sys; json.dump(sys.argv, sys.stdout)",
    )
    spec = RunSpec(
        spec_id="empty-token",
        argv=("claude", "--tools", "", "--print"),
        working_directory=workspace,
        timeout_seconds=5,
    )
    receipt = LocalCliExecutionService(parent_env=parent).execute(spec)
    assert receipt.status == "succeeded"
    assert json.loads(receipt.stdout) == [
        str(bindir / "claude"),
        "--tools",
        "",
        "--print",
    ]


def test_execution_receipt_maps_signal_exit_and_timed_out_status(
    tmp_path: Path,
) -> None:
    spec = RunSpec(
        spec_id="map-1",
        argv=("claude",),
        working_directory=tmp_path,
        timeout_seconds=5,
    )
    signaled = execution_receipt_from_runtime(
        spec,
        _execution_result(exit_code=-9, status="nonzero"),
    )
    assert signaled.status == "failed"
    assert signaled.returncode is None
    assert signaled.spec_sha256 == spec.spec_sha256

    timed_out = execution_receipt_from_runtime(
        spec,
        _execution_result(exit_code=None, status="timed_out", timed_out=False),
    )
    assert timed_out.status == "timeout"
    assert timed_out.returncode is None


def test_run_spec_service_maps_missing_executable_to_failed_receipt(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    parent = dict(_CANARY_ENV)
    parent["PATH"] = str(empty)
    spec = RunSpec(
        spec_id="missing",
        argv=("definitely-not-installed-cli",),
        working_directory=workspace,
        timeout_seconds=5,
    )
    receipt = LocalCliExecutionService(parent_env=parent).execute(spec)
    assert receipt.status == "failed"
    assert receipt.returncode is None
    assert receipt.spec_sha256 == spec.spec_sha256
    assert "could not be launched" in receipt.stderr
    assert receipt.failure_class is None


def test_run_spec_service_rejects_symlink_working_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    parent = dict(_CANARY_ENV)
    spec = RunSpec(
        spec_id="symlink-workspace",
        argv=("claude",),
        working_directory=link,
        timeout_seconds=5,
    )
    receipt = LocalCliExecutionService(parent_env=parent).execute(spec)
    assert receipt.status == "failed"
    assert "real directory" in receipt.stderr


def test_run_spec_service_rejects_symlink_scratch_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "local-cli-scratch").symlink_to(outside)
    parent = dict(_CANARY_ENV)
    spec = RunSpec(
        spec_id="symlink-scratch",
        argv=("claude",),
        working_directory=workspace,
        timeout_seconds=5,
    )
    receipt = LocalCliExecutionService(parent_env=parent).execute(spec)
    assert receipt.status == "failed"
    assert "symlink" in receipt.stderr


def test_run_spec_service_maps_missing_parent_workspace_to_failed_receipt(
    tmp_path: Path,
) -> None:
    spec = RunSpec(
        spec_id="missing-parent",
        argv=("claude",),
        working_directory=tmp_path / "nope" / "workspace",
        timeout_seconds=5,
    )
    receipt = LocalCliExecutionService(parent_env=dict(_CANARY_ENV)).execute(spec)
    assert receipt.status == "failed"
    assert "real directory" in receipt.stderr


def _execution_result(
    *,
    exit_code: int | None,
    status: str,
    timed_out: bool = False,
) -> LocalCliExecutionResult:
    return LocalCliExecutionResult(
        spec_id="map-1",
        spec_sha256="sha256:" + "a" * 64,
        auth_profile=FIXTURE_NONE,
        status=status,
        exit_code=exit_code,
        stdout=b"",
        stderr=b"",
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=timed_out,
        cwd="scratch",
        duration_ms=1,
        cost_usd=None,
        containment_establishment="established",
        executable_sha256="b" * 64,
        executable_version="0.1.0",
        scheduling=unevaluated_scheduling(
            requested_max_concurrency=1,
            requested_ordering=ORDERING_SERIAL,
        ),
    )


def _version_probe_args(path: Path) -> tuple[str, ...]:
    if path.name == "local_cli_fake_cli.py":
        return ("--mode", "version")
    return ()


def _write_script(tmp_path: Path, body: str, *, name: str = "cli.py") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def _write_path_cli(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"#!{sys.executable}\n{body.strip()}\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path
