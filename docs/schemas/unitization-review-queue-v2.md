# Unitization Review Queue v2

`legalforecast.unitization_review_queue.v2` is a non-authoritative sidecar projection of the merged Stage A human-review queue. It is written beside the v1 queue by `acquisition llm-review-stage-a` — `unitization-review-queue-reviewed-v2.jsonl` next to `unitization-review-queue-reviewed.jsonl` — and is deliberately absent from that stage's run-card output paths and output commitments. Nothing consumes it as adjudication input: `apply-unitization-review` still reads v1 rows only.

## What v1 conflates

A v1 row carries a single free-form `route_reason` string that has to answer four different questions at once: what is under review, why, what the system will actually accept as a resolution, and what an unverified model merely suggested. A reviewer reading `structural_reviewer_terminal_reconstruction_failure` on a unit row cannot tell from the row that the finding is not about that unit at all.

v2 keeps the four separate:

- `review_subject` — `unit` or `candidate`.
- `reason` — an immutable `{code, class, summary}` drawn from a closed table. `class` is `substantive` (a question about the law) or `technical` (a question about the machinery). The summary is fixed per code, not per row.
- `allowed_actions` — authoritative. The closed set of actions that can legitimately resolve the item.
- `suggested_actions` — non-authoritative. Every entry carries `authoritative: false` and names the unverified source it came from.

`review_id` is preserved for unit items. `source_review_ids` is the exact-once coverage relation: each v1 row appears there on exactly one v2 item. Candidate items also carry `terminal_evidence_review_ids`, which names every v1 row that supplied terminal escalation evidence, including coalesced rows whose `source_review_ids` remain on their substantive unit items.

## Allowed actions are derived, not guessed

For a unit-subject item, `allowed_actions` is the set of dispositions `_validate_disposition_shape` will actually accept for a review that consumes one unit: `ACCEPT`, `AMEND`, `SPLIT`, `MERGE`, `DROP`, `CANDIDATE-EXCLUSION`. `ADD` is offered only for `structural_omitted`, because the frozen ADD validator requires an omitted structural review. Narrowing further — offering only `SPLIT` on a `structural_combined` flag, say — would substitute a guess about legal judgment for a fact about the validators, so v2 does not do it.

A candidate-subject technical item currently has an empty authoritative `allowed_actions` list. Frozen Cycle 1 has no candidate-level adjudication consumer, so `RETRY-STRUCTURAL-REVIEW`, `WAIVE-STRUCTURAL-REVIEW`, and `EXCLUDE-CANDIDATE` are outside the current v2 contract rather than advertised as executable resolutions. A future version may add those operations only alongside an authoritative consumer path. No unit disposition appears, because every current disposition consumes source units and the item names no unit.

## Terminal structural-review failures become one candidate item

Today a terminal escalation emits one v1 row per frozen unit, all carrying identical evidence about a single failed reviewer run. v2 collapses them into one candidate-subject technical item carrying:

- `validator_code` and `invalid_field` — a stable classification of the failure, derived from the journaled `(failure_type, failure_message)` pair by an exhaustive table. Unrecognized failures classify as `unclassified` with the exact message preserved; attempts that failed *different* validators classify as `structural_review_validator_mixed` with per-attempt detail intact, rather than naming one code that would misdescribe the run.
- `attempt_commitments` — the per-attempt `raw_response_sha256` and `normalized_response_sha256` already recorded in the escalation, plus that attempt's own classification and verbatim failure message.
- `safe_parsed_flags` — see below; empty unless response bytes are supplied.
- `affected_unit_ids` — every frozen unit the failed run touched. The supported producer-to-merge-to-projection path collects this full cohort from the v1 rows; safe suggestions never narrow it.
- `terminal_evidence_review_ids` — every v1 row carrying the terminal escalation evidence. This is provenance rather than coverage, so it may overlap unit items' `source_review_ids` when terminal evidence is coalesced into a substantive v1 row.

A unit already under substantive review keeps its own unit item and its own `review_id`; the candidate item absorbs only standalone terminal rows in `source_review_ids`, while `terminal_evidence_review_ids` remains complete. Two different reviewer runs for one candidate fail closed rather than merging.

## Safe parsed flags are authenticated before parsing

A response that failed whole-payload validation may still contain individually well-formed flags, and those are worth showing a reviewer as suggestions. `safe_parsed_structural_flags` verifies the supplied bytes against the commitment already in the queue row *before* handing anything to the JSON decoder, then keeps only flags whose type, explanation, and unique in-cohort `affected_unit_ids` all stand on their own. Mismatched bytes fail closed. With no bytes supplied the result is empty and `suggested_actions` is empty — an honest absence rather than a guess.

Nothing recovered this way is ever accepted as a structural flag. It is reviewer-facing advice, marked `authoritative: false`.

## Coverage is verified independently

`verify_review_queue_v2_coverage` re-derives coverage from the two record sets rather than trusting the projection: every v1 `review_id` must be represented exactly once, no v2 item may name a `review_id` v1 does not have, and the set of `(candidate_id, unit_id)` pairs must match exactly in both directions. The CLI asserts this before writing the sidecar, so a projection that dropped or invented review work never reaches disk.
