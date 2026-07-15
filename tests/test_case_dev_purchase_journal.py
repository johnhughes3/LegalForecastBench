from __future__ import annotations

import hashlib
import json
import sqlite3
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
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerBusyError,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicyError,
    CaseDevPurchaseReconciliationRequired,
    PurchaseMaterialState,
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


def test_policy_freezes_canonical_opening_case_commitments(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    decisions = _policy_decisions(ledger)
    decisions["opening_committed_spend_usd"] = "4.00"
    decisions["opening_case_committed_spend_usd"] = {
        "case-z": "1.00",
        "case-a": "3.00",
    }

    artifact = generate_case_dev_purchase_policy(decisions)
    policy = verify_case_dev_purchase_policy(artifact)

    assert list(artifact["policy"]["opening_case_committed_spend_usd"]) == [
        "case-a",
        "case-z",
    ]
    assert policy.opening_case_committed_spend_usd == {
        "case-a": Decimal("3.00"),
        "case-z": Decimal("1.00"),
    }


@pytest.mark.parametrize(
    ("opening_total", "mapping", "message"),
    [
        ("0.00", [], "must be an object"),
        ("1.00", {"": "1.00"}, "case ID"),
        ("1.00", {" case-1 ": "1.00"}, "case ID"),
        ("1.00", {"case-1": 1}, "canonical nonnegative USD"),
        ("1.00", {"case-1": "1.0"}, "canonical nonnegative USD"),
        ("1.00", {"case-1": "-1.00"}, "canonical nonnegative USD"),
        ("4.00", {"case-1": "4.00"}, "per-case cap"),
        (
            "3.00",
            {"case-1": "2.00", "case-2": "2.00"},
            "opening committed spend",
        ),
        (
            "3.00",
            {"case-1": "2.00"},
            "must exactly equal opening committed spend",
        ),
    ],
)
def test_policy_rejects_invalid_opening_case_commitments(
    tmp_path: Path,
    opening_total: str,
    mapping: object,
    message: str,
) -> None:
    decisions = _policy_decisions((tmp_path / "cycle-purchases.sqlite3").resolve())
    decisions["opening_committed_spend_usd"] = opening_total
    decisions["max_per_case_usd"] = "3.05"
    decisions["opening_case_committed_spend_usd"] = mapping

    with pytest.raises(CaseDevPurchasePolicyError, match=message):
        generate_case_dev_purchase_policy(decisions)


def test_opening_case_commitment_consumes_per_case_headroom(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    decisions = _policy_decisions(ledger)
    decisions["opening_committed_spend_usd"] = "3.05"
    decisions["opening_case_committed_spend_usd"] = {"case-1": "3.05"}
    decisions["max_per_case_usd"] = "6.10"
    policy = verify_case_dev_purchase_policy(
        generate_case_dev_purchase_policy(decisions)
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        with pytest.raises(
            CaseDevPurchaseLedgerError,
            match="cumulative reservation exceeds per-case cap",
        ):
            journal.plan(_plan(("doc-1", "doc-2")))


def test_crash_before_post_leaves_planned_and_reopen_can_submit(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    plan = _plan(("doc-1",))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(plan)
        assert journal.statuses() == {"doc-1": "planned"}

    transport = _success_transport("doc-1")
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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


def test_unknown_attempt_billing_and_material_states_are_orthogonal(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
        assert journal.submit("doc-1") is True
        journal.mark_unknown("doc-1", "broker timeout")

        evidence = journal.operation_evidence("doc-1")
        assert evidence is not None
        assert evidence["status"] == "unknown"
        assert evidence["material_state"] == PurchaseMaterialState.NOT_RECOVERED
        assert evidence["material_authority"] == "unknown_status_attempt"
        assert evidence["attempt_policy_sha256"] == "a" * 64
        assert journal.committed_amount_usd == "3.05"
        operation_key = str(evidence["operation_key"])
        journal.record_broker_receipt(
            "doc-1",
            {
                "operation_key": operation_key,
                "reservation_id": "reservation-1",
                "cycle_id": "cycle-1",
                "purchase_policy_sha256": policy.policy_sha256,
                "recap_document": "doc-1",
                "case_id": "case-1",
                "client_code": "test",
                "reservation_usd": "3.05",
                "id": "queue-1",
                "state": "confirmed",
                "authoritative_fee_usd": "3.05",
                "billing_evidence": {"evidence_sha256": "f" * 64},
            },
        )
        journal.recover_broker_queue(
            "doc-1", queue_id="queue-1", reservation_id="reservation-1"
        )
        journal.mark_material_available_for_quarantine(
            "doc-1",
            provider_detail_sha256="b" * 64,
            queue_response_sha256="c" * 64,
            download_url_sha256="d" * 64,
        )
        journal.record_quarantined_material_bytes(
            "doc-1", content_sha256="e" * 64, byte_count=123
        )
        journal.reconcile_unknown_broker_billing(
            "doc-1",
            actual_usd="3.05",
            evidence_sha256="f" * 64,
            source_reference=f"recap-fetch-broker:{operation_key}:{'f' * 64}",
        )

        recovered = journal.operation_evidence("doc-1")
        assert recovered is not None
        assert recovered["status"] == "confirmed"
        assert recovered["material_state"] == (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )
        assert recovered["material_evidence"] == {
            "provider_detail_sha256": "b" * 64,
            "queue_response_sha256": "c" * 64,
            "download_url_sha256": "d" * 64,
            "content_sha256": "e" * 64,
            "byte_count": 123,
        }
        replay = journal.replay_attempt("case-1", "doc-1")
        assert replay is not None
        assert replay.status is CaseDevPacerPurchaseStatus.QUARANTINED
        assert replay.download_url is None
        assert "storage.courtlistener.com" not in json.dumps(
            [dict(record) for record in journal.operation_records()]
        )
        assert journal.committed_amount_usd == "3.05"


def test_unknown_material_clearance_is_independent_of_unresolved_billing(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
        journal.submit("doc-1")
        journal.queue("doc-1", response={"queue_id": "77"})
        journal.mark_material_available_for_quarantine(
            "doc-1",
            provider_detail_sha256="b" * 64,
            queue_response_sha256="c" * 64,
            download_url_sha256="d" * 64,
        )
        journal.record_quarantined_material_bytes(
            "doc-1", content_sha256="e" * 64, byte_count=123
        )
        resolved = {
            "candidate_id": "case-1",
            "source_document_id": "doc-1",
            "recovery_origin": "unknown_status_attempt",
            "attempt_policy_sha256": "a" * 64,
            "selection_document_sha256": "9" * 64,
            "queue_response_sha256": "c" * 64,
            "fresh_recap_detail_sha256": "b" * 64,
            "download_url_sha256": "d" * 64,
            "content_sha256": "e" * 64,
            "byte_count": 123,
            "clearance_record_sha256": "f" * 64,
            "parser_eligible": True,
            "packet_eligible": True,
        }
        resolved["record_sha256"] = hashlib.sha256(
            json.dumps(resolved, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        journal.clear_unknown_material("doc-1", resolved_record=resolved)
        evidence = journal.operation_evidence("doc-1")
        assert evidence is not None
        assert evidence["status"] == "queued"
        assert evidence["material_state"] is PurchaseMaterialState.CLEARED_PUBLIC
        assert journal.committed_amount_usd == "3.05"


def test_unknown_attempt_authority_is_exact_and_immutable(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        with pytest.raises(CaseDevPurchaseLedgerError, match="candidate identity"):
            journal.authorize_unknown_material_attempts(
                {
                    "doc-1": {
                        "case_id": "case-other",
                        "selection_document_sha256": "9" * 64,
                    }
                },
                attempt_policy_sha256="a" * 64,
            )
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
        with pytest.raises(CaseDevPurchaseLedgerError, match="immutable"):
            journal.authorize_unknown_material_attempts(
                {
                    "doc-1": {
                        "case_id": "case-1",
                        "selection_document_sha256": "9" * 64,
                    }
                },
                attempt_policy_sha256="b" * 64,
            )


def test_unknown_attempt_cannot_use_ordinary_confirmation_paths(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
        journal.submit("doc-1")
        with pytest.raises(CaseDevPurchaseLedgerError, match="URL-free"):
            journal.confirm(
                "doc-1",
                response={"downloadUrl": "https://example.test/doc.pdf"},
                fees={"total_usd": "3.05"},
            )
        journal.queue("doc-1", response={"queue_id": "77"})
        with pytest.raises(CaseDevPurchaseLedgerError, match="quarantined"):
            journal.confirm_reserved("doc-1", response={"queue_id": "77"})
        with pytest.raises(CaseDevPurchaseLedgerError, match="URL-free"):
            journal.reconcile(
                {
                    "source_document_id": "doc-1",
                    "disposition": "confirmed",
                    "source_type": "billing_receipt",
                    "source_reference": "receipt-1",
                    "pacer_fees": {
                        "pacerFee": "3.00",
                        "serviceFee": "0.05",
                        "total": "3.05",
                    },
                    "download_url": "https://example.test/doc.pdf",
                }
            )


def test_reopen_rejects_nonexact_operation_schema(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True):
        pass
    connection = sqlite3.connect(ledger)
    connection.execute("ALTER TABLE purchase_operations ADD COLUMN surprise TEXT")
    connection.commit()
    connection.close()

    with pytest.raises(CaseDevPurchaseLedgerError, match="exact supported"):
        CaseDevPurchaseJournal(ledger, policy=policy)


def test_reopen_rejects_contradictory_material_state(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        journal.authorize_unknown_material_attempts(
            {
                "doc-1": {
                    "case_id": "case-1",
                    "selection_document_sha256": "9" * 64,
                }
            },
            attempt_policy_sha256="a" * 64,
        )
    connection = sqlite3.connect(ledger)
    connection.execute(
        "UPDATE purchase_material_state SET status='recovered_pending_clearance' "
        "WHERE source_document_id='doc-1'"
    )
    connection.commit()
    connection.close()

    with pytest.raises(CaseDevPurchaseLedgerError, match="contradictory"):
        CaseDevPurchaseJournal(ledger, policy=policy)


def test_nonempty_legacy_ledger_migrates_after_operations_and_preserves_cap(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "legacy.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    operation_key = "5e675533-550b-4a6f-85f8-75e977004e3c"
    connection = sqlite3.connect(ledger)
    connection.executescript(
        """
        CREATE TABLE purchase_ledger (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            cycle_id TEXT NOT NULL,
            cohort_policy_sha256 TEXT NOT NULL,
            purchase_policy_sha256 TEXT NOT NULL,
            canonical_ledger_path TEXT NOT NULL,
            hard_cap_usd TEXT NOT NULL,
            opening_committed_spend_usd TEXT NOT NULL,
            max_per_case_usd TEXT NOT NULL,
            per_document_reservation_usd TEXT NOT NULL
        );
        CREATE TABLE purchase_operations (
            source_document_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            reservation_usd TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN
                ('planned','submitted','confirmed','failed','unknown')),
            operation_key TEXT UNIQUE,
            actual_usd TEXT,
            response_json TEXT,
            error TEXT,
            reconciliation_json TEXT
        );
        CREATE TABLE replacement_events (
            sequence INTEGER PRIMARY KEY CHECK(sequence >= 0),
            event_key TEXT NOT NULL UNIQUE,
            record_json TEXT NOT NULL,
            record_sha256 TEXT NOT NULL UNIQUE
        );
        """
    )
    connection.execute(
        "INSERT INTO purchase_ledger VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            policy.cycle_id,
            policy.cohort_policy_sha256,
            policy.policy_sha256,
            str(policy.canonical_ledger_path),
            "9.15",
            "0.00",
            "9.15",
            "3.05",
        ),
    )
    connection.execute(
        """INSERT INTO purchase_operations VALUES
        ('doc-legacy','case-1','3.05','submitted',?,NULL,NULL,NULL,NULL)""",
        (operation_key,),
    )
    connection.commit()
    connection.close()

    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        evidence = journal.operation_evidence("doc-legacy")
        assert evidence is not None
        assert evidence["operation_key"] == operation_key
        assert evidence["status"] == "submitted"
        assert evidence["material_authority"] == "ordinary_public"
        assert journal.committed_amount_usd == "3.05"
        foreign_key = journal._connection.execute(
            "PRAGMA foreign_key_list(purchase_material_state)"
        ).fetchone()
        assert foreign_key is not None
        assert foreign_key["table"] == "purchase_operations"
        assert journal._connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_crash_after_post_leaves_submitted_and_resume_requires_reconciliation(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    plan = _plan(("doc-1",))
    client = _CrashAfterPostClient()

    with pytest.raises(KeyboardInterrupt):
        with CaseDevPurchaseJournal(
            ledger, policy=policy, allow_create=True
        ) as journal:
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
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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

    with pytest.raises(CaseDevPurchaseLedgerError, match="cycle cap"):
        with CaseDevPurchaseJournal(
            ledger, policy=policy, allow_create=True
        ) as journal:
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


def test_per_case_cap_is_cumulative_across_separate_purchase_runs(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(
        _policy(ledger, cap="9.15", max_per_case="6.10")
    )
    transport = _success_transport("doc-1", "doc-2")
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        first = CaseDevPacerPurchaseClient(
            _client(transport),
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            journal=journal,
        ).execute_purchase_plan(
            _plan(("doc-1", "doc-2")),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert first.executed_purchase_count == 2

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        with pytest.raises(
            CaseDevPurchaseLedgerError,
            match="cumulative reservation exceeds per-case cap",
        ):
            CaseDevPacerPurchaseClient(
                _client(CaseDevFixtureTransport([])),
                capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
                journal=journal,
            ).execute_purchase_plan(
                _plan(("doc-3",)),
                live=True,
                acknowledge_pacer_fees=True,
            )

    assert len(transport.requests) == 2


def test_second_writer_and_conflicting_identity_are_rejected(tmp_path: Path) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    first = CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True)
    try:
        with pytest.raises(CaseDevPurchaseLedgerBusyError):
            CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True)
    finally:
        first.close()

    conflicting = verify_case_dev_purchase_policy(_policy(ledger, cycle_id="cycle-2"))
    with pytest.raises(CaseDevPurchasePolicyError, match="identity"):
        CaseDevPurchaseJournal(ledger, policy=conflicting, allow_create=True)


def test_provider_evidence_reconciles_unknown_and_writeoff_stays_counted(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
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
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        assert journal.statuses() == {"doc-1": "failed"}
        assert journal.committed_amount_usd == "0.00"


@pytest.mark.parametrize("transition", ["fail", "mark_unknown"])
def test_paid_state_transitions_hard_fail_when_no_row_is_eligible(
    tmp_path: Path, transition: str
) -> None:
    ledger = (tmp_path / f"{transition}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan(("doc-1",)))
        method = getattr(journal, transition)
        with pytest.raises(CaseDevPurchaseLedgerError, match="transition failed"):
            method("doc-1", RuntimeError("must not disappear"))


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
        "opening_case_committed_spend_usd": {},
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
