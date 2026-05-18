"""Recover fee-acknowledged purchased documents into provenance records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentFetch,
    FreeDocumentSource,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    RedactionOrSealStatus,
    SourceDocumentProvenance,
)
from legalforecast.path_safety import safe_path_component

_PURCHASED_PROVIDER = "case.dev+pacer"
_PURCHASED_PROVIDER_PATH = "case-dev-pacer"


class PurchasedDocumentRecoveryStatus(StrEnum):
    """Machine-readable recovery result for one purchased document."""

    RECOVERED = "recovered"
    RECOVERED_AUDIT_ONLY = "recovered_audit_only"
    PURCHASE_NOT_EXECUTED = "purchase_not_executed"
    UNAVAILABLE_AFTER_PURCHASE = "unavailable_after_purchase"


@dataclass(frozen=True, slots=True)
class PurchasedDocumentRecoveryRequest:
    """Metadata needed to reconcile one purchased document into provenance."""

    purchase_attempt: CaseDevPacerPurchaseAttempt
    source_case_id: str
    court: str
    docket_number: str
    document_role: DocumentRole
    docket_entry_number: int | None
    pre_purchase_evidence: Mapping[str, str]
    is_predecision_material: bool = True
    contains_target_outcome: bool = False
    file_extension: str = "pdf"


@dataclass(frozen=True, slots=True)
class PurchasedDocumentRecoveryRecord:
    """Stored purchased document plus pre/post purchase audit evidence."""

    candidate_id: str
    source_document_id: str
    status: PurchasedDocumentRecoveryStatus
    free_or_purchased: str
    purchase_cost_usd: str | None
    pre_purchase_evidence: Mapping[str, str]
    post_purchase_evidence: Mapping[str, str]
    provenance: SourceDocumentProvenance | None
    local_path: str | None = None
    sha256: str | None = None
    byte_count: int | None = None
    retry_count: int = 0
    rate_limited: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "free_or_purchased": self.free_or_purchased,
            "purchase_cost_usd": self.purchase_cost_usd,
            "pre_purchase_evidence": dict(self.pre_purchase_evidence),
            "post_purchase_evidence": dict(self.post_purchase_evidence),
            "local_path": self.local_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "retry_count": self.retry_count,
            "rate_limited": self.rate_limited,
            "provenance": (
                None if self.provenance is None else self.provenance.to_record()
            ),
        }


def recover_purchased_documents(
    requests: tuple[PurchasedDocumentRecoveryRequest, ...],
    *,
    output_root: str | Path,
    source: FreeDocumentSource,
    retrieved_at: datetime,
) -> tuple[PurchasedDocumentRecoveryRecord, ...]:
    """Fetch successful purchase attempts and write provenance-safe records."""

    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return tuple(
        _recover_one(
            request,
            output_root=root,
            source=source,
            retrieved_at=retrieved_at,
        )
        for request in requests
    )


def _recover_one(
    request: PurchasedDocumentRecoveryRequest,
    *,
    output_root: Path,
    source: FreeDocumentSource,
    retrieved_at: datetime,
) -> PurchasedDocumentRecoveryRecord:
    attempt = request.purchase_attempt
    purchase_cost = _purchase_cost(attempt)
    if attempt.status is not CaseDevPacerPurchaseStatus.PURCHASED:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.PURCHASE_NOT_EXECUTED,
            post_purchase_evidence={
                "availability": "not_checked",
                "purchase_status": attempt.status.value,
                "reason": attempt.reason or "",
            },
        )
    if attempt.download_url is None:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.UNAVAILABLE_AFTER_PURCHASE,
            post_purchase_evidence={
                "availability": "missing",
                "purchase_status": attempt.status.value,
                "reason": "missing_post_purchase_download_url",
            },
        )
    try:
        fetch = source.fetch(attempt.download_url)
    except RuntimeError as exc:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.UNAVAILABLE_AFTER_PURCHASE,
            post_purchase_evidence={
                "availability": "missing",
                "purchase_status": attempt.status.value,
                "reason": str(exc),
            },
        )

    output_path = _document_output_path(output_root, request)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(fetch.content)
    digest = hashlib.sha256(fetch.content).hexdigest()
    is_mounted = request.is_predecision_material and not request.contains_target_outcome
    status = (
        PurchasedDocumentRecoveryStatus.RECOVERED
        if is_mounted
        else PurchasedDocumentRecoveryStatus.RECOVERED_AUDIT_ONLY
    )
    local_path = output_path.relative_to(output_root).as_posix()
    provenance = SourceDocumentProvenance(
        source_provider=_PURCHASED_PROVIDER,
        source_case_id=request.source_case_id,
        source_document_id=attempt.source_document_id,
        court=request.court,
        docket_number=request.docket_number,
        document_role=request.document_role,
        retrieved_at=retrieved_at,
        source_url_or_reference=attempt.download_url,
        sha256=digest,
        is_predecision_material=request.is_predecision_material,
        is_mounted_for_model=is_mounted,
        availability_status=AvailabilityStatus.AVAILABLE,
        redaction_or_seal_status=RedactionOrSealStatus.PUBLIC,
        docket_entry_number=request.docket_entry_number,
        contains_target_outcome=request.contains_target_outcome,
        packet_section="filings" if is_mounted else None,
        notes=(
            "Purchased through case.dev PACER recovery for "
            f"{purchase_cost or 'unknown'}"
        ),
    )
    return PurchasedDocumentRecoveryRecord(
        candidate_id=attempt.candidate_id,
        source_document_id=attempt.source_document_id,
        status=status,
        free_or_purchased="purchased",
        purchase_cost_usd=purchase_cost,
        pre_purchase_evidence=dict(request.pre_purchase_evidence),
        post_purchase_evidence=_post_purchase_evidence(
            attempt,
            digest=digest,
            fetch=fetch,
        ),
        provenance=provenance,
        local_path=local_path,
        sha256=digest,
        byte_count=len(fetch.content),
        retry_count=fetch.retry_count,
        rate_limited=fetch.rate_limited,
    )


def _not_recovered_record(
    request: PurchasedDocumentRecoveryRequest,
    *,
    status: PurchasedDocumentRecoveryStatus,
    post_purchase_evidence: Mapping[str, str],
) -> PurchasedDocumentRecoveryRecord:
    attempt = request.purchase_attempt
    return PurchasedDocumentRecoveryRecord(
        candidate_id=attempt.candidate_id,
        source_document_id=attempt.source_document_id,
        status=status,
        free_or_purchased="purchased",
        purchase_cost_usd=_purchase_cost(attempt),
        pre_purchase_evidence=dict(request.pre_purchase_evidence),
        post_purchase_evidence=dict(post_purchase_evidence),
        provenance=None,
    )


def _post_purchase_evidence(
    attempt: CaseDevPacerPurchaseAttempt,
    *,
    digest: str,
    fetch: FreeDocumentFetch,
) -> dict[str, str]:
    return {
        "availability": "available",
        "purchase_status": attempt.status.value,
        "download_url": attempt.download_url or "",
        "sha256": digest,
        "byte_count": str(len(fetch.content)),
        "retry_count": str(fetch.retry_count),
        "rate_limited": "true" if fetch.rate_limited else "false",
    }


def _document_output_path(
    output_root: Path,
    request: PurchasedDocumentRecoveryRequest,
) -> Path:
    attempt = request.purchase_attempt
    candidate_id = safe_path_component(attempt.candidate_id, field_name="candidate_id")
    document_id = safe_path_component(
        attempt.source_document_id,
        field_name="source_document_id",
    )
    extension = safe_path_component(
        request.file_extension.removeprefix("."),
        field_name="file_extension",
    )
    entry_prefix = (
        "entry-unknown"
        if request.docket_entry_number is None
        else f"entry-{request.docket_entry_number}"
    )
    filename = f"{entry_prefix}_{document_id}.{extension}"
    output_path = (
        output_root / candidate_id / _PURCHASED_PROVIDER_PATH / filename
    ).resolve()
    output_path.relative_to(output_root)
    return output_path


def _purchase_cost(attempt: CaseDevPacerPurchaseAttempt) -> str | None:
    if attempt.pacer_fees is None:
        return None
    return attempt.pacer_fees.get("total_usd")
