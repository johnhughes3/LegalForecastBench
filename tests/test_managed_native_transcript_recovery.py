# pyright: reportPrivateUsage=false
"""Native text-output replay and document-read acceptance regressions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import legalforecast.runner.managed_transcript_recovery as transcript_recovery
import pytest
from legalforecast.runner.ledger import RunnerLedger
from legalforecast.runner.managed_execution import run_managed_tool_agent
from legalforecast.runner.managed_transcript_recovery import recover_managed_transcript
from pydantic_ai import ModelResponse
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from tests.test_managed_transcript_recovery import (
    _anthropic_entry,
    _anthropic_response,
    _Executor,
    _prompt,
    _reserve_cell,
)


@pytest.mark.parametrize("without_documents", [False, True])
def test_anthropic_native_text_output_transcript_recovers_without_final_tool(
    tmp_path: Path,
    without_documents: bool,
) -> None:
    entry = _anthropic_entry()
    prompt = _prompt()
    raw_output = (
        '{"case_assessment":"The claim likely survives.","predictions":['
        '{"unit_id":"unit-a","probability_fully_dismissed":0.25}]}'
    )
    turns = [
        _anthropic_response(
            [
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/0000.txt"},
                    tool_call_id="read-1",
                )
            ],
            inputs=100,
            outputs=40,
            cache_read=30,
            cache_write=10,
        ),
        _anthropic_response(
            [TextPart(raw_output)],
            inputs=150,
            outputs=60,
            cache_read=80,
            cache_write=20,
        ),
    ]

    async def scripted(_messages: list[Any], _info: Any) -> ModelResponse:
        return turns.pop(0)

    transcript_path = tmp_path / "anthropic-transcript.json"
    live_result = run_managed_tool_agent(
        entry,
        initial_prompt=prompt,
        required_unit_ids=("unit-a",),
        executor=_Executor(),
        workspace=tmp_path / "workspace",
        request_id="cell-1",
        model=FunctionModel(scripted),
        transcript_path=transcript_path,
    )
    transcript = json.loads(transcript_path.read_text())
    response_messages = [
        message
        for message in transcript["messages"]
        if message.get("kind") == "response"
    ]
    assert len(response_messages) == 2
    for message in response_messages:
        message["model_name"] = entry.model_version_or_snapshot
        message["provider_name"] = entry.provider
        message["finish_reason"] = "stop"
        message["provider_details"] = {}
    # Native output ends the conversation directly; it has no final-result
    # tool return request after the provider's text response.
    transcript["messages"] = [
        message for message in transcript["messages"] if message.get("parts")
    ]
    if without_documents:
        transcript["messages"] = [transcript["messages"][0], transcript["messages"][-1]]
    transcript_path.write_text(json.dumps(transcript, sort_keys=True))

    with RunnerLedger(
        tmp_path / "ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        _reserve_cell(ledger, entry, prompt)
        ledger.mark_ambiguous(
            "cell-1", provider_attempt_id="attempt-1", failure_type="SettlementError"
        )
        if without_documents:
            with pytest.raises(
                transcript_recovery.NonReplayableTranscript,
                match="no successful document tool",
            ):
                recover_managed_transcript(
                    ledger,
                    entry=entry,
                    transcript_path=transcript_path,
                    cell_id="cell-1",
                )
            assert ledger.read_cell_for_recovery("cell-1").response_payload is None
            return
        recovered = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=transcript_path,
            cell_id="cell-1",
        )

    assert recovered.result.called_tools == ("read",)
    assert recovered.result.input_tokens == live_result.input_tokens == 250
    assert recovered.result.output_tokens == live_result.output_tokens == 100
    assert (
        recovered.result.response_cache_usages
        == live_result.response_cache_usages
        == (
            (30, 10),
            (80, 20),
        )
    )
    assert recovered.estimated_cost_usd == pytest.approx(0.0065025)
    assert json.loads(recovered.result.raw_output) == json.loads(raw_output)

    with RunnerLedger(
        tmp_path / "ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        record = ledger.read_cell_for_recovery("cell-1")
        assert record.response_payload is not None
        payload = json.loads(record.response_payload)
        evidence = payload["anthropic_cache_evidence"]
        assert evidence["cache_read_tokens"] == 110
        assert evidence["cache_write_tokens"] == 30
        assert evidence["cache_pricing_ttl"] == "5m"
        assert evidence["cost_method"] == "anthropic_cache_aware_usage_reconstruction"
        assert payload["estimated_cost_usd"] == pytest.approx(0.0065025)
