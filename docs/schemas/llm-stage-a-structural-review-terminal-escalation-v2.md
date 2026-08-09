# Stage A structural-review terminal escalation v2

`legalforecast.llm_stage_a_structural_review_terminal_escalation.v2` is a provider-free, immutable receipt for one explicitly selected Stage A structural-review call whose three normal reconstruction attempts are all durably `reconstruction_failed`.

It is an exhausted-retry route, not a relaxation of `v1`. Every attempt must belong to the current candidate/model/prompt identity, have ordinal 1, 2, or 3 in order, contain raw and normalized response evidence, retain no reconstructed result, and carry a nonempty validator failure type and message. The three responses and failures may differ. The receipt commits every failed attempt's raw and normalized digests, individual validator evidence, frozen prediction units, exact reviewer prompt, and blinded predecision Markdown-source commitments.

`v1` remains the earlier route for exactly two byte-identical normalized responses with identical validator evidence. The v2 producer never changes either v1 qualification or the fixed three-attempt retry ceiling.

The receipt is not a structural flag and cannot clear, amend, or exclude a unit. `llm-review-stage-a --terminal-escalation <receipt>` reconstructs it from the authenticated shared provider journal and Stage A lineage before it emits one immutable pending-review item per affected frozen unit. The queue records retain the prompt, all three failure commitments, and blinded sources for John, while the structural-review audit retains `status: terminal_escalation`, zero accepted flags, and the receipt commitment.

No receipt ever calls a provider, reserves provider spend, or changes prior journal rows or accounting. It fails closed for fewer or more than three rows, a fourth attempted retry, non-failed status, skipped or changed ordinal, absent raw/normalized/failure evidence, reconstructed result, identity drift, missing units, changed source, symlinked receipt, or a hand-authored replacement.
