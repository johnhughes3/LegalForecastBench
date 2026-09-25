from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.multiharness.claude_code_container import (
    CLAUDE_CODE_CONTAINER_ADAPTER_ID,
    ClaudeCodeContainerAdapterError,
    ClaudeCodeContainerExecutionService,
    _stage_visible_solver_input,
    _verify_staged_solver_input,
    build_claude_code_container_adapter,
)

IMAGE = "sha256:" + "a" * 64


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
        fixture_base_url="http://fixture-provider:8010",
    )

    assert adapter.sandbox_verified is False
    assert isinstance(
        adapter.delegate.execution_service, ClaudeCodeContainerExecutionService
    )


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
    _verify_staged_solver_input(files)
    for path, _payload in reversed(files):
        path.unlink()
    for path in reversed(directories):
        path.rmdir()
    assert not (workspace / "documents" / "opinion.txt").exists()
