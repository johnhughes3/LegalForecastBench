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
  --cycle-series official \
  --clean-motion-count 250 \
  --prediction-unit-count 1000 \
  --official-window-days 28 \
  --model-key google:gemini-3-flash-preview \
  --model-key openai:gpt-5.4-mini \
  --model-key anthropic:claude-sonnet-4-6 \
  --ablation full_packet
```

Keep `--output-dir` outside `--per-case-dir` so repeated aggregation does not
inspect its own private debug bundle as a per-case artifact.

The cycle-power inputs are publication facts, not inferred from the downloaded
per-case output folders. Use:

- `--cycle-series` for the planned cadence (`pilot`, `rapid`, `official`, or
  `annual_aggregate`);
- `--clean-motion-count` for the adjudicated motion count after exclusions;
- `--prediction-unit-count` for the locked prediction-unit count;
- `--elapsed-days` for rapid cycles when the elapsed-time exception is relevant;
- `--official-window-days` for official-cycle window length disclosure.
- repeat `--model-key` for every frozen registry entry expected in the matrix.
  A 25-case, 3-model pilot should therefore aggregate 75 per-case/model rows
  while still reporting 25 distinct cases.

The aggregation command runs the publication guardrail scanner on `public/`
before writing the final artifact manifest. The same scanner can be run
explicitly against downloaded logs:

```bash
uv run python -m legalforecast.publication.publication_guardrails \
  --public-dir tmp/official-results/cycle-2026-05/public \
  --log-dir tmp/official-eval-artifacts
```

## Validation

The aggregator treats the run-input manifest crossed with repeated
`--model-key` values as the expected matrix. It fails before publication when:

- a case/ablation/model row is missing from the downloaded artifacts;
- an unexpected or duplicate case/ablation/model output is present;
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
- `cycle-power.json` with the cadence classification, claim-strength label,
  thresholds, warnings, and strong-ranking claim flag;
- `report/leaderboard.json`, `.csv`, `.md`, and `.html`;
- `run-cards/aggregate-run-card.json`;
- `artifact-index.json` with SHA-256 hashes and byte sizes;
- `artifact-manifest.json` with the public artifact list.

The same `cycle_power` object is embedded in `report/leaderboard.json` and
`run-cards/aggregate-run-card.json` so public leaderboard consumers see the
maximum supported claim strength next to the scores. For example, a 25-motion
pilot fixture reports `claim_strength: feasibility_only` and
`strong_ranking_claim_allowed: false`; it must not be described as supporting a
strong ranking.

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
