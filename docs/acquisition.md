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

The intended sequence is:

```bash
uv run legalforecast acquisition plan \
  --candidates candidates.jsonl \
  --output-root tmp/acquisition

uv run legalforecast acquisition download-free \
  --requests tmp/acquisition/free-document-requests.jsonl \
  --output-root tmp/acquisition \
  --execute

uv run legalforecast acquisition purchase-missing \
  --plan tmp/acquisition/missing-core-plan.jsonl \
  --output-root tmp/acquisition \
  --dry-run

uv run legalforecast acquisition parse-documents \
  --manifest tmp/acquisition/document-manifest.jsonl \
  --output-root tmp/acquisition

uv run legalforecast acquisition build-packets \
  --candidates candidates.jsonl \
  --document-manifest tmp/acquisition/document-manifest.jsonl \
  --markdown-manifest tmp/acquisition/markdown-manifest.jsonl \
  --output-root tmp/acquisition
```

Use `--dry-run` first. The only stage designed to purchase documents is
`purchase-missing`, and it should remain dry-run unless a human operator has
reviewed the plan, budget, and fee acknowledgement.

## Case.dev and PACER Guardrails

- `CASE_DEV_API_KEY` is required for live Case.dev requests.
- Live PACER-backed recovery must not run unless the operator passes the live
  purchase flag and fee acknowledgement.
- Budget checks should assume the worst-case document cost before any purchase.
- The default planning metric is missing core documents, not total docket
  length. That aligns the optimization target with acquisition cost.
- Federal district courts are the intended search scope for v1.

## Public Release Boundary

The v0.1 alpha includes the acquisition code path and fixtures, not a public
case corpus. When the live path is unblocked, a public cycle should publish the
frozen manifests, hashes, run cards, model cards, cost accounting, scores, and
result tier. Until then, any fixture leaderboard is a synthetic smoke artifact.
