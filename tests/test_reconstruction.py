from __future__ import annotations

import hashlib
import json

import pytest
from legalforecast.publication.reconstruction import (
    VerificationStatus,
    load_reconstruction_plans,
    verify_reconstructed_documents,
    write_reconstruction_plan,
)


def test_load_reconstruction_plans_from_manifest_jsonl(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(_manifest_record()) + "\n", encoding="utf-8")

    plans = load_reconstruction_plans(manifest)
    record = plans[0].to_record()

    assert plans[0].candidate_id == "cand-1"
    assert plans[0].documents[0].source_document_id == "doc-complaint"
    assert plans[0].documents[0].redistribution_policy == (
        "source_handle_and_hash_only"
    )
    assert record["documents"][0]["source_url_or_reference"] == (
        "case.dev://doc-complaint"
    )


def test_write_reconstruction_plan_emits_source_handles_without_text(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(_manifest_record()) + "\n", encoding="utf-8")
    plans = load_reconstruction_plans(manifest)

    output = write_reconstruction_plan(plans, tmp_path / "plan.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload[0]["documents"][0]["source_document_id"] == "doc-complaint"
    assert "docket_text" not in json.dumps(payload)
    assert "source_handle_and_hash_only" in json.dumps(payload)


def test_verify_reconstructed_documents_reports_verified_missing_and_mismatch(
    tmp_path,
) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(_manifest_record()) + "\n", encoding="utf-8")
    plans = load_reconstruction_plans(manifest)
    document_root = tmp_path / "docs"
    document_root.mkdir()
    (document_root / "doc-complaint.txt").write_bytes(b"complaint bytes")
    (document_root / "doc-motion.pdf").write_bytes(b"wrong bytes")

    verifications = verify_reconstructed_documents(plans, document_root)
    by_id = {
        verification.source_document_id: verification for verification in verifications
    }

    assert by_id["doc-complaint"].status is VerificationStatus.VERIFIED
    assert by_id["doc-motion"].status is VerificationStatus.MISMATCH
    assert by_id["doc-reply"].status is VerificationStatus.MISSING
    assert by_id["doc-complaint"].actual_sha256 == _sha256(b"complaint bytes")


def test_verify_reconstructed_documents_rejects_path_like_source_document_id(
    tmp_path,
) -> None:
    manifest_record = _manifest_record()
    documents = manifest_record["documents"]
    assert isinstance(documents, list)
    documents[0]["source_document_id"] = "../outside"
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(manifest_record) + "\n", encoding="utf-8")
    plans = load_reconstruction_plans(manifest)

    with pytest.raises(ValueError, match="source_document_id"):
        verify_reconstructed_documents(plans, tmp_path / "docs")


def _manifest_record() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "manifest_record_hash": _sha256(b"manifest"),
        "documents": [
            {
                "source_document_id": "doc-complaint",
                "source_provider": "case.dev",
                "document_role": "complaint",
                "sha256": _sha256(b"complaint bytes"),
                "source_url_or_reference": "case.dev://doc-complaint",
                "is_mounted_for_model": True,
            },
            {
                "source_document_id": "doc-motion",
                "source_provider": "case.dev",
                "document_role": "mtd_memorandum",
                "sha256": _sha256(b"motion bytes"),
                "source_url_or_reference": "case.dev://doc-motion",
                "is_mounted_for_model": True,
            },
            {
                "source_document_id": "doc-reply",
                "source_provider": "case.dev",
                "document_role": "reply",
                "sha256": _sha256(b"reply bytes"),
                "source_url_or_reference": "case.dev://doc-reply",
                "is_mounted_for_model": True,
            },
        ],
    }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
