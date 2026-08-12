# Unitizer terminal review queue and bundle v1

`legalforecast.unitizer_terminal_review_queue.v1` is the candidate-level attorney-review projection of one authenticated [`legalforecast.llm_stage_a_unitizer_terminal_escalation.v1`](llm-stage-a-unitizer-terminal-escalation-v1.md) receipt. It is separate from the frozen unit-subject review queue because the exhausted unitizer emitted no accepted source unit.

The queue row has `status: pending_adjudication`, `review_subject: candidate`, the exact candidate and case IDs, and a deterministic `review_id` formed from the candidate ID and the first 16 characters of the canonical terminal-receipt digest. Its technical reason code is `unitizer_terminal_reconstruction_failure`. `allowed_actions` is exactly `ADD` and `CANDIDATE-EXCLUSION`; `suggested_actions` is empty.

The row commits the complete receipt digest, unitizer model, registry digest, v5 namespace, prompt digest, ordered predecision source commitments, and all three failed-attempt commitments. It deliberately omits the prompt text and every proposed prediction unit. No model-authored legal conclusion is exposed as an attorney suggestion.

`legalforecast.unitizer_terminal_review_bundle.v1` reproduces the queue's identity, reason, actions, receipt digest, and review item and adds `cited_predecision_markdown` in the receipt's committed order. Each source must be one of the closed predecision roles, its metadata must equal the receipt, and the exact Markdown must reproduce the prefixed digest. Decision, order, judgment, outcome, uncommitted, missing, duplicated, reordered, or byte-different material fails construction.

The queue and bundle cover exactly one candidate per receipt. They do not modify the ordinary unitization review queue or bundle, invoke a provider, or confer adjudication authority by themselves. The attorney records the decision separately under [`legalforecast.unitization_adjudication.v3`](unitization-adjudication-v3.md).
