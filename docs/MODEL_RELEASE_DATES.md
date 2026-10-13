# Model Release Dates

This file records the model identities, release dates, and provider-reported cutoffs behind the Cycle 1 comparisons. The maintained eligibility evidence is [`legalforecast/data/model_cutoffs.json`](../legalforecast/data/model_cutoffs.json); each frozen registry under [`model_registries/`](../model_registries/) carries its own source fields. See [methods](METHODS.md) for the eligibility rule.

## September 2026 comparisons

The repaired 91-case release contains decisions dated June 30 through August 7, 2026. New model comparisons reuse those cases and labels. Official comparison eligibility follows the provider-reported training-data or knowledge cutoff (owner rule, clarified September 28, 2026), rather than public release date; the evidence table is `legalforecast/data/model_cutoffs.json`, and see [methods](METHODS.md). Release dates and historical post-anchor assignments remain provenance metadata. Neither a provider cutoff nor a stable API ID is an independent guarantee about training data or unchanged weights.

[Gemini 3.8 Flash](../model_registries/cycle-1-official-gemini-3.8-flash-2026-09-08.json) uses the stable `google:gemini-3.8-flash` ID, high thinking, document tools, and a 65,536-token output limit. Google reports a [March 2026 knowledge cutoff](https://deepmind.google/models/model-cards/gemini-3-8-flash/) and [September 2, 2026 release](https://ai.google.dev/gemini-api/docs/changelog). The cutoff is month-granular; the registry does not invent an exact day. The registry records the introductory pricing expiration and stable-ID limitation.

The [additional comparison registry](../model_registries/cycle-1-official-held-models-2026-09-08.json) records the following configurations. Registration does not establish live runtime readiness or authorize execution.

| Model | Provider-reported cutoff | Comparison qualification |
| --- | --- | --- |
| GPT-6 Astra | April 30, 2026 | Predates all 91 decisions; [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra). |
| Claude Opus 5 | May 2026 | Predates all 91 decisions; exact day undisclosed; [Anthropic model documentation](https://platform.claude.com/docs/en/models/overview). |
| Claude Fable 5.1 | June 2026 | Month-only cutoff, compared as June 1, 2026 under the September 28 rule, which precedes the earliest June 30 decision, so eligible; exact day undisclosed; [Anthropic model documentation](https://platform.claude.com/docs/en/models/fable-5-1/overview). |
| Kimi K3 | Unknown | Reuses the existing DeepInfra configuration and its probe requirements; no verified cutoff claim. |
| Muse Spark 1.3 | Unknown | Future runs use the [standard-tier Gateway registry](../model_registries/cycle-1-official-muse-spark-1.3-standard-2026-09-08.json). The contributor-tier run completed; standard-tier execution is not yet measured. [Meta announcement](https://research.meta.ai/blog/introducing-muse-spark-1-3). |

[Grok 4.7](../model_registries/cycle-1-official-grok-4.7-gateway-2026-09-21.json) is an official post-anchor candidate using the ordinary Gateway document-tool condition. [xAI reports a May 2026 knowledge cutoff](https://docs.x.ai/developers/grok-4-7) and a [September 21 release](https://x.ai/news/grok-4-7). May precedes the documented cohort window, so Grok 4.7 is eligible under the reported-cutoff rule; the frozen registry still preserves month precision. It has since been run and scored on the Cycle 1 release (forecast run 35799524684, scoring run 35885175070). This entry does not change the Grok 4.6-to-Jev summary experiment.

The September 30, 2026 comparison adds two full-document agentic runs with high reasoning. [GPT-6.1 Sol](../model_registries/cycle-1-agentic-gpt-6.1-sol-high-2026-09-29.json) uses `gpt-6.1-sol`. OpenAI reports an April 30, 2026 knowledge cutoff, which precedes the cohort, so the configuration is eligible. The registry release timestamp is the September 29, 2026 model-page observation date, not a separately verified launch announcement. [Claude Sonnet 5.5](../model_registries/cycle-1-agentic-claude-sonnet-5-5-high-2026-09-29.json) uses `claude-sonnet-5-5`, released September 28, 2026, with high effort pinned. Anthropic reports a June 2026 training cutoff, compared as June 1 under the maintained rule, which also precedes the cohort. Forecast runs are 36673524599 and 36673527185; scoring runs are 36741462923 and 36741468019.

The September 24, 2026 comparison adds one explicit exception for Google's `gemini-3.1-pro-preview`, which has no documented dated snapshot. It runs as **Gemini 3.1 Pro Preview**, with high thinking and the full agentic document-tool harness. The frozen registry retains the preview alias and the run records the served version; neither is a claim that the underlying weights are immutable. This exception does not admit other preview or latest aliases or change the collection registry. Google's reported January 2025 knowledge cutoff predates the cohort, so the configuration is eligible under the reported-cutoff rule. See the [model specifications](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) and [Gemini 3 guide](https://ai.google.dev/gemini-api/docs/gemini-3).

## Cycle 1 Late-June Registry

The frozen collection registry is [`model_registries/cycle-1-2026-06-30.json`](../model_registries/cycle-1-2026-06-30.json). Its latest first documented external deployment is Claude Sonnet 5 on June 30, 2026, which supplied the original collection boundary of `2026-06-30` UTC; the current training-cutoff reporting rule does not change the frozen cohort. The June 26 restricted GPT-5.6 API and Codex preview is the first external deployment of the same named Sol, Terra, and Luna family that became generally available on July 9; general availability does not move the contamination anchor.

| Provider | Model | Registry key | Frozen model ID | Release timestamp | Standard input/output price per MTok at registry freeze |
| --- | --- | --- | --- | --- | --- |
| OpenAI | GPT-5.6 Sol | `openai:gpt-5.6-sol` | `gpt-5.6-sol` | `2026-06-26T00:00:00Z` | $5 / $30 |
| OpenAI | GPT-5.6 Terra | `openai:gpt-5.6-terra` | `gpt-5.6-terra` | `2026-06-26T00:00:00Z` | $2.50 / $15 |
| OpenAI | GPT-5.6 Luna | `openai:gpt-5.6-luna` | `gpt-5.6-luna` | `2026-06-26T00:00:00Z` | $1 / $6 |
| Anthropic | Claude Sonnet 5 | `anthropic:claude-sonnet-5` | `claude-sonnet-5` | `2026-06-30T00:00:00Z` | $2 / $10 introductory pricing through Aug. 31, 2026 |

OpenAI's official model pages currently list each tier-specific callable ID in that model's **Snapshots** section, whose stated purpose is to lock a model version so behavior remains consistent. No separate dated GPT-5.6 snapshot is exposed. Cycle 1 therefore freezes the tier-specific IDs exactly as those official pages present them and deliberately does not use the `gpt-5.6` family alias, which OpenAI documents as routing to Sol. This is a provider-documentation-backed identity decision, not a claim that an unlisted dated ID exists; a future cycle must re-verify the pages rather than assume the convention persists.

The OpenAI scalar prices are the standard rates for prompts through 272K input tokens; longer prompts are billed at twice the input rate and 1.5 times the output rate. Claude Sonnet 5's introductory $2/$10 rates change to $3/$15 on September 1, 2026. These limitations are repeated in each registry entry's pricing provenance and caveats so a later dispatch cannot silently treat the scalar prices as universal. OpenAI reports a February 16, 2026 knowledge cutoff. Anthropic reports only a month-level January 2026 training-data cutoff, so the registry records the exact-date field as unknown rather than inventing a day.

Primary sources: OpenAI's [GPT-5.6 preview announcement](https://openai.com/index/previewing-gpt-5-6-sol/) and model pages for [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), and [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna); Anthropic's [Claude Sonnet 5 launch](https://www.anthropic.com/news/claude-sonnet-5), [model-versioning documentation](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions), and [pricing documentation](https://platform.claude.com/docs/en/about-claude/pricing). All registry values were checked on July 11, 2026.

## Label-generation models

The models that built the Cycle 1 ground truth are frozen separately in [`model_registries/cycle-1-labeling-2026-07-12.json`](../model_registries/cycle-1-labeling-2026-07-12.json) and [`model_registries/cycle-1-stage-b-judges-2026-07-12.json`](../model_registries/cycle-1-stage-b-judges-2026-07-12.json) (Claude Sonnet 4.6, GPT-5.4 mini, and Gemini 3.5 Flash). They are not candidate models, and the label construction process is owned by the companion LegalForecastCorpus repository.
