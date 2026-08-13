from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.codex_cli import (
    CODEX_CLI_ADAPTER_ID,
    CODEX_CLI_ADAPTER_VERSION,
    CODEX_FAILURE_CLASSES,
    CODEX_LOCAL_CLI_MANIFEST_PATH,
    CodexCliAdapter,
    CodexCliAdapterError,
    CodexCliExecutionOutcome,
    CodexCliExecutionRequest,
    adapter_bundle_sha256,
    build_capabilities,
    build_codex_invocation_plan,
    load_codex_local_cli_manifest,
    parse_codex_jsonl,
    run_offline_protocol_fixture,
)
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.validation import validate_public_record

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "adapters" / "codex-cli" / "adapter-manifest.json"
LOCAL_CLI_MANIFEST = (
    ROOT / "examples" / "adapters" / "codex-cli" / "local-cli-manifest.json"
)
CLEAN_NATIVE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "local_cli_adapters" / "codex-cli.json"
)
SUCCESS_TRANSCRIPT = ROOT / "tests" / "fixtures" / "codex_cli_adapter" / "success.jsonl"
MODULE = ROOT / "legalforecast" / "multiharness" / "codex_cli.py"
SHA256 = "sha256:" + "1" * 64
OTHER_SHA256 = "sha256:" + "2" * 64
SECRET_CANARY = "LEGALFORECAST_SECRET_CANARY_7f3a"
THREAD_ID = "00000000-0000-7000-8000-000000000001"


class RecordingFakeExecutionService:
    """In-process B2 stand-in that never spawns a process."""

    def __init__(self, outcome: CodexCliExecutionOutcome) -> None:
        self.outcome = outcome
        self.requests: list[CodexCliExecutionRequest] = []

    def execute(self, request: CodexCliExecutionRequest) -> CodexCliExecutionOutcome:
        self.requests.append(request)
        return self.outcome


def _jsonl(*events: Mapping[str, Any]) -> str:
    return "".join(
        json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n"
        for event in events
    )


def _error_outcome(message: str, returncode: int) -> CodexCliExecutionOutcome:
    return CodexCliExecutionOutcome(
        returncode=returncode,
        stdout=_jsonl(
            {"type": "thread.started", "thread_id": THREAD_ID},
            {"type": "turn.started"},
            {"type": "error", "message": message},
            {"type": "turn.failed", "error": {"message": message}},
        ),
        stderr="",
    )


def _message_outcome(text: str, *, complete: bool = False) -> CodexCliExecutionOutcome:
    events: list[dict[str, Any]] = [
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": text},
        },
    ]
    if complete:
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "cached_input_tokens": 0,
                    "input_tokens": 3,
                    "output_tokens": 4,
                },
            }
        )
    return CodexCliExecutionOutcome(returncode=0, stdout=_jsonl(*events), stderr="")


def test_adapter_module_does_not_import_or_spawn_processes() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    assert "subprocess" not in imported
    assert "os.system" not in source
    assert "Popen" not in source


def test_capabilities_are_stable_and_public_safe() -> None:
    first = build_capabilities()
    second = build_capabilities()

    assert first == second
    assert first.adapter_id == CODEX_CLI_ADAPTER_ID
    assert first.supported_families == ("legalforecast_mtd",)
    assert first.tool_protocol_version is None
    validate_public_record(first.to_record(), "capabilities")
    assert adapter_bundle_sha256().startswith("sha256:")
    assert (
        first.capabilities_sha256 == load_codex_local_cli_manifest().capability_digest
    )


def test_offline_local_cli_manifest_drives_non_interactive_exec() -> None:
    manifest = load_codex_local_cli_manifest()

    assert LOCAL_CLI_MANIFEST == CODEX_LOCAL_CLI_MANIFEST_PATH
    assert manifest.manifest_id == CODEX_CLI_ADAPTER_ID
    assert manifest.invocation.headless_mode == "exec_subcommand"
    assert manifest.invocation.prompt_delivery == "stdin"
    assert manifest.invocation.schema_enforcement == "none"
    assert "--json" in manifest.invocation.argv_template
    assert "--ephemeral" in manifest.invocation.argv_template
    assert "workspace-write" in manifest.invocation.argv_template
    assert 'approval_policy="never"' in manifest.invocation.argv_template
    assert manifest.invocation.argv_template[-1] == "-"
    assert "--approve-for-me" not in manifest.invocation.argv_template
    assert "--ask-for-approval" not in manifest.invocation.argv_template
    assert manifest.auth_profile_name == "fixture_none"
    assert manifest.harness_binding.implements_harness_adapter is True
    assert manifest.harness_binding.implements_harness_solver is False


def test_clean_native_fixture_is_not_the_offline_invocation() -> None:
    offline = load_codex_local_cli_manifest()
    shipped = LocalCliAdapterManifest.from_record(
        json.loads(CLEAN_NATIVE_FIXTURE.read_text(encoding="utf-8"))
    )

    assert shipped.manifest_id == "codex-cli-clean-native"
    assert shipped.invocation.prompt_delivery == "argv_placeholder"
    assert shipped.invocation.schema_enforcement == "output_schema_file"
    assert "read-only" in shipped.invocation.argv_template
    assert shipped.invocation.prompt_delivery != offline.invocation.prompt_delivery
    assert (
        shipped.invocation.schema_enforcement != offline.invocation.schema_enforcement
    )


def test_invocation_plan_is_deterministic_and_non_interactive(tmp_path: Path) -> None:
    request = _request()
    first = build_codex_invocation_plan(request, tmp_path, prompt="solve fixture")
    second = build_codex_invocation_plan(request, tmp_path, prompt="solve fixture")

    assert first.argv == second.argv
    assert first.stdin == "solve fixture"
    assert first.argv[0] == "codex"
    assert first.argv[1] == "exec"
    assert "--json" in first.argv
    assert first.argv[first.argv.index("--color") + 1] == "never"
    assert "--ephemeral" in first.argv
    assert "--ignore-user-config" in first.argv
    assert "--ignore-rules" in first.argv
    assert "--strict-config" in first.argv
    assert "--skip-git-repo-check" in first.argv
    assert first.argv[first.argv.index("--sandbox") + 1] == "workspace-write"
    assert first.argv[first.argv.index("--model") + 1] == "gpt-5.1"
    assert 'approval_policy="never"' in first.argv
    assert 'model_reasoning_effort="medium"' in first.argv
    assert first.argv[-1] == "-"
    assert first.argv[first.argv.index("--output-last-message") + 1] == (
        "private-logs/codex-last-message.txt"
    )
    for forbidden in (
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--approve-for-me",
        "--profile",
        "--oss",
        "--search",
    ):
        assert forbidden not in first.argv
    assert "auth.json" not in " ".join(first.argv)
    assert not any(char in token for token in first.argv for char in ";|&`$")


def test_reasoning_effort_is_closed_and_pinned(tmp_path: Path) -> None:
    request = _request(metadata={"prompt": "solve", "reasoning_effort": "high"})
    plan = build_codex_invocation_plan(request, tmp_path, prompt="solve")

    assert 'model_reasoning_effort="high"' in plan.argv
    with pytest.raises(CodexCliAdapterError, match="reasoning_effort"):
        build_codex_invocation_plan(
            _request(metadata={"prompt": "solve", "reasoning_effort": "max"}),
            tmp_path,
            prompt="solve",
        )


def test_live_model_key_requires_codex_namespace(tmp_path: Path) -> None:
    with pytest.raises(CodexCliAdapterError, match="codex:"):
        build_codex_invocation_plan(
            _request(model_key="gpt-5.1"),
            tmp_path,
            prompt="solve",
        )


def test_success_fixture_binds_run_result_and_deliverable(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    service = RecordingFakeExecutionService(_success_outcome())
    adapter = CodexCliAdapter(execution_service=service)
    request = _request()

    result = adapter.run(request, workspace)

    assert result.status == "succeeded"
    assert result.request_id == request.request_id
    assert (
        result.public_summary["sandbox_policy_id"] == request.sandbox_policy.policy_id
    )
    assert "failure_class" not in result.public_summary
    assert result.public_summary["auth_mode"] == "none-offline-cli-adapter"
    assert result.public_summary["subscription_login_claimed"] is False
    assert result.public_summary["deliverable_manifest_sha256"].startswith("sha256:")
    assert result.public_summary["input_tokens"] == 3
    assert result.public_summary["output_tokens"] == 4
    validate_public_record(result.to_record(), "run_result")
    assert len(service.requests) == 1
    executed = service.requests[0]
    assert executed.environment == {}
    assert executed.stdin == "solve fixture\n"
    assert executed.argv[0] == "codex"
    assert (workspace / "sealed-deliverable" / "work-product" / "answer.md").read_text(
        encoding="utf-8"
    ) == "LEGALFORECAST_FAKE_CODEX_RESULT\n"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    (
        (
            CodexCliExecutionOutcome(
                returncode=-1, stdout="", stderr="", timed_out=True
            ),
            "timeout",
        ),
        (
            CodexCliExecutionOutcome(
                returncode=139, stdout="", stderr="", crashed=True
            ),
            "crash",
        ),
        (_error_outcome("sandbox denied write under landlock", 1), "sandbox_denial"),
        (_message_outcome("I must refuse this request."), "refusal"),
        (
            CodexCliExecutionOutcome(
                returncode=0,
                stdout='{"type":"thread.started"}\n{"type":',
                stderr="",
            ),
            "schema_violation",
        ),
        (
            CodexCliExecutionOutcome(
                returncode=0,
                stdout=_jsonl(
                    {"type": "thread.started", "thread_id": THREAD_ID},
                    {"type": "turn.started"},
                )
                + "not-json\n",
                stderr="",
            ),
            "schema_violation",
        ),
        (
            CodexCliExecutionOutcome(
                returncode=0,
                stdout=_jsonl(
                    {"type": "thread.started", "thread_id": THREAD_ID},
                    {"type": "turn.started"},
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_0",
                            "type": "agent_message",
                            "text": "partial",
                        },
                    },
                ),
                stderr="",
            ),
            "schema_violation",
        ),
        (_error_outcome("fake provider failure", 17), "crash"),
        (
            CodexCliExecutionOutcome(
                returncode=0,
                stdout=_jsonl(
                    {
                        "type": "thread.started",
                        "thread_id": THREAD_ID,
                        "requested_model": "gpt-5.1",
                        "actual_model": "unexpected-model",
                    },
                    {"type": "turn.started"},
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_0",
                            "type": "agent_message",
                            "text": "drift",
                        },
                    },
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 1,
                            "output_tokens": 1,
                            "cached_input_tokens": 0,
                        },
                    },
                ),
                stderr="",
            ),
            "schema_violation",
        ),
    ),
)
def test_declared_failure_fixtures_are_classified_fail_closed(
    tmp_path: Path,
    outcome: CodexCliExecutionOutcome,
    expected: str,
) -> None:
    assert expected in CODEX_FAILURE_CLASSES
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    adapter = CodexCliAdapter(execution_service=RecordingFakeExecutionService(outcome))

    result = adapter.run(_request(), workspace)

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == expected
    assert "deliverable_manifest_sha256" not in result.public_summary
    validate_public_record(result.to_record(), "failed_run_result")


def test_secret_canary_is_confined_to_private_workspace_bytes(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _message_outcome(SECRET_CANARY, complete=True)
        )
    )

    result = adapter.run(_request(), workspace)

    public = json.dumps(result.public_summary, sort_keys=True)
    assert SECRET_CANARY not in public
    assert SECRET_CANARY not in json.dumps(result.to_record(), sort_keys=True)
    private = (workspace / "private-logs" / "codex-stdout.jsonl").read_text(
        encoding="utf-8"
    )
    assert SECRET_CANARY in private


def test_provider_environment_grants_are_rejected(tmp_path: Path) -> None:
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_success_outcome())
    )
    request = _request(allowed_provider_env_vars=("OPENAI_API_KEY",))
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve\n", encoding="utf-8")

    with pytest.raises(CodexCliAdapterError, match="provider environment"):
        adapter.run(request, workspace)


def test_offline_conformance_fixture_does_not_execute_codex(tmp_path: Path) -> None:
    request = _request(
        model_key="conformance-fixture-model",
        metadata={"fixture": "adapter-conformance"},
        adapter_id=CODEX_CLI_ADAPTER_ID,
    )
    # Conformance uses the adapter id from the manifest; rebuild with matching adapter.
    request = RunRequest(
        request_id=request.request_id,
        task=request.task,
        adapter=_manifest(),
        model_key="conformance-fixture-model",
        sandbox_policy=request.sandbox_policy,
        request_sha256=request.request_sha256,
    )

    result = run_offline_protocol_fixture(request, tmp_path / "conformance")

    assert result.status == "succeeded"
    assert result.public_summary["offline_protocol_fixture"] is True
    assert result.public_summary["auth_mode"] == "none-offline-protocol-fixture"
    assert (
        result.public_summary["sandbox_policy_id"] == request.sandbox_policy.policy_id
    )


def test_codex_cli_manifest_passes_offline_conformance(tmp_path: Path) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=MANIFEST,
        output_dir=tmp_path / "codex-cli-conformance",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == CODEX_CLI_ADAPTER_ID
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("skipped:")


def test_command_adapter_capabilities_match_in_process(tmp_path: Path) -> None:
    adapter = CommandAdapter.from_manifest_file(MANIFEST, timeout_seconds=30)
    capabilities = adapter.capabilities(tmp_path / "capabilities")

    assert capabilities.adapter_id == CODEX_CLI_ADAPTER_ID
    assert capabilities.adapter_version == CODEX_CLI_ADAPTER_VERSION
    assert capabilities.tool_protocol_version is None


def test_parser_rejects_unknown_event_types() -> None:
    stdout = _jsonl(
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {"type": "unexpected.event"},
    )

    envelope = parse_codex_jsonl(
        stdout,
        requested_model_name="gpt-5.1",
        returncode=0,
        timed_out=False,
        crashed=False,
    )

    assert envelope.failure_class == "schema_violation"


def _success_outcome() -> CodexCliExecutionOutcome:
    return CodexCliExecutionOutcome(
        returncode=0,
        stdout=SUCCESS_TRANSCRIPT.read_text(encoding="utf-8"),
        stderr="",
    )


def _manifest() -> AdapterManifest:
    return AdapterManifest(
        adapter_id=CODEX_CLI_ADAPTER_ID,
        display_name="Codex CLI Offline Adapter",
        adapter_version=CODEX_CLI_ADAPTER_VERSION,
        command=("python", "-m", "legalforecast.multiharness.codex_cli_cli"),
    )


def _request(
    *,
    model_key: str = "codex:gpt-5.1",
    metadata: dict[str, object] | None = None,
    allowed_provider_env_vars: tuple[str, ...] = (),
    adapter_id: str = CODEX_CLI_ADAPTER_ID,
) -> RunRequest:
    task_metadata = {"prompt": "solve fixture"}
    if metadata is not None:
        task_metadata.update(metadata)
    return RunRequest(
        request_id="request-1",
        task=CanonicalTask(
            task_id="lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="fixture",
            source_id="case-1",
            task_sha256=SHA256,
            metadata=task_metadata,
        ),
        adapter=AdapterManifest(
            adapter_id=adapter_id,
            display_name="Codex CLI Offline Adapter",
            adapter_version=CODEX_CLI_ADAPTER_VERSION,
            command=("python", "-m", "legalforecast.multiharness.codex_cli_cli"),
        ),
        model_key=model_key,
        sandbox_policy=SandboxPolicy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            network_policy="provider_egress_host_only",
            timeout_seconds=30,
            working_directory="/workspace",
            allowed_provider_env_vars=allowed_provider_env_vars,
        ),
        request_sha256=OTHER_SHA256,
    )
