# Cycle 1 v4 ranked-reserve continuation

This continuation replaces a candidate only after a downstream stage emits explicit terminal, nonretryable exclusion evidence.
It replays the complete frozen v4 target projection, retains the original target count, consumes the five-case reserve in its frozen order, preserves the canonical Cycle purchase ledger and hard cap, and emits a successor selected-XOR-excluded resolution.

This is not an acquisition rerun and does not edit the frozen v4 artifacts.
It performs no provider request, network request, fee acknowledgement, purchase, model evaluation, cycle freeze, or dispatch.
A replacement with missing paid documents stops with `successor_approval_required: true`; the original approval does not authorize the successor tranche.

## Required evidence

Use generated local metadata to locate these existing absolute paths:

- the completed v4 target-cohort root containing 100 selected cases and five ordered reserves;
- the approved v2 purchase policy, canonical ledger, initialization receipt, and original controlled private root;
- a separately committed terminal-exclusion JSONL file and its digest file; and
- a new continuation output root outside every frozen and private evidence root.

Each terminal record has the closed schema `legalforecast.ranked_reserve_terminal_exclusion.v1` and exactly these fields:

```json
{
  "candidate_id": "courtlistener-docket-00000000",
  "reason": "stage_a_boundary_unresolvable",
  "retryable": false,
  "schema_version": "legalforecast.ranked_reserve_terminal_exclusion.v1",
  "source_artifact_sha256": "sha256:<64 lowercase hex>",
  "source_record_sha256": "sha256:<64 lowercase hex>",
  "source_stage": "apply-unitization-review",
  "terminal": true
}
```

Provider failures, retryable errors, pending human review, and ambiguous records are not terminal evidence and must not consume a reserve.
Write the exact prefixed digest plus one newline to `terminal-candidate-exclusions.sha256`.

## Provider-free planning command

The reviewed path map is [`cycle-1-target-100.v4-ranked-reserve-replacement-plan.template.json`](../manifests/cycle-1-target-100.v4-ranked-reserve-replacement-plan.template.json).
It is deliberately a command template rather than an acquisition-cycle manifest: the planner may establish that a paid successor approval is required, but it must never chain automatically into a paid or downstream model stage.

Run the command with the absolute paths from generated local metadata:

```zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL

uv run legalforecast acquisition plan-ranked-reserve-replacements \
  --target-cohort-root "$frozen_v4_root" \
  --purchase-policy "$purchase_authority_root/purchase-policy-v2.json" \
  --controlled-private-root "$initial_private_root" \
  --purchase-ledger "$purchase_ledger" \
  --purchase-ledger-initialization-receipt "$purchase_ledger_receipt" \
  --terminal-exclusions "$terminal_evidence_root/terminal-candidate-exclusions.jsonl" \
  --terminal-exclusions-sha256-file "$terminal_evidence_root/terminal-candidate-exclusions.sha256" \
  --output "$continuation_root/replacement-result.json" \
  --active-selection-output "$continuation_root/active-selection.jsonl" \
  --replacement-selection-output "$continuation_root/replacement-selection.jsonl" \
  --successor-exclusions-output "$continuation_root/successor-exclusions.jsonl" \
  --replacement-budget-plan-output "$continuation_root/replacement-budget-plan.json"
```

The planner authenticates the target projection through the existing full semantic replay, not by reading the projection summary alone.
It then binds the exact selected, reserve, original-exclusion, and full source-pool bytes; verifies counts, canonical ID and reserve commitments, reserve ranks and costs, and resolved-pool reconciliation; checks the external terminal-evidence digest; and appends replay-safe hash-chained decisions to the existing purchase journal only after all validation and cap checks pass.

## Required stop

Review `replacement-result.json` before doing anything downstream.
Its activity and authority flags must all remain false.
If `successor_approval_required` is true, record and replay a new exact successor approval for `replacement-selection.jsonl` and `replacement-budget-plan.json`; do not reuse the original target-100 approval as authority for those documents.
Until that approval path authenticates this ranked-reserve result schema, stop without purchasing.

Only a later, separately reviewed continuation may rebuild acquisition materialization, Stage A, Stage B, packet inputs, or corpus readiness from `active-selection.jsonl` and `successor-exclusions.jsonl`.
Evaluation, freeze, and dispatch remain out of scope.
