# Hermes Agent Multi-Harness Adapter

The Hermes Agent track is a first-class community adapter path for running LegalForecastBench and Harvey LAB fixture tasks through a Hermes CLI, batch runner, API server, or Python-library entry point. It is not an official LegalForecastBench evaluation path, and its results publish only to community comparison surfaces.

The checked-in fixture manifest is at `examples/adapters/hermes-agent/adapter-manifest.json`. It uses `examples/adapters/fixture_bridge.py --profile hermes-agent`, runs with no network, and proves the adapter contract before a contributor points the manifest at a real Hermes runtime.

Run the fixture bridge conformance check:

```bash
uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/hermes-agent/adapter-manifest.json \
  --output-dir tmp/hermes-agent-conformance
```

A production Hermes bridge should isolate `HERMES_HOME` and profile state per run, then record public-safe provenance in each run result: Hermes version or commit, provider/runtime resolution, enabled toolsets, terminal backend, memory/session policy, MCP configuration, trajectory export reference and hash, and session export reference and hash.

Persistent memory must either be disabled/reset for benchmark runs or snapshotted and hashed as public provenance. Do not publish provider account identifiers, API keys, raw transcripts, private matter materials, sealed materials, or official LegalForecastBench infrastructure details.

The fixture bridge supports both `legalforecast_mtd` and `harvey_lab` conformance fixtures. A real bridge may initially use the same command-manifest shape and translate each `RunRequest` into the selected Hermes entry point.
