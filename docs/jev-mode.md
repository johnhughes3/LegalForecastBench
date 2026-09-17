# Jev one-shot condition

Jev receives one shared case record and one Boolean question for each original prediction unit. Its native probability of “yes” becomes `probability_fully_dismissed`. The target remains the actual first written disposition of the motion, with the same full-dismissal, partial-dismissal, and leave-to-amend rules used by the document-tool condition. The case selection, document selection, unit identifiers, and scoring labels remain unchanged.

This is a distinct official evaluation condition. Report it as **Jev (Luna summaries; one shot)**, or **Jev (full text; one shot)** when the entire record fits. Do not describe the summary condition as a direct comparison of model reasoning over identical text: it measures a pipeline whose performance also depends on Luna's selection and compression. The summary mode is applied to every case in its run, including small cases, so input treatment does not vary silently with case size. Model release-date and contamination classifications still apply separately.

## Request size

TypeSafe documents an approximate shared budget of 32,000 tokens for state and questions, or roughly 150,000 English characters. It supplies no exact public tokenizer or preflight counting endpoint. We therefore measure the complete serialized request and use a conservative 64,000-byte application budget. This is not an exact token count or a provider guarantee. Provider-returned token usage is retained in each receipt. Requests above the application budget fail before a forecast is purchased; source text is never silently truncated. See [TypeSafe's question documentation](https://docs.typesafe.ai/primitives).

The September 17, 2026 inspection of the Cycle 1 release `cycle-1-91-2026-09-08-luna-r5` covered 91 cases, 409 prediction units, and 482 selected documents. Full-text request sizes ranged from 21,479 to 607,966 bytes, with a median of 124,580 bytes. Only 17 of 91 fit the 64,000-byte application budget. These are serialized byte measurements, not Jev token counts. Reproduce the census on the original blinded release:

```bash
uv run legalforecast jev inspect \
  --manifest run-manifest.json \
  --forecast forecast-release.json \
  --artifact-root artifacts
```

## Persisted document summaries

Luna sees one complete selected document at a time, with its role and identity. It receives neither scoring labels nor other models' forecasts. The prompt asks for facts, allegations, procedural posture, arguments, counterarguments, authorities, and material details throughout the document. It forbids adding outside knowledge or predicting the outcome. All selected documents, including docket histories and notices, are represented. There is no outcome-based selection of summaries.

Summaries are stored in a reusable JSON cache bound to the original release and document identities. Each record includes the source identity, summary model, prompt version, text, token usage, and estimated preparation cost. Keep the cache and its spend ledger together. Matching entries are reused without another provider request. Per-document size allowances guide Luna, while the complete case request determines whether the summaries fit. A longer summary can use space left by shorter ones. If the complete request exceeds the budget, the summaries are retained and the run stops; the code does not truncate them or automatically repurchase them.

Resume reuses saved output and continues unstarted documents. A provider failure with an uncertain charge stops preparation for reconciliation; rerunning does not authorize another purchase of that document. Luna input admission and temporary spend reservations use a conservative UTF-8 byte upper bound, not a measured token count. Successful requests settle against returned token usage and release the unused reservation. This may reject an unusually large document that would fit under the provider tokenizer; it does not silently remove text.

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

The numeric ceiling is an example, not spend authorization. Official preparation runs through the protected `prepare-jev-summaries.yaml` workflow. Retain its summary cache, registry, and spend ledger as research artifacts. Subsequent official inference uses `run-benchmark.yaml` with the same original release and manifest, the generated registry, and `jev_summaries_uri`. The registry binds the exact cache used by the run. Preparation cost is reported separately from Jev inference cost and must be included when discussing end-to-end pipeline cost.

## Native evaluation

Jev returns probabilities directly rather than generating a textual rationale. Its Boolean probability is not a confidence score, and the adapter neither thresholds it nor asks another model to translate it. Independent questions share the same state in one call; question instructions carry the claim, defendant group, and count because TypeSafe says question keys are not model-visible. See [TypeSafe's probability primitive](https://docs.typesafe.ai/primitives/noul).

The implementation uses Vercel's supported AI SDK evaluation API, pinned in `integrations/jev`. It makes one SDK evaluation request with automatic SDK retries disabled. It does not use a chat-completion endpoint or an undocumented direct Gateway HTTP protocol. The Gateway route is `typesafe-ai/jev`; no dated provider snapshot is invented when the service does not expose one. See [Vercel's evaluation documentation](https://vercel.com/docs/ai-gateway/modalities/evaluation).

The Jev workflow stops queued cells after a failed evaluation. On recovery, use `--max-parallel 1` to inspect the first repaired result before more requests accumulate. Saved errors retain a bounded, redacted message, HTTP status, and Gateway generation ID when available; an error class alone does not establish the cause. Recovery retains uncertain charges and reuses the frozen summary cache.

From a repository checkout, install the pinned runtime before contributor-owned inference:

```bash
pnpm --dir integrations/jev install --frozen-lockfile
uv run legalforecast run execute --help
```

Use the ordinary run arguments with `--model-key vercel_ai_gateway:typesafe-ai/jev`, the generated model registry, and `--jev-summaries jev-summaries.json`. Completed cases use the ordinary durable receipt and resume path. Missing units, extra units, invalid probabilities, stale caches, and oversized requests are errors, not default predictions. Receipts identify the Jev condition explicitly. Full-text mode omits the summary argument and is registered by running `jev registry` without `--summaries`.
