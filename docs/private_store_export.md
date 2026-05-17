# Private Store Export

Official evaluation jobs consume frozen packet exports. They must not call
Case.dev, PACER, CourtListener, or fallback acquisition code while scoring
models.

After local acquisition and packet assembly, stage an export bundle with:

```bash
uv run python -m legalforecast.publication.private_store_export \
  --source-dir tmp/acquisition-cycle \
  --output-dir tmp/private-store-export \
  --cycle-id cycle-2026-05
```

The command writes local object-store staging paths under
`objects/packet/` and `objects/results/`. Maintainers can sync those staged
objects to the COS-managed packet and results buckets with the
`cos.benchmark.data-operator` profile after checking the verification report.

## Inputs

The source directory must contain:

- `document-manifest.jsonl` with `source_document_id` and local `path`;
- `candidate-manifest.jsonl` with source handles, source hashes, model-mounted
  flags, and manifest record hashes;
- `packets.jsonl` with model-visible packet records.

Optional inputs are included when present:

- `extracted_texts.jsonl`;
- `retrievals.jsonl`;
- `linkage.jsonl`;
- `exclusion-ledger.jsonl`;
- `accounting.jsonl`.

The exporter verifies every copied object by SHA-256. Source documents must
match the hashes recorded in `candidate-manifest.jsonl`; otherwise the export
fails before producing a usable manifest.

## Outputs

The private packet staging tree contains:

- `source-documents/{cycle_id}/{case_id}/{source_document_id}.{ext}`;
- `extracted-text/{cycle_id}/extracted_texts.jsonl`, if present;
- `model-packets/{cycle_id}/{case_id}/{ablation}.json`;
- `audit-bundles/{cycle_id}/acquisition-audit.json`.

The results staging tree contains public-safe manifests:

- `manifests/{cycle_id}.freeze.json`;
- `manifests/{cycle_id}.run-inputs.json`;
- `manifests/{cycle_id}.public-reconstruction.json`.

The root `verification-report.json` is a maintainer-side transfer check. It
lists staged object keys, SHA-256 hashes, byte sizes, classifications, and the
non-secret accounting summary. It is not a raw-document store.

## Publication Boundary

Public-safe manifests contain source handles, object hashes, model-packet
hashes, run-input rows, and redistribution status. They do not contain raw
source-document bytes, extracted filing text, audit bundle content, provider
credentials, account IDs, bucket names beyond protected environment values, or
private object-store URLs.

Evaluation workflows consume only the run-input manifest and
`model-packets/` objects. Acquisition and export remain a separate maintainer
operation.
