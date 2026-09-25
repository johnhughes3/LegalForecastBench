from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.claude_code_container import (
    CLAUDE_CODE_CONTAINER_ADAPTER_ID,
    ClaudeCodeContainerAdapterError,
    ClaudeCodeContainerExecutionService,
    _normalize_claude_stream,
    _stage_visible_solver_input,
    _terminal_success,
    _verify_staged_solver_input,
    build_claude_code_container_adapter,
)

IMAGE = "sha256:" + "a" * 64


def _stream(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(event, separators=(",", ":")) for event in events)


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
