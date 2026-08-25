# Official evaluation IAM boundary

This Terraform root defines the IAM roles and inline policies used by the
official evaluation cell and provider-free fan-in. It has not been applied by
this branch, and local code validation is not live acceptance.

## Ownership boundary

The existing packet and results buckets are owned by the COS CloudFormation
stack `LegalForecastBenchArtifactStack`. That stack remains the sole owner of
the buckets and every storage subresource, including public-access blocks,
ownership controls, encryption, versioning, lifecycle configuration, and
bucket policies. This root intentionally contains no `aws_s3_*` resources and
must never import those storage resources into its state. That avoids two
control planes reconciling the same S3 configuration.

`packet_bucket_name`, `results_bucket_name`, and `artifacts_kms_key_arn` are
verified external inputs. The root derives the corresponding exact S3 ARNs
only to render the IAM policies; it does not create, update, or adopt the
buckets. The exact KMS grants remain `kms:Decrypt` and
`kms:GenerateDataKey`. The packet, manifest, per-case, closure, receipt, and
canonical-publication prefixes remain constrained by the policy templates.

Before any infrastructure operation, an authorized operator must verify the
live COS stack and bucket controls through read-only inventory. After these IAM
roles are applied and configured, the operator must first run one explicitly
approved bounded non-dry-run shard. That shard is the only producer of the
admissible per-case object `VersionId` and immutable shard receipt needed by
`.github/workflows/official-s3-access-validation.yaml`; dry runs and fixture
rehearsals cannot issue those inputs. Capture the exact keys and version before
dispatching that provider-free validation, and require it to pass before the
remaining official shards. A failed, missing, or ambiguous live-storage check
is a halt; it is not permission to add storage resources here.

## Required operational order

The external storage boundary follows one ordered path:

1. Inventory the CloudFormation stack and packet/results bucket controls
   read-only; keep that evidence outside this Terraform state.
2. If prior state contains obsolete S3 addresses, detach only those reviewed
   addresses through the protected state migration, then inventory and import
   existing IAM objects, review the exact plan, and obtain the approved
   protected apply. Do not import or manage the buckets here.
3. Treat dry-run commands and fixture rehearsals as provider-free checks only;
   neither can issue official per-case versions or shard receipts.
4. Run one explicitly approved bounded non-dry-run shard. It is the only
   producer of admissible per-case `VersionId` and immutable shard-receipt
   evidence for storage validation.
5. Capture the exact packet, manifest, per-case, and shard-receipt keys plus
   the per-case `VersionId`, then run
   `.github/workflows/official-s3-access-validation.yaml` from the exact
   trusted `main` SHA.
6. Dispatch the remaining official shards only after that validation passes;
   fan-in remains provider-free and consumes only accepted immutable receipts.

## Exact two-role contract

The two managed roles are:

| Role | Boundary |
| --- | --- |
| `legalforecastbench-official-eval` | GitHub OIDC trust, exact provider-authority DynamoDB data-plane policy, and the cell S3/KMS policy rendered from the verified external inputs. |
| `legalforecastbench-official-eval-fan-in` | GitHub OIDC trust and the provider-free fan-in S3/KMS policy rendered from the verified results bucket and KMS inputs. |

Both roles use exclusive inline-policy and managed-policy-attachment
resources. Inventory any existing role policies before an import or apply;
the exclusive resources deliberately remove unlisted policy surfaces.
Bedrock is disabled by default and remains a separately reviewed cell-only
contract when enabled; global inference profiles remain unsupported by this
root.

## Protected inputs

The protected infrastructure environment supplies the exact values below:

- `LFB_AWS_REGION`
- `LFB_GITHUB_OIDC_PROVIDER_ARN`
- `LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256`
- `LFB_PROVIDER_AUTHORITY_TABLE_ARN`
- `LFB_ARTIFACTS_KMS_KEY_ARN`
- `LFB_PACKET_BUCKET`
- `LFB_RESULTS_BUCKET`

The packet/results names and KMS ARN are external verified values, not
Terraform storage-management identifiers. Lifecycle-rule IDs and retention
settings are intentionally absent from this module and environment contract.
The Terraform input `provider_authority_resource_identity_sha256` is the
lowercase SHA-256 commitment of the exact authority-table ARN.

## IAM-only imports

If the reviewed role names and inline policies already exist, the only
official-eval import addresses are:

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
```

The protected workflow resolves those addresses to fixed reviewed role and
inline-policy IDs using `terraform import`. Bucket names are never import IDs
for this root. Do not run a Terraform import for a bucket, bucket policy, lifecycle configuration,
encryption configuration, versioning configuration, ownership control, or
public-access block.

If an older official-eval state already contains S3 addresses from a prior
revision of this root, inspect that state before planning. Do not accept the
destroy plan produced by simply deleting the configuration. Use the protected
state-only migration operation `detach-external-storage-state` in the protected
workflow; it creates an encrypted
pre-migration backup, removes only the exact closed obsolete S3 addresses that
are present, verifies that no other state address changed, and emits a redacted
receipt. If the reviewed backend is provably fresh and contains no state, no
detachment run is needed. The operation must not change live S3 resources, and
the final plan must contain no S3 address or destroy action.

## Local validation

These checks are provider-free and do not establish live acceptance:

```bash
terraform fmt -check -recursive infra/official-eval
export TF_DATA_DIR="$(mktemp -d)"
terraform -chdir=infra/official-eval init -backend=false -input=false
terraform -chdir=infra/official-eval validate
uv run pytest -q tests/test_official_eval_infra.py
```

The protected workflow may later produce an exact plan, but the plan must
contain only the IAM addresses listed above. Storage ownership and live S3
behavior must continue to be proven by the external COS inventory and the
official S3 validation workflow.
