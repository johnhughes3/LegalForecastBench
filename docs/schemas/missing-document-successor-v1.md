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
`(candidate_id, docket_entry_number, requested_role)` obligation. It binds the
material `source_document_id`, acquisition source and cost, byte hash and count,
markdown hash, admitted role, and validator version.

`legalforecast.missing_document_exclusion.v1` records either a removed inherited
document whose bytes mismatch its selected role or the terminal reason an
approved missing-document obligation was not admitted.

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
