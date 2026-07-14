# Retained cohort extension v1

`acquisition extend-target-cohort` is the noncharging bridge from an executed exact 100-case `project-target-cohort` root to an exact combined 150-case cohort.

The command requires the complete base projection root, the full resolved selection and case-relevance records, the full acquired-document manifest and authenticated clearance rows, the frozen target-150 cohort policy, the exact snapshot manifest, and the canonical purchase-policy artifact plus its bound SQLite journal.
It rejects symlink inputs, overlapping input/output roots, changed base output commitments, changed snapshot lineage, duplicate candidate/docket/motion identities, incomplete clearance coverage, restricted material, truncated or insufficient omitted frontiers, and any cumulative obligation above the immutable cap.

The base selection is retained in its original order.
For each selected-candidate JSONL artifact, including the original free and purchased manifest partitions, the combined artifact begins with the exact original base bytes and appends only the selected incremental rows.
The target-100 exclusion ledger is verified against its original projection but cannot remain a prefix because some former omissions become selected; the combined exclusion ledger is therefore rederived at the new boundary.
Incremental candidates are chosen only from the eligible omitted full-pool frontier and are ranked by the existing deterministic missing-core budget rule.
The final exclusion ledger contains every full-pool candidate not in the combined 150 and no selected candidate.

`retained-cohort-budget.json` separately records base projected cost, incremental projected cost, opening commitments, confirmed spend, live reservations, unknown-outcome reservations, reconciled write-offs, cumulative obligation, and remaining headroom.
These categories are derived from the verified canonical journal rather than supplied by an operator, must reconcile exactly to the journal's committed amount, and are never released by this command.
The artifact binds both the purchase-policy identity and the journal state hash.
The standard combined `missing-core-budget-plan.json` preserves the first 100 case plans and appends the 50 incremental plans while recomputing frontier, omission, and intrinsic-exclusion metadata over the combined 150.

`retained-cohort-extension.json` binds every base and full-pool input hash, cohort-policy hash, snapshot lineage value, selected-ID sequence, budget hash, output hash, and base-prefix byte count/hash.
An identical `--resume` invocation validates the completed run card first, verifies all committed output bytes, and then returns without reconstructing or rewriting artifacts or appending another completion event.
Custom run-card and log paths are part of output-scope validation and cannot alias any input, cohort artifact, or each other.

The command has no provider client, purchase flag, fee-acknowledgment flag, or live mode.
