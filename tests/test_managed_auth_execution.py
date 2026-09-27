"""Managed case authentication and whole-session spend integration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import legalforecast.runner.managed_execution as managed_execution
import pytest
from legalforecast.runner.managed_execution import (
    ManagedCaseInput,
    ManagedToolAgentResult,
)

from test_managed_tool_agent import _AttemptHandler, _entry, _Executor


@pytest.mark.parametrize("standard_tier", [False, True])
@pytest.mark.parametrize("auth_mode", ["api_key", "workload_identity"])
def test_official_cell_settles_the_entire_agent_session_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, standard_tier: bool, auth_mode: str
) -> None:
    from collections.abc import Generator
    from contextlib import contextmanager

    entry = (
        replace(
            _entry(),
            model_id="gpt-4.1-2025-04-14",
            model_version_or_snapshot="gpt-4.1-2025-04-14",
            reasoning_effort=None,
            input_token_price=2.0,
            output_token_price=8.0,
            cache_read_token_price=0.5,
        )
        if standard_tier
        else _entry()
    )
    tier = "default" if standard_tier else "flex"
    executor = _Executor()

    @contextmanager
    def session(**_kwargs: Any) -> Generator[_Executor]:
        yield executor

    raw_output = (
        '{"case_assessment":"Assessment","predictions":['
        '{"unit_id":"unit-a","probability_fully_dismissed":0.5}]}'
    )
    monkeypatch.setattr(
        "legalforecast.runner.tool_runtime.open_official_tool_session", session
    )
    managed_arguments: dict[str, Any] = {}

    def managed_agent(*_args: Any, **kwargs: Any) -> ManagedToolAgentResult:
        managed_arguments.update(kwargs)
        return ManagedToolAgentResult(
            raw_output=raw_output,
            request_count=3,
            input_tokens=100,
            output_tokens=20,
            served_model=entry.model_version_or_snapshot,
            finish_reason="stop",
            service_tier=tier,
            called_tools=("read",),
            response_usages=((40, 5), (30, 5), (30, 10)),
        )

    monkeypatch.setattr(managed_execution, "run_managed_tool_agent", managed_agent)
    observed: list[bytes] = []
    handler = _AttemptHandler()

    response = managed_execution.complete_managed_tool_cell(
        entry,
        handler=cast(Any, handler),
        managed_case=ManagedCaseInput(
            case_id="case-1",
            required_unit_ids=("unit-a",),
            documents={"documents/case-1/motion.txt": b"FULL DOCUMENT BODY"},
            unit_descriptions=(
                {
                    "unit_id": "unit-a",
                    "claim_name": "Section 10(b)",
                    "defendant_group": "issuer",
                    "count": "Count I",
                },
            ),
            document_descriptions=(
                {
                    "path": "/workspace/documents/case-1/motion.txt",
                    "document_id": "motion",
                    "role": "motion_to_dismiss",
                },
            ),
            cell_id="cell-1",
        ),
        request_body_observer=observed.append,
        environ={
            "OPENAI_API_KEY": "fixture-key",
            "LEGALFORECAST_OPENAI_AUTH_MODE": auth_mode,
            "LEGALFORECAST_OPENAI_WIF_AUDIENCE": "benchmark-audience",
            "LEGALFORECAST_OPENAI_WIF_PROVIDER_ID": "provider-id",
            "LEGALFORECAST_OPENAI_WIF_SERVICE_ACCOUNT_ID": "service-account-id",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://run.actions.githubusercontent.com/token",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "secret-github-token",
            "LFB_HARVEY_TOOL_IMAGE": "sha256:" + "a" * 64,
        },
        registry_sha256="sha256:" + "b" * 64,
    )

    assert len(observed) == 1
    assert response.raw_output == raw_output
    assert response.request_count == 3
    assert response.metadata is not None
    assert response.metadata["execution_backend"] == "pydantic_ai"
    assert response.metadata["authentication_mode"] == auth_mode
    assert managed_arguments["authentication"].mode == auth_mode
    assert managed_arguments["api_key"] == (
        "fixture-key" if auth_mode == "api_key" else None
    )
    assert handler.settlement == (
        100,
        20,
        0.00036 if standard_tier else 0.00022,
        raw_output,
    )
    assert response.metadata["requested_service_tier"] == tier
    assert response.metadata["observed_service_tier"] == tier
    initial_prompt = cast(str, managed_arguments["initial_prompt"])
    assert "Section 10(b)" in initial_prompt
    assert "/workspace/documents/case-1/motion.txt" in initial_prompt
    assert "should_score" not in initial_prompt
    assert "FULL DOCUMENT BODY" not in initial_prompt
