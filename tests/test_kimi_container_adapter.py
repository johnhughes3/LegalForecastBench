"""The containerized tools-on Kimi Code manifest and its stream parser.

Nothing here needs a container or a provider.  Three things are under test:
that the manifest says what this lane requires it to say, that the parser reads
the run's posture back out of a real-shaped ``stream-json`` envelope, and --
because it is a real, load-bearing gap rather than a hypothetical one -- that
the generic manifest projection cannot read this harness today while the
parser can.

FIXTURE EVIDENCE CLASS.  The ``meta`` lines below reproduce bytes observed live
on 2026-08-31 (``system.version``, and the ``turn.step.retrying`` ladder the
provider's HTTP 500s produced).  The ``assistant`` and ``tool`` lines are
synthetic, built from the CLI's bundled writer source, because that
characterization run never reached a completion.  No session id, host path or
provider message from the live probe is reproduced here.
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
from legalforecast.multiharness.container_harness.parser_kimi import (
    KimiStreamError,
    kimi_deliverable_text,
    parse_kimi_stream,
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
    ROOT / "examples" / "adapters" / "kimi-native" / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "kimi-cli-container-tools-on"
SHA256 = "sha256:" + "1" * 64

# A successful tool-using turn, in the writer's documented order: the version
# line, an assistant flush carrying a tool call, that call's result, and the
# final assistant flush carrying the answer.
_TRANSCRIPT_EVENTS: tuple[dict[str, Any], ...] = (
    {"role": "meta", "type": "system.version", "version": "0.36.0"},
    {
        "role": "assistant",
        "content": "Reading the record.",
        "tool_calls": [
            {
                "type": "function",
                "id": "call_0",
                "function": {"name": "Read", "arguments": '{"path":"case.txt"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_0", "content": "docket text"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "type": "function",
                "id": "call_1",
                "function": {"name": "Bash", "arguments": '{"command":"ls"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "case.txt"},
    {"role": "meta", "type": "an_event_kind_this_parser_has_never_seen"},
    {"role": "assistant", "content": "GRANTED"},
    {
        "role": "meta",
        "type": "session.resume_hint",
        "session_id": "redacted",
        "command": "kimi --continue",
        "content": "resume hint",
    },
)

# Live-observed bytes: the provider returned HTTP 500 and the CLI walked its own
# retry ladder.  Two of the eight observed lines are enough to pin the shape.
_RETRY_STORM_EVENTS: tuple[dict[str, Any], ...] = (
    {"role": "meta", "type": "system.version", "version": "0.36.0"},
    {
        "role": "meta",
        "type": "turn.step.retrying",
        "failed_attempt": 1,
        "next_attempt": 2,
        "max_attempts": 10,
        "delay_ms": 590.9291911895363,
        "error_name": "APIStatusError",
        "error_message": "500 The server had an error while processing your request",
        "status_code": 500,
    },
    {
        "role": "meta",
        "type": "turn.step.retrying",
        "failed_attempt": 2,
        "next_attempt": 3,
        "max_attempts": 10,
        "delay_ms": 1072.3515012900712,
        "error_name": "APIStatusError",
        "error_message": "500 The server had an error while processing your request",
        "status_code": 500,
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
    assert "empty_tools" not in manifest.capabilities
    assert manifest.containment.network_policy == "provider_egress_host_only"
    assert manifest.executable.sha256 is None
    image = manifest.executable.container_image_digest
    assert image is not None and image.startswith("sha256:")


def test_manifest_claims_no_capability_kimi_has_no_mechanism_for() -> None:
    """Kimi 0.36.0 offers no schema, budget, turn or tool-posture flag.

    Print mode does force permission mode ``auto`` internally, but that is a
    documented native default rather than something this manifest asks for, and
    a capability token is a claim about a lever the manifest pulls.
    """

    declared = set(_manifest().capabilities)
    assert declared.isdisjoint(
        {
            "isolated_setting_sources",
            "json_output",
            "json_schema_enforcement",
            "max_budget_usd",
            "max_turns",
            "permission_mode",
            "reasoning_effort",
            "strict_mcp_config",
            "tool_allowlist",
        }
    )


def test_manifest_session_persistence_is_ephemeral_not_forbidden() -> None:
    """Kimi cannot be told to run stateless; the container throws the state away.

    Every ``-p`` run creates and indexes a session, and the only lever
    (``KIMI_CODE_HOME``) also relocates the credential store, so declaring
    ``forbidden`` would be a claim the CLI cannot honour.  What is true is that
    the writes land in the run's throwaway bind-mounted HOME.
    """

    assert _manifest().containment.session_persistence == "ephemeral"


def test_manifest_reports_no_usage_because_the_envelope_carries_none() -> None:
    """The writer has no usage code path, so no field is claimed to exist."""

    usage = _manifest().usage_reporting
    assert usage.cost_basis == "subscription_unallocable"
    assert usage.cost_usd_field is None
    assert usage.cache_read_tokens_field is None
    assert usage.cache_write_tokens_field is None
    assert usage.input_tokens_field.startswith("unreported.")
    assert usage.output_tokens_field.startswith("unreported.")


def test_manifest_capability_digest_is_the_committed_one() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["capability_digest"] == capability_digest_for(record)


def test_manifest_argv_is_minimal_and_avoids_the_print_mode_conflicts() -> None:
    argv = _manifest().invocation.render_argv(
        prompt="forecast this motion",
        model="kimi-code/kimi-for-coding",
        workspace="/workspace",
    )
    assert argv == (
        "-p",
        "forecast this motion",
        "--output-format",
        "stream-json",
        "--model",
        "kimi-code/kimi-for-coding",
    )
    # -y/--yolo, --auto and --plan are hard OptionConflictErrors when combined
    # with -p, and print mode already forces permission mode auto.
    assert {"-y", "--yolo", "--auto", "--plan"}.isdisjoint(argv)
    # Neither flag exists on this CLI; claiming either would be argv that fails
    # before the first token is spent.
    assert "--json-schema" not in argv
    assert "--disallowed-tools" not in argv


def test_manifest_declares_no_working_directory_flag() -> None:
    """Kimi has no cwd option: the process working directory is the workspace.

    The container plan supplies it with ``--workdir /workspace``, so a
    ``{workspace}`` argv placeholder would be a flag this CLI would reject.
    """

    assert _manifest().invocation.working_directory_flag is None


def test_manifest_without_the_web_tool_gate_is_refused() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record["capabilities"] = sorted(
        set(record["capabilities"]) - {"server_side_web_tools_disabled"}
    )
    record["capability_digest"] = capability_digest_for(record)
    with pytest.raises(LocalCliAdapterManifestError, match="server_side_web_tools"):
        LocalCliAdapterManifest.from_record(record)


def test_parser_reads_the_answer_and_the_tools_off_a_real_shaped_stream() -> None:
    parsed = parse_kimi_stream(_stream(*_TRANSCRIPT_EVENTS))
    assert parsed.answer == "GRANTED"
    assert parsed.failure_class is None
    assert parsed.version == "0.36.0"
    assert parsed.used_any_tool
    assert parsed.tools_used == ("Read", "Bash")
    assert parsed.assistant_lines == 3
    assert parsed.tool_result_lines == 2
    assert parsed.web_retrieval_requests == 0
    assert parsed.retry.retried is False
    # No line in this envelope carries token or cost accounting, and the parser
    # says so rather than reporting zeros that read as a measurement.
    assert parsed.reports_usage is False


def test_parser_takes_the_last_assistant_line_that_carried_text() -> None:
    """A tool-call-only flush omits ``content`` entirely and must not win.

    The writer flushes an assistant line before every tool result and again at
    finish, and hook output is emitted as an assistant line too, so "last line
    with text" is the rule -- not "last line" and not "first line".
    """

    tail: dict[str, Any] = {"role": "assistant", "tool_calls": []}
    events = (*_TRANSCRIPT_EVENTS, tail)
    assert parse_kimi_stream(_stream(*events)).answer == "GRANTED"


def test_parser_ignores_unknown_meta_types_and_roleless_lines() -> None:
    # goal.summary is the one documented line with no `role` key at all.
    events = (
        *_TRANSCRIPT_EVENTS,
        {
            "type": "goal.summary",
            "goalId": "g0",
            "status": "completed",
            "turnsUsed": 2,
        },
    )
    parsed = parse_kimi_stream(_stream(*events))
    assert parsed.answer == "GRANTED"
    assert parsed.roleless_lines == 1
    assert parsed.unknown_meta_types == ("an_event_kind_this_parser_has_never_seen",)


def test_parser_tolerates_a_stray_non_json_line() -> None:
    stream = "not json at all\n" + _stream(*_TRANSCRIPT_EVENTS)
    assert parse_kimi_stream(stream).answer == "GRANTED"


def test_parser_surfaces_a_retrieval_tool_that_the_redirect_did_not_stop() -> None:
    """A named WebSearch/FetchURL call is evidence the fence leaked.

    Kimi's retrieval services default to the same host as the completion API,
    so the container's host allowlist cannot separate them; the image redirects
    their base URLs instead.  This count is how a run shows the redirect held.
    """

    events = [dict(event) for event in _TRANSCRIPT_EVENTS]
    events[1] = {
        **events[1],
        "tool_calls": [
            {
                "type": "function",
                "id": "call_w",
                "function": {"name": "WebSearch", "arguments": '{"query":"outcome"}'},
            }
        ],
    }
    parsed = parse_kimi_stream(_stream(*events))
    assert parsed.web_tools_invoked == ("WebSearch",)
    assert parsed.web_retrieval_requests == 1
    assert parsed.to_record()["web_retrieval_requests"] == 1


def test_parser_records_the_retry_ladder_and_calls_it_a_crash() -> None:
    parsed = parse_kimi_stream(_stream(*_RETRY_STORM_EVENTS))
    assert parsed.answer == ""
    assert parsed.failure_class is LocalCliFailureClass.CRASH
    assert parsed.retry.retried
    assert parsed.retry.attempts_observed == 2
    assert parsed.retry.max_attempts == 10
    assert parsed.retry.last_status_code == 500
    assert parsed.retry.last_error_name == "APIStatusError"
    assert parsed.retry.total_backoff_ms == pytest.approx(1663.28069248)


def test_parser_record_carries_no_transcript_and_no_provider_message() -> None:
    record = parse_kimi_stream(_stream(*_RETRY_STORM_EVENTS)).to_record()
    assert "answer" not in record
    assert record["answer_characters"] == 0
    # The provider's prose reaches a public summary otherwise.
    assert "error_message" not in record["retry"]
    assert json.dumps(record).find("the server had an error") == -1


def test_parser_refuses_the_empty_successful_run() -> None:
    """Exit 0 with empty stdout is the auto-update branch, not an empty answer.

    ``runUpdatePreflight`` executes in print mode and on one path calls
    ``process.exit(0)`` having written nothing at all, which a parser that
    trusted the exit code would publish as a successful blank forecast.
    """

    with pytest.raises(KimiStreamError, match="no JSON lines"):
        parse_kimi_stream("")


def test_parser_classifies_a_started_run_that_produced_nothing() -> None:
    version_only = _stream(_TRANSCRIPT_EVENTS[0])
    parsed = parse_kimi_stream(version_only)
    assert parsed.failure_class is LocalCliFailureClass.SCHEMA_VIOLATION


def test_deliverable_accessor_refuses_a_transcript_with_no_answer() -> None:
    with pytest.raises(KimiStreamError, match="no assistant line"):
        kimi_deliverable_text(_stream(*_RETRY_STORM_EVENTS))
    assert kimi_deliverable_text(_stream(*_TRANSCRIPT_EVENTS)) == "GRANTED"


def test_generic_projection_cannot_read_this_harness_yet() -> None:
    """Pins the exact shared-helper gap this lane worked around.

    ``project_structured_stdout_deliverable`` selects a stream event by
    ``event["type"]``.  Kimi's assistant lines are keyed on ``role`` and carry
    no ``type`` at all, so the projection matches nothing and the containerized
    adapter cannot project this harness's answer from stdout.  The request is
    an optional ``deliverable_event_field`` on ``task_projection`` naming the
    discriminator key (default ``"type"``); until it lands,
    ``parse_kimi_stream`` is the accessor.  DELETE THIS TEST when it lands.
    """

    projection = _manifest().task_projection
    assert projection.deliverable_event_type == "assistant"
    assert projection.deliverable_field == "content"
    with pytest.raises(LocalCliAdapterManifestError, match="no matching deliverable"):
        project_structured_stdout_deliverable(
            _stream(*_TRANSCRIPT_EVENTS),
            output_format="stream_json",
            projection=projection,
        )
    assert parse_kimi_stream(_stream(*_TRANSCRIPT_EVENTS)).answer == "GRANTED"


def test_adapter_runs_the_manifest_argv_but_cannot_project_the_answer_yet(
    tmp_path: Path,
) -> None:
    """The run reaches the container correctly; only the projection is missing.

    ``schema_violation`` here is the honest consequence of the gap pinned in
    ``test_generic_projection_cannot_read_this_harness_yet``, not a defect in
    the manifest or the image.  WHEN ``deliverable_event_field`` LANDS this
    test must flip to ``succeeded`` with the answer projected.
    """

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
            duration_seconds=31.5,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("api.kimi.com", "auth.kimi.com"),
            refused=(
                {
                    "host": "web-tools-disabled.invalid",
                    "port": 443,
                    "reason": "host_not_allowlisted",
                },
            ),
            allowlist=spec.allowlist().to_record(),
        )

    manifest = _manifest()
    adapter = ContainerCliAdapter(
        identity=identity_for_registry_name(REGISTRY_NAME),
        local_manifest=manifest,
        auth_profile=FIXTURE_NONE,
        allow_hosts=("api.kimi.com", "auth.kimi.com"),
        parent_env={},
        runner=runner,
    )
    result = adapter.run(_request(manifest), tmp_path)

    assert seen[0].image == manifest.executable.container_image_digest
    assert seen[0].harness_argv[:4] == (
        "-p",
        "Forecast the motion.",
        "--output-format",
        "stream-json",
    )
    assert result.public_summary["native_tools_enabled"] is True
    assert result.public_summary["server_side_web_tools_disabled"] is True
    # The image redirects Kimi's retrieval services at a non-allowlisted host
    # precisely so an attempt shows up here instead of hiding inside allowed
    # provider traffic.
    assert result.public_summary["egress_refused"] == [
        {
            "host": "web-tools-disabled.invalid",
            "port": 443,
            "reason": "host_not_allowlisted",
        }
    ]
    assert result.status == "failed"
    assert result.public_summary["failure_class"] == "schema_violation"


def test_adapter_refuses_a_manifest_that_pins_another_harness() -> None:
    claude_native = LocalCliAdapterManifest.from_record(
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
    with pytest.raises(ContainerCliAdapterError, match="runs 'kimi'"):
        ContainerCliAdapter(
            identity=identity_for_registry_name(REGISTRY_NAME),
            local_manifest=claude_native,
            auth_profile=FIXTURE_NONE,
            parent_env={},
        )


def _request(manifest: LocalCliAdapterManifest) -> RunRequest:
    adapter_manifest = manifest.to_adapter_manifest(
        command=("legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",)
    )
    return RunRequest(
        request_id="kimi-container-smoke",
        task=CanonicalTask(
            task_id="lfb:kimi-container-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="kimi-container-smoke",
            task_sha256=SHA256,
            metadata={"solver_prompt": "Forecast the motion."},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key="kimi-code/kimi-for-coding",
        sandbox_policy=SandboxPolicy(
            policy_id="kimi-container-smoke",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=900,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )
