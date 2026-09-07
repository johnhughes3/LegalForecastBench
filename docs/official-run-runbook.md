# Official run and reproduction guide

This guide describes the public release boundary and the provider-free commands a reader can use to validate, score, and report a published LegalForecastBench cycle. Official execution and publication use protected workflows; they are separate from local reproduction and from the private Corpus construction process.

The public release consists of a locked run manifest, an outcome-blinded forecast release, model-visible artifacts, and a separately controlled labels release. The forecast worker receives no labels. Every published score is tied to the exact release identities and the immutable artifacts used to produce it.

## Reproduce a published release

Start from an exact checkout and the release files named by the publication record. Validate the public inputs before scoring:

```bash
uv run legalforecast manifest validate \
  --manifest <run-manifest.json> \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <artifact-root>

uv run legalforecast release validate \
  --forecast <forecast-release.json> \
  --labels <labels-release.json> \
  --artifact-root <artifact-root>

uv run python -m legalforecast.contracts.ratchet
uv run pytest -q
```

A validation error names the release, artifact, or field that failed. Check the relevant schema and rerun the command with `--help` before changing an input. Do not replace an immutable artifact with a mutable checkout or a newly generated document.

## Score and report

The strict local contract accepts an authenticated receipt set and the same immutable releases:

```bash
uv run legalforecast score \
  --runs <run-records.jsonl> \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <artifact-root> \
  --manifest <run-manifest.json> \
  --model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output scores.json \
  --unit-scores-output unit_scores.jsonl

uv run legalforecast report \
  --scores scores.json \
  --labels-release <labels-release.json> \
  --forecast-release <forecast-release.json> \
  --artifact-root <artifact-root> \
  --manifest <run-manifest.json> \
  --frozen-model-registry <model-registry.json> \
  --ledger <run-ledger.sqlite3> \
  --output-dir reports/
```

The public workflow names remain `run-benchmark.yaml` for forecast execution and `fan-in-publish.yaml` for labels fan-in. They run from a trusted revision under protected environments. Their existence and input contracts are checked in the repository; a local fixture or a green workflow plan is not live-cycle evidence.

For a credential-free fixture reproduction of the same validation and scoring path, use [reproduce-or-audit.md](reproduce-or-audit.md). The fixture proves command and artifact compatibility; it is not evidence that an official cycle ran.

## Public reporting boundary

Publish only sanitized JSON, CSV, Markdown, and HTML leaderboard artifacts bound to the score identity and their machine-readable provenance. Never publish labels, raw provider responses, private source bytes, or private withdrawal reasons.

If a published case must be removed, use the repository's withdrawal contract and publish the resulting public erratum. Withdrawal does not rewrite an immutable prior release or silently alter score artifacts.

## What local checks do not prove

Provider-free tests, release validation, a pull request, and a workflow plan prove source and artifact contracts only. They do not prove that a protected workflow ran, that its provider calls succeeded, or that a result is authorized for publication. Those facts come from the exact workflow run and the release evidence attached to it.

The companion private Corpus repository owns source acquisition, case selection, quality control, release issuance, and the handoff of outcome-blinded public artifacts. This repository does not reconstruct those inputs from private source material.
