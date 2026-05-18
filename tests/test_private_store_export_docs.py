from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/private_store_export.md").read_text(encoding="utf-8")
DOCS_README = (ROOT / "docs/README.md").read_text(encoding="utf-8")


def test_private_store_export_docs_describe_command_and_inputs() -> None:
    assert "python -m legalforecast.publication.private_store_export" in DOC
    assert "private runbook" in DOC
    for artifact in (
        "document-manifest.jsonl",
        "candidate-manifest.jsonl",
        "packets.jsonl",
        "extracted_texts.jsonl",
        "accounting.jsonl",
    ):
        assert artifact in DOC


def test_private_store_export_docs_describe_private_and_public_outputs() -> None:
    for key in (
        "source-documents/{cycle_id}/{case_id}/{source_document_id}.{ext}",
        "extracted-text/{cycle_id}/extracted_texts.jsonl",
        "model-packets/{cycle_id}/{case_id}/{ablation}.json",
        "audit-bundles/{cycle_id}/acquisition-audit.json",
        "manifests/{cycle_id}.freeze.json",
        "manifests/{cycle_id}.run-inputs.json",
        "manifests/{cycle_id}.public-reconstruction.json",
    ):
        assert key in DOC


def test_private_store_export_docs_pin_publication_boundary() -> None:
    normalized_doc = " ".join(DOC.split())
    for forbidden_public_detail in (
        "raw source-document bytes",
        "extracted filing text",
        "audit bundle content",
        "provider credentials",
        "account IDs",
        "private object-store URLs",
    ):
        assert forbidden_public_detail in normalized_doc
    assert "Private Store Export" in DOCS_README
    assert re.search(r"\b\d{12}\b", DOC) is None
