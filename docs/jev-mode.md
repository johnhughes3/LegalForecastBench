# Jev one-shot condition

Jev receives one shared case record and one Boolean question for each original prediction unit. Its native probability of “yes” becomes `probability_fully_dismissed`. The target remains the actual first written disposition of the motion, with the same full-dismissal, partial-dismissal, and leave-to-amend rules used by the document-tool condition. The case selection, document selection, unit identifiers, and scoring labels remain unchanged.

This is a distinct official evaluation condition. Report it as **Jev (Luna summaries; one shot)**, **Jev (Grok 4.6 summaries; one shot)**, or **Jev (full text; one shot)** when the entire record fits. Do not describe the summary condition as a direct comparison of model reasoning over identical text: it measures a pipeline whose performance also depends on the summarizer's selection and compression. The summary mode is applied to every case in its run, including small cases, so input treatment does not vary silently with case size. Model release-date and contamination classifications still apply separately.

## Request size

TypeSafe documents a 64,000-token total request budget and a 32,000-token bound for state plus the longest question. It supplies no exact public tokenizer or preflight counting endpoint. Admission estimates both quantities using the larger of `cl100k_base` and `o200k_base` token counts, multiplied by 1.5, with another 1,024 tokens reserved for formatting. Neither tokenizer is Jev's tokenizer: these are estimates with headroom, not a provider guarantee. On the 91 completed Cycle 1 Luna-summary cases, reported Jev input tokens were between 1.087 and 1.180 times the larger whole-request proxy count. That observation supports the margin for this English legal corpus but does not establish it for other text. Provider-returned usage and context errors remain authoritative. See [TypeSafe's model reference](https://docs.typesafe.ai/models).

The original 64,000-byte value remains the **summary planning target**, so the Luna and Grok summary prompts, existing caches, and spend-ledger identities stay unchanged. It is no longer an inference rejection threshold. This fixes refusal of longer English summaries that fit the token estimates without truncating or repurchasing them. Requests exceeding either estimated token budget still fail before a forecast is purchased. Both summarizers use this same admission code. The pinned `tiktoken` dependency caches the two public encoding tables on first use; this is harness setup, not a tool available to a forecasting model.

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

Resume reuses saved output and continues unstarted documents. A provider failure with an uncertain charge stops preparation for reconciliation; rerunning does not authorize another purchase of that document. Summarizer input admission and temporary spend reservations use a conservative UTF-8 byte upper bound, not a measured token count. Successful requests settle against returned token usage and release the unused reservation. This may reject an unusually large document that would fit under the provider tokenizer; it does not silently remove text.

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
