# Retained cohort extension v1

`acquisition extend-target-cohort` is the noncharging bridge from an executed exact 100-case `project-target-cohort` root to an exact combined 150-case cohort.

The command requires the complete base projection root, the full resolved selection and case-relevance records, the full acquired-document manifest and authenticated clearance rows, the frozen target-150 cohort policy, and the exact snapshot manifest.
It rejects symlink inputs, overlapping input/output roots, changed base output commitments, changed snapshot lineage, duplicate candidate/docket/motion identities, incomplete clearance coverage, restricted material, truncated or insufficient omitted frontiers, and any cumulative obligation above the immutable cap.

The base selection is retained in its original order.
For each candidate-scoped JSONL artifact, the combined artifact begins with the exact original base bytes and appends only the selected incremental rows.
Incremental candidates are chosen only from the eligible omitted full-pool frontier and are ranked by the existing deterministic missing-core budget rule.
The final exclusion ledger contains every full-pool candidate not in the combined 150 and no selected candidate.

`retained-cohort-budget.json` separately records base projected cost, incremental projected cost, pre-existing reserved obligations, unknown-outcome obligations, reconciled write-offs, cumulative obligation, and remaining headroom.
The three pre-existing obligation fields are disjoint and additive; the command never releases any of them.
The standard combined `missing-core-budget-plan.json` preserves the first 100 case plans and appends the 50 incremental plans so it remains consumable by downstream purchase-policy tooling.

`retained-cohort-extension.json` binds every base and full-pool input hash, cohort-policy hash, snapshot lineage value, selected-ID sequence, budget hash, output hash, and base-prefix byte count/hash.
An identical `--resume` invocation verifies all immutable output bytes and the completed run card, then returns without rewriting artifacts or appending another completion event.

The command has no provider client, purchase flag, fee-acknowledgment flag, or live mode.
