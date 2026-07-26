# Opinion docket-gap plan v1

`legalforecast acquisition plan-opinion-docket-gaps` verifies a complete saturated screening snapshot and projects the cost of refreshing authoritative docket history for public-opinion-backed candidates whose current RECAP history cannot prove the target motion, unique decision row, or earliest written disposition.

The source observation remains an `excluded` terminal with reason `opinion_backed_docket_history_incomplete`; it is refreshable acquisition evidence, not a clean-screen acceptance.

## Admission boundary

The observation path first revalidates the exact resolved RECAP identity, the frozen complete opinion-source transfer, the CourtListener cluster and single sub-opinion, the opinion date, a safe public CourtListener PDF path, response and text hashes, and a verbatim passage recognized as an actual MTD disposition.

If the reconstructed RECAP history lacks a unique same-day decision anchor, the evidence records `packet_eligible=false`, `paid_gap_candidate=true`, `target_motion_linkage_proven=false`, and `earliest_written_disposition_proven=false`.

The opinion never invents a docket entry, target motion, complaint, brief, document identifier, or first-disposition proof.

## Planner contract

The planner consumes only the exact verified exclusion reason and its source-binding, saturation, reconstruction, and opinion commitments.

The self-hashed summary binds the authenticated source manifest, cycle hash, batch identity and digest, and `exclusions.jsonl` commitment.

Each output item contains only the RECAP docket identity, public decision identity and hashes, the independently revalidated eligibility anchor and decision-window end, `refresh_scope=docket_history_only`, the explicit per-docket cost reservation, and `packet_eligible=false`.

The plan and summary set `paid_activity_requested=false` and `paid_activity_executed=false`; the command cannot acknowledge fees, purchase a docket or document, or supply packet inputs.

After a separately authorized docket-history refresh, the candidate must be observed again through the ordinary canonical REST screen and must independently prove the unique target motion, earliest written disposition on or after 2026-06-30, required pre-decision materials, privacy and restriction clearance, leakage screening, and all downstream packet gates.

## Example

```bash
uv run legalforecast acquisition plan-opinion-docket-gaps \
  --output-root artifacts/cycle-1/opinion-docket-gap-plan \
  --snapshot artifacts/cycle-1/snapshots/current \
  --expected-cycle-hash "$EXPECTED_CYCLE_HASH" \
  --expected-snapshot-manifest-sha256 "$EXPECTED_MANIFEST_SHA256" \
  --cost-per-docket-usd 3.05 \
  --execute
```

The dollar value is a projection supplied by the operator; it does not modify or bypass any configured budget cap.

All output, log, and run-card paths must be distinct and outside the immutable source snapshot. Existing deterministic outputs are reused only when their bytes match exactly.
