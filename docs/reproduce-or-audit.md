# Reproduce Or Audit LegalForecastBench Results

LegalForecastBench separates public arithmetic reproduction from private source
audit. Public artifacts support verification of hashes, score arithmetic, run
metadata, release commitments, and source handles. A deeper audit may require
locked labels, accepted per-case outputs, and court-document bytes that the
project cannot redistribute as a public corpus.

The Apache-2.0 license covers repository code. It does not grant redistribution
rights for court filings, PACER or RECAP documents, provider outputs, locked
labels, or third-party data.

## Credential-Free Fixture Reproduction

Run the provider-free synthetic pipeline and validate its issued releases:

```bash
uv run legalforecast run issue-fixture --output-dir tmp/fixture-run

uv run legalforecast release validate \
  --forecast tmp/fixture-run/release/forecast-release.json \
  --labels tmp/fixture-run/release/labels-release.json \
  --artifact-root tmp/fixture-run/release
```

The source-tree release gate additionally prepares a locked fixture manifest,
executes a dry-run against the forecast release, collects authenticated public
receipts, and runs the strict score/report contract. This path requires no
provider credentials and does not claim a live official cycle.

## Recompute Public Scores and Reports

With the accepted run records, exact frozen manifest, separately issued labels
and forecast releases, artifact root, model registry, and run ledger:

```bash
uv run legalforecast score \
  --runs <run-records.jsonl> \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <release-root> \
  --manifest <run-manifest.json> \
  --model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output scores.json \
  --unit-scores-output unit_scores.jsonl

uv run legalforecast report \
  --scores scores.json \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <release-root> \
  --manifest <run-manifest.json> \
  --frozen-model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output-dir reports/
```

These commands consume already-issued public releases and authenticated run
receipts. They do not reconstruct private source inputs, accept a mutable
checkout as an official release, or provide a private acquisition path.

## Verify Public Score Arithmetic

`unit_scores.jsonl` contains public per-unit score rows and
`reports/leaderboard.json` contains the published summaries. Recompute a
model's micro-Brier as the arithmetic mean of its public unit `brier` values and
compare that result with its leaderboard row. This verifies published
arithmetic, not the private label-creation process.

Also verify every entry in the release artifact index against the referenced
file's SHA-256 and compare the run records with the manifest, release digests,
registry keys, expected matrix, and observed receipts. A receipt is evidence of
an authenticated run record; it is not evidence that protected publication or
live infrastructure was authorized.

Source handles and release commitments can support an audit without granting
redistribution rights. Do not publish locked labels, raw provider responses,
private withdrawal reasons, or restricted source-document bytes.

## Audit Checklist

1. Confirm the forecast and labels release SHAs and locked manifest predate the
   run records.
2. Verify the manifest, releases, model registry, artifact commitments, scorer,
   prompt, and other committed public artifacts.
3. Confirm the authenticated run records form the expected case, model, and
   repeat matrix exactly once.
4. Recompute strict scores and reports with the commands above and compare
   output hashes.
5. Recompute public unit-score arithmetic and inspect any documented warnings.
6. Verify every report artifact was built from the strict score output and
   release identities.
7. Use the private archive only for the deeper label, source-document, and
   provider-response audit.

The public release commands validate already-issued artifacts; private corpus
construction and source-document acquisition remain in LegalForecastCorpus.
