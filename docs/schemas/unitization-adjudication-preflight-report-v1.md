# Unitization Adjudication Preflight Report v1

`legalforecast.unitization_adjudication_preflight_report.v1` is the stdout-only report printed by `acquisition preflight-unitization-adjudication`. It is observational: the command authenticates its inputs and rehearses `apply_unitization_reviews` with the exact invariants apply enforces, but the report itself is never written by the pipeline, never consumed by a downstream gate, and never becomes an authenticated artifact.

## What the command authenticates

The preflight is provider-free and non-writing. It replays the completed `llm-unitize` and structural-review run cards, reads every input exactly once as singly linked regular bytes, re-checks those bytes after the report is assembled, and then runs the frozen applicator over the raw prediction units, the exact merged review queue, and the proposed adjudications. A failure is the same `UnitizationReviewError` apply would raise. When `--finalized-prediction-units` is passed, the artifact is verified with the independent finalized-units verifier and must equal the recomputation byte-for-byte.

## Report contents

- `input_commitments` — resolved path plus `sha256:`-prefixed digest of every input, computed from the exact bytes that were parsed.
- `totals` and per-candidate counts — before/after unit counts, additions, drops, excluded candidates, unclear units (`challenge_scope: unclear`), nonmovant units (`challenged_by_motion: false`), duplicate claim-defendant keys, and nonconforming adjudicated units.
- `worklist` — one row per adjudication, grouped per candidate and sorted by `adjudication_id`, echoing the disposition, adjudicator, consumed review IDs, reviewed units, route reasons, source units, emitted units, and the drop, exclusion, or structural-flag binding where applicable. Source and emitted units are derived from the applicator's validated provenance, not from a second reading of the adjudication rows.
- `matrix` — the per-candidate claim-defendant matrix keyed by `(claim_name, defendant_group)` (the claim-ontology-v4 contract folds movant capacity into `defendant_group`), with before/after unit entries carrying challenge scope, motion challenge, grouping, and `should_score`.
- `finalized_artifact` — `null`, or the canonical-records digest of the optional finalized artifact with `matches_recomputation: true`.

Adjudicated `AMEND`/`SPLIT`/`MERGE` outputs are not required by apply to be canonical prediction units, so the preflight reports a unit missing well-formed matrix fields as nonconforming instead of inventing a new gate.

## Privacy

The report is deterministic: identical inputs print identical bytes. Lists are sorted, except that a worklist row's `review_ids`, `reviewed_unit_ids`, and `source_unit_ids` preserve the adjudication's own consumption order, which is itself part of the authenticated content. The report contains blinded Stage A case content: keep any saved copy under the private review root, outside the repository and every publishable root.
