from __future__ import annotations

from dataclasses import replace

import legalforecast.runner.managed_execution as managed_execution
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.runner.managed_execution import (
    ManagedResponseUsage,
    ManagedToolAgentResult,
)
from legalforecast.runner.managed_receipt import add_managed_cost_evidence
from pydantic_ai.messages import ModelResponse
from pydantic_ai.usage import RequestUsage


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


def test_managed_cost_reconstructs_cached_input_at_authoritative_rates() -> None:
    entry = replace(
        _entry(),
        cache_read_token_price=0.2,
        cache_write_token_price=0.5,
    )
    usage = ManagedResponseUsage(
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=400,
        cache_write_tokens=100,
        reasoning_tokens=30,
    )
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="flex",
        called_tools=("read",),
        response_usages=((1000, 200),),
        response_usage_details=(usage,),
    )

    evidence = managed_execution._managed_result_cost_evidence(entry, result=result)

    # Input is inclusive: 500 uncached + 400 read + 100 write. Reasoning is
    # already included in the normalized 200 output tokens and is not added.
    assert evidence.amount_usd == pytest.approx(0.00183)
    assert evidence.basis == "estimated_from_pricing_snapshot"
    assert evidence.method == "cache_aware_usage_reconstruction"
    assert evidence.rate_provenance == "fixture"


def test_managed_cost_keeps_missing_cache_usage_as_a_legacy_estimate() -> None:
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model="gpt-5.6-luna",
        finish_reason="stop",
        service_tier="flex",
        called_tools=("read",),
        response_usages=((1000, 200),),
    )

    evidence = managed_execution._managed_result_cost_evidence(_entry(), result=result)

    assert evidence.amount_usd == pytest.approx(0.0022)
    assert evidence.method == "legacy_uncached_usage_estimate"
    assert evidence.basis == "estimated_from_pricing_snapshot"


def test_managed_cost_reconstructs_read_cache_without_write_rate() -> None:
    entry = replace(_entry(), cache_read_token_price=0.2)
    usage = ManagedResponseUsage(
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=400,
        cache_write_tokens=0,
    )
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="flex",
        called_tools=("read",),
        response_usages=((1000, 200),),
        response_usage_details=(usage,),
    )

    evidence = managed_execution._managed_result_cost_evidence(entry, result=result)

    assert evidence.amount_usd == pytest.approx(0.00188)
    assert evidence.method == "cache_aware_usage_reconstruction"


def test_managed_response_usage_serialization_does_not_invent_omitted_dimensions() -> (
    None
):
    assert ManagedResponseUsage(10, 5).to_record() == {
        "input_tokens": 10,
        "output_tokens": 5,
    }


def test_managed_response_usage_preserves_provider_dimensions_once() -> None:
    response = ModelResponse(
        parts=[],
        usage=RequestUsage(
            input_tokens=100,
            cache_read_tokens=40,
            cache_write_tokens=10,
            output_tokens=20,
            details={"thoughts_tokens": 7},
        ),
        model_name="gpt-5.6-luna",
        provider_name="openai",
        finish_reason="stop",
    )

    usage = managed_execution._managed_response_usage(response)

    assert usage.to_record() == {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 40,
        "cache_write_tokens": 10,
        "reasoning_tokens": 7,
    }


def test_receipt_projection_labels_charged_gateway_amount() -> None:
    receipt: dict[str, object] = {
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "estimated_cost_microusd": 1000,
        }
    }

    add_managed_cost_evidence(
        receipt,
        {
            "cost_basis": "provider_reported",
            "cost_method": "gateway_reported_charge",
            "rate_provenance": "gateway_response_metadata",
            "service_tier": "standard",
            "response_usage_details": "not_reported",
        },
    )

    assert receipt["cost_evidence"] == {
        "basis": "provider_reported",
        "method": "gateway_reported_charge",
        "rate_provenance": "gateway_response_metadata",
        "service_tier": "standard",
        "charged_cost_microusd": 1000,
    }
