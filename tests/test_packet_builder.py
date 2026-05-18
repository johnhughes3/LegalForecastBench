from __future__ import annotations

from datetime import UTC, datetime

import pytest
from legalforecast.evals.packet_builder import (
    PacketAblation,
    PacketText,
    build_model_packet,
    texts_from_mapping,
)
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_full_packet_excludes_decision_and_includes_predecision_hashes() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
            _document("reply", DocumentRole.REPLY, 44),
            _document(
                "decision",
                DocumentRole.DECISION,
                50,
                mounted=False,
                predecision=False,
                outcome=True,
            ),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-memo", "opposition", "reply"),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
    )
    record = packet.to_record()

    assert [document["source_document_id"] for document in record["documents"]] == [
        "complaint",
        "mtd-memo",
        "opposition",
        "reply",
    ]
    assert "decision" in record["excluded_document_ids"]
    assert record["source_hashes"]["complaint"] == sha256_text("complaint source")
    assert record["metadata"]["judge"] == "Judge Example"
    assert "source_citations" not in record["prediction_units"][0]


def test_no_briefs_ablation_keeps_complaint_and_notice_only() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-notice", DocumentRole.MTD_NOTICE, 33),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-notice", "mtd-memo", "opposition"),
        ablation=PacketAblation.NO_BRIEFS,
    )

    assert [document.source_document_id for document in packet.documents] == [
        "complaint",
        "mtd-notice",
    ]
    assert packet.excluded_document_ids == ("mtd-memo", "opposition")
    assert packet.ablation is PacketAblation.NO_BRIEFS


def test_metadata_only_ablation_mounts_no_document_text() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-memo", "opposition"),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
        ablation=PacketAblation.METADATA_ONLY,
    )

    assert packet.documents == ()
    assert packet.excluded_document_ids == ("complaint", "mtd-memo", "opposition")
    assert packet.metadata["judge"] == "Judge Example"
    assert packet.ablation is PacketAblation.METADATA_ONLY


def test_briefs_only_redacted_ablation_mounts_briefs_and_redacts_judge() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-notice", DocumentRole.MTD_NOTICE, 33),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
            _document("reply", DocumentRole.REPLY, 44),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-notice", "mtd-memo", "opposition", "reply"),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
        ablation=PacketAblation.BRIEFS_ONLY_REDACTED,
    )

    assert [document.source_document_id for document in packet.documents] == [
        "mtd-memo",
        "opposition",
        "reply",
    ]
    assert packet.excluded_document_ids == ("complaint", "mtd-notice")
    assert packet.metadata["judge"] == "[redacted]"
    assert packet.metadata["nos_macro_category"] == "securities"


def test_judge_removed_ablation_keeps_packet_and_redacts_judge_metadata() -> None:
    packet = build_model_packet(
        case_packet=_case_packet(
            [
                _document("complaint", DocumentRole.COMPLAINT, 1),
                _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            ]
        ),
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-memo"),
        metadata={"judge": "Judge Example", "court": "S.D.N.Y."},
        ablation=PacketAblation.JUDGE_REMOVED,
    )

    assert [document.source_document_id for document in packet.documents] == [
        "complaint",
        "mtd-memo",
    ]
    assert packet.metadata == {"judge": "[redacted]", "court": "S.D.N.Y."}


def test_missing_reply_is_reported_but_not_required() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document("opposition", DocumentRole.OPPOSITION, 41),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-memo", "opposition"),
    )

    assert packet.missing_optional_sections == ("reply",)


def test_target_docket_entries_filter_multiple_motions() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("target-mtd", DocumentRole.MTD_MEMORANDUM, 34),
            _document("other-mtd", DocumentRole.MTD_MEMORANDUM, 60),
            _document("target-opposition", DocumentRole.OPPOSITION, 41),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "target-mtd", "other-mtd", "target-opposition"),
        target_docket_entry_numbers=(34, 41),
    )

    assert [document.source_document_id for document in packet.documents] == [
        "complaint",
        "target-mtd",
        "target-opposition",
    ]
    assert packet.excluded_document_ids == ("other-mtd",)


def test_related_case_metadata_is_preserved_without_mounting_outcome_material() -> None:
    case_packet = _case_packet(
        [
            _document("complaint", DocumentRole.COMPLAINT, 1),
            _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            _document(
                "related-decision",
                DocumentRole.DECISION,
                75,
                mounted=False,
                predecision=False,
                outcome=True,
            ),
        ]
    )

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=(_unit(),),
        texts=_texts("complaint", "mtd-memo"),
        metadata={"related_case_risk": "related_case_risk"},
        related_family_id="family-123",
        mdl_family_id="mdl-456",
    )

    assert packet.related_family_id == "family-123"
    assert packet.mdl_family_id == "mdl-456"
    assert packet.to_record()["mdl_family_id"] == "mdl-456"
    assert "related-decision" in packet.excluded_document_ids
    assert all(
        document.source_document_id != "related-decision"
        for document in packet.documents
    )


def test_ocr_normalized_text_artifact_is_carried_into_packet() -> None:
    artifact = ExtractedTextArtifact(
        source_document_id="complaint",
        extracted_at=datetime(2026, 5, 14, tzinfo=UTC),
        extraction_method="ocr",
        text_sha256=sha256_text("Motion to dismiss Count I"),
        page_count=1,
        quality_flags=("ocr_applied", "ocr_noise_repaired"),
    )

    packet = build_model_packet(
        case_packet=_case_packet([_document("complaint", DocumentRole.COMPLAINT, 1)]),
        prediction_units=(_unit(),),
        texts=texts_from_mapping(
            {"complaint": "Motion to dismiss Count I"},
            artifacts=(artifact,),
        ),
    )

    assert packet.documents[0].extraction_method == "ocr"
    assert packet.documents[0].quality_flags == ("ocr_applied", "ocr_noise_repaired")
    assert packet.documents[0].text_sha256 == artifact.text_sha256


def test_packet_builder_rejects_missing_text_for_mounted_document() -> None:
    with pytest.raises(ValueError, match="missing extracted text"):
        build_model_packet(
            case_packet=_case_packet(
                [_document("complaint", DocumentRole.COMPLAINT, 1)]
            ),
            prediction_units=(_unit(),),
            texts=(),
        )


def _case_packet(
    documents: list[SourceDocumentProvenance],
) -> CasePacketSchema:
    return CasePacketSchema(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        generated_at=datetime(2026, 5, 14, tzinfo=UTC),
        documents=tuple(documents),
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"case.dev://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
        packet_section="filings",
    )


def _texts(*document_ids: str) -> tuple[PacketText, ...]:
    return tuple(
        PacketText(source_document_id=document_id, text=f"{document_id} text")
        for document_id in document_ids
    )


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count_i_issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )
