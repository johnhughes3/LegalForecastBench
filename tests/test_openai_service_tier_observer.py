from __future__ import annotations

from typing import Any

import pytest
from legalforecast.evals.live_model_solver import (
    OPENAI_SERVICE_TIER,
    LiveModelResponseError,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry


@pytest.mark.parametrize(
    "payload",
    (
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "service_tier": OPENAI_SERVICE_TIER,
            "status": "failed",
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        },
        {
            "model": "gpt-test-2026-05-14",
            "service_tier": OPENAI_SERVICE_TIER,
            "status": "completed",
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        },
        {
            "model": "gpt-test-latest",
            "output_text": '{"predictions":[]}',
            "service_tier": OPENAI_SERVICE_TIER,
            "status": "completed",
            "usage": {"input_tokens": 1000, "output_tokens": 250},
        },
        {
            "model": "gpt-test-2026-05-14",
            "output_text": '{"predictions":[]}',
            "service_tier": OPENAI_SERVICE_TIER,
            "status": "completed",
            "usage": {},
        },
    ),
    ids=("status", "output", "served_model", "usage"),
)
def test_openai_observes_service_tier_before_invalid_response_validation(
    payload: dict[str, Any],
) -> None:
    observed_tiers: list[str] = []

    with pytest.raises(LiveModelResponseError):
        complete_live_prompt(
            _openai_entry(),
            "Predict the case outcome.",
            environ={"OPENAI_API_KEY": "openai-secret"},
            transport=lambda _request, _timeout: payload,
            openai_service_tier_observer=observed_tiers.append,
        )

    assert observed_tiers == [OPENAI_SERVICE_TIER]


def _openai_entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "openai",
            "model_id": "gpt-test",
            "display_name": "openai gpt-test",
            "model_version_or_snapshot": "gpt-test-2026-05-14",
            "release_timestamp": "2026-05-14T09:00:00Z",
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-04-01",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "provider-price-sheet-2026-05-14",
            "input_token_price": 0.25,
            "output_token_price": 1.0,
            "known_cutoff_publicity_caveats": [],
        }
    )
