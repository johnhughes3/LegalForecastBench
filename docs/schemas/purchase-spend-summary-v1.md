# Purchase spend summary v1

`legalforecast.purchase_spend_summary.v1` is a provider-free, immutable sidecar that reports the difference between a PACER purchase commitment and provable actual billing. Produce it with `legalforecast acquisition summarize-purchase-spend`.

The command never contacts CourtListener, RECAP, PACER, a broker, a model provider, an evaluation runner, the official freeze path, or dispatch. It opens the canonical purchase ledger read-only and never records a reconciliation or changes a cap.

## Inputs and authentication

The sidecar authenticates the published v2 purchase policy, frozen cohort policy, ledger initialization receipt, and canonical logical purchase-ledger snapshot. The supplied policy and cohort files must exactly match the byte hashes recorded by the initialization receipt. It also binds the exact bytes, SHA-256, validated closed result semantics, and source-document identity sets of the initial and replacement purchase-result roots. Together, those two roots must cover every authenticated ledger operation exactly once and agree with the ledger's candidate identity.

The published v2 policy includes verified purchase approval and is authoritative without a private approval replay. An operator may pass `--controlled-private-root` for an additional private-provenance replay; it is not necessary for ordinary provider-free accounting and is never embedded in the sidecar.

The sidecar rejects an unreconciled ledger operation when either purchase-result root contains a non-null provider fee for it. A result-root fee is evidence that must be reconciled in the authoritative journal, not a reason to guess a billing outcome.

## Spend semantics

`spend_summary` uses the purchase journal's shared cap classifier:

- `known_actual_operation_spend_usd` is the sum of recorded actual fees. A value of `"0.00"` means only that no actual fee has been recorded; it does **not** mean PACER charged nothing.
- `actual_spend_usd` is null unless all actual billing outcomes are terminal and known.
- `unresolved_cap_counted_usd` is the dollar amount that remains reserved against the cap while billing is unresolved.
- `cap_counted_committed_spend_usd`, `hard_cap_usd`, and `remaining_cap_headroom_usd` retain their purchase-authority meanings.

`actual_charge_reconciliation.classification` is one of:

- `actual_charge_reconciled`: no ledger operation has unresolved billing;
- `actual_charge_partially_unavailable`: some ledger billing is unresolved while separate recorded billing evidence exists; or
- `actual_charge_unavailable`: no authenticated provider billing evidence exists for any unresolved operation.

The latter is the honest Cycle 1 state when purchase results and the ledger contain no billing receipts. It must never be reported as `$0.00` actual spend.

## Publication and resume

The output is canonical JSON with a self-hash. Its source commitments include SHA-256 and byte count for ordinary files, and logical purchase-state hash, operation-list hash, committed amount, and operation count for the SQLite ledger.

The writer uses a create-once, no-follow file operation in an existing non-symlinked output directory. Exact-byte output resume is accepted; changed bytes, symlinked output parents, symlinked files, hardlinks, or conflicting existing output fail closed. The command intentionally does not choose a canonical Cycle 1 artifact location: the owner of the active acquisition lineage must place this sidecar alongside the run card that consumes it.
