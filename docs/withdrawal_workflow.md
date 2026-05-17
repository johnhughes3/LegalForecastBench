# Withdrawal Workflow

This workflow handles sealed-case orders, restricted filings, source-system
takedowns, sensitive-party concerns, and material corrections after a cycle has
been frozen. It keeps private bytes removable without silently rewriting public
benchmark history.

Live account IDs, bucket names, role ARNs, SSO URLs, court-sealed text, and
private object-store URLs do not belong in this repository or in public errata.

## Roles And Inputs

The data steward owns destructive withdrawal work through the
`cos.benchmark.data-steward` profile. The data operator may help identify and
hash affected objects through `cos.benchmark.data-operator`, but ordinary
evaluation jobs and packet-read roles must not read `source-documents/`,
`extracted-text/`, `audit-bundles/`, `withdrawn/`, or `quarantine/`.

The steward starts from a private intake note kept in the vault, not from a
GitHub issue containing sensitive text. The intake note records:

- the court order, source notice, or correction request;
- affected `cycle_id`, `case_id`, `candidate_id`, and source-document handles;
- affected packet object keys under `model-packets/`;
- affected public artifact paths, releases, mirrors, indexes, prompts, or logs;
- original manifest hashes and any replacement manifest hashes;
- the non-sensitive public reason that may appear in errata.

## Ledger Contract

Every withdrawal creates a private JSONL ledger record using
`legalforecast-withdrawal-ledger-v1`. The durable fields are:

| Field | Purpose |
| --- | --- |
| `withdrawal_id` | Stable incident identifier, unique within the ledger |
| `cycle_id` | Frozen cycle affected by the withdrawal |
| `scope` | `case`, `document`, `packet`, or `public_artifact` |
| `reason` | Internal reason code such as `sealed_or_restricted` |
| `public_reason` | Non-sensitive reason safe for public errata |
| `effective_at` | Time the material became blocked for future use |
| `case_id` / `candidate_id` | Public-safe benchmark identifiers, when known |
| `source_document_ids` | Source handles or internal IDs, not raw text |
| `packet_object_keys` | Affected `model-packets/` keys |
| `public_artifact_paths` | Public paths, release files, mirror paths, or index keys |
| `private_tombstone_key` | `withdrawn/` or `quarantine/` tombstone key |
| `errata_path` | Public-safe `manifests/` or `reports/` errata path |
| `supersedes_manifest_sha256` | Original manifest hash |
| `replacement_manifest_sha256` | Replacement manifest hash, if issued |
| `score_bundle_superseded` | Whether official scores need a replacement bundle |
| `future_use_blocked` | Always true for valid withdrawal records |

The ledger is private because it may reference packet object keys and private
tombstone locations. Public errata are generated from the ledger but omit raw
document text, extracted text, private object-store URLs, bucket names, account
IDs, and provider credentials.

## Operational Steps

1. Freeze current identifiers: record the old manifest hash, packet keys, source
   handles, run IDs, release tags, and public artifact paths before mutating
   storage.
2. Move, copy, or delete affected raw documents and extracted text under
   `withdrawn/` or `quarantine/` as the legal instruction requires.
3. Quarantine affected model packets and audit bundles so future run-input
   manifests cannot reference them.
4. Add the withdrawal ledger record and regenerate the run-input manifest after
   filtering withdrawn `case_id`, `candidate_id`, `source_document_ids`, and
   `packet_object_keys`.
5. Remove or replace affected GitHub Actions artifacts, releases, public
   mirrors, search indexes, embeddings, prompts, and logs when public mirrors or
   other surfaces include raw documents, extracted source text, or now-restricted
   packet content.
6. Publish a public-safe errata record under `manifests/` or `reports/`. If the
   withdrawal changes scores, publish a superseding score bundle and mark the old
   score bundle superseded.
7. Re-run the official environment validation and the raw-artifact guardrails
   before using the replacement run-input manifest.

## Future-Run Exclusion

Official workflow matrix construction must load the private withdrawal ledger
before dispatching case jobs. Any run-input row matching a withdrawn case,
candidate, source document, or packet key is excluded. A workflow that cannot
load the ledger for a cycle with known withdrawals should fail closed rather
than run stale packets.

The public reconstruction manifest keeps only source handles, hashes,
withdrawal/tombstone status, manifest hashes, and errata paths. It must not
publish raw filing text unless a separate redistribution review approves that
specific text release.

## Verification Checklist

Before closing a withdrawal:

- packet-read roles cannot read `withdrawn/` or `quarantine/`;
- run-input manifests no longer contain withdrawn cases, documents, or packets;
- public artifacts contain no raw filings, extracted text, audit-only
  dispositions, secrets, provider account identifiers, private object-store
  URLs, hidden files, or stale search/index material;
- errata preserve prior manifest hashes and replacement hashes without exposing
  sensitive text;
- score changes, if any, have a superseding score bundle and non-sensitive
  public note.
