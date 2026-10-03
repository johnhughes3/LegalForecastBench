---
name: site-export
description: Produce or change the public website JSON export, schema, and generated TypeScript contract; use when connecting the results frontend to Python scoring.
---

# Website export

Use the native score artifact produced by `legalforecast score`, not raw run receipts or the legacy static-site bundle. The command is `uv run legalforecast site export --scores scores.json --output site-data.json`; inspect `site export --help` for metadata and withdrawal options.

Protected fan-in scoring generates `accounting.jsonl` from its identity-validated receipts using `uv run python -m legalforecast.publication.receipt_accounting --receipts validated-receipts.jsonl --registry model-registry.json --model-key PROVIDER:MODEL --output accounting.jsonl`. It passes accounting to both report and site export, retains the results, and publishes them alongside scores in S3 when publication is enabled. Preserve charge-versus-estimate evidence, successful-workload scope, missing usage/rates, and standard-rate coverage. Never infer invoice totals from completed-case receipts alone.

The Python contract is authoritative. After changing it, run `uv run legalforecast site schema --output docs/schemas/site-export-v1.schema.json`, `pnpm --filter @legalforecastbench/site contract:generate`, and `pnpm site:check`. Validate exporter behavior with the focused `tests/test_site_export*` tests. Type generation does not replace runtime JSON validation: frontend code uses `parseSiteExport` from `site/src/data/site-export.ts`.

Keep Python scoring and eligibility logic shared. Withdrawals must affect aggregate metrics as well as visible case rows. Null cost means missing evidence, not zero. Separate summary experiments from full-document agentic runs, and do not infer eligibility from model release dates. The synthetic fixture supports development only.

See [the public contract guide](../../../docs/site-data.md) for integration and publication semantics. Exporting data does not deploy the website or authorize publication of private inputs.

The selected site combines the historical aggregate snapshot with validated native exports in `site/src/data/exports/`. Reproduce its updated paired case-cluster analysis with `uv run scripts/compare_site_results.py --inputs site/src/data/significance/inputs.json --output /tmp/comparison.json`. Preserve the input manifest's planned comparison family and missing-model disclosure; missing prediction data is not evidence of nonsignificance.

When the owner requests S3 publication, dispatch `gh workflow run publish-site-data.yaml --ref main` after the selected data lands. The protected fan-in environment publishes built JSON and JSONL under `reports/site-data/multi-ablation/<commit>/data/` and checks every object by readback. Verify the job's publication step and dataset count before claiming success. This is separate from the website's Vercel deployment.

For selected runs with separately recovered cost evidence, join `site/src/data/receipt-costs.json` by exact forecast/scoring run and model identity with complete case coverage. Preserve native exports unchanged; absent estimates remain null. Keep beta pipeline, provenance, and cost explanations on `/data/beta-run-mechanics/`, linked from Data.

Summary comparisons use a separate `supplementary-results.ts` adapter and table; never add them to the agentic snapshot. Reproduce their native exports with `uv run python scripts/reproduce_summary_comparisons.py site/public/data/summary-comparison /tmp/summary-exports`. Preserve frozen registry bytes, the original scored cohort, and per-condition input/reasoning labels. The public catalog distinguishes reconstruction against already published outcomes from a new protected scoring run. Publication automatically includes the reproduction JSON files.

For an explicitly requested case withdrawal, build current public data first (`pnpm site:build`), then run `uv run legalforecast site refresh --input-dir site/dist/data --output-dir /tmp/refreshed-site-data --withdrawn-case CASE_ID`. Repeat `--withdrawn-case` for multiple cases. This provider-free command rescores every reconstructable selected native and summary configuration, preserves the planned significance families, and filters all forecast/outcome/significance downloads plus the separate historical appendix. It writes a new complete data tree; it does not publish or change the originals. Models with only aggregate evidence remain in `historical-aggregates.json` as superseded observations excluded from current ranking/significance. Costs retain original workload scope unless exact per-case appendix evidence supports retained-cohort sums. Use the existing protected publication path after integrating the complete generated data tree; do not publish individual refreshed files alongside old-cohort data.

The separate historical appendix reproducer accepts `--expected-case-count` and `--expected-unit-count` for a refreshed extract; use `available_cases` and `available_units` from its downloaded results. Defaults remain the original 100 cases and 425 units. No new provider calls or private corpus inputs are needed.
