# Exact-100 document-repair executor v2

`legalforecast.exact100_document_repair_execution.v2` supersedes v1 without changing or reinterpreting any v1 artifact. Everything the [v1 contract](exact100-document-repair-executor-v1.md) specifies about resolution, purchase authority, journal capability, the dependency-injected runner, and sealing is unchanged.

The single difference is what the execution digest covers. Each operation record adds two fields derived from the authenticated CourtListener snapshot:

- `public_clearance`: `null`, or an object with exactly `status`, `is_private`, and `is_sealed`. The runtime already refuses `null` before a paid `acquire()`; under v2 the derivation is inside the committed bytes rather than beside them.
- `paid_clearance_pending`: whether the resolved paid route still owes a delivery-time clearance basis.

Under v1 both fields sat outside `to_record()`, so `object.__setattr__` could rewrite them without invalidating `execution_sha256`. Under v2 every boundary that recomputes the execution commitment — `record_document_repair_outcomes`, the runner, `seal_document_repair_execution`, and verify-only replay — fails closed on that mutation.

`legalforecast.exact100_document_repair_receipt.v1` is unchanged and remains the only receipt schema. Receipt ledger rows still carry the frozen v1 operation spelling, so no receipt bytes move; a v2 execution is bound into its receipt through `execution_sha256` alone. Receipt authentication now also requires an independently supplied `expected_receipt_sha256` at `seal_document_repair_execution` and `verify_document_repair_pilot_bytes`, matching what `replay_document_repair_receipt` already required for persisted bytes.

Freshly built executions mint v2. `build_document_repair_execution` and `build_full_document_repair_execution` accept `schema_version=` so v1 bytes stay reproducible for verify-only replay of executions that were committed before the migration; see [the migration note](../cycle-1-document-repair-contract-migration.md).
