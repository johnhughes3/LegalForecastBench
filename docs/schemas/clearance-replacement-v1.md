# Clearance replacement artifacts v1

`legalforecast.clearance_replacement_frontier.v1` freezes the complete canonical order used when a purchased document fails disclosure clearance.

Build it before activating the purchase broker:

```console
uv run legalforecast acquisition build-clearance-replacement-frontier \
  --cohort-policy COHORT_POLICY.json \
  --purchase-policy PURCHASE_POLICY.json \
  --projection TARGET_COHORT_PROJECTION.json \
  --initial-selection INITIAL_SELECTION.json \
  --candidate-frontier FULL_FRONTIER.jsonl \
  --candidate-selection FULL_CANDIDATE_SELECTION.jsonl \
  --source snapshot=SNAPSHOT_MANIFEST.json \
  --output CLEARANCE_REPLACEMENT_FRONTIER.json \
  --broker-allowlist-plan-output BROAD_FRONTIER_ALLOWLIST.json
```

The builder preserves the supplied frontier order rather than re-ranking observations after clearance.
For an approved-v2 purchase policy it requires the verified `legalforecast.target_cohort_candidate_frontier.v1` artifact and requires the captured candidate-selection bytes to equal that frontier's `reconciled_selection_sha256`; a separately supplied selection cannot self-attest a new replacement universe.
It binds the exact cohort-policy, purchase-policy, projection, selection, candidate-frontier, and named source hashes; asserts that the frontier is untruncated; freezes the initial selected IDs, target count, four case-mix dimensions, and optional per-bucket cap; and verifies every candidate cost against the frozen purchase reservation and per-case cap.
Every initial selected candidate must appear in the full frontier.
The builder simultaneously emits the broad dry-run broker allowlist plan, so it can be activated before the first purchase and before any clearance outcome is observed.

After authenticated clearance of all confirmed purchased documents, plan the next iteration:

```console
uv run legalforecast acquisition plan-clearance-replacements \
  --cohort-policy COHORT_POLICY.json \
  --purchase-policy PURCHASE_POLICY.json \
  --controlled-private-root INITIAL_APPROVAL_PRIVATE_ROOT \
  --frontier CLEARANCE_REPLACEMENT_FRONTIER.json \
  --candidate-selection FULL_CANDIDATE_SELECTION.jsonl \
  --purchase-ledger PURCHASE.sqlite3 \
  --purchase-ledger-initialization-receipt PURCHASE_LEDGER_INITIALIZATION.json \
  --purchased-clearance PURCHASED_CLEARANCE.jsonl \
  --clearance-run-card CLEARANCE_RUN_CARD.json \
  --output REPLACEMENT_RESULT.json \
  --replacement-budget-plan-output NARROW_REPLACEMENT_PLAN.json \
  --broker-allowlist-plan-output BROAD_FRONTIER_ALLOWLIST.json \
  --exclusions-output REPLACEMENT_EXCLUSIONS.jsonl \
  --active-selection-output ACTIVE_SELECTION.jsonl \
  --replacement-selection-output REPLACEMENT_SELECTION.jsonl
```

This command never calls a provider and never purchases a document.
The canonical purchase SQLite journal is also the single writer for `legalforecast.clearance_replacement_event.v1` records.
Each event binds every frozen input plus the current canonical purchase-journal state, records the quarantined documents and journal-derived committed write-off, recomputes headroom without releasing that write-off, applies the frozen case-mix cap to retained cases, and points to the previous event hash.
An identical replay returns identical output without another event, selection, reservation, or bill.
An unresolved submitted or unknown purchase fails closed before replacement selection.

The two plan classes have deliberately different authority:

- `NARROW_REPLACEMENT_PLAN.json` is non-dry-run and contains only replacements selected in the durable iteration ledger.
- `BROAD_FRONTIER_ALLOWLIST.json` is produced up front by the frontier builder, is dry-run, and contains every eligible paid document in the frozen frontier; the later planner reproduces it byte-for-byte as a consistency check.

Neither artifact inherits purchase authority from the initial approved-v2 selection.
After the planner selects a nonempty tranche, record a new exact John Hughes decision:

```console
uv run legalforecast acquisition record-replacement-purchase-approval \
  --cohort-policy COHORT_POLICY.json \
  --initial-purchase-policy PURCHASE_POLICY_V2.json \
  --initial-controlled-private-root INITIAL_APPROVAL_PRIVATE_ROOT \
  --frontier CLEARANCE_REPLACEMENT_FRONTIER.json \
  --replacement-result REPLACEMENT_RESULT.json \
  --replacement-budget-plan NARROW_REPLACEMENT_PLAN.json \
  --replacement-selection REPLACEMENT_SELECTION.jsonl \
  --purchase-ledger PURCHASE.sqlite3 \
  --purchase-ledger-initialization-receipt PURCHASE_LEDGER_INITIALIZATION.json \
  --controlled-private-root NEW_SUCCESSOR_PRIVATE_ROOT \
  --output-root NEW_SUCCESSOR_PRIVATE_ROOT \
  --authority-output REPLACEMENT_PURCHASE_AUTHORITY.json \
  --attempt-policy-output REPLACEMENT_ATTEMPT_POLICY.json \
  --execute --no-resume
```

The successor request commits the unchanged initial policy and approval identities, the frozen frontier, exact replacement result, executable budget-plan and selection bytes, canonical ledger, reconciled pre-tranche journal state, committed spend, unchanged Cycle cap, before/after headroom, ranked unselected candidate IDs, document IDs, and replacement-event hashes.
Its typed confirmation is tranche-specific.
The checkpoint and run card record no provider request, PACER fee acknowledgment, or paid activity.

After replay-verifying the private evidence, the recorder publishes the exact public successor authority and attempt policy as one provider-free continuation when both output flags are supplied.
The standalone `verify-replacement-purchase-approval`, `generate-replacement-purchase-authority`, and `generate-recap-fetch-attempt-policy` commands remain available for independent verification and reproduction.
Every successor command and replacement attempt/broker-policy generator also receives the same immutable purchase-ledger initialization receipt; the successor binds its absolute path and exact SHA-256 before opening the existing journal.
`generate-recap-fetch-attempt-policy`, `generate-recap-fetch-broker-policy`, and `purchase-missing-recap-fetch` accept the sidecar only together with its private root.
Without both, replacement plan bytes fail the original exact-selection approval check before any output, environment-backed client, broker, request-budget ledger, or purchase journal is constructed.
With both, the runtime keeps the original v2 policy hash, canonical ledger, hard cap, per-case cap, reservation, and initial private replay; it authorizes only the exact successor plan and selection bytes.
Safe resume requires every pre-approval operation record to remain byte-identical and permits only a suffix of operations for the approved candidate/document pairs, while committed spend may advance only inside the approved tranche envelope.
An unrelated post-approval ledger operation invalidates the successor even when total spend remains below the tranche ceiling.

Repeat `plan-clearance-replacements -> record successor approval and authority -> generate the exact successor broker policy -> protected broker deployment and activation verification -> purchase -> recover -> review and clear -> resolve -> accumulate clearance` until the next planning pass emits no replacement case plans.
Each repetition is a separate run-cycle stage block with a new successor private root and immutable outputs; a prior tranche approval never authorizes a later tranche.
[`manifests/cycle-1-target-100.replacement-purchase-tranche.template.json`](../../manifests/cycle-1-target-100.replacement-purchase-tranche.template.json) is the checked-in partial coordinator plan for one such tranche.
Its human stage records the exact decision and publishes the provider-free authority and attempt policy.
The next provider-free stage generates `replacement-recap-fetch-broker-policy.json` from the exact successor budget, selection, attempt policy, public authority, successor private root, unchanged initialization receipt, and unchanged initial policy.
It deliberately omits `--broad-frontier-allowlist`: an approved-v2 successor authorizes only those exact tranche bytes, and broad mode is rejected.
Policy generation does not deploy or activate anything.
Stop after its completion card, inspect the generated policy and digest, deploy and activate those exact bytes through the protected secure-gate RECAP Fetch broker control plane, and independently verify that the active cycle and purchase-policy identity refer to that deployment before enabling `run-cycle --allow-network --allow-paid`.
The coordinator cannot perform, infer, or adopt that deployment.
The paid stage must carry the same generated artifact with `--broker-policy`; the CLI replay-verifies it against the exact successor authority before loading broker identity or provider configuration.
Never continue merely because a policy file exists locally, never substitute a broad frontier, and never reuse the active policy from an earlier tranche.
After recovery and human disclosure review, `accumulate-replacement-clearance` recursively authenticates the prior cumulative clearance and the current tranche clearance, reproduces their manifests and restriction evidence, reconciles every document against the canonical purchase ledger, and emits the only clearance/card pair accepted by the next planning or reprojection pass.
For the first tranche, set `PRIOR_CLEARANCE` and `PRIOR_CLEARANCE_RUN_CARD` to the authenticated initial purchased clearance; for every later tranche, set them to the preceding tranche's `07-cumulative-clearance` outputs.
Never concatenate or hand-assemble clearance JSONL between tranches.

Purchase completion is not the canonical cohort transition.
When the planner reaches a terminal iteration with no replacement case plans, its `ACTIVE_SELECTION.jsonl` is the only selection handoff: the planner authenticates it against the full candidate-selection hash frozen in the replacement frontier, requires exactly one source row for every active candidate ID, and commits its exact SHA-256 and count into `REPLACEMENT_RESULT.json`.
The same result separately commits `REPLACEMENT_SELECTION.jsonl`, the exact next-tranche purchase input; do not hand-author that file.
Do not hand-copy candidate IDs out of `REPLACEMENT_RESULT.json`.

Render and execute the checked-in reprojection plan:

```console
uv run legalforecast acquisition render-cycle-config \
  --template manifests/cycle-1-target-100.replacement-reprojection.template.json \
  --variable REPO_ROOT=/absolute/repository-root \
  --variable ARTIFACT_ROOT=/absolute/cycle-artifacts \
  --variable INITIAL_PRIVATE_ROOT=/absolute/initial-purchase-approval-root \
  --variable REPLACEMENT_ROOT=/absolute/replacement-root \
  --variable SOURCE_ROOT=/absolute/source-root \
  --output /absolute/replacement-root/reprojection-cycle.json

uv run legalforecast acquisition run-cycle \
  --config /absolute/replacement-root/reprojection-cycle.json \
  --state-root /absolute/replacement-root/reprojection-state \
  --execute --json
```

The `project-replacement-exact-100` stage consumes both `/absolute/replacement-root/01-plan/active-selection.jsonl` and the planner's `/absolute/replacement-root/01-plan/replacement-result.json`, together with the final `07-cumulative-clearance` artifact and accumulation card.
It verifies the result's plan hash, active-selection byte/count commitment, and complete authenticated clearance lineage; reruns the unchanged clearance, cost, case-mix, and target gates; and publishes `/absolute/replacement-root/01-projection/target-cohort-selection.jsonl` plus its authenticated `project-target-cohort` run card.
It fails rather than publishing if fewer than 100 active candidates survive.
That projection root, not the initial pre-quarantine projection and not the narrow replacement purchase selection, is canonical for every downstream stage.
In particular, `materialize-cohort-documents` must receive it as `--target-cohort-root`; `plan-parse-documents`, `build-decision-texts`, `llm-unitize`, `llm-label`, `plan-packet-inputs`, `build-packets`, and `finalize-corpus` must receive its `target-cohort-selection.jsonl` wherever they accept `--selection`; and any stage requiring the projection card must receive `01-projection/run-cards/project-target-cohort.json`.
`finalize-corpus --target-clean-cases 100` is the terminal proof that this replacement projection remained exact through packet construction.
[`manifests/cycle-1-target-100.replacement-corpus.template.json`](../../manifests/cycle-1-target-100.replacement-corpus.template.json) is the executable corpus-mode continuation for that handoff.
After its required `init-cycle` stage, `build-replacement-recovery-index` canonicalizes one required `initial_v2` recovery-source descriptor followed by ordinal-ordered `successor` descriptors (individual files or ordinal-prefixed JSON files in one directory) into `${REPLACEMENT_ROOT}/tranche-recovery-index.json`.
Consolidation requires the producer's completed run card and rejects a hand-authored, reordered, duplicated, or byte-changed index.
The closed union gives the initial source only its authenticated recovery, selection, clearance, clearance card, and optional resolved-document paths; every successor additionally requires its exact purchase authority, controlled private root, and budget plan.
`consolidate-replacement-recovery` authenticates the initial v2 recovery without inventing a successor authority, replays every successor authority against the unchanged policy, ledger, and initialization receipt, and publishes one conflict-free recovery/clearance/resolution root covering every purchased document in the reprojected active cohort.
Before consolidation, `build-replacement-exclusions` authenticates the completed replacement projection and its terminal replacement result, supersedes upstream target exclusions for candidates promoted into the final cohort, adds every quarantined or replaced candidate recorded by the immutable replacement ledger, and proves that selected and excluded candidates form a disjoint, exhaustive partition of the screened pool.
`finalize-corpus` replays that successor exclusion card and accepts the successor ledger—not the stale pre-replacement target ledger—as its target-level exclusion source.
The remaining stages consume only that consolidated root and the replacement projection through canonical materialization, parse, both labeling stages, packet planning/building, and `finalize-corpus`.
Consolidation is provider-free and performs no purchase or model call; missing selected ledger operations, missing tranche coverage, conflicting duplicate records, changed authority, and changed document bytes fail closed.

Generate each replacement secure-gate broker policy only from the narrow, non-dry-run successor plan in that tranche.
`--broad-frontier-allowlist` is reserved for unapproved dry-run planning and is invalid once approved-v2 exact-selection authority exists.
The broker continues to enforce the unchanged signed Cycle cap, per-case cap, reservation, and canonical purchase journal on each request after the exact successor policy is protectedly deployed and activated.

Planner-derived replacement exclusions are intermediate audit evidence, not a new eligibility rule.
The terminal successor exclusion ledger preserves those reasons where applicable, removes every now-selected candidate from older target exclusions, adds immutable quarantine/replacement outcomes, and is accepted only when `selected xor excluded` covers the complete screened pool.
