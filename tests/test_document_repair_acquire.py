"""Adapter tests mapping repair operations onto existing acquire primitives."""

from __future__ import annotations

from decimal import Decimal

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.document_repair_acquire import (
    DocumentRepairAcquireError,
    DocumentRepairAcquirer,
)
from legalforecast.ingestion.document_repair_executor import ResolvedRepairOperation
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadError,
    FreeDocumentFetch,
)


class _DummyJournal:
    pass


class _StubRecapClient:
    def __init__(self, journal: object, attempt: CaseDevPacerPurchaseAttempt) -> None:
        self.journal = journal
        self.attempt = attempt
        self.calls: list[tuple[str, str]] = []

    def execute_one_document(
        self, candidate_id: str, document_id: str
    ) -> CaseDevPacerPurchaseAttempt:
        self.calls.append((candidate_id, document_id))
        return self.attempt


def _free_operation() -> ResolvedRepairOperation:
    return ResolvedRepairOperation(
        candidate_id="72309777",
        docket_entry_number=15,
        document_selector="main_document",
        document_role="reply",
        route="courtlistener_free",
        recap_document_id="1001",
        docket_entry_id="2001",
        source_url="https://storage.courtlistener.com/recap/example/1001.pdf",
        projected_cost_usd=Decimal("0.00"),
        docket_snapshot_sha256="a" * 64,
        public_clearance=("cleared", False, False),
    )


def _paid_operation() -> ResolvedRepairOperation:
    return ResolvedRepairOperation(
        candidate_id="70754103",
        docket_entry_number=1,
        document_selector="main_document",
        document_role="complaint",
        route="pacer_purchase",
        recap_document_id="1002",
        docket_entry_id="2002",
        source_url=None,
        projected_cost_usd=Decimal("3.00"),
        docket_snapshot_sha256="b" * 64,
        public_clearance=("cleared", False, False),
    )


def test_free_operation_uses_existing_public_downloader() -> None:
    source = FixtureFreeDocumentSource(
        {_free_operation().source_url or "": b"%PDF-1.4 free"}
    )
    acquirer = DocumentRepairAcquirer(journal=None, free_source=source)

    result = acquirer(_free_operation())

    assert result.disposition == "included"
    assert result.document_bytes == b"%PDF-1.4 free"
    assert result.committed_cost_usd == "0.00"
    assert result.source_document_id == "1001"
    assert source.requested_urls == (
        "https://storage.courtlistener.com/recap/example/1001.pdf",
    )


def test_free_operation_without_url_fails_closed() -> None:
    operation = ResolvedRepairOperation(
        candidate_id="72309777",
        docket_entry_number=15,
        document_selector="main_document",
        document_role="reply",
        route="courtlistener_free",
        recap_document_id="1001",
        docket_entry_id="2001",
        source_url=None,
        projected_cost_usd=Decimal("0.00"),
        docket_snapshot_sha256="a" * 64,
        public_clearance=("cleared", False, False),
    )
    acquirer = DocumentRepairAcquirer(
        journal=None, free_source=FixtureFreeDocumentSource({})
    )

    with pytest.raises(DocumentRepairAcquireError, match="public download URL"):
        acquirer(operation)


def test_paid_operation_uses_existing_one_document_recap_fetch() -> None:
    journal = _DummyJournal()
    attempt = CaseDevPacerPurchaseAttempt(
        candidate_id="70754103",
        source_document_id="1002",
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        download_url="https://storage.courtlistener.com/recap/example/1002.pdf",
        pacer_fees={"total_usd": "3.00"},
    )
    client = _StubRecapClient(journal, attempt)
    acquirer = DocumentRepairAcquirer(
        journal=journal,  # type: ignore[arg-type]
        free_source=FixtureFreeDocumentSource({}),
        recap_client=client,
        fetch_purchased=lambda url: FreeDocumentFetch(content=b"%PDF-1.4 paid"),
    )

    result = acquirer(_paid_operation())

    assert client.calls == [("70754103", "1002")]
    assert result.disposition == "included"
    assert result.document_bytes == b"%PDF-1.4 paid"
    assert result.committed_cost_usd == "3.00"


def test_paid_operation_requires_the_runtime_journal() -> None:
    journal = _DummyJournal()
    other = _DummyJournal()
    attempt = CaseDevPacerPurchaseAttempt(
        candidate_id="70754103",
        source_document_id="1002",
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        download_url="https://storage.courtlistener.com/recap/example/1002.pdf",
    )
    acquirer = DocumentRepairAcquirer(
        journal=journal,  # type: ignore[arg-type]
        free_source=FixtureFreeDocumentSource({}),
        recap_client=_StubRecapClient(other, attempt),
    )

    with pytest.raises(DocumentRepairAcquireError, match="not bound"):
        acquirer(_paid_operation())


def test_paid_unknown_stops_without_bytes() -> None:
    journal = _DummyJournal()
    attempt = CaseDevPacerPurchaseAttempt(
        candidate_id="70754103",
        source_document_id="1002",
        status=CaseDevPacerPurchaseStatus.UNKNOWN,
        reason="purchase_outcome_unknown",
    )
    acquirer = DocumentRepairAcquirer(
        journal=journal,  # type: ignore[arg-type]
        free_source=FixtureFreeDocumentSource({}),
        recap_client=_StubRecapClient(journal, attempt),
    )

    result = acquirer(_paid_operation())

    assert result.disposition == "unknown"
    assert result.document_bytes is None
    assert result.reason == "purchase_outcome_unknown"


def test_paid_download_failure_excludes_confirmed_bytes() -> None:
    journal = _DummyJournal()
    attempt = CaseDevPacerPurchaseAttempt(
        candidate_id="70754103",
        source_document_id="1002",
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        download_url="https://storage.courtlistener.com/recap/example/1002.pdf",
        pacer_fees={"total_usd": "3.00"},
    )

    def fail(_url: str) -> FreeDocumentFetch:
        raise FreeDocumentDownloadError("unavailable")

    acquirer = DocumentRepairAcquirer(
        journal=journal,  # type: ignore[arg-type]
        free_source=FixtureFreeDocumentSource({}),
        recap_client=_StubRecapClient(journal, attempt),
        fetch_purchased=fail,
    )

    result = acquirer(_paid_operation())

    assert result.disposition == "excluded"
    assert result.document_bytes is None
    assert result.reason == "purchased_bytes_unavailable"
