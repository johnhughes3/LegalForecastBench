"""Frozen candidate manifest schema and deterministic hashing."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from legalforecast.ingestion.provenance import SourceDocumentProvenance
from legalforecast.selection.case_mix_diagnostics import CaseMixCandidate
from legalforecast.selection.eligibility import ContaminationMetadata, EligibilityStatus
from legalforecast.selection.exclusion_ledger import ExclusionLedgerEntry

MANIFEST_SCHEMA_VERSION = "legalforecast-mtd-manifest-v1"
_REQUIRED_CASE_MIX_FIELDS = (
    "district",
    "circuit",
    "nos_code",
    "nos_macro_category",
    "document_completeness",
    "prediction_unit_count",
)


class ManifestExclusionStatus(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class ManifestDocumentReference:
    """Hash and provenance fields for one manifest source document."""

    source_document_id: str
    source_provider: str
    document_role: str
    sha256: str
    source_url_or_reference: str
    is_mounted_for_model: bool

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.source_provider, "source_provider")
        _require_non_empty(self.document_role, "document_role")
        _require_sha256(self.sha256, "sha256")
        _require_non_empty(self.source_url_or_reference, "source_url_or_reference")

    @classmethod
    def from_provenance(
        cls,
        provenance: SourceDocumentProvenance,
    ) -> ManifestDocumentReference:
        return cls(
            source_document_id=provenance.source_document_id,
            source_provider=provenance.source_provider,
            document_role=provenance.document_role.value,
            sha256=provenance.sha256,
            source_url_or_reference=provenance.source_url_or_reference,
            is_mounted_for_model=provenance.is_mounted_for_model,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "source_provider": self.source_provider,
            "document_role": self.document_role,
            "sha256": self.sha256,
            "source_url_or_reference": self.source_url_or_reference,
            "is_mounted_for_model": self.is_mounted_for_model,
        }


@dataclass(frozen=True, slots=True)
class CandidateManifestRecord:
    """One JSONL manifest row for a candidate case or exclusion."""

    protocol_version: str
    candidate_id: str
    case_id: str
    court: str
    docket_number: str
    decision_date: date
    source_case_id: str
    documents: tuple[ManifestDocumentReference, ...]
    unit_hash: str
    label_hash: str
    eligibility_status: EligibilityStatus
    exclusion_status: ManifestExclusionStatus
    contamination_metadata: Mapping[str, Any]
    case_mix_fields: Mapping[str, Any]
    related_family_id: str | None = None
    mdl_family_id: str | None = None
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.protocol_version, "protocol_version")
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.court, "court")
        _require_non_empty(self.docket_number, "docket_number")
        _require_non_empty(self.source_case_id, "source_case_id")
        if not self.documents:
            raise ValueError("manifest records require at least one document")
        _require_unique_document_ids(self.documents)
        _require_sha256(self.unit_hash, "unit_hash")
        _require_sha256(self.label_hash, "label_hash")
        _require_case_mix_fields(self.case_mix_fields)
        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")
        if self.mdl_family_id is not None:
            _require_non_empty(self.mdl_family_id, "mdl_family_id")
        if self.exclusion_status is ManifestExclusionStatus.EXCLUDED:
            _require_non_empty(self.exclusion_reason or "", "exclusion_reason")
        elif self.exclusion_reason is not None:
            raise ValueError("included manifest records must not set exclusion_reason")

    @property
    def source_document_ids(self) -> tuple[str, ...]:
        return tuple(document.source_document_id for document in self.documents)

    @property
    def document_hashes(self) -> dict[str, str]:
        return {
            document.source_document_id: document.sha256 for document in self.documents
        }

    @property
    def manifest_record_hash(self) -> str:
        return hash_record(self.to_record(include_manifest_hash=False))

    def to_record(self, *, include_manifest_hash: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "protocol_version": self.protocol_version,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "decision_date": self.decision_date.isoformat(),
            "source_case_id": self.source_case_id,
            "source_document_ids": list(self.source_document_ids),
            "documents": [document.to_record() for document in self.documents],
            "document_hashes": self.document_hashes,
            "unit_hash": self.unit_hash,
            "label_hash": self.label_hash,
            "eligibility_status": self.eligibility_status.value,
            "exclusion_status": self.exclusion_status.value,
            "exclusion_reason": self.exclusion_reason,
            "contamination_metadata": dict(self.contamination_metadata),
            "case_mix_fields": dict(self.case_mix_fields),
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
        }
        if include_manifest_hash:
            record["manifest_record_hash"] = self.manifest_record_hash
        return record

    def to_jsonl_line(self) -> str:
        return f"{canonical_json(self.to_record())}\n"

    def to_preregistration_fields(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "protocol_version": self.protocol_version,
            "manifest_record_hash": self.manifest_record_hash,
            "unit_hash": self.unit_hash,
            "label_hash": self.label_hash,
            "eligibility_status": self.eligibility_status.value,
        }

    def to_packet_build_fields(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "source_case_id": self.source_case_id,
            "source_document_ids": list(self.source_document_ids),
            "model_packet_document_ids": [
                document.source_document_id
                for document in self.documents
                if document.is_mounted_for_model
            ],
            "document_hashes": self.document_hashes,
        }


def build_candidate_manifest_record(
    *,
    protocol_version: str,
    candidate_id: str,
    case_id: str,
    court: str,
    docket_number: str,
    decision_date: date,
    source_case_id: str,
    documents: Iterable[SourceDocumentProvenance],
    unit_records: Iterable[Mapping[str, Any]],
    label_records: Iterable[Mapping[str, Any]],
    contamination_metadata: ContaminationMetadata,
    case_mix_candidate: CaseMixCandidate,
    exclusion_entry: ExclusionLedgerEntry | None = None,
) -> CandidateManifestRecord:
    return CandidateManifestRecord(
        protocol_version=protocol_version,
        candidate_id=candidate_id,
        case_id=case_id,
        court=court,
        docket_number=docket_number,
        decision_date=decision_date,
        source_case_id=source_case_id,
        documents=tuple(
            ManifestDocumentReference.from_provenance(document)
            for document in documents
        ),
        unit_hash=hash_records(unit_records),
        label_hash=hash_records(label_records),
        eligibility_status=contamination_metadata.eligibility_status,
        exclusion_status=(
            ManifestExclusionStatus.EXCLUDED
            if exclusion_entry is not None
            else ManifestExclusionStatus.INCLUDED
        ),
        exclusion_reason=(
            exclusion_entry.primary_exclusion_reason
            if exclusion_entry is not None
            else None
        ),
        contamination_metadata=contamination_metadata.to_manifest_record(),
        case_mix_fields=case_mix_candidate.to_record(),
        related_family_id=case_mix_candidate.related_family_id,
        mdl_family_id=case_mix_candidate.mdl_family_id,
    )


def hash_records(records: Iterable[Mapping[str, Any]]) -> str:
    return hash_payload([dict(record) for record in records])


def hash_record(record: Mapping[str, Any]) -> str:
    return hash_payload(dict(record))


def hash_payload(payload: Any) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _require_case_mix_fields(case_mix_fields: Mapping[str, Any]) -> None:
    for field_name in _REQUIRED_CASE_MIX_FIELDS:
        if field_name not in case_mix_fields:
            raise ValueError(f"case_mix_fields missing required field: {field_name}")


def _require_unique_document_ids(
    documents: tuple[ManifestDocumentReference, ...],
) -> None:
    seen: set[str] = set()
    for document in documents:
        if document.source_document_id in seen:
            raise ValueError(
                f"duplicate document in manifest: {document.source_document_id}"
            )
        seen.add(document.source_document_id)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
