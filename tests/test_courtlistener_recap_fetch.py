from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    CourtListenerRecapFetchOutcomeUnknown,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecapFetchHTTPResponse,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)


def test_purchase_verifies_id_then_submits_exact_broker_contract_and_recovers(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _response(
                "GET",
                "/recap-documents/123/",
                {
                    "id": 123,
                    "is_available": True,
                    "filepath_local": "https://storage.courtlistener.com/123.pdf",
                },
            ),
        ]
    )
    broker = FixtureRecapFetchPurchaseBroker(
        [{"id": 77, "reservation_id": "reservation-1"}]
    )
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CourtListenerRecapFetchClient(
            _config(), journal=journal, transport=transport, purchase_broker=broker
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )

        assert journal.statuses() == {"123": "confirmed"}
        assert journal.committed_amount_usd == "3.05"

    assert result.executed_purchase_count == 1
    assert result.attempts[0].source_provider == "courtlistener.recap-fetch+pacer"
    assert result.attempts[0].pacer_fees == {
        "pacer_fee_usd": "3.05",
        "service_fee_usd": "0.00",
        "total_usd": "3.05",
        "cost_basis": "worst_case_reservation",
    }
    assert broker.requests == [
        {
            "request_type": "2",
            "recap_document": "123",
            "cycle_id": "cycle-1",
            "purchase_policy_sha256": policy.policy_sha256,
            "operation_key": broker.requests[0]["operation_key"],
            "reservation_usd": "3.05",
        }
    ]


def test_live_fails_closed_without_budget_broker_before_paid_submission(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    transport = FixtureRecapFetchTransport(
        [_response("GET", "/recap-documents/123/", {"id": 123})]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        with pytest.raises(CourtListenerRecapFetchError, match="budget-enforcing"):
            CourtListenerRecapFetchClient(
                _config(), journal=journal, transport=transport
            ).execute_purchase_plan(
                _plan(),
                public_documents=_public_documents(),
                live=True,
                acknowledge_pacer_fees=True,
            )
        assert journal.statuses() == {"123": "planned"}


def test_unknown_broker_outcome_is_reserved_and_never_retried(tmp_path: Path) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    broker = FixtureRecapFetchPurchaseBroker([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [_response("GET", "/recap-documents/123/", {"id": 123})]
            ),
            purchase_broker=broker,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"123": "unknown"}
        assert journal.committed_amount_usd == "3.05"
    assert result.attempts[0].status.value == "unknown"
    assert len(broker.requests) == 1


def test_confirmed_reservation_can_be_reconciled_to_authoritative_fee(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 2}),
                    _response(
                        "GET",
                        "/recap-documents/123/",
                        {
                            "id": 123,
                            "is_available": True,
                            "filepath_local": "https://storage.courtlistener.com/123.pdf",
                        },
                    ),
                ]
            ),
            purchase_broker=FixtureRecapFetchPurchaseBroker(
                [{"id": 77, "reservation_id": "reservation-1"}]
            ),
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        journal.reconcile(
            {
                "source_document_id": "123",
                "disposition": "confirmed",
                "source_type": "billing_receipt",
                "source_reference": "broker-receipt-1",
                "pacer_fees": {
                    "pacerFee": "1.20",
                    "serviceFee": "0.00",
                    "total": "1.20",
                },
                "download_url": "https://storage.courtlistener.com/123.pdf",
            }
        )
        assert journal.committed_amount_usd == "1.20"


@pytest.mark.parametrize(
    "starting_status", ["submitted", "unknown", "queued", "confirmed", "failed"]
)
def test_reconciliation_replays_every_preconfirmation_paid_state(
    tmp_path: Path, starting_status: str
) -> None:
    ledger = (tmp_path / f"purchases-{starting_status}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    context = {
        "source_provider": "courtlistener.recap-fetch+pacer",
        "reservation_usd": "3.05",
    }
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(_plan())
        journal.submit("123", context=context)
        if starting_status in {"queued", "confirmed", "failed"}:
            journal.queue(
                "123",
                response={**context, "queue_id": "77", "reservation_id": "r-1"},
            )
        if starting_status == "unknown":
            journal.mark_unknown("123", "ambiguous")
        elif starting_status == "confirmed":
            journal.confirm_reserved(
                "123",
                response={
                    **context,
                    "queue_id": "77",
                    "download_url": "https://storage.courtlistener.com/123.pdf",
                },
            )
        elif starting_status == "failed":
            journal.fail("123", RuntimeError("terminal"))
        journal.reconcile(
            {
                "source_document_id": "123",
                "disposition": "confirmed",
                "source_type": "billing_receipt",
                "source_reference": "broker-receipt-1",
                "pacer_fees": {
                    "pacerFee": "1.20",
                    "serviceFee": "0.00",
                    "total": "1.20",
                },
                "download_url": "https://storage.courtlistener.com/123.pdf",
            }
        )
        result = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport([]),
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
    assert result.executed_purchase_count == 1
    assert result.attempts[0].reason == (
        "confirmed_with_authoritative_fee_reconciliation"
    )
    assert result.attempts[0].pacer_fees is not None
    assert result.attempts[0].pacer_fees["total_usd"] == "1.20"


def test_config_repr_never_exposes_courtlistener_token() -> None:
    assert "fixture-token" not in repr(_config())


def test_noncharging_poll_retries_transient_transport_failure(
    tmp_path: Path,
) -> None:
    class _TransientPollTransport:
        def __init__(self) -> None:
            self.delegate = FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                ]
            )
            self.failed = False

        def request(
            self,
            *,
            method: str,
            path: str,
            form: Mapping[str, str],
            headers: Mapping[str, str],
            timeout_seconds: float,
        ) -> RecapFetchHTTPResponse:
            if path == "/recap-fetch/77/" and not self.failed:
                self.failed = True
                raise CourtListenerRecapFetchOutcomeUnknown("timeout")
            return self.delegate.request(
                method=method,
                path=path,
                form=form,
                headers=headers,
                timeout_seconds=timeout_seconds,
            )

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    transport = _TransientPollTransport()
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker(
                [{"id": 77, "reservation_id": "reservation-1"}]
            ),
            poll_attempts=1,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
    assert transport.failed is True
    assert result.attempts[0].reason == "recap_fetch_queued_status_1"


def test_cli_help_exposes_brokered_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", "purchase-missing-recap-fetch", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--purchase-broker-fixture" in output
    assert "--live-purchase" in output


@pytest.mark.parametrize(
    ("queue_status", "expected_status", "expected_reason"),
    [
        (1, "not_attempted", "recap_fetch_queued_status_1"),
        (3, "provider_error", "recap_fetch_status_3"),
        (4, "not_attempted", "recap_fetch_queued_status_4"),
        (5, "not_attempted", "recap_fetch_queued_status_5"),
        (6, "provider_error", "recap_fetch_status_6"),
        (7, "provider_error", "recap_fetch_status_7"),
    ],
)
def test_all_non_success_queue_statuses_are_fail_closed(
    tmp_path: Path,
    queue_status: int,
    expected_status: str,
    expected_reason: str,
) -> None:
    ledger = (tmp_path / f"purchases-{queue_status}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            *[
                _response("GET", "/recap-fetch/77/", {"status": queue_status})
                for _ in range(3 if queue_status in {1, 4, 5} else 1)
            ],
        ]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker(
                [{"id": 77, "reservation_id": "reservation-1"}]
            ),
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.committed_amount_usd == "3.05"
    assert result.attempts[0].status.value == expected_status
    assert result.attempts[0].reason == expected_reason


def test_resume_queued_polls_without_duplicate_paid_submission(tmp_path: Path) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    first_broker = FixtureRecapFetchPurchaseBroker(
        [{"id": 77, "reservation_id": "reservation-1"}]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        first = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                ]
            ),
            purchase_broker=first_broker,
            poll_attempts=1,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert first.attempts[0].status.value == "not_attempted"
        assert journal.statuses() == {"123": "queued"}

    second_broker = FixtureRecapFetchPurchaseBroker([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        second = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-fetch/77/", {"status": 2}),
                    _response(
                        "GET",
                        "/recap-documents/123/",
                        {
                            "id": 123,
                            "is_available": True,
                            "filepath_local": "https://storage.courtlistener.com/123.pdf",
                        },
                    ),
                ]
            ),
            purchase_broker=second_broker,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
    assert second.executed_purchase_count == 1
    assert len(first_broker.requests) == 1
    assert second_broker.requests == []


def test_replayed_terminal_failure_does_not_starve_later_document(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    plan = _plan(("123", "124"))
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(plan)
        journal.submit("123")
        journal.queue("123", response={"queue_id": "77"})
        journal.fail("123", RuntimeError("terminal"))

    broker = FixtureRecapFetchPurchaseBroker(
        [{"id": 78, "reservation_id": "reservation-2"}]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        result = CourtListenerRecapFetchClient(
            _config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/124/", {"id": 124}),
                    _response("GET", "/recap-fetch/78/", {"status": 2}),
                    _response(
                        "GET",
                        "/recap-documents/124/",
                        {
                            "id": 124,
                            "is_available": True,
                            "filepath_local": "https://storage.courtlistener.com/124.pdf",
                        },
                    ),
                ]
            ),
            purchase_broker=broker,
        ).execute_purchase_plan(
            plan,
            public_documents={
                **_public_documents(),
                "124": {
                    "redaction_or_seal_status": "public",
                    "is_sealed": False,
                    "is_private": False,
                },
            },
            live=True,
            acknowledge_pacer_fees=True,
        )
    assert [attempt.status.value for attempt in result.attempts] == [
        "provider_error",
        "purchased",
    ]
    assert len(broker.requests) == 1


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"redaction_or_seal_status": "sealed", "is_sealed": True, "is_private": False},
        {"redaction_or_seal_status": "public", "is_sealed": False},
        {"redaction_or_seal_status": "public", "is_sealed": False, "is_private": True},
    ],
)
def test_restricted_or_unknown_documents_never_reach_provider(
    tmp_path: Path, metadata: dict[str, object]
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    transport = FixtureRecapFetchTransport([])
    broker = FixtureRecapFetchPurchaseBroker([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        with pytest.raises(CourtListenerRecapFetchError, match="public"):
            CourtListenerRecapFetchClient(
                _config(), journal=journal, transport=transport, purchase_broker=broker
            ).execute_purchase_plan(
                _plan(),
                public_documents={"123": metadata},
                live=True,
                acknowledge_pacer_fees=True,
            )
    assert transport.requests == []
    assert broker.requests == []


def test_document_identity_mismatch_blocks_paid_submission(tmp_path: Path) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    broker = FixtureRecapFetchPurchaseBroker([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        with pytest.raises(CourtListenerRecapFetchError, match="identity mismatch"):
            CourtListenerRecapFetchClient(
                _config(),
                journal=journal,
                transport=FixtureRecapFetchTransport(
                    [_response("GET", "/recap-documents/123/", {"id": 999})]
                ),
                purchase_broker=broker,
            ).execute_purchase_plan(
                _plan(),
                public_documents=_public_documents(),
                live=True,
                acknowledge_pacer_fees=True,
            )
    assert broker.requests == []


def _response(
    method: str, path: str, payload: dict[str, object]
) -> RecordedRecapFetchResponse:
    return RecordedRecapFetchResponse(method, path, {}, 200, payload)


def _config() -> CourtListenerRecapFetchConfig:
    return CourtListenerRecapFetchConfig(api_token="fixture-token")


def _public_documents() -> dict[str, dict[str, object]]:
    return {
        "123": {
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
        }
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
        max_projected_budget=Decimal("9.15"),
        max_missing_core_documents_per_case=3,
        dry_run=False,
    )


def _policy(ledger: Path) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "9.15",
            "opening_committed_spend_usd": "0.00",
            "max_per_case_usd": "9.15",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-13T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
