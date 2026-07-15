from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from legalforecast.ingestion.disclosure_clearance import (
    DisclosureClearanceError,
    ReviewAuthority,
    build_clearance_records,
    ranked_replacement,
    require_cleared_documents,
    require_cleared_parse_requests,
    require_cleared_parser_records,
    validate_review_receipt,
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
        "controlled_store_provenance": "private-store://cycle1/reviews/batch-001",
        "reviewed_at": "2026-07-12T18:00:00Z",
    }


def _public_evidence() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "restriction_status": "public",
        "restriction_evidence": "courtlistener-public-docket",
    }


def _authority() -> ReviewAuthority:
    artifact = b"fixture review artifact"
    return validate_review_receipt(
        artifact,
        {
            "schema_version": "legalforecast.disclosure_review_receipt.v1",
            "review_artifact_sha256": hashlib.sha256(artifact).hexdigest(),
            "authenticated_reviewer_id": "reviewer:john",
            "controlled_store_uri": "private-store://cycle1/reviews/batch-001",
            "authentication_method": "cloudflare_access_oidc",
            "authenticated_at": "2026-07-12T18:00:00Z",
        },
    )


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
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    assert cleared.status == "cleared"
    assert cleared.reviewer_id == "reviewer:john"
    assert cleared.sha256 == document["sha256"]


@pytest.mark.parametrize("malformed_value", ("true", "false", 1, 0))
def test_malformed_restriction_flags_cannot_be_cleared_as_public(
    tmp_path: Path,
    malformed_value: object,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    public = _public_evidence()
    public["is_sealed"] = malformed_value

    [record] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[public],
    )

    assert record.status == "quarantined"
    assert "field_issealed_malformed" in record.automated_markers


def test_null_restriction_flag_does_not_override_independent_public_evidence(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Public motion memorandum"))
    public = _public_evidence()
    public["is_sealed"] = None

    [record] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[public],
    )

    assert record.status == "cleared"
    assert "field_issealed" not in record.automated_markers


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
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    (tmp_path / str(document["local_path"])).write_bytes(b"tampered")
    with pytest.raises(DisclosureClearanceError, match=r"hash mismatch|bytes changed"):
        require_cleared_documents(
            [document],
            document_root=tmp_path,
            clearance_records=[clearance.to_record()],
        )
    parser_record = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "source_sha256": clearance.sha256,
        "source_byte_count": clearance.byte_count + 1,
    }
    with pytest.raises(DisclosureClearanceError, match="byte-count mismatch"):
        require_cleared_parser_records([parser_record], [clearance.to_record()])


def test_unknown_restriction_and_missing_review_timestamp_fail_closed(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    review = _review(document)
    with pytest.raises(DisclosureClearanceError, match="verified controlled-store"):
        build_clearance_records(
            [document],
            document_root=tmp_path,
            reviews=[review],
            restriction_records=[_public_evidence()],
        )
    [unknown] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[review],
        review_authority=_authority(),
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
            review_authority=_authority(),
            restriction_records=[_public_evidence()],
        )


@pytest.mark.parametrize("evidence", [None, "", [], [" "]])
def test_clearance_gates_reject_public_status_without_restriction_evidence(
    tmp_path: Path, evidence: object
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    forged = clearance.to_record()
    forged["restriction_evidence"] = evidence
    with pytest.raises(DisclosureClearanceError, match="restriction evidence"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[forged]
        )
    request = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "expected_sha256": clearance.sha256,
        "expected_byte_count": clearance.byte_count,
    }
    with pytest.raises(DisclosureClearanceError, match="restriction evidence"):
        require_cleared_parse_requests([request], [forged])


@pytest.mark.parametrize("provenance", [None, "", "https://example.com/review"])
def test_clearance_gates_reject_missing_or_foreign_store_provenance(
    tmp_path: Path, provenance: object
) -> None:
    document = _document(tmp_path, _text_pdf(b"Motion memorandum"))
    [clearance] = build_clearance_records(
        [document],
        document_root=tmp_path,
        reviews=[_review(document)],
        review_authority=_authority(),
        restriction_records=[_public_evidence()],
    )
    forged = clearance.to_record()
    forged["controlled_store_provenance"] = provenance
    with pytest.raises(DisclosureClearanceError, match=r"provenance|private store"):
        require_cleared_documents(
            [document], document_root=tmp_path, clearance_records=[forged]
        )
    parser_record = {
        "candidate_id": "cand-1",
        "source_document_id": "doc-1",
        "source_sha256": clearance.sha256,
        "source_byte_count": clearance.byte_count,
    }
    with pytest.raises(DisclosureClearanceError, match=r"provenance|private store"):
        require_cleared_parser_records([parser_record], [forged])


def test_ranked_replacement_uses_next_cheapest_under_same_cap() -> None:
    frontier = [
        {
            "candidate_id": "a",
            "missing_required_document_count": 0,
            "projected_paid_cost_usd": "0.00",
        },
        {
            "candidate_id": "b",
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "3.05",
        },
        {
            "candidate_id": "c",
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "3.05",
        },
        {
            "candidate_id": "d",
            "missing_required_document_count": 2,
            "projected_paid_cost_usd": "6.10",
        },
    ]
    selected = ranked_replacement(
        frontier,
        quarantined_candidate_id="b",
        already_selected_candidate_ids=("a",),
        spent_or_reserved_usd="3.05",
        max_projected_cost_usd="9.15",
    )
    assert selected.replacement_candidate_id == "c"
    assert selected.write_off_cost_usd == "3.05"


def _text_pdf(text: bytes) -> bytes:
    return b"%PDF-1.4\n/Type /Page\n<< >>\nstream\nBT (" + text + b") Tj ET\nendstream"
