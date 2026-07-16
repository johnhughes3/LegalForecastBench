# Disclosure review bundle v1

The disclosure-review bundle is the authenticated, exact-byte human-review lineage required before a downloaded court document may enter parsing, labeling, or packet planning.

The production path is `prepare-disclosure-review` -> `preflight-disclosure-review-signer` -> explicit human decisions -> `build-disclosure-review-bundle` -> external hardware SSHSIG -> `seal-disclosure-review-bundle` -> `clear-disclosures`.

The commands are provider-free and noncharging.
They do not authorize a purchase, parser or labeling-model call, model evaluation, official freeze, or dispatch.

## Security boundary

The public acquisition root and the controlled private review store are separate roots.
`prepare-disclosure-review` writes the value-redacted worksheet under the acquisition output root and writes `private-document-inspection-map.jsonl` only under the explicitly supplied `--controlled-private-store-root`.
The private map contains absolute local inspection paths and must not be copied into a run card, packet input, checked-in artifact, provider prompt, or public output.
The worksheet, signing statement, and receipt bind document and source hashes without disclosing those private paths or matched sensitive values.

Production authentication requires an externally precommitted reviewer-policy SHA-256 and a human hardware-backed OpenSSH security-key identity.
The only accepted production public-key types are `sk-ssh-ed25519@openssh.com` and `sk-ecdsa-sha2-nistp256@openssh.com`.
An ordinary software SSH key cannot be represented as a human reviewer identity.
Software-key service identities exist only for direct test fixtures behind an internal opt-in that the CLI does not expose; they are not a production alternative.

The production hardware signer is tracked by `LegalForecastBench-5qd6.39.7.1`.
If preflight or signing reports that no hardware-backed signer is configured, stop this stage and update that bead rather than substituting a local key or weakening the policy.

## Exact inputs

Preparation consumes the exact bytes of:

- `review-requests.jsonl`, with one `legalforecast.disclosure_review_request.v1` row per document and `required_human_decision: "cleared_or_quarantined"`;
- the merged download-manifest JSONL;
- restriction-evidence JSONL; and
- every document addressed by the manifest beneath `--document-root`.

The request, manifest, and restriction key sets must be identical on `(candidate_id, source_document_id)`.
Duplicate, missing, or extra keys fail closed.
The request `sha256`, `byte_count`, and `free_or_purchased` values must equal the manifest, and the scanner rehashes the actual document bytes.

## Worksheet and private inspection map

`disclosure-review-worksheet.json` has schema `legalforecast.disclosure_review_worksheet.v1` and these top-level fields:

- `schema_version`;
- `source_sha256`, containing the exact raw-byte SHA-256 values for `review_requests`, `download_manifest`, and `restriction_evidence`;
- `document_set_sha256`, the SHA-256 of the canonical ordered `documents` array;
- `document_count`; and
- `documents`.

Each worksheet document contains `candidate_id`, `source_document_id`, `sha256`, `byte_count`, `free_or_purchased`, `restriction_status`, restriction-evidence count and hash, restriction-evidence categories, automated-marker categories, and `required_human_decision`.
The worksheet records marker categories, not matched sensitive values.

The private inspection map is newline-delimited JSON with one exact `(candidate_id, source_document_id, inspection_path, sha256, byte_count)` row per worksheet document.
Every path must resolve beneath the document root to a unique regular file without a symlink component, and its bytes must match the worksheet hash.

## Reviewer policy

The reviewer-policy JSON has schema `legalforecast.disclosure_reviewer_policy.v1` and exactly these fields:

```json
{
  "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
  "reviewer_id": "<reviewed-human-identity>",
  "ssh_principal": "<reviewed-sshsig-principal>",
  "ssh_public_key": "sk-ssh-ed25519@openssh.com <base64-public-key>",
  "identity_kind": "human_hardware",
  "controlled_store_uri_prefix": "private-store://<authority>/<review-root>",
  "signature_namespace": "legalforecast-disclosure-review-v1"
}
```

The value passed through `--expected-reviewer-policy-sha256` must come from the independently reviewed, externally recorded precommitment for those exact policy bytes.
Computing a digest from a newly supplied policy at invocation time and treating it as precommitted defeats the pin and is not permitted.
The `controlled_store_uri_prefix` and every review's `controlled_store_provenance` use the `private-store://` scheme; the signed URI must equal the prefix or be a descendant path with a segment boundary.

## Human decisions and canonical reviews

`record-disclosure-review-decisions` is the supported production recorder.
It uses a TTY only as its interactive review interface, with its output, run card, log, and durable per-document checkpoints inside `--controlled-private-store-root`; the TTY is not authentication authority.

The command displays each private inspection path and requires the operator to type the full inspected hash and explicit decision, while the later hardware SSHSIG remains the sole reviewer authentication authority.
After every row, it displays counts and a batch hash and requires an exact typed batch confirmation.
Do not hand-author or bulk-import the decision JSONL.

The recorder opens inspection bytes and checkpoints through no-follow file descriptors, requires one regular-file link, and compares file metadata before and after each read.
It reopens and rehashes the inspection bytes after the decision prompt, before publishing the per-document checkpoint.
The final decision JSONL is derived byte-for-byte from those reloaded checkpoints; a completed resume rejects any decision artifact that is not exactly checkpoint-derived.

`--resume` accepts a valid failed-history prefix and can repair either half of an interrupted terminal publication (an exact completed run card without its terminal log record, or the reverse) without rewriting the surviving marker.
Malformed inputs, interrupted interaction, and artifact publication failures produce failed run-card/log metadata when no completion marker already exists; a completed marker is never overwritten by later failure handling.

`status` is exactly `cleared` or `quarantined`.
A document with any automated marker or a restriction status other than `public` or `redacted` cannot be cleared; record it as quarantined and allow the downstream replacement process to handle the case.
The decisions must cover the worksheet exactly, `inspected_sha256` must equal the worksheet document hash, `recording_method` must be `interactive_review_cli`, `intended_reviewer_id` must equal the later signed policy identity, and every row carries the recorder's common `batch_confirmation_sha256`.

`build-disclosure-review-bundle` converts those decisions to canonical, newline-terminated `disclosure-reviews.jsonl`.
Every row has exactly `candidate_id`, `source_document_id`, `sha256`, `status`, `reviewer_id`, `controlled_store_provenance`, `reviewed_at`, `inspected_at`, and `inspected_sha256`.
The timestamps must ultimately satisfy `inspected_at <= reviewed_at <= authenticated_at`.

## Signing statement and SSHSIG

`disclosure-review-signing-statement.json` has schema `legalforecast.disclosure_review_statement.v1`.
It binds the exact review JSONL, canonical recorder decision JSONL, batch confirmation hash, worksheet, review requests, download manifest, restriction evidence, document set and count, authenticated reviewer, controlled-store URI, authentication method, authentication time, reviewer-policy hash, signature namespace, and a human-visible per-document decision summary with cleared/quarantined counts.

Run `preflight-disclosure-review-signer --signing-statement ...` immediately before signing and inspect every displayed candidate/document/status row and the counts.

The human signs the exact statement file outside LegalForecastBench:

```bash
/usr/bin/ssh-keygen -Y sign \
  -f <hardware-backed-signing-key-or-key-reference> \
  -n legalforecast-disclosure-review-v1 \
  <disclosure-review-signing-statement.json>
```

OpenSSH writes the detached signature beside the input as `<disclosure-review-signing-statement.json>.sig`.
Do not pipe a reformatted statement into the signer, edit either file after signing, change the namespace, or sign with an ordinary local Git key.

## Receipt and verification

`seal-disclosure-review-bundle` independently verifies the SSHSIG against the exact externally pinned policy and exact source bytes, then emits `disclosure-review-receipt.json` with schema `legalforecast.disclosure_review_receipt.v2`:

```json
{
  "schema_version": "legalforecast.disclosure_review_receipt.v2",
  "statement": { "schema_version": "legalforecast.disclosure_review_statement.v1" },
  "sshsig_base64": "<base64-armored-sshsig-bytes>",
  "decision_artifact_base64": "<base64-canonical-decision-jsonl>"
}
```

The displayed `statement` object is abbreviated; the actual receipt contains the complete, exact statement.
Seal rejects a changed source, worksheet, review artifact, canonical decision artifact, batch confirmation, status count, document set, reviewer policy, identity, namespace, provenance URI, timestamp ordering, or signature.

`clear-disclosures` then recomputes the worksheet from the current document and source bytes, requires byte-for-byte equality with the signed worksheet, verifies the receipt again, rescans every document, and writes `disclosure-clearance.jsonl` plus `disclosure-quarantine.jsonl`.
No document is cleared merely because it has a signed decision: all automated, restriction, byte-integrity, coverage, and authentication checks still apply.
Passing this command is necessary but not sufficient for downstream admission.
Every projection, recovery, parse, extension, packet, and finalization boundary that consumes the clearance must independently verify the completed clearance run card, its signed-review source commitments, and the same reviewer-policy pin; if a downstream command's current contract omits that lineage, stop before that command rather than treating the clearance files alone as authority.

## Immutability and resume

All three producer stages are dry-run unless `--execute` is present and default to resume behavior.
Use `--resume` explicitly in the operator runbook.
On resume, existing deterministic artifacts must match the newly derived bytes; drift fails closed rather than overwriting a frozen artifact.
Use `--no-resume` when an exclusive first publication is required.
Never hand-edit a worksheet, canonical reviews file, signing statement, signature, receipt, clearance file, or run card.

The commands reject output/input aliasing, symlinked or hard-linked unsafe artifacts, output overlap, and a private store nested inside the acquisition output root or vice versa.
