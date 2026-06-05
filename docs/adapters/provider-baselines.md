# Provider Runtime Baseline Adapters

The provider/runtime baseline tracks give community users reference points for interpreting LQ.AI, Hermes Agent, OpenClaw, and other harness comparisons. They are not official LegalForecastBench evaluation paths, and their results publish only to community comparison surfaces.

The checked-in fixture manifests are:

- `examples/adapters/openai-responses/adapter-manifest.json`
- `examples/adapters/claude-agent-sdk/adapter-manifest.json`

Both manifests use `examples/adapters/fixture_bridge.py`, run with no network, and prove the adapter contract before a contributor points a manifest at a real provider runtime.

Run the fixture bridge conformance checks:

```bash
uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/openai-responses/adapter-manifest.json \
  --output-dir tmp/openai-responses-conformance

uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/claude-agent-sdk/adapter-manifest.json \
  --output-dir tmp/claude-agent-sdk-conformance
```

Production provider baseline bridges should use API-key auth or another explicit provider-supported API auth mechanism. Do not claim that a ChatGPT, Claude, or similar subscription login is a general third-party API entitlement.

Each result should record public-safe provenance: provider route, model route, runtime style, agent-loop style, auth mode, provider terms assumption, and whether any subscription-login claim was made. Public artifacts must not include provider account identifiers, API keys, raw transcripts, private matter materials, sealed materials, or official LegalForecastBench infrastructure details.
