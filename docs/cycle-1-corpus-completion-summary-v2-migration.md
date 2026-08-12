# Cycle 1 corpus-completion-summary v2 migration

**Status:** required only for a Cycle 1 successor whose completed Stage A lineage contains unitizer-terminal candidates; governed by [Cycle 1 change control](cycle-1-change-control.md).

The original completion-summary/finalize handoff has only the ordinary frozen-unit Stage A review queue and adjudications. That shape cannot prove that an exhausted unitizer candidate was presented to, and resolved by, the separate attorney terminal-review route. Version 2 therefore adds the separately authenticated `unitizer-terminal-review-queue.jsonl` and `unitizer-terminal-adjudications.jsonl` inputs to the affected handoff artifacts:

1. the completed `finalize-corpus` run card's `input_paths` and `completion_summary_input_commitments`;
2. `legalforecast.corpus_completion_summary.v2`; and
3. `legalforecast.corpus_completion_summary_run_card.v2`.

`summarize-corpus` does not accept caller-selected terminal paths. It derives the pair from the exact finalized card: the exact legacy six-key commitment set emits v1; the exact eight-key set containing both terminal keys emits v2; malformed partial or extra commitment sets fail closed. The successor records ordinary Stage A, terminal Stage A, and aggregate Stage A queue/adjudication/pending counts. The aggregate is a reconciliation view over two disjoint authenticated review surfaces; it is not a conversion of terminal adjudication v3 into an ordinary v1/v2 adjudication.

No earlier summary, finalize card, packet, selection, raw-unit, label, evaluation, freeze, or dispatch artifact is modified or rehashed. V1 remains the required output for a completed lineage with no terminal pair. The migration is provider-free and does not open PACER, provider, evaluation, freeze, or dispatch authority.
