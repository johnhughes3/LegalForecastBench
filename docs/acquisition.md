# Acquisition Status

LegalForecast-MTD does not yet publish a live benchmark corpus. The offline
fixture pipeline works, but the public-data acquisition path still needs a
reliable docket-entry and source-document retrieval route before official model
evaluation can begin.

## Current State

- Case.dev discovery can surface recent federal district-court MTD candidates.
- The live acquisition blocker is complete packet recovery: the operative
  complaint, motion, briefing, exhibits selected for the packet, and first
  written disposition must be identified and preserved with provenance.
- CourtListener/RECAP and PACER are fallback sources when public records are
  missing from the primary path.
- No official cycle should run until the retained cases have clean
  pre-decision packets, audited labels, frozen manifests, and cost records.

## Defaults

Development and CI must stay offline by default:

```bash
uv run pytest -q
uv run legalforecast fixture e2e --output-dir tmp/fixture-run
```

Live or paid acquisition must be explicitly opted in. Commands that can spend
money require both an execution flag and the relevant fee acknowledgement.

## Production Acquisition Commands

The production acquisition surface is grouped under:

```bash
uv run legalforecast acquisition --help
```

The current alpha CLI is stage-oriented. Input filenames below are illustrative;
the upstream screening/review step must produce the JSONL inputs for each stage.
Omitting `--execute` keeps a stage in dry-run mode.

```bash
uv run legalforecast acquisition plan \
  --core-filter-results tmp/acquisition/core-filter-results.jsonl \
  --output-root tmp/acquisition

uv run legalforecast acquisition download-free \
  --requests tmp/acquisition/free-document-requests.jsonl \
  --output-root tmp/acquisition

uv run legalforecast acquisition purchase-missing \
  --budget-plan tmp/acquisition/missing-core-budget-plan.json \
  --output-root tmp/acquisition

uv run legalforecast acquisition parse-documents \
  --requests tmp/acquisition/parse-document-requests.jsonl \
  --output-root tmp/acquisition

uv run legalforecast acquisition build-packets \
  --input tmp/acquisition/packet-build-input.jsonl \
  --output-root tmp/acquisition
```

Use `--dry-run` first. The only stage designed to purchase documents is
`purchase-missing`, and it should remain dry-run unless a human operator has
reviewed the plan, budget, and fee acknowledgement.

Execution flags are intentionally explicit:

- `plan --execute` writes a non-dry-run budget plan for later purchase review.
- `download-free --execute` performs fixture-safe free-document downloads in
  this alpha path and requires `--fixture-documents`.
- `purchase-missing --execute` additionally requires `--live-purchase` and
  `--acknowledge-pacer-fees`.
- `parse-documents --execute` uses the configured parser, or
  `--fixture-markdown-dir` for fixture runs.
- `build-packets --execute` writes `packets.jsonl`, `case-packets.jsonl`, and
  `packet-audit.jsonl`.

## Case.dev and PACER Guardrails

- `CASE_DEV_API_KEY` is required for live Case.dev requests.
- Live PACER-backed recovery must not run unless the operator passes the live
  purchase flag and fee acknowledgement.
- Budget checks should assume the worst-case document cost before any purchase.
- The default planning metric is missing core documents, not total docket
  length. That aligns the optimization target with acquisition cost.
- Federal district courts are the intended search scope for v1.

## Official Readiness Gate

The live blocker is complete packet retrieval, not just credentials. Case.dev is
currently the discovery-first surface; it should not be described as a complete
packet source unless docket-entry and source-document retrieval are available for
sampled candidates.

A readiness pilot may use CourtListener/RECAP/PACER fallback reconstruction when
public records are missing from the primary path. Its diagnostics must be based
on reviewed or retained packets, not search hits. Do not start official model
execution until the acquisition evidence shows at least 50 clean packets or a
credible path to 50-100 clean packets, with:

- source-class counts for `case.dev-only`, `case.dev-plus-fallback`, and
  `excluded`;
- linkage, leakage, text-quality, and document-completeness exclusion counts;
- retained-packet case-mix diagnostics;
- separate discovery, fallback reconstruction, and live purchase cost totals;
- label ambiguity and lawyer review-time measurements for reviewed packets.

## Public Release Boundary

The v0.1 alpha includes the acquisition code path and fixtures, not a public
case corpus. When the live path is unblocked, a public cycle should publish the
frozen manifests, hashes, run cards, model cards, cost accounting, scores, and
result tier. Until then, any fixture leaderboard is a synthetic smoke artifact.
