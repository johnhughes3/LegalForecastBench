# Corpus completion summary v1

`legalforecast.corpus_completion_summary.v1` is the deterministic,
provider-free terminal audit for a completed acquisition corpus. Produce it with
`legalforecast acquisition summarize-corpus`. The command validates only by
default; `--execute` is required to publish the immutable summary and run card.

The command never contacts a model provider, CourtListener, PACER, AWS, an
evaluation runner, the official freeze path, or dispatch. Its run card records
that closed activity boundary explicitly.

## Inputs and authentication

The command requires the successful `finalize-corpus` run card and its corpus
readiness and complete-exclusion-ledger outputs, the authenticated cohort
materialization summary and run card, the purchase/cohort policies and canonical
SQLite purchase ledger initialization receipt, the frozen model registry, and
the Stage A and Stage B review queues and adjudication/audit artifacts.

Every regular-file input is committed by resolved path, SHA-256, and byte count.
The purchase journal is committed by canonical logical state SHA-256, canonical
operation-list SHA-256, committed amount, and operation count. The journal is
re-authenticated before summary publication, between summary and run-card
publication, and before success. Any drift fails closed.

## Summary fields

The summary contains:

- target count, clean count, target status, and registry-derived eligibility
  anchor;
- discovered, accepted, excluded, and processed reconciliation;
- complete-ledger primary and secondary exclusion-reason counts;
- free, purchased, and total materialized-document counts;
- parsed, Stage A, Stage B, packet-input, packet-built, excluded, and clean funnel
  counts;
- the six final case-mix strata emitted by `finalize-corpus`;
- Stage A and Stage B queue, resolved, and pending counts;
- canonical known actual operation spend, whether actual spend is complete,
  cap-counted committed obligations, unresolved obligations, hard cap, and
  remaining headroom; and
- exact source commitments plus the summary's self-hash.

Pending review rows require repeatable
`--adjudication-bead REVIEW_ID=BEAD_ID` mappings whose review IDs exactly equal
the pending queue IDs. Extra, duplicate, missing, or unrelated mappings are
rejected. When both queues are empty or fully adjudicated, bead mappings must be
absent.

## Spend semantics

Spend reporting delegates to the purchase journal's shared cap classifier.
`known_actual_operation_spend_usd` sums recorded actual fees only.
`actual_spend_usd` remains null until every billing outcome is terminal and any
opening committed amount is zero. Submitted, queued, unknown, and ambiguous
failed or confirmed rows continue to count against the cap under the same rules
used by purchase authorization; they are never silently treated as zero spend.

## Publication

Execution owns exactly:

- `OUTPUT_ROOT/corpus-completion-summary.json`
- `OUTPUT_ROOT/run-cards/summarize-corpus.json`

Existing exact bytes are accepted for deterministic crash recovery. Conflicting
bytes, symlinks, hardlinks, unexpected entries, changed source files, or changed
SQLite state are rejected. Neither artifact contains a timestamp.
