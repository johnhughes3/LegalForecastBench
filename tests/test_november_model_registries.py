"""November comparisons retain the full-document condition and cutoff policy."""

from datetime import date
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.reporting.model_cutoffs import cutoff_eligibility, evidence_for
from legalforecast.runner.managed_anthropic import anthropic_model_settings
from legalforecast.runner.managed_execution import require_managed_document_tools


@pytest.mark.parametrize(
    ("model_id", "context", "output", "cutoff"),
    [
        ("gemini-4-carbon", 1048576, 65536, date(2026, 3, 1)),
        ("gemini-4-hydrogen", 1048576, 65536, date(2026, 3, 1)),
        ("claude-fable-5-2", 1000000, 128000, date(2026, 6, 1)),
    ],
)
def test_november_comparisons_use_eligible_full_document_high_effort(
    model_id: str, context: int, output: int, cutoff: date
) -> None:
    entry = load_model_registry(
        Path(f"model_registries/cycle-1-agentic-{model_id}-high-2026-11-12.json")
    ).entries[0]
    require_official_registry_entries((entry,))
    require_managed_document_tools(entry)
    assert entry.jev_input_mode is None and entry.jev_summaries_sha256 is None
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert entry.network_disabled and entry.search_disabled
    assert entry.temperature is None and entry.top_p is None
    assert entry.context_limit == context and entry.max_output_tokens == output
    # Month-only provider evidence must not become an invented exact training day.
    assert entry.provider_training_cutoff is None
    evidence = evidence_for(model_id)
    assert evidence is not None and evidence.comparison_date == cutoff
    assert cutoff_eligibility(evidence, first_decision=date(2026, 6, 30)) == (
        "eligible",
        "reported_cutoff_predates_decisions",
    )
    if entry.provider == "anthropic":
        assert entry.reasoning_effort is not None
        assert entry.reasoning_effort.value == "high"
        settings = anthropic_model_settings(entry)
        assert settings["anthropic_effort"] == "high"
        assert settings["anthropic_thinking"] == {"type": "adaptive"}
        assert settings["anthropic_cache"] is True
    else:
        assert entry.thinking_level is not None
        assert entry.thinking_level.value == "high"
        assert entry.long_context_surcharge is None
