# Case.dev purchase policy v1

`legalforecast.case_dev_purchase_policy.v1` is the historical safety envelope for fixture and read-only compatibility only.
It cannot mint new official purchase authority and every live purchase path rejects it before opening a journal, reading provider configuration, acknowledging a fee, constructing a client, or making a request.

The removed hand-authored `--decisions` workflow must not be used for a new cycle.
Use [Case.dev purchase policy v2](case-dev-purchase-policy-v2.md), which replays the exact post-clearance target projection and private John approval.

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

No operational command accepts v1 authority.
Do not use a v1 artifact to initialize or resume a purchase ledger, project or extend a paid cohort, generate attempt or broker policy, purchase, reconcile, recover, materialize, parse, assemble packets, or finalize a corpus.
Those workflows require [Case.dev purchase policy v2](case-dev-purchase-policy-v2.md) and its recorded approval evidence.
V1 artifacts remain supported only where an explicitly fixture-only or read-only compatibility test needs to parse historical bytes and prove rejection at an operational boundary.
