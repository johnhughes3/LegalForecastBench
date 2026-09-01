"""Closed vocabulary for the local CLI adapter manifest schema.

Every set here is a fail-closed enum: ``local_cli_manifest`` rejects any
member a manifest names that is absent from these sets, so a new harness
registers by shipping a manifest built from this vocabulary rather than by
editing a central switch.  The vocabulary lives in its own module because
several lanes extend it concurrently while ``local_cli_manifest.py`` sits
above its reviewed line ceiling.

Two postures are describable.  The *clean-native* posture (Claude Code,
Codex CLI) runs the CLI as a host process with its tool suite stripped.  The
*containerized tools-on* posture runs the CLI inside a digest-pinned
container image with its own local tools live, which is the only posture
that can measure whether a harness beats the bare provider API.  The tokens
that separate the two are enumerated in ``LOCAL_CLI_CAPABILITIES`` below and
are cross-checked against each other in ``LocalCliAdapterManifest``.
"""

from __future__ import annotations

# Owned by dm0g.4.2.5. This lane stores the name only; do not duplicate profile
# semantics or credential projection here.
AUTH_PROFILE_NAMES = frozenset(
    {
        "contributor-subscription",
        "fixture-none",
        "published-api-key",
    }
)
# Public environment-variable NAMES a manifest may declare for projection.
# Values, files, and Infisical paths never appear on a manifest.  The three
# GROK_AUTH_PROVIDER_* names are one set: xAI's documented token-injection
# path supplies access token, refresh token, and expiry together, and a
# container cannot complete an interactive browser login to obtain them.
LOCAL_CLI_AUTH_ENV_VARS = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROK_AUTH_PROVIDER_ACCESS_TOKEN",
        "GROK_AUTH_PROVIDER_EXPIRES_AT",
        "GROK_AUTH_PROVIDER_REFRESH_TOKEN",
        "KIMI_API_KEY",
        "KIMI_CODE_OAUTH_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
    }
)
# Capability tokens double as posture declarations: they are covered by
# ``capability_digest``, so changing the tool or containment posture of a
# manifest is visible as a digest change.  Executable identity is not covered,
# so rebuilding an image or upgrading a binary is identity drift, not
# capability drift.
LOCAL_CLI_CAPABILITIES = frozenset(
    {
        "container_execution",
        "empty_tools",
        "headless_print",
        "isolated_setting_sources",
        "json_output",
        "json_schema_enforcement",
        "max_budget_usd",
        "max_turns",
        "model_selection",
        "native_tools_enabled",
        "no_session_persistence",
        "permission_mode",
        "reasoning_effort",
        "restricted_egress",
        "server_side_web_tools_disabled",
        "stream_json_output",
        "strict_mcp_config",
        "tool_allowlist",
        "working_directory_isolation",
    }
)
LOCAL_CLI_DISTRIBUTION_KINDS = frozenset(
    {
        "fixture",
        "homebrew-cask",
        "sdk-bundled",
        "standalone-cli",
    }
)
LOCAL_CLI_HEADLESS_MODES = frozenset({"exec_subcommand", "print_flag"})
LOCAL_CLI_OUTPUT_FORMATS = frozenset({"json", "stream_json", "text"})
LOCAL_CLI_SCHEMA_ENFORCEMENT = frozenset(
    {
        "json_schema_flag",
        "none",
        "output_schema_file",
    }
)
LOCAL_CLI_PROMPT_DELIVERY = frozenset({"argv_placeholder", "stdin"})
LOCAL_CLI_SESSION_PERSISTENCE = frozenset({"ephemeral", "forbidden", "none"})
LOCAL_CLI_SETTING_SOURCES = frozenset({"local", "project", "user"})
LOCAL_CLI_TRANSCRIPT_POINTS = frozenset(
    {
        "private_execution_log",
        "session_transcript",
        "stderr",
        "stdout",
    }
)
LOCAL_CLI_COST_BASES = frozenset(
    {
        "estimated_from_pricing_snapshot",
        "metered",
        "provider_reported",
        "subscription_unallocable",
        "unknown",
    }
)
# Where a row's prompt bytes come from. ``solver_input_prompt`` is the private
# LFB store, whose exact bytes are proved against the task's own commitment.
# A projected Harvey LAB task has no such store -- its file set is a directory
# of documents -- so its prompt is the projection's own ``instructions``
# artifact, staged with the documents and named here so a manifest cannot
# claim an authenticated prompt source it never reads.
LOCAL_CLI_SOLVER_INPUT_PROMPT = "solver_input_prompt"
LOCAL_CLI_PROJECTED_TASK_INSTRUCTIONS = "projected_task_instructions"
LOCAL_CLI_PROMPT_SOURCES = frozenset(
    {LOCAL_CLI_SOLVER_INPUT_PROMPT, LOCAL_CLI_PROJECTED_TASK_INSTRUCTIONS}
)
LOCAL_CLI_DELIVERABLE_SOURCES = frozenset(
    {
        "structured_stdout",
        "workspace_relative_file",
    }
)
LOCAL_CLI_ARGV_PLACEHOLDERS = frozenset(
    {
        "model",
        "output_schema",
        "output_schema_path",
        "prompt",
        "workspace",
    }
)
LOCAL_CLI_USAGE_SOLVER_FIELDS = frozenset(
    {
        "estimated_cost",
        "input_tokens",
        "output_tokens",
        "request_count",
    }
)

# Tool posture: a manifest declares at most one of these.  ``empty_tools`` is
# the stripped clean-native posture; ``native_tools_enabled`` keeps the CLI's
# own local tools (read/write/bash/grep/subagents) live.
LOCAL_CLI_EMPTY_TOOLS = "empty_tools"
LOCAL_CLI_NATIVE_TOOLS_ENABLED = "native_tools_enabled"
# Provider-executed web retrieval (server-side web_search / web_fetch) runs on
# the provider's infrastructure, so no container egress rule can stop it.  The
# forecast targets are real federal cases whose outcomes are one search away,
# so a tools-on manifest must state that no provider-executed web retrieval is
# available to the run -- disabled by flag, or absent by construction.
LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED = "server_side_web_tools_disabled"
# The CLI runs inside a digest-pinned container image rather than as a host
# process; paired with ``executable.container_image_digest``.
LOCAL_CLI_CONTAINER_EXECUTION = "container_execution"
# Egress is confined to an allowlist reaching provider API and auth endpoints
# only, which is exactly the existing ``provider_egress_host_only`` policy.
LOCAL_CLI_RESTRICTED_EGRESS = "restricted_egress"
