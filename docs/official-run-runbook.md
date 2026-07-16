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

Unitize Stage A only from that exact authenticated materialization and pinned live-parser lineage. Use one explicit provider journal for the cycle; creating a fresh output-root-local journal is refused because it would reset the cycle reservation ledger:

```bash
uv run legalforecast acquisition llm-unitize \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --selection-run-card <project-or-extend-target-cohort-run-card.json> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --document-root <materialized-document-root> \
  --parse-requests <parse-document-requests.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parser-run-card <parse-documents-run-card.json> \
  --markdown-root <parsed-markdown-root> \
  --model-registry <frozen-stage-a-registry.json> \
  --model-key <provider:model-id> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --execute --no-resume
```

Before any provider call, the command replays the target selection, immutable materializer, parse requests, pinned live-Mistral card, parser manifest, and complete Markdown tree. It rejects provider caps whose `cycle_id` differs from the authenticated cohort. The journal stores an immutable v2 identity containing that cycle ID, the exact caps-artifact hash, and its canonical path; copying it to another output root or opening it with changed caps is refused. The completed run card commits the journal schema and identity, exact registry entry, caps artifact, prompts, settled provider attempts, reconstructed units, raw outputs, audit, and review queue. A partial `--continue-on-error` run remains resumable but is explicitly marked incomplete and is inadmissible downstream.

Run the structural Stage A review against the same unitizer card, caps artifact, and canonical provider journal even when its ordinary outputs live under a different root:

```bash
uv run legalforecast acquisition llm-review-stage-a \
  --output-root <structural-review-root> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --markdown-root <parsed-markdown-root> \
  --prediction-units <prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --unitization-review-queue <unitization-review-queue.jsonl> \
  --model-registry <frozen-stage-a-reviewer-registry.json> \
  --model-key <provider:model-id> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --execute --no-resume
```

The command replays Stage A before resolving the reviewer model, refuses a different journal path, wrong cycle, or byte-different caps artifact before a provider call, and commits the exact reviewer model, prompt identities, provider attempts, input artifacts, merged queue, flags, and audit in its run card.

After structural review, apply adjudications only through the authenticated unitizer card:

```bash
uv run legalforecast acquisition apply-unitization-review \
  --output-root <assembled-cycle-root> \
  --prediction-units <prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --llm-review-stage-a-run-card <llm-review-stage-a-run-card.json> \
  --unitization-review-queue <verified-merged-review-queue.jsonl> \
  --adjudications <unitization-adjudications.jsonl> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --execute --no-resume
```

The apply card propagates the unitizer and structural-review cards plus the exact caps and journal authority, and commits the raw units, authenticated merged queue, adjudications, and replayed finalized units. Neither this command nor finalization accepts a rehashed, hand-authored, cross-cohort, cross-model, prompt-substituted, or independently regenerated Stage A artifact.

Build the Stage B disposition-text artifact only from the exact selected cohort, authenticated download manifest, authenticated disclosure-clearance run card, restriction evidence, and pinned Mistral parser output used by the cycle:

```bash
uv run legalforecast acquisition build-decision-texts \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --selection-run-card <project-or-extend-target-cohort-run-card.json> \
  --download-manifest <download-manifest.jsonl> \
  --disclosure-clearance <disclosure-clearance.jsonl> \
  --clearance-run-card <clear-disclosures-run-card.json> \
  --restriction-evidence <restriction-evidence.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parser-run-card <parse-documents-run-card.json> \
  --markdown-root <parsed-markdown-root> \
  --decision-texts-output <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest-output <assembled-cycle-root>/decision-texts-manifest.json \
  --execute --no-resume
```

The command reconciles exact candidate and document coverage; verifies the target-cohort, authenticated clearance, and live-parser run-card commitments; admits only the single public, outcome-bearing, non-model-visible first written disposition entered on or after the Cycle 1 anchor; and binds the source and extracted-text hashes to the pinned parser revision. Fixture parser provenance is refused. It fails closed on missing, ambiguous, sealed, private, malformed restriction flags, unpinned, unauthenticated, or drifted inputs. `decision-texts.jsonl` is private Stage B and audit input only: never place it in a model-visible packet, hand-edit it, or substitute a manually assembled file.

Pass that exact artifact, its immutable manifest, and the completed builder run card to Stage B. The parser manifest and Markdown remain required only to cross-check the authenticated artifact against the pinned live-Mistral lineage; `llm-label` never uses Markdown directly as prompt authority:

```bash
uv run legalforecast acquisition llm-label \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --markdown-root <parsed-markdown-root> \
  --decision-texts <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest <assembled-cycle-root>/decision-texts-manifest.json \
  --decision-texts-run-card <assembled-cycle-root>/run-cards/build-decision-texts.json \
  --prediction-units <finalized-prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --llm-review-stage-a-run-card <llm-review-stage-a-run-card.json> \
  --unitization-review-run-card <apply-unitization-review-run-card.json> \
  --llm-label-run-card <llm-label-run-card.json> \
  --model-registry <frozen-stage-b-judge-registry.json> \
  --evaluated-model-registry <frozen-evaluated-model-registry.json> \
  --model-key <provider:model-id> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --execute --no-resume
```

Repeat `--model-key` for every entry in the frozen judge registry. Before the first provider reservation, the command replays the authenticated unitizer, structural-review, and apply-review cards; verifies exact candidate and case mapping, decision-document, disposition-date, text, text-hash, source hash and byte count, empty parser quality flags, selection, parser, and finalized-unit coverage and provenance; and requires the same canonical journal and exact caps artifact used by Stage A. It binds the decision JSONL, manifest, run-card, per-record, and text hashes plus the exact finalized-units file, candidate-envelope hashes, full Stage A card chain, journal identity, and stage-specific settled attempts into the label audit and `llm-label` run card. Changing `--output-root` cannot create a new ledger because `--provider-journal` must still resolve to the unitizer-committed canonical path. Any mismatch stops the stage without a provider call.

After Stage B labeling completes, freeze the single cycle-level reliability sample before any lawyer adjudication:

```bash
uv run legalforecast acquisition plan-label-audit \
  --output-root <assembled-cycle-root> \
  --llm-label-audit <llm-label-audit.jsonl> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --markdown-root <parsed-markdown-root> \
  --decision-texts <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest <assembled-cycle-root>/decision-texts-manifest.json \
  --decision-texts-run-card <assembled-cycle-root>/run-cards/build-decision-texts.json \
  --labeling-policy <precommitted-labeling-policy.json> \
  --lawyer-review-queue <lawyer-review-queue.jsonl> \
  --execute --no-resume
```

Keep `llm-label-audit-cycle-planned.jsonl`, `cycle-label-audit-plan.json`, and the merged review queue in controlled private storage for lawyer review. The only check-in-safe outputs are `cycle-label-audit-summary.json` and `adjudication-routing-summary.json`; both are redacted and hash-bound to the private plan. Supply the plan and the same precommitted policy back to `apply-lawyer-review` with `--cycle-label-audit-plan` and `--labeling-policy`; audit-sample adjudications do not replace unanimous model labels.

```bash
uv run legalforecast acquisition apply-lawyer-review \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --markdown-root <parsed-markdown-root> \
  --labels <labels.jsonl> \
  --adjudications <checked-in-lawyer-adjudications.jsonl> \
  --decision-texts <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest <assembled-cycle-root>/decision-texts-manifest.json \
  --decision-texts-run-card <assembled-cycle-root>/run-cards/build-decision-texts.json \
  --llm-label-audit <assembled-cycle-root>/llm-label-audit-cycle-planned.jsonl \
  --cycle-label-audit-plan <assembled-cycle-root>/cycle-label-audit-plan.json \
  --labeling-policy <precommitted-labeling-policy.json> \
  --execute --no-resume
```

Plan official packet inputs only from the canonical discovery snapshot's committed raw-artifact manifest:

```bash
uv run legalforecast acquisition plan-packet-inputs \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --download-manifest <download-manifest.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --disclosure-clearance <disclosure-clearance.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --model-registry model_registries/cycle-1-2026-06-30.json \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --execute --no-resume
```

The executed command refuses an omitted manifest. Use the final `union-screening-snapshots` output root, not a guessed directory inside its exported snapshot. A numeric target-selection candidate ID may bind only to the exact canonical `courtlistener-docket-<same-digits>` manifest identity; a bare numeric manifest identity is refused. The loader accepts the direct canonical `<docket-id>.html` layout and the union-owned `<namespaced-candidate-id>/<sha256>.html` layout, verifying the path ownership and content commitment in either case. The planner preserves both IDs, the original manifest path, byte count, and SHA-256 in audit provenance; it fails closed on nonnumeric reserved aliases, exact-versus-namespaced collisions, multiple candidate owners, missing ownership, duplicate paths, cross-candidate path substitution, or content/hash drift. Never rename raw-artifact candidate IDs or hand-edit the manifest to make packet planning pass.

Build packets only after the packet-input plan succeeds:

```bash
uv run legalforecast acquisition build-packets \
  --output-root <assembled-cycle-root> \
  --input <assembled-cycle-root>/packet-build-input.jsonl \
  --packet-input-run-card <assembled-cycle-root>/run-cards/plan-packet-inputs.json \
  --selection <selection.jsonl> \
  --download-manifest <download-manifest.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parser-run-card <parse-documents-run-card.json> \
  --disclosure-clearance <disclosure-clearance.jsonl> \
  --raw-prediction-units <raw-prediction-units.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --llm-unitization-audit <llm-unitization-audit.jsonl> \
  --original-unitization-review-queue <original-review-queue.jsonl> \
  --stage-a-structural-flags <stage-a-structural-flags.jsonl> \
  --stage-a-structural-review-audit <stage-a-structural-review-audit.jsonl> \
  --stage-a-review-model-registry <stage-a-review-model-registry.json> \
  --stage-a-review-model-key <stage-a-review-model-key> \
  --unitization-review-queue <merged-unitization-review-queue.jsonl> \
  --unitization-review-adjudications <john-adjudications.jsonl> \
  --model-registry model_registries/cycle-1-2026-06-30.json \
  --expected-model-registry-sha256 <sha256-of-frozen-registry> \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --document-root <materialized-document-root> \
  --markdown-root <parsed-markdown-root> \
  --materialization-run-card <materialization-run-card.json> \
  --execute --no-resume
```

Final corpus reconciliation runs only after both packet stages complete. It consumes the authenticated decision-text JSONL, its manifest and completed builder run card, and the three content files from one canonical complete and saturated screening snapshot plus that snapshot's manifest:

Executed packet-planner cards commit every deterministic parameter and exact source file, and executed packet-builder cards commit the selected ablation and all three outputs. `build-packets` replays planning byte-for-byte, authenticates the raw docket bytes against the materializer's screening snapshot, authenticates the parser manifest and finalized Stage A units against their upstream run cards, and requires the evaluated registry to match the separately frozen SHA-256 supplied by the operator. `finalize-corpus --execute` repeats those authorities and replays both planning and packet assembly before accepting the cards. Never hand-author, rehash, or repair these cards or their committed artifacts.

```bash
uv run legalforecast acquisition finalize-corpus \
  <all-other-stage-inputs> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parse-plan-run-card <plan-parser-inputs-run-card.json> \
  --parser-run-card <parse-documents-run-card.json> \
  --raw-prediction-units <prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --llm-review-stage-a-run-card <llm-review-stage-a-run-card.json> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --prediction-units <finalized-prediction-units.jsonl> \
  --unitization-review-run-card <apply-unitization-review-run-card.json> \
  --markdown-root <parsed-markdown-root> \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --decision-texts <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest <assembled-cycle-root>/decision-texts-manifest.json \
  --decision-texts-run-card <assembled-cycle-root>/run-cards/build-decision-texts.json \
  --packet-build-input <assembled-cycle-root>/packet-build-input.jsonl \
  --packets <assembled-cycle-root>/packets.jsonl \
  --model-registry model_registries/cycle-1-2026-06-30.json \
  --expected-model-registry-sha256 <sha256-of-frozen-registry> \
  --screened-cases <screening-snapshot>/screened-cases.jsonl \
  --discovery-summary <screening-snapshot>/summary.json \
  --discovery-exclusions <screening-snapshot>/exclusions.jsonl \
  --screening-snapshot-manifest <screening-snapshot>/manifest.json \
  --screening-cycle-store <assembled-cycle-root>/store/cycle-acquisition.sqlite3 \
  --target-cohort-preparation-root <successful-target-cohort-root> \
  --target-clean-cases <100-or-150> \
  --execute --no-resume
```

Do not hand-author a compatibility summary or substitute a replay-stage summary. `finalize-corpus` requires the successful canonical `prepare-target-cohort` root, verifies its self-hashed configuration, completion evidence, and exhaustive stage commitments, and uses that authenticated lineage to pin the exact snapshot path, manifest hash, cycle hash, batch digest, and target size. It replays the authenticated unitizer and structural-review cards against the exact raw units, original and merged review queues, structural flags, review audit, reviewer registry and key, provider-caps bytes, and canonical shared journal before accepting and reproducing the apply-review output. It then replays the authenticated `llm-label` card against the same Stage A authority, exact decision-text inputs, judge registry, journaled per-model reconstructions, labels, audit, and original lawyer queue. Finally it verifies the snapshot's immutable cycle-store registration, complete and saturated state, member hashes, row counts, and accepted-plus-excluded reconciliation, and accepts the packet artifacts only after those gates pass. Include every later exclusion file separately with `--exclusion-source` so every screened-but-unselected or downstream-rejected candidate reaches the complete exclusion ledger.

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

The preferred hierarchy is saturated CourtListener search → `batch-002 seed-direct-search` → authenticated `batch-002 observe` → `batch-002 snapshot` → `acquisition prepare-target-cohort --target-case-count 150`. CourtListener remains the source for decision results, docket reconstruction, free RECAP documents, authoritative paid-gap metadata, and every RECAP Fetch purchase. Firecrawl is used only for the demonstrated CourtListener search and docket-HTML surface gap, as a compatibility fallback when authenticated REST cannot supply the required surface; it does not become a legal-data or purchase authority. Case.dev is used only for equivalent free lookup and prioritization; no Case.dev live PACER fetch or purchase is permitted. Run every stage against the official acquisition store, never a batch-001 store, and do not pass mutable checkpoints directly to preparation.

### Credential Prerequisites

The search and docket-HTML stages require Firecrawl, the optional-equivalent enrichment stage requires Case.dev, and the later CourtListener REST paid-gap bridge requires the CourtListener token:

```bash
export FIRECRAWL_API_KEY=…
export CASE_DEV_API_KEY=…
export COURTLISTENER_API_TOKEN=…
```

Each command fails closed when its stage-specific key is absent. Firecrawl consumes only the preauthorized cycle credit allowance. Case.dev enrichment is free lookup only. None of Steps 1–5 acknowledges PACER fees or purchases a document.

### Step 1: Search CourtListener Decisions Through Firecrawl

CourtListener does not expose the required decision-first `type=r` search through the supported API route. Materialize the frozen CourtListener search pages through Firecrawl, with the eligibility anchor separate from the bounded search window:

```bash
uv run legalforecast acquisition discover-firecrawl-recap-decisions \
  --output-root artifacts/cycle-1/official-acquisition/decision-search \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id batch-002-decision-search \
  --run-id batch-002-decision-search-primary \
  --eligibility-anchor 2026-06-30 \
  --search-window-start 2026-06-30 \
  --search-window-end 2026-07-14 \
  --credit-cap 45000 \
  --live-firecrawl \
  --dockets-output artifacts/cycle-1/official-acquisition/decision-search/decision-dockets.jsonl \
  --execute --resume
```

The command completes every frozen query term and page before publishing the potential-docket file. A partial checkpoint is not a saturated discovery result and must not proceed downstream.

### Preferred REST Transfer Before Compatibility Steps 2 And 3

When discovery already committed a saturated `provider: courtlistener` batch, reuse that exact docket union without searching again or scraping docket HTML. The transfer is provider-free: it verifies every frozen source term is exhausted, canonicalizes numeric docket IDs, commits a hash of the exact source candidate set and all contributing search-hit payloads, and preserves only safe metadata prescreens plus the minimum positive triggering entry number.

```bash
uv run legalforecast batch-002 seed-direct-search \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <saturated-direct-search-batch-id> \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <new-rest-screen-batch-id> \
  --page-size 100 \
  --summary-output artifacts/cycle-1/official-acquisition/direct-search-transfer.json
```

Reconstruct and strictly screen the transferred dockets through authenticated CourtListener REST. The durable request ledger enforces the configured minute, hour, and day ceilings; stopping at a ceiling is resumable and does not change candidate membership.

```bash
uv run legalforecast batch-002 observe \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <new-rest-screen-batch-id> \
  --eligibility-anchor 2026-06-30 \
  --live \
  --request-ledger artifacts/cycle-1/official-acquisition/courtlistener-requests.sqlite3 \
  --courtlistener-rate-profile base \
  --summary-output artifacts/cycle-1/official-acquisition/rest-screen-summary.json
```

Only after every transferred candidate is terminal, publish the immutable REST snapshot:

```bash
uv run legalforecast batch-002 snapshot \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <new-rest-screen-batch-id> \
  --snapshot-id <new-rest-screen-batch-id>-complete \
  --output-root artifacts/cycle-1/official-acquisition/snapshots
```

This REST path supersedes the Case.dev-ranking and Firecrawl-docket steps below whenever it is available. Retain those steps only as bounded compatibility fallbacks for genuine REST-unavailable dockets.

### Step 2: Enrich And Rank With Free Case.dev Lookup

Use Case.dev only for noncharging docket lookup and `includeEntries` enrichment. The authenticated source mode accepts either a saturated CourtListener opinion search (`search_type=o`) or a saturated unrestricted RECAP search (`search_type=r`) whose frozen config records `available_only=omitted`. It projects only the exact positive numeric docket identities committed by that source; it never sends `live: true`, acknowledges PACER fees, or supplies purchase authority:

```bash
uv run legalforecast acquisition enrich-recap-case-dev \
  --output-root artifacts/cycle-1/official-acquisition/case-dev-enrichment \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <saturated-o-or-r-source-batch-id> \
  --workers 2 \
  --live-case-dev \
  --ranked-output artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --failures-output artifacts/cycle-1/official-acquisition/case-dev-enrichment/enrichment-failures.jsonl \
  --execute --resume
```

Pagination exhaustion must be proven for each successful docket. Bounded provider exhaustion, page-limit exhaustion, continuation cycles, and unproven pagination remain explicit terminal-exclusion records rather than cheap candidates; identity or metadata conflicts still block the handoff.

For either source schema, the projection and completion card bind the source batch/config/cycle digests, complete candidate and hit-set digests, ordered query terms, search window, source type, and `available_only` semantics. Eligibility remains independently anchored to 2026-06-30. The enrichment retains every Case.dev docket entry and filed date and replays the canonical MTD screen before cost ordering. Linked post-anchor merits dispositions rank first; moot or procedural rulings, pre-anchor dispositions, missing dates, and unproved target-motion linkage are demoted but never silently excluded. The ranked artifact records `ranking_policy_version`, the complete eligibility screen, and the exact entry evidence.

Before Firecrawl, materialize an authenticated exact prefix (or use `select-case-dev-ranked-subset` with repeated `--docket-id` for an exact noncontiguous set). Pin the raw enrichment run-card SHA-256 out of band and preserve the selector run card:

```bash
uv run legalforecast batch-002 select-case-dev-ranked \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <saturated-o-or-r-source-batch-id> \
  --source-projection artifacts/cycle-1/official-acquisition/case-dev-enrichment/checkpoints/case-dev-recap-source-projection.jsonl \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --failures artifacts/cycle-1/official-acquisition/case-dev-enrichment/enrichment-failures.jsonl \
  --enrichment-run-card artifacts/cycle-1/official-acquisition/case-dev-enrichment/run-cards/enrich-recap-case-dev.json \
  --expected-enrichment-run-card-sha256 <pinned-enrichment-run-card-sha256> \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <ranked-selection-batch-id> \
  --top-n 100 \
  --run-card-output artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-selection-run-card.json
```

Immediately after selection, compute the selector run card's SHA-256 from its raw bytes and record that digest out of band. The acquisition command must receive this independently recorded digest through `--expected-ranked-selection-run-card-sha256`; never derive or recompute the expected value from the selector card supplied to acquisition.

The selector authenticates both enrichment outputs. Ranked successes and authorized terminal exclusions must be disjoint and together reconcile the complete frozen source projection. The terminal-exclusion JSONL is bound by raw-byte digest, source index and docket identity, reason counts, and excluded-candidate-set commitment. Transient rows, conversion failures, identity conflicts, contradictory metadata, or noncanonical exclusion records still block selection; they may not be silently dropped from the ranked file.

### Step 3: Acquire And Screen Complete CourtListener Dockets

Fetch the ranked public CourtListener docket pages through Firecrawl, including every docket page needed to prove pagination completeness. The ten workers parallelize Firecrawl requests; SQLite authorization and artifact commits remain serialized:

```bash
uv run legalforecast acquisition acquire-ranked-firecrawl-dockets \
  --output-root artifacts/cycle-1/official-acquisition/docket-acquisition \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --parent-batch-id <ranked-selection-batch-id> \
  --selected-batch-id batch-002-ranked-dockets \
  --run-id batch-002-ranked-dockets-primary \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --ranked-selection-run-card artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-selection-run-card.json \
  --expected-ranked-selection-run-card-sha256 <pinned-ranked-selection-run-card-sha256> \
  --max-candidates 100 \
  --max-pages-per-docket 100 \
  --workers 10 \
  --decision-filed-on-or-after 2026-06-30 \
  --credit-cap 45000 \
  --live-firecrawl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/docket-acquisition/raw-docket-html \
  --successes-output artifacts/cycle-1/official-acquisition/docket-acquisition/docket-successes.jsonl \
  --exclusions-output artifacts/cycle-1/official-acquisition/docket-acquisition/docket-fetch-exclusions.jsonl \
  --execute --resume
```

For authenticated source-bound input, `--max-candidates` must exactly equal the selector's committed prefix/subset count. The command verifies the external selector-card digest, the full ranked-file digest, every selected ranked-record digest, the source schema/type commitments, the saturated parent transfer, and the exact selected/omitted reconciliation before any Firecrawl request. Source-bound ranked JSONL without this run card is rejected.

Strict-screen the committed CourtListener docket bytes and publish the immutable complete snapshot:

```bash
uv run legalforecast acquisition screen-firecrawl-dockets \
  --output-root artifacts/cycle-1/official-acquisition/docket-screening \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets \
  --successes artifacts/cycle-1/official-acquisition/docket-acquisition/docket-successes.jsonl \
  --fetch-exclusions artifacts/cycle-1/official-acquisition/docket-acquisition/docket-fetch-exclusions.jsonl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/docket-acquisition/raw-docket-html \
  --decision-filed-on-or-after 2026-06-30 \
  --snapshot-root artifacts/cycle-1/official-acquisition/snapshots \
  --snapshot-id batch-002-ranked-dockets-complete \
  --execute --resume
```

Do not rank or prepare from partial outputs. Require the screening summary and snapshot manifest to report complete reconciliation, `complete: true`, and `saturated: true`, then record the manifest's exact `cycle_hash`. `prepare-target-cohort` rejects a partial, changed, or wrong-cycle snapshot and carries every viable row through authoritative CourtListener public-document and paid-gap resolution.

If the same cycle gains reviewed candidates after a completed PACER-gap bridge, first publish a complete saturated `union-screening-snapshots` output. Reuse old terminal checkpoints only through `rebase-pacer-gap-checkpoints` with both externally pinned manifest hashes and one `--expected-added-candidate-id` per exact addition. A pure append requires the old snapshot in the union ancestry. If a complete current-policy replay invalidates a prior acceptance, also pass one `--expected-invalidated-candidate-id` per exact invalidation; that explicitly pinned path may replace the ancestry requirement but must prove every other prior terminal evidence record and raw commitment unchanged. Both paths require exact screened projections, unchanged retained route semantics, and a terminal checkpoint for every prior paid gap. The receipt's `replay_required_candidate_ids` must equal the new paid-gap additions plus only invalidated candidates that remain currently routed; invalidated candidates removed from current routes must be recorded separately and not replayed. Otherwise stop. The rebase is provider-free and preserves byte-identical prior checkpoints when their index, input hash, and payload did not change.

The acquisition objective and launch minimum are separate. Plan and preserve the full frontier against **150** clean cases. A supported initial launch may later project the cheapest cleared **100** cases from that same authenticated full pool. Do not rewrite the preparation objective as 100 merely because the supported launch projection is 100, and never raise or relax the frozen budget cap to make either count fit.

`legalforecast acquisition prepare-target-100` remains a compatibility wrapper for previously frozen exact-100 artifacts; do not use it to replace the 150-case preparation objective for this cycle.

### Step 4: Prepare The Resolved Pool And Provisional Budget

Run the public-first preparation chain from that immutable snapshot. This command plans public downloads against the 150-case objective, downloads free documents, resolves remaining gap metadata through authenticated noncharging CourtListener REST, applies the core-document filter, and emits disclosure-review requests plus the full untruncated frontier. It never purchases a document.

```bash
uv run legalforecast acquisition prepare-target-cohort \
  --output-root artifacts/cycle-1/official-acquisition/target-150-frontier \
  --snapshot artifacts/cycle-1/official-acquisition/snapshots/batch-002-ranked-dockets-complete \
  --expected-cycle-hash <snapshot-cycle-hash> \
  --use-embedded-entries \
  --live-public-download \
  --live-courtlistener \
  --request-ledger artifacts/cycle-1/official-acquisition/courtlistener-requests.sqlite3 \
  --cost-per-document-usd 3.05 \
  --max-projected-budget-usd 567.30 \
  --max-missing-core-documents-per-case 24 \
  --target-case-count 150 \
  --execute --resume
```

The successful preparation summary commits the snapshot, immutable semantic configuration, stage inputs and outputs, provisional selected candidate IDs, 150-case objective, and full cost frontier. Cycle 1 freezes the provisional cap at `$567.30`; every later projection must repeat that exact value rather than falling back to the CLI default. The `06-clearance-inputs/` directory contains one restriction-evidence row and one disclosure-review request for every downloaded free document. The summary deliberately names `clear-disclosures`, not purchase, as the next stage.

An `is_sealed: null` provider field is unknown metadata, not affirmative evidence that a filing is sealed. The pipeline may continue trying public routes and later classify the document as a recoverable missing/paid gap. It must not mark the document free unless public availability is affirmatively proven, and packet admission still fails closed until disclosure clearance is complete.

### Step 5: Clear Every Free Document And Freeze The Exact Cohort

Complete the supported authenticated disclosure-review flow over the full free manifest before projecting the exact cohort.
The contract and artifact schemas are documented in [Disclosure review bundle v1](schemas/disclosure-review-bundle-v1.md).
Do not hand-edit a preparation, review, signature, receipt, clearance, or run-card artifact.

This sequence is local, provider-free, and noncharging.
Do not run a purchase, parser or labeling-model call, model evaluation, official freeze, or dispatch as part of this gate.

Set paths for the exact completed preparation outputs, a normal acquisition review root, and a separate controlled private store.
The frozen cohort policy selects the reviewer authority from the immutable main-pinned registry; callers cannot supply or replace the expected reviewer-policy digest.

```zsh
review_requests=artifacts/cycle-1/official-acquisition/target-150-frontier/06-clearance-inputs/disclosure-review-requests.jsonl
download_manifest=artifacts/cycle-1/official-acquisition/target-150-frontier/03c-merged-downloads/document-downloads-merged.jsonl
document_root=artifacts/cycle-1/official-acquisition/target-150-frontier/documents/free
restriction_evidence=artifacts/cycle-1/official-acquisition/target-150-frontier/06-clearance-inputs/restriction-evidence.jsonl
review_root=artifacts/cycle-1/official-acquisition/target-150-frontier/disclosure-review
clearance_root=artifacts/cycle-1/official-acquisition/target-150-frontier/free-clearance
private_review_root=<absolute-controlled-private-review-root>
reviewer_policy=<externally-reviewed-human-hardware-reviewer-policy.json>
cohort_policy=<frozen-cohort-policy.json>
controlled_store_uri=private-store://<authority>/<cycle-1-review-location>
```

First prepare the value-redacted worksheet and the private exact-byte inspection map.
The private root must not equal, contain, or be contained by the acquisition output root.
The command writes `private-document-inspection-map.jsonl` only under that private root and deliberately excludes its path and bytes from downstream run-card commitments.

```zsh
uv run legalforecast acquisition prepare-disclosure-review \
  --output-root "$review_root" \
  --review-requests "$review_requests" \
  --download-manifest "$download_manifest" \
  --document-root "$document_root" \
  --restriction-evidence "$restriction_evidence" \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy" \
  --worksheet-output "$review_root/disclosure-review-worksheet.json" \
  --controlled-private-store-root "$private_review_root" \
  --execute --resume
```

Preflight the exact reviewer-policy bytes against the authority selected by the frozen cohort before recording an authenticated bundle:

```zsh
uv run legalforecast acquisition preflight-disclosure-review-signer \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy"
```

Production requires `identity_kind: "human_hardware"` and an `sk-ssh-ed25519@openssh.com` or `sk-ecdsa-sha2-nistp256@openssh.com` public key.
The CLI has no production override for a software-key service/test identity.
The hardware-signer prerequisite is tracked in `LegalForecastBench-5qd6.39.7.1`; if it is unresolved or preflight fails, stop and record the blocker rather than substituting an ordinary local SSH or Git key.

Next, use the private interactive recorder; do not hand-author the decision JSONL.
For every document it displays the exact private inspection path, SHA-256, restriction status, and marker categories, then requires the human to type the full inspected hash and an explicit decision.
It finishes with an exact batch summary and typed batch confirmation; flagged or non-public documents cannot be cleared.

```zsh
decisions="$private_review_root/disclosure-review-decisions.jsonl"

uv run legalforecast acquisition record-disclosure-review-decisions \
  --output-root "$private_review_root/recorder-metadata" \
  --review-worksheet "$review_root/disclosure-review-worksheet.json" \
  --private-inspection-map "$private_review_root/private-document-inspection-map.jsonl" \
  --reviewer-id reviewer:john \
  --controlled-private-store-root "$private_review_root" \
  --decisions-output "$decisions" \
  --execute --resume
```

The recorder checkpoints each document before continuing and derives the final decisions only from the reloaded checkpoint bytes.
If the process is interrupted or reports a failed stage, correct the underlying input or filesystem problem and rerun the identical command with `--resume`; do not edit the checkpoint, decision, run-card, or log artifacts.
A valid failure-history prefix and a partially published terminal run-card/log pair are recovered automatically, while mismatched metadata or decision bytes fail closed.

Set `authenticated_at` to an RFC 3339 time at or after every recorded `reviewed_at`, then build the canonical reviews and signing statement:

```zsh
authenticated_at=<RFC-3339-authentication-time>

uv run legalforecast acquisition build-disclosure-review-bundle \
  --output-root "$review_root" \
  --review-worksheet "$review_root/disclosure-review-worksheet.json" \
  --decisions "$decisions" \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy" \
  --controlled-store-uri "$controlled_store_uri" \
  --authenticated-at "$authenticated_at" \
  --reviews-output "$review_root/disclosure-reviews.jsonl" \
  --signing-statement-output "$review_root/disclosure-review-signing-statement.json" \
  --execute --resume
```

Sign the exact statement outside LegalForecastBench with the precommitted human hardware-backed key and fixed SSHSIG namespace.
Immediately before the hardware touch, display and inspect the exact per-document decision summary embedded in the statement:

```zsh
uv run legalforecast acquisition preflight-disclosure-review-signer \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy" \
  --signing-statement "$review_root/disclosure-review-signing-statement.json"
```

The displayed candidate/document/status rows and cleared/quarantined counts are part of the signed bytes; stop if any row or count is wrong.
OpenSSH writes the detached signature as `disclosure-review-signing-statement.json.sig`:

```zsh
/usr/bin/ssh-keygen -Y sign \
  -f <hardware-backed-signing-key-or-key-reference> \
  -n legalforecast-disclosure-review-v1 \
  "$review_root/disclosure-review-signing-statement.json"
```

Do not reserialize or edit the statement after signing.
Seal verifies the signature and the exact request, manifest, restriction, worksheet, review, policy, document-set, identity, provenance, and timestamp commitments before publishing the receipt:

```zsh
uv run legalforecast acquisition seal-disclosure-review-bundle \
  --output-root "$review_root" \
  --review-requests "$review_requests" \
  --download-manifest "$download_manifest" \
  --restriction-evidence "$restriction_evidence" \
  --review-worksheet "$review_root/disclosure-review-worksheet.json" \
  --reviews "$review_root/disclosure-reviews.jsonl" \
  --decisions "$decisions" \
  --signing-statement "$review_root/disclosure-review-signing-statement.json" \
  --signature "$review_root/disclosure-review-signing-statement.json.sig" \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy" \
  --review-receipt-output "$review_root/disclosure-review-receipt.json" \
  --execute --resume
```

Finally, run clearance over the same exact inputs and current document bytes.
The command recomputes the worksheet, requires byte-for-byte equality with the signed worksheet, verifies the receipt again, and fails closed on any drift or incomplete coverage:

```zsh
uv run legalforecast acquisition clear-disclosures \
  --output-root "$clearance_root" \
  --review-requests "$review_requests" \
  --download-manifest "$download_manifest" \
  --document-root "$document_root" \
  --review-worksheet "$review_root/disclosure-review-worksheet.json" \
  --reviews "$review_root/disclosure-reviews.jsonl" \
  --review-receipt "$review_root/disclosure-review-receipt.json" \
  --reviewer-policy "$reviewer_policy" \
  --cohort-policy "$cohort_policy" \
  --restriction-evidence "$restriction_evidence" \
  --execute --resume
```

The producer stages default to deterministic resume, but the runbook spells out `--resume` for audit clarity.
An identical retry must reuse matching bytes; changed inputs or outputs fail closed rather than overwriting the signed lineage.
Use `--no-resume` only when an exclusive first publication is intended, never to replace an already frozen artifact.

Clearance success is necessary but does not by itself authorize a downstream command.
Before projection, recovery, parse, extension, packet planning, or finalization, require that command's current verifier to consume the completed clearance run card and carry its exact signed-review source commitments and reviewer-policy pin.
If the live downstream contract omits that lineage, stop here and fix the gate; do not pass loose clearance files as a substitute.

Only after clearance succeeds may the supported 100-case launch cohort be projected from the 150-case preparation. This recomputes the cheapest complete frontier after quarantines and writes selection, relevance, restriction, manifest, clearance, budget, and exclusion artifacts containing exactly the chosen cases. It does not replace or lower the 150-case acquisition objective.

```bash
uv run legalforecast acquisition project-target-cohort \
  --output-root artifacts/cycle-1/official-acquisition/target-150-frontier/launch-100 \
  --selection artifacts/cycle-1/official-acquisition/target-150-frontier/03-gap-bridge/public-packet-selection-reconciled.jsonl \
  --case-relevance artifacts/cycle-1/official-acquisition/target-150-frontier/03-gap-bridge/case-relevance.jsonl \
  --download-manifest artifacts/cycle-1/official-acquisition/target-150-frontier/03c-merged-downloads/document-downloads-merged.jsonl \
  --disclosure-clearance artifacts/cycle-1/official-acquisition/target-150-frontier/free-clearance/disclosure-clearance.jsonl \
  --clearance-run-card artifacts/cycle-1/official-acquisition/target-150-frontier/free-clearance/run-cards/clear-disclosures.json \
  --restriction-evidence artifacts/cycle-1/official-acquisition/target-150-frontier/06-clearance-inputs/restriction-evidence.jsonl \
  --preparation-summary artifacts/cycle-1/official-acquisition/target-150-frontier/target-cohort-preparation-summary.json \
  --preparation-config artifacts/cycle-1/official-acquisition/target-150-frontier/target-cohort-config.json \
  --snapshot-manifest artifacts/cycle-1/official-acquisition/snapshots/batch-002-ranked-dockets-complete/manifest.json \
  --target-case-count 100 \
  --cost-per-document-usd 3.05 \
  --max-projected-budget-usd 567.30 \
  --max-missing-core-documents-per-case 24 \
  --execute --resume
```

If fewer than 100 post-clearance cases fit the unchanged cap, acquire more candidates rather than restoring a quarantined case or weakening a gate. The exact-cohort summary binds every source and output hash and reconciles every unselected resolved-pool candidate into `target-cohort-exclusions.jsonl`.

### Step 6: Generate Allowlist, Initialize Ledger, Then Purchase

Paid acquisition remains a separate, operator-visible stage. First freeze the cohort and purchase-policy artifacts required by the CLI, then generate the signed RECAP Fetch broker allowlist from the exact post-clearance outputs:

```bash
uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy <verified-purchase-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --budget-plan artifacts/cycle-1/official-acquisition/target-150-frontier/launch-100/missing-core-budget-plan.json \
  --selection artifacts/cycle-1/official-acquisition/target-150-frontier/launch-100/target-cohort-selection.jsonl \
  --output artifacts/cycle-1/official-acquisition/target-150-frontier/courtlistener-recap-fetch-policy-v1.json
```

Inspect the projected total, allowlisted numeric RECAP document IDs, and remaining budget before invoking the only fee-bearing happy path:

Ledger initialization is a mandatory, non-provider step. The absolute ledger path below must exactly match `canonical_ledger_path` in the verified purchase policy. This command must succeed and publish its authenticated initialization receipt before any purchase command runs:

```bash
uv run legalforecast acquisition init-purchase-ledger \
  --output-root artifacts/cycle-1/official-acquisition/target-150-frontier \
  --purchase-policy <verified-purchase-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --purchase-ledger <absolute-canonical-purchase-ledger-path> \
  --initialization-receipt-output artifacts/cycle-1/official-acquisition/target-150-frontier/purchase-ledger-initialization.json \
  --execute --resume
```

The allowlist accepts explicit-public proof or the exact current CourtListener REST paid-gap evidence contract.
Case.dev may support noncharging search and docket enrichment, but its legacy paid-unknown evidence is never purchase authority.

```bash
uv run legalforecast acquisition purchase-missing-recap-fetch \
  --output-root artifacts/cycle-1/official-acquisition/target-150-frontier \
  --budget-plan artifacts/cycle-1/official-acquisition/target-150-frontier/launch-100/missing-core-budget-plan.json \
  --selection artifacts/cycle-1/official-acquisition/target-150-frontier/launch-100/target-cohort-selection.jsonl \
  --purchase-policy <verified-purchase-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --purchase-ledger <absolute-canonical-purchase-ledger-path> \
  --request-ledger artifacts/cycle-1/official-acquisition/courtlistener-requests.sqlite3 \
  --live-purchase --acknowledge-pacer-fees \
  --execute --resume
```

Never substitute a Case.dev live purchase, a Case.dev fee-bearing docket refresh, or an implicit purchase inside preparation. The RECAP Fetch purchase stage may dispatch only IDs present in the generated broker policy and remains bounded by the verified purchase policy and broker-side budget controls.

### Expected Volumes

Do not use an estimated docket count as completion evidence. The decision-search summary must prove every frozen term and page terminal; the docket-acquisition summary must reconcile every ranked candidate; and the screening snapshot must be complete and saturated. Record the actual discovered, enriched, fetched, screened, excluded, and Firecrawl-credit counts from those artifacts.

### Reading The Tallies

Each command prints a machine-readable JSON summary to stdout (use `--summary-output PATH` to also persist it):

- `discover` funnel: `terms_terminal`/`terms_total` (how many frozen terms reached a bounded terminal state), `total_hits` (raw document hits), `distinct_candidates` (deduped dockets), `prescreen_exclusions_by_reason` (bankruptcy/criminal dockets dropped before any fetch), and `per_term` progress. `complete: true` means every term is bounded; `saturated: true` means every term was exhausted rather than limit-bound.
- `observe` tally: `considered` (candidates scanned), `skipped_already_observed` (resume skips), `observed` (fetched this pass), `eligible` (strict-clean accepted), `excluded_by_reason` (immutable/posture exclusions, with the underlying strict-screen reason surfaced as `strict_clean_screen_failed:<screen_reason>`), and `transient_by_reason` (retryable failures to re-run).
- `seed-batch-001-leads`: `leads_selected`, `leads_seeded`, and `already_seeded`.
- `seed-direct-search`: the same transfer counts plus `source_batch_digest` and `source_candidate_set_sha256`, which bind the REST batch to the exact saturated source pool.
