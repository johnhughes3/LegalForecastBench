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
    declared_failure_classes,
    load_codex_local_cli_manifest,
    parse_codex_jsonl,
    run_offline_protocol_fixture,
)
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
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
TRANSCRIPTS = ROOT / "tests" / "fixtures" / "codex_cli_adapter" / "transcripts"
MODULE = ROOT / "legalforecast" / "multiharness" / "codex_cli.py"
SHA256 = "sha256:" + "1" * 64
OTHER_SHA256 = "sha256:" + "2" * 64
SECRET_CANARY = "LEGALFORECAST_SECRET_CANARY_7f3a"
THREAD_ID = "00000000-0000-7000-8000-000000000001"
PLAN_MODEL = "gpt-5.1"
PLAN_PROMPT = "solve fixture"


def _canonical_argv(
    workspace: Path, *, model: str = PLAN_MODEL, effort: str = "medium"
) -> tuple[str, ...]:
    return (
        "codex",
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
        str(workspace),
        "--model",
        model,
        "-c",
        'approval_policy="never"',
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--output-last-message",
        "codex-last-message.txt",
        "-",
    )


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
    assert manifest.invocation.output_format == "stream_json"
    assert "stream_json_output" in manifest.capabilities
    assert "--json" in manifest.invocation.argv_template
    assert "--ephemeral" in manifest.invocation.argv_template
    assert "workspace-write" in manifest.invocation.argv_template
    assert 'approval_policy="never"' in manifest.invocation.argv_template
    assert manifest.invocation.argv_template[-1] == "-"
    assert "--approve-for-me" not in manifest.invocation.argv_template
    assert "--ask-for-approval" not in manifest.invocation.argv_template
    assert manifest.auth_profile_name == "fixture-none"
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


def test_invocation_plan_snapshot_is_exact_and_non_interactive(tmp_path: Path) -> None:
    request = _request()
    first = build_codex_invocation_plan(request, tmp_path, prompt=PLAN_PROMPT)
    second = build_codex_invocation_plan(request, tmp_path, prompt=PLAN_PROMPT)

    assert first.argv == _canonical_argv(tmp_path)
    assert first.argv == second.argv
    assert first.stdin == PLAN_PROMPT
    assert "--ask-for-approval" not in first.argv
    assert "--approve-for-me" not in first.argv
    assert not any(char in token for token in first.argv for char in ";|&`$")


def test_manifest_model_and_reasoning_placeholders_propagate(tmp_path: Path) -> None:
    plan = build_codex_invocation_plan(
        _request(model_key="codex:gpt-5-nano", metadata={"reasoning_effort": "low"}),
        tmp_path,
        prompt=PLAN_PROMPT,
    )
    source = MODULE.read_text(encoding="utf-8")

    assert plan.argv == _canonical_argv(tmp_path, model="gpt-5-nano", effort="low")
    assert "gpt-5.1" not in source
    assert "gpt-5-nano" not in source


def test_unallowlisted_manifest_flag_is_refused_at_plan_time(tmp_path: Path) -> None:
    manifest = _mutated_manifest(extra_flags=("--verbose",))
    with pytest.raises(CodexCliAdapterError, match="un-allowlisted flag"):
        build_codex_invocation_plan(
            _request(),
            tmp_path,
            prompt=PLAN_PROMPT,
            local_cli_manifest=manifest,
        )


def test_interactive_approval_mode_is_refused_at_plan_time(tmp_path: Path) -> None:
    asked = _mutated_manifest(extra_flags=("--ask-for-approval",))
    with pytest.raises(CodexCliAdapterError, match="interactive"):
        build_codex_invocation_plan(
            _request(),
            tmp_path,
            prompt=PLAN_PROMPT,
            local_cli_manifest=asked,
        )
    on_request = _mutated_manifest(
        replace=('approval_policy="never"', 'approval_policy="on-request"')
    )
    with pytest.raises(CodexCliAdapterError, match="approval"):
        build_codex_invocation_plan(
            _request(),
            tmp_path,
            prompt=PLAN_PROMPT,
            local_cli_manifest=on_request,
        )


def test_fixture_transcripts_declare_synthetic_provenance() -> None:
    inventory = {
        "success": True,
        "timeout": True,
        "refusal": True,
        "schema_violation": True,
        "crash": True,
        "sandbox_denial": True,
        "malformed": True,
    }
    for name, synthetic in inventory.items():
        comments, _record = _load_transcript_file(TRANSCRIPTS / f"{name}.json")
        assert any(line.startswith("command:") for line in comments)
        assert any(line.startswith("generated_at:") for line in comments)
        assert f"synthetic: {str(synthetic).lower()}" in comments


def test_declared_failure_classes_include_sandbox_denial() -> None:
    assert declared_failure_classes() == CODEX_FAILURE_CLASSES
    assert "sandbox_denial" in declared_failure_classes()
    for name in declared_failure_classes():
        assert (TRANSCRIPTS / f"{name}.json").is_file()
    assert (TRANSCRIPTS / "malformed.json").is_file()


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
        "codex-last-message.txt"
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
    service = RecordingFakeExecutionService(_outcome_from_fixture("success"))
    adapter = CodexCliAdapter(execution_service=service)
    request = _request()

    result = adapter.run(request, workspace)

    assert result.status == "succeeded"
    assert result.request_id == request.request_id
    assert result.public_summary["task_id"] == request.task.task_id
    assert result.public_summary["returncode"] == 0
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
    assert executed.argv == _canonical_argv(workspace)
    assert (workspace / "sealed-deliverable" / "work-product" / "answer.md").read_text(
        encoding="utf-8"
    ) == "LEGALFORECAST_FAKE_CODEX_RESULT\n"


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    (
        ("timeout", "timeout"),
        ("crash", "crash"),
        ("sandbox_denial", "sandbox_denial"),
        ("refusal", "refusal"),
        ("schema_violation", "schema_violation"),
        ("malformed", "schema_violation"),
    ),
)
def test_declared_failure_fixtures_are_classified_fail_closed(
    tmp_path: Path,
    fixture_name: str,
    expected: str,
) -> None:
    assert expected in CODEX_FAILURE_CLASSES
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _outcome_from_fixture(fixture_name)
        )
    )
    request = _request()

    result = adapter.run(request, workspace)

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == expected
    assert result.public_summary["task_id"] == request.task.task_id
    assert "returncode" in result.public_summary
    assert f"task_id={request.task.task_id}" in result.public_summary["failure_detail"]
    assert "returncode=" in result.public_summary["failure_detail"]
    assert "deliverable_manifest_sha256" not in result.public_summary
    validate_public_record(result.to_record(), "failed_run_result")


def test_unparseable_envelope_is_error_not_empty_success(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _outcome_from_fixture("malformed")
        )
    ).run(_request(), workspace)

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == "schema_violation"
    assert result.public_summary["task_id"] == "lfb:case-1:full_packet"
    assert result.artifacts == ()


def test_sandbox_denial_is_distinct_from_crash(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    denied = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _outcome_from_fixture("sandbox_denial")
        )
    ).run(_request(), workspace)
    crashed = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_outcome_from_fixture("crash"))
    ).run(_request(), workspace)

    assert denied.public_summary["failure_class"] == "sandbox_denial"
    assert crashed.public_summary["failure_class"] == "crash"
    assert (
        denied.public_summary["failure_class"]
        != crashed.public_summary["failure_class"]
    )


def test_legal_refused_language_is_not_classified_as_refusal(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    text = "The district court refused relief on the remaining counts."
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _message_outcome(text, complete=True)
        )
    ).run(_request(), workspace)

    assert result.status == "succeeded"
    assert "failure_class" not in result.public_summary
    assert "served_model" not in result.public_summary


def test_first_person_refusal_is_still_classified(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _message_outcome("I must decline this request.", complete=True)
        )
    ).run(_request(), workspace)

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == "refusal"


def test_landlocked_legal_language_is_not_classified_as_sandbox_denial(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    text = "The plaintiff is a landlocked state seeking seccomp-style discovery limits."
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            _message_outcome(text, complete=True)
        )
    ).run(_request(), workspace)

    assert result.status == "succeeded"
    assert "failure_class" not in result.public_summary


def test_thread_started_must_be_the_unique_first_event() -> None:
    stdout = _jsonl(
        {"type": "turn.started"},
        {"type": "thread.started", "thread_id": THREAD_ID},
        {
            "type": "item.completed",
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        },
    )
    envelope = parse_codex_jsonl(
        stdout,
        requested_model_name="gpt-5.1",
        returncode=0,
        timed_out=False,
        crashed=False,
    )

    assert envelope.failure_class == "schema_violation"


class _SymlinkDuringExecute(RecordingFakeExecutionService):
    def __init__(
        self,
        outcome: CodexCliExecutionOutcome,
        *,
        target: Path,
        relative: str,
    ) -> None:
        super().__init__(outcome)
        self.target = target
        self.relative = relative

    def execute(self, request: CodexCliExecutionRequest) -> CodexCliExecutionOutcome:
        destination = request.cwd / self.relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        destination.symlink_to(self.target)
        return super().execute(request)


def test_private_stdout_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    outside = tmp_path / "host-secret.txt"
    outside.write_text("HOST_SECRET\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=_SymlinkDuringExecute(
            _success_outcome(),
            target=outside,
            relative="private-logs/codex-stdout.jsonl",
        )
    )

    with pytest.raises(CodexCliAdapterError, match="symlink"):
        adapter.run(_request(), workspace)
    assert outside.read_text(encoding="utf-8") == "HOST_SECRET\n"


def test_last_message_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    outside = tmp_path / "host-secret.txt"
    outside.write_text("HOST_SECRET\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=_SymlinkDuringExecute(
            _success_outcome(),
            target=outside,
            relative="codex-last-message.txt",
        )
    )

    with pytest.raises(CodexCliAdapterError, match="symlink"):
        adapter.run(_request(), workspace)
    assert outside.read_text(encoding="utf-8") == "HOST_SECRET\n"


def test_prompt_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    outside = tmp_path / "host-secret.txt"
    outside.write_text("HOST_SECRET\n", encoding="utf-8")
    (workspace / "prompt.txt").symlink_to(outside)
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_success_outcome())
    )

    with pytest.raises(CodexCliAdapterError, match="symlink"):
        adapter.run(_request(), workspace)
    assert outside.read_text(encoding="utf-8") == "HOST_SECRET\n"


def test_private_logs_directory_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    outside = tmp_path / "host-dir"
    outside.mkdir()
    (workspace / "private-logs").symlink_to(outside)
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_success_outcome())
    )

    with pytest.raises(CodexCliAdapterError, match="real directory"):
        adapter.run(_request(), workspace)


def test_submission_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    outside = tmp_path / "host-secret.txt"
    outside.write_text("HOST_SECRET\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=_SymlinkDuringExecute(
            _success_outcome(),
            target=outside,
            relative="codex-output/submission.md",
        )
    )

    with pytest.raises(CodexCliAdapterError, match="symlink"):
        adapter.run(_request(), workspace)
    assert outside.read_text(encoding="utf-8") == "HOST_SECRET\n"


def test_deliverable_manifest_symlink_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    outside = tmp_path / "host-secret.txt"
    outside.write_text("HOST_SECRET\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=_SymlinkDuringExecute(
            _success_outcome(),
            target=outside,
            relative="private-logs/codex-deliverable-manifest.json",
        )
    )

    with pytest.raises(CodexCliAdapterError, match="symlink"):
        adapter.run(_request(), workspace)
    assert outside.read_text(encoding="utf-8") == "HOST_SECRET\n"


def test_command_execution_events_are_counted(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    stdout = _jsonl(
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {
            "type": "item.updated",
            "item": {
                "id": "item_cmd",
                "type": "command_execution",
                "status": "running",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "item_cmd",
                "type": "command_execution",
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        },
    )
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            CodexCliExecutionOutcome(returncode=0, stdout=stdout, stderr="")
        )
    ).run(_request(), workspace)

    assert result.status == "succeeded"
    assert result.public_summary["tool_call_count"] == 1
    assert "provider_request_count" not in result.public_summary


def test_timeout_preserves_partial_command_execution_count(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    stdout = _jsonl(
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "item_cmd",
                "type": "command_execution",
                "status": "completed",
            },
        },
    )
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(
            CodexCliExecutionOutcome(
                returncode=-1,
                stdout=stdout,
                stderr="",
                timed_out=True,
            )
        )
    ).run(_request(), workspace)

    assert result.status == "failed"
    assert result.public_summary["failure_class"] == "timeout"
    assert result.public_summary["tool_call_count"] == 1


def test_item_updated_events_are_not_schema_violations() -> None:
    stdout = _jsonl(
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {
            "type": "item.updated",
            "item": {
                "id": "item_cmd",
                "type": "command_execution",
                "status": "running",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        },
    )
    envelope = parse_codex_jsonl(
        stdout,
        requested_model_name="gpt-5.1",
        returncode=0,
        timed_out=False,
        crashed=False,
    )

    assert envelope.failure_class is None
    assert envelope.served_model is None
    assert envelope.input_tokens == 3


def test_malformed_usage_is_schema_violation_not_zero_tokens() -> None:
    stdout = _jsonl(
        {"type": "thread.started", "thread_id": THREAD_ID},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "item_0",
                "text": "LEGALFORECAST_FAKE_CODEX_RESULT",
                "type": "agent_message",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": "3", "output_tokens": 4}},
    )
    envelope = parse_codex_jsonl(
        stdout,
        requested_model_name="gpt-5.1",
        returncode=0,
        timed_out=False,
        crashed=False,
    )

    assert envelope.failure_class == "schema_violation"


def test_stale_last_message_file_is_cleared_before_execute(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    (workspace / "codex-last-message.txt").write_text(
        "STALE_ANSWER\n", encoding="utf-8"
    )
    result = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_success_outcome())
    ).run(_request(), workspace)

    assert result.status == "succeeded"
    answer = (
        workspace / "sealed-deliverable" / "work-product" / "answer.md"
    ).read_text(encoding="utf-8")
    assert answer == "LEGALFORECAST_FAKE_CODEX_RESULT\n"
    assert "STALE_ANSWER" not in answer


def test_workspace_can_be_reused_after_a_successful_seal(tmp_path: Path) -> None:
    workspace = tmp_path / "row"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("solve fixture\n", encoding="utf-8")
    adapter = CodexCliAdapter(
        execution_service=RecordingFakeExecutionService(_success_outcome())
    )
    first = adapter.run(_request(), workspace)
    second = adapter.run(_request(), workspace)

    assert first.status == "succeeded"
    assert second.status == "succeeded"


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


def _load_transcript_file(path: Path) -> tuple[list[str], dict[str, Any]]:
    comments: list[str] = []
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("//"):
            comments.append(line[2:].strip())
        else:
            body.append(line)
    decoded = json.loads("\n".join(body))
    if not isinstance(decoded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return comments, decoded


def _outcome_from_fixture(name: str) -> CodexCliExecutionOutcome:
    _comments, record = _load_transcript_file(TRANSCRIPTS / f"{name}.json")
    stdout = record.get("stdout_text")
    if not isinstance(stdout, str):
        stdout = ""
    returncode = record.get("returncode", 0)
    if type(returncode) is not int:
        returncode = 0
    return CodexCliExecutionOutcome(
        returncode=returncode,
        stdout=stdout,
        stderr=str(record.get("stderr") or ""),
        timed_out=bool(record.get("timed_out")),
        crashed=bool(record.get("crashed")),
    )


def _mutated_manifest(
    *,
    extra_flags: tuple[str, ...] = (),
    replace: tuple[str, str] | None = None,
) -> LocalCliAdapterManifest:
    record = json.loads(LOCAL_CLI_MANIFEST.read_text(encoding="utf-8"))
    template = list(record["invocation"]["argv_template"])
    if replace is not None:
        template = [replace[1] if token == replace[0] else token for token in template]
    if extra_flags:
        insert_at = template.index("-") if "-" in template else len(template)
        for flag in extra_flags:
            template.insert(insert_at, flag)
            insert_at += 1
    record["invocation"]["argv_template"] = template
    record["capability_digest"] = capability_digest_for(record)
    return LocalCliAdapterManifest.from_record(record)


def _success_outcome() -> CodexCliExecutionOutcome:
    return _outcome_from_fixture("success")


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
