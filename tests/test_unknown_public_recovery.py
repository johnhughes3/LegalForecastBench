from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    PurchaseMaterialState,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.recap_fetch_quarantine_recovery import (
    RecapFetchQuarantineRecoveryError,
    recover_recap_fetch_quarantine_documents,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures


@pytest.fixture(autouse=True)
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


def test_recovery_discovers_public_unknown_material_and_quarantines_without_post(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    allowed = {
        "123": {
            "case_id": "case-1",
            "selection_document_sha256": "9" * 64,
        }
    }
    detail = _public_detail()
    transport = FixtureRecapFetchTransport(
        [
            RecordedRecapFetchResponse(
                method="GET",
                path="/recap-documents/123/",
                form={},
                status_code=200,
                payload=detail,
            )
        ]
    )
    source = FixtureFreeDocumentSource(
        {"https://storage.courtlistener.com/123.pdf": b"%PDF-1.4\npublic\n%%EOF"}
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("123", "124")))
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.mark_unknown("123", "ambiguous HTTP 400 after dispatch")

        records, restrictions = recover_recap_fetch_quarantine_documents(
            journal=journal,
            allowed_documents=allowed,
            attempt_policy_sha256="a" * 64,
            output_root=tmp_path / "quarantine",
            source=source,
            config=CourtListenerRecapFetchConfig(api_token="fixture"),
            transport=transport,
        )

        operation = journal.operation_evidence("123")
        assert operation is not None
        assert operation["status"] == "unknown"
        assert operation["material_state"] is (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )
        assert operation["actual_usd"] is None
        assert journal.committed_amount_usd == "3.05"
        journal.require_reconciled()

        continuation_transport = FixtureRecapFetchTransport(
            [
                RecordedRecapFetchResponse(
                    "GET", "/recap-documents/124/", {}, 200, {"id": 124}
                ),
                RecordedRecapFetchResponse(
                    "GET", "/recap-fetch/77/", {}, 200, {"status": 2}
                ),
                RecordedRecapFetchResponse(
                    "GET",
                    "/recap-documents/124/",
                    {},
                    200,
                    {
                        "id": 124,
                        "is_available": True,
                        "filepath_local": "https://storage.courtlistener.com/124.pdf",
                    },
                ),
            ]
        )
        broker = FixtureRecapFetchPurchaseBroker(
            [{"id": "77", "reservation_id": "reservation-2"}]
        )
        result = CourtListenerRecapFetchClient(
            CourtListenerRecapFetchConfig(api_token="fixture"),
            journal=journal,
            transport=continuation_transport,
            purchase_broker=broker,
        ).execute_purchase_plan(
            _plan(("123", "124")),
            public_documents={
                "123": _unknown_metadata(),
                "124": {
                    "redaction_or_seal_status": "public",
                    "is_sealed": False,
                    "is_private": False,
                },
            },
            attempt_documents=allowed,
            attempt_policy_sha256="a" * 64,
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert [attempt.status.value for attempt in result.attempts] == [
            "quarantined",
            "purchased",
        ]
        assert len(broker.requests) == 1
        assert broker.requests[0]["recap_document"] == "124"

    assert transport.requests == [("GET", "/recap-documents/123/", {})]
    assert len(records) == len(restrictions) == 1
    assert restrictions[0]["is_sealed"] is None
    assert restrictions[0]["restriction_evidence"] == [
        "courtlistener_recap_fetch_fresh_detail_exact_match",
        "courtlistener_recap_fetch_is_available_true",
        "courtlistener_recap_fetch_is_sealed_unknown",
        "courtlistener_recap_fetch_no_positive_private_marker",
        "courtlistener_recap_fetch_public_download_url_allowlisted",
    ]
    assert records[0]["parser_eligible"] is False
    assert records[0]["packet_eligible"] is False
    assert (tmp_path / "quarantine/case-1/123.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize(
    "detail_override",
    (
        {"is_available": False},
        {"is_sealed": True},
        {"is_private": True},
        {"is_available": 1},
        {"is_sealed": 0},
        {"is_sealed": "false"},
        {"is_private": 0},
        {"is_private": "false"},
        {"omit_is_sealed": True},
    ),
)
def test_recovery_rejects_unknown_operation_when_detail_is_not_public(
    tmp_path: Path, detail_override: dict[str, object]
) -> None:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    allowed = {
        "123": {
            "case_id": "case-1",
            "selection_document_sha256": "9" * 64,
        }
    }
    detail = _public_detail()
    if detail_override == {"omit_is_sealed": True}:
        del detail["is_sealed"]
    else:
        detail.update(detail_override)
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.mark_unknown("123", "ambiguous")

        with pytest.raises(
            RecapFetchQuarantineRecoveryError, match="not explicitly public"
        ):
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=FixtureFreeDocumentSource({}),
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=FixtureRecapFetchTransport(
                    [
                        RecordedRecapFetchResponse(
                            method="GET",
                            path="/recap-documents/123/",
                            form={},
                            status_code=200,
                            payload=detail,
                        )
                    ]
                ),
            )
        operation = journal.operation_evidence("123")
        assert operation is not None
        assert operation["material_state"] is PurchaseMaterialState.NOT_RECOVERED
        assert operation["reconciliation"] is None


def _public_detail() -> dict[str, object]:
    return {
        "id": 123,
        "is_available": True,
        "is_sealed": None,
        "is_private": False,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
    }


def _policy(ledger: Path) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "1" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "6.10",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "6.10",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-08-05T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _unknown_metadata() -> dict[str, object]:
    return {
        "redaction_or_seal_status": "unknown",
        "is_sealed": None,
        "is_private": None,
        "is_available": False,
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
        "restriction_evidence": [
            "courtlistener_rest_docket_exact_match",
            "courtlistener_rest_docket_entry_exact_match",
            "courtlistener_rest_recap_document_exact_match",
            "courtlistener_rest_recap_document_is_available_false",
            "courtlistener_rest_recap_document_seal_status_unknown",
            "courtlistener_rest_no_positive_restriction_marker",
        ],
    }


def _plan(document_ids: tuple[str, ...] = ("123",)) -> MissingCoreBudgetPlan:
    return MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=document_ids,
                missing_core_document_count=len(document_ids),
                estimated_cost=Decimal("3.05") * len(document_ids),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("6.10"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )
