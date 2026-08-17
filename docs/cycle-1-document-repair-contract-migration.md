# Cycle 1 document-repair contract migration

**Status:** adopted 2026-08-16 · authorized under the versioned-migration path in [cycle-1-change-control.md](cycle-1-change-control.md).

Two authenticated contracts in the document-repair lane widen together here. Neither is edited in place: each gets a new version id, and every artifact already committed under the old id keeps its original bytes and its original semantics.

## 1. What changes

### `legalforecast.exact100_document_repair_execution.v1` → `.v2`

The derived snapshot `public_clearance` (and the paired `paid_clearance_pending`) move inside the committed operation record. See [exact100-document-repair-executor-v2.md](schemas/exact100-document-repair-executor-v2.md). Under v1 those fields were deliberately outside `to_record()`, so an in-process `object.__setattr__` on `public_clearance` did not invalidate `execution_sha256`; under v2 it does, at every boundary that recommits the execution.

### `legalforecast.document_body_role_validator.v1` → `.v2`

The body-vs-role validator behind `missing_document_inclusion.v1` changes in two ways:

- **Widened**: `other_claim_bearing_filing` — the cohort-policy v3 fallback claim-bearing role — is now recognizable. v1 always returned `false` for it, so no v1-stamped artifact can have relied on that rejection.
- **Tightened**: `opposition` and `reply` are no longer admitted on a single incidental keyword. Admission requires the word in a responsive-brief construction (`in opposition to …`, `response in opposition to …`, `reply memorandum`, `reply in further support of …`, `reply to the opposition`). A declaration that merely mentions "the opposition", or an order noting that no reply was filed, no longer satisfies the role.

New inclusions stamp `role_validator_version: legalforecast.document_body_role_validator.v2`.

## 2. Affected artifacts

Named by identity, not by inlined digest — the committed hex lives in the run cards and stage roots, which are the authority:

- **Pilot-scope executions**: the five-case `legalforecastbench-3ak.11` pilot receipts and their `execution_sha256` values.
- **Full-plan executions**: any `scope=full_plan` execution committed before this note, and the successors sealed from them.
- **Inclusion ledgers**: every `legalforecast.missing_document_inclusion.v1` row stamped `…document_body_role_validator.v1`, and the `legalforecast.exact100_missing_document_successor.v2` artifacts containing them.

No hash in any of those artifacts is patched. They remain valid under their recorded versions.

## 3. Replaying the current chain

`build_document_repair_execution` and `build_full_document_repair_execution` take `schema_version=`. Passing `legalforecast.exact100_document_repair_execution.v1` reproduces the pre-migration bytes exactly, so verify-only replay of already-acquired pilot bytes (`verify_document_repair_pilot_bytes`) authenticates against the `execution_sha256` those artifacts recorded. Omitting the argument mints v2, which is what all new work does.

Because the receipt schema is unchanged and receipt ledger rows keep the frozen v1 operation spelling, no `receipt_sha256` moves in either direction.

## 4. Batching

Both contract changes land in one migration rather than two, and every known violation of the tightened role validator is re-derived in that single pass. Re-running a repair projection under v2 may terminally exclude a slot that v1 admitted on an incidental keyword; that exclusion is the intended outcome and is recorded in the exclusion ledger with `acquired_bytes_mismatch_requested_role`, not patched around.

## 5. What this note does not authorize

No provider call, no purchase, no freeze, no dispatch, no publication. It authorizes exactly the two version bumps above and the code that emits them.
