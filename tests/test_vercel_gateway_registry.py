from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from legalforecast.evals.model_registry import load_model_registry
from legalforecast.reporting.result_class import (
    ResultClass,
    classify_registry_entry,
    require_lane_result_classes,
)

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "model_registries"
GATEWAY_REGISTRY = REGISTRY_DIR / "cycle-1-official-gateway-held-models-2026-09-08.json"
CONTRIBUTOR_REGISTRY = (
    REGISTRY_DIR / "cycle-1-official-muse-spark-1.3-contributor-2026-09-08.json"
)
DEFERRED_CANDIDATES = (
    REGISTRY_DIR / "cycle-1-gateway-deferred-candidates-2026-09-08.json"
)


def test_gateway_registry_has_only_explicitly_allowlisted_post_anchor_models() -> None:
    registry = load_model_registry(GATEWAY_REGISTRY)
    assert [entry.registry_key for entry in registry.entries] == [
        "vercel_ai_gateway:moonshotai/kimi-k3",
        "vercel_ai_gateway:meta/muse-spark-1.3",
    ]
    assert all(
        classify_registry_entry(entry, corpus_anchor=date(2026, 6, 30))
        is ResultClass.POST_ANCHOR
        for entry in registry.entries
    )
    require_lane_result_classes(
        list(registry.entries), corpus_anchor=date(2026, 6, 30), supplementary=True
    )


def test_gateway_registry_freezes_current_routes_prices_and_tool_policy() -> None:
    registry = load_model_registry(GATEWAY_REGISTRY)
    values = {
        entry.model_id: (
            entry.input_token_price,
            entry.output_token_price,
            entry.reasoning_effort.value if entry.reasoning_effort else None,
            entry.tool_policy.value,
        )
        for entry in registry.entries
    }
    assert values == {
        "moonshotai/kimi-k3": (2.85, 14.25, "high", "controlled_docket_tool_only"),
        "meta/muse-spark-1.3": (1.25, 4.25, "high", "controlled_docket_tool_only"),
    }
    for entry in registry.entries:
        assert entry.provider == "vercel_ai_gateway"
        assert entry.network_disabled is True
        assert entry.search_disabled is True
        assert entry.max_output_tokens == 128000
        assert entry.context_limit > entry.max_output_tokens
        assert "vercel.com/ai-gateway/models/" in entry.pricing_source
        assert "2026-09-08" in entry.pricing_source
        assert entry.known_cutoff_publicity_caveats


def test_owner_approved_contributor_has_a_dedicated_executable_registry() -> None:
    registry = load_model_registry(CONTRIBUTOR_REGISTRY)
    assert [entry.registry_key for entry in registry.entries] == [
        "vercel_ai_gateway:meta/muse-spark-1.3-contributor"
    ]
    entry = registry.entries[0]
    assert (
        classify_registry_entry(entry, corpus_anchor=date(2026, 6, 30))
        is ResultClass.POST_ANCHOR
    )
    require_lane_result_classes(
        list(registry.entries), corpus_anchor=date(2026, 6, 30), supplementary=True
    )
    assert (entry.input_token_price, entry.output_token_price) == (0.1, 0.2)
    assert entry.context_limit == 1_000_000
    assert entry.max_output_tokens == 128_000
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.network_disabled is True
    assert entry.search_disabled is True
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert "muse-spark-1.3-contributor" in entry.pricing_source
    assert "USD 0.002/M cached input" in entry.pricing_source
    assert "owner-approved" in " ".join(entry.known_cutoff_publicity_caveats)


def test_muse_contributor_and_sonnet_are_deferred_and_not_executable() -> None:
    payload = json.loads(DEFERRED_CANDIDATES.read_text(encoding="utf-8"))
    assert payload["status"] == "deferred"
    assert payload["schema_version"] == "legalforecast.gateway_deferred_candidates.v1"
    assert payload["candidates"] == [
        {
            "display_name": "Claude Sonnet 5 via Vercel AI Gateway",
            "input_token_price": 2.0,
            "model_id": "anthropic/claude-sonnet-5",
            "output_token_price": 10.0,
            "pricing_source": (
                "https://vercel.com/ai-gateway/models/claude-sonnet-5 "
                "(current starting prices), checked 2026-09-08"
            ),
            "reason": (
                "Deferred candidate: absent from the current held model set and "
                "intentionally not executable or dispatched by this lane."
            ),
            "release_timestamp": "2026-06-29T00:00:00Z",
            "release_timestamp_source": (
                "https://vercel.com/ai-gateway/models/claude-sonnet-5 "
                "(release date), checked 2026-09-08"
            ),
        }
    ]
    registry = load_model_registry(GATEWAY_REGISTRY)
    assert "anthropic/claude-sonnet-5" not in {
        entry.model_id for entry in registry.entries
    }
    assert "meta/muse-spark-1.3-contributor" not in {
        entry.model_id for entry in registry.entries
    }
