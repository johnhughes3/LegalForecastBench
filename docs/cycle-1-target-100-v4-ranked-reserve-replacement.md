# Cycle 1 v4 ranked-reserve continuation

This continuation replaces a candidate only after a downstream stage emits explicit terminal, nonretryable exclusion evidence.
It replays the complete frozen v4 target projection, consumes the reserve only in its frozen order, preserves the canonical Cycle purchase ledger and hard cap, and emits a successor selected-XOR-excluded resolution.
When the unchanged cap cannot fund every terminal replacement, the result is an explicitly incomplete precursor whose `active_case_count` is below 100; it must not be presented to downstream corpus stages as a complete cohort.

This is not an acquisition rerun and does not edit the frozen v4 artifacts.
It performs no provider request, network request, fee acknowledgement, purchase, model evaluation, cycle freeze, or dispatch.
A replacement with missing paid documents stops with `successor_approval_required: true`; the original approval does not authorize the successor tranche.

## Required evidence

Use generated local metadata to locate these existing absolute paths:

- the completed v4 target-cohort root containing 100 selected cases and five ordered reserves;
- the approved v2 purchase policy, canonical ledger, initialization receipt, and original controlled private root;
- the completed purchase result and run card plus the pinned complete screening snapshot used to derive the terminal retained-versus-residual partition; and
- a new continuation output root outside every frozen and private evidence root.

`continuation_root` names the parent replacement-cycle root used by the checked-in downstream coordinators. The planner owns its canonical `01-plan` child; do not bind `continuation_root` to an `01-plan` directory or create a manual alias.

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

Unauthenticated provider failures, retryable errors, pending human review, and ambiguous records are not terminal evidence and must not consume a reserve.
Write the exact prefixed digest plus one newline to `terminal-candidate-exclusions.sha256`.

## Authenticated terminal RECAP failures

The provider-free adapter in `legalforecast.ingestion.terminal_purchase_failure` may issue terminal retrieval authority only for a completed live `purchase-missing-recap-fetch` result whose `provider_error` attempt encodes CourtListener queue status `3`, `6`, or `7` and whose exact canonical purchase ledger has the matching `failed` operation.

`verify_terminal_purchase_failure_authority(...)` accepts paths to the purchase result and completed acquisition run card plus the already-authenticated `CaseDevPurchaseJournal`.
It captures both inputs through race-checked, no-follow unique-regular-file reads, requires the run card's first output path to repeat the caller-supplied result path in exactly the same string form and its second output path to name the canonical ledger, and safely captures the purchase budget plan named by the run card's first input path.
Pass a relative or absolute result path exactly as the producer recorded it; those two spellings are not interchangeable at this provenance boundary.
Every candidate/document attempt in that committed budget-plan tranche must appear exactly once in the result, while historical failures from an earlier completed tranche may remain durably cap-counted in the ledger.
The verifier also binds the UUID operation key, queue and reservation identities, unchanged policy reservation, complete purchase counts, result and run-card hashes, journal-state hash, and the fact that each unreconciled failed response still counts its full reservation against both budget caps.

The verifier fails closed for queue status `1`, `4`, or `5`, every retryable, `not_attempted`, or unknown result, any submitted, queued, or unknown journal operation, a missing or mismatched result/run card/ledger operation, a released or reconciled hold, a different reservation, a non-CourtListener failure, or a fabricated authority object.

`terminal_retrieval_exclusions_bytes(authority)` emits canonical `legalforecast.ranked_reserve_terminal_exclusion.v1` JSONL with `source_stage=purchase-missing-recap-fetch`; its source hashes bind the closed `legalforecast.terminal_recap_fetch_failure_evidence.v1` records retained by `authority.evidence_records`.

The core planner accepts those retrieval-stage records only when the caller also supplies the same verifier-issued object as `terminal_purchase_failure_authority=authority` and the current journal still has its authenticated state hash.
At planner time the authority replays the substantive verifier from its immutable captured source bytes and requires the regenerated evidence to match exactly, so neither a raw lookalike JSONL nor direct access to a private issuer helper can consume a reserve.
The authority covers the complete terminal-failure universe for its purchase tranche.
The supported CLI composes it with `verify_docket_decision_text_sources(...)`, which replays the frozen selection and pinned screening snapshot and derives one exact, disjoint, exhaustive retained-versus-residual partition.
Only the verifier-owned residual terminal bytes reach the reserve planner; no caller supplies retained IDs, residual IDs, or a terminal subset.

This adapter performs only local safe reads; it performs no file write, network request, provider request, purchase, journal mutation, model call, evaluation, freeze, or dispatch.
The CLI invokes the verifier only after the result and run card are durably published, rechecks every captured source before publishing outputs, and passes the opaque disposition authority into the planner.
It rechecks and substantively replays that authority immediately before the planner's first journal mutation and again before output publication.
Authenticated runs emit `legalforecast.ranked_reserve_replacement_result.v2`, which commits the complete closed disposition record and its purchase-result, purchase-run-card, screening-snapshot, retained-source, and residual-exclusion hashes.

When a fresh replay follows an unrelated, authenticated purchase-material recovery, the command accepts `--legacy-ranked-result` as a singly linked canonical v2 witness and emits `legalforecast.ranked_reserve_replacement_result.v3`. The v3 top level commits the current journal state and current terminal disposition. Its closed `authenticated_legacy_replay` object proves that substituting only the historical aggregate journal-state commitment reconstructs the complete legacy terminal-evidence artifact and every durable replacement-event source hash. The proof embeds the canonical v2 `precursor_result` and binds its digest, so every downstream replay can reauthenticate the predecessor rather than trusting self-asserted hashes. Legacy replay cannot append replacement events. The active selection, replacement selection, successor exclusions, and replacement budget plan must be independently rendered byte-identically to their v2 commitments; prior output bytes are never copied.

The proof schema `legalforecast.ranked_reserve_legacy_event_replay.v1` is closed to exactly these fields: `schema_version`, `precursor_result`, `precursor_result_sha256`, `precursor_active_selection_sha256`, `precursor_replacement_selection_sha256`, `precursor_successor_exclusions_sha256`, `precursor_replacement_budget_plan_sha256`, `historical_purchase_journal_state_sha256`, `historical_terminal_evidence_sha256`, `current_terminal_evidence_sha256`, `authenticated_event_record_sha256s`, and `historical_state_substitution_only`.
The legacy `--terminal-exclusions` mode remains available only for authenticated non-retrieval downstream exclusions and is mutually exclusive with purchase-result disposition mode.

## Provider-free planning command for authenticated retrieval failures

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
  --purchase-result "$purchase_result_root/purchased-document-downloads.jsonl" \
  --purchase-run-card "$purchase_result_root/run-cards/purchase-missing-recap-fetch.json" \
  --screening-snapshot-manifest "$screening_snapshot_root/manifest.json" \
  --output "$continuation_root/01-plan/replacement-result.json" \
  --active-selection-output "$continuation_root/01-plan/active-selection.jsonl" \
  --replacement-selection-output "$continuation_root/01-plan/replacement-selection.jsonl" \
  --successor-exclusions-output "$continuation_root/01-plan/successor-exclusions.jsonl" \
  --replacement-budget-plan-output "$continuation_root/01-plan/replacement-budget-plan.json"
```

For the recovery-only replay that follows an unrelated journal-state advance, run the same authenticated command with the canonical predecessor added before the outputs:

```zsh
  --legacy-ranked-result "$legacy_plan_root/replacement-result.json"
```

Do not use that option for an initial v2 plan.

The planner authenticates the target projection through the existing full semantic replay, not by reading the projection summary alone.
It then binds the exact selected, reserve, original-exclusion, and full source-pool bytes; verifies counts, canonical ID and reserve commitments, reserve ranks and costs, and resolved-pool reconciliation; authenticates the exact residual terminal digest from the exhaustive disposition authority; and appends replay-safe hash-chained decisions to the existing purchase journal only after all validation and cap checks pass.
If output publication is interrupted after those journal appends, rerunning the same authenticated command reconstructs the same rank-1/rank-2 tranche and immutable bytes from the durable events rather than emitting an empty successor tranche.

For the current Cycle ledger, the frozen completion envelope is `$545.95` and only `$21.35` remains under the unchanged `$567.30` cap.
That headroom permits reserve rank 1 (`$9.15`) and reserve rank 2 (`$12.20`) exactly.
Rank 3 is not attempted, inspected as an alternative, or authorized; with three residual terminal candidates the output is therefore the authenticated 99-case precursor comprising 97 retained original candidates plus ranks 1 and 2.

## Required stop

Review `01-plan/replacement-result.json` before doing anything downstream.
Its activity and authority flags must all remain false.
If `successor_approval_required` is true, record and replay a new exact successor approval for `replacement-selection.jsonl` and `replacement-budget-plan.json`; do not reuse the original target-100 approval as authority for those documents.
Until that approval path authenticates this ranked-reserve result schema, stop without purchasing.

After the operator records that exact successor approval, first render [`cycle-1-target-100.replacement-recovery-disclosure-plan.template.json`](../manifests/cycle-1-target-100.replacement-recovery-disclosure-plan.template.json). It binds the ranked-reserve projection digest `sha256:1dab63dd17c69fd0222b58d6e30af67ad56550ca6578262f1089222a68257e56` directly, preserves the successor attempt policy, performs the exact purchase and recovery, and completes `plan-disclosure-provenance` under an immutable `PLAN_ROOT`; it does not accept the older clearance-replacement frontier.
Its paid stage uses `--direct-courtlistener-purchase`, the existing CourtListener request ledger, the successor attempt policy and purchase authority, and the unchanged Cycle ledger and caps. Rendering or preflighting it performs no provider call, fee acknowledgement, or purchase.

Inspect only the completed plan run card and authenticated worksheet to choose the suffix. Render [`cycle-1-target-100.replacement-disclosure-model-continuation.template.json`](../manifests/cycle-1-target-100.replacement-disclosure-model-continuation.template.json) when eligible exceptions exist, or [`cycle-1-target-100.replacement-disclosure-empty-continuation.template.json`](../manifests/cycle-1-target-100.replacement-disclosure-empty-continuation.template.json) when the run card proves the eligible set is empty. Supply the same `PLAN_ROOT` to the chosen suffix. Neither suffix contains purchase, recovery, or planning stages, so it cannot repurchase the tranche or rewrite the plan. The empty continuation requires the exact plan run card and `--require-no-model-review-eligible-exceptions`; the model continuation supplies the authenticated model authority instead. Exactly one mode must be selected.

An `active_case_count` below 100 is a precursor only.
A separately authenticated zero-cost clearance successor must bring it back to exactly 100 before the replacement reprojection and corpus templates may rebuild acquisition materialization, Stage A, Stage B, packet inputs, or corpus readiness.
Evaluation, freeze, and dispatch remain out of scope.
