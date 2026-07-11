# Model Release Dates

This file tracks the model-release anchors used or queued for LegalForecastBench benchmark cycles. The first table follows the current checked-in pilot registry and benchmark workflow defaults. The second table records additional release dates that are not yet full runnable registry entries.

## Current Pilot Registry

| Provider | Model | Registry key | Release timestamp | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.4 mini | `openai:gpt-5.4-mini` | 2026-03-17T00:00:00Z | OpenAI API changelog, Mar. 17, 2026 GPT-5.4 mini API release |
| Anthropic | Claude Sonnet 4.6 | `anthropic:claude-sonnet-4-6` | 2026-02-17T00:00:00Z | Anthropic launch post, Feb. 17, 2026 Claude Sonnet 4.6 launch |

Both anchored pilot dates were independently re-verified on 2026-07-03 against primary and press sources (full evidence record: `docs/reviews/model-release-date-verification-2026-07-03.md` in git history) and confirmed unchanged. The verification also confirmed that the earlier `2026-04-24` date once attached to GPT-5.4 mini belongs to GPT-5.5, a different model; the checked-in registry already carries the correct `2026-03-17` anchor. GPT-5.4 mini offers a dated pinned snapshot (`gpt-5.4-mini-2026-03-17`); for Claude Sonnet 4.6 the dateless ID `claude-sonnet-4-6` is itself the pinned snapshot per Anthropic's 4.6-generation convention.

The GitHub Actions benchmark workflow currently defaults to the same two registry keys in `.github/workflows/run-benchmark.yaml`. Gemini 3 Flash Preview is excluded from the anchored pilot registry until a source-backed pinned snapshot convention is available; its release date is now confirmed as December 17, 2025 via primary sources, but Google still documents only the mutable `gemini-3-flash-preview` preview ID with no immutable snapshot alias, so it remains ineligible for re-inclusion on snapshot grounds (not date grounds).

### Filename Window Versus Computed Release Anchor

The registry **filename window** (for example `pilot-2026-04-24_to_2026-05-18.json`) names the case *collection window* — the date range of the disposition/labeling cohort for that cycle — and is not the model release anchor. The eligibility **anchor** used to gate contamination is computed at runtime from each registry entry's `release_timestamp`, independent of the filename. `release_timestamp` means the first documented external deployment of the evaluated model, including a restricted external preview: deployment establishes that the model artifact existed by that date, which is the fact relevant to whether a later court decision could have appeared in its training data. Temporary suspension or delayed general availability does not move the anchor. Provider-stated knowledge cutoffs are informative and generally earlier, but their definitions and independent auditability vary; first documented external deployment is therefore the deliberately conservative rule. Cases are eligible on or after the UTC calendar date of that anchor. Because court-decision metadata is date-granular and the model artifact necessarily existed by first deployment, the benchmark does not add an arbitrary calendar-day buffer. The filename should be read as the collection window, never as the release anchor.

## Additional Tracked Release Dates

These anchors are recorded for future cycle planning. They are not yet active workflow defaults and do not have complete checked-in registry entries. The original review was completed on 2026-07-03 and the GPT-5.6 status was updated on 2026-07-11 after general availability confirmed the identity of the restricted-preview family; per-model evidence, pinned-snapshot availability, and full source lists are preserved in git history (`docs/reviews/model-release-date-verification-2026-07-03.md`) and in each registry entry's source fields.

| Provider or family | Model | Release timestamp | Registry status | Source |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.6 Sol | 2026-06-26T00:00:00Z (confirmed first external deployment) | Not yet in registry — verify exact runnable snapshot identity before inclusion | Restricted API and Codex preview began June 26; July 9 general availability did not move the contamination anchor; https://openai.com/index/previewing-gpt-5-6-sol/ |
| OpenAI | GPT-5.6 Terra | 2026-06-26T00:00:00Z (confirmed first external deployment) | Not yet in registry — verify exact runnable snapshot identity before inclusion | Restricted API and Codex preview began June 26; July 9 general availability did not move the contamination anchor; https://openai.com/index/previewing-gpt-5-6-sol/ |
| OpenAI | GPT-5.6 Luna | 2026-06-26T00:00:00Z (confirmed first external deployment) | Not yet in registry — verify exact runnable snapshot identity before inclusion | Restricted API and Codex preview began June 26; July 9 general availability did not move the contamination anchor; https://openai.com/index/previewing-gpt-5-6-sol/ |
| Google | Gemini 3 Flash Preview | 2025-12-17T00:00:00Z (confirmed) | Excluded from anchored registry — date confirmed but no immutable snapshot ID exists (mutable `gemini-3-flash-preview` only); ineligible for re-inclusion on snapshot grounds | Google blog + Gemini API changelog, Dec. 17, 2025 public preview release; https://blog.google/products/gemini/gemini-3-flash/ |
| Fable | Fable 5 | 2026-06-09T00:00:00Z (confirmed) | Not yet in registry — pinned snapshot `claude-fable-5`; access suspended ~2026-06-12 to 2026-06-30 by export controls (anchor unchanged) | Anthropic launch post, June 9, 2026 Claude Fable 5 GA; https://www.anthropic.com/news/claude-fable-5-mythos-5 |
| Anthropic | Claude Sonnet 5 | 2026-06-30T00:00:00Z (confirmed) | Not yet in registry — pinned snapshot `claude-sonnet-5` | Anthropic launch post, June 30, 2026 Claude Sonnet 5 GA; https://www.anthropic.com/news/claude-sonnet-5 |
