"""Managed Claude policy and outer-container fixture behavior."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import legalforecast.multiharness.claude_code_container_runtime as container_runtime
import pytest
from legalforecast.multiharness.claude_code_container import (
    ClaudeCodeContainerAdapterError,
    ClaudeCodeContainerExecutionService,
    build_claude_code_container_adapter,
)

IMAGE = "sha256:" + "a" * 64
RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "infra" / "claude-code-runtime"


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
