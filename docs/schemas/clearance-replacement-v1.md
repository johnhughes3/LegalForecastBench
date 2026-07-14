# Clearance replacement artifacts v1

`legalforecast.clearance_replacement_frontier.v1` freezes the complete canonical order used when a purchased document fails disclosure clearance.

Build it before activating the purchase broker:

```console
uv run legalforecast acquisition build-clearance-replacement-frontier \
  --cohort-policy COHORT_POLICY.json \
  --purchase-policy PURCHASE_POLICY.json \
  --projection TARGET_COHORT_PROJECTION.json \
  --initial-selection INITIAL_SELECTION.json \
  --candidate-frontier FULL_FRONTIER.jsonl \
  --source snapshot=SNAPSHOT_MANIFEST.json \
  --output CLEARANCE_REPLACEMENT_FRONTIER.json \
  --broker-allowlist-plan-output BROAD_FRONTIER_ALLOWLIST.json
```

The builder preserves the supplied frontier order rather than re-ranking observations after clearance.
It binds the exact cohort-policy, purchase-policy, projection, selection, candidate-frontier, and named source hashes; asserts that the frontier is untruncated; freezes the initial selected IDs, target count, four case-mix dimensions, and optional per-bucket cap; and verifies every candidate cost against the frozen purchase reservation and per-case cap.
Every initial selected candidate must appear in the full frontier.
The builder simultaneously emits the broad dry-run broker allowlist plan, so it can be activated before the first purchase and before any clearance outcome is observed.

After authenticated clearance of all confirmed purchased documents, plan the next iteration:

```console
uv run legalforecast acquisition plan-clearance-replacements \
  --cohort-policy COHORT_POLICY.json \
  --purchase-policy PURCHASE_POLICY.json \
  --frontier CLEARANCE_REPLACEMENT_FRONTIER.json \
  --purchase-ledger PURCHASE.sqlite3 \
  --purchased-clearance PURCHASED_CLEARANCE.jsonl \
  --clearance-run-card CLEARANCE_RUN_CARD.json \
  --output REPLACEMENT_RESULT.json \
  --replacement-budget-plan-output NARROW_REPLACEMENT_PLAN.json \
  --broker-allowlist-plan-output BROAD_FRONTIER_ALLOWLIST.json \
  --exclusions-output REPLACEMENT_EXCLUSIONS.jsonl
```

This command never calls a provider and never purchases a document.
The canonical purchase SQLite journal is also the single writer for `legalforecast.clearance_replacement_event.v1` records.
Each event binds every frozen input plus the current canonical purchase-journal state, records the quarantined documents and journal-derived committed write-off, recomputes headroom without releasing that write-off, applies the frozen case-mix cap to retained cases, and points to the previous event hash.
An identical replay returns identical output without another event, selection, reservation, or bill.
An unresolved submitted or unknown purchase fails closed before replacement selection.

The two plan classes have deliberately different authority:

- `NARROW_REPLACEMENT_PLAN.json` is non-dry-run and contains only replacements selected in the durable iteration ledger.
- `BROAD_FRONTIER_ALLOWLIST.json` is produced up front by the frontier builder, is dry-run, and contains every eligible paid document in the frozen frontier; the later planner reproduces it byte-for-byte as a consistency check.

Generate the secure-gate broker policy from the broad plan with `generate-recap-fetch-broker-policy --broad-frontier-allowlist`.
That explicit mode may allowlist a frontier whose aggregate hypothetical cost exceeds the Cycle cap because allowlisting is not spending; the broker continues to enforce the unchanged signed Cycle cap, per-case cap, reservation, and canonical purchase journal on each request.
Without that flag, broker-policy generation continues to require the narrow non-dry-run executable plan and rejects aggregate reservations above the remaining envelope.

Derived replacement exclusions are an audit artifact, not a new eligibility rule.
They identify candidates already selected or attempted, candidates already marked ineligible in the frozen frontier, candidates blocked by the frozen case-mix cap, and candidates that do not fit remaining journal-derived headroom.
