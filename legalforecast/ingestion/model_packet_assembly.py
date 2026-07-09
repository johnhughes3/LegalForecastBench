"""Assemble final model packets from docket and parsed-document artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketText,
    build_model_packet,
)
from legalforecast.ingestion.docket_markdown import ControlledDocketMarkdownArtifacts
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRecord,
    MistralMarkdownConversionStatus,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    PacketExclusionNote,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.unitization.schemas import PredictionUnit

_COMPLAINT_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
    }
)
_TARGET_MTD_ROLES = frozenset(
    {
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
    }
)
_ALWAYS_TARGET_RELEVANT_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.DOCKET_HISTORY,
    }
)
_AUDIT_ONLY_PACKET_SECTIONS = frozenset({"post_decision", "labels", "audit_only"})
_CONTROLLED_DOCKET_PROVIDER = "legalforecast"
_CONTROLLED_DOCKET_SECTION = "docket"
_CONTROLLED_DOCKET_EXTRACTION_METHOD = "controlled_docket_markdown"


class PacketAssemblyError(ValueError):
    """Raised when artifacts cannot form an outcome-safe model packet."""


@dataclass(frozen=True, slots=True)
class ParsedMarkdownDocument:
    """Markdown extracted from one acquired source document."""

    source_document_id: str
    markdown: str
    extracted_text: ExtractedTextArtifact | None = None
    quality_flags: tuple[str, ...] = ()
    extraction_method: str = "provided_markdown"

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.markdown, "markdown")
        if self.extracted_text is not None:
            if self.extracted_text.source_document_id != self.source_document_id:
                raise ValueError("extracted_text source_document_id must match")
            return
        _require_non_empty(self.extraction_method, "extraction_method")
        for flag in self.quality_flags:
            _require_non_empty(flag, "quality_flags")

    @property
    def effective_extraction_method(self) -> str:
        if self.extracted_text is not None:
            return self.extracted_text.extraction_method
        return self.extraction_method

    @property
    def effective_quality_flags(self) -> tuple[str, ...]:
        if self.extracted_text is not None:
            return self.extracted_text.quality_flags
        return self.quality_flags

    @property
    def effective_text_sha256(self) -> str:
        if self.extracted_text is not None:
            return self.extracted_text.text_sha256
        return sha256_text(self.markdown)

    def to_packet_text(self) -> PacketText:
        return PacketText(
            source_document_id=self.source_document_id,
            text=self.markdown,
            text_sha256=self.effective_text_sha256,
            quality_flags=self.effective_quality_flags,
            extraction_method=self.effective_extraction_method,
        )

    def extracted_artifact(
        self,
        *,
        extracted_at: datetime,
    ) -> ExtractedTextArtifact:
        if self.extracted_text is not None:
            return self.extracted_text
        return ExtractedTextArtifact(
            source_document_id=self.source_document_id,
            extracted_at=extracted_at,
            extraction_method=self.extraction_method,
            text_sha256=sha256_text(self.markdown),
            quality_flags=self.quality_flags,
        )


@dataclass(frozen=True, slots=True)
class ModelPacketAssembly:
    """Final case packet, model packet, and complete audit material."""

    case_packet: CasePacketSchema
    model_packet: ModelPacket
    audit_bundle: Mapping[str, Any]

    @property
    def excluded_document_ids(self) -> tuple[str, ...]:
        return self.model_packet.excluded_document_ids

    def to_record(self) -> dict[str, Any]:
        return {
            "case_packet": self.case_packet.to_record(),
            "model_packet": self.model_packet.to_record(),
            "audit_bundle": dict(self.audit_bundle),
        }


def parsed_markdown_documents_from_conversion_records(
    records: Iterable[MistralMarkdownConversionRecord],
    *,
    markdown_root: str | Path | None = None,
) -> tuple[ParsedMarkdownDocument, ...]:
    """Load succeeded parser records into packet-ready Markdown texts."""

    root = None if markdown_root is None else Path(markdown_root).expanduser().resolve()
    documents: list[ParsedMarkdownDocument] = []
    for record in records:
        if record.status is not MistralMarkdownConversionStatus.SUCCEEDED:
            continue
        if record.extracted_text is None:
            raise PacketAssemblyError(
                "succeeded parser record missing extracted_text: "
                f"{record.source_document_id}"
            )
        markdown_path = _resolve_markdown_path(record.markdown_path, root)
        documents.append(
            ParsedMarkdownDocument(
                source_document_id=record.source_document_id,
                markdown=markdown_path.read_text(encoding="utf-8"),
                extracted_text=record.extracted_text,
            )
        )
    return tuple(documents)


def assemble_model_packet(
    *,
    candidate_id: str,
    case_id: str,
    court: str,
    docket_number: str,
    generated_at: datetime,
    docket_markdown: ControlledDocketMarkdownArtifacts,
    documents: Iterable[SourceDocumentProvenance],
    parsed_documents: Iterable[ParsedMarkdownDocument],
    prediction_units: Iterable[PredictionUnit],
    source_case_id: str | None = None,
    metadata: Mapping[str, str] | None = None,
    ablation: PacketAblation = PacketAblation.FULL_PACKET,
    target_docket_entry_numbers: Iterable[int] | None = None,
    decision_date: str | None = None,
    related_family_id: str | None = None,
    mdl_family_id: str | None = None,
) -> ModelPacketAssembly:
    """Build the final outcome-safe packet and its audit bundle."""

    _require_aware(generated_at, "generated_at")
    parsed_by_id = _index_parsed_documents(parsed_documents)
    normalized_documents = tuple(
        _normalize_unavailable_document(document) for document in documents
    )
    target_entries = (
        frozenset(target_docket_entry_numbers)
        if target_docket_entry_numbers is not None
        else None
    )
    _validate_required_documents(
        normalized_documents,
        parsed_by_id=parsed_by_id,
        target_entries=target_entries,
    )

    docket_document = _controlled_docket_document(
        candidate_id=candidate_id,
        case_id=case_id,
        court=court,
        docket_number=docket_number,
        source_case_id=source_case_id or case_id,
        generated_at=generated_at,
        docket_markdown=docket_markdown,
    )
    docket_text = _controlled_docket_text(
        candidate_id=candidate_id,
        docket_markdown=docket_markdown,
    )
    docket_artifact = _controlled_docket_text_artifact(
        candidate_id=candidate_id,
        generated_at=generated_at,
        docket_markdown=docket_markdown,
    )
    exclusion_notes = _exclusion_notes(
        normalized_documents,
        parsed_by_id=parsed_by_id,
        target_entries=target_entries,
    )
    case_packet = CasePacketSchema(
        candidate_id=candidate_id,
        case_id=case_id,
        court=court,
        docket_number=docket_number,
        generated_at=generated_at,
        documents=(docket_document, *normalized_documents),
        extracted_texts=(
            docket_artifact,
            *tuple(
                parsed.extracted_artifact(extracted_at=generated_at)
                for parsed in parsed_by_id.values()
            ),
        ),
        exclusion_notes=exclusion_notes,
    )
    try:
        model_packet = build_model_packet(
            case_packet=case_packet,
            prediction_units=prediction_units,
            texts=(
                docket_text,
                *(parsed.to_packet_text() for parsed in parsed_by_id.values()),
            ),
            metadata=metadata,
            ablation=ablation,
            target_docket_entry_numbers=target_entries,
            decision_date=decision_date,
            related_family_id=related_family_id,
            mdl_family_id=mdl_family_id,
        )
    except ValueError as exc:
        raise PacketAssemblyError(str(exc)) from exc
    return ModelPacketAssembly(
        case_packet=case_packet,
        model_packet=model_packet,
        audit_bundle=_audit_bundle(
            case_packet=case_packet,
            model_packet=model_packet,
            docket_markdown=docket_markdown,
            parsed_documents=tuple(parsed_by_id.values()),
        ),
    )


def _resolve_markdown_path(path_text: str, root: Path | None) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    if root is None:
        raise PacketAssemblyError(
            "markdown_root is required for relative markdown paths"
        )
    return root / path


def _index_parsed_documents(
    parsed_documents: Iterable[ParsedMarkdownDocument],
) -> dict[str, ParsedMarkdownDocument]:
    parsed_by_id: dict[str, ParsedMarkdownDocument] = {}
    for parsed in parsed_documents:
        if parsed.source_document_id in parsed_by_id:
            raise PacketAssemblyError(
                f"duplicate parsed document: {parsed.source_document_id}"
            )
        parsed_by_id[parsed.source_document_id] = parsed
    return parsed_by_id


def _normalize_unavailable_document(
    document: SourceDocumentProvenance,
) -> SourceDocumentProvenance:
    if (
        document.availability_status is AvailabilityStatus.AVAILABLE
        or not document.is_mounted_for_model
    ):
        return document
    return replace(
        document,
        is_mounted_for_model=False,
        packet_section=None,
        notes=_append_note(document.notes, "Excluded because source is unavailable."),
    )


def _controlled_docket_document(
    *,
    candidate_id: str,
    case_id: str,
    court: str,
    docket_number: str,
    source_case_id: str,
    generated_at: datetime,
    docket_markdown: ControlledDocketMarkdownArtifacts,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider=_CONTROLLED_DOCKET_PROVIDER,
        source_case_id=source_case_id,
        source_document_id=_controlled_docket_document_id(candidate_id),
        court=court,
        docket_number=docket_number,
        document_role=DocumentRole.DOCKET_HISTORY,
        retrieved_at=generated_at,
        source_url_or_reference=f"legalforecast://controlled-docket/{case_id}",
        sha256=sha256_text(docket_markdown.model_visible_markdown),
        is_predecision_material=True,
        is_mounted_for_model=True,
        packet_section=_CONTROLLED_DOCKET_SECTION,
        notes=(
            "Outcome-safe controlled docket markdown generated during packet assembly."
        ),
    )


def _controlled_docket_text(
    *,
    candidate_id: str,
    docket_markdown: ControlledDocketMarkdownArtifacts,
) -> PacketText:
    return PacketText(
        source_document_id=_controlled_docket_document_id(candidate_id),
        text=docket_markdown.model_visible_markdown,
        text_sha256=sha256_text(docket_markdown.model_visible_markdown),
        extraction_method=_CONTROLLED_DOCKET_EXTRACTION_METHOD,
    )


def _controlled_docket_text_artifact(
    *,
    candidate_id: str,
    generated_at: datetime,
    docket_markdown: ControlledDocketMarkdownArtifacts,
) -> ExtractedTextArtifact:
    return ExtractedTextArtifact(
        source_document_id=_controlled_docket_document_id(candidate_id),
        extracted_at=generated_at,
        extraction_method=_CONTROLLED_DOCKET_EXTRACTION_METHOD,
        text_sha256=sha256_text(docket_markdown.model_visible_markdown),
    )


def _controlled_docket_document_id(candidate_id: str) -> str:
    return f"{candidate_id}:controlled-docket"


def _validate_required_documents(
    documents: tuple[SourceDocumentProvenance, ...],
    *,
    parsed_by_id: Mapping[str, ParsedMarkdownDocument],
    target_entries: frozenset[int] | None,
) -> None:
    ready_documents = tuple(
        document
        for document in documents
        if _model_ready_document(
            document,
            parsed_by_id=parsed_by_id,
            target_entries=target_entries,
        )
    )
    if not any(
        document.document_role in _COMPLAINT_ROLES for document in ready_documents
    ):
        raise PacketAssemblyError("model packet requires an operative complaint")
    if not any(
        document.document_role in _TARGET_MTD_ROLES for document in ready_documents
    ):
        raise PacketAssemblyError("model packet requires target MTD papers")


def _model_ready_document(
    document: SourceDocumentProvenance,
    *,
    parsed_by_id: Mapping[str, ParsedMarkdownDocument],
    target_entries: frozenset[int] | None,
) -> bool:
    return (
        document.is_mounted_for_model
        and document.availability_status is AvailabilityStatus.AVAILABLE
        and document.is_predecision_material
        and not document.contains_target_outcome
        and _is_target_relevant(document, target_entries)
        and document.source_document_id in parsed_by_id
    )


def _exclusion_notes(
    documents: tuple[SourceDocumentProvenance, ...],
    *,
    parsed_by_id: Mapping[str, ParsedMarkdownDocument],
    target_entries: frozenset[int] | None,
) -> tuple[PacketExclusionNote, ...]:
    notes: list[PacketExclusionNote] = []
    for document in documents:
        reason = _exclusion_reason(
            document,
            parsed_by_id=parsed_by_id,
            target_entries=target_entries,
        )
        if reason is not None:
            notes.append(
                PacketExclusionNote(
                    source_document_id=document.source_document_id,
                    reason=reason,
                    notes=_exclusion_note_text(document, reason),
                )
            )
    return tuple(notes)


def _exclusion_reason(
    document: SourceDocumentProvenance,
    *,
    parsed_by_id: Mapping[str, ParsedMarkdownDocument],
    target_entries: frozenset[int] | None,
) -> str | None:
    if document.availability_status is not AvailabilityStatus.AVAILABLE:
        return document.availability_status.value
    if (
        not document.is_predecision_material
        or document.contains_target_outcome
        or document.document_role in {DocumentRole.ORDER, DocumentRole.DECISION}
        or document.packet_section in _AUDIT_ONLY_PACKET_SECTIONS
    ):
        return "audit_only_outcome_or_post_decision"
    if not document.is_mounted_for_model:
        return "not_selected_for_model_packet"
    if not _is_target_relevant(document, target_entries):
        return "outside_target_motion"
    if document.source_document_id not in parsed_by_id:
        return "missing_extracted_text"
    return None


def _exclusion_note_text(
    document: SourceDocumentProvenance,
    reason: str,
) -> str:
    role = document.document_role.value
    return (
        f"{document.source_document_id} ({role}) excluded from model packet: {reason}"
    )


def _is_target_relevant(
    document: SourceDocumentProvenance,
    target_entries: frozenset[int] | None,
) -> bool:
    if (
        target_entries is None
        or document.document_role in _ALWAYS_TARGET_RELEVANT_ROLES
    ):
        return True
    return (
        document.docket_entry_number is not None
        and document.docket_entry_number in target_entries
    )


def _audit_bundle(
    *,
    case_packet: CasePacketSchema,
    model_packet: ModelPacket,
    docket_markdown: ControlledDocketMarkdownArtifacts,
    parsed_documents: tuple[ParsedMarkdownDocument, ...],
) -> dict[str, Any]:
    return {
        "case_packet": case_packet.to_record(),
        "model_packet": model_packet.to_record(),
        "controlled_docket": {
            "model_visible_markdown": docket_markdown.model_visible_markdown,
            "audit_markdown": docket_markdown.audit_markdown,
        },
        "parsed_documents": [
            {
                "source_document_id": parsed.source_document_id,
                "text_sha256": parsed.effective_text_sha256,
                "quality_flags": list(parsed.effective_quality_flags),
                "extraction_method": parsed.effective_extraction_method,
            }
            for parsed in parsed_documents
        ],
        "exclusion_notes": [note.to_record() for note in case_packet.exclusion_notes],
    }


def _append_note(existing: str | None, note: str) -> str:
    if existing is None:
        return note
    return f"{existing} {note}"


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
