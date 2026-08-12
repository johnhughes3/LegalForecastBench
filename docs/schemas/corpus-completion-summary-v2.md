# Corpus completion summary v2

`legalforecast.corpus_completion_summary.v2` is the deterministic, provider-free terminal audit for a completed acquisition corpus whose Stage A lineage includes one or more exhausted unitizer candidates. `legalforecast acquisition summarize-corpus` selects it automatically from the authenticated `finalize-corpus` handoff; it takes no caller-selected terminal Stage A paths. The corresponding publication record is `legalforecast.corpus_completion_summary_run_card.v2`.

Version 2 is an additive Cycle 1 correctness migration. It does not reinterpret, replace, or widen `legalforecast.corpus_completion_summary.v1` or `legalforecast.corpus_completion_summary_run_card.v1`. A summary invocation without the terminal input pair continues to emit the unchanged v1 summary and v1 run card. Existing v1 artifacts remain valid against their original byte commitments.

## Automatic version selection and additional Stage A inputs

The completed `finalize-corpus` card is the authority for the summary input shape. The command reads its `completion_summary_input_commitments` before choosing a version:

- exactly the legacy six summary keys selects v1;
- exactly those six keys plus the two terminal keys below selects v2; and
- a partial terminal pair, duplicate key, unknown key, or any other key-set shape is rejected.

The v2 terminal pair is:

- `unitizer_terminal_review_queue`: the authenticated `legalforecast.unitizer_terminal_review_queue.v1` JSONL emitted from exhausted unitizer receipts;
- `unitizer_terminal_adjudications`: the completed `legalforecast.unitization_adjudication.v3` JSONL that resolves those candidate-level terminal review rows.

The ordinary `unitization_review_queue` and `unitization_adjudications` inputs remain required and remain the authority for ordinary frozen-unit review. Terminal rows are not copied into, treated as aliases for, or resolved through either ordinary input. A v2 summary derives both terminal file paths from the authenticated finalize-card commitments, then rejects a missing half of the pair, duplicate review IDs within either review surface, an adjudication that names an unknown terminal review ID, a review ID resolved more than once, or overlap between ordinary and terminal review IDs.

The successful `finalize-corpus` handoff must separately own the terminal queue and terminal adjudication bytes. Its `input_paths` and `completion_summary_input_commitments` therefore contain the ordinary six summary inputs plus `unitizer_terminal_review_queue` and `unitizer_terminal_adjudications`. Each commitment binds the resolved path, lowercase SHA-256, and byte count. The completion summary independently reads and commits the same exact bytes, and repeats its input-drift and purchase-ledger checks before, between, and after publication.

## Summary and run-card fields

V2 preserves every v1 top-level field and activity prohibition. Its `adjudication` object makes Stage A coverage explicit in three views:

- `stage_a_ordinary_*` fields report the ordinary frozen-unit queue, adjudications, and pending review IDs;
- `stage_a_terminal_*` fields report the unitizer-terminal candidate queue, v3 adjudications, and pending review IDs; and
- `stage_a_*` aggregate fields report the union of both disjoint Stage A surfaces.

The aggregate Stage A queue, adjudication, and pending counts equal the respective ordinary-plus-terminal counts. Aggregate pending review IDs are the sorted union of the ordinary and terminal pending IDs. Stage B counts, aggregate pending count, and required `adjudication_bead` mappings continue to work over the combined pending Stage A and Stage B review-ID set. Thus a terminal candidate cannot disappear from the completion report merely because the exhausted unitizer emitted no ordinary source unit.

The v2 run card retains the v1 stage (`summarize-corpus`), output names, deterministic publication protocol, and explicit zero-provider/zero-paid/evaluation/freeze/dispatch prohibitions. It changes only its schema version and input commitments to identify the exact v2 evidence set. Neither the summary nor its run card contains a timestamp.

## Publication

Execution owns exactly:

- `OUTPUT_ROOT/corpus-completion-summary.json`
- `OUTPUT_ROOT/run-cards/summarize-corpus.json`

As in v1, exact pre-existing bytes are accepted solely for deterministic crash recovery. Conflicting bytes, symlinks, hardlinks, unexpected output entries, changed authenticated inputs, or changed canonical SQLite purchase-ledger state fail closed. The command never contacts a model provider, CourtListener, PACER, AWS, an evaluation runner, the official freeze path, or dispatch.
