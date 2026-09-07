# Hugging Face benchmark publication

LegalForecastBench publishes each completed official cycle as an immutable revision of a public, manually gated Hugging Face Dataset repository. The Dataset Card, native leaderboard metadata, and repository history remain discoverable; downloading repository files requires an individually approved Hugging Face account.

The Hugging Face copy is a distribution surface. The authenticated LegalForecastBench release, artifact indexes, and evidence bundle remain the reproducibility and governance records.

## Immutable version model

Each official publication has an immutable `hugging_face_release_version`. The package is written under `releases/<version>/<cycle>/`, and the generated `eval.yaml` uses a cycle-specific task ID such as `legalforecast_mtd_cycle_1`.

Model result files should always set `dataset.revision` to the full Hugging Face commit SHA. A mutable branch name or task ID alone is not a reproducible benchmark identity. If a later cycle changes the cohort, task, or scoring semantics, give it a new task ID; never silently reinterpret an old task. Hugging Face preserves earlier repository commits, so older releases remain addressable even as the Dataset Card and current leaderboard evolve.

## What a publication means

A publication contains the sanitized official score/report and the public metadata needed to identify the cycle and its release. A successful upload, the Hugging Face leaderboard UI, or Hugging Face's `verified` presentation does not prove that a result satisfied the benchmark's official controls. Check the corresponding LegalForecastBench evidence bundle and the full dataset revision when auditing a result.

The publication path uses a short-lived OpenID Connect token for repository-scoped automation. No durable Hugging Face token belongs in the repository, package, logs, or a workflow secret. Manual access approval is a Hugging Face repository setting and remains part of the publication boundary.

## Post-anchor models

A model released after the cycle's corpus decision window closed cannot claim contamination resistance on that corpus, so it publishes in its own arm rather than mixed into the pre-anchor rows. It is an official, viable result all the same — a post-anchor score is published rather than withheld, and the separation exists so the two arms stay comparable, not to rank one below the other. See [publication-governance.md](publication-governance.md) for what each arm may claim. It runs through the same pipeline and is aggregated into its own official-shaped bundle against a one-model registry, then merged into the published page at render time. It never enters the pre-anchor aggregate, so no set-equality or matrix gate over that aggregate ever sees it.

The CLI flags, paths, manifest fields, and config names below still spell this arm `supplementary`. Those identifiers are frozen schema and package vocabulary; the user-visible label is post-anchor.

Pass the supplementary bundle to the publisher with `--supplementary-artifacts-dir`. The package then writes it under `releases/<version>/<cycle>/supplementary/`, alongside but separate from `aggregate/`, and the Dataset Card gains a second config, `<cycle>_supplementary`, whose `supplementary` split points at those rows. The official `<cycle>` config and its `test` split remain pre-anchor-only.

A publication that carries a supplementary split uses the `legalforecast-official-hf-publication-v2` manifest, which additionally commits to `supplementary_path` and `supplementary_artifact_index_sha256`. A publication without supplementary models still emits `legalforecast-official-hf-publication-v1` unchanged, and validation refuses a `-v1` package that carries supplementary files.

On the rendered page a post-anchor model appears in the same table as the pre-anchor models, after them, ranked within the post-anchor arm, badged `Official LegalForecast-MTD Cycle 1 result (post-anchor)` and labelled with a trailing `†`. The dagger is deliberately distinct from the contamination-tier asterisk, which marks a model whose training cutoff is undisclosed; a post-anchor row can legitimately carry both. The headline and overall best-model figure remain the best pre-anchor row. Delta-vs-best is versus the best model in the same arm.

## Controlled access

The generated Dataset Card uses the following short terms:

> By requesting or using access, you agree that, for each court record in the dataset, you submit to the jurisdiction of the court from which that record was obtained for matters concerning your possession, use, or disclosure of the record. You will promptly comply with any applicable order of that court to delete or destroy information that the court determines was made public inadvertently. You will take reasonable precautions not to republish dataset material in a manner that exposes sensitive information included in a court filing.

These are access conditions, not a claim that court records are proprietary. Hugging Face gating is access control, not a conclusion that every source document may lawfully be redistributed. Withdrawal, sealing, redaction, and source-court orders continue to control; affected material must be removed from future revisions and access revoked when appropriate.

The publisher accepts only the already sanitized official aggregate. Source documents or other case materials may be added only through an authenticated, separately reviewed public-release artifact; they must never be copied from private-debug, acquisition, provider-response, or audit-store paths merely because the Hugging Face repository is gated.

## Current HF limitations

- Manual gating is configured outside repository YAML and should be checked after repository creation.
- Official benchmark registration requires Hugging Face allow-listing.
- The leaderboard API does not expose the dataset revision for each row. Preserve the revision in model `.eval_results` files and the project evidence bundle.
- Open model-repository pull requests may appear as community results. They are not LegalForecastBench official results unless accepted through this project's controlled publication path.

For the command-line validation and reproduction path, start with [reproduce-or-audit.md](reproduce-or-audit.md) and use `--help` on the installed CLI when a command reports an invalid option or artifact shape.
