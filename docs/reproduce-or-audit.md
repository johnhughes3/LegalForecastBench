# Reproduce Or Audit LegalForecastBench Results

LegalForecastBench separates public arithmetic reproduction from private source
audit. Public artifacts support verification of hashes, score arithmetic, run
metadata, release commitments, and source handles. A deeper audit may require
locked labels, accepted per-case outputs, and court-document bytes that the
project cannot redistribute as a public corpus.

A public release consists of a locked run manifest, an outcome-blinded forecast
release, model-visible artifacts, and a separately controlled labels release.
The forecast worker receives no labels. Every published score is tied to the
exact release identities and the immutable artifacts used to produce it.

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

## Validate a Published Release

Start from an exact checkout and the release files named by the publication
record. Validate the public inputs before scoring:

```bash
uv run legalforecast manifest validate \
  --manifest <run-manifest.json> \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <artifact-root>

uv run legalforecast release validate \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <artifact-root>

uv run python -m legalforecast.contracts.ratchet
uv run pytest -q
```

A validation error names the release, artifact, or field that failed. Check the
relevant schema and rerun the command with `--help` before changing an input.
Do not replace an immutable artifact with a mutable checkout or a newly
generated document.

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

Managed document-tool runs retain a JSON conversation in `transcripts/<cell_id>.json` beside the run's receipts. The conversation includes the task instructions, model-visible prompt, tool calls and arguments, tool results, intermediate model messages, and final response. It captures only reasoning the provider exposes; it cannot reveal hidden internal reasoning. Failed runs retain the available conversation when the model runtime captured messages before the failure. Older runs may have no transcript, and resuming an older result does not recreate one.

The Run Benchmark workflow retains these files in its per-case state artifacts and combined forecast artifact. Inspect transcripts as part of the source audit: tool results can contain document text. They are separate from the score and leaderboard reports and must not be committed to this repository.

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

## How Official Runs Are Produced

Official execution and publication use two protected workflows from a trusted
revision: `run-benchmark.yaml` for forecast execution and `fan-in-publish.yaml`
for labels fan-in, scoring, and publication. Their existence and input
contracts are checked in the repository. `ForecastRunMetadata` in
`legalforecast/contracts/forecast_run.py` defines the shared `forecast-run.json`
fields; run `uv run pytest tests/test_fan_in_metadata.py -q` when changing
either workflow.

Provider-free tests, release validation, a pull request, and a workflow plan
prove source and artifact contracts only. They do not prove that a protected
workflow ran, that its provider calls succeeded, or that a result is authorized
for publication. Those facts come from the exact workflow run and the release
evidence attached to it.

Publish only sanitized JSON, CSV, Markdown, and HTML leaderboard artifacts
bound to the score identity and their machine-readable provenance. Never
publish labels, raw provider responses, private source bytes, or private
withdrawal reasons. If a published case must be removed, use the repository's
withdrawal contract and publish the resulting public erratum; withdrawal does
not rewrite an immutable prior release.

## Retained workflow artifacts

The `archive-github-artifacts.yaml` workflow runs automatically when Run Benchmark, Recover Benchmark, Protected Labels Fan In, Score Terminal Release, or Prepare Jev Summaries completes, copying that run's artifacts whatever its conclusion. A manual dispatch with no `source_run_id` preserves all GitHub artifact types available in this repository when its inventory is taken, including failed-run checkpoints and scoring reports. It copies original ZIPs without extracting or executing them to the configured results bucket under `reports/github-artifacts/multi-ablation/<owner>/<repository>/artifacts/<artifact-id>.zip`. Artifact IDs distinguish runs and artifacts with identical names. This archive is separate from canonical cycle reports and does not designate a run as a published benchmark result.

Each archived ZIP also gets a small pointer at `by-run/<source-run-id>/<artifact-name>/<artifact-id>.json` that records its GitHub SHA-256 digest, so a package can be found from its run ID after GitHub has expired and delisted it; protected fan-in restores an expired `official-forecast-results-<run>-<attempt>` package this way and checks the digest. Each archive invocation saves the source inventory and a result index under the same prefix's `runs/` directory. Those indexes map original names and source run IDs to durable objects and identify any failed copies. An artifact that expires or becomes unavailable after inventory is reported as a failed copy; artifacts already expired at inventory are counted separately. Artifacts created after inventory require a later invocation. Reruns preserve existing matching objects and refuse conflicting bytes. The workflow uses the existing protected publication environment; it does not make model calls or change provider spending authority.

Artifact downloads run before assuming the S3 role. The downloader checks GitHub API quota in bounded batches and waits for its reset when necessary; the upload phase then obtains fresh one-hour AWS credentials. Large inventories can therefore take one or more quota windows. Download failures remain failures even if successfully downloaded ZIPs are preserved.
