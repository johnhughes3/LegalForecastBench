from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
from tests.official_infra_trust_helpers import (
    job_environment,
    job_grants_id_token_write,
    replace_terraform_local,
    role_assuming_jobs,
    terraform_local_string,
    terraform_variable_default,
    workflow_jobs,
)

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-eval-bootstrap"
POLICY_ROOT = INFRA_ROOT / "policies"
RUNBOOK = ROOT / "docs" / "official-run-runbook.md"
ENVIRONMENT_MANIFEST = ROOT / "infra" / "official-eval" / "github-environments.json"
OPERATOR_WORKFLOW = (
    ROOT / ".github" / "workflows" / "official-provider-authority-infra.yaml"
)
OPERATOR_ENVIRONMENT = "legalforecastbench-official-provider-authority-infra"

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
        assert sid not in statements, f"duplicate statement Sid: {sid}"
        statements[sid] = statement
    return statements


def test_statement_helper_rejects_duplicate_sids() -> None:
    duplicate_policy: dict[str, object] = {
        "Statement": [{"Sid": "Duplicate"}, {"Sid": "Duplicate"}]
    }

    with pytest.raises(AssertionError, match="duplicate statement Sid: Duplicate"):
        _statements(duplicate_policy)


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
    lockfile_arn = f"{BUCKET_ARN}/bootstrap/terraform.tfstate.tflock"
    statements = _statements(bucket_policy)
    for sid in ("DenyNonKmsObjectWrites", "DenyWrongKmsKey"):
        covered_resource = str(statements[sid]["Resource"])
        assert covered_resource.endswith("*")
        assert lockfile_arn.startswith(covered_resource.removesuffix("*"))


def test_operator_trust_is_exact_environment_bound_oidc() -> None:
    github_repository = "example-org/LegalForecastBench"
    policy = _render_policy(
        "github-oidc-trust.json.tftpl",
        github_oidc_provider_arn=OIDC_ARN,
        github_repository=github_repository,
        github_ref="refs/heads/main",
        github_environment=("legalforecastbench-official-provider-authority-infra"),
        github_subject=(
            f"repo:{github_repository}:environment:"
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
                            f"repo:{github_repository}:environment:"
                            "legalforecastbench-official-provider-authority-infra"
                        ),
                        "token.actions.githubusercontent.com:repository": (
                            github_repository
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

    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    github_repository_variable = variables.split(
        'variable "github_repository"', maxsplit=1
    )[1].split('variable "github_environment"', maxsplit=1)[0]
    assert "default" not in github_repository_variable
    assert 'split("/", var.github_repository)' in github_repository_variable


def _assert_operator_trust_satisfiable(
    *,
    locals_text: str,
    variables_text: str,
    workflow_text: str,
    manifest_text: str,
) -> None:
    """Raise unless every pinned operator trust condition stays reachable.

    Reads only production bytes: the bootstrap Terraform locals and variable
    defaults that render github-oidc-trust.json.tftpl, the environment
    manifest, and the operator workflow. Any drift this catches would turn a
    green plan into a deploy-time AssumeRoleWithWebIdentity denial.
    """
    ref = terraform_local_string(locals_text, "github_ref")
    subject = terraform_local_string(locals_text, "github_subject")
    environment = terraform_variable_default(variables_text, "github_environment")

    # The rendered trust must be fed from exactly these locals and variables;
    # otherwise the values parsed above are not the ones AWS evaluates.
    for wiring in (
        r"^\s*github_ref\s*=\s*local\.github_ref\s*$",
        r"^\s*github_environment\s*=\s*var\.github_environment\s*$",
        r"^\s*github_subject\s*=\s*local\.github_subject\s*$",
    ):
        assert re.search(wiring, locals_text, flags=re.MULTILINE), wiring
    assert subject == (
        "repo:${var.github_repository}:environment:${var.github_environment}"
    )

    # `:environment` matches only if the pinned environment is provisioned,
    # with the environment-qualified subject that the trust's `sub` pins.
    loaded: object = json.loads(manifest_text)
    assert isinstance(loaded, dict)
    manifest = cast(dict[str, object], loaded)
    repository = manifest["repository"]
    assert isinstance(repository, str)
    rows = manifest["environments"]
    assert isinstance(rows, list)
    subjects = {
        cast(dict[str, object], row)["name"]: cast(dict[str, object], row)[
            "aws_oidc_subject"
        ]
        for row in cast(list[object], rows)
    }
    assert environment in subjects
    assert subjects[environment] == f"repo:{repository}:environment:{environment}"

    # `:ref` matches only from the single branch the manifest lets these
    # environments deploy from.
    protection = manifest["common_protection"]
    assert isinstance(protection, dict)
    raw_branches = cast(dict[str, object], protection)["custom_branch_policies"]
    assert isinstance(raw_branches, list)
    branches = cast(list[object], raw_branches)
    assert len(branches) == 1
    branch = branches[0]
    assert isinstance(branch, str)
    assert ref == f"refs/heads/{branch}"

    # Only the job that assumes the role emits those claims, so the
    # environment and the OIDC token grant must sit on that exact job. A
    # workflow-wide substring stays green when either binding drifts onto a
    # different job.
    assuming = role_assuming_jobs(workflow_text)
    assert set(assuming) == {"operate"}
    operate = assuming["operate"]
    assert job_environment(operate) == environment
    assert job_grants_id_token_write(operate)

    # The dispatch gate in front of that job pins the same branch the trust
    # names, and the role-assuming job cannot run without it.
    assert (
        f'"${{GITHUB_REF}}" != "{ref}"'
        in workflow_jobs(workflow_text)["validate-request"]
    )
    assert re.search(r"^    needs: validate-request\s*$", operate, flags=re.MULTILINE)


def test_operator_trust_conditions_are_satisfiable_by_the_bootstrap_workflow() -> None:
    """Every pinned claim must be one the operator job actually emits.

    The trust tests `:repository`, `:ref`, and `:environment` on top of
    `aud`/`sub`. All three are real AWS condition keys for the GitHub IdP and
    are populated on protected-environment tokens; docs/github-aws-oidc-trust-
    claims.md records the primary sources behind that, after two reviews
    argued the opposite and one PR deleted the conditions on a false premise.

    The live risk is not the keys, it is drift between a pinned value and what
    the workflow can produce. AWS is explicit that `:environment` only matches
    when "an environment must be configured and provided in the GitHub
    workflow", and `:ref` only matches from a branch the environment permits.
    So the guard binds to the production inputs -- the Terraform locals and
    variable defaults that render the trust, the environment manifest, and
    the one workflow job that assumes the role -- never to test-owned copies
    of those values. The companion mutation test drifts the same production
    bytes to prove this fence discriminates.
    """
    _assert_operator_trust_satisfiable(
        locals_text=(INFRA_ROOT / "locals.tf").read_text(encoding="utf-8"),
        variables_text=(INFRA_ROOT / "variables.tf").read_text(encoding="utf-8"),
        workflow_text=OPERATOR_WORKFLOW.read_text(encoding="utf-8"),
        manifest_text=ENVIRONMENT_MANIFEST.read_text(encoding="utf-8"),
    )

    # Other fences in this module name the operator environment directly; pin
    # that copy to the deployed default so drift cannot hide behind it.
    assert OPERATOR_ENVIRONMENT == terraform_variable_default(
        (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8"),
        "github_environment",
    )


def test_operator_trust_satisfiability_fence_discriminates_on_real_drift() -> None:
    """Drifting the production inputs must redden the satisfiability fence.

    Every case mutates the real bytes -- never a test-owned copy -- and each
    models a drift that a workflow-wide or copy-based check would miss while
    the deployed role became unassumable.
    """
    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    variables_text = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    workflow_text = OPERATOR_WORKFLOW.read_text(encoding="utf-8")
    manifest_text = ENVIRONMENT_MANIFEST.read_text(encoding="utf-8")

    def check(
        *,
        mutated_locals: str | None = None,
        mutated_workflow: str | None = None,
        mutated_manifest: str | None = None,
    ) -> None:
        _assert_operator_trust_satisfiable(
            locals_text=locals_text if mutated_locals is None else mutated_locals,
            variables_text=variables_text,
            workflow_text=(
                workflow_text if mutated_workflow is None else mutated_workflow
            ),
            manifest_text=(
                manifest_text if mutated_manifest is None else mutated_manifest
            ),
        )

    check()

    # Repoint the production ref local at a branch the manifest forbids.
    with pytest.raises(AssertionError):
        check(
            mutated_locals=replace_terraform_local(
                locals_text, "github_ref", "refs/heads/release"
            )
        )

    # Widen the manifest to a second deployable branch.
    widened = manifest_text.replace(
        '"custom_branch_policies": ["main"]',
        '"custom_branch_policies": ["main", "release"]',
    )
    assert widened != manifest_text
    with pytest.raises(AssertionError):
        check(mutated_manifest=widened)

    # Relocate the environment binding onto the non-assuming job. The binding
    # is still present workflow-wide -- exactly the drift the previous
    # workflow-wide substring fence stayed green on.
    environment = terraform_variable_default(variables_text, "github_environment")
    binding = f"\n    environment: {environment}\n"
    assert workflow_text.count(binding) == 1
    relocated = workflow_text.replace(binding, "\n").replace(
        "\n  validate-request:\n", f"\n  validate-request:{binding}", 1
    )
    assert binding in relocated
    with pytest.raises(AssertionError):
        check(mutated_workflow=relocated)

    # Drop the role-assuming job's OIDC token grant.
    grant = "\n      id-token: write"
    assert workflow_text.count(grant) == 1
    with pytest.raises(AssertionError):
        check(mutated_workflow=workflow_text.replace(grant, ""))


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

    assert set(statements) == {
        "EnableAccountAdministration",
        "AllowOperatorUse",
    }
    operator = statements["AllowOperatorUse"]
    assert operator["Principal"] == {"AWS": OPERATOR_ROLE_ARN}
    assert operator["Action"] == [
        "kms:Decrypt",
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
    bash_blocks = re.findall(r"```bash\n(.*?)\n```", readme, re.DOTALL)
    assert bash_blocks
    assert all(block.startswith("set -euo pipefail\n") for block in bash_blocks)
    migration_guard = readme.index("aws s3api list-object-versions")
    migration = readme.index(
        'TF_DATA_DIR="$tf_data_dir" terraform -chdir="$root_dir" init -migrate-state'
    )
    assert migration_guard < migration
    for required_guard in (
        'state_key="bootstrap/terraform.tfstate"',
        ".Versions // []",
        ".DeleteMarkers // []",
        "Reconcile its lineage and serial",
    ):
        assert required_guard in readme
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


def test_backend_lockfile_uses_the_reviewed_sse_kms_configuration() -> None:
    readme = (INFRA_ROOT / "README.md").read_text(encoding="utf-8")
    versions = (INFRA_ROOT / "versions.tf").read_text(encoding="utf-8")
    migration_command = readme.split(
        'terraform -chdir="$root_dir" init -migrate-state', maxsplit=1
    )[1].split("```", maxsplit=1)[0]

    assert 'required_version = ">= 1.11.0"' in versions
    for backend_config in (
        '-backend-config="encrypt=true"',
        '-backend-config="kms_key_id=<exact-kms-key-arn>"',
        '-backend-config="use_lockfile=true"',
    ):
        assert backend_config in migration_command
    assert (
        "The S3 backend applies that same SSE-KMS configuration to its "
        "`.tflock` writes" in readme
    )
