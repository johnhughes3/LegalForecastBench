# Official evaluation AWS boundary

This Terraform root defines the intended S3 and GitHub Actions OIDC boundary for the current official-evaluation call graph. It has not been applied by this branch, and code validation is not live acceptance.

## Exact two-role contract

The current workflows use exactly two AWS roles and two protected GitHub environments:

| Environment | Human-configured variable | Authority |
| --- | --- | --- |
| `legalforecastbench-official-eval` | `LFB_GITHUB_PACKET_READ_ROLE_ARN` | Read model packets and frozen manifests; read/write the current per-case object shape; create and read immutable intent/done markers; read and exactly probe a cycle seal. Optional exact-resource Bedrock invocation is disabled by default. |
| `legalforecastbench-official-eval-fan-in` | `LFB_GITHUB_FAN_IN_ROLE_ARN` | Read exact per-case `VersionId` values; read/write immutable shard receipts and closure state; publish only the canonical `reports/<cycle_id>/multi-ablation/` prefix. |

The fan-in role has no provider secrets or provider-spend authority. Neither role receives DynamoDB, delete, ACL, bucket administration, `ListBucketVersions`, or broad bucket-list authority. The cell role has no shard-receipt or top-level canonical-report read/write authority; its only report-shaped permission is `GetObject` and `PutObject` for the runner's exact versioned `per-case/<cycle>/reports/<cycle>/<run>.runner-log.jsonl` path. The cell job writes that log, and the aggregate job's current durable-union sync reads it before selecting only metrics artifacts. Its only optional provider permission is `bedrock:InvokeModel` under the structured direct-model and geographic inference-profile contract below. Parseable policy templates under `policies/` are the reviewed contract and are tested against extra statements, principals, actions, and resources.

All create-once object namespaces split read from write. The write statements require the request to carry `If-None-Match: *`, exposed to IAM as a non-null `s3:if-none-match` condition key. That matches the current immutable Python writers and prevents an authorized role from overwriting an existing intent, done marker, receipt, seal, or canonical report. Ordinary per-case metrics and runner logs remain repeatable/versioned and their `PutObject` permissions are intentionally unconditional.

The observed repository OIDC customization uses GitHub's default subject behavior with subject prefix `repo:johnhughes3/LegalForecastBench`. Each trust therefore retains the exact environment-qualified `sub` and additionally requires exact `repository = johnhughes3/LegalForecastBench` and `ref = refs/heads/main` claims. It intentionally does not invent a workflow claim.

## Storage and retention

Both existing buckets are modeled as private, `BucketOwnerEnforced`, AES-256 server-side encrypted, versioned, and TLS-only. Public-access blocks and `prevent_destroy` are mandatory.

This root deliberately does not expire `per-case/` current objects or noncurrent versions. Per-case outputs can repeat filing text or other PII, so indefinite private retention has a data-minimization cost; however, deleting a noncurrent version can invalidate a receipt that commits its exact S3 `VersionId`. Any destructive raw-result lifecycle must therefore be a separate, explicit review that reconciles PII obligations with the receipt-retention horizon and archived audit evidence. A stale blanket 30-day noncurrent-version rule is not safe.

`reports/security-negative-controls/` is reserved for later live denied-write canaries. It is never a canonical report destination and neither runtime role is granted that prefix as a negative-control namespace. Only an administrator may seed or clean those disposable objects; the narrowly scoped lifecycle expires their current and noncurrent versions after the reviewed short retention. Incomplete multipart uploads are aborted after seven days on both buckets.

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
terraform -chdir=infra/official-eval import aws_s3_bucket_lifecycle_configuration.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_lifecycle_configuration.results "$LFB_RESULTS_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_policy.packet "$LFB_PACKET_BUCKET"
terraform -chdir=infra/official-eval import aws_s3_bucket_policy.results "$LFB_RESULTS_BUCKET"
```

Import existing IAM roles and inline policies, or choose reviewed new role names after an account inventory; never guess whether those names are already managed elsewhere. If the default role names already exist, the exact IAM imports are:

```bash
terraform -chdir=infra/official-eval import aws_iam_role.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role.fan_in legalforecastbench-official-eval-fan-in
terraform -chdir=infra/official-eval import aws_iam_role_policy.cell_storage legalforecastbench-official-eval:official-eval-cell-storage
terraform -chdir=infra/official-eval import aws_iam_role_policy.fan_in_storage legalforecastbench-official-eval-fan-in:official-eval-fan-in-storage
terraform -chdir=infra/official-eval import aws_iam_role_policies_exclusive.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role_policies_exclusive.fan_in legalforecastbench-official-eval-fan-in
terraform -chdir=infra/official-eval import aws_iam_role_policy_attachments_exclusive.cell legalforecastbench-official-eval
terraform -chdir=infra/official-eval import aws_iam_role_policy_attachments_exclusive.fan_in legalforecastbench-official-eval-fan-in
```

If Bedrock was already configured under the exact intended inline-policy name and is deliberately enabled, also import it with `terraform -chdir=infra/official-eval import 'aws_iam_role_policy.cell_bedrock[0]' legalforecastbench-official-eval:official-eval-cell-bedrock-invoke`. Do not import or enable it merely because some other Bedrock policy exists.

The two `aws_iam_role_policies_exclusive` resources make the listed inline policies authoritative, and the two `aws_iam_role_policy_attachments_exclusive` resources set the authoritative managed-policy set to empty. Before the first apply, inventory every existing inline and attached managed policy on both roles. Reconcile any legitimate policy into this configuration or select new role names; otherwise the saved plan will deliberately remove it. Importing an exclusivity resource records management ownership but does not make an unlisted policy safe to remove. Reconcile every imported bucket policy, lifecycle, trust policy, inline policy, and managed attachment difference before saving a plan. An apply is allowed only from the reviewed remote state, against an exact saved plan, through the normal protected infrastructure path.

## Optional Bedrock runtime decision

`enable_bedrock_runtime` defaults to `false`. With that default, leave `LFB_ANTHROPIC_RUNTIME` unset (or configured for the separately reviewed direct Anthropic API path), keep `bedrock_direct_foundation_model_arns` empty, and keep `bedrock_geographic_inference_profiles` empty. The live value of `LFB_ANTHROPIC_RUNTIME` could not be read during this review, so this root does not guess it and no illustrative ARN is a live recommendation.

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

As observed on 2026-07-24, the repository environments are only `copilot`, `legalforecastbench-official-eval`, and `pypi`; the fan-in environment does not yet exist (GET returned 404), and the official environment's variables and secrets—including `LFB_ANTHROPIC_RUNTIME`—could not be verified (GET returned 403). A human-approved server-side step must create `legalforecastbench-official-eval-fan-in`, protect both official environments for `main`, ensure the fan-in environment has no provider secrets, and set `LFB_GITHUB_PACKET_READ_ROLE_ARN` and `LFB_GITHUB_FAN_IN_ROLE_ARN` from the applied outputs. The cell environment must either leave Bedrock disabled and use the reviewed direct Anthropic path, or enable it only with the exact structured direct-model or geographic-profile contract described above.

The existing S3 validation runs predate this two-role boundary, and `fan-in-publish.yaml` has never run. Before acceptance, the official S3 validation workflow must be rewritten under the separate workflow-review path to exercise both positive and denied operations, using only `reports/security-negative-controls/` for denied-write canaries. After provisioning, that rewritten validation must be dispatched from `main`, followed by a provider-free fan-in verification dispatch from `main`. Passing Terraform validation or an unapplied plan is not evidence that AWS, GitHub environments, or live OIDC claims satisfy the contract.
