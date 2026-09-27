"""Native help/version subprocess checks; no provider or authentication calls."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.local_cli_identity import (
    LocalCliIdentityError,
    executable_pin_for,
)
from legalforecast.multiharness.local_cli_probe import LocalCliProbeError
from legalforecast.multiharness.native_cli_preflight import (
    main,
    preflight_native_cli,
    preflight_solver_identity,
)

CLAUDE_FLAGS = (
    "--print --output-format --json-schema --tools --strict-mcp-config "
    "--no-session-persistence --setting-sources --model --add-dir --max-budget-usd"
)
CODEX_FLAGS = (
    "--json --color --ephemeral --skip-git-repo-check --strict-config "
    "--ignore-user-config --ignore-rules --sandbox --cd --model --config "
    "--output-last-message"
)


def _binary(tmp_path: Path, cli: str, *, missing: str = "") -> tuple[Path, str]:
    version = "2.1.283 (Claude Code)" if cli == "claude" else "codex-cli 0.147.0"
    flags = CLAUDE_FLAGS if cli == "claude" else CODEX_FLAGS
    flags = " ".join(flag for flag in flags.split() if flag != missing)
    path = tmp_path / cli
    help_args = ["--help"] if cli == "claude" else ["exec", "--help"]
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        f"log = pathlib.Path({str(tmp_path / 'calls.jsonl')!r})\n"
        "with log.open('a') as stream:\n"
        "    stream.write(json.dumps({'args': sys.argv[1:], "
        "'env': dict(os.environ), 'cwd': os.getcwd()}) + '\\n')\n"
        "if sys.argv[1:] == ['--version']:\n"
        f"    print({version!r})\n"
        f"elif sys.argv[1:] == {help_args!r}:\n"
        f"    print({flags!r})\n"
        "else:\n"
        "    raise SystemExit('MODEL COMMAND MUST NEVER RUN')\n",
        encoding="utf-8",
    )
    path.chmod(0o700)
    return path, version


@pytest.mark.parametrize("cli", ["claude", "codex"])
def test_native_probe_accepts_vendor_text_and_only_runs_safe_commands(
    tmp_path: Path, cli: str
) -> None:
    path, version = _binary(tmp_path, cli)
    scratch = tmp_path / "scratch"
    probe = preflight_native_cli(
        executable_pin_for(path, version=version),
        scratch_root=scratch,
        parent_env={
            "PATH": f"{tmp_path}{os.pathsep}/usr/bin",
            "OPENAI_API_KEY": "canary",
        },
        paid=True,
    )
    assert probe.pin_version_match and probe.pin_digest_match
    calls = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert [call["args"] for call in calls] == [
        ["--version"],
        ["--help"] if cli == "claude" else ["exec", "--help"],
    ]
    for call in calls:
        assert "OPENAI_API_KEY" not in call["env"]
        assert Path(call["env"]["HOME"]).is_relative_to(scratch)
        assert Path(call["cwd"]) == scratch


@pytest.mark.parametrize(
    "cli,flag",
    [
        ("claude", "--tools"),
        ("codex", "--strict-config"),
        ("claude", "--max-budget-usd"),
    ],
)
def test_missing_required_invocation_flag_refuses(
    tmp_path: Path, cli: str, flag: str
) -> None:
    path, version = _binary(tmp_path, cli, missing=flag)
    with pytest.raises(LocalCliProbeError, match=flag):
        preflight_native_cli(
            executable_pin_for(path, version=version),
            scratch_root=tmp_path / "scratch",
            parent_env={"PATH": f"{tmp_path}{os.pathsep}/usr/bin"},
            paid=True,
        )


@pytest.mark.parametrize("drift", ["version", "digest"])
def test_identity_drift_refuses(tmp_path: Path, drift: str) -> None:
    path, version = _binary(tmp_path, "claude")
    pin = executable_pin_for(path, version=version)
    pin = (
        replace(pin, version="wrong")
        if drift == "version"
        else replace(pin, sha256="0" * 64)
    )
    with pytest.raises(
        (LocalCliProbeError, LocalCliIdentityError), match=r"(version|digest|hash)"
    ):
        preflight_native_cli(
            pin,
            scratch_root=tmp_path / "scratch",
            parent_env={"PATH": f"{tmp_path}{os.pathsep}/usr/bin"},
        )
    if drift == "digest":
        assert not (tmp_path / "calls.jsonl").exists()


def test_repeatable_command_reports_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, version = _binary(tmp_path, "codex", missing="--ignore-rules")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}/usr/bin")
    pin = executable_pin_for(path, version=version)
    assert main(["--cli", "codex", "--version", version, "--sha256", pin.sha256]) == 1


def test_vendor_text_does_not_satisfy_custom_json_probe(tmp_path: Path) -> None:
    path, version = _binary(tmp_path, "claude")
    with pytest.raises(LocalCliIdentityError, match="framing"):
        preflight_solver_identity(
            executable_pin_for(path, version=version),
            native=False,
            version_probe_args=("--version",),
            scratch_root=tmp_path / "scratch",
            parent_env={"PATH": f"{tmp_path}{os.pathsep}/usr/bin"},
            requested_model="test-model",
            paid=False,
        )


@pytest.mark.parametrize("cli", ["claude", "codex"])
@pytest.mark.parametrize("missing", ["", "--model"])
def test_tier0_preflight_checks_native_vendor_interface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cli: str, missing: str
) -> None:
    from legalforecast.multiharness.tier0_runner import (
        Tier0ExecutableSpec,
        Tier0RunnerError,
        _preflight_executables,
    )
    from tests.test_multiharness_tier0_runner import (
        _install_fixture_binaries,
        _spec_record,
    )

    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    path, version = _binary(tmp_path / "bin", cli, missing=missing)
    pin = executable_pin_for(path, version=version)
    record = _spec_record(env)
    record["arms"][0].update(
        adapter="claude-code-clean-native" if cli == "claude" else "codex-cli-offline",
        solver_executable=cli,
        solver_executable_version=version,
        solver_executable_sha256="sha256:" + pin.sha256,
        version_probe_args=["--version"],
        settings={},
    )
    spec = Tier0ExecutableSpec.from_record(record)
    if missing:
        with pytest.raises(Tier0RunnerError, match="identity does not match"):
            _preflight_executables(spec, env)
    else:
        identities = _preflight_executables(spec, env)
        assert identities["arm-opaque-01"].version == version
        assert main(["--cli", cli, "--version", version, "--sha256", pin.sha256]) == 0
