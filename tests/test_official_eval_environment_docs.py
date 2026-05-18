from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/official_eval_environment.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/official-s3-access-validation.yaml").read_text(
    encoding="utf-8"
)
MATRIX_WORKFLOW = (ROOT / ".github/workflows/official-eval-matrix.yaml").read_text(
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
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
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


def test_official_eval_environment_documents_actions_artifact_guardrails() -> None:
    assert "artifact_retention_days" in DOC
    assert "1 through 90 days" in DOC
    assert "actions/upload-artifact" in DOC
    assert "runner-log.jsonl" in DOC
    assert "publication_guardrails" in DOC
    assert "model_registry_uri" in DOC
    assert "--backend live" in DOC
    assert "--model-registry" in DOC
    assert "--model-key" in DOC
    assert "raw PDFs" in DOC
    assert "provider account IDs" in DOC
    assert "retention-days: ${{ fromJSON(" in MATRIX_WORKFLOW
    assert "path: tmp/official-eval/" in MATRIX_WORKFLOW
    assert "model-packet.json" not in MATRIX_WORKFLOW


def test_official_eval_environment_documents_revocation_without_keys() -> None:
    normalized_doc = " ".join(DOC.split())
    assert "Rotation And Revocation" in DOC
    assert "remove or replace `LFB_GITHUB_PACKET_READ_ROLE_ARN`" in DOC
    assert "private vault" in DOC
    assert "local credentials must not be used inside GitHub Actions" in normalized_doc
    assert "Official Evaluation Environment" in DOCS_README
    assert "AWS_ACCESS_KEY_ID" not in DOC
    assert "AWS_SECRET_ACCESS_KEY" not in DOC
