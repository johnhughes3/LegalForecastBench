from __future__ import annotations

import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.runner.anthropic_cache import anthropic_cache_cost


def _entry(
    model_id: str, *, input_price: float, output_price: float
) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "anthropic",
            "model_id": model_id,
            "display_name": model_id,
            "model_version_or_snapshot": model_id,
            "provider_training_cutoff_status": "unknown",
            "max_output_tokens": 128000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 1000000,
            "pricing_source": "frozen-test-registry",
            "input_token_price": input_price,
            "output_token_price": output_price,
            "known_cutoff_publicity_caveats": [],
        }
    )


@pytest.mark.parametrize(
    ("model_id", "input_price", "output_price", "expected", "read", "write"),
    (
        ("claude-fable-5-1", 10.0, 50.0, 0.01635, 400, 100),
        ("claude-opus-5", 5.0, 25.0, 0.008325, 400, 100),
        ("claude-sonnet-5", 2.0, 10.0, 0.00333, 400, 100),
    ),
)
def test_anthropic_cache_cost_prices_each_input_bucket_once(
    model_id: str,
    input_price: float,
    output_price: float,
    expected: float,
    read: int,
    write: int,
) -> None:
    amount, metadata = anthropic_cache_cost(
        _entry(model_id, input_price=input_price, output_price=output_price),
        response_usages=((1000, 200),),
        cache_usages=((read, write),),
    )

    assert amount == pytest.approx(expected)
    assert metadata["cost_basis"] == "estimated_from_pricing_snapshot"
    assert metadata["cost_method"] == "anthropic_cache_aware_usage_reconstruction"
    assert metadata["cache_pricing_model"] == model_id
    assert metadata["cache_pricing_ttl"] == "5m"
    assert metadata["cache_pricing_source"] == (
        "https://platform.claude.com/docs/en/about-claude/pricing, "
        "Anthropic prompt-cache pricing checked 2026-09-12"
    )
    assert "cache_read=" in str(metadata["rate_provenance"])
    assert "cache_write=" in str(metadata["rate_provenance"])


def test_anthropic_cache_cost_keeps_zero_cache_responses_valid() -> None:
    amount, metadata = anthropic_cache_cost(
        _entry("claude-opus-5", input_price=5.0, output_price=25.0),
        response_usages=((1000, 200),),
        cache_usages=((0, 0),),
    )

    assert amount == pytest.approx(0.01)
    assert metadata["cache_read_token_price_usd_per_million"] == 0.5
    assert metadata["cache_write_token_price_usd_per_million"] == 6.25


@pytest.mark.parametrize(
    ("response_usages", "cache_usages", "message"),
    (
        (((100, 10), (100, 10)), ((50, 10),), "equal lengths"),
        (((100, 10),), ((91, 10),), "exceeds input"),
    ),
)
def test_anthropic_cache_cost_rejects_inconsistent_usage(
    response_usages: tuple[tuple[int, int], ...],
    cache_usages: tuple[tuple[int, int], ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        anthropic_cache_cost(
            _entry("claude-opus-5", input_price=5.0, output_price=25.0),
            response_usages=response_usages,
            cache_usages=cache_usages,
        )


def test_anthropic_cache_cost_rejects_unverified_model() -> None:
    with pytest.raises(ValueError, match="no verified five-minute"):
        anthropic_cache_cost(
            _entry("claude-opus-4-8", input_price=5.0, output_price=25.0),
            response_usages=((100, 10),),
            cache_usages=((0, 0),),
        )
