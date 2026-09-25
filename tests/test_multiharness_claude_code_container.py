from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import legalforecast.multiharness.claude_code_container_runtime as container_runtime
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
from legalforecast.multiharness.claude_code_container_runtime import (
    _fence_allows_forecast,
)
from legalforecast.multiharness.container_harness.fence import (
    ParserFenceFields,
    fence_from_parser_fields,
)

IMAGE = "sha256:" + "a" * 64
RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "infra" / "claude-code-runtime"


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


def test_outer_fixture_factory_uses_gateway_and_skips_native_probe(
    tmp_path: Path,
) -> None:
    adapter = build_claude_code_container_adapter(
        image_digest=IMAGE,
        auth_profile="fixture-none",
        model_key="anthropic:claude-sonnet-4",
        max_budget_usd=None,
        approval_reference=None,
        output_root=tmp_path,
        execution_mode="outer-container-only",
        gateway_base_url="https://fixture-gateway:8443/v1",
    )

    assert adapter.execution_mode == "outer-container-only"
    assert adapter.sandbox_verified is False
    assert adapter.outer_container_verified is True
    service = adapter.delegate.execution_service
    assert isinstance(service, ClaudeCodeContainerExecutionService)
    assert service.gateway_base_url == ("https://fixture-gateway:8443/v1")
    adapter._preflight("anthropic:claude-sonnet-4")


def test_outer_fixture_mode_rejects_paid_profile_and_shared_network(
    tmp_path: Path,
) -> None:
    with pytest.raises(ClaudeCodeContainerAdapterError, match="fixture-only"):
        build_claude_code_container_adapter(
            image_digest=IMAGE,
            auth_profile="published-api-key",
            model_key="anthropic:claude-sonnet-4",
            max_budget_usd=1.0,
            approval_reference="approval-record",
            output_root=tmp_path,
            case_count=1,
            execution_mode="outer-container-only",
            gateway_base_url="https://fixture-gateway:8443",
        )

    with pytest.raises(ClaudeCodeContainerAdapterError, match="per-run egress"):
        build_claude_code_container_adapter(
            image_digest=IMAGE,
            auth_profile="fixture-none",
            model_key="anthropic:claude-sonnet-4",
            max_budget_usd=None,
            approval_reference=None,
            output_root=tmp_path,
            execution_mode="outer-container-only",
            gateway_base_url="https://fixture-gateway:8443",
            fixture_egress_network="shared-network",
        )


def test_outer_fixture_service_bounds_gateway_and_projects_only_dummy_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def refuse_run(
        spec: object, *, publication_directory: Path, backend: str
    ) -> object:
        del publication_directory, backend
        captured["spec"] = spec
        raise RuntimeError("fixture probe stops before model exchange")

    monkeypatch.setattr(container_runtime, "run_container_harness", refuse_run)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "prompt.txt").write_text("fixture prompt", encoding="utf-8")
    (workspace / "documents").mkdir()
    (workspace / "documents" / "opinion.txt").write_text(
        "fixture opinion", encoding="utf-8"
    )
    service = ClaudeCodeContainerExecutionService(
        image_digest=IMAGE,
        auth_profile="fixture-none",
        output_root=tmp_path / "output",
        gateway_base_url="https://fixture-gateway:8443/v1",
        execution_mode="outer-container-only",
    )
    receipt = service.execute(
        container_runtime.RunSpec(
            spec_id="outer-fixture",
            argv=("claude", "-p", "fixture"),
            working_directory=workspace,
        )
    )

    assert receipt.status == "failed"
    planned = captured["spec"]
    assert isinstance(planned, container_runtime.ContainerHarnessSpec)
    assert planned.allow_hosts == ("fixture-gateway",)
    assert planned.allow_ports == (8443,)
    assert planned.egress_network is None
    assert planned.environment["ANTHROPIC_API_KEY"] == "fixture-only-dummy-key"
    assert "ANTHROPIC_AUTH_TOKEN" not in planned.environment
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in planned.environment
    assert planned.read_only_workspace_paths == ("prompt.txt", "documents")
    assert planned.container_user == "0:0"


def test_image_policy_is_managed_and_denies_direct_vendor_web_tools() -> None:
    policy_path = RUNTIME_ROOT / "managed-settings.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert policy["permissions"]["deny"] == ["WebSearch", "WebFetch", "mcp__*"]
    assert policy["allowManagedPermissionRulesOnly"] is True
    assert policy["disableSideloadFlags"] is True
    assert policy["sandbox"]["network"] == {
        "allowManagedDomainsOnly": True,
        "allowedDomains": [],
        "strictAllowlist": True,
    }
    containerfile = (RUNTIME_ROOT / "Containerfile").read_text(encoding="utf-8")
    assert "COPY infra/claude-code-runtime/managed-settings.json" in containerfile
    assert "chmod 0444 /etc/claude-code/managed-settings.json" in containerfile


@pytest.mark.skipif(
    not os.environ.get("LEGALFORECAST_CLAUDE_RUNTIME_E2E_IMAGE"),
    reason="set LEGALFORECAST_CLAUDE_RUNTIME_E2E_IMAGE to run the built-image probe",
)
def test_built_image_direct_vendor_cannot_reenable_web_search() -> None:
    """Exercise the absolute vendor path, bypassing the PATH wrapper.

    The dummy endpoint is intentionally unreachable and the network is none;
    the first stream event is emitted before any model request. A direct vendor
    invocation that asks for WebSearch must still report no enabled tools from
    the image-managed policy. This test never contacts a provider.
    """

    image = os.environ["LEGALFORECAST_CLAUDE_RUNTIME_E2E_IMAGE"]
    container_name = f"lfb-claude-policy-{os.getpid()}"
    argv = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=16m",
        "--tmpfs",
        "/home/harness:rw,nosuid,nodev,size=16m",
        "--env",
        "ANTHROPIC_API_KEY=fixture-only-dummy-key",
        "--env",
        "ANTHROPIC_BASE_URL=https://127.0.0.1:1",
        "--entrypoint",
        "/opt/legalforecast/libexec/claude",
        image,
        "-p",
        "probe",
        "--tools",
        "WebSearch",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        stdout_value = exc.stdout or ""
        stderr_value = exc.stderr or ""
        stdout = (
            stdout_value.decode(errors="replace")
            if isinstance(stdout_value, bytes)
            else stdout_value
        )
        stderr = (
            stderr_value.decode(errors="replace")
            if isinstance(stderr_value, bytes)
            else stderr_value
        )
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container_name],
            capture_output=True,
            text=True,
            check=False,
        )
    first = next((line for line in stdout.splitlines() if line.strip()), None)
    assert first is not None, stderr
    event = json.loads(first)
    assert event["type"] == "system"
    assert event["subtype"] == "init"
    assert event["tools"] == []


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
