from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.purchased_document_recovery import (
    PurchasedDocumentRecoveryRequest,
    PurchasedDocumentRecoveryStatus,
    recover_purchased_documents,
)


def test_recovery_downloads_purchased_document_and_marks_provenance(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/doc-1.pdf": b"purchased complaint pdf"}
    )
    retrieved_at = datetime(2026, 5, 17, tzinfo=UTC)

    records = recover_purchased_documents(
        (
            _request(
                _attempt("doc-1", download_url="https://case.dev/download/doc-1.pdf"),
                role=DocumentRole.COMPLAINT,
                docket_entry_number=1,
                pre_purchase_evidence={"availability": "pacer_only"},
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=retrieved_at,
    )

    record = records[0]
    assert record.status is PurchasedDocumentRecoveryStatus.RECOVERED
    assert record.local_path == "cand-1/case-dev-pacer/entry-1_doc-1.pdf"
    assert (tmp_path / record.local_path).read_bytes() == b"purchased complaint pdf"
    assert record.sha256 == hashlib.sha256(b"purchased complaint pdf").hexdigest()
    assert record.free_or_purchased == "purchased"
    assert record.purchase_cost_usd == "3.05"
    assert record.pre_purchase_evidence == {"availability": "pacer_only"}
    assert record.post_purchase_evidence["availability"] == "available"
    assert record.provenance is not None
    assert record.provenance.source_provider == "case.dev+pacer"
    assert record.provenance.source_document_id == "doc-1"
    assert record.provenance.is_mounted_for_model is True
    assert record.provenance.retrieved_at == retrieved_at


def test_recovery_handles_partial_purchases_without_fetching_failed_attempts(
    tmp_path,
) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/doc-1.pdf": b"purchased motion pdf"}
    )

    records = recover_purchased_documents(
        (
            _request(
                _attempt("doc-1", download_url="https://case.dev/download/doc-1.pdf"),
                role=DocumentRole.MTD_MEMORANDUM,
                docket_entry_number=34,
            ),
            _request(
                CaseDevPacerPurchaseAttempt(
                    candidate_id="cand-1",
                    source_document_id="doc-2",
                    status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                    reason="pacer fee cap exceeded",
                ),
                role=DocumentRole.OPPOSITION,
                docket_entry_number=35,
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert [record.status for record in records] == [
        PurchasedDocumentRecoveryStatus.RECOVERED,
        PurchasedDocumentRecoveryStatus.PURCHASE_NOT_EXECUTED,
    ]
    assert records[1].provenance is None
    assert records[1].post_purchase_evidence["purchase_status"] == "provider_error"
    assert source.requested_urls == ("https://case.dev/download/doc-1.pdf",)


def test_recovery_never_mounts_post_decision_outcome_material(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/order.pdf": b"outcome order pdf"}
    )

    records = recover_purchased_documents(
        (
            _request(
                _attempt(
                    "order-doc",
                    download_url="https://case.dev/download/order.pdf",
                ),
                role=DocumentRole.DECISION,
                docket_entry_number=44,
                is_predecision_material=False,
                contains_target_outcome=True,
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    record = records[0]
    assert record.status is PurchasedDocumentRecoveryStatus.RECOVERED_AUDIT_ONLY
    assert record.provenance is not None
    assert record.provenance.contains_target_outcome is True
    assert record.provenance.is_mounted_for_model is False
    assert record.provenance.packet_section is None


def _attempt(
    source_document_id: str,
    *,
    download_url: str,
) -> CaseDevPacerPurchaseAttempt:
    return CaseDevPacerPurchaseAttempt(
        candidate_id="cand-1",
        source_document_id=source_document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        fee_acknowledged=True,
        pacer_fees={
            "pacer_fee_usd": "0.00",
            "service_fee_usd": "3.05",
            "total_usd": "3.05",
        },
        download_url=download_url,
    )


def _request(
    attempt: CaseDevPacerPurchaseAttempt,
    *,
    role: DocumentRole,
    docket_entry_number: int,
    pre_purchase_evidence: dict[str, str] | None = None,
    is_predecision_material: bool = True,
    contains_target_outcome: bool = False,
) -> PurchasedDocumentRecoveryRequest:
    return PurchasedDocumentRecoveryRequest(
        purchase_attempt=attempt,
        source_case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        document_role=role,
        docket_entry_number=docket_entry_number,
        pre_purchase_evidence=(
            {} if pre_purchase_evidence is None else pre_purchase_evidence
        ),
        is_predecision_material=is_predecision_material,
        contains_target_outcome=contains_target_outcome,
    )
