from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/official_eval_environment.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/official-s3-access-validation.yaml").read_text(
    encoding="utf-8"
)
DOCS_README = (ROOT / "docs/README.md").read_text(encoding="utf-8")


def test_official_eval_environment_documents_protected_values() -> None:
    for value in (
        "legalforecastbench-official-eval",
        "legalforecastbench-official-results",
        "secure-gate deployment protection",
        "LFB_AWS_REGION",
        "LFB_PACKET_BUCKET",
        "LFB_RESULTS_BUCKET",
        "LFB_GITHUB_PACKET_READ_ROLE_ARN",
        "LFB_GITHUB_RESULTS_WRITE_ROLE_ARN",
    ):
        assert value in DOC


def test_official_eval_environment_matches_workflow_security_posture() -> None:
    assert "workflow_dispatch" in DOC
    assert "github.ref == 'refs/heads/main'" in DOC
    assert "id-token: write" in DOC
    assert "pull_request" not in WORKFLOW
    assert WORKFLOW.count("id-token: write") == 1
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}" in WORKFLOW


def test_official_eval_environment_documents_allowed_and_denied_access() -> None:
    for allowed in ("model-packets/", "manifests/"):
        assert allowed in DOC
    for denied in (
        "source-documents/",
        "extracted-text/",
        "audit-bundles/",
        "withdrawn/",
        "quarantine/",
    ):
        assert denied in DOC
    assert "write or delete either bucket" in DOC
    assert "Case.dev, PACER, or CourtListener" in DOC


def test_official_eval_environment_documents_revocation_without_keys() -> None:
    assert "Rotation And Revocation" in DOC
    assert "remove or replace `LFB_GITHUB_PACKET_READ_ROLE_ARN`" in DOC
    assert "private vault" in DOC
    assert "Official Evaluation Environment" in DOCS_README
    assert "AWS_ACCESS_KEY_ID" not in DOC
    assert "AWS_SECRET_ACCESS_KEY" not in DOC
