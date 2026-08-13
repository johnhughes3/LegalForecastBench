from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliExecutionResult,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    NullScheduler,
    execute_local_cli,
)

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
        def before_execute(self, spec: LocalCliRunSpec) -> None:
            events.append(f"before:{spec.spec_id}")

        def after_execute(
            self,
            spec: LocalCliRunSpec,
            result: LocalCliExecutionResult,
        ) -> None:
            events.append(f"after:{spec.spec_id}:{result.status}")

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

    with pytest.raises(LocalCliRuntimeError):
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
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(script)),
        supported_auth_profiles=supported,
        profile_env_vars=profile_env_vars,
    )


def _write_script(tmp_path: Path, body: str, *, name: str = "cli.py") -> Path:
    path = tmp_path / name
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path
