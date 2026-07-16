# Labeling Protocol

LegalForecast-MTD labels each frozen prediction unit from the first written disposition of the motion to dismiss. The primary target is whether that claim-defendant unit was dismissed in full. The label is not an assessment of whether dismissal was legally correct, and it is not revised because of later events.

## Scope

A prediction unit is a challenged claim against a defendant or group of similarly situated defendants. Stage A freezes the prediction units from the pre-decision record. Stage B labels only those frozen units from the written disposition and may not create new scored units from the decision text.

Bankruptcy adversary proceedings are eligible only when the docket is explicitly identified as an adversary proceeding, was begun by a complaint or counterclaim, and contains a linked motion challenging the adversary proceeding, complaint, counterclaim, claims, counts, or other pleadings. The motion may establish its Rule-12-equivalent basis either by expressly invoking Bankruptcy Rule 7012 or Civil Rule 12(b)–(i) or 12(c), or by explicitly asking to dismiss the adversary proceeding or adversary complaint. Ordinary motions to dismiss or convert a main bankruptcy case remain outside the benchmark because they do not produce claim-by-defendant prediction units. Administrative, stipulated, voluntary, and generic non-motion dismissal entries remain insufficient. Eligible adversary matters are reported separately as the `bankruptcy_adversary` case-type stratum; related-family identifiers are preserved only when supplied explicitly and are never inferred from captions or docket-number proximity.

Every scored label must cite a verbatim excerpt from the disposition. Excerpts are validation material: if the cited text is not present in the first written disposition text, the label is invalid.

## Cycle 1 Model Panel

Cycle 1 freezes construction models separately from the candidate-model evaluation registry in `model_registries/cycle-1-labeling-2026-07-12.json`, and freezes the exact voting panel in the dedicated `model_registries/cycle-1-stage-b-judges-2026-07-12.json` registry. Labeling-model release dates therefore do not alter the corpus eligibility anchor computed from `model_registries/cycle-1-2026-06-30.json`. `llm-label` requires every entry in the dedicated judge registry to be selected explicitly and refuses blank, duplicate, omitted, or extra judges.

Claude Sonnet 4.6 (`claude-sonnet-4-6`) constructs Stage A units from blinded pre-decision materials only. Gemini 3.5 Flash (`gemini-3.5-flash`) performs a flag-only structural review before the units freeze; it may identify omitted, combined, or mis-split units but may not rewrite them. GPT-5.4 mini (`gpt-5.4-mini-2026-03-17`) and Gemini 3.5 Flash are the frozen Stage B voters. A Stage B model classifies the canonical frozen unit identifiers; it does not regenerate party names, claims, or unit boundaries. Agreement is computed over the structured outcome fields, not over prose rationales or the exact span selected as the supporting excerpt.

Google's documentation calls `gemini-3.5-flash` a stable ID that "usually" does not change; it does not document that ID as an immutable snapshot or expose a dated snapshot ID. Cycle 1 therefore freezes the exact stable ID and records this limitation rather than describing it as immutable. A live identity probe returned the same `modelVersion` on July 12, 2026, and every official call must return that exact served version or fail closed. Do not substitute `gemini-flash-latest`. This explicitly documented construction-model exception does not relax the candidate-model registry requirements.

Once both Stage B snapshots are eligible and frozen, an automatic label requires exact two-model agreement on the structured outcome tuple and valid verbatim disposition evidence from both voters. Any outcome disagreement, ambiguity, low-confidence response, structural objection, or invalid excerpt routes to lawyer review; there is no majority fallback.

The structured outcome tuple includes `unit_resolution`, so `partial_dismissal_only` and `survives_in_material_respect` remain distinct even though both map to `fully_dismissed = false`. The field is preserved through model votes, auto labels, lawyer responses, adjudications, resume reconstruction, and audit comparisons.

## First Written Disposition

The benchmark locks labels to the first written disposition that resolves the relevant motion-to-dismiss issue. Reconsideration orders, appeals, amended complaints, settlements, and later voluntary dismissals can be recorded as later procedural changes, but they do not change the locked primary label.

If a later order changes the practical posture of the case, the label remains tied to what the first written disposition did to the frozen unit. This rule keeps scoring aligned with what the model was asked to forecast.

Stage B and label-audit disposition text must come from `uv run legalforecast acquisition build-decision-texts`. The command requires exact cohort and document reconciliation against committed target-cohort, authenticated disclosure-clearance, restriction, and live pinned-Mistral-parser run cards and artifacts; enforces the Cycle 1 eligibility anchor; and admits only a single public, explicitly outcome-bearing disposition that was never model-visible. Its hash-bound JSONL output is private label evidence, not packet input. `llm-label` requires that JSONL, its immutable manifest, and the completed builder run card; it authenticates their hashes, source hash and byte count, empty parser quality flags, exact candidate and case mapping, and selection/parser/finalized-unit coverage and provenance before any provider call. Parser Markdown is retained only as a pinned-lineage cross-check: every Stage B prompt is constructed from the authenticated JSONL record and binds the JSONL, manifest, run-card, record, text, raw finalized-units, and candidate-envelope hashes into the provider journal and audit. Do not hand-author or edit these artifacts; any missing, extra, duplicate, ambiguous, restricted, malformed, unauthenticated, hash-drifted, fixture-derived, or unpinned input stops the stage.

## Primary Outcome

The primary label is `fully_dismissed`.

- `true`: the first written disposition fully dismisses the frozen claim-defendant unit.
- `false`: the unit survives in any material respect, including a partial dismissal that leaves any theory, claim, defendant group, or requested relief in that unit alive.
- `null`: the disposition is ambiguous and the unit has no primary scoring outcome.

Micro-Brier scoring uses `primary_outcome`: `1` for fully dismissed, `0` for not fully dismissed, and no scored value for ambiguous units.

## Partial Dispositions

A partial dismissal is not a full dismissal. If the court dismisses one theory, one remedy, one defendant, or one portion of a claim but leaves the frozen unit alive in material respect, label the unit as not fully dismissed.

Examples:

- "The notice theory is dismissed, but Count IV survives" maps to `fully_dismissed = false`.
- "Count I is dismissed as to the issuer, but denied as to the officer defendants" maps separately by unit: issuer unit `true`, officer unit `false`.
- "Punitive damages are dismissed, but the claim proceeds" maps to `false` for a claim-level unit.

## Leave To Amend

Leave to amend is a secondary label, not the primary target. A claim dismissed in full with leave to amend is still `fully_dismissed = true` for the primary benchmark outcome.

For fully dismissed units, record one amendment class:

- express leave to amend or an express invitation to seek leave: `dismissed_with_express_amendment_opportunity`
- express denial of leave: `dismissed_with_express_denial_of_leave`
- dismissal silent on amendment: `dismissed_without_express_amendment_opportunity`

The conditional amendment target applies only to fully dismissed units. Units that survive in material respect use `not_fully_dismissed` and do not receive a conditional amendment target.

## Mooted Motions

If the first written disposition denies or terminates the MTD as moot without independently dismissing the frozen claim-defendant unit, label the unit as not fully dismissed. The benchmark target is whether the judge dismissed the frozen unit in full, not whether the original motion remained procedurally live.

If the same disposition both declares a motion moot and separately dismisses the frozen unit in full, label the unit as fully dismissed and record the applicable amendment class. If the text does not make the unit-level outcome clear, mark the unit ambiguous rather than guessing.

## Ambiguous Or Missing Coverage

Use `ambiguous` when the first written disposition cannot be mapped reliably to a frozen unit. Ambiguous labels omit `fully_dismissed`, use the ambiguous amendment class, and are excluded from primary scoring.

If the decision resolves a material unit that Stage A failed to freeze, do not create a new scored unit at Stage B. Record a missing-unit flag and exclude the affected frozen unit from scoring under the v0.1 policy below.

If a frozen unit is not addressed by the first written disposition, do not infer an outcome from silence. Route it for review or exclusion under the current cycle's adjudication policy.

## Fail-Closed Human Review Gates

Stage A construction ambiguities are written to `unitization-review-queue.jsonl` with deterministic review IDs and remain outside the clean corpus until John or a delegated lawyer supplies a separate, checked-in adjudication record. Preserve that original queue, then run `llm-review-stage-a` with the frozen Gemini registry entry. The structural-review outputs are a flag artifact, a complete per-candidate audit, and the deterministic union of the original queue plus structural flags. Final readiness requires all three, verifies Gemini's served version and input/output commitments, and rejects a queue that is not the exact verified union.

The generated queue is immutable evidence, not an adjudication surface. Copy its identifiers into a separate `legalforecast.unitization_adjudication.v1` JSONL file; never edit or reorder the queue to record a decision. Each adjudication names the adjudicator, records nonempty notes, and uses exactly one disposition: `ACCEPT`, `AMEND`, `SPLIT`, `MERGE`, or `CANDIDATE-EXCLUSION`. Amendments and split/merge replacements must be derived only from the blinded predecision materials in the queue workflow.

Drain Stage A manually before labeling:

1. Review every pending queue item against only the predecision materials and write checked-in adjudication rows. A merge names every consumed review and source unit; a candidate exclusion consumes every unit and pending review for that candidate.
2. Run `uv run legalforecast acquisition apply-unitization-review --help`, then execute the documented command with the raw prediction units, immutable queue, adjudications, and an isolated output root.
3. Inspect the resulting `finalized-prediction-units.jsonl` diff and reconcile candidate/unit counts. The command fails unless every queued review is consumed exactly once and every output is hash-linked to its raw units, the exact merged review queue, and any adjudication.
4. Pass only that finalized artifact to `llm-label`, packet planning, readiness, and `finalize-corpus`. Those gates reject the raw `llm-unitize` artifact.

Before production labeling begins, run `uv run legalforecast acquisition generate-labeling-policy --help` and publish the immutable labeling policy from the frozen Stage B judge registry, approved publication timestamp, and threshold source. Verify it with `acquisition verify-labeling-policy`. These commands call the same canonical pure generator and verifier used by the freeze tooling, but cannot freeze, dispatch, evaluate, or mutate official cycle state; rerunning the generator is idempotent only when the requested bytes are identical. At final readiness, `finalize-corpus` also requires the exact policy and two-model judge registry, rejects any consensus other than unanimous, and validates each voter's served version and verbatim disposition excerpts.

Stage B does not sample inside the per-case labeling loop. After the whole cycle's ensembles are durable, run `acquisition plan-label-audit` with that precommitted labeling-policy artifact. The command hashes the pre-adjudication ensemble corpus, derives its seed from `SHA-256(cycle_id || ensemble_corpus_sha256 || labeling_policy_sha256)`, allocates one sample across grant, deny, and partial strata by largest remainder with the frozen per-stratum minimum, and writes blinded review packets without the ensemble's proposed outcome. Empty population strata are recorded as empty; any observed but unsampled stratum fails closed.

Pass the generated cycle-planned audit JSONL, immutable cycle audit plan, and exact precommitted labeling policy to `apply-lawyer-review`. Audit-sample adjudications measure but never replace the frozen unanimous auto label. The case cannot count clean until the cycle-level gate reconstructs the plan from that policy and the pre-adjudication ensemble corpus, then passes its per-stratum LLM-error and human-disagreement ceilings. Keep the full plan, ensembles, review queue, and annotations in controlled private storage; only the redacted hash-bound audit and routing summaries are check-in safe. Pending adjudications remain John decisions.

Pending adjudications are John decisions. Automation may assemble the queues and validate checked-in results, but it must not self-adjudicate them.

## Frozen-Unit Repair Policy (v0.1: Exclusion-Only)

The v0.1 benchmark policy is **exclusion-only**. When Stage B reports that the decision resolved a material unit missing from the frozen Stage A set, the affected frozen unit is excluded from scoring rather than repaired. Exclusion is the conservative direction: it removes a unit the model was never given a fair chance to forecast instead of retroactively adding a scored unit informed by the decision text.

Blinded frozen-unit repair — reconstructing the missing unit from the pre-decision record only, without exposing the disposition to the Stage A unitizer — is planned as **future work**. The data structures for blinded repair exist (`BlindedUnitRepairRequest`, `repair_frozen_units` in `legalforecast/unitization/adjudication.py`), but v0.1 has no production repair path or CLI and does not invoke one. Until a blinded repair workflow is built and validated, every missing-Stage-A case takes the exclusion branch.

Each such exclusion is recorded in the exclusion ledger with the primary reason `unit_missing_from_stage_a`, so the count of frozen-unit exclusions is auditable rather than silent.

## Public Accounting

Released artifacts should let reviewers distinguish at least these categories:

- scored fully dismissed units
- scored surviving or partially surviving units
- ambiguous units excluded from primary scoring
- frozen units excluded because a material unit was missing from Stage A (exclusion ledger reason `unit_missing_from_stage_a`; blinded repair is future work, so v0.1 counts these as exclusions)
- units or cases excluded because the first written disposition did not support a reliable label

Frozen-unit exclusion counts, keyed by exclusion-ledger reason (including `unit_missing_from_stage_a`), should be reported as aggregate counts in the released public accounting so an auditor can see how many units were dropped and why, without exposing non-public candidate material. The underlying per-candidate exclusion ledger stays in the private audit bundle; only the aggregate counts are public. The public artifact should include enough citation metadata for an auditor to trace every scored label back to the first written disposition without exposing non-public material.
