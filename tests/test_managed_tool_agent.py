from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.runner.managed_execution as managed_execution
import pytest
from legalforecast.evals.live_model_solver import LiveModelProviderError
from legalforecast.evals.model_registry import LongContextSurcharge, ModelRegistryEntry
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.runner.managed_execution import (
    ManagedCaseInput,
    ManagedToolAgentResult,
    run_managed_tool_agent,
)
from pydantic_ai import ModelHTTPError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage


class _Executor:
    def __init__(self) -> None:
        self.requests: list[ToolRequest] = []

    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        assert workspace.name == "workspace"
        self.requests.append(request)
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={
                "file_path": "/workspace/documents/motion.txt",
                "content": "Motion",
            },
        )


def _response(parts: list[Any], *, inputs: int, outputs: int) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(input_tokens=inputs, output_tokens=outputs),
        model_name="gpt-5.6-luna",
        provider_name="openai",
        finish_reason="stop",
        provider_details={"service_tier": "flex"},
    )


def _entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "openai",
            "model_id": "gpt-5.6-luna",
            "display_name": "GPT-5.6 Luna",
            "model_version_or_snapshot": "gpt-5.6-luna",
            "release_timestamp": "2026-06-26T00:00:00Z",
            "release_timestamp_source": "fixture",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-02-16",
            "temperature": 0,
            "top_p": 1,
            "reasoning_effort": "high",
            "max_output_tokens": 16000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1050000,
            "pricing_source": "fixture",
            "input_token_price": 1.0,
            "output_token_price": 6.0,
            "known_cutoff_publicity_caveats": [],
        }
    )


def _google_entry() -> ModelRegistryEntry:
    record = _entry().to_record()
    record.update(
        {
            "provider": "google",
            "model_id": "gemini-3.8-flash",
            "model_version_or_snapshot": "gemini-3.8-flash",
            "reasoning_effort": None,
            "thinking_level": "high",
            "max_output_tokens": 65536,
            "input_token_price": 0.75,
            "output_token_price": 3.75,
        }
    )
    return ModelRegistryEntry.from_record(record)


def _gateway_entry(model_id: str = "moonshotai/kimi-k3") -> ModelRegistryEntry:
    record = _entry().to_record()
    record.update(
        {
            "provider": "vercel_ai_gateway",
            "model_id": model_id,
            "model_version_or_snapshot": model_id,
            "release_timestamp": "2026-07-17T00:00:00Z",
            "release_timestamp_source": "fixture",
            "provider_training_cutoff_status": "unknown",
            "provider_training_cutoff": None,
            "input_token_price": 2.85,
            "output_token_price": 14.25,
        }
    )
    return ModelRegistryEntry.from_record(record)


def _gateway_response_metadata() -> dict[str, str]:
    return {
        "original_model_id": "moonshotai/kimi-k3",
        "resolved_provider": "deepinfra",
        "resolved_provider_api_model_id": "moonshotai/Kimi-K3",
        "canonical_slug": "moonshotai/kimi-k3",
        "final_provider": "deepinfra",
        "generation_id": "generation-fixture",
        "cost_usd": "0.001",
        "market_cost_usd": "0.002",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }


def test_gateway_response_metadata_is_extracted_from_openai_compatible_envelope() -> (
    None
):
    metadata = _gateway_response_metadata()
    response = SimpleNamespace(
        model_extra={
            "providerMetadata": {
                "gateway": {
                    "routing": {
                        "originalModelId": metadata["original_model_id"],
                        "resolvedProvider": metadata["resolved_provider"],
                        "resolvedProviderApiModelId": metadata[
                            "resolved_provider_api_model_id"
                        ],
                        "canonicalSlug": metadata["canonical_slug"],
                        "finalProvider": metadata["final_provider"],
                        "modelAttemptCount": 1,
                        "totalProviderAttemptCount": 1,
                    },
                    "generationId": metadata["generation_id"],
                    "cost": 0.001,
                    "marketCost": 0.002,
                }
            }
        }
    )
    assert managed_execution.gateway_response_metadata(cast(Any, response)) == metadata


def test_gateway_metadata_accepts_omitted_api_model_id_and_prefers_gateway_cost() -> (
    None
):
    fixture = json.loads(
        (
            Path("tests/fixtures/vercel_ai_gateway")
            / "muse-spark-1.3-contributor-metadata.json"
        ).read_text(encoding="utf-8")
    )
    response = SimpleNamespace(
        model_extra={"provider_metadata": fixture["provider_metadata"]}
    )
    metadata = managed_execution.gateway_response_metadata(cast(Any, response))
    assert metadata == {
        "original_model_id": "meta/muse-spark-1.3-contributor",
        "resolved_provider": "meta",
        "canonical_slug": "meta/muse-spark-1.3-contributor",
        "final_provider": "meta",
        "generation_id": "redacted-generation-id",
        "cost_usd": "0.0001657",
        "market_cost_usd": "6.57e-05",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }


@pytest.mark.parametrize("model_id", ["gpt-5.6-luna", "gpt-6-astra"])
def test_managed_agent_uses_native_tool_loop_and_returns_one_case_envelope(
    tmp_path: Path,
    model_id: str,
) -> None:
    entry = replace(_entry(), model_id=model_id, model_version_or_snapshot=model_id)
    assert managed_execution.uses_managed_document_tools(entry)
    turns = [
        _response(
            [
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/motion.txt"},
                    tool_call_id="read-1",
                )
            ],
            inputs=100,
            outputs=10,
        ),
        _response(
            [
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "The pleading likely survives in part.",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.35,
                            },
                            {
                                "unit_id": "unit-b",
                                "probability_fully_dismissed": 0.6,
                            },
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            inputs=150,
            outputs=20,
        ),
    ]

    async def scripted(_messages: list[Any], _info: Any) -> ModelResponse:
        return turns.pop(0)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = _Executor()
    result = run_managed_tool_agent(
        entry,
        initial_prompt=("Case: case-1\nDocuments:\n- /workspace/documents/motion.txt"),
        required_unit_ids=("unit-a", "unit-b"),
        executor=executor,
        workspace=workspace,
        request_id="cell-1",
        model=FunctionModel(scripted),
    )

    assert result.called_tools == ("read",)
    assert result.request_count == 2
    assert result.input_tokens == 250
    assert result.output_tokens == 30
    assert result.response_usages == ((100, 10), (150, 20))
    assert result.served_model == "function:scripted:"
    assert result.service_tier == "flex"
    assert [request.operation for request in executor.requests] == ["read"]
    assert '"unit_id":"unit-a"' in result.raw_output
    assert '"unit_id":"unit-b"' in result.raw_output


def test_gateway_managed_agent_roundtrips_tools_usage_and_route_metadata(
    tmp_path: Path,
) -> None:
    turns = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/motion.txt"},
                    tool_call_id="read-1",
                )
            ],
            usage=RequestUsage(input_tokens=100, output_tokens=10),
            model_name="moonshotai/kimi-k3",
            provider_name="vercel_ai_gateway",
            finish_reason="stop",
            provider_details={"gateway_metadata": _gateway_response_metadata()},
        ),
        ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "Assessment",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.5,
                            }
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            usage=RequestUsage(input_tokens=150, output_tokens=20),
            model_name="moonshotai/kimi-k3",
            provider_name="vercel_ai_gateway",
            finish_reason="stop",
            provider_details={"gateway_metadata": _gateway_response_metadata()},
        ),
    ]

    async def scripted(_messages: list[Any], _info: Any) -> ModelResponse:
        return turns.pop(0)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = run_managed_tool_agent(
        _gateway_entry(),
        initial_prompt="Case: case-1\nDocuments: /workspace/documents/motion.txt",
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=workspace,
        request_id="cell-1",
        model=FunctionModel(scripted),
    )

    assert result.called_tools == ("read",)
    assert result.request_count == 2
    assert result.response_usages == ((100, 10), (150, 20))
    assert result.gateway_response_metadata == (
        _gateway_response_metadata(),
        _gateway_response_metadata(),
    )


def test_gateway_provider_uses_gateway_endpoint_and_hard_route_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def scripted(_messages: list[Any], _info: Any) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "Assessment",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.5,
                            }
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            usage=RequestUsage(input_tokens=1, output_tokens=1),
            model_name="moonshotai/kimi-k3",
            provider_name="vercel_ai_gateway",
            finish_reason="stop",
            provider_details={"gateway_metadata": _gateway_response_metadata()},
        )

    def observed_model(model_id: str, **kwargs: Any) -> FunctionModel:
        captured.update(model_id=model_id, **kwargs)
        return FunctionModel(scripted)

    monkeypatch.setattr(
        managed_execution, "_ObservedTierOpenAIResponsesModel", observed_model
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_managed_tool_agent(
        _gateway_entry(),
        initial_prompt="Case: case-1",
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=workspace,
        request_id="cell-1",
        api_key="gateway-fixture-key",
    )

    assert captured["model_id"] == "moonshotai/kimi-k3"
    provider = captured["provider"]
    assert provider.base_url.rstrip("/") == managed_execution.VERCEL_AI_GATEWAY_BASE_URL
    assert captured["profile"]["openai_supports_reasoning"] is True
    assert managed_execution.gateway_route_provider("meta/muse-spark-1.3") == "meta"
    assert (
        managed_execution.gateway_route_provider("meta/muse-spark-1.3-contributor")
        == "meta"
    )
    assert managed_execution.gateway_request_extra_body("moonshotai/kimi-k3") == {
        "providerOptions": {"gateway": {"only": ["deepinfra"]}}
    }
    with pytest.raises(ValueError, match="not allowlisted"):
        managed_execution.gateway_route_provider("unknown/model")


def test_managed_agent_exposes_exactly_the_six_harvey_tools(tmp_path: Path) -> None:
    seen: list[str] = []

    async def capture(_messages: list[Any], info: Any) -> ModelResponse:
        seen.extend(sorted(tool.name for tool in info.function_tools))
        return _response(
            [
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "Assessment",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.5,
                            }
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            inputs=1,
            outputs=1,
        )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_managed_tool_agent(
        _entry(),
        initial_prompt="Case: case-1\nDocuments: /workspace/documents/motion.txt",
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=workspace,
        request_id="cell-1",
        model=FunctionModel(capture),
    )

    assert seen == ["bash", "edit", "glob", "grep", "read", "write"]


def test_google_managed_agent_uses_native_tools_and_bills_thoughts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini uses the same six tools while retaining provider reasoning usage."""

    seen: list[str] = []
    turns = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/motion.txt"},
                    tool_call_id="read-1",
                )
            ],
            usage=RequestUsage(
                input_tokens=100,
                output_tokens=40,
                details={"thoughts_tokens": 30},
            ),
            model_name="gemini-3.8-flash",
            provider_name="google",
            finish_reason="stop",
        ),
        ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "Assessment",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.5,
                            }
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            usage=RequestUsage(
                input_tokens=150,
                output_tokens=60,
                details={"thoughts_tokens": 40},
            ),
            model_name="gemini-3.8-flash",
            provider_name="google",
            finish_reason="stop",
        ),
    ]

    async def scripted(_messages: list[Any], info: Any) -> ModelResponse:
        seen.extend(sorted(tool.name for tool in info.function_tools))
        return turns.pop(0)

    captured: dict[str, Any] = {}

    def google_model(model_id: str, *, provider: Any) -> FunctionModel:
        captured.update(model_id=model_id, provider=provider)
        return FunctionModel(scripted)

    monkeypatch.setattr(managed_execution, "GoogleModel", google_model)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = run_managed_tool_agent(
        _google_entry(),
        initial_prompt="Case: case-1\nDocuments: /workspace/documents/motion.txt",
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=workspace,
        request_id="cell-1",
        api_key="fixture-key",
    )

    assert captured["model_id"] == "gemini-3.8-flash"
    assert captured["provider"].__class__.__name__ == "GoogleProvider"
    assert managed_execution.uses_managed_document_tools(_google_entry())
    assert result.served_model == "function:scripted:"
    assert result.service_tier == "unreported"
    assert result.input_tokens == 250
    assert result.output_tokens == 100
    assert result.thoughts_tokens == 70
    assert result.response_usages == ((100, 40), (150, 60))
    assert seen == ["bash", "edit", "glob", "grep", "read", "write"] * 2


def test_google_sdk_usage_counts_thoughts_once_in_output_tokens() -> None:
    """Pydantic AI's Google usage extractor includes thought tokens in output."""

    usage = RequestUsage.extract(
        {
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 30,
                "totalTokenCount": 150,
            }
        },
        provider="google",
        provider_url="https://generativelanguage.googleapis.com",
        provider_fallback="google",
        details={"thoughts_tokens": 30},
    )

    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.details["thoughts_tokens"] == 30


class _AttemptHandler:
    def __init__(self) -> None:
        self.settlement: tuple[int, int, float, str] | None = None
        self.run_count = 0
        self.replayable_response: dict[str, object] | None = None

    def run_attempt(self, _ordinal: int, call: Any) -> Any:
        self.run_count += 1
        return call()

    def durable_attempt_ordinal(self, _ordinal: int) -> int:
        return 7

    def settle_attempt(
        self,
        _ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        self.settlement = (
            input_tokens,
            output_tokens,
            actual_cost_usd,
            raw_output,
        )

    def record_post_response_failure(self, _ordinal: int, *, failure_type: str) -> None:
        pytest.fail(f"unexpected post-response failure: {failure_type}")


class _ReplayHandler(_AttemptHandler):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__()
        self.payload = payload
        self.replayable_response = payload

    def run_attempt(self, _ordinal: int, call: Any) -> dict[str, object]:
        self.run_count += 1
        del call
        return self.payload


def test_official_cell_settles_the_entire_agent_session_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from contextlib import contextmanager

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
            served_model="gpt-5.6-luna",
            finish_reason="stop",
            service_tier="flex",
            called_tools=("read",),
            response_usages=((40, 5), (30, 5), (30, 10)),
        )

    monkeypatch.setattr(managed_execution, "run_managed_tool_agent", managed_agent)
    observed: list[bytes] = []
    handler = _AttemptHandler()

    response = managed_execution.complete_managed_tool_cell(
        _entry(),
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
            "LFB_HARVEY_TOOL_IMAGE": "sha256:" + "a" * 64,
        },
        registry_sha256="sha256:" + "b" * 64,
    )

    assert len(observed) == 1
    assert response.raw_output == raw_output
    assert response.request_count == 3
    assert response.metadata is not None
    assert response.metadata["execution_backend"] == "pydantic_ai"
    assert handler.settlement == (100, 20, 0.00022, raw_output)
    initial_prompt = cast(str, managed_arguments["initial_prompt"])
    assert "Section 10(b)" in initial_prompt
    assert "/workspace/documents/case-1/motion.txt" in initial_prompt
    assert "should_score" not in initial_prompt
    assert "FULL DOCUMENT BODY" not in initial_prompt


def test_google_managed_cell_uses_gemini_key_and_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Generator
    from contextlib import contextmanager

    executor = _Executor()

    @contextmanager
    def session(**_kwargs: Any) -> Generator[_Executor]:
        yield executor

    monkeypatch.setattr(
        "legalforecast.runner.tool_runtime.open_official_tool_session", session
    )
    raw_output = (
        '{"case_assessment":"Assessment","predictions":['
        '{"unit_id":"unit-a","probability_fully_dismissed":0.5}]}'
    )

    def managed_agent(*_args: Any, **kwargs: Any) -> ManagedToolAgentResult:
        assert kwargs["api_key"] == "fixture-key"
        return ManagedToolAgentResult(
            raw_output=raw_output,
            request_count=2,
            input_tokens=100,
            output_tokens=20,
            served_model="gemini-3.8-flash",
            finish_reason="stop",
            service_tier="unreported",
            called_tools=("read",),
            response_usages=((60, 10), (40, 10)),
            thoughts_tokens=10,
        )

    monkeypatch.setattr(managed_execution, "run_managed_tool_agent", managed_agent)
    handler = _AttemptHandler()

    response = managed_execution.complete_managed_tool_cell(
        _google_entry(),
        handler=cast(Any, handler),
        managed_case=ManagedCaseInput(
            case_id="case-1",
            required_unit_ids=("unit-a",),
            documents={"documents/0000.txt": b"motion"},
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
                    "path": "/workspace/documents/0000.txt",
                    "document_id": "motion",
                    "role": "motion_to_dismiss",
                },
            ),
            cell_id="cell-1",
        ),
        request_body_observer=lambda _body: None,
        environ={
            "GEMINI_API_KEY": "fixture-key",
            "LFB_HARVEY_TOOL_IMAGE": "sha256:" + "a" * 64,
        },
        registry_sha256="sha256:" + "b" * 64,
    )

    assert response.raw_output == raw_output
    assert response.input_tokens == 100
    assert response.output_tokens == 20
    assert response.metadata is not None
    assert response.metadata["provider"] == "google"
    assert response.metadata["served_model_version"] == "gemini-3.8-flash"
    assert response.metadata["service_tier"] == "unreported"
    assert response.metadata["thoughts_tokens"] == "10"
    assert "requested_service_tier" not in response.metadata
    assert handler.settlement == (100, 20, 0.00015, raw_output)


def test_gateway_managed_cell_requires_only_the_scoped_gateway_key() -> None:
    with pytest.raises(
        managed_execution.RunValidationError, match="AI_GATEWAY_API_KEY is required"
    ):
        managed_execution.complete_managed_tool_cell(
            _gateway_entry(),
            handler=cast(Any, _AttemptHandler()),
            managed_case=ManagedCaseInput(
                case_id="case-1",
                required_unit_ids=("unit-a",),
                documents={},
                unit_descriptions=(),
                document_descriptions=(),
                cell_id="cell-1",
            ),
            request_body_observer=lambda _body: None,
            environ={"OPENAI_API_KEY": "must-not-be-used"},
            registry_sha256="sha256:" + "b" * 64,
        )


def test_official_cell_replays_aggregate_response_without_starting_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_output = (
        '{"case_assessment":"Assessment","predictions":['
        '{"unit_id":"unit-a","probability_fully_dismissed":0.5}]}'
    )
    handler = _ReplayHandler(
        {
            "raw_output": raw_output,
            "request_count": 2,
            "input_tokens": 80,
            "output_tokens": 10,
            "served_model": "gpt-5.6-luna",
            "finish_reason": "stop",
            "service_tier": "flex",
            "called_tools": ["read"],
            "estimated_cost_usd": 0.00014,
        }
    )
    monkeypatch.setattr(
        "legalforecast.runner.tool_runtime.open_official_tool_session",
        lambda **_kwargs: pytest.fail("replay must not start a tool container"),
    )
    observed: list[bytes] = []

    response = managed_execution.complete_managed_tool_cell(
        _entry(),
        handler=cast(Any, handler),
        managed_case=ManagedCaseInput(
            case_id="case-1",
            required_unit_ids=("unit-a",),
            documents={"documents/0000.txt": b"motion"},
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
                    "path": "/workspace/documents/0000.txt",
                    "document_id": "motion",
                    "role": "motion_to_dismiss",
                },
            ),
            cell_id="cell-1",
        ),
        request_body_observer=observed.append,
        environ={"OPENAI_API_KEY": "fixture-key"},
        registry_sha256="sha256:" + "b" * 64,
    )

    assert observed == []
    assert response.raw_output == raw_output
    assert handler.settlement == (80, 10, 0.00014, raw_output)
    assert handler.run_count == 1


class _FailureHandler(_AttemptHandler):
    def __init__(self) -> None:
        super().__init__()
        self.ambiguous: bool | None = None

    def run_attempt(self, _ordinal: int, call: Any) -> Any:
        self.run_count += 1
        try:
            return call()
        except BaseException as exc:
            retryable_nonbillable = (
                getattr(exc, "status_code", None) == 429
                and getattr(exc, "retryable", None) is True
            )
            self.ambiguous = not retryable_nonbillable
            raise


def test_late_managed_429_keeps_the_case_reservation_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from contextlib import contextmanager

    @contextmanager
    def session(**_kwargs: Any) -> Generator[_Executor]:
        yield _Executor()

    monkeypatch.setattr(
        "legalforecast.runner.tool_runtime.open_official_tool_session", session
    )
    monkeypatch.setattr(
        managed_execution,
        "run_managed_tool_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ModelHTTPError(429, "gpt-5.6-luna", {"error": "rate limited"})
        ),
    )
    handler = _FailureHandler()

    with pytest.raises(LiveModelProviderError) as exc_info:
        managed_execution.complete_managed_tool_cell(
            _entry(),
            handler=cast(Any, handler),
            managed_case=ManagedCaseInput(
                case_id="case-1",
                required_unit_ids=("unit-a",),
                documents={"documents/0000.txt": b"motion"},
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
                        "path": "/workspace/documents/0000.txt",
                        "document_id": "motion",
                        "role": "motion_to_dismiss",
                    },
                ),
                cell_id="cell-1",
            ),
            request_body_observer=lambda _body: None,
            environ={"OPENAI_API_KEY": "fixture-key"},
            registry_sha256="sha256:" + "b" * 64,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.retryable is False
    assert handler.run_count == 1
    assert handler.ambiguous is True
    assert handler.settlement is None


def test_managed_cost_applies_long_context_surcharge_per_provider_request() -> None:
    entry = replace(
        _entry(),
        long_context_surcharge=LongContextSurcharge(
            threshold_input_tokens=100,
            input_price_multiplier=2.0,
            output_price_multiplier=2.0,
        ),
    )

    below_threshold_turns = managed_execution._managed_estimated_cost(
        entry,
        response_usages=((60, 10), (60, 10)),
    )
    one_surcharged_turn = managed_execution._managed_estimated_cost(
        entry,
        response_usages=((101, 10), (19, 10)),
    )

    assert below_threshold_turns == pytest.approx(0.00024)
    assert one_surcharged_turn == pytest.approx(0.000401)
