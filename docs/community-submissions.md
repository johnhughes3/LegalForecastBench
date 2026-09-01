# Community Submissions

Community submissions are reviewed metadata packages under `community/submissions/<year>/<submission_id>/`. They are not official LegalForecastBench results. The official benchmark, official publication artifacts, and official protected workflows remain separate.

Walk through install, fixture-none, interrupt/resume, and packaging in [docs/community-contributor-guide.md](community-contributor-guide.md) before you open a PR.

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

The package command writes `submission.json`, `public-summary.json`, `conformance-report.json`, `run-manifest.json`, `run-compatibility.json`, `selection-manifest.json`, `artifact-manifest.json`, `row-results.jsonl`, `canonical-runs.jsonl`, and optionally `hf-upload-plan.json`. If the source run contains projected public artifacts such as `lfb/runs.jsonl` or `lab/task-results.jsonl`, those are copied into the package and referenced from `artifact-manifest.json`. Receipt-backed efficiency observations (`efficiency-observation.json`), public execution receipts, evaluation receipts, and score artifacts are copied when present. New run summaries use `legalforecast.multiharness.community_run_summary.v2` and must bind the hashes of those artifacts; the v1 reader remains characterization-exact. Aggregate and site pages reconstruct displayed figures from those hashes. Claim policy refuses full-suite language from a scoped or partial run, a contamination-resistant claim from a preliminary (#715) result, and ranking language below the repeat threshold. See [harness-efficiency-observations.md](harness-efficiency-observations.md).

Checked-in examples live under `community/submissions/2026/`. They cover the first-class LQ.AI, Hermes Agent, OpenClaw, OpenAI Responses, and Claude Agent SDK fixture adapters. These are no-network community examples, not official LegalForecastBench results.

A plan-only `sandbox.plan.json` is not container-execution evidence. A submission claiming live tool isolation must use the explicit live-tool mode and retain a valid private execution receipt for every successful row. The package command revalidates each private receipt against the exact request and result before publishing only its receipt commitment; submitters must still preserve the private receipt for review. Provider credentials stay in the host adapter and must never appear in the tool container, receipt, transcripts, or public artifacts.

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

## Who Runs And Funds Submissions

Community submissions are contributor-run and contributor-funded. The submitter or their organization executes the harness with their own provider credentials and pays their own model API costs. Every published row discloses who operated the run through the `run_operator` credit role above. Runs using donated compute also disclose the sponsor through `compute_sponsor`; self-funded runs may omit that optional credit and are understood to be funded by the run operator.

This uniform policy applies to all contributors. It keeps each community row credible as the contributor's own result and keeps the official/community boundary crisp: official rows are run and funded by the benchmark; community rows are self-run and validated.

All contributors receive the same attribution: organization or personal name, plus a link when one is provided, on their community rows. LegalForecastBench provides free automated validation on pull request intake and maintainer review; it does not fund or operate community runs.

## Large Artifacts And Hugging Face Mirrors

Do not commit raw model transcripts, private logs, source documents, sealed/private materials, or large binary outputs. The one exception is a containerized harness-lane package built by the intake tool described in [Containerized Harness-Lane Submissions](#containerized-harness-lane-submissions), whose scrubbed transcripts ride in the pull request precisely so CI can scan them. The checked-in metadata under `community/submissions/` is the registry of record; neither a generated aggregate, GitHub Actions artifact, GitHub Release, nor an external mirror can add or replace an accepted submission.

The optional large-artifact mirror is the Hugging Face Dataset repository [`johnhughes3/legalforecastbench-community-artifacts`](https://huggingface.co/datasets/johnhughes3/legalforecastbench-community-artifacts), owned and administered by John Hughes. Maintainers of `johnhughes3/LegalForecastBench` may publish public-safe artifacts after submission validation. Repository recovery consists of recreating that Dataset repository under the same owner and re-uploading bytes verified against the SHA-256 values in the git registry; mirror access never authorizes changing checked-in metadata.

Every mirrored artifact reference must use an HTTPS Hugging Face `resolve` URL pinned to a full 40- or 64-character lowercase commit SHA in that exact Dataset repository, and must retain the artifact's `sha256:` digest in `submission.json`. Branch names, tags, `main`, `master`, `latest`, query parameters, redirects, and mutable replacement at an existing URL are not accepted. The optional `hf-upload-plan.json` records the designated repository and `immutable-commit` revision policy; it is a planning artifact and does not upload anything itself.

Accepted metadata and mirrored artifacts are retained indefinitely. Corrections are new submissions or new artifact records at new immutable URLs; existing records and bytes are never replaced in place. A legal, privacy, provider-terms, or integrity problem triggers prompt withdrawal: maintainers remove public access to affected mirror bytes when necessary and commit a tombstone that preserves the submission ID, withdrawal date, reason category, and prior artifact hashes without republishing sensitive details. Ordinary withdrawal does not erase provenance. Deletion from both git history and the mirror is reserved for a binding legal requirement or a confirmed secret/private-material exposure, and the public tombstone should remain whenever legally and safely possible.

GitHub Releases are not an artifact mirror for community submissions. They may carry versioned LegalForecastBench software and official release notes, but community artifact durability and identity come from the checked-in registry plus the optional commit-pinned Hugging Face mirror.

All public artifact paths must be safe relative paths. Public files are scanned for secrets, provider account IDs, private path segments, raw-document-like suffixes, and audit-only markers.

## Containerized Harness-Lane Submissions

The multi-harness *harness lane* asks a different question from the benchmark proper: does an agentic CLI, running with its own tools live, beat the same model's bare API? The evidence for that question is the transcript. A contributor who runs the lane on their own machine therefore has something worth publishing and nowhere to put it, so this is the one submission shape whose **full results** are accepted, and we host them.

This is a carve-out from "do not commit raw model transcripts" above, and it is narrow: it applies only to a run produced by the containerized harness lane, packaged by the tool below. It exists because a containerized row structurally cannot carry the operator's environment. The harness container receives exactly two bind mounts — the task workspace and a freshly staged HOME holding only the credential files the adapter manifest declared — its environment is constructed rather than inherited from the operator's shell, and it sits on an internal Docker network whose only route off the host is the allowlist CONNECT proxy. There is no home directory, no personal configuration, and no unrelated host data inside the container for a transcript to leak.

So the redaction is deliberately light. What is rewritten is what the *host* half of the run wrote — absolute paths, which become readable placeholders such as `/[host-run-dir]/rows/row-0` and `/[host-home]/…` — plus credential values, since the staged login is copied into the container and a CLI that echoes its own token puts it in a transcript. Prompts, reasoning, tool calls, tool outputs, and answers are kept verbatim. A transcript scrubbed into unreadability would defeat the purpose of accepting it.

Package a completed run. One command packages it, writes the upload plan, and runs every check the publishing workflow runs, so a problem surfaces on your machine instead of in a failed workflow run days later:

```bash
uv run legalforecast multiharness harness submit \
  --run-dir tmp/multiharness/run \
  --output-dir community/submissions/2026/<submission-id> \
  --submission-id <submission-id> \
  --submitter-name "Your Name" \
  --submitter-github your-handle \
  --run-operator-name "Your Name" \
  --adapter-author-name "Adapter Author or Team"
```

That writes `community-harness-submission.json`, `harness-lane-summary.json`, `hf-upload-plan.json`, and the scrubbed run under `full-results/`, then prints the exact files to commit and the exact `submission_dir` and `release_path` a maintainer will dispatch with. Provider-token shapes and host paths are rewritten automatically; pass `--secret-value` (repeatable) for any additional exact value that must not survive. Package somewhere else and the command tells you where the package has to move to; the intake workflow refuses a `submission_dir` outside `community/submissions/<year>/`.

To re-run the checks against a package that already exists — after a rebase, or before asking a maintainer to dispatch:

```bash
uv run legalforecast multiharness harness check-submission \
  --submission-dir community/submissions/2026/<submission-id>
```

Running the checks locally does not weaken or skip the server-side ones. It is deliberately the same code called earlier: the publishing job still re-validates from scratch at the dispatched commit, because bytes that travelled through a pull request are not the bytes you checked, and because your local run is not evidence about anyone else's package.

Validation is load-bearing, because this accepts bytes from strangers into storage we host, and it is the same code at every stage — contributor, pull-request CI, and the maintainer's publish job. It refuses a package whose declared per-file size or total exceeds the intake caps (8 MiB per artifact, 64 MiB and 2,000 artifacts per submission); whose declared SHA-256 does not match the actual bytes; that carries a file the upload plan does not declare; that carries a symlink; that fails the publication secret scan; whose upload plan names a mirror other than the community dataset repository; or that does not declare `official: false`, `result_class: community_harness_lane`, and the `not_official_legalforecastbench_result` attestation. The caps are review-sized on purpose: the bytes ride inside the pull request so that CI scans the real files rather than a description of them.

### What The Package Leaves Out

The publication guardrails refuse a `.txt` or `.text` file anywhere in a public artifact package, because a raw-document suffix is how case text gets republished by accident. That rule and this lane collide in exactly one place, and the packager resolves it rather than carving an exception: `rows/*/container-workspace/` is dropped and never travels.

That directory is what the lane staged *into* the container, not what the harness produced. Every run writes a tool-use sentinel token there (`harness-sentinel/workspace-token.txt`), and a Harvey LAB row also holds the projected corpus documents themselves. Publishing the first would refuse the package outright; publishing the second would republish case documents through a community mirror. The count of files left behind is recorded as `excluded_workspace_file_count` in `community-harness-submission.json` rather than dropped silently.

Nothing is lost on the LegalForecastBench corpus path: the model's answer is packaged in `full-results/rows/*/private-logs/release-forecast-output.json` and its transcript in `container-logs/` and `private-logs/`, all kept verbatim. **On the Harvey LAB path the deliverable is lost**, because a LAB deliverable exists only as files the agent wrote into that workspace and `lab/scores.jsonl` carries digests rather than text. A LAB harness-lane submission therefore publishes its scores and transcripts but not its written work product. If you are writing an adapter, project the deliverable from `structured_stdout` — every shipped manifest does — so the answer reaches the package through the scored channel.

### What Happens After You Open The Pull Request

A maintainer reviews and merges the pull request, then dispatches `.github/workflows/community-harness-intake.yaml` at that commit, which re-validates from scratch and uploads the package to an immutable path in the community dataset repository `johnhughes3/legal-quants-community-submissions`. That repository is deliberately not the official benchmark dataset: the job reads its destination from the `LFB_HF_COMMUNITY_DATASET_REPO` variable and refuses to publish if it is unset, names any other repository, or equals `LFB_HF_OFFICIAL_DATASET_REPO`, so a community submission cannot land where official results live. The upload path is immutable — an existing prefix is refused, never overwritten. The workflow is `workflow_dispatch` only — no pull-request trigger reaches it — and it obtains a repository-scoped Hugging Face token by exchanging the GitHub OIDC identity, exactly as [hugging-face-publication.md](hugging-face-publication.md) describes for the official lane. No durable `HF_TOKEN` exists and contributors never receive a credential to anything of ours.

**A harness-lane submission is not an official LegalForecastBench result.** It is contributor-run and contributor-funded, it never enters the official aggregate, and it is not comparable to an official row: the lane changes the treatment, not just the model.

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
- run compatibility hash
- compatible-shard group ID
- contributor credit per shard

Composite rows can roll up compatible shards only when their compatible-shard group (family, scoring mode, and suite version), adapter ID/version, model key, sandbox policy hash, and run compatibility hash match, and task IDs do not overlap. The canonical `run-compatibility.json` preimage retains the task-index identity, adapter identities, resolved adapter capabilities, model configuration, a sandbox-policy commitment, and incomplete-run policy while excluding the partial selection, run ID, scheduling parallelism, local command paths, mount paths, and provider environment-variable names. Its digest is cross-checked against the hashed local run manifest before aggregation, and the full run config hash remains in each source shard as provenance. Older submissions without a compatibility hash remain valid as single-shard rows but do not compose until they are repackaged with the new provenance field. Composite rows publish a deterministic hash and label for the combined task selection, retain every source selection and run hash, credit each underlying shard, and link back to every submission.

## Community Aggregate Outputs

`legalforecast multiharness community aggregate` rebuilds a public bundle under the requested output directory. Current outputs include `registry/` indexes, `reports/` JSON/CSV/Markdown/HTML comparisons, per-submission public JSON under `submissions/`, a generated `site/`, and root `artifact-index.json` / `artifact-manifest.json` files.

## Pull Request Intake

Open a PR that adds only the submission package under `community/submissions/<year>/<submission_id>/`. The community validation workflow runs with read-only repository permissions and without official benchmark environments, OIDC, AWS credentials, or provider secrets. On merge to `main`, the workflow rebuilds the community aggregate and uploads the generated registry, reports, and static site as a build artifact from accepted submission metadata.

Harvey LAB is a separate Harvey AI project and task corpus. Any submission using Harvey LAB tasks must preserve Harvey LAB credit/license language. Final public branding and positioning for LegalForecastBench, Legal Quants, and any Harvey LAB comparison remains subject to John Hughes/Legal Quants approval.
