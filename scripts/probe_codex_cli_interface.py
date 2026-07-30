#!/usr/bin/env python3
"""Probe the installed Codex CLI through allowlisted public interface commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = "legalforecast.codex_cli_interface_characterization.v1"
REQUIRED_EXEC_FLAGS = {
    "--cd",
    "--ephemeral",
    "--ignore-rules",
    "--ignore-user-config",
    "--json",
    "--model",
    "--sandbox",
    "--strict-config",
}
REQUIRED_SANDBOX_MODES = {
    "danger-full-access",
    "read-only",
    "workspace-write",
}
RECORDED_FEATURES = {
    "apps",
    "hooks",
    "image_generation",
    "memories",
    "multi_agent",
    "plugins",
    "shell_tool",
    "unified_exec",
}
SAFE_ENVIRONMENT_KEYS = {
    "CODEX_HOME",
    "HOME",
    "NO_COLOR",
    "PATH",
    "TERM",
}

type JsonObject = dict[str, Any]


class CharacterizationDriftError(RuntimeError):
    """Raised when installed Codex identity or interface differs from the pin."""


def parse_subcommands(help_text: str) -> list[str]:
    """Extract command names without retaining help prose."""

    commands: list[str] = []
    in_commands = False
    for line in help_text.splitlines():
        if line == "Commands:":
            in_commands = True
            continue
        if in_commands and line and not line.startswith(" "):
            break
        if in_commands and (match := re.match(r"^  ([a-z][a-z0-9-]*)\s", line)):
            commands.append(match.group(1))
    return sorted(commands)


def parse_long_flags(help_text: str) -> list[str]:
    """Extract stable long-option names without retaining paths or values."""

    return sorted(set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", help_text)))


def parse_feature_rows(feature_text: str) -> dict[str, dict[str, object]]:
    """Parse the public ``features list`` table."""

    rows: dict[str, dict[str, object]] = {}
    for line in feature_text.splitlines():
        match = re.fullmatch(r"(\S+)\s+(.+?)\s+(true|false)", line.strip())
        if match is None:
            continue
        name, stage, enabled = match.groups()
        rows[name] = {"stage": stage, "enabled": enabled == "true"}
    return dict(sorted(rows.items()))


def build_safe_parser_probe(
    *,
    executable: Path,
    expected_model: str,
    workspace: Path,
) -> list[str]:
    """Build a help-only parse check for every required execution control."""

    return [
        str(executable),
        "exec",
        "--json",
        "--ephemeral",
        "--model",
        expected_model,
        "--cd",
        str(workspace),
        "--sandbox",
        "read-only",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--help",
    ]


def assert_matches_fixture(observed: JsonObject, expected: JsonObject) -> None:
    """Reject any identity, interface, or requested-model drift."""

    if observed != expected:
        raise CharacterizationDriftError(
            "Codex CLI characterization drift detected; review a sanitized "
            "interface observation before changing the pin"
        )


def check_fixture(
    *,
    executable_name: str,
    expected_model: str,
    fixture_path: Path,
) -> JsonObject:
    """Load the trusted pin before observing, then require an exact match."""

    expected = _load_fixture(fixture_path)
    _require_expected_model(expected, expected_model)
    observation = observe(
        executable_name,
        expected_model,
        expected_fixture=expected,
    )
    assert_matches_fixture(observation, expected)
    return observation


def observe(
    executable_name: str,
    expected_model: str,
    *,
    expected_fixture: JsonObject | None = None,
) -> JsonObject:
    """Collect requested interface facts without claiming external containment."""

    if expected_fixture is not None:
        _require_expected_model(expected_fixture, expected_model)
    executable = _resolve_executable(executable_name)
    source_mode = stat.S_IMODE(executable.stat().st_mode)
    source_sha256 = _sha256_file(executable)
    if expected_fixture is not None:
        _preflight_expected_binary(
            executable,
            source_mode=source_mode,
            source_sha256=source_sha256,
            expected=expected_fixture,
        )

    with tempfile.TemporaryDirectory(
        prefix=".codex-cli-interface-",
        dir=Path.cwd(),
    ) as temporary_directory:
        isolated_root = Path(temporary_directory)
        workspace = isolated_root / "workspace"
        codex_home = isolated_root / "codex-home"
        home = isolated_root / "home"
        staged_executable = isolated_root / executable.name
        workspace.mkdir()
        codex_home.mkdir()
        home.mkdir()
        _stage_executable(
            executable,
            staged_executable,
            expected_sha256=source_sha256,
            expected_mode=source_mode,
        )
        environment = {
            "CODEX_HOME": str(codex_home),
            "HOME": str(home),
            "NO_COLOR": "1",
            "PATH": os.environ.get("PATH", ""),
            "TERM": "dumb",
        }
        commands = [
            [str(staged_executable), "--version"],
            [str(staged_executable), "--help"],
            [str(staged_executable), "exec", "--help"],
            [str(staged_executable), "features", "list"],
            build_safe_parser_probe(
                executable=staged_executable,
                expected_model=expected_model,
                workspace=workspace,
            ),
        ]
        allowed_commands = {tuple(command) for command in commands}
        try:
            version = run_allowlisted_interface_command(
                commands[0],
                environment,
                allowed_commands=allowed_commands,
            ).strip()
            root_help = run_allowlisted_interface_command(
                commands[1],
                environment,
                allowed_commands=allowed_commands,
            )
            exec_help = run_allowlisted_interface_command(
                commands[2],
                environment,
                allowed_commands=allowed_commands,
            )
            feature_text = run_allowlisted_interface_command(
                commands[3],
                environment,
                allowed_commands=allowed_commands,
            )
            parser_help = run_allowlisted_interface_command(
                commands[4],
                environment,
                allowed_commands=allowed_commands,
            )
        finally:
            _verify_staged_executable(
                staged_executable,
                expected_sha256=source_sha256,
                expected_mode=source_mode,
            )

    exec_flags = set(parse_long_flags(exec_help))
    missing_flags = sorted(REQUIRED_EXEC_FLAGS - exec_flags)
    if missing_flags:
        raise CharacterizationDriftError(
            f"Codex CLI is missing required execution flags: {missing_flags}"
        )
    sandbox_modes = _parse_sandbox_modes(exec_help)
    if sandbox_modes != REQUIRED_SANDBOX_MODES:
        raise CharacterizationDriftError(
            "Codex CLI sandbox mode interface drift detected"
        )
    if _sha256_text(parser_help) != _sha256_text(exec_help):
        raise CharacterizationDriftError(
            "Codex CLI help-only combined parser probe changed output"
        )

    all_features = parse_feature_rows(feature_text)
    missing_features = sorted(RECORDED_FEATURES - all_features.keys())
    if missing_features:
        raise CharacterizationDriftError(
            f"Codex CLI is missing recorded feature rows: {missing_features}"
        )
    feature_rows = {name: all_features[name] for name in sorted(RECORDED_FEATURES)}

    return {
        "schema_version": SCHEMA_VERSION,
        "binary": {
            "distribution": _distribution(executable, version),
            "executable": executable.name,
            "mode": f"{source_mode:04o}",
            "sha256": source_sha256,
            "version": version,
        },
        "platform": {
            "machine": platform.machine(),
            "system": platform.system().lower(),
        },
        "interface": {
            "exec_help_sha256": _sha256_text(exec_help),
            "exec_long_flags": sorted(exec_flags),
            "parser_probe": {
                "help_only": True,
                "probe_requested_model_call": False,
                "sha256": _sha256_text(parser_help),
            },
            "required_exec_flags": sorted(REQUIRED_EXEC_FLAGS),
            "root_help_sha256": _sha256_text(root_help),
            "root_long_flags": parse_long_flags(root_help),
            "root_subcommands": parse_subcommands(root_help),
            "sandbox_modes": sorted(sandbox_modes),
        },
        "model": {
            "requested": expected_model,
            "resolved": None,
            "resolved_verification": ("requires a separately approved model request"),
        },
        "tools": {
            "feature_list_sha256": _sha256_text(feature_text),
            "feature_rows": feature_rows,
            "native_model_tool_inventory": None,
            "observed_without_model_request": False,
        },
        "identity": {
            "adapter_profile": "codex-cli-clean-native",
            "foreign_mcp_primary_loop": False,
            "openai_responses_adapter": False,
        },
        "activation": {
            "allowed": False,
            "blocking_gaps": [
                "native model tool inventory not observed for this binary",
                "resolved model not observed for this binary",
            ],
        },
        "safety": {
            "auth_paths_requested": False,
            "benchmark_task_paths_requested": False,
            "external_network_isolation_enforced": False,
            "no_external_behavior_claimed": True,
            "probe_kind": "version-help-feature-interface-only",
            "probe_requested_model_calls": 0,
            "provider_credential_environment_inherited": False,
        },
    }


def _resolve_executable(executable_name: str) -> Path:
    located = shutil.which(executable_name)
    if located is None:
        raise CharacterizationDriftError("Codex CLI executable is unavailable")
    return Path(located).resolve(strict=True)


def run_allowlisted_interface_command(
    command: list[str],
    environment: dict[str, str],
    *,
    allowed_commands: set[tuple[str, ...]],
) -> str:
    """Run one exact allowlisted interface command with the safe environment."""

    if tuple(command) not in allowed_commands:
        raise CharacterizationDriftError(
            "Codex CLI interface command is not allowlisted"
        )
    if set(environment) != SAFE_ENVIRONMENT_KEYS:
        raise CharacterizationDriftError(
            "Codex CLI interface environment is not the exact safe projection"
        )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise CharacterizationDriftError(
            "Codex CLI safe interface command failed without producing "
            "publishable stderr"
        )
    return completed.stdout


def _parse_sandbox_modes(exec_help: str) -> set[str]:
    sandbox_section = exec_help.split("--sandbox <SANDBOX_MODE>", maxsplit=1)
    if len(sandbox_section) != 2:
        return set()
    match = re.search(
        r"\[possible values: ([a-z0-9-, ]+)\]",
        sandbox_section[1],
    )
    if match is None:
        return set()
    return {item.strip() for item in match.group(1).split(",")}


def _distribution(executable: Path, version: str) -> JsonObject:
    parts = executable.parts
    try:
        cask_position = parts.index("Caskroom")
    except ValueError:
        return {"kind": "unknown", "package": "codex", "version": version}
    if len(parts) <= cask_position + 2 or parts[cask_position + 1] != "codex":
        return {"kind": "unknown", "package": "codex", "version": version}
    return {
        "kind": "homebrew-cask",
        "package": "codex",
        "version": parts[cask_position + 2],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stage_executable(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_mode: int,
) -> None:
    with (
        source.open("rb") as source_handle,
        destination.open("xb") as destination_handle,
    ):
        shutil.copyfileobj(source_handle, destination_handle)
    destination.chmod(expected_mode)
    _verify_staged_executable(
        destination,
        expected_sha256=expected_sha256,
        expected_mode=expected_mode,
    )


def _verify_staged_executable(
    executable: Path,
    *,
    expected_sha256: str,
    expected_mode: int,
) -> None:
    actual_stat = executable.stat()
    if not stat.S_ISREG(actual_stat.st_mode):
        raise CharacterizationDriftError("staged Codex CLI is not a regular file")
    if stat.S_IMODE(actual_stat.st_mode) != expected_mode:
        raise CharacterizationDriftError("staged Codex CLI mode drift detected")
    if _sha256_file(executable) != expected_sha256:
        raise CharacterizationDriftError("staged Codex CLI hash drift detected")


def _require_expected_model(expected: JsonObject, expected_model: str) -> None:
    model = expected.get("model")
    if not isinstance(model, dict):
        raise CharacterizationDriftError(
            "requested model drift detected before Codex CLI invocation"
        )
    model_record = cast(dict[str, object], model)
    if model_record.get("requested") != expected_model:
        raise CharacterizationDriftError(
            "requested model drift detected before Codex CLI invocation"
        )


def _preflight_expected_binary(
    executable: Path,
    *,
    source_mode: int,
    source_sha256: str,
    expected: JsonObject,
) -> None:
    binary = expected.get("binary")
    if not isinstance(binary, dict):
        raise CharacterizationDriftError("expected binary pin is missing")
    binary_record = cast(dict[str, object], binary)
    if binary_record.get("executable") != executable.name:
        raise CharacterizationDriftError(
            "Codex CLI executable identity drift detected before invocation"
        )
    if binary_record.get("mode") != f"{source_mode:04o}":
        raise CharacterizationDriftError(
            "Codex CLI mode drift detected before invocation"
        )
    if binary_record.get("sha256") != source_sha256:
        raise CharacterizationDriftError(
            "Codex CLI hash drift detected before invocation"
        )


def _load_fixture(path: Path) -> JsonObject:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise CharacterizationDriftError("characterization fixture must be an object")
    return cast(JsonObject, decoded)


def main() -> int:
    """Run the safe observation and optionally compare it to an exact fixture."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="codex")
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--print-observation", action="store_true")
    arguments = parser.parse_args()

    if arguments.check is not None:
        observation = check_fixture(
            executable_name=arguments.executable,
            expected_model=arguments.expected_model,
            fixture_path=arguments.check,
        )
    else:
        observation = observe(arguments.executable, arguments.expected_model)
    if arguments.print_observation:
        print(json.dumps(observation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
