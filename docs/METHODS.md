# LegalForecastBench Methods

## Construct And Intended Use

LegalForecastBench measures whether a model can predict federal motion-to-dismiss outcomes from a frozen written pre-decision record. The prediction unit is a challenged claim against a defendant or defendant group, and the target is the probability that the unit will be fully dismissed in the first written disposition of the target motion.

Published predictions are retrospective research artifacts about matters already decided before scoring. They are not legal advice and are not a prediction service for pending litigation.

## Frozen Inputs And Leakage Controls

Each run uses a cycle ID, run-input manifest, locked labels, model registry, model-visible packet hashes, prompt and scorer artifacts, and a committed hash-only freeze record. The protected workflow validates the downloaded manifest, labels hash, registry, packet rows, model keys, requested ablations, and projected cost before provider fan-out.

Model-visible docket and filing text is screened for target-outcome leakage before packet construction. Exclusions and redactions are recorded in acquisition and audit artifacts. Packets exclude the target written disposition.

## Model Execution And Recovery

Provider calls run as isolated case, ablation, model, and repeat cells. Complete results are published to the durable results store with identity metadata that includes the packet hash and solver/registry contract. Resume mode reuses only complete matching results. Failed cells retain logs but do not become score records.

Labeling and evaluation calls share a remotely atomic cycle ledger for each provider and public account alias. Before the first paid labeling call, the provider-cycle-caps artifact fixes the account ceiling, maximum billable attempts per cell, failure threshold and window, and exact authority-table identity. Labeling consumes that commitment directly; the later frozen execution policy must reproduce it and bind the exact pre-labeling artifact hash rather than originate or raise any limit. Every HTTP attempt reserves its conservative maximum immediately before transport. A provider or transport failure for which billed usage cannot be determined retains that reservation until immutable provider usage records reconcile it. The shared windowed breaker counts those provider or transport failures and prevents new calls after its threshold is reached; an application-level labeling-schema rejection after provider usage was successfully recorded does not by itself make the remote usage ambiguous or increment that breaker.

This ledger is an accidental-overspend control, not a privilege-enforced spending boundary: the same job that checks the ledger also holds authority to call the provider, so compromised or deliberately altered job code could bypass it. A deployment that requires a literally rejecting boundary must move the raw provider credential behind a separately administered capped gateway or proxy and let evaluation jobs hold only scoped gateway authority. That is the documented upgrade path, not a stronger claim about the Cycle 1 design.

Official prompts request a probability and short rationale for every prediction unit. Parsing is fail-closed for malformed structures, and required units without valid probabilities are handled by the documented parser/scorer defaults rather than silently dropped.

## Metrics And Inference

The headline metric is micro-Brier over scored prediction units. Reports also include calibration, log loss, case- and family-capped sensitivity metrics, accounting, refusal and invalid-output rates, and paired differences.

Paired bootstrap resampling uses the coarsest declared independence cluster: MDL family when present, otherwise related-case family when present, otherwise case. Exact bootstrap ties receive half credit in pairwise win probabilities. When the independent-cluster count is below the configured threshold, reports retain observed ranks but suppress uncertainty group assignments and publish a small-cluster warning.

The `full_packet` headline analysis is paired with `metadata_only` unless the operator explicitly requests a single-ablation diagnostic. Ablation reports publish the paired micro-Brier difference, confidence interval, and probability that the record-bearing packet performs better.

Fitted statistical baselines remain in paired inference and public comparison artifacts, but they are labeled as baseline rows and ranked separately from evaluated models. The best-model anchor and model differences are computed among evaluated-model rows only. A cycle without a frozen historical baseline corpus must explicitly use the no-baseline override, which is recorded in the run card.

## Public And Private Artifacts

Aggregation produces a public directory and a private debug directory. Public outputs include score summaries, unit scores, leaderboard formats, cycle-power diagnostics, artifact hashes, and run cards. Publication guardrails reject secret-looking or private material from public paths. Locked labels, raw provider material, restricted source bytes, and private operational records remain outside the public site.

The static official site renderer accepts only the public aggregate directory. Public reproduction verifies hashes and score arithmetic; deeper source and label review is an audit workflow because the project cannot redistribute every underlying court document or private record.

## Withdrawals And Corrections

Withdrawal handling records private operational detail separately from public-safe errata. A corrected publication is produced as a superseding aggregate rather than by silently changing an already published bundle.

## Related Work

LegalForecast-MTD is not the first effort to predict litigation outcomes or motions to dismiss. Commercial products exist: [Pre/Dicta](https://www.pre-dicta.com/) markets motion-level federal litigation prediction, reportedly from judge, party, and case metadata rather than the briefs themselves — evidence that metadata-only prediction is commercially pursued, and the reason fitted metadata and judge-history baselines are planned as central comparisons once a historical baseline corpus is frozen.

Legal judgment prediction is a mature research area, including [Katz, Bommarito, and Blackman on SCOTUS prediction](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0174698), [Aletras et al.](https://discovery.ucl.ac.uk/id/eprint/1522370/) and [Chalkidis et al.](https://aclanthology.org/P19-1424/) on ECtHR decisions, [CAIL2018](https://arxiv.org/abs/1810.05851), [Swiss-Judgment-Prediction](https://aclanthology.org/2021.nllp-1.3/), and [CLC-UKET](https://aclanthology.org/2024.nllp-1.7/). Many of those setups predict outcomes from court-authored fact sections or judgment texts; [Medvedeva, Wieling, and Vols](https://d-nb.info/1257127764/34) emphasize the difference between that and prediction in a realistic professional setting. This benchmark stays on the realistic side of the line: the model sees the pre-decision litigation record, never the judge's later explanation. CLC-UKET is the closest legal analogue and includes human predictions as a reference; [ForecastBench](https://openreview.net/forum?id=lfPkGWXLLf) is the closest design analogue outside law (post-cutoff evaluation, Brier scoring), whose contamination-resistant pattern this benchmark applies to court records.

Harvey LAB is a complementary benchmark family — long-horizon legal work-product tasks scored against expert-written criteria — rather than probabilistic outcome forecasting. The two measure different things: LAB scores deliverable quality; LegalForecast-MTD scores calibrated prediction against objective ground truth, penalizing both false confidence and missed probability mass.

The defensible positioning is therefore narrow: an open, contamination-controlled benchmark for probabilistic, claim-defendant-level MTD forecasting from the pre-decision record.

## Human Baseline

The first cycle includes no human-baseline arm: no reviewers were recruited, no human forecasts were collected, and no model-vs-human comparison is part of its leaderboard. A pre-specified protocol for a future human-forecaster arm — recruitment strata, blinding, per-stratum sample-size floors, compensation rules, and author exclusion — is preserved in git history and can be inspected with `git show 444022a^:docs/human-baseline-protocol.md`. It will be republished with any cycle that runs a human arm, so the design verifiably predates the data.

## Limitations

Temperature and fixed prompts reduce avoidable variation but do not guarantee deterministic provider behavior. Within-cycle comparisons still depend on case mix, legal subject matter, packet completeness, model serving changes, and the number of independent clusters. Cross-cycle comparisons require caution because the underlying cases and release anchors differ. Performance on this benchmark is a hypothesized proxy for legal reasoning, not a direct measure of it.

See [labeling-protocol.md](labeling-protocol.md), [official-run-runbook.md](official-run-runbook.md), and [reproduce-or-audit.md](reproduce-or-audit.md) for the operational contracts.
