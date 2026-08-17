from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    read_case_dev_purchase_authority_audit,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    DirectCourtListenerRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecapFetchHTTPResponse,
)
from legalforecast.ingestion.recap_fetch_confirmation_provenance import (
    PUBLIC_DOCUMENT_CONFIRMATION,
    QUEUE_RECEIPT_CONFIRMATION,
    ConfirmationProvenance,
    RecapFetchConfirmationProvenanceError,
    attach_queue_receipt,
    confirmation_provenance_path,
    provenance_from_confirmed_response,
    read_confirmation_provenance,
    record_confirmation_provenance,
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


def test_queue_receipt_confirmation_preserves_frozen_response_shape(
    tmp_path: Path,
) -> None:
    """Observational provenance never enters authenticated purchase bytes."""

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

    assert "confirmation_evidence" not in response
    assert "queue_response" in response
    assert len(paid.calls) == 1


def test_queue_lag_confirmation_preserves_frozen_response_shape(
    tmp_path: Path,
) -> None:
    """Public-document recovery retains the pre-existing response field set."""

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

    assert "confirmation_evidence" not in response
    assert "queue_response" not in response
    assert response["queue_id"] == "77"
    assert len(paid.calls) == 1


def test_queue_lag_confirmation_records_public_document_provenance_sidecar(
    tmp_path: Path,
) -> None:
    """A confirmation without a queue receipt names its weaker evidence."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        _purchase_through_queue_lag(journal)
        response = _confirmed_response(journal, "123")

    recorded = _sidecar(ledger, policy)["123"]
    assert recorded.confirmation_evidence == PUBLIC_DOCUMENT_CONFIRMATION
    assert recorded.queue_id == "77"
    assert recorded.queue_response is None
    assert recorded.queue_receipt_attached_after_confirmation is False
    # The marker is an observation about the frozen bytes, never part of them.
    assert "confirmation_evidence" not in response
    assert "queue_response" not in response


def test_queue_receipt_confirmation_records_the_receipt_it_rested_on(
    tmp_path: Path,
) -> None:
    """The ordinary path is named explicitly too, not left to be inferred."""

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

    recorded = _sidecar(ledger, policy)["123"]
    assert recorded.confirmation_evidence == QUEUE_RECEIPT_CONFIRMATION
    assert recorded.queue_response == {"status": 2}
    assert recorded.queue_receipt_attached_after_confirmation is False


def test_late_visible_queue_receipt_attaches_without_changing_billing_state(
    tmp_path: Path,
) -> None:
    """The stronger receipt is filed once visible; frozen bytes do not move."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        _purchase_through_queue_lag(journal)
        confirmed_before = dict(_confirmed_response(journal, "123"))
        state_before = journal.authenticated_snapshot().purchase_state_sha256

    later = FixtureRecapFetchTransport(
        [_response("GET", "/recap-fetch/77/", {"status": 2})]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        attempt = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=later,
            poll_attempts=3,
            poll_backoff_seconds=0.0,
        ).execute_one_document("case-1", "123")
        confirmed_after = dict(_confirmed_response(journal, "123"))
        state_after = journal.authenticated_snapshot().purchase_state_sha256

    assert attempt.status.value == "purchased"
    recorded = _sidecar(ledger, policy)["123"]
    assert recorded.confirmation_evidence == PUBLIC_DOCUMENT_CONFIRMATION
    assert recorded.queue_response == {"status": 2}
    assert recorded.queue_receipt_attached_after_confirmation is True
    # Billing state, and every byte the purchase digests cover, are untouched.
    assert confirmed_after == confirmed_before
    assert "queue_response" not in confirmed_after
    assert state_after == state_before


def test_confirmed_purchase_without_a_sidecar_backfills_its_provenance(
    tmp_path: Path,
) -> None:
    """A lost observation is reconstructible from the confirmed response."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        _purchase_through_queue_lag(journal)

    confirmation_provenance_path(ledger).unlink()
    exhausted = FixtureRecapFetchTransport([])
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=exhausted,
            poll_attempts=3,
            poll_backoff_seconds=0.0,
        ).execute_one_document("case-1", "123")

    recorded = _sidecar(ledger, policy)["123"]
    assert recorded.confirmation_evidence == PUBLIC_DOCUMENT_CONFIRMATION
    assert recorded.queue_response is None
    # Backfill reconstructs from bytes already held, so it asks CourtListener
    # nothing; only a genuine late attachment costs a free queue read.
    assert exhausted.requests == []


def test_sidecar_stays_outside_the_purchase_authority_byte_closure(
    tmp_path: Path,
) -> None:
    """No observational file may enter an authenticated purchase read."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        _purchase_through_queue_lag(journal)

    sidecar = confirmation_provenance_path(ledger)
    assert sidecar.is_file()
    audit = read_case_dev_purchase_authority_audit(ledger, policy=policy)
    assert sidecar.absolute() not in audit.snapshots
    assert sidecar.absolute() not in audit.absent_paths


def test_late_attachment_is_refused_when_the_confirmed_response_moved(
    tmp_path: Path,
) -> None:
    """A receipt may not be filed against a row the record no longer describes."""

    path = tmp_path / "purchases.sqlite3.confirmation-provenance.json"
    record_confirmation_provenance(
        path,
        cycle_id="cycle-1",
        purchase_policy_sha256="b" * 64,
        provenance=ConfirmationProvenance(
            source_document_id="123",
            queue_id="77",
            confirmation_evidence=PUBLIC_DOCUMENT_CONFIRMATION,
            confirmed_response_sha256="c" * 64,
        ),
    )

    assert not attach_queue_receipt(
        path,
        cycle_id="cycle-1",
        purchase_policy_sha256="b" * 64,
        source_document_id="123",
        confirmed_response_sha256="d" * 64,
        queue_response={"status": 2},
        queue_response_sha256="e" * 64,
    )
    assert (
        read_confirmation_provenance(
            path, cycle_id="cycle-1", purchase_policy_sha256="b" * 64
        )["123"].queue_response
        is None
    )


def test_sidecar_from_another_ledger_generation_reads_as_no_observation(
    tmp_path: Path,
) -> None:
    """A record about a replaced ledger must not be read as this ledger's."""

    path = tmp_path / "purchases.sqlite3.confirmation-provenance.json"
    record_confirmation_provenance(
        path,
        cycle_id="cycle-1",
        purchase_policy_sha256="b" * 64,
        provenance=ConfirmationProvenance(
            source_document_id="123",
            queue_id="77",
            confirmation_evidence=PUBLIC_DOCUMENT_CONFIRMATION,
            confirmed_response_sha256="c" * 64,
        ),
    )

    assert (
        read_confirmation_provenance(
            path, cycle_id="cycle-1", purchase_policy_sha256="f" * 64
        )
        == {}
    )


def test_a_confirmation_that_was_never_queued_gets_no_entry() -> None:
    """Queue-lag provenance must not invent a record for a non-queued buy."""

    assert (
        provenance_from_confirmed_response(
            "123",
            {"download_url": "https://storage.courtlistener.com/123.pdf"},
            confirmed_response_sha256="c" * 64,
        )
        is None
    )


def test_a_foreign_or_corrupt_sidecar_fails_closed(tmp_path: Path) -> None:
    """Silently treating an unreadable document as empty would hide loss."""

    path = tmp_path / "purchases.sqlite3.confirmation-provenance.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(RecapFetchConfirmationProvenanceError):
        read_confirmation_provenance(
            path, cycle_id="cycle-1", purchase_policy_sha256="b" * 64
        )

    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RecapFetchConfirmationProvenanceError):
        read_confirmation_provenance(
            path, cycle_id="cycle-1", purchase_policy_sha256="b" * 64
        )


def _purchase_through_queue_lag(journal: CaseDevPurchaseJournal) -> None:
    """Buy document 123 and confirm it from the PDF while the queue lags."""

    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )
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
    assert len(paid.calls) == 1


def _sidecar(
    ledger: Path, policy: CaseDevPurchasePolicy
) -> Mapping[str, ConfirmationProvenance]:
    return read_confirmation_provenance(
        confirmation_provenance_path(ledger),
        cycle_id=policy.cycle_id,
        purchase_policy_sha256=policy.policy_sha256,
    )


def _confirmed_response(
    journal: CaseDevPurchaseJournal, document_id: str
) -> Mapping[str, object]:
    evidence = journal.operation_evidence(document_id)
    assert evidence is not None
    assert evidence["status"] == "confirmed"
    response = evidence["response"]
    assert isinstance(response, Mapping)
    return cast(Mapping[str, object], response)
