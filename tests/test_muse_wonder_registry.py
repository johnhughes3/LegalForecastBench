"""Muse Wonder uses the standard full-document managed benchmark."""

from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.runner.gateway import (
    gateway_model_profile,
    gateway_request_extra_body,
    gateway_route_provider,
)
from legalforecast.runner.managed_execution import require_managed_document_tools
from pydantic_ai.providers.openai import OpenAIProvider

REGISTRY = Path("model_registries/cycle-1-agentic-muse-wonder-1-0-high-2026-10-12.json")


def test_muse_wonder_uses_high_reasoning_and_managed_document_tools() -> None:
    registry = load_model_registry(REGISTRY)
    entry = registry.entries[0]
    assert require_official_registry_entries(registry.entries) == registry.entries
    require_managed_document_tools(entry)
    assert entry.registry_key == "vercel_ai_gateway:meta/muse-wonder-1.0"
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert entry.network_disabled and entry.search_disabled
    assert entry.jev_input_mode is None and entry.jev_summaries_sha256 is None
    assert entry.context_limit == 1048576
    assert entry.max_output_tokens == 128000
    assert entry.input_token_price == 4
    assert entry.output_token_price == 20
    assert entry.cache_read_token_price == 0.2
    assert entry.provider_training_cutoff is None
    assert entry.provider_training_cutoff_status.value == "unknown"
    assert gateway_request_extra_body(entry.model_id) == {
        "providerOptions": {"gateway": {"only": ["meta"]}}
    }


def test_muse_wonder_profile_uses_supported_automatic_tool_choice() -> None:
    provider = OpenAIProvider(api_key="offline-test-key")
    profile = gateway_model_profile(provider, "meta/muse-wonder-1.0")
    assert profile.get("openai_supports_tool_choice_required") is False
    assert profile.get("openai_supports_reasoning") is True
    assert profile.get("openai_supports_reasoning_effort_none") is False


def test_subscription_only_muse_wonder_full_has_no_gateway_route() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        gateway_route_provider("meta/muse-wonder-full-1.0")
