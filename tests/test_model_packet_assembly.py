from __future__ import annotations

from datetime import UTC, datetime

import pytest
from legalforecast.ingestion.docket_markdown import (
    ControlledDocketMarkdownEntry,
    DocketMarkdownMetadata,
    render_controlled_docket_markdown,
)
from legalforecast.ingestion.model_packet_assembly import (
    PacketAssemblyError,
    ParsedMarkdownDocument,
    assemble_model_packet,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

_GENERATED_AT = datetime(2026, 5, 17, tzinfo=UTC)


def test_assembler_emits_case_packet_model_packet_and_audit_bundle() -> None:
    assembly = assemble_model_packet(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        generated_at=_GENERATED_AT,
        docket_markdown=_docket_markdown(),
        documents=(
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
            _document("reply", DocumentRole.REPLY, 44),
            _document("core-exhibit", DocumentRole.OTHER, 35, section="exhibits"),
            _document("other-mtd", DocumentRole.MTD_MEMORANDUM, 60),
            _document(
                "decision",
                DocumentRole.DECISION,
                75,
                mounted=False,
                predecision=False,
                outcome=True,
                section="post_decision",
            ),
        ),
        parsed_documents=(
            _parsed("complaint"),
            _parsed("mtd-memo"),
            _parsed("opposition"),
            _parsed("reply"),
            _parsed("core-exhibit"),
            _parsed("other-mtd"),
        ),
        prediction_units=(_unit(),),
        target_docket_entry_numbers=(34, 35, 41, 44),
    )

    assert assembly.case_packet.candidate_id == "cand-1"
    assert [
        document.source_document_id for document in assembly.model_packet.documents
    ] == [
        "cand-1:controlled-docket",
        "complaint",
        "mtd-memo",
        "opposition",
        "reply",
        "core-exhibit",
    ]
    assert "other-mtd" in assembly.excluded_document_ids
    assert "decision" in assembly.excluded_document_ids
    assert (
        "Audit Docket Entries"
        in assembly.audit_bundle["controlled_docket"]["audit_markdown"]
    )
    assert {note.reason for note in assembly.case_packet.exclusion_notes} == {
        "outside_target_motion",
        "audit_only_outcome_or_post_decision",
    }


def test_assembler_reports_missing_reply_without_rejecting_packet() -> None:
    assembly = assemble_model_packet(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        generated_at=_GENERATED_AT,
        docket_markdown=_docket_markdown(),
        documents=(
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
        ),
        parsed_documents=(
            _parsed("complaint"),
            _parsed("mtd-memo"),
            _parsed("opposition"),
        ),
        prediction_units=(_unit(),),
    )

    assert assembly.model_packet.missing_optional_sections == ("reply",)


def test_assembler_rejects_packet_without_operative_complaint() -> None:
    with pytest.raises(PacketAssemblyError, match="operative complaint"):
        assemble_model_packet(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=_GENERATED_AT,
            docket_markdown=_docket_markdown(),
            documents=(_document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),),
            parsed_documents=(_parsed("mtd-memo"),),
            prediction_units=(_unit(),),
        )


def test_assembler_mounts_purchased_core_documents() -> None:
    assembly = assemble_model_packet(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        generated_at=_GENERATED_AT,
        docket_markdown=_docket_markdown(),
        documents=(
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document(
                "purchased-mtd",
                DocumentRole.MTD_MEMORANDUM,
                34,
                provider="case.dev+pacer",
                reference="case.dev+pacer://purchased-mtd",
            ),
        ),
        parsed_documents=(_parsed("complaint"), _parsed("purchased-mtd")),
        prediction_units=(_unit(),),
    )

    purchased = next(
        document
        for document in assembly.model_packet.documents
        if document.source_document_id == "purchased-mtd"
    )
    assert purchased.source_provider == "case.dev+pacer"
    assert purchased.text == "purchased-mtd markdown"


def test_assembler_keeps_audit_only_documents_out_of_model_visibility() -> None:
    assembly = assemble_model_packet(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        generated_at=_GENERATED_AT,
        docket_markdown=_docket_markdown(),
        documents=(
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document(
                "audit-decision",
                DocumentRole.DECISION,
                75,
                mounted=False,
                predecision=False,
                outcome=True,
                section="post_decision",
            ),
            _document(
                "unavailable-core",
                DocumentRole.OPPOSITION,
                41,
                availability=AvailabilityStatus.UNAVAILABLE,
            ),
        ),
        parsed_documents=(_parsed("complaint"), _parsed("mtd-memo")),
        prediction_units=(_unit(),),
    )

    assert "audit-decision" in assembly.excluded_document_ids
    assert "unavailable-core" in assembly.excluded_document_ids
    assert [note.reason for note in assembly.case_packet.exclusion_notes] == [
        "audit_only_outcome_or_post_decision",
        "unavailable",
    ]
    assert all(
        document.source_document_id not in {"audit-decision", "unavailable-core"}
        for document in assembly.model_packet.documents
    )


def _docket_markdown():
    return render_controlled_docket_markdown(
        DocketMarkdownMetadata(
            candidate_id="cand-1",
            case_id="case-1",
            case_name="Example Securities Case",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            source_provider="case.dev",
            source_case_id="case-dev-1",
            source_url="https://example.test/case-dev-1",
            search_query="motion to dismiss securities",
            search_window="2021-01-01..2025-12-31",
            discovered_at="2026-05-17T00:00:00Z",
        ),
        (
            ControlledDocketMarkdownEntry(
                docket_entry_id="entry-1",
                entry_number="1",
                filed_at="2024-01-01",
                entry_text="Complaint filed.",
                packet_section="filings",
                source_document_ids=("complaint",),
            ),
            ControlledDocketMarkdownEntry(
                docket_entry_id="entry-34",
                entry_number="34",
                filed_at="2024-03-01",
                entry_text="Motion to dismiss filed.",
                packet_section="filings",
                source_document_ids=("mtd-memo",),
            ),
            ControlledDocketMarkdownEntry(
                docket_entry_id="entry-75",
                entry_number="75",
                filed_at="2024-10-01",
                entry_text="Order resolving motion.",
                packet_section="post_decision",
                source_document_ids=("decision",),
                is_predecision_material=False,
                contains_target_outcome=True,
            ),
        ),
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    provider: str = "courtlistener",
    reference: str | None = None,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
    section: str = "filings",
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider=provider,
        source_case_id="case-source-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=_GENERATED_AT,
        source_url_or_reference=reference or f"{provider}://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        availability_status=availability,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
        packet_section=section,
    )


def _parsed(document_id: str) -> ParsedMarkdownDocument:
    return ParsedMarkdownDocument(
        source_document_id=document_id,
        markdown=f"{document_id} markdown",
    )


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count-i-issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )
