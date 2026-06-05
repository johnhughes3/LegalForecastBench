# LegalForecast-MTD

LegalForecast-MTD is a contamination-controlled benchmark of frontier models on a high-value legal task: predicting how federal judges will rule on motions to dismiss, from the same written record the judge sees. Each benchmark version is anchored to a set of model release dates and uses only cases decided after the latest model release being evaluated, so there's no chance that any model in a given run was contaminated by seeing the judge's actual ruling during its training. The prediction unit is a claim-defendant pair (i.e., whether the judge granted or denied a motion to dismiss a specific claim as to a specific defendant or group of similarly situated defendants). The headline metric is micro-Brier with case-clustered confidence intervals.

## Why This Exists

Existing legal-reasoning benchmarks tend to test models on tasks a junior associate can handle: bar exam questions, contract clause classification, citation lookup, basic drafting. These tasks have objective correct answers, which is good for scoring — but frontier models have largely saturated them, and the gaps they reveal between current models are modest. The current generation of models is already demonstrating capabilities in the legal context far beyond what existing legal benchmarks are testing.

Higher-value legal work is harder to benchmark because it is laden with subjective judgments. This benchmark addresses that problem by testing prediction rather than analysis: given the same written record a federal judge received, the model is asked to predict how that judge will rule — not to opine on how the motion should be decided. Prediction has objective ground truth (the judge either granted or denied the motion as to each claim and defendant) but it is still a critical task that clients pay senior lawyers to do. Partners and counsel routinely have to assess the likely outcomes of a case, or of specific motions they might file, to advise clients on what motions to pursue and whether to settle or litigate. Although prediction is distinct from objective legal reasoning, rigorously understanding the facts and law (as presented to the judge) is the most reliable way to predict the outcome — so performance on this benchmark should proxy models' legal reasoning ability.

This benchmark focuses on federal motions to dismiss because hundreds are decided each week, which yields usable sample sizes in the weeks following any new model release. They involve a broad range of substantive legal reasoning over a self-contained written record, and they resolve to a clear binary outcome on each challenged claim against each challenged defendant.

AI models that can predict litigation outcomes well would be useful in a range of circumstances: litigation finance firms deciding whether to finance a litigation, plaintiffs' attorneys deciding whether to take a case on contingency, investors in litigation-affected instruments, and defendants facing settlement decisions. More broadly, parties often persist in zero-sum litigation because they have significantly different views of the likely outcome. Tools that help both sides form more realistic assessments could help resolve disputes earlier, on terms that better serve everyone involved.

## Approach

### Prediction unit and metric

The benchmark predicts, for each challenged claim against each challenged defendant, the probability that the claim will be dismissed in full. The prediction unit is the claim-defendant pair, not the motion as a whole. The headline metric is micro-Brier over prediction units, with confidence intervals clustered by case to account for within-motion correlation.

### Contamination control

For a given universe of model releases being compared, eligible cases are those with written MTD decisions entered after the latest release. Pre-decision materials (complaint, motion, briefing, docket history) may predate the release; those are legitimate forecasting inputs and are made available to all models. Outcome leakage — pre-run access to a tentative ruling, oral-argument transcript, or related-case order resolving the same issue — is a hard exclusion. Models run without network access or web search.

### Versioned artifact

Each benchmark run is a versioned artifact tied to a specific set of model releases. When a new generation of frontier models ships, the benchmark ingests fresh cases — all decided after the new releases — and compares predictions on that cohort. The tradeoff is that the benchmark cannot run immediately on a new model (it takes time for enough post-release decisions to accumulate), and it cannot cleanly demonstrate absolute capability gains across generations because the case mix differs each version. What it does well is compare the relative capabilities of frontier models within a generation, which is the question most useful to practitioners deciding which model to rely on.

Release-date anchors for current frontier models are tracked in [MODEL_RELEASE_DATES.md](MODEL_RELEASE_DATES.md).

### Pilot

A pilot run has scored Gemini Flash 3, Claude Sonnet 4.5, and GPT-5.5-mini on twelve cases to validate the end-to-end infrastructure. The pilot is too small to support claims about relative model capability and is not a published benchmark result; it confirms that ingestion, unitization, packet construction, model invocation, and scoring run together on real cases. We are seeking feedback from researchers experienced with benchmark design before incurring the cost of a full model run.

## How Runs Are Executed

Each official run is driven by a GitHub Actions matrix job, with one matrix cell per (model, case) pair. The matrix structure isolates failures per cell, lets runs resume without rerunning successful cells, and produces a uniform per-cell audit trail.

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

Default checks must not require live credentials.

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

## Public Records and Recusal

The benchmark sources only from court filings that are already public. As a practicing attorney, I reserve the right but do not assume the obligation of excluding from benchmark sets any cases with which I or any entity I am associated with may be involved.

## Withdrawals

If a case is later sealed, redacted, or otherwise must be removed from the public corpus, the package provides a withdrawal path that records the removal in public errata.

## Repository Map

- `legalforecast/`: Python package for ingestion, selection, unitization, labeling, evaluation, scoring, reporting, and publication artifacts.
- `tests/`: synthetic fixtures and regression coverage.
- `MODEL_RELEASE_DATES.md`: tracked frontier-model release anchors.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). There is no preprint or published benchmark cycle yet.
