from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-eval-bootstrap"
POLICY_ROOT = INFRA_ROOT / "policies"
RUNBOOK = ROOT / "docs" / "official-run-runbook.md"

ACCOUNT_ID = "123456789012"
PARTITION = "aws"
REGION = "us-east-1"
BUCKET_ARN = "arn:aws:s3:::lfb-terraform-state-example"
KEY_ARN = f"arn:{PARTITION}:kms:{REGION}:{ACCOUNT_ID}:key/example-key-id"
OIDC_ARN = (
    f"arn:{PARTITION}:iam::{ACCOUNT_ID}:"
    "oidc-provider/token.actions.githubusercontent.com"
)
OPERATOR_ROLE_ARN = (
    f"arn:{PARTITION}:iam::{ACCOUNT_ID}:"
    "role/legalforecastbench-official-provider-authority-infra"
)
TABLE_ARN = (
    f"arn:{PARTITION}:dynamodb:{REGION}:{ACCOUNT_ID}:"
    "table/legalforecastbench-official-eval-provider-authority"
)
LABELING_ROLE_ARN = (
    f"arn:{PARTITION}:iam::{ACCOUNT_ID}:"
    "role/legalforecastbench-official-labeling-authority"
)


def _terraform() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )


def _render_policy(name: str, **values: str) -> dict[str, object]:
    rendered = (POLICY_ROOT / name).read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace(f"${{{key}}}", value)
    assert re.findall(r"\$\{[^}]+\}", rendered) == []
    loaded = json.loads(rendered)
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _statements(policy: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = policy["Statement"]
    assert isinstance(raw, list)
    statements: dict[str, dict[str, object]] = {}
    for item in cast(list[object], raw):
        assert isinstance(item, dict)
        statement = cast(dict[str, object], item)
        sid = statement["Sid"]
        assert isinstance(sid, str)
        statements[sid] = statement
    return statements


def test_root_owns_only_the_bootstrap_trust_anchor() -> None:
    terraform = _terraform()
    resources = set(
        re.findall(r'^resource "([^"]+)" "([^"]+)"', terraform, re.MULTILINE)
    )

    assert resources == {
        ("aws_iam_openid_connect_provider", "github_actions"),
        ("aws_iam_role", "operator"),
        ("aws_iam_role_policy", "operator"),
        ("aws_iam_role_policies_exclusive", "operator"),
        ("aws_iam_role_policy_attachments_exclusive", "operator"),
        ("aws_kms_alias", "terraform_state"),
        ("aws_kms_key", "terraform_state"),
        ("aws_s3_bucket", "terraform_state"),
        ("aws_s3_bucket_ownership_controls", "terraform_state"),
        ("aws_s3_bucket_policy", "terraform_state"),
        ("aws_s3_bucket_public_access_block", "terraform_state"),
        ("aws_s3_bucket_server_side_encryption_configuration", "terraform_state"),
        ("aws_s3_bucket_versioning", "terraform_state"),
    }
    assert terraform.count("prevent_destroy = true") >= 5
    assert "aws_access_key" not in terraform
    assert "aws_iam_access_key" not in terraform


def test_state_storage_is_private_versioned_kms_encrypted_and_tls_only() -> None:
    terraform = _terraform()
    bucket_policy = _render_policy(
        "tls-only-bucket-policy.json.tftpl",
        bucket_arn=BUCKET_ARN,
        kms_key_arn=KEY_ARN,
    )

    for assignment in (
        "block_public_acls       = true",
        "block_public_policy     = true",
        "ignore_public_acls      = true",
        "restrict_public_buckets = true",
        'object_ownership = "BucketOwnerEnforced"',
        'status = "Enabled"',
        'sse_algorithm     = "aws:kms"',
        "bucket_key_enabled = true",
        "enable_key_rotation     = true",
        "multi_region            = false",
        "deletion_window_in_days = 30",
        "force_destroy = false",
    ):
        assert assignment in terraform
    assert "aws_kms_key.terraform_state.arn" in terraform
    assert bucket_policy == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [BUCKET_ARN, f"{BUCKET_ARN}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            },
            {
                "Sid": "DenyNonKmsObjectWrites",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:PutObject",
                "Resource": f"{BUCKET_ARN}/*",
                "Condition": {
                    "StringNotEquals": {"s3:x-amz-server-side-encryption": "aws:kms"}
                },
            },
            {
                "Sid": "DenyWrongKmsKey",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:PutObject",
                "Resource": f"{BUCKET_ARN}/*",
                "Condition": {
                    "StringNotEquals": {
                        "s3:x-amz-server-side-encryption-aws-kms-key-id": KEY_ARN
                    }
                },
            },
        ],
    }


def test_operator_trust_is_exact_environment_bound_oidc() -> None:
    policy = _render_policy(
        "github-oidc-trust.json.tftpl",
        github_oidc_provider_arn=OIDC_ARN,
        github_repository="johnhughes3/LegalForecastBench",
        github_ref="refs/heads/main",
        github_environment=("legalforecastbench-official-provider-authority-infra"),
        github_subject=(
            "repo:johnhughes3/LegalForecastBench:environment:"
            "legalforecastbench-official-provider-authority-infra"
        ),
    )

    assert policy == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "GitHubActionsOidc",
                "Effect": "Allow",
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Principal": {"Federated": OIDC_ARN},
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": (
                            "sts.amazonaws.com"
                        ),
                        "token.actions.githubusercontent.com:sub": (
                            "repo:johnhughes3/LegalForecastBench:environment:"
                            "legalforecastbench-official-provider-authority-infra"
                        ),
                        "token.actions.githubusercontent.com:repository": (
                            "johnhughes3/LegalForecastBench"
                        ),
                        "token.actions.githubusercontent.com:ref": "refs/heads/main",
                        "token.actions.githubusercontent.com:environment": (
                            "legalforecastbench-official-provider-authority-infra"
                        ),
                    }
                },
            }
        ],
    }
    assert "*" not in json.dumps(policy)
    assert "StringLike" not in json.dumps(policy)


def test_operator_policy_cannot_broaden_its_bootstrap_authority() -> None:
    policy = _render_policy(
        "operator-policy.json.tftpl",
        state_bucket_arn=BUCKET_ARN,
        provider_authority_state_key=(
            "official-eval/provider-authority/terraform.tfstate"
        ),
        official_labeling_state_key=(
            "official-eval/official-labeling/terraform.tfstate"
        ),
        kms_key_arn=KEY_ARN,
        kms_via_service="s3.us-east-1.amazonaws.com",
        provider_authority_table_arn=TABLE_ARN,
        official_labeling_role_arn=LABELING_ROLE_ARN,
    )
    statements = _statements(policy)

    assert set(statements) == {
        "ListExactRuntimeState",
        "ReadWriteExactRuntimeState",
        "ManageExactRuntimeStateLocks",
        "UseExactStateKey",
        "ManageExactProviderAuthorityTable",
        "ManageExactOfficialLabelingRole",
    }
    state = statements["ReadWriteExactRuntimeState"]
    assert state["Action"] == ["s3:GetObject", "s3:PutObject"]
    assert all(
        not str(resource).endswith("bootstrap/terraform.tfstate")
        for resource in cast(list[object], state["Resource"])
    )
    locks = statements["ManageExactRuntimeStateLocks"]
    assert locks["Action"] == [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
    ]
    assert all(
        str(resource).endswith(".tflock")
        for resource in cast(list[object], locks["Resource"])
    )
    kms = statements["UseExactStateKey"]
    assert kms["Action"] == [
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:Encrypt",
        "kms:GenerateDataKey",
    ]
    assert kms["Resource"] == KEY_ARN
    assert kms["Condition"] == {
        "StringEquals": {"kms:ViaService": "s3.us-east-1.amazonaws.com"},
        "StringLike": {"kms:EncryptionContext:aws:s3:arn": BUCKET_ARN},
    }

    table = statements["ManageExactProviderAuthorityTable"]
    assert table["Action"] == [
        "dynamodb:CreateTable",
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:ListTagsOfResource",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateTimeToLive",
    ]
    assert table["Resource"] == TABLE_ARN

    labeling = statements["ManageExactOfficialLabelingRole"]
    assert labeling["Action"] == [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:PutRolePolicy",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:UpdateAssumeRolePolicy",
        "iam:UpdateRole",
    ]
    assert labeling["Resource"] == LABELING_ROLE_ARN

    serialized = json.dumps(policy)
    for forbidden in (
        "iam:PassRole",
        "iam:CreateOpenIDConnectProvider",
        "iam:UpdateOpenIDConnectProviderThumbprint",
        "iam:DeleteOpenIDConnectProvider",
        "iam:PutRolePermissionsBoundary",
        "kms:PutKeyPolicy",
        "kms:ScheduleKeyDeletion",
        "s3:PutBucketPolicy",
        "s3:PutBucketPublicAccessBlock",
        OPERATOR_ROLE_ARN,
        '"Resource": "*"',
    ):
        assert forbidden not in serialized


def test_key_policy_grants_operator_use_but_not_administration() -> None:
    policy = _render_policy(
        "kms-key-policy.json.tftpl",
        account_root_arn=f"arn:{PARTITION}:iam::{ACCOUNT_ID}:root",
        operator_role_arn=OPERATOR_ROLE_ARN,
        kms_via_service="s3.us-east-1.amazonaws.com",
        state_bucket_arn=BUCKET_ARN,
    )
    statements = _statements(policy)

    assert set(statements) == {"EnableAccountAdministration", "AllowOperatorUse"}
    operator = statements["AllowOperatorUse"]
    assert operator["Principal"] == {"AWS": OPERATOR_ROLE_ARN}
    assert operator["Action"] == [
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:Encrypt",
        "kms:GenerateDataKey",
    ]
    assert operator["Condition"] == {
        "StringEquals": {"kms:ViaService": "s3.us-east-1.amazonaws.com"},
        "StringLike": {"kms:EncryptionContext:aws:s3:arn": BUCKET_ARN},
    }
    assert '"Principal": "*"' not in json.dumps(policy)


def test_kms_key_waits_for_the_operator_role_and_matches_bucket_key_context() -> None:
    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    storage = (INFRA_ROOT / "storage.tf").read_text(encoding="utf-8")
    operator_policy = (POLICY_ROOT / "operator-policy.json.tftpl").read_text(
        encoding="utf-8"
    )
    key_policy = (POLICY_ROOT / "kms-key-policy.json.tftpl").read_text(encoding="utf-8")

    assert "operator_role_arn     = aws_iam_role.operator.arn" in locals_text
    assert "bucket_key_enabled = true" in storage
    assert (
        '"kms:EncryptionContext:aws:s3:arn": "${state_bucket_arn}"' in operator_policy
    )
    assert '"kms:EncryptionContext:aws:s3:arn": "${state_bucket_arn}"' in key_policy
    assert (
        '${state_bucket_arn}/*"'
        not in operator_policy.split('"Sid": "UseExactStateKey"', maxsplit=1)[1]
    )


def test_runbook_is_import_first_and_migrates_verified_local_state() -> None:
    readme = (INFRA_ROOT / "README.md").read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    gitignore = (INFRA_ROOT / ".gitignore").read_text(encoding="utf-8")

    for required in (
        "separately authorized human/operator AWS credentials",
        "umask 077",
        "LFB_PROTECTED_BOOTSTRAP_STATE_DIR",
        "terraform import",
        "aws_iam_openid_connect_provider.github_actions",
        "terraform init -migrate-state",
        "use_lockfile=true",
        "VersionId",
        "SSEKMSKeyId",
        "zero-drift",
        "Only after all remote-state checks pass",
        'root_dir="$state_dir/root"',
        'cp -rf infra/official-eval-bootstrap "$root_dir"',
        'cp -f "$root_dir/backend.s3.tf.example" "$root_dir/backend.s3.tf"',
        "aws_s3_bucket.terraform_state",
        "aws_kms_key.terraform_state",
        "aws_kms_alias.terraform_state",
        "aws_iam_role.operator",
    ):
        assert required in readme
    assert '-state="$state_dir/terraform.tfstate"' not in readme
    versions = (INFRA_ROOT / "versions.tf").read_text(encoding="utf-8")
    backend_example = (INFRA_ROOT / "backend.s3.tf.example").read_text(encoding="utf-8")
    assert 'backend "s3"' not in versions
    assert 'backend "s3" {}' in backend_example
    assert readme.index("terraform import") < readme.index("terraform plan")
    assert readme.index("terraform apply") < readme.index(
        "terraform init -migrate-state"
    )
    assert readme.index("zero-drift") < readme.index(
        "Only after all remote-state checks pass"
    )
    assert "One-time AWS/Terraform bootstrap trust anchor" in runbook
    for pattern in (
        ".terraform/",
        "*.tfstate",
        "*.tfstate.*",
        "*.tfplan",
        "*.tfvars",
        "*.tfvars.json",
        "crash.log",
        "override.tf",
    ):
        assert pattern in gitignore
    assert ".terraform.lock.hcl" not in gitignore
