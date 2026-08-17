# Missing-document successor v1 schemas

These schemas define the generic repair boundary for an already-selected
cohort. They do not authorize acquisition, evaluation, freeze, dispatch, or
publication.

## `legalforecast.repair_manifest_approval.v1`

An exact-key approval sidecar:

- `schema_version`
- `decision` (`approve`)
- `manifest_sha256`
- `maximum_cost_usd`
- `candidate_count`
- `repair_count`
- `keep_count`
- `replace_count`
- `missing_slot_count`

Verification recomputes the manifest digest and all counts before minting the
opaque approval capability used by the projector.

## Inclusion and exclusion ledgers

`legalforecast.missing_document_inclusion.v1` records one admitted
`(candidate_id, docket_entry_number, document_selector, requested_role)`
obligation. The selector distinguishes a main document from same-entry
attachments. The record binds the material `source_document_id`, acquisition
source and cost, byte hash and count, markdown hash, admitted role, and validator
version.

New inclusions stamp `legalforecast.document_body_role_validator.v2`, which
recognizes the cohort-policy v3 fallback role `other_claim_bearing_filing` on
claim-asserting body text and refuses to admit an `opposition` or `reply` on a
single incidental keyword — the word must appear in a responsive-brief
construction. Artifacts stamped `…validator.v1` keep their original semantics;
see [the migration note](../cycle-1-document-repair-contract-migration.md).

`legalforecast.missing_document_exclusion.v1` records either a removed inherited
document whose bytes mismatch its selected role or the terminal reason an
approved missing-document obligation was not admitted. A candidate-level
exclusion records an approved `replace` recommendation and clears that
candidate's inherited documents pending reserve replacement.

Each approved obligation appears in exactly one of the inclusion or terminal
slot-exclusion ledgers.

## `legalforecast.missing_document_successor_state.v1`

The sealed state binds:

- exact repair-manifest and approval digests;
- predecessor selection digest;
- approved and paid cost totals;
- approved, included, excluded, terminal, and removed-mismatch counts; and
- SHA-256 commitments for successor selection and both ledgers.

Artifacts use the frozen canonical artifact JSON codec: UTF-8, sorted keys,
compact separators, non-ASCII preserved, non-finite numbers rejected, and one
trailing newline.
