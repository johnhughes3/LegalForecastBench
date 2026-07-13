from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseClient,
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerBusyError,
    CaseDevPurchasePolicyError,
    CaseDevPurchaseReconciliationRequired,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)


def test_policy_is_hashed_and_binds_the_canonical_ledger(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    artifact = _policy(ledger)

    policy = verify_case_dev_purchase_policy(artifact)

    assert policy.cycle_id == "cycle-1"
    assert policy.canonical_ledger_path == ledger
    assert policy.hard_cap_usd == Decimal("9.15")
    assert policy.per_document_reservation_usd == Decimal("3.05")

    artifact["policy"]["hard_cap_usd"] = "99.00"
    with pytest.raises(CaseDevPurchasePolicyError, match="hash"):
        verify_case_dev_purchase_policy(artifact)


def test_crash_before_post_leaves_planned_and_reopen_can_submit(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    plan = _plan(("doc-1",))

    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(plan)
        assert journal.statuses() == {"doc-1": "planned"}

    transport = _success_transport("doc-1")
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CaseDevPacerPurchaseClient(
            _client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        ).execute_purchase_plan(
            plan,
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert result.executed_purchase_count == 1
    assert len(transport.requests) == 1


def test_crash_after_post_leaves_submitted_and_resume_requires_reconciliation(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    plan = _plan(("doc-1",))
    client = _CrashAfterPostClient()

    with pytest.raises(KeyboardInterrupt):
        with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
            CaseDevPacerPurchaseClient(
                client,  # type: ignore[arg-type]
                capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
                journal=journal,
            ).execute_purchase_plan(
                plan,
                live=True,
                acknowledge_pacer_fees=True,
            )

    assert client.calls == 1
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        assert journal.statuses() == {"doc-1": "submitted"}
        with pytest.raises(CaseDevPurchaseReconciliationRequired):
            CaseDevPacerPurchaseClient(
                _client(CaseDevFixtureTransport([])),
                capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
                journal=journal,
            ).execute_purchase_plan(
                plan,
                live=True,
                acknowledge_pacer_fees=True,
            )


@pytest.mark.parametrize("status", [302, 503])
def test_ambiguous_response_is_unknown_and_paid_post_is_never_retried(
    tmp_path: Path,
    status: int,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=status,
                payload={"error": "ambiguous"},
            ),
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload=_success_payload("doc-1"),
            ),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CaseDevPacerPurchaseClient(
            _client(transport, max_retries=9),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        ).execute_purchase_plan(
            _plan(("doc-1",)),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"doc-1": "unknown"}
        assert journal.committed_amount_usd == "3.05"

    assert result.attempts[0].status.value == "unknown"
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "fees",
    [
        None,
        {"pacerFee": "bad", "serviceFee": "0.05", "total": "3.05"},
        {"pacerFee": "3.00", "serviceFee": "0.05"},
        {"pacerFee": "3.00", "serviceFee": "0.05", "total": "3.04"},
    ],
)
def test_missing_or_malformed_fees_are_unknown_with_full_reservation(
    tmp_path: Path,
    fees: object,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    payload = _success_payload("doc-1")
    payload["pacerFees"] = fees
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload=payload,
            )
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CaseDevPacerPurchaseClient(
            _client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        ).execute_purchase_plan(
            _plan(("doc-1",)),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"doc-1": "unknown"}
        assert journal.committed_amount_usd == "3.05"

    assert result.attempts[0].reason == "unparseable_provider_fees"


def test_fee_above_verified_worst_case_is_unknown_and_counts_actual(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    payload = _success_payload("doc-1")
    payload["pacerFees"] = {
        "pacerFee": "3.01",
        "serviceFee": "0.05",
        "total": "3.06",
    }
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/documents/doc-1/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload=payload,
            )
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CaseDevPacerPurchaseClient(
            _client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        ).execute_purchase_plan(
            _plan(("doc-1",)), live=True, acknowledge_pacer_fees=True
        )

        assert result.attempts[0].status.value == "unknown"
        assert journal.committed_amount_usd == "3.06"


def test_reservation_refuses_request_that_would_cross_cycle_cap(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger, cap="3.05"))
    transport = _success_transport("doc-1", "doc-2")

    with pytest.raises(Exception, match="cycle cap"):
        with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
            CaseDevPacerPurchaseClient(
                _client(transport),
                capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
                journal=journal,
            ).execute_purchase_plan(
                _two_case_plan(),
                live=True,
                acknowledge_pacer_fees=True,
            )

    assert len(transport.requests) == 1


def test_second_writer_and_conflicting_identity_are_rejected(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    first = CaseDevPurchaseJournal(ledger, policy=policy)
    try:
        with pytest.raises(CaseDevPurchaseLedgerBusyError):
            CaseDevPurchaseJournal(ledger, policy=policy)
    finally:
        first.close()

    conflicting = verify_case_dev_purchase_policy(_policy(ledger, cycle_id="cycle-2"))
    with pytest.raises(CaseDevPurchasePolicyError, match="identity"):
        CaseDevPurchaseJournal(ledger, policy=conflicting)


def test_provider_evidence_reconciles_unknown_and_writeoff_stays_counted(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(_two_case_plan())
        assert journal.submit("doc-1") is True
        journal.mark_unknown("doc-1", "lost response")
        journal.reconcile(
            {
                "source_document_id": "doc-1",
                "disposition": "write_off",
                "source_type": "support_confirmation",
                "source_reference": "support-ticket-123",
                "pacer_fees": None,
                "download_url": None,
            }
        )
        journal.require_reconciled()
        assert journal.committed_amount_usd == "3.05"
        assert journal.submit("doc-2") is True
        journal.mark_unknown("doc-2", "lost response")
        journal.reconcile(
            {
                "source_document_id": "doc-2",
                "disposition": "confirmed",
                "source_type": "billing_receipt",
                "source_reference": "receipt-456",
                "pacer_fees": {
                    "pacerFee": "2.00",
                    "serviceFee": "0.05",
                    "total": "2.05",
                },
                "download_url": "https://case.dev/download/doc-2.pdf",
            }
        )

        assert journal.statuses() == {"doc-1": "unknown", "doc-2": "confirmed"}
        assert journal.committed_amount_usd == "5.10"


def test_cli_generates_policy_and_records_provider_reconciliation(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    cohort_decisions = cli._fixture_cohort_policy_decisions()
    cohort_decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "9.15",
        "max_per_case_usd": "9.15",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(cohort_decisions)
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    decisions = tmp_path / "decisions.json"
    purchase_decisions = _policy_decisions(ledger)
    purchase_decisions["cohort_policy_sha256"] = cohort["policy_sha256"]
    decisions.write_text(json.dumps(purchase_decisions), encoding="utf-8")
    policy_path = tmp_path / "purchase-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-purchase-policy",
                "--decisions",
                str(decisions),
                "--cohort-policy",
                str(cohort_path),
                "--output",
                str(policy_path),
            ]
        )
        == 0
    )
    policy = verify_case_dev_purchase_policy(
        json.loads(policy_path.read_text(encoding="utf-8"))
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(_plan(("doc-1",)))
        assert journal.submit("doc-1") is True
        journal.mark_unknown("doc-1", "lost response")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "source_document_id": "doc-1",
                "disposition": "failed",
                "source_type": "statement_export",
                "source_reference": "statement-2026-07-13",
                "pacer_fees": None,
                "download_url": None,
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "acquisition",
                "reconcile-purchase",
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger),
                "--evidence",
                str(evidence),
            ]
        )
        == 0
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        assert journal.statuses() == {"doc-1": "failed"}
        assert journal.committed_amount_usd == "0.00"


def _policy(
    ledger: Path,
    *,
    cap: str = "9.15",
    max_per_case: str | None = None,
    cycle_id: str = "cycle-1",
) -> dict[str, object]:
    decisions = _policy_decisions(ledger)
    decisions["cycle_id"] = cycle_id
    decisions["hard_cap_usd"] = cap
    decisions["max_per_case_usd"] = max_per_case or cap
    return generate_case_dev_purchase_policy(decisions)


def _policy_decisions(ledger: Path) -> dict[str, object]:
    return {
        "cycle_id": "cycle-1",
        "cohort_policy_sha256": "a" * 64,
        "canonical_ledger_path": str(ledger),
        "hard_cap_usd": "9.15",
        "opening_committed_spend_usd": "0.00",
        "max_per_case_usd": "9.15",
        "per_document_reservation_usd": "3.05",
        "fee_schedule": {
            "source_citation": "case.dev pricing docs checked 2026-07-13",
            "verified_at_utc": "2026-07-13T00:00:00Z",
            "includes_pacer_fees": True,
            "includes_service_fees": True,
            "includes_rounding": True,
        },
    }


def _plan(document_ids: tuple[str, ...]) -> MissingCoreBudgetPlan:
    count = len(document_ids)
    return MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=document_ids,
                missing_core_document_count=count,
                estimated_cost=Decimal("3.05") * count,
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("999.00"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )


def _two_case_plan() -> MissingCoreBudgetPlan:
    return MissingCoreBudgetPlan(
        case_plans=tuple(
            CaseMissingCorePurchasePlan(
                candidate_id=f"case-{number}",
                purchase_document_ids=(f"doc-{number}",),
                missing_core_document_count=1,
                estimated_cost=Decimal("3.05"),
                audit_only_document_count=0,
                dry_run=False,
            )
            for number in (1, 2)
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("999.00"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )


def _success_transport(*document_ids: str) -> CaseDevFixtureTransport:
    return CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path=f"/legal/v1/documents/{document_id}/pacer",
                params={"live": True, "acknowledgePacerFees": True},
                status_code=200,
                payload=_success_payload(document_id),
            )
            for document_id in document_ids
        ]
    )


def _success_payload(document_id: str) -> dict[str, object]:
    return {
        "documentId": document_id,
        "acknowledgePacerFees": True,
        "pacerFees": {
            "pacerFee": "3.00",
            "serviceFee": "0.05",
            "total": "3.05",
        },
        "downloadUrl": f"https://case.dev/download/{document_id}.pdf",
    }


def _client(
    transport: CaseDevFixtureTransport,
    *,
    max_retries: int = 2,
) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=transport,
        max_retries=max_retries,
    )


class _CrashAfterPostClient:
    def __init__(self) -> None:
        self.calls = 0

    def purchase_pacer_document(
        self,
        document_id: str,
        *,
        acknowledge_pacer_fees: bool,
    ) -> dict[str, object]:
        del document_id, acknowledge_pacer_fees
        self.calls += 1
        raise KeyboardInterrupt
