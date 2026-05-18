# LegalForecast-MTD

LegalForecast-MTD is a pre-data alpha for a public benchmark of model forecasts
on federal motion-to-dismiss outcomes. The benchmark target is narrow: predict
claim-defendant outcomes from the same pre-decision docket materials a model
would have seen before the court ruled.

This repository is the benchmark machinery, not a completed benchmark corpus.
It has typed pipeline stages, frozen artifact formats, synthetic fixture runs,
scoring, reporting, no-paid defaults, and release checks. It does not yet publish
public cases, human labels, model scores, or an official leaderboard.

## Why This Exists

I am a practicing lawyer, and my view is that the legal profession is
systematically underestimating what current AI models can do. Existing
legal-reasoning benchmarks tend to focus on tasks a junior associate could
handle: bar-style questions, contract clause classification, citation lookup.
Those tasks have unambiguous right answers, which is good for scoring, but as
frontier models have improved the benchmarks have approached saturation, and
the gaps they reveal between top systems are small and shrinking.

The reason most legal benchmarks stay at the junior level is that higher-stakes
legal work is laden with subjectivity and value judgments, which is hard to
score. This benchmark takes a different route. It asks models to *predict* how
a real federal judge ruled on a real motion, given the same record the judge
saw. Prediction has an objective ground truth (the judge either granted or
denied the motion) but sits closer to the work clients actually pay senior
lawyers for: assessing the likely outcome of a dispute, not declaring what the
outcome ought to be.

Federal motions to dismiss are the starting point because hundreds are decided
each week. Even after excluding cases that could create training-data
contamination (oral argument, written questions to the parties, tentative
rulings, and similar pre-ruling signals from the judge), there is more than
enough volume to build a comparison set within a week or two of a new model
release.

A reliable prediction tool would also be useful in its own right. Litigation
persists in large part because parties disagree about its likely outcome;
well-calibrated probability estimates would make settlement easier and the
system less wasteful. The same capability matters to litigation funders,
plaintiffs' attorneys deciding whether to take a case, and investors in
litigation-affected instruments.

I have no formal AI background, and this work is still in development. The
current version is being shared mainly to get feedback from researchers with
experience building benchmarks.

## What Exists Today

- A deterministic no-network fixture pipeline.
- Candidate, retrieval, extraction, unitization, labeling, packet, run, score,
  and report schemas.
- Micro-Brier scoring, calibration summaries, cost/tool accounting, and
  leaderboard rendering.
- Preregistration, run-card, model-card, and result-tier artifacts.
- A guarded acquisition pipeline for the future live corpus.
- CI-equivalent local release checks.

## What Does Not Exist Yet

- No public case corpus.
- No audited public labels.
- No real model submissions.
- No canonical leaderboard.
- No claim that the synthetic fixture results say anything about model quality.

The main blocker is live packet acquisition. Case.dev discovery is useful, but
the project still needs a reliable route for docket entries and source
documents before an official cycle can run.

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

Those files prove the pipeline can run end to end. They are not public
benchmark results.

Before cutting a release candidate:

```bash
uv run scripts/alpha_release_check.py
```

Default checks must not require live credentials.

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

See [docs/acquisition.md](docs/acquisition.md) before running anything that can
touch live Case.dev, CourtListener, RECAP, PACER, or provider credentials.

## Documentation

The root README is the public quickstart. The full map lives in the
[documentation index](docs/README.md). Start with:

- [Methodology](docs/methodology.md) for task design, scoring, and validity.
- [Acquisition status](docs/acquisition.md) for live-data blockers and no-paid defaults.
- [Result tiers](docs/result_tiers.md) for what can and cannot be called canonical.
- [Ethics and legal-risk note](docs/ethics.md) for intended use, privacy, and takedown framing.

Generated smoke reports and internal release-gate notes are not tracked as
public docs. If a command writes an exploratory report, put it under `tmp/`.

## Repository Map

- `legalforecast/`: Python package for ingestion, selection, unitization,
  labeling, evaluation, scoring, reporting, and publication artifacts.
- `docs/`: public methodology and protocol references.
- `protocols/`: preregistration templates and cycle protocol examples.
- `manifests/`: frozen manifest examples.
- `tests/`: synthetic fixtures and regression coverage.
- `docker/docket_tool/`: sandboxed docket-tool container scaffold.

## Result Claims

Use the result tiers in [docs/result_tiers.md](docs/result_tiers.md). Only
`official` results belong in a canonical leaderboard. Synthetic fixture outputs
are `alpha-non-canonical`; self-reported external runs remain community-tier
unless the policy's reproduction and audit requirements are met.

## Feedback

High-value alpha feedback is concrete:

- a command that fails from a clean checkout;
- a stale or contradictory document reference;
- a fixture artifact missing provenance needed for audit;
- a result-tier claim that sounds more official than it is;
- a security, cost, or legal-record handling issue.

Please file issues for feedback that could affect reproducibility, result-tier
claims, security, cost, or legal-record handling, and avoid including secrets,
account identifiers, sealed filings, or private source-document text in public
reports.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). There is no preprint or
published benchmark cycle yet.
