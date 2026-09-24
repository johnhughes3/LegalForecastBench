from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.runner.managed_execution import require_managed_document_tools


@pytest.mark.parametrize("model", ["gpt-4.1", "gemini-3.1-pro-preview"])
def test_requested_models_keep_full_agentic_condition(model: str) -> None:
    registry = load_model_registry(
        Path(f"model_registries/cycle-1-agentic-{model}-2026-09-24.json")
    )
    entry = registry.entries[0]
    assert require_official_registry_entries(registry.entries) == registry.entries
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
        assert "Preview" in entry.display_name
        assert entry.model_version_or_snapshot == entry.model_id
        assert entry.thinking_level is not None
        assert entry.thinking_level.value == "high"
        assert entry.long_context_surcharge is not None


@pytest.mark.parametrize(
    "model_id", ["gemini-3.1-pro-preview-customtools", "gemini-3.1-pro-latest"]
)
def test_preview_exception_does_not_admit_other_aliases(model_id: str) -> None:
    registry = load_model_registry(
        Path("model_registries/cycle-1-agentic-gemini-3.1-pro-preview-2026-09-24.json")
    )
    entry = replace(
        registry.entries[0], model_id=model_id, model_version_or_snapshot=model_id
    )
    with pytest.raises(ValueError, match="mutable aliases"):
        require_official_registry_entries((entry,))
