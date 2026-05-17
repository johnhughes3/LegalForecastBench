"""Source-document provenance and case-packet schemas."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class DocumentRole(StrEnum):
    COMPLAINT = "complaint"
    AMENDED_COMPLAINT = "amended_complaint"
    MTD_NOTICE = "motion_to_dismiss_notice"
    MTD_MEMORANDUM = "motion_to_dismiss_memorandum"
    OPPOSITION = "opposition"
    REPLY = "reply"
    DOCKET_HISTORY = "docket_history"
    ORDER = "order"
    DECISION = "decision"
    EXCLUSION_NOTE = "exclusion_note"
    OTHER = "other"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    RESTRICTED = "restricted"


class RedactionOrSealStatus(StrEnum):
    PUBLIC = "public"
    REDACTED = "redacted"
    SEALED = "sealed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SourceDocumentProvenance:
    """Provider provenance for a source document or packet artifact."""

    source_provider: str
    source_case_id: str
    source_document_id: str
    court: str
    docket_number: str
    document_role: DocumentRole
    retrieved_at: datetime
    source_url_or_reference: str
    sha256: str
    is_predecision_material: bool
    is_mounted_for_model: bool
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    redaction_or_seal_status: RedactionOrSealStatus = RedactionOrSealStatus.PUBLIC
    docket_entry_number: int | None = None
    contains_target_outcome: bool = False
    packet_section: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.source_provider, "source_provider")
        _require_non_empty(self.source_case_id, "source_case_id")
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.court, "court")
        _require_non_empty(self.docket_number, "docket_number")
        _require_non_empty(self.source_url_or_reference, "source_url_or_reference")
        _require_sha256(self.sha256)
        _require_aware(self.retrieved_at, "retrieved_at")
        if self.docket_entry_number is not None and self.docket_entry_number <= 0:
            raise ValueError("docket_entry_number must be positive")
        if self.is_mounted_for_model and not self.is_predecision_material:
            raise ValueError("model packet documents must be pre-decision material")
        if self.is_mounted_for_model and self.contains_target_outcome:
            raise ValueError("model packet documents must not expose target outcomes")

    @property
    def packet_membership(self) -> str:
        return "model_packet" if self.is_mounted_for_model else "not_mounted"

    def to_record(self) -> dict[str, Any]:
        return {
            "source_provider": self.source_provider,
            "source_case_id": self.source_case_id,
            "source_document_id": self.source_document_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "retrieved_at": _iso_datetime(self.retrieved_at),
            "source_url_or_reference": self.source_url_or_reference,
            "sha256": self.sha256,
            "is_predecision_material": self.is_predecision_material,
            "is_mounted_for_model": self.is_mounted_for_model,
            "packet_membership": self.packet_membership,
            "availability_status": self.availability_status.value,
            "redaction_or_seal_status": self.redaction_or_seal_status.value,
            "contains_target_outcome": self.contains_target_outcome,
            "packet_section": self.packet_section,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ExtractedTextArtifact:
    """Hashable extracted text derived from a source document."""

    source_document_id: str
    extracted_at: datetime
    extraction_method: str
    text_sha256: str
    page_count: int | None = None
    quality_flags: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.extraction_method, "extraction_method")
        _require_sha256(self.text_sha256)
        _require_aware(self.extracted_at, "extracted_at")
        if self.page_count is not None and self.page_count <= 0:
            raise ValueError("page_count must be positive")
        for flag in self.quality_flags:
            _require_non_empty(flag, "quality_flags")

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "extracted_at": _iso_datetime(self.extracted_at),
            "extraction_method": self.extraction_method,
            "text_sha256": self.text_sha256,
            "page_count": self.page_count,
            "quality_flags": list(self.quality_flags),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class PacketExclusionNote:
    """Reason a source document is known but absent from the model packet."""

    source_document_id: str | None
    reason: str
    notes: str

    def __post_init__(self) -> None:
        if self.source_document_id is not None:
            _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.reason, "reason")
        _require_non_empty(self.notes, "notes")

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "reason": self.reason,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class CasePacketSchema:
    """Provenance-backed packet manifest for one candidate case."""

    candidate_id: str
    case_id: str
    court: str
    docket_number: str
    generated_at: datetime
    documents: tuple[SourceDocumentProvenance, ...]
    extracted_texts: tuple[ExtractedTextArtifact, ...] = ()
    exclusion_notes: tuple[PacketExclusionNote, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.court, "court")
        _require_non_empty(self.docket_number, "docket_number")
        _require_aware(self.generated_at, "generated_at")
        if not self.documents:
            raise ValueError("case packet must include at least one source document")
        for document in self.documents:
            if document.court != self.court:
                raise ValueError("document court must match packet court")
            if document.docket_number != self.docket_number:
                raise ValueError("document docket_number must match packet")
            if document.is_mounted_for_model and document.contains_target_outcome:
                raise ValueError("model packet cannot contain target outcome material")

    @property
    def model_documents(self) -> tuple[SourceDocumentProvenance, ...]:
        return tuple(
            document for document in self.documents if document.is_mounted_for_model
        )

    @property
    def non_model_documents(self) -> tuple[SourceDocumentProvenance, ...]:
        return tuple(
            document for document in self.documents if not document.is_mounted_for_model
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "generated_at": _iso_datetime(self.generated_at),
            "documents": [document.to_record() for document in self.documents],
            "model_document_ids": [
                document.source_document_id for document in self.model_documents
            ],
            "excluded_document_ids": [
                document.source_document_id for document in self.non_model_documents
            ],
            "extracted_texts": [
                extracted_text.to_record() for extracted_text in self.extracted_texts
            ],
            "exclusion_notes": [note.to_record() for note in self.exclusion_notes],
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_datetime(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("sha256 must be a lowercase 64-character hex digest")
