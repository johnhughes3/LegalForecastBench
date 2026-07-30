#!/usr/bin/env python3
"""Probe the installed Codex CLI through non-spending public interfaces only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
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


def observe(executable_name: str, expected_model: str) -> JsonObject:
    """Collect a sanitized observation without reading auth or making a model call."""

    executable = _resolve_executable(executable_name)
    with tempfile.TemporaryDirectory(
        prefix=".codex-cli-interface-",
        dir=Path.cwd(),
    ) as temporary_directory:
        isolated_root = Path(temporary_directory)
        workspace = isolated_root / "workspace"
        codex_home = isolated_root / "codex-home"
        home = isolated_root / "home"
        workspace.mkdir()
        codex_home.mkdir()
        home.mkdir()
        environment = {
            "CODEX_HOME": str(codex_home),
            "HOME": str(home),
            "NO_COLOR": "1",
            "PATH": os.environ.get("PATH", ""),
            "TERM": "dumb",
        }

        version = _run_safe([str(executable), "--version"], environment).strip()
        root_help = _run_safe([str(executable), "--help"], environment)
        exec_help = _run_safe([str(executable), "exec", "--help"], environment)
        feature_text = _run_safe(
            [str(executable), "features", "list"],
            environment,
        )
        parser_help = _run_safe(
            build_safe_parser_probe(
                executable=executable,
                expected_model=expected_model,
                workspace=workspace,
            ),
            environment,
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
            "sha256": _sha256_file(executable),
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
                "provider_request_possible": False,
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
            "auth_state_inspected_or_copied": False,
            "benchmark_task_bytes": 0,
            "model_or_provider_requests": 0,
            "probe_kind": "version-help-feature-interface-only",
        },
    }


def _resolve_executable(executable_name: str) -> Path:
    located = shutil.which(executable_name)
    if located is None:
        raise CharacterizationDriftError("Codex CLI executable is unavailable")
    return Path(located).resolve(strict=True)


def _run_safe(command: list[str], environment: dict[str, str]) -> str:
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
    if parts[cask_position + 1] != "codex":
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

    observation = observe(arguments.executable, arguments.expected_model)
    if arguments.check is not None:
        assert_matches_fixture(observation, _load_fixture(arguments.check))
    if arguments.print_observation:
        print(json.dumps(observation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
