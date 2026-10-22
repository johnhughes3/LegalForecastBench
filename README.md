# LegalForecast-MTD

LegalForecast-MTD tests whether frontier models can forecast federal motion-to-dismiss rulings from the judge's written record. It reports claim-defendant micro-Brier scores with clustered intervals.

Model eligibility depends on the provider-reported training-data or knowledge cutoff preceding the earliest scored decision; missing or overlapping cutoffs are qualified. Known outcome leakage is excluded, and benchmark models run without web access. This reduces a defined leakage path; it does not prove zero contamination or frozen served weights.

<!-- result-publication-state: completed-cycle-1-runs -->

**First publication — October 13, 2026:** The Cycle 1 public beta reports eighteen ranked model configurations on 91 cases and 387 scored claim–defendant units. The [working paper](https://www.legalforecastbench.org/paper/) and [results](https://www.legalforecastbench.org/) present the comparison; summary experiments and the GPT-4.1 reference are reported separately.

## Start Here

[Read the methods](docs/METHODS.md) · [Reproduce or audit](docs/reproduce-or-audit.md) · [Check publication rules](docs/publication-governance.md)

## Why This Exists

Existing legal-reasoning benchmarks tend to test models on tasks a junior associate can handle: bar exam questions, contract clause classification, citation lookup, basic drafting. These tasks have objective correct answers, which is good for scoring, but they do not directly test higher-level legal judgment tasks.

Higher-value legal work is harder to benchmark because it is laden with subjective judgments. This benchmark addresses that problem by testing prediction rather than analysis: given the same written record a federal judge received, the model is asked to predict how that judge will rule — not to opine on how the motion should be decided. Prediction has objective ground truth (the judge either granted or denied the motion as to each claim and defendant) but it is still a critical task that clients pay senior lawyers to do. Partners and counsel routinely have to assess the likely outcomes of a case, or of specific motions they might file, to advise clients on what motions to pursue and whether to settle or litigate. Although prediction is distinct from objective legal reasoning, rigorously understanding the facts and law (as presented to the judge) often may be the most reliable way to predict the outcome, so my hypothesis is that performance on this benchmark could be a good proxy for models' legal reasoning ability (though that admittedly is unproven and a theory we intend to test over time). Whether or not prediction tasks are a good proxy for legal reasoning, they are themselves important and high-value tasks and training models to perform these tasks could significantly improve their practical, real-world utility to lawyers.

This benchmark focuses on federal motions to dismiss because hundreds are decided each week, which yields usable sample sizes in the weeks following any new model release. They involve a broad range of substantive legal reasoning over a self-contained written record, and they resolve to a clear binary outcome on each challenged claim against each challenged defendant.

AI models that can predict litigation outcomes well would be useful in a range of circumstances: litigation finance firms deciding whether to finance a litigation, plaintiffs' attorneys deciding whether to take a case on contingency, investors in litigation-affected instruments, and defendants facing settlement decisions. More broadly, parties often persist in zero-sum litigation because they have significantly different views of the likely outcome. Tools that help both sides form more realistic assessments could help resolve disputes earlier, on terms that better serve everyone involved.

## Approach

### Prediction unit and metric

The benchmark predicts, for each challenged claim against each challenged defendant, the probability that the claim will be dismissed in full. The prediction unit is the claim-defendant pair, not the motion as a whole. The base proper scoring metric is micro-Brier over prediction units, with confidence intervals clustered at the coarsest declared independence level: MDL family when present, otherwise related-case family when present, otherwise case. The first benchmark cycle makes relative model comparisons only — which model forecasts best on the shared frozen record. Fitted empirical baseline rows and Brier-skill-over-informed-baseline interpretation (especially `judge_history`) are planned for a later cycle once a historical baseline corpus is frozen; see the Related Work section of [docs/METHODS.md](docs/METHODS.md).

### Contamination control

Comparison eligibility is based on the model's provider-reported training-data or knowledge cutoff preceding the earliest scored decision, not on its public release date. A month-only cutoff is compared as the first day of that month. This reflects the policy clarified on September 28, 2026. Frequent model releases make waiting for a new post-release corpus impractical. We expect limited contamination under this rule, but that is a research assumption, not a measured guarantee: provider-stated knowledge cutoffs are imperfect proxies for training exposure, including later updates. Unknown or overlapping cutoffs are disclosed separately rather than treated as verified eligible comparisons.

Outcome-leaking material is excluded from forecast inputs, and models run without network access or web search. We retain cutoff sources, release dates, requested model identities, and served versions where available. See [methods](docs/METHODS.md).

### Versioned artifact

Each run is tied to a frozen cohort and model configuration. We will add fresh cohorts over time and may compare models' relative performance on old cases and cases decided after their release. Raw scores across different cohorts are not directly comparable; changes in relative performance may flag possible contamination but can also reflect case mix or serving changes.

Cutoff evidence lives in [`legalforecast/data/model_cutoffs.json`](legalforecast/data/model_cutoffs.json); model release dates and registry notes are in [docs/MODEL_RELEASE_DATES.md](docs/MODEL_RELEASE_DATES.md).

## Official Benchmark Results

The [working paper](https://www.legalforecastbench.org/paper/) reports micro-Brier and equal-case Brier scores, uncertainty, accuracy, and actual and standard-rate inference costs. The [results site](https://www.legalforecastbench.org/) provides the ranked comparison and downloadable data, with coverage and missing usage disclosed.

## Community Multi-Harness Comparisons

A separate, non-official community track for comparing agent harnesses includes accepted historical provider smoke examples. The Claude Code, Codex, Hermes, and OpenClaw baselines remain unfinished. Its contracts, evidence limits, and contributor docs live in [docs/multiharness/](docs/multiharness/README.md).

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

## How Runs Are Executed

Each official run is driven by a GitHub Actions matrix job, with one matrix cell per (model, case) pair. The matrix structure isolates failures per cell and produces a uniform per-cell audit trail.

The official workflow keeps bounded per-cell state artifacts for the protected fan-in. A rerun restores the newest valid prior state for the same cell and refuses a fresh duplicate provider call when prior state cannot be authenticated; `max_parallel` bounds concurrent cells. `repeat_count` is an explicit dispatch input but must be exactly `1` until repeated-sampling fan-in is supported. The fan-in binds the successful cells to the exact `forecast_run_id` and `forecast_run_attempt` before scoring, reporting, and publication.

## Quickstart

Package release candidate: `0.1.0a4` / `v0.1.0-alpha.4`.

See the package help with:

```bash
uv run legalforecast --help
```

Run the synthetic fixture workflow:

```bash
uv run legalforecast run issue-fixture --output-dir tmp/fixture-run
```

Useful outputs:

- `tmp/fixture-run/release/forecast-release.json`
- `tmp/fixture-run/release/labels-release.json`
- `tmp/fixture-run/release/packets/`
- `tmp/fixture-run/release/prompts/`
- `tmp/fixture-run/model-registry.json`

Those files prove the pipeline can run end to end. They are not public benchmark results.

Before cutting a release candidate:

```bash
uv run scripts/release_check.py
```

Default checks must not require live credentials. The release check runs locked dependency sync, formatting, linting, type checking, tests, CLI smokes, fixture E2E, no-network adapter smokes, package build, package hashes, and installed wheel/sdist smokes.

Tags matching `v*` run the package-publish workflow. That workflow reruns the release check, publishes the built wheel/sdist from `tmp/release-check/dist` to PyPI with trusted publishing, and attaches the wheel, sdist, and package hash file to the GitHub release. Publishing is tag-only; the workflow cannot be dispatched manually from an arbitrary branch.

The protected fan-in workflow can also publish an official result as an immutable revision of a manually gated Hugging Face Dataset; that path is built but not yet used. See [Hugging Face benchmark publication](docs/hugging-face-publication.md).

## CLI Shape

The package exposes one primary CLI, `uv run legalforecast <command>`. The public artifact commands are `run issue-fixture`, `release validate`, `manifest validate`, `score`, and `report`; [Reproduce or audit](docs/reproduce-or-audit.md) shows each with its full arguments.

Corpus construction and acquisition are private operations in the companion LegalForecastCorpus repository. The public package consumes already-issued releases and locked run manifests.

## Context and Sampling Policy

Official runs enforce prompt-size comparability against the smallest evaluated model budget: each packet must fit within `context_limit - max_output_tokens` for every model in the frozen registry. Aggregate run cards report the packet token distribution by ablation, the smallest prompt-input budget, and the provider-default sampling policy.

Live provider requests omit `temperature`, `top_p`, and equivalent controls, so each provider supplies its own default sampling settings. The legacy registry values remain only as provenance for already-frozen registry bytes; they are not sent to providers and do not configure the run. Provider responses are therefore not assumed to be perfectly deterministic, and repeat-sampling runs measure residual provider-side variance.

## Public Records and Recusal

The benchmark sources only from court filings that are already public. As a practicing attorney, I reserve the right but do not assume the obligation of excluding from benchmark sets any cases with which I or any entity I am associated with may be involved.

Any discretionary recusal or conflict exclusion must be recorded in the exclusion ledger with `conflict_of_interest` as the primary reason. The public ledger entry should identify the candidate and case metadata needed for auditability, but it should not disclose privileged, confidential, or merits-sensitive details about the conflict.

## Withdrawals

If a case is later sealed, redacted, or otherwise must be removed from the public corpus, the package provides a withdrawal path that records the removal in public errata.

## Repository Map

- `legalforecast/`: Python package for public release validation, manifest/run execution, scoring, reporting, and publication, plus community multi-harness tooling.
- `examples/adapters/`, `community/submissions/`: adapter fixtures and submission examples for the [community multi-harness track](docs/multiharness/README.md).
- `docs/`: methods, reproduction/audit guide, publication rules, release contracts, papers, and the multi-harness docs — start at [docs/README.md](docs/README.md). Corpus construction and acquisition live in the companion LegalForecastCorpus repository.
- `tests/`: synthetic fixtures and regression coverage.
- `scripts/`: release checks, deterministic fixture input preparation, and provider/runtime validation utilities.
- `model_registries/`: frozen evaluation registries and public release metadata. Locked run manifests are issued release inputs in official storage, not files in this tree.
- `infra/`: Terraform roots for the retained official evaluation IAM boundary and bootstrap trust anchor.

## Authorship

The "Why This Exists" section above was written personally by John J. Hughes, III. The remainder of this README and the technical documentation in [docs/](docs/README.md) are drafted and maintained with substantial assistance from AI systems (Claude, Codex, and others) working under my direction, and are reviewed on a best-effort basis. Where possible, documentation accuracy is enforced mechanically: the reproduction guide is checked against the actual CLI by automated tests. Corrections are welcome as issues or pull requests.

## License

Code: Apache License 2.0. See [LICENSE](LICENSE).

Benchmark data (published results, exports, and the site's data downloads): Creative Commons Attribution 4.0 International (CC BY 4.0). See [LICENSE-DATA](LICENSE-DATA).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). Please cite the [working paper](https://www.legalforecastbench.org/paper/).
