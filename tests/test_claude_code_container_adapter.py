"""The containerized tools-on Claude Code manifest and its stream parser.

Two things are under test and neither needs a container: that the manifest says
what this lane requires it to say, and that the parser reads the posture back
out of a real ``stream-json`` envelope rather than trusting the argv that was
supposed to produce it.  The live end-to-end proof is
``tests/test_claude_code_container_smoke.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.container_harness.parsers import (
    ClaudeCodeStreamError,
    parse_claude_code_stream,
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
    / "claude-code-native"
    / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "claude-code-container-tools-on"
SHA256 = "sha256:" + "1" * 64

# Modelled on the 2.1.251 envelope characterised on 2026-08-31: a system/init
# event, an out-of-band rate_limit_event, a tool_use turn, its tool_result, and
# the terminal result event.
_TRANSCRIPT_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "type": "system",
        "subtype": "init",
        "cwd": "/workspace",
        "model": "claude-opus-5",
        "permissionMode": "bypassPermissions",
        "apiKeySource": "none",
        "tools": ["Bash", "Edit", "Read", "StructuredOutput", "Task", "Write"],
        "mcp_servers": [],
    },
    {"type": "rate_limit_event", "rate_limit_info": {}},
    {"type": "an_event_kind_this_parser_has_never_seen", "payload": {}},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Reading the record."},
                {"type": "tool_use", "name": "Read", "input": {"file": "case.txt"}},
            ]
        },
    },
    {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                {"type": "tool_use", "name": "Read", "input": {"file": "b.txt"}},
            ]
        },
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "stop_reason": "end_turn",
        "terminal_reason": "completed",
        "api_error_status": None,
        "result": "GRANTED",
        "num_turns": 4,
        "duration_ms": 3656,
        "total_cost_usd": 0.0421,
        "usage": {
            "input_tokens": 41,
            "output_tokens": 12,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 37747,
            "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        },
    },
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
    assert manifest.executable.sha256 is None
    image = manifest.executable.container_image_digest
    assert image is not None and image.startswith("sha256:")


def test_manifest_capability_digest_is_the_committed_one() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["capability_digest"] == capability_digest_for(record)


def test_manifest_argv_turns_web_tools_off_and_keeps_local_tools_on() -> None:
    argv = _manifest().invocation.render_argv(
        prompt="forecast this motion",
        model="sonnet",
        workspace="/workspace",
    )
    assert argv[:2] == ("-p", "forecast this motion")
    assert "--disallowedTools" in argv
    denied = argv[argv.index("--disallowedTools") + 1 : argv.index("--safe-mode")]
    assert set(denied) == {"WebSearch", "WebFetch"}
    # --tools "" is the clean-native lane's tool-stripping flag; using it here
    # would delete the very capability this lane measures.
    assert "--tools" not in argv
    assert "--permission-mode" in argv and "bypassPermissions" in argv
    assert "--max-budget-usd" in argv
    assert "--json-schema" not in argv


def test_manifest_without_the_web_tool_gate_is_refused() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record["capabilities"] = sorted(
        set(record["capabilities"]) - {"server_side_web_tools_disabled"}
    )
    record["capability_digest"] = capability_digest_for(record)
    with pytest.raises(LocalCliAdapterManifestError, match="server_side_web_tools"):
        LocalCliAdapterManifest.from_record(record)


def test_parser_reads_the_posture_and_the_tools_off_a_real_shaped_stream() -> None:
    parsed = parse_claude_code_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.answer == "GRANTED"
    assert parsed.failure_class is None
    assert parsed.model == "claude-opus-5"
    assert parsed.permission_mode == "bypassPermissions"
    # apiKeySource "none" is how a run shows it spent the subscription login
    # rather than an ANTHROPIC_API_KEY that leaked in from the environment.
    assert parsed.api_key_source == "none"
    assert parsed.used_any_tool
    assert parsed.tools_used == ("Read", "Bash")
    assert parsed.server_side_web_tools_available == ()
    assert parsed.usage.input_tokens == 41
    assert parsed.usage.cache_creation_input_tokens == 37747
    assert parsed.usage.total_cost_usd == pytest.approx(0.0421)
    assert parsed.usage.num_turns == 4
    # The provider's own count of server-executed retrievals, which is the
    # evidence the init tool list cannot give: nothing came back over a channel
    # the container's egress fence never sees.
    assert parsed.server_side_web_requests == 0


def test_parser_counts_server_executed_web_retrievals_that_did_happen() -> None:
    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    usage = dict(events[-1]["usage"])
    usage["server_tool_use"] = {"web_search_requests": 2, "web_fetch_requests": 1}
    events[-1] = {**events[-1], "usage": usage}
    parsed = parse_claude_code_stream(_stream(*events))
    assert parsed.server_side_web_requests == 3
    assert parsed.to_record()["server_side_web_requests"] == 3


def test_parser_ignores_event_kinds_it_does_not_know() -> None:
    parsed = parse_claude_code_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.unknown_event_types == (
        "an_event_kind_this_parser_has_never_seen",
        "rate_limit_event",
    )


def test_parser_tolerates_a_stray_non_json_line() -> None:
    stream = _stream(*_TRANSCRIPT_EVENTS).replace(
        '{"type": "rate_limit_event"', 'not json at all\n{"type": "rate_limit_event"', 1
    )
    assert parse_claude_code_stream(stream).answer == "GRANTED"


def test_parser_reports_web_tools_that_were_still_available() -> None:
    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[0]["tools"] = ["Bash", "Read", "WebFetch", "WebSearch"]
    parsed = parse_claude_code_stream(_stream(*events))
    assert parsed.server_side_web_tools_available == ("WebFetch", "WebSearch")


def test_parser_requires_a_terminal_result_event() -> None:
    stream = _stream(*_TRANSCRIPT_EVENTS[:-1])
    with pytest.raises(ClaudeCodeStreamError, match="no terminal result event"):
        parse_claude_code_stream(stream)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"is_error": True, "subtype": "error_during_execution"},
            LocalCliFailureClass.CRASH,
        ),
        (
            {"is_error": True, "subtype": "error_max_turns"},
            LocalCliFailureClass.TIMEOUT,
        ),
        (
            {"is_error": True, "subtype": "error_refusal", "stop_reason": "refusal"},
            LocalCliFailureClass.REFUSAL,
        ),
        (
            {"is_error": True, "subtype": "error", "api_error_status": "529"},
            LocalCliFailureClass.CRASH,
        ),
        ({"result": "   "}, LocalCliFailureClass.SCHEMA_VIOLATION),
    ],
)
def test_parser_classifies_failures_from_the_terminal_event(
    overrides: dict[str, Any], expected: LocalCliFailureClass
) -> None:
    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[-1] = {**events[-1], **overrides}
    assert parse_claude_code_stream(_stream(*events)).failure_class is expected


def test_parser_record_carries_no_transcript(tmp_path: Path) -> None:
    del tmp_path
    record = parse_claude_code_stream(_stream(*_TRANSCRIPT_EVENTS)).to_record()
    assert "answer" not in record
    assert record["answer_characters"] == len("GRANTED")
    assert record["tools_used"] == ["Read", "Bash"]


def test_adapter_runs_the_manifest_argv_and_publishes_the_egress_evidence(
    tmp_path: Path,
) -> None:
    seen: list[ContainerHarnessSpec] = []

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        seen.append(spec)
        stdout = spec.log_root / "stdout"
        stderr = spec.log_root / "stderr"
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout.write_text(_stream(*_TRANSCRIPT_EVENTS), encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=12.5,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("api.anthropic.com",),
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
        allow_hosts=("api.anthropic.com", "platform.claude.com"),
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
    assert "--disallowedTools" in seen[0].harness_argv


def test_adapter_refuses_the_clean_native_manifest_under_this_family() -> None:
    clean_native = LocalCliAdapterManifest.from_record(
        json.loads(
            (
                ROOT
                / "examples"
                / "adapters"
                / "claude-code"
                / "local-cli-adapter-manifest.json"
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


def _summary_for(tmp_path: Path, stdout: str) -> dict[str, Any]:
    """Return the public summary of one adapter run over a canned transcript."""

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout_path = spec.log_root / "stdout"
        stderr_path = spec.log_root / "stderr"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=12.5,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("api.anthropic.com",),
            refused=(),
            allowlist=spec.allowlist().to_record(),
        )

    manifest = _manifest()
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name(REGISTRY_NAME),
        local_manifest=manifest,
        auth_profile=FIXTURE_NONE,
        allow_hosts=("api.anthropic.com",),
        parent_env={},
        runner=runner,
    )
    return dict(adapter.run(_request(manifest), tmp_path).public_summary)


def test_adapter_publishes_the_tokens_the_transcript_reported(
    tmp_path: Path,
) -> None:
    """Real counts reach the summary the release projection reads.

    Before this projection every LFB row carried ``input_tokens: 0`` because
    the adapter never carried the parsed usage across, which read as "this
    harness spent no tokens" rather than "nobody looked".
    """

    summary = _summary_for(tmp_path, _stream(*_TRANSCRIPT_EVENTS))

    assert summary["usage_reporting"] == "cli_reported_usage"
    assert summary["input_tokens"] == 41
    assert summary["output_tokens"] == 12
    assert summary["usage"]["cache_read_tokens"] == 900
    assert summary["usage"]["cache_write_tokens"] == 37747
    assert summary["usage"]["caveats"] == []


def test_the_dollar_figure_is_published_as_an_imputation_not_as_spend(
    tmp_path: Path,
) -> None:
    """This lane runs on a subscription, so no per-run dollar was metered.

    ``total_cost_usd`` is the CLI's list-price estimate of what the same tokens
    would have cost on the API.  It is published labelled, and it is kept out
    of ``estimated_cost``, which the release projection copies into the LFB row
    as an unlabelled float that reads as money.
    """

    summary = _summary_for(tmp_path, _stream(*_TRANSCRIPT_EVENTS))

    assert summary["usage"]["imputed_cost_usd"] == 0.0421
    assert summary["usage"]["cost_metering"] == "imputed_list_price"
    assert summary["usage"]["cost_basis"] == "subscription_unallocable"
    assert "estimated_cost" not in summary


def test_an_empty_usage_block_is_published_as_unreported(tmp_path: Path) -> None:
    """The parser fills absent fields with zeros; zeros are not a measurement.

    A turn that reached the model cannot have spent zero input and zero output
    tokens, so an all-zero block is a missing accounting object.
    """

    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[-1] = {**events[-1], "usage": {}, "total_cost_usd": None}
    summary = _summary_for(tmp_path, _stream(*events))

    assert summary["usage_reporting"] == "unreported"
    assert "input_tokens" not in summary
    assert "output_tokens" not in summary
    assert summary["usage"]["input_tokens"] is None
    assert summary["usage"]["caveats"] == ["empty_usage_block"]


def _request(manifest: LocalCliAdapterManifest) -> RunRequest:
    adapter_manifest = manifest.to_adapter_manifest(
        command=("legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",)
    )
    return RunRequest(
        request_id="container-smoke",
        task=CanonicalTask(
            task_id="lfb:container-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="container-smoke",
            task_sha256=SHA256,
            metadata={"solver_prompt": "Forecast the motion."},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key="sonnet",
        sandbox_policy=SandboxPolicy(
            policy_id="container-smoke",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=900,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )
