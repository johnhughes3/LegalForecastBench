# Model Release-Date Verification — 2026-07-03

Six independent research sessions verified the model-release anchors recorded in `MODEL_RELEASE_DATES.md` and the checked-in pilot registry (`model_registries/pilot-2026-04-24_to_2026-05-18.json`). This document records each finding, the availability evidence used to establish first documented external deployment, whether an immutable pinned snapshot ID exists, and the source URLs.

**Anchor definition.** The original 2026-07-03 review used ordinary-developer public API availability. On 2026-07-11 the project adopted the more directly relevant contamination rule: the anchor is the first documented external deployment of the evaluated model, including a restricted API preview. First deployment establishes that the model artifact existed by that date; delayed general availability or a temporary suspension does not imply that later court decisions entered its training data. Provider-stated knowledge cutoffs are informative and generally much earlier, but they are not the eligibility anchor because their definitions and auditability vary. First documented external deployment is the deliberately conservative, independently observable rule. Announcement-only and waitlist-only dates remain insufficient.

## Summary

| Registry key | Verdict | First documented external deployment date | Pinned snapshot ID | Applied |
| --- | --- | --- | --- | --- |
| `openai:gpt-5.4-mini` | Confirmed | 2026-03-17 | `gpt-5.4-mini-2026-03-17` | No change needed (already correct) |
| `anthropic:claude-sonnet-4-6` | Confirmed | 2026-02-17 | dateless ID is the snapshot | No change needed (already correct) |
| `google:gemini-3-flash-preview` | Corrected (date sourced) | 2025-12-17 | **none — mutable preview ID** | Date/source updated; stays excluded |
| `openai:gpt-5.6` (Sol/Terra/Luna) | Confirmed first external deployment | 2026-06-26 | verify exact runnable snapshot before inclusion | Date confirmed; not yet in runnable registry |
| `anthropic/fable:fable-5` | Confirmed | 2026-06-09 | `claude-fable-5` (dateless-pinned) | Source upgraded to primary |
| `anthropic:claude-sonnet-5` | Confirmed | 2026-06-30 | `claude-sonnet-5` (dateless-pinned) | Source upgraded to primary |

No pilot-registry (`*.json`) date required correction: both anchored pilot models were confirmed at their existing dates, so no `release_timestamp` value was rewritten and no circular sourcing was introduced.

---

## 1. `openai:gpt-5.4-mini` — CONFIRMED (2026-03-17)

- **Verified public-API date:** 2026-03-17. Every source agrees the model was announced and made callable in the API (and Codex and ChatGPT) on the same day; there is no separate waitlist/preview date to reconcile.
- **Pinned snapshot:** `gpt-5.4-mini-2026-03-17` (a dated snapshot exists alongside the rolling `gpt-5.4-mini` alias).
- **Registry impact:** none. The pilot JSON already carries `2026-03-17T00:00:00Z` with a primary-source citation. The report specifically checked the earlier-version `2026-04-24` date and found it belongs to **GPT-5.5** (a different model in the same changelog), not GPT-5.4-mini — that mis-attribution had already been corrected in the checked-in registry.
- **Sources:**
  - https://developers.openai.com/api/docs/changelog
  - https://openai.com/index/introducing-gpt-5-4-mini-and-nano/
  - https://developers.openai.com/api/docs/models/gpt-5.4-mini
  - https://9to5mac.com/2026/03/17/openai-releases-gpt-5-4-mini-and-nano-its-most-capable-small-models-yet/

## 2. `anthropic:claude-sonnet-4-6` — CONFIRMED (2026-02-17)

- **Verified public-API date:** 2026-02-17. Announcement post and independent press (CNBC) agree; the model was available via the Claude API immediately, with no waitlist/preview window.
- **Pinned snapshot:** none separate. Per Anthropic's versioning docs, from the Claude 4.6 generation onward the dateless ID (`claude-sonnet-4-6`) **is itself** the pinned snapshot, not an evergreen alias. There is therefore no `-YYYYMMDD`-suffixed ID to report.
- **Registry impact:** none. The pilot JSON already carries `2026-02-17T00:00:00Z` with a primary-source citation.
- **Sources:**
  - https://www.anthropic.com/news/claude-sonnet-4-6
  - https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions
  - https://www.cnbc.com/2026/02/17/anthropic-ai-claude-sonnet-4-6-default-free-pro.html

## 3. `google:gemini-3-flash-preview` — CORRECTED date, but NOT eligible for re-inclusion (2025-12-17)

- **Verified public-API date:** 2025-12-17. Google's blog post states the model was "available now in preview via the Gemini API" that day; corroborated by the Gemini API changelog and contemporaneous press. This is genuine same-day public API access, not a waitlist.
- **Pinned snapshot:** **NONE.** Only the mutable `gemini-3-flash-preview` ID exists — no `gemini-3-flash-preview-MM-DD` immutable alias. The report confirms the ID is mutable *in practice*: the `gemini-flash-latest` alias was repointed to it on 2026-01-21 and Computer Use support was added to the same ID on 2026-01-29. Any anchored run pinned to this ID is exposed to silent behavior drift.
- **Re-inclusion eligibility (task item 3):** re-inclusion requires **both** a sourced date **and** a pinned snapshot. This model now has a source-backed date but still has **no immutable snapshot**, so it **remains ineligible** for the anchored registry. `MODEL_RELEASE_DATES.md` is updated to reflect that the date is now confirmed via primary sources while the exclusion stands. Re-adding it to the pilot registry is a John decision and was **not** performed.
- **Knowledge cutoff (do not conflate):** documented separately as January 2025 on the model card — a different field from release/availability date.
- **Sources:**
  - https://blog.google/products/gemini/gemini-3-flash/
  - https://ai.google.dev/gemini-api/docs/changelog
  - https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview
  - https://techcrunch.com/2025/12/17/google-launches-gemini-3-flash-makes-it-the-default-model-in-the-gemini-app/
  - https://simonwillison.net/2025/Dec/17/gemini-3-flash/

## 4. `openai:gpt-5.6` (Sol / Terra / Luna) — CONFIRMED first external deployment (2026-06-26)

- **What 2026-06-26 actually is:** the date OpenAI announced a **restricted** preview of GPT-5.6 Sol/Terra/Luna. On that date — and still as of 2026-07-03 — API and Codex access is limited to roughly 20 government-vetted partner organizations at the U.S. government's request (tied to a White House-directed pre-release safety/cybersecurity review). The models are **not** in ChatGPT and **not** callable by ordinary developers.
- **First external deployment date:** 2026-06-26. Restricted partners could use the models through the API and Codex, establishing that the deployed model artifacts existed by that date. OpenAI subsequently made the same named family generally available on 2026-07-09; that expansion of access does not move the contamination anchor.
- **Pinned snapshot:** none. API names are reportedly `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna` (undated preview aliases per secondary reporting of the system card); no dated snapshot IDs found.
- **Registry impact:** `2026-06-26` is the confirmed release anchor under the first-external-deployment rule. The models remain outside a runnable registry until their exact callable identities and snapshot stability are recorded.
- **Sources:**
  - https://openai.com/index/previewing-gpt-5-6-sol/
  - https://help.openai.com/en/articles/20001325-a-preview-of-gpt-56-sol-terra-and-luna
  - https://techcrunch.com/2026/06/26/openai-limits-gpt-5-6-rollout-after-government-request-says-restrictions-shouldnt-be-the-norm/
  - https://www.engadget.com/2203102/openai-starts-previewing-gpt-56-and-its-three-variants/
  - https://venturebeat.com/technology/openai-unveils-gpt-5-6-sol-terra-and-luna-models-but-only-accessible-to-limited-preview-partners-for-now-per-us-gov
  - https://www.axios.com/2026/06/26/openai-gpt-sol-terra-luna-trump
  - https://deploymentsafety.openai.com/gpt-5-6-preview

## 5. `anthropic/fable:fable-5` — CONFIRMED (2026-06-09)

- **Verified public-API date:** 2026-06-09. Anthropic's docs state Fable 5 became "generally available on the Claude API, Claude Platform on AWS, Amazon Bedrock, Google Cloud, and Microsoft Foundry" that day — genuine public GA, not a preview.
- **Pinned snapshot:** `claude-fable-5` (dateless ID is the pinned snapshot per the 4.6-generation-onward convention).
- **Availability caveat (does not move the anchor):** U.S. export controls forced Anthropic to suspend all access to Fable 5 / Mythos 5 from ~2026-06-12 until 2026-07-01. First public availability remains 2026-06-09, so the contamination anchor is unchanged, but continuous availability was interrupted — relevant only if a cycle also cares about reproducibility continuity.
- **Sibling note:** Claude Mythos 5 (`claude-mythos-5`) is **not** generally available (limited to Project Glasswing partners). A documented limited external deployment could establish an anchor if its exact date and evaluated artifact were verified; lack of public GA alone is not disqualifying under the current rule.
- **Registry impact:** not in any registry; the `MODEL_RELEASE_DATES.md` source citation is upgraded from the user-supplied anchor to Anthropic's primary announcement.
- **Sources:**
  - https://www.anthropic.com/news/claude-fable-5-mythos-5
  - https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5
  - https://www.anthropic.com/news/redeploying-fable-5
  - https://techcrunch.com/2026/06/09/anthropic-released-claude-fable-5-its-most-powerful-model-publicly-days-after-warning-ai-is-getting-too-dangerous/
  - https://github.blog/changelog/2026-06-09-claude-fable-5-is-generally-available-for-github-copilot/

## 6. `anthropic:claude-sonnet-5` — CONFIRMED (2026-06-30)

- **Verified public-API date:** 2026-06-30. Announcement and system card (both dated that day) state "From today, Claude Sonnet 5 is available across all plans... via the Claude API, Claude Code, and the Claude Platform." No waitlist or staged rollout.
- **Pinned snapshot:** `claude-sonnet-5` (dateless ID is the pinned snapshot). AWS Bedrock ID is `anthropic.claude-sonnet-53`; Google Cloud ID is `claude-sonnet-5`.
- **Registry impact:** not in any registry; the `MODEL_RELEASE_DATES.md` source citation is upgraded from the user-supplied anchor to Anthropic's primary announcement.
- **Sources:**
  - https://www.anthropic.com/news/claude-sonnet-5
  - https://platform.claude.com/docs/en/about-claude/models/overview
  - https://www.anthropic.com/claude-sonnet-5-system-card
  - https://www.testingcatalog.com/anthropic-launches-claude-sonnet-5-model-on-claude-and-apis/

---

## Actions taken

- **Pilot registry (`model_registries/pilot-2026-04-24_to_2026-05-18.json`):** no change. Both anchored models were confirmed at their existing dates with existing primary-source citations. No `release_timestamp` was rewritten, so no circular sourcing was introduced (V2-8 remains satisfied).
- **`MODEL_RELEASE_DATES.md`:**
  - Pilot table: added a note recording independent verification on 2026-07-03 (dates unchanged).
  - Gemini 3 Flash Preview: date `2025-12-17` re-cited to primary sources; exclusion retained and re-inclusion ineligibility (no pinned snapshot) made explicit.
  - GPT-5.6 Sol/Terra/Luna: originally relabeled as unverified on 2026-07-03; superseded on 2026-07-11 by the first-external-deployment rule and confirmed at 2026-06-26.
  - Fable 5 and Claude Sonnet 5: source citations upgraded to primary Anthropic announcements; pinned-snapshot IDs recorded.

## Unverifiable / open items

- **GPT-5.6 (all three variants):** the date is confirmed at first external deployment. Exact runnable snapshot identity remains to be verified before adding the family to an official registry.
- **Gemini 3 Flash Preview:** date is verified, but the absence of an immutable snapshot means any anchored run would be exposed to silent endpoint drift. Blocked from re-inclusion on snapshot grounds, not date grounds.
