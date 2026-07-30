from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from scripts.probe_codex_cli_interface import (
    CharacterizationDriftError,
    assert_matches_fixture,
    build_safe_parser_probe,
    check_fixture,
    observe,
    parse_feature_rows,
    parse_long_flags,
    parse_subcommands,
    run_allowlisted_interface_command,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "codex_cli_characterization"
    / "codex-cli-interface-0.146.0.json"
)
DOC = ROOT / "docs" / "adapters" / "codex-cli-characterization.md"
EXPECTED_SHA256 = "2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_committed_characterization_pins_binary_and_requested_probe_controls() -> None:
    evidence = _fixture()

    assert evidence["schema_version"] == (
        "legalforecast.codex_cli_interface_characterization.v1"
    )
    assert evidence["binary"] == {
        "distribution": {
            "kind": "homebrew-cask",
            "package": "codex",
            "version": "0.146.0",
        },
        "executable": "codex-x86_64-unknown-linux-musl",
        "mode": "0755",
        "sha256": EXPECTED_SHA256,
        "version": "codex-cli 0.146.0",
    }
    assert evidence["safety"] == {
        "auth_paths_requested": False,
        "benchmark_task_paths_requested": False,
        "external_network_isolation_enforced": False,
        "no_external_behavior_claimed": True,
        "probe_kind": "version-help-feature-interface-only",
        "probe_requested_model_calls": 0,
        "provider_credential_environment_inherited": False,
    }


def test_characterization_pins_required_noninteractive_controls() -> None:
    evidence = _fixture()
    interface = evidence["interface"]

    assert "exec" in interface["root_subcommands"]
    assert set(interface["required_exec_flags"]) == {
        "--cd",
        "--ephemeral",
        "--ignore-rules",
        "--ignore-user-config",
        "--json",
        "--model",
        "--sandbox",
        "--strict-config",
    }
    assert set(interface["sandbox_modes"]) == {
        "danger-full-access",
        "read-only",
        "workspace-write",
    }
    assert interface["parser_probe"]["help_only"] is True
    assert interface["parser_probe"]["probe_requested_model_call"] is False


def test_identity_is_distinct_and_unverified_activation_is_blocked() -> None:
    evidence = _fixture()

    assert evidence["identity"] == {
        "adapter_profile": "codex-cli-clean-native",
        "foreign_mcp_primary_loop": False,
        "openai_responses_adapter": False,
    }
    assert evidence["model"] == {
        "requested": "gpt-5.1",
        "resolved": None,
        "resolved_verification": "requires a separately approved model request",
    }
    assert evidence["tools"]["native_model_tool_inventory"] is None
    assert evidence["tools"]["observed_without_model_request"] is False
    assert evidence["activation"]["allowed"] is False
    assert set(evidence["activation"]["blocking_gaps"]) == {
        "native model tool inventory not observed for this binary",
        "resolved model not observed for this binary",
    }


def test_documentation_preserves_the_non_spending_claim_boundary() -> None:
    documentation = DOC.read_text(encoding="utf-8")

    assert "`codex-cli 0.146.0`" in documentation
    assert EXPECTED_SHA256 in documentation
    assert "does not prove JSONL event semantics" in documentation
    assert "does not supersede" in documentation
    assert "OpenAI Responses adapter" in documentation
    assert "Activation remains blocked" in documentation


def test_help_parsers_extract_only_public_interface_data() -> None:
    help_text = """Commands:
  exec       Run non-interactively
  login      Manage login

Options:
  -m, --model <MODEL>
      --json
"""
    feature_text = """shell_tool  stable             true
multi_agent stable             false
"""

    assert parse_subcommands(help_text) == ["exec", "login"]
    assert parse_long_flags(help_text) == ["--json", "--model"]
    assert parse_feature_rows(feature_text) == {
        "multi_agent": {"stage": "stable", "enabled": False},
        "shell_tool": {"stage": "stable", "enabled": True},
    }


def test_safe_parser_probe_uses_help_and_all_required_controls(tmp_path: Path) -> None:
    command = build_safe_parser_probe(
        executable=Path("/opt/codex"),
        expected_model="gpt-5.1",
        workspace=tmp_path,
    )

    assert command == [
        "/opt/codex",
        "exec",
        "--json",
        "--ephemeral",
        "--model",
        "gpt-5.1",
        "--cd",
        str(tmp_path),
        "--sandbox",
        "read-only",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--help",
    ]
    assert "login" not in command
    assert "doctor" not in command


def test_fixture_comparison_fails_closed_on_binary_interface_or_model_drift() -> None:
    expected = _fixture()
    for path, drifted_value in (
        (("binary", "sha256"), "0" * 64),
        (("interface", "exec_help_sha256"), "1" * 64),
        (("model", "requested"), "different-model"),
    ):
        observed = json.loads(json.dumps(expected))
        target = observed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = drifted_value

        with pytest.raises(CharacterizationDriftError, match="drift"):
            assert_matches_fixture(observed, expected)


def test_hash_drift_is_rejected_before_executable_invocation(tmp_path: Path) -> None:
    marker = tmp_path / "invoked"
    executable = _write_recording_fake(
        tmp_path,
        marker=marker,
        name="codex-x86_64-unknown-linux-musl",
    )

    with pytest.raises(CharacterizationDriftError, match="hash"):
        check_fixture(
            executable_name=str(executable),
            expected_model="gpt-5.1",
            fixture_path=FIXTURE,
        )

    assert not marker.exists()


def test_observation_executes_only_staged_allowlisted_commands_with_safe_env(
    tmp_path: Path,
) -> None:
    record_path = tmp_path / "record.jsonl"
    executable = _write_recording_fake(tmp_path, record_path=record_path)

    evidence = observe(str(executable), "gpt-5.1")

    records = [
        json.loads(line)
        for line in record_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["argv"] for record in records] == [
        ["--version"],
        ["--help"],
        ["exec", "--help"],
        ["features", "list"],
        [
            "exec",
            "--json",
            "--ephemeral",
            "--model",
            "gpt-5.1",
            "--cd",
            records[-1]["argv"][6],
            "--sandbox",
            "read-only",
            "--strict-config",
            "--ignore-user-config",
            "--ignore-rules",
            "--help",
        ],
    ]
    staged_executables = {record["executable"] for record in records}
    assert len(staged_executables) == 1
    staged_executable = Path(staged_executables.pop())
    assert staged_executable != executable
    assert staged_executable.name == executable.name
    assert staged_executable.parent.name.startswith(".codex-cli-interface-")
    for record in records:
        environment = record["environment"]
        assert set(environment) == {
            "CODEX_HOME",
            "HOME",
            "LC_CTYPE",
            "NO_COLOR",
            "PATH",
            "TERM",
        }
        assert environment["NO_COLOR"] == "1"
        assert environment["PATH"] == os.environ.get("PATH", "")
        assert environment["TERM"] == "dumb"
        assert Path(environment["HOME"]).parent.name.startswith(".codex-cli-interface-")
        assert Path(environment["CODEX_HOME"]).parent.name.startswith(
            ".codex-cli-interface-"
        )
        assert not {
            "ANTHROPIC_API_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "CODEX_API_KEY",
            "OPENAI_API_KEY",
        } & set(environment)
    assert evidence["binary"]["sha256"] == _sha256(executable)
    assert evidence["safety"]["provider_credential_environment_inherited"] is False


def test_execution_helper_rejects_non_allowlisted_command_before_invocation(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "invoked"
    executable = _write_recording_fake(tmp_path, marker=marker)
    command = [str(executable), "login"]

    with pytest.raises(CharacterizationDriftError, match="allowlisted"):
        run_allowlisted_interface_command(
            command,
            {"PATH": os.environ.get("PATH", "")},
            allowed_commands={(str(executable), "--help")},
        )

    assert not marker.exists()


def test_staged_binary_hash_is_rechecked_after_interface_commands(
    tmp_path: Path,
) -> None:
    executable = _write_recording_fake(tmp_path, mutate_staged=True)

    with pytest.raises(CharacterizationDriftError, match="hash drift"):
        observe(str(executable), "gpt-5.1")


def _write_recording_fake(
    directory: Path,
    *,
    marker: Path | None = None,
    mutate_staged: bool = False,
    name: str = "codex-recording-fake",
    record_path: Path | None = None,
) -> Path:
    executable = directory / name
    marker_statement = (
        f"Path({str(marker)!r}).write_text('invoked', encoding='utf-8')"
        if marker is not None
        else "pass"
    )
    record_statement = (
        (
            f"with Path({str(record_path)!r}).open('a', encoding='utf-8') as handle:\n"
            "    handle.write(json.dumps({'argv': sys.argv[1:], "
            "'environment': dict(os.environ), 'executable': sys.argv[0]}, "
            "sort_keys=True) + '\\n')"
        )
        if record_path is not None
        else "pass"
    )
    mutation_statement = (
        "with Path(sys.argv[0]).open('a', encoding='utf-8') as handle:\n"
        "            handle.write('\\n# staged drift\\n')"
        if mutate_staged
        else "pass"
    )
    executable.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

{marker_statement}
{record_statement}

ROOT_HELP = '''Commands:
  exec      Run non-interactively
  features  Inspect features

Options:
  --help
'''
EXEC_HELP = '''Options:
  --cd <DIR>
  --ephemeral
  --ignore-rules
  --ignore-user-config
  --json
  --model <MODEL>
  --sandbox <SANDBOX_MODE>
      [possible values: read-only, workspace-write, danger-full-access]
  --strict-config
'''
FEATURES = '''apps stable true
hooks stable true
image_generation stable true
memories stable false
multi_agent stable true
plugins stable true
shell_tool stable true
unified_exec stable true
'''

arguments = sys.argv[1:]
if arguments == ['--version']:
    print('codex-cli recording-fake')
elif arguments == ['--help']:
    print(ROOT_HELP, end='')
elif arguments == ['features', 'list']:
    print(FEATURES, end='')
elif arguments == ['exec', '--help'] or (
    arguments and arguments[0] == 'exec' and arguments[-1] == '--help'
):
    print(EXEC_HELP, end='')
    if len(arguments) > 2:
        {mutation_statement}
else:
    raise SystemExit(64)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
