# LegalForecast-MTD

LegalForecast-MTD is a pre-data alpha for a public benchmark of model forecasts
on federal motion-to-dismiss outcomes. The benchmark target is narrow: predict
claim-defendant outcomes from the same pre-decision docket materials a model
would have seen before the court ruled.

This repository is the benchmark machinery, not a completed benchmark corpus.
It has typed pipeline stages, frozen artifact formats, synthetic fixture runs,
scoring, reporting, no-paid defaults, and release checks. It does not yet publish
public cases, human labels, model scores, or an official leaderboard.

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

Install with `uv` and run the local checks:

```bash
uv sync
uv run legalforecast --help
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
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

## CLI Shape

The package exposes one CLI:

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
uv run legalforecast eval run --packets packets.jsonl --mock-output mock_outputs.jsonl --output runs.jsonl --accounting-output accounting.jsonl
uv run legalforecast score --runs runs.jsonl --labels labels.jsonl --output scores.jsonl --unit-scores-output unit_scores.jsonl
uv run legalforecast report --scores scores.jsonl --accounting accounting.jsonl --output-dir reports/
```

Production acquisition commands live under:

```bash
uv run legalforecast acquisition --help
```

See [docs/acquisition.md](docs/acquisition.md) before running anything that can
touch live Case.dev, CourtListener, RECAP, PACER, or provider credentials.

## Documentation

The public docs are intentionally small:

- [Documentation index](docs/README.md)
- [Methodology](docs/methodology.md)
- [Data card](docs/data_card.md)
- [Acquisition status](docs/acquisition.md)
- [Result tiers](docs/result_tiers.md)
- [Ethics and legal-risk note](docs/ethics.md)
- [Preregistration](docs/preregistration.md)
- [Outcome rules appendix](docs/outcome_rules_appendix.md)

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

## Release Check

Before cutting a release candidate:

```bash
uv run scripts/alpha_release_check.py
```

That command runs dependency sync, formatting, lint, pyright, pytest, CLI help,
fixture E2E, package build, installed wheel smoke, installed wheel fixture E2E,
installed sdist smoke, and artifact validation.

## Result Claims

Use the result tiers in [docs/result_tiers.md](docs/result_tiers.md).

- `alpha-non-canonical`: synthetic or release-readiness artifacts.
- `community-unverified`: self-reported external runs.
- `verified-community`: externally run results reproduced or audited by a
  maintainer.
- `official`: maintainer-run results from frozen packets and preregistered
  protocol artifacts.

Only `official` results belong in a canonical leaderboard.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff). There is no preprint or
published benchmark cycle yet.

## Feedback

High-value alpha feedback is concrete:

- a command that fails from a clean checkout;
- a stale or contradictory document reference;
- a fixture artifact missing provenance needed for audit;
- a result-tier claim that sounds more official than it is;
- a security, cost, or legal-record handling issue.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
