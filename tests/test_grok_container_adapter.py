"""The containerized tools-on Grok manifest and its headless-envelope parser.

No live Grok run backs any of this, which is a finding rather than a gap: the
owner's Grok Build usage balance is exhausted, so the single permitted
2026-08-31 probe returned ``HTTP 402`` and no second attempt is allowed.  That
probe's 171 bytes are the only real Grok output in the tree and they are the
fixture in ``_QUOTA_EXHAUSTED_STDOUT``: an out-of-credit account is the failure
this parser will meet next, so it is tested against captured bytes rather than
against something invented.

The success path is synthesised from the CLI's bundled documentation, so these
tests prove the shape the adapter depends on -- terminal ``result`` line,
``tool_use`` blocks, usage block -- and cannot prove xAI emits it.  The
manifest and image checks are real: the image was built and its ``grok
--help`` ran offline in a clean HOME.
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
from legalforecast.multiharness.container_harness.parser_grok import (
    GrokFailureKind,
    GrokStreamError,
    classify_grok_error,
    parse_grok_stream,
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
    ROOT / "examples" / "adapters" / "grok-native" / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "grok-cli-container-tools-on"
QUOTA = GrokFailureKind.QUOTA_EXHAUSTED
RATE_LIMITED = GrokFailureKind.RATE_LIMITED
AUTH = GrokFailureKind.AUTH
UNKNOWN = GrokFailureKind.UNKNOWN_ERROR
SHA256 = "sha256:" + "1" * 64

# The real captured stdout of the 2026-08-31 probe, byte for byte.  The CLI
# printed well-formed JSON even on the failure path, which is why the parser
# reads stdout rather than an exit code that cannot tell "out of credits" from
# "logged out".
_QUOTA_EXHAUSTED_STDOUT = (
    '{"type":"error","message":"Internal error: {\\n  \\"message\\": \\"API error '
    '(status 402 Payment Required): Grok Build usage balance exhausted\\",\\n  '
    '\\"http_status\\": 402\\n}"}\n'
)

# Shaped from the CLI's documentation of --output-format streaming-messages-json
# (NDJSON in the Anthropic Messages wire format), not from an observed run.
_TRANSCRIPT_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "type": "system",
        "subtype": "init",
        "model": "grok-4.6",
        "tools": ["read_file", "run_terminal_cmd", "grep_search"],
    },
    {"type": "an_event_kind_this_parser_has_never_seen", "payload": {}},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Reading the record."},
                {
                    "type": "tool_use",
                    "name": "read_file",
                    "input": {"path": "case.txt"},
                },
            ]
        },
    },
    {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "run_terminal_cmd",
                    "input": {"command": "ls"},
                },
                {
                    "type": "tool_use",
                    "name": "read_file",
                    "input": {"path": "b.txt"},
                },
            ]
        },
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "stop_reason": "end_turn",
        "result": "GRANTED",
        "num_turns": 4,
        "duration_ms": 4211,
        "total_cost_usd": 0.0312,
        "cost_is_partial": False,
        "usage_is_incomplete": False,
        "modelUsage": {"grok-4.6": {"modelCalls": 3, "costUSD": 0.0312}},
        "usage": {
            "input_tokens": 57,
            "output_tokens": 14,
            "cache_read_input_tokens": 880,
            "cache_creation_input_tokens": 20114,
            "reasoning_tokens": 512,
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


def test_manifest_admits_that_grok_cannot_stop_writing_sessions() -> None:
    """Grok has no flag or config key that disables session persistence.

    ``ephemeral`` is the honest declaration -- transcripts land in the run's
    throwaway container HOME and die with it -- where the
    ``no_session_persistence`` capability would claim a flag that does not
    exist.
    """

    manifest = _manifest()
    assert manifest.containment.session_persistence == "ephemeral"
    assert "no_session_persistence" not in manifest.capabilities


def test_manifest_capability_digest_is_the_committed_one() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["capability_digest"] == capability_digest_for(record)


def test_manifest_argv_is_flag_explicit_because_the_container_has_no_config() -> None:
    """Grok's model, effort and permission posture live in ~/.grok/config.toml.

    None of the three is a binary default and the run's HOME holds only the
    staged login, so inheriting them would silently fall back to
    ``--permission-mode default`` (ask) and the catalogue's ``high`` effort.
    """

    argv = _manifest().invocation.render_argv(
        prompt="forecast this motion",
        model="grok-4.6",
        workspace="/workspace",
    )
    assert argv[:2] == ("-p", "forecast this motion")
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    assert argv[argv.index("--model") + 1] == "grok-4.6"
    assert argv[argv.index("--reasoning-effort") + 1] == "xhigh"
    assert argv[argv.index("--cwd") + 1] == "/workspace"
    assert argv[argv.index("--output-format") + 1] == "streaming-messages-json"
    # Provider-executed retrieval runs downstream of the egress fence, and this
    # one flag turns off both web_search and web_fetch.
    assert "--disable-web-search" in argv
    # The prompt must reach the model byte-exact.
    assert "--verbatim" in argv
    # --tools is grok's headless allowlist; naming it here would strip the very
    # capability this lane measures.  --json-schema is out because this lane's
    # schema_enforcement is "none" and its landing key was never verified.
    assert "--tools" not in argv
    assert "--json-schema" not in argv


def test_manifest_without_the_web_tool_gate_is_refused() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record["capabilities"] = sorted(
        set(record["capabilities"]) - {"server_side_web_tools_disabled"}
    )
    record["capability_digest"] = capability_digest_for(record)
    with pytest.raises(LocalCliAdapterManifestError, match="server_side_web_tools"):
        LocalCliAdapterManifest.from_record(record)


def test_parser_names_the_real_402_quota_failure_from_the_captured_bytes() -> None:
    """The only live Grok evidence in this repository, parsed as-is."""

    assert len(_QUOTA_EXHAUSTED_STDOUT.encode("utf-8")) == 171
    parsed = parse_grok_stream(_QUOTA_EXHAUSTED_STDOUT)
    assert parsed.is_error
    assert parsed.error_kind is GrokFailureKind.QUOTA_EXHAUSTED
    assert parsed.failure_kind is GrokFailureKind.QUOTA_EXHAUSTED
    assert parsed.http_status == 402
    assert parsed.error_message is not None
    assert "usage balance exhausted" in parsed.error_message
    assert parsed.answer == ""
    # The shared taxonomy has no billing member, so it degrades to crash; the
    # typed kind is what an operator reads.
    assert parsed.failure_class is LocalCliFailureClass.CRASH
    record = parsed.to_record()
    assert record["error_kind"] == "quota_exhausted"
    assert record["http_status"] == 402
    assert record["failure_class"] == "crash"


def test_parser_survives_prose_after_the_embedded_error_blob() -> None:
    """A greedy ``{.*}`` match would swallow the trailing text and fail."""

    stdout = json.dumps(
        {
            "type": "error",
            "message": (
                'Internal error: {"message": "usage limit reached", '
                '"http_status": 402} (retry later)'
            ),
        }
    )
    parsed = parse_grok_stream(stdout)
    assert parsed.http_status == 402
    assert parsed.error_message == "usage limit reached"
    assert parsed.error_kind is GrokFailureKind.QUOTA_EXHAUSTED


@pytest.mark.parametrize(
    ("message", "status", "expected"),
    [
        ("Grok Build usage balance exhausted", None, QUOTA),
        ("You hit your weekly limit.", None, QUOTA),
        ("You've hit the rate limit for your plan.", None, RATE_LIMITED),
        ("anything at all", 429, RATE_LIMITED),
        ("Not signed in. Run `grok login` to authenticate", None, AUTH),
        ("anything at all", 401, AUTH),
        ("The service is busy.", None, GrokFailureKind.PROVIDER_ERROR),
        ("connection reset by peer", None, UNKNOWN),
    ],
)
def test_error_vocabulary_classifies_without_an_exit_code(
    message: str, status: int | None, expected: GrokFailureKind
) -> None:
    assert classify_grok_error(message, status) is expected


def test_parser_reads_the_posture_and_the_tools_off_a_documented_shaped_stream() -> (
    None
):
    parsed = parse_grok_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.answer == "GRANTED"
    assert parsed.failure_kind is None
    assert parsed.failure_class is None
    assert parsed.model == "grok-4.6"
    assert parsed.used_any_tool
    assert parsed.tools_used == ("read_file", "run_terminal_cmd")
    assert parsed.server_side_web_tools_available == ()
    assert parsed.server_side_web_tools_used == ()
    assert parsed.usage.input_tokens == 57
    assert parsed.usage.cache_creation_input_tokens == 20114
    assert parsed.usage.reasoning_tokens == 512
    assert parsed.usage.total_cost_usd == pytest.approx(0.0312)
    assert parsed.usage.num_turns == 4


def test_parser_reports_provider_executed_web_retrieval_that_did_happen() -> None:
    """No container egress rule reaches xAI's own web_search, so name it."""

    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[0] = {**events[0], "tools": ["read_file", "web_search", "web_fetch"]}
    events[2] = {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "web_search"}]},
    }
    parsed = parse_grok_stream(_stream(*events))
    assert parsed.server_side_web_tools_available == ("web_fetch", "web_search")
    assert parsed.to_record()["server_side_web_tools_used"] == ["web_search"]


def test_parser_falls_back_to_model_usage_when_there_is_no_init_line() -> None:
    events = [event for event in _TRANSCRIPT_EVENTS if event["type"] != "system"]
    assert parse_grok_stream(_stream(*events)).model == "grok-4.6"


def test_parser_ignores_event_kinds_it_does_not_know() -> None:
    parsed = parse_grok_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.unknown_event_types == ("an_event_kind_this_parser_has_never_seen",)


def test_parser_tolerates_a_stray_non_json_line() -> None:
    stream = "warming up\n" + _stream(*_TRANSCRIPT_EVENTS)
    assert parse_grok_stream(stream).answer == "GRANTED"


def test_parser_requires_an_error_object_or_a_terminal_result() -> None:
    stream = _stream(*_TRANSCRIPT_EVENTS[:-1])
    with pytest.raises(GrokStreamError, match="neither an error object"):
        parse_grok_stream(stream)


@pytest.mark.parametrize(
    ("overrides", "kind", "expected"),
    [
        (
            {"is_error": True, "subtype": "error_max_turns"},
            GrokFailureKind.MAX_TURNS,
            LocalCliFailureClass.TIMEOUT,
        ),
        (
            {"is_error": True, "subtype": "error", "stop_reason": "max_turn_requests"},
            GrokFailureKind.MAX_TURNS,
            LocalCliFailureClass.TIMEOUT,
        ),
        (
            {"is_error": True, "subtype": "error", "stop_reason": "refusal"},
            GrokFailureKind.REFUSAL,
            LocalCliFailureClass.REFUSAL,
        ),
        (
            {"is_error": True, "subtype": "error_during_execution"},
            GrokFailureKind.UNKNOWN_ERROR,
            LocalCliFailureClass.CRASH,
        ),
        (
            {"result": "   "},
            GrokFailureKind.EMPTY_ANSWER,
            LocalCliFailureClass.SCHEMA_VIOLATION,
        ),
    ],
)
def test_parser_classifies_failures_from_the_terminal_event(
    overrides: dict[str, Any],
    kind: GrokFailureKind,
    expected: LocalCliFailureClass,
) -> None:
    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[-1] = {**events[-1], **overrides}
    parsed = parse_grok_stream(_stream(*events))
    assert parsed.failure_kind is kind
    assert parsed.failure_class is expected


def test_parser_record_carries_no_transcript_and_no_error_prose() -> None:
    record = parse_grok_stream(_stream(*_TRANSCRIPT_EVENTS)).to_record()
    assert "answer" not in record
    assert "error_message" not in record
    assert record["answer_characters"] == len("GRANTED")
    assert record["tools_used"] == ["read_file", "run_terminal_cmd"]


def test_adapter_runs_the_manifest_argv_and_projects_the_same_bytes(
    tmp_path: Path,
) -> None:
    """The manifest projection and the parser must agree on one transcript.

    The adapter reads the answer through ``task_projection`` and the posture
    comes from ``parse_grok_stream``; disagreement about which line is
    terminal would publish one run's answer beside another's tool evidence.
    """

    seen: list[ContainerHarnessSpec] = []
    transcript = _stream(*_TRANSCRIPT_EVENTS)

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        seen.append(spec)
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout = spec.log_root / "stdout"
        stderr = spec.log_root / "stderr"
        stdout.write_text(transcript, encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=31.2,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("api.x.ai",),
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
        allow_hosts=("api.x.ai", "cli-chat-proxy.grok.com"),
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
    assert "--disable-web-search" in seen[0].harness_argv
    assert parse_grok_stream(transcript).answer == "GRANTED"


def test_adapter_refuses_a_manifest_that_pins_another_harness() -> None:
    """The registry name and the pinned executable must be the same harness."""

    other = LocalCliAdapterManifest.from_record(
        json.loads(
            (
                ROOT
                / "examples"
                / "adapters"
                / "claude-code-native"
                / "local-cli-adapter-manifest.json"
            ).read_text(encoding="utf-8")
        )
    )
    with pytest.raises(ContainerCliAdapterError, match="pins 'claude'"):
        ContainerCliAdapter(
            identity=identity_for_registry_name(REGISTRY_NAME),
            local_manifest=other,
            auth_profile=FIXTURE_NONE,
            parent_env={},
        )


def _request(manifest: LocalCliAdapterManifest) -> RunRequest:
    adapter_manifest = manifest.to_adapter_manifest(
        command=("legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",)
    )
    return RunRequest(
        request_id="grok-container-projection",
        task=CanonicalTask(
            task_id="lfb:grok-container-projection:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="grok-container-projection",
            task_sha256=SHA256,
            metadata={"solver_prompt": "Forecast the motion."},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key="grok-4.6",
        sandbox_policy=SandboxPolicy(
            policy_id="grok-container-projection",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=900,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )
