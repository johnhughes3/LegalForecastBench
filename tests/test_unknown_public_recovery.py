from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import legalforecast.ingestion.recap_fetch_quarantine_recovery as recovery_module
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    PurchaseMaterialState,
    generate_case_dev_purchase_policy,
    validate_unknown_public_recovery_evidence,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.recap_fetch_broker import recap_fetch_client_code
from legalforecast.ingestion.recap_fetch_quarantine_recovery import (
    RecapFetchQuarantineRecoveryError,
    recover_recap_fetch_quarantine_documents,
    validate_terminal_unavailable_records,
    write_recap_fetch_quarantine_manifest,
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

        records, restrictions, terminal_unavailable = (
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=source,
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=transport,
            )
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
    assert terminal_unavailable == ()
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


def test_recovery_repairs_exact_legacy_relative_url_commitment_before_bytes(
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
    relative_path = "recap/gov.uscourts.example.123/gov.uscourts.example.123.1.0.pdf"
    detail = {
        "id": 123,
        "is_available": True,
        "is_sealed": None,
        "is_private": False,
        "filepath_local": relative_path,
    }
    detail_digest = hashlib.sha256(
        json.dumps(detail, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    legacy_url = f"https://www.courtlistener.com/{relative_path}"
    corrected_url = f"https://storage.courtlistener.com/{relative_path}"
    corrected_digest = hashlib.sha256(corrected_url.encode()).hexdigest()

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.queue(
            "123",
            response={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
                "queue_id": "77",
                "reservation_id": "reservation-123",
            },
        )
        journal.mark_material_available_for_quarantine(
            "123",
            provider_detail_sha256=detail_digest,
            queue_response_sha256="8" * 64,
            download_url_sha256=hashlib.sha256(legacy_url.encode()).hexdigest(),
        )

        with pytest.raises(RecapFetchQuarantineRecoveryError, match="download failed"):
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=FixtureFreeDocumentSource({}),
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=_detail_transport(detail),
            )

        pending = journal.operation_evidence("123")
        assert pending is not None
        assert pending["material_state"] is (
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE
        )
        journal.correct_legacy_courtlistener_url_commitment(
            "123",
            candidate_id="case-1",
            operation_key=str(pending["operation_key"]),
            attempt_policy_sha256="a" * 64,
            attempt_document_sha256="9" * 64,
            provider_detail_sha256=detail_digest,
            queue_response_sha256="8" * 64,
            legacy_download_url_sha256=hashlib.sha256(legacy_url.encode()).hexdigest(),
            corrected_download_url_sha256=corrected_digest,
        )
        source = FixtureFreeDocumentSource({corrected_url: b"%PDF-1.4\npublic\n%%EOF"})
        records, restrictions, terminal_unavailable = (
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=source,
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=_detail_transport(detail),
            )
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        assert operation["material_state"] is (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )
        assert operation["material_evidence"]["download_url_sha256"] == (
            corrected_digest
        )
        operation_key = str(operation["operation_key"])
        journal.record_broker_receipt(
            "123",
            {
                "operation_key": operation_key,
                "reservation_id": "reservation-123",
                "cycle_id": "cycle-1",
                "purchase_policy_sha256": policy.policy_sha256,
                "recap_document": "123",
                "case_id": "case-1",
                "client_code": "test",
                "reservation_usd": "3.05",
                "id": "77",
                "state": "confirmed",
                "authoritative_fee_usd": "3.05",
                "billing_evidence": {"evidence_sha256": "f" * 64},
            },
        )
        journal.reconcile_unknown_broker_billing(
            "123",
            actual_usd="3.05",
            evidence_sha256="f" * 64,
            source_reference=f"recap-fetch-broker:{operation_key}:{'f' * 64}",
        )
        journal.reconcile(
            {
                "source_document_id": "123",
                "disposition": "write_off",
                "source_type": "support_confirmation",
                "source_reference": "fixture://post-confirmation-write-off",
                "pacer_fees": None,
                "download_url": None,
            }
        )

    assert len(records) == len(restrictions) == 1
    assert terminal_unavailable == ()
    assert source.requested_urls == (corrected_url,)

    with CaseDevPurchaseJournal(ledger, policy=policy) as reopened:
        operation = reopened.operation_evidence("123")
        assert operation is not None
        assert operation["status"] == "unknown"
        assert operation["actual_usd"] == "3.05"
        assert operation["material_state"] is (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )

    with closing(sqlite3.connect(ledger)) as connection:
        row = connection.execute(
            "SELECT response_json FROM purchase_operations "
            "WHERE source_document_id='123'"
        ).fetchone()
        assert row is not None
        original_response_json = str(row[0])
        response = json.loads(original_response_json)
        response["courtlistener_url_commitment_correction"]["record_sha256"] = "0" * 64
        connection.execute(
            "UPDATE purchase_operations SET response_json=? "
            "WHERE source_document_id='123'",
            (json.dumps(response, sort_keys=True, separators=(",", ":")),),
        )
        connection.commit()
    with pytest.raises(CaseDevPurchaseLedgerError, match="correction record"):
        with CaseDevPurchaseJournal(ledger, policy=policy):
            pass
    with closing(sqlite3.connect(ledger)) as connection:
        connection.execute(
            "UPDATE purchase_operations SET response_json=? "
            "WHERE source_document_id='123'",
            (original_response_json,),
        )
        connection.execute(
            "UPDATE purchase_operations SET operation_key=NULL "
            "WHERE source_document_id='123'"
        )
        connection.commit()
    with pytest.raises(CaseDevPurchaseLedgerError, match="correction record"):
        with CaseDevPurchaseJournal(ledger, policy=policy):
            pass
    with closing(sqlite3.connect(ledger)) as connection:
        connection.execute(
            "UPDATE purchase_operations SET operation_key='not-a-uuid' "
            "WHERE source_document_id='123'"
        )
        connection.commit()
    with pytest.raises(CaseDevPurchaseLedgerError, match="correction record"):
        with CaseDevPurchaseJournal(ledger, policy=policy):
            pass
    with closing(sqlite3.connect(ledger)) as connection:
        connection.execute(
            "UPDATE purchase_operations SET operation_key=? "
            "WHERE source_document_id='123'",
            (response["courtlistener_url_commitment_correction"]["operation_key"],),
        )
        connection.execute(
            "UPDATE purchase_operations SET response_json='[]' "
            "WHERE source_document_id='123'"
        )
        connection.commit()
    with pytest.raises(CaseDevPurchaseLedgerError, match="must be an object"):
        with CaseDevPurchaseJournal(ledger, policy=policy):
            pass


def test_recovery_repairs_authenticated_unknown_public_legacy_url_before_bytes(
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
    relative_path = "recap/gov.uscourts.example.123/gov.uscourts.example.123.1.0.pdf"
    detail = {
        "id": 123,
        "is_available": True,
        "is_sealed": None,
        "is_private": False,
        "filepath_local": relative_path,
    }
    detail_digest = hashlib.sha256(
        json.dumps(detail, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    legacy_url = f"https://www.courtlistener.com/{relative_path}"
    corrected_url = f"https://storage.courtlistener.com/{relative_path}"
    legacy_digest = hashlib.sha256(legacy_url.encode()).hexdigest()
    corrected_digest = hashlib.sha256(corrected_url.encode()).hexdigest()

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.mark_unknown("123", "direct CourtListener purchase returned HTTP 400")
        pending_operation = journal.operation_evidence("123")
        assert pending_operation is not None
        journal.mark_unknown_public_material_available(
            "123",
            candidate_id="case-1",
            operation_key=str(pending_operation["operation_key"]),
            attempt_policy_sha256="a" * 64,
            attempt_document_sha256="9" * 64,
            provider_detail_sha256=detail_digest,
            download_url_sha256=legacy_digest,
        )
        with closing(sqlite3.connect(ledger)) as connection:
            connection.execute(
                "UPDATE purchase_operations SET response_json=? "
                "WHERE source_document_id='123'",
                (
                    json.dumps(
                        {
                            "reservation_usd": "3.05",
                            "source_provider": "courtlistener.recap-fetch+pacer",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
            connection.commit()

        with pytest.raises(RecapFetchQuarantineRecoveryError, match="download failed"):
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=FixtureFreeDocumentSource({}),
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=_detail_transport(detail),
            )
        corrected_operation = journal.operation_evidence("123")
        assert corrected_operation is not None
        assert corrected_operation["material_state"] is (
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE
        )
        recovery = corrected_operation["public_material_recovery"]
        assert recovery["schema_version"] == (
            "legalforecast.unknown_public_material_recovery.v2"
        )
        correction = recovery["courtlistener_url_commitment_correction"]
        assert correction["legacy_download_url_sha256"] == legacy_digest
        assert correction["corrected_download_url_sha256"] == corrected_digest
        assert not recovery_module._is_bound_public_recovery(
            recovery,
            operation=corrected_operation,
            candidate_id="case-1",
            document_id="123",
            attempt_policy_sha256="a" * 64,
            selection_document_sha256="9" * 64,
            purchase_policy_sha256="0" * 64,
        )
        for mismatched_operation in (
            {**corrected_operation, "candidate_id": "other-case"},
            {**corrected_operation, "source_document_id": "other-document"},
        ):
            with pytest.raises(
                CaseDevPurchaseLedgerError,
                match="operation identity conflicts",
            ):
                validate_unknown_public_recovery_evidence(
                    recovery,
                    mismatched_operation,
                    candidate_id="case-1",
                    document_id="123",
                    purchase_policy_sha256=policy.policy_sha256,
                )
        with pytest.raises(
            CaseDevPurchaseLedgerError,
            match="purchase policy is invalid",
        ):
            validate_unknown_public_recovery_evidence(
                recovery,
                corrected_operation,
                candidate_id="case-1",
                document_id="123",
                purchase_policy_sha256="not-a-policy-sha",
            )
        journal.correct_unknown_public_recovery_url_commitment(
            "123",
            candidate_id="case-1",
            operation_key=str(corrected_operation["operation_key"]),
            attempt_policy_sha256="a" * 64,
            attempt_document_sha256="9" * 64,
            provider_detail_sha256=detail_digest,
            legacy_download_url_sha256=legacy_digest,
            corrected_download_url_sha256=corrected_digest,
        )
        source = FixtureFreeDocumentSource({corrected_url: b"%PDF-1.4\npublic\n%%EOF"})
        records, restrictions, terminal_unavailable = (
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=source,
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=_detail_transport(detail),
            )
        )
        recovered_operation = journal.operation_evidence("123")
        assert recovered_operation is not None
        journal.correct_unknown_public_recovery_url_commitment(
            "123",
            candidate_id="case-1",
            operation_key=str(recovered_operation["operation_key"]),
            attempt_policy_sha256="a" * 64,
            attempt_document_sha256="9" * 64,
            provider_detail_sha256=detail_digest,
            legacy_download_url_sha256=legacy_digest,
            corrected_download_url_sha256=corrected_digest,
        )

    assert len(records) == len(restrictions) == 1
    assert terminal_unavailable == ()
    assert source.requested_urls == (corrected_url,)
    with CaseDevPurchaseJournal(ledger, policy=policy) as reopened:
        operation = reopened.operation_evidence("123")
        assert operation is not None
        assert operation["material_state"] is (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )

    with closing(sqlite3.connect(ledger)) as connection:
        original_row = connection.execute(
            "SELECT record_json, record_sha256 "
            "FROM unknown_public_material_recoveries "
            "WHERE source_document_id='123'"
        ).fetchone()
    assert original_row is not None
    original_record_json, original_record_sha256 = map(str, original_row)
    for bad_legacy_digest in ("not-a-sha256", corrected_digest):
        tampered = json.loads(original_record_json)
        correction = tampered["courtlistener_url_commitment_correction"]
        correction["legacy_download_url_sha256"] = bad_legacy_digest
        legacy_recovery = {
            key: value
            for key, value in tampered.items()
            if key != "courtlistener_url_commitment_correction"
        }
        legacy_recovery["schema_version"] = (
            "legalforecast.unknown_public_material_recovery.v1"
        )
        legacy_recovery["download_url_sha256"] = bad_legacy_digest
        correction["legacy_recovery_record_sha256"] = hashlib.sha256(
            json.dumps(legacy_recovery, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        correction_without_digest = {
            key: value for key, value in correction.items() if key != "record_sha256"
        }
        correction["record_sha256"] = hashlib.sha256(
            json.dumps(
                correction_without_digest, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        tampered_json = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        with closing(sqlite3.connect(ledger)) as connection:
            connection.execute(
                "UPDATE unknown_public_material_recoveries "
                "SET record_json=?, record_sha256=? "
                "WHERE source_document_id='123'",
                (
                    tampered_json,
                    hashlib.sha256(tampered_json.encode()).hexdigest(),
                ),
            )
            connection.commit()
        with pytest.raises(
            CaseDevPurchaseLedgerError,
            match="unknown public recovery correction record is invalid",
        ):
            with CaseDevPurchaseJournal(ledger, policy=policy):
                pass
        with closing(sqlite3.connect(ledger)) as connection:
            connection.execute(
                "UPDATE unknown_public_material_recoveries "
                "SET record_json=?, record_sha256=? "
                "WHERE source_document_id='123'",
                (original_record_json, original_record_sha256),
            )
            connection.commit()


def test_recovery_repairs_confirmed_billed_legacy_commitment_before_bytes(
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
    relative_path = "recap/gov.uscourts.example.123/gov.uscourts.example.123.1.0.pdf"
    detail = {
        "id": 123,
        "is_available": True,
        "is_sealed": None,
        "is_private": False,
        "filepath_local": relative_path,
    }
    detail_digest = hashlib.sha256(
        json.dumps(detail, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    legacy_url = f"https://www.courtlistener.com/{relative_path}"
    corrected_url = f"https://storage.courtlistener.com/{relative_path}"
    billing_digest = "f" * 64

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.queue(
            "123",
            response={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
                "queue_id": "77",
                "reservation_id": "reservation-123",
            },
        )
        journal.mark_material_available_for_quarantine(
            "123",
            provider_detail_sha256=detail_digest,
            queue_response_sha256="8" * 64,
            download_url_sha256=hashlib.sha256(legacy_url.encode()).hexdigest(),
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        operation_key = str(operation["operation_key"])
        confirmed_receipt = _broker_receipt(
            operation_key=operation_key,
            policy_sha256=policy.policy_sha256,
            document_id="123",
            reservation_id="reservation-123",
        )
        confirmed_receipt.update(
            {
                "state": "confirmed",
                "held_usd": "3.05",
                "authoritative_fee_usd": "3.05",
                "updated_at": "2026-08-05T00:02:00.000Z",
                "delivered_at": "2026-08-05T00:01:00.000Z",
                "reconciled_at": "2026-08-05T00:02:00.000Z",
                "billing_evidence": {
                    "kind": "pacer_detailed_transactions",
                    "statement_period": "2026-08",
                    "evidence_sha256": billing_digest,
                    "evidence_ref": "statement-123",
                    "imported_at": "2026-08-05T00:02:00.000Z",
                },
            }
        )
        journal.record_broker_receipt(
            "123",
            confirmed_receipt,
        )
        journal.reconcile_unknown_broker_billing(
            "123",
            actual_usd="3.05",
            evidence_sha256=billing_digest,
            source_reference=(f"recap-fetch-broker:{operation_key}:{billing_digest}"),
        )

        source = FixtureFreeDocumentSource({corrected_url: b"%PDF-1.4\npublic\n%%EOF"})
        records, restrictions, terminal_unavailable = (
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=source,
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=_detail_transport(detail),
            )
        )
        corrected = journal.operation_evidence("123")
        assert corrected is not None
        assert corrected["status"] == "confirmed"
        assert corrected["actual_usd"] == "3.05"
        assert corrected["material_state"] is (
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE
        )
        assert corrected["response"]["courtlistener_url_commitment_correction"][
            "billing_authority"
        ] == {
            "state": "confirmed_billed",
            "actual_usd": "3.05",
            "billing_evidence_sha256": billing_digest,
            "source_reference": (
                f"recap-fetch-broker:{operation_key}:{billing_digest}"
            ),
            "reconciliation_sha256": hashlib.sha256(
                json.dumps(
                    corrected["reconciliation"],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        }
        journal.reconcile(
            {
                "source_document_id": "123",
                "disposition": "write_off",
                "source_type": "support_confirmation",
                "source_reference": "fixture://post-confirmation-write-off",
                "pacer_fees": None,
                "download_url": None,
            }
        )

    assert len(records) == len(restrictions) == 1
    assert terminal_unavailable == ()
    assert source.requested_urls == (corrected_url,)
    with CaseDevPurchaseJournal(ledger, policy=policy) as reopened:
        operation = reopened.operation_evidence("123")
        assert operation is not None
        assert operation["status"] == "unknown"
        assert operation["actual_usd"] == "3.05"
    with closing(sqlite3.connect(ledger)) as connection:
        row = connection.execute(
            "SELECT response_json FROM purchase_operations "
            "WHERE source_document_id='123'"
        ).fetchone()
        assert row is not None
        response = json.loads(str(row[0]))
        correction = response["courtlistener_url_commitment_correction"]
        correction["billing_authority"]["reconciliation_sha256"] = "0" * 64
        correction_without_hash = {
            key: value for key, value in correction.items() if key != "record_sha256"
        }
        correction["record_sha256"] = hashlib.sha256(
            json.dumps(
                correction_without_hash,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        connection.execute(
            "UPDATE purchase_operations SET response_json=? "
            "WHERE source_document_id='123'",
            (json.dumps(response, sort_keys=True, separators=(",", ":")),),
        )
        connection.commit()
    with pytest.raises(CaseDevPurchaseLedgerError, match="billing authority"):
        with CaseDevPurchaseJournal(ledger, policy=policy):
            pass


@pytest.mark.parametrize(
    "conflict",
    (
        "wrong_url",
        "changed_detail",
        "destination",
        "actual",
        "reconciliation",
        "error",
        "reservation",
    ),
)
def test_recovery_rejects_unsafe_legacy_url_correction(
    tmp_path: Path, conflict: str
) -> None:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    allowed = {
        "123": {
            "case_id": "case-1",
            "selection_document_sha256": "9" * 64,
        }
    }
    relative_path = "recap/gov.uscourts.example.123/document.pdf"
    detail = {
        "id": 123,
        "is_available": True,
        "is_sealed": None,
        "is_private": False,
        "filepath_local": relative_path,
    }
    detail_digest = hashlib.sha256(
        json.dumps(detail, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    legacy_url = f"https://www.courtlistener.com/{relative_path}"
    legacy_digest = hashlib.sha256(legacy_url.encode()).hexdigest()

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.queue(
            "123",
            response={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
                "queue_id": "77",
                "reservation_id": "reservation-123",
            },
        )
        journal.mark_material_available_for_quarantine(
            "123",
            provider_detail_sha256=(
                "6" * 64 if conflict == "changed_detail" else detail_digest
            ),
            queue_response_sha256="8" * 64,
            download_url_sha256=(
                "7" * 64 if conflict == "wrong_url" else legacy_digest
            ),
        )
        if conflict == "destination":
            destination = tmp_path / "quarantine/case-1/123.pdf"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(tmp_path / "missing.pdf")
        if conflict in {"actual", "reconciliation", "error", "reservation"}:
            with closing(sqlite3.connect(ledger)) as connection:
                if conflict == "reservation":
                    row = connection.execute(
                        "SELECT response_json FROM purchase_operations "
                        "WHERE source_document_id='123'"
                    ).fetchone()
                    assert row is not None
                    response = json.loads(str(row[0]))
                    response["reservation_usd"] = "2.00"
                    connection.execute(
                        "UPDATE purchase_operations SET response_json=? "
                        "WHERE source_document_id='123'",
                        (json.dumps(response, sort_keys=True, separators=(",", ":")),),
                    )
                else:
                    field = {
                        "actual": "actual_usd",
                        "reconciliation": "reconciliation_json",
                        "error": "error",
                    }[conflict]
                    value = "1.00" if conflict == "actual" else "{}"
                    connection.execute(
                        f"UPDATE purchase_operations SET {field}=? "
                        "WHERE source_document_id='123'",
                        (value,),
                    )
                connection.commit()

        with pytest.raises(
            RecapFetchQuarantineRecoveryError,
            match="conflicts with delivery commitment",
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
        assert operation["material_state"] is (
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE
        )
        assert operation["material_evidence"]["download_url_sha256"] == (
            "7" * 64 if conflict == "wrong_url" else legacy_digest
        )


def test_terminal_writer_names_conflicting_artifact(tmp_path: Path) -> None:
    path = tmp_path / "terminal.jsonl"
    write_recap_fetch_quarantine_manifest(
        path, (), label="terminal unavailable operations"
    )
    with pytest.raises(
        RecapFetchQuarantineRecoveryError,
        match="existing terminal unavailable operations conflicts",
    ):
        write_recap_fetch_quarantine_manifest(
            path,
            ({"different": True},),
            label="terminal unavailable operations",
        )


def test_recovery_partitions_canonical_terminal_failure_without_provider_request(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    allowed = {
        document_id: {
            "case_id": "case-1",
            "selection_document_sha256": digest * 64,
        }
        for document_id, digest in (("123", "9"), ("124", "8"))
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
        assert journal.submit(
            "124",
            context={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
            },
        )
        journal.queue(
            "124",
            response={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
                "queue_id": "77",
                "reservation_id": "reservation-124",
            },
        )
        terminal_operation = journal.operation_evidence("124")
        assert terminal_operation is not None
        journal.record_broker_receipt(
            "124",
            _broker_receipt(
                operation_key=str(terminal_operation["operation_key"]),
                policy_sha256=policy.policy_sha256,
                document_id="124",
                reservation_id="reservation-124",
            ),
        )
        journal.fail(
            "124",
            CourtListenerRecapFetchError("RECAP Fetch terminal queue status 6"),
        )

        records, restrictions, terminal_unavailable = (
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=source,
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=transport,
            )
        )

    assert transport.requests == [("GET", "/recap-documents/123/", {})]
    assert len(records) == len(restrictions) == 1
    assert len(terminal_unavailable) == 1
    terminal = terminal_unavailable[0]
    assert terminal["schema_version"] == (
        "legalforecast.recap_fetch_terminal_unavailable.v1"
    )
    assert terminal["candidate_id"] == "case-1"
    assert terminal["source_document_id"] == "124"
    assert terminal["queue_status"] == 6
    assert terminal["ledger_status"] == "failed"
    assert terminal["material_state"] == "not_recovered"
    assert terminal["cap_counted"] is True
    assert terminal["recovery_provider_request_executed"] is False
    assert terminal["paid_redispatch_executed"] is False
    assert isinstance(terminal["ledger_operation_sha256"], str)
    assert str(terminal["ledger_operation_sha256"]).startswith("sha256:")
    assert len(terminal["ledger_operation_sha256"]) == 71
    malformed_terminal = dict(terminal)
    malformed_terminal["queue_status"] = 6.0
    with pytest.raises(
        RecapFetchQuarantineRecoveryError,
        match="malformed or ambiguous",
    ):
        validate_terminal_unavailable_records(
            [malformed_terminal], attempt_policy_sha256="a" * 64
        )


@pytest.mark.parametrize(
    ("mutation", "error_pattern"),
    (
        ("wrapper_digest", "terminal broker receipt history is malformed or ambiguous"),
        (
            "cycle_id",
            "terminal broker receipt history conflicts with purchase identity",
        ),
        (
            "purchase_policy_sha256",
            "terminal broker receipt history conflicts with purchase identity",
        ),
        ("duplicate", "terminal broker receipt history is malformed or ambiguous"),
        ("null_history", "terminal broker receipt history is malformed or ambiguous"),
        (
            "queue_id",
            "failed operation is not a canonical terminal-unavailable purchase",
        ),
        (
            "billing_evidence",
            "terminal broker receipt history conflicts with purchase identity",
        ),
    ),
)
def test_recovery_rejects_terminal_operation_with_malformed_broker_history(
    tmp_path: Path,
    mutation: str,
    error_pattern: str,
) -> None:
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    allowed = {
        "123": {
            "case_id": "case-1",
            "selection_document_sha256": "9" * 64,
        }
    }
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit(
            "123",
            context={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
            },
        )
        journal.queue(
            "123",
            response={
                "source_provider": "courtlistener.recap-fetch+pacer",
                "reservation_usd": "3.05",
                "queue_id": "77",
                "reservation_id": "reservation-123",
            },
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        journal.record_broker_receipt(
            "123",
            _broker_receipt(
                operation_key=str(operation["operation_key"]),
                policy_sha256=policy.policy_sha256,
                document_id="123",
                reservation_id="reservation-123",
            ),
        )
        journal.fail(
            "123",
            CourtListenerRecapFetchError("RECAP Fetch terminal queue status 6"),
        )
    with closing(sqlite3.connect(ledger)) as connection:
        raw_response = connection.execute(
            "SELECT response_json FROM purchase_operations "
            "WHERE source_document_id='123'"
        ).fetchone()
        assert raw_response is not None
        response = json.loads(str(raw_response[0]))
        if mutation == "null_history":
            response["broker_receipts"] = None
        elif mutation == "queue_id":
            response["queue_id"] = "\u0667\u0667"
        else:
            receipt_item = response["broker_receipts"][0]
            if mutation == "wrapper_digest":
                receipt_item["sha256"] = "0" * 64
            elif mutation == "duplicate":
                response["broker_receipts"].append(json.loads(json.dumps(receipt_item)))
            elif mutation == "billing_evidence":
                receipt = receipt_item["receipt"]
                receipt.update(
                    {
                        "state": "failed",
                        "held_usd": "0.00",
                        "authoritative_fee_usd": "0.00",
                        "reconciled_at": "2026-08-05T00:01:00.000Z",
                        "billing_evidence": {
                            "kind": "pacer_detailed_transactions",
                            "statement_period": "2026-08",
                            "evidence_sha256": "b" * 64,
                            "evidence_ref": "fixture://billing",
                            "imported_at": "2026-08-05T00:01:00.000Z",
                        },
                    }
                )
                receipt_item["sha256"] = hashlib.sha256(
                    json.dumps(
                        receipt,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
            else:
                receipt_item["receipt"][mutation] = (
                    "cycle-other" if mutation == "cycle_id" else "f" * 64
                )
                receipt_item["sha256"] = hashlib.sha256(
                    json.dumps(
                        receipt_item["receipt"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
        connection.execute(
            "UPDATE purchase_operations SET response_json=? "
            "WHERE source_document_id='123'",
            (json.dumps(response, sort_keys=True, separators=(",", ":")),),
        )
        connection.commit()
    transport = FixtureRecapFetchTransport([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        with pytest.raises(
            RecapFetchQuarantineRecoveryError,
            match=error_pattern,
        ):
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=FixtureFreeDocumentSource({}),
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=transport,
            )
    assert transport.requests == []


def test_recovery_rejects_failed_before_dispatch_as_noncanonical_terminal(
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
    transport = FixtureRecapFetchTransport([])
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        journal.authorize_unknown_material_attempts(
            allowed, attempt_policy_sha256="a" * 64
        )
        assert journal.submit("123") is True
        journal.fail_before_dispatch("123", "local validation failed")

        with pytest.raises(
            RecapFetchQuarantineRecoveryError,
            match="failed operation is not a canonical terminal-unavailable purchase",
        ):
            recover_recap_fetch_quarantine_documents(
                journal=journal,
                allowed_documents=allowed,
                attempt_policy_sha256="a" * 64,
                output_root=tmp_path / "quarantine",
                source=FixtureFreeDocumentSource({}),
                config=CourtListenerRecapFetchConfig(api_token="fixture"),
                transport=transport,
            )

    assert transport.requests == []


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


def _detail_transport(
    detail: dict[str, object],
) -> FixtureRecapFetchTransport:
    return FixtureRecapFetchTransport(
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


def _broker_receipt(
    *,
    operation_key: str,
    policy_sha256: str,
    document_id: str,
    reservation_id: str,
) -> dict[str, object]:
    return {
        "version": "courtlistener-recap-fetch-receipt-v1",
        "operation_key": operation_key,
        "reservation_id": reservation_id,
        "cycle_id": "cycle-1",
        "purchase_policy_sha256": policy_sha256,
        "recap_document": document_id,
        "case_id": "case-1",
        "client_code": recap_fetch_client_code(operation_key),
        "id": "77",
        "state": "queued",
        "reservation_usd": "3.05",
        "held_usd": "3.05",
        "authoritative_fee_usd": None,
        "provider_response_body_sha256": "d" * 64,
        "provider_response_sha256": "e" * 64,
        "submitted_at": "2026-08-05T00:00:00.000Z",
        "updated_at": "2026-08-05T00:01:00.000Z",
        "delivered_at": None,
        "reconciled_at": None,
        "billing_evidence": None,
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
