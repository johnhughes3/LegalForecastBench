from __future__ import annotations

from decimal import Decimal

import pytest
from legalforecast.ingestion import (
    CaseDevClient,
    CaseDevFixtureTransport,
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
    PurchaseBudgetExceededError,
)
from legalforecast.ingestion.case_dev_client import RecordedCaseDevResponse
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseClient,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.missing_core_budget import (
    plan_missing_core_document_budget,
)


def test_purchase_client_blocks_without_live_flag_or_acknowledgment() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )
    plan = _budget_plan("case-1", ("doc-1",), dry_run=False)

    result = client.execute_purchase_plan(
        plan,
        live=False,
        acknowledge_pacer_fees=True,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED
    assert result.attempts[0].reason == "live_flag_required"

    result = client.execute_purchase_plan(
        plan,
        live=True,
        acknowledge_pacer_fees=False,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED
    assert result.attempts[0].reason == "acknowledge_pacer_fees_required"


def test_purchase_client_records_capability_blocked_for_docket_level_only() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCKET_LEVEL_LIVE_FETCH_ONLY,
    )

    result = client.execute_purchase_plan(
        _budget_plan("case-1", ("doc-1",), dry_run=False),
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert transport.requests == []
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.CAPABILITY_BLOCKED
    assert result.attempts[0].reason == "document_level_purchase_unavailable"


def test_purchase_client_posts_acknowledged_document_purchase_and_records_fees() -> (
    None
):
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload={
                    "documentId": "doc-1",
                    "acknowledgePacerFees": True,
                    "pacerFees": {
                        "serviceFee": 3.05,
                        "pacerFee": 0.0,
                        "total": 3.05,
                    },
                    "downloadUrl": "https://case.dev/download/doc-1.pdf",
                },
            )
        ]
    )
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )

    result = client.execute_purchase_plan(
        _budget_plan("case-1", ("doc-1",), dry_run=False),
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert transport.requests == [
        (
            "POST",
            "/legal/v1/documents/doc-1/pacer",
            {"live": True, "acknowledgePacerFees": True},
        )
    ]
    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.PURCHASED
    assert result.attempts[0].fee_acknowledged is True
    assert result.attempts[0].pacer_fees == {
        "pacer_fee_usd": "0.00",
        "service_fee_usd": "3.05",
        "total_usd": "3.05",
    }


def test_purchase_client_records_case_dev_errors_without_continuing_blindly() -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=402,
                payload={"error": "pacer fee cap exceeded"},
            )
        ]
    )
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )

    result = client.execute_purchase_plan(
        _budget_plan("case-1", ("doc-1",), dry_run=False),
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert result.attempts[0].status is CaseDevPacerPurchaseStatus.PROVIDER_ERROR
    assert result.attempts[0].reason == "pacer fee cap exceeded"


def test_purchase_redirect_records_unknown_and_retains_full_plan_reservation() -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=302,
                payload={"error": "redirected purchase"},
            )
        ]
    )
    case_dev_client = _case_dev_client(transport)
    client = CaseDevPacerPurchaseClient(
        case_dev_client,
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )

    result = client.execute_purchase_plan(
        _budget_plan("case-1", ("doc-1", "doc-2"), dry_run=False),
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert [attempt.status for attempt in result.attempts] == [
        CaseDevPacerPurchaseStatus.UNKNOWN,
        CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
    ]
    assert result.attempts[0].reason == "purchase_redirect_outcome_unknown"
    assert result.attempts[1].reason == "unknown_outcome_before_attempt"
    assert result.projected_cost_usd == "6.10"
    assert result.executed_purchase_count == 0
    assert case_dev_client.request_count == 1
    assert len(transport.requests) == 1


def test_purchase_client_rechecks_spend_cap_before_any_request() -> None:
    transport = CaseDevFixtureTransport([])
    client = CaseDevPacerPurchaseClient(
        _case_dev_client(transport),
        capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
    )
    bad_plan = MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=("doc-1", "doc-2"),
                missing_core_document_count=2,
                estimated_cost=Decimal("6.10"),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("6.09"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )

    with pytest.raises(
        PurchaseBudgetExceededError,
        match=r"projected total \$6\.10 exceeds budget \$6\.09",
    ):
        client.execute_purchase_plan(
            bad_plan,
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert transport.requests == []


def _budget_plan(
    candidate_id: str,
    document_ids: tuple[str, ...],
    *,
    dry_run: bool,
) -> MissingCoreBudgetPlan:
    filter_result = _filter_result(candidate_id, document_ids)
    return plan_missing_core_document_budget([filter_result], dry_run=dry_run)


def _filter_result(candidate_id: str, document_ids: tuple[str, ...]):
    from legalforecast.ingestion import CoreDocumentFilterResult

    return CoreDocumentFilterResult(
        candidate_id=candidate_id,
        purchase_document_ids=document_ids,
        core_mtd_documents=document_ids,
        core_exhibit_documents=(),
        model_visible_document_ids=document_ids,
        operative_complaint_document_id=document_ids[0] if document_ids else None,
        operative_complaint_documents=document_ids[:1],
        audit_only_document_ids=(),
        core_missing_documents=document_ids,
        exclusion_reasons=(),
    )


def _case_dev_client(transport: CaseDevFixtureTransport) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=transport,
    )
