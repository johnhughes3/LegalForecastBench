from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import legalforecast.runner.managed_execution as managed_execution
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.runner.managed_execution import run_managed_tool_agent
from pydantic_ai import ModelHTTPError, ModelMessagesTypeAdapter
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RequestUsage


class _Executor:
    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        del workspace
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={
                "file_path": "/workspace/documents/motion.txt",
                "content": "Motion text",
            },
        )


def _entry(
    *, provider: str = "openai", model_id: str = "gpt-5.6-luna"
) -> ModelRegistryEntry:
    record: dict[str, Any] = {
        "provider": provider,
        "model_id": model_id,
        "display_name": model_id,
        "model_version_or_snapshot": model_id,
        "release_timestamp": "2026-06-26T00:00:00Z",
        "release_timestamp_source": "fixture",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-02-16",
        "temperature": 0,
        "top_p": 1,
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
    if provider == "openai":
        record["reasoning_effort"] = "high"
    else:
        record["thinking_level"] = "high"
    return ModelRegistryEntry.from_record(record)


def _response(parts: list[Any], *, inputs: int, outputs: int) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(input_tokens=inputs, output_tokens=outputs),
        model_name="gpt-5.6-luna",
        provider_name="openai",
        finish_reason="stop",
        provider_details={"service_tier": "flex"},
    )


def _run_kwargs(tmp_path: Path, *, cell_id: str = "cell-1") -> dict[str, Any]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return {
        "initial_prompt": "Case case-1; inspect /workspace/documents/motion.txt",
        "required_unit_ids": ("unit-a",),
        "executor": _Executor(),
        "workspace": workspace,
        "request_id": cell_id,
    }


def _read_transcript(path: Path) -> tuple[dict[str, Any], list[Any]]:
    record = json.loads(path.read_text(encoding="utf-8"))
    messages = ModelMessagesTypeAdapter.validate_json(
        json.dumps(record["messages"], separators=(",", ":"))
    )
    return record, messages


def test_function_model_transcript_round_trips_full_tool_conversation(
    tmp_path: Path,
) -> None:
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
                        "case_assessment": "The motion likely survives.",
                        "predictions": [
                            {
                                "unit_id": "unit-a",
                                "probability_fully_dismissed": 0.25,
                            }
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

    transcript_path = tmp_path / "transcripts" / "cell-1.json"
    result = run_managed_tool_agent(
        _entry(),
        **_run_kwargs(tmp_path),
        model=FunctionModel(scripted),
        api_key="do-not-persist-this-key",
        transcript_path=transcript_path,
    )

    record, messages = _read_transcript(transcript_path)
    assert set(record) == {"model", "cell", "agent_status", "messages"}
    assert record["model"] == "openai:gpt-5.6-luna"
    assert record["cell"] == "cell-1"
    assert record["agent_status"] == "succeeded"
    assert len(messages) == 5
    assert messages[0].instructions is not None
    assert (
        "Forecast the actual first written court disposition"
        in messages[0].instructions
    )
    assert any(
        isinstance(part, ToolCallPart) and part.tool_name == "read"
        for message in messages
        for part in getattr(message, "parts", ())
    )
    assert any(
        getattr(part, "tool_name", None) == "read"
        and "Motion text" in str(getattr(part, "content", ""))
        for message in messages
        for part in getattr(message, "parts", ())
    )
    assert any(
        getattr(part, "tool_name", None) == "final_result"
        for message in messages
        for part in getattr(message, "parts", ())
    )
    assert result.input_tokens == 250
    assert result.output_tokens == 30
    serialized = transcript_path.read_text(encoding="utf-8")
    assert "Forecast the actual first written court disposition" in serialized
    assert "do-not-persist-this-key" not in serialized
    assert "OPENAI_API_KEY" not in serialized


def test_test_model_toolcall_output_failure_saves_partial_history_without_api_key(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "transcripts" / "cell-2.json"
    model = TestModel(
        call_tools=["read"],
        custom_output_args={"case_assessment": "", "predictions": []},
        model_name="gemini-3.8-flash",
    )

    with pytest.raises(Exception, match="Exceeded maximum output retries"):
        run_managed_tool_agent(
            _entry(provider="google", model_id="gemini-3.8-flash"),
            **_run_kwargs(tmp_path, cell_id="cell-2"),
            model=model,
            transcript_path=transcript_path,
        )

    record, messages = _read_transcript(transcript_path)
    assert record["model"] == "google:gemini-3.8-flash"
    assert record["cell"] == "cell-2"
    assert record["agent_status"] == "failed"
    assert len(messages) >= 5
    assert any(
        getattr(part, "tool_name", None) == "read"
        for message in messages
        for part in getattr(message, "parts", ())
    )
    assert any(
        getattr(part, "part_kind", None) == "retry-prompt"
        for message in messages
        for part in getattr(message, "parts", ())
    )
    serialized = transcript_path.read_text(encoding="utf-8")
    assert "api_key" not in serialized.lower()


def test_managed_case_can_finish_after_twenty_five_document_reads(
    tmp_path: Path,
) -> None:
    calls = 0

    async def read_then_finish(_messages: list[Any], _info: Any) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls <= 25:
            parts = [
                ToolCallPart("read", {"file_path": "/workspace/documents/motion.txt"})
            ]
        else:
            parts = [
                ToolCallPart(
                    "final_result",
                    {
                        "case_assessment": "The record supports this forecast.",
                        "predictions": [
                            {"unit_id": "unit-a", "probability_fully_dismissed": 0.4}
                        ],
                    },
                )
            ]
        return _response(parts, inputs=100, outputs=10)

    result = run_managed_tool_agent(
        _entry(),
        **_run_kwargs(tmp_path),
        model=FunctionModel(read_then_finish),
    )
    assert result.request_count == 26
    assert len(result.called_tools) == 25
    assert json.loads(result.raw_output)["predictions"][0]["unit_id"] == "unit-a"


def test_request_limit_preserves_completed_tool_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(managed_execution, "MAX_AGENT_REQUESTS", 2)

    async def keep_reading(_messages: list[Any], _info: Any) -> ModelResponse:
        return _response(
            [ToolCallPart("read", {"file_path": "/workspace/documents/motion.txt"})],
            inputs=100,
            outputs=10,
        )

    path = tmp_path / "transcripts" / "limited.json"
    with pytest.raises(UsageLimitExceeded):
        run_managed_tool_agent(
            _entry(),
            **_run_kwargs(tmp_path),
            model=FunctionModel(keep_reading),
            transcript_path=path,
        )
    record, messages = _read_transcript(path)
    assert record["agent_status"] == "failed"
    calls = [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]
    assert len(calls) == 2
    assert "Motion text" in path.read_text()


def test_provider_failure_transcript_excludes_exception_body_and_headers(
    tmp_path: Path,
) -> None:
    async def failing(_messages: list[Any], _info: Any) -> ModelResponse:
        raise ModelHTTPError(
            503,
            "gpt-5.6-luna",
            {"secret": "provider-response-body"},
            headers={"authorization": "Bearer provider-header"},
        )

    transcript_path = tmp_path / "transcripts" / "cell-3.json"
    with pytest.raises(ModelHTTPError):
        run_managed_tool_agent(
            _entry(),
            **_run_kwargs(tmp_path),
            model=FunctionModel(failing),
            api_key="provider-api-key",
            transcript_path=transcript_path,
        )

    record, messages = _read_transcript(transcript_path)
    assert record["agent_status"] == "failed"
    assert messages
    serialized = transcript_path.read_text(encoding="utf-8")
    assert "provider-response-body" not in serialized
    assert "provider-header" not in serialized
    assert "provider-api-key" not in serialized
    assert "authorization" not in serialized.lower()
