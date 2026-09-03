from __future__ import annotations

import ast
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.evals.inspect_task import (
    HarnessRequest,
    InspectTaskSample,
    SolverKind,
)
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.evals.prediction_units import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE, PUBLISHED_API_KEY
from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_ADAPTER_ID,
    CLAUDE_CODE_ADAPTER_VERSION,
    CLAUDE_CODE_CLEAN_NATIVE_TOOLS,
    CLAUDE_CODE_TOOLS_ARGV_ENCODING,
    CLAUDE_CODE_TOOLS_ARGV_EXAMPLE,
    CLAUDE_CODE_WRAPPER_COMMAND,
    DEFAULT_CLAUDE_CODE_MANIFEST_PATH,
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
    ClaudeCodeCliSolver,
    build_claude_invocation_plan,
    claude_code_local_manifest,
    claude_code_manifest,
    declared_failure_classes,
    encode_claude_code_tools_argv_token,
    encode_forecast_output_schema,
    load_claude_code_local_manifest,
)
from legalforecast.multiharness.local_cli_contracts import (
    CREDENTIAL_ENV_VAR_NAMES,
    FakeLocalCliExecutionService,
    FixtureTranscript,
    LocalCliContractError,
    LocalCliFailureClass,
    RunSpec,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    RunResult,
    SandboxPolicy,
)

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "tests" / "fixtures" / "claude_code" / "transcripts"
B1_MANIFEST = ROOT / "tests" / "fixtures" / "local_cli_adapters" / "claude-code.json"
EXAMPLE_MANIFEST = (
    ROOT / "examples" / "adapters" / "claude-code" / "adapter-manifest.json"
)
ADAPTER_SOURCE = ROOT / "legalforecast" / "multiharness" / "claude_code.py"
CONTRACTS_SOURCE = ROOT / "legalforecast" / "multiharness" / "local_cli_contracts.py"
PROMPT = "Forecast this fixture case. ; rm -rf / && echo $HOME"
CANARY = "fixture-secret-canary-7Jx9"
PLAN_WORKSPACE = Path("workspace")
PLAN_SCHEMA = PLAN_WORKSPACE / "output-schema.json"
PLAN_MODEL = "claude-sonnet-4-6"
SOLVER_MODEL_KEY = f"anthropic:{PLAN_MODEL}"
PLAN_SCHEMA_JSON = encode_forecast_output_schema(("count_i",))
CANONICAL_ARGV = (
    "claude",
    "-p",
    PROMPT,
    "--output-format",
    "json",
    "--json-schema",
    PLAN_SCHEMA_JSON,
    "--tools",
    "",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--setting-sources",
    "",
    "--model",
    PLAN_MODEL,
    "--add-dir",
    PLAN_WORKSPACE.as_posix(),
)


def test_example_manifest_round_trips_community_v1() -> None:
    manifest = AdapterManifest.from_record(
        json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    )
    assert manifest.adapter_id == CLAUDE_CODE_ADAPTER_ID
    assert manifest.adapter_version == CLAUDE_CODE_ADAPTER_VERSION
    assert manifest.command == CLAUDE_CODE_WRAPPER_COMMAND
    assert manifest.command != ("claude",)
    assert claude_code_manifest() == manifest


def test_adapter_consumes_b1_frozen_manifest() -> None:
    b1 = load_claude_code_local_manifest(B1_MANIFEST)
    published = claude_code_local_manifest()
    assert b1 == published
    assert DEFAULT_CLAUDE_CODE_MANIFEST_PATH.is_file()
    assert b1.manifest_id == CLAUDE_CODE_ADAPTER_ID
    assert b1.harness_binding.solver_kind == SolverKind.INSPECT_AI.value
    assert b1.auth_profile_name == "fixture-none"
    assert "--bare" not in b1.invocation.argv_template


def test_invocation_plan_snapshot_is_exact_and_order_sensitive() -> None:
    first = build_claude_invocation_plan(
        prompt=PROMPT,
        model=PLAN_MODEL,
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
    )
    second = build_claude_invocation_plan(
        prompt=PROMPT,
        model=PLAN_MODEL,
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
    )

    assert first.argv == CANONICAL_ARGV
    assert first.argv == second.argv
    assert (
        json.loads(first.argv[first.argv.index("--json-schema") + 1])[
            "additionalProperties"
        ]
        is False
    )
    assert "--bare" not in first.argv
    assert "sh" not in first.argv
    assert "-c" not in first.argv


def test_manifest_model_placeholder_propagates_and_is_not_hardcoded() -> None:
    haiku = build_claude_invocation_plan(
        prompt=PROMPT,
        model="claude-haiku-4-5",
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
    )
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert haiku.argv[haiku.argv.index("--model") + 1] == "claude-haiku-4-5"
    assert haiku.argv != CANONICAL_ARGV
    assert "claude-sonnet-4-6" not in source
    assert "claude-haiku-4-5" not in source


def test_unallowlisted_manifest_flag_is_refused_at_plan_time() -> None:
    record = json.loads(B1_MANIFEST.read_text(encoding="utf-8"))
    template = list(record["invocation"]["argv_template"])
    template.extend(["--verbose"])
    record["invocation"]["argv_template"] = template
    record["capability_digest"] = capability_digest_for(record)
    manifest = LocalCliAdapterManifest.from_record(record)
    with pytest.raises(ClaudeCodeCliAdapterError, match="un-allowlisted flag"):
        build_claude_invocation_plan(
            prompt=PROMPT,
            model=PLAN_MODEL,
            required_unit_ids=("count_i",),
            workspace=PLAN_WORKSPACE,
            output_schema_path=PLAN_SCHEMA,
            manifest=manifest,
        )


def test_fixture_transcripts_declare_synthetic_provenance() -> None:
    inventory = {
        "success": True,
        "timeout": True,
        "refusal": True,
        "schema_violation": True,
        "crash": True,
        "sandbox_denial": True,
        "cancelled": True,
        "identity_drift": True,
        "malformed": True,
        "auth_closed": False,
    }
    for name, synthetic in inventory.items():
        comments, _record = _load_transcript_file(TRANSCRIPTS / f"{name}.json")
        assert any(line.startswith("command:") for line in comments)
        assert any(line.startswith("generated_at:") for line in comments)
        assert f"synthetic: {str(synthetic).lower()}" in comments


def test_invocation_plan_enables_tools_only_when_the_task_profile_lists_them() -> None:
    plan = build_claude_invocation_plan(
        prompt="prompt",
        model=PLAN_MODEL,
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
        allowed_tools=("Read", "Glob"),
    )

    assert plan.argv[plan.argv.index("--tools") + 1] == "Read,Glob"
    assert plan.argv.count("--tools") == 1
    assert plan.argv[plan.argv.index("--tools") + 2] == "--strict-mcp-config"
    assert encode_claude_code_tools_argv_token(("Read", "Glob")) == (
        CLAUDE_CODE_TOOLS_ARGV_EXAMPLE
    )
    native = encode_claude_code_tools_argv_token(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert native == ",".join(CLAUDE_CODE_CLEAN_NATIVE_TOOLS)
    assert " " not in native
    assert "WebFetch" not in native
    assert encode_claude_code_tools_argv_token(()) == ""
    assert CLAUDE_CODE_TOOLS_ARGV_ENCODING == "comma-joined-single-token"


def test_invocation_plan_appends_extra_add_dirs_without_forking_tools_slot() -> None:
    extra = Path("projected-task")
    plan = build_claude_invocation_plan(
        prompt="prompt",
        model=PLAN_MODEL,
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
        allowed_tools=("Read", "Glob"),
        extra_add_dirs=(extra,),
    )

    assert plan.argv[plan.argv.index("--tools") + 1] == "Read,Glob"
    assert plan.argv.count("--tools") == 1
    assert plan.argv[-2:] == ("--add-dir", extra.as_posix())
    assert plan.argv.count("--add-dir") == 2


def test_run_spec_allows_empty_tools_token_and_rejects_credentials() -> None:
    plan = build_claude_invocation_plan(
        prompt="prompt",
        model="claude-sonnet-4-6",
        required_unit_ids=("count_i",),
        workspace=PLAN_WORKSPACE,
        output_schema_path=PLAN_SCHEMA,
    )
    spec = RunSpec(
        spec_id="spec-1",
        argv=plan.argv,
        working_directory=PLAN_WORKSPACE,
    )
    assert spec.argv[spec.argv.index("--tools") + 1] == ""
    with pytest.raises(LocalCliContractError, match="credential"):
        RunSpec(
            spec_id="spec-1",
            argv=plan.argv,
            working_directory=PLAN_WORKSPACE,
            environment={"ANTHROPIC_API_KEY": CANARY},
        )


def test_adapter_source_never_spawns_or_reads_credentials() -> None:
    for source_path in (ADAPTER_SOURCE, CONTRACTS_SOURCE):
        source = source_path.read_text(encoding="utf-8")
        assert "subprocess" not in source
        assert "Popen" not in source
        assert "os.environ" not in source
        assert "os.getenv" not in source


def test_adapter_execute_path_imports_the_contained_runtime_service() -> None:
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert (
        "from legalforecast.multiharness.local_cli_runtime import "
        "LocalCliExecutionService" in source
    )
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
    assert "FakeLocalCliExecutionService" not in imported
    assert "subprocess" not in imported


def test_fake_success_binds_spec_receipt_and_deliverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plant_credential_canaries(monkeypatch)
    adapter = _adapter("success")
    workspace = tmp_path / "workspace"
    result = adapter.run(_run_request(), workspace)

    assert result.status == "succeeded"
    assert result.public_summary["adapter_id"] == CLAUDE_CODE_ADAPTER_ID
    assert result.public_summary["auth_mode"] == "none-offline"
    assert result.public_summary["auth_profile"] == "fixture-none"
    assert result.public_summary["sandbox_policy_id"] == "offline-cli"
    assert result.public_summary["spec_sha256"].startswith("sha256:")
    assert result.public_summary["deliverable_manifest_sha256"].startswith("sha256:")
    assert "failure_class" not in result.public_summary
    assert result.artifacts[0].path == "deliverable-sealed/forecast.json"
    public = json.dumps(result.to_record(), sort_keys=True)
    assert CANARY not in public
    assert str(tmp_path) not in public
    sealed = workspace / "deliverable-sealed" / "forecast.json"
    forecast = json.loads(sealed.read_text(encoding="utf-8"))
    assert forecast["predictions"][0]["unit_id"] == "count_i"
    schema = json.loads((workspace / "output-schema.json").read_text(encoding="utf-8"))
    assert schema["required"] == ["case_assessment", "predictions"]
    _make_writable(workspace / "deliverable-sealed")


@pytest.mark.parametrize(
    ("fixture_name", "failure_class"),
    (
        ("timeout", LocalCliFailureClass.TIMEOUT),
        ("refusal", LocalCliFailureClass.REFUSAL),
        ("schema_violation", LocalCliFailureClass.SCHEMA_VIOLATION),
        ("crash", LocalCliFailureClass.CRASH),
        ("sandbox_denial", LocalCliFailureClass.SANDBOX_DENIAL),
        ("cancelled", LocalCliFailureClass.CANCELLED),
        ("identity_drift", LocalCliFailureClass.IDENTITY_DRIFT),
        ("malformed", LocalCliFailureClass.CRASH),
    ),
)
def test_declared_failure_fixtures_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_name: str,
    failure_class: LocalCliFailureClass,
) -> None:
    _plant_credential_canaries(monkeypatch)
    adapter = _adapter(fixture_name)
    result = adapter.run(_run_request(), tmp_path / "workspace")

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == failure_class.value
    assert result.public_summary["task_id"] == "lfb:case-1:full_packet"
    assert "returncode" in result.public_summary
    assert "deliverable_manifest_sha256" not in result.public_summary
    assert CANARY not in json.dumps(result.to_record(), sort_keys=True)
    assert not (tmp_path / "workspace" / "deliverable-sealed").exists()


def test_unparseable_envelope_is_crash_not_empty_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plant_credential_canaries(monkeypatch)
    result = _adapter("malformed").run(_run_request(), tmp_path / "workspace")

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == LocalCliFailureClass.CRASH.value
    assert result.public_summary["task_id"] == "lfb:case-1:full_packet"
    assert result.public_summary["returncode"] == 0
    assert result.artifacts == ()


def test_observed_auth_closed_envelope_is_crash_with_zero_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plant_credential_canaries(monkeypatch)
    result = _adapter("auth_closed").run(_run_request(), tmp_path / "workspace")

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == LocalCliFailureClass.CRASH.value
    assert result.public_summary["task_id"] == "lfb:case-1:full_packet"
    assert result.public_summary["returncode"] == 1
    assert result.public_summary["estimated_cost"] == 0.0


def test_declared_failure_classes_match_fixtures() -> None:
    assert declared_failure_classes() == (
        "timeout",
        "refusal",
        "schema_violation",
        "crash",
        "sandbox_denial",
        "cancelled",
        "identity_drift",
    )
    for name in declared_failure_classes():
        assert (TRANSCRIPTS / f"{name}.json").is_file()


def test_sandbox_denial_is_distinct_from_crash(tmp_path: Path) -> None:
    denied = _adapter("sandbox_denial").run(_run_request(), tmp_path / "denied")
    crashed = _adapter("crash").run(_run_request(), tmp_path / "crash")

    assert denied.public_summary["failure_class"] == (
        LocalCliFailureClass.SANDBOX_DENIAL.value
    )
    assert crashed.public_summary["failure_class"] == LocalCliFailureClass.CRASH.value
    assert (
        denied.public_summary["failure_class"]
        != crashed.public_summary["failure_class"]
    )


def test_identity_drift_failure_detail_names_served_model(tmp_path: Path) -> None:
    result = _adapter("identity_drift").run(_run_request(), tmp_path / "workspace")

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == (
        LocalCliFailureClass.IDENTITY_DRIFT.value
    )
    assert "served_model" in result.public_summary["failure_detail"]
    assert result.public_summary["served_model"] == "claude-haiku-4-5"


def test_landlocked_legal_language_is_not_classified_as_sandbox_denial(
    tmp_path: Path,
) -> None:
    def mutate(envelope: dict[str, object]) -> None:
        envelope["result"] = {
            "case_assessment": (
                "The plaintiff is a landlocked state seeking "
                "seccomp-style discovery limits."
            ),
            "predictions": [
                {
                    "unit_id": "count_i",
                    "probability_fully_dismissed": 0.7,
                    "rationale": "Fixture rationale.",
                }
            ],
        }

    result = _adapter_from_mutated_success(tmp_path, mutate_envelope=mutate)
    assert result.status == "succeeded"
    assert "failure_class" not in result.public_summary
    _make_writable(tmp_path / "workspace" / "deliverable-sealed")


def test_crash_does_not_scan_structured_forecast_for_sandbox_denial(
    tmp_path: Path,
) -> None:
    def mutate(envelope: dict[str, Any]) -> None:
        envelope["result"]["case_assessment"] = "The plaintiff is a landlocked state."

    result = _adapter_from_mutated_success(
        tmp_path,
        mutate_envelope=mutate,
        status="failed",
        returncode=1,
    )
    assert result.status == "failed"
    assert result.public_summary["failure_class"] == LocalCliFailureClass.CRASH.value


def test_timeout_subtype_precedes_sandbox_denial_markers(tmp_path: Path) -> None:
    def mutate(envelope: dict[str, Any]) -> None:
        envelope.update(
            is_error=True,
            subtype="timeout",
            result="Timed out while discussing a landlocked state.",
        )

    result = _adapter_from_mutated_success(
        tmp_path,
        mutate_envelope=mutate,
        status="failed",
        returncode=1,
    )
    assert result.status == "failed"
    assert result.public_summary["failure_class"] == LocalCliFailureClass.TIMEOUT.value


def test_offline_adapter_rejects_provider_environment_grants(tmp_path: Path) -> None:
    adapter = _adapter("success")
    request = _run_request(allowed_provider_env_vars=("ANTHROPIC_API_KEY",))
    with pytest.raises(ClaudeCodeCliAdapterError, match="provider environment"):
        adapter.run(request, tmp_path / "workspace")


def test_solver_uses_inspect_ai_kind() -> None:
    solver = ClaudeCodeCliSolver(
        execution_service=_service("success"),
        model_key=SOLVER_MODEL_KEY,
    )

    assert solver.solver_kind is SolverKind.INSPECT_AI
    assert solver.solver_id.startswith(CLAUDE_CODE_ADAPTER_ID)
    assert solver.adapter is not None
    assert solver.adapter.manifest.adapter_version == CLAUDE_CODE_ADAPTER_VERSION
    assert solver.adapter.manifest.adapter_id == CLAUDE_CODE_ADAPTER_ID


def test_solver_returns_structured_output_from_fixture_transcript(
    tmp_path: Path,
) -> None:
    solver = ClaudeCodeCliSolver(
        execution_service=_service("success"),
        model_key=SOLVER_MODEL_KEY,
        workspace=tmp_path / "solver-workspace",
    )
    response = solver.solve(_harness_request())

    payload = json.loads(response.raw_output)
    assert payload["predictions"][0]["unit_id"] == "count_i"
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.metadata is not None
    assert response.metadata["adapter_id"] == CLAUDE_CODE_ADAPTER_ID
    assert response.metadata["auth_profile"] == FIXTURE_NONE


def test_solver_metadata_records_published_api_key_profile(tmp_path: Path) -> None:
    service = _ProfiledFakeService(
        _transcript("success"),
        auth_profile=PUBLISHED_API_KEY,
        projected_env_vars=("ANTHROPIC_API_KEY",),
    )
    solver = ClaudeCodeCliSolver(
        execution_service=service,
        model_key=SOLVER_MODEL_KEY,
        workspace=tmp_path / "solver-workspace",
        network_policy="provider_egress_host_only",
    )
    response = solver.solve(_harness_request())

    assert response.metadata is not None
    assert response.metadata["auth_profile"] == PUBLISHED_API_KEY


def test_solver_raises_typed_failure_for_refusal() -> None:
    solver = ClaudeCodeCliSolver(
        execution_service=_service("refusal"),
        model_key=SOLVER_MODEL_KEY,
    )
    with pytest.raises(
        ClaudeCodeCliAdapterError,
        match="refusal task_id=sample-1 returncode=0",
    ) as exc_info:
        solver.solve(_harness_request())
    assert exc_info.value.failure_class is LocalCliFailureClass.REFUSAL


def test_solver_refuses_controlled_docket_tool_samples() -> None:
    solver = ClaudeCodeCliSolver(
        execution_service=_service("success"),
        model_key=SOLVER_MODEL_KEY,
    )
    with pytest.raises(ClaudeCodeCliAdapterError, match="docket-tool"):
        solver.solve(_harness_request(use_docket_tool=True))


def test_receipt_served_model_drift_fails_closed_when_envelope_omits_model(
    tmp_path: Path,
) -> None:
    def mutate(envelope: dict[str, Any]) -> None:
        envelope.pop("model", None)

    result = _adapter_from_mutated_success(
        tmp_path,
        mutate_envelope=mutate,
        served_model="claude-haiku-4-5",
    )
    assert result.status == "failed"
    assert result.public_summary["failure_class"] == (
        LocalCliFailureClass.IDENTITY_DRIFT.value
    )
    assert "served_model" in result.public_summary["failure_detail"]


def test_extra_forecast_property_is_schema_violation(tmp_path: Path) -> None:
    def mutate(envelope: dict[str, Any]) -> None:
        envelope["result"]["unexpected"] = "field"

    result = _adapter_from_mutated_success(tmp_path, mutate_envelope=mutate)
    assert result.status == "failed"
    assert (
        result.public_summary["failure_class"]
        == LocalCliFailureClass.SCHEMA_VIOLATION.value
    )


def test_non_string_rationale_is_schema_violation(tmp_path: Path) -> None:
    def mutate(envelope: dict[str, Any]) -> None:
        envelope["result"]["predictions"][0]["rationale"] = 12

    result = _adapter_from_mutated_success(tmp_path, mutate_envelope=mutate)
    assert result.status == "failed"
    assert (
        result.public_summary["failure_class"]
        == LocalCliFailureClass.SCHEMA_VIOLATION.value
    )


def test_local_cli_manifest_round_trip() -> None:
    manifest = load_claude_code_local_manifest(B1_MANIFEST)
    assert LocalCliAdapterManifest.from_record(manifest.to_record()) == manifest


def test_capabilities_are_stable(tmp_path: Path) -> None:
    adapter = _adapter("success")
    first = adapter.capabilities(tmp_path / "a")
    second = adapter.capabilities(tmp_path / "b")
    assert first.capabilities_sha256 == second.capabilities_sha256
    assert first.supported_families == ("legalforecast_mtd",)
    assert first.adapter_id == CLAUDE_CODE_ADAPTER_ID


def test_task_profile_tools_reach_the_run_spec(tmp_path: Path) -> None:
    captured: list[RunSpec] = []

    class _CapturingService:
        def execute(self, spec: RunSpec) -> Any:
            captured.append(spec)
            return _service("success").execute(spec)

    adapter = ClaudeCodeCliAdapter(execution_service=_CapturingService())
    adapter.run(
        _run_request(allowed_tools=("Read",)),
        tmp_path / "workspace",
    )
    assert captured[0].argv[captured[0].argv.index("--tools") + 1] == "Read"
    _make_writable(tmp_path / "workspace" / "deliverable-sealed")


def _adapter(fixture_name: str) -> ClaudeCodeCliAdapter:
    return ClaudeCodeCliAdapter(execution_service=_service(fixture_name))


def _adapter_from_mutated_success(
    tmp_path: Path,
    *,
    mutate_envelope: Callable[[dict[str, Any]], None],
    served_model: str | None = "claude-sonnet-4-6",
    status: str = "succeeded",
    returncode: int = 0,
) -> RunResult:
    _comments, record = _load_transcript_file(TRANSCRIPTS / "success.json")
    envelope = cast(dict[str, Any], json.loads(json.dumps(record["envelope"])))
    mutate_envelope(envelope)
    transcript = FixtureTranscript(
        stdout=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
        stderr="",
        returncode=returncode,
        status=status,
        duration_ms=int(record.get("duration_ms") or 0),
        served_model=served_model,
        executable_version=record.get("executable_version"),
        cost_usd=record.get("cost_usd"),
        usage=_usage(envelope),
    )
    adapter = ClaudeCodeCliAdapter(
        execution_service=FakeLocalCliExecutionService(transcript)
    )
    return adapter.run(_run_request(), tmp_path / "workspace")


def _service(fixture_name: str) -> FakeLocalCliExecutionService:
    return FakeLocalCliExecutionService(_transcript(fixture_name))


@dataclass(frozen=True, slots=True)
class _ProfiledFakeService(FakeLocalCliExecutionService):
    auth_profile: str = FIXTURE_NONE
    projected_env_vars: tuple[str, ...] = ()

    def env_vars_for_profile(self, profile_id: str) -> tuple[str, ...]:
        if profile_id == self.auth_profile:
            return self.projected_env_vars
        return ()


def _transcript(fixture_name: str) -> FixtureTranscript:
    _comments, record = _load_transcript_file(TRANSCRIPTS / f"{fixture_name}.json")
    envelope = record.get("envelope")
    if "stdout_text" in record:
        stdout = record["stdout_text"]
    elif envelope is None:
        stdout = ""
    else:
        stdout = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    return FixtureTranscript(
        stdout=stdout,
        stderr=record.get("stderr", ""),
        returncode=record.get("returncode"),
        status=record["status"],
        duration_ms=int(record.get("duration_ms") or 0),
        served_model=record.get("served_model"),
        executable_version=record.get("executable_version"),
        cost_usd=record.get("cost_usd"),
        usage=_usage(envelope),
    )


def _usage(envelope: object) -> dict[str, int]:
    if not isinstance(envelope, dict):
        return {}
    usage = cast(dict[str, Any], envelope).get("usage")
    if not isinstance(usage, dict):
        return {}
    result: dict[str, int] = {}
    for key, value in cast(dict[str, Any], usage).items():
        if type(value) is int:
            result[key] = value
    return result


def _run_request(
    *,
    allowed_provider_env_vars: tuple[str, ...] = (),
    allowed_tools: tuple[str, ...] | None = None,
) -> RunRequest:
    metadata: dict[str, Any] = {
        "required_unit_ids": ["count_i"],
        "solver_prompt": PROMPT,
    }
    if allowed_tools is not None:
        metadata["allowed_tools"] = list(allowed_tools)
    task = CanonicalTask(
        task_id="lfb:case-1:full_packet",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="legalforecast-mtd-v1",
        source_id="case-1",
        task_sha256="sha256:" + "1" * 64,
        metadata=metadata,
    )
    policy = SandboxPolicy(
        policy_id="offline-cli",
        backend="none",
        image="none",
        network_policy="none",
        timeout_seconds=30,
        allowed_provider_env_vars=allowed_provider_env_vars,
    )
    return RunRequest(
        request_id="request-1",
        task=task,
        adapter=claude_code_manifest(),
        model_key=SOLVER_MODEL_KEY,
        sandbox_policy=policy,
        request_sha256="sha256:" + "3" * 64,
    )


def _harness_request(*, use_docket_tool: bool = False) -> HarnessRequest:
    packet = build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                SourceDocumentProvenance(
                    source_provider="case.dev",
                    source_case_id="case-dev-1",
                    source_document_id="complaint",
                    court="S.D.N.Y.",
                    docket_number="1:26-cv-1",
                    document_role=DocumentRole.COMPLAINT,
                    retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
                    source_url_or_reference="case.dev://complaint",
                    sha256=sha256_text("complaint source"),
                    is_predecision_material=True,
                    is_mounted_for_model=True,
                    docket_entry_number=1,
                    contains_target_outcome=False,
                    packet_section="filings",
                ),
            ),
        ),
        prediction_units=(
            PredictionUnit(
                unit_id="count_i",
                count="I",
                claim_name="Section 10(b)",
                defendant_group="Issuer",
                challenged_by_motion=True,
                challenge_scope=ChallengeScope.ENTIRE_CLAIM,
                unit_confidence=0.95,
                source_citations=(SourceCitation(document_id="complaint", page=1),),
            ),
        ),
        texts=(PacketText(source_document_id="complaint", text="complaint text"),),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
    )
    sample = InspectTaskSample(
        sample_id="sample-1",
        packet=packet,
        prompt=PROMPT,
        allowed_entry_numbers=(1,),
        use_docket_tool=use_docket_tool,
    )
    return HarnessRequest(sample=sample, docket_tool=sample.build_docket_tool())


def _load_transcript_file(path: Path) -> tuple[list[str], dict[str, Any]]:
    comments: list[str] = []
    body_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not body_lines and line.startswith("//"):
            comments.append(line[2:].strip())
            continue
        body_lines.append(line)
    record = json.loads("\n".join(body_lines))
    if not isinstance(record, dict):
        raise AssertionError(f"{path.name} must be a JSON object")
    return comments, cast(dict[str, Any], record)


def _plant_credential_canaries(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CREDENTIAL_ENV_VAR_NAMES:
        monkeypatch.setenv(name, CANARY)


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        item.chmod(item.stat().st_mode | 0o200)
