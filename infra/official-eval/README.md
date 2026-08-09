# Official evaluation AWS boundary

This Terraform root defines the intended S3 and GitHub Actions OIDC boundary for the current official-evaluation call graph. It has not been applied by this branch, and code validation is not live acceptance.

## Exact two-role contract

The current workflows use exactly two AWS roles and two protected GitHub environments:

| Environment | Human-configured variable | Authority |
| --- | --- | --- |
| `legalforecastbench-official-eval` | `LFB_AWS_REGION`, `LFB_GITHUB_PACKET_READ_ROLE_ARN`, `LFB_PROVIDER_AUTHORITY_TABLE` | Read model packets and frozen manifests; read/write the current per-case object shape; create and read immutable intent/done markers; read and exactly probe a cycle seal; use the exact provider-attempt authority table. Optional exact-resource Bedrock invocation is disabled by default. |
| `legalforecastbench-official-eval-fan-in` | `LFB_AWS_REGION`, `LFB_GITHUB_FAN_IN_ROLE_ARN` | Bulk-list current per-case `VersionId` values under `per-case/*`; read exact committed per-case versions; read/write immutable shard receipts and closure state; publish only the canonical `reports/<cycle_id>/multi-ablation/` prefix. |

The canonical machine-readable setup contract is `github-environments.json`.
It covers these two runtime environments and the separately bootstrapped `legalforecastbench-official-provider-authority-infra` environment, and closes each environment over its exact reviewer, main-only deployment policy, OIDC subject, secret names, and variable names.
The infrastructure environment contains only its plan-decryption age identity; the evaluation cell contains the three provider API-key names consumed by `run-benchmark.yaml`; and fan-in contains no secrets or provider role.
The manifest contains configuration names only and does not authorize environment writes, infrastructure changes, or provider calls.

The fan-in role has no provider secrets or provider-spend authority. Neither role receives delete, ACL, bucket administration, or broad bucket-list authority. The cell role receives no `ListBucketVersions`; the fan-in role receives prefix-conditioned `s3:ListBucketVersions` authority only for `per-case/<cycle_id>/` inventory and no version-list authority for receipts, closure state, or reports. The cell role receives only `ConditionCheckItem`, `DescribeTable`, `GetItem`, `PutItem`, and `UpdateItem` on one exact DynamoDB table ARN whose SHA-256 commitment must match the frozen resource identity; it receives no DynamoDB table administration, scan, or delete authority. The cell role has no shard-receipt or top-level canonical-report read/write authority; its only report-shaped permission is `GetObject` and `PutObject` for the runner's exact versioned `per-case/<cycle>/reports/<cycle>/<run>.runner-log.jsonl` path. The cell job writes that log, and the aggregate job's current durable-union sync reads it before selecting only metrics artifacts. Its only optional model-provider permission is `bedrock:InvokeModel` under the structured direct-model and geographic inference-profile contract below. Parseable policy templates under `policies/` are the reviewed contract and are tested against extra statements, principals, actions, and resources.

All create-once object namespaces split read from write. The write statements require the request to carry `If-None-Match: *`, exposed to IAM as a non-null `s3:if-none-match` condition key. That matches the current immutable Python writers and prevents an authorized role from overwriting an existing intent, done marker, receipt, seal, or canonical report. Ordinary per-case metrics and runner logs remain repeatable/versioned and their `PutObject` permissions are intentionally unconditional.

The observed repository OIDC customization uses GitHub's default subject behavior with subject prefix `repo:johnhughes3/LegalForecastBench`. Each trust therefore retains the exact environment-qualified `sub` and additionally requires exact `repository = johnhughes3/LegalForecastBench` and `ref = refs/heads/main` claims. It intentionally does not invent a workflow claim.

## Storage and retention

Both existing buckets are modeled as global-namespace general purpose buckets that are private, `BucketOwnerEnforced`, AES-256 server-side encrypted, versioned, and TLS-only. Public-access blocks and `prevent_destroy` are mandatory. Account-regional `-an` names and directory/table bucket suffixes are rejected because this root does not set a non-global `bucket_namespace` or model those bucket types.

This root deliberately does not expire `per-case/` current objects or noncurrent versions. Per-case outputs can repeat filing text or other PII, so indefinite private retention has a data-minimization cost; however, deleting a noncurrent version can invalidate a receipt that commits its exact S3 `VersionId`. Any destructive raw-result lifecycle must therefore be a separate, explicit review that reconciles PII obligations with the receipt-retention horizon and archived audit evidence. A stale blanket 30-day noncurrent-version rule is not safe.

`reports/security-negative-controls/` is reserved for live denied-write canaries. It is never a canonical report destination and neither runtime role is granted that prefix as a negative-control namespace. Only an administrator may seed or clean those disposable objects; the narrowly scoped lifecycle expires their current and noncurrent versions after the reviewed whole-day retention. Incomplete multipart uploads are aborted after seven days on both buckets.

## Existing buckets, import, and remote state

The packet and result buckets already exist. Do not apply this root against empty local state: doing so would propose duplicate bucket creation and could replace unreviewed bucket subresource configuration. Configure the approved encrypted S3 remote state backend first, back it up, and run `terraform import` for every existing object into that remote state before reviewing a plan.

Representative imports, with the real bucket names supplied through the protected operator path, are:

```bash
terraform -chdir=infra/official-eval import aws_s3_bucket.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket.results "$LFB_RESULTS_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_public_access_block.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_public_access_block.results "$LFB_RESULTS_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_ownership_controls.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_ownership_controls.results "$LFB_RESULTS_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_server_side_encryption_configuration.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_server_side_encryption_configuration.results "$LFB_RESULTS_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_versioning.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_versioning.results "$LFB_RESULTS_BUCKET"
```

Before importing lifecycle or bucket-policy subresources, capture their live state in a protected directory outside the checkout. Run the inventory and its conditional imports in one Bash session:

```bash
set -euo pipefail
inventory_dir="${LFB_OFFICIAL_EVAL_INVENTORY_DIR:?set a protected directory outside the checkout}"
install -d -m 0700 "$inventory_dir"

inventory_s3_subresource() {
  local operation="$1"
  local bucket="$2"
  local output_path="$3"
  local absent_code="$4"
  local presence_variable="$5"
  local error_path="${output_path}.stderr"

  if aws s3api "$operation" --bucket "$bucket" \
    --output json --no-cli-pager >"$output_path" 2>"$error_path"; then
    if [[ ! -s "$output_path" ]]; then
      echo "empty AWS inventory response for $operation on $bucket" >&2
      return 1
    fi
    rm -f "$error_path"
    printf -v "$presence_variable" '%s' true
    return 0
  fi
  if grep -Fq "($absent_code)" "$error_path"; then
    rm -f "$output_path" "$error_path"
    printf -v "$presence_variable" '%s' false
    return 0
  fi
  cat "$error_path" >&2
  return 1
}

inventory_s3_subresource get-bucket-lifecycle-configuration \
  "$LFB_PACKET_BUCKET" "$inventory_dir/packet-lifecycle.json" \
  NoSuchLifecycleConfiguration packet_lifecycle_exists
inventory_s3_subresource get-bucket-lifecycle-configuration \
  "$LFB_RESULTS_BUCKET" "$inventory_dir/results-lifecycle.json" \
  NoSuchLifecycleConfiguration results_lifecycle_exists
inventory_s3_subresource get-bucket-policy \
  "$LFB_PACKET_BUCKET" "$inventory_dir/packet-policy.json" \
  NoSuchBucketPolicy packet_policy_exists
inventory_s3_subresource get-bucket-policy \
  "$LFB_RESULTS_BUCKET" "$inventory_dir/results-policy.json" \
  NoSuchBucketPolicy results_policy_exists

if [[ "$packet_lifecycle_exists" == true ]]; then
  terraform -chdir=infra/official-eval import \
    aws_s3_bucket_lifecycle_configuration.packet "$LFB_PACKET_BUCKET"
fi
if [[ "$results_lifecycle_exists" == true ]]; then
  terraform -chdir=infra/official-eval import \
    aws_s3_bucket_lifecycle_configuration.results "$LFB_RESULTS_BUCKET"
fi
if [[ "$packet_policy_exists" == true ]]; then
  terraform -chdir=infra/official-eval import \
    aws_s3_bucket_policy.packet "$LFB_PACKET_BUCKET"
fi
if [[ "$results_policy_exists" == true ]]; then
  terraform -chdir=infra/official-eval import \
    aws_s3_bucket_policy.results "$LFB_RESULTS_BUCKET"
fi
```

Successful inventory responses remain as JSON for plan review. `NoSuchLifecycleConfiguration` or `NoSuchBucketPolicy` marks only that exact subresource as absent and skips only its corresponding import. Any other AWS CLI error stops reconciliation; do not suppress errors or continue with an incomplete inventory.

Reconcile every pre-existing lifecycle rule and bucket-policy statement into this Terraform configuration before saving a plan. Both S3 APIs are full-replacement surfaces, so an acceptable first-apply plan must preserve every intended live rule and statement and show no unintended deletion.

Import existing IAM roles and inline policies, or choose reviewed new role names after an account inventory; never guess whether those names are already managed elsewhere. If the default role names already exist, the exact IAM imports are:

```bash
terraform -chdir=infra/official-eval import aws_iam_role.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role.fan_in legalforecastbench-official-eval-fan-in
terraform -chdir=infra/official-eval import aws_iam_role_policy.cell_storage legalforecastbench-official-eval:official-eval-cell-storage
terraform -chdir=infra/official-eval import aws_iam_role_policy.cell_provider_authority legalforecastbench-official-eval:official-eval-cell-exact-provider-authority
terraform -chdir=infra/official-eval import aws_iam_role_policy.fan_in_storage legalforecastbench-official-eval-fan-in:official-eval-fan-in-storage
terraform -chdir=infra/official-eval import aws_iam_role_policies_exclusive.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role_policies_exclusive.fan_in legalforecastbench-official-eval-fan-in
terraform -chdir=infra/official-eval import aws_iam_role_policy_attachments_exclusive.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role_policy_attachments_exclusive.fan_in legalforecastbench-official-eval-fan-in
```

If Bedrock was already configured under the exact intended inline-policy name and is deliberately enabled, also import it with `terraform -chdir=infra/official-eval import 'aws_iam_role_policy.cell_bedrock[0]' legalforecastbench-official-eval:official-eval-cell-bedrock-invoke`. Do not import or enable it merely because some other Bedrock policy exists.

The two `aws_iam_role_policies_exclusive` resources make the listed inline policies authoritative, and the two `aws_iam_role_policy_attachments_exclusive` resources set the authoritative managed-policy set to empty. Before the first apply, inventory every existing inline and attached managed policy on both roles. Reconcile any legitimate policy into this configuration or select new role names; otherwise the saved plan will deliberately remove it. Importing an exclusivity resource records management ownership but does not make an unlisted policy safe to remove. Reconcile every imported bucket policy, lifecycle, trust policy, inline policy, and managed attachment difference before saving a plan. An apply is allowed only from the reviewed remote state, against an exact saved plan, through the normal protected infrastructure path.

## Provider spend authority

The cell job is the only official-evaluation principal that may reserve and settle provider attempts. Set `provider_authority_table_arn` to the exact existing table ARN and set `provider_authority_resource_identity_sha256` to the lowercase SHA-256 of that literal ARN. Terraform fails closed unless the commitment matches and the table uses the configured AWS partition, region, and account. Set the protected `LFB_PROVIDER_AUTHORITY_TABLE` variable from the `provider_authority_table_name` output. The runner derives the provider account from the selected provider's unique frozen cap and independently verifies the frozen table identity, retry policy, and execution-policy binding before any provider call.

## Optional Bedrock runtime decision

`enable_bedrock_runtime` defaults to `false`. With that default, leave `LFB_ANTHROPIC_RUNTIME` unset (or configured for the separately reviewed direct Anthropic API path), keep `bedrock_direct_foundation_model_arns` empty, and keep `bedrock_geographic_inference_profiles` empty. This root never infers the protected `LFB_ANTHROPIC_RUNTIME` value; verify it through the approved operator path before provisioning or enabling Bedrock. No illustrative ARN is a live recommendation.

To use the workflow's `bedrock`, `aws-bedrock`, or `aws_bedrock` runtime, first review the protected cell environment's runtime and `LFB_ANTHROPIC_BEDROCK_MODEL_ID`, then set `enable_bedrock_runtime = true` and select exactly one reviewed authority shape for that model ID:

- For direct foundation-model invocation, add only the exact model ARN to `bedrock_direct_foundation_model_arns`. This produces a standalone unconditional direct-invocation statement and grants no inference-profile authority.
- For a `us.*`, `eu.*`, or `apac.*` geographic inference profile, add a `bedrock_geographic_inference_profiles` entry containing the exact profile ARN and the complete reviewed set of source-and-destination foundation-model ARNs. The generated policy follows AWS's two-statement geographic contract: one unconditional statement grants only the exact profile ARN, and a second grants only the reviewed foundation-model ARNs conditioned by exact equality on `bedrock:InferenceProfileArn`. Destination ARNs do not become directly invokable through that conditioned statement.

Wildcards, empty destination sets, application inference profiles, and global inference profiles are rejected. AWS global inference profiles require a distinct three-part policy shape; this module deliberately does not model or claim support for it. The permission is attached only to the cell role; fan-in remains provider-free.

## Validation versus live acceptance

Local validation is provider-free:

```bash
terraform fmt -check -recursive infra/official-eval
export TF_DATA_DIR="$(mktemp -d)"
terraform -chdir=infra/official-eval init -backend=false
terraform -chdir=infra/official-eval validate
uv run pytest -q tests/test_official_eval_infra.py
```

Before live acceptance, verify that both `legalforecastbench-official-eval` and `legalforecastbench-official-eval-fan-in` exist as protected GitHub environments for `main`. Ensure the fan-in environment has no provider secrets, set the same reviewed `LFB_AWS_REGION` on both environments, and set `LFB_GITHUB_PACKET_READ_ROLE_ARN`, `LFB_GITHUB_FAN_IN_ROLE_ARN`, and `LFB_PROVIDER_AUTHORITY_TABLE` from the reviewed applied outputs through the human-approved server-side configuration path. Verify the cell environment's `LFB_ANTHROPIC_RUNTIME`: it must either leave Bedrock disabled and use the reviewed direct Anthropic path, or enable Bedrock only with the exact structured direct-model or geographic-profile contract described above.

The validation workflow exercises both roles' positive read/list contracts and actual denied operations without a session-policy overlay; denied writes target only `reports/security-negative-controls/`. This is code evidence, not live acceptance. After provisioning, dispatch the validation from `main`, followed by a provider-free fan-in verification dispatch from `main`. Passing local workflow tests, Terraform validation, or an unapplied plan is not evidence that AWS, GitHub environments, or live OIDC claims satisfy the contract.
