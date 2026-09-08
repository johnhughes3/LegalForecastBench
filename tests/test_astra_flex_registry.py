from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, cast

import legalforecast.runner.managed_execution as managed_execution
from legalforecast.evals.live_model_solver import OPENAI_SERVICE_TIER, _openai_request
from legalforecast.evals.model_registry import load_model_registry

ROOT = Path(__file__).resolve().parents[1]
FLEX_REGISTRY = (
    ROOT / "model_registries" / ("cycle-1-official-gpt-6-astra-flex-2026-09-08.json")
)
HELD_REGISTRY = (
    ROOT / "model_registries" / ("cycle-1-official-held-models-2026-09-08.json")
)


def _json_body(request: urllib.request.Request) -> dict[str, Any]:
    data = request.data
    assert isinstance(data, bytes)
    payload: object = json.loads(data.decode("utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_astra_flex_registry_freezes_flex_rates_and_identity() -> None:
    registry = load_model_registry(FLEX_REGISTRY)

    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.registry_key == "openai:gpt-6-astra"
    assert entry.display_name == "GPT-6 Astra Flex"
    assert (entry.input_token_price, entry.output_token_price) == (5.0, 25.0)
    assert entry.reasoning_effort is not None
    assert entry.reasoning_effort.value == "high"
    assert entry.long_context_surcharge is not None
    assert entry.long_context_surcharge.threshold_input_tokens == 272000
    assert entry.long_context_surcharge.input_price_multiplier == 2.0
    assert entry.long_context_surcharge.output_price_multiplier == 1.5
    assert "Flex" in entry.pricing_source
    assert "USD 0.50/M cached input" in entry.pricing_source
    assert "2026-09-08" in entry.pricing_source


def test_astra_flex_registry_does_not_rewrite_held_standard_registry() -> None:
    standard = load_model_registry(HELD_REGISTRY).get("openai", "gpt-6-astra")
    flex = load_model_registry(FLEX_REGISTRY).get("openai", "gpt-6-astra")

    assert (standard.input_token_price, standard.output_token_price) == (10.0, 50.0)
    assert (flex.input_token_price, flex.output_token_price) == (5.0, 25.0)
    assert standard.model_id == flex.model_id
    assert standard.model_version_or_snapshot == flex.model_version_or_snapshot


def test_astra_flex_live_request_and_managed_estimate_use_flex_rates() -> None:
    entry = load_model_registry(FLEX_REGISTRY).entries[0]

    request = _openai_request(entry, "fixture prompt", "fixture-key", None)
    body = _json_body(request)
    assert body["model"] == "gpt-6-astra"
    assert body["service_tier"] == OPENAI_SERVICE_TIER
    assert body["reasoning"] == {"effort": "high"}

    # The existing managed runtime prices registry usage directly. This catches
    # accidentally passing the held Standard entry into an explicitly Flex run.
    assert (
        managed_execution._managed_estimated_cost(
            entry, response_usages=((1000, 1000),)
        )
        == 0.03
    )
