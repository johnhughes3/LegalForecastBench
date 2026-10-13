# Hugging Face benchmark publication

> **Status: built, not yet used.** The protected fan-in workflow can publish an official result as an immutable revision of a public, manually gated Hugging Face Dataset. No result has been published there yet: Cycle 1 is published on the [results site](https://www.legalforecastbench.org/) and in the [working paper](https://www.legalforecastbench.org/paper/), and the target dataset repository is not yet configured.

A Hugging Face copy would be a distribution surface. The authenticated LegalForecastBench release, artifact indexes, and evidence bundle remain the reproducibility and governance records.

## How publication runs

`fan-in-publish.yaml` publishes only when it is dispatched with `publish` enabled and a `hugging_face_release_version`, and only when the protected fan-in environment defines `LFB_HF_OFFICIAL_DATASET_REPO`. The workflow packages the scores, unit scores, and leaderboard report of that fan-in run:

```bash
uv run python -m legalforecast.hugging_face_publication \
  --score scores.json \
  --unit-scores unit-scores.jsonl \
  --report-dir reports/ \
  --cycle-id CYCLE_ID \
  --output-dir hugging-face-package \
  --release-version RELEASE_VERSION \
  --dataset-repository OWNER/DATASET
```

The package writes the aggregate under `releases/<version>/<cycle>/aggregate/`, a small static site under `releases/<version>/<cycle>/site/`, a gated Dataset Card, and an `eval.yaml` with a cycle-specific task ID such as `legalforecast_mtd_cycle_1`. The upload uses a short-lived OpenID Connect token scoped to the dataset repository; no durable Hugging Face token belongs in the repository, package, logs, or a workflow secret.

## Immutable versions

Each publication has an immutable `hugging_face_release_version`; mutable names such as `main` are refused. Model result files should set `dataset.revision` to the full Hugging Face commit SHA, because a branch name or task ID alone is not a reproducible benchmark identity. If a later cycle changes the cohort, task, or scoring semantics, it gets a new task ID; an old task is never silently reinterpreted.

## What a publication means

A publication contains the sanitized official scores and report plus the public metadata needed to identify the cycle and release. A successful upload, the Hugging Face leaderboard UI, or Hugging Face's `verified` presentation does not prove that a result satisfied the benchmark's controls. Check the corresponding LegalForecastBench evidence and the full dataset revision when auditing a result.

Model eligibility follows the training-cutoff rule in [METHODS.md](METHODS.md) and [publication governance](publication-governance.md). The publisher still accepts a `--supplementary-artifacts-dir` option from the earlier release-date ("post-anchor") arm, which writes a separate `supplementary/` split with a `-v2` manifest. The protected workflow does not use it, and it does not implement the training-cutoff rule.

## Controlled access

The generated Dataset Card requires manual access approval and uses these short terms:

> By requesting or using access, you agree that, for each court record in the dataset, you submit to the jurisdiction of the court from which that record was obtained for matters concerning your possession, use, or disclosure of the record. You will promptly comply with any applicable order of that court to delete or destroy information that the court determines was made public inadvertently. You will take reasonable precautions not to republish dataset material in a manner that exposes sensitive information included in a court filing.

These are access conditions, not a claim that court records are proprietary. Hugging Face gating is access control, not a conclusion that every source document may lawfully be redistributed. Withdrawal, sealing, redaction, and source-court orders continue to control; affected material must be removed from future revisions and access revoked when appropriate.

The publisher accepts only the already sanitized official outputs. Source documents or other case materials may be added only through a separately reviewed public-release artifact, never copied from private, acquisition, provider-response, or audit storage because the repository is gated.

## Before the first publication

- Create the public Dataset repository, enable manual gating in its settings (gating is not set by repository YAML), and set `LFB_HF_OFFICIAL_DATASET_REPO` on the protected fan-in environment.
- Registration as an official Hugging Face benchmark requires Hugging Face allow-listing.
- The leaderboard API does not expose each row's dataset revision; preserve it in model `.eval_results` files and the project evidence.
- Open model-repository pull requests may appear as community results. They are not LegalForecastBench results unless published through this path.
