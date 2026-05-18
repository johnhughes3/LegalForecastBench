from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/official-s3-access-validation.yaml").read_text(
    encoding="utf-8",
)


def test_official_s3_workflow_is_manual_and_protected() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "secure-gate deployment protection" in WORKFLOW
    assert "github.ref == 'refs/heads/main'" in WORKFLOW
    assert "Official LegalForecastBench S3 validation is allowed only from" in WORKFLOW
    assert "release_sha must be reachable from origin/main" in WORKFLOW


def test_official_s3_workflow_scopes_oidc_to_the_protected_job() -> None:
    assert WORKFLOW.count("id-token: write") == 1
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}" in WORKFLOW
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN: ${{ vars." in WORKFLOW
    assert (
        "aws-actions/configure-aws-credentials@d979d5b3a71173a29b74b5b88418bfda9437d885"
    ) in WORKFLOW
    assert "AWS_ACCESS_KEY_ID" not in WORKFLOW
    assert "AWS_SECRET_ACCESS_KEY" not in WORKFLOW


def test_official_s3_workflow_consumes_only_the_read_contract() -> None:
    assert "LFB_PACKET_BUCKET: ${{ vars.LFB_PACKET_BUCKET }}" in WORKFLOW
    assert "LFB_RESULTS_BUCKET: ${{ vars.LFB_RESULTS_BUCKET }}" in WORKFLOW
    assert "LFB_MODEL_PACKET_PREFIX" in WORKFLOW
    assert "model-packets/" in WORKFLOW
    assert "LFB_RESULTS_MANIFEST_PREFIX" in WORKFLOW
    assert "manifests/" in WORKFLOW
    assert "aws s3api list-objects-v2" in WORKFLOW
    assert "aws s3api head-object" in WORKFLOW


def test_official_s3_workflow_checks_denied_private_prefixes() -> None:
    assert "AccessDenied|Forbidden|403" in WORKFLOW
    for prefix in (
        "source-documents/",
        "extracted-text/",
        "audit-bundles/",
        "withdrawn/",
        "quarantine/",
    ):
        assert prefix in WORKFLOW


def test_official_s3_workflow_does_not_mutate_aws_or_s3_state() -> None:
    forbidden_snippets = (
        "cdk deploy",
        "cloudformation",
        "create-stack",
        "delete-stack",
        "s3api put-object",
        "s3api delete-object",
        "aws s3 cp",
        "iam create-",
        "iam delete-",
        "iam put-",
    )
    lowered = WORKFLOW.lower()
    for snippet in forbidden_snippets:
        assert snippet not in lowered
