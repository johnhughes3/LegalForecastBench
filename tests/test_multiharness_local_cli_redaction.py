"""Canary tests: planted secrets must not persist in any artifact byte."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import PUBLISHED_API_KEY
from legalforecast.multiharness.local_cli_environment import StaticCredentialSource
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_redaction import (
    PRIVATE_EXECUTION_DIR,
    REDACTED,
    artifact_dir_contains_secret,
    redact_bytes,
    redact_text,
    redaction_secret_values,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)

_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_ENV_SECRET = "planted-env-secret-H2b-7Jx9ZZ"
_ARG_SECRET = "planted-arg-secret-H2b-9xJ7QQ"
_PARENT_SECRET = "planted-parent-canary-H2b-4mK2WW"


def test_redaction_helpers_replace_exact_secret_bytes() -> None:
    values = redaction_secret_values(
        projected={"OPENAI_API_KEY": _ENV_SECRET},
        parent_env={"CANARY_PLANTED": _PARENT_SECRET, "PATH": "/usr/bin"},
        extra_args=(
            "--token",
            _ARG_SECRET,
            f"--token={_ARG_SECRET}",
            "--mode",
            "dump-env",
        ),
    )
    assert _ENV_SECRET in values
    assert _ARG_SECRET in values
    assert _PARENT_SECRET in values
    assert "/usr/bin" not in values
    blob = f"pre {_ENV_SECRET} {_ARG_SECRET} {_PARENT_SECRET} post"
    assert redact_text(blob, values) == f"pre {REDACTED} {REDACTED} {REDACTED} post"
    assert _ENV_SECRET.encode("utf-8") not in redact_bytes(blob.encode("utf-8"), values)


def test_planted_env_and_arg_secrets_are_absent_from_artifact_dir(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    parent = {
        "OPENAI_API_KEY": "ambient-openai-canary",
        "CANARY_PLANTED": _PARENT_SECRET,
        "PATH": os.environ.get("PATH", "/usr/bin"),
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
    }
    result = execute_local_cli(
        _canary_spec(),
        scratch,
        credential_source=StaticCredentialSource({"OPENAI_API_KEY": _ENV_SECRET}),
        parent_env=parent,
    )
    captured = json.loads(result.stdout.decode("utf-8"))
    assert captured["OPENAI_API_KEY"] == _ENV_SECRET
    assert result.stderr.decode("utf-8").strip() == _ARG_SECRET
    public = json.dumps(result.to_public_record())
    for secret in (_ENV_SECRET, _ARG_SECRET, _PARENT_SECRET):
        assert secret not in public
        assert not artifact_dir_contains_secret(scratch, secret)

    artifact_dir = scratch / PRIVATE_EXECUTION_DIR
    stdout_text = (artifact_dir / "stdout.transcript").read_text(encoding="utf-8")
    stderr_text = (artifact_dir / "stderr.transcript").read_text(encoding="utf-8")
    events_text = (artifact_dir / "events.jsonl").read_text(encoding="utf-8")
    receipt_text = (artifact_dir / "receipt.json").read_text(encoding="utf-8")
    assert REDACTED in stdout_text
    assert REDACTED in stderr_text
    assert REDACTED in events_text
    assert _ENV_SECRET not in stdout_text
    assert _ARG_SECRET not in stderr_text
    assert _ARG_SECRET not in events_text
    assert _ENV_SECRET not in receipt_text


def test_identity_refusal_error_and_artifacts_omit_planted_arg_secret(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    pin = executable_pin_for(_FAKE_CLI, version="0.1.0")
    tampered = replace(pin, sha256="ab" * 32)
    spec = _canary_spec()
    spec = LocalCliRunSpec(
        spec_id="canary-mismatch",
        manifest=replace(spec.manifest, executable=tampered),
        auth_profile=spec.auth_profile,
        extra_args=spec.extra_args,
    )
    with pytest.raises(LocalCliRuntimeError, match="executable digest mismatch") as exc:
        execute_local_cli(
            spec,
            scratch,
            credential_source=StaticCredentialSource({"OPENAI_API_KEY": _ENV_SECRET}),
            parent_env={
                "CANARY_PLANTED": _PARENT_SECRET,
                "PATH": os.environ.get("PATH", "/usr/bin"),
                "LC_CTYPE": "C.UTF-8",
            },
        )
    for secret in (_ENV_SECRET, _ARG_SECRET, _PARENT_SECRET):
        assert secret not in str(exc.value)
        assert not artifact_dir_contains_secret(scratch, secret)
    error_text = (scratch / PRIVATE_EXECUTION_DIR / "error.txt").read_text(
        encoding="utf-8"
    )
    assert "digest mismatch" in error_text
    assert _ARG_SECRET not in error_text
    assert oct(scratch.stat().st_mode)[-3:] == "700"
    assert oct((scratch / PRIVATE_EXECUTION_DIR).stat().st_mode)[-3:] == "700"


def test_combined_flag_assignment_is_redacted_from_artifacts(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    spec = _canary_spec()
    spec = LocalCliRunSpec(
        spec_id="canary-eq",
        manifest=spec.manifest,
        auth_profile=spec.auth_profile,
        extra_args=("--mode", "dump-env", f"--token={_ARG_SECRET}"),
    )
    result = execute_local_cli(
        spec,
        scratch,
        credential_source=StaticCredentialSource({"OPENAI_API_KEY": _ENV_SECRET}),
        parent_env={
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "LC_CTYPE": "C.UTF-8",
        },
    )
    assert _ARG_SECRET.encode("utf-8") in result.stderr
    assert not artifact_dir_contains_secret(scratch, _ARG_SECRET)
    events = (scratch / PRIVATE_EXECUTION_DIR / "events.jsonl").read_text(
        encoding="utf-8"
    )
    assert _ARG_SECRET not in events
    assert REDACTED in events


def test_planted_artifact_symlink_is_refused(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    leaked = tmp_path / "leaked"
    leaked.mkdir()
    scratch.mkdir(mode=0o700)
    (scratch / PRIVATE_EXECUTION_DIR).symlink_to(leaked)
    with pytest.raises(LocalCliRuntimeError, match="symlink"):
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="symlink",
                manifest=LocalCliAdapterManifest(
                    adapter_id="fixture-cli",
                    display_name="Fixture CLI",
                    adapter_version="0.1.0",
                    command=(sys.executable, str(_FAKE_CLI.resolve())),
                    executable=executable_pin_for(_FAKE_CLI, version="0.1.0"),
                    supported_auth_profiles=(PUBLISHED_API_KEY,),
                    profile_env_vars=((PUBLISHED_API_KEY, ("OPENAI_API_KEY",)),),
                    version_probe_args=("--mode", "version"),
                ),
                auth_profile=PUBLISHED_API_KEY,
                extra_args=("--mode", "succeed-json"),
            ),
            scratch,
            credential_source=StaticCredentialSource({"OPENAI_API_KEY": _ENV_SECRET}),
            parent_env={
                "PATH": os.environ.get("PATH", "/usr/bin"),
                "LC_CTYPE": "C.UTF-8",
            },
        )
    assert list(leaked.iterdir()) == []


def _canary_spec() -> LocalCliRunSpec:
    path = _FAKE_CLI.resolve()
    return LocalCliRunSpec(
        spec_id="canary",
        manifest=LocalCliAdapterManifest(
            adapter_id="fixture-cli",
            display_name="Fixture CLI",
            adapter_version="0.1.0",
            command=(sys.executable, str(path)),
            executable=executable_pin_for(path, version="0.1.0"),
            supported_auth_profiles=(PUBLISHED_API_KEY,),
            profile_env_vars=((PUBLISHED_API_KEY, ("OPENAI_API_KEY",)),),
            version_probe_args=("--mode", "version"),
        ),
        auth_profile=PUBLISHED_API_KEY,
        extra_args=("--mode", "dump-env", "--token", _ARG_SECRET),
    )
