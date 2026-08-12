# Cycle 1 Stage A unitizer terminal-review migration

**Status:** correctness-emergency migration for an exhausted `claim-ontology-v5` unitizer call; governed by [Cycle 1 change control](cycle-1-change-control.md).

## Trigger and bounded remedy

One selected candidate can exhaust all three authenticated Stage A unitizer reconstruction attempts without producing an accepted prediction unit. The pre-migration chain could preserve the failed provider evidence but could not complete an exact-100 Stage A artifact honestly: inventing an empty legal conclusion would lose the candidate, while issuing a fourth call would violate the fixed retry ceiling.

This migration adds a provider-free attorney reconstruction route. It authenticates exactly attempts 1, 2, and 3 from the canonical provider journal, commits the unchanged frozen unitizer prompt and predecision sources, resumes the unitizer with a candidate-level terminal sidecar, preserves that candidate through the structural reviewer without calling it, and permits the attorney either to add the reconstructed units or record that the candidate must be excluded. No failed model response becomes a prediction unit or legal suggestion. For the exact-100 cycle, an exclusion is a terminal stop: it requires an authenticated replacement before any complete finalized Stage A artifact may be published.

The route does not authorize a fourth provider call, expand a provider cap, release or rewrite a reservation, patch a failed response, weaken citation reconstruction, or relax any eligibility, lineage, review, adjudication, Stage B, evaluation, freeze, or dispatch gate.

## Versioned artifacts

The affected artifact chain is explicit and additive:

1. [`legalforecast.llm_stage_a_unitizer_terminal_escalation.v1`](schemas/llm-stage-a-unitizer-terminal-escalation-v1.md) is the immutable receipt for one selected candidate's three exhausted reconstruction failures.
2. [`legalforecast.unitizer_terminal_review_queue.v1` and `legalforecast.unitizer_terminal_review_bundle.v1`](schemas/unitizer-terminal-review-v1.md) present one candidate-level technical review item and its exact predecision Markdown.
3. [`legalforecast.successor_attorney_packet_manifest.v2` and `legalforecast.successor_attorney_packet_view.v2`](schemas/successor-attorney-packet-v2.md) add those candidate-level items to the existing private attorney packet without changing its frozen unit-review authority.
4. [`legalforecast.unitization_adjudication.v3`](schemas/unitization-adjudication-v3.md) records one `ADD` or `CANDIDATE-EXCLUSION` decision without pretending a source unit existed.
5. [`legalforecast.finalized_prediction_units.v4`](schemas/finalized-prediction-units-v4.md) binds the terminal receipt, queue, `ADD` adjudication, attorney-reconstructed units, and authenticated predecision documents. The exact-100 successor apply does not emit v4 for an exclusion.

The completed `llm-unitize` run card additionally commits every terminal receipt path and digest plus the separate `unitizer-terminal-review-queue.jsonl`. The raw candidate envelope remains present with `prediction_units: []`; its audit status is `terminal_escalation`. The v4 structural-review card preserves the same candidate with status `unitizer_terminal_preserved`, zero flags, and no reviewer prompt or provider attempt for that candidate.

## Frozen prompts and complete-chain validation

The `claim-ontology-v5` unitizer prompt bytes and the `claim-ontology-v4` structural-review prompt bytes are unchanged. The latter remain pinned by SHA-256 `d34a368f10dba9160399b97775d31847ad46f80610d80712f079f3410f6a7eac`. This migration adds no `claim-ontology-v6` unitizer and no v5 structural reviewer. The sole active pair remains v5/v4 as defined by the [v5 selector migration](cycle-1-stage-a-v5-unitizer-selector-migration.md).

Before emitting a terminal receipt, local code replays the exact selection, eligibility audit, parser manifest and Markdown, model registry, caps identity, journal identity, logical-call identity, prompt, sources, and all three durable failure rows. It then proves the journal did not change. Resume independently reconstructs that receipt from the same evidence and commits its exact bytes. Queue, bundle, packet, adjudication, and successor apply each independently reproduce the prior hash link and exact candidate coverage. Successor apply starts from the full raw unitizer JSONL and both authenticated Stage A run cards, partitions ordinary and terminal candidates internally, applies both decision streams, and replays the selection-order merge after writing.

An `ADD` must add at least one unit. Every complete citation structure is reconstructed against authenticated source text and validated for document role, exact line span and excerpt, page marker, and docket evidence; membership in the receipt's document-ID list alone is insufficient. A `CANDIDATE-EXCLUSION` adjudication emits no unit and causes exact-100 successor apply to fail closed without publishing a finalized artifact until the cohort has an authenticated replacement. Coverage drift, duplicate candidates, a changed prompt or source, citation drift, a fourth attempt, any settled or incomplete attempt set, any source-unit claim, or any broken digest stops the chain.

## Backward compatibility

All preexisting schemas and artifacts remain immutable and verifiable. A candidate with a settled v5 unitizer attempt continues through the ordinary unit-subject queue and v1/v2 adjudication path. Structural-review terminal escalation v1/v2 remains a different route for a unitizer that succeeded but whose v4 reviewer could not reconstruct a response. Successor attorney packet v1 remains valid when no unitizer-terminal candidates exist.

The terminal schemas are not accepted as aliases for earlier ones. In particular, adjudication v3 and finalized v4 are valid only for candidate-level unitizer-terminal review; ordinary omission `ADD` remains adjudication v2/finalized v3, and ordinary review actions remain governed by the existing v1/v2 finalized contracts. This separation prevents an emergency migration from widening the frozen unit-review ontology.
