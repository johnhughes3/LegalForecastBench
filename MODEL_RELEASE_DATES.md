# Model Release Dates

This file tracks the model-release anchors used or queued for LegalForecastBench benchmark cycles. The first table follows the current checked-in pilot registry and benchmark workflow defaults. The second table records additional release dates that are not yet full runnable registry entries.

## Current Pilot Registry

| Provider | Model | Registry key | Release timestamp | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.4 mini | `openai:gpt-5.4-mini` | 2026-03-17T00:00:00Z | OpenAI API changelog, Mar. 17, 2026 GPT-5.4 mini API release |
| Anthropic | Claude Sonnet 4.6 | `anthropic:claude-sonnet-4-6` | 2026-02-17T00:00:00Z | Anthropic launch post, Feb. 17, 2026 Claude Sonnet 4.6 launch |

Both anchored pilot dates were independently re-verified on 2026-07-03 against primary and press sources (see [docs/reviews/model-release-date-verification-2026-07-03.md](docs/reviews/model-release-date-verification-2026-07-03.md)) and confirmed unchanged. The verification also confirmed that the earlier `2026-04-24` date once attached to GPT-5.4 mini belongs to GPT-5.5, a different model; the checked-in registry already carries the correct `2026-03-17` anchor. GPT-5.4 mini offers a dated pinned snapshot (`gpt-5.4-mini-2026-03-17`); for Claude Sonnet 4.6 the dateless ID `claude-sonnet-4-6` is itself the pinned snapshot per Anthropic's 4.6-generation convention.

The GitHub Actions benchmark workflow currently defaults to the same two registry keys in `.github/workflows/run-benchmark.yaml`. Gemini 3 Flash Preview is excluded from the anchored pilot registry until a source-backed pinned snapshot convention is available; its release date is now confirmed as December 17, 2025 via primary sources, but Google still documents only the mutable `gemini-3-flash-preview` preview ID with no immutable snapshot alias, so it remains ineligible for re-inclusion on snapshot grounds (not date grounds).

### Filename Window Versus Computed Release Anchor

The registry **filename window** (for example `pilot-2026-04-24_to_2026-05-18.json`) names the case *collection window* — the date range of the disposition/labeling cohort for that cycle — and is not the model release anchor. The eligibility **anchor** used to gate contamination is computed at runtime from each registry entry's `release_timestamp` (plus a buffer), independent of the filename. The two can legitimately diverge: after GPT-5.4 mini's sourced release date was corrected to 2026-03-17, its computed anchor (2026-03-19 with buffer) falls earlier than the `2026-04-24` filename window. That is expected and carries no contamination risk — an earlier true release only widens the window in which a case's decision post-dates the model, and the checked-in manifests already use the later collection window — but the filename should be read as the collection window, never as the release anchor. John should spot-check the two `release_timestamp_source` URLs in the pilot registry, since those citations were authored by agents.

## Additional Tracked Release Dates

These anchors are recorded for future cycle planning. They are not yet active workflow defaults and do not have complete checked-in registry entries. All entries below were verified on 2026-07-03; see [docs/reviews/model-release-date-verification-2026-07-03.md](docs/reviews/model-release-date-verification-2026-07-03.md) for per-model verdicts, pinned-snapshot availability, and full source lists.

| Provider or family | Model | Release timestamp | Registry status | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.6 Sol | UNVERIFIED (no public-API GA) | Unverifiable anchor — do not use 2026-06-26 | Restricted government-partner preview only as of 2026-07-03, not public API availability; https://openai.com/index/previewing-gpt-5-6-sol/ |
| OpenAI | GPT-5.6 Terra | UNVERIFIED (no public-API GA) | Unverifiable anchor — do not use 2026-06-26 | Restricted government-partner preview only as of 2026-07-03, not public API availability; https://openai.com/index/previewing-gpt-5-6-sol/ |
| OpenAI | GPT-5.6 Luna | UNVERIFIED (no public-API GA) | Unverifiable anchor — do not use 2026-06-26 | Restricted government-partner preview only as of 2026-07-03, not public API availability; https://openai.com/index/previewing-gpt-5-6-sol/ |
| Google | Gemini 3 Flash Preview | 2025-12-17T00:00:00Z (confirmed) | Excluded from anchored registry — date confirmed but no immutable snapshot ID exists (mutable `gemini-3-flash-preview` only); ineligible for re-inclusion on snapshot grounds | Google blog + Gemini API changelog, Dec. 17, 2025 public preview release; https://blog.google/products/gemini/gemini-3-flash/ |
| Fable | Fable 5 | 2026-06-09T00:00:00Z (confirmed) | Not yet in registry — pinned snapshot `claude-fable-5`; access suspended ~2026-06-12 to 2026-06-30 by export controls (anchor unchanged) | Anthropic launch post, June 9, 2026 Claude Fable 5 GA; https://www.anthropic.com/news/claude-fable-5-mythos-5 |
| Anthropic | Claude Sonnet 5 | 2026-06-30T00:00:00Z (confirmed) | Not yet in registry — pinned snapshot `claude-sonnet-5` | Anthropic launch post, June 30, 2026 Claude Sonnet 5 GA; https://www.anthropic.com/news/claude-sonnet-5 |
