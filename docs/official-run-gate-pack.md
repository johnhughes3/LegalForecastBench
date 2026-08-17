# Official-run gate pack (Lane F4, preparation only)

> [!CAUTION]
> **DO NOT EXECUTE.** This is a preparation and review artifact only. Do not
> dispatch workflows, resolve credentials, access provider infrastructure, or
> run an official cycle from these commands without the separately recorded
> human approvals and protected-environment evidence.

This pack compresses the remaining operator work for the first official cycle. It is intentionally a preparation artifact: publishing the reviewed workflow changes through PR #772 did not apply infrastructure, read or write secrets, dispatch a protected workflow, call a model provider, purchase a document, or run an official cycle.

## Stop condition and ownership

The official first cycle (`ur6`) remains blocked on `ue7.32` (rehearsal, failure drill, and John’s sign-off). `ue7.32` remains behind the protected infrastructure and workflow gates `hckb.15`, `5qd6.119`, `5qd6.32`, and `5qd6.101`. Secure-gate is down under the standing repository instruction; the workflow files were published only after explicit operator authorization, and landing them is not evidence that any operational gate ran or passed.

The corpus dependency is strict: Lane F2 must finish Stage A and Gate 3, then freeze the exact corpus and release inputs. The official evaluation consumes those frozen bytes; it must not start from a fixture, an inferred successor, or a mutable working tree.

## Evidence status

| Status | Evidence | Boundary |
| --- | --- | --- |
| Green — verified today | `actionlint` on `run-benchmark.yaml`, `official-provider-cell.yaml`, and `official-s3-access-validation.yaml`; 0 diagnostics | Static workflow syntax only |
| Green — verified today | Official workflow/infra/environment contract set: `uv run pytest -q tests/test_official_provider_workflow.py tests/test_official_eval_matrix_workflow.py tests/test_official_eval_infra.py tests/test_official_eval_environment_manifest.py` — 61 passed; runbook contract: `uv run pytest -q tests/test_official_run_runbook.py` — 30 passed; integrated fixture smoke: `uv run pytest -q tests/test_integrated_fixture_pipeline.py` — 1 passed | Provider-free tests and fixture pipeline only |
| Green — verified today | `uv run pytest -q tests/test_downstream_rehearsal.py` — 92 passed; exact-100 public fixture chain included | Fixture-only rehearsal machinery; no live corpus, provider, or infrastructure |
| Green — verified today | `terraform fmt -check -recursive infra/official-eval`; backend-free `terraform init`; `terraform validate` | Local Terraform code shape only |
| Yellow — fixture only | The `hfk` downstream rehearsal and staged-rollout tests exercise deterministic response fixtures, packet exclusion, zero review queues, zero provider billing, and receipt byte identity | Not evidence of a live corpus, provider, S3, OIDC, or protected environment |
| Yellow — non-authoritative | A local scratch offline official-eval plan had `Plan: 23 to add, 0 to change, 0 to destroy.` against placeholder identifiers in a temporary copy; SHA-256 `3b66966009736cf1ff1f67a49f8e655aea711ec9274603d1a11b8723dd956a8d` | Structural shape only; not an AWS plan and not apply authorization |
| Red — John gate | Existing-resource import, protected plan review, and apply for `hckb.15` | Requires the protected infrastructure environment, remote state, hidden identifiers, and John’s approval |
| Red — John gate | Workflow-bearing publication and sanctioned dispatches (`5qd6.119`, `5qd6.32`, `5qd6.101`) | No agent PR or main publication while secure-gate is down |
| Red — John gate | Provider-free live OIDC/S3 validation, bounded provider smoke, rehearsal sign-off, and `ur6` | Requires applied AWS/GitHub state, Stage A + Gate 3 frozen corpus, and human authority |

## Draft branch and workflow changes

The draft was prepared on `feat/code2`, originally stacked on `feat/code`. After the parent landed, PR #772 was retargeted to `main` for exact-head review and landing.

The draft changes are:

- `.github/workflows/official-provider-cell.yaml` — new reusable provider-cell workflow. It accepts one provider, binds the job environment from the allowlisted `environment_name`, scopes the generic `PROVIDER_API_KEY` only to the provider shell, keeps packet/result AWS authority in the cell role, clears AWS credentials before receipt upload, and uploads receipt-only Actions artifacts.
- `.github/workflows/run-benchmark.yaml` — partitions the matrix into `run-openai`, `run-anthropic`, and `run-gemini` reusable-workflow lanes; fan-in waits for all three and consumes completion receipts only. Matrix and fan-in jobs do not reference provider API-key secrets.
- `tests/test_official_provider_workflow.py` and `tests/test_official_eval_matrix_workflow.py` — static provider-boundary, receipt, matrix, and immutable-action contracts.
- `tests/test_official_eval_infra.py` and `tests/official_infra_trust_helpers.py` — trust satisfiability checks now cover the reusable provider-cell environment input and caller mappings.

Every external action in the three official provider-smoke workflows is pinned to a full commit SHA with a version/provenance comment:

| Action | Full SHA | Comment |
| --- | --- | --- |
| `actions/checkout` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `v7.0.1` |
| `actions/download-artifact` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | `v8.0.1` |
| `actions/upload-artifact` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | `v7.0.0` |
| `astral-sh/setup-uv` | `37802adc94f370d6bfd71619e3f0bf239e1f3b78` | `v7.1.6` |
| `aws-actions/configure-aws-credentials` | `e6de054238d6b7531b4efff3b6587d9aade6a06c` | `v6.2.3` |

`official-s3-access-validation.yaml` already uses the same full-SHA pins and was not changed by this lane.

### Workflow publication record

The reviewed branch and PR already exist; John does not need to repeat the publication step. These are the generic commands corresponding to the completed publication record:

```bash
F4_COMMIT_SHA="$(git rev-parse feat/code2)"
git show --stat --oneline "$F4_COMMIT_SHA"
git push origin HEAD:refs/heads/feat/code2
export GITHUB_REPOSITORY="<owner>/<repository>"
gh pr create --repo "$GITHUB_REPOSITORY" \
  --base main --head feat/code2 \
  --title "feat(eval): prepare provider-isolated official run gates" \
  --body 'F4 reviewed workflow drafts only. The F4 agent performed no infrastructure apply, protected dispatch, provider call, secret operation, or official run. The PR remains blocked until hckb.15, 5qd6.119, the live validation and smoke gates, and ue7.32 sign-off complete.'
```

The PR body records that the workflow files are reviewed drafts, that F4 itself performed no infrastructure apply or provider call, and that the operational sequence remains blocked until `hckb.15`, `5qd6.119`, the live validation/smoke gates, and `ue7.32` sign-off complete. Do not split, weaken, or force-push the draft.

An earlier non-workflow-capable push was rejected before updating the remote ref:

```text
! [remote rejected] feat/code2 -> feat/code2 (refusing to allow a GitHub App to create or update workflow `.github/workflows/official-provider-cell.yaml` without `workflows` permission)
error: failed to push some refs to 'https://github.com/<owner>/<repository>'
```

That rejected attempt performed no remote mutation. The later operator-authorized publication created PR #772 without a force-push or path split. Before merge, verify that the PR head equals the locally validated commit; after merge, verify the merge commit on remote `main`. Neither proof authorizes an infrastructure apply or workflow dispatch.

All GitHub CLI snippets below assume `GITHUB_REPOSITORY` is exported as the current `<owner>/<repository>` slug; they never require a hard-coded account identifier.

## `hckb.15`: protected import, plan, and apply

The canonical protected workflow is `.github/workflows/official-provider-authority-infra.yaml`. It runs only from `main`, requires the pre-created and reviewer-protected infrastructure environment, uses encrypted remote state and an age-encrypted plan artifact, validates the closed address/action allowlist, and refuses stale `main` before any apply.

The import and exact saved-plan path below is the protected implementation merged by PR #703 (merge `2f4ae2c8e9e3f49cdd53d4cc6d1d701aa7c5308c`). F4 only prepares the operator inputs and records the expected evidence; it does not dispatch or apply that workflow.

### 1. Prepare the protected identity commitments

John supplies these values from the protected infrastructure environment without printing their raw contents: `LFB_AWS_REGION`, `LFB_INFRA_OPERATOR_ROLE_ARN`, `LFB_TERRAFORM_STATE_BUCKET`, `LFB_TERRAFORM_STATE_KEY_PREFIX`, `LFB_TERRAFORM_STATE_KMS_KEY_ID`, `LFB_INFRA_PLAN_AGE_RECIPIENT`, `LFB_GITHUB_OIDC_PROVIDER_ARN`, `LFB_PROVIDER_AUTHORITY_TABLE_ARN`, `LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256`, `LFB_PACKET_BUCKET`, and `LFB_RESULTS_BUCKET`.

The workflow’s identity formulas are reproduced below so request commitments can be computed in the operator session without exposing identifiers:

```bash
set -euo pipefail
# Use the exact current-main SHA that contains PR #703's protected infra
# workflow; F4 workflow pins are published only after this apply completes.
RELEASE_SHA=<exact-main-sha-before-f4-workflow-publication>
MODULE=official-eval
STATE_KEY="${LFB_TERRAFORM_STATE_KEY_PREFIX%/}/official-eval/terraform.tfstate"
OPERATOR_ROLE_IDENTITY_SHA256="$(jq -cn --arg role "$LFB_INFRA_OPERATOR_ROLE_ARN" '{role:$role}' | sha256sum | cut -d' ' -f1)"
STATE_BACKEND_IDENTITY_SHA256="$(jq -cn \
  --arg bucket "$LFB_TERRAFORM_STATE_BUCKET" --arg key "$STATE_KEY" \
  --arg region "$LFB_AWS_REGION" --arg kms_key "$LFB_TERRAFORM_STATE_KMS_KEY_ID" \
  '{bucket:$bucket,key:$key,region:$region,kms_key:$kms_key}' | sha256sum | cut -d' ' -f1)"
TERRAFORM_INPUT_IDENTITY_SHA256="$(jq -cn \
  --arg module "$MODULE" --arg region "$LFB_AWS_REGION" \
  --arg oidc "$LFB_GITHUB_OIDC_PROVIDER_ARN" \
  --arg identity "$LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256" \
  --arg packet_bucket "$LFB_PACKET_BUCKET" --arg results_bucket "$LFB_RESULTS_BUCKET" \
  --arg table "$LFB_PROVIDER_AUTHORITY_TABLE_ARN" \
  '{module:$module,region:$region,oidc:$oidc,identity:$identity,packet_bucket:$packet_bucket,results_bucket:$results_bucket,table:$table}' | sha256sum | cut -d' ' -f1)"
```

### 2. Inventory and import every existing official-eval resource

The import address list is conditional on the live bucket subresources. Before
dispatching any import, the designated operator performs a read-only inventory
of the two protected buckets and removes absent optional resources from the
dispatch set. In particular, `get-bucket-lifecycle-configuration` and
`get-bucket-policy` return a documented absence when no lifecycle configuration
or bucket policy exists; that absence is not an import target.

The inventory result is retained as operator evidence and is used to construct
`EXISTING_IMPORT_ADDRESSES` from the closed list below. Every IAM, bucket, and
present lifecycle/policy address remains exact; only an address whose live
object is absent is omitted.

Import is one protected workflow dispatch per address. The closed address set is:

```text
aws_iam_role.cell
aws_iam_role.fan_in
aws_iam_role_policy.cell_provider_authority
aws_iam_role_policy.cell_storage
aws_iam_role_policy.fan_in_storage
aws_iam_role_policies_exclusive.cell
aws_iam_role_policies_exclusive.fan_in
aws_iam_role_policy_attachments_exclusive.cell
aws_iam_role_policy_attachments_exclusive.fan_in
aws_s3_bucket.packet
aws_s3_bucket.results
aws_s3_bucket_lifecycle_configuration.packet
aws_s3_bucket_lifecycle_configuration.results
aws_s3_bucket_ownership_controls.packet
aws_s3_bucket_ownership_controls.results
aws_s3_bucket_policy.packet
aws_s3_bucket_policy.results
aws_s3_bucket_public_access_block.packet
aws_s3_bucket_public_access_block.results
aws_s3_bucket_server_side_encryption_configuration.packet
aws_s3_bucket_server_side_encryption_configuration.results
aws_s3_bucket_versioning.packet
aws_s3_bucket_versioning.results
```

The fixed role/policy IDs are defined in `scripts/official_infra_contract.py`; bucket IDs come only from protected variables. The following operator function computes the raw-ID SHA-256 and canonical import-authorization commitment, then dispatches the exact request without printing the raw import ID:

```bash
import_authorized() {
  address="$1"
  case "$address" in
    aws_iam_role.cell) import_id=legalforecastbench-official-eval ;;
    aws_iam_role.fan_in) import_id=legalforecastbench-official-eval-fan-in ;;
    aws_iam_role_policy.cell_provider_authority) import_id=legalforecastbench-official-eval:official-eval-cell-exact-provider-authority ;;
    aws_iam_role_policy.cell_storage) import_id=legalforecastbench-official-eval:official-eval-cell-storage ;;
    aws_iam_role_policy.fan_in_storage) import_id=legalforecastbench-official-eval-fan-in:official-eval-fan-in-storage ;;
    aws_iam_role_policies_exclusive.cell|aws_iam_role_policy_attachments_exclusive.cell) import_id=legalforecastbench-official-eval ;;
    aws_iam_role_policies_exclusive.fan_in|aws_iam_role_policy_attachments_exclusive.fan_in) import_id=legalforecastbench-official-eval-fan-in ;;
    aws_s3_bucket.packet|aws_s3_bucket_public_access_block.packet|aws_s3_bucket_ownership_controls.packet|aws_s3_bucket_server_side_encryption_configuration.packet|aws_s3_bucket_versioning.packet|aws_s3_bucket_lifecycle_configuration.packet|aws_s3_bucket_policy.packet) import_id="$LFB_PACKET_BUCKET" ;;
    aws_s3_bucket.results|aws_s3_bucket_public_access_block.results|aws_s3_bucket_ownership_controls.results|aws_s3_bucket_server_side_encryption_configuration.results|aws_s3_bucket_versioning.results|aws_s3_bucket_lifecycle_configuration.results|aws_s3_bucket_policy.results) import_id="$LFB_RESULTS_BUCKET" ;;
    *) echo "unallowlisted address: $address" >&2; return 1 ;;
  esac
  import_id_sha256="$(printf %s "$import_id" | sha256sum | cut -d' ' -f1)"
  authorization_sha256="$(uv run python - "$RELEASE_SHA" "$address" "$import_id_sha256" "$OPERATOR_ROLE_IDENTITY_SHA256" "$STATE_BACKEND_IDENTITY_SHA256" "$TERRAFORM_INPUT_IDENTITY_SHA256" <<'PY'
import sys
from scripts.official_infra_contract import import_authorization_sha256
print(import_authorization_sha256(
    release_sha=sys.argv[1], module="official-eval", address=sys.argv[2],
    import_id_sha256=sys.argv[3], operator_role_identity_sha256=sys.argv[4],
    state_backend_identity_sha256=sys.argv[5], terraform_input_identity_sha256=sys.argv[6]))
PY
  )"
  gh workflow run .github/workflows/official-provider-authority-infra.yaml \
    --repo "$GITHUB_REPOSITORY" --ref main \
    -f operation=import -f module=official-eval -f release_sha="$RELEASE_SHA" \
    -f import_address="$address" -f import_id_sha256="$import_id_sha256" \
    -f import_authorization_sha256="$authorization_sha256" \
    -f import_operator_role_identity_sha256="$OPERATOR_ROLE_IDENTITY_SHA256" \
    -f import_state_backend_identity_sha256="$STATE_BACKEND_IDENTITY_SHA256" \
    -f import_terraform_input_identity_sha256="$TERRAFORM_INPUT_IDENTITY_SHA256"
}

# Preparation-only pseudocode for the protected operator session. The helper
# must not dispatch an address that the inventory proved absent.
EXISTING_IMPORT_ADDRESSES=(...closed addresses with present optional objects...)
for address in "${EXISTING_IMPORT_ADDRESSES[@]}"; do
  import_authorized "$address"
done
```

John runs `import_authorized <address>` once for each of the 23 addresses above and waits for the protected approval and `gh run watch <IMPORT_RUN_ID> --exit-status`. Expected evidence is a successful `state-binding` check and `import-receipt.json` with `result` `imported` or `already_present`; no apply is performed by an import run. Any non-absent AWS error stops reconciliation; it is not suppressed.

### 3. Read-only protected plan

After all imports and live bucket-policy/lifecycle/IAM inventory have been reconciled into Terraform, dispatch exactly:

```bash
gh workflow run .github/workflows/official-provider-authority-infra.yaml \
  --repo "$GITHUB_REPOSITORY" --ref main \
  -f operation=plan -f module=official-eval -f release_sha="$RELEASE_SHA"
```

Watch the resulting run to completion. Successful evidence is `terraform validate`, `terraform plan`, `official_infra_contract.py validate-plan`, encrypted plan upload, and sensitive-file cleanup. Capture the run ID/attempt, artifact name `provider-authority-infra-plan-official-eval-<run_id>-<run_attempt>`, GitHub artifact digest, plaintext plan SHA-256 from `plan-receipt.json`, and the redacted `resource_changes` list. The plan is acceptable only when the contract validator accepts every address, contains no destroy/replace action, and preserves every pre-existing authoritative bucket policy/lifecycle/inline/attachment member. The synthetic 23-create plan in this pack is not a substitute.

### 4. John-only apply of that exact saved plan

Apply is not a local `terraform apply`. After John reviews the saved plan and approves the protected environment, use the exact plan run identity and digest:

```bash
PLAN_RUN_ID=<successful-plan-run-id>
PLAN_RUN_ATTEMPT=<exact-plan-run-attempt>
PLAN_ARTIFACT_DIGEST=<sha256:...-from-GitHub-artifact-metadata>
PLAN_FILE_SHA256=<64-lowercase-hex-from-plan-receipt.json>
PLAN_ARTIFACT_NAME="provider-authority-infra-plan-official-eval-${PLAN_RUN_ID}-${PLAN_RUN_ATTEMPT}"

gh workflow run .github/workflows/official-provider-authority-infra.yaml \
  --repo "$GITHUB_REPOSITORY" --ref main \
  -f operation=apply -f module=official-eval -f release_sha="$RELEASE_SHA" \
  -f plan_run_id="$PLAN_RUN_ID" -f plan_run_attempt="$PLAN_RUN_ATTEMPT" \
  -f plan_artifact_name="$PLAN_ARTIFACT_NAME" \
  -f plan_artifact_digest="$PLAN_ARTIFACT_DIGEST" \
  -f plan_file_sha256="$PLAN_FILE_SHA256"
```

Expected protected output is successful exact-artifact authentication, age decryption and SHA-256 verification, a fresh `main` equality check, `terraform apply -auto-approve <exact-plan>`, encrypted Terraform outputs, and a redacted `apply-receipt.json`. If any precondition fails, the workflow stops before apply. John records the apply run/attempt, receipt, output digest, and exact role/environment variables assigned server-side; this lane does not read or write those values.

## `5qd6.119`: post-apply provider-free dispatches

After the applied outputs and environment variables are assigned, John dispatches the existing-object validation from the exact `main` SHA. The five object values are operator inputs; the agent must not discover or print them:

```bash
gh workflow run .github/workflows/official-s3-access-validation.yaml \
  --repo "$GITHUB_REPOSITORY" --ref main \
  -f release_sha="$RELEASE_SHA" \
  -f packet_object_key="<existing-model-packets-key>" \
  -f manifest_object_key="<existing-manifests-key>" \
  -f per_case_object_key="<existing-per-case-metrics-key>" \
  -f per_case_version_id="<exact-s3-version-id>" \
  -f shard_receipt_object_key="<existing-shard-receipt-key>"
```

Expected evidence is successful cell-role positive reads and fan-in-role positive exact-version/receipt reads, followed by `AccessDenied` for the listed report-prefix write, bucket-wide list, delete, ACL, object-version, and private-prefix negative controls. A successful workflow proves only those operations; it does not prove provider calls or the full DynamoDB transaction contract.

Run the provider-free fan-in verification only after a successful shard receipt and exact source dispatch attempt are available:

```bash
gh workflow run .github/workflows/fan-in-publish.yaml \
  --repo "$GITHUB_REPOSITORY" --ref main \
  -f release_sha="$RELEASE_SHA" \
  -f cycle_id="<frozen-cycle-id>" \
  -f freeze_bundle_path="manifests/<frozen-cycle-id>.freeze.json" \
  -f source_dispatch_run_id="<run-benchmark-run-id>" \
  -f source_dispatch_run_attempt="<exact-source-attempt>" \
  -f verify_only=true \
  -f artifact_retention_days=30
```

The expected terminal artifact is `fan-in-report.json` with the accepted receipt map, exact S3 VersionId/hash commitments, frozen artifact hashes, derived counts, and no canonical report write. For the bounded provider-authority smoke, John uses the separately protected workflow and its exact main SHA; no provider API key or smoke result is available to this lane.

`RELEASE_SHA` above is the pre-publication tip used by the Terraform import/plan/apply dispatches. Publishing the F4 workflow pins advances `main`, and `official-paid-labeling-authority-smoke.yaml` requires `release_sha` to equal the dispatch `GITHUB_SHA`. Recompute after publication instead of reusing the infra SHA:

```bash
SMOKE_RELEASE_SHA="$(git ls-remote origin refs/heads/main | cut -f1)"
gh workflow run .github/workflows/official-paid-labeling-authority-smoke.yaml \
  --repo "$GITHUB_REPOSITORY" --ref main \
  -f release_sha="$SMOKE_RELEASE_SHA"
```

## `ue7.32`: annotated fixture rehearsal and failure drill

The supported fixture path is the runbook’s `hfk` machinery. It is provider-free, does not use infrastructure, and cannot produce an official-eligible artifact. The following is the execution map used for this prep:

| Step | Command/evidence | Status |
| --- | --- | --- |
| Contract and runbook validation | `uv run pytest -q tests/test_official_run_runbook.py tests/test_downstream_rehearsal.py tests/test_integrated_fixture_pipeline.py` | Green today; 123 provider-free fixture tests passed |
| Authenticated fixture cohort projection | `uv run legalforecast acquisition project-target-cohort ... --execute --no-resume` from the runbook | Yellow until Lane F2 supplies authenticated free-clearance inputs; no hand-authored substitute is allowed |
| Fixture purchase-policy/ledger path | `record-purchase-approval`, `verify-purchase-approval`, `generate-purchase-policy`, `generate-recap-fetch-broker-policy`, `init-purchase-ledger`, then `purchase-missing-recap-fetch --courtlistener-fixture ... --purchase-broker-fixture ... --acknowledge-pacer-fees` | Yellow fixture-only; the fee flag is mechanical here and must record `paid_activity_requested=false`, `paid_activity_executed=false`; no PACER/provider call |
| Fixture recovery, disclosure, materialization, and parser | Runbook commands `recover-purchased`, `plan-disclosure-provenance`, `record-disclosure-review-decisions`, `clear-provenance-disclosures`, `materialize-cohort-documents`, `plan-parse-documents`, `parse-documents` | Yellow fixture-only; authenticated source/clearance inputs and private roots are required |
| Eight downstream fixture stages | `rehearsal-build-decision-texts`, `rehearsal-stage-a-unitize`, `rehearsal-stage-a-review`, `rehearsal-stage-a-apply`, `rehearsal-stage-b-label`, `rehearsal-stage-b-apply`, `rehearsal-plan-packet-inputs`, `rehearsal-build-packets` with the exact shared `rehearsal_args` in `docs/official-run-runbook.md` | Yellow fixture-only; success requires exact target counts, zero pending review queues, `provider_journal_created=false`, `provider_billing_usd="0.00"`, and `packet_outcome_material_excluded=true` |
| Fixture finalization | `uv run legalforecast acquisition finalize-rehearsal-corpus ...` | Yellow fixture-only; output must retain `official_eligible=false` |
| Staged-rollout failure drill | Freeze fixture A, run/aggregate fixture A, amend with fixture B, fan-in the union, and byte-compare every A artifact as specified in the runbook | Red for live sign-off; fixture assertions are covered by `tests/test_official_run_runbook.py` |
| Live provider-free OIDC/S3 validation | John dispatches `official-s3-access-validation.yaml` from the exact `main` SHA after `hckb.15` apply, supplying existing packet/manifest/per-case VersionId/shard-receipt keys | Red on `hckb.15` + `5qd6.119`; no agent dispatch |
| Provider smoke and official run | John executes the bounded provider smoke, then `Run Benchmark` dry-run and official shards, followed by `Fan In Official Shards` | Red on applied infrastructure, workflow publication, provider authority, Stage A + Gate 3 freeze, and sign-off |

The fixture runbook intentionally never self-adjudicates a nonempty review queue. Any nonempty Stage A or Stage B fixture queue is a failed rehearsal that requires correction or a John-review bead.

## John-only PACER broker steps (`5qd6.57.x`)

The `[JOHN/OPERATOR]` items remain untouched by F4. They are context in the gate chain, not implementation work for this branch:

- `5qd6.57.1`: provision the broker-only RECAP identity and reconciliation principals through secure-gate; do not expose PACER credentials to this repository or Agent Sandbox.
- `5qd6.57.12`: apply the broker infrastructure and populate the exact-five client view (`RECAP_FETCH_BROKER_URL`, `RECAP_FETCH_BROKER_MACHINE_ID`, `RECAP_FETCH_BROKER_PRIVATE_KEY_JWK`, `RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON`, and `RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256`; optional timeout plus the separately scoped CourtListener token remain operator-managed).
- `5qd6.57.13`: pass the signed non-purchase end-to-end verification; no paid request or fee acknowledgement is implied.
- `5qd6.57.14`: restage the Broker/Admin workflow-policy tombstone for the current-main transition.

F4 performed none of these operations and did not read any broker credential or secret value.

## Strict sequencing and timing

```text
Lane F2 Stage A + Gate 3 frozen corpus
        |  (dependency; attorney/review queues can take hours to days)
        v
hckb.15 protected import -> reviewed plan -> John-approved apply
        |  (one operator sitting, typically 45-90 minutes plus approvals)
        v
5qd6.32 / 5qd6.101 workflow pins published on main
        |  (15-30 minutes once workflow-capable authority is available)
        v
5qd6.119 provider-free OIDC/S3 validation and fan-in verification
        |  (20-45 minutes; exact existing object/version inputs required)
        v
Bounded one-provider smoke and provider-authority smoke
        |  (30-60 minutes; provider spend and smoke freeze are John-gated)
        v
ue7.32 fixture rehearsal + staged-rollout failure drill
        |  (about 1-2 hours when the authenticated fixture packet is ready)
        v
John reviews evidence and signs off ue7.32
        |
        v
ur6 official Cycle 1 shards -> immutable receipts -> provider-free fan-in/publication
        |  (run duration follows the frozen corpus/model matrix; do not estimate from fixture timing)
```

The first two lines are a hard dependency, not parallel work: the official run consumes the frozen corpus and cannot be made ready by infrastructure alone. Coordinate exact Stage A/Gate 3 completion and the freeze SHA with Lane F2 (`MagentaGorge`) before starting the operator sitting.

## One ordered checklist for John

1. Confirm Lane F2’s Stage A + Gate 3 completion, exact frozen corpus, model registry, execution policy, and the current-main release SHA.
2. Run all approved `hckb.15` imports; reconcile live bucket policies/lifecycle and IAM attachments; dispatch and save the protected `official-eval` plan.
3. Review the complete saved plan and apply only that exact plan through the protected workflow; record the redacted apply receipt and outputs.
4. Publish this branch through the workflow-capable path, then merge the stacked workflow drafts so `main` contains the exact pinned workflows.
5. Set the reviewed GitHub environment variables and secret-name inventory server-side; keep fan-in provider-free and verify the Bedrock runtime choice explicitly.
6. Dispatch `official-s3-access-validation.yaml` and the provider-free fan-in verification from the exact post-publication `main` SHA; retain run IDs and terminal receipts.
7. Run the bounded provider-authority and one-provider smoke under the dedicated smoke freeze/prefix; stop on any omission-denial or identity mismatch.
8. Execute the fixture rehearsal and staged-rollout failure drill; retain the final summary, run card, and byte-identity evidence.
9. Review and sign `ue7.32`; only then dispatch `ur6` official shards with `dry_run=true` first, explicit projected-cost ceiling, `shard_only=true`, and `resume_existing_results=true`.
10. Fan in only accepted immutable shard receipts, prove exact source attempt/release identity, and publish the canonical report through the provider-free fan-in path.
