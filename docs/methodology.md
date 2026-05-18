# Methodology Frame

LegalForecast-MTD v1.0 is the intended benchmark target. The current public
release state is v0.1 alpha: the offline fixture harness works, but no canonical
live leaderboard exists and no official cycle should begin until live packet
acquisition is proven.

The benchmark is for calibrated prediction of federal motion-to-dismiss
outcomes. Its purpose is relative model comparison on a defined public-record
forecasting task, not estimation of the representative distribution of outcomes
across all federal motions to dismiss.

The benchmark asks each model to predict, from the same pre-decision litigation
record, the probability that each challenged claim will be dismissed in full as
to each challenged defendant or defendant group. The target unit is a
claim-defendant prediction unit, not the motion as a whole and not every
separate legal theory inside a claim.

The headline metric is micro-Brier over prediction units. Model comparisons and
confidence intervals must account for within-motion correlation, so inference is
clustered by case or motion. Macro-Brier, capped case contribution metrics, and
related-case-family sensitivities are required robustness views, not substitutes
for the primary score.

## Scope

The benchmark is intentionally MTD-only for v1.0. Motions to dismiss are a
practical first domain because the relevant record is usually smaller than on
summary judgment, the legal target is clearer than on appeal, and claim-level
survival is operationally meaningful to litigators and clients.

The benchmark does not claim that its cases are a representative sample of all
federal MTDs. Public docket availability, case.dev or RECAP coverage, decision
windows, district mix, represented-party mix, and case-type mix are all scope
constraints. They matter for describing what the benchmark covers. They become
design defects only when they plausibly distort the relative ranking of models
on the intended task.

Every official report should therefore state:

- the case source and discovery process;
- the decision window and release anchor;
- the distribution of districts, courts, NOS categories, party types, and unit
  counts;
- any dominance by one case, court, case family, or subject-matter category;
- which claims are descriptive, provisional, official, or strong ranking claims.

## Acquisition Status

Live packet acquisition remains the blocker for official evaluation. Case.dev is
the primary discovery layer, but the current public release should not describe
case.dev as the complete packet source unless docket-entry and source-document
retrieval become available. The operator commands, no-paid defaults, fallback
path, and readiness gates live in `docs/acquisition.md`; this methodology keeps
only the design consequence: no official cycle should begin until acquisition
can produce clean pre-decision packets with measured linkage, leakage,
review-time, case-mix, and cost outputs.

## Validity Standard

The governing question for methodological objections is not whether some bias or
selection artifact exists. Feasible public-record legal benchmarks will always
have selection artifacts. The governing question is whether the issue plausibly
changes model rankings, changes the skill being measured, leaks the answer, or
makes the benchmark too noisy to distinguish models.

| Question | Treatment if yes | Treatment if no |
| --- | --- | --- |
| Does the issue create outcome leakage? | Serious; exclude or fix before scoring. | Treat as scope/context. |
| Does it create model-specific contamination? | Serious; diagnose, stratify, or sensitivity-test. | Treat as scope/context. |
| Does it reduce power enough that model deltas are not interpretable? | Serious; adjust sample size, cadence, or claims. | Treat as scope/context. |
| Does it make the benchmark measure a different skill than intended? | Serious; narrow, stratify, or redesign that component. | Treat as scope/context. |
| Does it allow one case, case family, court, or subject area to dominate? | Serious if rankings change; cap or report sensitivity. | Treat as scope/context. |
| Does it merely limit representativeness of the federal docket? | Disclose as an external-validity limit. | Not a design problem. |
| Is the proposed cure unrealistic for a rolling benchmark? | Do not adopt it unless the issue is validity-critical. | Consider adopting it. |

This standard should guide implementation decisions. The project should spend
engineering effort first on leakage, contamination, label reliability,
unitization stability, power, dominance controls, and cost/cadence feasibility.
It should not overfit the design to abstract objections about representativeness
unless those objections plausibly affect relative model comparison.

## Legitimate Signal vs. Leakage

The core eligibility anchor is the decision date. For a model-release series,
eligible cases are written MTD decisions entered after the series release date.

The case, complaint, motion, briefing, docket history, judge identity, parties,
counsel, and public procedural context may have existed before the model release
or before a provider's stated training cutoff. That fact alone does not make the
case contaminated. Those materials are legitimate public pre-decision signal
when the benchmark provides the same packet to every model and the outcome was
not known from the supplied materials.

The serious contamination question is narrower: whether a model has asymmetric
access to the target outcome or materially identical target materials in a way
that another model does not. The benchmark should record cutoff metadata and
run sensitivity strata, but it should not gate the headline sample on filing
date or briefing-completion date.

Recommended metadata fields include:

```json
{
  "case_filed_after_model_cutoff": true,
  "motion_filed_after_model_cutoff": false,
  "briefing_completed_after_model_cutoff": false,
  "decision_entered_after_model_release": true,
  "publicity_or_related_case_risk": "none_detected",
  "press_publicity_tags": []
}
```

Outcome leakage is different and must be hard-excluded. Examples include
pre-run access to a minute order granting or denying the target motion, an oral
ruling transcript, an R&R that already resolves the target motion, a related-case
order resolving the same issue, a docket entry that reveals the disposition, or
public reporting that reveals the target result before evaluation.

Non-leaking publicity is not a hard exclusion. Cases with high news volume,
Wikipedia coverage, major public-company parties, major mass-tort or MDL
attention, or constitutional or political salience should remain eligible unless
they reveal the target outcome. They should be tagged in candidate manifests and
reported as pre-specified sensitivity slices.

## Priority Risks

### Outcome Leakage

Leakage destroys the benchmark because the task becomes answer retrieval rather
than legal forecasting. Leakage checks should be hard gates in candidate
selection, packet construction, docket tools, model sandboxing, and publication.

### Model-Specific Contamination

The benchmark cannot fully prove what every provider trained on, but it can
reduce and diagnose the risk. It should record model release dates, known
training cutoffs where available, evaluation timestamps, packet hashes, and
post-cutoff sensitivity strata. If results materially change on stricter
post-cutoff subsets, reports should say so directly.

### Unitization Stability

Prediction units must be defined before outcome labeling and without reading the
decision. A motion should not be decomposed opportunistically after seeing the
order. Unit schemas must support grouped defendants, claim-level units,
uncertainty flags, source citations, and a frozen repair-or-exclude workflow.

### Label Reliability

The label pipeline must be reliable enough that observed model deltas are not
overwhelmed by label noise. Ambiguous decisions, missing units, unclear partial
grants, leave-to-amend questions, and multi-defendant rulings should route to
review or exclusion according to documented rules. LLM-assisted labels should be
audited against human disagreement rather than assumed correct.

### Dominance and Case Mix

Micro-Brier is the headline because the operational prediction is at the legal
exposure-unit level. But one sprawling case, related family, MDL pattern, court,
or subject-matter bucket should not silently drive rankings. Reports must show
case-mix diagnostics and robustness scores with capped case and related-family
contributions when applicable.

### Power and Cadence

The benchmark should distinguish pilot, rapid, official descriptive, strong
ranking, and aggregate claims. A small run can be useful for feasibility and
debugging, but it should not be described as strong evidence of model ordering
unless the motion count and clustered uncertainty support that claim.

### Cost and Operational Feasibility

Cost, latency, invalid outputs, refusals, and tool use are part of the product
being evaluated. A benchmark that cannot be rerun at tolerable cost will not
remain useful. Reports should therefore include cost per case, cost per unit,
tool-call distributions, invalid-output rates, refusal rates, and run-time
metadata alongside accuracy metrics.

case.dev discovery costs, CourtListener web-scrape counts, case.dev live PACER
fees, direct PACER document purchases, and model/API costs must remain separate.
When clean packets are zero, cost per clean packet is undefined; reports should
say so directly rather than imputing packet economics from search requests.

## Treatment of Common Criticisms

Pre-release briefing is not itself a defect. The benchmark predicts decisions
entered after the relevant release anchor using pre-decision public materials.
Those materials are legitimate forecasting inputs unless they contain the
outcome or create model-specific memorization risk.

case.dev, CourtListener, RECAP, and PACER coverage limitations are primarily
external-validity constraints. The practical response is to measure the
available case mix, report the distribution, run targeted live feasibility
tests, and add fallback retrieval only where the empirical pilot shows it is
needed. Fallback use is summarized in `docs/acquisition.md`: case.dev remains
the discovery layer when it found the candidate, supplemental sources are
recorded per document, and leakage, sealed material, and unresolved linkage
ambiguity remain exclusions rather than fallback problems.

The current Phase 0 evidence shows a structural retrieval gap, not a query-term
or credential problem. Search-hit distributions should not be used as retained
packet case-mix diagnostics. District, NOS, judge, document-completeness, unit,
and dominance tables belong to retained or reviewed packets only.

Decision-window artifacts are also primarily scope constraints. A 28-day or
other fixed window should be reported as the decision stream for that period,
not as the federal docket. The concern becomes serious only if the window
produces a case mix or difficulty profile that plausibly changes relative model
rankings. Rapid runs should be labeled provisional, and stronger claims should
come from larger official or rolling aggregates.

Brief quality and docket context are legitimate signal. The benchmark is not
trying to remove all human-lawyer signal from the record. It is asking whether a
model can use the same public pre-decision record to forecast what the court
will do.

## Reporting Commitments

Official reports should avoid population language such as "models predict
federal MTD outcomes at X percent accuracy" unless the claim is clearly limited
to the benchmark sample. Preferred wording is:

> On the LegalForecast-MTD v1.0 public-record benchmark sample, model A achieved
> a lower micro-Brier score than model B, with clustered uncertainty and
> required robustness checks reported below.

Reports should also identify:

- the exact model registry and run parameters;
- the frozen manifest, unit, label, prompt, scorer, and harness hashes;
- the exclusion ledger and dominant exclusion reasons;
- the case-mix diagnostics and dominance sensitivities;
- contamination/cutoff sensitivity results, including press-publicity tagged
  slices;
- cost, latency, invalid-output, refusal, and tool-use metrics;
- whether the run supports pilot, descriptive, strong ranking, or aggregate
  claims.

## Result tiers

Publication should follow `docs/result_tiers.md`. This methodology treats result
claims as part of the validity design; the tier policy owns the detailed rules
for official, verified-community, community-unverified, and alpha-non-canonical
outputs. Reports must not mix community-unverified rows into the canonical
leaderboard or use them as evidence for benchmark claims.
