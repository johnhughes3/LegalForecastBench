"""Docket and filing retrieval normalization pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevCase,
    CaseDevClient,
    CaseDevClientError,
    CaseDevDocketHit,
    CaseDevDocument,
    CaseDevRateLimitError,
    CaseDevResponseError,
    CaseDevServerError,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)


@dataclass(frozen=True, slots=True)
class NormalizedDocketEntry:
    source_provider: str
    source_case_id: str
    docket_entry_id: str
    entry_number: str | None
    entry_text: str
    filed_at: str | None
    document_role: DocumentRole
    source_document_ids: tuple[str, ...]
    source_url: str | None

    @property
    def has_available_documents(self) -> bool:
        return bool(self.source_document_ids)

    def to_record(self) -> dict[str, Any]:
        return {
            "source_provider": self.source_provider,
            "source_case_id": self.source_case_id,
            "docket_entry_id": self.docket_entry_id,
            "entry_number": self.entry_number,
            "entry_text": self.entry_text,
            "filed_at": self.filed_at,
            "document_role": self.document_role.value,
            "source_document_ids": list(self.source_document_ids),
            "source_url": self.source_url,
            "has_available_documents": self.has_available_documents,
        }


@dataclass(frozen=True, slots=True)
class RetrievedFiling:
    docket_entry_id: str
    source_document_id: str
    document_role: DocumentRole
    provenance: SourceDocumentProvenance

    def to_record(self) -> dict[str, Any]:
        return {
            "docket_entry_id": self.docket_entry_id,
            "source_document_id": self.source_document_id,
            "document_role": self.document_role.value,
            "provenance": self.provenance.to_record(),
        }


@dataclass(frozen=True, slots=True)
class MissingFiling:
    docket_entry_id: str
    entry_number: str | None
    document_role: DocumentRole
    reason: str

    def to_record(self) -> dict[str, Any]:
        return {
            "docket_entry_id": self.docket_entry_id,
            "entry_number": self.entry_number,
            "document_role": self.document_role.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DocketRetrievalResult:
    candidate_id: str
    case_id: str
    court: str
    docket_number: str
    retrieved_at: datetime
    docket_entries: tuple[NormalizedDocketEntry, ...]
    filings: tuple[RetrievedFiling, ...]
    missing_filings: tuple[MissingFiling, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "retrieved_at": self.retrieved_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "docket_entries": [entry.to_record() for entry in self.docket_entries],
            "filings": [filing.to_record() for filing in self.filings],
            "missing_filings": [
                missing_filing.to_record() for missing_filing in self.missing_filings
            ],
        }


class DocketRetrievalPipeline:
    def __init__(self, client: CaseDevClient) -> None:
        self.client = client

    def retrieve_candidate(
        self,
        *,
        candidate_id: str,
        case_id: str,
        retrieved_at: datetime | None = None,
    ) -> DocketRetrievalResult:
        timestamp = datetime.now(UTC) if retrieved_at is None else retrieved_at
        case = self.client.get_case(case_id)
        docket_entries = tuple(
            normalize_docket_hit(hit)
            for hit in self.client.iter_case_docket_entries(case_id)
        )

        filings: list[RetrievedFiling] = []
        missing_filings: list[MissingFiling] = []
        for entry in docket_entries:
            if not entry.source_document_ids:
                missing_filings.append(
                    MissingFiling(
                        docket_entry_id=entry.docket_entry_id,
                        entry_number=entry.entry_number,
                        document_role=entry.document_role,
                        reason="no_source_document_id",
                    )
                )
                continue
            for source_document_id in entry.source_document_ids:
                try:
                    document = self.client.get_document(source_document_id)
                except (
                    CaseDevAuthError,
                    CaseDevRateLimitError,
                    CaseDevServerError,
                ):
                    raise
                except CaseDevResponseError:
                    missing_filings.append(
                        MissingFiling(
                            docket_entry_id=entry.docket_entry_id,
                            entry_number=entry.entry_number,
                            document_role=entry.document_role,
                            reason="document_response_incomplete",
                        )
                    )
                    continue
                except CaseDevClientError:
                    missing_filings.append(
                        MissingFiling(
                            docket_entry_id=entry.docket_entry_id,
                            entry_number=entry.entry_number,
                            document_role=entry.document_role,
                            reason="document_unavailable",
                        )
                    )
                    continue
                filings.append(
                    RetrievedFiling(
                        docket_entry_id=entry.docket_entry_id,
                        source_document_id=source_document_id,
                        document_role=entry.document_role,
                        provenance=_provenance_for_document(
                            case=case,
                            entry=entry,
                            document=document,
                            retrieved_at=timestamp,
                        ),
                    )
                )

        return DocketRetrievalResult(
            candidate_id=candidate_id,
            case_id=case.case_id,
            court=case.court or "unknown",
            docket_number=case.docket_number or "unknown",
            retrieved_at=timestamp,
            docket_entries=docket_entries,
            filings=tuple(filings),
            missing_filings=tuple(missing_filings),
        )


def normalize_docket_hit(hit: CaseDevDocketHit) -> NormalizedDocketEntry:
    return NormalizedDocketEntry(
        source_provider="case.dev",
        source_case_id=hit.case_id,
        docket_entry_id=hit.docket_entry_id,
        entry_number=hit.entry_number,
        entry_text=hit.entry_text,
        filed_at=hit.filed_at,
        document_role=classify_document_role(hit.entry_text),
        source_document_ids=hit.source_document_ids,
        source_url=hit.source_url,
    )


def classify_document_role(text: str) -> DocumentRole:
    normalized = text.lower()
    references_mtd = _references_motion_to_dismiss(normalized)
    if "reply" in normalized and references_mtd:
        return DocumentRole.REPLY
    if "opposition" in normalized and references_mtd:
        return DocumentRole.OPPOSITION
    if _looks_like_decision(normalized):
        return DocumentRole.DECISION
    if "memorandum" in normalized and references_mtd:
        return DocumentRole.MTD_MEMORANDUM
    if references_mtd:
        return DocumentRole.MTD_NOTICE
    if "amended complaint" in normalized:
        return DocumentRole.AMENDED_COMPLAINT
    if "complaint" in normalized:
        return DocumentRole.COMPLAINT
    return DocumentRole.OTHER


def _looks_like_decision(normalized_text: str) -> bool:
    return (
        "order" in normalized_text
        or "opinion" in normalized_text
        or "decision" in normalized_text
        or "report and recommendation" in normalized_text
        or "r&r" in normalized_text
    )


def _references_motion_to_dismiss(normalized_text: str) -> bool:
    return (
        "motion to dismiss" in normalized_text
        or "motions to dismiss" in normalized_text
        or "rule 12" in normalized_text
        or "mtd" in normalized_text
        or "judgment on the pleadings" in normalized_text
        or "judgment on pleadings" in normalized_text
    )


def _provenance_for_document(
    *,
    case: CaseDevCase,
    entry: NormalizedDocketEntry,
    document: CaseDevDocument,
    retrieved_at: datetime,
) -> SourceDocumentProvenance:
    text_or_raw = document.text or json.dumps(document.raw, sort_keys=True)
    is_outcome_material = entry.document_role is DocumentRole.DECISION
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id=case.case_id,
        source_document_id=document.document_id,
        court=case.court or "unknown",
        docket_number=case.docket_number or "unknown",
        docket_entry_number=_entry_number_as_int(entry.entry_number),
        document_role=entry.document_role,
        retrieved_at=retrieved_at,
        source_url_or_reference=(
            document.source_url or entry.source_url or document.document_id
        ),
        sha256=sha256_text(text_or_raw),
        is_predecision_material=not is_outcome_material,
        is_mounted_for_model=not is_outcome_material,
        availability_status=(
            AvailabilityStatus.AVAILABLE
            if document.text is not None
            else AvailabilityStatus.UNAVAILABLE
        ),
        contains_target_outcome=is_outcome_material,
    )


def _entry_number_as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
