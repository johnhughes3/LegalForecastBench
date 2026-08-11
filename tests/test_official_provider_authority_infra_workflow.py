from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/official-provider-authority-infra.yaml"
CONTRACT = ROOT / "scripts/official_infra_contract.py"
RUNBOOK = ROOT / "docs/official-run-runbook.md"
TERRAFORM_ROOTS = (
    ROOT / "infra/provider-authority",
    ROOT / "infra/official-labeling",
    ROOT / "infra/official-eval",
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
        r"^\s+- (provider-authority|official-labeling|official-eval)$",
        text,
        re.MULTILINE,
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
        "Unexpected Terraform resource address",
        '"${AGE_ROOT}/age" --encrypt',
        '"${RUNNER_TEMP}/provider-authority-plan.log" 2>&1',
        '"${RUNNER_TEMP}/provider-authority-apply.log" 2>&1',
        "mask-aws-account-id: true",
    )
    contract = CONTRACT.read_text(encoding="utf-8")
    _assert_contains(
        contract,
        '(["no-op"], ["create"], ["update"])',
        '"delete_before_create"',
        '"create_before_destroy"',
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
    assert ":kms:" in text
    assert "immutable KMS key ARN, not an alias" in text


def test_import_and_official_eval_are_closed_and_public_safe() -> None:
    text = _text()
    _assert_contains(
        text,
        "- import",
        "import_address:",
        "import_id_sha256:",
        "import_authorization_sha256:",
        "import_operator_role_identity_sha256:",
        "import_state_backend_identity_sha256:",
        "import_terraform_input_identity_sha256:",
        'module_root="infra/official-eval"',
        'state_key="official-eval/terraform.tfstate"',
        "scripts/official_infra_contract.py resolve-import",
        "scripts/official_infra_contract.py state-binding",
        'terraform -chdir="${MODULE_ROOT}" import',
        'schema_version:"legalforecast.provider_authority_infra_import_receipt.v1"',
        "import-id-sha256",
        "before_state_sha256",
        "after_state_sha256",
        "terraform-output.json.age",
        "AGE_RECIPIENT_IDENTITY_SHA256",
        "terraform_output_sha256",
        "encrypted_output_sha256",
        "official-infra-import-id",
        "legalforecast.provider_authority_infra_import_recovery_receipt.v1",
        "mutation_succeeded=true",
        "Upload import recovery receipt after post-mutation failure",
    )
    assert "import_id:" not in text
    assert 'if [[ "${MODULE}" != "official-eval" ]]; then' in text
    assert (
        'IFS= read -r LFB_IMPORT_ID < "${RUNNER_TEMP}/official-infra-import-id"' in text
    )
    assert 'test ! -e "${RUNNER_TEMP}/official-infra-import-id"' in text
    recovery_upload = text.split(
        "- name: Upload import recovery receipt after post-mutation failure", 1
    )[1]
    assert "steps.import.outputs.mutation_succeeded == 'true'" in recovery_upload
    assert "steps.clear_sensitive.outcome == 'success'" in recovery_upload
    assert "import-recovery-receipt.json" in recovery_upload

    contract = CONTRACT.read_text(encoding="utf-8")
    assert '"LFB_IMPORT_ID":' not in contract
    assert "os.O_EXCL" in contract
    assert "0o600" in contract

    import_upload = text.split("- name: Upload redacted import receipt", 1)[1]
    assert "import-receipt.json" in import_upload
    for forbidden in (
        "terraform.tfstate",
        "terraform-output.json\n",
        "official-infra-import.log",
        "official-infra-state-before.json",
        "official-infra-state-after.json",
    ):
        assert forbidden not in import_upload


def test_protected_job_rechecks_current_main_before_aws_mutation() -> None:
    text = _text()
    main_check = text.index("Prove release is still current main")
    aws_auth = text.index("Configure externally bootstrapped AWS authority")
    terraform_init = text.index("Initialize protected remote state")
    assert main_check < aws_auth < terraform_init
    _assert_contains(
        text[main_check:aws_auth],
        "/git/ref/heads/main",
        '[[ "${current_main_sha}" == "${RELEASE_SHA}" ]]',
    )
