# Shared provider authority table

This table-only Terraform module owns the optional DynamoDB authority shared by distributed paid labeling and later official evaluation, plus one disposable DynamoDB canary used only by the provider-free permission smoke.
The canonical Cycle 1 replacement-corpus continuation instead uses one local SQLite provider journal with `--local-provider-journal-only`; it does not require this table.
When the distributed path is selected, Stage A/B uses the table to reserve and reconcile provider spend against one frozen provider/account ceiling.

The module creates the shared authority table and a distinct smoke canary table; it does not create IAM roles, does not create S3 resources, and does not configure GitHub environments or provider credentials.
The distinct paid-labeling role in `infra/official-labeling` receives exact-table data-plane access separately.

The stable table name preserves the identity expected by the reviewed paid-labeling configuration.
The table has string partition key `authority_key`, string sort key `record_key`, on-demand capacity, deletion protection, point-in-time recovery, server-side encryption, and TTL on `expires_at`.
Terraform also refuses destructive replacement through `prevent_destroy`.

## Disposable authority-smoke canary

The module also provisions `aws_dynamodb_table.outside_authority_canary` with the fixed name `legalforecastbench-official-labeling-authority-smoke-canary` and exports its exact name as the sensitive `outside_authority_table_name` output.
The canary is on-demand, encrypted, and TTL-enabled on `expires_at`; it has no point-in-time recovery, deletion protection, or `prevent_destroy` because it contains only negative-control smoke data and must be removable after the smoke.
Its tags identify it as a `disposable-canary` negative control.
Neither `infra/official-labeling` nor `infra/official-eval` references this table: their policies continue to name only the shared authority-table ARN.
The protected provider-authority Terraform workflow includes both table resource addresses in its closed plan/import contract, so an existing canary may be imported by its fixed name or a new one may be created by the reviewed plan.

After the separately authorized apply, decrypt the protected Terraform-output handoff only on the trusted operator machine, read `outside_authority_table_name`, and set `LFB_OUTSIDE_AUTHORITY_TABLE` in the protected authority-smoke environment through the approved server-side configuration path.
The fixed reviewed canary name is intentionally a public code contract; keep the protected Terraform-output handoff, account-specific ARN, account ID, state, and protected environment values private, and do not copy them into repository artifacts.
The current protected Terraform workflow rejects destructive plan actions, so this lane intentionally leaves the declared canary in place after the smoke. Retain it until a separately reviewed disposal operation is available; do not delete it manually, mutate Terraform state, or remove the durable shared authority table.

## Protected Terraform operator procedure

Here, provider-free describes the later fan-in runtime: it does not embed provider credentials in repository artifacts.
Terraform itself still uses the AWS provider and must run with short-lived credentials from a protected operator workflow.
Keep its state and input variables in protected storage outside the repository checkout.
Committing this module does not authorize or perform an AWS mutation.

The supported repository workflow is `.github/workflows/official-provider-authority-infra.yaml`.
It consumes the separately bootstrapped `legalforecastbench-official-provider-authority-infra` GitHub environment, a short-lived OIDC operator role, and an encrypted S3 remote-state backend.
It cannot create that environment, operator role, state bucket, KMS key, or the secure-gate allowlists that provision their values.
Those are external bootstrap prerequisites and must be reviewed before the first workflow plan.

For an existing table, inspect its protected identity and controls first, then use `terraform import` rather than attempting to create a replacement:

```bash
state_dir="${LFB_PROTECTED_STATE_DIR:?set a durable protected directory outside the checkout}"
var_file="${LFB_PROVIDER_AUTHORITY_VAR_FILE:?set a protected external tfvars path}"
tf_data_dir="$state_dir/tfdata"
install -d -m 0700 "$state_dir" "$tf_data_dir"
test -f "$var_file"

TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir=infra/provider-authority init -backend=false
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/provider-authority import \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  aws_dynamodb_table.provider_authority \
  legalforecastbench-official-eval-provider-authority
```

The explicit state path prevents Terraform's default local backend from writing `terraform.tfstate` beneath `infra/provider-authority`.
Protect and back up that state as sensitive operational data.
If this import is performed before the repository workflow is used, migrate the verified state into the workflow's exact encrypted S3 backend and verify the remote lineage before dispatching `plan`.
The workflow deliberately does not import a live resource or create its own state backend.

For either an imported or new table, save and review a Terraform plan before a separately authorized operator applies that exact plan:

```bash
TF_DATA_DIR="$tf_data_dir" terraform -chdir=infra/provider-authority plan \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  -var-file="$var_file" \
  -out="$state_dir/lfb-provider-authority.tfplan"
```

After separate authorization, apply that reviewed plan with the same explicit protected state path:

```bash
TF_DATA_DIR="$tf_data_dir" \
  terraform -chdir=infra/provider-authority apply \
  -input=false \
  -state="$state_dir/terraform.tfstate" \
  "$state_dir/lfb-provider-authority.tfplan"
```

Record the reviewed plan digest and protected apply evidence in bead `LegalForecastBench-5qd6.98.1`.
Do not publish the table ARN or AWS account ID.
Configure the protected paid-labeling environments with the table name, role values, and public resource-identity SHA-256, then run the separate provider-free authority smoke.
Download the raw reviewed smoke receipt and pass it, its exact release and digest, immutable legacy caps, and the canonical public alias policy to `legalforecast acquisition materialize-provider-cycle-caps-successor`.
Never hand-edit the authority identity into `provider-cycle-caps`; the supported provider-free successor command binds the complete smoke evidence and publishes the caps, receipt, and run card atomically.
