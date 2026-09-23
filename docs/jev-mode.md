# Jev one-shot condition

Jev receives one shared case record and one Boolean question for each original prediction unit. Its native probability of “yes” becomes `probability_fully_dismissed`. The target remains the actual first written disposition of the motion, with the same full-dismissal, partial-dismissal, and leave-to-amend rules used by the document-tool condition. The case selection, document selection, unit identifiers, and scoring labels remain unchanged.

This is a distinct official evaluation condition. Report it as **Jev (Luna summaries; one shot)**, **Jev (Grok 4.6 summaries; one shot)**, or **Jev (full text; one shot)** when the entire record fits. Do not describe the summary condition as a direct comparison of model reasoning over identical text: it measures a pipeline whose performance also depends on the summarizer's selection and compression. The summary mode is applied to every case in its run, including small cases, so input treatment does not vary silently with case size. Model release-date and contamination classifications still apply separately.

## Request size

TypeSafe documents a 64,000-token total request budget and a 32,000-token bound for state plus the longest question. It supplies no exact public tokenizer or preflight counting endpoint. Admission estimates both quantities using the larger of `cl100k_base` and `o200k_base` token counts, multiplied by 1.5, with another 1,024 tokens reserved for formatting. Neither tokenizer is Jev's tokenizer: these are estimates with headroom, not a provider guarantee. On the 91 completed Cycle 1 Luna-summary cases, reported Jev input tokens were between 1.087 and 1.180 times the larger whole-request proxy count. That observation supports the margin for this English legal corpus but does not establish it for other text. Provider-returned usage and context errors remain authoritative. See [TypeSafe's model reference](https://docs.typesafe.ai/models).

For the default `standard` summary profile, the original 64,000-byte value remains the **summary planning target**, so the Luna and Grok summary prompts, existing caches, and spend-ledger identities stay unchanged. It is no longer an inference rejection threshold. This fixes refusal of longer English summaries that fit the token estimates without truncating or repurchasing them. Requests exceeding either estimated token budget still fail before a forecast is purchased. Both summarizers use this same admission code. Newly frozen Jev registries declare the 64,000-token aggregate context for spend reservations; replaying an older registry also respects its smaller frozen total bound. The pinned `tiktoken` dependency caches the two public encoding tables on first use; this is harness setup, not a tool available to a forecasting model.

The September 17, 2026 inspection of the Cycle 1 release `cycle-1-91-2026-09-08-luna-r5` covered 91 cases, 409 prediction units, and 482 selected documents. Full-text request sizes ranged from 21,479 to 607,966 bytes, with a median of 124,580 bytes. Only 17 of 91 fit the former 64,000-byte cutoff. These historical measurements are bytes, not Jev token counts. The current inspection command reports both bytes and token estimates for the original blinded release:

```bash
uv run legalforecast jev inspect \
  --manifest run-manifest.json \
  --forecast forecast-release.json \
  --artifact-root artifacts
```

## Persisted document summaries

The selected summarizer (Luna or Grok 4.6) sees one complete selected document at a time, with its role and identity. It receives neither scoring labels nor other models' forecasts. The prompt asks for facts, allegations, procedural posture, arguments, counterarguments, authorities, and material details throughout the document. It forbids adding outside knowledge or predicting the outcome. All selected documents, including docket histories and notices, are represented. There is no outcome-based selection of summaries.

Summaries are stored in a reusable JSON cache bound to the original release and document identities. Each record includes the source identity, summary model, prompt version, text, token usage, and estimated preparation cost. Keep the cache and its spend ledger together. Matching entries are reused without another provider request. Per-document size allowances guide the summarizer, while the complete case request determines whether the summaries fit both estimated token budgets. A longer summary can use space left by shorter ones. If the complete request exceeds the budget, the summaries are retained and the run stops; the code does not truncate them or automatically repurchase them.

Resume reuses saved output and continues unstarted documents. Grok summary reservations use the frozen registry output ceiling rather than assuming the requested 8,192-token setting bounds all reported billable output. The request setting and summary prompt remain unchanged. A reservation overrun blocks the ledger. For the known Grok output overrun with a saved response, `jev prepare --reconcile-saved-overrun` validates the original cache, release, registry, every prior attempt, and the unchanged ceiling before reconciling the saved charge. The ledger retains recovery evidence and all prior costs; no summary is repurchased. Other poisoned or ambiguous states still fail. The protected workflow exposes the same explicit `reconcile_saved_overrun` option. A provider failure with an uncertain charge stops preparation for reconciliation; rerunning does not authorize another purchase of that document. Summarizer input admission and temporary spend reservations use a conservative UTF-8 byte upper bound, not a measured token count. Successful requests settle against returned token usage and release the unused reservation. This may reject an unusually large document that would fit under the provider tokenizer; it does not silently remove text.

For contributor-owned preparation, the CLI is:

```bash
uv run legalforecast jev prepare \
  --manifest run-manifest.json \
  --forecast forecast-release.json \
  --artifact-root artifacts \
  --luna-registry model_registries/cycle-1-2026-06-30-claude-fable-5-successor-2026-08-31.json \
  --cache jev-summaries.json \
  --ledger summary-spend.sqlite3 \
  --ceiling-microusd 20000000

uv run legalforecast jev registry \
  --summaries jev-summaries.json \
  --output jev-model-registry.json
```

The registry command defaults to the first-party TypeSafe route (`typesafe:jev-1.13.0`). To reproduce a previously issued Gateway registry, pass `--provider vercel_ai_gateway`; that compatibility choice is part of the frozen registry identity.

The numeric ceiling is an example, not spend authorization. Official preparation runs through the protected `prepare-jev-summaries.yaml` workflow. Retain its summary cache, registry, and spend ledger as research artifacts. Subsequent official inference uses `run-benchmark.yaml` with the same original release and manifest, the generated registry, and `jev_summaries_uri`. The registry binds the exact cache used by the run. Preparation cost is reported separately from Jev inference cost and must be included when discussing end-to-end pipeline cost.

### Comparing summarizers

Select Grok with `jev prepare --summary-model grok --summary-registry model_registries/cycle-1-supplementary-grok-4.6-gateway-2026-09-08.json` and the same release arguments. Use a new cache and ledger for each summarizer. Grok uses the existing Gateway route `vercel_ai_gateway:spacexai/grok-4.6`, restricted to xAI, with high reasoning and no tools or search. The document selection, summary instructions, and summary planning target remain the same. The legacy `--luna-registry` option remains an alias for `--summary-registry`.

Freeze the new condition with `jev registry --summary-model grok --provider vercel_ai_gateway --summaries grok-summaries.json --output jev-grok-registry.json` when comparing against an existing Gateway Jev run. Selecting a new summarizer creates a distinct cache, registry, and inference run identity; never resume the Luna condition with Grok summaries. Retain and report both runs, including all summary preparation costs.

The protected preparation workflow exposes `summary_model`, `summary_registry_path`, and `jev_provider` inputs. Defaults preserve Luna preparation and the TypeSafe inference route. For a controlled summarizer comparison, explicitly retain the prior Jev route. Changing the summarizer does not affect the agentic document-tool condition used by other models.

## Native evaluation

### Luna comparison on the same summaries

The Luna comparator receives the same cached document summaries, event definition, and per-unit questions as Jev. It returns numerical probabilities for those original units in one provider request, with no document tools, web search, follow-up turns, or output-repair calls. Register separate conditions with reasoning effort `none` and `high`; high reasoning permits internal reasoning within that one request. Both conditions use the same 16,000-token output allowance; an incomplete or invalid response fails rather than triggering another model turn. The ordinary agentic Luna benchmark is unchanged.

Use `jev registry --predictor luna --reasoning-effort none --summary-model luna --summaries jev-summaries.json --output luna-one-shot-none.json`, and repeat with `--reasoning-effort high` and a separate output path. In the protected preparation workflow, select `registry_only=true`, the completed prior summary artifact, `predictor=luna`, and the requested `predictor_reasoning`. This reuses the saved summaries without another summarization call. Dispatch each registry through the ordinary benchmark workflow with its bound summary cache.

Report these as **Luna (Luna summaries; one shot; reasoning none)** and **Luna (Luna summaries; one shot; reasoning high)**. Luna's numbers are elicited probability estimates; Jev's numbers come from its native Boolean probability interface. Identical evidence and questions make this a useful comparison, but they do not make those output mechanisms identical. Keep each condition's inference costs separate, and report the shared summary preparation cost when describing the complete pipeline.

Jev returns probabilities directly rather than generating a textual rationale. Its Boolean probability is not a confidence score, and the adapter neither thresholds it nor asks another model to translate it. Independent questions share the same state in one call; question instructions carry the claim, defendant group, and count because TypeSafe says question keys are not model-visible. See [TypeSafe's probability primitive](https://docs.typesafe.ai/primitives/noul).

The official route uses TypeSafe's pinned first-party Python SDK (`typesafe-sdk==0.7.0`) against `POST https://api.typesafe.ai/v1/systemone`, with model `jev-1.13.0`, the native `noul` primitive, and SDK retries disabled. The request and response use the provider's documented `state`, `questions`, `answers`, `usage`, and versioned `model` fields. The native response JSON is retained in the provider-attempt evidence while the existing normalized prediction envelope feeds the benchmark parser. A historical Vercel AI Gateway route remains replay-compatible; register it explicitly with `--provider vercel_ai_gateway` and do not treat it as first-party TypeSafe execution. See [TypeSafe's API reference](https://docs.typesafe.ai/api), [TypeSafe's model reference](https://docs.typesafe.ai/models), and [Vercel's evaluation documentation](https://vercel.com/docs/ai-gateway/modalities/evaluation).

The Jev workflow permits isolated case failures but stops scheduling new Jev calls after three failed case execution steps in the current workflow attempt; the limit is total rather than consecutive, and already-running calls may finish. On recovery, use `--max-parallel 1` to inspect the first repaired result before more requests accumulate. Saved errors retain a bounded, redacted message, HTTP status, and Gateway generation ID when available; an error class alone does not establish the cause. Recovery retains uncertain charges and reuses the frozen summary cache.

From a repository checkout, install the pinned Python runtime before contributor-owned inference:

```bash
uv sync --locked
uv run legalforecast run execute --help
```

Use the ordinary run arguments with `--model-key typesafe:jev-1.13.0`, the generated model registry, `TYPESAFE_API_KEY`, and `--jev-summaries jev-summaries.json`. Completed cases use the ordinary durable receipt and resume path. Missing units, extra units, invalid probabilities, stale caches, and oversized requests are errors, not default predictions. Receipts identify the Jev condition, exact served model, token usage, SDK metadata, and provider-attempt evidence explicitly. Full-text mode omits the summary argument and is registered by running `jev registry` without `--summaries`. Existing Gateway artifacts can be replayed with `--model-key vercel_ai_gateway:typesafe-ai/jev`; the compatibility route requires the pinned Node SDK under `integrations/jev` and `AI_GATEWAY_API_KEY`.

HTTP 429 handling is the same for every Jev rate-limit response, regardless of SDK retryability flags: up to seven retries, for eight total attempts, after waits of 30, 60, 120, 240, 300, 300, and 300 seconds. Both the TypeSafe and Gateway routes use this policy. SDK-internal retries remain disabled; Tenacity bounds the retries under the existing case reservation, with the identical request and first successful response retained. Successful receipts record `jev_request_count`. HTTP 401/403, other server errors, timeouts, and malformed successful responses are not automatically retried. Exhausted 429s retain their nonbillable status for ordinary recovery; successful cases and the summary cache are reused.

The same saved Luna summaries also support `--predictor sol-6`, `luna-6`, and `opus-5.5`. OpenAI comparisons use `--reasoning-effort none` and `high`; Opus 5.5 uses `low` and `high` because its adaptive thinking cannot be disabled. Each condition has one provider request per case, no tools or follow-up turns, the original unit IDs, a 64,000-token admission bound, and a 16,000-token output allowance including reasoning. Opus low must not be labeled reasoning off. The base metadata and standard-price estimates are frozen in `model_registries/summary-comparator-models-2026-09-22.json`; each generated condition separately binds the completed cache. OpenAI requests Flex, but these comparison estimates retain standard uncached rates rather than claiming an observed invoice or discount. Provider-reported knowledge cutoffs and month-only training cutoffs remain explicit caveats; these runs do not establish training-cutoff eligibility.

## Separate agentic and summary experiments

New foundation-model benchmark runs use `cycle-1-agentic-*-high-2026-09-22.json`: controlled document tools, high reasoning, and the full original document set. These registries omit `jev_input_mode` and `jev_summaries_sha256`; dispatch them without `jev_summaries_uri`. Model identity alone never selects summary mode.

The separate small-model comparison uses `cycle-1-luna-6-luna-summaries-one-shot-none-2026-09-22.json` with the persisted summaries that Jev received: no tools, no reasoning, and one request per case. Never substitute that registry for the regular GPT-6 Luna agentic run.

## Shorter summaries

`jev prepare --summary-profile short` uses a separate prompt version and a 24,000-byte per-case planning target, with packet overhead and an escaping margin deducted before allocating document budgets. It also requests a smaller word count. Every selected document is supplied in full; the actual context estimator still checks each assembled case, and paid output is saved even when that check fails. Summaries are never truncated. Registry generation labels these results as shorter summaries and binds the exact cache. The default `standard` profile retains the original behavior.

Start the short condition with a fresh cache and ledger, retaining the original artifacts and costs. When both conditions share an approved total, subtract settled historical spend before setting the new preparation ceiling. Recover the same run and ledger instead of dispatching another independent allowance. The protected preparation workflow exposes this choice as `summary_profile`.
