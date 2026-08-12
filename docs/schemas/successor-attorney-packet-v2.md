# Successor attorney packet v2

`legalforecast.successor_attorney_packet_manifest.v2` and `legalforecast.successor_attorney_packet_view.v2` extend the private provider-free [successor attorney packet v1](successor-attorney-packet-v1.md) with candidates whose v5 unitizer exhausted reconstruction before accepting any prediction unit.

The v2 builder first reproduces the complete v1 packet. It then authenticates three exact-byte, newline-terminated JSONL inputs:

- `legalforecast.llm_stage_a_unitizer_terminal_escalation.v1` receipts;
- `legalforecast.unitizer_terminal_review_queue.v1` rows; and
- `legalforecast.unitizer_terminal_review_bundle.v1` records.

For each input the manifest records schema, byte count, lowercase SHA-256, and record count. It also records the exact unitizer-terminal candidate count. Receipt, queue, and bundle candidate/review coverage must be identical; each queue and bundle is deterministically rebuilt from its receipt; every bundled predecision source must reproduce its committed metadata and Markdown hash; and no candidate may appear in both the frozen-unit v1 packet and terminal-unitizer review.

The v2 view retains every v1 candidate unchanged and adds one sorted `unitizer_terminal` section per exhausted candidate containing the authenticated queue and bundle records. Its `unitizer_terminal_authoritative_source` names the terminal review bundle. The terminal queue exposes only `ADD` and `CANDIDATE-EXCLUSION`, includes no prompt text or proposed units, and the bundle contains only committed predecision Markdown. For the exact-100 cycle, `CANDIDATE-EXCLUSION` records that the selected candidate cannot continue; it triggers authenticated cohort replacement and does not authorize publication of a shrunken finalized artifact.

Packet v2 is an attorney presentation and exact-byte manifest, not an adjudication artifact. The attorney's executable decision is a separate [`legalforecast.unitization_adjudication.v3`](unitization-adjudication-v3.md) record. Packet v1 remains valid and unchanged for cycles with no unitizer-terminal candidates.
