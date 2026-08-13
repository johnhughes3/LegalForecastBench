"""Attack tests: swapped or drifted executables must refuse before spawn."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_identity import (
    LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION,
    ExecutableIdentityPin,
    executable_pin_for,
    sha256_file,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)

_IDENTITY_CLI = (
    Path(__file__).resolve().parent / "fixtures" / "local_cli_identity_cli.py"
)
_FAKE_CLI = Path(__file__).resolve().parent / "fixtures" / "local_cli_fake_cli.py"
_CANARY_ENV = {
    "PATH": "/usr/bin",
    "LC_CTYPE": "C.UTF-8",
    "HOME": "/private/operator-home",
}


def test_tampered_digest_refuses_before_spawn(tmp_path: Path) -> None:
    sentinel = tmp_path / "ran"
    pin = executable_pin_for(_IDENTITY_CLI, version="1.0.0")
    tampered = ExecutableIdentityPin(
        basename=pin.basename,
        version=pin.version,
        sha256="ab" * 32,
        distribution_kind=pin.distribution_kind,
    )
    with pytest.raises(LocalCliRuntimeError, match="executable digest mismatch"):
        execute_local_cli(
            _identity_spec(
                extra_args=("--mode", "would-run", "--sentinel", str(sentinel)),
                executable=tampered,
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_swapped_binary_bytes_refuse_before_spawn(tmp_path: Path) -> None:
    copy = tmp_path / "local_cli_identity_cli.py"
    copy.write_bytes(_IDENTITY_CLI.read_bytes())
    pin = executable_pin_for(copy, version="1.0.0")
    copy.write_text(
        "from pathlib import Path\nPath('ran').write_text('swapped')\n",
        encoding="utf-8",
    )
    sentinel = tmp_path / "scratch" / "ran"
    with pytest.raises(LocalCliRuntimeError, match="executable digest mismatch"):
        execute_local_cli(
            _spec_for(
                copy,
                extra_args=("--mode", "would-run"),
                executable=pin,
                version_probe_args=(),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()
    assert pin.sha256 != sha256_file(copy)


def test_version_mismatch_refuses_without_task_spend(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    with pytest.raises(LocalCliRuntimeError, match="executable version mismatch"):
        execute_local_cli(
            _identity_spec(
                extra_args=("--mode", "would-run", "--sentinel", str(sentinel)),
                executable=executable_pin_for(_IDENTITY_CLI, version="9.9.9"),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_unknown_identity_framing_refuses(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    script = tmp_path / "cli.py"
    script.write_text(
        "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "if '--mode' in sys.argv and 'version' in sys.argv:",
                "    print('not-json')",
                "    raise SystemExit(0)",
                f"Path({str(sentinel)!r}).write_text('task')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LocalCliRuntimeError, match="identity probe framing"):
        execute_local_cli(
            _spec_for(
                script,
                version_probe_args=("--mode", "version"),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_unknown_identity_schema_refuses(tmp_path: Path) -> None:
    script = tmp_path / "cli.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "print(json.dumps({",
                "    'schema_version':",
                "    'legalforecast.multiharness.local_cli_identity_probe.v0',",
                "    'version': '1.0.0',",
                "}))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LocalCliRuntimeError, match="unknown identity schema"):
        execute_local_cli(
            _spec_for(script, version_probe_args=("--mode", "version")),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION.endswith(".v1")


def test_missing_required_capability_refuses(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    with pytest.raises(LocalCliRuntimeError, match="required flag missing"):
        execute_local_cli(
            _identity_spec(
                extra_args=("--mode", "would-run", "--sentinel", str(sentinel)),
                required_capabilities=("no_session_persistence",),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_unknown_event_refuses_before_task(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    pin = executable_pin_for(
        _IDENTITY_CLI,
        version="1.0.0",
        allowed_events=("result",),
    )
    with pytest.raises(LocalCliRuntimeError, match="unknown event"):
        execute_local_cli(
            _identity_spec(
                extra_args=("--mode", "would-run", "--sentinel", str(sentinel)),
                executable=pin,
                version_probe_args=(
                    "--mode",
                    "identity",
                    "--report-events",
                    "weird",
                ),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_requested_model_drift_refuses_before_task(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    pin = executable_pin_for(
        _IDENTITY_CLI,
        version="1.0.0",
        allowed_models=("fixture-haiku",),
    )
    with pytest.raises(LocalCliRuntimeError, match="requested model drift"):
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="model-drift",
                manifest=LocalCliAdapterManifest(
                    adapter_id="fixture-cli",
                    display_name="Fixture CLI",
                    adapter_version="0.1.0",
                    command=(sys.executable, str(_IDENTITY_CLI)),
                    executable=pin,
                    supported_auth_profiles=(FIXTURE_NONE,),
                    version_probe_args=("--mode", "identity"),
                ),
                auth_profile=FIXTURE_NONE,
                extra_args=("--mode", "would-run", "--sentinel", str(sentinel)),
                requested_model="other-model",
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_matching_pin_runs_and_receipt_binds_identity(tmp_path: Path) -> None:
    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="ok",
            manifest=_fake_manifest(),
            auth_profile=FIXTURE_NONE,
            extra_args=("--mode", "succeed-json"),
        ),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    pin = executable_pin_for(_FAKE_CLI, version="0.1.0")
    assert result.status == "completed"
    assert result.executable_sha256 == pin.sha256
    assert result.executable_version == "0.1.0"
    public = result.to_public_record()
    assert public["executable_sha256"] == pin.sha256
    assert public["executable_version"] == "0.1.0"


def _identity_spec(
    *,
    extra_args: tuple[str, ...],
    executable: ExecutableIdentityPin | None = None,
    required_capabilities: tuple[str, ...] = (),
    version_probe_args: tuple[str, ...] = ("--mode", "identity"),
) -> LocalCliRunSpec:
    return _spec_for(
        _IDENTITY_CLI,
        extra_args=extra_args,
        executable=executable,
        version="1.0.0",
        version_probe_args=version_probe_args,
        required_capabilities=required_capabilities,
    )


def _spec_for(
    script: Path,
    *,
    extra_args: tuple[str, ...] = (),
    executable: ExecutableIdentityPin | None = None,
    version: str = "0.1.0",
    version_probe_args: tuple[str, ...] = (),
    required_capabilities: tuple[str, ...] = (),
) -> LocalCliRunSpec:
    path = script.resolve()
    pin = (
        executable
        if executable is not None
        else executable_pin_for(path, version=version)
    )
    return LocalCliRunSpec(
        spec_id="identity",
        manifest=LocalCliAdapterManifest(
            adapter_id="fixture-cli",
            display_name="Fixture CLI",
            adapter_version="0.1.0",
            command=(sys.executable, str(path)),
            executable=pin,
            supported_auth_profiles=(FIXTURE_NONE,),
            version_probe_args=version_probe_args,
            required_capabilities=required_capabilities,
        ),
        auth_profile=FIXTURE_NONE,
        extra_args=extra_args,
    )


def _fake_manifest() -> LocalCliAdapterManifest:
    path = _FAKE_CLI.resolve()
    return LocalCliAdapterManifest(
        adapter_id="fixture-cli",
        display_name="Fixture CLI",
        adapter_version="0.1.0",
        command=(sys.executable, str(path)),
        executable=executable_pin_for(path, version="0.1.0"),
        supported_auth_profiles=(FIXTURE_NONE,),
        version_probe_args=("--mode", "version"),
    )
