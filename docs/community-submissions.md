# Community Submissions

Community submissions are reviewed metadata packages under `community/submissions/<year>/<submission_id>/`. They are not official LegalForecastBench results. The official benchmark, official publication artifacts, and official protected workflows remain separate.

## Package A Run

Start from a completed multi-harness run directory and a conformance report:

```bash
uv run legalforecast multiharness community package \
  --run-dir tmp/multiharness/run \
  --conformance-report tmp/multiharness/conformance/conformance-report.json \
  --output-dir community/submissions/2026/example-submission \
  --submission-id example-submission \
  --submitter-name "Your Name" \
  --submitter-github your-handle \
  --run-operator-name "Your Name" \
  --adapter-author-name "Adapter Author or Team" \
  --task-source-credit-name "LegalForecastBench and/or Harvey LAB" \
  --benchmark-credit-name "LegalForecastBench" \
  --acknowledge-required-attestations \
  --hf-upload-plan
```

The package command writes `submission.json`, `public-summary.json`, `conformance-report.json`, `run-manifest.json`, `selection-manifest.json`, `artifact-manifest.json`, `row-results.jsonl`, `canonical-runs.jsonl`, and optionally `hf-upload-plan.json`. If the source run contains projected public artifacts such as `lfb/runs.jsonl` or `lab/task-results.jsonl`, those are copied into the package and referenced from `artifact-manifest.json`.

Checked-in examples live under `community/submissions/2026/`. They cover the first-class LQ.AI, Hermes Agent, OpenClaw, OpenAI Responses, and Claude Agent SDK fixture adapters. These are no-network community examples, not official LegalForecastBench results.

Validate before opening a pull request:

```bash
uv run legalforecast multiharness community validate-submission \
  --submission community/submissions/2026/example-submission/submission.json \
  --output tmp/community-validation.json
```

## Required Attestations

Every submission must attest to all of the following values:

- `not_official_legalforecastbench_result`
- `no_private_or_sealed_material_in_public_artifacts`
- `right_to_submit_artifacts`
- `provider_terms_acknowledged`

These attestations are public statements. They are not a substitute for legal review of provider terms, court-file handling rules, or third-party dataset licenses.

## Required Credits

Submissions must distinguish these roles:

- `submitter`: the person or organization opening the PR.
- `run_operator`: the person or organization that ran the harness.
- `adapter_author`: the person or organization responsible for the adapter.
- `task_source`: the task/corpus source, such as LegalForecastBench or Harvey LAB.
- `benchmark_infrastructure`: LegalForecastBench infrastructure credit.
- `compute_sponsor`: optional credit for donated compute.

Optional identifiers include GitHub handle, Hugging Face handle, ORCID, institution, and URL when appropriate.

## Large Artifacts And Hugging Face Mirrors

Do not commit raw model transcripts, private logs, source documents, sealed/private materials, or large binary outputs. Large public-safe artifacts should be referenced by immutable URL plus SHA-256. The optional `hf-upload-plan.json` is a planning artifact for mirroring public-safe files to a Hugging Face Dataset repo; it does not upload anything itself.

All public artifact paths must be safe relative paths. Public files are scanned for secrets, provider account IDs, private path segments, raw-document-like suffixes, and audit-only markers.

## Partial Runs And Composite Rows

Community comparisons are grouped by compatible-shard group ID, which is derived from family, scoring mode, and suite version rather than a single partial-run selection hash. LegalForecastBench Brier-style rows and Harvey LAB rubric/native rows are not ranked against each other.

Partial-run shards include:

- `selection_sha256` and `selection_label`
- source suite and suite version
- explicit task IDs and selectors
- adapter ID/version
- model key
- sandbox policy hash
- run config hash
- compatible-shard group ID
- contributor credit per shard

Composite rows can roll up compatible shards only when their compatible-shard group (family, scoring mode, and suite version), adapter ID/version, model key, and sandbox policy hash match, and task IDs do not overlap. The run config hash remains in each source shard for provenance, but it is not a composite key because it includes the partial selection and run identity. Composite rows credit each underlying shard and link back to every submission.

## Community Aggregate Outputs

`legalforecast multiharness community aggregate` rebuilds a public bundle under the requested output directory. Current outputs include `registry/` indexes, `reports/` JSON/CSV/Markdown/HTML comparisons, per-submission public JSON under `submissions/`, a generated `site/`, and root `artifact-index.json` / `artifact-manifest.json` files.

## Pull Request Intake

Open a PR that adds only the submission package under `community/submissions/<year>/<submission_id>/`. The community validation workflow runs with read-only repository permissions and without official benchmark environments, OIDC, AWS credentials, or provider secrets. On merge to `main`, the workflow rebuilds the community aggregate and uploads the generated registry, reports, and static site as a build artifact from accepted submission metadata.

Harvey LAB is a separate Harvey AI project and task corpus. Any submission using Harvey LAB tasks must preserve Harvey LAB credit/license language. Final public branding and positioning for LegalForecastBench, Legal Quants, and any Harvey LAB comparison remains subject to John Hughes/Legal Quants approval.
