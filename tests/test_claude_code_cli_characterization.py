from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from scripts.probe_claude_code_cli_interface import (
    CharacterizationDriftError,
    assert_matches_fixture,
    build_safe_parser_probe,
    check_fixture,
    observe,
    parse_long_flags,
    parse_output_formats,
    run_allowlisted_interface_command,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "claude_code_cli_characterization"
    / "claude-code-cli-interface-2.1.231.json"
)
DOC = ROOT / "docs" / "adapters" / "claude-code-cli-characterization.md"
MANIFEST = ROOT / "tests" / "fixtures" / "local_cli_adapters" / "claude-code.json"
EXPECTED_SHA256 = "47a01daebf794f6c86c13d1875ad6e5be0627029ad8600731161f24018ecde5b"
EXPECTED_MODEL = "claude-haiku-4-5"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_committed_characterization_pins_binary_and_requested_probe_controls() -> None:
    evidence = _fixture()

    assert evidence["schema_version"] == (
        "legalforecast.claude_code_cli_interface_characterization.v1"
    )
    assert evidence["binary"] == {
        "distribution": {
            "kind": "standalone-cli",
            "package": "claude",
            "version": "2.1.231 (Claude Code)",
        },
        "executable": "claude",
        "mode": "0755",
        "sha256": EXPECTED_SHA256,
        "version": "2.1.231 (Claude Code)",
    }
    assert evidence["safety"] == {
        "auth_paths_requested": False,
        "benchmark_task_paths_requested": False,
        "external_network_isolation_enforced": False,
        "no_external_behavior_claimed": True,
        "probe_kind": "version-help-print-interface-only",
        "probe_requested_model_calls": 0,
        "provider_credential_environment_inherited": False,
    }


def test_characterization_pins_required_noninteractive_controls() -> None:
    evidence = _fixture()
    interface = evidence["interface"]

    assert set(interface["required_print_flags"]) == {
        "--json-schema",
        "--model",
        "--no-session-persistence",
        "--output-format",
        "--print",
        "--setting-sources",
        "--strict-mcp-config",
        "--tools",
    }
    assert set(interface["output_formats"]) == {"json", "stream-json", "text"}
    assert interface["parser_probe"]["help_only"] is True
    assert interface["parser_probe"]["probe_requested_model_call"] is False


def test_identity_is_distinct_and_unverified_activation_is_blocked() -> None:
    evidence = _fixture()

    assert evidence["identity"] == {
        "adapter_profile": "claude-code-clean-native",
        "claude_agent_sdk_adapter": False,
        "uses_bare_flag": False,
    }
    assert evidence["model"] == {
        "requested": EXPECTED_MODEL,
        "resolved": None,
        "resolved_verification": "requires a separately approved model request",
    }
    assert evidence["tools"]["native_model_tool_inventory"] is None
    assert evidence["activation"]["allowed"] is False
    assert evidence["auth"]["status_command_requested"] is False


def test_documentation_and_manifest_preserve_the_non_spending_claim_boundary() -> None:
    documentation = DOC.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert "2.1.231" in documentation
    assert EXPECTED_SHA256 in documentation
    assert "does not prove JSON envelope semantics" in documentation
    assert "Claude Agent SDK" in documentation
    assert "Activation remains blocked" in documentation
    assert manifest["executable"]["sha256"] == EXPECTED_SHA256
    assert manifest["auth_profile_name"] == "fixture-none"
    assert manifest["timeout_retry"]["max_attempts"] == 1
    typed = LocalCliAdapterManifest.from_record(manifest)
    assert typed.executable.sha256 == EXPECTED_SHA256
    assert typed.executable.version == "2.1.231 (Claude Code)"
    assert typed.to_record() == manifest


def test_json_schema_flag_takes_inline_json_not_a_path() -> None:
    documentation = DOC.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    template = manifest["invocation"]["argv_template"]
    auth_closed = (
        ROOT / "tests" / "fixtures" / "claude_code" / "transcripts" / "auth_closed.json"
    ).read_text(encoding="utf-8")

    assert "inline JSON" in documentation
    assert "rejected as invalid JSON" in documentation
    assert "filesystem path was rejected as invalid JSON" in auth_closed
    assert template[template.index("--json-schema") + 1] == "{output_schema}"
    assert "{output_schema_path}" not in template
    probe = build_safe_parser_probe(
        executable=Path("claude"),
        expected_model=EXPECTED_MODEL,
    )
    token = probe[probe.index("--json-schema") + 1]
    json.loads(token)
    assert not token.endswith(".json")


def test_non_empty_tools_argv_is_one_comma_joined_token() -> None:
    from legalforecast.multiharness.claude_code import (
        CLAUDE_CODE_CLEAN_NATIVE_TOOLS,
        CLAUDE_CODE_TOOLS_ARGV_ENCODING,
        CLAUDE_CODE_TOOLS_ARGV_EXAMPLE,
        encode_claude_code_tools_argv_token,
    )

    documentation = DOC.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    template = manifest["invocation"]["argv_template"]

    assert "--tools <tools...>" in documentation
    assert "comma-joined" in documentation
    assert CLAUDE_CODE_TOOLS_ARGV_EXAMPLE in documentation
    assert "Read,Glob" in documentation
    assert CLAUDE_CODE_TOOLS_ARGV_ENCODING == "comma-joined-single-token"
    assert template[template.index("--tools") + 1] == ""
    assert template[template.index("--tools") + 2] == "--strict-mcp-config"
    probe = build_safe_parser_probe(
        executable=Path("claude"),
        expected_model=EXPECTED_MODEL,
    )
    assert probe[probe.index("--tools") + 1] == ""
    assert encode_claude_code_tools_argv_token(("Read", "Glob")) == "Read,Glob"
    native = encode_claude_code_tools_argv_token(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert native == ",".join(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert native.count(",") == len(CLAUDE_CODE_CLEAN_NATIVE_TOOLS) - 1


def test_help_parsers_extract_only_public_interface_data() -> None:
    help_text = """Options:
  -p, --print
  --output-format <format>
      (choices: "text", "json", "stream-json")
  --json-schema <schema>
"""

    assert parse_long_flags(help_text) == [
        "--json-schema",
        "--output-format",
        "--print",
    ]
    assert parse_output_formats(help_text) == {"json", "stream-json", "text"}


def test_safe_parser_probe_uses_help_and_all_required_controls() -> None:
    command = build_safe_parser_probe(
        executable=Path("/opt/claude"),
        expected_model=EXPECTED_MODEL,
    )

    assert command[:4] == ["/opt/claude", "-p", "--output-format", "json"]
    assert command[-2:] == [EXPECTED_MODEL, "--help"]
    assert "--no-session-persistence" in command
    assert "--strict-mcp-config" in command
    assert "login" not in command


def test_fixture_comparison_fails_closed_on_binary_interface_or_model_drift() -> None:
    expected = _fixture()
    for path, drifted_value in (
        (("binary", "sha256"), "0" * 64),
        (("interface", "root_help_sha256"), "1" * 64),
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
    executable = _write_recording_fake(tmp_path, marker=marker, name="claude")

    with pytest.raises(CharacterizationDriftError, match="hash"):
        check_fixture(
            executable_name=str(executable),
            expected_model=EXPECTED_MODEL,
            fixture_path=FIXTURE,
        )

    assert not marker.exists()


def test_observation_executes_only_staged_allowlisted_commands_with_safe_env(
    tmp_path: Path,
) -> None:
    record_path = tmp_path / "record.jsonl"
    executable = _write_recording_fake(tmp_path, record_path=record_path, name="claude")

    evidence = observe(str(executable), EXPECTED_MODEL)

    records = [
        json.loads(line)
        for line in record_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["argv"] for record in records] == [
        ["--version"],
        ["--help"],
        [
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
            EXPECTED_MODEL,
            "--help",
        ],
    ]
    staged_executables = {record["executable"] for record in records}
    assert len(staged_executables) == 1
    staged_executable = Path(next(iter(staged_executables)))
    assert staged_executable != executable
    assert staged_executable.name == "claude"
    assert staged_executable.parent.name.startswith(".claude-cli-interface-")
    for record in records:
        environment = record["environment"]
        assert {"HOME", "NO_COLOR", "PATH", "TERM"} <= set(environment)
        assert set(environment) <= {
            "HOME",
            "LC_CTYPE",
            "NO_COLOR",
            "PATH",
            "TERM",
        }
        assert not {
            "ANTHROPIC_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "OPENAI_API_KEY",
        } & set(environment)
    assert evidence["binary"]["sha256"] == _sha256(executable)
    assert evidence["safety"]["provider_credential_environment_inherited"] is False


def test_execution_helper_rejects_non_allowlisted_command_before_invocation(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "invoked"
    executable = _write_recording_fake(tmp_path, marker=marker, name="claude")
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
    executable = _write_recording_fake(tmp_path, mutate_staged=True, name="claude")

    with pytest.raises(CharacterizationDriftError, match="hash drift"):
        observe(str(executable), EXPECTED_MODEL)


def _write_recording_fake(
    directory: Path,
    *,
    marker: Path | None = None,
    mutate_staged: bool = False,
    name: str = "claude-recording-fake",
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

ROOT_HELP = '''Options:
  -p, --print
  --json-schema <schema>
  --model <model>
  --no-session-persistence
  --output-format <format>
      (choices: "text", "json", "stream-json")
  --setting-sources <sources>
  --strict-mcp-config
  --tools <tools...>
  --bare
'''

arguments = sys.argv[1:]
if arguments == ['--version']:
    print('2.1.229 (Claude Code)')
elif arguments == ['--help']:
    print(ROOT_HELP, end='')
elif arguments and arguments[0] == '-p' and arguments[-1] == '--help':
    print(ROOT_HELP, end='')
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
