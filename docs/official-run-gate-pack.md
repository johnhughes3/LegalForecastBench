# Official-run gate pack (preparation only)

> [!CAUTION]
> **HOLD.** This pack is for review and input preparation. Do not dispatch a
> protected workflow, resolve credentials, call a model provider, purchase a
> document, or publish an official result from these instructions. The held
> legacy-deletion PR must not merge until `legalforecast-f454` closes live
> ingest and two-pass QC.

This pack describes the retained public release boundary. A public run starts
with immutable release URIs and a locked manifest, executes the supported
forecast matrix, and ends at the protected labels fan-in. Private corpus
construction and source bytes are supplied by the companion
LegalForecastCorpus repository; they are not reconstructed here.

## Ownership

LegalForecastCorpus owns private source bytes, selection, unitization, quality
control, deterministic release issuance, and the OIDC staging handoff.
LegalForecastBench owns public release validation, manifest/run execution,
scoring, reporting, withdrawal records, and community publication.

The staging handoff is an interface, not a public acquisition path. It supplies
immutable `manifest_uri`, `forecast_release_uri`, `artifact_root_uri`,
`model_registry_uri`, and `labels_release_uri` values to the protected fan-in.
The forecast job receives only its approved artifact inputs and never receives
labels or private source bytes.

## Retained workflows

| Workflow | Responsibility | Required evidence |
| --- | --- | --- |
| `.github/workflows/run-benchmark.yaml` | Execute the frozen forecast matrix | Each run receipt binds the locked manifest, release digests, model key, and code revision |
| `.github/workflows/fan-in-publish.yaml` | Validate receipts, score, report, and publish | Protected environment approval plus complete receipt and release set |

Local action references in these workflows must resolve to an action checked
into this repository. The public release coherence test enforces that boundary
and rejects references to removed acquisition or legacy provider machinery.

## Preparation gates

Run the following provider-free checks against the exact release inputs before
requesting any protected dispatch:

```bash
uv run legalforecast manifest validate \
  --manifest <run-manifest.json> \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <release-root>

uv run legalforecast release validate \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <release-root>

uv run python -m legalforecast.contracts.ratchet
uv run pytest -q
```

Record the exact manifest SHA, release SHAs, model-registry digest, artifact
root digest, and code revision. A green fixture run or a local Terraform plan
is not evidence of a live official run.

## Protected handoff

After human review and protected-environment approval, dispatch the forecast
matrix with immutable URIs:

```bash
gh workflow run run-benchmark.yaml \
  --ref <reviewed-commit> \
  -f release_sha=<full-main-sha> \
  -f manifest_uri=<immutable-manifest-uri> \
  -f forecast_release_uri=<immutable-forecast-release-uri> \
  -f artifact_root_uri=<immutable-artifact-root-uri> \
  -f model_registry_uri=<immutable-model-registry-uri> \
  -f model_key=<provider:model-id> \
  -f ceiling_microusd=<positive-microusd-ceiling> \
  -f account=default \
  -f repeat_count=1 \
  -f max_parallel=4 \
  -f artifact_retention_days=14
```

Wait for every matrix receipt and verify that each receipt has the expected
manifest, release, model, code, and artifact bindings. Then request the
protected fan-in with the same exact inputs:

```bash
gh workflow run fan-in-publish.yaml \
  --ref <reviewed-commit> \
  -f release_sha=<full-main-sha> \
  -f cycle_id=<cycle-id> \
  -f forecast_run_id=<forecast-run-id> \
  -f forecast_run_attempt=<forecast-run-attempt> \
  -f manifest_uri=<immutable-manifest-uri> \
  -f forecast_release_uri=<immutable-forecast-release-uri> \
  -f artifact_root_uri=<immutable-artifact-root-uri> \
  -f model_registry_uri=<immutable-model-registry-uri> \
  -f labels_release_uri=<immutable-labels-release-uri> \
  -f model_key=<provider:model-id> \
  -f publish=false \
  -f hugging_face_release_version=<immutable-hf-release-version> \
  -f artifact_retention_days=14
```

The fan-in is the only supported publication boundary. It must fail closed on
missing receipts, mismatched identities, changed bytes, incomplete model
coverage, or an unapproved protected environment.

## Strict score and report contract

The supported local and protected score path consumes issued releases and
authenticated run records. It does not consume a private acquisition tree or
an aggregate command:

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

Publication is false by default during reproduction. Public reports may expose
score arithmetic and release metadata; they must not expose locked labels,
private withdrawal reasons, provider credentials, or restricted source bytes.

## Reporting, withdrawal, and community boundaries

The report output is derived from the strict score output and its release
identities. A withdrawal records a public erratum and removes the affected
public result without revealing private reasons or source bytes. Community
submissions use the documented separate registry and publication path and are
never silently promoted to official results.

## Infrastructure boundary

The retained Terraform root is `infra/official-eval/`; it describes the IAM
boundary for the official evaluation handoff and references externally managed
storage. The bootstrap notes describe the
**One-time AWS/Terraform bootstrap trust anchor** and its required human
approval. Source code, a Terraform plan, or merged workflow changes do not
prove that AWS resources, protected environments, or live storage are applied.

## Review record

Before unholding the PR, attach exact commit and workflow run IDs, release and
manifest digests, model identity, receipt set, artifact index, and protected
authorization evidence. If any item is absent or mutable, stop and retain the
hold.
