from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast.multiharness.claude_code_container import (
    CLAUDE_CODE_CONTAINER_ADAPTER_ID,
    ClaudeCodeContainerAdapter,
    ClaudeCodeContainerAdapterError,
    ClaudeCodeContainerExecutionService,
    _normalize_claude_stream,
    _stage_visible_solver_input,
    _terminal_success,
    _verify_staged_solver_input,
    build_claude_code_container_adapter,
)
from legalforecast.multiharness.claude_code_container_runtime import (
    _fence_allows_forecast,
)
from legalforecast.multiharness.container_harness.fence import (
    ParserFenceFields,
    fence_from_parser_fields,
)
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    read_release_object,
    release_bytes_sha256,
    write_release_json_create_only,
)
from legalforecast.multiharness.release_runtime import write_release_create_only
from legalforecast.multiharness.spec import ArtifactRecord, RunResult

IMAGE = "sha256:" + "a" * 64


@pytest.mark.parametrize(
    ("tools", "web_tools", "web_requests", "observable", "accepted"),
    (
        (("Bash",), (), 0, True, True),
        (("Bash",), ("WebSearch",), 0, True, False),
        (("Bash",), (), 1, True, False),
        ((), (), 0, True, False),
        (("Bash",), (), 0, False, False),
    ),
)
def test_scored_forecast_requires_observed_no_web_fence(
    tools: tuple[str, ...],
    web_tools: tuple[str, ...],
    web_requests: int,
    observable: bool,
    accepted: bool,
) -> None:
    fence = fence_from_parser_fields(
        ParserFenceFields(
            parse_ok=True,
            reports_fence=observable,
            tools_available=tools,
            server_side_web_tools_available=web_tools,
            server_side_web_request_count=web_requests,
        )
    )
    assert _fence_allows_forecast(fence) is accepted


def _stream(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(event, separators=(",", ":")) for event in events)


class _FakeClaudeDelegate:
    def __init__(self, output: bytes) -> None:
        self.output = output

    def run_with_prompt(
        self,
        _request: object,
        workspace: Path,
        _instruction: str,
    ) -> RunResult:
        output_path = workspace / "deliverable-sealed/forecast.json"
        output_path.parent.mkdir(parents=True)
        write_release_create_only(output_path, self.output, mode=0o600)
        artifact = ArtifactRecord(
            artifact_id="claude-code-forecast",
            path="deliverable-sealed/forecast.json",
            sha256=release_bytes_sha256(self.output),
            media_type="application/json",
            public=True,
            size_bytes=len(self.output),
        )
        return RunResult(
            result_id="request:claude-code-container",
            request_id="request",
            status="succeeded",
            result_sha256="sha256:" + "b" * 64,
            artifacts=(artifact,),
            public_summary={"tool_call_count": 2, "input_tokens": 9},
        )


def _write_container_evidence(output_root: Path, request_id: str) -> None:
    run_key = hashlib.sha256(request_id.encode()).hexdigest()[:16]
    run_root = output_root / run_key
    package_root = run_root / "package"
    logs_root = run_root / "logs"
    package_root.mkdir(parents=True)
    logs_root.mkdir()
    write_release_json_create_only(
        package_root / "result.json",
        {
            "run_id": "claude-test",
            "exit_code": 0,
            "timed_out": False,
            "stdout_file": "harness.stdout",
            "stderr_file": "harness.stderr",
            "gateway_usage": {"request_count": 3},
        },
    )
    write_release_json_create_only(
        package_root / "fence.json",
        {
            "source": "parser",
            "parser_fields": {
                "tools_available": ["Bash", "StructuredOutput"],
            },
        },
    )
    write_release_json_create_only(
        package_root / "proxy-logs.json",
        {"decision_count": 3, "refused": []},
    )
    write_release_create_only(
        logs_root / "harness.stdout", b"actual stdout\n", mode=0o600
    )
    write_release_create_only(
        logs_root / "harness.stderr", b"actual stderr\n", mode=0o600
    )


def test_solver_input_run_bridges_container_forecast_and_evidence(
    tmp_path: Path,
) -> None:
    request_id = "request"
    prompt = b"authenticated prompt\n"
    forecast = json.dumps(
        {
            "case_assessment": "ok",
            "predictions": [
                {"unit_id": "unit-1", "probability_fully_dismissed": 0.25}
            ],
        },
        separators=(",", ":"),
    ).encode()
    solver_input_root = tmp_path / "solver-input"
    solver_input_root.mkdir()
    write_release_create_only(
        solver_input_root / "prompt.txt", prompt, mode=0o600
    )
    output_root = tmp_path / "container-output"
    _write_container_evidence(output_root, request_id)
    request = SimpleNamespace(
        request_id=request_id,
        request_sha256="sha256:" + "c" * 64,
        model_key="anthropic:claude-sonnet-4",
        task=SimpleNamespace(
            metadata={
                "prompt_sha256": release_bytes_sha256(prompt),
                "packet_sha256": "sha256:" + "d" * 64,
                "required_unit_ids": ["unit-1"],
            }
        ),
    )
    adapter = ClaudeCodeContainerAdapter(
        delegate=_FakeClaudeDelegate(forecast),
        image_digest=IMAGE,
        model_key=request.model_key,
        auth_profile="fixture-none",
        max_budget_usd=None,
        approval_reference=None,
        output_root=output_root,
        backend="docker",
        timeout_seconds=30,
        case_count=None,
        per_case_budget_usd=None,
        execution_mode="outer-container-only",
        outer_container_verified=True,
    )

    result = adapter.run_with_solver_input(
        request, tmp_path / "workspace", solver_input_root
    )

    output_artifact = next(
        artifact
        for artifact in result.artifacts
        if artifact.artifact_id == RELEASE_FORECAST_OUTPUT_ARTIFACT_ID
    )
    transcript_artifact = next(
        artifact
        for artifact in result.artifacts
        if artifact.artifact_id == RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID
    )
    assert output_artifact.public is False
    assert transcript_artifact.public is False
    assert output_artifact.path == "private-logs/release-forecast-output.json"
    assert transcript_artifact.path == "private-logs/release-harness-transcript.json"
    assert result.public_summary["harness_track"] == "native"
    assert result.public_summary["allowed_tools"] == ["Bash", "StructuredOutput"]
    assert result.public_summary["tool_policy"] == "container_fence:parser"
    assert result.public_summary["tool_call_count"] == 2
    transcript = read_release_object(
        tmp_path / "workspace/private-logs/release-harness-transcript.json",
        "test transcript",
    )
    assert transcript["request_sha256"] == request.request_sha256
    assert transcript["packet_sha256"] == request.task.metadata["packet_sha256"]
    assert transcript["response_sha256"] == output_artifact.sha256
    assert transcript["stdout_sha256"] == release_bytes_sha256(b"actual stdout\n")
    assert transcript["stderr_sha256"] == release_bytes_sha256(b"actual stderr\n")
    assert transcript["fence"]["source"] == "parser"
    assert result.result_sha256 != "sha256:" + "b" * 64


class _FailingClaudeDelegate:
    def run_with_prompt(
        self,
        _request: object,
        _workspace: Path,
        _instruction: str,
    ) -> RunResult:
        return RunResult(
            result_id="request:claude-code-container",
            request_id="request",
            status="failed",
            result_sha256="sha256:" + "e" * 64,
            public_summary={"failure_class": "timeout", "tool_call_count": 1},
        )


def test_solver_input_run_preserves_delegate_failure_without_projection(
    tmp_path: Path,
) -> None:
    prompt = b"authenticated prompt\n"
    solver_input_root = tmp_path / "solver-input"
    solver_input_root.mkdir()
    write_release_create_only(
        solver_input_root / "prompt.txt", prompt, mode=0o600
    )
    request = SimpleNamespace(
        request_id="request",
        request_sha256="sha256:" + "c" * 64,
        model_key="anthropic:claude-sonnet-4",
        task=SimpleNamespace(
            metadata={"prompt_sha256": release_bytes_sha256(prompt)}
        ),
    )
    result = _FailingClaudeDelegate()
    adapter = ClaudeCodeContainerAdapter(
        delegate=result,
        image_digest=IMAGE,
        model_key=request.model_key,
        auth_profile="fixture-none",
        max_budget_usd=None,
        approval_reference=None,
        output_root=tmp_path / "container-output",
        backend="docker",
        timeout_seconds=30,
        case_count=None,
        per_case_budget_usd=None,
        execution_mode="outer-container-only",
        outer_container_verified=True,
    )

    observed = adapter.run_with_solver_input(
        request, tmp_path / "workspace", solver_input_root
    )

    assert observed.status == "failed"
    assert observed.result_sha256 == "sha256:" + "e" * 64
    assert observed.public_summary["failure_class"] == "timeout"


def test_factory_binds_image_and_release_identity(tmp_path: Path) -> None:
    adapter = build_claude_code_container_adapter(
        image_digest=IMAGE,
        auth_profile="fixture-none",
        model_key="anthropic:claude-sonnet-4",
        max_budget_usd=None,
        approval_reference=None,
        output_root=tmp_path,
    )

    assert adapter.manifest.adapter_id == CLAUDE_CODE_CONTAINER_ADAPTER_ID
    assert adapter.image_digest == IMAGE
    assert adapter.model_key == "anthropic:claude-sonnet-4"
    assert adapter.sandbox_verified is False


def test_paid_factory_requires_case_count_and_approval(tmp_path: Path) -> None:
    with pytest.raises(ClaudeCodeContainerAdapterError, match="approval_reference"):
        build_claude_code_container_adapter(
            image_digest=IMAGE,
            auth_profile="published-api-key",
            model_key="anthropic:claude-sonnet-4",
            max_budget_usd=10.0,
            approval_reference=None,
            output_root=tmp_path,
            case_count=2,
        )

    with pytest.raises(ClaudeCodeContainerAdapterError, match="case_count"):
        build_claude_code_container_adapter(
            image_digest=IMAGE,
            auth_profile="published-api-key",
            model_key="anthropic:claude-sonnet-4",
            max_budget_usd=10.0,
            approval_reference="approval-record",
            output_root=tmp_path,
        )


def test_run_refuses_before_any_credential_or_container_step(tmp_path: Path) -> None:
    adapter = build_claude_code_container_adapter(
        image_digest=IMAGE,
        auth_profile="fixture-none",
        model_key="anthropic:claude-sonnet-4",
        max_budget_usd=None,
        approval_reference=None,
        output_root=tmp_path,
    )

    with pytest.raises(ClaudeCodeContainerAdapterError, match="sandbox"):
        adapter._preflight("anthropic:claude-sonnet-4")


def test_factory_uses_real_container_execution_service_and_internal_probe(
    tmp_path: Path,
) -> None:
    adapter = build_claude_code_container_adapter(
        image_digest=IMAGE,
        auth_profile="fixture-none",
        model_key="anthropic:claude-sonnet-4",
        max_budget_usd=None,
        approval_reference=None,
        output_root=tmp_path,
        fixture_base_url="https://fixture-provider:8443",
    )

    assert adapter.sandbox_verified is False
    assert isinstance(
        adapter.delegate.execution_service, ClaudeCodeContainerExecutionService
    )
    assert adapter.delegate.output_format == "stream-json"
    assert adapter.delegate.verbose is True
    assert adapter.delegate.execution_service.sandbox_verified is False


def test_stream_result_requires_bash_reference_to_staged_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "prompt.txt").write_text("prompt")
    (tmp_path / "documents" / "opinion.txt").write_text("opinion")
    stream = _stream(
        {"type": "system", "subtype": "init", "model": "claude-sonnet-4"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-read",
                        "name": "Bash",
                        "input": {
                            "command": "cat /workspace/prompt.txt "
                            "/workspace/documents/opinion.txt"
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-read",
                        "content": "authenticated input",
                    }
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '{"case_assessment":"ok","predictions":[]}',
        },
    )

    normalized, envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is True
    assert envelope is not None
    assert envelope["model"] == "claude-sonnet-4"
    trace = envelope["_lfb_tool_trace"]
    assert trace == {
        "bash_tool_count": 1,
        "read_tool_count": 1,
        "referenced_paths": [
            "/workspace/prompt.txt",
            "/workspace/documents/opinion.txt",
        ],
    }
    assert "cat /workspace" not in normalized
    assert _terminal_success(envelope) is True


def test_stream_result_does_not_count_path_mention_as_a_read(
    tmp_path: Path,
) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "prompt.txt").write_text("prompt")
    (tmp_path / "documents" / "opinion.txt").write_text("opinion")
    stream = _stream(
        {"type": "system", "subtype": "init", "model": "claude-sonnet-4"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-echo",
                        "name": "Bash",
                        "input": {
                            "command": "echo /workspace/prompt.txt "
                            "/workspace/documents/opinion.txt"
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-echo",
                        "is_error": False,
                        "content": "mentioned",
                    }
                ]
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "{}"},
    )

    _normalized, envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is False
    assert envelope is not None
    assert envelope["_lfb_tool_trace"] == {
        "bash_tool_count": 1,
        "read_tool_count": 0,
        "referenced_paths": [],
    }
    assert _terminal_success(envelope) is True


@pytest.mark.parametrize(
    "command",
    (
        "cat --help /workspace/prompt.txt /workspace/documents/opinion.txt",
        "cat --version /workspace/prompt.txt /workspace/documents/opinion.txt",
        "cat /workspace/prompt.txt /workspace/documents/opinion.txt; echo ok",
        "cat /workspace/prompt.txt\n/workspace/documents/opinion.txt",
    ),
)
def test_stream_result_rejects_cat_options_as_read_evidence(
    tmp_path: Path,
    command: str,
) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "prompt.txt").write_text("prompt")
    (tmp_path / "documents" / "opinion.txt").write_text("opinion")
    stream = _stream(
        {"type": "system", "subtype": "init", "model": "claude-sonnet-4"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-option",
                        "name": "Bash",
                        "input": {"command": command},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-option",
                        "is_error": False,
                    }
                ]
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "{}"},
    )

    _normalized, envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is False
    assert envelope is not None
    assert envelope["_lfb_tool_trace"] == {
        "bash_tool_count": 1,
        "read_tool_count": 0,
        "referenced_paths": [],
    }


def test_stream_result_requires_every_staged_document(
    tmp_path: Path,
) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "prompt.txt").write_text("prompt")
    (tmp_path / "documents" / "opinion-a.txt").write_text("opinion a")
    (tmp_path / "documents" / "opinion-b.txt").write_text("opinion b")
    stream = _stream(
        {"type": "system", "subtype": "init", "model": "claude-sonnet-4"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-one-doc",
                        "name": "Bash",
                        "input": {
                            "command": "cat /workspace/prompt.txt "
                            "/workspace/documents/opinion-a.txt"
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-one-doc",
                        "is_error": False,
                    }
                ]
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "{}"},
    )

    _normalized, envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is False
    assert envelope is not None
    assert envelope["_lfb_tool_trace"]["referenced_paths"] == [
        "/workspace/prompt.txt",
        "/workspace/documents/opinion-a.txt",
    ]


def test_stream_result_requires_successful_matching_tool_result(
    tmp_path: Path,
) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "prompt.txt").write_text("prompt")
    (tmp_path / "documents" / "opinion.txt").write_text("opinion")
    stream = _stream(
        {"type": "system", "subtype": "init", "model": "claude-sonnet-4"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-failed",
                        "name": "Bash",
                        "input": {
                            "command": "cat /workspace/prompt.txt "
                            "/workspace/documents/opinion.txt"
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-failed",
                        "is_error": True,
                        "content": "permission denied",
                    }
                ]
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "{}"},
    )

    _normalized, envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is False
    assert envelope is not None
    assert envelope["_lfb_tool_trace"]["bash_tool_count"] == 0


def test_stream_result_without_bash_reference_is_not_success(
    tmp_path: Path,
) -> None:
    (tmp_path / "prompt.txt").write_text("prompt")
    stream = "\n".join(
        (
            '{"type":"system","subtype":"init","model":"claude-sonnet-4"}',
            '{"type":"result","subtype":"success","is_error":false,"result":"{}"}',
        )
    )

    _normalized, _envelope, trace_ok = _normalize_claude_stream(stream, tmp_path)

    assert trace_ok is False


def test_stage_solver_input_copies_prompt_and_visible_documents_only(
    tmp_path: Path,
) -> None:
    source = tmp_path / "solver-input"
    (source / "documents").mkdir(parents=True)
    (source / "prompt.txt").write_bytes(b"authenticated prompt")
    (source / "documents" / "opinion.txt").write_bytes(b"visible opinion")
    workspace = tmp_path / "workspace"

    files, directories = _stage_visible_solver_input(source, workspace)

    assert (workspace / "prompt.txt").read_bytes() == b"authenticated prompt"
    assert (workspace / "documents" / "opinion.txt").read_bytes() == b"visible opinion"
    assert (workspace / "prompt.txt").stat().st_mode & 0o777 == 0o444
    assert (workspace / "documents" / "opinion.txt").stat().st_mode & 0o777 == 0o444
    assert (workspace / "documents").stat().st_mode & 0o777 == 0o755
    _verify_staged_solver_input(files)
    for path, _payload in reversed(files):
        path.unlink()
    for path in reversed(directories):
        path.rmdir()
    assert not (workspace / "documents" / "opinion.txt").exists()
