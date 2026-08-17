from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CONFIRMED_BY_PUBLIC_DOCUMENT,
    CONFIRMED_BY_QUEUE_RECEIPT,
    CourtListenerRecapFetchClient,
    DirectCourtListenerRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecapFetchHTTPResponse,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures
from tests.test_direct_courtlistener_purchase import (
    RecordedRecapFetchResponse,
    _available_document_response,
    _direct_config,
    _plan,
    _policy,
    _public_config,
    _public_documents,
    _RecordingPaidTransport,
    _response,
)


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_direct_queue_lag_waits_beyond_default_three_polls_without_duplicate_post(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        result = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                    _response("GET", "/recap-fetch/77/", {"status": 2}),
                    _available_document_response("123"),
                ]
            ),
            purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                _direct_config(), transport=paid
            ),
            poll_attempts=4,
            poll_backoff_seconds=0.0,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert result.attempts[0].status.value == "purchased"
    assert len(paid.calls) == 1


def test_queue_receipt_confirmation_names_its_evidence(tmp_path: Path) -> None:
    """A status=2 queue receipt is recorded as the confirming evidence."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 2}),
                    _available_document_response("123"),
                ]
            ),
            purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                _direct_config(), transport=paid
            ),
            poll_attempts=3,
            poll_backoff_seconds=0.0,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        response = _confirmed_response(journal, "123")

    assert response["confirmation_evidence"] == CONFIRMED_BY_QUEUE_RECEIPT
    assert "queue_response" in response
    assert len(paid.calls) == 1


def test_queue_lag_confirmation_records_public_document_recovery_provenance(
    tmp_path: Path,
) -> None:
    """Confirming from the public PDF names the weaker recovery evidence."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
                    _available_document_response("123"),
                ]
            ),
            purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                _direct_config(), transport=paid
            ),
            poll_attempts=3,
            poll_backoff_seconds=0.0,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        response = _confirmed_response(journal, "123")

    assert response["confirmation_evidence"] == CONFIRMED_BY_PUBLIC_DOCUMENT
    assert "queue_response" not in response
    assert response["queue_id"] == "77"
    assert len(paid.calls) == 1


def _confirmed_response(
    journal: CaseDevPurchaseJournal, document_id: str
) -> Mapping[str, object]:
    evidence = journal.operation_evidence(document_id)
    assert evidence is not None
    assert evidence["status"] == "confirmed"
    response = evidence["response"]
    assert isinstance(response, Mapping)
    return cast(Mapping[str, object], response)
