---
name: site-export
description: Produce or change the public website JSON export, schema, and generated TypeScript contract; use when connecting the results frontend to Python scoring.
---

# Website export

Use the native score artifact produced by `legalforecast score`, not raw run receipts or the legacy static-site bundle. The command is `uv run legalforecast site export --scores scores.json --output site-data.json`; inspect `site export --help` for metadata and withdrawal options.

The Python contract is authoritative. After changing it, run `uv run legalforecast site schema --output docs/schemas/site-export-v1.schema.json`, `pnpm --filter @legalforecastbench/site contract:generate`, and `pnpm site:check`. Validate exporter behavior with the focused `tests/test_site_export*` tests. Type generation does not replace runtime JSON validation: frontend code uses `parseSiteExport` from `site/src/data/site-export.ts`.

Keep Python scoring and eligibility logic shared. Withdrawals must affect aggregate metrics as well as visible case rows. Null cost means missing evidence, not zero. Separate summary experiments from full-document agentic runs, and do not infer eligibility from model release dates. The synthetic fixture supports development only.

See [the public contract guide](../../../docs/site-data.md) for integration and publication semantics. Exporting data does not deploy the website or authorize publication of private inputs.

The selected site combines the historical aggregate snapshot with validated native exports in `site/src/data/exports/`. Reproduce its updated paired case-cluster analysis with `uv run scripts/compare_site_results.py --inputs site/src/data/significance/inputs.json --output /tmp/comparison.json`. Preserve the input manifest's planned comparison family and missing-model disclosure; missing prediction data is not evidence of nonsignificance.

When the owner requests S3 publication, dispatch `gh workflow run publish-site-data.yaml --ref main` after the selected data lands. The protected fan-in environment publishes built JSON and JSONL under `reports/site-data/multi-ablation/<commit>/data/` and checks every object by readback. Verify the job's publication step and dataset count before claiming success. This is separate from the website's Vercel deployment.

For selected runs with separately recovered cost evidence, join `site/src/data/receipt-costs.json` by exact forecast/scoring run and model identity with complete case coverage. Preserve native exports unchanged; absent estimates remain null. Keep beta pipeline, provenance, and cost explanations on `/data/beta-run-mechanics/`, linked from Data.
