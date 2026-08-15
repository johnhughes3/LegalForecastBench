from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    DirectCourtListenerRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecapFetchHTTPResponse,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures
from tests.test_direct_courtlistener_purchase import (
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
