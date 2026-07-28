# Cycle 1 Target-100 Direct Prerequisites

This checklist covers the authority and protected-workflow steps that cannot be represented as ordinary coordinator stages.
It belongs next to [`manifests/cycle-1-target-100.acquisition-cycle.template.json`](../manifests/cycle-1-target-100.acquisition-cycle.template.json), whose terminal stage is `finalize-corpus --target-clean-cases 100`.
Nothing here authorizes evaluation, official freeze, dispatch, or a budget increase.

## Render once

Choose five absolute, nonsymlinked roots:

```zsh
repo_root="$PWD"
source_root="$PWD/artifacts/cycle-1/official-acquisition-main-e0d7177-20260716/target-150-plus-five-current-policy-v1/15-final-provider-free-union-main-4d3ba85-v1/33-10k-continuation-main-5781216-v1"
artifact_root="$PWD/artifacts/cycle-1/target-100-production"
private_root="/absolute/controlled-private/cycle-1-target-100"
parser_root="/absolute/clean/pinned/mistral-parser"
```

Create only the new artifact root; the renderer itself rejects a symlinked or rebound output directory and never replaces an existing config:

```zsh
mkdir -p -- "$artifact_root"
```

Before rendering, verify that `SOURCE_ROOT` contains:

- `courtlistener-request-ledger-base-v1.sqlite3`;
- `01-current-cycle/cycle-acquisition.sqlite3`;
- `10-purchase-authority/courtlistener-recap-fetch-fee-schedule-v1.json`;
- `15-final153-union-main-911371f-v1/snapshots/cycle1-final153-current-policy-union-main-911371f-v1/{manifest.json,screened-cases.jsonl,summary.json,exclusions.jsonl}`;
- `15-final153-union-main-911371f-v1/union-raw-artifacts/`; and
- `15-final153-union-main-911371f-v1/union-raw-artifacts.jsonl`.

The frozen snapshot manifest SHA-256 is `487bec5f70289e212554a9af59fc195c9d6244060550d346612cb589405b138c`, and its cycle hash is `35f70123bfc966512d61119746ba09716332a181c074f131d553b56b610641cb`.
The template fixes the eligibility anchor at `2026-06-30`, the launch target at 100, the purchase cap at `$567.30`, the per-document ceiling at `$3.05`, and the per-case gap ceiling at 24.
Do not render if any of those inputs or values has changed.

```zsh
uv run legalforecast acquisition render-cycle-config \
  --template "$repo_root/manifests/cycle-1-target-100.acquisition-cycle.template.json" \
  --variable REPO_ROOT="$repo_root" \
  --variable SOURCE_ROOT="$source_root" \
  --variable ARTIFACT_ROOT="$artifact_root" \
  --variable PRIVATE_ROOT="$private_root" \
  --variable PARSER_ROOT="$parser_root" \
  --output "$artifact_root/acquisition-cycle.json"

uv run legalforecast acquisition run-cycle \
  --config "$artifact_root/acquisition-cycle.json" \
  --state-root "$artifact_root/orchestrator" \
  --json
```

After the first receipt exists, never edit or rerender that config.
Resume by repeating `run-cycle` against the same config and state root, adding only the boundary switches reported by status: `--execute`, `--allow-network`, `--allow-human`, `--allow-model-provider`, or `--allow-paid`.
Every invocation stops immediately after one authorized non-provider-free stage, so a disclosure decision cannot implicitly authorize the later purchase decision and parser authority cannot flow into Stage A.

## Frozen policy and registry inputs

The following exact checked-in inputs must exist before downstream model work:

| Input | Required path | SHA-256 |
|---|---|---|
| Evaluated late-June registry | `$REPO_ROOT/model_registries/cycle-1-2026-06-30.json` | `fe4df0edc1e81d3d53fa0e24114df8faadab4229fcf7d8e575a4592d3d40659f` |
| Stage A registry | `$REPO_ROOT/model_registries/cycle-1-labeling-2026-07-12.json` | `e24b0a235936de4b0870fd6b688fabbd4901ccd3a8378a826c4a287a26c1aba0` |
| Stage B judge registry | `$REPO_ROOT/model_registries/cycle-1-stage-b-judges-2026-07-12.json` | `5243b74bfdb2d3accc1a301f7c997b9520abc8586bbf944e22f67e2b263106a2` |
| Target-cycle provider caps base | `$REPO_ROOT/model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json` | `71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74` |
| Provider caps successor policy | `$REPO_ROOT/model_registries/cycle-1-target-100-provider-caps-successor-policy-2026-07-28.json` | `894b59465c44caa109197667f43495de1c93e0d22afdbbd9f5c6f95722d76ed6` |
| Labeling policy | `$REPO_ROOT/docs/labeling-policy.json` | `80dc05cdf9ebece514899a60645cfd11c730a359af2bca50f8f122fade723004` |
| Cohort policy | `$REPO_ROOT/docs/cohort-policy-cycle-1-target-100-2026-07-25.json` | `5afa4d2368eca39719892bfd816c25a191f65c935ada3ca81e33e9af9861c6c8` |

Verify the labeling policy before any Stage B provider call:

```zsh
uv run legalforecast acquisition verify-labeling-policy \
  --artifact "$repo_root/docs/labeling-policy.json" \
  --judge-registry "$repo_root/model_registries/cycle-1-stage-b-judges-2026-07-12.json" \
  --cycle-id cycle-1-target-100-2026-07-25
```

This artifact retains the already approved Cycle 1 publication timestamp, judge registry, audit thresholds, and threshold source while binding the exact target-cycle identity used by acquisition, provider caps, labeling, and finalization.
This is a mechanical identity repair before any Stage B label corpus exists, not a post-yield policy selection: every substantive policy field is unchanged, and the target-cycle identifier was already fixed by the acquisition config and cohort policy.

The checked-in base is deliberately provider-free and cannot authorize a model call.
Before Stage A, obtain the raw reviewed `official-paid-labeling-authority-smoke` workflow artifact and materialize the target-cycle authority-enabled successor:

```zsh
smoke_receipt="$private_root/provider-authority/authority-smoke.json"

uv run legalforecast acquisition materialize-provider-cycle-caps-successor \
  --legacy-provider-cycle-caps "$repo_root/model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json" \
  --expected-legacy-caps-sha256 71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74 \
  --authority-smoke-receipt "$smoke_receipt" \
  --expected-authority-smoke-sha256 "<sha256-of-exact-downloaded-smoke-bytes>" \
  --expected-smoke-release-sha "<reviewed-40-character-main-release>" \
  --provider-caps-successor-policy "$repo_root/model_registries/cycle-1-target-100-provider-caps-successor-policy-2026-07-28.json" \
  --expected-provider-policy-sha256 894b59465c44caa109197667f43495de1c93e0d22afdbbd9f5c6f95722d76ed6 \
  --output-root "$artifact_root/01-provider-authority"
```

Every Stage A/B/finalization command in the rendered manifest binds `$ARTIFACT_ROOT/01-provider-authority/provider-cycle-caps.json`.
That successor must retain cycle ID `cycle-1-target-100-2026-07-25`, the three reviewed public account aliases, and the checked-in per-provider cycle caps.
It does not require a hardware key or independent external-spend-cap artifact.
Do not hand-edit the successor, change its caps, or create a second provider journal.

## Purchase approval and policy generators

`run-cycle` pauses after `record-purchase-approval`.
Before allowing it to run `init-purchase-ledger`, verify the exact private decision while the ledger path is still absent:

```zsh
uv run legalforecast acquisition verify-purchase-approval \
  --target-cohort-root "$artifact_root/05-target-cohort" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --fee-schedule "$source_root/10-purchase-authority/courtlistener-recap-fetch-fee-schedule-v1.json" \
  --canonical-ledger-path "$artifact_root/06-purchase-authority/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3" \
  --controlled-private-root "$private_root/purchase-approval" \
  --checkpoint "$private_root/purchase-approval/purchase-approval-checkpoint.json" \
  --approval-run-card "$private_root/purchase-approval/run-cards/record-purchase-approval.json"
```

Stop on `reject`.
For the approved paid path, generate all three deterministic policies before resuming:

```zsh
uv run legalforecast acquisition generate-purchase-policy \
  --target-cohort-root "$artifact_root/05-target-cohort" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --fee-schedule "$source_root/10-purchase-authority/courtlistener-recap-fetch-fee-schedule-v1.json" \
  --canonical-ledger-path "$artifact_root/06-purchase-authority/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3" \
  --controlled-private-root "$private_root/purchase-approval" \
  --checkpoint "$private_root/purchase-approval/purchase-approval-checkpoint.json" \
  --approval-run-card "$private_root/purchase-approval/run-cards/record-purchase-approval.json" \
  --output "$artifact_root/06-purchase-authority/purchase-policy-v2.json"

uv run legalforecast acquisition generate-recap-fetch-attempt-policy \
  --purchase-policy "$artifact_root/06-purchase-authority/purchase-policy-v2.json" \
  --controlled-private-root "$private_root/purchase-approval" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --budget-plan "$artifact_root/05-target-cohort/missing-core-budget-plan.json" \
  --selection "$artifact_root/05-target-cohort/target-cohort-selection.jsonl" \
  --output "$artifact_root/06-purchase-authority/recap-fetch-attempt-policy.json"

uv run legalforecast acquisition generate-recap-fetch-broker-policy \
  --purchase-policy "$artifact_root/06-purchase-authority/purchase-policy-v2.json" \
  --controlled-private-root "$private_root/purchase-approval" \
  --cohort-policy "$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json" \
  --budget-plan "$artifact_root/05-target-cohort/missing-core-budget-plan.json" \
  --selection "$artifact_root/05-target-cohort/target-cohort-selection.jsonl" \
  --attempt-policy "$artifact_root/06-purchase-authority/recap-fetch-attempt-policy.json" \
  --output "$artifact_root/06-purchase-authority/recap-fetch-broker-policy.json"
```

The outputs must be at exactly those paths before resuming.
The secure-gate RECAP Fetch broker must already be deployed with the exact generated broker policy and its dedicated five-name production view; the CourtListener request ledger must still be the source-root ledger named by the template.
Neither policy generation nor ledger initialization acknowledges fees.
Only resume the paid stage with `--allow-network --allow-paid` after the run status names `purchase-missing-documents` and the remaining ledger capacity is sufficient.

## Parser boundary

Before resuming at `parse-documents`, the clean parser checkout at `PARSER_ROOT` must be pinned to revision `9402306972462a5bdd0da7f687c5e6b4cea373a0`.
The `/agents/sandbox/legalforecastbench/parser` development view must expose exactly `MISTRAL_API_KEY`, nonempty, and no acquisition or labeling key.
If the path, key, or pinned clean checkout is unavailable, stop; do not substitute a parser.

Run the coordinator inside that narrow parser environment with the same rendered config and state root:

```zsh
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench/parser \
  -- uv run legalforecast acquisition run-cycle \
  --config "$artifact_root/acquisition-cycle.json" \
  --state-root "$artifact_root/orchestrator" \
  --execute --allow-network --allow-model-provider --json
```

The parser stage must leave these exact outputs before ordinary provider-free resume:

- `$ARTIFACT_ROOT/14-parse/mistral-markdown-conversions.jsonl`;
- `$ARTIFACT_ROOT/14-parse/markdown/`; and
- `$ARTIFACT_ROOT/14-parse/run-cards/parse-documents.json`.

## Protected Stage A and Stage B provider work

All paid model calls run through `.github/workflows/official-paid-labeling.yaml` and its encrypted sequential baton flow.
Use the same frozen registries, provider-cycle caps, canonical journal path, authority table `legalforecastbench-official-eval-provider-authority`, region `us-east-1`, input paths, output paths, and run-card paths that the rendered manifest names.
The protected environment values must equal those literals before the config receives its first receipt; a different deployed authority identity requires correcting and rerendering the template before execution, never editing a receipted config.

The protected Stage A unitizer must populate:

- `$ARTIFACT_ROOT/15-stage-a-unitize/prediction-units.jsonl`;
- `$ARTIFACT_ROOT/15-stage-a-unitize/llm-unitization-audit.jsonl`;
- `$ARTIFACT_ROOT/15-stage-a-unitize/unitization-review-queue.jsonl`;
- `$ARTIFACT_ROOT/15-stage-a-unitize/run-cards/llm-unitize.json`; and
- `$PRIVATE_ROOT/paid-labeling/provider-attempts.sqlite3`.

The model key is `anthropic:claude-sonnet-4-6`.
After the protected model-provider workflow restores the encrypted result at those exact paths, adopt that externally completed stage with:

```zsh
uv run legalforecast acquisition run-cycle \
  --config "$artifact_root/acquisition-cycle.json" \
  --state-root "$artifact_root/orchestrator" \
  --adopt-next-completed --json
```

Do not combine `--adopt-next-completed` with `--execute`, `--allow-model-provider`, or any other authority flag.
Adoption must successfully replay the settled `llm-unitize` attempt from the same journal and exact output root without rebilling; any prompt, registry, caps, journal, account, authority, or path identity mismatch fails closed.

The immediately following protected structural-review baton must reuse that same journal and populate:

- `$ARTIFACT_ROOT/16-stage-a-review/stage-a-structural-flags.jsonl`;
- `$ARTIFACT_ROOT/16-stage-a-review/unitization-review-queue-reviewed.jsonl`;
- `$ARTIFACT_ROOT/16-stage-a-review/stage-a-structural-review-audit.jsonl`; and
- `$ARTIFACT_ROOT/16-stage-a-review/run-cards/llm-review-stage-a.json`.

The reviewer key is `google:gemini-3.5-flash`.
After the protected model-provider workflow restores the structural-review outputs, repeat the same `run-cycle --adopt-next-completed --json` invocation above without `--execute` or authority flags.
The coordinator adopts only by successful settled-attempt replay; do not create another journal or change the output root.

After John supplies Stage A adjudications and `apply-unitization-review` completes, run the two Stage B provider shards sequentially from the same journal, never in parallel:

1. OpenAI, for `openai:gpt-5.4-mini-2026-03-17`, writes `$ARTIFACT_ROOT/19-stage-b-shards/openai-audit.jsonl` and `$ARTIFACT_ROOT/19-stage-b-shards/openai-run-card.json`.
2. Google, for `google:gemini-3.5-flash`, consumes the immediately preceding baton and writes `$ARTIFACT_ROOT/19-stage-b-shards/google-audit.jsonl` and `$ARTIFACT_ROOT/19-stage-b-shards/google-run-card.json`.

Each shard job must name the complete two-model Stage B registry while the protected wrapper supplies its one allowed `--execution-provider`.
After both shard cards and audits are restored at those exact paths, resume the coordinator.
Its `merge-stage-b-provider-shards` stage is provider-free despite the conservative `model_provider` boundary and produces the canonical labels, audit, queue, and `llm-label` card under `$ARTIFACT_ROOT/20-stage-b-labels`.

## John adjudications and beads

The Stage A review queue is immutable.
Record every required structural adjudication through the labeling protocol and place the resulting JSONL at:

```text
$PRIVATE_ROOT/adjudications/stage-a-adjudications.jsonl
```

If no Stage A adjudication is required, place the protocol-valid empty artifact there rather than omitting the file.
Anything routed to lawyer review remains John's decision; agents must not self-adjudicate it.

After `plan-label-audit`, John reviews the private merged queue and audit plan:

```text
$PRIVATE_ROOT/label-audit/lawyer-review-queue.jsonl
$PRIVATE_ROOT/label-audit/cycle-label-audit-plan.json
$PRIVATE_ROOT/label-audit/llm-label-audit-cycle-planned.jsonl
```

Place the protocol-valid Stage B adjudication JSONL at:

```text
$PRIVATE_ROOT/adjudications/stage-b-adjudications.jsonl
```

Create or update a bead listing every pending adjudication, the candidate/unit identity, and the exact private queue commitment.
An empty queue must be recorded as empty in the bead; a nonempty queue is not authorization for an agent to decide it.
Resume `apply-lawyer-review` only after the adjudication artifact covers every required row.

## Terminal acceptance

The final coordinator stages write packet inputs, packets, the complete exclusion ledger, and corpus readiness under:

```text
$ARTIFACT_ROOT/23-packet-plan/
$ARTIFACT_ROOT/24-packets/
$ARTIFACT_ROOT/25-final-corpus/
```

`finalize-corpus` separately consumes discovery exclusions plus all later preparation, gap, budget, cohort, and packet-plan exclusion sources named in the template.
Completion is proven only when `run-cycle` reports `plan_completed: true`, `corpus_target_verified: true`, and `clean_case_count >= 100`.
Then update the summary bead with discovered, excluded-by-reason, acquired, parsed, labeled, clean, spend-versus-`$567.30`, and per-stratum case-mix counts.
Do not invoke evaluation, freeze, dispatch, or publication from this acquisition plan.
