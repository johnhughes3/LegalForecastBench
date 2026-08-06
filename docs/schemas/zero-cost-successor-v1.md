# Zero-cost exact-100 successor v1

`legalforecast acquisition project-zero-cost-successor` is the provider-free bridge from the authenticated 99-case ranked-reserve precursor to an exact 100-case acquisition cohort.

The command replays the complete original target projection, substantively replays the purchase policy, journal, initialization receipt, purchase result, purchase run card, and screening snapshot that issued the opaque terminal-disposition authority, and requires that authority's exact closed disposition to equal the ranked-reserve result's terminal partition. It accepts the historical v2 result, the current-state v3 result, and the post-purchase v4 result. A v3 or v4 result must carry a closed `authenticated_legacy_replay` proof whose embedded canonical v2 precursor matches `precursor_result_sha256`, whose four precursor output commitments equal the independently verified current companion artifacts, and whose exhaustive event hashes equal the durable replacement-event sequence. A v4 result must additionally carry the closed `authenticated_post_purchase_replay` proof and the command requires the complete `--prior-ranked-result`, `--prior-replacement-selection`, `--prior-replacement-budget-plan`, `--replacement-purchase-authority`, `--replacement-controlled-private-root`, and `--cohort-policy` bundle. The downstream command replays the actual replacement authority before minting the opaque transition capability, reconstructs the entire v4 result byte-for-byte, and only then mints the full-result capability required by the zero-cost projector. It authenticates the proof's exact prior v3 digest, replacement-authority digest, baseline and current state and money, and disjoint baseline/successor operation hashes against the current journal. Neither a digest-only proof nor two identical caller-supplied mappings substitute for the verifier-issued capabilities.

The proof schema `legalforecast.ranked_reserve_legacy_event_replay.v1` contains exactly twelve fields: `schema_version`, `precursor_result`, `precursor_result_sha256`, `precursor_active_selection_sha256`, `precursor_replacement_selection_sha256`, `precursor_successor_exclusions_sha256`, `precursor_replacement_budget_plan_sha256`, `historical_purchase_journal_state_sha256`, `historical_terminal_evidence_sha256`, `current_terminal_evidence_sha256`, `authenticated_event_record_sha256s`, and `historical_state_substitution_only`.

Only then does it prove that the active precursor is exactly 97 retained original cases plus frozen reserve ranks 1 and 2 and replays the completed model-backed disclosure-clearance run card.

It considers only candidate IDs `70525291`, `71279774`, and `71677178`, in that order, and selects the first candidate whose exact document set is complete and cleared.

Every candidate must retain the Cycle 1 eligibility anchor, have no model-visible target outcome, have complete core-document relevance, and have no positive sealed, private, or restricted marker.

The added candidate's documents must all be free, and the final 100-case selection, relevance, merged manifest, disclosure clearance, and restriction surfaces must expose one identical unique document-key universe.

The output root uses the standard target-cohort filenames:

- `target-cohort-selection.jsonl`
- `target-cohort-projection.json`
- `case-relevance.jsonl`
- `document-downloads-merged.jsonl`
- `free-document-downloads.jsonl`
- `purchased-document-downloads.jsonl`
- `disclosure-clearance.jsonl`
- `restriction-evidence.jsonl`
- `core-filter-results.jsonl`
- `missing-core-budget-plan.json`
- `target-cohort-exclusions.jsonl`
- `target-cohort-ranked-reserve.jsonl`
- `run-cards/project-target-cohort.json`

The projection schema is `legalforecast.zero_cost_successor_config.v1`; its closed record commits the unchanged cycle ID, target count, anchor, hard cap, frozen candidate order, selected candidate, every authenticated source, and every emitted data artifact.

The terminal state schema is `legalforecast.zero_cost_successor_state.v1`; it records the exact 97 plus 2 plus 1 composition, spend and headroom carried from the ranked result, and false provider, paid, evaluation, freeze, and dispatch authorities.

The standard materialization projection loader recognizes this successor state as a separate closed union member, replays `project-zero-cost-successor` from the fifteen committed inputs, rejects any unexpected, linked, or special file in the output tree, requires byte-identical immutable outputs, and only then returns the normal selection, free/purchased manifest, clearance, restriction, and selected-document-key interface consumed by `materialize-cohort-documents`.

The command never contacts CourtListener, PACER, or a model provider, never mutates its inputs, and publishes only immutable outputs.
