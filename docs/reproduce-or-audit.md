# Reproduce Or Audit LegalForecastBench Results

LegalForecastBench separates public arithmetic reproduction from private source audit. Public artifacts support verification of hashes, score arithmetic, aggregate diagnostics, run metadata, and source handles. A deeper audit may require locked labels, accepted per-case outputs, and court-document bytes that the project cannot redistribute as a public corpus.

The Apache-2.0 license covers repository code. It does not grant redistribution rights for court filings, PACER or RECAP documents, provider outputs, locked labels, or third-party data.

## Credential-Free Fixture Reproduction

Run the CI-backed synthetic pipeline:

```bash
uv run legalforecast run issue-fixture --output-dir tmp/fixture-run

uv run legalforecast release validate \
  --forecast tmp/fixture-run/release/forecast-release.json \
  --labels tmp/fixture-run/release/labels-release.json \
  --artifact-root tmp/fixture-run/release
```

The report command writes JSON, CSV, Markdown, and HTML leaderboard artifacts. The fixture path uses synthetic records and requires no provider credentials.

## Recompute An Official Aggregate

With the accepted per-case artifact tree, exact frozen manifest, locked labels, and registry used for the run:

```bash
uv run legalforecast publish aggregate \
  --per-case-dir tmp/official-downloads/<cycle_id> \
  --run-input-manifest manifests/<cycle_id>.run-inputs.json \
  --model-registry manifests/<cycle_id>.model-registry.json \
    --labels private/labels/<cycle_id>.labels.jsonl \
  --output-dir tmp/official-aggregate/<cycle_id> \
  --cycle-id <cycle_id> \
  --cycle-series <cycle_series> \
  --clean-motion-count <count> \
  --prediction-unit-count <count> \
  --allow-no-baselines
```

Use `--baseline-training-examples <baseline-corpus.jsonl>` instead of `--allow-no-baselines` when the cycle has a baseline-training corpus. The registry defines the complete expected model set; do not narrow it with `--model-key`. Omit `--ablation` for the headline multi-ablation aggregate; passing it deliberately requests a single-ablation diagnostic.

Render the public result only after aggregation succeeds:

```bash
uv run legalforecast publish site \
  --official-artifacts-dir tmp/official-aggregate/<cycle_id>/public \
  --output-dir tmp/official-site/<cycle_id>
```

## Verify Public Score Arithmetic

`public/unit-scores.jsonl` contains public per-unit score rows and `public/report/leaderboard.json` contains the published summaries. Recompute a model's micro-Brier as the arithmetic mean of its public unit `brier` values and compare that result with its leaderboard row. This verifies published arithmetic, not the private label-creation process.

Also verify every entry in `public/artifact-index.json` against the referenced file's SHA-256 and compare the aggregate run card with the dispatched cycle, registry keys, ablations, expected and observed matrix counts, baseline disclosure, and any small-cluster warning.

Source handles and release commitments can support an audit without granting redistribution rights. Do not publish locked labels, raw provider responses, private withdrawal reasons, or restricted source-document bytes.

## Audit Checklist

1. Confirm the release SHA and locked run-input manifest predate the live outputs.
2. Verify the run-input manifest, labels, registry, packet commitments, scorer, prompt, and other committed artifacts.
3. Confirm the per-case artifacts form the expected case, ablation, model, and repeat matrix exactly once.
4. Recompute the aggregate with the command above and compare artifact hashes.
5. Recompute public unit-score arithmetic and inspect bootstrap warnings and ablation deltas.
6. Verify the rendered site was built only from the aggregate's `public/` directory.
7. Use the private archive only for the deeper label, source-document, and provider-response audit.

The public release commands validate already-issued artifacts; private corpus construction and source-document acquisition remain in LegalForecastCorpus.
