"""The containerized tools-on Codex CLI manifest and its JSONL parser.

Two things are under test and neither needs a container: that the manifest says
what this lane requires it to say, and that the parser reads the posture back
out of a real-shaped ``codex exec --json`` stream rather than trusting the argv
that was supposed to produce it.

The failure fixture is not invented.  It is the shape captured on 2026-08-31
from a real ``codex exec`` run against an empty ``CODEX_HOME`` -- an
unauthenticated call that cost nothing and returned the CLI's own typed
failure: ten top-level ``error`` retry events, one ``item.completed`` error
item, and a terminal ``turn.failed`` carrying ``error.message``, at exit 1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.container_harness.parser_codex_cli import (
    CodexCliStreamError,
    parse_codex_cli_stream,
)
from legalforecast.multiharness.harness_lane.adapter import (
    ContainerCliAdapter,
    ContainerCliAdapterError,
)
from legalforecast.multiharness.harness_lane.harnesses import (
    identity_for_registry_name,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    LocalCliAdapterManifestError,
    capability_digest_for,
    project_structured_stdout_deliverable,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "examples"
    / "adapters"
    / "codex-cli-native"
    / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "codex-cli-container-tools-on"
SHA256 = "sha256:" + "1" * 64

# Modelled on the 0.151.0 envelope characterised on 2026-08-31: thread.started,
# turn.started, item.started/item.completed pairs whose item.type distinguishes
# the kinds, and a terminal turn.completed carrying the only usage block in the
# stream.  There is deliberately NO opening session event -- this CLI emits
# none, which is why nothing here reports a model or a tool inventory.
_TRANSCRIPT_EVENTS: tuple[dict[str, Any], ...] = (
    {"type": "thread.started", "thread_id": "00000000-0000-4000-8000-000000000000"},
    {"type": "turn.started"},
    {"type": "item.started", "item": {"id": "item_0", "type": "reasoning"}},
    {
        "type": "item.completed",
        "item": {"id": "item_0", "type": "reasoning", "text": "Read the record."},
    },
    {"type": "an_event_kind_this_parser_has_never_seen", "payload": {}},
    {
        "type": "item.completed",
        "item": {
            "id": "item_1",
            "type": "command_execution",
            "command": "ls",
            "aggregated_output": "case.txt",
            "exit_code": 0,
            "status": "completed",
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item_2",
            "type": "command_execution",
            "command": "cat case.txt",
            "aggregated_output": "GRANTED",
            "exit_code": 0,
            "status": "completed",
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item_3",
            "type": "file_change",
            "changes": [{"path": "notes.md", "kind": "add"}],
        },
    },
    {
        "type": "item.completed",
        "item": {"id": "item_4", "type": "an_item_kind_this_parser_has_never_seen"},
    },
    {
        "type": "item.completed",
        "item": {"id": "item_5", "type": "agent_message", "text": "GRANTED"},
    },
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 24576,
            "cached_input_tokens": 900,
            "cache_write_input_tokens": 37747,
            "output_tokens": 15,
            "reasoning_output_tokens": 4,
        },
    },
)
# Byte-shaped like the captured 401 run, with the provider URL and request id
# replaced: those are host-run identifiers and this repository is public.
_FAILED_EVENTS: tuple[dict[str, Any], ...] = (
    {"type": "thread.started", "thread_id": "00000000-0000-4000-8000-000000000000"},
    {"type": "turn.started"},
    {"type": "error", "message": "Reconnecting... 1/5 (unexpected status 401)"},
    {"type": "error", "message": "Reconnecting... 2/5 (unexpected status 401)"},
    {
        "type": "item.completed",
        "item": {
            "id": "item_0",
            "type": "error",
            "message": "Falling back from WebSockets to HTTPS transport.",
        },
    },
    {"type": "turn.failed", "error": {"message": "unexpected status 401"}},
)


def _stream(*events: Any) -> str:
    return "".join(f"{json.dumps(event)}\n" for event in events)


def _manifest() -> LocalCliAdapterManifest:
    return LocalCliAdapterManifest.from_record(
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    )


def test_manifest_declares_the_containerized_tools_on_posture() -> None:
    manifest = _manifest()
    assert manifest.manifest_id == REGISTRY_NAME
    assert {
        "container_execution",
        "native_tools_enabled",
        "restricted_egress",
        "server_side_web_tools_disabled",
    }.issubset(manifest.capabilities)
    # empty_tools is the clean-native lane's posture and the opposite of this
    # one; a manifest carrying both would be measuring neither.
    assert "empty_tools" not in manifest.capabilities
    assert manifest.containment.network_policy == "provider_egress_host_only"
    assert manifest.usage_reporting.cost_basis == "subscription_unallocable"
    # No cost field exists anywhere in this envelope, so claiming one would be
    # a number nobody measured.
    assert manifest.usage_reporting.cost_usd_field is None
    assert manifest.executable.sha256 is None
    assert manifest.executable.basename == "codex"
    image = manifest.executable.container_image_digest
    assert image is not None and image.startswith("sha256:")
    assert manifest.invocation.headless_mode == "exec_subcommand"


def test_manifest_capability_digest_is_the_committed_one() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["capability_digest"] == capability_digest_for(record)


def test_manifest_argv_turns_web_search_off_and_keeps_the_inner_sandbox_off() -> None:
    argv = _manifest().invocation.render_argv(
        prompt="forecast this motion",
        model="gpt-5.6-sol",
        workspace="/workspace",
    )
    assert argv[0] == "exec"
    # The prompt is the trailing positional, after every flag, so a prompt that
    # begins with a hyphen cannot be read as one.
    assert argv[-1] == "forecast this motion"
    # Provider-executed retrieval off by flag, not by hope.  No container
    # egress rule reaches a server-side web_search.
    assert 'web_search="disabled"' in argv
    # Codex's own INNER sandbox comes off because this container IS the
    # external sandbox its help text requires; leaving it on would measure a
    # doubly-jailed agent that cannot use the tools this lane exists to test.
    assert "--dangerously-bypass-approvals-and-sandbox" in argv
    assert 'approval_policy="never"' in argv
    # -s/--sandbox would re-impose an inner filesystem jail.
    assert "--sandbox" not in argv and "-s" not in argv
    # Self-sufficient: a clean-HOME container has no config.toml to inherit, so
    # the model is named and the host's config and rules are excluded.
    assert "--model" in argv and "gpt-5.6-sol" in argv
    assert "--ignore-user-config" in argv and "--ignore-rules" in argv
    assert "--ephemeral" in argv
    # /workspace is a plain directory, not a git repo; without this the run
    # fails before any model call.
    assert "--skip-git-repo-check" in argv
    assert argv[argv.index("--cd") + 1] == "/workspace"


def test_manifest_declares_no_mcp_configuration_without_claiming_a_flag() -> None:
    manifest = _manifest()
    # The containment FACT is true -- with --ignore-user-config and a clean
    # container HOME, `codex doctor` reports "mcp servers: 0".  The capability
    # TOKEN is not declared, because `codex exec` has no --strict-mcp-config
    # flag to claim; that token belongs to Claude Code.
    assert manifest.containment.strict_mcp_config is True
    assert "strict_mcp_config" not in manifest.capabilities
    assert manifest.containment.setting_sources == ()
    assert manifest.containment.session_persistence == "forbidden"


def test_manifest_without_the_web_tool_gate_is_refused() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record["capabilities"] = sorted(
        set(record["capabilities"]) - {"server_side_web_tools_disabled"}
    )
    record["capability_digest"] = capability_digest_for(record)
    with pytest.raises(LocalCliAdapterManifestError, match="server_side_web_tools"):
        LocalCliAdapterManifest.from_record(record)


def test_manifest_projection_and_parser_agree_on_the_same_stream() -> None:
    """The generic projector and this parser must not disagree about the answer.

    The projector is what publishes the deliverable and it knows no Codex event
    names -- it follows the manifest's item.completed / agent_message /
    item.text selectors.  If the parser read a different field the lane would
    score one string and report tool evidence about another.
    """

    manifest = _manifest()
    stream = _stream(*_TRANSCRIPT_EVENTS)
    projected = project_structured_stdout_deliverable(
        stream,
        output_format=manifest.invocation.output_format,
        projection=manifest.task_projection,
    )
    assert projected == parse_codex_cli_stream(stream).answer == "GRANTED"


def test_parser_reads_the_tools_and_usage_off_a_real_shaped_stream() -> None:
    parsed = parse_codex_cli_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.answer == "GRANTED"
    assert parsed.failure_class is None
    assert parsed.turn_completed is True
    assert parsed.used_any_tool
    # Order of first appearance, de-duplicated: two command_execution items
    # are one tool.  reasoning and agent_message are the model talking.
    assert parsed.tools_used == ("command_execution", "file_change")
    # The evidence the init event cannot give, because this CLI has none:
    # no provider-executed retrieval item was ever produced.
    assert parsed.server_side_web_calls == 0
    assert parsed.usage.input_tokens == 24576
    assert parsed.usage.output_tokens == 15
    assert parsed.usage.cached_input_tokens == 900
    assert parsed.usage.cache_write_input_tokens == 37747
    assert parsed.usage.reasoning_output_tokens == 4
    assert parsed.error_event_count == 0
    assert parsed.terminal_error_message is None


def test_parser_counts_provider_executed_web_retrievals_that_did_happen() -> None:
    events = list(_TRANSCRIPT_EVENTS)
    events.insert(
        -1,
        {
            "type": "item.completed",
            "item": {"id": "item_6", "type": "web_search", "query": "did the court"},
        },
    )
    parsed = parse_codex_cli_stream(_stream(*events))
    assert parsed.server_side_web_calls == 1
    assert parsed.to_record()["server_side_web_calls"] == 1
    # A server-executed search is not one of the harness's own tools; counting
    # it as one would let a contaminated run look like a healthy tools-on run.
    assert "web_search" not in parsed.tools_used


def test_parser_reports_the_clis_own_typed_failure() -> None:
    parsed = parse_codex_cli_stream(_stream(*_FAILED_EVENTS))
    assert parsed.turn_completed is False
    assert parsed.failure_class is LocalCliFailureClass.CRASH
    assert parsed.terminal_error_message == "unexpected status 401"
    # Codex reconnects internally on transport errors; the count is how an
    # operator sees that a slow run was a retry storm, not model work.
    assert parsed.error_event_count == 2
    assert parsed.answer == ""


def test_parser_reports_a_turn_failed_event_with_no_error_message() -> None:
    events = [*_FAILED_EVENTS[:-1], {"type": "turn.failed"}]
    parsed = parse_codex_cli_stream(_stream(*events))
    assert parsed.failure_class is LocalCliFailureClass.CRASH
    assert parsed.terminal_error_message is not None


def test_parser_calls_a_completed_turn_with_no_answer_a_schema_violation() -> None:
    events = [
        event for event in _TRANSCRIPT_EVENTS if "agent_message" not in str(event)
    ]
    parsed = parse_codex_cli_stream(_stream(*events))
    assert parsed.turn_completed is True
    assert parsed.failure_class is LocalCliFailureClass.SCHEMA_VIOLATION


def test_parser_ignores_event_and_item_kinds_it_does_not_know() -> None:
    parsed = parse_codex_cli_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.unknown_event_types == ("an_event_kind_this_parser_has_never_seen",)
    assert parsed.unknown_item_types == ("an_item_kind_this_parser_has_never_seen",)


def test_parser_tolerates_a_stray_non_json_line() -> None:
    # The real CLI writes exactly this to the console before reading stdin.
    stream = "Reading additional input from stdin...\n" + _stream(*_TRANSCRIPT_EVENTS)
    assert parse_codex_cli_stream(stream).answer == "GRANTED"


def test_parser_requires_a_terminal_turn_event() -> None:
    stream = _stream(*_TRANSCRIPT_EVENTS[:-1])
    with pytest.raises(
        CodexCliStreamError, match=re.escape("turn.completed or turn.failed")
    ):
        parse_codex_cli_stream(stream)


def test_parser_record_carries_no_transcript_and_no_error_text() -> None:
    record = parse_codex_cli_stream(_stream(*_FAILED_EVENTS)).to_record()
    assert "answer" not in record
    # The observed messages embed provider URLs and request ids, and this
    # record reaches a published summary.
    assert "terminal_error_message" not in record
    assert record["terminal_error"] is True
    assert record["answer_characters"] == 0
    assert record["failure_class"] == "crash"


def test_adapter_runs_the_manifest_argv_and_publishes_the_egress_evidence(
    tmp_path: Path,
) -> None:
    seen: list[ContainerHarnessSpec] = []

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        seen.append(spec)
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout = spec.log_root / "stdout"
        stderr = spec.log_root / "stderr"
        stdout.write_text(_stream(*_TRANSCRIPT_EVENTS), encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=9.0,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("api.openai.com",),
            refused=(
                {"host": "example.com", "port": 443, "reason": "host_not_allowlisted"},
            ),
            allowlist=spec.allowlist().to_record(),
        )

    manifest = _manifest()
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name(REGISTRY_NAME),
        local_manifest=manifest,
        auth_profile=FIXTURE_NONE,
        allow_hosts=("api.openai.com", "auth.openai.com"),
        parent_env={},
        runner=runner,
    )
    result = adapter.run(_request(manifest), tmp_path)

    assert result.status == "succeeded"
    assert result.public_summary["native_tools_enabled"] is True
    assert result.public_summary["server_side_web_tools_disabled"] is True
    assert result.public_summary["egress_refused"] == [
        {"host": "example.com", "port": 443, "reason": "host_not_allowlisted"}
    ]
    assert seen[0].image == manifest.executable.container_image_digest
    assert seen[0].harness_argv[0] == "exec"
    assert 'web_search="disabled"' in seen[0].harness_argv
    # No provider key reaches the container: `codex` declares no extra child
    # environment, so the child gets HOME plus the proxy variables and nothing
    # that could authenticate a fallback API call.
    assert "OPENAI_API_KEY" not in seen[0].environment
    # Real token counts, and no dollar figure at all: there is no cost field
    # anywhere in this envelope, which is why the manifest's `cost_usd_field`
    # is null.  An absent cost is published as absent, not as 0.0.
    assert result.public_summary["usage_reporting"] == "cli_reported_usage"
    assert result.public_summary["input_tokens"] == 24576
    assert result.public_summary["output_tokens"] == 15
    assert manifest.usage_reporting.cost_usd_field is None
    assert result.public_summary["usage"]["imputed_cost_usd"] is None
    assert result.public_summary["usage"]["cost_metering"] == "unreported"
    assert "estimated_cost" not in result.public_summary


def test_adapter_refuses_the_clean_native_manifest_under_this_family() -> None:
    clean_native = LocalCliAdapterManifest.from_record(
        json.loads(
            (
                ROOT / "examples" / "adapters" / "codex-cli" / "local-cli-manifest.json"
            ).read_text(encoding="utf-8")
        )
    )
    with pytest.raises(ContainerCliAdapterError, match="missing capabilities"):
        ContainerCliAdapter(
            identity=identity_for_registry_name(REGISTRY_NAME),
            local_manifest=clean_native,
            auth_profile=FIXTURE_NONE,
            parent_env={},
        )


def _request(manifest: LocalCliAdapterManifest) -> RunRequest:
    adapter_manifest = manifest.to_adapter_manifest(
        command=("legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",)
    )
    return RunRequest(
        request_id="codex-container-smoke",
        task=CanonicalTask(
            task_id="lfb:codex-container-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="codex-container-smoke",
            task_sha256=SHA256,
            metadata={"solver_prompt": "Forecast the motion."},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key="gpt-5.6-sol",
        sandbox_policy=SandboxPolicy(
            policy_id="codex-container-smoke",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=900,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )
