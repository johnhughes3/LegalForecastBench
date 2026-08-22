# One-time official-evaluation AWS bootstrap

This Terraform root owns the trust anchor consumed by `.github/workflows/official-provider-authority-infra.yaml`: one private versioned state bucket, one customer-managed KMS key and alias, the account-level GitHub Actions OIDC provider, and the exact environment-bound infrastructure operator role.
The routine workflow cannot apply this root and its role has no permission to change its own trust or policy, administer the OIDC provider, bucket, KMS key, or bootstrap state, or broaden the three reviewed downstream roots.

Creating or importing this root does not authorize AWS work.
The one-time apply requires separately authorized human/operator AWS credentials, independent review of the exact plan, and protected local state custody until remote migration is proven complete.

The rendered operator policy keeps the durable `legalforecastbench-official-eval-provider-authority` table in its existing exact, non-destructive statement and grants a separate exact-resource statement for the public fixed-name canary `legalforecastbench-official-labeling-authority-smoke-canary`. The canary statement grants only the Terraform management actions required to provision and inspect the negative-control resource; it does not grant the labeling or evaluation roles access to the canary. Disposal remains a separately reviewed follow-up because the current protected plan contract rejects destructive actions.

## Operator role trust surface

The operator trust pins five conditions: `aud`, the environment-qualified `sub`, `repository`, `ref`, and `environment`.
Do not delete `repository`, `ref`, or `environment`. They are documented AWS condition keys for the GitHub IdP, they are populated on protected-environment tokens, and they are satisfiable here because the operator job binds the `legalforecastbench-official-provider-authority-infra` environment and runs only from `refs/heads/main`. Reviews have twice argued they are unmatchable; [docs/github-aws-oidc-trust-claims.md](../../docs/github-aws-oidc-trust-claims.md) records the primary sources that settle it, and `tests/test_official_eval_bootstrap_infra.py` binds directly to the production locals, variable defaults, environment manifest, and the role-assuming `operate` job, failing if a condition is dropped, a pinned value drifts, or that job stops producing a claim — with in-suite mutation tests proving the fence discriminates.

## Protected first apply

Use an exact reviewed commit on a trusted operator machine.
Keep the variable file and state directory outside the checkout, do not print Terraform state or outputs into logs, and do not place AWS credentials in a variable file.
Set `github_repository` in that protected variable file to the exact reviewed GitHub `owner/repository`; the root intentionally has no account-specific default.
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
If it already exists, verify that its sole audience is `sts.amazonaws.com`, determine whether other roles depend on it, and run `terraform import` into this root before any plan; never create a duplicate provider or silently rewrite a shared audience list:

```bash
set -euo pipefail
TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" import \
  -input=false \
  -var-file="$var_file" \
  aws_iam_openid_connect_provider.github_actions \
  "<exact-existing-provider-arn>"
```

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
For an absent provider, the separately authorized bootstrap apply creates it and this root becomes its Terraform owner.

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
