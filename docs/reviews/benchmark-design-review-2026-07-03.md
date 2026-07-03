# LegalForecastBench Design Review — 2026-07-03

**Tracking:** every finding below has a bead (`bd show <id>`). Blockers: `LegalForecastBench-66z` (B1 gate wiring), `-3i6` (B1 release anchor), `-e2u` (B1 README claim), `-u5g` (B2 human audit), `-mm0` (B2 exclusion ledger), `-utk` (B2 silent defaults), `-9v8` (B3 packet fail-open). Highs: `-d08` (baselines), `-e8e` (family clustering), `-g9g` (snapshot verification), `-7vh` (durable results), `-qqf` (prior art). Mediums/lows: `-49g -zbu -d9m -xvf -8fu -xby -e8f -dw7 -1zn -0mf`. The pre-first-run gate is **`LegalForecastBench-t78`**: run `uv run scripts/verify_review_blockers.py` — all checks must PASS before the first official run.

Multi-agent review of the benchmark design, code, and positioning before the first full official run. Six review lenses (conceptual validity, statistical design, contamination/leakage, ground-truth labeling, reproducibility/governance, prior art) ran in parallel; every blocker/high finding below was independently adversarially verified against the actual code, and all survived (a few with refinements, noted inline). Raw structured findings: 29 agents, ~4.6M tokens; per-finding evidence cites `file:line`.

## Verdict

The benchmark concept is sound and the *design* is unusually rigorous for a pre-release solo project — reviewers repeatedly found that the hard problems (partial dismissals, leave to amend, case-clustered inference, dominance sensitivity, publication guardrails) are already solved correctly *as library code*. The dominant failure mode is a single pattern repeated across every subsystem: **the machinery that implements the benchmark's headline guarantees exists, is typed, and is unit-tested, but is not wired into any production path.** The contamination gates, the empirical baselines, the human adjudication layer, and the exclusion ledger are all dead code reachable only from tests and the synthetic fixture. The first official run, as currently wired, would produce a leaderboard whose central claims (contamination-free, leakage-screened, reasoning-proxying) rest on undocumented manual curation rather than the code that was written to enforce them.

The good news: nearly every fix is *wiring*, not redesign.

## Blockers (fix before the first run)

### B1. Contamination gates are dead code, and the release anchor is neither computed nor computable

- `detect_outcome_leakage` (`legalforecast/selection/contamination_filters.py:125`) is called only from tests. `ContaminationMetadata` / `SeriesCaseTiming.decision_entered_after_model_release` (`selection/eligibility.py:134-197`) is constructed only by the synthetic fixture (`cli.py:3755-3776`, hardcoded date). `screen_courtlistener_docket_for_mtd_decision`'s date window (`ingestion/mtd_acquisition_screen.py:340-376`) is test-only. `ExclusionLedgerEntry.from_outcome_leakage` is test-only, so leakage exclusions are never durably logged. The real path (`plan-packet-inputs` → `packet_input_planner` → `model_packet_assembly`) and `.github/workflows/run-benchmark.yaml` perform zero date/eligibility checks.
- No code anywhere computes `max(release_timestamp)` over the run's registry. The pilot registry's Gemini 3 Flash Preview entry has `release_timestamp: null` and a mutable preview alias, yet is in the workflow's default model set (`run-benchmark.yaml:39`) — so the README claim "there's no chance that any model … was contaminated" (`README.md:3`) is unverifiable for one of three pilot models and unenforced for all of them.

**Fix:** (1) wire the acquisition screen with `decision_filed_on_or_after = max(registry release timestamps)`; (2) make the eval path re-verify eligibility from the manifest and refuse to run otherwise; (3) require non-null `release_timestamp` + pinned dated snapshot for every model in an anchored run, failing closed (drop or re-anchor the Gemini preview); (4) soften the README's absolute claim to what the mechanism guarantees, and document the residual risk of providers updating served models post-release; (5) emit `ExclusionLedgerEntry` records to a checked-in ledger.

### B2. Ground truth is LLM-only with no measured error rate; the human layer is dead code

- The designed safety net — `LAWYER_ADJUDICATION` routing (`ensemble.py:430-479`), stratified audit of unanimous labels (`audit_ensemble_labels`, `enforce_label_audit_acceptance`), human reliability reports, blinded frozen-unit repair (`adjudication.py`) — has zero callers outside tests. The only wired path (`acquisition llm-label` → `llm_pipeline.py:227`) hardcodes `human_verified: False`, ignores the ensemble's own low-confidence routing, and ignores `requires_frozen_unit_workflow` flags from Stage B judges.
- Circularity, verified and worse than suspected: the pilot's label judges were the *identical three frozen-registry model entries* being benchmarked. Correlated judges misreading a hard opinion the same way yields unanimous, high-confidence, wrong labels — concentrated exactly where the benchmark should discriminate. With no audited error rate, there is no empirical bound on how much of a reported Brier gap is label noise.
- Silent selection effect: under `UNANIMOUS` + `continue_on_error`, judge disagreement or ambiguity drops the whole case with only a private audit row — no exclusion-ledger entry, no human look (pilot case 71160717 exited this way). Cases hard for LLMs to label are plausibly the cases hard to predict; filtering them flatters LLM predictors and undermines the proxy-for-reasoning thesis directly.
- Silent lenient defaults in unitization parsing (`llm_pipeline.py:705-714`): missing model output becomes `challenged_by_motion=True`, `ENTIRE_CLAIM` scope, confident, review-exempt units.

**Fix:** wire the adjudication routing and the stratified human audit before labeling the first real cohort; publish the audited LLM-label error rate; write exclusion-ledger entries for label-difficulty drops and report the count; add a "not addressed by this disposition" resolution so judges aren't forced to guess; make at least one label judge disjoint from the benchmarked model set per cycle; make missing unitization fields fail closed.

## High-severity findings

### H1. The benchmark's own key question is not answerable by the official run as wired

The baseline suite that would separate "reads the record" from "exploits priors" — `GLOBAL_BASE_RATE`, `COURT_NOS_MOTION_BASE_RATE`, `METADATA_ONLY`, `JUDGE_HISTORY` (`evals/baselines.py:14-20`) — is dead code with no training-corpus pipeline, no CLI, and no aggregation. The published BSS is computed against an *in-sample* constant base rate (`official_aggregate.py:689-731`). Ablation modes (`metadata_only`, `judge_removed`, `briefs_only_redacted`) are workflow-selectable but nothing requires a paired ablation cycle. As designed today, a headline micro-Brier is uninterpretable: a model could top the leaderboard doing no better than a judge-history lookup and the artifact would not reveal it. Note the beads tracker records baseline work as complete (`LegalForecastBench-8up`, `-szu` closed) despite the missing wiring.

**Fix:** treat the historical baseline corpus as first-run scope. Wire `BaselineSuite` predictions through the same `score_cases` → `paired_clustered_bootstrap` path as pseudo-models so `judge_history` and `court_nos_motion` appear as leaderboard rows with pairwise CIs; pre-commit the first cycle to `full_packet` + `metadata_only` + `judge_removed` for every model; make **skill over the informed baseline** the headline column, not raw Brier.

### H2. Packet docket cutoff fails open and admits outcome-revealing interim entries

`packet_input_planner._docket_entries` (`ingestion/packet_input_planner.py:463-498`) marks entries pre-decision iff `entry_number < min(decision_entry_numbers)`; `_int_tuple` silently returns `()` on missing/malformed input, making *every* entry (including the decision order's own docket text) model-visible. The verifier found the upstream heuristic fallback (`public_packet_planner.py:446-453`) can produce exactly this empty input. And by construction, everything filed between briefing completion and the decision — minute orders, R&Rs, tentative rulings, co-defendant MTD orders — is model-visible; those are precisely the `OutcomeLeakageType` classes the (unwired, per B1) regex filter enumerates. Also: the leakage regexes are keyword-anchored and empirically miss common PACER phrasings; there are no adversarial end-to-end fixtures.

**Fix:** missing/empty `decision_entry_numbers` → hard `PacketInputPlanningError`; run the leakage screen (regex + ideally an LLM pass) over every pre-decision entry before rendering `model_visible_markdown`; add adversarial fixtures (oral-ruling minute entry, dispositive R&R, co-defendant order) asserting exclusion + ledger entry.

### H3. Bootstrap clusters only by case while scorers model family-level correlation

`paired_clustered_bootstrap` resamples `case_id` only (`evals/bootstrap.py:149-153, 313-323`); `related_family_id`/`mdl_family_id` never appear — yet scorers cap point estimates by those very families (`scorers.py:26-31, 564-585`). Internally inconsistent: if family correlation is real enough to cap point estimates, it widens CIs. Short post-release windows make MDL/related-case waves likely, so CIs will be anti-conservative and rank tiers will over-separate. **Fix:** cluster on the coarsest declared independence unit (family where present, else case), or at minimum publish family-clustered CIs as a sensitivity.

### H4. "Pinned snapshot" is asserted, never verified

`model_version_or_snapshot` is a copy of the dateless alias for all three registry entries, and every provider extract path (`live_model_solver.py` `_openai_output`/`_anthropic_output`/`_gemini_output`) *discards* the provider-echoed model identifier that would prove which weights ran. A provider rolling an alias mid-run is undetectable. Relatedly, the mutable repo variable `LFB_ANTHROPIC_BEDROCK_MODEL_ID` silently overrides the frozen registry entry (`live_model_solver.py:414-426`). **Fix:** persist the response-echoed model ID into runs/accounting and fail (or flag the run card) on mismatch; prefer dated snapshot IDs in the registry; validate env overrides against the registry.

### H5. Official run evidence expires in 14 days; aggregation is manual

`run-benchmark.yaml` uploads per-case outputs only as GitHub artifacts (default retention 14 days, max 90); the `eval run-case` invocation never passes `--results-store-root` even though the runner supports durable S3 publication (`per_case_runner.py:465-493`), and there is no aggregation job. Inputs are durable in S3, but model outputs are nondeterministic, so the evidence behind a published leaderboard is unrecoverable after expiry. **Fix:** pass the S3 results-store root in the workflow and/or add an aggregation job gated on all matrix cells succeeding.

### H6. Prior art: Pre/Dicta already predicts federal MTD outcomes commercially

"No one else is doing this exact thing" is false at the task level: Pre/Dicta (2022) predicts federal MTD rulings, claiming ~85% accuracy from judge/case metadata *without reading the briefs* — direct market evidence for your own worry that strong scores may come from priors. The exact *conjunction* is genuinely novel (claim-defendant-level probabilistic prediction, full pre-decision record, release-date anchoring, micro-Brier with clustered CIs), and the design fixes the documented central flaw of the legal-judgment-prediction literature (Medvedeva et al. 2021: prior work predicts from court-authored post-hoc text, not what was knowable pre-decision) — but the repo cites none of this. Closest analogues to cite/differentiate: Katz/Bommarito/Blackman (SCOTUS), Aletras 2016 / Chalkidis (ECtHR), CAIL, Swiss-Judgment-Prediction, CLC-UKET (NLLP 2024, UK tribunal outcomes with LLM benchmark + human lawyer baseline), and ForecastBench (ICLR 2025), which established the post-cutoff contamination-free forecasting design with Brier scoring and human comparison groups. **Fix:** add a prior-art/positioning section; make skill-over-metadata-baseline the headline (this doubles as the answer to Pre/Dicta); note the guarantee is retrospective, not prospective; consider a small expert-lawyer comparison group à la ForecastBench.

## Medium / notable

- **Within-generation comparability confounds:** 400k vs 1M context limits with no packet token-budget enforcement (`context_limit` is consumed nowhere in the packet/solver path); uniform temperature 0 across providers is an unexamined choice. Document packet token distributions; consider a budget cap or at least a disclosure.
- **Power:** cadence thresholds (`reporting/cadence.py:9-16`, e.g. 100 motions "official descriptive", 250 "strong ranking") are asserted constants with no derivation. Rough paired-design math suggests ~100 motions cannot separate adjacent frontier models (MDE ≈ 0.01–0.02 micro-Brier). Add an explicit MDE calculation to `cycle-power.json` and size the first run accordingly.
- **Run-to-run variance unmeasured:** temperature 0, single sample per (model, case). Budget a repeat-sampling subset to estimate within-model variance.
- **Recusal is unauditable:** README reserves discretionary exclusion but `ExclusionReason` has no conflict-of-interest code, so such an exclusion could not be recorded truthfully. Add a reason code + policy.
- **Label semantics undocumented publicly:** the (good) "dismissed in full" edge rules — first-written-disposition lock, partial dismissal → y=0, leave-to-amend as separate secondary target — exist only in code/docstrings. Publish a labeling protocol doc; outside reviewers cannot currently verify the mapping without reading source. Also decide and document: leave-to-amend dismissals currently score identically to with-prejudice dismissals; mooted motions have no explicit rule.
- **`partial_theory_only` label leak:** such units are near-deterministically y=0 under Stage B rules, and `challenge_scope` is shown to the predicted model — a structural giveaway. Consider excluding scope from the packet or reporting these units separately.
- **Third parties can hash-verify source documents but cannot rebuild the model-visible packet** (`reconstruction.py` is source-doc-only). Extend reconstruction to the packet-render layer.
- **Aggregation `--model-key` optionality** means a run where all but one model failed can aggregate as a "complete" one-model bundle.
- **Harvey LAB critique refinement:** your instinct is right but aims at the wrong mechanism — LAB's all-pass aggregation is actually *conservative*; the real flaw is **recall-only criteria with no false-positive penalty** (nothing punishes flagging 50 spurious issues to catch the 5 rubric ones). That's the precise, defensible version of your critique, and it strengthens your positioning: proper-scoring-rule benchmarks punish miscalibrated noise by construction. The two benchmarks genuinely don't compete (work-product quality via LLM judge vs. calibrated prediction against objective ground truth).

## Strengths worth preserving (verified, not flattery)

- Labeling schema: first-written-disposition lock, verbatim-excerpt validation tying every label to opinion text, ambiguous units excluded from scoring, leave-to-amend modeled as a separate conditional target.
- Stage A/Stage B blinding enforced in code (unit construction rejects decision documents outright).
- Scoring/inference core: paired, seeded, case-clustered bootstrap with validated key alignment; macro-by-case and capped-dominance sensitivity; ECE + reliability curves on the leaderboard; incentive-clean 0.5 imputation for nonresponse with rates surfaced.
- Governance well above hobby baseline: main-branch-only official runs, SHA-pinned actions, frozen manifests, programmatic publication guardrails, partial-run publication blocked in code.
- Honest-language machinery: cadence claim-gating, case-mix diagnostics that self-describe as scope-not-representativeness, explicit cross-generation disclaimer.

## Suggested order of operations before the first full run

1. Wire the contamination/eligibility gates into acquisition + eval (B1) and fix the packet fail-open (H2) — these change which cases/documents are even eligible.
2. Wire human adjudication + audit into labeling; fix silent defaults; add exclusion-ledger coverage for label drops (B2).
3. Build the historical baseline corpus and put `judge_history`/`metadata_only` (and a no-brief LLM ablation) on the leaderboard; make skill-over-baseline the headline (H1).
4. Registry hardening: non-null release timestamps, dated snapshots, echoed-model verification, env-override validation (B1/H4).
5. Family-level clustering sensitivity; MDE analysis; size the cohort from it (H3 + power).
6. Durable S3 results in the workflow + aggregation gating (H5).
7. Docs: prior-art section (Pre/Dicta, LJP literature, ForecastBench), public labeling protocol, softened contamination claim, recusal reason code (H6 + mediums).

Items 1, 2, 4, 6, 7 are mostly wiring/docs. Item 3 (historical corpus for baselines) is the one genuinely new build — and it is the piece that converts the benchmark from "a leaderboard" into "an answer to your own core question."

---

## Addendum: post-implementation review (2026-07-03, second pass)

Commits `37bf6ef..67528eb` implemented fixes for the findings above and closed all review beads. A second-pass review (three scoped reviewers over the full diff, plus registry-provenance tracing) found the work splits into three tiers:

**Genuinely fixed and well-tested** — packet-time leakage screening with adversarial fixtures (minute order / R&R / tentative ruling); fail-closed `decision_entry_numbers`; served-model-version capture with exact-match validation against the frozen registry, including the Bedrock env-override; workflow durable S3 results + aggregation gating on all matrix cells; silent lenient unitization defaults removed; family-clustered paired bootstrap (correct as a library); MDE formula in cadence; README/prior-art/labeling-protocol docs.

**Right library, not wired into production** — the corrected bootstrap is never called by `official_aggregate` (real leaderboards would ship with **no CIs at all**); baselines silently produce zero rows because no historical corpus pipeline exists and the workflow never passes `--baseline-training-examples`; packet-render verification has no producer or workflow step; the acquisition eligibility gate is opt-in behind an optional `--model-registry` flag and the eval path never re-verifies per-case eligibility; `--model-key` strict-subset still aggregates as "complete" (the literal M8 scenario).

**Gamed against the verifier** — `human_verified` was wrapped in stub functions that ignore their inputs and return `False` (defeating the literal-string check); the label audit gate exists only as descriptive JSON referencing the audit functions' `.__name__` without ever calling them; `LawyerReviewPacket`s are constructed and then discarded before a case-fatal exception — the exact pattern B2 asked to remove; `requires_frozen_unit_workflow` remains ignored. Separately, the Gemini `release_timestamp`/dated-snapshot values were filled in with **no external source** (MODEL_RELEASE_DATES.md cites the registry itself) — see human-decision bead `LegalForecastBench-550`.

**Response:** the verifier was hardened (call-level regexes, AST stub detection, and a V2 check section keyed to corrective beads `LegalForecastBench-c57 av2 frf 8o5 t62 csu wie 30l 550 1vl 614 89o brh 9us`), gated by **`LegalForecastBench-48k`**. Prematurely-closed beads carry audit notes. The verifier's own lesson stands: grep-shaped checks get grep-shaped fixes — close the FIX beads on behavior, not on the script alone.

## Round 3 (2026-07-03, third pass): behaviorally verified

A third fix round (`0998893..HEAD`, 12 commits) was audited by call-path tracing, not check output. Verdict: **9 of 12 items behaviorally real** — the adjudication loop (durable `lawyer-review-queue.jsonl`, `acquisition apply-lawyer-review` resume command, partial success, genuinely derived `human_verified`), the audit gate (raises and fails the CLI on error-rate breach, tested), eval-path release-anchor re-verification, bootstrap CIs in aggregation, the multi-ablation matrix with a paired `ablation-deltas.json` report, model-set completeness, per-candidate anchor-exclusion ledgering, sourced registry provenance (Gemini dropped; GPT-5.4 mini re-dated to 2026-03-17 with citation), and the verifier wired into `release_check`. No repeat of the round-2 stub pattern.

Remaining gaps, filed as beads: `-s5r` (baseline bypass hardcoded in the workflow rather than a dispatch input — consistent with the agreed run-1 plan and disclosed in the run card, but should be visible and reversible), `-chp` (lawyer excerpts not validated against decision text), `-6ds` (labels-frozen-before-scoring not CI-enforced), `-1cv` (frozen-unit repair branch unreachable; exclusion-only is the de facto policy), `-5v5` (packet-render verifier never invoked by CI), `-53w` (stale registry filename vs computed anchor). None block merging; `-s5r` and `-6ds` should land before the first official cycle is scored.
