"""Shared public record helpers.

Corpus discovery and acquisition live in LegalForecastCorpus. The benchmark
repository retains only the source-document records and canonical serializer
needed by public release consumers; importing this package must not eagerly
load the retired acquisition runtime.
"""

from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    CasePacketSchema,
    DocumentRole,
    ExtractedTextArtifact,
    PacketExclusionNote,
    RedactionOrSealStatus,
    SourceDocumentProvenance,
    case_packet_from_record,
    extracted_text_artifact_from_record,
    sha256_text,
    source_document_provenance_from_record,
)

__all__ = [
    "AvailabilityStatus",
    "CasePacketSchema",
    "DocumentRole",
    "ExtractedTextArtifact",
    "PacketExclusionNote",
    "RedactionOrSealStatus",
    "SourceDocumentProvenance",
    "canonical_json_bytes",
    "canonical_json_value_bytes",
    "case_packet_from_record",
    "extracted_text_artifact_from_record",
    "sha256_text",
    "source_document_provenance_from_record",
]
