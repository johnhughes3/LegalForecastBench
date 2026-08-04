# Cycle 1 v4 ranked-reserve materialization

This runbook materializes the already approved v4 ranked-reserve target-100 acquisition authority without rerunning selection, changing frozen evidence, contacting a provider, acknowledging fees, evaluating, freezing, or dispatching.
It uses [`cycle-1-target-100.v4-ranked-reserve.template.json`](../manifests/cycle-1-target-100.v4-ranked-reserve.template.json), not the older v3 coordinator.

## Fixed evidence

Load the canonical approval-checkpoint, successor-root, and parser-root paths from generated local metadata rather than assuming that the current checkout or a parent-directory layout supplies them.
The authenticated checkpoint fixes the repository, cohort, source, and ledger paths; choosing another root must fail replay.

```zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL

approval_checkpoint="${LFB_V4_APPROVAL_CHECKPOINT:?load this canonical path from generated local metadata}"
successor_root="${LFB_V4_SUCCESSOR_ARTIFACT_ROOT:?load this canonical path from generated local metadata}"
private_cycle_root="${LFB_V4_SUCCESSOR_PRIVATE_ROOT:?load this canonical path from generated local metadata}"
parser_root="${LFB_V4_PARSER_ROOT:?load the pinned parser path from generated local metadata}"
test "${approval_checkpoint#/}" != "$approval_checkpoint"
test "${successor_root#/}" != "$successor_root"
test "${private_cycle_root#/}" != "$private_cycle_root"
test "${parser_root#/}" != "$parser_root"
test -f "$approval_checkpoint"
test -d "$parser_root"

approval_root="${approval_checkpoint:h}"
frozen_v4_root="$(jq -er '.checkpoint.verification_inputs.target_cohort_root' "$approval_checkpoint")"
cohort_policy="$(jq -er '.checkpoint.verification_inputs.cohort_policy_path' "$approval_checkpoint")"
fee_schedule="$(jq -er '.checkpoint.verification_inputs.fee_schedule_path' "$approval_checkpoint")"
ledger="$(jq -er '.checkpoint.verification_inputs.canonical_ledger_path' "$approval_checkpoint")"
repo_root="${cohort_policy:h:h}"
source_root="${fee_schedule:h:h}"
authority_root="${ledger:h}"
frozen_artifact_root="$(jq -er '[.input_commitments | keys[] | select(endswith("/02-preparation/target-cohort-config.json")) | sub("/02-preparation/target-cohort-config.json$"; "")] | if length == 1 then .[0] else error("expected one frozen preparation root") end' "$frozen_v4_root/target-cohort-projection.json")"
test "$successor_root" != "$frozen_v4_root"
test "$successor_root" != "$approval_root"
test "$private_cycle_root" != "$frozen_v4_root"
test "$private_cycle_root" != "$approval_root"
test "$successor_root" != "$private_cycle_root"
test "${successor_root#$frozen_v4_root/}" = "$successor_root"
test "${successor_root#$approval_root/}" = "$successor_root"
test "${private_cycle_root#$frozen_v4_root/}" = "$private_cycle_root"
test "${private_cycle_root#$approval_root/}" = "$private_cycle_root"
test "$(git -C "$parser_root" rev-parse --show-toplevel)" = "$parser_root"
test "$(git -C "$parser_root" rev-parse HEAD)" = 9402306972462a5bdd0da7f687c5e6b4cea373a0
test -z "$(git -C "$parser_root" status --porcelain --untracked-files=normal)"
```

Authenticate the immutable public projection before creating anything.
The exact projection contains 100 selected cases, 179 planned purchases, a `$545.95` maximum reservation, and the unchanged `$567.30` cap.

```zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL

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
setopt ERR_EXIT NO_UNSET PIPE_FAIL

test ! -e "$ledger"

uv run legalforecast acquisition verify-purchase-approval \
  --target-cohort-root "$frozen_v4_root" \
  --cohort-policy "$cohort_policy" \
  --fee-schedule "$fee_schedule" \
  --canonical-ledger-path "$ledger" \
  --controlled-private-root "$approval_root" \
  --checkpoint "$approval_checkpoint" \
  --approval-run-card "$approval_root/run-cards/record-purchase-approval.json"
```

Generate the immutable v2 purchase policy and bounded RECAP attempt policy through their supported provider-free commands.
Existing exact bytes resume; different bytes fail closed.

```zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL

mkdir -p -- "$authority_root"

uv run legalforecast acquisition generate-purchase-policy \
  --target-cohort-root "$frozen_v4_root" \
  --cohort-policy "$cohort_policy" \
  --fee-schedule "$fee_schedule" \
  --canonical-ledger-path "$ledger" \
  --controlled-private-root "$approval_root" \
  --checkpoint "$approval_checkpoint" \
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
setopt ERR_EXIT NO_UNSET PIPE_FAIL

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
setopt ERR_EXIT NO_UNSET PIPE_FAIL

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
setopt ERR_EXIT NO_UNSET PIPE_FAIL

uv run legalforecast acquisition run-cycle \
  --config "$successor_root/acquisition-cycle-v4-ranked-reserve.json" \
  --state-root "$successor_root/orchestrator-v4-ranked-reserve" \
  --execute --json
```

Only after secure-gate has activated those exact broker-policy bytes may another provider-free `--execute` invocation initialize the ledger and emit `$authority_root/purchase-ledger-initialization.json`.
That invocation must stop before `purchase-missing-documents` with `paid_boundary_not_authorized`.
Do not add `--allow-paid` or `--allow-network` during materialization.

## Merge and adopt protected Stage B shards

Stage B provider calls run outside the coordinator in the protected official paid-labeling workflow.
Run the OpenAI shard first and the Google shard second through the same sequential encrypted baton and canonical provider journal; never run the two shards in parallel or inject both provider credentials into one job.
Each protected shard must name the complete two-model judge panel and restore its authenticated outputs at exactly these paths:

- `$successor_root/19-stage-b-shards/openai-audit.jsonl`
- `$successor_root/19-stage-b-shards/openai-run-card.json`
- `$successor_root/19-stage-b-shards/google-audit.jsonl`
- `$successor_root/19-stage-b-shards/google-run-card.json`

After both protected shard audit/card pairs exist, reconcile them locally with the credential-free merge command below.
This command verifies the shard cards, journal lineage, complete settled-attempt cross-product, Stage A chain, decision-text commitments, model registries, and provider caps before it writes any selected label.
It does not receive `--execution-provider`, a provider-authority table, an AWS region, or a provider credential.

```zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL

uv run legalforecast acquisition llm-label \
  --output-root "$successor_root/20-stage-b-labels" \
  --selection "$frozen_v4_root/target-cohort-selection.jsonl" \
  --parser-manifest "$successor_root/14-parse/mistral-markdown-conversions.jsonl" \
  --markdown-root "$successor_root/14-parse/markdown" \
  --decision-texts "$successor_root/18-decision-texts/decision-texts.jsonl" \
  --decision-texts-manifest "$successor_root/18-decision-texts/decision-texts-manifest.json" \
  --decision-texts-run-card "$successor_root/18-decision-texts/run-cards/build-decision-texts.json" \
  --prediction-units "$successor_root/17-stage-a-final/prediction-units-finalized.jsonl" \
  --llm-unitization-run-card "$successor_root/15-stage-a-unitize/run-cards/llm-unitize.json" \
  --llm-review-stage-a-run-card "$successor_root/16-stage-a-review/run-cards/llm-review-stage-a.json" \
  --unitization-review-run-card "$successor_root/17-stage-a-final/run-cards/apply-unitization-review.json" \
  --model-registry "$repo_root/model_registries/cycle-1-stage-b-judges-2026-07-12.json" \
  --evaluated-model-registry "$repo_root/model_registries/cycle-1-2026-06-30.json" \
  --model-key openai:gpt-5.4-mini-2026-03-17 \
  --model-key google:gemini-3.5-flash \
  --provider-cycle-caps "$successor_root/01-provider-authority/provider-cycle-caps.json" \
  --provider-journal "$private_cycle_root/paid-labeling/provider-attempts.sqlite3" \
  --provider-shard-audit "$successor_root/19-stage-b-shards/openai-audit.jsonl" \
  --provider-shard-run-card "$successor_root/19-stage-b-shards/openai-run-card.json" \
  --provider-shard-audit "$successor_root/19-stage-b-shards/google-audit.jsonl" \
  --provider-shard-run-card "$successor_root/19-stage-b-shards/google-run-card.json" \
  --labels-output "$successor_root/20-stage-b-labels/labels.jsonl" \
  --audit-output "$successor_root/20-stage-b-labels/llm-label-audit.jsonl" \
  --lawyer-review-queue-output "$successor_root/20-stage-b-labels/lawyer-review-queue.jsonl" \
  --run-card-output "$successor_root/20-stage-b-labels/run-cards/llm-label.json" \
  --execute --resume
```

The template deliberately retains the conservative `model_provider` boundary for this externally completed merge so the coordinator cannot execute it during an ordinary provider-free cycle advance.
Adopt the authenticated completion without invoking the handler or granting any provider authority:

```zsh
uv run legalforecast acquisition run-cycle \
  --config "$successor_root/acquisition-cycle-v4-ranked-reserve.json" \
  --state-root "$successor_root/orchestrator-v4-ranked-reserve" \
  --adopt-next-completed --json
```

Do not combine `--adopt-next-completed` with `--execute`, any `--allow-*` flag, or a changed output path.
The adoption must authenticate the exact next unreceipted `merge-stage-b-provider-shards` run card and outputs; a missing, drifted, partial, or unbound shard fails closed without a provider call.

Evaluation, freeze, dispatch, and publication are absent from the template and remain unauthorized.
