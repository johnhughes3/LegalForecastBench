"""Compatibility tests for the public owner-signed corpus manifest record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import (
    AUDIT_ONLY_DOCUMENT_ROLES,
    MODEL_VISIBLE_DOCUMENT_ROLES,
    REQUIRED_CLAIM_BEARING_ROLES,
    REQUIRED_TARGET_MOTION_ROLES,
    CorpusManifest,
    CorpusManifestError,
    load_signed_manifest,
    load_signed_manifest_bytes,
    manifest_digest,
)
from legalforecast.ingestion.provenance import DocumentRole

# This is a small legacy record in the public owner-signed format.  It keeps
# the field names and nested values emitted by the immutable compatibility
# source, while remaining synthetic and free of corpus bytes.
_LEGACY_RECORD: dict[str, Any] = {
    "cases": [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "court": "D. Del.",
            "decision_date": "2024-06-01",
            "docket_number": "1:24-cv-1",
            "documents": [
                {
                    "byte_role_verdict": None,
                    "docket_entry_number": 1,
                    "document_role": "complaint",
                    "markdown_path": "markdown/cand-1/complaint.md",
                    "markdown_sha256": "1" * 64,
                    "model_visible": True,
                    "pdf_path": "documents/complaint.pdf",
                    "pdf_sha256": "2" * 64,
                    "source_document_id": "doc-complaint",
                    "source_url": "https://example.invalid/doc-complaint.pdf",
                    "validation_basis": "synthetic",
                },
                {
                    "byte_role_verdict": None,
                    "docket_entry_number": 12,
                    "document_role": "motion_to_dismiss_notice",
                    "markdown_path": "markdown/cand-1/mtd.md",
                    "markdown_sha256": "3" * 64,
                    "model_visible": True,
                    "pdf_path": "documents/mtd.pdf",
                    "pdf_sha256": "4" * 64,
                    "source_document_id": "doc-mtd",
                    "source_url": "https://example.invalid/doc-mtd.pdf",
                    "validation_basis": "synthetic",
                },
                {
                    "byte_role_verdict": "audit",
                    "docket_entry_number": 40,
                    "document_role": "decision",
                    "markdown_path": None,
                    "markdown_sha256": None,
                    "model_visible": False,
                    "pdf_path": "documents/decision.pdf",
                    "pdf_sha256": "5" * 64,
                    "source_document_id": "doc-decision",
                    "source_url": "https://example.invalid/doc-decision.pdf",
                    "validation_basis": "synthetic",
                },
            ],
            "target_motion_entry_numbers": [12],
            "unresolved_audit_only_document_ids": ["doc-order"],
        }
    ],
    "cycle_id": "cycle-1",
    "generated_at": "2024-06-02T00:00:00Z",
    "prediction_units_source": {"path": "prediction-units.jsonl", "sha256": "a" * 64},
    "schema_version": "legalforecast.owner_signed_corpus_manifest.v1",
    "selection_source": {"path": "selection.jsonl", "sha256": "b" * 64},
}
_LEGACY_DIGEST = "21cec48ce617e36f28d46b6cea7e4505b3bb40ae9d8e0cbf7102683a01addf5e"


def _signed_record() -> dict[str, Any]:
    return {**_LEGACY_RECORD, "manifest_sha256": _LEGACY_DIGEST}


def test_legacy_record_round_trips_with_original_serialization() -> None:
    manifest = CorpusManifest.from_record(_LEGACY_RECORD)

    assert manifest.to_record() == _LEGACY_RECORD
    assert manifest.digest() == _LEGACY_DIGEST
    assert manifest.to_signed_record() == _signed_record()
    assert manifest_digest(_LEGACY_RECORD) == _LEGACY_DIGEST


def test_signed_legacy_record_loads_from_bytes_and_path(tmp_path: Path) -> None:
    payload = json.dumps(_signed_record(), separators=(",", ":")).encode("utf-8")
    path = tmp_path / "manifest.json"
    path.write_bytes(payload)

    from_bytes = load_signed_manifest_bytes(payload, expected_digest=_LEGACY_DIGEST)
    from_path = load_signed_manifest(path, expected_digest=_LEGACY_DIGEST)

    assert from_bytes == from_path
    assert from_bytes.cases[0].model_visible_documents[0].source_document_id == (
        "doc-complaint"
    )
    assert from_bytes.cases[0].unresolved_audit_only_document_ids == ("doc-order",)


def test_signed_legacy_record_rejects_tampering_and_resigning(tmp_path: Path) -> None:
    tampered = _signed_record()
    tampered_case = dict(tampered["cases"][0])
    tampered_case["court"] = "D. Elsewhere"
    tampered["cases"] = [tampered_case]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(CorpusManifestError, match="do not match the digest"):
        load_signed_manifest(path, expected_digest=_LEGACY_DIGEST)

    resigned = {**tampered, "manifest_sha256": manifest_digest(tampered)}
    with pytest.raises(CorpusManifestError, match="expected digest"):
        load_signed_manifest_bytes(
            json.dumps(resigned).encode("utf-8"), expected_digest=_LEGACY_DIGEST
        )


def test_public_role_partitions_keep_legacy_manifest_semantics() -> None:
    assert not MODEL_VISIBLE_DOCUMENT_ROLES & AUDIT_ONLY_DOCUMENT_ROLES
    assert MODEL_VISIBLE_DOCUMENT_ROLES | AUDIT_ONLY_DOCUMENT_ROLES == set(DocumentRole)
    assert DocumentRole.DECISION in AUDIT_ONLY_DOCUMENT_ROLES
    assert DocumentRole.ORDER in AUDIT_ONLY_DOCUMENT_ROLES
    assert DocumentRole.COMPLAINT in REQUIRED_CLAIM_BEARING_ROLES
    assert DocumentRole.MTD_NOTICE in REQUIRED_TARGET_MOTION_ROLES
