# LegalForecast-MTD Run Card Template

Run cards are machine-readable JSON artifacts for one model/run condition in a
cycle. They should be generated from the frozen model registry, run accounting
records, and freeze bundle, then validated before publication.

Canonical schema: `docs/run_card_schema.json`

Validation helper: `legalforecast.publication.run_cards.validate_run_card_record`

## Minimal Shape

```json
{
  "schema_version": "legalforecast.run_card.v1",
  "run": {
    "run_id": "cycle-2026-rapid-001/example-provider:example-model/full_packet",
    "cycle_id": "cycle-2026-rapid-001",
    "run_type": "rapid",
    "generated_at": "2026-05-14T18:30:00Z",
    "evaluation_timestamp": "2026-05-14T18:00:00Z",
    "harness_version": "sha256:...",
    "run_label": "full_packet",
    "limitations": []
  },
  "model": {
    "provider": "example-provider",
    "model_id": "example-model",
    "display_name": "Example Model",
    "model_version_or_snapshot": "2026-05-14",
    "release_timestamp": "2026-05-14T09:00:00Z",
    "provider_training_cutoff_status": "known",
    "provider_training_cutoff": "2026-04-01",
    "network_disabled": true,
    "search_disabled": true,
    "tool_policy": "controlled_docket_tool_only",
    "context_limit": 200000,
    "known_cutoff_publicity_caveats": []
  },
  "sampling": {
    "temperature": 0,
    "top_p": 1,
    "max_output_tokens": 4096
  },
  "policy": {
    "network_disabled": true,
    "search_disabled": true,
    "tool_policy": "controlled_docket_tool_only",
    "tool_call_cap": 10
  },
  "pricing": {
    "pricing_source": "provider-price-sheet-2026-05-14",
    "input_token_price": 0.25,
    "output_token_price": 1.0,
    "price_unit": "usd_per_1m_tokens"
  },
  "hashes": {
    "prompt_sha256": "sha256:...",
    "scorer_sha256": "sha256:...",
    "model_registry_sha256": "sha256:...",
    "manifest_sha256": "sha256:...",
    "prediction_unit_sha256": "sha256:...",
    "label_sha256": "sha256:..."
  },
  "accounting_summary": {
    "case_count": 150,
    "prediction_unit_count": 420,
    "request_count": 150,
    "prompt_tokens": 1000000,
    "completion_tokens": 120000,
    "total_tokens": 1120000,
    "mean_tool_calls_per_case": 2.1,
    "median_tool_calls_per_case": 2,
    "p95_tool_calls_per_case": 7,
    "cost_per_case": 0.18,
    "cost_per_prediction_unit": 0.064,
    "mean_latency_ms": 3500,
    "p95_latency_ms": 9000,
    "invalid_output_rate": 0,
    "refusal_rate": 0,
    "content_filter_rate": 0
  },
  "notes": []
}
```

## Publication Rule

Every official or rapid run should publish one validated run card per
model/run condition. Missing required fields, absent known cutoff dates,
disabled-policy mismatches, invalid hash formats, or out-of-range rates should
block publication until corrected.

Only official results are canonical for the leaderboard. A run card supports
publication, but it does not by itself make a community submission official.
Community-submitted run cards remain community-unverified until a maintainer or
trusted operator independently reproduces the run against the same frozen
artifacts. See `docs/result_tiers.md` for the full result-tier policy.
