# Shared provider authority table

This table-only Terraform module owns the DynamoDB authority shared by paid labeling and later official evaluation.
Stage A/B uses it to reserve and reconcile provider spend against one frozen provider/account ceiling.

The module creates one DynamoDB table and does not create IAM roles, does not create S3 resources, and does not configure GitHub environments or provider credentials.
The distinct paid-labeling role in `infra/official-labeling` receives exact-table data-plane access separately.

The stable table name preserves the identity expected by the reviewed paid-labeling configuration.
The table has string partition key `authority_key`, string sort key `record_key`, on-demand capacity, deletion protection, point-in-time recovery, server-side encryption, and TTL on `expires_at`.
Terraform also refuses destructive replacement through `prevent_destroy`.

## Protected Terraform operator procedure

Here, provider-free describes the later fan-in runtime: it does not embed provider credentials in repository artifacts.
Terraform itself still uses the AWS provider and must run with short-lived credentials from a protected operator workflow.
Keep its state and input variables in protected storage outside the repository checkout.
Committing this module does not authorize or perform an AWS mutation.

For an existing table, inspect its protected identity and controls first, then use `terraform import` rather than attempting to create a replacement:

```bash
state_dir="${LFB_PROTECTED_STATE_DIR:?set a durable protected directory outside the checkout}"
var_file="${LFB_PROVIDER_AUTHORITY_VAR_FILE:?set a protected external tfvars path}"
install -d -m 0700 "$state_dir"
test -f "$var_file"

TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata \
  terraform -chdir=infra/provider-authority init -backend=false
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata terraform -chdir=infra/provider-authority import \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  aws_dynamodb_table.provider_authority \
  legalforecastbench-official-eval-provider-authority
```

The explicit state path prevents Terraform's default local backend from writing `terraform.tfstate` beneath `infra/provider-authority`.
Protect and back up that state as sensitive operational data.

For either an imported or new table, save and review a Terraform plan before a separately authorized operator applies that exact plan:

```bash
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata terraform -chdir=infra/provider-authority plan \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  -out="$state_dir/lfb-provider-authority.tfplan"
```

After separate authorization, apply that reviewed plan with the same explicit protected state path:

```bash
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata \
  terraform -chdir=infra/provider-authority apply \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  "$state_dir/lfb-provider-authority.tfplan"
```

Record the reviewed plan digest and protected apply evidence in bead `LegalForecastBench-5qd6.98.1`.
Do not publish the table ARN or AWS account ID.
Freeze only the SHA-256 resource identity output into `provider-cycle-caps`, configure the protected paid-labeling environments with the table name and role values, and then run the separate provider-free authority smoke.
