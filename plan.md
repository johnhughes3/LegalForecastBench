# LegalForecast-MTD v1.0 implementation plan

I would now design v1.0 as:

> **LegalForecast-MTD v1.0: a rolling, contamination-resistant benchmark for calibrated prediction of claim-level outcomes on federal motions to dismiss.**

The headline task should be:

> Given pre-decision docket materials for a federal MTD, predict, for each challenged claim × defendant or defendant group, the probability that the court will dismiss that claim in its entirety as to that defendant/group.

The primary score should be **micro-Brier**, with **clustered inference by case/motion**. Macro-Brier should be reported as a robustness metric, not the headline.

That combination gives you the right operational target while still handling within-motion correlation correctly.

## Current project setup alignment

This repository is `LegalForecastBench`. The Python distribution should be
`legalforecast-mtd`, and the import package should be `legalforecast`. The plan
below should be read as the implementation target for that repo layout, not as a
separate `legalforecast_mtd` project.

Operational project conventions:

- use `bd` / Beads as the task graph and coordination layer;
- use `uv` and `pyproject.toml` for Python environment management;
- keep executable behavior behind `legalforecast` CLI commands as they are
  added;
- keep durable methodology and public-facing docs under `docs/`;
- keep frozen cycle protocols under `protocols/`;
- keep manifest and hash artifacts under `manifests/`;
- use reusable fixtures under `tests/fixtures/`;
- preserve offline tests by default, with live case.dev tests explicitly gated
  by credentials.

`plan.md` is the full design plan. The shorter files in `docs/` should become
the operational/public documentation extracted from this plan.

## Methodological frame

This benchmark is designed for **relative model comparison on a defined public-record forecasting task**, not for estimating the representative distribution of outcomes across all federal motions to dismiss. Selection artifacts from public docket availability, decision-date windows, and case.dev docket/document availability are treated as external-validity limitations unless they plausibly affect relative model rankings. The design therefore prioritizes controls for outcome leakage, model-specific contamination, label reliability, unitization stability, sample power, and dominance by repeated or mega-case patterns. Case-mix diagnostics define the benchmark's scope and support sensitivity analyses; they are not used to claim population representativeness.

The decision rule for criticisms should be:

| Question                                                                | If yes                              | If no                    |
| ----------------------------------------------------------------------- | ----------------------------------- | ------------------------ |
| Does the issue create outcome leakage?                                  | Serious; fix or exclude.            | Treat as scope/context.  |
| Does it create model-specific contamination?                            | Serious; diagnose/sensitivity-test. | Treat as scope/context.  |
| Does it reduce power to distinguish models?                             | Serious; adjust sample/cadence.     | Treat as scope/context.  |
| Does it make the benchmark measure a different skill than intended?     | Serious; narrow or stratify.        | Treat as scope/context.  |
| Does it merely limit representativeness of the federal docket?          | Scope note.                         | Not a design problem.    |
| Is the proposed fix operationally unrealistic for a rolling benchmark?  | Do not adopt it.                    | Consider adopting it.    |

------

# 1. Micro-Brier vs. macro-Brier

I agree with the critique you pasted. I would flip my earlier recommendation: **micro-Brier should be the headline.**

This is not because micro is “more statistically correct.” It is because it answers the more relevant question.

## The estimand

Let prediction unit (u) be a claim × defendant/group pair. Let (p_u) be the model’s predicted probability of full dismissal, and (y_u \in {0,1}) the actual outcome.

**Micro-Brier:**

[
\text{MicroBrier} = \frac{1}{N} \sum_{u=1}^{N} (p_u - y_u)^2
]

This answers:

> How good is the model’s average probabilistic prediction for a challenged legal claim against a defendant?

That is the right headline for a Holmesian legal-prediction benchmark.

**Macro-Brier:**

[
\text{MacroBrier} = \frac{1}{M} \sum_{m=1}^{M} \left(\frac{1}{N_m} \sum_{u \in m} (p_u - y_u)^2\right)
]

This answers:

> How good is the model’s average performance per motion, giving a one-unit motion and a twelve-unit motion equal weight?

That is useful, but it is a secondary view.

## Why micro should headline

A complex MTD with eight challenged claim-defendant units is not noise. It represents eight operational legal predictions. In practice, a client does not ask, “What is the motion-level average?” The client asks whether the Section 10(b) claim survives, whether the Section 20(a) claim survives, whether the unjust-enrichment claim survives, and so on.

So the benchmark’s main unit should be the **legal exposure unit**, not the docket event.

The right fix for correlation is not to demote micro-Brier. The right fix is:

> headline micro-Brier, but confidence intervals and model comparisons clustered by case/motion.

So the official scorecard should say:

```text
Primary score: micro-Brier over claim×defendant units.
Inference: paired clustered bootstrap by motion/case.
Required robustness: macro-Brier by motion, capped per-case micro-Brier,
and related-case-family capped sensitivity where applicable.
```

## One caution

Micro-Brier can be distorted if one mega-case creates 80 prediction units. The solution is not macro-Brier as headline; it is disciplined unit construction.

Use these anti-inflation rules:

1. Group defendants where the motion treats them identically.
2. Group claims only where they are legally identical for prediction purposes.
3. Exclude omnibus MDL orders only when clean unitization is impossible.
4. Report a mandatory sensitivity metric with a per-case cap or winsorized case contribution.
5. Report macro-Brier alongside micro-Brier.
6. Treat related cases, coordinated actions, and MDL families as case families for sensitivity caps when the same legal pattern repeats.

So the headline remains micro, but no reviewer can fairly say the leaderboard was driven by one sprawling complaint.

------

# 2. Core v1.0 scope

I would make v1.0 **MTD-only**.

Do not include MSJs or appeals in the first release. MSJs introduce factual-record complexity, evidence admissibility issues, deposition exhibits, sealed materials, and sprawling factual disputes. Appeals introduce base-rate affirmance problems and a different document ecosystem.

MTDs are the cleanest first target because:

- the operative record is smaller;
- the legal target is clearer;
- motions are common;
- the task is close to what litigators actually forecast;
- claim-level survival is operationally meaningful;
- the docket materials are often public and self-contained.

## Official v1.0 task

```text
Task: Federal district court motion-to-dismiss prediction.

Input: pre-decision docket materials, case metadata, complaint, motion papers, and controlled docket access.

Prediction unit: challenged claim × challenged defendant or defendant group.

Primary target: whether the claim is fully dismissed as to that defendant/group.

Prediction format: calibrated probability from 0 to 1.

Primary metric: micro-Brier.

Inference: paired clustered bootstrap by motion/case.
```

------

# 3. Outcome schema

## Primary binary target

For each unit:

```text
Will the court dismiss this claim in its entirety as to this defendant or defendant group?
```

Label as `1` if the claim is fully dismissed as to that defendant/group.

Label as `0` if the claim survives in any material respect.

Examples:

| Ruling                                                       | Label                    |
| ------------------------------------------------------------ | ------------------------ |
| Claim dismissed entirely against Defendant A                 | 1                        |
| Claim survives entirely against Defendant A                  | 0                        |
| Some statements/theories dismissed, but claim survives       | 0                        |
| Claim dismissed against officers but survives against issuer | issuer = 0; officers = 1 |
| Claim dismissed as to Defendant A but not Defendant B        | A = 1; B = 0             |
| Court says only “motion granted in part” and unit cannot be resolved | exclude/ambiguous        |

This is clean, objective, and legally useful.

## Secondary leave-to-amend track

I agree with the smaller refinement: capture leave-to-amend labels from day one, but do **not** make them headline.

Use a three-class secondary label:

```text
0 = not fully dismissed
1 = fully dismissed with express amendment opportunity
2 = fully dismissed without express amendment opportunity
```

But for scoring, I would split this into two things:

1. **Primary binary dismissal score** over all units.
2. **Conditional amendment-opportunity score** only over units that were fully dismissed.

The conditional target should be:

> Among fully dismissed units, did the decision expressly grant leave to amend, set a deadline to amend, or expressly invite a motion/request for leave to amend?

Do not treat silence, ordinary Rule 15 background law, or later procedural developments as an amendment invitation.

This secondary label will be valuable, but it is inherently noisier than dismissal.

## Reconsideration and later amendments

Lock ground truth at the **first written disposition** resolving the MTD.

Later Rule 59, Rule 60, reconsideration, amendment, reinstatement, or appellate reversal should be tagged but should not change the primary label. Otherwise the target becomes unstable.

------

# 4. Eligibility and contamination

Your contamination standard should distinguish **public pre-decision signal** from **outcome leakage**.

## Eligibility anchor

For a model-release series:

```text
Eligible decisions are written MTD decisions entered after the series release date.
```

That is the core contamination rule.

You do **not** need to require the case to have been filed after the model’s knowledge cutoff. That would unnecessarily shrink the sample and is conceptually overstrict. If the complaint, briefs, judge, parties, or docket history existed before release, those are legitimate public forecasting inputs, and you are giving the same inputs to every model.

## Preferred but not required

Track whether the following occurred after the model’s stated knowledge cutoff:

- case filed;
- complaint filed;
- MTD filed;
- opposition filed;
- reply filed;
- motion fully submitted.

Use these as contamination diagnostics and sensitivity strata, not hard gates.

I would include a metadata field:

```json
{
  "filed_after_cutoff": true,
  "motion_after_cutoff": false,
  "briefing_completed_after_cutoff": false,
  "decision_after_release": true
}
```

Then report:

```text
Main result: all eligible post-release decisions.
Sensitivity: cases filed after cutoff.
Sensitivity: briefing completed after cutoff.
```

The existence of pre-release briefing is not itself a defect. Public pre-decision materials are legitimate forecasting signal when each model receives the same packet. The serious contamination question is narrower: whether a model has an asymmetric memorization or outcome-leakage advantage on the target materials.

For every evaluated model, record:

```json
{
  "model_name": "example-model",
  "provider": "example-provider",
  "model_version_or_snapshot": "2026-05-14",
  "evaluation_timestamp": "2026-05-14T12:00:00Z",
  "network_disabled": true,
  "search_disabled": true,
  "provider_training_cutoff_if_known": "2026-04-01",
  "post_cutoff_sensitivity_available": true
}
```

If a provider cannot identify a training cutoff or stable snapshot, that should be disclosed. It should not automatically exclude the model unless there is evidence of target leakage.

## Exclude outcome leakage

Exclude cases where pre-run materials disclose or practically reveal the target outcome.

Examples:

- minute order already granting or denying the motion;
- oral ruling transcript announcing result;
- R&R already resolving the motion, if the target is later adoption;
- tentative ruling;
- written questions that reveal the intended disposition;
- related-case order that resolves the same claim-defendant units in a materially identical case;
- public news coverage reporting the disposition before benchmark execution.

But do not exclude ordinary legal developments. If the court of appeals decided a relevant legal issue before the district-court ruling, that is not contamination. That is law, and a real lawyer would use it.

------

# 5. Cadence: rapid usefulness without bad sampling incentives

I partly agree and partly disagree with the critique about N-threshold cadence.

The critique is strongest if the benchmark selects motions **filed after release** and then closes when the first 150 are decided. That would overrepresent fast-deciding judges and easy motions.

But your proposed design is different: select **decisions issued after release**. In that setting, the first 150 clean decisions are not necessarily fast-disposition cases. They are simply the first 150 decisions in the post-release stream. There can still be temporal, court, holiday, ingestion, and docket-availability artifacts, but the “fast judge” bias is much weaker.

## Recommended cadence

Use both rapid and official windows.

### Rapid series

```text
Rapid Series = first 150 clean MTD decisions after model release, or first 14 days, whichever comes later.
```

Purpose:

- quick leaderboard;
- market/lab relevance;
- early signal;
- useful for “new model just dropped” comparisons.

Label it clearly:

```text
Rapid / provisional
```

### Official series

```text
Official Series = all eligible clean MTD decisions entered during the first 28 days after model release.
```

Minimum condition:

```text
Official descriptive if ≥100 clean motions and ≥400 prediction units.
Strong ranking cycle if ≥250 clean motions, preferably 300-500.
Otherwise preliminary and aggregated into the next official or annual window.
```

I would not use a rigid “150 or 30 days, whichever first” as the only official rule. The better structure is:

| Product              | Case rule                  | Purpose                         |
| -------------------- | -------------------------- | ------------------------------- |
| Rapid leaderboard    | first N clean decisions    | fast relative ranking           |
| Official leaderboard | fixed decision-date window | cleaner series comparison       |
| Rolling aggregate    | multiple windows           | higher power / trend estimation |

This gives you speed without pretending the rapid result is the final scientific estimate.

The annual aggregate should be the main vehicle for high-confidence model ranking. Early windows are useful and worth publishing, but they should not be oversold when motion-level power is thin.

------

# 6. Data source and ingestion architecture

Primary ingestion should use **case.dev** where available. CourtListener/RECAP may remain optional reference/fallback tooling, but it should not be a required dependency for v1 unless the project explicitly chooses that fallback path later. The practical reason is simple: case.dev should be easier to query and simpler to bill against for the benchmark's operational workflow. The methodological reason is also simple: coverage questions are empirical, not abstract. We should test whether case.dev can produce enough clean MTD packets before redesigning around hypothetical coverage problems.

CourtListener/RECAP remains useful as a reference and possible fallback because RECAP is the public archive of PACER-derived documents and dockets. But v1 should be **case.dev-first**. If case.dev search works but docket entries or source documents are unavailable, the default next step is a case.dev retrieval/export path, not making CourtListener a required operational dependency.

## Phase 0: case.dev feasibility test

Before building the full rolling benchmark, run a real-world case.dev pilot:

```text
Sample: 50-100 recent candidate federal MTD decisions.

Measure:
- candidate discovery yield;
- docket completeness;
- complaint availability;
- motion/opposition/reply availability;
- order/decision availability;
- OCR/text-extraction quality;
- motion-to-order linkage success;
- exclusion rate and exclusion reasons;
- average prediction units per motion;
- median lawyer review minutes per case;
- case.dev/API cost per candidate and per clean benchmark packet;
- district, circuit, and NOS macro-category mix.
```

Decision rule:

If case.dev yields enough clean MTD packets at acceptable cost, use it as the
primary ingestion layer for v1. If not, use case.dev as the discovery layer and
run a bounded public-record acquisition pilot:

```text
case.dev docket search -> CourtListener public docket page -> Firecrawl rawHtml
-> exclude dockets with more than one visible page -> docket-text AI screen for
recent MTD orders or decisions -> parse motion, memorandum, exhibit,
opposition, reply, and order rows -> rank by missing purchase count -> cheapest
150 eligible cases
```

The CourtListener step should use public HTML pages rather than a credentialed
CourtListener API dependency. Resolve the case.dev docket ID to the slugged
CourtListener docket URL, request raw HTML, and parse `#docket-entry-table`.
Stop at 500 CourtListener docket-page scrapes. Use case.dev live PACER fetch
only for an otherwise essential docket or document after explicit fee
acknowledgement; log PACER/service fees separately from case.dev discovery and
model/API costs.

## Pipeline stages

```text
0. Repository skeleton, tooling, fixtures, logging, and CLI placeholders
1. case.dev runtime configuration and secret handling
2. case.dev feasibility pilot design
3. Candidate discovery
4. Docket ingestion and filing retrieval
5. Source-document provenance and case-packet schema
6. Text extraction / OCR
7. Motion-to-order linkage
8. Prediction-unit construction
9. Outcome labeling
10. Human adjudication / audit
11. Model registry and run matrix
12. Protocol pre-registration
13. Manifest/unit/label/prompt/scorer freeze and hashes
14. Model evaluation
15. Scoring / leaderboard
16. Reporting, data card, and reconstruction artifacts
```

## Runtime configuration and live smoke tests

Live case.dev access should be explicit and safely skippable.

```text
CASE_DEV_API_KEY=<secret, never committed>
CASE_DEV_BASE_URL=<optional override>
CASE_DEV_LIVE_TESTS=1
```

Default tests should run offline against fixtures or recorded responses. Live
smoke tests should skip with a clear message when credentials are absent and
should log query strings, request counts, estimated billing-relevant usage,
candidate yield, clean-packet yield, and missing-document reasons.

The first live smoke test should search for MTD candidates using the
dismiss/dismissal and Rule 12 docket terms below, retrieve representative
dockets/documents, and write `docs/phase0_case_dev_smoke.md` or an equivalent
pilot artifact. The goal is to find out whether case.dev coverage is actually a
problem before adding more complicated fallback ingestion.

## Candidate discovery search terms

Because v1 accepts only motion-to-dismiss cases, candidate discovery should search docket-entry text broadly for `dismiss` / `dismissal` language and then filter aggressively for actual MTDs. The first pass should favor recall; the eligibility stage can remove false positives.

Positive docket-entry triggers:

```text
motion to dismiss
motions to dismiss
MTD
Rule 12
Fed. R. Civ. P. 12
12(b)(1)
12(b)(2)
12(b)(6)
12(c)
dismiss complaint
dismiss amended complaint
dismiss the complaint
dismissal of complaint
```

Decision/order linkage triggers:

```text
order granting motion to dismiss
order denying motion to dismiss
order granting in part and denying in part motion to dismiss
memorandum opinion and order
opinion and order
decision and order
dismissed with leave to amend
dismissed without prejudice
dismissed with prejudice
```

Common false positives to exclude unless linked to a qualifying MTD:

```text
notice of voluntary dismissal
stipulation of dismissal
voluntary dismissal
dismissal for failure to prosecute
clerk's judgment
administrative closure
motion to dismiss appeal
motion to dismiss counterclaim only, unless the counterclaim is the benchmark target
order of dismissal with no linked Rule 12-style motion
```

Eligibility should require an identifiable motion to dismiss and a written disposition resolving that motion. Generic dismissal language is a discovery signal, not enough by itself.

## Source-document provenance

Every retrieved source document and packet artifact should carry provenance
metadata. This is necessary for leakage control, reconstruction, redistribution,
and hash-based reproducibility.

At minimum, track:

```json
{
  "source_provider": "case.dev",
  "source_case_id": "provider-case-id",
  "source_document_id": "provider-document-id",
  "court": "S.D.N.Y.",
  "docket_number": "1:26-cv-00001",
  "docket_entry_number": 34,
  "document_role": "motion_to_dismiss_memorandum",
  "retrieved_at": "2026-05-14T12:00:00Z",
  "source_url_or_reference": "provider-reference",
  "sha256": "hex-hash",
  "is_predecision_material": true,
  "is_mounted_for_model": true,
  "availability_status": "available",
  "redaction_or_seal_status": "public"
}
```

Packets should be reconstructable from manifest records, source IDs, and hashes.
The packet builder should never need to infer provenance from filenames alone.

## Repository layout

```text
LegalForecastBench/
  pyproject.toml
  README.md
  docs/
    methodology.md
    data_card.md
    logging.md
    phase0_case_dev_pilot.md
    outcome_rules_appendix.md
    preregistration.md
    preregistration_template.md
    model_card_template.md
    ethics.md
  legalforecast/
    __init__.py
    cli.py
    py.typed
    ingestion/
      case_dev_client.py
      courtlistener_client.py
      recap_client.py
      docket_sync.py
    extraction/
      pdf_text.py
      ocr.py
      normalize_text.py
    selection/
      candidate_discovery.py
      eligibility.py
      contamination_filters.py
      exclusion_ledger.py
      case_mix_diagnostics.py
    protocol/
      preregistration.py
      freeze.py
    unitization/
      construct_units.py
      schemas.py
      adjudication.py
    labeling/
      label_outcomes.py
      ensemble.py
      lawyer_review.py
    evals/
      inspect_task.py
      tools.py
      scorers.py
      baselines.py
      bootstrap.py
    reporting/
      leaderboard.py
      calibration.py
      pareto.py
  manifests/
    README.md
    cycle_2026_05_rapid.jsonl
    cycle_2026_05_official.jsonl
  protocols/
    README.md
    cycle_template.preregistration.yaml
    cycle_2026_05_official.preregistration.yaml
  docker/
    docket_tool/
      README.md
      Dockerfile
      docker-compose.yaml
  scripts/
    README.md
  tests/
    README.md
    fixtures/
      README.md
      case_packet/
      manifests/
      protocols/
```

The initial scaffold can contain placeholders, but it should establish these
paths early so later beads can add behavior without reorganizing the project.

## Shared fixtures and structured logs

Create one reusable fixture corpus rather than ad hoc fixtures in each module.
It should include clean grants/denials, mixed dispositions, amended complaints,
multiple defendants, grouped defendants, ambiguous orders, false-positive
dismissal docket entries, related cases, OCR noise, malformed model outputs, and
minimal manifest/protocol examples.

Every pipeline stage should emit structured logs with fields such as:

```text
case_id
candidate_id
stage
source_provider
source_document_id
source_hash
decision
exclusion_reason
elapsed_ms
request_count
estimated_cost
```

This matters because the benchmark will be built by multiple agents and later
debugged from artifacts. A failed candidate should leave enough context to
understand whether the failure was discovery, retrieval, extraction, linkage,
unitization, labeling, freeze validation, model execution, or scoring.

## Exclusion ledger

Every excluded candidate gets one primary exclusion reason:

```json
{
  "candidate_id": "cand_2026_05_000481",
  "court": "S.D.N.Y.",
  "decision_date": "2026-05-18",
  "primary_exclusion": "unclean_motion_order_linkage",
  "secondary_exclusions": ["multiple_motions_resolved"],
  "notes": "Order resolved MTD and preliminary injunction issues together."
}
```

This matters. It turns selection bias from an accusation into an auditable design choice.

## Mandatory case-mix diagnostics

Do not try to "fix" all public-docket selection bias. Instead, measure the included benchmark and report what it is. For every cycle, publish diagnostics for:

- district and circuit;
- NOS code and NOS macro-category;
- represented-party status;
- government-party status;
- MDL flag;
- public-company flag, where reliably detectable;
- number of claims;
- number of defendants and defendant groups;
- prediction units per motion;
- document completeness;
- motion/opposition/reply availability;
- exclusion reason distribution;
- related-case or MDL-family concentration.

Use a pre-specified dominance rule:

```text
If any single district, NOS macro-category, related-case family, or MDL family
accounts for more than the pre-specified share of benchmark units, report a
sensitivity result excluding or capping that bucket.
```

The default should be transparency and sensitivity testing, not aggressive rebalancing. Rebalancing can create more complexity than it solves unless a single bucket dominates enough to plausibly distort relative model rankings.

------

# 7. Prediction-unit construction

This is one of the most important design decisions.

## Stage A: construct units without reading the decision

The unit-construction agents may read:

- complaint / amended complaint;
- MTD notice;
- memorandum in support;
- opposition;
- reply;
- docket entries before decision;
- case metadata.

They may **not** read the decision.

Their job is to produce:

```json
[
  {
    "unit_id": "count_1_section_10b_issuer",
    "count": "I",
    "claim_name": "Section 10(b) / Rule 10b-5",
    "defendant_group": "Issuer defendant",
    "challenged_by_motion": true,
    "challenge_scope": "entire claim",
    "unit_confidence": 0.93
  }
]
```

## Unitization rules

Use defendant groups when legally appropriate.

Examples:

- “Individual defendants” if motion treats all officers identically.
- “Underwriter defendants” if arguments are common.
- Separate individual defendants only when the motion or complaint makes distinct arguments.

Use claim-level units, not theory-level units.

If a Section 10(b) claim is challenged on falsity, scienter, loss causation, and standing, that is still one prediction unit unless the claim is asserted against different defendants or separable subclaims.

## Stage B: outcome labeling with decision access

The outcome-labeling agents read the final written decision and label each pre-defined unit.

```json
[
  {
    "unit_id": "count_1_section_10b_issuer",
    "fully_dismissed": true,
    "amendment_class": "dismissed_with_express_amendment_opportunity",
    "ambiguous": false,
    "label_confidence": 0.96,
    "supporting_excerpt": "short non-public-for-score excerpt or citation"
  }
]
```

The decision-reading agents should never create new prediction units except to flag:

```text
unit_missing_from_stage_a
```

Those go to human review under a frozen-unit rule.

## Frozen-unit rule

Prediction units are frozen before outcome labelers see the decision. If decision-stage review identifies a missing material unit, the case is not automatically repaired using decision knowledge. Instead, use one of two paths:

1. exclude the case or affected motion from the scored set; or
2. return the case to a separate blinded unitization adjudicator who receives only pre-decision materials.

Any repaired case must be flagged in the manifest:

```json
{
  "unitization_repaired": true,
  "repair_method": "blinded_predecision_adjudicator",
  "repair_reason": "material_unit_missing_from_stage_a"
}
```

Decision-informed unit creation should never enter the scored set without a blinded repair protocol. This is a real validity issue because unitization instability can change model scores.

## Outcome-rules appendix

Before launch, maintain a short `docs/outcome_rules_appendix.md` that defines how to handle recurring edge cases encountered in the pilot. At minimum, cover:

- Rule 12(b)(1), Rule 12(b)(2), Rule 12(b)(6), and Rule 12(c);
- arbitration or stay orders framed as dismissal motions;
- venue, transfer, forum non conveniens, and personal-jurisdiction dismissals;
- anti-SLAPP motions when bundled with Rule 12 arguments;
- reports and recommendations and later district-court adoptions;
- mixed MTD/MSJ orders;
- voluntary withdrawal or mootness;
- dismissal without prejudice;
- partial theory dismissal versus claim dismissal;
- generic "granted in part" orders;
- successive amended complaints;
- multiple motions resolved in one order.

The appendix should be written from actual pilot examples, not speculative taxonomy. The goal is stable unitization and labeling, not exhaustive civil-procedure coverage.

------

# 8. Label-quality methodology

I agree with the critique: an absolute 2–3% LLM-label error threshold may be too strict and possibly incoherent if senior lawyers cannot meet it.

Use a **human-relative threshold**, with an absolute safety backstop.

## Pilot human reliability study

Before accepting automated labels, run a pilot:

```text
Two senior litigators independently label 50–100 MTDs at the claim×defendant level.
```

Measure:

- raw disagreement rate;
- Cohen’s κ or Krippendorff’s α;
- disagreement by label type;
- disagreement by complexity stratum;
- adjudicated final label.

This establishes the human floor.

## LLM ensemble acceptance rule

Use three cheap labeling models.

For each unit:

- unanimous + high confidence → candidate auto-label;
- disagreement → lawyer adjudication;
- low confidence → lawyer adjudication;
- ambiguous → lawyer adjudication or exclusion.

Audit a stratified sample of unanimous labels.

Acceptance criterion:

```text
Unanimous LLM audited error rate must be no worse than blind senior-lawyer disagreement rate,
and must not exceed a pre-specified absolute ceiling.
```

I would set the ceiling around **8–10% for v1**, then tighten it if the pilot shows the task is cleaner.

Why include an absolute ceiling? Because if human disagreement is 18%, that means the schema is too ambiguous. You should not allow the LLM pipeline to inherit an unacceptably noisy target merely because humans also struggled.

So:

```text
Accept if:
LLM audited error ≤ human blind disagreement rate
AND LLM audited error ≤ 10%
```

If not, revise schema, add exclusion rules, or increase lawyer adjudication.

Publish:

```text
Human disagreement: X%
LLM unanimous audited error: Y%
Lawyer-adjudicated share: Z%
Excluded ambiguous units: W%
```

That is a very defensible labeling story.

------

# 9. Pre-registration and manifest locking

Add pre-registration. It is a cheap credibility upgrade and should be part of the code/documentation structure, not just a paper promise.

Use **OSF Registrations** or **AsPredicted** for the public timestamp. Keep a repo-local copy in:

```text
docs/preregistration.md
docs/preregistration_template.md
protocols/<cycle_id>.preregistration.yaml
```

The code should validate the preregistration metadata before official model evaluation. A small module such as `legalforecast/protocol/preregistration.py` should:

- validate required protocol fields;
- compute SHA-256 hashes for the manifest, prediction-unit file, label file, prompt, scorer, and harness version;
- validate the frozen model registry / run matrix for the cycle;
- record the OSF/AsPredicted registration identifier or URL once available;
- prevent an official evaluation run from starting if required hashes or protocol fields are missing.

## Model registry and run matrix

The model list should be a first-class artifact, not a free-text field in the
paper. Keep a registry or run-matrix file that records:

```json
{
  "provider": "example-provider",
  "model_id": "example-model",
  "display_name": "Example Model",
  "model_version_or_snapshot": "2026-05-14",
  "release_timestamp": "2026-05-14T09:00:00Z",
  "provider_training_cutoff_status": "known",
  "provider_training_cutoff": "2026-04-01",
  "temperature": 0,
  "top_p": 1,
  "max_output_tokens": 4096,
  "network_disabled": true,
  "search_disabled": true,
  "tool_policy": "controlled_docket_tool_only",
  "context_limit": 200000,
  "pricing_source": "provider-price-sheet-date",
  "input_token_price": 0.0,
  "output_token_price": 0.0
}
```

Preregistration, Inspect execution, cost logging, model cards, run cards, and
leaderboard reporting should all read from this same registry.

## What to pre-register

For each official cycle:

1. release date/time anchor;
2. decision-date window;
3. eligibility rules;
4. exclusion rules;
5. contamination filters;
6. unitization rules;
7. primary metric;
8. secondary metrics;
9. bootstrap method;
10. pairwise comparison plan;
11. model registry / run matrix and hash;
12. harness version;
13. prompt hash;
14. manifest hash;
15. prediction-unit hash;
16. label hash;
17. scorer hash;
18. baseline definitions;
19. case-mix diagnostic fields;
20. dominance/capping sensitivity rule;
21. OSF or AsPredicted registration identifier once available.

## Timing

The clean sequence is:

```text
Before official collection:
1. Pre-register eligibility rules, exclusion rules, unitization rules,
   contamination rules, metrics, bootstrap method, dominance/capping rule,
   and analysis plan.

Before model evaluation:
2. Freeze and hash candidate manifest.
3. Freeze and hash prediction units.
4. Freeze and hash outcome labels.
5. Freeze harness version, prompt, scorer, model registry, and baseline definitions.
6. Publish or timestamp the final hash bundle.
7. Run model evaluations.
8. Publish results.
```

You do not need to publish all labels before running models, but you should freeze them and hash them.

For rapid/provisional runs, use the same template but allow a lighter preregistration artifact:

```text
Required for rapid: release anchor, eligibility rule, exclusion rule,
manifest hash, unit hash, scorer hash, model registry, and
provisional-status label.
```

------

# 10. Harness recommendation

Use **Inspect AI** for the headline benchmark.

Inspect is built for frontier AI evaluations, including tasks that combine datasets, solvers, scorers, tools, and sandboxing; its scorer documentation specifically frames scorers as evaluating model outputs against dataset targets. ([Inspect](https://inspect.aisi.org.uk/))

## Why Inspect over vendor agents

Do not use Claude Code vs. Codex vs. Gemini CLI as the v1 headline. Those are productized agent systems, not just models. They differ in hidden scaffolds, system prompts, file-navigation defaults, planning behavior, and context management.

The headline should test:

```text
model + neutral legal-forecast harness
```

not:

```text
vendor agent product + hidden harness
```

Use vendor-native coding-agent harnesses as a later appendix or v2 track:

```text
Provider-native agent track: operational product comparison.
```

That could be interesting, but it should not be the scientific headline.

## Model packet

For each case, the model receives:

```text
1. Case caption
2. Court
3. judge
4. magistrate judge, if relevant
5. NOS code and NOS macro-category
6. parties and counsel
7. docket sheet up to pre-decision cutoff
8. prediction-unit enum
9. operative complaint
10. motion to dismiss papers
11. opposition
12. reply, if filed
13. controlled docket tool
```

I agree with the refinement: include subject-area/NOS macro-category explicitly. Do not force models to infer that from the complaint.

## Tooling

For v1 MTDs, keep tools minimal.

Primary tool:

```text
read_docket_entry(entry_number)
```

Optional tool:

```text
list_available_docket_entries()
```

Avoid broad search tools in v1 unless necessary. The point is legal prediction, not general file-system exploration.

Server-side enforcement:

- no network;
- no decision text mounted;
- no post-decision entries mounted;
- no outcome labels mounted;
- no leaked minute order / transcript / R&R if excluded;
- per-case allowed-entry list;
- fixed tool-call cap;
- full tool-call logging.

## File layout

```text
/case/
  metadata.json
  docket_predecision.md
  prediction_units.json
  filings/
    001_complaint.md
    034_motion_to_dismiss.md
    035_memorandum_in_support.md
    041_opposition.md
    044_reply.md
  allowed_entries/
    001.md
    034.md
    035.md
    041.md
    044.md
```

Not mounted:

```text
decision.md
outcome_labels.json
post_decision_docket.md
```

------

# 11. Model output format

Require structured JSON.

```json
{
  "case_assessment": "Brief rationale, no more than 300 words.",
  "predictions": [
    {
      "unit_id": "count_1_section_10b_issuer",
      "probability_fully_dismissed": 0.67
    },
    {
      "unit_id": "count_2_section_20a_officers",
      "probability_fully_dismissed": 0.41
    }
  ]
}
```

I would allow decimal probabilities, not only integer percentages. Integer percentages are fine operationally, but decimals avoid artificial rounding.

Use a strict parser:

- invalid JSON → repair attempt using deterministic parser, not another model;
- missing unit → penalize with default probability or invalid-output penalty, pre-specified;
- probability outside [0,1] → invalid;
- probabilities need not sum to one because each unit is binary.

The rationale should be collected but not scored as headline.

------

# 12. Scoring and leaderboard

## Primary score

```text
Micro-Brier across prediction units.
```

[
\text{Brier}_u = (p_u - y_u)^2
]

[
\text{MicroBrier} = \frac{1}{N}\sum_u \text{Brier}_u
]

Lower is better.

Brier is appropriate because it is a proper probabilistic scoring rule for binary forecasts; ForecastBench uses Brier-style scoring for binary forecasts and discusses its role in probabilistic forecasting. ([Wharton Faculty Platform](https://faculty.wharton.upenn.edu/wp-content/uploads/2026/02/ForecastBench_A_Dynamic_.pdf))

## Primary inference

Use paired clustered bootstrap by case/motion.

Procedure:

1. sample motions with replacement;
2. include all prediction units within sampled motions;
3. compute micro-Brier for each model;
4. compute pairwise deltas;
5. repeat 5,000–10,000 times;
6. report CIs and rank tiers.

This preserves the micro estimand while respecting within-motion correlation.

When related cases or MDL families repeat the same legal pattern, also report a sensitivity clustered or capped by related-case family. This is not a replacement for micro-Brier; it is a guardrail against one repeated pattern driving the leaderboard.

## Reported metrics

Headline panel:

| Metric                              | Role                                |
| ----------------------------------- | ----------------------------------- |
| Micro-Brier                         | primary accuracy/calibration score  |
| Brier Skill Score vs. base rate     | primary normalized skill score      |
| Log loss                            | secondary sharpness-sensitive score |
| ECE / calibration                   | calibration diagnostic              |
| Mean tool calls per case            | co-headline efficiency metric       |
| Cost per case / per prediction unit | co-headline deployment metric       |
| Invalid-output rate                 | reliability metric                  |
| Refusal/content-filter rate         | reliability metric                  |
| Macro-Brier                         | robustness metric                   |
| Capped per-case micro-Brier         | robustness metric                   |
| Related-family capped sensitivity   | robustness metric, if applicable    |

I agree with the critique: tool calls and cost should be elevated. Do not bury them.

But do **not** combine them into one composite score. Instead report a Pareto frontier:

```text
accuracy vs. cost
accuracy vs. tool calls
accuracy vs. latency
```

Two models with the same Brier but radically different cost/tool behavior are operationally different products.

Pre-specify scoring edge cases:

```text
Log-loss clipping: fixed epsilon before evaluation.
ECE bins: fixed bin count and binning rule before evaluation.
Missing prediction: default probability or invalid-output penalty, pre-specified.
Duplicate prediction for same unit: deterministic resolution rule.
Probability outside [0,1]: invalid.
Non-JSON output: deterministic repair attempt, then invalid if still unparsable.
```

------

# 13. Baselines

Use strong baselines. Weak baselines invite a skeptical reviewer to say the benchmark is mostly measuring base rates.

## Required baselines

### 1. Global base rate

Historical probability of full dismissal across all training-period units.

### 2. Motion/court/NOS base rate

Empirical dismissal probability conditioned on:

- motion type;
- court or district;
- NOS macro-category;
- maybe plaintiff/defendant type.

### 3. Metadata-only model

Features:

- court;
- district/circuit;
- judge;
- NOS;
- party types;
- law-firm/counsel indicators if available;
- motion length;
- complaint length;
- number of claims;
- number of defendants;
- represented/government flags;
- case age;
- docket length.

Model can be logistic regression, gradient-boosted trees, or calibrated random forest. Keep it simple and reproducible.

### 4. Judge-history baseline

I agree with the refinement:

```text
Use judge-specific MTD prior only if judge has ≥30 historical MTD decisions.
Otherwise use court-level or district/NOS prior.
```

Publish:

```text
Share of benchmark units using judge-specific prior: X%
Share using court-level fallback: Y%
Share using global fallback: Z%
```

### 5. No-brief LLM

Give model metadata and prediction units, but no briefs. This shows how much the model gets from institutional/docket priors.

### 6. Full-packet LLM

Main result.

## Ablations

Ablations are not anti-contamination. They explain signal source.

Run at least:

| Condition                     | Purpose                      |
| ----------------------------- | ---------------------------- |
| Metadata only                 | institutional/docket priors  |
| Briefs only, redacted sample  | argument/legal merits signal |
| Judge removed/redacted sample | judicial prior sensitivity   |
| Full packet                   | headline                     |
| Full packet without tool      | value of docket exploration  |
| Full packet with tool         | main agentic condition       |

Do not remove judge identity from the headline. Judge identity is signal for a prediction benchmark.

------

# 14. Human expertise ladder

I agree this should be treated as a core contribution, not a nice-to-have.

A serious expertise ladder makes the paper much more interesting to both legal and AI audiences.

## Recommended design

Use a stratified sample of cases:

```text
60–100 MTDs total for human baseline.
```

Groups:

| Group                            | Suggested burden | Role                            |
| -------------------------------- | ---------------- | ------------------------------- |
| Summer associates / law students | 40–80 cases      | novice legal baseline           |
| Junior/midlevel litigators       | 20–50 cases      | practicing-lawyer baseline      |
| Senior litigators                | 20–30 cases      | expert baseline                 |
| You / small expert panel         | 20–30 cases      | calibration/adjudication anchor |

Each human receives the same packet as the model:

- no external research unless models get it;
- same prediction units;
- same probability format;
- same time limit;
- same instructions.

Report:

- Brier;
- calibration;
- time spent;
- confidence;
- agreement with model;
- performance by complexity stratum.

The strongest possible empirical finding is not “LLMs beat summer associates.” It is something like:

> Frontier models match midlevel associates on simple MTD units but trail senior litigators on complex, multi-defendant, mixed-doctrine motions.

Or, if models outperform everyone, that is even more striking.

Either way, the expertise ladder makes the benchmark legible to lawyers.

------

# 15. Cross-cycle comparability

Your instinct remains right:

> Within-series relative ranking is the clean headline. Cross-series capability gain is secondary.

## What versioning solves

Versioned manifests solve:

- reproducibility;
- within-series comparability;
- re-running new models on old cycles;
- auditability.

They do not solve:

- case-mix drift;
- court-mix drift;
- doctrine drift;
- seasonal docket drift;
- differing complexity across cycles.

ForecastBench’s methodology is directly relevant here because it identifies the problem with comparing forecasters on different question sets and uses a difficulty-adjusted Brier approach that separates forecaster ability from question difficulty. ([ForecastBench](https://www.forecastbench.org/assets/pdfs/forecastbench_updated_methodology.pdf))

## Practical cross-cycle plan

### Headline

```text
Series-specific leaderboard.
```

Example:

```text
LegalForecast-MTD Series 2026-05 Rapid
LegalForecast-MTD Series 2026-05 Official
```

### Secondary

```text
Difficulty-adjusted rolling leaderboard.
```

Use bridge predictors:

- fixed open-weight LLMs;
- base-rate model;
- metadata model;
- judge-history baseline;
- maybe one stable commercial model if API version remains available.

For each series, the reference models estimate the cycle’s empirical difficulty.

A simple model:

[
\text{loss}*{m,u} = \alpha_m + \gamma_s + X_u\beta + \epsilon*{m,u}
]

Where:

- (m) = model;
- (u) = prediction unit;
- (s) = series;
- (\alpha_m) = model effect;
- (\gamma_s) = series difficulty;
- (X_u) = observable unit/case features.

A stronger model, if enough overlap exists:

[
\text{loss}*{m,u} = \alpha_m + \delta_u + \epsilon*{m,u}
]

Where (\delta_u) is item difficulty.

But because old closed models may disappear, the most practical bridge is stable open-weight/reference models.

## Difficulty diagnostics

Report per series:

- base-rate Brier;
- metadata-baseline Brier;
- judge-history baseline Brier;
- average number of units per motion;
- average complaint length;
- average briefing length;
- court/NOS mix;
- model prediction dispersion;
- label ambiguity rate;
- human disagreement rate, if sampled.

Prediction dispersion can help identify hard cases, but I would not make it the primary difficulty adjustment. It is a useful diagnostic, not a ground-truth difficulty measure.

------

# 16. Series design and publication cadence

## Proposed series types

### Rapid series

Use for model-release responsiveness.

```text
Trigger: major model release.
Window: begins at public/API release timestamp.
Dataset: first 150 clean post-release MTD decisions, or first 14 days, whichever gives enough sample.
Status: provisional.
```

### Official series

Use for paper/leaderboard credibility.

```text
Window: fixed 28-day decision-date window after release.
Minimum descriptive threshold: 100 clean motions and 400 prediction units.
Strong ranking threshold: 250 clean motions, preferably 300-500.
Status: official descriptive if minimum met; strong ranking only if power threshold met.
```

### Rolling annual aggregate

Use for stronger claims.

```text
All official cycles in a calendar year, difficulty-adjusted.
```

This structure lets you publish quickly without making rapid windows carry all methodological weight. The rolling annual aggregate should carry the strongest claims about model ranking unless an individual official cycle has enough motion-level power on its own.

------

# 17. Press/publicity contamination

The press filter should be a sensitivity analysis, not only a hard exclusion.

Hard-exclude:

- cases where public reporting revealed the target outcome before model evaluation;
- cases where the decision itself was quoted or summarized before the run;
- cases where related coverage makes the exact result obvious.

Tag and sensitivity-test:

- high Google News volume;
- Wikipedia page;
- major public company parties;
- major mass tort / MDL;
- major constitutional/political salience.

Report:

```text
Main result excluding known outcome leakage.
Sensitivity excluding high-publicity top decile.
Sensitivity including high-publicity but non-leaked cases.
```

Do not overfilter high-stakes cases out of existence. They are operationally important.

------

# 18. MDLs

Do not categorically exclude MDLs.

Exclude only when clean prediction units cannot be defined.

Include MDL-related cases when:

- the motion targets identifiable claims/defendants;
- the ruling clearly resolves those units;
- the parties/claims are not duplicated in a way that inflates unit count;
- the order is not an omnibus ruling spanning dozens of non-comparable complaints.

Add:

```json
{
  "mdl_related": true,
  "mdl_unitization_clean": true
}
```

Then report an MDL sensitivity analysis.

------

# 19. Government-party cases

For v1, I would not categorically exclude government parties unless they create label or distribution problems.

Instead tag:

```json
{
  "government_plaintiff": false,
  "government_defendant": true
}
```

Run sensitivity:

```text
private-only
all represented civil
government-party subset
```

If government cases create a weird distribution, you can exclude them in v1. But do not assume in advance that exclusion is necessary.

------

# 20. Appellate track

Do not include appeals in v1.0.

A balanced 50/50 affirm/reverse appellate dataset would test discrimination, not calibrated prediction under the natural distribution. It could be valuable, but it is a different benchmark.

If you later build it, call it:

```text
LegalForecast-Appellate-Discrimination
```

or

```text
LegalForecast-Appellate-Calibrated
```

Do not mix it with MTDs.

For v1, the clean contribution is:

```text
Federal MTD claim-level prediction.
```

That is enough.

------

# 21. Implementation details in Inspect

## Task design

Each sample is one motion/case. Each sample contains multiple prediction units.

The model produces one JSON object with predictions for all units.

The scorer expands the sample into unit-level scores.

Pseudo-structure:

```python
class PredictionUnit(BaseModel):
    unit_id: str
    claim_name: str
    defendant_group: str
    target: bool | None = None


class ModelPrediction(BaseModel):
    unit_id: str
    probability_fully_dismissed: float


class CaseOutput(BaseModel):
    case_assessment: str
    predictions: list[ModelPrediction]
```

Scorer behavior:

```text
1. Parse JSON.
2. Match predictions to required unit_ids.
3. Validate probabilities.
4. Compute unit-level Brier.
5. Store per-unit metadata.
6. Aggregate micro-Brier.
7. Aggregate macro-Brier.
8. Log invalid/missing predictions.
```

## CLI orchestration

The repo should expose implementation stages through `uv run legalforecast ...`
commands as the modules mature. Expected command groups:

```text
legalforecast discover
legalforecast retrieve
legalforecast extract
legalforecast link
legalforecast unitize
legalforecast label
legalforecast prereg validate
legalforecast freeze
legalforecast packet build
legalforecast eval run
legalforecast score
legalforecast report
legalforecast fixture e2e
```

Each command should support fixture mode where practical, emit structured logs,
write declared artifacts, and fail with actionable errors. The e2e fixture
command should be the smoke test for the full local workflow.

## Offline model fixtures

Harness and scoring tests should not require paid model calls. Maintain
deterministic mock-model fixtures for:

- calibrated predictions;
- overconfident predictions;
- base-rate predictions;
- invalid JSON;
- missing units;
- duplicate units;
- out-of-range probabilities;
- refusals;
- excessive tool use.

These fixtures should run through the same parser, accounting, scorer, and
leaderboard paths used by real model outputs.

## Tool-call cap

Set a cap, probably:

```text
0-tool condition: no tool, default packet only.
Main condition: up to 10 docket-entry reads.
Stress condition: up to 25 reads.
```

For v1 headline, I would use **10**. MTDs should not require 25 docket pulls if the core papers are already in context.

Report:

```text
mean tool calls
median tool calls
95th percentile tool calls
unused-tool share
cost per motion
```

## Sampling parameters

For official runs:

```text
temperature = 0 or provider-equivalent deterministic setting
top_p = 1
max_output_tokens fixed
one run per model for official leaderboard
optional 3-run variance appendix
```

If models are nondeterministic despite temperature 0, run a variance study on a subset.

------

# 22. Leaderboard design

The leaderboard should not be a single column.

Minimum columns:

| Rank | Model | Micro-Brier ↓ | BSS ↑ | Log loss ↓ | ECE ↓ | Cost/case ↓ | Tool calls/case ↓ | Invalid % ↓ |
| ---- | ----- | ------------- | ----- | ---------- | ----- | ----------- | ----------------- | ----------- |
|      |       |               |       |            |       |             |                   |             |

Add rank tiers:

```text
Tier 1: statistically indistinguishable from best model
Tier 2: significantly below Tier 1 but not distinguishable within tier
Tier 3: below Tier 2
```

Use paired clustered bootstrap.

Also include a Pareto chart:

```text
x-axis: cost per case
y-axis: micro-Brier
```

Lower-left frontier models are operationally best.

------

# 23. Power planning

Because inference is clustered, think in motions, not raw units.

Rough guide:

| Clean MTDs | Likely use                                     |
| ---------- | ---------------------------------------------- |
| 50         | pilot only                                     |
| 100        | official descriptive cycle; large deltas only  |
| 150        | useful rapid leaderboard if deltas are sizable |
| 250–300    | serious official cycle                         |
| 500+       | strong paper-level inference                   |

If each motion yields 3–8 units, micro-Brier will be stable descriptively, but pairwise statistical inference still depends heavily on motion-level clustering.

A practical first target:

```text
Pilot: 50 MTDs
Rapid release: 150 MTDs
Official descriptive: ≥100 MTDs and ≥400 units
Strong v1 ranking / paper: 300–500 MTDs if available
```

Given the federal docket volume, your optimism may be right. The bottleneck may not be decisions; it may be **clean linkage, public briefing availability, and reliable unit labels**.

------

# 24. Ethics and legal-risk documentation

Publish a data card and ethics note.

Cover:

- public-record status;
- privacy and sensitive facts;
- sealed-material exclusion;
- minors/victims/sensitive-party policy;
- judge profiling;
- party/counsel profiling;
- non-use as legal advice;
- limitations of predictive use;
- takedown policy;
- document redistribution policy.

On judge profiling, be direct:

> Judge identity is included because the benchmark evaluates outcome prediction, and judge-specific priors are legitimate predictive signals. The benchmark reports judge-only and no-judge ablations to quantify reliance on this signal.

That is better than pretending judge identity is irrelevant.

------

# 25. Data redistribution

Be careful.

Public PACER filings are public, but redistribution at scale can still raise practical, contractual, privacy, and reputational issues.

Safest public release:

- manifests;
- CourtListener/RECAP IDs;
- hashes;
- extracted metadata;
- prediction units;
- labels;
- prompts;
- scorer;
- Docker harness;
- scripts to reconstruct case packets where documents are publicly available.

For documents, choose one of:

1. publish full extracted text only for documents clearly available via RECAP and appropriate for redistribution;
2. publish references/hashes and reconstruction scripts;
3. provide benchmark packets under a research-use license;
4. maintain a hosted eval service that runs models without distributing all filings.

For open-source credibility, option 2 plus scripts may be enough.

------

# 26. Paper framing

I would write the paper for **AI/ML methodological credibility first**, with a legal-practitioner executive framing.

Why? Because the artifact’s long-term credibility depends on whether researchers take the benchmark seriously. But the opening should be legible to litigators and lateral/hiring audiences.

## Suggested title

> LegalForecast-MTD: A Rolling, Contamination-Resistant Benchmark for Calibrated Prediction of Federal Motion-to-Dismiss Outcomes

## Abstract claim

Something like:

> We introduce LegalForecast-MTD, an open benchmark for evaluating frontier language models on calibrated prediction of federal motion-to-dismiss outcomes using pre-decision docket materials. Unlike legal-reasoning benchmarks that test doctrinal classification, LegalForecast-MTD evaluates practitioner-style forecasts of what courts actually do. The benchmark uses post-release decisions, claim-by-defendant prediction units, micro-Brier scoring, clustered inference, contamination filters, human-audited labels, and cost/tool-use reporting.

## Narrative hierarchy

1. Legal outcome prediction is economically important.
2. Existing legal benchmarks mostly test doctrinal reasoning or static classification.
3. Real litigation forecasting requires calibrated probabilities over messy docket records.
4. Contamination is a central issue for frontier LLM evals.
5. LegalForecast-MTD offers a rolling, auditable benchmark.
6. Results compare frontier models, baselines, and human legal expertise.

This serves all three audiences:

- AI researchers see a benchmark methodology.
- Legal practitioners see operational relevance.
- Hiring/lateral audiences see that you built something serious at the law/AI frontier.

------

# 27. Recommended v1.0 protocol, condensed

## Scope

```text
Federal district court MTDs only.
Represented civil cases.
Post-model-release written decisions.
Claim×defendant/group binary prediction units.
```

## Primary target

```text
Probability that each challenged claim is fully dismissed as to each challenged defendant/group.
```

## Primary metric

```text
Micro-Brier over prediction units.
```

## Inference

```text
Paired clustered bootstrap by motion/case.
```

## Secondary metrics

```text
Macro-Brier
Capped per-case micro-Brier
Related-case-family capped sensitivity
Log loss
Brier Skill Score
ECE / calibration
Tool calls
Cost
Invalid-output rate
Human baseline comparison
```

## Dataset

```text
case.dev-first deterministic selector, with optional public-record fallback only
if explicitly enabled.
Explicit case.dev runtime config and live-smoke-test gate.
Candidate discovery from dismiss/dismissal docket-entry terms plus Rule 12 filters.
Source-document provenance schema and packet reconstruction metadata.
Two-stage unitization and labeling.
Frozen pre-decision prediction units, with blinded repair or exclusion.
LLM ensemble plus lawyer adjudication/audit.
Frozen manifest with hashes.
Exclusion ledger.
Mandatory case-mix diagnostics.
Shared golden fixture corpus and structured test logs.
```

## Contamination

```text
Decision after model release.
Exclude outcome leakage.
Tag cutoff sensitivity variables.
Prefer post-cutoff filings where available, but do not require them.
```

## Harness

```text
Inspect AI.
Neutral prompt.
No network.
Controlled docket tool.
Same packet for all models.
Vendor-native agent harness only as later comparison.
```

## Baselines

```text
Global base rate
Court/NOS/motion base rate
Metadata-only model
Judge-history baseline with ≥30-decision threshold
No-brief LLM
Human expertise ladder
```

## Publication

```text
Rapid leaderboard for first-N post-release decisions.
Official fixed-window leaderboard.
OSF/AsPredicted preregistration plus repo-local protocol YAML/hash bundle.
Frozen model registry / run matrix.
Open manifest, scorer, logs, and reconstruction scripts.
Pareto frontier for accuracy vs. cost/tool use.
Annual aggregate for strongest model-ranking claims.
```

## Development workflow

```text
bd tracks implementation work and dependencies.
uv manages Python environments and commands.
pyproject.toml is the dependency and tooling source of truth.
legalforecast CLI commands orchestrate pipeline stages.
tests/fixtures supplies offline fixtures for deterministic validation.
Live case.dev tests are opt-in and credential-gated.
```

------

# 28. The main methodological vulnerabilities and your answers

The serious risks are the ones that can distort relative model rankings or make the labels unreliable. Ordinary non-representativeness is a scope note unless it plausibly creates a model-specific advantage.

High-priority validity risks:

1. outcome leakage;
2. model-specific contamination or memorization advantage;
3. unstable prediction-unit construction;
4. label noise large relative to model deltas;
5. domination by mega-cases, repeated related cases, one district, or one NOS category;
6. insufficient motion-level sample size for pairwise model comparisons;
7. cost/cadence infeasibility for rolling releases.

| Vulnerability                                    | Revised response                                                                                           |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| Outcome leakage                                  | Hard exclusion; no decision text, post-decision docket entries, R&Rs, oral rulings, or leaked results in packet. |
| Model-specific contamination                     | Record model snapshot/cutoff/evaluation timestamp; disable network/search; run cutoff sensitivity where available. |
| Unitization instability                          | Freeze units before decision review; use blinded repair or exclude; publish repaired-case flags.           |
| Label ambiguity/noise                            | Human reliability pilot; LLM ensemble audit; lawyer adjudication; publish disagreement and error rates.    |
| Micro-Brier overweights complex cases            | Keep micro-Brier headline; report macro, capped per-case micro, related-family capped sensitivity, and clustered inference. |
| Mega-case or related-case domination             | Group identical units; cap/winsorize sensitivity; flag related-case and MDL families.                      |
| Insufficient power                               | Separate pilot, rapid/provisional, official descriptive, strong ranking, and annual aggregate claims.       |
| case.dev/RECAP public-docket skew                | Use available public data; report case-mix diagnostics; sensitivity only if one bucket dominates.          |
| Pre-release briefing                             | Intended design; public pre-decision materials are legitimate signal; track cutoff strata but do not gate. |
| 28-day decision-window artifacts                 | Rapid is provisional; official is fixed-window; annual aggregate carries the strongest ranking claims.      |
| Non-representativeness of all federal MTDs        | Expressly disclaimed; benchmark compares models on the included public-record task.                        |
| Judge identity as "shortcut"                     | Prediction benchmark includes judge priors; judge-only/no-judge ablations quantify reliance on this signal. |
| Tool-use harness confound                        | Neutral Inspect harness; fixed tool cap; cost/tool-call/latency co-headlines.                             |
| Human baseline too weak                          | Stratified expertise ladder, not just summer associates.                                                   |
| Leave-to-amend ambiguity                         | Secondary conditional task only.                                                                           |
| Appellate base-rate dominance                    | Defer appellate to separate track.                                                                         |

------

# Final recommendation

Adopt the other model’s main refinements, with two adjustments.

First, **micro-Brier should be the headline**. The prediction unit is the claim-defendant exposure unit, and the benchmark should score the average quality of those predictions. Use clustered bootstrap for inference and macro-Brier as a robustness metric.

Second, the N-threshold cadence critique is overstated for your design because you are sampling decisions issued after release, not newly filed motions that resolve fastest. Still, use a two-tier cadence: **rapid first-N leaderboard** for model-release relevance, and **official fixed-window leaderboard** for methodological cleanliness.

Everything else points toward a tight v1:

> MTD-only, claim-level, post-release, case.dev-ingested, Inspect-harnessed, micro-Brier scored, human-audited, cost-aware, with an expertise ladder, mandatory case-mix diagnostics, frozen pre-decision units, and pre-registered analysis.

That is a strong benchmark design. It is narrow enough to execute, objective enough to defend, and legally meaningful enough not to look like another generic LLM eval with legal flavor pasted on. The plan should not pretend to be an unbiased census of federal MTD outcomes. It should be clear that the benchmark compares models on a defined public-record forecasting task and spends its methodological effort on the risks that can actually corrupt that comparison: leakage, model-specific contamination, unitization instability, label noise, dominance, power, and cost.
