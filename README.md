# LegalForecast-MTD

LegalForecast-MTD tests whether frontier models can forecast federal motion-to-dismiss rulings from the judge's written record. It reports claim-defendant micro-Brier scores with clustered intervals.

Eligible decisions follow the models' latest first external deployment; known outcome leakage is excluded, and official models run without web access. This reduces a defined leakage path; it does not prove zero contamination or frozen served weights.

<!-- result-publication-state: pre-publication -->

**Current status — 2026-07-17:** No official or community benchmark score is published yet. Official LegalForecast-MTD Cycle 1 and non-official Community Harness Comparisons remain in preparation. After validation, publication owners replace this line and add canonical links within 24 hours.

## Start Here

[Read the methods](docs/METHODS.md) · [Reproduce or audit](docs/reproduce-or-audit.md) · [Check publication rules](docs/publication-governance.md) · [Track execution in issue #203](https://github.com/johnhughes3/LegalForecastBench/issues/203)

## Why This Exists

Existing legal-reasoning benchmarks tend to test models on tasks a junior associate can handle: bar exam questions, contract clause classification, citation lookup, basic drafting. These tasks have objective correct answers, which is good for scoring, but they do not directly test higher-level legal judgment tasks.

Higher-value legal work is harder to benchmark because it is laden with subjective judgments. This benchmark addresses that problem by testing prediction rather than analysis: given the same written record a federal judge received, the model is asked to predict how that judge will rule — not to opine on how the motion should be decided. Prediction has objective ground truth (the judge either granted or denied the motion as to each claim and defendant) but it is still a critical task that clients pay senior lawyers to do. Partners and counsel routinely have to assess the likely outcomes of a case, or of specific motions they might file, to advise clients on what motions to pursue and whether to settle or litigate. Although prediction is distinct from objective legal reasoning, rigorously understanding the facts and law (as presented to the judge) often may be the most reliable way to predict the outcome, so my hypothesis is that performance on this benchmark could be a good proxy for models' legal reasoning ability (though that admittedly is unproven and a theory we intend to test over time). Whether or not prediction tasks are a good proxy for legal reasoning, they are themselves important and high-value tasks and training models to perform these tasks could significantly improve their practical, real-world utility to lawyers.

This benchmark focuses on federal motions to dismiss because hundreds are decided each week, which yields usable sample sizes in the weeks following any new model release. They involve a broad range of substantive legal reasoning over a self-contained written record, and they resolve to a clear binary outcome on each challenged claim against each challenged defendant.

AI models that can predict litigation outcomes well would be useful in a range of circumstances: litigation finance firms deciding whether to finance a litigation, plaintiffs' attorneys deciding whether to take a case on contingency, investors in litigation-affected instruments, and defendants facing settlement decisions. More broadly, parties often persist in zero-sum litigation because they have significantly different views of the likely outcome. Tools that help both sides form more realistic assessments could help resolve disputes earlier, on terms that better serve everyone involved.

## Approach

### Prediction unit and metric

The benchmark predicts, for each challenged claim against each challenged defendant, the probability that the claim will be dismissed in full. The prediction unit is the claim-defendant pair, not the motion as a whole. The base proper scoring metric is micro-Brier over prediction units, with confidence intervals clustered at the coarsest declared independence level: MDL family when present, otherwise related-case family when present, otherwise case. The first benchmark cycle makes relative model comparisons only — which model forecasts best on the shared frozen record. Fitted empirical baseline rows and Brier-skill-over-informed-baseline interpretation (especially `judge_history`) are planned for a later cycle once a historical baseline corpus is frozen; see the Related Work section of [docs/METHODS.md](docs/METHODS.md).

### Contamination control

For a given universe of models being compared, eligible cases are those with written MTD decisions entered on or after the UTC calendar date of the latest first documented external deployment. Restricted API or Codex previews count as external deployment; later general availability, temporary suspension, or re-release does not reset the anchor. Provider-stated knowledge cutoffs are informative and usually months earlier, but they are not the eligibility anchor because their definitions and auditability vary. First external deployment is the deliberately conservative, independently observable rule, and no additional calendar-day buffer is applied. Pre-decision materials (complaint, motion, briefing, docket history) may predate the deployment; those are legitimate forecasting inputs and are made available to all models. Outcome leakage — pre-run access to a tentative ruling, oral-argument transcript, or related-case order resolving the same issue — is a hard exclusion. Models run without network access or web search.

The release-date anchor is a retrospective contamination control, not a guarantee that providers will never update an alias after release. Official runs therefore require non-null release timestamps, dated snapshot metadata in the frozen registry, and run artifacts that record the provider-served model version when the provider exposes it.

### Versioned artifact

Each benchmark run is a versioned artifact tied to a specific set of model deployments. When a new generation of frontier models ships, the benchmark ingests fresh cases — all decided on or after the new deployment anchor — and compares predictions on that cohort. The tradeoff is that the benchmark cannot run immediately on a new model (it takes time for enough eligible decisions to accumulate), and it cannot cleanly demonstrate absolute capability gains across generations because the case mix differs each version. What it does well is compare the relative capabilities of frontier models within a generation, which is the question most useful to practitioners deciding which model to rely on.

Current pilot model anchors are tracked in [MODEL_RELEASE_DATES.md](MODEL_RELEASE_DATES.md).

## Official Benchmark Results

**No official result is claimed by this README revision.** Its reserved label is **Official LegalForecast-MTD Cycle 1 result**. Publication adds the audited report, leaderboard, and evidence; official and community scores are never ranked together.

## Preliminary Community Result

**No validated result is linked yet.** Its reserved label is **Preliminary — one task pair, operator-run, not independently reproducible**. This non-official tier does not close issue #49.

## Reproducible Community Comparisons

**No row is accepted yet.** Its reserved label is **Reproducible community result — contributor-grade, non-official**. Contributor path: [adapter spec](docs/multiharness-adapter-spec.md) · [contributor guide](docs/community-contributor-guide.md) · [submission guide](docs/community-submissions.md).

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

## How Runs Are Executed

Each official run is driven by a GitHub Actions matrix job, with one matrix cell per (model, case) pair. The matrix structure isolates failures per cell and produces a uniform per-cell audit trail.

The official workflow keeps bounded per-cell state artifacts for the protected fan-in. A rerun restores the newest valid prior state for the same cell and refuses a fresh duplicate provider call when prior state cannot be authenticated; `max_parallel` bounds concurrent cells. `repeat_count` is an explicit dispatch input but must be exactly `1` until repeated-sampling fan-in is supported. The fan-in binds the successful cells to the exact `forecast_run_id` and `forecast_run_attempt` before scoring, reporting, and publication.

## Quickstart

Version: `0.1.0a3` / `v0.1.0-alpha.3`.

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

Default checks must not require live credentials. The release check runs locked dependency sync, formatting, linting, type checking, tests, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

Tags matching `v*` run the package-publish workflow. That workflow reruns the release check, publishes the built wheel/sdist from `tmp/release-check/dist` to PyPI with trusted publishing, and attaches the wheel, sdist, and package hash file to the GitHub release. Publishing is tag-only; the workflow cannot be dispatched manually from an arbitrary branch.

Official benchmark cycles can also be published as immutable revisions of a public, manually gated Hugging Face Dataset through the protected fan-in workflow. See [Hugging Face benchmark publication](docs/hugging-face-publication.md) for versioning, access terms, one-time setup, and the distinction between HF distribution and the benchmark's authoritative evidence.

## Community Multi-Harness Contributor Details

The repo includes a separate non-official community multi-harness layer for comparing LegalForecastBench fixture/subset tasks, Harvey LAB tasks, and contributor adapters without weakening official benchmark boundaries.

Start with:

```bash
uv run legalforecast multiharness --help
```

Contributor docs:

- [Community Contributor Guide](docs/community-contributor-guide.md)
- [Multi-Harness Adapter Spec](docs/multiharness-adapter-spec.md)
- [Community Submissions](docs/community-submissions.md)

Community submissions live under `community/submissions/` and are rebuilt into a separate community registry/site. They are not official LegalForecastBench results.

## CLI Shape

The package exposes one primary CLI:

```bash
uv run legalforecast <command>
```

Public artifact commands:

```bash
uv run legalforecast run issue-fixture --output-dir tmp/fixture-run
uv run legalforecast release validate \
  --forecast tmp/fixture-run/release/forecast-release.json \
  --labels tmp/fixture-run/release/labels-release.json \
  --artifact-root tmp/fixture-run/release
uv run legalforecast score \
  --runs <run-records.jsonl> \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <release-root> \
  --manifest <run-manifest.json> \
  --model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output scores.json \
  --unit-scores-output unit_scores.jsonl
uv run legalforecast report \
  --scores scores.json \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <release-root> \
  --manifest <run-manifest.json> \
  --frozen-model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output-dir reports/
```

Corpus construction and acquisition are private operations in the companion
LegalForecastCorpus repository. The public package consumes already-issued
releases and locked run manifests.

## Context and Sampling Policy

Official runs enforce prompt-size comparability against the smallest evaluated model budget: each packet must fit within `context_limit - max_output_tokens` for every model in the frozen registry. Aggregate run cards report the packet token distribution by ablation, the smallest prompt-input budget, and the provider-default sampling policy.

Live provider requests omit `temperature`, `top_p`, and equivalent controls, so each provider supplies its own default sampling settings. The legacy registry values remain only as provenance for already-frozen registry bytes; they are not sent to providers and do not configure the run. Provider responses are therefore not assumed to be perfectly deterministic, and repeat-sampling runs measure residual provider-side variance.

## Public Records and Recusal

The benchmark sources only from court filings that are already public. As a practicing attorney, I reserve the right but do not assume the obligation of excluding from benchmark sets any cases with which I or any entity I am associated with may be involved.

Any discretionary recusal or conflict exclusion must be recorded in the exclusion ledger with `conflict_of_interest` as the primary reason. The public ledger entry should identify the candidate and case metadata needed for auditability, but it should not disclose privileged, confidential, or merits-sensitive details about the conflict.

## Withdrawals

If a case is later sealed, redacted, or otherwise must be removed from the public corpus, the package provides a withdrawal path that records the removal in public errata.

## Repository Map

- `legalforecast/`: Python package for public release validation, manifest/run execution, scoring, reporting, publication, and community multi-harness tooling.
- `examples/adapters/`: no-network fixture manifests for first-class community multi-harness adapter tracks.
- `community/submissions/`: reviewed community submission examples and future accepted metadata packages.
- `docs/`: methods, official-run runbook, reproduction/audit guide, schema contracts, and community/adapter docs — start at [docs/README.md](docs/README.md). Corpus construction and acquisition live in the companion LegalForecastCorpus repository.
- `tests/`: synthetic fixtures and regression coverage.
- `scripts/`: release checks, deterministic fixture input preparation, and offline adapter probes.
- `manifests/`: public run manifests and other release inputs.
- `model_registries/`: frozen evaluation registries and public release metadata.
- `infra/`: Terraform roots for the retained official evaluation IAM boundary and bootstrap trust anchor.
- `MODEL_RELEASE_DATES.md`: tracked pilot anchors and additional release-date candidates.

## Authorship

The "Why This Exists" section above was written personally by John J. Hughes, III. The remainder of this README and the technical documentation in [docs/](docs/README.md) are drafted and maintained with substantial assistance from AI systems (Claude, Codex, and others) working under my direction, and are reviewed on a best-effort basis. Where possible, documentation accuracy is enforced mechanically: the official-run runbook and reproduction guide are checked against the actual CLI by automated tests. Corrections are welcome as issues or pull requests.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). Before citing a result, follow the dated status and canonical evidence links at the top of this README; this revision claims no released benchmark result.
