---
name: site-export
description: Produce or change the public website JSON export, schema, and generated TypeScript contract; use when connecting the results frontend to Python scoring.
---

# Website export

Use the native score artifact produced by `legalforecast score`, not raw run receipts or the legacy static-site bundle. The command is `uv run legalforecast site export --scores scores.json --output site-data.json`; inspect `site export --help` for metadata and withdrawal options.

The Python contract is authoritative. After changing it, run `uv run legalforecast site schema --output docs/schemas/site-export-v1.schema.json`, `pnpm --filter @legalforecastbench/site contract:generate`, and `pnpm site:check`. Validate exporter behavior with the focused `tests/test_site_export*` tests. Type generation does not replace runtime JSON validation: frontend code uses `parseSiteExport` from `site/src/data/site-export.ts`.

Keep Python scoring and eligibility logic shared. Withdrawals must affect aggregate metrics as well as visible case rows. Null cost means missing evidence, not zero. Separate summary experiments from full-document agentic runs, and do not infer eligibility from model release dates. The synthetic fixture supports development only.

See [the public contract guide](../../../docs/site-data.md) for integration and publication semantics. Exporting data does not deploy the website or authorize publication of private inputs.
