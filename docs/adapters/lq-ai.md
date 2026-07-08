# LQ.AI Multi-Harness Adapter

The LQ.AI track is a first-class community adapter path for running LegalForecastBench and Harvey LAB fixture tasks through a local or self-hosted LegalQuants LQ.AI deployment. It is not an official LegalForecastBench evaluation path, and its results publish only to community comparison surfaces.

The checked-in fixture manifest is at `examples/adapters/lq-ai/adapter-manifest.json`. It uses `examples/adapters/fixture_bridge.py --profile lq-ai`, runs with no network, and is intended to prove the adapter contract and conformance shape before a contributor points the manifest at a real LQ.AI gateway.

Run the fixture bridge conformance check:

```bash
uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/lq-ai/adapter-manifest.json \
  --output-dir tmp/lq-ai-conformance
```

A production LQ.AI bridge should keep provider calls in the host adapter process and record public-safe provenance in each run result: LQ.AI version or commit, gateway/API route, project or matter scope, inference tier, provider route, anonymization setting, citation-verification setting, audit-log correlation ID, skill/playbook context, auth mode, and provider terms assumption.

Do not publish provider account identifiers, API keys, raw transcripts, private matter materials, sealed materials, or official LegalForecastBench infrastructure details. Large public-safe artifacts should be referenced by immutable URL plus SHA-256 through the community submission manifest.

The fixture bridge supports both `legalforecast_mtd` and `harvey_lab` conformance fixtures. A real bridge may initially use the same command-manifest shape and translate each `RunRequest` into the local LQ.AI gateway/API route for the selected project or matter.
