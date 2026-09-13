# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import legalforecast.runner.managed_execution as managed_execution
import legalforecast.runner.managed_transcript_recovery as transcript_recovery
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
    RunValidationError,
)
from legalforecast.runner.managed_execution import run_managed_tool_agent
from legalforecast.runner.managed_transcript_recovery import (
    recover_managed_transcript,
)
from pydantic_ai import ModelResponse
from pydantic_ai.messages import TextPart, ToolCallPart
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


def _anthropic_entry() -> ModelRegistryEntry:
    record = _entry().to_record()
    record.update(
        {
            "provider": "anthropic",
            "model_id": "claude-fable-5-1",
            "model_version_or_snapshot": "claude-fable-5-1",
            "thinking_level": None,
            "input_token_price": 10.0,
            "output_token_price": 50.0,
        }
    )
    return ModelRegistryEntry.from_record(record)


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


def _anthropic_response(
    parts: list[Any],
    *,
    inputs: int,
    outputs: int,
    cache_read: int = 0,
    cache_write: int = 0,
) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(
            input_tokens=inputs,
            output_tokens=outputs,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        ),
        model_name="claude-fable-5-1",
        provider_name="anthropic",
        finish_reason="stop",
    )


def _gateway_entry(
    model_id: str = "meta/muse-spark-1.3-contributor",
) -> ModelRegistryEntry:
    record = _entry().to_record()
    record.update(
        {
            "provider": "vercel_ai_gateway",
            "model_id": model_id,
            "model_version_or_snapshot": model_id,
            "reasoning_effort": "high",
            "thinking_level": None,
            "max_output_tokens": 128000,
            "input_token_price": 0.1,
            "output_token_price": 0.2,
            "provider_training_cutoff_status": "unknown",
            "provider_training_cutoff": None,
        }
    )
    return ModelRegistryEntry.from_record(record)


def _gateway_metadata() -> dict[str, str]:
    return {
        "original_model_id": "meta/muse-spark-1.3-contributor",
        "resolved_provider": "meta",
        "canonical_slug": "meta/muse-spark-1.3-contributor",
        "final_provider": "meta",
        "generation_id": "redacted-generation-id",
        "cost_usd": "0.0001657",
        "market_cost_usd": "0.0000657",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }


def _grok_gateway_entry() -> ModelRegistryEntry:
    record = _gateway_entry("spacexai/grok-4.6").to_record()
    record.update({"reasoning_effort": "high", "thinking_level": None})
    return ModelRegistryEntry.from_record(record)


def _grok_gateway_metadata() -> dict[str, str]:
    return {
        "original_model_id": "spacexai/grok-4.6",
        "resolved_provider": "xai",
        "canonical_slug": "xai/grok-4.6",
        "final_provider": "xai",
        "generation_id": "redacted-grok-generation-id",
        "cost_usd": "0.001",
        "market_cost_usd": "0.001",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }


def _gateway_response(
    parts: list[Any],
    *,
    inputs: int,
    outputs: int,
    model_name: str = "meta/muse-spark-1.3-contributor",
    metadata: dict[str, str] | None = None,
) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(
            input_tokens=inputs,
            output_tokens=outputs,
            details={"thoughts_tokens": 2},
        ),
        model_name=model_name,
        # The native Gateway transport uses PydanticAI's OpenAI adapter.
        provider_name="openai",
        finish_reason="stop",
        provider_details={
            "finish_reason": "STOP",
            "service_tier": "standard",
            "gateway_metadata": metadata or _gateway_metadata(),
        },
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
        assert payload["gateway_response_metadata"] == []

        # A repeated operator invocation is idempotent and still provider-free.
        repeated = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=transcript_path,
            cell_id="cell-1",
        )
        assert repeated.payload_sha256 == recovered.payload_sha256

    # Responses persisted before Gateway metadata was introduced omit the
    # optional field. Recovery must reproduce the existing bytes and digest
    # while allowing the current empty metadata projection to compare equal.
    legacy_payload = dict(payload)
    legacy_payload.pop("gateway_response_metadata")
    legacy_payload_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(legacy_payload)
    legacy_payload_sha256 = hashlib.sha256(legacy_payload_bytes).hexdigest()
    with RunnerLedger(
        tmp_path / "legacy-ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        _reserve_cell(ledger, entry, prompt)
        ledger.record_response_payload(
            "cell-1",
            provider_attempt_id="attempt-1",
            response_payload=legacy_payload_bytes,
            response_payload_sha256=legacy_payload_sha256,
        )
        recovered = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=transcript_path,
            cell_id="cell-1",
        )
        assert recovered.payload_sha256 == legacy_payload_sha256
        record = ledger.read_cell_for_recovery("cell-1")
        assert record.response_payload == legacy_payload_bytes
        assert record.response_payload_sha256 == legacy_payload_sha256

    changed_content = dict(legacy_payload)
    changed_content["raw_output"] = str(changed_content["raw_output"]).replace(
        "0.25", "0.26"
    )
    changed_cost = dict(legacy_payload)
    changed_cost["estimated_cost_usd"] = 999.0
    nonempty_metadata = dict(legacy_payload)
    nonempty_metadata["gateway_response_metadata"] = [{"unexpected": "metadata"}]
    for label, changed_payload in (
        ("content", changed_content),
        ("cost", changed_cost),
        ("metadata", nonempty_metadata),
    ):
        changed_payload_bytes = ARTIFACT_CANONICAL_JSON_V1.encode(changed_payload)
        changed_payload_sha256 = hashlib.sha256(changed_payload_bytes).hexdigest()
        with RunnerLedger(
            tmp_path / f"mismatch-{label}.sqlite3", state_only_provider_attempts=True
        ) as ledger:
            _reserve_cell(ledger, entry, prompt)
            ledger.record_response_payload(
                "cell-1",
                provider_attempt_id="attempt-1",
                response_payload=changed_payload_bytes,
                response_payload_sha256=changed_payload_sha256,
            )
            with pytest.raises(
                RunValidationError,
                match="existing durable response differs from transcript recovery",
            ):
                recover_managed_transcript(
                    ledger,
                    entry=entry,
                    transcript_path=transcript_path,
                    cell_id="cell-1",
                )


@pytest.mark.parametrize(
    ("entry", "model_name", "metadata", "agent_status", "expected_cost"),
    [
        pytest.param(
            _gateway_entry(),
            "meta/muse-spark-1.3-contributor",
            _gateway_metadata(),
            "succeeded",
            0.0003314,
            id="muse",
        ),
        pytest.param(
            _gateway_entry("openai/gpt-5.6-sol"),
            "openai/gpt-5.6-sol",
            {
                **_gateway_metadata(),
                "original_model_id": "openai/gpt-5.6-sol",
                "canonical_slug": "openai/gpt-5.6-sol",
                "resolved_provider": "openai",
                "final_provider": "openai",
                "resolved_provider_api_model_id": "gpt-5.6-sol",
            },
            "succeeded",
            0.0003314,
            id="sol-standard-served-after-flex-request",
        ),
        pytest.param(
            _grok_gateway_entry(),
            "xai/grok-4.6",
            _grok_gateway_metadata(),
            "failed",
            0.002,
            id="grok-post-response-validation-failure",
        ),
    ],
)
def test_gateway_transcript_recovery_preserves_route_metadata_and_charged_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: ModelRegistryEntry,
    model_name: str,
    metadata: dict[str, str],
    agent_status: str,
    expected_cost: float,
) -> None:
    prompt = _prompt()
    turns = [
        _gateway_response(
            [
                ToolCallPart(
                    "read",
                    {"file_path": "/workspace/documents/0000.txt"},
                    tool_call_id="read-1",
                )
            ],
            inputs=100,
            outputs=10,
            model_name=model_name,
            metadata=metadata,
        ),
        _gateway_response(
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
            model_name=model_name,
            metadata=metadata,
        ),
    ]

    async def scripted(_messages: list[Any], _info: Any) -> ModelResponse:
        return turns.pop(0)

    transcript_path = tmp_path / "gateway-transcript.json"
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
    for message in transcript["messages"]:
        if message.get("kind") == "response":
            # FunctionModel replaces provider-owned identity fields in its
            # transcript; restore the native Gateway response projection while
            # retaining the SDK adapter's actual provider name.
            message["model_name"] = model_name
            message["provider_name"] = "openai"
            message["finish_reason"] = "stop"
            message["provider_details"] = {
                "finish_reason": "STOP",
                "service_tier": "standard",
                "gateway_metadata": metadata,
            }
    transcript["agent_status"] = agent_status
    transcript_path.write_text(json.dumps(transcript, sort_keys=True))

    def fail_if_provider_constructed(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Gateway recovery must not construct provider transport")

    monkeypatch.setattr(
        managed_execution, "OpenAIProvider", fail_if_provider_constructed
    )
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
        assert recovered.result.gateway_response_metadata == (metadata, metadata)
        assert recovered.estimated_cost_usd == pytest.approx(expected_cost)
        assert live_result.input_tokens == recovered.result.input_tokens == 250
        assert live_result.output_tokens == recovered.result.output_tokens == 30
        record = ledger.read_cell_for_recovery("cell-1")
        assert record.response_payload is not None
        payload = json.loads(record.response_payload)
        assert payload["gateway_response_metadata"] == [metadata, metadata]
        assert payload["estimated_cost_usd"] == pytest.approx(expected_cost)


def test_failed_transcript_without_messages_is_rejected_before_restore(
    tmp_path: Path,
) -> None:
    entry = _grok_gateway_entry()
    prompt = _prompt()
    transcript_path = tmp_path / "incomplete-grok-transcript.json"
    transcript_path.write_text(
        json.dumps(
            {
                "model": entry.registry_key,
                "cell": "cell-1",
                "agent_status": "failed",
                "messages": [],
            },
            sort_keys=True,
        )
    )
    with RunnerLedger(
        tmp_path / "ledger.sqlite3", state_only_provider_attempts=True
    ) as ledger:
        _reserve_cell(ledger, entry, prompt)
        ledger.mark_ambiguous(
            "cell-1", provider_attempt_id="attempt-1", failure_type="SettlementError"
        )
        with pytest.raises(RunValidationError, match="no SDK messages"):
            recover_managed_transcript(
                ledger,
                entry=entry,
                transcript_path=transcript_path,
                cell_id="cell-1",
            )
        assert ledger.read_cell_for_recovery("cell-1").response_payload is None


def test_anthropic_native_text_output_transcript_recovers_without_final_tool(
    tmp_path: Path,
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


def test_anthropic_zero_cache_legacy_payload_candidate_omits_new_evidence() -> None:
    entry = _anthropic_entry()
    result = managed_execution.ManagedToolAgentResult(
        raw_output="{}",
        request_count=2,
        input_tokens=250,
        output_tokens=100,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="unreported",
        called_tools=("read",),
        response_usages=((100, 40), (150, 60)),
        response_cache_usages=((0, 0), (0, 0)),
    )

    current_payload = transcript_recovery.managed_replay_payload(result, entry=entry)
    legacy_payload = transcript_recovery._legacy_managed_replay_payload(
        result, entry=entry
    )

    assert "anthropic_cache_evidence" in current_payload
    assert legacy_payload is not None
    assert "anthropic_cache_evidence" not in legacy_payload
    assert legacy_payload["estimated_cost_usd"] == pytest.approx(0.0075)


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
