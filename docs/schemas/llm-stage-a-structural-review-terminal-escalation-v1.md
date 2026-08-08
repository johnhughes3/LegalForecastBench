# Stage A structural-review terminal escalation v1

`legalforecast.llm_stage_a_structural_review_terminal_escalation.v1` is a provider-free, immutable receipt for one explicitly selected Stage A structural-review call that has exactly two durable `reconstruction_failed` attempts.

It is deliberately narrower than ordinary retry or reconstruction recovery. The receipt is valid only when both attempts belong to the current candidate/model/prompt identity, carry the same nonempty validator failure type and message, have no reconstructed result, and contain byte-identical normalized response JSON. It commits the two raw and normalized response digests, the frozen prediction units, the exact reviewer prompt, and blinded predecision Markdown-source commitments.

The receipt is not a structural flag and cannot clear, amend, or exclude a unit. `llm-review-stage-a --terminal-escalation <receipt>` reconstructs it from the authenticated shared provider journal and Stage A lineage before it emits one immutable pending-review item per affected frozen unit. The queue records retain the prompt, failure commitments, and blinded sources for John, while the structural-review audit retains `status: terminal_escalation`, zero accepted flags, and the receipt commitment.

The normal retry path is unchanged when no receipt is supplied. A receipt never calls a provider, never reserves provider spend, never changes the two prior journal rows or their accounting, and fails closed for a different attempt count or status, byte drift, identity drift, duplicate receipt/candidate, missing units, a changed source, a symlinked receipt, or any hand-authored replacement.
