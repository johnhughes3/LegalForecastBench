# Official Run Runbook

This is the operator checklist for `.github/workflows/run-benchmark.yaml` on the current `main` branch. The workflow builds the matrix, runs isolated provider cells, resumes complete matching cells from the durable S3 result store, aggregates successful artifacts, and publishes the public aggregate to S3.

## Before Dispatch

Run the release gate at the exact SHA you intend to dispatch:

```bash
uv run scripts/release_check.py
```

Prepare the frozen run-input manifest, locked labels, model registry, and packet objects. The run-input manifest must use the same `cycle_id` as the dispatch and either omit `labels_sha256` or contain the SHA-256 of the exact labels JSONL. Generate and commit the hash-only freeze commitment before dispatch:

```bash
uv run legalforecast freeze \
  --cycle-id <cycle_id> \
  --bundle-output manifests/<cycle_id>.freeze.json \
  --manifest <cycle-manifest> \
  --labels <labels.jsonl> \
  --exclusion-ledger <exclusion-ledger.jsonl> \
  --prompt <prompt-artifact> \
  --scorer <scorer-artifact> \
  --harness <harness-artifact> \
  --model-registry <model-registry.json> \
  --baselines <baselines-artifact>
```

Use `uv run legalforecast freeze --help` for the exact argument shape. The workflow verifies the committed freeze commitment, substituting the downloaded labels and model registry for their checkout paths, before matrix fan-out. The separately downloaded run-input manifest is validated and label-bound by the workflow's manifest-freeze step; it is not substituted for the cycle manifest recorded in the freeze bundle.

Provision the protected GitHub environment `legalforecastbench-official-eval`, provider secrets, `LFB_RESULTS_BUCKET`, `LFB_PACKET_BUCKET`, `LFB_AWS_REGION`, `LFB_GITHUB_PACKET_READ_ROLE_ARN`, and the corresponding OIDC trust. Always set `max_projected_model_cost_usd` to an explicit non-empty limit for a live run.

## Dispatch Sequence

Dispatch `Run Benchmark` from `main` with the frozen `cycle_id`, `run_input_manifest_uri`, `labels_uri`, `model_registry_uri`, `model_keys`, and intended comma-separated `ablations`. Keep `resume_existing_results: true`.

1. Run with `dry_run: true`, the full intended matrix, and an explicit spend cap. This validates inputs, hashes, model eligibility, projected cost, and matrix coverage without provider calls.
2. Run a bounded live smoke by using a temporary frozen manifest containing the intended smoke cases. Do not edit a manifest after freezing it; create and commit a new freeze commitment for changed bytes.
3. Run the full live matrix only after the dry run and smoke pass.
4. For transient cell failures, use GitHub's re-run-failed-jobs action. A full redispatch is also safe: complete matching durable cells are reused and are not sent to the provider again.

The resume identity includes the case, ablation, packet hash, solver/model identity, registry content, and repeat count. Failed cells do not become canonical score rows. Preserve failed logs for audit.

## Aggregation

On a successful live matrix, the workflow downloads all per-case artifacts, independently re-verifies the frozen manifest and labels hashes, runs the same official aggregation implementation exposed by the local CLI, uploads the aggregate artifact, and synchronizes the public directory to:

```text
s3://$LFB_RESULTS_BUCKET/reports/<cycle_id>/multi-ablation/
```

For a local audit or recovery aggregation, use:

```bash
uv run legalforecast publish aggregate \
  --per-case-dir tmp/official-downloads/<cycle_id> \
  --run-input-manifest manifests/<cycle_id>.run-inputs.json \
  --model-registry manifests/<cycle_id>.model-registry.json \
  --labels private/labels/<cycle_id>.labels.jsonl \
  --output-dir tmp/official-aggregate/<cycle_id> \
  --cycle-id <cycle_id> \
  --cycle-series <pilot|rapid|official|annual_aggregate> \
  --clean-motion-count <count> \
  --prediction-unit-count <count> \
  --model-key provider:model-a \
  --model-key provider:model-b \
  --allow-no-baselines
```

Replace `--allow-no-baselines` with `--baseline-training-examples <frozen-corpus.jsonl>` once a compatible historical baseline corpus exists. Omit `--ablation` for the headline multi-ablation aggregation so the `full_packet` and `metadata_only` companion check remains active.

## Render And Review The Site

Render only from the public aggregate directory:

```bash
uv run legalforecast publish site \
  --official-artifacts-dir tmp/official-aggregate/<cycle_id>/public \
  --output-dir tmp/official-site/<cycle_id>
```

Review `index.html`, `artifact-index.json`, the aggregate run card, leaderboard outputs, small-cluster warnings, model-versus-baseline row types, and the publication-guardrail result before publishing. Keep `private-debug/`, locked labels, source-document bytes, and raw provider material out of the public site.

## Recovery Acceptance Criteria

A recovery is complete only when every expected matrix cell is present exactly once, artifact hashes match, aggregation succeeds without incomplete-model overrides, the public/private split passes guardrails, and the rendered site refers only to public artifacts. If inputs, prompt, scorer, registry, packet hashes, repeat count, or labels change, treat that as a new frozen run rather than a retry.
