from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/official-provider-authority-infra.yaml"
CONTRACT = ROOT / "scripts/official_infra_contract.py"
GATE_PACK = ROOT / "docs/official-run-gate-pack.md"
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
        '([.reviewers[].reviewer.login] == ["johnjhughes"])',
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
        "jq -cn --arg role",
        "Do not switch to `jq -cnS`",
        "require `johnjhughes`",
        "Because `johnjhughes` is the sole reviewer",
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


def test_terraform_input_identity_recipes_share_exact_module_shapes() -> None:
    workflow = _text()
    workflow_identity = workflow.rsplit('case "${MODULE}" in', 1)[1].split(
        "age_recipient_identity_sha256", 1
    )[0]
    gate_pack = GATE_PACK.read_text(encoding="utf-8")
    gate_pack_identity = gate_pack.split('TERRAFORM_INPUT_IDENTITY_SHA256="$(', 1)[
        1
    ].split("\n```", 1)[0]
    runbook = RUNBOOK.read_text(encoding="utf-8")
    runbook_identity = runbook.split('case "$module" in', 1)[1].split(
        "Keep the raw import ID", 1
    )[0]

    eval_fields = (
        "module:$module",
        "region:$region",
        "oidc:$oidc",
        "artifacts_kms_key:$artifacts_kms_key",
        "identity:$identity",
        "packet_bucket:$packet_bucket",
        "results_bucket:$results_bucket",
        "table:$table",
    )
    for source in (workflow_identity, gate_pack_identity, runbook_identity):
        positions = [source.index(field) for field in eval_fields]
        assert positions == sorted(positions)
        for field in eval_fields:
            assert field in source

    for module, fields in {
        "official-labeling": (
            "module:$module",
            "region:$region",
            "oidc:$oidc",
            "identity:$identity",
            "table:$table",
        ),
        "provider-authority": ("module:$module", "region:$region"),
    }.items():
        workflow_module = workflow_identity.split(f"{module})", 1)[1].split(";;", 1)[0]
        runbook_module = runbook_identity.split(f"{module})", 1)[1].split(";;", 1)[0]
        for source in (workflow_module, runbook_module):
            positions = [source.index(field) for field in fields]
            assert positions == sorted(positions)
            for field in fields:
                assert field in source
            assert "artifacts_kms_key:" not in source
            assert "packet_bucket:" not in source
            assert "results_bucket:" not in source


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
        "astral-sh/setup-uv@",
        "uv sync --locked",
        "uv run python scripts/official_infra_contract.py resolve-import",
        "uv run python scripts/official_infra_contract.py state-binding",
        "uv run python scripts/official_infra_contract.py validate-plan",
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
        "legalforecast.provider_authority_infra_apply_recovery_receipt.v1",
        "applied_pending_output_handoff",
        "Upload apply recovery receipt after post-mutation failure",
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


def test_external_storage_state_detach_is_closed_backed_up_and_s3_read_only() -> None:
    text = _text()
    step = text.split("- name: Detach obsolete external-storage state bindings", 1)[
        1
    ].split("- name: Produce and guard exact Terraform plan", 1)[0]
    obsolete_block = step.split("cat > \"${obsolete_addresses}\" <<'EOF'", 1)[1].split(
        "EOF", 1
    )[0]
    obsolete_addresses = {
        line.strip() for line in obsolete_block.splitlines() if line.strip()
    }
    assert obsolete_addresses == {
        f"aws_s3_{kind}.{name}"
        for kind in (
            "bucket",
            "bucket_lifecycle_configuration",
            "bucket_ownership_controls",
            "bucket_policy",
            "bucket_public_access_block",
            "bucket_server_side_encryption_configuration",
            "bucket_versioning",
        )
        for name in ("packet", "results")
    }
    _assert_contains(
        text,
        "- detach-external-storage-state",
        '[[ "${MODULE}" == "official-eval" ]]',
        "State-detachment provenance inputs must remain empty.",
    )
    _assert_contains(
        step,
        'terraform -chdir="${MODULE_ROOT}" state pull',
        'terraform -chdir="${MODULE_ROOT}" state list',
        '"${AGE_ROOT}/age" --encrypt',
        'terraform -chdir="${MODULE_ROOT}" state rm "${addresses_to_remove[@]}"',
        'cmp --silent "${expected_after_addresses}" "${after_addresses}"',
        "legalforecast.official_eval_external_storage_state_detach.v1",
        "legalforecast.official_eval_external_storage_state_detach_recovery.v1",
        "before_state_sha256",
        "after_state_sha256",
        "encrypted_backup_sha256",
        "removed_addresses",
    )
    assert step.index('"${AGE_ROOT}/age" --encrypt') < step.index(
        'terraform -chdir="${MODULE_ROOT}" state rm'
    )
    assert "aws s3" not in step
    assert "terraform apply" not in step

    success_upload = text.split(
        "- name: Upload encrypted pre-migration state and redacted detach receipt", 1
    )[1].split("- name: Upload apply recovery receipt", 1)[0]
    _assert_contains(
        success_upload,
        "official-eval-state-before.tfstate.age",
        "state-detach-receipt.json",
        "include-hidden-files: false",
        "overwrite: false",
    )
    recovery_upload = text.split(
        "- name: Upload state-detach recovery receipt after post-mutation failure", 1
    )[1]
    _assert_contains(
        recovery_upload,
        "steps.detach_storage_state.outcome != 'success'",
        "steps.clear_sensitive.outcome == 'success'",
        "official-eval-state-before.tfstate.age",
        "state-detach-recovery-receipt.json",
    )

    gate_pack = GATE_PACK.read_text(encoding="utf-8")
    assert "Plan: 23 to add" not in gate_pack
    assert gate_pack.index("read-only CloudFormation and S3") < gate_pack.index(
        "operation=detach-external-storage-state"
    )
    assert gate_pack.index("operation=detach-external-storage-state") < gate_pack.index(
        "operation=plan"
    )
    assert gate_pack.index("operation=apply") < gate_pack.rindex(
        "gh workflow run .github/workflows/official-s3-access-validation.yaml"
    )


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
