from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from legalforecast.ingestion.disclosure_clearance import (
    DisclosureClearanceError,
    build_clearance_records,
    ranked_replacement,
    require_cleared_documents,
)


def _document(tmp_path: Path, content: bytes) -> dict[str, object]:
    path = tmp_path / "cand-1" / "doc-1.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "local_path": "cand-1/doc-1.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_count": len(content),
        "free_or_purchased": "free",
    }


def _review(
    document: dict[str, object], *, status: str = "cleared"
) -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "sha256": document["sha256"],
        "status": status,
        "reviewer_id": "reviewer:john",
        "reviewed_at": "2026-07-12T18:00:00Z",
    }


def _public_evidence() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "restriction_status": "public",
        "restriction_evidence": "courtlistener-public-docket",
    }


def test_ssn_bearing_document_is_quarantined_without_review(tmp_path: Path) -> None:
    document = _document(tmp_path, _text_pdf(b"Client SSN 123-45-6789"))
    [record] = build_clearance_records([document], document_root=tmp_path, reviews=[])
    assert record.status == "quarantined"
    assert "ssn" in record.automated_markers


def test_image_only_pdf_is_quarantined(tmp_path: Path) -> None:
    document = _document(tmp_path, b"%PDF-1.7\n/Type /Image\nstream\x00\x01endstream")
    [record] = build_clearance_records([document], document_root=tmp_path, reviews=[])
    assert "unscannable_or_image_only" in record.automated_markers
    assert record.status == "quarantined"


def test_sealed_evidence_fails_closed_and_cleared_hash_is_recorded(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    [quarantined] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[],
        restriction_records=[
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "is_sealed": True,
            }
        ],
    )
    assert quarantined.status == "quarantined"
    assert "field_issealed" in quarantined.automated_markers

    [cleared] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        restriction_records=[_public_evidence()],
    )
    assert cleared.status == "cleared"
    assert cleared.reviewer_id == "reviewer:john"
    assert cleared.sha256 == document["sha256"]


def test_parse_gate_rejects_uncleared_and_tampered_documents(tmp_path: Path) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    with pytest.raises(DisclosureClearanceError, match="coverage mismatch"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[]
        )
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        restriction_records=[_public_evidence()],
    )
    (tmp_path / str(document["local_path"])).write_bytes(b"tampered")
    with pytest.raises(DisclosureClearanceError, match=r"hash mismatch|bytes changed"):
        require_cleared_documents(
            [document],
            document_root=tmp_path,
            clearance_records=[clearance.to_record()],
        )


def test_unknown_restriction_and_missing_review_timestamp_fail_closed(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    review = _review(document)
    [unknown] = build_clearance_records(
        [document], document_root=tmp_path, reviews=[review]
    )
    assert unknown.status == "quarantined"
    assert "restriction_status_unknown" in unknown.automated_markers

    missing_timestamp = _review(document)
    missing_timestamp.pop("reviewed_at")
    with pytest.raises(DisclosureClearanceError, match="requires reviewed_at"):
        build_clearance_records(
            [document],
            document_root=tmp_path,
            reviews=[missing_timestamp],
            restriction_records=[_public_evidence()],
        )


def test_ranked_replacement_uses_next_cheapest_under_same_cap() -> None:
    frontier = [
        {
            "candidate_id": "a",
            "estimated_purchase_count": 1,
            "estimated_cost_usd": "3.00",
        },
        {
            "candidate_id": "b",
            "estimated_purchase_count": 1,
            "estimated_cost_usd": "4.00",
        },
        {
            "candidate_id": "c",
            "estimated_purchase_count": 2,
            "estimated_cost_usd": "2.00",
        },
    ]
    selected = ranked_replacement(
        frontier,
        quarantined_candidate_id="a",
        already_selected_candidate_ids=(),
        spent_or_reserved_usd="0.00",
        max_projected_cost_usd="9.00",
    )
    assert selected.replacement_candidate_id == "b"


def _text_pdf(text: bytes) -> bytes:
    return b"%PDF-1.4\n/Type /Page\n<< >>\nstream\nBT (" + text + b") Tj ET\nendstream"
