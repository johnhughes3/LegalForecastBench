# Exact-100 document-repair executor v1

`legalforecast.exact100_document_repair_execution.v1` is a provider-neutral bridge from one authenticated full repair plan and its exact five-case pilot projection to existing acquisition primitives. It binds every pilot candidate's exact docket-snapshot bytes, requires exactly one main RECAP document for each planned docket entry, preserves the approved free-versus-paid route, and emits a `MissingCoreBudgetPlan` with an explicit `$3.00` reservation and the pilot's approved aggregate cap.

Before paid execution, the bridge verifies an existing typed purchase policy. The policy's per-document reservation must equal `$3.00`, and its remaining global and per-case headroom must cover the exact emitted budget. The bridge does not mint purchase approval, initialize a ledger, acknowledge fees, call a provider, or submit a purchase; callers pass the verified policy and budget to the established ledgered RECAP Fetch executor.

`legalforecast.exact100_document_repair_receipt.v1` records the exact ordered execution outcomes. Every row binds the full-plan, pilot, execution, docket snapshot, candidate, docket entry, and RECAP document identities and records route, disposition, retry count, monotonic duration, committed cost, and retry permission. An unknown paid outcome retains its approved reservation, is permanently nonretryable, and deterministically marks every later planned operation `not_attempted_after_unknown`.

These sidecars do not seal the repaired corpus. Acquired bytes still require exact hash/length and semantic role validation through the missing-document successor before admission, and a complete exact-100 successor remains a separate immutable artifact.
