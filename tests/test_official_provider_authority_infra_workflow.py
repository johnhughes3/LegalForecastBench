from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/official-provider-authority-infra.yaml"
RUNBOOK = ROOT / "docs/official-run-runbook.md"
TERRAFORM_ROOTS = (
    ROOT / "infra/provider-authority",
    ROOT / "infra/official-labeling",
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _assert_contains(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text


def test_workflow_is_exact_main_external_authority_only() -> None:
    text = _text()
    _assert_contains(
        text,
        "operation:",
        "module:",
        '[[ "${GITHUB_REF}" != "refs/heads/main" ]]',
        '[[ "${RELEASE_SHA}" != "${GITHUB_SHA}" ]]',
        '[[ "$(git rev-parse HEAD)" != "${GITHUB_SHA}" ]]',
        "environment: legalforecastbench-official-provider-authority-infra",
        "id-token: write",
        "actions: read",
        'backend "s3"',
        "use_lockfile=true",
        "aws-actions/configure-aws-credentials@",
        '.type == "required_reviewers"',
        ".prevent_self_review == false",
        "/deployment-branch-policies?per_page=100",
        '([.[].branch_policies[].name] == ["main"])',
    )
    assert re.search(r"^\s+- (plan|apply)$", text, re.MULTILINE)
    assert re.search(
        r"^\s+- (provider-authority|official-labeling)$", text, re.MULTILINE
    )
    for forbidden in (
        "aws iam create-role",
        "aws iam create-open-id-connect-provider",
        "aws s3api create-bucket",
        "aws kms create-key",
        "gh api --method PUT /repos/",
        "terraform force-unlock",
        "-lock=false",
    ):
        assert forbidden not in text


def test_apply_authenticates_one_plan_without_unavailable_rest_inputs() -> None:
    text = _text()
    _assert_contains(
        text,
        '".github/workflows/official-provider-authority-infra.yaml"',
        '.event == "workflow_dispatch"',
        '.head_branch == "main"',
        ".head_sha == $release_sha",
        ".run_attempt == $attempt",
        '.conclusion == "success"',
        ".digest == $digest",
        "actions/download-artifact@",
        '"${AGE_ROOT}/age" --decrypt',
        "trap 'shred --force --iterations=1 --zero --remove",
        "sha256sum --check --strict",
        'terraform -chdir="${MODULE_ROOT}" apply',
        '.schema_version == "legalforecast.provider_authority_infra_plan_receipt.v1"',
        ".module == $module",
        ".release_sha == $release_sha",
    )
    assert ".inputs." not in text
    for field in (
        "plan_run_id",
        "plan_run_attempt",
        "plan_artifact_name",
        "plan_artifact_digest",
        "plan_file_sha256",
        "operator_role_identity_sha256",
        "state_backend_identity_sha256",
        "terraform_input_identity_sha256",
    ):
        assert text.count(field) >= 2
    apply_receipt = text.split(
        'schema_version:"legalforecast.provider_authority_infra_apply_receipt.v1"', 1
    )[1]
    for field in (
        "plan_run_id",
        "plan_artifact_digest",
        "state_backend_identity_sha256",
    ):
        assert field in apply_receipt


def test_plan_guard_upload_and_authority_are_closed() -> None:
    text = _text()
    _assert_contains(
        text,
        'terraform -chdir="${MODULE_ROOT}" show -json',
        "delete_before_create",
        "create_before_destroy",
        "Unexpected Terraform resource address",
        'all(. == "no-op" or . == "create" or . == "update")',
        '"${AGE_ROOT}/age" --encrypt',
        '"${RUNNER_TEMP}/provider-authority-plan.log" 2>&1',
        '"${RUNNER_TEMP}/provider-authority-apply.log" 2>&1',
        "mask-aws-account-id: true",
    )
    upload = text.split("- name: Upload encrypted reviewed plan", 1)[1].split(
        "- name: Upload redacted apply receipt", 1
    )[0]
    _assert_contains(
        upload,
        "provider-authority.tfplan.age",
        "plan-receipt.json",
        "include-hidden-files: false",
        "overwrite: false",
    )
    assert "provider-authority.tfplan\n" not in upload
    assert "terraform.tfstate" not in upload
    for forbidden in (
        "PROVIDER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "run-benchmark",
        "legalforecast freeze",
        "gh workflow run",
        "actions: write",
    ):
        assert forbidden not in text


def test_runbook_and_toolchain_define_the_reviewed_boundary() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for name in (
        "LFB_INFRA_PLAN_AGE_IDENTITY",
        "LFB_INFRA_OPERATOR_ROLE_ARN",
        "LFB_TERRAFORM_STATE_BUCKET",
        "LFB_TERRAFORM_STATE_KMS_KEY_ID",
        "LFB_GITHUB_OIDC_PROVIDER_ARN",
        "LFB_PROVIDER_AUTHORITY_TABLE_ARN",
    ):
        assert name in runbook
    _assert_contains(
        runbook,
        "This is a nonblocking distributed-authority and later-evaluation path",
        "does not block the canonical Cycle 1 local-journal Stage A or Stage B stages",
        "It contains no provider key",
        "A plan dispatch does not authorize apply.",
        "independently retained age identity",
        'repository/infra/provider-authority" show -no-color',
        'terraform_version)" = "1.13.5"',
        'age --version)" = "v1.3.1"',
    )
    assert "terraform_version: 1.13.5" in _text()
    assert "keep paid labeling blocked" not in runbook
    for root in TERRAFORM_ROOTS:
        lock = (root / ".terraform.lock.hcl").read_text(encoding="utf-8")
        _assert_contains(
            lock,
            'provider "registry.terraform.io/hashicorp/aws"',
            'version     = "6.56.0"',
            "zh:",
        )


def test_workflow_actions_are_sha_pinned() -> None:
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", _text(), re.MULTILINE)
    assert uses
    assert all(
        len(reference) == 40
        and all(character in "0123456789abcdef" for character in reference)
        for _, reference in (action.rsplit("@", 1) for action in uses)
    )


def test_aws_region_is_fail_closed_external_bootstrap() -> None:
    """The region must be bootstrapped, never silently defaulted.

    The Terraform state bucket and KMS key are region-bound external resources,
    so a fallback region would point the backend at the wrong account state
    while still appearing to satisfy the bootstrap contract.
    """

    text = _text()
    assert "LFB_AWS_REGION\n" in text.split("required=(", maxsplit=1)[1].split(")")[0]
    assert "us-east-1" not in text
    assert "vars.LFB_AWS_REGION ||" not in text
    assert "LFB_AWS_REGION" in RUNBOOK.read_text(encoding="utf-8")
