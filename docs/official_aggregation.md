# Official Aggregation

The official matrix runs one isolated case job per selected manifest row. After
the GitHub run finishes, maintainers aggregate downloaded per-case artifacts in
a private workspace that also has the locked labels file.

Download the per-case artifacts for the workflow run, then build the official
bundle:

```bash
gh run download <run-id> --dir tmp/official-eval-artifacts

uv run python -m legalforecast.publication.official_aggregate \
  --per-case-dir tmp/official-eval-artifacts \
  --run-input-manifest tmp/private-store-export/objects/results/manifests/cycle-2026-05.run-inputs.json \
  --labels tmp/locked-labels/cycle-2026-05.labels.jsonl \
  --output-dir tmp/official-results/cycle-2026-05 \
  --cycle-id cycle-2026-05 \
  --ablation full_packet
```

Keep `--output-dir` outside `--per-case-dir` so repeated aggregation does not
inspect its own private debug bundle as a per-case artifact.

The aggregation command runs the publication guardrail scanner on `public/`
before writing the final artifact manifest. The same scanner can be run
explicitly against downloaded logs:

```bash
uv run python -m legalforecast.publication.publication_guardrails \
  --public-dir tmp/official-results/cycle-2026-05/public \
  --log-dir tmp/official-eval-artifacts
```

## Validation

The aggregator treats the run-input manifest as the expected matrix. It fails
before publication when:

- a case/ablation row is missing from the downloaded artifacts;
- an unexpected or duplicate case/ablation output is present;
- `metrics.json` is not `legalforecast.per_case_metrics.v1`;
- the metrics `cycle_id`, `case_id`, `ablation`, packet object key, packet
  SHA-256, run count, or raw-output hashes do not match the manifest and
  `runs.jsonl`;
- `runs.jsonl` declares a `raw_output_sha256` that does not match the model
  output bytes;
- accounting rows do not cover the run-output hashes;
- locked labels are missing for required prediction units.

## Outputs

`public/` is the publication bundle. It contains:

- `scores.json` and `unit-scores.jsonl`;
- `report/leaderboard.json`, `.csv`, `.md`, and `.html`;
- `run-cards/aggregate-run-card.json`;
- `artifact-index.json` with SHA-256 hashes and byte sizes;
- `artifact-manifest.json` with the public artifact list.

`private-debug/` is not a publication bundle. It contains raw `runs.jsonl`,
`accounting.jsonl`, and `case-metrics.jsonl` for maintainer review and incident
debugging.

## Public Boundary

Public outputs contain scores, calibration and leaderboard diagnostics, run-card
metadata, artifact hashes, model identifiers, and non-secret accounting
summaries. Raw model outputs remain in `private-debug/`; raw court documents,
extracted filing text, packet JSON, provider account IDs, credentials, private
bucket URLs, and maintainer-only audit bundles must not be copied into
`public/`.
