from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from legalforecast.ingestion import (
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    PacketExclusionNote,
    SourceDocumentProvenance,
    sha256_text,
)


def _retrieved_at() -> datetime:
    return datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _document(
    *,
    source_document_id: str = "doc-34",
    role: DocumentRole = DocumentRole.MTD_MEMORANDUM,
    is_mounted_for_model: bool = True,
    is_predecision_material: bool = True,
    contains_target_outcome: bool = False,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="provider-case-1",
        source_document_id=source_document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        docket_entry_number=34,
        document_role=role,
        retrieved_at=_retrieved_at(),
        source_url_or_reference=f"case.dev/{source_document_id}",
        sha256=sha256_text(source_document_id),
        is_predecision_material=is_predecision_material,
        is_mounted_for_model=is_mounted_for_model,
        contains_target_outcome=contains_target_outcome,
        packet_section="filings",
    )


def test_source_document_provenance_serializes_plan_fields() -> None:
    document = _document()

    record = document.to_record()

    assert record["source_provider"] == "case.dev"
    assert record["source_case_id"] == "provider-case-1"
    assert record["source_document_id"] == "doc-34"
    assert record["document_role"] == "motion_to_dismiss_memorandum"
    assert record["retrieved_at"] == "2026-05-14T12:00:00Z"
    assert record["is_predecision_material"] is True
    assert record["is_mounted_for_model"] is True
    assert record["packet_membership"] == "model_packet"
    json.dumps(record)


def test_model_packet_rejects_post_decision_or_outcome_material() -> None:
    with pytest.raises(ValueError, match="pre-decision"):
        _document(is_predecision_material=False, is_mounted_for_model=True)

    with pytest.raises(ValueError, match="target outcomes"):
        _document(contains_target_outcome=True, is_mounted_for_model=True)


def test_packet_schema_keeps_final_decision_out_of_model_documents() -> None:
    complaint = _document(
        source_document_id="doc-1",
        role=DocumentRole.COMPLAINT,
        is_mounted_for_model=True,
    )
    final_decision = _document(
        source_document_id="doc-99",
        role=DocumentRole.DECISION,
        is_mounted_for_model=False,
        is_predecision_material=False,
        contains_target_outcome=True,
    )
    packet = CasePacketSchema(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        generated_at=_retrieved_at(),
        documents=(complaint, final_decision),
        exclusion_notes=(
            PacketExclusionNote(
                source_document_id="doc-99",
                reason="post_decision_outcome_material",
                notes="Final decision is tracked for labeling but not mounted.",
            ),
        ),
    )

    record = packet.to_record()

    assert [document.source_document_id for document in packet.model_documents] == [
        "doc-1"
    ]
    assert record["model_document_ids"] == ["doc-1"]
    assert record["excluded_document_ids"] == ["doc-99"]
    assert record["exclusion_notes"][0]["reason"] == "post_decision_outcome_material"


def test_extracted_text_artifact_tracks_source_hash_and_quality_flags() -> None:
    artifact = ExtractedTextArtifact(
        source_document_id="doc-34",
        extracted_at=_retrieved_at(),
        extraction_method="pdf_text",
        text_sha256=sha256_text("extracted text"),
        page_count=12,
        quality_flags=("ocr_not_needed",),
    )

    record = artifact.to_record()

    assert record["source_document_id"] == "doc-34"
    assert record["text_sha256"] == sha256_text("extracted text")
    assert record["quality_flags"] == ["ocr_not_needed"]


def test_sha256_validation_rejects_non_hex_digest() -> None:
    with pytest.raises(ValueError, match="sha256"):
        SourceDocumentProvenance(
            source_provider="case.dev",
            source_case_id="provider-case-1",
            source_document_id="doc-34",
            court="S.D.N.Y.",
            docket_number="1:26-cv-00001",
            document_role=DocumentRole.MTD_MEMORANDUM,
            retrieved_at=_retrieved_at(),
            source_url_or_reference="case.dev/doc-34",
            sha256="not-a-real-hash",
            is_predecision_material=True,
            is_mounted_for_model=True,
        )
