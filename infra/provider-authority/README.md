# Shared provider authority table

This table-only Terraform module owns the DynamoDB authority shared by paid labeling and later official evaluation.
Stage A/B uses it to reserve and reconcile provider spend against one frozen provider/account ceiling.

The module creates one DynamoDB table and does not create IAM roles, does not create S3 resources, and does not configure GitHub environments or provider credentials.
The distinct paid-labeling role in `infra/official-labeling` receives exact-table data-plane access separately.

The stable table name preserves the identity expected by the reviewed paid-labeling configuration.
The table has string partition key `authority_key`, string sort key `record_key`, on-demand capacity, deletion protection, point-in-time recovery, server-side encryption, and TTL on `expires_at`.
Terraform also refuses destructive replacement through `prevent_destroy`.

## Provider-free operator procedure

Run Terraform only from a protected operator context and keep state outside public artifacts.
Committing this module does not authorize or perform an AWS mutation.

For an existing table, inspect its protected identity and controls first, then use `terraform import` rather than attempting to create a replacement:

```bash
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata terraform -chdir=infra/provider-authority init
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata terraform -chdir=infra/provider-authority import \
  aws_dynamodb_table.provider_authority \
  legalforecastbench-official-eval-provider-authority
```

For either an imported or new table, save and review a Terraform plan before John separately authorizes Terraform apply:

```bash
TF_DATA_DIR=/tmp/lfb-provider-authority-tfdata terraform -chdir=infra/provider-authority plan \
  -out=/tmp/lfb-provider-authority.tfplan
```

Record the reviewed plan digest and protected apply evidence in bead `5qd6.98.1`.
Do not publish the table ARN or AWS account ID.
Freeze only the SHA-256 resource identity output into `provider-cycle-caps`, configure the protected paid-labeling environments with the table name and role values, and then run the separate provider-free authority smoke.
