from __future__ import annotations

from pathlib import Path

from legalforecast.evals.model_registry import load_model_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_registries" / "cycle-1-disclosure-reviewer-2026-07-27.json"
EVALUATED_REGISTRY = ROOT / "model_registries" / "cycle-1-2026-06-30.json"


def test_cycle_1_disclosure_review_registry_is_one_disjoint_gemini_entry() -> None:
    registry = load_model_registry(REGISTRY)

    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.registry_key == "google:gemini-3.5-flash"
    assert entry.model_version_or_snapshot == "gemini-3.5-flash"
    assert entry.network_disabled
    assert entry.search_disabled
    assert entry.tool_policy.value == "no_tools"
    assert entry.max_output_tokens == 16_384
    assert "disclosure" in entry.display_name.casefold()


def test_cycle_1_disclosure_reviewer_is_provider_and_model_disjoint() -> None:
    reviewer = load_model_registry(REGISTRY).entries[0]
    evaluated = load_model_registry(EVALUATED_REGISTRY).entries

    assert reviewer.provider not in {entry.provider for entry in evaluated}
    assert reviewer.model_id not in {entry.model_id for entry in evaluated}
    assert reviewer.registry_key not in {entry.registry_key for entry in evaluated}
