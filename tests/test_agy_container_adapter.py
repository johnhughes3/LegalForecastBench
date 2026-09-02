"""The containerized tools-on Antigravity CLI manifest and its JSON parser.

Two things are under test and neither needs a container: that the manifest says
what this lane requires it to say, and that the parser reads an ``agy
--output-format json`` envelope faithfully -- including reading back the two
things that envelope does *not* carry, which is the whole reason agy needs its
own test rather than sharing Claude Code's.

The image's web-retrieval fence is tested here too, and also needs no
container: it is a ``PreToolUse`` hook, and one that stopped matching
``search_web`` or crashed instead of answering would leave a tools-on agy row
able to look up the outcome it is scored on.

Envelope provenance: the shape below is the one characterised live from agy
1.1.22 on 2026-08-31, with two deliberate differences.  ``conversation_id`` is
a synthetic UUID, because the observed one is a real session id and this repo
is public.  ``structured_output`` and ``json_schema`` are absent from the
default fixture, because this lane's manifest declares
``schema_enforcement: none`` and never passes ``--json-schema``; the one test
that needs them adds them.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.container_harness.parser_agy import (
    AntigravityJsonError,
    parse_antigravity_json,
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
    ROOT / "examples" / "adapters" / "agy-native" / "local-cli-adapter-manifest.json"
)
REGISTRY_NAME = "antigravity-cli-container-tools-on"
SHA256 = "sha256:" + "1" * 64
FENCE_DIR = ROOT / "infra" / "harness-images" / "agy"
HOOK_SCRIPT = FENCE_DIR / "deny_web_tools.py"
HOOK_COMMAND = "/usr/local/bin/lfb-agy-deny-web-tools"
FENCE_FILES = (
    ("hooks-shared-root.json", "lfb-web-fence-shared-root"),
    ("hooks-cli-root.json", "lfb-web-fence-cli-root"),
)
# agy's own tool names: its CORTEX_STEP_TYPE_ enum lowercased without the
# prefix.  Fenced covers a browser name in prefix, infix and suffix position;
# live keeps two names containing "search" that an unanchored pattern eats.
FENCED_TOOLS = "search_web read_url_content browser_subagent \
capture_browser_screenshot click_browser_pixel".split()
LOCAL_TOOLS = "run_command view_file grep_search code_search find".split()

_ENVELOPE: dict[str, Any] = {
    "conversation_id": "00000000-0000-4000-8000-000000000000",
    "status": "SUCCESS",
    "response": "GRANTED\n",
    "duration_seconds": 6.325560011,
    "num_turns": 2,
    "usage": {
        "input_tokens": 24312,
        "output_tokens": 376,
        "thinking_tokens": 344,
        "cache_read_tokens": 16294,
        "total_tokens": 24688,
    },
}


def _stdout(envelope: dict[str, Any]) -> str:
    return f"{json.dumps(envelope)}\n"


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
    assert manifest.executable.basename == "agy"
    assert manifest.containment.network_policy == "provider_egress_host_only"
    # No cost anywhere in agy's envelope, so nothing may claim to meter it.
    assert manifest.usage_reporting.cost_basis == "subscription_unallocable"
    assert manifest.usage_reporting.cost_usd_field is None
    assert manifest.usage_reporting.cache_write_tokens_field is None
    assert manifest.executable.sha256 is None
    image = manifest.executable.container_image_digest
    assert image is not None and image.startswith("sha256:")


def test_manifest_capability_digest_is_the_committed_one() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["capability_digest"] == capability_digest_for(record)


def test_manifest_does_not_claim_postures_agy_cannot_enact() -> None:
    # agy 1.1.22 has no --tools/--max-turns/--max-budget-usd/--setting-sources
    # /--strict-mcp-config flag and no way to suppress session state, so a
    # manifest naming any of these would be describing a different program.
    declared = set(_manifest().capabilities)
    assert declared.isdisjoint(
        {
            "isolated_setting_sources",
            "max_budget_usd",
            "max_turns",
            "no_session_persistence",
            "reasoning_effort",
            "stream_json_output",
            "strict_mcp_config",
            "tool_allowlist",
        }
    )


def test_manifest_argv_is_flag_explicit_and_bounded() -> None:
    manifest = _manifest()
    argv = manifest.invocation.render_argv(
        prompt="forecast this motion",
        model="gemini-3.1-pro-high",
        workspace="/workspace",
    )
    assert argv[-2:] == ("-p", "forecast this motion")
    # A clean container HOME has no settings.json, so agy's default model and
    # permission posture -- both mutable per-user state on a host -- have to be
    # in argv or the run is not reproducible.
    assert "--model" in argv and "gemini-3.1-pro-high" in argv
    assert "--dangerously-skip-permissions" in argv
    # A corpus-derived prompt beginning with "/" is otherwise expanded as a
    # slash command instead of being read as user text.
    assert "--disable-slash-commands" in argv
    # schema_enforcement is "none" for this lane, so the finish-tool schema
    # path -- which pollutes .response with the tool arguments -- stays off.
    assert "--json-schema" not in argv
    # --print-timeout is agy's only turn budget (there is no --max-turns), so
    # it has to fire before the container is killed, or a runaway surfaces as
    # an opaque kill instead of agy's own TIMEOUT status.
    budget = argv[argv.index("--print-timeout") + 1]
    assert budget.endswith("s")
    assert int(budget.removesuffix("s")) < manifest.timeout_retry.timeout_seconds


def test_manifest_without_the_web_tool_gate_is_refused() -> None:
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record["capabilities"] = sorted(
        set(record["capabilities"]) - {"server_side_web_tools_disabled"}
    )
    record["capability_digest"] = capability_digest_for(record)
    with pytest.raises(LocalCliAdapterManifestError, match="server_side_web_tools"):
        LocalCliAdapterManifest.from_record(record)


def test_manifest_projects_the_answer_off_the_response_field() -> None:
    manifest = _manifest()
    projected = project_structured_stdout_deliverable(
        _stdout(_ENVELOPE),
        output_format=manifest.invocation.output_format,
        projection=manifest.task_projection,
    )
    assert projected.strip() == "GRANTED"


def test_parser_reads_the_answer_and_the_usage_off_a_real_shaped_envelope() -> None:
    parsed = parse_antigravity_json(_stdout(_ENVELOPE))
    assert parsed.answer.strip() == "GRANTED"
    assert parsed.status == "SUCCESS"
    assert parsed.failure_class is None
    assert parsed.usage.input_tokens == 24312
    assert parsed.usage.output_tokens == 376
    assert parsed.usage.thinking_tokens == 344
    assert parsed.usage.cache_read_tokens == 16294
    assert parsed.usage.total_tokens == 24688
    assert parsed.usage.num_turns == 2
    assert parsed.usage.duration_seconds == pytest.approx(6.325560011)
    assert parsed.structured_output is None


def test_parser_reports_the_two_absences_rather_than_inventing_them() -> None:
    parsed = parse_antigravity_json(_stdout(_ENVELOPE))
    # (1) No model key exists anywhere in agy's envelope, so a run cannot
    # confirm which model served it; the manifest pins --model and that is all
    # the provenance there is.
    assert parsed.model is None
    assert parsed.model_provenance == "request_side_only"
    # (2) No tool inventory and no tool-call records either, so an empty
    # tools_used means UNREPORTED, not unused.  A tools-on lane that read this
    # as "the harness used no tools" would be publishing a fabricated finding.
    assert parsed.tools_used == ()
    assert parsed.reports_tool_use is False
    record = parsed.to_record()
    assert record["model"] is None
    assert record["model_provenance"] == "request_side_only"
    assert record["reports_tool_use"] is False


def test_parser_keeps_the_schema_path_structured_output_when_it_is_present() -> None:
    envelope = {
        **_ENVELOPE,
        "structured_output": {"reply": "GRANTED"},
        "json_schema": {"type": "object"},
    }
    parsed = parse_antigravity_json(_stdout(envelope))
    assert parsed.structured_output == {"reply": "GRANTED"}
    assert parsed.unknown_fields == ()
    record = parsed.to_record()
    assert record["structured_output_present"] is True
    assert record["error_reported"] is False


def test_parser_reads_the_error_envelope_the_first_live_run_produced() -> None:
    """The failure path this lane actually hit, on 2026-08-31, run one.

    agy refused to start behind the provider-only egress allowlist: its
    startup eligibility check fetches the signed-in operator's Google profile
    picture from a user-content CDN, the proxy refused that host, and agy exited
    1 with this envelope.  Two things about it are worth freezing: it carries an
    ``error`` key that the 2026-08-31 envelope census did not list, and its real
    error string embedded an account-scoped URL -- redacted here, and excluded
    from the published record by the parser.
    """

    envelope = {
        "conversation_id": "",
        "status": "ERROR",
        "response": "",
        "error": (
            "Eligibility check failed: failed to get profile picture: "
            'Get "https://lh3.googleusercontent.com/REDACTED": Forbidden'
        ),
        "duration_seconds": 0,
        "num_turns": 0,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        },
    }
    parsed = parse_antigravity_json(_stdout(envelope))
    assert parsed.failure_class is LocalCliFailureClass.CRASH
    assert parsed.error_detail is not None
    assert "Eligibility check failed" in parsed.error_detail
    assert parsed.unknown_fields == ()
    record = parsed.to_record()
    assert record["error_reported"] is True
    # The error text can name a URL carrying an account-scoped identifier for
    # the logged-in operator, so it must not reach a published record.
    assert "lh3.googleusercontent.com" not in json.dumps(record)
    assert "REDACTED" not in json.dumps(record)


def test_parser_ignores_top_level_fields_it_does_not_know() -> None:
    envelope = {**_ENVELOPE, "a_field_this_parser_has_never_seen": {"payload": 1}}
    parsed = parse_antigravity_json(_stdout(envelope))
    assert parsed.unknown_fields == ("a_field_this_parser_has_never_seen",)
    assert parsed.failure_class is None


def test_parser_tolerates_a_stray_non_json_line() -> None:
    stdout = f"agy: notice, not json\n{_stdout(_ENVELOPE)}"
    assert parse_antigravity_json(stdout).answer.strip() == "GRANTED"


def test_parser_requires_a_result_envelope() -> None:
    with pytest.raises(AntigravityJsonError, match="no result envelope"):
        parse_antigravity_json('{"not": "an envelope"}\n')


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"status": "TIMEOUT"}, LocalCliFailureClass.TIMEOUT),
        ({"status": "CANCELLED"}, LocalCliFailureClass.CANCELLED),
        ({"status": "DENIED"}, LocalCliFailureClass.SANDBOX_DENIAL),
        ({"status": "FAILURE"}, LocalCliFailureClass.CRASH),
        ({"status": "ERROR", "response": ""}, LocalCliFailureClass.CRASH),
        # Fail closed: a literal this parser has never seen is not a success.
        ({"status": "SOMETHING_NEW"}, LocalCliFailureClass.CRASH),
        ({"response": "   "}, LocalCliFailureClass.SCHEMA_VIOLATION),
    ],
)
def test_parser_classifies_the_run_from_its_status(
    overrides: dict[str, Any], expected: LocalCliFailureClass
) -> None:
    parsed = parse_antigravity_json(_stdout({**_ENVELOPE, **overrides}))
    assert parsed.failure_class is expected
    assert parsed.to_record()["failure_class"] == expected.value


def test_parser_record_carries_no_transcript_and_no_session_id() -> None:
    record = parse_antigravity_json(_stdout(_ENVELOPE)).to_record()
    assert "answer" not in record
    assert "response" not in record
    # conversation_id keys agy's on-disk conversation and transcript tree; this
    # record is published, so it must never carry one.
    assert "conversation_id" not in json.dumps(record)
    assert record["answer_characters"] == len("GRANTED\n")
    assert record["status_is_declared"] is True
    assert record["usage"]["thinking_tokens"] == 344


def test_adapter_runs_the_manifest_argv_and_publishes_the_egress_evidence(
    tmp_path: Path,
) -> None:
    seen: list[ContainerHarnessSpec] = []

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        seen.append(spec)
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout = spec.log_root / "stdout"
        stderr = spec.log_root / "stderr"
        stdout.write_text(_stdout(_ENVELOPE), encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=8.075,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=("cloudcode-pa.googleapis.com",),
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
        allow_hosts=("cloudcode-pa.googleapis.com", "oauth2.googleapis.com"),
        parent_env={},
        runner=runner,
    )
    result = adapter.run(_request(manifest), tmp_path)

    assert result.status == "succeeded"
    assert result.public_summary["executable"] == "agy"
    assert result.public_summary["native_tools_enabled"] is True
    assert result.public_summary["egress_refused"] == [
        {"host": "example.com", "port": 443, "reason": "host_not_allowlisted"}
    ]
    assert seen[0].image == manifest.executable.container_image_digest
    assert seen[0].harness_argv[-2] == "-p"
    # No provider API key reaches the container: agy's login descriptor
    # projects no environment variables, and GEMINI_API_KEY/GOOGLE_API_KEY are
    # exactly the fallback this lane must never take.
    assert "GEMINI_API_KEY" not in seen[0].environment
    assert "GOOGLE_API_KEY" not in seen[0].environment
    # The two accountings are independent and this harness is the proof: agy's
    # envelope names no tool it called but does report its tokens, so one field
    # says `unreported` while the other carries real counts.
    assert result.public_summary["tool_use_reporting"] == "unreported"
    assert result.public_summary["usage_reporting"] == "cli_reported_usage"
    assert result.public_summary["input_tokens"] == 24312
    assert result.public_summary["usage"]["reasoning_tokens"] == 344


def test_adapter_refuses_a_manifest_for_a_different_harness(tmp_path: Path) -> None:
    del tmp_path
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
    with pytest.raises(ContainerCliAdapterError, match="'agy'"):
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
        request_id="agy-container-smoke",
        task=CanonicalTask(
            task_id="lfb:agy-container-smoke:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="agy-container-smoke",
            task_sha256=SHA256,
            metadata={"solver_prompt": "Forecast the motion."},
        ),
        adapter=AdapterManifest.from_record(adapter_manifest.to_record()),
        model_key="gemini-3.1-pro-high",
        sandbox_policy=SandboxPolicy(
            policy_id="agy-container-smoke",
            backend="docker",
            image=str(manifest.executable.container_image_digest),
            network_policy="provider_egress_host_only",
            timeout_seconds=900,
            working_directory="/workspace",
        ),
        request_sha256="sha256:" + "3" * 64,
    )


def _hook_module(journal: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("lfb_agy_deny_web_tools", HOOK_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DENIAL_LOG = str(journal)
    return module


def test_image_fence_denies_web_tools_and_leaves_local_tools_live() -> None:
    for name, hook_name in FENCE_FILES:
        hooks = json.loads((FENCE_DIR / name).read_text(encoding="utf-8"))
        # agy merges hooks from every customization root it loads, so the two
        # seeded files carry distinct names rather than one arriving twice.
        assert list(hooks) == [hook_name] and hooks[hook_name]["enabled"] is True
        (group,) = hooks[hook_name]["PreToolUse"]
        assert [handler["command"] for handler in group["hooks"]] == [HOOK_COMMAND]
        # Go matches with an unanchored regexp.MatchString, so mirror it with
        # search(); the pattern carries its own anchors.
        matcher = re.compile(group["matcher"])
        assert [tool for tool in FENCED_TOOLS if not matcher.search(tool)] == []
        assert [tool for tool in LOCAL_TOOLS if matcher.search(tool)] == []


def test_image_fence_hook_denies_every_shape_and_journals_what_it_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A hook that crashed would hand agy no decision at all, so this one must
    # never be the reason a web call was allowed. The last case cannot write
    # its journal: losing the record must not lose the denial.
    journal = tmp_path / "denials.jsonl"
    search_web = '{"toolCall": {"name": "search_web"}}'
    shapes = [search_web, '{"toolCall": null}', "[]", "not json at all", ""]
    unwritable = tmp_path / "absent" / "denials.jsonl"
    for payload, target in [*((s, journal) for s in shapes), (search_web, unwritable)]:
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert _hook_module(target).main() == 0
        assert json.loads(capsys.readouterr().out)["decision"] == "deny"
    written = journal.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["denied_tool"] for line in written] == [
        "search_web",
        *("unknown" for _ in range(4)),
    ]
