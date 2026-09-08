from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import legalforecast.runner.managed_execution as managed_execution
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.runner.managed_execution import run_managed_tool_agent
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RequestUsage


def _metadata() -> dict[str, str]:
    return {
        "original_model_id": "meta/muse-spark-1.3-contributor",
        "resolved_provider": "meta",
        "canonical_slug": "meta/muse-spark-1.3-contributor",
        "final_provider": "meta",
        "generation_id": "generation-fixture",
        "cost_usd": "0.001",
        "market_cost_usd": "0.001",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }


def _entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "vercel_ai_gateway",
            "model_id": "meta/muse-spark-1.3-contributor",
            "display_name": "Muse Spark 1.3 Contributor",
            "model_version_or_snapshot": "meta/muse-spark-1.3-contributor",
            "release_timestamp": "2026-07-17T00:00:00Z",
            "release_timestamp_source": "fixture",
            "provider_training_cutoff_status": "unknown",
            "provider_training_cutoff": None,
            "temperature": 0,
            "top_p": 1,
            "reasoning_effort": None,
            "thinking_level": None,
            "max_output_tokens": 16000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1050000,
            "pricing_source": "fixture",
            "input_token_price": 2.85,
            "output_token_price": 14.25,
            "known_cutoff_publicity_caveats": [],
        }
    )


class _Executor:
    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        assert workspace.name == "workspace"
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={"file_path": request.arguments["file_path"], "content": "Motion"},
        )


class _ResponsesRecorder:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = responses

    async def create(self, **kwargs: Any) -> ModelResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _OpenAIClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = _ResponsesRecorder(responses)


def _response(parts: list[Any], *, inputs: int, outputs: int) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(input_tokens=inputs, output_tokens=outputs),
        model_name="meta/muse-spark-1.3-contributor",
        provider_name="openai",
        finish_reason="stop",
        provider_details={"gateway_metadata": _metadata()},
    )


def _final_result(probability: float, call_id: str) -> ToolCallPart:
    return ToolCallPart(
        "final_result",
        {
            "case_assessment": "Assessment",
            "predictions": [
                {
                    "unit_id": "unit-a",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        tool_call_id=call_id,
    )


def test_muse_profile_only_disables_forced_tool_choice() -> None:
    provider = OpenAIProvider(openai_client=cast(Any, _OpenAIClient([])))

    muse_profile = managed_execution.gateway_model_profile(
        provider, "meta/muse-spark-1.3-contributor"
    )
    kimi_profile = managed_execution.gateway_model_profile(
        provider, "moonshotai/kimi-k3"
    )

    assert muse_profile.get("openai_supports_tool_choice_required") is False
    assert kimi_profile.get("openai_supports_tool_choice_required", True) is True


def test_muse_openai_responses_serialization_keeps_tools_and_retries_output(
    tmp_path: Path,
) -> None:
    responses = [
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
        _response([_final_result(2.0, "final-invalid")], inputs=150, outputs=20),
        _response([_final_result(0.5, "final-valid")], inputs=175, outputs=25),
    ]
    client = _OpenAIClient(responses)
    provider = OpenAIProvider(openai_client=cast(Any, client))
    model = managed_execution._ObservedTierOpenAIResponsesModel(
        "meta/muse-spark-1.3-contributor",
        provider=provider,
        profile=managed_execution.gateway_model_profile(
            provider, "meta/muse-spark-1.3-contributor"
        ),
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = run_managed_tool_agent(
        _entry(),
        initial_prompt="Case: case-1\nDocuments: /workspace/documents/motion.txt",
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=workspace,
        request_id="cell-1",
        model=model,
    )

    expected_tools = {"bash", "edit", "glob", "grep", "read", "write"}
    assert len(client.responses.calls) == 3
    assert result.request_count == 3
    assert result.called_tools == ("read",)
    assert result.response_usages == ((100, 10), (150, 20), (175, 25))
    assert '"probability_fully_dismissed":0.5' in result.raw_output
    for call in client.responses.calls:
        assert call["tool_choice"] == "auto"
        serialized_tools = call["tools"]
        assert isinstance(serialized_tools, list)
        tool_names = {tool["name"] for tool in serialized_tools}
        assert expected_tools <= tool_names
        assert "final_result" in tool_names
        assert call["extra_body"] == {
            "providerOptions": {"gateway": {"only": ["meta"]}}
        }
