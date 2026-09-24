from pathlib import Path

import pytest
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.runner.managed_execution import require_managed_document_tools


@pytest.mark.parametrize("model", ["gpt-4.1", "gemini-3.1-pro-preview"])
def test_requested_models_keep_full_agentic_condition(model: str) -> None:
    registry = load_model_registry(
        Path(f"model_registries/cycle-1-agentic-{model}-2026-09-24.json")
    )
    entry = registry.entries[0]
    require_managed_document_tools(entry)
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert entry.network_disabled and entry.search_disabled
    assert entry.jev_input_mode is None
    assert entry.jev_summaries_sha256 is None
    assert entry.provider_training_cutoff is None
    assert entry.provider_training_cutoff_status.value == "unknown"
    if entry.provider == "openai":
        assert entry.model_id == "gpt-4.1-2025-04-14"
        assert entry.reasoning_effort is None
    else:
        assert entry.thinking_level is not None
        assert entry.thinking_level.value == "high"
        assert entry.long_context_surcharge is not None
