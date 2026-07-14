# Official Run Runbook

This is the operator checklist for `.github/workflows/run-benchmark.yaml` on the current `main` branch. The workflow builds the matrix, runs isolated provider cells, resumes complete matching cells from the durable S3 result store, aggregates successful artifacts, and publishes the public aggregate to S3.

## Acquisition Downstream Preflight

### Bounded Firecrawl terminal-target recovery (compatibility fallback only)

The official happy path is the CourtListener REST workflow documented under [Cycle 1 Batch-002 CourtListener-First Acquisition](#cycle-1-batch-002-courtlistener-first-acquisition). Use Firecrawl only as a compatibility fallback when a required search is not exposed by a supported CourtListener API. Case.dev may supply an optional free upstream or bulk lookup only when its response is equivalent to the CourtListener data needed at that step; it is never the final authority for paid gaps and must not perform a fee-bearing fetch.

`discover-firecrawl-recap --resume` deliberately does not retry a nontransient `terminal_error`. If a primary discovery fails for that reason, run exactly one child recovery with a unique run ID, `--proxy enhanced`, `--force-browser`, and `--recover-terminal-errors-from-run <primary-run-id>`. If bounded fresh runs were already attempted, repeat `--reuse-verified-pages-from-run <run-id>` for each one. The command verifies that every source uses the exact frozen batch/query plan, SHA-checks and deduplicates successful pages by search URL, rejects conflicting bytes, routes only still-unresolved evidenced terminal URLs through the child, resumes newly revealed continuation pages under the parent's immutable scheduler settings, shares the cycle-wide credit cap, and refuses both recovery chaining and a second child of the same parent.

Generated or private acquisition runbooks must guard each primary discovery explicitly and let either command's failure stop the script. Never use `|| true`. Repeat every frozen batch/window/query argument byte-for-byte in the recovery command; only the child run ID, recovery flag, proxy, and browser setting differ:

```zsh
if uv run legalforecast acquisition discover-firecrawl-recap \
  --output-root "$cycle_root" --cycle-store "$cycle_store" \
  --batch-id "$batch_id" --run-id "$primary_run_id" \
  --eligibility-anchor "$anchor" --search-window-start "$window_start" \
  --search-window-end "$window_end" "${frozen_query_args[@]}" \
  --credit-cap 45000 --live-firecrawl --execute --resume; then
  discovery_prefix="$batch_id"
else
  recovery_run_id="${primary_run_id}-recovery-1"
  uv run legalforecast acquisition discover-firecrawl-recap \
    --output-root "$cycle_root" --cycle-store "$cycle_store" \
    --batch-id "$batch_id" --run-id "$recovery_run_id" \
    --recover-terminal-errors-from-run "$primary_run_id" \
    --eligibility-anchor "$anchor" --search-window-start "$window_start" \
    --search-window-end "$window_end" "${frozen_query_args[@]}" \
    --credit-cap 45000 --proxy enhanced --force-browser \
    --live-firecrawl --execute --resume
  discovery_prefix="$recovery_run_id"
fi
```

Recovery outputs default to `checkpoints/<recovery-run-id>-recap-{entries,dockets,summary}.*` so they cannot overwrite the primary batch paths. Every downstream command in that runbook must consume `$discovery_prefix` rather than assuming the primary batch filename. The recovery summary and failure run card include parent lineage and both runs' reconcilable budget evidence.

Do not substitute a parser. The LegalForecastBench wrapper pins the reviewed parser revision `9402306972462a5bdd0da7f687c5e6b4cea373a0`, verifies that checkout is clean, requires a nonempty `MISTRAL_API_KEY`, and constructs the parser child environment from only that key, `PATH`, the environment-only fallback guard, and nonempty locale variables.

The live parser may run only from the dedicated development path `/agents/sandbox/legalforecastbench/parser`, containing only `MISTRAL_API_KEY`. If the path is absent or exposes any additional secret name, stop the parse stage. Verify names only, never values:

```bash
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench/parser \
  -- zsh -lc 'for n in MISTRAL_API_KEY; do [[ -n ${(P)n:-} ]] && print -- "$n=present" || print -- "$n=missing"; done'
```

Run the live parse against the clean pinned checkout explicitly; the default parser checkout may be on a different revision and will correctly fail closed:

```bash
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench/parser \
  -- uv run legalforecast acquisition parse-documents \
  --output-root <assembled-cycle-root> \
  --requests <parse-document-requests.jsonl> \
  --disclosure-clearance <disclosure-clearance.jsonl> \
  --parser-root /work/Development/.worktrees/parser/fix/env-only-api-keys \
  --execute --resume
```

The sentinel-`op` and child-environment tests in `tests/test_mistral_markdown_parser.py` enforce the subprocess boundary, but they do not authorize injecting a broad acquisition secret set into the parent process.

After Stage B labeling completes, freeze the single cycle-level reliability sample before any lawyer adjudication:

```bash
uv run legalforecast acquisition plan-label-audit \
  --output-root <assembled-cycle-root> \
  --llm-label-audit <llm-label-audit.jsonl> \
  --selection <selection.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --decision-texts <decision-texts.jsonl> \
  --labeling-policy <precommitted-labeling-policy.json> \
  --lawyer-review-queue <lawyer-review-queue.jsonl> \
  --execute --no-resume
```

Keep `llm-label-audit-cycle-planned.jsonl`, `cycle-label-audit-plan.json`, and the merged review queue in controlled private storage for lawyer review. The only check-in-safe outputs are `cycle-label-audit-summary.json` and `adjudication-routing-summary.json`; both are redacted and hash-bound to the private plan. Supply the plan and the same precommitted policy back to `apply-lawyer-review` with `--cycle-label-audit-plan` and `--labeling-policy`; audit-sample adjudications do not replace unanimous model labels.

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

The resume identity includes the case, ablation, packet hash, solver/model identity, registry content, and repeat count. Current results bind to the canonical per-model registry-entry hash, so an unchanged model can resume across a registry amendment. Pre-amendment durable metrics that lack that field instead validate against the exact whole-registry hash recorded by their freeze in the provenance chain; supply that historical registry when recovering those cells. An unknown or mismatched registry hash fails closed rather than re-evaluating and overwriting durable outputs. Failed cells do not become canonical score rows. Preserve failed logs for audit.

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

## Add Models To A Frozen Cycle

Treat a staged model addition as an amendment to the existing freeze, not as a new cycle and never as an edit to the original bundle. Preserve the original freeze and registry at their committed paths, write the superset registry at a new path, and create a new bundle that points to the freeze it amends:

```bash
uv run legalforecast freeze amend \
  --prior-bundle manifests/<cycle_id>.freeze.json \
  --model-registry model_registries/<cycle_id>.amendment-1.json \
  --root . \
  --bundle-output manifests/<cycle_id>.amendment-1.freeze.json
```

For a second or later amendment, repeat `--amendment-bundle <ancestor.freeze.json>` for every earlier ancestor needed to reach the original freeze. Commit the new registry and amendment bundle before dispatch. The amendment command fails closed unless the registry is a strict superset, every existing model entry has the same canonical entry hash, the cycle and all non-registry artifact hashes are unchanged, and the added models do not move the original release anchor.

Dispatch with `freeze_bundle_path` set to the new amendment bundle, `model_registry_uri` set to its superset registry, and `model_keys` containing exactly the newly added keys. Do not include a previously dispatched model. Supply `prior_dispatches_json` as a JSON array containing each earlier canonical workflow run, its attempt, its freeze hash, and the models introduced by that freeze; for example:

```json
[
  {
    "workflow_run_id": "1001",
    "workflow_run_attempt": 1,
    "freeze_bundle_sha256": "<original_bundle_sha256>",
    "model_keys": ["provider:model-a"]
  }
]
```

The workflow walks the committed freeze chain and rechecks the amendment invariants before matrix construction. It then rejects the dispatch unless the requested matrix keys exactly equal the models introduced by the selected freeze, so existing cells never enter the matrix. Resume remains enabled, but it is a recovery guard rather than the mechanism that protects old outputs.

After the added-model cells finish, the aggregate job downloads and materializes the durable union under `s3://$LFB_RESULTS_BUCKET/per-case/<cycle_id>/`, validates coverage against every model in the superset registry, and embeds `dispatch_provenance` in the aggregate run card. For local recovery, use the same union tree and provenance artifact:

```bash
uv run legalforecast publish aggregate \
  --per-case-dir tmp/official-downloads/<cycle_id>/union \
  --run-input-manifest manifests/<cycle_id>.run-inputs.json \
  --model-registry model_registries/<cycle_id>.amendment-1.json \
  --dispatch-provenance tmp/official-downloads/<cycle_id>/lfb-dispatch-provenance.json \
  --labels private/labels/<cycle_id>.labels.jsonl \
  --output-dir tmp/official-aggregate/<cycle_id> \
  --cycle-id <cycle_id> \
  --cycle-series <pilot|rapid|official|annual_aggregate> \
  --clean-motion-count <count> \
  --prediction-unit-count <count> \
  --allow-no-baselines
```

Re-render the site from that complete union bundle and publish it to the same cycle report location. The new run card marks this as `additive_supersession` and points to the report it supersedes. Do not use the withdrawal path: the original model rows remain canonical and the amended publication only adds the new rows.

## Staged-Rollout Rehearsal Drill

Extend the ue7.32 fixture rehearsal with this sequence before the real amendment dispatch:

1. Freeze and run fixture model A, aggregate it, and save SHA-256 checksums for every file in A's per-case artifact directory.
2. Create an amendment freeze whose registry adds fixture model B, then dispatch only B with the original dispatch in `prior_dispatches_json`.
3. Materialize the union, aggregate against the two-model registry with `--dispatch-provenance`, and confirm the leaderboard contains exactly A and B.
4. Recompute A's per-case artifact checksums and require an exact match with the pre-amendment checksum set. Any added, removed, or changed A artifact fails the drill as evidence of possible silent re-sampling.
5. Confirm the amended run card lists both dispatches, both freezes in order, A mapped to the original freeze, B mapped to the amendment freeze, and publication mode `additive_supersession`.

The automated rehearsal in `tests/test_official_run_runbook.py` performs the same two-generation aggregation and byte-identity assertion. The live ue7.32 log must still record the workflow run IDs, S3 union location, aggregate artifact, and checksum result for operator sign-off.

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

## Cycle 1 Batch-002 CourtListener-First Acquisition

The canonical hierarchy is `batch-002 discover` → `batch-002 observe` → `batch-002 snapshot` → `acquisition prepare-target-100`. CourtListener REST v4 is the primary discovery and reconstruction source and the final authority for unresolved paid gaps. Case.dev is permitted only as an optional free equivalent upstream or bulk source; Firecrawl is a compatibility fallback only when a required search is unavailable through a supported CourtListener API. Run the batch commands against the official acquisition store, never a batch-001 store, and do not skip directly from mutable observations to preparation.

### Token Prerequisite

Reconstruction reads the token-required `dockets`/`docket-entries` endpoints, so `observe` and any live reconstruction require an API token:

```bash
export COURTLISTENER_API_TOKEN=…   # Authorization: Token <token>
```

The `discover` search index answers anonymously (it is paced at ~3s/request without a token, 0s with one), but `observe` fails closed before any network call when the token is absent. The moment the token is set, the three commands below are runnable end to end.

### Step 1: Discover

Attach batch-002 and materialize each frozen decision-first term before attempting any observation:

```bash
uv run legalforecast batch-002 discover \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --live
```

### First-Run Observation Smoke Step (required)

After discovery has attached the batch and materialized candidates, validate the live foreign-key and ordering assumptions with a **single** reconstruction before observing the full backlog:

```bash
uv run legalforecast batch-002 observe \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --live --limit 1
```

If that one reconstruction succeeds (the tally shows `observed: 1`), the docket foreign-key shape and entry ordering are sound and the full sweep is safe. If it fails closed, stop and inspect before spending the backlog.

### Step 2: Seed Optional Leads, Then Observe

```bash
# 2. (Optional) Seed batch-001 Case.dev enrichment failures as re-observation leads.
uv run legalforecast batch-002 seed-batch-001-leads \
  --source-store artifacts/cycle-1/batch-001-zero-paid/cycle-acquisition.sqlite3 \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3

# Observe: reconstruct + strict-screen every unresolved candidate.
uv run legalforecast batch-002 observe \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --live
```

`discover` and `observe` are both resumable: re-running `discover` continues from durable per-term cursors, and re-running `observe` skips candidates that already carry a current observation (candidates whose only prior result was a transient failure are retried). `seed-batch-001-leads` is idempotent — a second run finds the re-observation term already terminal and seeds nothing new.

### Step 3: Freeze The Complete Saturated Snapshot

Do not choose or rank the cheapest cases from a partial candidate set. After observation is complete, require the discovery summary to report `complete: true` and `saturated: true`, then freeze the full viable screened cohort:

```bash
uv run legalforecast batch-002 snapshot \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --snapshot-id <immutable-snapshot-id> \
  --output-root artifacts/cycle-1/official-acquisition/snapshots
```

Record the snapshot manifest's exact `cycle_hash`. `prepare-target-100` rejects a partial, unsaturated, changed, or wrong-cycle snapshot and carries every viable snapshot row through authoritative public-document and paid-gap resolution. Its budget is provisional until disclosure clearance removes unsafe documents and `project-target-cohort` recomputes the frontier.

### Step 4: Prepare The Resolved Pool And Provisional Budget

Run the public-first preparation chain from that immutable snapshot. This command plans public downloads, downloads free documents, resolves remaining gap metadata through authenticated noncharging CourtListener REST, applies the core-document filter, and emits disclosure-review requests plus a provisional 100-case budget. It never purchases a document.

```bash
uv run legalforecast acquisition prepare-target-100 \
  --output-root artifacts/cycle-1/official-acquisition/target-100 \
  --snapshot artifacts/cycle-1/official-acquisition/snapshots/<immutable-snapshot-id> \
  --expected-cycle-hash <snapshot-cycle-hash> \
  --live-public-download \
  --live-courtlistener \
  --request-ledger artifacts/cycle-1/official-acquisition/courtlistener-requests.sqlite3 \
  --execute --resume
```

The successful preparation summary commits the snapshot, immutable semantic configuration, stage inputs and outputs, provisional selected candidate IDs, and cost frontier. The `06-clearance-inputs/` directory contains one restriction-evidence row and one disclosure-review request for every downloaded free document. The summary deliberately names `clear-disclosures`, not purchase, as the next stage.

### Step 5: Clear Every Free Document And Freeze The Exact Cohort

Complete the authenticated legal-review artifact and its controlled-store receipt, then run the existing clearance gate over the full free manifest. Do not hand-edit any preparation artifact.

```bash
uv run legalforecast acquisition clear-disclosures \
  --output-root artifacts/cycle-1/official-acquisition/target-100/free-clearance \
  --download-manifest artifacts/cycle-1/official-acquisition/target-100/03c-merged-downloads/document-downloads-merged.jsonl \
  --document-root artifacts/cycle-1/official-acquisition/target-100/documents/free \
  --reviews <controlled-store-review-export.jsonl> \
  --review-receipt <controlled-store-review-receipt.json> \
  --restriction-evidence artifacts/cycle-1/official-acquisition/target-100/06-clearance-inputs/restriction-evidence.jsonl \
  --execute
```

Only after clearance succeeds may the exact downstream cohort be projected. This recomputes the cheapest complete frontier after quarantines and writes selection, relevance, restriction, manifest, clearance, budget, and exclusion artifacts containing exactly the chosen cases.

```bash
uv run legalforecast acquisition project-target-cohort \
  --output-root artifacts/cycle-1/official-acquisition/target-100/exact-cohort \
  --selection artifacts/cycle-1/official-acquisition/target-100/03-gap-bridge/public-packet-selection-reconciled.jsonl \
  --case-relevance artifacts/cycle-1/official-acquisition/target-100/03-gap-bridge/case-relevance.jsonl \
  --download-manifest artifacts/cycle-1/official-acquisition/target-100/03c-merged-downloads/document-downloads-merged.jsonl \
  --disclosure-clearance artifacts/cycle-1/official-acquisition/target-100/free-clearance/disclosure-clearance.jsonl \
  --clearance-run-card artifacts/cycle-1/official-acquisition/target-100/free-clearance/run-cards/clear-disclosures.json \
  --restriction-evidence artifacts/cycle-1/official-acquisition/target-100/06-clearance-inputs/restriction-evidence.jsonl \
  --preparation-summary artifacts/cycle-1/official-acquisition/target-100/target-100-preparation-summary.json \
  --preparation-config artifacts/cycle-1/official-acquisition/target-100/target-100-config.json \
  --snapshot-manifest artifacts/cycle-1/official-acquisition/snapshots/<immutable-snapshot-id>/manifest.json \
  --target-case-count 100 \
  --execute --resume
```

If fewer than 100 post-clearance cases fit the unchanged cap, acquire more candidates rather than restoring a quarantined case or weakening a gate. The exact-cohort summary binds every source and output hash and reconciles every unselected resolved-pool candidate into `target-cohort-exclusions.jsonl`.

### Step 6: Generate The Broker Allowlist, Then Purchase Explicitly

Paid acquisition remains a separate, operator-visible stage. First freeze the cohort and purchase-policy artifacts required by the CLI, then generate the signed RECAP Fetch broker allowlist from the exact post-clearance outputs:

```bash
uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy <verified-purchase-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --budget-plan artifacts/cycle-1/official-acquisition/target-100/exact-cohort/missing-core-budget-plan.json \
  --selection artifacts/cycle-1/official-acquisition/target-100/exact-cohort/target-cohort-selection.jsonl \
  --output artifacts/cycle-1/official-acquisition/target-100/courtlistener-recap-fetch-policy-v1.json
```

Inspect the projected total, allowlisted numeric RECAP document IDs, and remaining budget before invoking the only fee-bearing happy path:

The allowlist accepts explicit-public proof or the exact current CourtListener REST paid-gap evidence contract.
Case.dev may support noncharging search and docket enrichment, but its legacy paid-unknown evidence is never purchase authority.

```bash
uv run legalforecast acquisition purchase-missing-recap-fetch \
  --output-root artifacts/cycle-1/official-acquisition/target-100 \
  --budget-plan artifacts/cycle-1/official-acquisition/target-100/exact-cohort/missing-core-budget-plan.json \
  --selection artifacts/cycle-1/official-acquisition/target-100/exact-cohort/target-cohort-selection.jsonl \
  --purchase-policy <verified-purchase-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --purchase-ledger artifacts/cycle-1/official-acquisition/recap-fetch-purchases.sqlite3 \
  --request-ledger artifacts/cycle-1/official-acquisition/courtlistener-requests.sqlite3 \
  --live-purchase --acknowledge-pacer-fees \
  --execute --resume
```

Never substitute a Case.dev live purchase, a Case.dev fee-bearing docket refresh, or an implicit purchase inside preparation. The RECAP Fetch purchase stage may dispatch only IDs present in the generated broker policy and remains bounded by the verified purchase policy and broker-side budget controls.

### Expected Volumes

The June 30 – July 12 decision-window backlog is roughly ~830 dockets. `seed-batch-001-leads` additionally carries the batch-001 candidates that never reached a terminal observation (the ~608 Case.dev enrichment failures, identified as `current_observation_id IS NULL` in the batch-001 store) into batch-002 for re-observation through the API route.

### Reading The Tallies

Each command prints a machine-readable JSON summary to stdout (use `--summary-output PATH` to also persist it):

- `discover` funnel: `terms_terminal`/`terms_total` (how many frozen terms reached a bounded terminal state), `total_hits` (raw document hits), `distinct_candidates` (deduped dockets), `prescreen_exclusions_by_reason` (bankruptcy/criminal dockets dropped before any fetch), and `per_term` progress. `complete: true` means every term is bounded; `saturated: true` means every term was exhausted rather than limit-bound.
- `observe` tally: `considered` (candidates scanned), `skipped_already_observed` (resume skips), `observed` (fetched this pass), `eligible` (strict-clean accepted), `excluded_by_reason` (immutable/posture exclusions, with the underlying strict-screen reason surfaced as `strict_clean_screen_failed:<screen_reason>`), and `transient_by_reason` (retryable failures to re-run).
- `seed-batch-001-leads`: `leads_selected`, `leads_seeded`, and `already_seeded`.
