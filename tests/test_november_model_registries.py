"""November comparisons retain the full-document condition and cutoff policy."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.reporting.model_cutoffs import cutoff_eligibility, evidence_for
from legalforecast.runner.anthropic_cache import anthropic_cache_cost
from legalforecast.runner.gateway import (
    gateway_model_profile,
    gateway_request_extra_body,
)
from legalforecast.runner.managed_anthropic import anthropic_model_settings
from legalforecast.runner.managed_execution import require_managed_document_tools


@pytest.mark.parametrize(
    ("model_id", "context", "output", "cutoff"),
    [
        ("gemini-4-carbon", 1048576, 65536, date(2026, 3, 1)),
        ("gemini-4-hydrogen", 1048576, 65536, date(2026, 3, 1)),
        ("claude-fable-5-2", 1000000, 128000, date(2026, 6, 1)),
        ("claude-haiku-5-5", 1000000, 128000, date(2026, 6, 1)),
        ("gpt-6.1-terra", 1050000, 128000, date(2026, 6, 1)),
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
    elif entry.provider == "google":
        assert entry.thinking_level is not None
        assert entry.thinking_level.value == "high"
        assert entry.long_context_surcharge is None


@pytest.mark.parametrize(
    ("model_id", "route", "threshold"),
    [
        ("moonshotai/kimi-k3.1-pro", "deepinfra", None),
        ("meta/muse-ember", "meta", 200000),
    ],
)
def test_november_gateway_routes_stay_qualified_and_provider_locked(
    model_id: str, route: str, threshold: int | None
) -> None:
    entry = load_model_registry(
        Path(
            f"model_registries/cycle-1-agentic-{model_id.split('/')[-1]}-high-2026-11-12.json"
        )
    ).entries[0]
    require_official_registry_entries((entry,))
    require_managed_document_tools(entry)
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.max_output_tokens == 128000
    assert entry.jev_input_mode is None
    assert entry.temperature is None and entry.top_p is None
    assert entry.network_disabled and entry.search_disabled
    assert gateway_request_extra_body(model_id) == {
        "providerOptions": {"gateway": {"only": [route]}}
    }
    evidence = evidence_for(model_id)
    assert evidence is not None and evidence.comparison_date is None
    assert (
        cutoff_eligibility(evidence, first_decision=date(2026, 6, 30))[0] == "qualified"
    )
    assert (
        entry.long_context_surcharge.threshold_input_tokens
        if entry.long_context_surcharge
        else None
    ) == threshold


def test_ember_profile_uses_automatic_tool_choice() -> None:
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key="fixture")
    assert (
        gateway_model_profile(provider, "meta/muse-ember")[
            "supports_forced_tool_choice"
        ]
        is False
    )
    assert (
        gateway_model_profile(provider, "moonshotai/kimi-k3.1-pro").get(
            "supports_forced_tool_choice", True
        )
        is True
    )


@pytest.mark.parametrize("inputs,multiplier", [(100000, 1), (100001, 5)])
def test_haiku_prices_all_cache_buckets_at_the_context_tier(
    inputs: int, multiplier: int
) -> None:
    entry = load_model_registry(
        Path("model_registries/cycle-1-agentic-claude-haiku-5-5-high-2026-11-12.json")
    ).entries[0]
    actual, _ = anthropic_cache_cost(
        entry, response_usages=((inputs, 200),), cache_usages=((40000, 10000),)
    )
    expected = (
        ((inputs - 50000) * 0.1 + 40000 * 0.01 + 10000 * 0.125 + 200 * 0.5)
        * multiplier
        / 1000000
    )
    assert actual == pytest.approx(expected)
    base, _ = anthropic_cache_cost(
        replace(entry, long_context_surcharge=None),
        response_usages=((inputs, 200),),
        cache_usages=((40000, 10000),),
    )
    assert actual == pytest.approx(base * multiplier)


@pytest.mark.parametrize(
    "model_id,provider,native_id",
    [
        ("meta/muse-ember", "meta", "muse-ember-1.0"),
        ("moonshotai/kimi-k3.1-pro", "deepinfra", "moonshotai/Kimi-K3.1-Pro"),
    ],
)
def test_new_gateway_models_require_the_documented_native_identity(
    model_id: str, provider: str, native_id: str
) -> None:
    from legalforecast.runner.gateway import validate_gateway_metadata

    metadata = {
        "original_model_id": model_id,
        "canonical_slug": model_id,
        "resolved_provider": provider,
        "final_provider": provider,
        "generation_id": "fixture",
        "cost_usd": "0.01",
        "market_cost_usd": "0.01",
        "model_attempt_count": "1",
        "total_provider_attempt_count": "1",
    }
    for wrong in (None, "wrong-model"):
        candidate = dict(metadata)
        if wrong is not None:
            candidate["resolved_provider_api_model_id"] = wrong
        with pytest.raises(ValueError, match="native model identity"):
            validate_gateway_metadata(
                candidate, expected_model_id=model_id, expected_provider=provider
            )
    assert (
        validate_gateway_metadata(
            metadata,
            expected_model_id=model_id,
            expected_provider=provider,
            observed_model_id=native_id,
        )
        == metadata
    )
    with pytest.raises(ValueError, match="native model identity"):
        validate_gateway_metadata(
            metadata,
            expected_model_id=model_id,
            expected_provider=provider,
            observed_model_id="wrong-model",
        )
    with pytest.raises(ValueError, match="native model identity"):
        validate_gateway_metadata(
            {**metadata, "resolved_provider_api_model_id": "wrong-model"},
            expected_model_id=model_id,
            expected_provider=provider,
            observed_model_id=native_id,
        )
    from legalforecast.runner.gateway import gateway_normalize_model_identity

    assert (
        gateway_normalize_model_identity(
            model_id, native_id, gateway_metadata=(metadata,)
        )
        == model_id
    )
    metadata["resolved_provider_api_model_id"] = native_id
    assert (
        validate_gateway_metadata(
            metadata, expected_model_id=model_id, expected_provider=provider
        )
        == metadata
    )


@pytest.mark.parametrize("slug", ["kimi-k3.1-pro", "muse-ember"])
def test_corrected_gateway_snapshot_preserves_model_request_settings(slug: str) -> None:
    prior = load_model_registry(
        Path(f"model_registries/cycle-1-agentic-{slug}-high-2026-11-12.json")
    ).entries[0]
    corrected = load_model_registry(
        Path(f"model_registries/cycle-1-agentic-{slug}-high-2026-11-13.json")
    ).entries[0]
    assert (
        replace(
            corrected,
            known_cutoff_publicity_caveats=prior.known_cutoff_publicity_caveats,
        )
        == prior
    )
    assert (
        "returned response model name" in corrected.known_cutoff_publicity_caveats[-1]
    )
