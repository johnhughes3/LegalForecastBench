# One-time official-evaluation AWS bootstrap

This Terraform root owns the trust anchor consumed by `.github/workflows/official-provider-authority-infra.yaml`: one private versioned state bucket, one customer-managed KMS key and alias, the account-level GitHub Actions OIDC provider, and the exact environment-bound infrastructure operator role.
The routine workflow cannot apply this root and its role has no permission to change its own trust or policy, administer the OIDC provider, bucket, KMS key, or bootstrap state, or broaden the two reviewed downstream roots.

Creating or importing this root does not authorize AWS work.
The one-time apply requires separately authorized human/operator AWS credentials, independent review of the exact plan, and protected local state custody until remote migration is proven complete.

## Protected first apply

Use an exact reviewed commit on a trusted operator machine.
Keep the variable file and state directory outside the checkout, do not print Terraform state or outputs into logs, and do not place AWS credentials in a variable file:

```bash
umask 077
state_dir="${LFB_PROTECTED_BOOTSTRAP_STATE_DIR:?set a protected directory outside the checkout}"
var_file="${LFB_BOOTSTRAP_VAR_FILE:?set a protected external tfvars path}"
tf_data_dir="$state_dir/tfdata"
install -d -m 0700 "$state_dir" "$tf_data_dir"
test -f "$var_file"

TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir=infra/official-eval-bootstrap init -backend=false -input=false
terraform -chdir=infra/official-eval-bootstrap fmt -check
TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir=infra/official-eval-bootstrap validate
```

Inventory the account-level provider for `https://token.actions.githubusercontent.com` before planning.
If it already exists, verify that its sole audience is `sts.amazonaws.com`, determine whether other roles depend on it, and run `terraform import` into this root before any plan; never create a duplicate provider or silently rewrite a shared audience list:

```bash
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/official-eval-bootstrap import \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  aws_iam_openid_connect_provider.github_actions \
  "<exact-existing-provider-arn>"
```

Apply the same import-first rule to any reviewed bucket, KMS key/alias, or operator role that already exists.
Stop on any ownership ambiguity rather than planning a replacement.
For an absent provider, the separately authorized bootstrap apply creates it and this root becomes its Terraform owner.

Before any `terraform plan`, complete the inventory and required imports above.
Save, review, and apply one exact local-state plan; a `terraform apply` is permitted only for the separately authorized saved plan:

```bash
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/official-eval-bootstrap plan \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  -out="$state_dir/official-eval-bootstrap.tfplan"

# Run only after the exact saved plan receives separate authorization.
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/official-eval-bootstrap apply \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  "$state_dir/official-eval-bootstrap.tfplan"
```

Verify the live bucket public-access block, ownership controls, versioning, TLS-only policy and exact KMS default encryption; verify KMS rotation and policy; verify the OIDC audience; and inspect the operator role's exact trust and inline policy.
Do not infer these properties from a successful apply.

## Migrate the bootstrap state

Use the exact KMS key ARN from the protected apply evidence, not the mutable alias.
The bootstrap state key is intentionally outside the routine role's state prefix:
Run `terraform init -migrate-state` only after the live bootstrap controls have been independently verified:

```bash
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/official-eval-bootstrap init -migrate-state \
  -force-copy \
  -input=false \
  -backend-config="bucket=<exact-state-bucket>" \
  -backend-config="key=bootstrap/terraform.tfstate" \
  -backend-config="region=<exact-region>" \
  -backend-config="encrypt=true" \
  -backend-config="kms_key_id=<exact-kms-key-arn>" \
  -backend-config="use_lockfile=true"
```

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
