from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.runner.managed_execution import (
    ManagedToolAgentDeps,
    run_managed_tool_agent,
)
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage


class _Executor:
    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        assert workspace.name == "workspace"
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={},
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


def test_provider_sees_target_case_instructions_and_output_schema(
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    async def capture(messages: list[Any], info: Any) -> ModelResponse:
        observed["messages"] = messages
        observed["instructions"] = info.instructions
        observed["output_tools"] = info.output_tools
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "Assessment",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.25,
                            },
                            {
                                "unit_id": "unit-b",
                                "probability_fully_dismissed": 0.75,
                            },
                        ],
                    },
                    tool_call_id="final-1",
                )
            ],
            usage=RequestUsage(input_tokens=1, output_tokens=1),
            model_name="gpt-5.6-luna",
            provider_name="openai",
            finish_reason="stop",
            provider_details={"service_tier": "flex"},
        )

    case_payload = (
        '{"case_id":"case-1","prediction_units":['
        '{"unit_id":"unit-a"},{"unit_id":"unit-b"}],'
        '"documents":[{"path":"/workspace/documents/0.txt"}]}'
    )
    run_managed_tool_agent(
        _entry(),
        initial_prompt=case_payload,
        required_unit_ids=("unit-a", "unit-b"),
        executor=_Executor(),
        workspace=tmp_path / "workspace",
        request_id="cell-1",
        model=FunctionModel(capture),
    )

    instructions = cast(str, observed["instructions"])
    assert "actual first written court disposition" in instructions
    assert "not what the court should decide" in instructions
    assert "partial dismissal" in instructions
    assert "Leave to amend does not change" in instructions
    assert "pre-decision evidence" in instructions
    assert "documents that are not included in the workspace" in instructions
    assert "later orders, amendments, appeals, settlements" in instructions
    for forbidden in ("label", "confidence", "rationale", "scoring"):
        assert forbidden not in instructions.lower()

    request = cast(Any, observed["messages"][0])
    assert request.instructions == instructions
    assert request.parts[0].content == case_payload
    assert "case-1" in request.parts[0].content
    assert "unit-a" in request.parts[0].content
    assert "/workspace/documents/0.txt" in request.parts[0].content

    output_tools = cast(list[Any], observed["output_tools"])
    assert [tool.name for tool in output_tools] == ["final_result"]
    schema = cast(dict[str, Any], output_tools[0].parameters_json_schema)
    assert {"case_assessment", "predictions"} <= set(schema["required"])
    prediction_schema = cast(dict[str, Any], schema["$defs"]["ForecastPrediction"])
    assert {"unit_id", "probability_fully_dismissed"} <= set(
        prediction_schema["required"]
    )
    probability_schema = cast(
        dict[str, Any], prediction_schema["properties"]["probability_fully_dismissed"]
    )
    assert probability_schema["minimum"] == 0.0
    assert probability_schema["maximum"] == 1.0


def test_managed_tool_result_is_serializable_by_pydantic_ai(tmp_path: Path) -> None:
    """Nested ToolProtocol output must cross the provider serializer boundary."""

    class NestedExecutor:
        def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
            return ToolResponse(
                request_id=request.request_id,
                status="succeeded",
                output={
                    "rows": [{"metadata": {"source": "fixture"}, "content": "Motion"}]
                },
            )

    deps = ManagedToolAgentDeps(
        executor=NestedExecutor(),
        workspace=tmp_path / "workspace",
        request_id="cell-serialization",
    )
    result = deps.invoke("read", {})

    # This is the same PydanticAI serializer used when rendering a tool return
    # into the next OpenAI request. It raises on a nested MappingProxyType.
    serialized = ToolReturnPart(tool_name="read", content=result).model_response_str()

    assert (
        serialized == '{"rows":[{"metadata":{"source":"fixture"},"content":"Motion"}]}'
    )
