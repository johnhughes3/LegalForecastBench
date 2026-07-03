"""Model packet construction for pre-decision benchmark materials."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.unitization.schemas import PredictionUnit


class PacketAblation(StrEnum):
    """Packet views used for headline and ablation model runs."""

    METADATA_ONLY = "metadata_only"
    BRIEFS_ONLY_REDACTED = "briefs_only_redacted"
    JUDGE_REMOVED = "judge_removed"
    FULL_PACKET = "full_packet"
    NO_BRIEFS = "no_briefs"


_ALWAYS_VISIBLE_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.DOCKET_HISTORY,
    }
)
_BRIEF_ROLES = frozenset(
    {
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
    }
)
_OUTCOME_ROLES = frozenset({DocumentRole.ORDER, DocumentRole.DECISION})
_EXHIBIT_PACKET_SECTION = "exhibits"


@dataclass(frozen=True, slots=True)
class PacketText:
    """Model-visible extracted text for one source document."""

    source_document_id: str
    text: str
    text_sha256: str | None = None
    quality_flags: tuple[str, ...] = ()
    extraction_method: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.text, "text")
        if self.text_sha256 is not None and self.text_sha256 != sha256_text(self.text):
            raise ValueError("text_sha256 does not match packet text")
        for flag in self.quality_flags:
            _require_non_empty(flag, "quality_flags")
        if self.extraction_method is not None:
            _require_non_empty(self.extraction_method, "extraction_method")

    @property
    def effective_text_sha256(self) -> str:
        return self.text_sha256 or sha256_text(self.text)


@dataclass(frozen=True, slots=True)
class PacketDocument:
    """One source document mounted into the model-visible packet."""

    source_document_id: str
    document_role: DocumentRole
    docket_entry_number: int | None
    source_provider: str
    source_url_or_reference: str
    source_sha256: str
    text: str
    text_sha256: str
    quality_flags: tuple[str, ...] = ()
    extraction_method: str | None = None
    packet_section: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "document_role": self.document_role.value,
            "docket_entry_number": self.docket_entry_number,
            "source_provider": self.source_provider,
            "source_url_or_reference": self.source_url_or_reference,
            "source_sha256": self.source_sha256,
            "text": self.text,
            "text_sha256": self.text_sha256,
            "quality_flags": list(self.quality_flags),
            "extraction_method": self.extraction_method,
            "packet_section": self.packet_section,
        }


@dataclass(frozen=True, slots=True)
class ModelPacket:
    """Complete model-visible packet for one case or motion."""

    candidate_id: str
    case_id: str
    court: str
    docket_number: str
    ablation: PacketAblation
    metadata: Mapping[str, str]
    documents: tuple[PacketDocument, ...]
    prediction_units: tuple[PredictionUnit, ...]
    excluded_document_ids: tuple[str, ...]
    decision_date: str | None = None
    missing_optional_sections: tuple[str, ...] = ()
    related_family_id: str | None = None
    mdl_family_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.court, "court")
        _require_non_empty(self.docket_number, "docket_number")
        if not self.documents and self.ablation is not PacketAblation.METADATA_ONLY:
            raise ValueError("model packet must include at least one document")
        if not self.prediction_units:
            raise ValueError("model packet must include prediction units")
        for key, value in self.metadata.items():
            _require_non_empty(key, "metadata key")
            _require_non_empty(value, f"metadata[{key}]")
        if self.decision_date is not None:
            _require_non_empty(self.decision_date, "decision_date")
            date.fromisoformat(self.decision_date)
        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")
        if self.mdl_family_id is not None:
            _require_non_empty(self.mdl_family_id, "mdl_family_id")

    @property
    def source_hashes(self) -> dict[str, str]:
        return {
            document.source_document_id: document.source_sha256
            for document in self.documents
        }

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "ablation": self.ablation.value,
            "metadata": dict(self.metadata),
            "decision_date": self.decision_date,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
            "documents": [document.to_record() for document in self.documents],
            "source_hashes": self.source_hashes,
            "prediction_units": [
                _model_visible_unit_record(unit) for unit in self.prediction_units
            ],
            "excluded_document_ids": list(self.excluded_document_ids),
            "missing_optional_sections": list(self.missing_optional_sections),
        }


def build_model_packet(
    *,
    case_packet: CasePacketSchema,
    prediction_units: Iterable[PredictionUnit],
    texts: Iterable[PacketText],
    metadata: Mapping[str, str] | None = None,
    ablation: PacketAblation = PacketAblation.FULL_PACKET,
    target_docket_entry_numbers: Iterable[int] | None = None,
    decision_date: str | None = None,
    related_family_id: str | None = None,
    mdl_family_id: str | None = None,
) -> ModelPacket:
    """Build a model-visible packet while excluding outcome materials."""

    units = tuple(prediction_units)
    texts_by_document_id = _index_texts(texts)
    packet_metadata = _ablation_metadata(dict(metadata or {}), ablation)
    target_entries = (
        frozenset(target_docket_entry_numbers)
        if target_docket_entry_numbers is not None
        else None
    )

    documents: list[PacketDocument] = []
    excluded_document_ids: list[str] = []
    for provenance in case_packet.documents:
        if _should_mount_document(
            provenance,
            ablation=ablation,
            target_docket_entry_numbers=target_entries,
        ):
            packet_text = texts_by_document_id.get(provenance.source_document_id)
            if packet_text is None:
                raise ValueError(
                    "missing extracted text for mounted source document: "
                    f"{provenance.source_document_id}"
                )
            documents.append(_packet_document(provenance, packet_text))
        else:
            excluded_document_ids.append(provenance.source_document_id)

    return ModelPacket(
        candidate_id=case_packet.candidate_id,
        case_id=case_packet.case_id,
        court=case_packet.court,
        docket_number=case_packet.docket_number,
        ablation=ablation,
        metadata=packet_metadata,
        documents=tuple(documents),
        prediction_units=units,
        excluded_document_ids=tuple(excluded_document_ids),
        decision_date=decision_date,
        missing_optional_sections=_missing_optional_sections(case_packet),
        related_family_id=related_family_id,
        mdl_family_id=mdl_family_id,
    )


def texts_from_mapping(
    values: Mapping[str, str],
    *,
    artifacts: Iterable[ExtractedTextArtifact] = (),
) -> tuple[PacketText, ...]:
    """Build packet text records from document text plus optional artifacts."""

    artifacts_by_id = {artifact.source_document_id: artifact for artifact in artifacts}
    return tuple(
        PacketText(
            source_document_id=document_id,
            text=text,
            text_sha256=(
                artifacts_by_id[document_id].text_sha256
                if document_id in artifacts_by_id
                else None
            ),
            quality_flags=(
                artifacts_by_id[document_id].quality_flags
                if document_id in artifacts_by_id
                else ()
            ),
            extraction_method=(
                artifacts_by_id[document_id].extraction_method
                if document_id in artifacts_by_id
                else None
            ),
        )
        for document_id, text in values.items()
    )


def _should_mount_document(
    provenance: SourceDocumentProvenance,
    *,
    ablation: PacketAblation,
    target_docket_entry_numbers: frozenset[int] | None,
) -> bool:
    if provenance.document_role in _OUTCOME_ROLES:
        return False
    if not provenance.is_mounted_for_model:
        return False
    if not provenance.is_predecision_material or provenance.contains_target_outcome:
        raise ValueError(
            "model packet source documents must be pre-decision and outcome-free"
        )
    if target_docket_entry_numbers is not None and not _is_relevant_to_target_motion(
        provenance,
        target_docket_entry_numbers,
    ):
        return False
    if ablation is PacketAblation.METADATA_ONLY:
        return False
    if ablation is PacketAblation.BRIEFS_ONLY_REDACTED:
        return provenance.document_role in _BRIEF_ROLES
    if provenance.document_role in _ALWAYS_VISIBLE_ROLES:
        return True
    if (
        ablation
        in {
            PacketAblation.FULL_PACKET,
            PacketAblation.JUDGE_REMOVED,
        }
        and provenance.document_role in _BRIEF_ROLES
    ):
        return True
    if (
        ablation
        in {
            PacketAblation.FULL_PACKET,
            PacketAblation.JUDGE_REMOVED,
        }
        and provenance.packet_section == _EXHIBIT_PACKET_SECTION
    ):
        return True
    return False


def _ablation_metadata(
    metadata: dict[str, str],
    ablation: PacketAblation,
) -> dict[str, str]:
    if ablation not in {
        PacketAblation.BRIEFS_ONLY_REDACTED,
        PacketAblation.JUDGE_REMOVED,
    }:
        return metadata
    return {
        key: ("[redacted]" if "judge" in key.lower() else value)
        for key, value in metadata.items()
    }


def _is_relevant_to_target_motion(
    provenance: SourceDocumentProvenance,
    target_docket_entry_numbers: frozenset[int],
) -> bool:
    if provenance.document_role in {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.DOCKET_HISTORY,
    }:
        return True
    return (
        provenance.docket_entry_number is not None
        and provenance.docket_entry_number in target_docket_entry_numbers
    )


def _packet_document(
    provenance: SourceDocumentProvenance,
    packet_text: PacketText,
) -> PacketDocument:
    return PacketDocument(
        source_document_id=provenance.source_document_id,
        document_role=provenance.document_role,
        docket_entry_number=provenance.docket_entry_number,
        source_provider=provenance.source_provider,
        source_url_or_reference=provenance.source_url_or_reference,
        source_sha256=provenance.sha256,
        text=packet_text.text,
        text_sha256=packet_text.effective_text_sha256,
        quality_flags=packet_text.quality_flags,
        extraction_method=packet_text.extraction_method,
        packet_section=provenance.packet_section,
    )


def _missing_optional_sections(case_packet: CasePacketSchema) -> tuple[str, ...]:
    mounted_roles = {
        document.document_role
        for document in case_packet.documents
        if document.is_mounted_for_model
    }
    missing: list[str] = []
    if DocumentRole.REPLY not in mounted_roles:
        missing.append(DocumentRole.REPLY.value)
    return tuple(missing)


def _index_texts(texts: Iterable[PacketText]) -> dict[str, PacketText]:
    indexed: dict[str, PacketText] = {}
    for packet_text in texts:
        if packet_text.source_document_id in indexed:
            raise ValueError(f"duplicate packet text: {packet_text.source_document_id}")
        indexed[packet_text.source_document_id] = packet_text
    return indexed


def _model_visible_unit_record(unit: PredictionUnit) -> dict[str, Any]:
    return {
        "unit_id": unit.unit_id,
        "count": unit.count,
        "claim_name": unit.claim_name,
        "defendant_group": unit.defendant_group,
        "should_score": unit.should_score,
    }


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
