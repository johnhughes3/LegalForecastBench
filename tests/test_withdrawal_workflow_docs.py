from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/withdrawal_workflow.md").read_text(encoding="utf-8")
DOCS_README = (ROOT / "docs/README.md").read_text(encoding="utf-8")


def test_withdrawal_workflow_documents_all_affected_surfaces() -> None:
    for required in (
        "raw documents",
        "extracted text",
        "model packets",
        "audit bundles",
        "GitHub Actions artifacts",
        "releases",
        "public mirrors",
        "search indexes",
        "embeddings",
        "prompts",
        "logs",
    ):
        assert required in DOC


def test_withdrawal_workflow_documents_ledger_and_errata_contracts() -> None:
    for field in (
        "legalforecast-withdrawal-ledger-v1",
        "withdrawal_id",
        "cycle_id",
        "scope",
        "source_document_ids",
        "packet_object_keys",
        "private_tombstone_key",
        "errata_path",
        "supersedes_manifest_sha256",
        "replacement_manifest_sha256",
        "future_use_blocked",
    ):
        assert field in DOC
    assert "public-safe errata record" in DOC
    assert "superseding score bundle" in DOC


def test_withdrawal_workflow_documents_future_run_exclusion() -> None:
    assert "Official workflow matrix construction must load" in DOC
    assert "fail closed" in DOC
    for identifier in (
        "case_id",
        "candidate_id",
        "source_document_ids",
        "packet_object_keys",
    ):
        assert identifier in DOC


def test_withdrawal_workflow_keeps_public_private_boundary_explicit() -> None:
    for forbidden_public_detail in (
        "private object-store URLs",
        "bucket names",
        "account IDs",
        "provider credentials",
        "raw filing text",
    ):
        assert forbidden_public_detail in DOC
    assert "Withdrawal Workflow" in DOCS_README
    assert re.search(r"\b\d{12}\b", DOC) is None
