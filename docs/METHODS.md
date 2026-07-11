# LegalForecastBench Methods

## Construct And Intended Use

LegalForecastBench measures whether a model can predict federal motion-to-dismiss outcomes from a frozen written pre-decision record. The prediction unit is a challenged claim against a defendant or defendant group, and the target is the probability that the unit will be fully dismissed in the first written disposition of the target motion.

Published predictions are retrospective research artifacts about matters already decided before scoring. They are not legal advice and are not a prediction service for pending litigation.

## Frozen Inputs And Leakage Controls

Each run uses a cycle ID, run-input manifest, locked labels, model registry, model-visible packet hashes, prompt and scorer artifacts, and a committed hash-only freeze record. The protected workflow validates the downloaded manifest, labels hash, registry, packet rows, model keys, requested ablations, and projected cost before provider fan-out.

Model-visible docket and filing text is screened for target-outcome leakage before packet construction. Exclusions and redactions are recorded in acquisition and audit artifacts. Packets exclude the target written disposition.

## Model Execution And Recovery

Provider calls run as isolated case, ablation, model, and repeat cells. Complete results are published to the durable results store with identity metadata that includes the packet hash and solver/registry contract. Resume mode reuses only complete matching results. Failed cells retain logs but do not become score records.

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

## Limitations

Temperature and fixed prompts reduce avoidable variation but do not guarantee deterministic provider behavior. Within-cycle comparisons still depend on case mix, legal subject matter, packet completeness, model serving changes, and the number of independent clusters. Cross-cycle comparisons require caution because the underlying cases and release anchors differ.

See [labeling-protocol.md](labeling-protocol.md), [official-run-runbook.md](official-run-runbook.md), and [reproduce-or-audit.md](reproduce-or-audit.md) for the operational contracts.
