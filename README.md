# LegalForecast-MTD

LegalForecast-MTD is a contamination-controlled benchmark of frontier models on a high-value legal task: predicting how federal judges will rule on motions to dismiss, from the same written record the judge sees. Each benchmark version is anchored to a set of model deployment dates and uses only cases decided on or after the UTC calendar date of the latest first documented external deployment among the evaluated models; for models whose served weights are frozen at that deployment, the ruling is outside the model's training record. The prediction unit is a claim-defendant pair (i.e., whether the judge granted or denied a motion to dismiss a specific claim as to a specific defendant or group of similarly situated defendants). The headline metric is micro-Brier with case-clustered confidence intervals.

## Why This Exists

Existing legal-reasoning benchmarks tend to test models on tasks a junior associate can handle: bar exam questions, contract clause classification, citation lookup, basic drafting. These tasks have objective correct answers, which is good for scoring, but they do not directly test higher-level legal judgment tasks.

Higher-value legal work is harder to benchmark because it is laden with subjective judgments. This benchmark addresses that problem by testing prediction rather than analysis: given the same written record a federal judge received, the model is asked to predict how that judge will rule — not to opine on how the motion should be decided. Prediction has objective ground truth (the judge either granted or denied the motion as to each claim and defendant) but it is still a critical task that clients pay senior lawyers to do. Partners and counsel routinely have to assess the likely outcomes of a case, or of specific motions they might file, to advise clients on what motions to pursue and whether to settle or litigate. Although prediction is distinct from objective legal reasoning, rigorously understanding the facts and law (as presented to the judge) often may be the most reliable way to predict the outcome, so my hypothesis is that performance on this benchmark could be a good proxy for models' legal reasoning ability (though that admittedly is unproven and a theory we intend to test over time). Whether or not prediction tasks are a good proxy for legal reasoning, they are themselves important and high-value tasks and training models to perform these tasks could significantly improve their practical, real-world utility to lawyers.

This benchmark focuses on federal motions to dismiss because hundreds are decided each week, which yields usable sample sizes in the weeks following any new model release. They involve a broad range of substantive legal reasoning over a self-contained written record, and they resolve to a clear binary outcome on each challenged claim against each challenged defendant.

AI models that can predict litigation outcomes well would be useful in a range of circumstances: litigation finance firms deciding whether to finance a litigation, plaintiffs' attorneys deciding whether to take a case on contingency, investors in litigation-affected instruments, and defendants facing settlement decisions. More broadly, parties often persist in zero-sum litigation because they have significantly different views of the likely outcome. Tools that help both sides form more realistic assessments could help resolve disputes earlier, on terms that better serve everyone involved.

## Approach

### Prediction unit and metric

The benchmark predicts, for each challenged claim against each challenged defendant, the probability that the claim will be dismissed in full. The prediction unit is the claim-defendant pair, not the motion as a whole. The base proper scoring metric is micro-Brier over prediction units, with confidence intervals clustered by case to account for within-motion correlation. The first benchmark cycle makes relative model comparisons only — which model forecasts best on the shared frozen record. Fitted empirical baseline rows and Brier-skill-over-informed-baseline interpretation (especially `judge_history`) are planned for a later cycle once a historical baseline corpus is frozen; see [Prior Art and Positioning](docs/prior-art-positioning.md).

### Contamination control

For a given universe of models being compared, eligible cases are those with written MTD decisions entered on or after the UTC calendar date of the latest first documented external deployment. Restricted API or Codex previews count as external deployment; later general availability, temporary suspension, or re-release does not reset the anchor. Provider-stated knowledge cutoffs are informative and usually months earlier, but they are not the eligibility anchor because their definitions and auditability vary. First external deployment is the deliberately conservative, independently observable rule, and no additional calendar-day buffer is applied. Pre-decision materials (complaint, motion, briefing, docket history) may predate the deployment; those are legitimate forecasting inputs and are made available to all models. Outcome leakage — pre-run access to a tentative ruling, oral-argument transcript, or related-case order resolving the same issue — is a hard exclusion. Models run without network access or web search.

The release-date anchor is a retrospective contamination control, not a guarantee that providers will never update an alias after release. Official runs therefore require non-null release timestamps, dated snapshot metadata in the frozen registry, and run artifacts that record the provider-served model version when the provider exposes it.

### Versioned artifact

Each benchmark run is a versioned artifact tied to a specific set of model deployments. When a new generation of frontier models ships, the benchmark ingests fresh cases — all decided on or after the new deployment anchor — and compares predictions on that cohort. The tradeoff is that the benchmark cannot run immediately on a new model (it takes time for enough eligible decisions to accumulate), and it cannot cleanly demonstrate absolute capability gains across generations because the case mix differs each version. What it does well is compare the relative capabilities of frontier models within a generation, which is the question most useful to practitioners deciding which model to rely on.

Current pilot model anchors are tracked in [MODEL_RELEASE_DATES.md](MODEL_RELEASE_DATES.md).

## How Runs Are Executed

Each official run is driven by a GitHub Actions matrix job, with one matrix cell per (model, case) pair. The matrix structure isolates failures per cell, lets runs resume without rerunning successful cells, and produces a uniform per-cell audit trail.

The official workflow keeps per-cell outputs in the durable results store under deterministic keys and defaults `resume_existing_results` to true. If a temporary provider outage, rate limit, or exhausted API-credit balance stops part of a run, replenish credentials or credits and rerun the failed jobs, or redispatch the same cycle with resume enabled; completed matching cells are reused as the canonical outputs rather than called again. Repeat-sampling is separate: `repeat_sample_case_ids` plus `repeat_count` intentionally performs multiple provider calls for a prebudgeted variance subset, while headline scores use the `repeat_index=1` row.

## Quickstart

Version: `0.1.0a1` / `v0.1.0-alpha.1`.

See the package help with:

```bash
uv run legalforecast --help
```

Run the synthetic fixture workflow:

```bash
uv run legalforecast fixture e2e --output-dir tmp/fixture-run
```

Useful outputs:

- `tmp/fixture-run/artifact-manifest.json`
- `tmp/fixture-run/artifact-index.json`
- `tmp/fixture-run/packets.jsonl`
- `tmp/fixture-run/runs.jsonl`
- `tmp/fixture-run/scores.json`
- `tmp/fixture-run/report/leaderboard.md`

Those files prove the pipeline can run end to end. They are not public benchmark results.

Before cutting a release candidate:

```bash
uv run scripts/release_check.py
```

Default checks must not require live credentials. The release check runs locked dependency sync, formatting, linting, type checking, tests, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

Tags matching `v*` run the package-publish workflow. That workflow reruns the release check, publishes the built wheel/sdist from `tmp/release-check/dist` to PyPI with trusted publishing, and attaches the wheel, sdist, and package hash file to the GitHub release. Manual dispatch can run the same workflow without publishing unless `publish` is set.

## Community Multi-Harness

The repo includes a separate non-official community multi-harness layer for comparing LegalForecastBench fixture/subset tasks, Harvey LAB tasks, and contributor adapters without weakening official benchmark boundaries.

Start with:

```bash
uv run legalforecast multiharness --help
```

Contributor docs:

- [Multi-Harness Adapter Spec](docs/multiharness-adapter-spec.md)
- [Community Submissions](docs/community-submissions.md)

Community submissions live under `community/submissions/` and are rebuilt into a separate community registry/site. They are not official LegalForecastBench results.

## CLI Shape

The package exposes one primary CLI:

```bash
uv run legalforecast <command>
```

Primary artifact stages:

```bash
uv run legalforecast discover --input docket_entries.jsonl --output candidates.jsonl
uv run legalforecast retrieve --candidates candidates.jsonl --output retrievals.jsonl --case-dev-fixture responses.jsonl
uv run legalforecast extract --documents documents.jsonl --output extracted_text.jsonl --text-output-dir tmp/text
uv run legalforecast link --retrievals retrievals.jsonl --output linked_motions.jsonl
uv run legalforecast unitize --input linked_motions.jsonl --output units.jsonl
uv run legalforecast label --input units.jsonl --output labels.jsonl
uv run legalforecast packet build --input packet_inputs.jsonl --output packets.jsonl
uv run legalforecast eval run --packets packets.jsonl --mock-output-file mock_outputs.jsonl --output runs.jsonl --accounting-output accounting.jsonl
uv run legalforecast score --runs runs.jsonl --labels labels.jsonl --output scores.json --unit-scores-output unit_scores.jsonl
uv run legalforecast report --scores scores.json --accounting accounting.jsonl --output-dir reports/
```

Production acquisition commands live under:

```bash
uv run legalforecast acquisition --help
```

Treat acquisition commands as live-credential paths; default checks must not require Case.dev, CourtListener, RECAP, PACER, or provider credentials.

## Context and Sampling Policy

Official runs enforce prompt-size comparability against the smallest evaluated model budget: each packet must fit within `context_limit - max_output_tokens` for every model in the frozen registry. Aggregate run cards report the packet token distribution by ablation, the smallest prompt-input budget, and the registry temperature settings.

Registry entries use `temperature=0` for official runs to reduce avoidable sampling variance and make prompt/context differences easier to audit. This does not make provider responses perfectly deterministic; repeat-sampling runs are used to measure residual provider-side variance.

## Public Records and Recusal

The benchmark sources only from court filings that are already public. As a practicing attorney, I reserve the right but do not assume the obligation of excluding from benchmark sets any cases with which I or any entity I am associated with may be involved.

Any discretionary recusal or conflict exclusion must be recorded in the exclusion ledger with `conflict_of_interest` as the primary reason. The public ledger entry should identify the candidate and case metadata needed for auditability, but it should not disclose privileged, confidential, or merits-sensitive details about the conflict.

## Withdrawals

If a case is later sealed, redacted, or otherwise must be removed from the public corpus, the package provides a withdrawal path that records the removal in public errata.

## Repository Map

- `legalforecast/`: Python package for ingestion, selection, unitization, labeling, evaluation, scoring, reporting, and publication artifacts.
- `examples/adapters/`: no-network fixture manifests for first-class community multi-harness adapter tracks.
- `community/submissions/`: reviewed community submission examples and future accepted metadata packages.
- `docs/`: methods, labeling and human-baseline protocols, official-run runbook, reproduction/audit guide, and community/adapter docs — start at [docs/README.md](docs/README.md).
- `tests/`: synthetic fixtures and regression coverage.
- `MODEL_RELEASE_DATES.md`: tracked pilot anchors and additional release-date candidates.

## Authorship

The "Why This Exists" section above was written personally by John J. Hughes, III. The remainder of this README and the technical documentation in [docs/](docs/README.md) are drafted and maintained with substantial assistance from AI systems (Claude, Codex, and others) working under my direction, and are reviewed on a best-effort basis. Where possible, documentation accuracy is enforced mechanically: the official-run runbook and reproduction guide are checked against the actual CLI by automated tests. Corrections are welcome as issues or pull requests.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). There is no preprint or published benchmark cycle yet.
