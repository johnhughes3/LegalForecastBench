# Cycle 1 v4 ranked-reserve materialization

This runbook materializes the already approved v4 ranked-reserve target-100 acquisition authority without rerunning selection, changing frozen evidence, contacting a provider, acknowledging fees, evaluating, freezing, or dispatching.
It uses [`cycle-1-target-100.v4-ranked-reserve.template.json`](../manifests/cycle-1-target-100.v4-ranked-reserve.template.json), not the older v3 coordinator.

## Fixed evidence

Run from the repository root and keep these exact canonical roots.
The approval fixes the ledger namespace under `successor_root`; choosing another root must fail replay.

```zsh
repo_root="$PWD"
source_root="$repo_root/artifacts/cycle-1/official-acquisition-main-e0d7177-20260716/target-150-plus-five-current-policy-v1/15-final-provider-free-union-main-4d3ba85-v1/33-10k-continuation-main-5781216-v1"
frozen_artifact_root="$repo_root/artifacts/cycle-1/target-100-production"
successor_root="$repo_root/artifacts/cycle-1/target-100-production-v4-ranked-reserve"
frozen_v4_root="$successor_root/05-target-cohort-v4"
private_cycle_root="${repo_root:h}/.legalforecastbench-private/cycle-1/target-100-production-v4-ranked-reserve"
approval_root="$private_cycle_root/purchase-approval"
parser_root="/absolute/clean/pinned/mistral-parser"
authority_root="$successor_root/06-purchase-authority"
ledger="$authority_root/cycle-1-target100-recap-fetch-purchase-ledger.sqlite3"
cohort_policy="$repo_root/docs/cohort-policy-cycle-1-target-100-2026-07-25.json"
fee_schedule="$source_root/10-purchase-authority/courtlistener-recap-fetch-fee-schedule-v1.json"
```

Authenticate the immutable public projection before creating anything.
The exact projection contains 100 selected cases, 179 planned purchases, a `$545.95` maximum reservation, and the unchanged `$567.30` cap.

```zsh
test "$(sha256sum "$frozen_v4_root/target-cohort-projection.json" | cut -d' ' -f1)" = 3d5e9702d4237785326457e21279181e21d3d40716e557c51d835287d1c99269
test "$(sha256sum "$frozen_v4_root/target-cohort-selection.jsonl" | cut -d' ' -f1)" = 877c299277a3675b5cf153d5a01e885a480e76720bd7a02115501282d95f4e0f
test "$(sha256sum "$frozen_v4_root/missing-core-budget-plan.json" | cut -d' ' -f1)" = 6129569287bbe94403d3449c0315c85dc223187549c70f24b8342962c3178f1b
jq -e '.selected_case_count == 100 and .total_missing_core_documents == 179 and .total_estimated_cost_usd == "545.95" and .max_projected_budget_usd == "567.30" and .paid_activity_executed == false' "$frozen_v4_root/target-cohort-projection.json" >/dev/null
```

Do not edit, copy, reformat, or replace any file below `frozen_v4_root` or `approval_root`.

## Replay approval and materialize purchase authority

The verifier must run while `ledger` is absent.
It authenticates the exact private checkpoint and approval run card against the public v4 projection, cohort policy, fee schedule, and approved canonical ledger path.

```zsh
test ! -e "$ledger"

uv run legalforecast acquisition verify-purchase-approval \
  --target-cohort-root "$frozen_v4_root" \
  --cohort-policy "$cohort_policy" \
  --fee-schedule "$fee_schedule" \
  --canonical-ledger-path "$ledger" \
  --controlled-private-root "$approval_root" \
  --checkpoint "$approval_root/purchase-approval-checkpoint.json" \
  --approval-run-card "$approval_root/run-cards/record-purchase-approval.json"
```

Generate the immutable v2 purchase policy and bounded RECAP attempt policy through their supported provider-free commands.
Existing exact bytes resume; different bytes fail closed.

```zsh
mkdir -p -- "$authority_root"

uv run legalforecast acquisition generate-purchase-policy \
  --target-cohort-root "$frozen_v4_root" \
  --cohort-policy "$cohort_policy" \
  --fee-schedule "$fee_schedule" \
  --canonical-ledger-path "$ledger" \
  --controlled-private-root "$approval_root" \
  --checkpoint "$approval_root/purchase-approval-checkpoint.json" \
  --approval-run-card "$approval_root/run-cards/record-purchase-approval.json" \
  --output "$authority_root/purchase-policy-v2.json"

uv run legalforecast acquisition generate-recap-fetch-attempt-policy \
  --purchase-policy "$authority_root/purchase-policy-v2.json" \
  --controlled-private-root "$approval_root" \
  --cohort-policy "$cohort_policy" \
  --budget-plan "$frozen_v4_root/missing-core-budget-plan.json" \
  --selection "$frozen_v4_root/target-cohort-selection.jsonl" \
  --output "$authority_root/recap-fetch-attempt-policy.json"
```

Do not initialize the ledger manually.
The coordinator does that later through `init-purchase-ledger`, producing the authenticated initialization receipt bound to the v2 policy and exact ledger identity.

## Materialize provider cycle caps successor

Provider caps require the raw reviewed authority-smoke workflow artifact and its separately recorded exact digest and reviewed release SHA.
Do not recreate the receipt or extract and hand-copy its resource identity.

```zsh
smoke_receipt="$private_cycle_root/provider-authority/authority-smoke.json"
smoke_sha256="<sha256-of-exact-downloaded-smoke-bytes>"
smoke_release_sha="<reviewed-40-character-main-release>"

uv run legalforecast acquisition materialize-provider-cycle-caps-successor \
  --legacy-provider-cycle-caps "$repo_root/model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json" \
  --expected-legacy-caps-sha256 71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74 \
  --authority-smoke-receipt "$smoke_receipt" \
  --expected-authority-smoke-sha256 "$smoke_sha256" \
  --expected-smoke-release-sha "$smoke_release_sha" \
  --provider-caps-successor-policy "$repo_root/model_registries/cycle-1-target-100-provider-caps-successor-policy-2026-07-28.json" \
  --expected-provider-policy-sha256 894b59465c44caa109197667f43495de1c93e0d22afdbbd9f5c6f95722d76ed6 \
  --output-root "$successor_root/01-provider-authority"
```

This is a structural prerequisite, not permission to obtain the smoke artifact or invoke its protected workflow.
If the exact raw receipt, digest, or reviewed release is unavailable, stop this stage and preserve the purchase-authority work already completed.

## Render and preflight the v4 cycle

Render exactly once after the policy, attempt policy, and provider caps successor exist.
The template consumes the v4 target root and approval root only as inputs; every coordinator output is under the successor public/private roots.

```zsh
uv run legalforecast acquisition render-cycle-config \
  --template "$repo_root/manifests/cycle-1-target-100.v4-ranked-reserve.template.json" \
  --variable REPO_ROOT="$repo_root" \
  --variable SOURCE_ROOT="$source_root" \
  --variable FROZEN_ARTIFACT_ROOT="$frozen_artifact_root" \
  --variable FROZEN_V4_ROOT="$frozen_v4_root" \
  --variable APPROVAL_ROOT="$approval_root" \
  --variable SUCCESSOR_ARTIFACT_ROOT="$successor_root" \
  --variable SUCCESSOR_PRIVATE_ROOT="$private_cycle_root" \
  --variable PARSER_ROOT="$parser_root" \
  --output "$successor_root/acquisition-cycle-v4-ranked-reserve.json"

uv run legalforecast acquisition run-cycle \
  --config "$successor_root/acquisition-cycle-v4-ranked-reserve.json" \
  --state-root "$successor_root/orchestrator-v4-ranked-reserve" \
  --json
```

The preflight must report cycle ID `cycle-1-target-100-2026-07-25-v4-ranked-reserve`, target 100, and next stage `initialize-cycle`.
After review, `--execute` runs the provider-free cycle identity and exact broker-policy generation, then stops at `broker_policy_deployment_checkpoint_stage_completed`.
It does not deploy the broker policy.

```zsh
uv run legalforecast acquisition run-cycle \
  --config "$successor_root/acquisition-cycle-v4-ranked-reserve.json" \
  --state-root "$successor_root/orchestrator-v4-ranked-reserve" \
  --execute --json
```

Only after secure-gate has activated those exact broker-policy bytes may another provider-free `--execute` invocation initialize the ledger and emit `$authority_root/purchase-ledger-initialization.json`.
That invocation must stop before `purchase-missing-documents` with `paid_boundary_not_authorized`.
Do not add `--allow-paid` or `--allow-network` during materialization.

Evaluation, freeze, dispatch, and publication are absent from the template and remain unauthorized.
