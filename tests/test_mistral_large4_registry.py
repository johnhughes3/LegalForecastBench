"""Mistral uses the regular managed document-tool benchmark treatment."""

from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.runner.gateway import (
    gateway_request_extra_body,
    gateway_route_provider,
)
from legalforecast.runner.managed_execution import require_managed_document_tools

REGISTRY = Path("model_registries/cycle-1-agentic-mistral-large-4-high-2026-10-12.json")


def test_mistral_large4_uses_high_reasoning_and_managed_document_tools() -> None:
    registry = load_model_registry(REGISTRY)
    entry = registry.entries[0]
    assert require_official_registry_entries(registry.entries) == registry.entries
    require_managed_document_tools(entry)
    assert entry.registry_key == "vercel_ai_gateway:mistral/mistral-large-4"
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert entry.network_disabled and entry.search_disabled
    assert entry.jev_input_mode is None and entry.jev_summaries_sha256 is None
    assert entry.context_limit == 524288
    assert entry.input_token_price == 1.36
    assert entry.output_token_price == 4.18
    assert entry.cache_read_token_price == 0.14
    assert entry.provider_training_cutoff_status.value == "unknown"
    assert gateway_route_provider(entry.model_id) == "mistral"
    assert gateway_request_extra_body(entry.model_id) == {
        "providerOptions": {"gateway": {"only": ["mistral"]}}
    }


def test_unregistered_mistral_models_cannot_fall_back_to_another_route() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        gateway_route_provider("mistral/mistral-large-latest")
