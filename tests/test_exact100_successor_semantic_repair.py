from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pytest
from legalforecast.ingestion.exact100_successor_semantic_repair import (
    Exact100SuccessorSemanticRepairError,
    VerifiedExact100SuccessorSemanticRepairs,
    _mint_verified_exact100_successor_semantic_repairs,  # pyright: ignore[reportPrivateUsage]
    _replay_verified_exact100_successor_semantic_repairs,  # pyright: ignore[reportPrivateUsage]
    require_verified_exact100_successor_semantic_repairs,
    verify_exact100_successor_semantic_repairs,
)
from reportlab.pdfgen.canvas import Canvas


def test_mint_recognizes_repairs_and_preserves_source_identity() -> None:
    complaint = _pdf(
        (
            "Notice of Removal of Action Under 28 U.S.C. Section 1441",
            "A true and correct copy of the first amended complaint is attached "
            "hereto as Exhibit B.",
            "Exhibit B",
            "Verified First Amended Complaint for Declaratory Relief",
        )
    )
    motion = _pdf(
        (
            "Defendant's Notice of Motion and Motion to Dismiss First Amended "
            "Complaint - Memorandum of Points and Authorities",
            "Memorandum of Points and Authorities Introduction",
            "Argument I. Plaintiff fails to state a claim",
        )
    )
    documents = (
        _document(
            "72309378", "entry-20-motion", "motion_to_dismiss_notice", 20, motion
        ),
        _document("72309378", "entry-1-complaint", "complaint", 1, complaint),
    )
    verified = _mint_verified_exact100_successor_semantic_repairs(
        document_records=documents,
        document_bytes_by_key={
            ("72309378", "entry-1-complaint"): complaint,
            ("72309378", "entry-20-motion"): motion,
        },
    )

    require_verified_exact100_successor_semantic_repairs(verified)
    assert [row["repair_kind"] for row in verified.records] == [
        "embedded_operative_amended_complaint",
        "combined_mtd_memorandum",
    ]
    complaint_row, motion_row = verified.records
    assert complaint_row["schema_version"] == (
        "legalforecast.exact100_successor_semantic_repair.v1"
    )
    assert complaint_row["candidate_id"] == "72309378"
    assert complaint_row["source_document_id"] == "entry-1-complaint"
    assert complaint_row["docket_entry_number"] == 1
    assert complaint_row["original_document_role"] == "complaint"
    assert complaint_row["derived_document_role"] == "amended_complaint"
    assert complaint_row["source_sha256"] == hashlib.sha256(complaint).hexdigest()
    assert complaint_row["source_byte_count"] == len(complaint)
    assert complaint_row["source_metadata_sha256"].startswith("sha256:")
    assert complaint_row["evidence_cues"] == [
        {"cue": "notice_of_removal", "page_number": 1},
        {
            "cue": "first_amended_complaint_attached_as_exhibit_b",
            "page_number": 2,
        },
        {"cue": "exhibit_b_cover", "page_number": 3},
        {"cue": "verified_first_amended_complaint", "page_number": 4},
    ]
    assert motion_row["original_document_role"] == "motion_to_dismiss_notice"
    assert motion_row["derived_document_role"] == "motion_to_dismiss_memorandum"
    assert motion_row["source_sha256"] == hashlib.sha256(motion).hexdigest()
    assert verified.semantic_roles_for(
        candidate_id="72309378", source_document_id="entry-1-complaint"
    ) == ("complaint", "amended_complaint")
    assert verified.derived_roles_for(
        candidate_id="72309378", source_document_id="entry-20-motion"
    ) == ("motion_to_dismiss_memorandum",)
    assert (
        verified.semantic_roles_for(
            candidate_id="missing", source_document_id="missing"
        )
        == ()
    )
    assert verified.records_bytes.endswith(b"\n")


def test_replay_is_exact_and_metadata_must_match_bytes() -> None:
    motion = _pdf(
        (
            "Notice of Motion and Motion to Dismiss - Memorandum of Points "
            "and Authorities",
            "Memorandum of Points and Authorities Introduction",
            "Argument I. Dismissal is required",
        )
    )
    document = _document(
        "candidate-1", "motion-1", "motion_to_dismiss_notice", 8, motion
    )
    minted = _mint_verified_exact100_successor_semantic_repairs(
        document_records=[document],
        document_bytes_by_key={("candidate-1", "motion-1"): motion},
    )
    replayed = _replay_verified_exact100_successor_semantic_repairs(
        persisted_repairs_bytes=minted.records_bytes,
        document_records=[document],
        document_bytes_by_key={("candidate-1", "motion-1"): motion},
    )
    assert replayed.records == minted.records
    with pytest.raises(Exact100SuccessorSemanticRepairError, match="differ"):
        _replay_verified_exact100_successor_semantic_repairs(
            persisted_repairs_bytes=minted.records_bytes + b"\n",
            document_records=[document],
            document_bytes_by_key={("candidate-1", "motion-1"): motion},
        )
    changed = dict(document, byte_count=len(motion) + 1)
    with pytest.raises(
        Exact100SuccessorSemanticRepairError, match="differ from metadata"
    ):
        _mint_verified_exact100_successor_semantic_repairs(
            document_records=[changed],
            document_bytes_by_key={("candidate-1", "motion-1"): motion},
        )


def test_incidental_or_misordered_text_does_not_repair() -> None:
    complaint = _pdf(
        (
            "Notice of Removal",
            "Exhibit B",
            "Verified First Amended Complaint",
            "A true and correct copy of the first amended complaint is attached "
            "hereto as Exhibit B.",
        )
    )
    notice = _pdf(
        (
            "Notice of Motion and Motion to Dismiss and Memorandum of Points "
            "and Authorities",
            "No substantive brief follows this notice.",
        )
    )
    documents = (
        _document("candidate-1", "complaint-1", "complaint", 1, complaint),
        _document("candidate-1", "motion-1", "motion_to_dismiss_notice", 2, notice),
    )
    verified = _mint_verified_exact100_successor_semantic_repairs(
        document_records=documents,
        document_bytes_by_key={
            ("candidate-1", "complaint-1"): complaint,
            ("candidate-1", "motion-1"): notice,
        },
    )
    assert verified.records == ()
    require_verified_exact100_successor_semantic_repairs(verified)


def test_direct_issuer_forgery_and_non_pdf_are_rejected() -> None:
    with pytest.raises(Exact100SuccessorSemanticRepairError, match="direct"):
        verify_exact100_successor_semantic_repairs(document_records=[])

    forged = object.__new__(VerifiedExact100SuccessorSemanticRepairs)
    object.__setattr__(forged, "_verification_seal", object())
    with pytest.raises(Exact100SuccessorSemanticRepairError, match="not produced"):
        require_verified_exact100_successor_semantic_repairs(forged)

    payload = b"not a PDF"
    document = _document(
        "candidate-1", "motion-1", "motion_to_dismiss_notice", 2, payload
    )
    with pytest.raises(Exact100SuccessorSemanticRepairError, match="not a readable"):
        _mint_verified_exact100_successor_semantic_repairs(
            document_records=[document],
            document_bytes_by_key={("candidate-1", "motion-1"): payload},
        )


def _document(
    candidate_id: str,
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    payload: bytes,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "document_role": role,
        "docket_entry_number": docket_entry_number,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        **extra,
    }


def _pdf(page_texts: tuple[str, ...]) -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    for text in page_texts:
        canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()
