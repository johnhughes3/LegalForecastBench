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
- `max_per_case_usd`: immutable per-case reservation ceiling.
- `per_document_reservation_usd`: verified worst-case amount reserved immediately before each POST.
- `fee_schedule`: a nonempty source citation and UTC verification time, plus true assertions that the reservation includes PACER fees, service fees, and rounding.

The generated artifact adds `schema_version` and `policy_sha256`.

`purchase-missing` requires `--cohort-policy`, `--purchase-policy`, and `--purchase-ledger` even in dry-run mode; it re-verifies the hash and caps at execution time.
For an executing run, the ledger path must exactly match the canonical path frozen in the policy.
The command persists every intended document as `planned`, commits `submitted` with a unique operation key immediately before one zero-retry POST, and then transitions to `confirmed`, `failed`, or `unknown`.
Confirmed rows settle to validated actual fees; submitted, unknown, and written-off rows retain at least the full reservation against the cap.

An unresolved `submitted` or `unknown` row blocks every subsequent purchase and cannot be retried.
Resolve it with `legalforecast acquisition reconcile-purchase --purchase-policy <policy.json> --purchase-ledger <ledger.sqlite3> --evidence <evidence.json>`.
Evidence must name a provider-side billing receipt, statement export, or support confirmation; document availability alone is not payment evidence.
`confirmed` evidence requires parseable PACER, service, and total fees plus the provider download URL; `failed` releases the reservation; `write_off` permits the Cycle to continue but permanently retains the reservation against the cap.
