"""Attack tests: swapped or drifted executables must refuse before spawn."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_identity import (
    LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION,
    ExecutableIdentityPin,
    bind_executable_identity,
    executable_pin_for,
    sha256_file,
    verify_executable_digest,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)
from legalforecast.multiharness.local_cli_scheduler import (
    NullScheduler,
    ScheduledSpec,
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


def test_symlink_shim_keeps_pin_basename_and_hashes_target_bytes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "cli.js"
    target.write_bytes(_FAKE_CLI.read_bytes())
    target.chmod(0o755)
    shim = tmp_path / "claude"
    shim.symlink_to(target)
    pin = executable_pin_for(shim, version="0.1.0")
    assert pin.basename == "claude"
    assert pin.sha256 == sha256_file(target)
    observed = bind_executable_identity(
        pin,
        (str(shim), "--mode", "succeed-json"),
        probe=False,
        parent_env=_CANARY_ENV,
    )
    assert observed.resolved_argv[0] == str(shim)
    assert Path(observed.resolved_argv[0]).name == "claude"
    assert observed.sha256 == pin.sha256

    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="shim",
            manifest=LocalCliAdapterManifest(
                adapter_id="fixture-cli",
                display_name="Fixture CLI",
                adapter_version="0.1.0",
                command=(sys.executable, str(shim)),
                executable=pin,
                supported_auth_profiles=(FIXTURE_NONE,),
            ),
            auth_profile=FIXTURE_NONE,
            extra_args=("--mode", "succeed-json"),
        ),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    assert result.executable_sha256 == pin.sha256

    located = bind_executable_identity(
        pin,
        ("claude",),
        probe=False,
        parent_env={"PATH": str(shim.parent)},
    )
    assert located.resolved_argv[0] == str(shim)
    assert located.sha256 == pin.sha256


def test_extra_arg_sharing_cli_basename_does_not_refuse(tmp_path: Path) -> None:
    path = _FAKE_CLI.resolve()
    pin = executable_pin_for(path, version="0.1.0")
    extra_file = str(tmp_path / path.name)
    observed = bind_executable_identity(
        pin,
        (sys.executable, str(path), "--output", path.name, extra_file),
        probe=False,
        parent_env=_CANARY_ENV,
    )
    assert observed.resolved_argv[1] == str(path)
    assert observed.resolved_argv[3] == path.name
    assert observed.resolved_argv[4] == extra_file

    result = execute_local_cli(
        LocalCliRunSpec(
            spec_id="extra-basename",
            manifest=_fake_manifest(),
            auth_profile=FIXTURE_NONE,
            extra_args=("--mode", "succeed-json", "--pid-file", path.name),
        ),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"


def test_relative_executable_path_is_refused(tmp_path: Path) -> None:
    script = tmp_path / "nested" / "cli.py"
    script.parent.mkdir()
    script.write_text("print('ok')\n", encoding="utf-8")
    pin = executable_pin_for(script, version="0.1.0")
    with pytest.raises(LocalCliRuntimeError, match="absolute"):
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="relative",
                manifest=LocalCliAdapterManifest(
                    adapter_id="fixture-cli",
                    display_name="Fixture CLI",
                    adapter_version="0.1.0",
                    command=(sys.executable, "nested/cli.py"),
                    executable=pin,
                    supported_auth_profiles=(FIXTURE_NONE,),
                ),
                auth_profile=FIXTURE_NONE,
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )


def test_omitted_probe_version_is_mismatch(tmp_path: Path) -> None:
    script = tmp_path / "cli.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                "    'schema_version':",
                f"    {LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION!r},",
                "    'basename': 'cli.py',",
                "}))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LocalCliRuntimeError, match="executable version mismatch"):
        execute_local_cli(
            _spec_for(script, version_probe_args=("--mode", "version")),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )


def test_omitted_probe_events_refuse_when_pin_lists_allowed_events(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "task-ran"
    script = _probe_only_script(tmp_path, sentinel, extra_fields=())
    pin = executable_pin_for(script.resolve(), allowed_events=("result",))
    with pytest.raises(LocalCliRuntimeError, match="identity probe omitted events"):
        execute_local_cli(
            _spec_for(
                script,
                extra_args=("--mode", "would-run"),
                executable=pin,
                version_probe_args=("--mode", "version"),
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_reported_empty_probe_events_are_accepted(tmp_path: Path) -> None:
    sentinel = tmp_path / "task-ran"
    script = _probe_only_script(tmp_path, sentinel, extra_fields=("'events': [],",))
    pin = executable_pin_for(script.resolve(), allowed_events=("result",))
    result = execute_local_cli(
        _spec_for(
            script,
            extra_args=("--mode", "would-run"),
            executable=pin,
            version_probe_args=("--mode", "version"),
        ),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    assert result.status == "completed"
    assert sentinel.exists()


def test_unreadable_executable_refuses_without_leaking_host_path(
    tmp_path: Path,
) -> None:
    script = tmp_path / "cli.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    pin = executable_pin_for(script, version="0.1.0")
    script.chmod(0o000)
    try:
        script.read_bytes()
    except OSError:
        pass
    else:
        script.chmod(0o600)
        pytest.skip("mode 0o000 is not enforced here (root or permissive mount)")
    try:
        with pytest.raises(LocalCliRuntimeError) as excinfo:
            execute_local_cli(
                _spec_for(script, executable=pin),
                tmp_path / "scratch",
                parent_env=_CANARY_ENV,
            )
    finally:
        script.chmod(0o600)
    assert "executable bytes could not be read" in str(excinfo.value)
    assert str(tmp_path) not in str(excinfo.value)
    assert "cli.py" not in str(excinfo.value)


def test_probe_launch_failure_refuses_without_leaking_host_path(
    tmp_path: Path,
) -> None:
    """A probe that cannot exec must not surface OSError's host-path text."""

    script = tmp_path / "cli.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    pin = executable_pin_for(script, version="0.1.0")
    with pytest.raises(LocalCliRuntimeError) as excinfo:
        execute_local_cli(
            LocalCliRunSpec(
                spec_id="probe-launch",
                manifest=LocalCliAdapterManifest(
                    adapter_id="fixture-cli",
                    display_name="Fixture CLI",
                    adapter_version="0.1.0",
                    # argv[0] is the pinned script itself, which is not
                    # executable, so exec fails inside the probe launch.
                    command=(str(script.resolve()),),
                    executable=pin,
                    supported_auth_profiles=(FIXTURE_NONE,),
                    version_probe_args=("--mode", "version"),
                ),
                auth_profile=FIXTURE_NONE,
            ),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
        )
    assert "identity probe could not be launched" in str(excinfo.value)
    assert str(tmp_path) not in str(excinfo.value)


def test_spawn_time_digest_recheck_refuses_a_swap_after_the_first_bind(
    tmp_path: Path,
) -> None:
    """The pre-Popen re-check must still catch bytes swapped after binding."""

    script = tmp_path / "cli.py"
    script.write_bytes(_FAKE_CLI.read_bytes())
    pin = executable_pin_for(script, version="0.1.0")
    sentinel = tmp_path / "scratch" / "swapped-ran"

    class _SwapBetweenBindAndSpawn(NullScheduler):
        def before_execute(self, spec: ScheduledSpec) -> None:
            del spec
            script.write_text(
                f"from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('swapped')\n",
                encoding="utf-8",
            )

    with pytest.raises(LocalCliRuntimeError, match="executable digest mismatch"):
        execute_local_cli(
            _spec_for(script, executable=pin),
            tmp_path / "scratch",
            parent_env=_CANARY_ENV,
            scheduler=_SwapBetweenBindAndSpawn(),
        )
    assert not sentinel.exists()


def test_digest_only_recheck_takes_no_environment(tmp_path: Path) -> None:
    """The spawn-time helper accepts a PATH string, not a credentialed env."""

    path = _FAKE_CLI.resolve()
    pin = executable_pin_for(path, version="0.1.0")
    observed = verify_executable_digest(
        pin,
        (sys.executable, str(path)),
        search_path="/usr/bin",
    )
    assert observed.sha256 == pin.sha256
    signature = inspect.signature(verify_executable_digest, eval_str=True)
    assert set(signature.parameters) == {"pin", "argv", "search_path"}
    assert signature.parameters["search_path"].annotation is str
    # No probe means no child process and no environment to project into one.
    assert "parent_env" not in signature.parameters
    assert "probe" not in signature.parameters


def _probe_only_script(
    tmp_path: Path,
    sentinel: Path,
    *,
    extra_fields: tuple[str, ...],
) -> Path:
    """Write a CLI that answers ``--mode version`` and otherwise runs a task."""

    script = tmp_path / "cli.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "from pathlib import Path",
                "if sys.argv[1:] == ['--mode', 'version']:",
                "    print(json.dumps({",
                "        'schema_version':",
                f"        {LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION!r},",
                "        'basename': 'cli.py',",
                "        'version': '0.1.0',",
                *[f"        {field}" for field in extra_fields],
                "    }))",
                "    raise SystemExit(0)",
                f"Path({str(sentinel)!r}).write_text('task')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script


def test_identity_probe_uses_isolated_home(tmp_path: Path) -> None:
    script = tmp_path / "cli.py"
    script.write_text(
        "\n".join(
            [
                "import json, os",
                "from pathlib import Path",
                "Path('probe-home.txt').write_text(os.environ.get('HOME', ''))",
                "print(json.dumps({",
                "    'schema_version':",
                f"    {LOCAL_CLI_IDENTITY_PROBE_SCHEMA_VERSION!r},",
                "    'basename': 'cli.py',",
                "    'version': '0.1.0',",
                "    'capabilities': ['json_output'],",
                "}))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    scratch = tmp_path / "scratch"
    execute_local_cli(
        _spec_for(
            script,
            extra_args=("--mode", "version"),
            version_probe_args=("--mode", "version"),
        ),
        scratch,
        parent_env=_CANARY_ENV,
    )
    recorded = (scratch / "probe-home.txt").read_text(encoding="utf-8")
    assert recorded.endswith("adapter-home")
    assert "/private/operator-home" not in recorded


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
