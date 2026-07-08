# Current Pilot Model Anchors

Model anchors for the current checked-in pilot registry and benchmark workflow defaults. This file follows repo-local registry truth; it is not a live catalog of every frontier-model release.

| Provider | Model | Registry key | Release timestamp | Source |
| --- | --- | --- | --- | --- |
| Google | Gemini 3 Flash Preview | `google:gemini-3-flash-preview` | Not disclosed in registry | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |
| OpenAI | GPT-5.4 mini | `openai:gpt-5.4-mini` | 2026-04-24T00:00:00Z | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |
| Anthropic | Claude Sonnet 4.6 | `anthropic:claude-sonnet-4-6` | 2026-02-17T00:00:00Z | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |

The GitHub Actions benchmark workflow currently defaults to the same three registry keys in `.github/workflows/run-benchmark.yaml`.
