# Retained cohort extension v1

`acquisition extend-target-cohort` is the noncharging bridge from an executed exact 100-case `project-target-cohort` root to an exact combined 150-case cohort.

The command requires the complete base projection root; an immutable completed preparation root; its self-hashed config and summary; the provider-free `materialize-target-cohort-frontier` artifact and completed run card; the completed disclosure-clearance run card, exact reviews, and controlled-store receipt; the frozen target-150 cohort policy and exact snapshot manifest; and the canonical purchase-policy artifact plus its bound SQLite journal.
It resolves selection, case relevance, merged downloads, restriction evidence, and clearance output only through those authenticated roots and run-card commitments; the CLI no longer accepts four loose pool-file overrides.
It rejects symlink inputs, overlapping or hard-linked writable outputs, changed base output commitments, changed snapshot or preparation lineage, a substituted or truncated frontier, a changed review receipt, duplicate candidate/docket/motion identities, cross-candidate reuse of a purchase-document identity, incomplete clearance coverage, restricted material, insufficient omitted frontiers, and any cumulative obligation above the explicit combined cap.

The target-100 projection cap is historical immutable lineage and is derived from the authenticated base budget and preparation config; the operator does not restate or replace it.
The required `--combined-max-projected-budget-usd` is a separate explicit target-150 ceiling: it may exceed the base cap, but it cannot be below retained cost plus existing obligations or above the frozen cohort-policy cycle cap.
Passing the flag records a projection request only and does not authorize or execute a purchase.

The base selection is retained in its original order.
For each selected-candidate JSONL artifact, including the original free and purchased manifest partitions, the combined artifact begins with the exact original base bytes and appends only the selected incremental rows.
The target-100 exclusion ledger is verified against its original projection but cannot remain a prefix because some former omissions become selected; the combined exclusion ledger is therefore rederived at the new boundary.
Incremental candidates are chosen only from the eligible omitted full-pool frontier and are ranked by the existing deterministic missing-core budget rule.
The final exclusion ledger contains every full-pool candidate not in the combined 150 and no selected candidate.

`retained-cohort-budget.json` separately records base projected cost, incremental projected cost, opening commitments, confirmed spend, live reservations, unknown-outcome reservations, reconciled write-offs, cumulative obligation, and remaining headroom.
These categories are derived from the verified canonical journal rather than supplied by an operator, must reconcile exactly to the journal's committed amount, and are never released by this command.
The artifact binds both the purchase-policy identity and the journal state hash.
The journal must already exist, be nonempty, pass read-only SQLite integrity and schema checks, and carry the exact immutable purchase-policy identity; extension never creates or repairs a missing, empty, or truncated ledger.
The standard combined `missing-core-budget-plan.json` uses the canonical recomputation of case plans, frontier, omission, and intrinsic-exclusion metadata over the combined 150, while the selected-candidate JSONL artifacts retain their exact target-100 byte prefixes.

`retained-cohort-extension.json` binds every base and full-pool input hash; preparation config/summary and snapshot hashes; full-frontier bytes and policy identity; frontier-materialization, clearance, review, and receipt hashes; cohort-policy and purchase-journal state; selected-ID sequence; budget and output hashes; and each preserved base-prefix byte count/hash.
An identical `--resume` invocation validates the completed run card and committed output bytes first, and then returns without reading acquisition sources, opening the mutable purchase journal, reconstructing or rewriting artifacts, or appending another completion event.
Custom run-card and log paths are part of output-scope validation and cannot alias any input, cohort artifact, or each other.

The command has no provider client, purchase flag, fee-acknowledgment flag, or live mode.
The legacy target-100 preparation root is upgraded by the separate provider-free materializer without rerunning CourtListener, Case.dev, or Firecrawl; extension tests fail if any provider client is constructed.
