# Website data contract

The website consumes a public JSON export produced by Python. Keep scoring, eligibility decisions, and withdrawal filtering in the benchmark package; the frontend handles presentation, sorting, and selection. The Python package stays at the repository root, and `site/` is an independent pnpm package.

## Produce the data

The supported input is the native score JSON written by `uv run legalforecast score --output scores.json`. The protected fan-in workflow already produces this artifact after scoring completed forecasts. Do not feed raw model responses, provider receipts, private corpus records, or the legacy static-site bundle into the frontend.

```bash
uv run legalforecast site export --scores scores.json --output site-data.json
# Optional: bind public model metadata and the scored decision boundary.
uv run legalforecast site export --scores scores.json --report leaderboard.json \
  --model-registry model-registry.json --output site-data.json
uv run legalforecast site schema --output docs/schemas/site-export-v1.schema.json
pnpm install --frozen-lockfile
pnpm --filter @legalforecastbench/site contract:generate
pnpm site:check
pnpm --filter @legalforecastbench/site contract:validate ../site-data.json
```

The validator path is relative to `site/` when invoked through the package script; use an absolute path for an export stored elsewhere. The schema and generated TypeScript types are committed so frontend contributors can work without Python. Python is required when producing data or changing the contract. Run contract generation after changing the Python schema, and commit both generated outputs.

Add `--withdrawn-case CASE_ID` for a public case exclusion, or supply `--withdrawal-ledger withdrawals.jsonl --cycle-id CYCLE` to apply the existing ledger. The exporter removes affected cases before recomputing Brier scores and calibration. `--accounting accounting.jsonl` accepts existing per-case accounting records and reports their coverage. Without matching metadata or cost evidence, the corresponding fields remain unknown.

## Frontend integration

Import `parseSiteExport` and the `SiteExport` type from `site/src/data/site-export.ts`. Pass parsed JSON as `unknown` to the validator at the data-loading boundary. For a static Astro build, validate at build time and pass typed data to React islands; this avoids shipping the validator to the browser. Validate in the browser when fetching new exports dynamically. A TypeScript assertion alone does not validate downloaded data. The committed fixture is synthetic development data, not a published benchmark result.

Treat each export as one scored artifact. A page may load multiple exports, but must preserve their source identities and experiment settings rather than merging rows solely by model name.

Build the first results page around the micro-Brier headline and equal-case Brier sensitivity, with case and prediction-unit counts visible. Keep full-document agentic and summary conditions distinguishable, show reasoning configuration when known, and retain unknown eligibility and missing cost as unknown. Missing cost must never appear as zero. The contract's fields, rather than the frontend, determine which evidence is available. Standard-rate repricing is currently unavailable in this export; its explicit null/status fields must not be presented as a calculated value.

A useful initial page has a sortable model table, calibration chart, model detail panel, methods links, and a download of the exact displayed JSON. Keep controls that share selection state inside one React island. Add a case explorer using only public fields supplied by the contract. Avoid linking raw input files merely because the exporter read them.

## Publication and withdrawals

After a successful publishing fan-in, the `Export published site data` workflow consumes the dedicated `site-source-{run_id}-{attempt}` artifact and produces `site-export-{run_id}-{attempt}/site-export.json`. It runs trusted current code with read-only permissions, allowing the original benchmark runtime to remain pinned. Verification-only runs and older workflows without a source artifact do not produce automatic exports. GitHub artifact retention is finite; the eventual website deployment must select and retain its public data rather than treating this artifact as a permanent download URL.

An export is a presentation artifact, not permission to publish its source data or evidence that a benchmark run is official. Keep publication status distinct from successful export validation. A website build should consume an explicitly selected public result and record its source in the displayed page.

There is no automatic withdrawal-update trigger in this change. Regenerate the export after withdrawals, rebuild the website, and replace affected hosted assets. Filtering case cards in the browser while retaining old aggregate scores is incorrect. The exporter handles supported withdrawals before computing the displayed metrics; unsupported withdrawal mappings must be resolved before publication. Previously downloaded files cannot be recalled by rebuilding a site.

## Hosting

The generated site can be hosted independently of benchmark execution and protected artifact storage. It needs the public export, not AWS, corpus, or model-provider credentials. Production deployment should retain the repository's protected deployment boundary. The frontend implementation can add Astro build and browser checks to the existing contract checks without moving the Python package.
