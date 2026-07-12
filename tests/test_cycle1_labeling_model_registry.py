from __future__ import annotations

from pathlib import Path

from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.labeling.provider_journal import load_provider_cycle_caps

ROOT = Path(__file__).resolve().parents[1]
LABELING_REGISTRY = ROOT / "model_registries" / "cycle-1-labeling-2026-07-12.json"
PROVIDER_CAPS = ROOT / "model_registries" / "cycle-1-provider-caps-2026-07-12.json"


def test_cycle_1_labeling_registry_freezes_only_verified_snapshots() -> None:
    entries = require_official_registry_entries(
        load_model_registry(LABELING_REGISTRY).entries
    )

    assert {entry.registry_key for entry in entries} == {
        "anthropic:claude-haiku-4-5-20251001",
        "anthropic:claude-sonnet-4-6",
        "google:gemini-3.5-flash",
        "openai:gpt-5.4-mini-2026-03-17",
    }
    assert all(entry.model_version_or_snapshot == entry.model_id for entry in entries)
    assert all(entry.network_disabled and entry.search_disabled for entry in entries)
    assert all(entry.tool_policy.value == "no_tools" for entry in entries)


def test_cycle_1_labeling_registry_records_roles_snapshots_and_prices() -> None:
    entries = load_model_registry(LABELING_REGISTRY).entries
    by_key = {entry.registry_key: entry for entry in entries}

    assert "Stage A unitizer" in by_key["anthropic:claude-sonnet-4-6"].display_name
    assert {
        key for key, entry in by_key.items() if "Stage B labeler" in entry.display_name
    } == {
        "anthropic:claude-haiku-4-5-20251001",
        "google:gemini-3.5-flash",
        "openai:gpt-5.4-mini-2026-03-17",
    }
    assert {
        key: (entry.input_token_price, entry.output_token_price)
        for key, entry in by_key.items()
    } == {
        "anthropic:claude-haiku-4-5-20251001": (1.0, 5.0),
        "anthropic:claude-sonnet-4-6": (3.0, 15.0),
        "google:gemini-3.5-flash": (1.5, 9.0),
        "openai:gpt-5.4-mini-2026-03-17": (0.75, 4.5),
    }


def test_gemini_stable_identity_caveat_and_exact_served_version_gate_are_frozen() -> (
    None
):
    entries = load_model_registry(LABELING_REGISTRY).entries
    gemini = next(entry for entry in entries if entry.provider == "google")

    assert gemini.model_id == "gemini-3.5-flash"
    assert gemini.model_version_or_snapshot == "gemini-3.5-flash"
    caveats = " ".join(gemini.known_cutoff_publicity_caveats)
    assert "does not guarantee immutable weights" in caveats
    assert "every official response must return that exact modelVersion" in caveats


def test_cycle_1_provider_caps_stay_below_verified_external_limits() -> None:
    caps = load_provider_cycle_caps(PROVIDER_CAPS)

    assert caps.cycle_id == "cycle-1"
    assert {provider: caps.cap_usd(provider) for provider in caps.providers} == {
        "anthropic": 100.0,
        "google": 50.0,
        "openai": 50.0,
    }
    assert all(
        cap.cycle_reservation_cap_usd < cap.external_spend_limit_usd
        for cap in caps.providers.values()
    )
