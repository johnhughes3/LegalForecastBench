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
    LOCAL_CLI_AUTH_ENV_VARS,
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
    project_structured_stdout_deliverable,
)
from legalforecast.multiharness.sandbox import NETWORK_NONE, PROVIDER_EGRESS_HOST_ONLY
from legalforecast.multiharness.spec import POSIX_PROCESS_GROUP_CONTAINMENT

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "local_cli_adapters"
CLAUDE_FIXTURE = FIXTURE_DIR / "claude-code.json"
CODEX_FIXTURE = FIXTURE_DIR / "codex-cli.json"
SCHEMA_DOC = ROOT / "docs" / "schemas" / "local-cli-adapter-manifest-v1.md"
CLAUDE_SHA256 = "55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9"
CODEX_SHA256 = "cb0a15567e9a60a5820d54b0f6ae86d504dc3805c1eab21a47f70e3eb7b73a40"


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
            "version": "2.1.233 (Claude Code)",
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
                "{output_schema}",
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
            "deliverable_event_type": None,
            "deliverable_item_type": None,
            "deliverable_field": "result",
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
            "version": "codex-cli 0.147.0",
            "sha256": CODEX_SHA256,
            "distribution_kind": "homebrew-cask",
        },
        "capabilities": [
            "headless_print",
            "model_selection",
            "no_session_persistence",
            "permission_mode",
            "stream_json_output",
            "working_directory_isolation",
        ],
        "capability_digest": "sha256:" + "a" * 64,
        "invocation": {
            "headless_mode": "exec_subcommand",
            "argv_template": [
                "exec",
                "--json",
                "--color",
                "never",
                "--ephemeral",
                "--skip-git-repo-check",
                "--strict-config",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "workspace-write",
                "--cd",
                "{workspace}",
                "--model",
                "{model}",
                "-c",
                'approval_policy="never"',
                "-",
            ],
            "output_format": "stream_json",
            "schema_enforcement": "none",
            "prompt_delivery": "stdin",
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
            "deliverable_event_type": "item.completed",
            "deliverable_item_type": "agent_message",
            "deliverable_field": "item.text",
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
    assert (
        claude.to_adapter_manifest(
            command=("legalforecast.multiharness.claude_code:ClaudeCodeAdapter",)
        ).adapter_id
        == claude.manifest_id
    )
    assert claude.to_adapter_manifest(
        command=("legalforecast.multiharness.claude_code:ClaudeCodeAdapter",)
    ).command != (claude.executable.basename,)
    assert "{output_schema}" in claude.invocation.argv_template
    assert "{output_schema_path}" not in claude.invocation.argv_template
    assert claude.to_adapter_capabilities().capabilities_sha256 == (
        claude.capability_digest
    )

    assert codex.executable.basename == "codex"
    assert codex.invocation.headless_mode == "exec_subcommand"
    assert codex.invocation.argv_template[0] == "exec"
    assert codex.invocation.output_format == "stream_json"
    assert "stream_json_output" in codex.capabilities
    assert "{output_schema_path}" not in codex.invocation.argv_template
    assert "{output_schema}" not in codex.invocation.argv_template
    assert "{prompt}" not in codex.invocation.argv_template
    assert codex.invocation.prompt_delivery == "stdin"
    assert codex.invocation.schema_enforcement == "none"
    assert codex.invocation.argv_template[-1] == "-"
    assert "workspace-write" in codex.invocation.argv_template
    assert 'approval_policy="never"' in codex.invocation.argv_template
    assert "--approve-for-me" not in codex.invocation.argv_template
    assert "--ask-for-approval" not in codex.invocation.argv_template
    assert "--json" in codex.invocation.argv_template
    assert "--cd" in codex.invocation.argv_template
    assert "--model" in codex.invocation.argv_template
    assert codex.task_projection.deliverable_event_type == "item.completed"
    assert codex.task_projection.deliverable_item_type == "agent_message"
    assert codex.task_projection.deliverable_field == "item.text"
    assert claude.task_projection.deliverable_field == "result"
    assert claude.task_projection.deliverable_event_type is None
    assert set(claude.capabilities).issubset(LOCAL_CLI_CAPABILITIES)
    assert set(codex.capabilities).issubset(LOCAL_CLI_CAPABILITIES)
    assert claude.auth_profile_name in AUTH_PROFILE_NAMES
    assert "claude" not in json.dumps(codex.to_record())


def test_missing_executable_digest_is_rejected() -> None:
    record = _claude_record()
    del record["executable"]["sha256"]

    with pytest.raises(LocalCliAdapterManifestError, match="sha256"):
        LocalCliAdapterManifest.from_record(record)


def _rehash(record: dict[str, Any]) -> dict[str, Any]:
    record["capability_digest"] = capability_digest_for(record)
    return record


CONTAINER_IMAGE_DIGEST = "sha256:" + "3b" * 32
CONTAINERIZED_TOKENS = (
    "container_execution",
    "max_turns",
    "native_tools_enabled",
    "reasoning_effort",
    "restricted_egress",
    "server_side_web_tools_disabled",
)


def _containerized_record() -> dict[str, Any]:
    """The clean-native fixture recast as a containerized, tools-on harness.

    Expressed as a delta so the test names exactly what the second posture
    changes: the identity pin moves from host bytes to the image digest, the
    stripped-tools token gives way to the tools-on tokens, and the cost basis
    becomes the subscription one every harness in this lane runs on.
    """

    record = _claude_record()
    record["manifest_id"] = "containerized-tools-on-fixture"
    record["display_name"] = "Containerized tools-on local CLI fixture"
    record["harness_binding"] = _binding("containerized-tools-on-fixture")
    record["executable"] = {
        "basename": "example-cli",
        "version": "1.0.0",
        "container_image_digest": CONTAINER_IMAGE_DIGEST,
        "distribution_kind": "standalone-cli",
    }
    declared = set(record["capabilities"]) - {"empty_tools"}
    record["capabilities"] = sorted(declared.union(CONTAINERIZED_TOKENS))
    record["usage_reporting"]["cost_basis"] = "subscription_unallocable"
    return _rehash(record)


def test_containerized_tools_on_manifest_round_trips() -> None:
    record = _containerized_record()

    manifest = LocalCliAdapterManifest.from_record(record)

    assert manifest.to_record() == record
    assert manifest.executable.container_image_digest == CONTAINER_IMAGE_DIGEST
    assert manifest.executable.sha256 is None
    assert "sha256" not in manifest.to_record()["executable"]
    assert manifest.usage_reporting.cost_basis == "subscription_unallocable"
    assert manifest.containment.network_policy == PROVIDER_EGRESS_HOST_ONLY
    assert "empty_tools" not in manifest.capabilities


def test_new_capability_tokens_are_published_verbatim() -> None:
    assert set(CONTAINERIZED_TOKENS).issubset(LOCAL_CLI_CAPABILITIES)


def test_new_auth_environment_variable_names_are_published_verbatim() -> None:
    assert {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROK_AUTH_PROVIDER_ACCESS_TOKEN",
        "GROK_AUTH_PROVIDER_EXPIRES_AT",
        "GROK_AUTH_PROVIDER_REFRESH_TOKEN",
        "KIMI_API_KEY",
        "KIMI_CODE_OAUTH_KEY",
        "XAI_API_KEY",
    }.issubset(LOCAL_CLI_AUTH_ENV_VARS)


def test_new_auth_environment_variable_names_are_accepted_on_a_manifest() -> None:
    record = _containerized_record()
    record["supported_auth_profiles"] = ["contributor-subscription", "fixture-none"]
    record["auth_profile_name"] = "contributor-subscription"
    record["auth_environment_variables"] = [
        {
            "names": [
                "GROK_AUTH_PROVIDER_ACCESS_TOKEN",
                "GROK_AUTH_PROVIDER_EXPIRES_AT",
                "GROK_AUTH_PROVIDER_REFRESH_TOKEN",
            ],
            "profile": "contributor-subscription",
        },
        {"names": [], "profile": "fixture-none"},
    ]

    manifest = LocalCliAdapterManifest.from_record(_rehash(record))

    assert manifest.env_vars_for_profile("contributor-subscription") == (
        "GROK_AUTH_PROVIDER_ACCESS_TOKEN",
        "GROK_AUTH_PROVIDER_EXPIRES_AT",
        "GROK_AUTH_PROVIDER_REFRESH_TOKEN",
    )


def test_executable_rejects_both_identity_digests() -> None:
    record = _containerized_record()
    record["executable"]["sha256"] = CLAUDE_SHA256

    with pytest.raises(LocalCliAdapterManifestError, match="exactly one"):
        LocalCliAdapterManifest.from_record(record)


def test_executable_rejects_an_unprefixed_container_image_digest() -> None:
    record = _containerized_record()
    record["executable"]["container_image_digest"] = "3b" * 32

    with pytest.raises(LocalCliAdapterManifestError, match="sha256:-prefixed"):
        LocalCliAdapterManifest.from_record(record)


def test_container_execution_requires_the_image_digest() -> None:
    record = _containerized_record()
    del record["executable"]["container_image_digest"]
    record["executable"]["sha256"] = CLAUDE_SHA256

    with pytest.raises(
        LocalCliAdapterManifestError, match="container_image_digest must"
    ):
        LocalCliAdapterManifest.from_record(record)


def test_image_digest_requires_the_container_execution_token() -> None:
    record = _containerized_record()
    record["capabilities"] = [
        name for name in record["capabilities"] if name != "container_execution"
    ]

    with pytest.raises(LocalCliAdapterManifestError, match="container_execution"):
        LocalCliAdapterManifest.from_record(_rehash(record))


def test_both_tool_postures_cannot_be_declared_at_once() -> None:
    record = _containerized_record()
    record["capabilities"] = sorted([*record["capabilities"], "empty_tools"])

    with pytest.raises(LocalCliAdapterManifestError, match="empty_tools"):
        LocalCliAdapterManifest.from_record(_rehash(record))


def test_tools_on_requires_server_side_web_tools_to_be_disabled() -> None:
    """The contamination gate: case outcomes are one provider-side search away."""

    record = _containerized_record()
    record["capabilities"] = [
        name
        for name in record["capabilities"]
        if name != "server_side_web_tools_disabled"
    ]

    with pytest.raises(
        LocalCliAdapterManifestError, match="server_side_web_tools_disabled"
    ):
        LocalCliAdapterManifest.from_record(_rehash(record))


def test_restricted_egress_requires_a_provider_egress_network_policy() -> None:
    record = _containerized_record()
    record["containment"]["network_policy"] = NETWORK_NONE

    with pytest.raises(LocalCliAdapterManifestError, match="restricted_egress"):
        LocalCliAdapterManifest.from_record(_rehash(record))


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
        output_schema='{"type":"object"}',
    )

    assert argv[0] == "-p"
    assert argv[1] == "Reply with OK"
    assert "{prompt}" not in argv
    assert "claude-haiku-4-5-20251001" in argv
    assert '{"type":"object"}' in argv
    assert "--tools" in argv
    assert argv[argv.index("--tools") + 1] == ""


def test_json_schema_flag_rejects_path_placeholder() -> None:
    record = _claude_record()
    record["invocation"]["argv_template"] = [
        "-p",
        "{prompt}",
        "--json-schema",
        "{output_schema_path}",
        "--model",
        "{model}",
        "--add-dir",
        "{workspace}",
    ]
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="output_schema"):
        LocalCliAdapterManifest.from_record(record)


def test_output_schema_file_rejects_inline_schema_placeholder() -> None:
    record = _codex_record()
    record["invocation"]["schema_enforcement"] = "output_schema_file"
    record["invocation"]["prompt_delivery"] = "argv_placeholder"
    record["invocation"]["argv_template"] = [
        "exec",
        "--output-schema",
        "{output_schema}",
        "{prompt}",
        "--model",
        "{model}",
        "--cd",
        "{workspace}",
    ]
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="output_schema_path"):
        LocalCliAdapterManifest.from_record(record)


def test_adapter_manifest_rejects_target_cli_basename() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())

    with pytest.raises(LocalCliAdapterManifestError, match="basename"):
        manifest.to_adapter_manifest(command=(manifest.executable.basename,))


def test_adapter_manifest_rejects_string_command() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())

    with pytest.raises(LocalCliAdapterManifestError, match="argv sequence"):
        manifest.to_adapter_manifest(
            command="legalforecast.multiharness.claude_code:ClaudeCodeAdapter"
        )


def test_adapter_manifest_rejects_absolute_target_cli_command() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())

    with pytest.raises(LocalCliAdapterManifestError, match="basename"):
        manifest.to_adapter_manifest(command=("/usr/bin/claude",))


def test_argv_template_rejects_host_paths() -> None:
    record = _claude_record()
    record["invocation"]["argv_template"] = [
        "-p",
        "{prompt}",
        "--json-schema",
        "{output_schema}",
        "--model",
        "{model}",
        "--add-dir",
        "/home/alice/bin/tool",
        "{workspace}",
    ]
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="host paths"):
        LocalCliAdapterManifest.from_record(record)


def test_stdin_prompt_delivery_rejects_prompt_placeholder() -> None:
    record = _codex_record()
    template = list(record["invocation"]["argv_template"])
    template[-1] = "{prompt}"
    record["invocation"]["argv_template"] = template
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="stdin prompt delivery"):
        LocalCliAdapterManifest.from_record(record)


def test_schema_enforcement_none_rejects_schema_placeholders() -> None:
    record = _codex_record()
    template = list(record["invocation"]["argv_template"])
    template.insert(-1, "--output-schema")
    template.insert(-1, "{output_schema_path}")
    record["invocation"]["argv_template"] = template
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="schema_enforcement none"):
        LocalCliAdapterManifest.from_record(record)


def test_working_directory_flag_must_appear_in_argv_template() -> None:
    record = _claude_record()
    record["invocation"]["working_directory_flag"] = "--cd"
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(
        LocalCliAdapterManifestError, match="working_directory_flag must appear"
    ):
        LocalCliAdapterManifest.from_record(record)


def test_model_flag_must_appear_in_argv_template() -> None:
    record = _claude_record()
    record["invocation"]["model_flag"] = "--model-id"
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="model_flag must appear"):
        LocalCliAdapterManifest.from_record(record)


def test_stream_json_structured_stdout_requires_event_type() -> None:
    record = _codex_record()
    record["task_projection"]["deliverable_event_type"] = None
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(LocalCliAdapterManifestError, match="deliverable_event_type"):
        LocalCliAdapterManifest.from_record(record)


def test_workspace_relative_file_forbids_event_projection() -> None:
    record = _codex_record()
    record["task_projection"] = {
        "prompt_source": "solver_input_prompt",
        "deliverable_source": "workspace_relative_file",
        "deliverable_relative_path": "codex-output/submission.md",
        "deliverable_event_type": "item.completed",
        "deliverable_item_type": None,
        "deliverable_field": "item.text",
    }
    record["capability_digest"] = capability_digest_for(record)

    with pytest.raises(
        LocalCliAdapterManifestError, match="workspace_relative_file forbids"
    ):
        LocalCliAdapterManifest.from_record(record)


def test_codex_jsonl_deliverable_is_projected_from_the_declared_event() -> None:
    manifest = LocalCliAdapterManifest.from_record(_codex_record())
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "t1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_cmd",
                        "type": "command_execution",
                        "aggregated_output": "ignored",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 3, "output_tokens": 4},
                }
            ),
        ]
    )

    text = project_structured_stdout_deliverable(
        stdout,
        output_format=manifest.invocation.output_format,
        projection=manifest.task_projection,
    )

    assert text == "LEGALFORECAST_FAKE_CODEX_RESULT"


def test_corrupt_jsonl_envelope_fails_deliverable_projection() -> None:
    manifest = LocalCliAdapterManifest.from_record(_codex_record())

    with pytest.raises(LocalCliAdapterManifestError, match="malformed"):
        project_structured_stdout_deliverable(
            '{"type":"thread.started"\nnot-json\n',
            output_format=manifest.invocation.output_format,
            projection=manifest.task_projection,
        )


def test_claude_json_deliverable_is_projected_from_result() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())

    text = project_structured_stdout_deliverable(
        json.dumps({"type": "result", "result": "forecast-json"}),
        output_format=manifest.invocation.output_format,
        projection=manifest.task_projection,
    )

    assert text == "forecast-json"


def test_claude_object_result_is_projected_as_json_text() -> None:
    manifest = LocalCliAdapterManifest.from_record(_claude_record())
    payload = {"case_assessment": "ok", "predictions": []}

    text = project_structured_stdout_deliverable(
        json.dumps({"type": "result", "result": payload}),
        output_format=manifest.invocation.output_format,
        projection=manifest.task_projection,
    )

    assert json.loads(text) == payload
    assert text.endswith("\n")


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


# Absent-allowed keys: the claude record does not carry them, so there is
# nothing to delete. `executable.sha256` stays in the parametrization because
# deleting it leaves neither identity digest set, which the exactly-one rule
# rejects by name.
_ABSENT_ALLOWED_FIELD_PATHS = frozenset({("executable", "container_image_digest")})


def _required_field_paths() -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for field in fields(LocalCliAdapterManifest):
        paths.append((field.name,))
        nested = _NESTED_RECORD_MODELS.get(field.name)
        if nested is None:
            continue
        for inner in fields(nested):
            if (field.name, inner.name) in _ABSENT_ALLOWED_FIELD_PATHS:
                continue
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
