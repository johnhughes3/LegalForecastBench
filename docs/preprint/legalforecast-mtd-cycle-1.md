# LegalForecast-MTD Cycle 1

Status: Pre-results methods draft - no Cycle 1 result claimed

Author: John J. Hughes III
Version: 2026-07-17 repository draft

## Abstract

LegalForecast-MTD evaluates probabilistic forecasts of federal motion-to-dismiss outcomes from written records frozen before the target decision. The prediction unit is a challenged claim against a defendant or defendant group, and the target is the probability that the unit will be fully dismissed in the first written disposition of the target motion. The benchmark is designed to measure calibrated forecasting on realistic litigation records while reducing two recurrent threats to legal prediction research: target leakage from court-authored outcome text and retrospective selection after outcomes are known.

Cycle 1 freezes a cohort, model-visible packets, prediction units, labels, model registry, execution policy, and scorer before official dispatch. Models receive docket and filing material available before the disposition, never the target written decision. The primary metric is micro-Brier score over prediction units. Supporting analyses report calibration, log loss, coverage and invalid-output behavior, realized outcome prevalence, accounting, paired packet ablations, baseline context, and clustered uncertainty. Public artifacts support hash and arithmetic reproduction; a controlled audit retains the source and label evidence that cannot be redistributed.

This document records the prespecified design and the exact result slots that will be populated only from the independently audited Cycle 1 public aggregate. It contains no Cycle 1 score, ranking, confidence interval, prevalence estimate, cost total, or model comparison. The results section is intentionally marked pending. The manuscript will become an **Official LegalForecast-MTD Cycle 1 result** only after the official freeze, dispatch, receipt, aggregation, audit, protected-publication, and authorship gates pass.

> Draft boundary. Every result cell in this version reads “Pending audited Cycle 1 aggregate.” A repository draft and a rendered PDF do not authorize SSRN or arXiv submission.

## 1. Research question and intended use

Legal forecasting is useful only when the forecast is made from information that would have been available at the decision point. Some legal judgment-prediction datasets ask a model to classify court-authored fact sections or other portions of a judgment that were written with knowledge of the result. Those tasks can be valuable text-classification benchmarks, but they do not fully reproduce the information constraints facing a lawyer, litigant, or court observer before decision. Recent work has therefore called for legal prediction studies to distinguish realistic pre-decision prediction from retrospective classification and to design around an identified end user [R1].

LegalForecast-MTD asks a narrower question: given a frozen written record preceding a federal court's first disposition of a target motion to dismiss, how well does a declared model configuration assign probabilities to full dismissal of each challenged claim-defendant unit? The benchmark does not attempt to predict every procedural consequence of an order. It does not score partial dismissal as full dismissal, infer later amendment outcomes, or claim to measure legal intelligence in the abstract. Its target is deliberately operational and auditable.

The unit of analysis matters. A complaint can contain several claims, and a motion can challenge different claims against different defendants on different grounds. A case-level win/loss label would erase that structure. Cycle 1 instead represents each challenged claim against a defendant or defendant group as a prediction unit. The model supplies a probability between zero and one for full dismissal of that unit in the first written disposition. The scorer compares that probability with a locked binary label under a prespecified parser and scoring policy.

Published predictions are retrospective research artifacts about matters already decided before scoring. The benchmark is not a service for pending litigation, and its outputs are not legal advice. A score describes performance on the frozen cohort and declared model configuration. It does not establish reliability for another court, motion type, time period, client matter, or model release.

Legal judgment prediction has a substantial research history. Prior work has modeled Supreme Court outcomes from pre-decision structured data [R2], classified European Court of Human Rights outcomes from judgment text [R3] [R4], and developed multilingual or jurisdiction-specific datasets [R5] [R6] [R7]. CLC-UKET is a particularly relevant legal comparison because it studies outcome prediction and includes human predictions as a reference [R7]. ForecastBench is a design analogue outside law because it evaluates forecasts on questions unresolved at submission time and uses proper probabilistic scoring [R8]. These projects establish context, not evidence that LegalForecast-MTD performs well.

LegalForecast-MTD's contribution is the combination of a pre-decision federal litigation record, claim-defendant prediction units, probability forecasts, frozen post-cutoff evaluation, public arithmetic artifacts, and a separate controlled audit. The defensible claim is correspondingly narrow: this is an open, contamination-controlled benchmark for probabilistic motion-to-dismiss forecasting from the pre-decision record.

## 2. Benchmark design

### 2.1 Cohort and target disposition

Cycle 1 is organized around a frozen cohort rather than a convenience sample assembled after model outputs are seen. Candidate matters must satisfy the cycle's dated eligibility, motion, document, and disposition rules. Acquisition records source handles, retrieval status, hashes, exclusions, and completeness evidence. The official freeze binds exactly 100 eligible matters; a shortfall blocks the official run rather than silently changing the denominator or weakening the inclusion rule.

The target outcome is the first written disposition of the target motion. This anchor avoids choosing among later procedural events after their substantive direction is known. A later amended complaint, renewed motion, reconsideration order, appeal, or settlement may matter to litigants, but it is not substituted for the frozen target. Withdrawals and corrections use explicit records and superseding publications rather than silent edits.

The labeling protocol separates the motion, prediction unit, and outcome. Reviewers determine whether each claim was challenged, the relevant defendant grouping, and whether the first written disposition fully dismissed the unit. Ambiguous or unsupported units follow the protocol's adjudication and exclusion rules. Locked labels remain private until the publication gate because early disclosure would defeat the benchmark's contamination boundary.

### 2.2 Model-visible packets

Each case packet contains only material permitted by the frozen packet policy. The full-packet condition may include a controlled docket chronology, operative complaint material, the target motion and supporting memorandum, opposition, reply, and other allowed pre-decision filings when available. Every included source has a stable identifier and content hash. Packet construction records missing optional sections rather than filling them with outcome-derived text.

The packet excludes the target written disposition and screens docket entries and filing text for outcome leakage. An audit representation can retain information needed to explain an exclusion while the model-visible representation removes it. This distinction prevents an operational audit trail from becoming an accidental model input. Restricted source bytes are not committed to the public repository merely because their hashes or source handles can be disclosed.

The headline `full_packet` condition is paired with `metadata_only` unless an operator explicitly requests a single-ablation diagnostic. The metadata condition removes the substantive record while preserving the declared metadata feature surface. Because each model configuration is evaluated on both conditions for the same cases and prediction units, the analysis can report a paired difference. The difference is evidence about these frozen packet conditions on this cohort; it is not automatically a general causal estimate of the value of legal text.

### 2.3 Model and prompt identities

The model registry freezes provider, model identifier or snapshot, execution backend, solver contract, and allowed settings. Official prompts request a probability and a short rationale for every prediction unit. The output schema is fixed before dispatch. The parser accepts only declared structures and probabilities in range. Missing or malformed required units follow the documented fail-closed defaults; they are not silently dropped to improve coverage or score.

Registry and prompt identity are part of the result. A provider label alone is not enough because hosted model behavior, tool availability, inference settings, and wrapper logic can differ. The public run card therefore records the frozen identities and relevant execution settings. Cross-cycle comparisons require special caution when any of those identities, the cohort, or the packet policy changes.

### 2.4 Human and statistical references

Cycle 1 has no human-baseline arm. No human forecasts were collected for this cycle, and the paper will not imply a model-versus-human comparison. A separately prespecified human-forecaster protocol may be used in a future cycle with recruitment, blinding, compensation, sample-size, and author-exclusion rules fixed before forecasts are observed.

Fitted statistical baselines require a frozen historical training corpus that predates the Cycle 1 outcomes under evaluation. If that corpus is valid and present, baseline rows remain in the paired analysis and public comparison artifacts but are labeled and ranked separately from evaluated models. If no valid frozen corpus exists, the run card records the no-baseline condition and the report uses the unranked constant-0.5 reference only as scoring context. The paper will not claim Brier skill without an allowed empirical baseline and the analysis needed to support that claim.

## 3. Contamination resistance

Benchmark contamination is not a single test. It is a chain of controls over when the target becomes knowable, what text reaches the model, when cases and methods are frozen, and whether later changes can be traced. ForecastBench's use of unresolved questions illustrates the value of evaluating information that was not available at submission time [R8]. LegalForecast-MTD applies a related principle to court records, while recognizing that litigation data require document-level and procedural controls.

First, the cycle uses a post-cutoff release anchor and eligibility dates intended to place target dispositions after relevant model knowledge cutoffs. A date rule is necessary but insufficient. Search indices, later docket summaries, and documents embedded in a packet can still reveal outcomes. The model-visible packet is therefore independently screened for target-disposition text and other direct outcome signals.

Second, the freeze binds the cohort and every result-producing contract before official dispatch. The committed hash-only record covers the run-input manifest, labels hash, model registry, packet rows and hashes, prompt and scorer artifacts, execution policy, shard schedule, budget policy, publication policy, and required receipt schema. Private labels are hash-bound without being exposed. The protected workflow validates those commitments before provider fan-out.

Third, packet provenance is content-addressed. Each model-visible document and controlled docket representation has a recorded digest. A packet cannot be replaced after the run without changing its identity. The accepted result also carries packet and solver identity, allowing fan-in to reject a response attached to the wrong case, packet, registry, ablation, or repeat.

Fourth, the official workflow retains attempts and distinguishes failed execution from accepted score records. A failure log does not become a result. Resume reuses only complete matching outputs; it does not accept partial or identity-mismatched material. This limits opportunities to select favorable retries after observing model behavior.

Fifth, the aggregate is exact over the frozen Cartesian product of case, ablation, model, and repeat. Missing cells, extra cells, duplicate identities, or a narrowed model set fail aggregation. Amendments use a contiguous provenance chain and preserve byte identity for previously accepted outputs. Corrections produce a superseding aggregate, rather than modifying a released bundle in place.

These controls reduce identifiable leakage and selection paths; they do not prove that a model has never encountered related public litigation material during pretraining or serving. The paper therefore uses “contamination-controlled” rather than “contamination-free.” The residual risk is disclosed as a limitation and is one reason performance is interpreted on the frozen cohort rather than as proof of a general legal capability.

## 4. Model execution and recovery

Official provider calls are partitioned into isolated case, ablation, model, and repeat cells. Before execution, the workflow validates the freeze record, expected model universe, packet identities, labels commitment, requested ablations, projected cost, and receipt contract. Each cell receives only its declared packet and runtime configuration. Credentials and private operator records are outside model-visible inputs and public artifacts.

A result is eligible for fan-in only when it is complete, schema-valid, and identity-matched. The durable result envelope records the cycle, case, packet, ablation, model, solver, registry, repeat, and attempt identities needed to distinguish one cell from another. The parser validates probability structure and required units. Refusals, invalid outputs, and required-unit defaults remain measurable outcomes rather than disappearing from the denominator.

Recovery is conservative. A resumed run may reuse a complete result only when the stored identity matches the current frozen cell. Interrupted or failed attempts remain available for controlled operational audit, but they do not become score rows. A later successful attempt does not erase the earlier failure. The public summary exposes only the accepted accounting fields enumerated below; it does not turn private operational records into promised manuscript inputs.

The official system separates solver execution from aggregation and publication. Provider-facing code does not decide which rows become public leaderboard entries. Fan-in first verifies authenticated receipts and the exact expected matrix. Aggregation then reconstructs scores from accepted per-case artifacts and locked labels. The static report renderer accepts only the aggregate's public directory. This separation reduces the authority of any single runtime component.

Temperature and fixed prompts reduce avoidable variation but cannot make a hosted model deterministic. Repeats expose some run-to-run variation, while the primary inferential pairing remains aligned to the declared case-family clusters. A result describes the exact registry and execution date, not a timeless property of a product name.

## 5. Metrics and statistical analysis

### 5.1 Primary score

For prediction unit i, let p_i be the forecast probability of full dismissal and y_i be the locked binary outcome. The Brier loss is (p_i - y_i)^2 [R9]. Cycle 1's headline micro-Brier is the arithmetic mean of that loss over all scored prediction units in the declared analysis cell. Public reconstruction must recompute each unit loss from `probability_fully_dismissed` and `outcome`, reject the aggregate if any published `brier` value differs from `(probability_fully_dismissed - outcome)^2`, and only then average the recomputed losses. Lower values indicate better probabilistic accuracy. Because the metric penalizes both false confidence and missed probability mass, a hard classification threshold is not required.

Micro-averaging gives each prediction unit equal weight, so cases with more challenged units contribute more terms. The report therefore includes case-capped and family-capped sensitivity analyses. Those analyses test how conclusions change when dense cases or related proceedings receive less aggregate weight; they do not replace the frozen headline metric after results are observed.

Log loss is reported as a complementary proper score and is more sensitive to extreme probabilities assigned to the wrong outcome. Calibration summaries compare forecast probabilities with observed frequencies in declared bins or curves. Coverage, refusal rate, invalid-output rate, and required-unit default behavior are reported beside accuracy because a superficially strong score can be misleading when a system avoids difficult units or fails to produce valid predictions.

### 5.2 Pairing and uncertainty

Comparisons use the paired structure of the benchmark. Model configurations and ablations are evaluated on the same frozen units. Bootstrap resampling occurs at the coarsest declared independence cluster: multidistrict-litigation family when present, otherwise related-case family when present, otherwise case. This avoids treating closely related units as independent merely because they occupy separate rows.

The report will publish paired score differences, confidence intervals, and pairwise win probabilities according to the frozen analysis contract. Exact bootstrap ties receive half credit. When the independent-cluster count is below the configured threshold, observed ranks remain visible but uncertainty grouping is suppressed and a small-cluster warning is required. The paper will not use significance language where the contract suppresses it.

Rank tiers use the prespecified multiplicity adjustment in the reporting code. The best-model anchor and evaluated-model differences are computed among evaluated models, not statistical baselines. Baselines remain labeled reference rows. The analysis will state whether an empirical baseline was available and valid before making any claim about skill relative to that baseline.

### 5.3 Full-packet and metadata-only analysis

For each evaluated model with both conditions, the ablation report computes the paired micro-Brier difference between `full_packet` and `metadata_only`, its interval, and the probability that the record-bearing packet has lower loss. The interpretation stays local to the frozen treatment definitions. The two conditions may differ in token length, available evidence, and model behavior; the study does not describe the observed difference as a universal “legal reasoning effect.”

### 5.4 Accounting

The public report includes the fields exported in `public/scores.json`: run count, request count, prompt tokens, completion tokens, total tokens, mean latency, 95th-percentile latency, estimated cost, cost per case, and cost per prediction unit. Missing provider dimensions are labeled missing rather than imputed. Dollar cost is reported with its auth and pricing basis because subscription execution, promotional credits, and API billing are not interchangeable. Efficiency observations are descriptive for the frozen run. More detailed operational records remain part of the controlled audit and are not promised as public manuscript inputs.

## 6. Cycle 1 results

**Publication status after audited population:** Official LegalForecast-MTD Cycle 1 result.

No result is available in this draft. Population is permitted only from the canonical audited public aggregate produced by the official publication gate. The package manifest binds each row below to a source path, source field, and reconstruction check. Independent arithmetic and claims review must pass after population.

| Result element | Cycle 1 value | Required interpretation |
| --- | --- | --- |
| Frozen cohort and scored units | Pending audited Cycle 1 aggregate | Report exact clean-motion, prediction-unit, cluster, model, ablation, and repeat counts. |
| Headline micro-Brier by evaluated model | Pending audited Cycle 1 aggregate | Lower is better; reproduce from public unit scores before ranking language. |
| Clustered uncertainty and rank tiers | Pending audited Cycle 1 aggregate | Report intervals, adjustment, and any small-cluster suppression exactly. |
| Full-packet versus metadata-only delta | Pending audited Cycle 1 aggregate | Describe only the observed paired contrast for the frozen conditions; if the audited artifact index contains no ablation-delta artifact, report that no paired full-packet/metadata-only rows were available. |
| Calibration and log loss | Pending audited Cycle 1 aggregate | Report alongside the primary metric without selecting bins after review. |
| Refusal, invalid-output, and coverage rates | Pending audited Cycle 1 aggregate | Keep failed or defaulted required units in the declared denominator. |
| Realized prevalence | Pending audited Cycle 1 aggregate | Provide outcome context without treating prevalence as model skill. |
| Baseline context | Pending audited Cycle 1 aggregate | State whether a valid frozen empirical baseline exists before skill claims. |
| Public run, request, token, latency, and cost accounting | Pending audited Cycle 1 aggregate | Reconstruct only the public fields in `public/scores.json`, preserve missing dimensions, and disclose cost/auth basis. |
| Public artifact and release hashes | Pending audited Cycle 1 aggregate | Bind the manuscript to the audited immutable publication. |

The final narrative will be populated after the table reconstructs from `public/unit-scores.jsonl`, `public/report/leaderboard.json`, the aggregate run card, calibration output, `public/variance/repeat-sampling.json`, accounting fields in `public/scores.json`, and `public/artifact-index.json`, plus `public/ablation-deltas.json` when that optional artifact is indexed. The narrative will identify the best observed evaluated-model row only if the frozen rank and uncertainty contract supports that description. It will not convert a within-cycle result into a claim about absolute legal intelligence or a different model version.

No Community Harness Comparison appears in this manuscript. Harvey LAB uses a different task, evaluator, and score meaning. If a later validated comparison is useful, it must appear in a separately labeled appendix with its exact preliminary or reproducible-community status and limitations. Placement in an official methods paper cannot promote community evidence to an official LegalForecast-MTD result.

## 7. Limitations

Cycle 1 is a finite sample of federal motion-to-dismiss matters selected under a specific eligibility window and document-availability regime. The case mix may differ by district, subject matter, party type, representation, motion practice, and pleading complexity. Within-cycle pairing improves comparison on the shared cohort but does not make that cohort representative of all federal civil litigation.

The prediction unit is legally meaningful but not independent within a case. Claims may share facts, defendants, and legal theories. Related proceedings can share even more structure. Clustered resampling addresses declared dependence at the MDL-family, related-case-family, or case level, but estimates may remain unstable when the number of independent clusters is small. The small-cluster guard makes that limitation visible rather than manufacturing precision.

Packet completeness varies. Some dockets expose every expected brief through public sources, while others have unavailable or restricted documents. The benchmark records missing optional sections, but missingness may correlate with court, party resources, or case type. The score therefore reflects both model behavior and the information surface produced by the acquisition policy.

Contamination controls reduce direct outcome leakage and retrospective selection, but they cannot establish that a hosted model has never encountered the case, a related filing, or commentary during training or serving. Provider systems can also change behind a stable product name. Model registry metadata and execution dates improve provenance without eliminating that uncertainty.

The binary target does not capture partial dismissal, leave to amend, reasoning quality, litigation value, settlement leverage, later procedural success, or normative legal correctness. A low Brier score would show calibrated prediction of the frozen target, not good lawyering or desirable adjudication. Rationales are collected for transparency and error analysis; unless a separate rubric is prespecified, they are not the headline score.

No human forecasts were collected in Cycle 1. The paper cannot say whether a model outperforms lawyers, judges, litigants, or expert forecasters. Statistical baselines are also conditional on a valid historical corpus and feature freeze. If that evidence is absent, the constant-0.5 row supplies orientation, not an empirical competitor or proof of skill.

Multiple model, ablation, and sensitivity views create opportunities for selective emphasis. The publication contract mitigates this by freezing the headline metric, model universe, analysis family, rank procedure, baseline treatment, and required disclosures. Readers should still treat secondary analyses as descriptive unless their uncertainty and multiplicity treatment support a stronger inference.

Finally, public reproducibility is intentionally incomplete. The repository can publish code, hashes, synthetic fixtures, score arithmetic, aggregate artifacts, run metadata, and lawful source handles. It cannot necessarily redistribute every court filing, provider response, locked label, withdrawal reason, or private audit record. The distinction between public reproduction and controlled audit is a constraint, not a claim of fully open data.

## 8. Reproducibility and audit

The release uses two verification depths. Public reproduction checks that a published result follows from the public aggregate. Controlled audit checks that the public aggregate follows from the frozen source, label, execution, and receipt evidence. The repository methods, labeling, run, and audit contracts define this split [R12]. It makes useful verification possible without publishing credentials, restricted records, or outcome labels before the benchmark gate.

### 8.1 Public arithmetic reproduction

The public bundle includes unit-level Brier rows, leaderboard summaries, calibration and variance outputs, cycle-power diagnostics, a run card, and artifact manifests. A reproducer must recompute every public unit loss from `probability_fully_dismissed` and `outcome`, reject any row whose supplied `brier` value drifts from that calculation, average only the recomputed losses, compare the result with the leaderboard, verify artifact SHA-256 values, and inspect the expected and observed matrix counts. The repository's synthetic end-to-end fixture exercises the same score and report interfaces without provider credentials or private case records.

The manuscript's result table has the same discipline. `package-manifest.json` names the canonical aggregate path and source field for every slot. Population must be mechanical. Reviewers compare every manuscript number, ordering statement, interval, and baseline sentence with the public artifacts. A mismatch blocks the final package.

### 8.2 Controlled source and label audit

A controlled auditor verifies that the release SHA and freeze commitment predate live outputs; that the manifest, labels, registry, packet hashes, scorer, prompt, budget, and publication policy match the commitment; and that accepted outputs form the expected case-by-ablation-by-model-by-repeat product exactly once. The auditor checks packet-source hashes and the target-disposition exclusions, then recomputes the aggregate from accepted artifacts and locked labels.

Raw provider responses, restricted source-document bytes, private withdrawal reasons, credentials, and private debug outputs stay outside the public site. Source handles and hashes can make lawful reconstruction possible without purporting to license third-party material. The Apache-2.0 repository license applies to repository code, not automatically to court documents, provider outputs, or third-party datasets.

### 8.3 Corrections and durable identity

The public artifact index binds the final manuscript to the released files. A correction produces a new, superseding aggregate and publication record. The prior bundle remains identifiable. This avoids silent changes to numbers already cited by readers and permits a correction note to state which freeze, artifact, or analysis changed.

### 8.4 Publication boundary

Repository source, a rendered draft, and a complete SSRN upload folder are not submission authority. John J. Hughes III separately approves authorship, destination, final text, and submission. arXiv is optional and never blocks the official report or SSRN package. The required non-affiliation statement is:

> LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

The final package must pass source-to-claim citation review, result-table reconstruction, leakage and publication scans, deterministic rendering, visual inspection, and independent methods review. After those checks, the only manuscript input allowed to remain pending is the audited official Cycle 1 public aggregate.

## 9. Related work

Early and contemporary legal prediction studies differ in target, jurisdiction, input timing, and unit. Katz, Bommarito, and Blackman used structured information available before decision to model Supreme Court votes and outcomes [R2]. Aletras and colleagues and Chalkidis and colleagues studied European Court of Human Rights judgments, using court-authored text to predict violation outcomes [R3] [R4]. CAIL2018 framed charges, statutes, and prison terms from fact descriptions in Chinese criminal cases [R5]. Swiss-Judgment-Prediction introduced a multilingual, diachronic corpus of Swiss Federal Supreme Court cases [R6].

CLC-UKET studies UK Employment Tribunal outcomes, legal annotations, and human predictions [R7]. Its task and data differ from federal motion practice, but its use of a professional outcome-prediction frame and a human reference makes it a close legal analogue. Medvedeva and McBride argue that legal judgment-prediction research should use data appropriate to the real prediction task, identify end users, and report in an application-centered way [R1]. LegalForecast-MTD adopts those concerns through its pre-decision packet boundary, narrow intended use, and explicit limitations.

ForecastBench evaluates probabilistic forecasts on questions that are unresolved when forecasts are submitted and reports Brier scores [R8]. LegalForecast-MTD does not reuse ForecastBench questions or claim equivalence between world-event forecasting and litigation. It borrows the high-level design lesson that post-cutoff outcomes and proper scoring reduce some benchmark-contamination and threshold-selection problems.

The benchmark is also distinct from long-form legal work-product evaluations such as Harvey LAB [R10]. A rubric score for a drafted deliverable and a Brier score for an outcome probability answer different questions. They must not be combined in one leaderboard or described as an overall winner. Commercial motion-level prediction products provide additional context that metadata-only legal forecasting is operationally pursued [R11], but marketing materials do not validate this benchmark's methods or results.

## 10. Ethics, governance, and disclosures

Cycle 1 uses public-record litigation material and may retain restricted copies for controlled processing. Public-record status does not eliminate privacy risk. Publication guardrails scan public paths for secret-looking content, private operational material, locked labels, raw provider outputs, restricted source bytes, and private withdrawal detail. The human-facing report is generated only from the aggregate's public directory.

The benchmark can affect perceptions of models, providers, courts, litigants, and legal work. Claims are therefore governed by their publication status and supporting evidence. A preliminary one-task community result, a contributor-grade reproducible community result, and an official LegalForecast-MTD result have different evidence and language rules. No surface can silently upgrade one status into another. Official Brier scores and community rubric scores remain separate products.

Model rationales may reproduce sensitive allegations from filings. They are retained for controlled analysis and are not automatically published merely because a numerical score is public. The official public bundle favors aggregate and unit-score evidence needed for verification while excluding raw text that is unnecessary for that purpose.

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work. Any credit for public feedback or upstream software is ordinary attribution, not evidence of review, approval, or affiliation. The author will disclose any additional funding or competing interest before submission.

## References

[R1]: M. Medvedeva and P. McBride. “Legal Judgment Prediction: If You Are Going to Do It, Do It Right.” Natural Legal Language Processing Workshop, 2023. [Source](https://aclanthology.org/2023.nllp-1.9/)

[R2]: D. M. Katz, M. J. Bommarito II, and J. Blackman. “A General Approach for Predicting the Behavior of the Supreme Court of the United States.” PLOS ONE 12(4), 2017. [Source](https://doi.org/10.1371/journal.pone.0174698)

[R3]: N. Aletras, D. Tsarapatsanis, D. Preotiuc-Pietro, and V. Lampos. “Predicting Judicial Decisions of the European Court of Human Rights: A Natural Language Processing Perspective.” PeerJ Computer Science 2:e93, 2016. [Source](https://doi.org/10.7717/peerj-cs.93)

[R4]: I. Chalkidis, I. Androutsopoulos, and N. Aletras. “Neural Legal Judgment Prediction in English.” ACL, 2019. [Source](https://aclanthology.org/P19-1424/)

[R5]: H. Zhong et al. “Overview of CAIL2018: Legal Judgment Prediction Competition.” arXiv:1810.05851, 2018. [Source](https://arxiv.org/abs/1810.05851)

[R6]: J. Niklaus, I. Chalkidis, and M. Stürmer. “Swiss-Judgment-Prediction: A Multilingual Legal Judgment Prediction Benchmark.” NLLP, 2021. [Source](https://aclanthology.org/2021.nllp-1.3/)

[R7]: H. Xie, F. Steffek, J. De Faria, C. Carter, and J. Rutherford. “The CLC-UKET Dataset: Benchmarking Case Outcome Prediction for the UK Employment Tribunal.” NLLP, 2024. [Source](https://aclanthology.org/2024.nllp-1.7/)

[R8]: E. Karger et al. “ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities.” ICLR, 2025. [Source](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ea74e45a229dac70b5b63b28d8934db6-Abstract-Conference.html)

[R9]: G. W. Brier. “Verification of Forecasts Expressed in Terms of Probability.” Monthly Weather Review 78(1), 1950. [Source](https://journals.ametsoc.org/view/journals/mwre/78/1/1520-0493_1950_078_0001_vofeit_2_0_co_2.xml)

[R10]: Harvey. “Legal Agent Benchmark.” Repository and benchmark documentation. [Source](https://github.com/harveyai/harvey-labs)

[R11]: Pre/Dicta. “Litigation Predictions.” Product documentation. [Source](https://www.pre-dicta.com/)

[R12]: LegalForecastBench. “Methods, Labeling Protocol, Official Run Runbook, and Reproduce or Audit.” Repository documentation, release draft. [Source](https://github.com/johnhughes3/LegalForecastBench)
