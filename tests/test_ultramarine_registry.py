"""Ultramarine's direct provider keeps the regular document-tool condition."""

from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.runner.ledger import RunValidationError
from legalforecast.runner.managed_execution import require_managed_document_tools
from legalforecast.runner.paperinstruments import paperinstruments_model
from legalforecast.runner.provider_auth import select_provider_authentication

REGISTRY = Path(
    "model_registries/cycle-1-agentic-ultramarine-1-flash-high-2026-10-14.json"
)


def test_ultramarine_registry_is_full_document_high_reasoning() -> None:
    entry = load_model_registry(REGISTRY).entries[0]
    require_official_registry_entries((entry,))
    require_managed_document_tools(entry)
    assert entry.registry_key == "paperinstruments:ultramarine-1-flash"
    assert entry.jev_input_mode is None and entry.jev_summaries_sha256 is None
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.context_limit == 131072 and entry.max_output_tokens == 32768
    assert entry.network_disabled and entry.search_disabled
    assert entry.provider_training_cutoff_status.value == "unknown"
    assert entry.cache_read_token_price == 0.03
    assert entry.input_token_price == 0.15 and entry.output_token_price == 0.5


def test_ultramarine_does_not_inherit_anthropic_credentials() -> None:
    with pytest.raises(RunValidationError, match="PAPERINSTRUMENTS_API_KEY"):
        select_provider_authentication(
            "paperinstruments", {"ANTHROPIC_API_KEY": "other"}
        )
    auth = select_provider_authentication(
        "paperinstruments", {"PAPERINSTRUMENTS_API_KEY": "fixture-key"}
    )
    assert auth.api_key is not None
    assert auth.api_key.get_secret_value() == "fixture-key"
    assert auth.provenance()["authentication_provider"] == "paperinstruments"
    assert "fixture-key" not in repr(auth)
    entry = load_model_registry(REGISTRY).entries[0]
    model = paperinstruments_model(entry, api_key="fixture-key")
    assert str(model.base_url).rstrip("/") == "https://api.paperinstruments.com"


@pytest.mark.parametrize(
    "field,value",
    [("max_output_tokens", 32769), ("context_limit", 131073), ("model_id", "unknown")],
)
def test_ultramarine_rejects_unsupported_configuration(
    field: str, value: object
) -> None:
    entry = load_model_registry(REGISTRY).entries[0]
    with pytest.raises(ValueError, match="Paper Instruments"):
        replace(entry, **{field: value})


def test_ultramarine_managed_wire_and_cache_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the SDK's real two-turn tool loop using an offline HTTP transport."""
    import json

    import httpx2
    from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
    from legalforecast.runner.managed_cost import managed_result_cost_evidence
    from legalforecast.runner.managed_execution import run_managed_tool_agent
    from pydantic_ai.providers import anthropic as provider_module

    entry = load_model_registry(REGISTRY).entries[0]
    requests: list[dict] = []
    output = {
        "case_assessment": "Assessment",
        "predictions": [{"unit_id": "unit-a", "probability_fully_dismissed": 0.5}],
    }

    async def handler(request):
        assert request.url.host == "api.paperinstruments.com"
        assert request.headers["x-api-key"] == "fixture-key"
        body = json.loads(await request.aread())
        requests.append(body)
        assert body["model"] == entry.model_id
        assert body["thinking"] == {"type": "adaptive", "display": "omitted"}
        assert body["output_config"]["effort"] == "high"
        assert body["output_config"]["format"]["type"] == "json_schema"
        assert body["cache_control"] == {"type": "ephemeral"}
        assert body["max_tokens"] == 32768
        assert body["tool_choice"]["type"] == "auto"
        block = (
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "read",
                "input": {"file_path": "/workspace/documents/motion.txt"},
            }
            if len(requests) == 1
            else {"type": "text", "text": json.dumps(output)}
        )
        usage = {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_read_input_tokens": 0 if len(requests) == 1 else 80,
            "cache_creation_input_tokens": 0,
        }
        response = {
            "id": f"msg_{len(requests)}",
            "type": "message",
            "role": "assistant",
            "model": entry.model_id,
            "content": [block],
            "stop_reason": "tool_use" if len(requests) == 1 else "end_turn",
            "stop_sequence": None,
            "usage": usage,
        }
        if not body.get("stream"):
            return httpx2.Response(200, json=response)
        start = (
            {**block, "input": {}}
            if block["type"] == "tool_use"
            else {"type": "text", "text": ""}
        )
        delta = (
            {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
            if block["type"] == "tool_use"
            else {"type": "text_delta", "text": block["text"]}
        )
        events = [
            {
                "type": "message_start",
                "message": {
                    **response,
                    "content": [],
                    "stop_reason": None,
                    "usage": {**usage, "output_tokens": 0},
                },
            },
            {"type": "content_block_start", "index": 0, "content_block": start},
            {"type": "content_block_delta", "index": 0, "delta": delta},
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {
                    "stop_reason": response["stop_reason"],
                    "stop_sequence": None,
                },
                "usage": {"output_tokens": 20},
            },
            {"type": "message_stop"},
        ]
        return httpx2.Response(
            200,
            text="".join(
                f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events
            ),
            headers={"content-type": "text/event-stream"},
        )

    real_provider = provider_module.AnthropicProvider
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    monkeypatch.setattr(
        provider_module,
        "AnthropicProvider",
        lambda **kwargs: real_provider(**kwargs, http_client=client),
    )

    class Executor:
        def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
            assert request.operation == "read"
            return ToolResponse(
                request_id=request.request_id,
                status="succeeded",
                output={"content": "Motion"},
            )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = run_managed_tool_agent(
        entry,
        initial_prompt="Case case-1. Read /workspace/documents/motion.txt",
        required_unit_ids=("unit-a",),
        executor=Executor(),
        workspace=workspace,
        request_id="cell-1",
        api_key="fixture-key",
    )
    assert len(requests) == 2
    assert result.served_model == entry.model_id
    assert result.called_tools == ("read",)
    assert json.loads(result.raw_output) == output
    assert result.input_tokens == 280
    assert result.output_tokens == 40
    cost = managed_result_cost_evidence(entry, result=result)
    assert cost.amount_usd == pytest.approx(
        (200 * 0.15 + 80 * 0.03 + 40 * 0.5) / 1_000_000
    )
    assert cost.basis == "estimated_from_pricing_snapshot"


def test_ultramarine_public_accounting_includes_standard_repricing() -> None:
    from legalforecast.publication.receipt_accounting import build_public_accounting

    registry = load_model_registry(REGISTRY)
    record = {
        "model_key": registry.entries[0].registry_key,
        "case_id": "case-a",
        "run_identity_sha256": "run-a",
        "usage": {
            "estimated_cost_microusd": 704000,
            "input_tokens": 2000000,
            "output_tokens": 1000000,
        },
        "cost_evidence": {
            "basis": "estimated_from_pricing_snapshot",
            "method": "cache_aware_usage_reconstruction",
            "response_usage_details": [
                {
                    "input_tokens": 2000000,
                    "output_tokens": 1000000,
                    "cache_read_tokens": 800000,
                    "cache_write_tokens": 0,
                }
            ],
        },
    }
    output = build_public_accounting([record], registry)[0]
    assert output["standard_rate_cost"] == pytest.approx(0.704)
    assert output["estimated_cost"] == 0.704
    assert output["missing_cache_read_response_count"] == 0
    assert output["missing_cache_write_response_count"] == 0
