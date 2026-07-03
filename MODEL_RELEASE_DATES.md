# Model Release Dates

This file tracks the model-release anchors used or queued for LegalForecastBench benchmark cycles. The first table follows the current checked-in pilot registry and benchmark workflow defaults. The second table records additional release dates that are not yet full runnable registry entries.

## Current Pilot Registry

| Provider | Model | Registry key | Release timestamp | Source |
| --- | --- | --- | --- | --- |
| Google | Gemini 3 Flash Preview | `google:gemini-3-flash-preview` | 2026-04-24T00:00:00Z | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |
| OpenAI | GPT-5.4 mini | `openai:gpt-5.4-mini` | 2026-04-24T00:00:00Z | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |
| Anthropic | Claude Sonnet 4.6 | `anthropic:claude-sonnet-4-6` | 2026-02-17T00:00:00Z | `model_registries/pilot-2026-04-24_to_2026-05-18.json` |

The GitHub Actions benchmark workflow currently defaults to the same three registry keys in `.github/workflows/run-benchmark.yaml`.

## Additional Tracked Release Dates

These anchors are recorded for future cycle planning. They are not yet active workflow defaults and do not have complete checked-in registry entries.

| Provider or family | Model | Release timestamp | Registry status | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.6 Sol | 2026-06-26T00:00:00Z | Not yet in registry | User-supplied release-date anchor, 2026-07-03 |
| OpenAI | GPT-5.6 Terra | 2026-06-26T00:00:00Z | Not yet in registry | User-supplied release-date anchor, 2026-07-03 |
| OpenAI | GPT-5.6 Luna | 2026-06-26T00:00:00Z | Not yet in registry | User-supplied release-date anchor, 2026-07-03 |
| Fable | Fable 5 | 2026-06-09T00:00:00Z | Not yet in registry | User-supplied release-date anchor, 2026-07-03 |
| Anthropic | Claude Sonnet 5 | 2026-06-30T00:00:00Z | Not yet in registry | User-supplied release-date anchor, 2026-07-03 |
