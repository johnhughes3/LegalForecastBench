# Official Run Runbook

For the remainder of Cycle 1, gate-changing work follows [cycle-1-change-control.md](cycle-1-change-control.md) (frozen byte contracts, single integration lane, emergency-migration path).

This is the operator checklist for `.github/workflows/run-benchmark.yaml` and the provider-free `.github/workflows/fan-in-publish.yaml` on the current `main` branch. Shard dispatches run isolated provider cells and finalize one immutable receipt per workflow attempt. Fan-in selects accepted receipts, reads only their exact committed S3 versions, derives cadence counts from frozen artifacts, delegates Cartesian completeness to `official_aggregate`, and publishes only the verified public directory.
Angle-bracket values such as `<cycle_id>` are placeholders, not literal shell input. Replace every such value before running a command.
The paired flags `--llm-unitization-run-card` / `--llm-unitize-run-card` and `--llm-review-stage-a-run-card` / `--stage-a-review-run-card` intentionally name the same authenticated card when both appear in one command. Substitute the same exact path for each pair; the different flag names describe validation roles, not different artifacts.

## On This Page

- [Acquisition downstream preflight](#acquisition-downstream-preflight)
  - [Exact post-clearance purchase approval](#exact-post-clearance-purchase-approval)
  - [Bounded Firecrawl terminal-target recovery](#bounded-firecrawl-terminal-target-recovery-compatibility-fallback-only)
  - [Provider-free exact-cohort downstream rehearsal](#provider-free-exact-cohort-downstream-rehearsal)
  - [Protected distributed paid-labeling authority](#protected-distributed-paid-labeling-authority)
- [Before dispatch](#before-dispatch)
- [Dispatch sequence](#dispatch-sequence)
- [Aggregation](#aggregation)
- [Add models to a frozen cycle](#add-models-to-a-frozen-cycle)
- [Staged-rollout rehearsal drill](#staged-rollout-rehearsal-drill)
- [Render and review the site](#render-and-review-the-site)
- [Recovery acceptance criteria](#recovery-acceptance-criteria)
- [Cycle 1 Batch-002 CourtListener-first acquisition](#cycle-1-batch-002-courtlistener-first-acquisition)
  - [Supported cycle coordinator](#supported-cycle-coordinator)
  - [Credential prerequisites](#credential-prerequisites)
  - [Step 1: Search CourtListener decisions through Firecrawl](#step-1-search-courtlistener-decisions-through-firecrawl)
  - [Preferred REST transfer](#preferred-rest-transfer-before-compatibility-steps-2-and-3)
  - [Exact-310 terminal REST policy rebind](#exact-310-terminal-rest-policy-rebind)
  - [Step 2: Enrich and rank with free Case.dev lookup](#step-2-enrich-and-rank-with-free-casedev-lookup)
  - [Step 3: Acquire and screen complete CourtListener dockets](#step-3-acquire-and-screen-complete-courtlistener-dockets)
  - [Step 4: Prepare the resolved pool and provisional budget](#step-4-prepare-the-resolved-pool-and-provisional-budget)
  - [Step 5: Clear every free document and freeze the exact cohort](#step-5-clear-every-free-document-and-freeze-the-exact-cohort)
  - [Step 6: Generate allowlist, initialize ledger, then purchase](#step-6-generate-allowlist-initialize-ledger-then-purchase)
  - [Expected volumes](#expected-volumes)
  - [Reading the tallies](#reading-the-tallies)
  - [Frozen priority-batch Firecrawl observation](#frozen-priority-batch-firecrawl-observation)

## Acquisition Downstream Preflight

### Exact post-clearance purchase approval

After `project-target-cohort` has completed, record John Hughes's decision against those exact replayed bytes before initializing a purchase ledger or activating a broker policy.
The controlled approval root is private operational state outside packets and freeze artifacts; the purchase-policy v2 `approval` subtree is the sole public derived authority.
The canonical purchase ledger is a new exact path under the cycle's `10-purchase-authority` root and must not exist yet.
The CourtListener request-budget ledger is different existing preparation evidence: every official purchase and recovery command must reuse the exact absolute `$PREP_PARENT/courtlistener-request-ledger-base-v1.sqlite3` committed under `33-10k-continuation`; never create a generic replacement request ledger.

```bash
uv run legalforecast acquisition record-purchase-approval \
  --output-root <absolute-controlled-private-approval-root> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-10-purchase-authority-ledger.sqlite3> \
  --execute --no-resume
```

The recorder is TTY-only, fixes the reviewer to `John Hughes`, derives every count and dollar amount from the fully authenticated projection and frozen cohort policy, and records `approve`, `reject`, or `free_only` plus the exact one-global-session and free-only-fallback confirmation.
The typed confirmation must include the displayed purchase rule and exact target count as `RULE <rule> TARGET <count>`; a dollar-cap-only or generic approval is not authority.
It contacts no provider and does not acknowledge PACER fees.
If it is interrupted after the checkpoint is durable, rerun the identical command with `--resume`; resume repairs only the missing exact run card and does not prompt again or change the recorded time.

```bash
uv run legalforecast acquisition verify-purchase-approval \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --checkpoint <absolute-controlled-private-approval-root/purchase-approval-checkpoint.json> \
  --approval-run-card <absolute-controlled-private-approval-root/run-cards/record-purchase-approval.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-10-purchase-authority-ledger.sqlite3>
```

```bash
uv run legalforecast acquisition generate-purchase-policy \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --checkpoint <absolute-controlled-private-approval-root/purchase-approval-checkpoint.json> \
  --approval-run-card <absolute-controlled-private-approval-root/run-cards/record-purchase-approval.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-10-purchase-authority-ledger.sqlite3> \
  --output <purchase-policy-v2.json>
```

Stop on `reject`.
For `free_only`, do not generate a purchase policy or initialize a ledger; materialize the exact all-free projection directly:

```bash
uv run legalforecast acquisition \
  materialize-cohort-documents \
  --output-root <immutable-materialized-cohort-root> \
  --preparation-root <completed-prepare-target-cohort-root> \
  --preparation-summary <completed-preparation-summary.json> \
  --preparation-config <completed-preparation-config.json> \
  --snapshot-manifest <authenticated-snapshot-manifest.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --free-disclosure-clearance <completed-project-target-cohort-root/disclosure-clearance.jsonl> \
  --cohort-policy <frozen-cohort-policy.json> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --free-only-approval-checkpoint <absolute-controlled-private-approval-root/purchase-approval-checkpoint.json> \
  --free-only-approval-run-card <absolute-controlled-private-approval-root/run-cards/record-purchase-approval.json> \
  --free-only-fee-schedule <immutable-fee-schedule.json> \
  --free-only-canonical-ledger-path <approved-absent-ledger-path> \
  --execute
```

The free-only path rejects every paid recovery, purchase-policy, purchase-ledger, initialization-receipt, and resolved-document input; it also fails closed unless the projected purchased manifest is empty and the free manifest exactly covers the selected documents.
A `free_only` decision recorded against a projection that still contemplated one or more paid gaps stops paid acquisition but does not authorize a later changed projection, even if those documents subsequently become free.
After provider-free gap recovery, publish and authenticate a new exact all-free projection, then record a new zero-cost `free_only` decision against those exact projection bytes before materialization.
For `approve`, the order is mandatory: record the private decision, verify that exact checkpoint and run card while the canonical ledger namespace is still absent, and only then generate the public v2 policy; generation cannot be moved before verification or repeated after ledger initialization.
Never hand-edit the private checkpoint, run card, or public v2 policy, and never reuse v1 policy input for a new official purchase.
See [Case.dev purchase policy v2](schemas/case-dev-purchase-policy-v2.md) for the complete replay and containment contract.

### Bounded Firecrawl terminal-target recovery (compatibility fallback only)

The official happy path is the CourtListener REST workflow documented under [Cycle 1 Batch-002 CourtListener-First Acquisition](#cycle-1-batch-002-courtlistener-first-acquisition). Use Firecrawl only as a compatibility fallback when a required search is not exposed by a supported CourtListener API. Case.dev may supply an optional free upstream or bulk lookup only when its response is equivalent to the CourtListener data needed at that step; it is never the final authority for paid gaps and must not perform a fee-bearing fetch.

For the authenticated exact target, plan a narrower public-link refresh before any fee-bearing recovery.
The plan reruns the canonical target verifier and makes no provider call:

```bash
uv run legalforecast acquisition plan-target-public-gaps \
  --output-root <new-public-gap-refresh-root> \
  --plan-output <immutable-public-gap-plan.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --expected-target-run-card-sha256 <external-lowercase-sha256> \
  --cycle-store <official-cycle-store.sqlite3> \
  --raw-html-dir <durable-raw-html-root> \
  --document-output-root <durable-free-document-root> \
  --batch-id <new-exact-target-refresh-batch> \
  --run-id <new-exact-target-refresh-run> \
  --firecrawl-mode live --document-mode live \
  --fresh-credit-cap 500 --workers 10
```

Record the lowercase SHA-256 of the single immutable plan file.
The recorded bounded Firecrawl authorization decision covers this narrower exact run; do not create a new spending decision artifact.
Execute only that plan and repeat every plan-bound identity argument exactly:

```bash
uv run legalforecast acquisition execute-target-public-gaps \
  --plan <immutable-public-gap-plan.json> \
  --expected-plan-sha256 <external-lowercase-plan-sha256> \
  --output-root <new-public-gap-refresh-root> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --expected-target-run-card-sha256 <external-lowercase-sha256> \
  --cycle-store <official-cycle-store.sqlite3> \
  --raw-html-dir <durable-raw-html-root> \
  --document-output-root <durable-free-document-root> \
  --batch-id <new-exact-target-refresh-batch> \
  --run-id <new-exact-target-refresh-run> \
  --firecrawl-mode live --document-mode live \
  --fresh-credit-cap 500 --workers 10 \
  --live-firecrawl --live-public-download
```

The command uses the durable Firecrawl scheduler, stops each docket after its selected gap-entry set is observed, routes matches through the existing public planner and free downloader, and records every required document in the per-document outcome ledger.
It cannot call PACER or RECAP Fetch, acknowledge fees, purchase a document, call a model, evaluate, freeze, or dispatch.
The terminal artifact is a distinct authenticated per-document gap-outcome ledger, not the canonical per-case exclusion ledger.
Recovered downloads remain ineligible for packets until the existing disclosure-provenance clearance and provider-free target reprojection are completed against the augmented manifest; that downstream reprojection emits at most one valid canonical candidate exclusion when required documents remain missing.
See [Exact-target public-gap refresh v1](schemas/target-public-gap-refresh-v1.md).

### Exact-target raw docket recovery (packet-input compatibility fallback)

When a pinned exact target selection has public docket HTML absent from a complete, saturated source snapshot, recover only the selected-minus-raw identities with the dedicated pair below.
This is a packet-input provenance repair, not a document-acquisition path: it never calls Case.dev, PACER, RECAP Fetch, a document downloader, a model, evaluation, freeze, or dispatch.
The planner hashes the exact selected cohort, source snapshot run card, and canonical raw-artifact manifest before deriving the target set; a missing, rebound, malformed, or duplicate source record fails closed.

```bash
uv run legalforecast acquisition plan-target-raw-docket-recovery \
  --execute --output-root <new-raw-recovery-plan-root> \
  --selection <exact-target-selection.jsonl> \
  --expected-selection-sha256 <external-lowercase-sha256> \
  --source-snapshot <complete-saturated-screening-snapshot> \
  --expected-source-snapshot-manifest-sha256 <external-lowercase-sha256> \
  --expected-cycle-hash <external-lowercase-cycle-hash> \
  --source-snapshot-run-card <completed-union-run-card.json> \
  --expected-source-snapshot-run-card-sha256 <external-lowercase-sha256> \
  --source-raw-manifest <source-snapshot/raw-artifacts.jsonl> \
  --expected-source-raw-manifest-sha256 <external-lowercase-sha256> \
  --cycle-store <official-cycle-store.sqlite3> \
  --batch-id <new-raw-recovery-batch> --run-id <new-raw-recovery-run> \
  --credit-cap <approved-bounded-cap> --workers 10 \
  --plan-output <immutable-raw-recovery-plan.json>
```

Execute only the returned plan SHA, repeating every bound input and scheduler argument.
The executor rechecks every pinned source input immediately before Firecrawl activity, uses complete pagination, and writes only canonical raw HTML plus screen-firecrawl-compatible success/exclusion records for the dedicated same-cycle batch.

After a successful execution, record the lowercase SHA-256 printed for the immutable receipt. A later completed `--resume` must repeat the command with `--expected-receipt-sha256 <external-lowercase-receipt-sha256>`; the executor will not authenticate an existing receipt from its own mutable bytes.

```bash
uv run legalforecast acquisition execute-target-raw-docket-recovery \
  --execute --output-root <new-raw-recovery-execution-root> \
  --plan <immutable-raw-recovery-plan.json> \
  --expected-plan-sha256 <external-lowercase-sha256> \
  --selection <exact-target-selection.jsonl> \
  --expected-selection-sha256 <external-lowercase-sha256> \
  --source-snapshot <complete-saturated-screening-snapshot> \
  --expected-source-snapshot-manifest-sha256 <external-lowercase-sha256> \
  --expected-cycle-hash <external-lowercase-cycle-hash> \
  --source-snapshot-run-card <completed-union-run-card.json> \
  --expected-source-snapshot-run-card-sha256 <external-lowercase-sha256> \
  --source-raw-manifest <source-snapshot/raw-artifacts.jsonl> \
  --expected-source-raw-manifest-sha256 <external-lowercase-sha256> \
  --cycle-store <official-cycle-store.sqlite3> \
  --batch-id <new-raw-recovery-batch> --run-id <new-raw-recovery-run> \
  --credit-cap <approved-bounded-cap> --workers 10 \
  --raw-html-dir <new-raw-html-root> \
  --successes-output <screening-successes.jsonl> \
  --exclusions-output <screening-exclusions.jsonl> \
  --summary-output <recovery-summary.json> \
  --receipt-output <recovery-receipt.json> --live-firecrawl
```

If that exact run ends `circuit_open` with zero successful pages, do not reset or reuse it. Freeze one direct successor from the externally pinned parent plan and failed run card:

```bash
uv run legalforecast acquisition plan-target-raw-docket-recovery-successor \
  --output-root <successor-plan-root> --execute --no-resume \
  --parent-plan <parent-plan.json> \
  --expected-parent-plan-sha256 <external-lowercase-sha256> \
  --parent-failure-run-card <failed-run-card.json> \
  --expected-parent-failure-run-card-sha256 <external-lowercase-sha256> \
  --parent-raw-html-dir <parent-raw-html-dir> \
  --batch-id <new-batch-id> --run-id <new-run-id> \
  --plan-output <successor-plan.json>

uv run legalforecast acquisition execute-target-raw-docket-recovery-successor \
  --output-root <successor-execution-root> --execute --no-resume \
  --successor-plan <successor-plan.json> \
  --expected-successor-plan-sha256 <external-lowercase-sha256> \
  --raw-html-dir <new-raw-html-dir> \
  --successes-output <screening-successes.jsonl> \
  --exclusions-output <screening-exclusions.jsonl> \
  --summary-output <recovery-summary.json> \
  --receipt-output <recovery-receipt.json> \
  --live-firecrawl
```

The successor inherits the exact target set, cycle store, credit cap, workers, pagination, retry, breaker, and proxy settings. It is accepted only for a zero-success all-5xx root failure, and the store permits only one direct child; successor chains are rejected.

There is one deliberately exceptional path if both that root and its direct successor are zero-success circuit-open failures and an owner has separately frozen a SHA-pinned authorization declaring the Firecrawl v2 `blockAds: false` request-contract defect.
The terminal failures alone do not establish the cause; that explicit authorization is required.
Only after the implementation that omits that property is reviewed and landed, freeze the one contract-bound retry below.
It derives all targets, URLs, source pins, scheduler settings, and the existing shared cycle credit cap from the two terminal ancestors; it does not accept replacements for them and cannot authorize a second contract retry.
It binds the sole request delta as the omission of `blockAds: false`; it never permits a proxy, browser, pagination, target, cap, or retry-policy change.

The owner-frozen authorization is a separately reviewed JSON file with exactly this semantic content; its externally supplied SHA-256 is the operator’s approval anchor:

```json
{
  "schema_version": "legalforecast.firecrawl_provider_contract_defect_authorization.v1",
  "declared_provider_contract_defect": {
    "provider": "firecrawl",
    "endpoint": "v2/scrape",
    "request_property": "blockAds",
    "prior_json_value": false,
    "authorized_retry_change": "omit_optional_json_property"
  }
}
```

```bash
uv run legalforecast acquisition plan-target-raw-docket-recovery-provider-contract-retry \
  --output-root <contract-retry-plan-root> --execute --no-resume \
  --root-plan <root-plan.json> \
  --expected-root-plan-sha256 <external-lowercase-sha256> \
  --root-failure-run-card <root-failed-run-card.json> \
  --expected-root-failure-run-card-sha256 <external-lowercase-sha256> \
  --direct-successor-plan <direct-successor-plan.json> \
  --expected-direct-successor-plan-sha256 <external-lowercase-sha256> \
  --direct-successor-failure-run-card <direct-successor-failed-run-card.json> \
  --expected-direct-successor-failure-run-card-sha256 <external-lowercase-sha256> \
  --direct-successor-raw-html-dir <direct-successor-raw-html-dir> \
  --provider-contract-defect-authorization <owner-frozen-defect-authorization.json> \
  --expected-provider-contract-defect-authorization-sha256 <external-lowercase-sha256> \
  --batch-id <bounded-contract-retry-batch> --run-id <bounded-contract-retry-run> \
  --plan-output <contract-retry-plan.json>

uv run legalforecast acquisition execute-target-raw-docket-recovery-provider-contract-retry \
  --output-root <contract-retry-execution-root> --execute --no-resume \
  --provider-contract-retry-plan <contract-retry-plan.json> \
  --expected-provider-contract-retry-plan-sha256 <external-lowercase-sha256> \
  --raw-html-dir <new-raw-html-dir> \
  --successes-output <screening-successes.jsonl> \
  --exclusions-output <screening-exclusions.jsonl> \
  --summary-output <recovery-summary.json> \
  --receipt-output <recovery-receipt.json> --live-firecrawl
```

The resulting screening step must authenticate that terminal handoff rather than consuming the success manifest as a generic unbound input:

```bash
uv run legalforecast acquisition screen-firecrawl-dockets \
  --execute --no-resume --output-root <new-screening-root> \
  --cycle-store <official-cycle-store.sqlite3> \
  --batch-id <new-raw-recovery-batch> \
  --successes <screening-successes.jsonl> \
  --fetch-exclusions <screening-exclusions.jsonl> \
  --raw-html-dir <new-raw-html-root> \
  --target-raw-docket-recovery-receipt <recovery-receipt.json> \
  --target-raw-docket-recovery-summary <recovery-summary.json> \
  --expected-target-raw-docket-recovery-receipt-sha256 <external-lowercase-sha256> \
  --expected-target-raw-docket-recovery-plan-sha256 <external-lowercase-sha256> \
  --decision-filed-on-or-after 2026-06-30 \
  --snapshot-id <new-complete-snapshot-id>
```

### Provider-free recovered raw-docket bridge

When a completed target selection is already authenticated against the final screening snapshot, and a completed recovery supplies only raw docket pages missing from that snapshot's canonical raw-artifact manifest, publish the bridge below before packet planning.

This is a deterministic local provenance join: it makes no provider request, purchases nothing, and does not rescreen or change the selected cohort.

```bash
uv run legalforecast acquisition build-target-raw-docket-auxiliary-provenance-bridge \
  --output-root <bridge-stage-root> --execute --no-resume \
  --selection <exact-target-selection.jsonl> \
  --expected-selection-sha256 <external-lowercase-sha256> \
  --source-snapshot <final-screening-snapshot-root> \
  --expected-source-snapshot-manifest-sha256 <external-lowercase-sha256> \
  --expected-cycle-hash <external-lowercase-cycle-hash> \
  --source-union-run-card <final-union-run-card.json> \
  --expected-source-union-run-card-sha256 <external-lowercase-sha256> \
  --source-cycle-store <official-cycle-store.sqlite3> \
  --source-raw-artifacts-manifest <canonical-raw-artifacts.jsonl> \
  --expected-source-raw-artifacts-manifest-sha256 <external-lowercase-sha256> \
  --source-raw-html-dir <canonical-raw-html-root> \
  --recovery-plan <completed-recovery-plan.json> \
  --expected-recovery-plan-sha256 <external-lowercase-sha256> \
  --recovery-receipt <completed-recovery-receipt.json> \
  --expected-recovery-receipt-sha256 <external-lowercase-sha256> \
  --recovery-successes <completed-recovery-successes.jsonl> \
  --recovery-exclusions <completed-recovery-exclusions.jsonl> \
  --recovery-summary <completed-recovery-summary.json> \
  --recovery-raw-html-dir <completed-recovery-raw-html-root> \
  --raw-artifacts-manifest-output <bridge-root>/raw-artifacts.jsonl \
  --bridge-output <bridge-root>/target-raw-docket-auxiliary-provenance-bridge.json \
  --bridge-run-card-output <bridge-root>/run-cards/bridge.json
```

Add `--raw-artifacts-manifest <bridge-root>/raw-artifacts.jsonl` and `--raw-provenance-bridge <bridge-root>/target-raw-docket-auxiliary-provenance-bridge.json` to the normal fully pinned `plan-packet-inputs` invocation.

`plan-packet-inputs` reauthenticates the bridge and commits it into its planner run card; `build-packets` reauthenticates that same commitment during replay.

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

The live parser may run only from the dedicated development path `/agents/sandbox/legalforecastbench/parser`, resolving only `MISTRAL_API_KEY` through a dependent-secret reference to the canonical acquisition-folder value. If the path is absent or the authoritative masked Infisical UI inventory exposes any additional secret name, stop the parse stage. The identical no-copy, no-folder-import rule, exact labeling-stage inventory, reference-permission requirement, and complete value-free preflights are defined in [the acquisition systemd launcher](acquisition-systemd-launcher.md). Run the parser defense-in-depth sentinel from an allowlisted empty caller environment; it verifies the required name and nonempty value and rejects every known labeling or acquisition credential without printing or exporting values:

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/parser \
  -- zsh -dfc '
    required=(MISTRAL_API_KEY)
    forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY CASE_DEV_API_KEY COURTLISTENER_API_TOKEN RECAP_API_TOKEN FIRECRAWL_API_KEY PACER_USERNAME PACER_PASSWORD)
    for name in $required; do (( ${+parameters[$name]} )) && [[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done'
```

Materialize the exact authenticated free and purchased document sets before parsing. The materializer verifies both disclosure-clearance lineages and the canonical purchase ledger, then emits one immutable manifest, clearance, and document root without modifying either source:

```bash
uv run legalforecast acquisition materialize-cohort-documents \
  --output-root <assembled-cycle-root> \
  --preparation-root <successful-target-cohort-preparation-root> \
  --preparation-summary <target-cohort-preparation-summary.json> \
  --preparation-config <target-cohort-preparation-config.json> \
  --snapshot-manifest <screening-snapshot-manifest.json> \
  --target-cohort-root <project-or-extend-target-cohort-root> \
  --free-disclosure-clearance <free-disclosure-clearance.jsonl> \
  --purchased-recovery-root <recover-recap-fetch-quarantine-root> \
  --purchased-disclosure-clearance <purchased-disclosure-clearance.jsonl> \
  --purchased-clearance-run-card <purchased-clear-disclosures-run-card.json> \
  --purchase-policy <purchase-policy.json> \
  --cohort-policy <cohort-policy.json> \
  --purchase-ledger <canonical-purchase-ledger.sqlite3> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --resolved-post-recovery-documents <resolved-post-recovery-documents.jsonl> \
  --execute --no-resume
```

Plan parse requests from those materialized bytes and preserve the completed plan card for packet construction and final reconciliation:

```bash
uv run legalforecast acquisition plan-parse-documents \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --resolved-post-recovery-documents <resolved-post-recovery-documents.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --purchase-policy <purchase-policy.json> \
  --purchase-ledger <canonical-purchase-ledger.sqlite3> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --document-root <materialized-document-root> \
  --requests-output <parse-document-requests.jsonl> \
  --markdown-output-root <parsed-markdown-root> \
  --execute --no-resume
```

Run the live parse against the clean pinned checkout explicitly; the default parser checkout may be on a different revision and will correctly fail closed:

```bash
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench/parser \
  -- uv run legalforecast acquisition parse-documents \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --requests <parse-document-requests.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --resolved-post-recovery-documents <resolved-post-recovery-documents.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --purchase-policy <purchase-policy.json> \
  --purchase-ledger <canonical-purchase-ledger.sqlite3> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --parser-root <pinned-parser-checkout> \
  --execute --resume
```

For a completed `free_only` materialization, use these downstream variants.
They retain the controlled private root needed to replay the exact zero-cost approval, but omit every paid recovery, purchase-policy, purchase-ledger, initialization-receipt, and resolved-document input:

```bash
uv run legalforecast acquisition plan-parse-documents \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --materialization-run-card <free-only-materialize-cohort-documents-run-card.json> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --document-root <materialized-document-root> \
  --requests-output <parse-document-requests.jsonl> \
  --markdown-output-root <parsed-markdown-root> \
  --execute --no-resume
```

```bash
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench/parser \
  -- uv run legalforecast acquisition parse-documents \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --requests <parse-document-requests.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --materialization-run-card <free-only-materialize-cohort-documents-run-card.json> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --parser-root <pinned-parser-checkout> \
  --execute --resume
```

The sentinel-`op` and child-environment tests in `tests/test_mistral_markdown_parser.py` enforce the subprocess boundary, but they do not authorize injecting a broad acquisition secret set into the parent process.

### Provider-free exact-cohort downstream rehearsal

Before spending on the live parser or labeling models, the supported rehearsal command can replay an exact 100- or 150-case cohort from an authenticated `project-target-cohort` selection, canonical combined materialization, completed fixture-Markdown parse, and prompt-bound deterministic response fixture.
It calls no network transport, reads no provider key, creates no provider journal, acknowledges no fee, and cannot freeze, evaluate, or dispatch anything.
Its decision-text manifest, model audits, packet outputs, final summary, and run card all retain `fixture_only` provenance with `official_eligible=false` and explicit false freeze/evaluation/dispatch authority.

The response fixture is newline-delimited `legalforecast.deterministic_model_response_fixture.v1` JSON.
Each row names the exact stage, candidate, and frozen model key; commits the exact prompt SHA-256; carries one raw JSON response validated by the same Stage A, structural-review, or Stage B schema used live; and records the served frozen model version.
Any missing, extra, duplicate, prompt-drifted, model-drifted, ambiguous, or review-routed response fails closed.
Every live-shaped fixture artifact has a mandatory adjacent `legalforecast.fixture_artifact_manifest.v1` sidecar with `fixture_only` provenance, its exact artifact hash and byte count, and false official, freeze, evaluation, and dispatch authority; each staged run card commits both files and the prior stage card.
Removing, replacing, symlinking, or changing either the artifact or sidecar breaks finalization.
Do not rewrite fixture parser fields to claim Mistral execution and do not copy rehearsal outputs into the official artifact names.

The supported end-to-end fixture rehearsal starts only after the ordinary preparation root and free-document disclosure review have completed through the provenance-first procedure below.
The inputs named `<authenticated-free-...>` are real, immutable outputs of that procedure, not hand-authored fixtures.
Project the exact cohort from those authenticated inputs first:

```bash
uv run legalforecast acquisition project-target-cohort \
  --output-root <fixture-target-cohort-root> \
  --selection <prepared-public-packet-selection.jsonl> \
  --case-relevance <prepared-case-relevance.jsonl> \
  --download-manifest <authenticated-free-download-manifest.jsonl> \
  --disclosure-clearance <authenticated-free-disclosure-clearance.jsonl> \
  --clearance-run-card <authenticated-free-clear-disclosures-run-card.json> \
  --restriction-evidence <authenticated-free-restriction-evidence.jsonl> \
  --preparation-summary <target-cohort-preparation-summary.json> \
  --preparation-config <target-cohort-preparation-config.json> \
  --snapshot-manifest <screening-snapshot-manifest.json> \
  --target-case-count 100 \
  --execute --no-resume
```

Reuse the exact frozen cohort policy that authenticated the free clearance; generating a different cohort authority after review would invalidate that lineage.
Even the fixture rehearsal uses the supported private recorder and v2 generator; its canonical absolute ledger path is under the isolated rehearsal root and must be absent at approval time:

```zsh
fixture_private_root=<absolute-private-fixture-approval-root>
fixture_ledger_receipt=<absolute-fixture-ledger-initialization-receipt>

uv run legalforecast acquisition record-purchase-approval \
  --output-root "$fixture_private_root" \
  --controlled-private-root "$fixture_private_root" \
  --target-cohort-root <fixture-target-cohort-root> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --fee-schedule <immutable-fixture-fee-schedule.json> \
  --canonical-ledger-path <absolute-fixture-purchase-ledger-path> \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition verify-purchase-approval \
  --controlled-private-root "$fixture_private_root" \
  --checkpoint "$fixture_private_root/purchase-approval-checkpoint.json" \
  --approval-run-card "$fixture_private_root/run-cards/record-purchase-approval.json" \
  --target-cohort-root <fixture-target-cohort-root> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --fee-schedule <immutable-fixture-fee-schedule.json> \
  --canonical-ledger-path <absolute-fixture-purchase-ledger-path>
```

```bash
uv run legalforecast acquisition generate-purchase-policy \
  --controlled-private-root "$fixture_private_root" \
  --checkpoint "$fixture_private_root/purchase-approval-checkpoint.json" \
  --approval-run-card "$fixture_private_root/run-cards/record-purchase-approval.json" \
  --target-cohort-root <fixture-target-cohort-root> \
  --fee-schedule <immutable-fixture-fee-schedule.json> \
  --canonical-ledger-path <absolute-fixture-purchase-ledger-path> \
  --output <fixture-purchase-policy.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json>
```

```bash
uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy <fixture-purchase-policy.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --budget-plan <fixture-target-cohort-root/missing-core-budget-plan.json> \
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl> \
  --controlled-private-root "$fixture_private_root" \
  --output <fixture-recap-fetch-broker-policy.json>
```

Initialize the isolated policy-bound ledger, then execute only the offline purchase fixture path:

```bash
uv run legalforecast acquisition init-purchase-ledger \
  --output-root <fixture-ledger-initialization-root> \
  --purchase-policy <fixture-purchase-policy.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --purchase-ledger <absolute-fixture-purchase-ledger-path> \
  --controlled-private-root "$fixture_private_root" \
  --initialization-receipt-output "$fixture_ledger_receipt" \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition purchase-missing-recap-fetch \
  --output-root <offline-fixture-purchase-root> \
  --budget-plan <fixture-target-cohort-root/missing-core-budget-plan.json> \
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl> \
  --purchase-policy <fixture-purchase-policy.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --purchase-ledger <absolute-fixture-purchase-ledger-path> \
  --controlled-private-root "$fixture_private_root" \
  --purchase-ledger-initialization-receipt "$fixture_ledger_receipt" \
  --courtlistener-fixture <offline-courtlistener-responses.jsonl> \
  --purchase-broker-fixture <offline-broker-receipts.json> \
  --acknowledge-pacer-fees \
  --execute --no-resume
```

`--acknowledge-pacer-fees` is currently a mechanical CLI gate shared with the live subcommand; in this invocation both fixture flags are present and `--live-purchase` is absent.
It does not acknowledge an actual charge or authorize a provider call: the completed fixture run card must record `paid_activity_requested=false` and `paid_activity_executed=false`, and no request ledger, provider request, or fee is created.
If either assertion is false, stop rather than continuing the rehearsal.

Recover only the fixture receipt URLs from operator-supplied PDF fixture bytes:

```bash
uv run legalforecast acquisition recover-purchased \
  --output-root <offline-fixture-recovery-root> \
  --purchase-result <offline-fixture-purchase-root/courtlistener-recap-fetch-purchases.json> \
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl> \
  --fixture-documents <offline-purchased-pdf-fixtures.json> \
  --manifest-output <offline-fixture-recovery-root/purchased-document-downloads.jsonl> \
  --recovery-output <offline-fixture-recovery-root/purchase-recovery.json> \
  --document-output-root <offline-fixture-recovery-root/documents/purchased> \
  --execute --no-resume
```

The recovered purchased bytes still require the same provenance-first plan, exception recorder, and replayed finalizer used for real free documents.
Do not substitute fixture review decisions.
Plan against the complete fixture-purchased case-relevance artifact, record any routed exceptions under the controlled private root, and finalize from those exact bytes:

```bash
uv run legalforecast acquisition plan-disclosure-provenance \
  --output-root <authenticated-purchased-review-root> \
  --review-requests <authenticated-purchased-review-requests.jsonl> \
  --download-manifest <offline-fixture-recovery-root/purchased-document-downloads.jsonl> \
  --case-relevance <complete-fixture-purchased-case-relevance.jsonl> \
  --document-root <offline-fixture-recovery-root/documents/purchased> \
  --restriction-evidence <authenticated-purchased-restriction-evidence.jsonl> \
  --controlled-private-store-root <absolute-private-purchased-review-root> \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition record-disclosure-review-decisions \
  --output-root <absolute-private-purchased-review-root/recorder-metadata> \
  --review-worksheet <authenticated-purchased-review-root/disclosure-exception-worksheet.json> \
  --private-inspection-map <absolute-private-purchased-review-root/private-document-inspection-map.jsonl> \
  --reviewer-id "John Hughes" \
  --controlled-private-store-root <absolute-private-purchased-review-root> \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition clear-provenance-disclosures \
  --output-root <authenticated-purchased-clearance-root> \
  --review-requests <authenticated-purchased-review-requests.jsonl> \
  --download-manifest <offline-fixture-recovery-root/purchased-document-downloads.jsonl> \
  --case-relevance <complete-fixture-purchased-case-relevance.jsonl> \
  --document-root <offline-fixture-recovery-root/documents/purchased> \
  --restriction-evidence <authenticated-purchased-restriction-evidence.jsonl> \
  --routing-plan <authenticated-purchased-review-root/disclosure-provenance-plan.json> \
  --exception-worksheet <authenticated-purchased-review-root/disclosure-exception-worksheet.json> \
  --exception-decisions <absolute-private-purchased-review-root/disclosure-review-decisions.jsonl> \
  --exception-review-run-card <absolute-private-purchased-review-root/recorder-metadata/run-cards/record-disclosure-review-decisions.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --execute --no-resume
```

Materialize the authenticated free and purchased lineages into one immutable document root, then plan and perform only a fixture-Markdown parse:

```bash
uv run legalforecast acquisition materialize-cohort-documents \
  --output-root <fixture-materialized-root> \
  --preparation-root <completed-target-cohort-preparation-root> \
  --preparation-summary <target-cohort-preparation-summary.json> \
  --preparation-config <target-cohort-preparation-config.json> \
  --snapshot-manifest <screening-snapshot-manifest.json> \
  --target-cohort-root <fixture-target-cohort-root> \
  --free-disclosure-clearance <fixture-target-cohort-root/disclosure-clearance.jsonl> \
  --purchased-recovery-root <offline-fixture-recovery-root> \
  --purchased-disclosure-clearance <authenticated-purchased-clearance-root/disclosure-clearance.jsonl> \
  --purchased-clearance-run-card <authenticated-purchased-clearance-root/run-cards/clear-disclosures.json> \
  --purchase-policy <fixture-purchase-policy.json> \
  --cohort-policy <authenticated-frozen-cohort-policy.json> \
  --purchase-ledger <absolute-fixture-purchase-ledger-path> \
  --controlled-private-root "$fixture_private_root" \
  --purchase-ledger-initialization-receipt "$fixture_ledger_receipt" \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition plan-parse-documents \
  --output-root <fixture-parse-root> \
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl> \
  --download-manifest <fixture-materialized-root/document-downloads-merged.jsonl> \
  --disclosure-clearance <fixture-materialized-root/disclosure-clearance.jsonl> \
  --materialization-run-card <fixture-materialized-root/run-cards/materialize-cohort-documents.json> \
  --purchase-policy <fixture-purchase-policy.json> \
  --purchase-ledger <absolute-fixture-purchase-ledger-path> \
  --controlled-private-root "$fixture_private_root" \
  --purchase-ledger-initialization-receipt "$fixture_ledger_receipt" \
  --document-root <fixture-materialized-root/documents> \
  --requests-output <fixture-parse-root/parse-document-requests.jsonl> \
  --markdown-output-root <fixture-parse-root/markdown> \
  --execute --no-resume
```

```bash
uv run legalforecast acquisition parse-documents \
  --output-root <fixture-parse-root> \
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl> \
  --requests <fixture-parse-root/parse-document-requests.jsonl> \
  --disclosure-clearance <fixture-materialized-root/disclosure-clearance.jsonl> \
  --materialization-run-card <fixture-materialized-root/run-cards/materialize-cohort-documents.json> \
  --purchase-policy <fixture-purchase-policy.json> \
  --purchase-ledger <absolute-fixture-purchase-ledger-path> \
  --controlled-private-root "$fixture_private_root" \
  --purchase-ledger-initialization-receipt "$fixture_ledger_receipt" \
  --manifest-output <fixture-parse-root/fixture-parser-manifest.jsonl> \
  --fixture-markdown-dir <operator-supplied-fixture-markdown-root> \
  --execute --no-resume
```

The parser card must retain fixture mode and is never evidence of a Mistral call.
No production parser, model provider, purchase broker, CourtListener transport, freeze, evaluation, or dispatch is invoked by this fixture chain.

Run the supported public downstream stages separately so each boundary publishes and re-authenticates its own run card.
All eight stages currently accept the same immutable input set; use one shared output root and do not alter the response fixture or any upstream bytes between stages:

```zsh
rehearsal_root=<fixture-rehearsal-root>
rehearsal_args=(
  --output-root "$rehearsal_root"
  --selection <fixture-target-cohort-root/target-cohort-selection.jsonl>
  --selection-run-card <fixture-target-cohort-root/run-cards/project-target-cohort.json>
  --download-manifest <fixture-materialized-root/document-downloads-merged.jsonl>
  --disclosure-clearance <fixture-materialized-root/disclosure-clearance.jsonl>
  --restriction-evidence <fixture-materialized-root/restriction-evidence.jsonl>
  --materialization-run-card <fixture-materialized-root/run-cards/materialize-cohort-documents.json>
  --controlled-private-root "$fixture_private_root"
  --purchase-ledger-initialization-receipt "$fixture_ledger_receipt"
  --parse-plan-run-card <fixture-parse-root/run-cards/plan-parse-documents.json>
  --parse-requests <fixture-parse-root/parse-document-requests.jsonl>
  --parser-manifest <fixture-parse-root/fixture-parser-manifest.jsonl>
  --parser-run-card <fixture-parse-root/run-cards/parse-documents.json>
  --document-root <fixture-materialized-root/documents>
  --markdown-root <fixture-parse-root/markdown>
  --raw-html-dir <authenticated-raw-docket-html-root>
  --unitizer-model-registry <frozen-stage-a-registry.json>
  --unitizer-model-key <provider:model-id>
  --reviewer-model-registry <frozen-stage-a-reviewer-registry.json>
  --reviewer-model-key <provider:model-id>
  --judge-model-registry <frozen-stage-b-judge-registry.json>
  --judge-model-key <provider:first-judge-model-id>
  --judge-model-key <provider:second-judge-model-id>
  --evaluated-model-registry <frozen-evaluated-model-registry.json>
  --response-fixtures <prompt-bound-deterministic-responses.jsonl>
  --target-case-count 100
  --generated-at 2026-07-17T00:00:00Z
)
rehearsal_stages=(
  rehearsal-build-decision-texts
  rehearsal-stage-a-unitize
  rehearsal-stage-a-review
  rehearsal-stage-a-apply
  rehearsal-stage-b-label
  rehearsal-stage-b-apply
  rehearsal-plan-packet-inputs
  rehearsal-build-packets
)
for rehearsal_stage in "${rehearsal_stages[@]}"; do
  uv run legalforecast acquisition "$rehearsal_stage" \
    "${rehearsal_args[@]}" --execute --no-resume
done
```

The staged sequence above is the acceptance path.
The final `rehearsal-build-packets` stage also emits the canonical `rehearsal-final-summary.json` and `run-cards/rehearse-downstream.json` reconciliation card consumed by the fixture finalizer; no aggregate rerun is required.
For a local convenience smoke test, `rehearse-downstream` runs the same fixture-only pipeline as one aggregate command:

```bash
uv run legalforecast acquisition rehearse-downstream \
  --output-root <fixture-rehearsal-root> \
  --selection <projected-exact-cohort-selection.jsonl> \
  --selection-run-card <project-target-cohort-run-card.json> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --restriction-evidence <materialized-restriction-evidence.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --parse-plan-run-card <plan-parse-documents-run-card.json> \
  --parse-requests <parse-document-requests.jsonl> \
  --parser-manifest <fixture-parser-manifest.jsonl> \
  --parser-run-card <fixture-parse-documents-run-card.json> \
  --document-root <materialized-document-root> \
  --markdown-root <fixture-parsed-markdown-root> \
  --raw-html-dir <authenticated-raw-docket-html-root> \
  --unitizer-model-registry <frozen-stage-a-registry.json> \
  --unitizer-model-key <provider:model-id> \
  --reviewer-model-registry <frozen-stage-a-reviewer-registry.json> \
  --reviewer-model-key <provider:model-id> \
  --judge-model-registry <frozen-stage-b-judge-registry.json> \
  --judge-model-key <provider:model-id> \
  --evaluated-model-registry <frozen-evaluated-model-registry.json> \
  --response-fixtures <prompt-bound-deterministic-responses.jsonl> \
  --target-case-count 100 \
  --generated-at 2026-07-17T00:00:00Z \
  --execute --no-resume
```

Repeat `--judge-model-key` for every entry in the dedicated judge registry.
The command authenticates the exact target-selection hash, combined materialization binding, parse-request/parser hash chain, fixture parser mode, release anchor, candidate/document coverage, and raw source hashes before model-schema validation.
It then constructs fixture-only decision texts, unitizes, structurally reviews, applies an empty Stage A queue, labels, applies an empty Stage B merits queue, plans and builds packets, proves the outcome-bearing decision document is excluded from every model packet, and reconciles the exact target count.
If either review queue is nonempty, stop and correct the deterministic fixture or file the corresponding John-review bead; the rehearsal never self-adjudicates.
Success is `rehearsal-final-summary.json` with all counts equal to the requested cohort, zero pending reviews, `provider_journal_created=false`, `provider_billing_usd="0.00"`, and `packet_outcome_material_excluded=true`.
Finalize that evidence only through the separate fixture authority:

```bash
uv run legalforecast acquisition finalize-rehearsal-corpus \
  --output-root <fixture-rehearsal-finalization-root> \
  --rehearsal-summary <fixture-rehearsal-root/rehearsal-final-summary.json> \
  --rehearsal-run-card <fixture-rehearsal-root/run-cards/rehearse-downstream.json> \
  --selection <projected-exact-cohort-selection.jsonl> \
  --prediction-units <fixture-rehearsal-root/rehearsal-finalized-prediction-units.jsonl> \
  --decision-texts <fixture-rehearsal-root/rehearsal-decision-texts.jsonl> \
  --labels <fixture-rehearsal-root/rehearsal-labels.jsonl> \
  --packets <fixture-rehearsal-root/rehearsal-packets.jsonl> \
  --target-case-count 100 \
  --corpus-output <fixture-rehearsal-finalization-root/fixture-rehearsal-corpus.json> \
  --execute --no-resume
```

The finalizer re-authenticates every exact-cohort output commitment, candidate and unit coverage, zero-review counts, zero billing, and packet exclusion of decision material before emitting `legalforecast.fixture_rehearsal_corpus.v1` with `official_eligible=false`.
This success is test evidence only: production `build-decision-texts`, readiness, `finalize-corpus`, freeze, evaluation, and dispatch continue to reject every rehearsal artifact.

The optional distributed-authority DynamoDB spend table is owned by the table-only `infra/provider-authority` module.
The canonical Cycle 1 replacement-corpus continuation instead uses the checked-in legacy caps, one canonical private SQLite provider journal, and explicit `--local-provider-journal-only`, as described below; that local Stage A/B path does not require this table, protected labeling environments, evaluation roles, S3 result infrastructure, `run-benchmark`, or an evaluation workflow.
Use the table only when selecting the separate distributed-authority path.
If the reviewed table already exists, import it into protected Terraform state after verifying the exact key schema and safeguards; otherwise review a table-only plan and obtain a separately authorized Terraform apply.
Only the ARN-derived resource-identity SHA-256 is frozen into `provider-cycle-caps`; the table ARN and AWS account ID remain protected configuration.
The caps artifact remains mandatory because its cycle-bound per-provider reservation caps govern the shared journal, but launch does not require documentary or admin-API evidence of an external account spending limit.
Legacy `external_spend_limit_usd`, `external_limit_scope`, `external_limit_source`, and `verified_at` fields are accepted only as optional annotations: they neither constrain the reservation cap nor grant provider spend authority, and the canonical Cycle 1 artifact omits them.
The digest is a public equality commitment, not a confidentiality boundary: an observer who can enumerate likely table ARNs can test candidate account IDs against it.
The currently committed `model_registries/cycle-1-provider-caps-2026-07-12.json` predates this contract and lacks both provider account aliases and top-level `spend_authority`.
Do not treat the distributed-authority path as runnable merely because this code lands: a deliberate artifact amendment must bind the reviewed public aliases and exact applied table-ARN digest, and the protected environments must match it before any distributed-authority provider call.

### Reviewed provider-authority infrastructure path

Use `.github/workflows/official-provider-authority-infra.yaml` for both `infra/provider-authority` and `infra/official-labeling`.
This is a nonblocking distributed-authority and later-evaluation path; it is not a prerequisite for the canonical Cycle 1 local-journal acquisition stages.
It has separate `plan` and `apply` operations, accepts only an exact current `main` release, uses an externally bootstrapped OIDC operator role, and keeps Terraform state in an externally bootstrapped S3 backend encrypted by the configured KMS key.
The plan operation rejects destructive actions and any managed resource outside the selected module's closed address allowlist, uploads only an age-encrypted saved plan plus a public-safe action-and-digest receipt, and clears temporary AWS credentials before upload.
The apply operation requires the exact successful plan run ID and attempt, canonical artifact name, GitHub artifact digest, plaintext plan digest, module, and release.
It rechecks hash commitments to the operator role, remote backend coordinates, and Terraform inputs before decrypting and applying that exact plan.

This workflow deliberately cannot bootstrap its own authority.
Before its first plan, a separately authorized operator must establish and protect `legalforecastbench-official-provider-authority-infra`, its short-lived OIDC role, encrypted S3 state bucket and KMS key, and its age plan-encryption identity.

#### One-time AWS/Terraform bootstrap trust anchor

The one-time bootstrap root for the bucket, KMS key and alias, account-level GitHub OIDC provider, and exact environment-bound operator role is defined in `infra/official-eval-bootstrap`.
Follow its import-first protected-local-state runbook, verify the live controls, and migrate that state into its separate encrypted backend key before configuring this workflow; the routine operator role cannot manage the bootstrap root or read its state.
The environment must admit only `main` and require `johnhughes3`; self-review prevention remains disabled because that sole reviewer may also dispatch the operation.
The operator role must trust only `repo:johnhughes3/LegalForecastBench:environment:legalforecastbench-official-provider-authority-infra` with audience `sts.amazonaws.com`.
That environment contains the one secret `LFB_INFRA_PLAN_AGE_IDENTITY` and only these variables:

- `LFB_AWS_REGION`
- `LFB_INFRA_OPERATOR_ROLE_ARN`
- `LFB_INFRA_PLAN_AGE_RECIPIENT`
- `LFB_TERRAFORM_STATE_BUCKET`
- `LFB_TERRAFORM_STATE_KEY_PREFIX`
- `LFB_TERRAFORM_STATE_KMS_KEY_ID`
- `LFB_GITHUB_OIDC_PROVIDER_ARN`
- `LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256`
- `LFB_PROVIDER_AUTHORITY_TABLE_ARN`

It contains no provider key, baton identity, AWS access key, evaluation role, packet or result bucket, freeze authority, or dispatch credential.
The exact provider-authority table must already be represented in that remote state through a reviewed import if it exists.
Secure-gate must separately allow only the required infrastructure and evaluation environment names, variable names, and secret names in `infra/official-eval/github-environments.json`.
The paid-labeling environments remain governed separately by `infra/official-labeling/github-environments.json`.
Do not add AWS access keys, provider keys, environment-creation API calls, state-backend creation, IAM self-bootstrap, evaluation, freeze, or workflow-dispatch authority to this path.

Dispatch a plan from the exact current main release:

```bash
release_sha="$(git rev-parse origin/main)"
gh workflow run official-provider-authority-infra.yaml \
  --ref main \
  -f operation=plan \
  -f module=provider-authority \
  -f release_sha="$release_sha"
```

Download the exact encrypted artifact to a trusted human-controlled machine and review the saved plan itself, not only the public receipt.
Use an independently retained age identity corresponding to `LFB_INFRA_PLAN_AGE_RECIPIENT`; do not export the repository environment secret.
The workflow and review use Terraform 1.13.5, age 1.3.1, and the exact AWS provider selection and checksums committed in each module's `.terraform.lock.hcl`.
For example, after recording the successful plan run ID, attempt, artifact name, GitHub artifact digest, and receipt plan digest:

```bash
umask 077
review_dir="$(mktemp -d)"
git worktree add --detach "$review_dir/repository" "$release_sha"
test "$(git -C "$review_dir/repository" rev-parse HEAD)" = "$release_sha"
test "$(terraform version -json | jq -r .terraform_version)" = "1.13.5"
test "$(age --version)" = "v1.3.1"
gh run download "$plan_run_id" \
  --name "$plan_artifact_name" \
  --dir "$review_dir"
test "$(
  gh api --paginate \
    "/repos/johnhughes3/LegalForecastBench/actions/runs/$plan_run_id/artifacts?per_page=100" \
    --jq ".artifacts[] | select(.name == \"$plan_artifact_name\") | .digest"
)" = "$plan_artifact_digest"
age --decrypt \
  --identity /protected/path/to/independently-retained-age-identity.txt \
  --output "$review_dir/provider-authority.tfplan" \
  "$review_dir/provider-authority.tfplan.age"
printf '%s  %s\n' "$plan_file_sha256" "$review_dir/provider-authority.tfplan" \
  | sha256sum --check --strict
terraform -chdir="$review_dir/repository/infra/provider-authority" \
  init -backend=false -input=false >/dev/null
terraform -chdir="$review_dir/repository/infra/provider-authority" show -no-color \
  "$review_dir/provider-authority.tfplan" \
  > "$review_dir/provider-authority-plan.txt"
```

Use `infra/official-labeling` as `-chdir` when reviewing that module.
Inspect the protected text output for every action, resource, account, and value; do not publish the decrypted plan, text rendering, or age identity.
After review, remove the registered checkout with `git worktree remove "$review_dir/repository"` and then remove the remaining protected temporary files.
The public receipt remains useful for confirming the exact release, module, plan SHA-256, closed resource-action summary, and operator/backend/input identity commitments, but it is not a substitute for this review.
A plan dispatch does not authorize apply.
Only after the exact plan receives separate owner approval may an operator dispatch `operation=apply` with all five plan-provenance inputs.
Repeat the sequence for `module=official-labeling`; never reuse a plan across modules, releases, attempts, backends, operator roles, or Terraform inputs.

### Protected distributed paid-labeling authority

When the distributed-authority mode is selected, paid unitization, structural review, and Stage B judge calls run only through `.github/workflows/official-paid-labeling.yaml`.
The canonical Cycle 1 replacement-corpus continuation remains the separate local-journal mode documented below and does not use this workflow or its GitHub environments.
The workflow assumes the distinct `${name_prefix}-authority` role defined by `infra/official-labeling`; it never reuses the evaluation cell role or packet-read role.
That role's base policy grants only `dynamodb:ConditionCheckItem`, `DescribeTable`, `DescribeTimeToLive`, `GetItem`, `PutItem`, and `UpdateItem` against the one existing shared authority table.
`TransactWriteItems` authorizes its constituent item operations rather than a standalone IAM action; the durable poison transaction specifically requires `ConditionCheckItem` and `UpdateItem`.
It grants no S3, `Scan`, delete, wildcard-resource, or table-administration permission.

Provision these exact protected environments:

- `legalforecastbench-official-labeling-baton`
- `legalforecastbench-official-labeling-authority-smoke`
- `legalforecastbench-official-labeling-anthropic-unitize`
- `legalforecastbench-official-labeling-google-review`
- `legalforecastbench-official-labeling-openai-label`
- `legalforecastbench-official-labeling-google-label`

The canonical machine-readable setup contract is `infra/official-labeling/github-environments.json`.
It defines exactly these six environments, their main-only protection and required human reviewer, exact OIDC subjects, and closed secret and variable inventories.
Because `johnhughes3` is the sole reviewer and may also dispatch an official run, self-review prevention remains disabled; enabling it without a second authorized reviewer would deadlock every deployment.
Environment creation, protection, variables, and secrets are separately authorized GitHub administration actions; the manifest is declarative evidence and does not perform those actions.

Each environment must require a human reviewer and use a deployment branch policy that admits only `main`, with no tag or side-branch deployment.
These rules are acceptance prerequisites: the OIDC trust policy binds the environment subject, but an environment-form subject does not independently bind the Git ref.
Each provider-bearing environment contains exactly one provider secret named `PROVIDER_API_KEY`, the transport-only `BATON_AGE_IDENTITY`, and protected variables `LFB_BATON_AGE_RECIPIENT`, `LFB_GITHUB_LABELING_ROLE_ARN`, `LFB_PROVIDER_AUTHORITY_TABLE`, `LFB_PROVIDER_ACCOUNT_ALIAS`, and `LFB_AWS_REGION`.
The baton environment contains only the `BATON_AGE_IDENTITY` secret and the matching public `LFB_BATON_AGE_RECIPIENT` variable, requires a human reviewer, admits only `main`, and grants no OIDC, AWS, provider, evaluation, freeze, or dispatch authority.
The same one-key age identity is present in the baton and four provider environments because GitHub environment secrets cannot alias one another; it is one cryptographic identity, not five independent credential values.
The authority-smoke environment contains no provider secret; it holds only the exact non-secret authority variables named by its workflow.
The workflow resolves the environment from a closed stage/provider mapping; the dispatcher cannot supply an environment or role ARN.
It maps the one generic secret to `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY` only inside the provider-call step.
The provider-bearing job is pinned to a GitHub-hosted runner rather than a mutable runner-label variable, and its 7,200-second OIDC role session matches the 120-minute job timeout.
AWS OIDC credentials are cleared through `GITHUB_ENV` before any result is sealed, the provider secret is step-scoped rather than persisted, and decrypted state is destroyed before upload.

LegalForecastBench is a public repository, so a plaintext Actions artifact is not private: signed-in public-repository readers can download it.
Never upload source documents, decision text, provider journals, raw model output, labels, or any other paid-labeling state as plaintext.
Before dispatch, build a closed source package containing `official-paid-labeling-job.json` and every path it names, encrypt it to the reviewed Cycle 1 age recipient, and upload only the ciphertext to a never-published draft GitHub release.
The source builder rejects provider journals, symlinks, hardlinks, special files, duplicate or escaping paths, undeclared residue, and file or aggregate size-limit violations; its package manifest commits the exact sorted path, byte count, and SHA-256 of every regular file plus the release, stage, provider, sequence, job-manifest hash, and predecessor identity.
Generate and retain the age identity only on a trusted human-controlled machine; expose only its public recipient to this provider-free command:

```bash
uv run legalforecast acquisition build-paid-labeling-source \
  --source-root <closed-provider-free-source-root> \
  --release-sha <exact-main-release-sha> \
  --stage llm-unitize \
  --provider anthropic \
  --sequence-ordinal 1 \
  --age-executable <reviewed-age-executable> \
  --age-recipient <public-cycle-age-recipient> \
  --output-ciphertext <private-staging-root>/official-paid-labeling-source-<exact-main-release-sha>-llm-unitize-anthropic-1.age \
  --receipt-output <private-staging-root>/source-receipt.json \
  --execute
```

For sequence 2 through 4, build the next stage-specific source tree and repeat the command with the exact next stage/provider/ordinal plus `--predecessor-receipt <prior-result-receipt.json>`.
The ciphertext asset name is canonical: `official-paid-labeling-source-<release-sha>-<stage>-<provider>-<sequence>.age`.
The receipt is public-safe commitment metadata, but the source tree and any decrypted bytes remain in controlled private storage.
Run `.github/workflows/official-paid-labeling-baton.yaml` with the exact draft release ID, asset ID, asset name, size, GitHub asset digest, package-manifest SHA-256, release SHA, stage, provider, and sequence ordinal.
The provider-free protected workflow rechecks the immutable `main` release, exact draft asset metadata and bytes, decrypts only under `legalforecastbench-official-labeling-baton`, validates the closed package without archive extraction shortcuts, re-encrypts it, destroys plaintext and the identity file, and uploads only the ciphertext plus a public-safe hash/count receipt.
Both the baton assembler and provider workflow rematerialize the package at `${{ github.workspace }}/.official-paid-labeling-job`, so the journal's immutable canonical-path identity survives sequential GitHub-hosted jobs instead of being silently rebased.
For sequence ordinals after one, it also requires the exact completed predecessor run attempt, encrypted artifact name and digest, predecessor package-manifest SHA-256, and immediate-predecessor identity; forks, skipped predecessors, collisions, or a reset provider journal fail closed.
There is no supported laptop-to-Actions-artifact upload API, and the shared code-quality runner must not be repurposed to read private acquisition state.
All paths are relative to the artifact root; absolute paths, `..` escapes, unknown arguments, provider-authority arguments, provider-shard merge inputs, and shell fragments are rejected.
Record the artifact-producing workflow run ID and attempt, exact artifact name and GitHub digest, package-manifest SHA-256, job-manifest SHA-256, full release SHA on `main`, sequence ordinal, stage, and provider as the protected workflow inputs.
The manifest has this closed shape:

```json
{
  "schema_version": "legalforecast.official_paid_labeling_job.v1",
  "release_sha": "<40-character-main-commit>",
  "stage": "llm-unitize",
  "provider": "anthropic",
  "arguments": {
    "output-root": "cycle-root",
    "selection": "inputs/selection.jsonl",
    "parser-manifest": "inputs/parser-manifest.jsonl",
    "model-registry": "inputs/stage-a-registry.json",
    "model-key": ["anthropic:<model-id>"],
    "provider-cycle-caps": "inputs/provider-cycle-caps.json",
    "provider-journal": "cycle-root/provider-attempts.sqlite3"
  }
}
```

Include every additional lineage argument required by the selected acquisition command.
The protected wrapper appends `--provider-authority-table`, `--provider-authority-region`, and `--execute`; the manifest may not supply them.
It also requires the selected model and protected public account alias to match the frozen registry and provider-cycle-caps.
The shared authority constructor runs `DescribeTable`, hashes the actual table ARN, compares it with `spend_authority.resource_identity_sha256`, verifies the exact two-key schema, and refuses any mismatch before a provider call.

For Stage B, create one job manifest per provider.
Each manifest names the complete frozen judge panel, while the protected wrapper appends the one `--execution-provider` allowed by its environment.
Each provider job emits `llm-label-provider-shard` audit and run-card artifacts but no selected labels.
Treat the encrypted result artifact as a sequential baton: every paid stage must start from the immediately preceding result artifact, retain the same canonical `provider-journal` path, and use distinct provider-specific audit, labels, queue, log, and run-card paths.
In particular, do not launch the Google and OpenAI Stage B shards in parallel from two copies of the same SQLite journal.
The workflow-wide `official-paid-labeling` concurrency group serializes protected paid jobs as a second guard against accidental parallel dispatch.
Run the first provider shard, rebuild the next encrypted closed baton from that result with only the next manifest and provider-specific output paths changed, then run the second shard.
The remote DynamoDB authority prevents aggregate overspend, but the local journal is the authenticated replay chain; divergent SQLite copies are intentionally not mergeable and will fail provider-free reconciliation.
After every provider shard succeeds, merge them in a provider-free context by passing each authenticated audit and run card to `llm-label`; the merge revalidates the full candidate/provider cross-product, exact prompts, decision commitments, model outputs, frozen-unit coverage, and shared journal before producing the ordinary `llm-label` run card.
No provider credential or remote authority role is needed by this finalization step.

Record the following evidence before treating the path as live:

1. Terraform plan/apply identity for `infra/official-labeling`, without copying the role ARN or AWS account ID into a public artifact.
2. Protected producer and provider workflow run URLs and attempts, release SHA, environments, encrypted artifact digests, package- and job-manifest SHA-256 values, sequence/predecessor identities, provider-cycle-caps SHA-256, public provider account alias, and output run-card SHA-256.
3. A provider-free live smoke proving allowed operations against the exact authority table and denied read/write operations against a distinct canary table, plus denied scan, delete, and table administration.
4. Confirmation that the identity and credential-clear steps ran, plaintext state was destroyed, and the uploaded artifact contains only ciphertext plus its public-safe receipt.

Provisioning and the live provider-free permission smoke are external checkpoints.
Until both are recorded, keep only the distributed protected-workflow path blocked; committed code and static tests alone do not satisfy that operational evidence.
This checkpoint does not block the canonical Cycle 1 local-journal Stage A or Stage B stages.
Run the smoke through `.github/workflows/official-paid-labeling-authority-smoke.yaml` in `legalforecastbench-official-labeling-authority-smoke`.
Set `LFB_OUTSIDE_AUTHORITY_TABLE` to a real, distinct disposable canary table so an `AccessDenied` result proves the exact-table resource boundary rather than merely encountering a missing table.
The smoke first requires DynamoDB TTL to be enabled on the exact `expires_at` attribute, then writes only TTL-bounded sentinel rows, makes no provider call, suppresses denial diagnostics that can contain AWS account details, and uploads only the release SHA, public table-identity hash, and boolean allow/deny results.

After the protected authority-smoke workflow succeeds, download its raw `authority-smoke.json` artifact without recreating or reformatting it and record the exact artifact SHA-256 plus the full reviewed main release SHA.
Create the public `legalforecast.provider_cycle_caps_successor_policy.v1` artifact in canonical JSON form as specified by [the successor contract](schemas/provider-cycle-caps-successor-v1.md), using one public account alias for each legacy provider and no ARN, AWS account ID, credential, secret, or token material.
Then derive the authority-enabled caps only through the supported provider-free command:

```bash
uv run legalforecast acquisition materialize-provider-cycle-caps-successor \
  --legacy-provider-cycle-caps /absolute/path/provider-cycle-caps-legacy.json \
  --expected-legacy-caps-sha256 <lowercase-sha256-of-exact-legacy-bytes> \
  --authority-smoke-receipt /absolute/path/authority-smoke.json \
  --expected-authority-smoke-sha256 <lowercase-sha256-of-exact-raw-smoke-bytes> \
  --expected-smoke-release-sha <full-lowercase-reviewed-main-commit> \
  --provider-caps-successor-policy /absolute/path/provider-caps-successor-policy.json \
  --expected-provider-policy-sha256 <lowercase-sha256-of-exact-policy-bytes> \
  --output-root /absolute/path/provider-caps-successor
```

The command verifies the complete closed smoke schema, exact release, raw byte digest, authority identity, all required allowed and denied operations, and `provider_call_made=false` before it opens or creates the output root.
It then exclusively publishes `provider-cycle-caps.json`, its public successor receipt, and the completed run card, with exact partial-output repair on resume and no AWS or provider call.
Any identity-only substitute, uppercase digest, changed input, noncanonical policy, unsafe link, special file, conflicting byte, or unexpected output residue fails closed.
Use the resulting exact `provider-cycle-caps.json` path in every paid Stage A and Stage B command below; retain the successor receipt and run card as pre-provider launch evidence.

Run every provider-bearing Stage A or Stage B shard only through `uv run legalforecast-provider-env-run --provider <provider> -- ...`. The wrapper accepts either the local labeling stage view containing `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY` or the protected workflow's single `LFB_PROVIDER_API_KEY`, rejects known cross-stage secret names, strips inherited `UV_ENV_FILE`, forces `UV_NO_ENV_FILE=1` for child `uv run` invocations, and starts the child with exactly one provider key name. No secret value appears on the command line.

Unitize Stage A only from that exact authenticated materialization and pinned live-parser lineage. Use one explicit provider journal for the cycle; creating a fresh output-root-local journal is refused because it would reset the cycle reservation ledger:

```bash
uv run legalforecast-provider-env-run \
  --provider anthropic -- \
  uv run legalforecast acquisition llm-unitize \
    --output-root <assembled-cycle-root> \
    --controlled-private-root <absolute-controlled-private-approval-root> \
    --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
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
    --provider-attempt-namespace claim-ontology-v4 \
    --provider-authority-table <exact-shared-authority-table-name> \
    --provider-authority-region <aws-region> \
    --execute --no-resume
```

Before any provider call, the command replays the target selection, immutable materializer, parse requests, pinned live-Mistral card, parser manifest, and complete Markdown tree. It rejects provider caps whose `cycle_id` differs from the authenticated cohort. The journal stores an immutable v2 identity containing that cycle ID, the exact caps-artifact hash, and its canonical path; copying it to another output root or opening it with changed caps is refused. The completed run card commits the journal schema and identity, exact registry entry, caps artifact, prompts, settled provider attempts, reconstructed units, raw outputs, audit, and review queue. A partial `--continue-on-error` run remains resumable but is explicitly marked incomplete and is inadmissible downstream.

The superseding Cycle 1 citation-provenance migration uses `--provider-attempt-namespace claim-ontology-v4` for both `llm-unitize` and `llm-review-stage-a`. V4 line-numbers each supplied predecision document, requires the unitizer to select bounded complaint and target-motion line spans for every unit, and reconstructs exact document-bound excerpts locally; the structural reviewer uses the same selector mechanism instead of authoring citation text. Do not mix v4 with an earlier unitizer or reviewer contract. The historical accepted pairs remain unnamespaced/unnamespaced, v2/v2, and v2/v3 for authenticated replay only. New journal-backed calls without a namespace fail closed. Provider-free unitization recovery may select the historical contract explicitly. Structural-review recovery and terminalization derive the legacy contract from the unitization card when no selector is supplied, or accept its exact closed contract explicitly. A namespace versions a reviewed contract; never use a new namespace to retry an unchanged contract or evade a settled or failed attempt.

Run the structural Stage A review against the same unitizer card, caps artifact, and canonical provider journal even when its ordinary outputs live under a different root:

```bash
uv run legalforecast-provider-env-run \
  --provider google -- \
  uv run legalforecast acquisition llm-review-stage-a \
    --output-root <structural-review-root> \
    --controlled-private-root <absolute-controlled-private-approval-root> \
    --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
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
    --provider-attempt-namespace claim-ontology-v4 \
    --provider-authority-table <exact-shared-authority-table-name> \
    --provider-authority-region <aws-region> \
    --execute --no-resume
```

The command replays Stage A before resolving the reviewer model, refuses a different journal path, wrong cycle, or byte-different caps artifact before a provider call, and commits the exact reviewer model, prompt identities, provider attempts, input artifacts, merged queue, flags, and audit in its run card.

If the same structural-review candidate has already produced exactly two byte-identical normalized responses that both failed local reconstruction, do not issue a third paid request or accept a flag. Generate the narrow `v1`, provider-free terminal receipt and then resume structural review with it. If that early shortcut did not qualify, complete no more than the normal three reconstruction attempts; after all three have durably failed, the same receipt command may emit the distinct `v2` receipt binding every failure. The receipt command authenticates the current Stage A lineage and journal, writes no journal state, and fails closed unless either the v1 two-attempt evidence or the v2 exhausted-three-attempt evidence matches exactly:

```bash
uv run legalforecast acquisition terminalize-llm-review-stage-a-reconstruction \
  --output-root <terminal-escalation-root> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --markdown-root <parsed-markdown-root> \
  --prediction-units <prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --unitization-review-queue <unitization-review-queue.jsonl> \
  --model-registry <frozen-stage-a-reviewer-registry.json> \
  --model-key <provider:model-id> \
  --provider-attempt-namespace claim-ontology-v4 \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --candidate-id <candidate-id> \
  --execute --no-resume
```

Pass the emitted receipt to the resumed review command with `--terminal-escalation <terminal-escalation-receipt.json>`. This produces a deterministic pending review item for every affected frozen unit, preserving the exact reviewer prompt, all failed-attempt commitments, and blinded predecision sources for John. It does not turn an invalid response into an accepted structural flag; ordinary retries remain unchanged for every candidate without a receipt.

Before adjudication, build John’s private blinded review bundle only after the current Stage A v4 structural-review run has completed and its exact merged queue exists. This command is provider-free: it replays both Stage A cards, does not open a provider client, and never writes adjudications. Keep `<private-stage-a-review-root>` out of the repository and all public/publishable artifact roots.

```bash
uv run legalforecast acquisition build-unitization-review-bundle \
  --output-root <private-stage-a-review-root> \
  --prediction-units <prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --llm-review-stage-a-run-card <llm-review-stage-a-run-card.json> \
  --unitization-review-queue <verified-merged-review-queue.jsonl> \
  --execute --no-resume
```

The output is `unitization-review-bundle.jsonl` plus `unitization-review-bundle-manifest.json` and the completion run card `run-cards/build-unitization-review-bundle.json`. The completion card records this provider-free handoff's authenticated inputs, output paths, and record count. Every pending review appears exactly once with the full raw candidate units and only the predecision Mistral Markdown cited by those units or its review item. Terminal reconstruction-escalation rows derive their source IDs from authenticated frozen units and predecision commitments. Decision/order material, text from decision artifacts, mismatched candidate/unit/source identifiers, markdown escapes, links, nonregular files, hard links, and byte drift all fail closed. The manifest binds the raw units, both cards, exact merged queue, selection, parser manifest, Markdown root/tree, and output SHA-256. Do not publish a production bundle before that Stage A structural-review output exists; use the JSONL solely to prepare a separate checked-in adjudication file.

After structural review, apply adjudications only through the authenticated unitizer card:

```bash
uv run legalforecast acquisition apply-unitization-review \
  --output-root <assembled-cycle-root> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
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

Build the Stage B disposition-text artifact only from the exact selected cohort, authenticated materialization lineage run card, restriction evidence, and pinned Mistral parser output used by the cycle:

```bash
uv run legalforecast acquisition build-decision-texts \
  --output-root <assembled-cycle-root> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --selection <selection.jsonl> \
  --selection-run-card <project-or-extend-target-cohort-run-card.json> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --restriction-evidence <restriction-evidence.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parser-run-card <parse-documents-run-card.json> \
  --markdown-root <parsed-markdown-root> \
  --decision-texts-output <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest-output <assembled-cycle-root>/decision-texts-manifest.json \
  --execute --no-resume
```

The command reconciles exact candidate and document coverage; verifies the target-cohort, authenticated clearance, and live-parser run-card commitments; admits only the single public, outcome-bearing, non-model-visible first written disposition entered on or after the Cycle 1 anchor; and binds the source and extracted-text hashes to the pinned parser revision. Fixture parser provenance is refused. It fails closed on missing, ambiguous, sealed, private, malformed restriction flags, unpinned, unauthenticated, or drifted inputs. `decision-texts.jsonl` is private Stage B and audit input only: never place it in a model-visible packet, hand-edit it, or substitute a manually assembled file.

Pass that exact artifact, its immutable manifest, and the completed builder run card to Stage B. The parser manifest and Markdown remain required only to cross-check the authenticated artifact against the pinned live-Mistral lineage; `llm-label` never uses Markdown directly as prompt authority. Run the following paid OpenAI shard through the protected workflow or the same reusable local wrapper:

```bash
uv run legalforecast-provider-env-run \
  --provider openai -- \
  uv run legalforecast acquisition llm-label \
    --output-root <assembled-cycle-root> \
    --controlled-private-root <absolute-controlled-private-approval-root> \
    --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
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
    --model-registry <frozen-stage-b-judge-registry.json> \
    --evaluated-model-registry <frozen-evaluated-model-registry.json> \
    --model-key <frozen-judge-key-1> \
    --model-key <frozen-judge-key-2> \
    --model-key <...every-remaining-frozen-judge-key> \
    --provider-cycle-caps <provider-cycle-caps.json> \
    --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
    --execution-provider openai \
    --audit-output <openai-shard-audit.jsonl> \
    --run-card-output <openai-shard-run-card.json> \
    --provider-authority-table <exact-shared-authority-table-name> \
    --provider-authority-region <aws-region> \
    --execute --no-resume
```

Run the matching Google shard the same way, with the identical frozen judge panel and canonical provider journal:

```bash
uv run legalforecast-provider-env-run \
  --provider google -- \
  uv run legalforecast acquisition llm-label \
    --output-root <assembled-cycle-root> \
    --controlled-private-root <absolute-controlled-private-approval-root> \
    --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
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
    --model-registry <frozen-stage-b-judge-registry.json> \
    --evaluated-model-registry <frozen-evaluated-model-registry.json> \
    --model-key <frozen-judge-key-1> \
    --model-key <frozen-judge-key-2> \
    --model-key <...every-remaining-frozen-judge-key> \
    --provider-cycle-caps <provider-cycle-caps.json> \
    --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
    --execution-provider google \
    --audit-output <google-shard-audit.jsonl> \
    --run-card-output <google-shard-run-card.json> \
    --provider-authority-table <exact-shared-authority-table-name> \
    --provider-authority-region <aws-region> \
    --execute --no-resume
```

Repeat `--model-key` for every entry in the frozen judge registry in every provider-shard job.
Do not place OpenAI and Google credentials in one job.
After all provider jobs complete, run the same command without a provider credential or authority-table argument, replacing `--execution-provider` with matching audit/card pairs:

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
  --model-registry <frozen-stage-b-judge-registry.json> \
  --evaluated-model-registry <frozen-evaluated-model-registry.json> \
  --model-key <every-frozen-judge-key-repeated> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --provider-shard-audit <openai-shard-audit.jsonl> \
  --provider-shard-run-card <openai-shard-run-card.json> \
  --provider-shard-audit <google-shard-audit.jsonl> \
  --provider-shard-run-card <google-shard-run-card.json> \
  --labels-output <labels.jsonl> \
  --audit-output <llm-label-audit.jsonl> \
  --lawyer-review-queue-output <lawyer-review-queue.jsonl> \
  --run-card-output <llm-label-run-card.json> \
  --execute --no-resume
```

Before the first provider reservation, each paid shard replays the authenticated unitizer, structural-review, and apply-review cards; verifies exact candidate and case mapping, decision-document, disposition-date, text, text-hash, source hash and byte count, empty parser quality flags, selection, parser, and finalized-unit coverage and provenance; and requires the same canonical journal and exact caps artifact used by Stage A.
The provider-free merge binds the decision JSONL, manifest, run card, per-record and text hashes, exact finalized-units file, candidate-envelope hashes, full Stage A card chain, authenticated shard cards, journal identity, and complete settled-attempt cross-product into the final `llm-label` run card.
Changing `--output-root` cannot create a new ledger because `--provider-journal` must still resolve to the unitizer-committed canonical path.
Any mismatch stops the paid shard without a provider call or stops the merge without selected labels.

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
  --download-manifest <materialized-download-manifest.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --resolved-post-recovery-documents <resolved-post-recovery-documents.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --purchase-policy <purchase-policy.json> \
  --purchase-ledger <canonical-purchase-ledger.sqlite3> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization.json> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --model-registry model_registries/cycle-1-2026-06-30.json \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --document-root <materialized-document-root> \
  --markdown-root <parsed-markdown-root> \
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
  --download-manifest <materialized-download-manifest.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parser-run-card <parse-documents-run-card.json> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --raw-prediction-units <raw-prediction-units.jsonl> \
  --prediction-units <finalized-prediction-units.jsonl> \
  --llm-unitization-audit <llm-unitization-audit.jsonl> \
  --llm-unitize-run-card <llm-unitize-run-card.json> \
  --llm-unitize-provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --original-unitization-review-queue <original-review-queue.jsonl> \
  --stage-a-structural-flags <stage-a-structural-flags.jsonl> \
  --stage-a-structural-review-audit <stage-a-structural-review-audit.jsonl> \
  --stage-a-review-run-card <llm-review-stage-a-run-card.json> \
  --stage-a-review-provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --stage-a-review-model-registry <stage-a-review-model-registry.json> \
  --stage-a-review-model-key <stage-a-review-model-key> \
  --unitization-review-queue <merged-unitization-review-queue.jsonl> \
  --unitization-review-adjudications <john-adjudications.jsonl> \
  --apply-unitization-review-run-card <apply-unitization-review-run-card.json> \
  --parse-plan-run-card <plan-parse-documents-run-card.json> \
  --model-registry model_registries/cycle-1-2026-06-30.json \
  --expected-model-registry-sha256 <sha256-of-frozen-registry> \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --document-root <materialized-document-root> \
  --markdown-root <parsed-markdown-root> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --controlled-private-root <purchase-approval-private-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization-receipt.json> \
  --execute --no-resume
```

Final corpus reconciliation runs only after both packet stages complete. It consumes the authenticated decision-text JSONL, its manifest and completed builder run card, and the three content files from one canonical complete and saturated screening snapshot plus that snapshot's manifest:

Executed packet-planner cards commit every deterministic parameter and exact source file, and executed packet-builder cards commit the selected ablation and all three outputs. `build-packets` replays planning byte-for-byte, authenticates the raw docket bytes against the materializer's screening snapshot, authenticates the parser manifest and finalized Stage A units against their upstream run cards, and requires the evaluated registry to match the separately frozen SHA-256 supplied by the operator. `finalize-corpus --execute` repeats those authorities and replays both planning and packet assembly before accepting the cards. Never hand-author, rehash, or repair these cards or their committed artifacts.

```bash
uv run legalforecast acquisition finalize-corpus \
  --output-root <assembled-cycle-root> \
  --selection <selection.jsonl> \
  --parser-manifest <parser-manifest.jsonl> \
  --parse-plan-run-card <plan-parse-documents-run-card.json> \
  --parser-run-card <parse-documents-run-card.json> \
  --disclosure-clearance <materialized-disclosure-clearance.jsonl> \
  --download-manifest <materialized-download-manifest.jsonl> \
  --materialization-run-card <materialize-cohort-documents-run-card.json> \
  --document-root <materialized-document-root> \
  --controlled-private-root <purchase-approval-private-root> \
  --purchase-ledger-initialization-receipt <purchase-ledger-initialization-receipt.json> \
  --raw-prediction-units <raw-prediction-units.jsonl> \
  --llm-unitization-run-card <llm-unitize-run-card.json> \
  --llm-review-stage-a-run-card <llm-review-stage-a-run-card.json> \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --prediction-units <finalized-prediction-units.jsonl> \
  --llm-unitization-audit <llm-unitization-audit.jsonl> \
  --llm-unitize-run-card <llm-unitize-run-card.json> \
  --llm-unitize-provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --original-unitization-review-queue <original-review-queue.jsonl> \
  --stage-a-structural-flags <stage-a-structural-flags.jsonl> \
  --stage-a-structural-review-audit <stage-a-structural-review-audit.jsonl> \
  --stage-a-review-run-card <llm-review-stage-a-run-card.json> \
  --stage-a-review-provider-journal <cycle-private-root>/provider-attempts.sqlite3 \
  --stage-a-review-model-registry <stage-a-review-model-registry.json> \
  --stage-a-review-model-key <stage-a-review-model-key> \
  --unitization-review-queue <merged-unitization-review-queue.jsonl> \
  --unitization-review-adjudications <john-adjudications.jsonl> \
  --apply-unitization-review-run-card <apply-unitization-review-run-card.json> \
  --markdown-root <parsed-markdown-root> \
  --raw-html-dir <union-output-root>/union-raw-artifacts \
  --raw-artifacts-manifest <union-output-root>/union-raw-artifacts.jsonl \
  --decision-texts <assembled-cycle-root>/decision-texts.jsonl \
  --decision-texts-manifest <assembled-cycle-root>/decision-texts-manifest.json \
  --decision-texts-run-card <assembled-cycle-root>/run-cards/build-decision-texts.json \
  --labels <labels.jsonl> \
  --llm-label-audit <llm-label-audit-cycle-planned.jsonl> \
  --original-llm-label-labels <llm-label-output-root>/labels.jsonl \
  --original-llm-label-audit <llm-label-output-root>/llm-label-audit.jsonl \
  --llm-label-run-card <llm-label-run-card.json> \
  --stage-b-judge-registry model_registries/cycle-1-stage-b-judges-2026-07-12.json \
  --labeling-policy <precommitted-labeling-policy.json> \
  --lawyer-review-queue <lawyer-review-queue.jsonl> \
  --lawyer-review-audit <lawyer-review-audit.jsonl> \
  --packet-build-input <assembled-cycle-root>/packet-build-input.jsonl \
  --packet-input-run-card <assembled-cycle-root>/run-cards/plan-packet-inputs.json \
  --packets <assembled-cycle-root>/packets.jsonl \
  --packet-build-run-card <assembled-cycle-root>/run-cards/build-packets.json \
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

Do not hand-author a compatibility summary or substitute a replay-stage summary. `finalize-corpus` requires the successful canonical `prepare-target-cohort` root, verifies its self-hashed configuration, completion evidence, and exhaustive stage commitments, and uses that authenticated lineage to pin the exact snapshot path, manifest hash, cycle hash, batch digest, and target size. It replays the authenticated unitizer and structural-review cards against the exact raw units, original and merged review queues, structural flags, review audit, reviewer registry and key, provider-caps bytes, and canonical shared journal before accepting and reproducing the apply-review output. It then replays the authenticated `llm-label` card against the same Stage A authority, exact decision-text inputs, judge registry, journaled per-model reconstructions, and the immutable outputs supplied separately as `--original-llm-label-labels` and `--original-llm-label-audit`; the reviewed `--labels` and cycle-planned `--llm-label-audit` remain the readiness inputs and cannot masquerade as the original provider outputs. Finally it verifies the snapshot's immutable cycle-store registration, complete and saturated state, member hashes, row counts, and accepted-plus-excluded reconciliation, and accepts the packet artifacts only after those gates pass. Include every later exclusion file separately with `--exclusion-source` so every screened-but-unselected or downstream-rejected candidate reaches the complete exclusion ledger.

## Before Dispatch

Run the release gate at the exact SHA you intend to dispatch:

```bash
uv run scripts/release_check.py
```

Prepare the frozen run-input manifest, locked labels, model registry, and packet objects. The run-input manifest must use the same `cycle_id` as the dispatch and either omit `labels_sha256` or contain the SHA-256 of the exact labels JSONL. Generate and commit the hash-only freeze commitment before dispatch:

```bash
uv run legalforecast freeze <cycle_id> \
  --bundle-output manifests/<cycle_id>.freeze.json \
  --manifest <cycle-manifest> \
  --units <prediction-units.jsonl> \
  --labels <labels.jsonl> \
  --exclusion-ledger <exclusion-ledger.jsonl> \
  --prompt <prompt-artifact> \
  --scorer <scorer-artifact> \
  --harness <harness-artifact> \
  --model-registry <model-registry.json> \
  --baselines manifests/<cycle_id>.no-baselines.json \
  --provider-cycle-caps <provider-cycle-caps.json> \
  --execution-policy <execution-policy.json> \
  --labeling-policy <labeling-policy.json> \
  --cohort-policy <cohort-policy.json>
```

`--baselines` is required even when the frozen execution policy sets `allow_no_baselines` to `true`. The current freeze implementation requires an existing regular file and hash-binds its bytes, but it does not parse or schema-validate the baselines artifact. For Cycle 1, which has no frozen historical baseline corpus, use a reviewed, committed JSON sentinel rather than a zero-byte file:

```json
{
  "schema_version": "legalforecast.no_baselines.v1",
  "cycle_id": "<cycle_id>",
  "status": "unavailable",
  "reason": "No frozen historical baseline corpus exists for Cycle 1."
}
```

The sentinel is a hash-bound disclosure, not the enforcement authority; `execution-policy.json` remains authoritative for `allow_no_baselines`, and the dispatch input must match it. Replace the sentinel with the frozen baseline artifact only in a later cycle that has one.

Use `uv run legalforecast freeze --help` for the exact argument shape. The workflow verifies the committed freeze commitment, substituting the downloaded labels and model registry for their checkout paths, before matrix fan-out. The separately downloaded run-input manifest is validated and label-bound by the workflow's manifest-freeze step; it is not substituted for the cycle manifest recorded in the freeze bundle.

The intended AWS boundary is defined, but not applied, under [`infra/official-eval/`](../infra/official-eval/README.md). Its canonical protected-environment contract is [`infra/official-eval/github-environments.json`](../infra/official-eval/github-environments.json), which defines the infrastructure bootstrap, evaluation cell, and fan-in environments with closed variable and secret-name inventories. The role bindings use the current `legalforecastbench-official-eval` cell environment with `LFB_AWS_REGION`, `LFB_GITHUB_PACKET_READ_ROLE_ARN`, and `LFB_PROVIDER_AUTHORITY_TABLE`, plus the `legalforecastbench-official-eval-fan-in` environment with the same reviewed `LFB_AWS_REGION`, `LFB_GITHUB_FAN_IN_ROLE_ARN`, and `LFB_PACKET_BUCKET`; do not recreate the obsolete five-environment topology. The runner derives each provider's account alias from its unique cap in the verified frozen execution policy. Before live acceptance, verify that both runtime environments exist and are protected for `main`, ensure fan-in has no secrets or provider role, and assign the reviewed applied outputs through the human-approved server-side configuration path.

The packet/result role used by each case writer has only the current packet, manifest, per-case, closure, and exact provider-attempt authority operations. It may create and read the two explicit resource patterns `cycle-publication-state/*/runs/*/*/intent.json` and `cycle-publication-state/*/runs/*/*/done.json`, has read-only GetObject authority for `cycle-publication-state/*/seal.json`, and has prefix-conditioned `s3:ListBucket` authority only for the exact seal-key pattern and current packet/per-case validation paths. `begin` uses this exact-key ListObjectsV2 probe before GetObject because S3 otherwise returns 403 rather than 404 for an absent object when ListBucket is denied. Immutable writes are separate from reads and require the `If-None-Match: *` request header; ordinary versioned per-case writes remain unconditional. The cell role may call only `ConditionCheckItem`, `DescribeTable`, `GetItem`, `PutItem`, and `UpdateItem` on the one DynamoDB table whose exact ARN hash is frozen in the provider-caps artifact. The workflow supplies the protected table name and region to every live runner; each runner derives its public account alias from the verified frozen provider cap and re-verifies the actual table ARN and key schema before a provider call. The cell role has no broader marker listing, seal write, receipt, or report-prefix authority. It also has no DynamoDB table administration, scan, or delete authority and no S3 delete, ACL, or version-list authority. The provider-free fan-in role has prefix-conditioned `s3:ListBucketVersions` authority only for `per-case/<cycle_id>/`, owns exact-version per-case reads, marker read/list and seal authority, finalizer marker and receipt writes, and exclusive canonical publication under `reports/<cycle_id>/multi-ablation/`, with the same create-once precondition on every immutable write.

Both roles use `aws_iam_role_policies_exclusive` and `aws_iam_role_policy_attachments_exclusive`, so the first apply is a reconciliation boundary: inventory and import existing role policies, account for every legitimate inline policy, and verify the planned managed-policy set is empty before apply. Unlisted policies will be removed.

Bedrock invocation is disabled by default. Verify the protected `LFB_ANTHROPIC_RUNTIME` value through the approved operator path before provisioning or enabling Bedrock; never infer or guess it. Keep the direct Anthropic path with both `bedrock_direct_foundation_model_arns = []` and `bedrock_geographic_inference_profiles = {}`, or deliberately enable the cell-only Bedrock policy with a structured contract that matches `LFB_ANTHROPIC_BEDROCK_MODEL_ID`. Direct foundation-model ARNs receive their own unconditional statement. Every reviewed `us.*`, `eu.*`, or `apac.*` geographic inference profile follows AWS's two-statement contract: an unconditional statement grants only its exact profile ARN, while a separate statement grants its complete reviewed source-and-destination foundation-model ARN set conditioned by exact equality on `bedrock:InferenceProfileArn`. Those conditioned model grants cannot be used for direct model invocation. Global inference profiles are rejected because their distinct three-part policy is not modeled here. Fan-in never receives provider authority.

The private versioned result bucket retains the noncurrent objects named by receipt `VersionId` commitments; there is no blanket 30-day deletion rule. Per-case data can include PII, so any future destructive retention is an explicit review against the receipt audit horizon. Reserve `reports/security-negative-controls/` for live denied-write canaries and administrator/lifecycle cleanup; never aim a negative control at a canonical report path.

Terraform format, initialization, validation, tests, and even a reviewed plan prove only the code shape. Import the existing buckets into approved encrypted remote state before any apply, reconcile current bucket policy and lifecycle state, and apply only an exact reviewed plan. The S3 validation workflow requires a known existing packet, manifest, exact-version per-case metrics object, and shard receipt. It proves the fan-in role can read the committed per-case version and receipt, then reassumes the cell role and proves that the same existing receipt is denied. The workflow proves only the specific S3 reads, lists, denied mutations, and DynamoDB `DescribeTable` call it actually performs; it does not establish the cell role's successful DynamoDB item writes or transactions. Acceptance requires a post-provision validation dispatch from `main`, a bounded provider-authority smoke that exercises the item-level DynamoDB contract, and a provider-free fan-in verification dispatch from `main`. Always set `max_projected_model_cost_usd` to an explicit non-empty limit for a live run.

## Dispatch Sequence

Dispatch `Run Benchmark` from `main` with the frozen `cycle_id`, `run_input_manifest_uri`, `labels_uri`, `model_registry_uri`, and exactly one declared shard through the `model_keys` and `ablations` inputs. Set `shard_only: true` and keep `resume_existing_results: true`.

1. Run each declared shard with `dry_run: true` and an explicit spend cap. This validates the frozen schedule, hashes, model eligibility, projected cost, and exact shard identity without provider calls.
2. Run the bounded smoke under its dedicated smoke freeze and prefix. Complete it with `Fan In Official Shards` in `verify_only: true` mode; verification-only may accept the smoke cycle because its entry point has no canonical publication code path.
3. Dispatch every official shard only after the dry run and smoke pass. The frozen execution policy declares the exact shard schedule.
4. For transient cell failures, use GitHub's re-run-failed-jobs action. The finalizer writes a new immutable per-attempt receipt and may adopt verified successful cells from an earlier attempt in the same workflow run.
5. Do not use the legacy non-shard aggregate path for an official sharded cycle. Cross-run fan-in is a separate provider-free workflow and must not rerun the matrix.

Every non-dry-run result writer creates its own immutable `cycle-publication-state/<cycle_id>/runs/<writer_id>/<run_attempt>/intent.json` before writing and creates the matching `done.json` afterward. Matrix cells use `<run_id>-case-<strategy_job_index>` and the shard finalizer uses `<run_id>-finalize-shard`, so GitHub's **Re-run failed jobs** path opens new attempt-scoped intents even when successful jobs from the prior attempt are not rerun. After creating its intent, a writer probes exactly `cycle-publication-state/<cycle_id>/seal.json`; an API error, malformed listing, or unexpected key fails closed, while an exact seal match is read and causes the late writer to abort before provider work. If a workflow is canceled before cleanup, do not fabricate completion evidence: inspect the run, prove that exact writer is no longer active, then use `cycle_closure finish --writer-id <exact-writer-id>` with the exact run attempt under the matching protected role before retrying publication.

The resume identity includes the case, ablation, packet hash, solver/model identity, registry content, and repeat count. Current results bind to the canonical per-model registry-entry hash, so an unchanged model can resume across a registry amendment. Pre-amendment durable metrics that lack that field instead validate against the exact whole-registry hash recorded by their freeze in the provenance chain; supply that historical registry when recovering those cells. An unknown or mismatched registry hash fails closed rather than re-evaluating and overwriting durable outputs. Failed cells do not become canonical score rows. Preserve failed logs for audit.

## Aggregation

After every declared shard has a receipt, dispatch `Fan In Official Shards` at the exact 40-character trusted release SHA and provide one accepted shard's `source_dispatch_run_id` and `source_dispatch_run_attempt`. The workflow validates the exact completed `run-benchmark.yaml` attempt through GitHub's attempt-specific API and requires that attempt's `Build benchmark matrix` job to have succeeded; the overall attempt may have failed before a later **Re-run failed jobs** attempt completed the shard. It downloads the source attempt's non-overwritable `official-dispatch-provenance-<run_id>-<run_attempt>` artifact and uses the exact frozen run-input manifest, labels, and model registry bytes. The artifact binds the run ID, source dispatch attempt, and release SHA; every accepted receipt must bind the same release SHA, and at least one accepted receipt must bind that exact source attempt even when its receipt was finalized by a later workflow attempt. Fan-in auto-selects singleton shards and refuses any multi-receipt shard until a committed [accepted-attempt map](schemas/accepted-attempt-map-v1.md) selects exactly one receipt for each ambiguity. It verifies that the current union contains no uncommitted or stale object, fetches each accepted object by its exact S3 `VersionId`, verifies its size and SHA-256, and materializes only those bytes for `official_aggregate`.

For an amended freeze, keep every ancestor `*.freeze.json` bundle committed under `manifests/`. Fan-in supplies those committed bundles as the verification chain before it accepts the current amended bundle.

Leave `clean_motion_count` and `prediction_unit_count` empty unless using them as assertions. Fan-in derives the authoritative counts from the frozen included manifest, finalized units, and run-input case set; a supplied mismatch fails closed. Publishing first creates the permanent `cycle-publication-state/<cycle_id>/seal.json` and waits for every pre-existing mutation intent to have a matching completion. It then requires a non-smoke identifier with frozen `cycle_series: official`, stable receipt and current union-VersionId inventories through the final commit boundary, an empty canonical destination prefix, and any accepted-attempt map to match a tracked `manifests/` file in the release checkout.

The publishing entry point conditionally creates only the verified public directory under the canonical prefix. It claims the exact snapshot, writes every payload with create-only preconditions, rechecks the sealed receipt and union inventories immediately before commit, and creates `.publication-complete.json` as the final successful operation:

```text
s3://$LFB_RESULTS_BUCKET/reports/<cycle_id>/multi-ablation/
```

For a local audit with read authority to the durable result bucket, use the nonpublishing entry point. Strict receipt verification intentionally requires the canonical S3 object identities; local fixture stores are appropriate for unit tests, not a full official verification rehearsal.

```bash
uv run python -m legalforecast.publication.shard_fan_in \
  --verify-only \
  --freeze-bundle manifests/<cycle_id>.freeze.json \
  --amendment-bundle manifests/<cycle_id>.ancestor.freeze.json \
  --run-input-manifest manifests/<cycle_id>.run-inputs.json \
  --receipt-root s3://$LFB_RESULTS_BUCKET \
  --output-dir tmp/fan-in-verification/<cycle_id> \
  --accepted-attempt-map manifests/<cycle_id>.accepted-attempts.json
```

Omit `--amendment-bundle` for an unamended root freeze and repeat it for every required ancestor of an amended freeze. Omit `--accepted-attempt-map` when every declared shard has exactly one receipt. Verification-only writes only `fan-in-report.json` to the requested output directory; its temporary materialized union, private debug output, and aggregate bundle are destroyed after aggregate validation. The report records the complete accepted map when present, every accepted receipt, the discovered inventory hash, frozen artifact hashes, derived counts, verified union commitment, and aggregate completeness facts.

When the frozen execution policy requires a training baseline corpus, pass its exact bytes with `--baseline-training-examples <frozen-corpus.json>`; fan-in accepts the override only when its SHA-256 matches the freeze. Leave the option absent for an `allow_no_baselines: true` cycle whose required baselines artifact is metadata rather than a training corpus.

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

Extend the staged-rollout fixture rehearsal with this sequence before the real amendment dispatch:

1. Freeze and run fixture model A, aggregate it, and save SHA-256 checksums for every file in A's per-case artifact directory.
2. Create an amendment freeze whose registry adds fixture model B, then dispatch only B with the original dispatch in `prior_dispatches_json`.
3. Materialize the union, aggregate against the two-model registry with `--dispatch-provenance`, and confirm the leaderboard contains exactly A and B.
4. Recompute A's per-case artifact checksums and require an exact match with the pre-amendment checksum set. Any added, removed, or changed A artifact fails the drill as evidence of possible silent re-sampling.
5. Confirm the amended run card lists both dispatches, both freezes in order, A mapped to the original freeze, B mapped to the amendment freeze, and publication mode `additive_supersession`.

The automated rehearsal in `tests/test_official_run_runbook.py` performs the same two-generation aggregation and byte-identity assertion. The operator evidence record must still include the workflow run IDs, S3 union location, aggregate artifact, and checksum result for sign-off.

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

The preferred hierarchy is saturated CourtListener search → `batch-002 seed-direct-search` → authenticated `batch-002 observe` → `batch-002 snapshot` → `acquisition prepare-target-cohort --target-case-count 100`. CourtListener remains the source for decision results, docket reconstruction, free RECAP documents, authoritative paid-gap metadata, and every RECAP Fetch purchase. Firecrawl is used only for the demonstrated CourtListener search and docket-HTML surface gap, as a compatibility fallback when authenticated REST cannot supply the required surface; it does not become a legal-data or purchase authority. Case.dev is used only for equivalent free lookup and prioritization; no Case.dev live PACER fetch or purchase is permitted. Run every stage against the official acquisition store, never a batch-001 store, and do not pass mutable checkpoints directly to preparation.

### Supported Cycle Coordinator

For a new cycle, record the ordered production acquisition commands in one canonical [`legalforecast.acquisition_cycle_config.v1`](schemas/acquisition-cycle-config-v1.md) file and use `acquisition run-cycle` as the supported status/resume entry point.
The coordinator delegates to the existing commands in this runbook; it does not replace their flags, artifact verifiers, credentials, human approvals, provider authority, or budget enforcement.
Commands that do not yet emit the common acquisition completion card remain explicit runbook steps rather than being guessed complete by the coordinator.
Its default `--execute` mode advances provider-free stages only and reports the exact next command when it reaches a network, human, model-provider, or paid boundary.
Evaluation, freeze, dispatch, and publication are outside its allowlist.

Use the checked-in [cycle-template schema](schemas/acquisition-cycle-template-v1.md) and `render-cycle-config` for machine-specific absolute paths.
The renderer validates the complete future stage list before publishing the immutable config, so later outputs may be named before they exist without resorting to `/tmp` run cards or shell-history reconstruction.

```bash
mkdir -p -- "$PWD/artifacts/<cycle>"

uv run legalforecast acquisition render-cycle-config \
  --template manifests/<cycle>.acquisition-cycle.template.json \
  --variable REPO_ROOT="$PWD" \
  --variable ARTIFACT_ROOT="$PWD/artifacts/<cycle>" \
  --variable PRIVATE_ROOT="<absolute-controlled-private-root>" \
  --output "$PWD/artifacts/<cycle>/acquisition-cycle.json"
```

```bash
uv run legalforecast acquisition run-cycle \
  --config <absolute-canonical-cycle-config.json> \
  --state-root <absolute-cycle-orchestrator-root> \
  --execute --json
```

Add only the boundary switch required for the next reviewed stage.
One invocation executes at most one non-provider-free boundary stage and then stops for receipt review, even if the same switch would classify a later stage.
The coordinator also stops after the provider-free `generate-recap-fetch-broker-policy` stage with `stop_reason: broker_policy_deployment_checkpoint_stage_completed`; deploy and verify that policy before a separate invocation may reach the paid stage.
In particular, `--allow-paid` also requires `--allow-network` and still cannot run without the existing approved purchase policy, initialized ledger, bounded attempt policy, broker policy, broker identity, and remaining budget.
Every successful stage receives an immutable receipt bound to the exact config and completion run-card bytes, so rerunning the same command reauthenticates and skips it rather than reconstructing shell history.

After the first receipt exists, register the config/state pair in the machine-local [cycle lineage index](schemas/cycle-lineage-index-v1.md).
Set `LEGALFORECAST_CYCLE_LINEAGE_INDEX` to the same absolute local-state file in every worktree, then use `uv run legalforecast acquisition locate-cycle-lineage --cycle-id <cycle-id> --json` as the provider-free handoff/status command.
It reauthenticates the authoritative records on every read, exposes completed and pending human decisions, and rejects ambiguous or superseded heads; the index itself grants no operational or publication authority and can be rebuilt with `register-cycle-lineage`.
For an existing reviewed direct continuation that has no coordinator receipt, use `register-cycle-stage-head` against its completed card and the prior registered root identity; lookup then rehashes every declared output and preserves any registered human-decision cards along that explicit chain.

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
  --credit-cap <approved-cycle-firecrawl-credit-cap> \
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

For a large saturated source, the provider-free priority-tranche command may schedule the most decision-looking leads first without changing source membership.
It uses only committed docket-entry descriptions and valid post-anchor dates, and writes an exact self-hashed deferred frontier.
Selected plus deferred candidates must be a disjoint union of the complete source; deferred means `unscreened_not_excluded`, never a merits or eligibility exclusion.
When a docket contains both the motion and a later disposition, the acquisition-only priority record is selected separately from the earliest-entry reconstruction hint, so the later order, opinion, or R&R can drive rank without changing strict-screen evidence.
Authenticated free-document availability is only a secondary scheduling signal after disposition/date evidence; it is never eligibility, disclosure, completeness, or public-availability proof.
The priority source must be the complete output of `seed-novel-direct-search`, not the raw search or rebind batch.
For a cross-cycle source, first run `rebind-direct-search`, then run `seed-novel-direct-search` against that exact rebind with every prior snapshot and manifest SHA-256 pinned; the reader preserves and verifies the original CourtListener authority, source-rebind digest, and prior-dedupe commitments through both provider-free carriers.

```bash
uv run legalforecast batch-002 materialize-direct-search-priority-tranche \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <complete-saturated-source-batch-id> \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <priority-tranche-001-batch-id> \
  --tranche-size 500 \
  --deferred-frontier-output artifacts/cycle-1/official-acquisition/priority-tranche-001-frontier.json \
  --summary-output artifacts/cycle-1/official-acquisition/priority-tranche-001-summary.json
```

For tranche 2 and later, externally record the predecessor frontier file SHA-256 and supply both predecessor flags.
The command re-authenticates the complete source, ranking policy, exact ranked order, predecessor self-hash, and source partition before writing anything.

```bash
uv run legalforecast batch-002 materialize-direct-search-priority-tranche \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <complete-saturated-source-batch-id> \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <priority-tranche-002-batch-id> \
  --tranche-size 500 \
  --predecessor-frontier artifacts/cycle-1/official-acquisition/priority-tranche-001-frontier.json \
  --expected-predecessor-frontier-sha256 <externally-recorded-file-sha256> \
  --deferred-frontier-output artifacts/cycle-1/official-acquisition/priority-tranche-002-frontier.json \
  --summary-output artifacts/cycle-1/official-acquisition/priority-tranche-002-summary.json
```

This command has no network, provider, purchase, fee-acknowledgment, model-evaluation, freeze, or dispatch path.
Run `observe` and `snapshot` separately for each selected tranche; each tranche snapshot is deliberately marked provisional and must not be treated as a globally saturated source, final cohort authority, or exclusion ledger.
Missing or malformed ranking metadata only lowers scheduling priority; the strict screen remains the sole eligibility and exclusion authority, and ranking metadata is acquisition-only and never packet-visible.
After the terminal tranche reports `deferred_count: 0` and `ranking_frontier_exhausted: true`, pass every externally hash-pinned tranche snapshot, in ordinal order, to `acquisition union-screening-snapshots`.
Even that last isolated tranche reports `global_source_saturated: false`; only the authenticated final union may assert full-source terminal conservation.
The union becomes non-provisional only if predecessor/frontier hashes form a contiguous chain and accepted-plus-excluded terminal rows exactly conserve the committed novel-source candidate-ID set; an incomplete, overlapping, mutated, or mixed chain fails closed.

For the approved Cycle 1 acquisition-shaped convenience cohort, the first frozen priority tranche may instead be promoted after every selected candidate is terminal, even though the remaining parent candidates have not been screened.
This narrow path is for relative model comparison only and does not claim a representative sample or population inference.
The promotion re-authenticates the complete parent source, exact first-tranche frontier, terminal mixed outcomes, strict 2026-06-30 evidence, and a separately reviewed policy proving that selection was acquisition-only, model-invisible, Stage-B-label-free, and outcome-polarity blind.
It preserves every deferred parent candidate in a hash-bound `unscreened_not_excluded` omission inventory; deferred candidates never enter the exclusion ledger.

```bash
uv run legalforecast acquisition promote-terminal-rest-priority-subset \
  --output-root artifacts/cycle-1/official-acquisition/rest-priority-promotion \
  --execute --no-resume \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --parent-source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --parent-source-batch-id <complete-saturated-source-batch-id> \
  --expected-parent-source-batch-digest <externally-recorded-batch-digest> \
  --priority-batch-id <terminal-priority-tranche-001-batch-id> \
  --expected-priority-batch-digest <externally-recorded-priority-batch-digest> \
  --priority-frontier artifacts/cycle-1/official-acquisition/priority-tranche-001-frontier.json \
  --expected-priority-frontier-sha256 <externally-recorded-file-sha256> \
  --source-snapshot artifacts/cycle-1/official-acquisition/priority-tranche-001-snapshot \
  --expected-source-snapshot-manifest-sha256 <externally-recorded-manifest-sha256> \
  --selection-policy artifacts/cycle-1/official-acquisition/rest-priority-selection-policy.json \
  --expected-selection-policy-sha256 <externally-recorded-policy-sha256> \
  --expected-cycle-hash <frozen-cycle-hash> \
  --decision-filed-on-or-after 2026-06-30 \
  --batch-id <promoted-priority-subset-batch-id> \
  --snapshot-id <promoted-priority-subset-snapshot-id> \
  --omission-inventory-output artifacts/cycle-1/official-acquisition/rest-priority-promotion/unscreened-not-excluded.jsonl
```

The first implementation requires `--parent-source-store` and `--cycle-store` to resolve to the same production store, authenticates all source inputs before creating the target batch, emits no raw-artifact substitute, and has no network, provider, PACER, fee-acknowledgment, purchase, model, evaluation, freeze, or dispatch option.
The promoted snapshot carries the distinct `rest_terminal_subset_promotion` commitment, not `direct_search_priority_tranche`; the ordinary incomplete-chain guard remains unchanged.
Union the promoted snapshot with the refreshed, disjoint base snapshot only after both manifest hashes are externally recorded.

Reconstruct and strictly screen the transferred dockets through authenticated CourtListener REST. The durable request ledger enforces the configured minute, hour, and day ceilings; stopping at a ceiling is resumable and does not change candidate membership.

```bash
uv run legalforecast batch-002 observe \
  --cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --batch-id <new-rest-screen-batch-id> \
  --eligibility-anchor 2026-06-30 \
  --live \
  --request-ledger "$PREP_PARENT/courtlistener-request-ledger-base-v1.sqlite3" \
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

### Exact-310 Terminal REST Policy Rebind

The supported target setup is provider-free `rebind-direct-search`, not a hand-built SQLite batch. The exact source belongs to the old screening cycle, so `seed-direct-search` correctly rejects it as cross-cycle. Start from a current-cycle union-store copy or new current-cycle store and transfer the identical saturated 310-docket broad-search source into a fresh target batch while committing both cycle hashes:

```bash
uv run legalforecast batch-002 rebind-direct-search \
  --source-store <saturated-broad-search-store> \
  --source-batch-id cycle1-courtlistener-20260711-to-20260715-broad-hybrid-v2 \
  --cycle-store <current-cycle-union-store> \
  --batch-id <current-cycle-exact310-rebind-batch> \
  --eligibility-anchor 2026-06-30 \
  --page-size 100 \
  --summary-output <current-cycle-exact310-setup-summary.json>
```

The setup summary is externally hash-pinned. Its `legalforecast.direct_search_cycle_rebind_result.v1` identity, zero provider/paid-activity flags, source and target cycle hashes, source batch identity, current source-projection commitment, exact target config, exhausted carrier term, and every candidate's rebind provenance are authenticated by both exact310 passes. The current projection commitment may differ from the historical transfer receipt's candidate-set commitment when the projection schema has been strengthened; the exact310 commands bind both commitments to their distinct roles rather than treating them as interchangeable.

After the old 8410bac REST batch is terminal, writer-free, WAL-clean, and published as a complete saturated snapshot, freeze a provider-free rebind contract. The command authenticates the exact old cycle, batch config, 310-candidate commitment, transfer receipt, snapshot, and every terminal observation against the current target cycle. Existing current-cycle outcomes are preserved; authenticated source exclusions retain their exact reason and evidence with rebind provenance; accepted strict-screen evidence is re-proved under the shared current validator; an old accepted row that cannot be re-proved fails closed.

```bash
uv run legalforecast batch-002 plan-exact310-rest-rebind \
  --source-store <old-8410bac-rest-store> \
  --source-snapshot <old-exact310-complete-snapshot> \
  --expected-source-snapshot-manifest-sha256 <pinned-old-manifest-sha256> \
  --transfer-receipt <old-direct-search-transfer-summary.json> \
  --target-seed-summary <current-cycle-exact310-setup-summary.json> \
  --expected-target-seed-summary-sha256 <pinned-target-setup-summary-sha256> \
  --cycle-store <current-cycle-union-store> \
  --batch-id <current-cycle-exact310-rebind-batch> \
  --expected-target-cycle-hash <current-cycle-hash> \
  --contract-output <exact310-rebind-contract.json>
```

Pin the printed contract SHA-256 externally before execution, then re-authenticate and publish:

```bash
uv run legalforecast batch-002 rebind-exact310-rest-observations \
  --source-store <old-8410bac-rest-store> \
  --source-snapshot <old-exact310-complete-snapshot> \
  --expected-source-snapshot-manifest-sha256 <pinned-old-manifest-sha256> \
  --transfer-receipt <old-direct-search-transfer-summary.json> \
  --target-seed-summary <current-cycle-exact310-setup-summary.json> \
  --expected-target-seed-summary-sha256 <pinned-target-setup-summary-sha256> \
  --cycle-store <current-cycle-union-store> \
  --batch-id <current-cycle-exact310-rebind-batch> \
  --expected-target-cycle-hash <current-cycle-hash> \
  --contract <exact310-rebind-contract.json> \
  --expected-contract-sha256 <externally-pinned-contract-sha256> \
  --snapshot-output-root <current-cycle-snapshots> \
  --snapshot-id <current-cycle-exact310-complete> \
  --run-card-output <exact310-rebind-run-card.json>
```

Neither command exposes network, provider, PACER, RECAP Fetch, fee acknowledgment, purchase, evaluation, freeze, or dispatch flags.

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
  --credit-cap <approved-cycle-firecrawl-credit-cap> \
  --live-firecrawl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/docket-acquisition/raw-docket-html \
  --successes-output artifacts/cycle-1/official-acquisition/docket-acquisition/docket-successes.jsonl \
  --exclusions-output artifacts/cycle-1/official-acquisition/docket-acquisition/docket-fetch-exclusions.jsonl \
  --execute --resume
```

For authenticated source-bound input, `--max-candidates` must exactly equal the selector's committed prefix/subset count. The command verifies the external selector-card digest, the full ranked-file digest, every selected ranked-record digest, the source schema/type commitments, the saturated parent transfer, and the exact selected/omitted reconciliation before any Firecrawl request. Source-bound ranked JSONL without this run card is rejected.

Use only the cycle cap John approved before execution. The seal below does not infer all prior Firecrawl authority from this run's store; the operator must supply the separately receipted total.

If this immutable run actually exhausts its Firecrawl authorization before every selected docket becomes terminal, do not raise its cap and do not start a second run in the same store. Wait for the writer to exit and the WAL to checkpoint, pin the run's exact `cycle_hash`, `config_digest`, and `credit_cap` from its durable summary, then seal it provider-free:

```bash
uv run legalforecast acquisition seal-ranked-firecrawl-run \
  --output-root artifacts/cycle-1/official-acquisition/docket-acquisition-seal \
  --source-cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --run-id batch-002-ranked-dockets-primary \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --ranked-selection-run-card artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-selection-run-card.json \
  --expected-ranked-selection-run-card-sha256 <pinned-ranked-selection-run-card-sha256> \
  --max-candidates 100 \
  --max-pages-per-docket 100 \
  --decision-filed-on-or-after 2026-06-30 \
  --expected-cycle-hash <pinned-source-cycle-hash> \
  --expected-run-config-sha256 <pinned-source-run-config-digest> \
  --expected-credit-cap <pinned-source-credit-cap> \
  --expected-total-prior-authorized-firecrawl-credits <pinned-total-prior-authorized-firecrawl-credits> \
  --authorized-fresh-recovery-credit-cap 0 \
  --execute --no-resume
```

The seal holds the source store's existing exclusive lock in SQLite read-only/query-only mode, rejects a live writer, nonempty WAL, outstanding authorization, nonexhausted budget, source/config/cap drift, malformed target ordinals, contradictory attempts, or changed raw page bytes. It emits normal successes and exclusions only for proven terminal dockets, plus exact terminal and unresolved manifests whose union conserves every selected target. Provider-global, interrupted, missing, in-progress, and retryable pages remain unresolved; they are never converted into candidate exclusions. Pin the raw seal-card plus both partition-manifest SHA-256 values out of band. A fresh cap of `0` is an explicit record that no continuation has been authorized; it does not block provider-free terminal screening.

If `terminal_count` is zero, do not materialize or screen an empty terminal partition; skip directly to the approval-gated unresolved path. If `unresolved_count` is zero, skip the recovery store and union and use the terminal screen as the complete result.

Initialize two distinct stores under the identical frozen cycle policy: one screening-only store for the terminal partition and one recovery store for the unresolved partition. Neither path may alias the exhausted source store. Verify that both emitted identity artifacts report the seal's pinned source cycle hash before continuing:

```bash
uv run legalforecast acquisition init-cycle \
  --output-root artifacts/cycle-1/official-acquisition/terminal \
  --cycle-store artifacts/cycle-1/official-acquisition/terminal/cycle-acquisition.sqlite3 \
  --identity-output artifacts/cycle-1/official-acquisition/terminal/cycle-identity.json \
  --eligibility-anchor 2026-06-30 \
  --execute --no-resume

uv run legalforecast acquisition init-cycle \
  --output-root artifacts/cycle-1/official-acquisition/recovery \
  --cycle-store artifacts/cycle-1/official-acquisition/recovery/cycle-acquisition.sqlite3 \
  --identity-output artifacts/cycle-1/official-acquisition/recovery/cycle-identity.json \
  --eligibility-anchor 2026-06-30 \
  --execute --no-resume
```

Authenticate the exact terminal manifest into the screening-only store. This selector card deliberately cannot authorize Firecrawl: `verify_authenticated_ranked_firecrawl_handoff` rejects its terminal recovery authority, so a terminal docket cannot be charged again:

```bash
uv run legalforecast batch-002 select-case-dev-ranked-subset \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <saturated-o-or-r-source-batch-id> \
  --source-projection artifacts/cycle-1/official-acquisition/case-dev-enrichment/checkpoints/case-dev-recap-source-projection.jsonl \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --failures artifacts/cycle-1/official-acquisition/case-dev-enrichment/enrichment-failures.jsonl \
  --enrichment-run-card artifacts/cycle-1/official-acquisition/case-dev-enrichment/run-cards/enrich-recap-case-dev.json \
  --expected-enrichment-run-card-sha256 <pinned-enrichment-run-card-sha256> \
  --sealed-terminal-manifest artifacts/cycle-1/official-acquisition/docket-acquisition-seal/firecrawl-terminal-partition.jsonl \
  --expected-sealed-terminal-manifest-sha256 <pinned-terminal-manifest-sha256> \
  --recovery-seal-run-card artifacts/cycle-1/official-acquisition/docket-acquisition-seal/run-cards/seal-ranked-firecrawl-run.json \
  --expected-recovery-seal-run-card-sha256 <pinned-seal-run-card-sha256> \
  --recovery-source-cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --cycle-store artifacts/cycle-1/official-acquisition/terminal/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets-terminal \
  --eligibility-anchor 2026-06-30 \
  --run-card-output artifacts/cycle-1/official-acquisition/terminal/terminal-selection-run-card.json
```

Do not continue unresolved acquisition without John's explicit approval of a fresh cap. After approval, rerun the provider-free seal into a new immutable `docket-acquisition-seal-authorized` output root, changing only `--authorized-fresh-recovery-credit-cap` from `0` to `<approved-fresh-recovery-credit-cap>`. The validator requires the externally pinned prior total plus that amount to remain strictly below 50,000. Pin the new seal card and both manifests; never modify or reuse the zero-authority card as acquisition authority.

Authenticate only the exact unresolved manifest from that newly authorized seal into the recovery store. The source and target stores must be different files, and the target cycle hash must equal the seal's source cycle hash:

```bash
uv run legalforecast batch-002 select-case-dev-ranked-subset \
  --source-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --source-batch-id <saturated-o-or-r-source-batch-id> \
  --source-projection artifacts/cycle-1/official-acquisition/case-dev-enrichment/checkpoints/case-dev-recap-source-projection.jsonl \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --failures artifacts/cycle-1/official-acquisition/case-dev-enrichment/enrichment-failures.jsonl \
  --enrichment-run-card artifacts/cycle-1/official-acquisition/case-dev-enrichment/run-cards/enrich-recap-case-dev.json \
  --expected-enrichment-run-card-sha256 <pinned-enrichment-run-card-sha256> \
  --sealed-unresolved-manifest artifacts/cycle-1/official-acquisition/docket-acquisition-seal-authorized/firecrawl-unresolved-partition.jsonl \
  --expected-sealed-unresolved-manifest-sha256 <pinned-unresolved-manifest-sha256> \
  --recovery-seal-run-card artifacts/cycle-1/official-acquisition/docket-acquisition-seal-authorized/run-cards/seal-ranked-firecrawl-run.json \
  --expected-recovery-seal-run-card-sha256 <pinned-seal-run-card-sha256> \
  --recovery-source-cycle-store artifacts/cycle-1/official-acquisition/cycle-acquisition.sqlite3 \
  --cycle-store artifacts/cycle-1/official-acquisition/recovery/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets-unresolved \
  --eligibility-anchor 2026-06-30 \
  --run-card-output artifacts/cycle-1/official-acquisition/recovery/unresolved-selection-run-card.json
```

The unresolved selector replays the original ranked selection and source ledger under the source lock, then transfers only the exact unresolved docket IDs in canonical rank order. Its fresh-store batch config and run card bind both external hashes, the source target/attempt commitments, the exhausted cap, the separately authorized recovery cap, and `terminal_dockets_reauthorized: 0`. Passing the terminal manifest, changing either partition, reusing the exhausted source store as the target, or attempting to select a terminal docket fails before any target-batch write. Pin the new unresolved selector card's raw SHA-256 out of band, then acquire exactly its committed count under the cap sealed into that card:

```bash
uv run legalforecast acquisition acquire-ranked-firecrawl-dockets \
  --output-root artifacts/cycle-1/official-acquisition/recovery/docket-acquisition \
  --cycle-store artifacts/cycle-1/official-acquisition/recovery/cycle-acquisition.sqlite3 \
  --parent-batch-id batch-002-ranked-dockets-unresolved \
  --selected-batch-id batch-002-ranked-dockets-unresolved-acquired \
  --run-id batch-002-ranked-dockets-recovery \
  --ranked artifacts/cycle-1/official-acquisition/case-dev-enrichment/ranked-dockets.jsonl \
  --ranked-selection-run-card artifacts/cycle-1/official-acquisition/recovery/unresolved-selection-run-card.json \
  --expected-ranked-selection-run-card-sha256 <pinned-unresolved-selection-run-card-sha256> \
  --max-candidates <sealed-unresolved-count> \
  --max-pages-per-docket 100 \
  --workers 10 \
  --decision-filed-on-or-after 2026-06-30 \
  --credit-cap <approved-fresh-recovery-credit-cap> \
  --live-firecrawl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/raw-docket-html \
  --successes-output artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/docket-successes.jsonl \
  --exclusions-output artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/docket-fetch-exclusions.jsonl \
  --execute --resume
```

The acquisition verifier requires `--credit-cap` to equal the sealed fresh-recovery authorization and `--max-candidates` to equal the complete unresolved selection. The sum of all prior and recovery Firecrawl authority must remain strictly below the cycle ceiling.

Strict-screen the terminal projection from the seal and the separately acquired unresolved projection in their respective stores:

```bash
uv run legalforecast acquisition screen-firecrawl-dockets \
  --output-root artifacts/cycle-1/official-acquisition/terminal/screening \
  --cycle-store artifacts/cycle-1/official-acquisition/terminal/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets-terminal \
  --successes artifacts/cycle-1/official-acquisition/docket-acquisition-seal/firecrawl-docket-successes.jsonl \
  --fetch-exclusions artifacts/cycle-1/official-acquisition/docket-acquisition-seal/firecrawl-docket-exclusions.jsonl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/docket-acquisition-seal/raw-docket-html \
  --decision-filed-on-or-after 2026-06-30 \
  --snapshot-root artifacts/cycle-1/official-acquisition/terminal/snapshots \
  --snapshot-id batch-002-ranked-dockets-terminal-screened \
  --execute --no-resume

uv run legalforecast acquisition screen-firecrawl-dockets \
  --output-root artifacts/cycle-1/official-acquisition/recovery/screening \
  --cycle-store artifacts/cycle-1/official-acquisition/recovery/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets-unresolved-acquired \
  --successes artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/docket-successes.jsonl \
  --fetch-exclusions artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/docket-fetch-exclusions.jsonl \
  --raw-html-dir artifacts/cycle-1/official-acquisition/recovery/docket-acquisition/raw-docket-html \
  --decision-filed-on-or-after 2026-06-30 \
  --snapshot-root artifacts/cycle-1/official-acquisition/recovery/snapshots \
  --snapshot-id batch-002-ranked-dockets-unresolved-screened \
  --execute --no-resume
```

Require both screening snapshots to report complete reconciliation, `complete: true`, and `saturated: true`. Pin each raw `manifest.json` SHA-256 out of band, then publish the only complete post-recovery acquisition authority as their manifest-authenticated same-cycle union:

```bash
uv run legalforecast acquisition union-screening-snapshots \
  --output-root artifacts/cycle-1/official-acquisition/recovery/union \
  --cycle-store artifacts/cycle-1/official-acquisition/recovery/cycle-acquisition.sqlite3 \
  --batch-id batch-002-ranked-dockets-complete-union \
  --expected-cycle-hash <pinned-source-cycle-hash> \
  --source-snapshot artifacts/cycle-1/official-acquisition/terminal/snapshots/batch-002-ranked-dockets-terminal-screened \
  --expected-source-snapshot-manifest-sha256 <pinned-terminal-snapshot-manifest-sha256> \
  --source-snapshot artifacts/cycle-1/official-acquisition/recovery/snapshots/batch-002-ranked-dockets-unresolved-screened \
  --expected-source-snapshot-manifest-sha256 <pinned-unresolved-snapshot-manifest-sha256> \
  --expected-terminal-correction-candidate-id <exact-conflicting-candidate-id> \
  --expected-terminal-correction-source-manifest-sha256 <pinned-authoritative-source-manifest-sha256> \
  --snapshot-root artifacts/cycle-1/official-acquisition/snapshots \
  --snapshot-id batch-002-ranked-dockets-complete \
  --execute --no-resume
```

Do not rank or prepare from either partition snapshot. Only the verified union is the complete recovery snapshot.

The union compares duplicate candidates by terminal state, reason code, and the complete evidence object. Identical duplicates need no correction. Every non-identical conflict requires one paired `--expected-terminal-correction-candidate-id` and `--expected-terminal-correction-source-manifest-sha256`; the candidate pins must exactly equal the detected conflict set, and the source hash must be one of the already pinned source manifests that actually owns that candidate. Source order, observation time, and retrieval time confer no authority.

`union-terminal-observations.jsonl` archives every source observation for each correction, including its source manifest, full evidence, terminal hash, source-local raw commitments, and canonical marker. The same rows are embedded in the authenticated union stage commitment so the correction proof survives source cleanup. If any accepted or newly-free proof exists, it must be the unique terminal commitment of that class and must be chosen; an exclusion cannot suppress it. The packet-facing raw row must come only from the authoritative active source, and every identical active duplicate must bind the same raw commitment. Multiple non-identical active proofs, missing active raw, source-raw drift, extra or missing correction pins, or an existing store state absent from the authenticated correction archive stop the union.

All manifest-authenticated raw versions remain archived under `<candidate-id>/<sha256>.html` and in `union-raw-observations.jsonl`. For an excluded canonical candidate, the earliest unambiguous UTC capture remains its packet projection. `union-raw-artifacts.jsonl` contains exactly one authenticated canonical row per candidate and is the `--raw-html-dir` union-root projection consumed downstream. Ambiguous or invalid retrieval timestamps, raw content drift, or candidate/path ownership mismatch fail closed. Do not delete an older observation or hand-select one to force a merge.

If an already terminal union was screened under the corrected restricted-material implementation but its cycle store was initialized with the immediately preceding restricted-material source hash, use the one-purpose provider-free rebind below instead of re-fetching dockets or hand-editing the cycle identity:

```bash
uv run legalforecast acquisition rebind-screening-union-policy \
  --output-root artifacts/cycle-1/official-acquisition/current-policy-rebind \
  --source-snapshot <complete-union-snapshot> \
  --expected-source-snapshot-manifest-sha256 <pinned-union-manifest-sha256> \
  --source-union-run-card <completed-union-run-card> \
  --expected-source-union-run-card-sha256 <pinned-union-run-card-sha256> \
  --source-cycle-store <source-cycle-store> \
  --expected-source-cycle-hash <pinned-source-cycle-hash> \
  --cycle-store <current-target-cycle-store> \
  --expected-target-cycle-hash <pinned-target-cycle-hash> \
  --batch-id <new-exact-rebind-batch-id> \
  --snapshot-root artifacts/cycle-1/official-acquisition/current-policy-rebind/snapshots \
  --snapshot-id <new-current-policy-snapshot-id> \
  --execute --no-resume
```

This compatibility route permits only the pinned `restricted_material_public_hearing_false_positive_fix_v1` hash transition. It authenticates the complete source union and run card, validates every accepted strict-screen record and post-anchor disposition, preserves every exclusion and original evidence namespace, preserves each source terminal observation timestamp, owns every source raw observation under the target root, and proves exact candidate conservation. The snapshot commits the closed rebind implementation source set as well as the inherited mixed-source union lineage, so later union loading rejects implementation drift. Source inputs, the target cycle store, the snapshot root, the raw root, and the immutable run card are checked for symlink traversal and unsafe overlap before target mutation. Any other policy drift, invalid accepted evidence, raw mismatch, extra output file, unsafe path, or nonterminal source fails closed. The command is restart-safe and has no provider, PACER, purchase, evaluation, freeze, or dispatch path.

If the primary Firecrawl acquisition completed without exhausting its immutable cap, skip the recovery sequence and strict-screen its committed CourtListener docket bytes directly:

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

Do not rank or prepare from partial outputs. Require the screening summary and snapshot manifest to report complete reconciliation, `complete: true`, and `saturated: true`, then externally record both the manifest file's SHA-256 and its exact `cycle_hash`. `prepare-target-cohort` and its `plan-public-downloads` substage require that manifest-file pin and reject a partial, changed, repinned, or wrong-cycle snapshot before carrying any viable row through authoritative CourtListener public-document and paid-gap resolution.

If the same cycle gains reviewed candidates after a completed PACER-gap bridge, first publish a complete saturated `union-screening-snapshots` output. Reuse old terminal checkpoints only through `rebase-pacer-gap-checkpoints` with both externally pinned manifest hashes and one `--expected-added-candidate-id` per exact addition. A pure append requires the old snapshot in the union ancestry. If a complete current-policy replay invalidates a prior acceptance, also pass one `--expected-invalidated-candidate-id` per exact invalidation; that explicitly pinned path may replace the ancestry requirement but must prove every other prior terminal evidence record and raw commitment unchanged. Both paths require exact screened projections, unchanged retained route semantics, and a terminal checkpoint for every prior paid gap. The receipt's `replay_required_candidate_ids` must equal the new paid-gap additions plus only invalidated candidates that remain currently routed; invalidated candidates removed from current routes must be recorded separately and not replayed. Otherwise stop. The rebase is provider-free and preserves byte-identical prior checkpoints when their index, input hash, and payload did not change.

The Cycle 1 launch requirement is **at least 100** clean cases. Plan and preserve the full untruncated frontier so acquisition can continue toward **150** as a nonblocking stretch/reserve target, but 150 is not a prerequisite for the first official run. Project the cheapest cleared 100 cases from the authenticated full pool, and never raise or relax the frozen budget cap or any eligibility, provenance, disclosure, leakage, or labeling gate to make either count fit.

`legalforecast acquisition prepare-target-100` remains a compatibility wrapper for previously frozen exact-100 artifacts. The canonical path is still `prepare-target-cohort --target-case-count 100`, which preserves the complete frontier rather than truncating discovery to the launch denominator.

### Step 4: Prepare The Resolved Pool And Provisional Budget

Run the public-first preparation chain from that immutable snapshot. This command plans public downloads against the 100-case launch requirement, downloads free documents, resolves remaining gap metadata through authenticated noncharging CourtListener REST, applies the core-document filter, and emits disclosure-review requests plus the full untruncated frontier. It never purchases a document.

```bash
SNAPSHOT=artifacts/cycle-1/official-acquisition/snapshots/batch-002-ranked-dockets-complete
# Set this to the digest recorded out of band when the snapshot was published.
# Do not derive the admission pin from the mutable snapshot being admitted.
SNAPSHOT_MANIFEST_SHA256='REPLACE_WITH_EXTERNALLY_RECORDED_MANIFEST_SHA256'
test "$(sha256sum "$SNAPSHOT/manifest.json" | cut -d' ' -f1)" = "$SNAPSHOT_MANIFEST_SHA256"

uv run legalforecast acquisition prepare-target-cohort \
  --output-root artifacts/cycle-1/official-acquisition/target-100-frontier \
  --snapshot "$SNAPSHOT" \
  --expected-snapshot-manifest-sha256 "$SNAPSHOT_MANIFEST_SHA256" \
  --expected-cycle-hash <snapshot-cycle-hash> \
  --use-embedded-entries \
  --live-public-download \
  --live-courtlistener \
  --request-ledger "$PREP_PARENT/courtlistener-request-ledger-base-v1.sqlite3" \
  --cost-per-document-usd 3.05 \
  --max-projected-budget-usd 567.30 \
  --max-missing-core-documents-per-case 24 \
  --target-case-count 100 \
  --execute --resume
```

The successful preparation summary commits the snapshot, immutable semantic configuration, stage inputs and outputs, provisional selected candidate IDs, 100-case launch requirement, and full cost frontier. Cycle 1 freezes the provisional cap at `$567.30`; every later projection must repeat that exact value rather than falling back to the CLI default. The `06-clearance-inputs/` directory contains one restriction-evidence row and one disclosure-review request for every downloaded free document. The summary deliberately names `clear-disclosures`, not purchase, as the next stage.

An `is_sealed: null` provider field is unknown metadata, not affirmative evidence that a filing is sealed. The pipeline may continue trying public routes and later classify the document as a recoverable missing/paid gap. It must not mark the document free unless public availability is affirmatively proven, and packet admission still fails closed until disclosure clearance is complete.

### Step 5: Clear Every Free Document And Freeze The Exact Cohort

Complete the provenance-first disclosure flow over the full free manifest before projecting the exact cohort.
The contract and current artifact schemas are documented in [Provenance clearance v2](schemas/provenance-clearance-v2.md).
Do not hand-edit a preparation, review, signature, receipt, clearance, or run-card artifact.

This sequence is local, provider-free, and noncharging.
Do not run a purchase, parser or labeling-model call, model evaluation, official freeze, or dispatch as part of this gate.

Set paths for the exact completed preparation outputs, a normal acquisition review root, and a separate controlled private store.

```zsh
preparation_root=artifacts/cycle-1/official-acquisition-main-e0d7177-20260716/target-150-plus-five-current-policy-v1/15-final-provider-free-union-main-4d3ba85-v1/33-10k-continuation-main-5781216-v1/21-target100-retarget-main-182bd3d-v1
review_requests="$preparation_root/06-clearance-inputs/disclosure-review-requests.jsonl"
download_manifest="$preparation_root/03c-merged-downloads/document-downloads-merged.jsonl"
document_root="$preparation_root/documents/free"
restriction_evidence="$preparation_root/06-clearance-inputs/restriction-evidence.jsonl"
review_root="$preparation_root/07-free-disclosure-review"
clearance_root="$preparation_root/08-free-clearance"
launch_root="$preparation_root/09-launch-100"
snapshot_manifest="artifacts/cycle-1/official-acquisition-main-e0d7177-20260716/target-150-plus-five-current-policy-v1/15-final-provider-free-union-main-4d3ba85-v1/33-10k-continuation-main-5781216-v1/15-final153-union-main-911371f-v1/snapshots/cycle1-final153-current-policy-union-main-911371f-v1/manifest.json"
snapshot_manifest_sha256="487bec5f70289e212554a9af59fc195c9d6244060550d346612cb589405b138c"
private_review_root=<absolute-controlled-private-review-root>
cohort_policy=docs/cohort-policy-cycle-1-target-100-2026-07-25.json
```

The current generated policy binds cycle hash `35f70123bfc966512d61119746ba09716332a181c074f131d553b56b610641cb`, the `2026-06-30` eligibility anchor, the saturated source window through `2026-07-23`, exactly 100 launch cases, and the unchanged `$567.30` cap.
Its internal policy identity is `76c98406536e38fede7a1a72b60af731088fae04888b9662b1d3ed37538a7207`.
The value-by-value human-authority and source derivation record is [Cycle 1 exact-100 cohort-policy provenance](cohort-policy-cycle-1-target-100-2026-07-25-provenance.md).
First derive the exact provenance routing plan, exception-only worksheet, and private exact-byte inspection map.
Only exact bytes with descriptor-stable manifest commitments, complete page-level text coverage, affirmative public CourtListener provenance, and a consistent model-visibility/target-outcome separation can auto-clear.
The v2 routing plan records the parsed page count and disjoint text-scanned, OCR-scanned, and unscanned page sets from the exact manifest bytes.
The current `pypdf_page_text_v2` scanner does not perform OCR, requires the reserved OCR-scanned set to be empty, and routes every page without nonempty extracted text to review as unscanned.
The redundant legacy extractor is retired for new v2 scans; immutable v1 scans replay through their historical scanner, whose content-stream/page-count mismatch remains diagnostic-only.
Incomplete coverage, `medical`, SSN, mixed, or any other substantive or unknown marker still routes to John, while positive restriction evidence and visibility contradictions remain impossible to clear.
The private root must not equal, contain, or be contained by the acquisition output root.
The command writes `private-document-inspection-map.jsonl` only under that private root and deliberately excludes its path and bytes from downstream run-card commitments.
This no-FIDO flow trusts the integrity of that controlled private root and its owning host UID; reviewer names and timestamps are audit assertions, not cryptographic identity or trusted-time proof, and a suspected same-UID compromise requires discarding and repeating the clearance on a trusted host.

```zsh
uv run legalforecast acquisition plan-disclosure-provenance \
  --output-root "$review_root" \
  --review-requests "$review_requests" \
  --download-manifest "$download_manifest" \
  --case-relevance "$preparation_root/03-gap-bridge/case-relevance.jsonl" \
  --document-root "$document_root" \
  --restriction-evidence "$restriction_evidence" \
  --routing-plan-output "$review_root/disclosure-provenance-plan.json" \
  --exception-worksheet-output "$review_root/disclosure-exception-worksheet.json" \
  --controlled-private-store-root "$private_review_root" \
  --execute --resume
```

Next, use the private interactive recorder for the exception worksheet only; do not hand-author the decision JSONL.
For every document it displays the exact private inspection path, SHA-256, restriction status, and marker categories, then requires the human to type the full inspected hash and an explicit decision.
It finishes with an exact batch summary and typed batch confirmation.
Marker-only exceptions may be cleared by John; positive restrictions and visibility contradictions cannot.

```zsh
decisions="$private_review_root/disclosure-review-decisions.jsonl"

uv run legalforecast acquisition record-disclosure-review-decisions \
  --output-root "$private_review_root/recorder-metadata" \
  --review-worksheet "$review_root/disclosure-exception-worksheet.json" \
  --private-inspection-map "$private_review_root/private-document-inspection-map.jsonl" \
  --reviewer-id "John Hughes" \
  --controlled-private-store-root "$private_review_root" \
  --decisions-output "$decisions" \
  --execute --resume
```

The recorder checkpoints each document before continuing and derives the final decisions only from the reloaded checkpoint bytes.
If the process is interrupted or reports a failed stage, correct the underlying input or filesystem problem and rerun the identical command with `--resume`; do not edit the checkpoint, decision, run-card, or log artifacts.
A valid failure-history prefix and a partially published terminal run-card/log pair are recovered automatically, while mismatched metadata, checkpoint trees, reviewer identity, timestamps, inspection-map bytes, or decision bytes fail closed.

Finally, run clearance over the same exact inputs and current document bytes.
The command recomputes the plan and worksheet, reconstructs decisions from the recorder's committed checkpoints, verifies the frozen cohort policy, and fails closed on any drift or incomplete coverage:

```zsh
uv run legalforecast acquisition clear-provenance-disclosures \
  --output-root "$clearance_root" \
  --review-requests "$review_requests" \
  --download-manifest "$download_manifest" \
  --case-relevance "$preparation_root/03-gap-bridge/case-relevance.jsonl" \
  --document-root "$document_root" \
  --restriction-evidence "$restriction_evidence" \
  --routing-plan "$review_root/disclosure-provenance-plan.json" \
  --exception-worksheet "$review_root/disclosure-exception-worksheet.json" \
  --exception-decisions "$decisions" \
  --exception-review-run-card "$private_review_root/recorder-metadata/run-cards/record-disclosure-review-decisions.json" \
  --cohort-policy "$cohort_policy" \
  --execute --resume
```

The producer stages default to deterministic resume, but the runbook spells out `--resume` for audit clarity.
An identical retry must reuse matching bytes; changed inputs or outputs fail closed rather than overwriting the signed lineage.
Use `--no-resume` only when an exclusive first publication is intended, never to replace an already frozen artifact.

Clearance success is necessary but does not by itself authorize a downstream command.
Before projection, recovery, parse, extension, packet planning, or finalization, require that command's current verifier to consume the completed clearance run card and independently replay the provenance plan, checkpoint-derived exceptions, cohort-policy pin, exact document tree, and clearance projection.
If the live downstream contract omits that lineage, stop here and fix the gate; do not pass loose clearance files as a substitute.

Only after clearance succeeds may the supported 100-case launch cohort be projected from the 150-case preparation. This recomputes the cheapest complete frontier after quarantines and writes selection, relevance, restriction, manifest, clearance, budget, and exclusion artifacts containing exactly the chosen cases. The first run has an exact-100 target; continued acquisition toward 150 is a nonblocking reserve and does not change that frozen denominator.

```bash
config_snapshot_manifest="$(
  jq -er '.snapshot + "/manifest.json"' \
    "$preparation_root/target-cohort-config.json"
)"
case "$config_snapshot_manifest" in
  "$snapshot_manifest"|*/"$snapshot_manifest") ;;
  *) echo "preparation config does not pin the expected snapshot manifest" >&2; exit 1 ;;
esac
test "$(jq -er '.snapshot_manifest_sha256 | sub("^sha256:"; "")' "$preparation_root/target-cohort-config.json")" = "$snapshot_manifest_sha256"
test "$(sha256sum "$snapshot_manifest" | cut -d' ' -f1)" = "$snapshot_manifest_sha256"

uv run legalforecast acquisition project-target-cohort \
  --output-root "$launch_root" \
  --selection "$preparation_root/03-gap-bridge/public-packet-selection-reconciled.jsonl" \
  --case-relevance "$preparation_root/03-gap-bridge/case-relevance.jsonl" \
  --download-manifest "$download_manifest" \
  --disclosure-clearance "$clearance_root/disclosure-clearance.jsonl" \
  --clearance-run-card "$clearance_root/run-cards/clear-disclosures.json" \
  --restriction-evidence "$restriction_evidence" \
  --preparation-summary "$preparation_root/target-cohort-preparation-summary.json" \
  --preparation-config "$preparation_root/target-cohort-config.json" \
  --snapshot-manifest "$snapshot_manifest" \
  --target-case-count 100 \
  --cost-per-document-usd 3.05 \
  --max-projected-budget-usd 567.30 \
  --max-missing-core-documents-per-case 24 \
  --execute --resume
```

If fewer than 100 post-clearance cases fit the unchanged cap, acquire more candidates rather than restoring a quarantined case or weakening a gate. The exact-cohort summary binds every source and output hash and reconciles every unselected resolved-pool candidate into `target-cohort-exclusions.jsonl`.

### Step 6: Generate Allowlist, Initialize Ledger, Then Purchase

Paid acquisition remains a separate, operator-visible stage. First freeze the cohort and purchase-policy artifacts required by the CLI. Unknown-status RECAP documents additionally require one immutable attempt policy derived from the exact executable plan and selection; it grants only bounded spend authority and never parser or packet eligibility:

```bash
purchase_policy=<verified-purchase-policy.json>
purchase_ledger=<absolute-canonical-purchase-ledger-path>
controlled_private_root=<absolute-controlled-private-approval-root>
purchase_ledger_initialization_receipt="$preparation_root/purchase-ledger-initialization.json"
attempt_policy="$preparation_root/recap-fetch-attempt-policy-v1.json"
broker_policy="$preparation_root/courtlistener-recap-fetch-policy-v1.json"

uv run legalforecast acquisition generate-recap-fetch-attempt-policy \
  --purchase-policy "$purchase_policy" \
  --cohort-policy "$cohort_policy" \
  --budget-plan "$launch_root/missing-core-budget-plan.json" \
  --selection "$launch_root/target-cohort-selection.jsonl" \
  --controlled-private-root "$controlled_private_root" \
  --output "$attempt_policy"
```

Generate the signed RECAP Fetch broker allowlist from those exact post-clearance outputs and the attempt authority:

```bash
uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy "$purchase_policy" \
  --cohort-policy "$cohort_policy" \
  --budget-plan "$launch_root/missing-core-budget-plan.json" \
  --selection "$launch_root/target-cohort-selection.jsonl" \
  --attempt-policy "$attempt_policy" \
  --controlled-private-root "$controlled_private_root" \
  --output "$broker_policy"
```

Inspect the projected total, allowlisted numeric RECAP document IDs, and remaining budget.
Generation is provider-free and does not deploy or activate the policy.
Before invoking the only fee-bearing happy path, deploy and activate those exact policy bytes through the protected secure-gate RECAP Fetch broker control plane and independently verify the active cycle, purchase-policy digest, and generated policy digest.
Do not use a broad-frontier allowlist for an approved-v2 purchase, and do not treat local generation as deployment evidence.

Ledger initialization is a mandatory, non-provider step. The absolute ledger path below must exactly match `canonical_ledger_path` in the verified purchase policy. This command must succeed and publish its authenticated initialization receipt before any purchase command runs:

```bash
uv run legalforecast acquisition init-purchase-ledger \
  --output-root "$preparation_root" \
  --purchase-policy "$purchase_policy" \
  --cohort-policy "$cohort_policy" \
  --purchase-ledger "$purchase_ledger" \
  --controlled-private-root "$controlled_private_root" \
  --initialization-receipt-output "$purchase_ledger_initialization_receipt" \
  --execute --resume
```

The receipt and immutable ledger singleton share a random initialization identity, so runtime opening rejects a replaced or independently re-initialized ledger even when its policy is identical. This identity survives legitimate ledger mutations. It does not detect restoration of a stale post-initialization snapshot from the same ledger lineage; operators must therefore preserve and restore the canonical ledger and its SQLite state as one controlled artifact and reconcile external purchase records before resuming after a restore.

The allowlist accepts explicit-public proof or the exact current CourtListener REST paid-gap evidence contract.
Case.dev may support noncharging search and docket enrichment, but its legacy paid-unknown evidence is never purchase authority.

The broker client may run only through `/agents/sandbox/legalforecastbench/recap-fetch-broker-client`.
Before the first or any resumed purchase, require the immutable successful broker activation and routing receipts, then perform the masked exact-inventory and closed-writer checks from [the acquisition systemd launcher](acquisition-systemd-launcher.md).
The view must contain exactly `RECAP_FETCH_BROKER_URL`, `RECAP_FETCH_BROKER_MACHINE_ID`, `RECAP_FETCH_BROKER_PRIVATE_KEY_JWK`, `RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON`, and `RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256` as ordinary post-activation values.
It must not use dependent references or folder imports, and it must not expose `PACER_USERNAME`, `PACER_PASSWORD`, `COURTLISTENER_API_TOKEN`, an acquisition/model credential, or any other name.
Run the launcher's name-only sentinel and preserve its value-free output with the run evidence; a missing, empty, extra, pre-activation, imported, or referenced setting blocks `purchase-missing-recap-fetch`.

```bash
broker_launch_receipt="$preparation_root/recap-fetch-broker-client-launch.json"
broker_unit_status="$preparation_root/recap-fetch-broker-client-systemd-status.txt"
broker_unit="lfb-recap-fetch-purchase-$(date +%s)-$$"
broker_systemd_run_status=0
systemd-run --user --wait \
  --unit="$broker_unit" \
  --property=Type=exec \
  --working-directory="$PWD" \
  /usr/bin/env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  uv run legalforecast-acquisition-systemd-run \
  --sandbox-path /agents/sandbox/legalforecastbench/recap-fetch-broker-client \
  --receipt-output "$broker_launch_receipt" \
  -- uv run legalforecast acquisition purchase-missing-recap-fetch \
  --output-root "$preparation_root" \
  --budget-plan "$launch_root/missing-core-budget-plan.json" \
  --selection "$launch_root/target-cohort-selection.jsonl" \
  --purchase-policy "$purchase_policy" \
  --cohort-policy "$cohort_policy" \
  --purchase-ledger "$purchase_ledger" \
  --controlled-private-root "$controlled_private_root" \
  --purchase-ledger-initialization-receipt "$purchase_ledger_initialization_receipt" \
  --attempt-policy "$attempt_policy" \
  --broker-policy "$broker_policy" \
  --request-ledger "$PREP_PARENT/courtlistener-request-ledger-base-v1.sqlite3" \
  --live-purchase --acknowledge-pacer-fees \
  --execute --resume || broker_systemd_run_status=$?

broker_result_show_status=0
broker_result="$(
  systemctl --user show "$broker_unit" --property=Result --value
)" || broker_result_show_status=$?
broker_exec_show_status=0
broker_exec_main_status="$(
  systemctl --user show "$broker_unit" --property=ExecMainStatus --value
)" || broker_exec_show_status=$?
{
  printf 'Result=%s\n' "$broker_result"
  printf 'ExecMainStatus=%s\n' "$broker_exec_main_status"
} > "$broker_unit_status"
broker_stop_status=0
systemctl --user stop "$broker_unit" >/dev/null 2>&1 || broker_stop_status=$?
broker_reset_status=0
systemctl --user reset-failed "$broker_unit" >/dev/null 2>&1 \
  || broker_reset_status=$?
broker_load_state_show_status=0
broker_load_state="$(
  systemctl --user show "$broker_unit" --property=LoadState --value
)" || broker_load_state_show_status=$?
{
  printf 'CleanupStopStatus=%s\n' "$broker_stop_status"
  printf 'CleanupResetStatus=%s\n' "$broker_reset_status"
  printf 'PostCleanupLoadState=%s\n' "$broker_load_state"
} >> "$broker_unit_status"

[[ "$broker_systemd_run_status" -eq 0 \
  && "$broker_result_show_status" -eq 0 \
  && "$broker_exec_show_status" -eq 0 \
  && "$broker_load_state_show_status" -eq 0 \
  && "$broker_load_state" == not-found \
  && "$broker_result" == success \
  && "$broker_exec_main_status" -eq 0 ]] || exit 1
```

The in-unit `/usr/bin/env -i` boundary prevents variables retained by the user service manager from reaching the launcher or its children; do not replace it with a separate caller-side check.
The unit deliberately omits `--collect`: preserve and require the captured systemd `Result=success` and `ExecMainStatus=0` evidence before stopping and resetting the unit.
The cleanup statuses are diagnostic because systemd may automatically unload a successful inactive transient unit after its properties are read; a nonzero cleanup status is acceptable only when `systemctl show` already captured the required terminal evidence and the post-cleanup `LoadState=not-found` gate proves the unit is no longer loaded.
Then verify the launch receipt has `child_receipt_observed=true`, `sandbox_exit_status=0`, and `effective_exit_status=0` before accepting the purchase command's own completed run card.
Never substitute a Case.dev live purchase, a Case.dev fee-bearing docket refresh, or an implicit purchase inside preparation. The RECAP Fetch purchase stage may dispatch only IDs present in the generated broker policy and remains bounded by the verified purchase policy and broker-side budget controls.

The purchase result is not parser- or packet-eligible. Recover every purchased unknown-status document through a fresh authenticated CourtListener detail check. This noncharging stage writes a URL-free quarantine manifest, fresh restriction evidence, the exact disclosure-review request queue, a terminal-unavailable operation manifest, and a committed document tree. It partitions the complete attempt authority: recoverable operations receive fresh public-detail and PDF requests, while only canonical cap-counted queue failures with statuses 3, 6, or 7 enter the terminal manifest without a provider request or paid redispatch. Any other failed, ambiguous, malformed, or unbound state stops the run. Do not hand-author the review requests, copy the PDFs into another recovery root, or reconstruct this stage as a one-off command.

The canonical exact-100 initial-recovery path is the checked-in `manifests/cycle-1-target-100.exact100-initial-recovery.template.json`. Render `INITIAL_APPROVED_ROOT` as the exact cohort root committed by the purchase policy and attempt authority; for the current v4 purchase this is `05-target-cohort-v4`, not the later `13-exact100-successor-*` projection. Recovery must conserve the complete approved attempt authority, while final-successor filtering happens only during authenticated consolidation. Render the remaining variables against the purchase authority, private approval root, and request ledger. The first invocation below is a provider-free status preflight; the second may execute only the provider-free initializer and must stop at `network_boundary_not_authorized`; the final invocation authorizes exactly the noncharging CourtListener recovery boundary. The partial template ends there and contains no disclosure, parser, labeling, purchase, evaluation, freeze, or dispatch stage:

```bash
repo_root="$(pwd -P)"
preparation_root=<absolute-preparation-artifact-root>
initial_approved_root=<absolute-purchase-approved-target-cohort-root>
purchase_authority_root=<absolute-authenticated-purchase-authority-root>
purchase_private_root=<absolute-controlled-private-purchase-approval-root>
source_root=<absolute-source-root-containing-courtlistener-request-ledger>
recovery_cycle_root=<absolute-exact100-initial-recovery-cycle-root>
quarantine_recovery_root="$preparation_root/purchased-quarantine-recovery"
recovery_config="$recovery_cycle_root/acquisition-cycle.json"
recovery_state_root="$recovery_cycle_root/orchestrator"

mkdir -p "$recovery_cycle_root"

uv run legalforecast acquisition render-cycle-config \
  --template "$repo_root/manifests/cycle-1-target-100.exact100-initial-recovery.template.json" \
  --variable "CYCLE_ROOT=$recovery_cycle_root" \
  --variable "INITIAL_APPROVED_ROOT=$initial_approved_root" \
  --variable "PURCHASE_AUTHORITY_ROOT=$purchase_authority_root" \
  --variable "PURCHASE_PRIVATE_ROOT=$purchase_private_root" \
  --variable "RECOVERY_ROOT=$quarantine_recovery_root" \
  --variable "REPO_ROOT=$repo_root" \
  --variable "SOURCE_ROOT=$source_root" \
  --output "$recovery_config"

uv run legalforecast acquisition run-cycle \
  --config "$recovery_config" \
  --state-root "$recovery_state_root" \
  --json

uv run legalforecast acquisition run-cycle \
  --config "$recovery_config" \
  --state-root "$recovery_state_root" \
  --execute --json

uv run legalforecast acquisition run-cycle \
  --config "$recovery_config" \
  --state-root "$recovery_state_root" \
  --execute --allow-network --json
```

Do not add `--allow-paid` to this cycle. The rendered recovery stage binds the exact target projection run card, purchase policy, cohort policy, budget plan, canonical purchase ledger, private approval root, ledger-initialization receipt, attempt policy, request ledger, and terminal-unavailable output. Review the rendered config and both provider-free status receipts before authorizing the network invocation.

Run the same provenance-first disclosure procedure specified in Step 5 over these generated purchased-document inputs.
Purchased bytes do not auto-clear merely because a purchase succeeded: the planner reopens and hashes every recovered document, commits the complete purchased case-relevance view and fresh restriction evidence, and routes every non-affirmative or marked row to John.
There is no signing-key, bundle, or sealed-receipt readiness dependency.
Start from the exact recovery outputs and a complete case-relevance artifact for the purchased documents:

```zsh
purchased_review_requests="$quarantine_recovery_root/disclosure-review-requests.jsonl"
purchased_download_manifest="$quarantine_recovery_root/recap-fetch-quarantine-downloads.jsonl"
purchased_document_root="$quarantine_recovery_root/documents/recap-fetch-quarantine"
purchased_restriction_evidence="$quarantine_recovery_root/post-recovery-restriction-evidence.jsonl"
purchased_review_root="$preparation_root/purchased-disclosure-review"
purchased_clearance_root="$preparation_root/purchased-clearance"
purchased_private_review_root=<absolute-controlled-private-review-root-for-purchased-documents>
purchased_case_relevance="$quarantine_recovery_root/purchased-case-relevance.jsonl"

uv run legalforecast acquisition plan-disclosure-provenance \
  --output-root "$purchased_review_root" \
  --review-requests "$purchased_review_requests" \
  --download-manifest "$purchased_download_manifest" \
  --case-relevance "$purchased_case_relevance" \
  --document-root "$purchased_document_root" \
  --restriction-evidence "$purchased_restriction_evidence" \
  --routing-plan-output "$purchased_review_root/disclosure-provenance-plan.json" \
  --exception-worksheet-output "$purchased_review_root/disclosure-exception-worksheet.json" \
  --controlled-private-store-root "$purchased_private_review_root" \
  --execute --resume
```

Record only the routed exceptions through the same checkpointed interactive recorder, then finalize clearance by replaying the exact purchased inputs and checkpoints:

```zsh
uv run legalforecast acquisition record-disclosure-review-decisions \
  --output-root "$purchased_private_review_root/recorder-metadata" \
  --review-worksheet "$purchased_review_root/disclosure-exception-worksheet.json" \
  --private-inspection-map "$purchased_private_review_root/private-document-inspection-map.jsonl" \
  --reviewer-id "John Hughes" \
  --controlled-private-store-root "$purchased_private_review_root" \
  --decisions-output "$purchased_private_review_root/disclosure-review-decisions.jsonl" \
  --execute --resume
```

```zsh
uv run legalforecast acquisition clear-provenance-disclosures \
  --output-root "$purchased_clearance_root" \
  --review-requests "$purchased_review_requests" \
  --download-manifest "$purchased_download_manifest" \
  --case-relevance "$purchased_case_relevance" \
  --document-root "$purchased_document_root" \
  --restriction-evidence "$purchased_restriction_evidence" \
  --routing-plan "$purchased_review_root/disclosure-provenance-plan.json" \
  --exception-worksheet "$purchased_review_root/disclosure-exception-worksheet.json" \
  --exception-decisions "$purchased_private_review_root/disclosure-review-decisions.jsonl" \
  --exception-review-run-card "$purchased_private_review_root/recorder-metadata/run-cards/record-disclosure-review-decisions.json" \
  --cohort-policy "$cohort_policy" \
  --execute --resume
```

Clearance alone does not rewrite the canonical purchase state.
Bind the replayed provenance authority, fresh restriction evidence, recovered bytes, attempt authority, and purchase operation into the immutable post-recovery resolution artifact.
For schema continuity the v1 resolved record's legacy-named review hash fields carry the exception-decisions and exception-recorder run-card hashes; the authority kind determines their semantics.

```bash
resolved_post_recovery="$preparation_root/resolved-post-recovery/resolved-post-recovery-documents.jsonl"

uv run legalforecast acquisition resolve-post-recovery-documents \
  --output-root "$preparation_root/resolved-post-recovery" \
  --selection "$launch_root/target-cohort-selection.jsonl" \
  --purchase-policy "$purchase_policy" \
  --cohort-policy "$cohort_policy" \
  --budget-plan "$launch_root/missing-core-budget-plan.json" \
  --purchase-ledger "$purchase_ledger" \
  --controlled-private-root "$controlled_private_root" \
  --purchase-ledger-initialization-receipt "$purchase_ledger_initialization_receipt" \
  --attempt-policy "$attempt_policy" \
  --download-manifest "$purchased_download_manifest" \
  --disclosure-clearance "$purchased_clearance_root/disclosure-clearance.jsonl" \
  --clearance-run-card "$purchased_clearance_root/run-cards/clear-disclosures.json" \
  --restriction-evidence "$purchased_restriction_evidence" \
  --resolved-output "$resolved_post_recovery" \
  --execute --resume
```

The canonical exact-100 descriptor path must use the v3 flow in [the recovery disclosure continuation](cycle-1-target-100-recovery-disclosure.md), not the legacy manual clearance card above. Render the authenticated-model template first and execute it provider-free through the immutable plan. Then execute the provider-free policy-bound suffix below against the exact same disclosure artifact, private, purchase, recovery, repository, and target-cohort roots. The owner policy clears only marker-only exceptions already carrying verifier-issued fresh CourtListener public provenance and complete scan coverage; every other exception remains quarantined. Never render another full cycle config or invoke `--allow-model-provider` for this branch.

```bash
initial_disclosure_root="$preparation_root/purchased-recovery-disclosure"
initial_disclosure_private_root="/absolute/path/to/controlled-private-disclosure-root"
initial_disclosure_cycle_root="$preparation_root/purchased-recovery-disclosure-cycle"
initial_disclosure_config="$initial_disclosure_cycle_root/acquisition-cycle.json"
initial_disclosure_state_root="$initial_disclosure_cycle_root/orchestrator"
initial_disclosure_template="$repo_root/manifests/cycle-1-target-100.initial-recovery-disclosure.template.json"
successor_history_recovery_root="/absolute/path/to/completed-successor-recovery"
successor_history_private_root="/absolute/path/to/successor-purchase-private-root"
successor_history_resolver_run_card="/absolute/path/to/completed-successor-resolver-run-card.json"
terminal_disposition_selection="/absolute/path/to/final-disposition-selection.jsonl"
terminal_disposition_snapshot_manifest="/absolute/path/to/screening-snapshot/manifest.json"
terminal_purchase_result="/absolute/path/to/completed-purchase-result.json"
terminal_purchase_run_card="/absolute/path/to/completed-purchase-run-card.json"

mkdir -p "$initial_disclosure_cycle_root"

uv run legalforecast acquisition render-cycle-config \
  --template "$initial_disclosure_template" \
  --variable "DISCLOSURE_ARTIFACT_ROOT=$initial_disclosure_root" \
  --variable "DISCLOSURE_PRIVATE_ROOT=$initial_disclosure_private_root" \
  --variable "PURCHASE_PRIVATE_ROOT=$purchase_private_root" \
  --variable "PURCHASE_ROOT=$purchase_authority_root" \
  --variable "RECOVERY_ROOT=$quarantine_recovery_root" \
  --variable "REPO_ROOT=$repo_root" \
  --variable "TARGET_COHORT_ROOT=$initial_approved_root" \
  --variable "TERMINAL_DISPOSITION_SELECTION=$terminal_disposition_selection" \
  --variable "TERMINAL_DISPOSITION_SNAPSHOT_MANIFEST=$terminal_disposition_snapshot_manifest" \
  --variable "TERMINAL_PURCHASE_RESULT=$terminal_purchase_result" \
  --variable "TERMINAL_PURCHASE_RUN_CARD=$terminal_purchase_run_card" \
  --output "$initial_disclosure_config"

uv run legalforecast acquisition run-cycle \
  --config "$initial_disclosure_config" \
  --state-root "$initial_disclosure_state_root" \
  --json

uv run legalforecast acquisition run-cycle \
  --config "$initial_disclosure_config" \
  --state-root "$initial_disclosure_state_root" \
  --execute --json
```

Keep `initial_disclosure_root` and `initial_disclosure_private_root` outside and disjoint from `repo_root`, which is the frozen authority source root. These writable roots should be siblings of the frozen checkout: neither may equal, contain, or be contained by it. Rendering and cycle loading fail before plan publication if a `review-disclosure-exceptions` artifact, private state path, or output overlaps that frozen tree; the review command enforces the same boundary again before provider activity.

Inspect the completed `01-plan` artifacts now, then execute the provider-free post-plan suffix below. Do not render the full no-review cycle template into a fresh state root: every cycle config starts with `init-cycle`, which would rewrite the already-receipted `00-cycle` run card. The finalizer authenticates the existing plan producer card and the cohort-bound owner policy before publishing clearance; the resolver then consumes that exact clearance card.

```bash
uv run legalforecast acquisition finalize-provenance-quarantine \
  --output-root "$initial_disclosure_root/03-clearance" \
  --review-requests "$quarantine_recovery_root/disclosure-review-requests.jsonl" \
  --download-manifest "$quarantine_recovery_root/recap-fetch-quarantine-downloads.jsonl" \
  --case-relevance "$quarantine_recovery_root/purchased-case-relevance.jsonl" \
  --document-root "$quarantine_recovery_root/documents/recap-fetch-quarantine" \
  --restriction-evidence "$quarantine_recovery_root/post-recovery-restriction-evidence.jsonl" \
  --routing-plan "$initial_disclosure_root/01-plan/disclosure-provenance-plan.json" \
  --exception-worksheet "$initial_disclosure_root/01-plan/disclosure-exception-worksheet.json" \
  --plan-run-card "$initial_disclosure_root/01-plan/run-cards/plan-disclosure-provenance.json" \
  --public-marker-clearance-policy "$repo_root/docs/disclosure-public-marker-policy-cycle-1-2026-08-06.json" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --recovery-run-card "$quarantine_recovery_root/run-cards/recover-recap-fetch-quarantine.json" \
  --selection "$initial_approved_root/target-cohort-selection.jsonl" \
  --purchase-policy "$purchase_authority_root/purchase-policy-v2.json" \
  --purchase-ledger "$purchase_authority_root/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3" \
  --purchase-ledger-initialization-receipt "$purchase_authority_root/purchase-ledger-initialization.json" \
  --controlled-private-root "$purchase_private_root" \
  --recovery-cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --successor-history-recovery-root "$successor_history_recovery_root" \
  --successor-history-controlled-private-root "$successor_history_private_root" \
  --clearance-output "$initial_disclosure_root/03-clearance/disclosure-clearance.jsonl" \
  --quarantine-output "$initial_disclosure_root/03-clearance/disclosure-quarantine.jsonl" \
  --run-card-output "$initial_disclosure_root/03-clearance/run-cards/finalize-provenance-quarantine.json" \
  --execute --resume

uv run legalforecast acquisition resolve-post-recovery-documents \
  --output-root "$initial_disclosure_root/04-resolved" \
  --selection "$initial_approved_root/target-cohort-selection.jsonl" \
  --purchase-policy "$purchase_authority_root/purchase-policy-v2.json" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --budget-plan "$initial_approved_root/missing-core-budget-plan.json" \
  --purchase-ledger "$purchase_authority_root/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3" \
  --controlled-private-root "$purchase_private_root" \
  --purchase-ledger-initialization-receipt "$purchase_authority_root/purchase-ledger-initialization.json" \
  --attempt-policy "$purchase_authority_root/recap-fetch-attempt-policy.json" \
  --download-manifest "$quarantine_recovery_root/recap-fetch-quarantine-downloads.jsonl" \
  --disclosure-clearance "$initial_disclosure_root/03-clearance/disclosure-clearance.jsonl" \
  --clearance-run-card "$initial_disclosure_root/03-clearance/run-cards/finalize-provenance-quarantine.json" \
  --restriction-evidence "$quarantine_recovery_root/post-recovery-restriction-evidence.jsonl" \
  --terminal-disposition-selection "$terminal_disposition_selection" \
  --terminal-disposition-snapshot-manifest "$terminal_disposition_snapshot_manifest" \
  --terminal-purchase-result "$terminal_purchase_result" \
  --terminal-purchase-run-card "$terminal_purchase_run_card" \
  --resolved-output "$initial_disclosure_root/04-resolved/resolved-post-recovery-documents.jsonl" \
  --run-card-output "$initial_disclosure_root/04-resolved/run-cards/resolve-post-recovery-documents.json" \
  --execute --resume
```

Do not run the model commands for the policy-bound provider-free route above.
The four terminal-disposition arguments are all-or-none and are mandatory when the recovery run card commits any terminal-unavailable operation.
They independently replay the exhaustive terminal-purchase disposition against the current journal and must match every recovery terminal document key exactly; the resolver's original `--selection` remains the recovery selection and is never replaced by `--terminal-disposition-selection`.
The resolver run card commits all five terminal evidence inputs, including the recovery terminal ledger, by path and bytes.
The separately authenticated model continuation remains available only if the owner deliberately selects that alternative route:

```bash
uv run legalforecast acquisition run-cycle \
  --config "$initial_disclosure_config" \
  --state-root "$initial_disclosure_state_root" \
  --execute --allow-network --allow-model-provider --json

uv run legalforecast acquisition run-cycle \
  --config "$initial_disclosure_config" \
  --state-root "$initial_disclosure_state_root" \
  --execute --json
```

Before any recovery-slice run or merge, execute the provider-free read-only development check. No arguments run the focused verifier regressions, successor-ledger capsule rehearsal, and checked-in manifest preflight. During iteration, `--quick --manifest <path>` runs the real-lineage preflight without pytest; before merge, `--require-real-lineage` fails instead of accepting fixture-only coverage. An absent real manifest is reported as `NOT_EVALUATED`, and the aggregate verdict is `PASS_FIXTURE_ONLY`, never an unqualified `PASS`; the checked-in public capsule and copies with the same artifact commitments do not satisfy strict real-lineage mode. The command emits text on a terminal and one stable JSON summary when piped; child diagnostics and phase timings go to stderr.

```bash
scripts/dev-check-recovery-vertical-slice.sh

scripts/dev-check-recovery-vertical-slice.sh \
  --quick --manifest <cycle-preflight-manifest.json>

scripts/dev-check-recovery-vertical-slice.sh \
  --manifest <cycle-preflight-manifest.json> --require-real-lineage
```

For a single stable machine-readable check, use `uv run python -m legalforecast.ingestion.cycle_preflight --manifest /absolute/path/to/cycle-preflight-manifest.json --format json`. The manifest declares dependency edges and byte commitments; the verifier collects independent defects, marks blocked descendants `NOT_EVALUATED`, returns nonzero for any violation or ambiguity, and never opens a purchase journal, acquires locks, invokes a provider, or writes artifacts, cards, ledgers, or dispatch state.

The canonical descriptor handoff after that continuation is `RECOVERY_SOURCE_ROOT`, which must be distinct from the immutable `RECOVERY_ROOT` used by the initial recovery cycle. The dedicated producer writes `$RECOVERY_SOURCE_ROOT/0000-initial-v2.json` and `$RECOVERY_SOURCE_ROOT/run-cards/build-replacement-recovery-source-0000.json`; do not hand-author either artifact or point `INITIAL_RECOVERY_SOURCE` at the raw recovery root:

```bash
RECOVERY_SOURCE_ROOT="$preparation_root/recovery-sources"

uv run legalforecast acquisition build-replacement-recovery-source \
  --output-root "$RECOVERY_SOURCE_ROOT" \
  --ordinal 0 \
  --recovery-root "$quarantine_recovery_root" \
  --purchased-clearance-run-card "$initial_disclosure_root/03-clearance/run-cards/finalize-provenance-quarantine.json" \
  --resolved-post-recovery-run-card "$initial_disclosure_root/04-resolved/run-cards/resolve-post-recovery-documents.json" \
  --successor-history-recovery-root "$successor_history_recovery_root" \
  --successor-history-controlled-private-root "$successor_history_private_root" \
  --additional-resolved-post-recovery-run-card "$successor_history_resolver_run_card" \
  --terminal-disposition-selection "$terminal_disposition_selection" \
  --terminal-disposition-snapshot-manifest "$terminal_disposition_snapshot_manifest" \
  --terminal-purchase-result "$terminal_purchase_result" \
  --terminal-purchase-run-card "$terminal_purchase_run_card" \
  --purchase-policy "$purchase_authority_root/purchase-policy-v2.json" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --purchase-ledger "$purchase_authority_root/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3" \
  --initial-controlled-private-root "$purchase_private_root" \
  --purchase-ledger-initialization-receipt "$purchase_authority_root/purchase-ledger-initialization.json" \
  --execute --resume
```

The producer authenticates the v2 recovery card, v3 purchased-clearance card, resolver card, policies, ledger, private approval root, and ledger-initialization receipt before publishing the descriptor.
For a nonempty terminal ledger it also rereads and independently replays the complete four-file terminal-disposition bundle; it does not trust the resolver card's metadata as authority.

Only after the v3 continuation's resolver succeeds may `materialize-cohort-documents` use `$quarantine_recovery_root` as `--purchased-recovery-root`, `$initial_disclosure_root/03-clearance/disclosure-clearance.jsonl`, its finalizer card, and `$initial_disclosure_root/04-resolved/resolved-post-recovery-documents.jsonl`. The materializer replays the generated review queue and recovery document-tree commitments, verifies the authenticated clearance and canonical operation bindings, and fails closed if any quarantine artifact was hand-edited or omitted.

If purchased-document clearance quarantines any selected candidate, do not continue with the initial `$launch_root`.
Run the authenticated replacement loop in [the clearance-replacement schema](schemas/clearance-replacement-v1.md) until `plan-clearance-replacements` reports no additional replacement plan, then execute the checked-in `cycle-1-target-100.replacement-reprojection.template.json`.

```bash
replacement_root="$preparation_root/replacement"
```

The planner's `--active-selection-output` is the reprojection's only candidate input; `project-replacement-exact-100` must publish exactly 100 rows under `$replacement_root/01-projection`.
Set `canonical_target_root="$replacement_root/01-projection"` after that authenticated reprojection succeeds.
Render and execute `manifests/cycle-1-target-100.replacement-corpus.template.json` for the downstream continuation.
Render `EXACT100_ROOT` as `$canonical_target_root`; the continuation consumes `$canonical_target_root/target-cohort-selection.jsonl` and `$canonical_target_root/run-cards/project-target-cohort.json` as the sole downstream cohort authority.
Render its `PREPARATION_ROOT`, `PURCHASE_ROOT`, `PURCHASE_PRIVATE_ROOT`, and `EXACT100_ROOT` variables as distinct immutable inputs, and render `SUCCESSOR_PLAN_ROOT` as the exact immutable `01-plan` directory committed by `EXACT100_ROOT/run-cards/project-target-cohort.json`; it must contain `SUCCESSOR_PLAN_ROOT/successor-exclusions.jsonl` and must not be inferred from `EXACT100_ROOT`. Supply `INITIAL_RECOVERY_SOURCE` as the authenticated `$RECOVERY_SOURCE_ROOT/0000-initial-v2.json` descriptor and supply the ordered `SUCCESSOR_RECOVERY_SOURCE_DIR`, then render `SUCCESSOR_ARTIFACT_ROOT` and `SUCCESSOR_PRIVATE_ROOT` as new output roots.
`EXACT100_ROOT` must be the authenticated standard projection containing `EXACT100_ROOT/target-cohort-selection.jsonl`, `EXACT100_ROOT/target-cohort-projection.json`, `EXACT100_ROOT/free-document-downloads.jsonl`, `EXACT100_ROOT/purchased-document-downloads.jsonl`, `EXACT100_ROOT/document-downloads-merged.jsonl`, `EXACT100_ROOT/disclosure-clearance.jsonl`, `EXACT100_ROOT/restriction-evidence.jsonl`, and `EXACT100_ROOT/run-cards/project-target-cohort.json`.
`PURCHASE_ROOT` is the completed v4 ranked-reserve purchase root containing common purchase authority, while `PURCHASE_PRIVATE_ROOT` is its immutable private approval root; neither is also the preparation or exact-100 root.
The corpus-mode plan consolidates every initial and successor purchased recovery/clearance descriptor selected by the exact-100 projection, materializes from that authenticated union, writes every downstream artifact beneath the two successor roots, and then performs parse planning, decision texts, Stage A, Stage B, packet planning, packet building, and `finalize-corpus --target-clean-cases 100`.
Before finalization, `build-replacement-exclusions` publishes the authenticated successor exclusion ledger; `finalize-corpus` consumes that ledger and its producer run card to prove every screened candidate is selected XOR excluded.
Provider stages use the checked-in `model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json`, one successor-private provider journal, and `--local-provider-journal-only`; they do not use DynamoDB authority arguments.
The narrow successor purchase selection authorizes a tranche but never becomes a downstream cohort, and the initial `$launch_root` remains historical evidence rather than an input after any quarantine.

### Expected Volumes

Do not use an estimated docket count as completion evidence. The decision-search summary must prove every frozen term and page terminal; the docket-acquisition summary must reconcile every ranked candidate; and the screening snapshot must be complete and saturated. Record the actual discovered, enriched, fetched, screened, excluded, and Firecrawl-credit counts from those artifacts.

### Reading The Tallies

Each command prints a machine-readable JSON summary to stdout (use `--summary-output PATH` to also persist it):

- `discover` funnel: `terms_terminal`/`terms_total` (how many frozen terms reached a bounded terminal state), `total_hits` (raw document hits), `distinct_candidates` (deduped dockets), `prescreen_exclusions_by_reason` (bankruptcy/criminal dockets dropped before any fetch), and `per_term` progress. `complete: true` means every term is bounded; `saturated: true` means every term was exhausted rather than limit-bound.
- `observe` tally: `considered` (candidates scanned), `skipped_already_observed` (resume skips), `observed` (fetched this pass), `eligible` (strict-clean accepted), `excluded_by_reason` (immutable/posture exclusions, with the underlying strict-screen reason surfaced as `strict_clean_screen_failed:<screen_reason>`), and `transient_by_reason` (retryable failures to re-run).
- `seed-batch-001-leads`: `leads_selected`, `leads_seeded`, and `already_seeded`.
- `seed-direct-search`: the same transfer counts plus `source_batch_digest` and `source_candidate_set_sha256`, which bind the REST batch to the exact saturated source pool.

### Frozen priority-batch Firecrawl observation

When authenticated CourtListener REST reconstruction is unavailable or its daily request budget is exhausted, `legalforecast batch-002 observe-firecrawl` may observe an exact unresolved subset of an already frozen direct-search priority tranche through Firecrawl:

```bash
uv run legalforecast batch-002 observe-firecrawl \
  --cycle-store "$CYCLE_STORE" \
  --batch-id "$PRIORITY_BATCH_ID" \
  --run-id "$FIRECRAWL_OBSERVE_RUN_ID" \
  --eligibility-anchor 2026-06-30 \
  --raw-artifact-dir "$FIRECRAWL_RAW_DIR" \
  --credit-cap 45000 \
  --workers 10 \
  --max-pages-per-docket 100 \
  --live-firecrawl
```

Repeat `--candidate-id courtlistener-docket-N` to restrict a new run to exact batch candidates. Caller order does not rerank them. Reuse the identical run ID and arguments after an interruption that left provider attempts unused; the durable run restores its original candidate scope, replays committed successful artifacts, and skips terminal observations. If committed HTML later fails parser or complete-docket reconstruction, same-run replay cannot change those immutable bytes. Preserve the transient `retry_contract`, then recover that exact unresolved candidate under a fresh run ID and a distinct raw-artifact directory.

This route changes only the docket-page transport. It preserves the frozen batch/order commitments and the canonical anchor, unbounded first-disposition, strict-screen, linkage, leakage, and exclusion-reason gates. A terminal outcome requires exhaustive docket history; an older-than-anchor page boundary is not sufficient because an unseen row could contain an earlier disposition or required linkage evidence. Incomplete pagination or ambiguous evidence remains transient and unresolved. Do not treat this route as PACER purchase authority, and do not use it to relax eligibility, freeze, dispatch, or evaluate models.
