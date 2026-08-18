"""Injected acquire adapter for one document-repair execution.

This module does not mint purchase authority, open a provider, or loop over a
plan. It maps one resolved operation onto the existing free downloader and the
existing one-document RECAP Fetch primitive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
)
from legalforecast.ingestion.document_repair_clearance import (
    PAID_DELIVERY_CLEARANCE_BASIS,
)
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    ResolvedRepairOperation,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentFetch,
    FreeDocumentSource,
)


class DocumentRepairAcquireError(ValueError):
    """Raised when a resolved repair operation cannot use existing primitives."""


class RepairRecapPurchaseClient(Protocol):
    """Existing one-document RECAP Fetch surface used by the paid callback."""

    journal: CaseDevPurchaseJournal

    def execute_one_document(
        self, candidate_id: str, document_id: str
    ) -> CaseDevPacerPurchaseAttempt:
        """Purchase one already-planned journal document through RECAP Fetch."""

        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class DocumentRepairAcquirer:
    """Free-then-paid callback bound to one verified purchase journal."""

    journal: CaseDevPurchaseJournal | None
    free_source: FreeDocumentSource
    recap_client: RepairRecapPurchaseClient | None = None
    fetch_purchased: Callable[[str], FreeDocumentFetch] | None = None

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        if operation.route == "courtlistener_free":
            return self._acquire_free(operation)
        if operation.route == "pacer_purchase":
            return self._acquire_paid(operation)
        raise DocumentRepairAcquireError(
            f"unsupported repair acquisition route: {operation.route}"
        )

    def _acquire_free(
        self, operation: ResolvedRepairOperation
    ) -> AcquiredRepairDocument:
        if operation.source_url is None or not operation.source_url.strip():
            raise DocumentRepairAcquireError(
                "free repair operation is missing a public download URL"
            )
        fetched = self.free_source.fetch(operation.source_url)
        return AcquiredRepairDocument(
            disposition="included",
            source_document_id=operation.recap_document_id,
            document_bytes=fetched.content,
            committed_cost_usd="0.00",
            retry_count=fetched.retry_count,
            document_selector=operation.document_selector,
        )

    def _acquire_paid(
        self, operation: ResolvedRepairOperation
    ) -> AcquiredRepairDocument:
        if self.journal is None or self.recap_client is None:
            raise DocumentRepairAcquireError(
                "paid repair operation requires the verified purchase journal"
            )
        if self.recap_client.journal is not self.journal:
            raise DocumentRepairAcquireError(
                "RECAP Fetch client is not bound to the repair purchase journal"
            )
        attempt = self.recap_client.execute_one_document(
            operation.candidate_id, operation.recap_document_id
        )
        if attempt.source_document_id != operation.recap_document_id:
            raise DocumentRepairAcquireError(
                "RECAP Fetch result differs from the resolved document identity"
            )
        if attempt.status is CaseDevPacerPurchaseStatus.PURCHASED:
            return self._included_purchased(operation, attempt)
        if attempt.status is CaseDevPacerPurchaseStatus.QUARANTINED:
            return _non_included(
                operation,
                disposition="excluded",
                reason=attempt.reason or "purchased_material_quarantined",
            )
        if attempt.status is CaseDevPacerPurchaseStatus.PROVIDER_ERROR:
            return _non_included(
                operation,
                disposition="provider_error",
                reason=attempt.reason or "provider_confirmed_failure",
            )
        if attempt.status in {
            CaseDevPacerPurchaseStatus.UNKNOWN,
            CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
        }:
            return _non_included(
                operation,
                disposition="unknown",
                reason=attempt.reason or "purchase_outcome_unknown",
            )
        raise DocumentRepairAcquireError(
            f"unsupported RECAP Fetch status: {attempt.status}"
        )

    def _included_purchased(
        self,
        operation: ResolvedRepairOperation,
        attempt: CaseDevPacerPurchaseAttempt,
    ) -> AcquiredRepairDocument:
        download_url = attempt.download_url
        if download_url is None or not download_url.strip():
            return _non_included(
                operation,
                disposition="excluded",
                reason="purchased_document_omitted_download_url",
            )
        paid_clearance = None
        paid_clearance_basis = None
        if operation.paid_clearance_pending:
            assert self.journal is not None
            paid_clearance = _paid_delivery_clearance_from_journal(
                self.journal, operation.recap_document_id
            )
            if paid_clearance is None:
                return _non_included(
                    operation,
                    disposition="excluded",
                    reason="paid_delivery_clearance_unproven",
                )
            paid_clearance_basis = PAID_DELIVERY_CLEARANCE_BASIS
        fetcher = self.fetch_purchased or self.free_source.fetch
        try:
            fetched = fetcher(download_url)
        except FreeDocumentDownloadError:
            return _non_included(
                operation,
                disposition="excluded",
                reason="purchased_bytes_unavailable",
            )
        fees = attempt.pacer_fees or {}
        cost = fees.get("total_usd") or "3.00"
        return AcquiredRepairDocument(
            disposition="included",
            source_document_id=operation.recap_document_id,
            document_bytes=fetched.content,
            committed_cost_usd=cost,
            retry_count=fetched.retry_count,
            document_selector=operation.document_selector,
            paid_clearance=paid_clearance,
            paid_clearance_basis=paid_clearance_basis,
        )


def _paid_delivery_clearance_from_journal(
    journal: CaseDevPurchaseJournal,
    document_id: str,
) -> tuple[str, bool, bool] | None:
    """Read provider restriction evidence persisted by paid delivery.

    The evidence is the post-purchase provider document that the RECAP Fetch
    client journals under ``post_delivery_restrictions``. Clearance requires
    that the delivered document assert neither restriction -- not that it
    explicitly denies both. CourtListener REST v4 never sends
    ``is_private: false``; it omits the field entirely, so demanding an explicit
    ``False`` excluded every purchased document after the money was already
    spent (legalforecastbench-n3y7).

    ``is_sealed`` must still be present. The provider serializes it on every
    RECAP document, so a mapping without it is not a delivery record and proves
    nothing -- which is also what keeps an empty mapping from clearing.

    Both fields are read as an identity whitelist, never as an ``is True``
    blacklist. Only an absent field, an explicit null, or an explicit ``False``
    states that no restriction applies; a malformed truthy value (``1``,
    ``"true"``) or any other type refuses, exactly as
    ``restricted_material.restricted_material_markers`` treats these same two
    fields. Refusing only the ``True`` singleton would let a type-confused
    restriction through the last gate before a real purchase.
    """

    evidence = journal.operation_evidence(document_id)
    if evidence is None:
        return None
    response = evidence.get("response")
    if not isinstance(response, Mapping):
        return None
    response = cast(Mapping[str, object], response)
    restrictions = response.get("post_delivery_restrictions")
    if not isinstance(restrictions, Mapping):
        return None
    restrictions = cast(Mapping[str, object], restrictions)
    if "is_sealed" not in restrictions:
        return None
    for field in ("is_private", "is_sealed"):
        value = restrictions.get(field)
        if value is not None and value is not False:
            return None
    return ("cleared", False, False)


def _non_included(
    operation: ResolvedRepairOperation,
    *,
    disposition: str,
    reason: str,
) -> AcquiredRepairDocument:
    return AcquiredRepairDocument(
        disposition=disposition,
        source_document_id=operation.recap_document_id,
        document_bytes=None,
        committed_cost_usd=("3.00" if disposition == "unknown" else "0.00"),
        retry_count=0,
        reason=reason,
        document_selector=operation.document_selector,
    )
