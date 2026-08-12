# Cycle 1 Stage A v5 unitizer selector migration

**Status:** required before a further Stage A provider call for the corrected exact-100 successor; governed by [Cycle 1 change control](cycle-1-change-control.md).

## Trigger and bounded remedy

The completed `claim-ontology-v4` unitizer contract required a model to emit inclusive `start_line` and `end_line` values whose difference could not exceed eleven. The corrected exact-100 v4 attempt showed a systematic reconstruction failure: the model repeatedly emitted overlong ranges despite the prompt’s stated maximum. The failure is in the model-authored endpoint arithmetic, not in the supplied document lines, the canonical-unit schema, or the structural-review schema.

This is a narrow versioned successor, not a repair of a failed v4 response. `claim-ontology-v4` prompt bytes, decoders, raw responses, provider-attempt records, run cards, and costs remain immutable historical evidence. No selector is silently shortened, split, clamped, accepted, rehashed, or replayed as v5 evidence.

## Active closed Stage A pair

The sole active successor pair is `claim-ontology-v5` for `llm-unitize` and `claim-ontology-v4` for `llm-review-stage-a`. The unitizer and reviewer stages therefore carry different explicit provider-attempt namespaces, each committed in its own run card, while sharing the same authenticated cycle lineage, provider-caps artifact, and canonical provider journal.

| Unitizer namespace | Structural-review namespace | Status |
| --- | --- | --- |
| unnamespaced | unnamespaced | Historical replay only |
| `claim-ontology-v2` | `claim-ontology-v2` | Historical replay only |
| `claim-ontology-v2` | `claim-ontology-v3` | Historical replay only |
| `claim-ontology-v4` | `claim-ontology-v4` | Historical replay only; preserves prior v4 evidence |
| `claim-ontology-v5` | `claim-ontology-v4` | The only active closed successor pair |

All other combinations fail closed. In particular, `claim-ontology-v5`/`claim-ontology-v5`, `claim-ontology-v4`/`claim-ontology-v5`, a v5 unitizer with a legacy reviewer, a legacy unitizer with a v4 reviewer, an omitted namespace, and any invented namespace are prohibited. A namespace identifies a reviewed contract; it is not a retry escape hatch for an unchanged prompt or a way to evade settled, failed, or reserved attempts.

## V5 unitizer citation selector

For a unitizer citation, v5 accepts only this model-authored selector shape:

```json
{
  "source_document_id": "<one supplied document id>",
  "start_line": 41,
  "line_count": 3
}
```

`start_line` is one-based, and `line_count` is an integer from 1 through 12 inclusive. V5 rejects an `end_line`, a missing or extra selector field, a noninteger, a nonpositive count, a count above 12, an unknown document, and a range whose locally derived endpoint is outside the supplied Markdown document. Local code derives `end_line = start_line + line_count - 1`, reconstructs the exact supplied excerpt and page marker, and applies the existing per-document citation checks before it creates a unit.

The canonical reconstructed prediction-unit shape is unchanged. In particular, v5 does not introduce a new canonical-unit schema, alter claim identity or motion-scope requirements, or relax the requirement that every unit carry operative-complaint claim-identity evidence and target-motion notice or memorandum challenge-scope evidence. The unchanged v4 structural reviewer continues to use its existing document-bound line-span contract and produces the unchanged `legalforecast.stage_a_structural_flag.v2` artifact; no v5 structural-flag schema exists.

## Eligibility, authority, and replay

Target-document eligibility is semantic and unchanged by the selector syntax. The target-document eligibility audit still verifies that the supplied target is an eligible contested motion-to-dismiss filing and that any required supporting memorandum is present in the authenticated predecision materials. Live Stage A treats v4 and v5 as line-addressed contracts when it replays that audit, its completed provider-free run card, the exact selection, parser manifest, and Markdown tree before opening registry, cap, journal, or provider authority. V5 changes only unitizer selector encoding; it does not turn docket-role metadata into authority or make a stipulated, voluntary, administrative, generic non-motion dismissal, or missing-supporting-memorandum candidate eligible.

The successor uses the same canonical provider journal and the same frozen caps artifact and cohort `cycle_id` as the prior v4 attempt. It neither resets spend authority nor copies, releases, deletes, or hand-edits existing journal rows. V4 raw attempts, including failures and reservations, stay bound to their original v4 logical calls; v5 produces distinct logical calls under its own namespace against the same cap-enforced journal.

Before the first v5 provider call, the execution path must authenticate the complete current chain: exact successor selection and exclusion ledger; materialization, download-manifest, disclosure-clearance, and document tree; parse requests, pinned parser run card, parser manifest, and Markdown tree; target-document eligibility audit and its completed run card; frozen Stage A registries; exact provider-caps bytes and matching cycle; and the immutable canonical-journal identity and prior attempt authority. After unitization, it must verify every v5 selector and reconstructed canonical citation, then authenticate the v4 reviewer against the v5 unitizer card and the same chain. Downstream bundle, adjudication, decision-text, and Stage B commands must replay this mixed pair as one closed accepted chain. Stage B, evaluation, official freeze, and dispatch remain prohibited until the Stage A queue is adjudicated and finalized units replay successfully.

## Operational namespaces

The unitizer command must use `--provider-attempt-namespace claim-ontology-v5`. The structural-review command, including a provider-free terminalization receipt and resumed review, must use `--provider-attempt-namespace claim-ontology-v4`. Commands that authenticate completed cards must derive and verify those exact namespaces from the cards rather than accepting a caller-created pair. The historical [v4 correctness migration](cycle-1-stage-a-v4-correctness-migration.md) remains the authoritative record of its v4/v4 run; this document supersedes only the live successor instructions after the endpoint-arithmetic failure.
