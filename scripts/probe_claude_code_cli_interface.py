#!/usr/bin/env python3
"""Probe the installed Claude Code CLI through allowlisted public interface commands."""

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

# contract-ratchet: allow observational CLI interface pin
SCHEMA_VERSION = "legalforecast.claude_code_cli_interface_characterization.v1"
REQUIRED_PRINT_FLAGS = {
    "--json-schema",
    "--model",
    "--no-session-persistence",
    "--output-format",
    "--print",
    "--setting-sources",
    "--strict-mcp-config",
    "--tools",
}
REQUIRED_OUTPUT_FORMATS = {"json", "stream-json", "text"}
SAFE_ENVIRONMENT_KEYS = {
    "HOME",
    "NO_COLOR",
    "PATH",
    "TERM",
}
OPTIONAL_RUNTIME_ENV_KEYS = frozenset({"LC_CTYPE"})
CREDENTIAL_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
)

type JsonObject = dict[str, Any]


class CharacterizationDriftError(RuntimeError):
    """Raised when installed Claude Code identity or interface differs from the pin."""


def parse_long_flags(help_text: str) -> list[str]:
    """Extract stable long-option names without retaining paths or values."""

    return sorted(set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", help_text)))


def parse_output_formats(help_text: str) -> set[str]:
    """Extract `--output-format` choices from help text."""

    match = re.search(
        r"--output-format <format>.*?choices:\s*"
        r"\"([^\"]+)\",\s*\"([^\"]+)\",\s*\"([^\"]+)\"",
        help_text,
        flags=re.DOTALL,
    )
    if match is None:
        return set()
    return set(match.groups())


def build_safe_parser_probe(
    *,
    executable: Path,
    expected_model: str,
) -> list[str]:
    """Build a help-only parse check for every required print-mode control."""

    return [
        str(executable),
        "-p",
        "--output-format",
        "json",
        "--json-schema",
        '{"type":"object"}',
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--setting-sources",
        "",
        "--model",
        expected_model,
        "--help",
    ]


def assert_matches_fixture(observed: JsonObject, expected: JsonObject) -> None:
    """Reject any identity, interface, or requested-model drift."""

    if observed != expected:
        raise CharacterizationDriftError(
            "Claude Code CLI characterization drift detected; review a sanitized "
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
    """Collect requested interface facts without a model or provider call."""

    if expected_fixture is not None:
        _require_expected_model(expected_fixture, expected_model)
    located, resolved = _resolve_executable(executable_name)
    source_mode = stat.S_IMODE(resolved.stat().st_mode)
    source_sha256 = _sha256_file(resolved)
    if expected_fixture is not None:
        _preflight_expected_binary(
            located,
            resolved,
            source_mode=source_mode,
            source_sha256=source_sha256,
            expected=expected_fixture,
        )

    with tempfile.TemporaryDirectory(
        prefix=".claude-cli-interface-",
        dir=Path.cwd(),
    ) as temporary_directory:
        isolated_root = Path(temporary_directory)
        home = isolated_root / "home"
        staged_executable = isolated_root / located.name
        home.mkdir()
        _stage_executable(
            resolved,
            staged_executable,
            expected_sha256=source_sha256,
            expected_mode=source_mode,
        )
        environment = {
            "HOME": str(home),
            "NO_COLOR": "1",
            "PATH": os.environ.get("PATH", ""),
            "TERM": "dumb",
        }
        lc_ctype = os.environ.get("LC_CTYPE")
        if lc_ctype:
            environment["LC_CTYPE"] = lc_ctype
        commands = [
            [str(staged_executable), "--version"],
            [str(staged_executable), "--help"],
            build_safe_parser_probe(
                executable=staged_executable,
                expected_model=expected_model,
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
            parser_help = run_allowlisted_interface_command(
                commands[2],
                environment,
                allowed_commands=allowed_commands,
            )
        finally:
            _verify_staged_executable(
                staged_executable,
                expected_sha256=source_sha256,
                expected_mode=source_mode,
            )

    flags = set(parse_long_flags(root_help))
    missing_flags = sorted(REQUIRED_PRINT_FLAGS - flags)
    if missing_flags:
        raise CharacterizationDriftError(
            f"Claude Code CLI is missing required print flags: {missing_flags}"
        )
    output_formats = parse_output_formats(root_help)
    if output_formats != REQUIRED_OUTPUT_FORMATS:
        raise CharacterizationDriftError(
            "Claude Code CLI output-format interface drift detected"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "binary": {
            "distribution": {
                "kind": "standalone-cli",
                "package": "claude",
                "version": version,
            },
            "executable": located.name,
            "mode": f"{source_mode:04o}",
            "sha256": source_sha256,
            "version": version,
        },
        "platform": {
            "machine": platform.machine(),
            "system": platform.system().lower(),
        },
        "interface": {
            "parser_probe": {
                "help_only": True,
                "probe_requested_model_call": False,
                "sha256": _sha256_text(parser_help),
            },
            "print_long_flags": sorted(flags),
            "required_print_flags": sorted(REQUIRED_PRINT_FLAGS),
            "root_help_sha256": _sha256_text(root_help),
            "output_formats": sorted(output_formats),
        },
        "model": {
            "requested": expected_model,
            "resolved": None,
            "resolved_verification": "requires a separately approved model request",
        },
        "tools": {
            "native_model_tool_inventory": None,
            "observed_without_model_request": False,
        },
        "identity": {
            "adapter_profile": "claude-code-clean-native",
            "claude_agent_sdk_adapter": False,
            "uses_bare_flag": False,
        },
        "auth": {
            "help_documents_api_key": "ANTHROPIC_API_KEY" in root_help,
            "help_documents_bare_oauth_skip": "--bare" in flags
            and "OAuth" in root_help,
            "status_command_requested": False,
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
            "probe_kind": "version-help-print-interface-only",
            "probe_requested_model_calls": 0,
            "provider_credential_environment_inherited": False,
        },
    }


def _resolve_executable(executable_name: str) -> tuple[Path, Path]:
    located_name = shutil.which(executable_name)
    if located_name is None:
        raise CharacterizationDriftError("Claude Code CLI executable is unavailable")
    located = Path(located_name)
    return located, located.resolve(strict=True)


def run_allowlisted_interface_command(
    command: list[str],
    environment: dict[str, str],
    *,
    allowed_commands: set[tuple[str, ...]],
) -> str:
    """Run one exact allowlisted interface command with the safe environment."""

    if tuple(command) not in allowed_commands:
        raise CharacterizationDriftError(
            "Claude Code CLI interface command is not allowlisted"
        )
    extra = set(environment) - SAFE_ENVIRONMENT_KEYS - OPTIONAL_RUNTIME_ENV_KEYS
    missing = SAFE_ENVIRONMENT_KEYS - set(environment)
    if extra or missing:
        raise CharacterizationDriftError(
            "Claude Code CLI interface environment is not the exact safe projection"
        )
    if set(CREDENTIAL_ENV_VARS) & set(environment):
        raise CharacterizationDriftError(
            "Claude Code CLI interface environment inherited a credential variable"
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
            "Claude Code CLI safe interface command failed without producing "
            "publishable stderr"
        )
    return completed.stdout


# contract-ratchet: allow non-persisted executable digest for the interface pin
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# contract-ratchet: allow non-persisted help-text digest for the interface pin
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
        raise CharacterizationDriftError("staged Claude Code CLI is not a regular file")
    if stat.S_IMODE(actual_stat.st_mode) != expected_mode:
        raise CharacterizationDriftError("staged Claude Code CLI mode drift detected")
    if _sha256_file(executable) != expected_sha256:
        raise CharacterizationDriftError("staged Claude Code CLI hash drift detected")


def _require_expected_model(expected: JsonObject, expected_model: str) -> None:
    model = expected.get("model")
    if not isinstance(model, dict):
        raise CharacterizationDriftError(
            "requested model drift detected before Claude Code CLI invocation"
        )
    model_record = cast(dict[str, object], model)
    if model_record.get("requested") != expected_model:
        raise CharacterizationDriftError(
            "requested model drift detected before Claude Code CLI invocation"
        )


def _preflight_expected_binary(
    located: Path,
    resolved: Path,
    *,
    source_mode: int,
    source_sha256: str,
    expected: JsonObject,
) -> None:
    del resolved
    binary = expected.get("binary")
    if not isinstance(binary, dict):
        raise CharacterizationDriftError("expected binary pin is missing")
    binary_record = cast(dict[str, object], binary)
    if binary_record.get("executable") != located.name:
        raise CharacterizationDriftError(
            "Claude Code CLI executable identity drift detected before invocation"
        )
    if binary_record.get("mode") != f"{source_mode:04o}":
        raise CharacterizationDriftError(
            "Claude Code CLI mode drift detected before invocation"
        )
    if binary_record.get("sha256") != source_sha256:
        raise CharacterizationDriftError(
            "Claude Code CLI hash drift detected before invocation"
        )


def _load_fixture(path: Path) -> JsonObject:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise CharacterizationDriftError("characterization fixture must be an object")
    return cast(JsonObject, decoded)


def main() -> int:
    """Run the safe observation and optionally compare it to an exact fixture."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="claude")
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
