# Official Run Runbook

This runbook covers the retained public release boundary: a locked manifest,
an outcome-blinded forecast release, the matrix in
`.github/workflows/run-benchmark.yaml`, and the protected labels fan-in in
`.github/workflows/fan-in-publish.yaml`. It does not describe private Corpus
construction or source-byte handling.

The companion LegalForecastCorpus repository owns private source bytes,
selection, quality control, release issuance, and the OIDC publication handoff.
The handoff must provide the exact immutable URIs consumed below; this public
repository never reconstructs private inputs or accepts a mutable checkout as
an official release. No provider or labels credential is present in the
forecast preparation job.

## Ownership and stop conditions

LegalForecastCorpus owns private corpus construction and the OIDC staging
operation. LegalForecastBench owns public release validation, forecast
execution, scoring, reporting, withdrawal records, and community publication.
The public workflows do not provide a replacement path for private source
acquisition, and no operator should revive one in this repository.

Stop before dispatch when any release, manifest, model registry, or URI is
missing; when an artifact digest differs; when the requested model key is not
in the frozen registry; or when the protected environment is not approved.
Source validation, a green pull request, a fixture run, and an infrastructure
plan are not evidence that a live official cycle ran or that it may be
published.

## Corpus-to-benchmark handoff

The private Corpus release handoff supplies these immutable public-boundary
inputs:

- `manifest_uri`: locked `run-manifest.json`;
- `forecast_release_uri`: outcome-blinded `forecast-release.json`;
- `artifact_root_uri`: prefix containing every forecast-declared packet and
  prompt object;
- `model_registry_uri`: frozen registry JSON; and
- `labels_release_uri`: locked labels release, supplied only to protected
  fan-in after forecast execution.

The handoff records the exact release SHA, manifest digest, forecast digest,
registry digest, and object versions outside this repository's source tree.
The benchmark workflow validates those commitments again before execution.

## Before dispatch

Run provider-free checks against the exact checked-out public revision:

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

Confirm that every URI is immutable and under the configured results store.
Keep labels out of the forecast worker's artifact root and do not upload labels
to the forecast workflow. The forecast job must use the exact model registry
entry, a positive owner-approved ceiling, and a stable provider-account scope.

## Forecast execution

Dispatch only from the trusted `main` revision after the Corpus handoff and
protected preparation environment are ready. The command shape is:

```bash
gh workflow run run-benchmark.yaml --ref main \
  -f release_sha=<full-main-sha> \
  -f manifest_uri=<immutable-manifest-uri> \
  -f forecast_release_uri=<immutable-forecast-release-uri> \
  -f artifact_root_uri=<immutable-artifact-prefix/> \
  -f model_registry_uri=<immutable-model-registry-uri> \
  -f model_key=<provider:model-id> \
  -f ceiling_microusd=<positive-microusd-ceiling> \
  -f account=<stable-account> \
  -f repeat_count=1 \
  -f max_parallel=4 \
  -f artifact_retention_days=14
```

The workflow validates the exact revision and release identities, materializes
only allowlisted forecast inputs, derives one identity for the full run, and
fans out resumable cells. Each cell receives no labels input and writes a
receipt bound to the forecast release, model registry, run identity, and cell
identity. A failed or interrupted cell is resumed only with the same identity;
an ambiguous provider transport is never retried as a new logical attempt.

Wait for the exact workflow run and attempt to finish successfully. Preserve
the forecast result artifact, its digest, the run identity, and the exact
release SHA. A successful fixture or a successful workflow plan is not a
publishable result.

## Labels fan-in, score, and report

After forecast execution, dispatch the protected fan-in with the exact
workflow run and attempt. This is the sole retained workflow that accepts a
labels-release URI:

```bash
gh workflow run fan-in-publish.yaml --ref main \
  -f release_sha=<full-main-sha> \
  -f cycle_id=<cycle-id> \
  -f forecast_run_id=<run-id> \
  -f forecast_run_attempt=<attempt> \
  -f manifest_uri=<immutable-manifest-uri> \
  -f forecast_release_uri=<immutable-forecast-release-uri> \
  -f artifact_root_uri=<immutable-artifact-prefix/> \
  -f model_registry_uri=<immutable-model-registry-uri> \
  -f labels_release_uri=<immutable-labels-release-uri> \
  -f model_key=<provider:model-id> \
  -f publish=false \
  -f artifact_retention_days=14
```

Fan-in verifies the exact successful forecast attempt, revalidates the paired
manifest and releases, reads only the declared receipts, and runs the strict
release-based score and report path. Publication remains false until the
operator has reviewed the sanitized report and the protected publication
authority permits the requested destination.

The strict local contract is also available for an authenticated receipt set:

```bash
uv run legalforecast score \
  --runs <run-records.jsonl> \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <artifact-root> \
  --manifest <run-manifest.json> \
  --model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output scores.json \
  --unit-scores-output unit_scores.jsonl

uv run legalforecast report \
  --scores scores.json \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <artifact-root> \
  --manifest <run-manifest.json> \
  --frozen-model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output-dir reports/
```

For a local provider-free reproduction of this sequence, use the fixture
instructions in [reproduce-or-audit.md](reproduce-or-audit.md). The fixture
proves command and artifact compatibility; it is not live-cycle evidence.

## Reporting and withdrawal

The report consists of the JSON, CSV, Markdown, and HTML leaderboard artifacts
bound to the score identity. Publish only those sanitized outputs and their
machine-readable provenance. Never publish labels, raw provider responses,
private source bytes, or private withdrawal reasons.

If a published case must be removed, use the repository's withdrawal contract
and publish the resulting public erratum. Withdrawal does not rewrite an
immutable prior release or silently alter score artifacts.

## Infrastructure boundary

The retained `infra/official-eval` root contains the IAM policy for the public
forecast, preparation, manifest handoff, and fan-in roles. The packet and
results buckets remain externally owned storage and are not imported into that
root. Infrastructure plans are provider-free source evidence only; the
protected environment, exact plan review, apply, storage checks, and live
workflow evidence remain separate operator gates.

Remote state, IAM import, and post-provision checks remain human-authorized
operations described by the infrastructure README. A source checkout or
Terraform plan is not proof that remote state or live storage has been applied.

The one-time bootstrap procedure remains documented in
`infra/official-eval-bootstrap/README.md` under the **One-time AWS/Terraform bootstrap trust anchor**. Do not run Terraform locally with production credentials from this runbook, and do not infer live authority from source files or a green CI job.
