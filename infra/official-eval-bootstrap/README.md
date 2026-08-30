# One-time official-evaluation AWS bootstrap

This Terraform root owns the repository-specific trust anchor consumed by `.github/workflows/official-provider-authority-infra.yaml`: one private versioned state bucket, one customer-managed KMS key and alias, and the exact environment-bound infrastructure operator role.
It consumes and verifies an existing account-level GitHub Actions OIDC provider without importing or owning that shared resource.
The routine workflow cannot apply this root and its role has no permission to change its own trust or policy, administer the shared OIDC provider, bucket, KMS key, or bootstrap state, or broaden the three reviewed downstream roots.

Creating or importing this root does not authorize AWS work.
The one-time apply requires separately authorized human/operator AWS credentials, independent review of the exact plan, and protected local state custody until remote migration is proven complete.

The rendered operator policy keeps the durable `legalforecastbench-official-eval-provider-authority` table in its existing exact, non-destructive statement and grants a separate exact-resource statement for the public fixed-name canary `legalforecastbench-official-labeling-authority-smoke-canary`. The canary statement grants only the Terraform management actions required to provision and inspect the negative-control resource; it does not grant the labeling or evaluation roles access to the canary. Disposal remains a separately reviewed follow-up because the current protected plan contract rejects destructive actions.
Initial creation of the `legalforecastbench-official-eval`, `legalforecastbench-official-eval-fan-in`, and `legalforecastbench-official-eval-manifest-staging` roles and issuance of their inline policies are one-time human-admin operations against an exact reviewed plan. After provisioning, the routine OIDC operator can only refresh those three exact role resources and use `UpdateRole` for reviewed `MaxSessionDuration` convergence; it cannot create roles, write policies or trust, tag roles, delete roles, pass roles, manage permissions boundaries, or act on any other IAM resource.

The manifest-staging statement is deliberately the read-only refresh set rather than the create-and-manage set the labeling role receives. The labeling role's whole authority is item operations against one DynamoDB spend-ledger table; the manifest-staging role holds `kms:Decrypt` and `kms:GenerateDataKey` on the artifacts key plus create-once object writes under the official results and packet prefixes, so it sits on the cell/fan-in side of that line. The packet and results buckets are governed by resource policies naming only these OIDC roles, so an operator that could rewrite this role's trust or inline policy could mint the only credential in existence that reads or writes the official corpus. That is the escalation the read-only set forecloses. The five granted verbs are exactly what `terraform import` and a converged no-op plan need: `GetRole` for the role, `GetRolePolicy` for the inline policy, `ListRolePolicies` and `ListAttachedRolePolicies` for the two `*_exclusive` ownership resources, and `UpdateRole` for reviewed `MaxSessionDuration` convergence. `DeleteRolePolicy` and `DetachRolePolicy` are withheld: the `*_exclusive` resources need them only to reconcile drift, and drift here should fail closed with an `AccessDenied` that a human admin resolves, not be silently repaired by an unattended workflow run.

## Operator role trust surface

The operator trust pins five conditions: `aud`, the environment-qualified `sub`, `repository`, `ref`, and `environment`.
Do not delete `repository`, `ref`, or `environment`. They are documented AWS condition keys for the GitHub IdP, they are populated on protected-environment tokens, and they are satisfiable here because the operator job binds the `legalforecastbench-official-provider-authority-infra` environment and runs only from `refs/heads/main`. Reviews have twice argued they are unmatchable; [docs/github-aws-oidc-trust-claims.md](../../docs/github-aws-oidc-trust-claims.md) records the primary sources that settle it, and `tests/test_official_eval_bootstrap_infra.py` binds directly to the production locals, variable defaults, environment manifest, and the role-assuming `operate` job, failing if a condition is dropped, a pinned value drifts, or that job stops producing a claim — with in-suite mutation tests proving the fence discriminates.

## Protected first apply

Use an exact reviewed commit on a trusted operator machine.
Keep the variable file and state directory outside the checkout, do not print Terraform state or outputs into logs, and do not place AWS credentials in a variable file.
Set `github_repository` and `github_oidc_provider_arn` in that protected variable file to the exact reviewed GitHub `owner/repository` and verified existing account-level provider ARN; neither input has an account-specific default.
Copy the exact root into that protected directory so Terraform's default local state is both discoverable by the later migration and never written beneath the repository checkout:

```bash
set -euo pipefail
umask 077
state_dir="${LFB_PROTECTED_BOOTSTRAP_STATE_DIR:?set a protected directory outside the checkout}"
var_file="${LFB_BOOTSTRAP_VAR_FILE:?set a protected external tfvars path}"
root_dir="$state_dir/root"
tf_data_dir="$state_dir/tfdata"
install -d -m 0700 "$state_dir" "$tf_data_dir"
test -f "$var_file"
test ! -e "$root_dir"
cp -rf infra/official-eval-bootstrap "$root_dir"
test ! -e "$root_dir/backend.s3.tf"

TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir="$root_dir" init -backend=false -input=false
terraform -chdir="$root_dir" fmt -check
TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir="$root_dir" validate
```

Inventory the account-level provider for `https://token.actions.githubusercontent.com` before planning.
Verify that its sole audience is `sts.amazonaws.com`, determine which other stacks and roles depend on it, and supply its exact ARN as `github_oidc_provider_arn`.
This root reads the provider as a data source and fails unless its account, partition, URL, and audience match; never import it, create a duplicate, or transfer ownership from the account foundation.
If it is absent, establish it through the separately reviewed account-foundation owner before continuing.

Apply the same import-first rule to every resource that already exists.
Inventory and import each applicable address with its provider-defined ID before planning:

```bash
set -euo pipefail
tf_import() {
  TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" import \
    -input=false -var-file="$var_file" "$1" "$2"
}

tf_import aws_s3_bucket.terraform_state "<exact-bucket-name>"
tf_import aws_s3_bucket_public_access_block.terraform_state "<exact-bucket-name>"
tf_import aws_s3_bucket_ownership_controls.terraform_state "<exact-bucket-name>"
tf_import aws_s3_bucket_server_side_encryption_configuration.terraform_state "<exact-bucket-name>"
tf_import aws_s3_bucket_versioning.terraform_state "<exact-bucket-name>"
tf_import aws_s3_bucket_policy.terraform_state "<exact-bucket-name>"
tf_import aws_kms_key.terraform_state "<exact-kms-key-id>"
tf_import aws_kms_alias.terraform_state "alias/legalforecastbench-official-terraform-state"
tf_import aws_iam_role.operator "legalforecastbench-official-provider-authority-infra"
tf_import aws_iam_role_policy.operator "legalforecastbench-official-provider-authority-infra:reviewed-lfb-terraform-roots"
tf_import aws_iam_role_policies_exclusive.operator "legalforecastbench-official-provider-authority-infra"
tf_import aws_iam_role_policy_attachments_exclusive.operator "legalforecastbench-official-provider-authority-infra"
```

Import the inline and exclusive-policy ownership resources only after verifying that the role has no unrelated inline or attached policy that this root would remove.
Stop on any ownership ambiguity or unsupported import result rather than planning a replacement.
Before any `terraform plan`, complete the inventory and required imports above.
Save, review, and apply one exact local-state plan; a `terraform apply` is permitted only for the separately authorized saved plan:

```bash
set -euo pipefail
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" plan \
  -input=false \
  -var-file="$var_file" \
  -out="$state_dir/official-eval-bootstrap.tfplan"

# Run only after the exact saved plan receives separate authorization.
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" apply \
  -input=false \
  "$state_dir/official-eval-bootstrap.tfplan"
```

Verify the live bucket public-access block, ownership controls, versioning, TLS-only policy and exact KMS default encryption; verify KMS rotation and policy; verify the OIDC audience; and inspect the operator role's exact trust and inline policy.
Do not infer these properties from a successful apply.

## Migrate the bootstrap state

Use the exact KMS key ARN from the protected apply evidence, not the mutable alias.
The bootstrap state key is intentionally outside the routine role's state prefix:
Run `terraform init -migrate-state` only after the live bootstrap controls have been independently verified:

```bash
set -euo pipefail
state_bucket="<exact-state-bucket>"
state_key="bootstrap/terraform.tfstate"
destination_history="$(
  aws s3api list-object-versions \
    --bucket "$state_bucket" \
    --prefix "$state_key" \
    --output json
)"
if jq -e --arg key "$state_key" \
  'any((.Versions // [])[]; .Key == $key) or any((.DeleteMarkers // [])[]; .Key == $key)' \
  <<<"$destination_history" >/dev/null; then
  echo "Refusing migration: the destination state has a version or delete marker. Reconcile its lineage and serial with the protected local state before retrying." >&2
  exit 1
fi

cp -f "$root_dir/backend.s3.tf.example" "$root_dir/backend.s3.tf"
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" init -migrate-state \
  -force-copy \
  -input=false \
  -backend-config="bucket=$state_bucket" \
  -backend-config="key=$state_key" \
  -backend-config="region=<exact-region>" \
  -backend-config="encrypt=true" \
  -backend-config="kms_key_id=<exact-kms-key-arn>" \
  -backend-config="use_lockfile=true"
```

The S3 backend applies that same SSE-KMS configuration to its `.tflock` writes, and the bucket policy rejects any state or lockfile write that omits `aws:kms` or names a different KMS key.

Pull the migrated state into a second protected file and compare its lineage and serial with the local state without emitting either file to logs.
Use `aws s3api head-object` on the exact bootstrap key and verify a nonempty `VersionId`, `ServerSideEncryption` equal to `aws:kms`, and `SSEKMSKeyId` equal to the reviewed key ARN.
Then run a remote-backend plan with the same protected variable file and require a zero-drift result.

Only after all remote-state checks pass may the operator remove the protected local state, backups, plan, and temporary Terraform data directory.
Do not claim secure erasure on SSD-backed storage; rely on the protected directory's custody until ordinary deletion is appropriate.

## Configure the reviewed workflow

Set the protected environment variables from verified live outputs without committing bucket names, account IDs, ARNs, or state:

- `LFB_AWS_REGION`
- `LFB_INFRA_OPERATOR_ROLE_ARN`
- `LFB_TERRAFORM_STATE_BUCKET`
- `LFB_TERRAFORM_STATE_KEY_PREFIX`
- `LFB_TERRAFORM_STATE_KMS_KEY_ID` (the exact key ARN)
- `LFB_GITHUB_OIDC_PROVIDER_ARN`

The routine role can read and write only the `provider-authority` and `official-labeling` state objects, and can delete only their native `.tflock` objects.
It cannot read the bootstrap state or delete a Terraform state object.

## Re-applying this root to add an official-eval role grant

This is the procedure for a *subsequent* apply of an already-migrated bootstrap root, not the protected first apply above: the state now lives at `bootstrap/terraform.tfstate` in the reviewed S3 backend, so there is no local state to create or migrate.
It is the operation required whenever a new official-eval role appears in `infra/official-eval`, because that root's roles are human-admin created and the routine operator cannot create them.
This root is not one of the three modules `.github/workflows/official-provider-authority-infra.yaml` offers, so there is no workflow path for it; every step below is a human-admin operation.

**Credential prerequisite.** Stage 1 and stage 2 require separately authorized admin AWS credentials. Restore that session before starting; it is a hard prerequisite, not a step that can be worked around with a stronger local credential later. Stage 3 needs no local credentials at all — it runs in GitHub Actions under the routine OIDC operator.

### Stage 1 — apply the bootstrap grant

Work from an exact reviewed commit on a trusted operator machine, with the root copied outside the checkout, the variable file outside the checkout, and no AWS credentials in that variable file.
Do not print Terraform state, plan JSON, or outputs into logs, terminal scrollback that will be pasted, or the bead.

```bash
set -euo pipefail
umask 077
state_dir="${LFB_PROTECTED_BOOTSTRAP_STATE_DIR:?set a protected directory outside the checkout}"
var_file="${LFB_BOOTSTRAP_VAR_FILE:?set a protected external tfvars path}"
root_dir="$state_dir/root"
tf_data_dir="$state_dir/tfdata"
install -d -m 0700 "$state_dir" "$tf_data_dir"
test -f "$var_file"
test ! -e "$root_dir"
cp -rf infra/official-eval-bootstrap "$root_dir"
cp -f "$root_dir/backend.s3.tf.example" "$root_dir/backend.s3.tf"

TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" init \
  -input=false \
  -backend-config="bucket=<exact-state-bucket>" \
  -backend-config="key=bootstrap/terraform.tfstate" \
  -backend-config="region=<exact-region>" \
  -backend-config="encrypt=true" \
  -backend-config="kms_key_id=<exact-kms-key-arn>" \
  -backend-config="use_lockfile=true"
terraform -chdir="$root_dir" fmt -check
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" validate
```

Save one plan, review it, and apply only that saved plan after it receives separate authorization.
The expected plan is exactly one in-place update of `aws_iam_role_policy.operator`, whose `policy` gains the new `ManageExactOfficialEvalManifestStagingRole` statement.
`aws_iam_role.operator`, `aws_iam_role_policies_exclusive.operator`, and `aws_iam_role_policy_attachments_exclusive.operator` must all be unchanged, because the inline policy keeps its `reviewed-lfb-terraform-roots` name.
Any create, destroy, replacement, or second changed resource is a halt: reconcile it before applying, and never apply a plan you did not review.

```bash
set -euo pipefail
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" plan \
  -input=false \
  -var-file="$var_file" \
  -out="$state_dir/official-eval-bootstrap-manifest-staging.tfplan"

# Run only after the exact saved plan receives separate authorization.
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" apply \
  -input=false \
  "$state_dir/official-eval-bootstrap-manifest-staging.tfplan"
```

Verify the live result by reading the operator role's inline policy back and confirming the new statement's exact Sid, its five actions, and its exact single role ARN resource.
Do not infer the grant from a successful apply.

### Stage 2 — create the official-eval role under admin credentials

The routine operator can now refresh the role but still cannot create it.
Create it with the *same* Terraform root that will later own it, under admin credentials and against the reviewed remote `official-eval` state.
That matters: the role must converge byte for byte with what `infra/official-eval` renders — the `default_tags` from its `versions.tf`, `max_session_duration = 3600`, the rendered OIDC trust policy, and the exact inline policy.
A role created by hand or by console will drift, and the routine operator cannot repair drift, so the next routine plan would fail closed with `AccessDenied` on verbs it deliberately lacks.

Use the same protected discipline: root and variable file outside the checkout, no credentials in the variable file, no state or outputs in logs.
Initialize the `official-eval` root against the reviewed backend with `key=<state-key-prefix>/official-eval/terraform.tfstate`, then plan with the same protected inputs the workflow supplies.

The expected plan is exactly four creates and no other change:

```text
aws_iam_role.manifest_staging
aws_iam_role_policy.manifest_staging_storage
aws_iam_role_policies_exclusive.manifest_staging
aws_iam_role_policy_attachments_exclusive.manifest_staging
```

Every pre-existing cell and fan-in address must be a no-op.
A plan that touches the cell or fan-in roles, or that shows any S3 address, is a halt — `infra/official-eval/README.md` records why this root must never manage storage.
Save that plan, obtain separate authorization for it, and apply the saved plan.

If the role somehow already exists in AWS, do not apply a create.
Inventory it first, confirm it carries no unrelated inline or attached policy that the `*_exclusive` resources would remove, then import the four addresses above through the workflow's `import` operation and continue at stage 3.

### Stage 3 — confirm routine convergence

Dispatch `.github/workflows/official-provider-authority-infra.yaml` with `module: official-eval` and `operation: plan` from the exact trusted `main` SHA.
The plan must be a clean no-op across all thirteen addresses.
A no-op there is the proof that the read-only grant is sufficient and that the admin-created role matches the module byte for byte; a create means stage 2 did not happen, and any other change means the live role drifted from the reviewed module and needs a human admin, not a widened operator policy.
