from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs/private_storage_layout.md").read_text(encoding="utf-8")
DOCS_README = (ROOT / "docs/README.md").read_text(encoding="utf-8")


def test_private_storage_layout_documents_bucket_prefix_contract() -> None:
    for prefix in (
        "source-documents/",
        "extracted-text/",
        "model-packets/",
        "audit-bundles/",
        "withdrawn/",
        "quarantine/",
        "run-cards/",
        "manifests/",
        "metrics/",
        "reports/",
    ):
        assert prefix in DOC


def test_private_storage_layout_documents_manifest_hash_fields() -> None:
    for field in (
        "storage_manifest_version",
        "cycle_id",
        "sha256",
        "size_bytes",
        "content_type",
        "classification",
        "source_handle",
        "redistribution_status",
        "mounted_for_model",
    ):
        assert field in DOC

    assert "SHA-256 digest of the exact object bytes" in DOC
    assert "must refuse to run" in DOC
    assert "manifests/{cycle_id}.run-inputs.json" in DOC
    assert "runner-facing input manifest" in DOC


def test_private_storage_layout_keeps_access_boundaries_explicit() -> None:
    assert "GitHub packet-read role can list/read only" in DOC
    assert "cannot write or" in DOC
    assert "delete either bucket" in DOC
    assert "optional GitHub results-writer role" in DOC
    assert "cos.benchmark.data-operator" in DOC
    assert "cos.benchmark.data-steward" in DOC
    assert "audit-only disposition is marked `mounted_for_model: true`" in DOC


def test_private_storage_layout_documents_public_and_takedown_limits() -> None:
    assert "Public release bundles may include only" in DOC
    assert "public-safe reconstruction manifest" in DOC
    assert "raw court text" in DOC
    assert "private object-store URLs" in DOC
    assert "under compliance-mode object lock" in DOC
    assert "non-sensitive tombstone" in DOC
    assert "public-safe errata record" in DOC
    assert "superseding score bundle" in DOC
    assert "Private Storage Layout" in DOCS_README


def test_private_storage_layout_does_not_record_private_cloud_details() -> None:
    assert re.search(r"\b\d{12}\b", DOC) is None
    for forbidden in (
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "sso_start_url =",
    ):
        assert forbidden not in DOC
