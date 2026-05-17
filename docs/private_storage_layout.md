# Private Storage Layout

Official evaluation packets live in the COS-managed LegalForecastBench artifact
account. LegalForecastBench treats that account as private object storage and
consumes only bucket names, prefixes, role ARNs, and frozen manifests supplied
through protected environment configuration or local vault files.

Live bucket names, AWS account IDs, root emails, SSO URLs, and operator notes do
not belong in this repository.

## Buckets And Prefixes

The private packet bucket contains model inputs and maintainer-only acquisition
material:

| Prefix | Classification | Intended Readers |
| --- | --- | --- |
| `source-documents/` | raw private filings and docket exports | local data operator and data steward only |
| `extracted-text/` | private extracted or OCR text | local data operator and data steward only |
| `model-packets/` | frozen model-visible packet shards | official eval jobs, local data operator, data steward |
| `audit-bundles/` | acquisition audit records and excluded dispositions | local data operator and data steward only |
| `withdrawn/` | sealed, suppressed, or withdrawn material | data steward only |
| `quarantine/` | takedown staging and tombstones | data steward only |

The separate results bucket contains non-sensitive official run outputs:

| Prefix | Classification | Intended Readers |
| --- | --- | --- |
| `run-cards/` | public-safe run cards | official aggregation, maintainers, publication |
| `manifests/` | public-safe freeze and reconstruction manifests | official eval jobs, maintainers, publication |
| `metrics/` | public-safe scores and diagnostics | official aggregation, maintainers, publication |
| `reports/` | public-safe leaderboard/report artifacts | official aggregation, maintainers, publication |

## Object Naming

Object keys are deterministic and cycle-scoped:

```text
source-documents/{cycle_id}/{case_id}/{document_id}.{extension}
extracted-text/{cycle_id}/{case_id}/{document_id}.normalized.txt
model-packets/{cycle_id}/{case_id}/{ablation}.json
audit-bundles/{cycle_id}/{case_id}/acquisition-audit.json
withdrawn/{cycle_id}/{case_id}/{document_id}.{extension}
quarantine/{cycle_id}/{case_id}/{document_id}.tombstone.json
manifests/{cycle_id}.freeze.json
manifests/{cycle_id}.run-inputs.json
manifests/{cycle_id}.public-reconstruction.json
run-cards/{cycle_id}/{run_id}.json
metrics/{cycle_id}/{run_id}.jsonl
reports/{cycle_id}/{run_id}/leaderboard.json
```

`cycle_id`, `case_id`, `document_id`, `ablation`, and `run_id` values must be
slug-safe. Keys must not contain absolute paths, `..`, hidden path components,
provider account identifiers, or raw court text.

## Manifest Contract

Each frozen cycle has a private freeze manifest in the results bucket at
`manifests/{cycle_id}.freeze.json`, plus a runner-facing input manifest at
`manifests/{cycle_id}.run-inputs.json`. Public release bundles may include only
the public-safe reconstruction manifest.

The freeze manifest is a JSON object with these top-level fields:

```json
{
  "storage_manifest_version": 1,
  "cycle_id": "cycle_yyyy_mm_label",
  "packet_bucket": "protected-env-value",
  "results_bucket": "protected-env-value",
  "packet_prefixes": ["model-packets/"],
  "result_prefixes": ["manifests/", "run-cards/", "metrics/", "reports/"],
  "model_packets": [],
  "source_documents": [],
  "audit_bundles": [],
  "withdrawn": []
}
```

Every object record referenced by a manifest must include:

| Field | Meaning |
| --- | --- |
| `key` | S3 object key under one of the approved prefixes |
| `sha256` | SHA-256 digest of the exact object bytes |
| `size_bytes` | Byte count used for transfer verification |
| `content_type` | Expected MIME type or structured artifact type |
| `classification` | `raw-private`, `model-visible-private`, `audit-private`, `withdrawn`, or `public-safe` |
| `source_handle` | Provider-neutral docket/document handle, not provider credentials |
| `redistribution_status` | `not-reviewed`, `blocked`, `approved-metadata-only`, or `approved-text` |
| `mounted_for_model` | Boolean that must be false for audit-only and withdrawn material |

S3 `version_id`, KMS key alias, and acquisition cost/accounting references may
be included when available. Provider account IDs and API credentials must not be
included.

The run-input manifest is a filtered view for official workflow matrix
construction. It may list `case_id`, `ablation`, packet object keys, packet
SHA-256 digests, packet byte sizes, and public-safe source handles. It must not
include raw source-document keys, extracted-text keys, audit-bundle keys,
withdrawn/quarantine keys, presigned URLs, provider account identifiers, or raw
court text.

The public reconstruction manifest is for outside reviewers who want to rebuild
the benchmark denominator without receiving private filings. It contains source
handles, court metadata, acquisition dates, object hashes, redistribution
status, and withdrawal/tombstone status. It does not contain raw filing text or
private object-store URLs unless a separate redistribution review approves that
specific text release.

## Hash And Runner Rules

Model packets must carry SHA-256 verification material for every packet object
and for every mounted source document or extracted-text object used to build the
packet. Official evaluation jobs must refuse to run if:

- the packet object hash differs from the freeze manifest;
- a packet references any `audit-bundles/`, `source-documents/`,
  `extracted-text/`, `withdrawn/`, or `quarantine/` key directly;
- an audit-only disposition is marked `mounted_for_model: true`;
- a public reconstruction artifact contains raw filing text without
  redistribution approval.

Evaluation jobs consume only frozen `model-packets/` and public-safe
`manifests/`. They do not call Case.dev, PACER, CourtListener, or acquisition
fallback tools.

## Access Boundaries

The GitHub packet-read role can list/read only `model-packets/` in the packet
bucket and public-safe `manifests/` in the results bucket. It cannot write or
delete either bucket and cannot read raw, extracted, audit, withdrawn, or
quarantine prefixes.

The optional GitHub results-writer role can write only tagged non-sensitive
objects under `run-cards/`, `manifests/`, `metrics/`, and `reports/`. It cannot
read or mutate packet-bucket objects and cannot delete result objects.

The local `cos.benchmark.data-operator` profile is for upload, download, hash
verification, and debug reads. The local `cos.benchmark.data-steward` profile is
separate and is used only for sealed-case takedown, quarantine, deletion, and
tombstone operations.

## Retention And Takedown

Packet and result buckets use versioning, encryption, SSL-only access, and
public access blocks. Raw case documents and extracted text must not be placed
under compliance-mode object lock because court-ordered removal must remain
possible.

When a document or case is sealed, corrected, withdrawn, or otherwise
suppressed:

1. move or copy affected private objects into `withdrawn/` or `quarantine/`;
2. remove future model-packet references to those keys;
3. write a non-sensitive tombstone under `quarantine/` and, if public impact
   exists, a public-safe errata record under `manifests/` or `reports/`;
4. keep only source handles, hashes, dates, and legal basis in public artifacts;
5. issue a superseding score bundle when withdrawal changes official results.
