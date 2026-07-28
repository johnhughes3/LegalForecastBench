from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "official-paid-labeling.yaml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_has_exact_stage_provider_environment_allowlist() -> None:
    text = _workflow_text()
    for boundary in (
        "llm-unitize:anthropic",
        "llm-review-stage-a:google",
        "llm-label-provider-shard:openai",
        "llm-label-provider-shard:google",
    ):
        assert boundary in text
    for environment in (
        "legalforecastbench-official-labeling-anthropic-unitize",
        "legalforecastbench-official-labeling-google-review",
        "legalforecastbench-official-labeling-openai-label",
        "legalforecastbench-official-labeling-google-label",
    ):
        assert environment in text
    assert (
        "environment: ${{ needs.authorize-boundary.outputs.environment_name }}" in text
    )
    assert "outside the reviewed paid-labeling allowlist" in text


def test_workflow_references_only_generic_provider_and_baton_secrets() -> None:
    text = _workflow_text()

    secret_expressions = re.findall(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}", text)
    assert secret_expressions == ["BATON_AGE_IDENTITY", "PROVIDER_API_KEY"]
    assert text.count("${{ secrets.BATON_AGE_IDENTITY }}") == 1
    assert text.count("${{ secrets.PROVIDER_API_KEY }}") == 1
    assert re.search(r"\bsecrets\s*\[", text) is None
    for forbidden in (
        "secrets.ANTHROPIC_API_KEY",
        "secrets.GEMINI_API_KEY",
        "secrets.GOOGLE_API_KEY",
        "secrets.OPENAI_API_KEY",
        "secrets: inherit",
    ):
        assert forbidden not in text
    assert 'export ANTHROPIC_API_KEY="${LFB_PROVIDER_API_KEY}"' in text
    assert 'export GEMINI_API_KEY="${LFB_PROVIDER_API_KEY}"' in text
    assert 'export OPENAI_API_KEY="${LFB_PROVIDER_API_KEY}"' in text


def test_workflow_uses_distinct_oidc_role_and_clears_before_upload() -> None:
    text = _workflow_text()

    assert "group: official-paid-labeling" in text
    assert "cancel-in-progress: false" in text
    assert "run-provider-stage:" in text
    assert "runs-on: ubuntu-latest" in text
    assert "CI_RUNNER" not in text
    assert "timeout-minutes: 120" in text
    assert "id-token: write" in text
    assert "LFB_GITHUB_LABELING_ROLE_ARN" in text
    assert "LFB_GITHUB_CELL_ROLE_ARN" not in text
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" not in text
    assert "configure-aws-credentials@e6de054" in text
    assert "role-duration-seconds: 7200" in text
    assert text.index(
        "Validate sealed job before authority configuration"
    ) < text.index("Configure exact-table labeling AWS authority")
    assert "--validate-only" in text
    assert "if: ${{ steps.validate_job.outcome == 'success' }}" in text
    assert text.index("Clear temporary credentials") < text.index(
        "Seal encrypted paid-labeling result"
    )
    assert text.index("Clear plaintext paid-labeling state") < text.index(
        "Upload encrypted paid-labeling result"
    )
    assert "id: clear_credentials" in text
    assert "steps.clear_credentials.outcome == 'success'" in text
    assert "id: clear_plaintext" in text
    assert "steps.clear_plaintext.outcome == 'success'" in text
    for credential in (
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_SESSION_TOKEN=",
        "AWS_SECURITY_TOKEN=",
    ):
        assert credential in text


def test_workflow_cannot_substitute_mutable_authority_or_untrusted_release() -> None:
    text = _workflow_text()

    assert "--provider-authority-table" in text
    assert "--expected-provider-account-alias" in text
    assert "job_manifest_sha256" in text
    assert "package_manifest_sha256" in text
    assert "job_artifact_run_attempt" in text
    assert "job_artifact_digest" in text
    assert "sha256sum --check --strict" in text
    assert '[[ "${GITHUB_REF}" != "refs/heads/main" ]]' in text
    assert '[[ "${RELEASE_SHA}" != "${GITHUB_SHA}" ]]' in text
    assert '[[ "$(git rev-parse HEAD)" != "${GITHUB_SHA}" ]]' in text
    assert "git merge-base --is-ancestor" not in text
    assert "git fetch --no-tags origin main" not in text
    assert "official_paid_job" in text
    assert "${{ inputs.provider_authority_table }}" not in text
    assert "${{ inputs.environment_name }}" not in text
    assert "${{ inputs.role_arn }}" not in text
    assert "${{ inputs.provider_account_alias }}" not in text
    assert "${{ inputs.provider_authority_resource_identity_sha256 }}" not in text


def test_workflow_authenticates_producer_and_uploads_only_ciphertext() -> None:
    text = _workflow_text()

    assert '".github/workflows/official-paid-labeling-baton.yaml"' in text
    assert '.event == "workflow_dispatch"' in text
    assert '.head_branch == "main"' in text
    assert ".head_sha == $release_sha" in text
    assert ".run_attempt == $attempt" in text
    assert '.conclusion == "success"' in text
    assert (
        "official-paid-labeling-baton-${{ inputs.job_artifact_run_id }}-"
        "${{ inputs.job_artifact_run_attempt }}" in text
    )
    assert "open-paid-labeling-baton" in text
    assert "seal-paid-labeling-result" in text
    assert "Clear baton decryption identity" in text
    assert "OUTPUT_ROOT: ${{ github.workspace }}/official-paid-labeling-output" in text
    upload = text.split("- name: Upload encrypted paid-labeling result", 1)[1]
    assert "official-paid-labeling-result.age" in upload
    assert "result-receipt.json" in upload
    assert "JOB_ROOT" not in upload
    assert "include-hidden-files: false" in upload
    assert "overwrite: false" in upload
    assert "continue-on-error: true" in text
    assert "PROVIDER_STAGE_OUTCOME: ${{ steps.run_provider_stage.outcome }}" in text


def test_workflow_actions_are_sha_pinned() -> None:
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", _workflow_text(), re.MULTILINE)

    assert uses
    for action in uses:
        if action.startswith("./"):
            continue
        _, reference = action.rsplit("@", 1)
        assert len(reference) == 40
        assert all(character in "0123456789abcdef" for character in reference)
