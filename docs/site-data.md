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

## Website

The Astro site in `site/` renders results, model pages, findings, and methods as static pages. Run `pnpm site:dev` for a local server and `pnpm site:build` for the production build in `site/dist/`. React islands handle the sortable leaderboard and the cost/quality chart; every other page is static HTML.

- **Results data.** Pages read `site/src/data/results.ts`, which combines the unchanged September 18 aggregate snapshot with six native scored exports in `site/src/data/exports/`. `parseSiteExport` validates each export, and the adapter rejects non-agentic conditions, different release identities, incomplete cohorts, or disagreeing unit identities/outcomes. Brier values come from the Python scorer; accuracy and high-confidence counts derive from exported units. The historical download remains `/data/beta-2026-09-18.json`; `/data/current.json` serves the displayed combined snapshot and `/data/exports/<slug>.json` preserves each native source. Model and data pages link the forecast and scoring runs. Missing costs remain null. The selected aggregate snapshot additionally joins `receipt-costs.json` by exact model and forecast/scoring run identity, using standard-rate estimates reconstructed from saved response usage and frozen prices through the shared cost helpers. The original native exports remain unchanged. `/data/costs.json` exposes successful workload costs separately from the chart estimates, coverage, cache limitations, and pricing references. Detailed cost explanations live on `/data/run-notes/#costs`.
- **Methods.** `/methods/` renders `docs/METHODS.md` directly, so edit the methods there.
- **Findings.** Reports and notes are MDX files in `site/src/content/findings/`. Set `draft: true` to render a post only under `astro dev`; no deployed build, including public Vercel previews, includes drafts. Keep unreviewed posts off pushed branches entirely.
- **Hosting.** Vercel builds the site through its Git integration: Root Directory `site`, production branch `main`, with source files outside the root directory included (the build reads `docs/`). `site/vercel.json` pins the install, build, and output settings. Set `ENABLE_EXPERIMENTAL_COREPACK=1` so Vercel uses the pinned pnpm version. No Vercel token is stored in this repository or in Actions.

The manual `publish-site-data.yaml` workflow builds trusted `main` and publishes every JSON download under `site/dist/data/` to the results bucket at `reports/site-data/multi-ablation/<commit>/data/`. It uses the protected fan-in environment and OIDC, conditionally creates immutable objects, and reads each object back to verify the uploaded bytes. This S3 preservation step is separate from the Vercel site deployment; a successful source merge does not prove either publication completed.

### Updated paired comparisons

The current paired analysis covers nine of the 16 displayed configurations. Seven older configurations retain aggregate scores but lack recoverable unit-level predictions; pairs involving them are untested. The updated analysis uses one million paired case-cluster bootstrap replicates with Bonferroni correction for the entire 16-model family (120 pairs × three metrics). It replaces, rather than combines with, the historical ten-model pair list. The unchanged September 18 download retains the original analysis.

Download `/data/significance/inputs.json` and its nine sibling JSONL files into one directory. `/data/significance/comparison.json` records confidence intervals, source provenance, covered and missing models, seed, and method. Reproduce it from the repository with:

```bash
OPENBLAS_NUM_THREADS=4 uv run scripts/compare_site_results.py --inputs path/to/downloads/inputs.json --output comparison.json
```

The script pins its numerical dependency. Public inputs contain only case/unit identifiers, forecast probabilities, and binary outcomes; no court documents or model transcripts are included. The S3 site-data workflow preserves the JSONL inputs alongside the JSON downloads.

## Summary comparisons

The `/experiments/summary-pipelines/` page keeps Jev and one-shot Luna summary conditions separate from the main agentic leaderboard. GPT-4.1 appears there as a full-record non-reasoning reference; its original native export remains unchanged. The shared cache was prepared by GPT-5.6 Luna. The high-reasoning reference also uses GPT-5.6 Luna, while the reasoning-off comparison uses GPT-6 Luna, so this is not an isolated reasoning-effort ablation of the same model.

The three summary exports are reconstructed with the canonical scorer from archived valid forecasts and the previously published GPT-6 Sol unit outcomes for the identical release. They are not new protected fan-in outputs. Download their native exports from `/data/exports/`, and the catalog, published outcomes, forecasts, and frozen registries under `/data/summary-comparison/`. The catalog records original run identities, common summary-cache identity, archive workflow/artifact IDs, and separate preparation/inference estimates. It preserves the 409-forecast census and scores the original 387 eligible units across 91 cases. The frozen registry files retain their original bytes and are excluded from automatic JSON formatting.

From a repository checkout, reproduce the displayed exports without model calls:

```bash
uv run python scripts/reproduce_summary_comparisons.py site/public/data/summary-comparison /tmp/summary-exports
```

The site publisher includes these public reproduction files and exports in its normal JSON/JSONL upload and readback verification. The main agentic snapshot and its significance family remain unchanged. The summary conditions have their own three-model significance family in `site/src/data/significance/summary/`, produced with `scripts/compare_site_results.py --inputs site/src/data/significance/summary/inputs.json`. Reader-facing details belong on `/experiments/summary-pipelines/#method`.
