# Exact-100 reserve extension v1

`legalforecast.exact100_reserve_extension.v1` is the provider-free planning boundary that derives additional reserve capacity for an authenticated `legalforecast.zero_cost_successor_config.v1` cohort.

The planner does not accept candidate IDs. It derives the reserve from the complete authenticated 115-row candidate frontier, the original frozen target projection and five-row reserve, the final disclosure-clearance authority, and the current authenticated quarantine.

## Required authority

The caller first replays the exact-100 successor and passes the replay result alongside the successor projection. The two records must be identical, and the projection must commit the byte-exact 100-row selected cohort and the final disclosure-clearance bytes and run card.

The full frontier must use `legalforecast.target_cohort_candidate_frontier.v1`, contain exactly 115 unique rows, set `frontier_truncated` to false, preserve consecutive ranks under `(missing_core_document_count, estimated_cost_usd, candidate_id)`, and carry the complete preparation source-commitment set including the reconciled source-pool bytes. Its completed `materialize-target-cohort-frontier` run card must bind the frontier bytes and prove zero provider activity. The caller also supplies the materializer replay result, which must equal the frontier artifact.

The original `legalforecast.target_cohort_projection.v1` must bind the exact original selection, five-row ranked reserve, exclusions, and 115-row source pool. The exact-100 successor must in turn bind that projection. Each original reserve row is checked against the full frontier's cost, missing-document, and ranking fields.

The final clearance and current quarantine must each have a completed run card with nonempty source commitments, an exact output commitment, and false provider and paid activity. The final clearance bytes and card must match the commitments in the replay-authenticated exact-100 successor. The caller supplies the current-quarantine run-card replay result, which must equal the run card. Every current-quarantine candidate must belong to the exact-100 selection. The requested replacement count must equal the number of unique quarantined cases.

## Derived candidates

A candidate can enter the extended reserve only when all of the following are true:

- it is absent from the exact-100 selection;
- it has no frozen frontier exclusion;
- it is either an unused member of the original five-row reserve or has only `cleared` rows in the later authenticated clearance;
- it has no quarantined row in that clearance.

Eligible candidates are reranked solely by the original frozen ranking key. Already-selected candidates, final-clearance quarantines, frozen-frontier exclusions, and candidates without authenticated later clearance are recorded in `legalforecast.exact100_reserve_exclusion.v1` rows.

## Outputs

The pure planner returns:

- the same selected-cohort `bytes` object supplied by the caller;
- `legalforecast.exact100_extended_reserve.v1` rows;
- `legalforecast.exact100_reserve_exclusion.v1` rows;
- a `legalforecast.exact100_reserve_cost_plan.v1` record;
- `legalforecast.exact100_free_refresh_request.v1` rows for noncharging CourtListener REST refresh;
- the closed `legalforecast.exact100_reserve_extension.v1` summary.

The summary binds every input and output byte surface. The cost plan records the maximum projected cost but always sets `paid_permitted` to false. The summary always denies provider, paid, evaluation, freeze, and dispatch authority.

This schema does not itself authorize a CourtListener request. A later acquisition command may consume the free-refresh rows, but must remain limited to noncharging REST availability checks unless separate authenticated purchase authority exists.

## CLI status

The v1 Python planning interface is intentionally isolated from `legalforecast acquisition` command wiring. CLI integration must be rebased after the ranked-reserve v3 command contract lands so the two changes do not create competing reserve schemas or parser arguments.
