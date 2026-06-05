# OpenClaw Multi-Harness Adapter

The OpenClaw track is a first-class community adapter path for running LegalForecastBench and Harvey LAB fixture tasks through OpenClaw's harness/plugin model. It is not an official LegalForecastBench evaluation path, and its results publish only to community comparison surfaces.

The checked-in fixture manifest is at `examples/adapters/openclaw/adapter-manifest.json`. It uses `examples/adapters/fixture_bridge.py --profile openclaw`, runs with no network, and proves the adapter contract before a contributor points the manifest at a real OpenClaw runtime or trusted native harness plugin.

Run the fixture bridge conformance check:

```bash
uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/openclaw/adapter-manifest.json \
  --output-dir tmp/openclaw-conformance
```

A production OpenClaw bridge should record public-safe provenance in each run result: OpenClaw version or commit, provider/model route, harness ID, runtime-plan policy, tool policy, transcript mirror behavior, selected native runtime, and fail-closed proof when a requested harness is unavailable.

OpenClaw core should remain responsible for provider/model/auth/tool policy and workspace state. The LegalForecastBench adapter should execute a prepared turn and normalize only public-safe result metadata into `RunResult`.

Do not publish provider account identifiers, API keys, raw transcripts, private matter materials, sealed materials, or official LegalForecastBench infrastructure details.
