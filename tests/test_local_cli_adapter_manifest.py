from __future__ import annotations

import copy
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.inspect_task import SolverKind
from legalforecast.multiharness.local_cli_manifest import (
    AUTH_PROFILE_NAMES,
    HARNESS_ADAPTER_CONTRACT,
    HARNESS_SOLVER_CONTRACT,
    LOCAL_CLI_ADAPTER_KIND,
    LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION,
    LOCAL_CLI_CAPABILITIES,
    SOLVER_RESPONSE_CONTRACT,
    LocalCliAdapterManifest,
    LocalCliAdapterManifestError,
    LocalCliContainment,
    LocalCliExecutableIdentity,
    LocalCliHarnessBinding,
    LocalCliInvocation,
    LocalCliTaskProjection,
    LocalCliTimeoutRetry,
    LocalCliTranscriptCapture,
    LocalCliUsageReporting,
    capability_digest_for,
)
from legalforecast.multiharness.spec import POSIX_PROCESS_GROUP_CONTAINMENT

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "local_cli_adapters"
CLAUDE_FIXTURE = FIXTURE_DIR / "claude-code.json"
CODEX_FIXTURE = FIXTURE_DIR / "codex-cli.json"
SCHEMA_DOC = ROOT / "docs" / "schemas" / "local-cli-adapter-manifest-v1.md"
CLAUDE_SHA256 = "47a01daebf794f6c86c13d1875ad6e5be0627029ad8600731161f24018ecde5b"
CODEX_SHA256 = "2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04"


def _binding(
    adapter_id: str,
    *,
    tool_protocol_version: str | None = None,
) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "adapter_version": "1.0.0",
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "tool_protocol_version": tool_protocol_version,
        "implements_harness_adapter": True,
        "implements_harness_solver": True,
        "harness_adapter_contract": HARNESS_ADAPTER_CONTRACT,
        "harness_solver_contract": HARNESS_SOLVER_CONTRACT,
        "solver_response_contract": SOLVER_RESPONSE_CONTRACT,
        "solver_kind": SolverKind.INSPECT_AI.value,
    }


def _claude_record() -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "claude-code-clean-native",
        "display_name": "Claude Code clean-native local CLI",
        "adapter_kind": LOCAL_CLI_ADAPTER_KIND,
        "executable": {
            "basename": "claude",
            "version": "2.1.231 (Claude Code)",
            "sha256": CLAUDE_SHA256,
            "distribution_kind": "standalone-cli",
        },
        "capabilities": [
            "empty_tools",
            "headless_print",
            "isolated_setting_sources",
            "json_output",
            "json_schema_enforcement",
            "max_budget_usd",
            "model_selection",
            "no_session_persistence",
            "permission_mode",
            "strict_mcp_config",
            "tool_allowlist",
            "working_directory_isolation",
        ],
        "capability_digest": "sha256:" + "a" * 64,
        "invocation": {
            "headless_mode": "print_flag",
            "argv_template": [
                "-p",
                "{prompt}",
                "--output-format",
                "json",
                "--json-schema",
                "{output_schema_path}",
                "--tools",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--setting-sources",
                "",
                "--model",
                "{model}",
                "--add-dir",
                "{workspace}",
            ],
            "output_format": "json",
            "schema_enforcement": "json_schema_flag",
            "prompt_delivery": "argv_placeholder",
            "working_directory_flag": "--add-dir",
            "model_flag": "--model",
        },
        "auth_profile_name": "fixture-none",
        "supported_auth_profiles": [
            "contributor-subscription",
            "fixture-none",
            "published-api-key",
        ],
        "auth_environment_variables": [
            {
                "names": ["CLAUDE_CODE_OAUTH_TOKEN"],
                "profile": "contributor-subscription",
            },
            {"names": [], "profile": "fixture-none"},
            {"names": ["ANTHROPIC_API_KEY"], "profile": "published-api-key"},
        ],
        "containment": {
            "host_process_containment": POSIX_PROCESS_GROUP_CONTAINMENT,
            "network_policy": "provider_egress_host_only",
            "isolated_host_environment": True,
            "session_persistence": "forbidden",
            "setting_sources": [],
            "strict_mcp_config": True,
        },
        "timeout_retry": {
            "timeout_seconds": 120,
            "max_attempts": 1,
            "retry_backoff_seconds": 2,
            "retryable_exit_codes": [],
        },
        "transcript_capture": {
            "points": ["private_execution_log", "stderr", "stdout"],
            "public_raw_transcript": False,
        },
        "usage_reporting": {
            "input_tokens_field": "usage.input_tokens",
            "output_tokens_field": "usage.output_tokens",
            "cache_read_tokens_field": "usage.cache_read_input_tokens",
            "cache_write_tokens_field": "usage.cache_creation_input_tokens",
            "cost_usd_field": "total_cost_usd",
            "cost_basis": "provider_reported",
            "solver_response_fields": [
                "estimated_cost",
                "input_tokens",
                "output_tokens",
                "request_count",
            ],
        },
        "task_projection": {
            "prompt_source": "solver_input_prompt",
            "deliverable_source": "structured_stdout",
            "deliverable_relative_path": None,
        },
        "harness_binding": _binding("claude-code-clean-native"),
    }
    record["capability_digest"] = capability_digest_for(record)
    return record


def _codex_record() -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "codex-cli-clean-native",
        "display_name": "Codex CLI clean-native local CLI",
        "adapter_kind": LOCAL_CLI_ADAPTER_KIND,
        "executable": {
            "basename": "codex",
            "version": "codex-cli 0.146.0",
            "sha256": CODEX_SHA256,
            "distribution_kind": "homebrew-cask",
        },
        "capabilities": [
            "headless_print",
            "json_output",
            "json_schema_enforcement",
            "model_selection",
            "no_session_persistence",
            "working_directory_isolation",
        ],
        "capability_digest": "sha256:" + "a" * 64,
        "invocation": {
            "headless_mode": "exec_subcommand",
            "argv_template": [
                "exec",
                "--json",
                "--ephemeral",
                "--model",
                "{model}",
                "--cd",
                "{workspace}",
                "--sandbox",
                "read-only",
                "--strict-config",
                "--ignore-user-config",
                "--ignore-rules",
                "--output-schema",
                "{output_schema_path}",
                "{prompt}",
            ],
            "output_format": "json",
            "schema_enforcement": "output_schema_file",
            "prompt_delivery": "argv_placeholder",
            "working_directory_flag": "--cd",
            "model_flag": "--model",
        },
        "auth_profile_name": "fixture-none",
        "supported_auth_profiles": [
            "contributor-subscription",
            "fixture-none",
            "published-api-key",
        ],
        "auth_environment_variables": [
            {"names": [], "profile": "contributor-subscription"},
            {"names": [], "profile": "fixture-none"},
            {"names": ["OPENAI_API_KEY"], "profile": "published-api-key"},
        ],
        "containment": {
            "host_process_containment": POSIX_PROCESS_GROUP_CONTAINMENT,
            "network_policy": "provider_egress_host_only",
            "isolated_host_environment": True,
            "session_persistence": "ephemeral",
            "setting_sources": [],
            "strict_mcp_config": False,
        },
        "timeout_retry": {
            "timeout_seconds": 120,
            "max_attempts": 1,
            "retry_backoff_seconds": 2,
            "retryable_exit_codes": [],
        },
        "transcript_capture": {
            "points": ["private_execution_log", "stderr", "stdout"],
            "public_raw_transcript": False,
        },
        "usage_reporting": {
            "input_tokens_field": "usage.input_tokens",
            "output_tokens_field": "usage.output_tokens",
            "cache_read_tokens_field": None,
            "cache_write_tokens_field": None,
            "cost_usd_field": None,
            "cost_basis": "unknown",
            "solver_response_fields": ["input_tokens", "output_tokens"],
        },
        "task_projection": {
            "prompt_source": "solver_input_prompt",
            "deliverable_source": "structured_stdout",
            "deliverable_relative_path": None,
        },
        "harness_binding": _binding("codex-cli-clean-native"),
    }
    record["capability_digest"] = capability_digest_for(record)
    return record


@pytest.mark.parametrize("builder", (_claude_record, _codex_record))
def test_local_cli_manifest_round_trips(builder: Any) -> None:
    record = builder()
    manifest = LocalCliAdapterManifest.from_record(record)

    assert LocalCliAdapterManifest.from_record(manifest.to_record()) == manifest


def test_committed_fixtures_validate_claude_and_codex() -> None:
    claude = LocalCliAdapterManifest.from_record(
        json.loads(CLAUDE_FIXTURE.read_text(encoding="utf-8"))
    )
    codex = LocalCliAdapterManifest.from_record(
        json.loads(CODEX_FIXTURE.read_text(encoding="utf-8"))
    )

    assert claude.executable.basename == "claude"
    assert claude.auth_profile_name == "fixture-none"
    assert claude.invocation.headless_mode == "print_flag"
    assert "--no-session-persistence" in claude.invocation.argv_template
    assert claude.timeout_retry.max_attempts == 1
    assert claude.transcript_capture.public_raw_transcript is False
    assert claude.to_adapter_manifest().adapter_id == claude.manifest_id
    assert claude.to_adapter_capabilities().capabilities_sha256 == (
        claude.capability_digest
    )

    assert codex.executable.basename == "codex"
    assert codex.invocation.headless_mode == "exec_subcommand"
    assert codex.invocation.argv_template[0] == "exec"
    assert set(claude.capabilities).issubset(LOCAL_CLI_CAPABILITIES)
    assert set(codex.capabilities).issubset(LOCAL_CLI_CAPABILITIES)
    assert claude.auth_profile_name in AUTH_PROFILE_NAMES
    assert "claude" not in json.dumps(codex.to_record())


def test_missing_executable_digest_is_rejected() -> None:
    record = _claude_record()
    del record["executable"]["sha256"]

    with pytest.raises(LocalCliAdapterManifestError, match="sha256"):
        LocalCliAdapterManifest.from_record(record)


def test_unknown_capability_is_rejected() -> None:
    record = _claude_record()
    record["capabilities"] = [*record["capabilities"], "browser_control"]
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="unknown token"):
        LocalCliAdapterManifest.from_record(record)


def test_unknown_field_is_rejected() -> None:
    record = _claude_record()
    record["provider"] = "anthropic"

    with pytest.raises(LocalCliAdapterManifestError, match="unexpected field"):
        LocalCliAdapterManifest.from_record(record)


def test_unknown_auth_profile_is_rejected() -> None:
    record = _claude_record()
    record["auth_profile_name"] = "claude-subscription-local"
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="auth_profile_name"):
        LocalCliAdapterManifest.from_record(record)


def test_legacy_auth_profile_aliases_fail_closed() -> None:
    record = _claude_record()
    record["auth_profile_name"] = "fixture_none"
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="auth_profile_name"):
        LocalCliAdapterManifest.from_record(record)


def test_host_path_basename_is_rejected() -> None:
    record = _claude_record()
    record["executable"]["basename"] = "/opt/legalforecastbench/claude"
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="pathless"):
        LocalCliAdapterManifest.from_record(record)


def test_capability_digest_drift_is_rejected() -> None:
    record = _claude_record()
    record["capability_digest"] = "sha256:" + "b" * 64

    with pytest.raises(LocalCliAdapterManifestError, match="capability_digest"):
        LocalCliAdapterManifest.from_record(record)


def test_public_raw_transcript_cannot_be_enabled() -> None:
    record = _claude_record()
    record["transcript_capture"]["public_raw_transcript"] = True
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="public_raw_transcript"):
        LocalCliAdapterManifest.from_record(record)


def test_retries_without_exit_codes_are_rejected() -> None:
    record = _claude_record()
    record["timeout_retry"]["max_attempts"] = 3
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="retryable_exit_codes"):
        LocalCliAdapterManifest.from_record(record)


def test_unknown_placeholder_is_rejected() -> None:
    record = _claude_record()
    record["invocation"]["argv_template"] = ["-p", "{task_file}"]
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="unknown placeholder"):
        LocalCliAdapterManifest.from_record(record)


def test_render_argv_substitutes_only_closed_placeholders() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())

    argv = manifest.invocation.render_argv(
        prompt="Reply with OK",
        model="claude-haiku-4-5-20251001",
        workspace="workspace",
        output_schema_path='{"type":"object"}',
    )

    assert argv[0] == "-p"
    assert argv[1] == "Reply with OK"
    assert "{prompt}" not in argv
    assert "claude-haiku-4-5-20251001" in argv
    assert "--tools" in argv
    assert argv[argv.index("--tools") + 1] == ""


def test_schema_doc_states_existing_solver_contracts() -> None:
    documentation = SCHEMA_DOC.read_text(encoding="utf-8")

    assert LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION in documentation
    assert "adapter_manifest.v1" in documentation
    assert HARNESS_ADAPTER_CONTRACT in documentation
    assert "HarnessSolver" in documentation
    assert "fixture-none" in documentation
    assert "published-api-key" in documentation
    assert "contributor-subscription" in documentation
    assert "legalforecast/cli.py" in documentation


def test_committed_fixtures_match_builders() -> None:
    claude = json.loads(CLAUDE_FIXTURE.read_text(encoding="utf-8"))
    codex = json.loads(CODEX_FIXTURE.read_text(encoding="utf-8"))

    assert claude == _claude_record()
    assert codex == _codex_record()
    assert copy.deepcopy(claude)["executable"]["sha256"] == CLAUDE_SHA256


def test_schema_doc_examples_round_trip_through_the_typed_model() -> None:
    documentation = SCHEMA_DOC.read_text(encoding="utf-8")
    examples = [
        json.loads(block)
        for block in re.findall(r"```json\n(.*?)```", documentation, flags=re.DOTALL)
    ]

    assert examples
    for example in examples:
        manifest = LocalCliAdapterManifest.from_record(example)
        assert manifest.to_record() == example


_NESTED_RECORD_MODELS = {
    "containment": LocalCliContainment,
    "executable": LocalCliExecutableIdentity,
    "harness_binding": LocalCliHarnessBinding,
    "invocation": LocalCliInvocation,
    "task_projection": LocalCliTaskProjection,
    "timeout_retry": LocalCliTimeoutRetry,
    "transcript_capture": LocalCliTranscriptCapture,
    "usage_reporting": LocalCliUsageReporting,
}


def _required_field_paths() -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for field in fields(LocalCliAdapterManifest):
        paths.append((field.name,))
        nested = _NESTED_RECORD_MODELS.get(field.name)
        if nested is None:
            continue
        for inner in fields(nested):
            paths.append((field.name, inner.name))
    return tuple(paths)


@pytest.mark.parametrize(
    "path",
    _required_field_paths(),
    ids=lambda path: ".".join(path),
)
def test_missing_required_field_names_the_field(path: tuple[str, ...]) -> None:
    record = _claude_record()
    if len(path) == 1:
        del record[path[0]]
    else:
        del record[path[0]][path[1]]

    with pytest.raises(LocalCliAdapterManifestError, match=re.escape(path[-1])):
        LocalCliAdapterManifest.from_record(record)


_FIELD_TABLE_MODELS = {
    "containment": LocalCliContainment,
    "executable": LocalCliExecutableIdentity,
    "harness_binding": LocalCliHarnessBinding,
    "invocation": LocalCliInvocation,
    "local_cli_adapter_manifest": LocalCliAdapterManifest,
    "task_projection": LocalCliTaskProjection,
    "timeout_retry": LocalCliTimeoutRetry,
    "transcript_capture": LocalCliTranscriptCapture,
    "usage_reporting": LocalCliUsageReporting,
}


def _field_tables_from_schema_doc(markdown: str) -> dict[str, frozenset[str]]:
    start = markdown.index("## Closed field inventory")
    tables: dict[str, frozenset[str]] = {}
    current: str | None = None
    collected: list[str] = []
    in_table = False
    heading_re = re.compile(r"^### ([a-z_]+)\s*$")
    for line in markdown[start:].splitlines():
        heading = heading_re.match(line)
        if heading is not None:
            if current is not None:
                tables[current] = frozenset(collected)
            current = heading.group(1)
            collected = []
            in_table = False
            continue
        if current is None:
            continue
        if re.match(r"^\|\s*field\s*\|", line, flags=re.IGNORECASE):
            in_table = True
            continue
        if in_table and re.match(r"^\|\s*-+", line):
            continue
        if in_table and line.startswith("|"):
            field_name = line.strip().strip("|").strip()
            if field_name:
                collected.append(field_name)
            continue
        if in_table and line.startswith("##"):
            tables[current] = frozenset(collected)
            current = None
            in_table = False
    if current is not None:
        tables[current] = frozenset(collected)
    return tables


def test_schema_doc_field_tables_match_typed_model() -> None:
    tables = _field_tables_from_schema_doc(SCHEMA_DOC.read_text(encoding="utf-8"))

    assert set(tables) == set(_FIELD_TABLE_MODELS)
    for heading, model in _FIELD_TABLE_MODELS.items():
        assert tables[heading] == {field.name for field in fields(model)}
