# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.runner.ledger import (
    RunBlockedError,
    RunnerLedger,
)
from legalforecast.runner.managed_execution import run_managed_tool_agent
from legalforecast.runner.managed_transcript_recovery import (
    recover_managed_transcript,
)
from pydantic_ai import ModelResponse
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage


class _Executor:
    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        del workspace
        return ToolResponse(
            request_id=request.request_id,
            status="succeeded",
            output={
                "file_path": "/workspace/documents/0000.txt",
                "content": "motion text",
            },
        )


def _entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "google",
            "model_id": "gemini-3.8-flash",
            "display_name": "Gemini",
            "model_version_or_snapshot": "gemini-3.8-flash",
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
            "thinking_level": "high",
            "known_cutoff_publicity_caveats": [],
        }
    )


def _response(parts: list[Any], *, inputs: int, outputs: int) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(
            input_tokens=inputs,
            output_tokens=outputs,
            details={"thoughts_tokens": 2},
        ),
        model_name="gemini-3.8-flash",
        provider_name="google",
        finish_reason="stop",
        provider_details={"finish_reason": "STOP", "service_tier": "standard"},
    )


def _prompt() -> str:
    return json.dumps(
        {
            "case_id": "case-1",
            "documents": [
                {
                    "document_id": "doc-1",
                    "path": "/workspace/documents/0000.txt",
                    "role": "motion_to_dismiss_memorandum",
                }
            ],
            "prediction_units": [
                {
                    "claim_name": "Claim",
                    "count": "Count I",
                    "defendant_group": "Defendant",
                    "unit_id": "unit-a",
                }
            ],
            "task": "forecast_motion_to_dismiss",
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _request_digest(entry: ModelRegistryEntry, prompt: str) -> str:
    body = ARTIFACT_CANONICAL_JSON_V1.encode(
        {
            "model": entry.model_id,
            "case_id": "case-1",
            "required_unit_ids": ["unit-a"],
            "initial_prompt": prompt,
            "tools": ["bash", "read", "write", "edit", "glob", "grep"],
        }
    )
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(body, domain=PUBLIC_RUN_RECEIPT_V1).digest
    )


def _reserve_cell(ledger: RunnerLedger, entry: ModelRegistryEntry, prompt: str) -> None:
    ledger.reserve_cell(
        cell_id="cell-1",
        run_identity_sha256="run-sha",
        case_id="case-1",
        unit_id="case-call:case-1:unit-a",
        required_unit_ids=("unit-a",),
        repeat_index=1,
        provider_attempt_id="attempt-1",
    )
    ledger.record_request_body(
        "cell-1",
        provider_attempt_id="attempt-1",
        request_body_sha256=_request_digest(entry, prompt),
    )


def test_successful_transcript_restores_typed_replay_payload_without_transport(
    tmp_path: Path,
) -> None:
    entry = _entry()
    prompt = _prompt()
    turns = [
        _response(
            [
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/0000.txt"},
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
                        "case_assessment": "The claim likely survives.",
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

    transcript_path = tmp_path / "transcript.json"
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
    # FunctionModel labels its responses ``function``.  Normalize the
    # provider-owned fields in this synthetic transcript to exercise the same
    # Gemini projection as a recorded provider response.
    transcript = json.loads(transcript_path.read_text())
    for message in transcript["messages"]:
        if message.get("kind") == "response":
            message["model_name"] = entry.model_version_or_snapshot
            message["provider_name"] = entry.provider
            message["finish_reason"] = "stop"
            message["provider_details"] = {
                "finish_reason": "STOP",
                "service_tier": "standard",
            }
    transcript_path.write_text(json.dumps(transcript, sort_keys=True))
    with RunnerLedger(
        tmp_path / "ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        _reserve_cell(ledger, entry, prompt)
        ledger.mark_ambiguous(
            "cell-1", provider_attempt_id="attempt-1", failure_type="SettlementError"
        )
        recovered = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=transcript_path,
            cell_id="cell-1",
        )
        assert recovered.result.raw_output == live_result.raw_output
        assert recovered.result.request_count == live_result.request_count
        assert recovered.result.input_tokens == live_result.input_tokens
        assert recovered.result.output_tokens == live_result.output_tokens
        assert (
            recovered.response_sha256
            == hashlib.sha256(live_result.raw_output.encode("utf-8")).hexdigest()
        )
        record = ledger.read_cell_for_recovery("cell-1")
        assert record.status == "reserved"
        assert record.provider_attempt_status == "reserved"
        assert record.response_payload is not None
        payload = json.loads(record.response_payload)
        assert json.loads(cast_str(live_result.raw_output)) == json.loads(
            payload["raw_output"]
        )
        assert payload["input_tokens"] == 250
        assert payload["output_tokens"] == 30
        assert payload["thoughts_tokens"] == 4

        # A repeated operator invocation is idempotent and still provider-free.
        repeated = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=transcript_path,
            cell_id="cell-1",
        )
        assert repeated.payload_sha256 == recovered.payload_sha256


def test_ambiguous_settlement_failure_retains_response_for_normal_replay(
    tmp_path: Path,
) -> None:
    entry = _entry()
    prompt = _prompt()
    response_payload = ARTIFACT_CANONICAL_JSON_V1.encode(
        {
            "raw_output": (
                '{"case_assessment":"ok","predictions":[{"unit_id":"unit-a",'
                '"probability_fully_dismissed":0.5}]}'
            ),
            "request_count": 1,
            "input_tokens": 10,
            "output_tokens": 2,
            "served_model": entry.model_version_or_snapshot,
            "finish_reason": "stop",
            "service_tier": "standard",
            "called_tools": ["read"],
            "thoughts_tokens": 0,
            "estimated_cost_usd": 0.000022,
        }
    )
    response_sha256 = hashlib.sha256(response_payload).hexdigest()
    with RunnerLedger(
        tmp_path / "ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        _reserve_cell(ledger, entry, prompt)
        ledger.record_response_payload(
            "cell-1",
            provider_attempt_id="attempt-1",
            response_payload=response_payload,
            response_payload_sha256=response_sha256,
        )
        ledger.mark_ambiguous(
            "cell-1", provider_attempt_id="attempt-1", failure_type="SettlementError"
        )
        record = ledger.inspect_cell(
            cell_id="cell-1",
            run_identity_sha256="run-sha",
            case_id="case-1",
            unit_id="case-call:case-1:unit-a",
            required_unit_ids=("unit-a",),
            repeat_index=1,
        )
        assert record is not None
        assert record.status == "ambiguous"
        assert record.response_payload == response_payload
        with pytest.raises(RunBlockedError, match="different response"):
            ledger.restore_ambiguous_response_payload(
                "cell-1",
                provider_attempt_id="attempt-1",
                response_payload=b"different",
                response_payload_sha256=hashlib.sha256(b"different").hexdigest(),
            )
        receipt_payload = b"receipt"
        ledger.mark_completed(
            "cell-1",
            request_body_sha256=_request_digest(entry, prompt),
            receipt_sha256=hashlib.sha256(receipt_payload).hexdigest(),
            receipt_payload=receipt_payload,
        )
        completed = ledger.read_cell_for_recovery("cell-1")
        assert completed.status == "completed"


def cast_str(value: object) -> str:
    assert isinstance(value, str)
    return value
