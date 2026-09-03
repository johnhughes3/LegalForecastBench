# Hugging Face benchmark publication

LegalForecastBench publishes each completed official cycle as an immutable revision of one public, manually gated Hugging Face Dataset repository. The Dataset Card, native leaderboard metadata, and repository history remain discoverable; downloading repository files requires an individually approved Hugging Face account.

The Hugging Face copy is a distribution surface. The authenticated LegalForecastBench releases, artifact indexes, and run cards remain the reproducibility and governance records.

## Version model

Each official publication supplies an immutable `hugging_face_release_version` to the protected `Protected Labels Fan In` workflow. The package is written under `releases/<version>/<cycle>/`, and the generated `eval.yaml` uses a cycle-specific task ID such as `legalforecast_mtd_cycle_1`.

Model result files should always set `dataset.revision` to the full Hugging Face commit SHA. A mutable branch name or task ID alone is not a reproducible benchmark identity. If a later cycle changes the cohort, task, or scoring semantics, give it a new task ID; never silently reinterpret an old task. Hugging Face preserves earlier repository commits, so older releases remain addressable even as the Dataset Card and current leaderboard evolve.

## One-time Hugging Face setup

1. Create the Dataset repository named by the protected environment variable `LFB_HF_OFFICIAL_DATASET_REPO`.
2. Make it public and set access requests to **Manual approval**. The card metadata and access form are published by this repository, but the approval mode is an HF repository setting and must be confirmed in the HF UI.
3. Configure an HF Trusted Publisher for `johnhughes3/LegalForecastBench`, branch `main`, and workflow `fan-in-publish.yaml`, scoped to that Dataset repository. The retained workflow sets `HF_OIDC_RESOURCE` and the Hugging Face client exchanges GitHub's protected-environment OIDC identity for a short-lived repository-scoped token. Pin the publisher claims to the exact repository, branch, and workflow; do not add a static token secret.
4. Configure `LFB_HF_OFFICIAL_DATASET_REPO` on the existing protected `legalforecastbench-official-eval-fan-in` GitHub environment. Store only `namespace/repository`, without a URL or `datasets/` prefix.
5. Ask Hugging Face to validate and allow-list the repository as an official benchmark. Native benchmark registration is currently beta and is not conferred merely by uploading `eval.yaml`.

No durable Hugging Face token is used. With `id-token: write` on the protected fan-in job, the `huggingface_hub` client exchanges GitHub's OIDC identity for a repository-scoped token lasting at most 60 minutes. The token is never written to the repository, package, logs, or a workflow secret.

## Publishing

Run the retained fan-in workflow from `main` with `publish=true` and an immutable `hugging_face_release_version`. The workflow validates and publishes the sanitized official score/report first, then builds the HF tree with:

```bash
uv run python -m legalforecast.hugging_face_publication \
  --score /tmp/lfb-score.json \
  --unit-scores /tmp/lfb-unit-scores.jsonl \
  --report-dir /tmp/lfb-report \
  --cycle-id cycle-1 \
  --output-dir tmp/hugging-face-benchmark \
  --release-version cycle-1.0.0 \
  --dataset-repository namespace/repository
```

It then uploads the validated tree through HF Trusted Publishing, refusing a repository that is not manually gated or already contains the immutable release path. Leaving `hugging_face_release_version` empty performs no HF build or write. A `publish=false` fan-in verifies and produces workflow artifacts but can never publish to S3 or HF.

After publication, record the resulting full HF commit SHA in every model repository result entry and in the LegalForecastBench evidence bundle. Do not treat a successful upload, the HF leaderboard UI, or HF's `verified` presentation as proof that a result satisfied the benchmark's official controls.

## Supplementary (unofficial) models

A model released after the cycle's corpus decision window closed cannot claim the contamination protection an official row claims, so it is published as *supplementary* rather than official. It runs through the same pipeline and is aggregated into its own official-shaped bundle against a one-model registry, then merged into the published page at render time. It never enters the official aggregate, so no official set-equality or matrix gate ever sees it.

Pass the supplementary bundle to the publisher with `--supplementary-artifacts-dir`. The package then writes it under `releases/<version>/<cycle>/supplementary/`, alongside but separate from `aggregate/`, and the Dataset Card gains a second config, `<cycle>_supplementary`, whose `supplementary` split points at those rows. The official `<cycle>` config and its `test` split remain official-only.

A publication that carries a supplementary split uses the `legalforecast-official-hf-publication-v2` manifest, which additionally commits to `supplementary_path` and `supplementary_artifact_index_sha256`. A publication without supplementary models still emits `legalforecast-official-hf-publication-v1` unchanged, and validation refuses a `-v1` package that carries supplementary files.

On the rendered page a supplementary model appears in the same table as the official models, after them, ordered by model id, badged `Supplementary†` and labelled with a trailing `†`. It is never ranked: it cannot be the best model, does not appear in the headline figures, and its delta-vs-best cell reads "Not ranked". The dagger is deliberately distinct from the contamination-tier asterisk, which marks an *official* model whose training cutoff is undisclosed; a supplementary row can legitimately carry both.

## Controlled access

The generated Dataset Card uses the following short terms:

> By requesting or using access, you agree that, for each court record in the dataset, you submit to the jurisdiction of the court from which that record was obtained for matters concerning your possession, use, or disclosure of the record. You will promptly comply with any applicable order of that court to delete or destroy information that the court determines was made public inadvertently. You will take reasonable precautions not to republish dataset material in a manner that exposes sensitive information included in a court filing.

These are access conditions, not a claim that court records are proprietary. Hugging Face gating is access control, not a conclusion that every source document may lawfully be redistributed. Withdrawal, sealing, redaction, and source-court orders continue to control; affected material must be removed from future revisions and access revoked when appropriate.

The current publisher accepts only the already sanitized official aggregate. Source documents or other case materials may be added only through an authenticated, separately reviewed public-release artifact; they must never be copied from private-debug, acquisition, provider-response, or audit-store paths merely because the HF repository is gated.

## Current HF limitations

- Manual gating is configured outside repository YAML and should be checked after repository creation.
- Official benchmark registration requires HF allow-listing.
- The leaderboard API does not expose the dataset revision for each row. Preserve the revision in model `.eval_results` files and the project evidence bundle.
- Open model-repository pull requests may appear as community results. They are not LegalForecastBench official results unless accepted through this project's controlled publication path.
