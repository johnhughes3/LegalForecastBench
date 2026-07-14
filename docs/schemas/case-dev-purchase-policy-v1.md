# Case.dev purchase policy v1

`legalforecast.case_dev_purchase_policy.v1` is the immutable safety envelope for Cycle-wide document purchases.

Generate it before any paid request with `legalforecast acquisition generate-purchase-policy --cohort-policy <frozen-cohort-policy.json> --decisions <approved.json> --output <policy.json>`.
Generation fails unless the purchase hard cap and per-case cap exactly equal the values in that frozen cohort policy and `cohort_policy_sha256` matches it.

The decisions object contains:

- `cycle_id`: immutable cycle identity.
- `cohort_policy_sha256`: SHA-256 of the frozen cohort policy this purchase envelope belongs to.
- `canonical_ledger_path`: normalized absolute path of the only permitted Cycle-wide document-purchase SQLite journal.
- `hard_cap_usd`: immutable Cycle-wide document-purchase ceiling; a budget plan can be lower but cannot raise it.
- `opening_committed_spend_usd`: already-committed Cycle spend imported before this canonical document journal is created; it remains counted against the hard cap.
- `opening_case_committed_spend_usd`: case ID to canonical nonnegative USD mapping for all opening committed spend; every value is bounded by the per-case cap and the mapping sum must exactly equal `opening_committed_spend_usd`.
- `max_per_case_usd`: immutable per-case reservation ceiling.
- `per_document_reservation_usd`: verified worst-case amount reserved immediately before each POST.
- `fee_schedule`: a nonempty source citation and UTC verification time, plus true assertions that the reservation includes PACER fees, service fees, and rounding.

The generated artifact adds `schema_version` and `policy_sha256`.

Initialize the canonical journal explicitly after both policies are frozen and before any projection, replacement, or purchase command that consumes journal state:

```console
uv run legalforecast acquisition init-purchase-ledger \
  --output-root PURCHASE_LEDGER_INIT_ROOT \
  --purchase-policy PURCHASE_POLICY.json \
  --cohort-policy COHORT_POLICY.json \
  --purchase-ledger /absolute/canonical/cycle-purchases.sqlite3 \
  --execute
```

`init-purchase-ledger` contacts no provider, acknowledges no fees, and performs no purchase.
It acquires the canonical journal lock, creates the ledger with exclusive-create semantics, binds the exact purchase-policy identity, verifies the pristine SQLite state, and publishes an immutable `legalforecast.purchase_ledger_initialization.v1` receipt containing the policy hashes, canonical path, ledger-byte hash, semantic purchase-state hash, and byte count.
An existing ledger without that exact receipt is never initialized or repaired; empty, truncated, symlinked, hard-linked, noncanonical, policy-mismatched, or changed-state paths fail closed.
With `--resume`, an exact completed receipt and still-pristine ledger are verified read-only; `--no-resume` refuses any completed initialization.
Run the command only once before operational journal use, because a later purchase or replacement event correctly changes the authenticated state.

`purchase-missing` requires `--cohort-policy`, `--purchase-policy`, and `--purchase-ledger` even in dry-run mode; it re-verifies the hash and caps at execution time.
For an executing run, the ledger path must exactly match the canonical path frozen in the policy.
The command persists every intended document as `planned`, commits `submitted` with a unique operation key immediately before one zero-retry POST, and then transitions to `confirmed`, `failed`, or `unknown`.
Confirmed rows settle to validated actual fees; submitted, unknown, and written-off rows retain at least the full reservation against the cap.
Each case's cumulative cap accounting begins with its frozen `opening_case_committed_spend_usd` amount; unattributed opening spend is rejected because it could evade the per-case cap.

Generate the secure-gate activation artifact only after the final executable purchase plan and final selection are frozen:

```console
uv run legalforecast acquisition generate-recap-fetch-broker-policy --purchase-policy PURCHASE_POLICY.json --cohort-policy COHORT_POLICY.json --budget-plan MISSING_CORE_BUDGET_PLAN.json --selection FINAL_SELECTION.jsonl --output BROKER_POLICY.json
```

The producer first re-verifies that the purchase-policy hash and caps consume the supplied frozen cohort policy, then copies the verified policy digest, caps, reservation, and opening commitments, and derives the document allowlist exclusively from `case_plans[].purchase_document_ids` whose matching selection metadata either proves the document explicitly public or carries the exact current CourtListener REST paid-gap evidence contract.
Any sealed, private, restricted, metadata-missing, or legacy Case.dev paid-unknown document is rejected.
Case.dev may still provide noncharging search or docket enrichment, but it is never purchase authority; only CourtListener REST evidence can authorize a paid gap for CourtListener RECAP Fetch.
Allowlisting never makes a recovered document packet-eligible without the separate post-recovery disclosure clearance.
It prints secure-gate's canonical broker-policy SHA-256, writes deterministic JSON atomically, and refuses to overwrite an existing different-byte artifact.

When the frozen cohort uses post-clearance replacement, activate one broader broker allowlist before the first purchase instead of changing broker policy after observing a quarantine:

```console
uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy PURCHASE_POLICY.json \
  --cohort-policy COHORT_POLICY.json \
  --budget-plan BROAD_FRONTIER_ALLOWLIST.json \
  --selection FULL_FRONTIER_SELECTION.jsonl \
  --broad-frontier-allowlist \
  --output BROKER_POLICY.json
```

Broad-frontier mode requires an explicitly dry-run scope artifact and may allowlist more hypothetical aggregate cost than the Cycle cap.
It does not authorize that spend: secure-gate still enforces the unchanged signed Cycle cap, per-case cap, reservation, and journal state for every request.
The separate non-dry-run replacement plan remains the narrow executable authority for each iteration.
See `docs/schemas/clearance-replacement-v1.md` for the full hash-chain and replay contract.

An unresolved `submitted` or `unknown` row blocks every subsequent purchase and cannot be retried.
Resolve it with `legalforecast acquisition reconcile-purchase --purchase-policy <policy.json> --cohort-policy <cohort-policy.json> --purchase-ledger <ledger.sqlite3> --evidence <evidence.json>`.
Evidence must name a provider-side billing receipt, statement export, or support confirmation; document availability alone is not payment evidence.
`confirmed` evidence requires parseable PACER, service, and total fees plus the provider download URL; `failed` releases the reservation; `write_off` permits the Cycle to continue but permanently retains the reservation against the cap.
