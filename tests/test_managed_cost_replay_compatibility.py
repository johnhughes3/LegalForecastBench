"""Retain costs and wire fields from the runner before cost-evidence metadata."""

from dataclasses import replace

import pytest
from legalforecast.runner.managed_cost import ManagedResponseUsage
from legalforecast.runner.managed_execution import ManagedToolAgentResult
from legalforecast.runner.managed_transcript_recovery import (
    _legacy_managed_replay_payload,
    _prior_managed_replay_payload,
)
from tests.test_managed_transcript_recovery import (
    _anthropic_entry,
    _entry,
    _gateway_entry,
    _gateway_metadata,
)


@pytest.mark.parametrize("provider", ["google", "anthropic", "gateway"])
def test_pre_evidence_payload_preserves_original_cost_and_gateway_field(
    provider: str,
) -> None:
    entry = {
        "google": _entry,
        "anthropic": _anthropic_entry,
        "gateway": _gateway_entry,
    }[provider]()
    metadata = (_gateway_metadata(),) if provider == "gateway" else ()
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="standard",
        called_tools=("read",),
        response_usages=((1000, 200),),
        gateway_response_metadata=metadata,
        response_usage_details=(ManagedResponseUsage(1000, 200, 400, 100),),
        response_cache_usages=((400, 100),) if provider == "anthropic" else (),
    )
    payload = _prior_managed_replay_payload(result, entry=entry)
    assert payload["gateway_response_metadata"] == list(metadata)
    assert "response_usage_details" not in payload
    assert "cost_basis" not in payload
    if provider == "anthropic":
        assert payload["estimated_cost_usd"] == pytest.approx(0.01635)
        assert "anthropic_cache_evidence" in payload
    elif provider == "gateway":
        assert payload["estimated_cost_usd"] == float(metadata[0]["cost_usd"])
    else:
        assert payload["estimated_cost_usd"] == pytest.approx(0.0022)
        legacy = _legacy_managed_replay_payload(result, entry=entry)
        assert legacy is not None
        assert "gateway_response_metadata" not in legacy
        assert "response_usage_details" not in legacy
        assert legacy["estimated_cost_usd"] == payload["estimated_cost_usd"]


def test_pre_evidence_anthropic_zero_defaults_remain_a_compatibility_projection() -> (
    None
):
    entry = _anthropic_entry()
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="unreported",
        called_tools=("read",),
        response_usages=((1000, 200),),
        response_usage_details=(ManagedResponseUsage(1000, 200),),
    )
    payload = _prior_managed_replay_payload(result, entry=entry)
    assert payload == _prior_managed_replay_payload(
        replace(result, response_cache_usages=((0, 0),)), entry=entry
    )
    assert result.response_usage_details[0].cache_read_tokens is None
    assert payload["estimated_cost_usd"] == pytest.approx(0.02)


def test_pre_cache_anthropic_payload_accepts_unknown_zero_defaults() -> None:
    entry = _anthropic_entry()
    result = ManagedToolAgentResult(
        raw_output="{}",
        request_count=1,
        input_tokens=1000,
        output_tokens=200,
        served_model=entry.model_version_or_snapshot,
        finish_reason="stop",
        service_tier="unreported",
        called_tools=("read",),
        response_usages=((1000, 200),),
        response_usage_details=(ManagedResponseUsage(1000, 200),),
    )
    legacy = _legacy_managed_replay_payload(result, entry=entry)
    assert legacy is not None
    assert "anthropic_cache_evidence" not in legacy
    assert "response_usage_details" not in legacy
    assert legacy["estimated_cost_usd"] == pytest.approx(0.02)
    assert (
        _legacy_managed_replay_payload(
            replace(
                result, response_usage_details=(ManagedResponseUsage(1000, 200, 20),)
            ),
            entry=entry,
        )
        is None
    )
