from datetime import date
from pathlib import Path

from legalforecast.evals.model_registry import load_model_registry
from legalforecast.reporting.contamination_tiers import classify_registry_entry
from legalforecast.runner.gateway import gateway_request_extra_body


def test_grok47_month_cutoff_is_eligible_under_reported_cutoff_rule() -> None:
    registry = load_model_registry(
        Path("model_registries/cycle-1-official-grok-4.7-gateway-2026-09-21.json")
    )
    entry = registry.entries[0]
    assert entry.model_id == "spacexai/grok-4.7"
    assert entry.tool_policy.value == "controlled_docket_tool_only"
    assert entry.network_disabled and entry.search_disabled
    assert gateway_request_extra_body(entry.model_id) == {
        "providerOptions": {"gateway": {"only": ["xai"]}}
    }
    assert entry.provider_training_cutoff is None
    assert entry.provider_training_cutoff_status.value == "unknown"
    assert "May 2026" in " ".join(entry.known_cutoff_publicity_caveats)
    assert (
        classify_registry_entry(
            entry, contamination_boundary=date(2026, 6, 30)
        ).tier.value
        # The frozen registry keeps the cutoff unknown; the maintained cutoff table
        # records May 2026, which precedes the June 30 first decision.
        == "contamination_resistant"
    )
