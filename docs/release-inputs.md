# Benchmark release inputs

LegalForecastBench consumes an immutable release produced by LegalForecastCorpus. Corpus owns acquisition, document selection, prediction-unit construction, and outcome labeling. Bench owns the public contracts, model execution, scoring, and reporting.

A runnable release contains:

- `run-manifest.json`: the selected cases and locked execution inputs.
- `forecast-release.json`: case and prediction-unit indexes plus the paths, byte counts, and SHA-256 values of model-visible artifacts.
- `artifacts/`: predecision documents, docket context when provided, unit packets, and case prompt artifacts.
- `labels-release.json`: the separate outcomes used for scoring. Forecast execution does not receive this file.
- A frozen model registry: model identity, release-date metadata, adapter selection, and pricing used by the run.

The forecast contract is `legalforecast.forecast-release.v1`; the scoring contract is `legalforecast.labels-release.v1`. Their authoritative typed definitions and validators live in [`legalforecast/release/`](../legalforecast/release/). Use those implementations rather than copying a schema into a consumer.

Each executable unit packet identifies its case, unit, claim, defendant group, available document IDs, policy, and ISO decision date. The runner validates these fields before launching the case matrix. Cases must have consistent packet dates and satisfy the selected model's release-anchor rule.

The prediction model receives task instructions and compact case/unit/document metadata. It uses tools to read documents from its workspace; the stored prompt artifact is not a promise that its entire contents are inserted into the starting context. Docket entries may mention documents that are not included. Outcome-bearing decisions and labels remain outside the forecast workspace.

All units for a case are predicted together. Units marked unscored remain in the prediction task but have no outcome in the labels release. Scoring requires the labels release to bind the forecast release and exactly its scored unit set.

For local validation, run `uv run legalforecast release validate --help`. For a provider-free example, run `uv run legalforecast release issue-synthetic --help`. See [reproduction](reproduce-or-audit.md) for evaluating published artifacts.
