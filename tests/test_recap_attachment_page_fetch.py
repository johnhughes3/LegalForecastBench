"""Fake-transport coverage for the attachment-menu (request type 3) lane.

Every fixture here is hand-authored (``synthetic: true``): no PACER or
CourtListener request is made, and the identifiers are invented rather than
copied from any live docket.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.cli_commands.recap_attachment_pages import (
    register as register_cli,
)
from legalforecast.cli_commands.recap_attachment_pages import run as run_cli
from legalforecast.ingestion.courtlistener_client import CourtListenerRecapDocument
from legalforecast.ingestion.courtlistener_recap_fetch import (
    DirectCourtListenerRecapFetchConfig,
    DirectCourtListenerRecapFetchPurchaseBroker,
    RecapFetchHTTPResponse,
)
from legalforecast.ingestion.recap_attachment_page_fetch import (
    ATTACHMENT_PAGE_FETCH_RECEIPT_SCHEMA,
    AttachmentPageFetchError,
    AttachmentPageFetchJournal,
    RecapFetchQueueReader,
    fetch_attachment_pages,
)
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerDefiniteRejection,
    PreparedRecapFetchSubmission,
    recap_fetch_client_code,
)

_AUTHORIZATION_SHA256 = "b" * 64
_MAIN_DOCUMENT = "900100245"
_DOCKET_ENTRY = "800100317"


def _entry_uri(docket_entry_id: str) -> str:
    return (
        f"https://www.courtlistener.com/api/rest/v4/docket-entries/{docket_entry_id}/"
    )


def _document(
    document_id: str,
    *,
    docket_entry_id: str = _DOCKET_ENTRY,
    attachment_number: int | None = None,
    page_count: int | None = None,
    is_available: bool = False,
    filepath_local: str | None = None,
) -> CourtListenerRecapDocument:
    record: dict[str, object] = {
        "id": int(document_id),
        "docket_entry": _entry_uri(docket_entry_id),
        "document_number": "19",
        "attachment_number": attachment_number,
        "description": "Exhibit A",
        "is_available": is_available,
        "page_count": page_count,
        "pacer_doc_id": "091234567892",
    }
    if filepath_local is not None:
        record["filepath_local"] = filepath_local
    return CourtListenerRecapDocument.from_record(record)


class _FakeMetadataClient:
    """Free GET double returning scripted listing views per docket entry."""

    def __init__(
        self,
        *,
        main: CourtListenerRecapDocument | None = None,
        listings: Sequence[Sequence[CourtListenerRecapDocument]] = (),
    ) -> None:
        self._main = main if main is not None else _document(_MAIN_DOCUMENT)
        self._listings = [tuple(listing) for listing in listings]
        self.listing_calls: list[str] = []

    def get_recap_document(self, document_id: str) -> CourtListenerRecapDocument:
        if document_id != self._main.document_id:
            raise AssertionError(f"unexpected document lookup {document_id}")
        return self._main

    def iter_recap_documents(
        self, docket_entry_id: str, *, page_size: int | None = None
    ) -> Iterator[CourtListenerRecapDocument]:
        del page_size
        self.listing_calls.append(docket_entry_id)
        listing = self._listings.pop(0) if self._listings else ()
        return iter(listing)


class _FakeTransport:
    """One transport for both the paid POST and the free queue-detail GET."""

    def __init__(self, responses: Sequence[RecapFetchHTTPResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        *,
        method: str,
        path: str,
        form: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse:
        del headers, timeout_seconds
        self.calls.append({"method": method, "path": path, "form": dict(form)})
        if not self._responses:
            raise AssertionError("unexpected additional CourtListener request")
        return self._responses.pop(0)

    @property
    def paid_calls(self) -> list[dict[str, object]]:
        return [
            call
            for call in self.calls
            if call["method"] == "POST" and call["path"] == "/recap-fetch/"
        ]


class _RejectingBroker:
    """Broker double that refuses before the charge-bearing dispatch."""

    def __init__(self) -> None:
        self.prepared = 0

    @property
    def paid_dispatch_count(self) -> int:
        return 0

    def prepare_submission(self) -> PreparedRecapFetchSubmission:
        self.prepared += 1
        return PreparedRecapFetchSubmission(self._submit)

    def _submit(self, request: Mapping[str, str]) -> Mapping[str, object]:
        del request
        raise BrokerDefiniteRejection("document_not_allowed", "menu is not allowed")

    def receipt(self, operation_key: str) -> Mapping[str, object]:
        del operation_key
        raise AssertionError("the direct lane has no broker receipt")


def _config() -> DirectCourtListenerRecapFetchConfig:
    return DirectCourtListenerRecapFetchConfig(
        api_token="courtlistener-secret",
        pacer_username="pacer-user-secret",
        pacer_password="pacer-password-secret",
        timeout_seconds=7.0,
    )


def _clock() -> datetime:
    return datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


def _run(
    journal: AttachmentPageFetchJournal,
    transport: _FakeTransport,
    metadata_client: _FakeMetadataClient,
    *,
    sleeps: list[float] | None = None,
    max_total_usd: str = "75.00",
    poll_attempts: int = 3,
    documents: Sequence[str] = (_MAIN_DOCUMENT,),
):
    config = _config()
    return fetch_attachment_pages(
        list(documents),
        journal=journal,
        broker=DirectCourtListenerRecapFetchPurchaseBroker(config, transport=transport),
        metadata_client=metadata_client,
        queue_reader=RecapFetchQueueReader(
            transport=transport,
            api_token=config.api_token,
            timeout_seconds=config.timeout_seconds,
        ),
        cycle_id="cycle-1-attachment-menus",
        authorization_sha256=_AUTHORIZATION_SHA256,
        max_total_usd=max_total_usd,
        poll_attempts=poll_attempts,
        poll_backoff_seconds=0.5,
        sleep=(sleeps.append if sleeps is not None else lambda _seconds: None),
        clock=_clock,
    )


def test_attachment_menu_fetch_dispatches_type_three_once_and_resolves_selectors(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 2}
            ),
        ]
    )
    metadata_client = _FakeMetadataClient(
        listings=[
            (),
            (
                _document(_MAIN_DOCUMENT, page_count=3, is_available=True),
                _document(
                    "900100246",
                    attachment_number=1,
                    page_count=4,
                    is_available=False,
                ),
                _document(
                    "900100247",
                    attachment_number=2,
                    page_count=2,
                    is_available=True,
                    filepath_local="recap/gov.uscourts.txt",
                ),
            ),
        ]
    )

    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        result = _run(journal, transport, metadata_client)
        records = journal.records()

    paid = transport.paid_calls
    assert len(paid) == 1
    assert paid[0]["form"] == {
        "request_type": "3",
        "pacer_username": "pacer-user-secret",
        "pacer_password": "pacer-password-secret",
        "recap_document": _MAIN_DOCUMENT,
        "client_code": _client_code(result.outcomes[0].operation_key),
    }
    outcome = result.outcomes[0]
    assert (outcome.state, outcome.reason) == ("confirmed", "queue_completed")
    assert outcome.queue_id == "4242"
    assert outcome.dispatched is True
    assert [selector.source_document_id for selector in outcome.selectors] == [
        "900100246",
        "900100247",
    ]
    assert [selector.projected_cost_usd for selector in outcome.selectors] == [
        "0.40",
        "0.00",
    ]
    assert all(len(selector.record_sha256) == 64 for selector in outcome.selectors)
    assert result.committed_usd == "0.30"
    assert records[0]["state"] == "confirmed"
    assert records[0]["queue_status"] == 2
    assert records[0]["authorization_sha256"] == _AUTHORIZATION_SHA256


def test_receipt_record_publishes_the_versioned_menu_schema(tmp_path: Path) -> None:
    transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 2}
            ),
        ]
    )
    metadata_client = _FakeMetadataClient(
        listings=[(), (_document("900100246", attachment_number=1, page_count=40),)]
    )

    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        record = _run(journal, transport, metadata_client).to_record()

    assert record["schema_version"] == ATTACHMENT_PAGE_FETCH_RECEIPT_SCHEMA
    assert record["cycle_id"] == "cycle-1-attachment-menus"
    assert record["authorization_sha256"] == _AUTHORIZATION_SHA256
    assert record["dispatched_count"] == 1
    assert record["halted"] is False
    assert record["committed_usd"] == "0.30"
    assert record["max_total_usd"] == "75.00"
    outcome_record = record["outcomes"][0]
    assert outcome_record["selector_count"] == 1
    # PACER caps a single item at USD 3.00 regardless of page count.
    assert outcome_record["selectors"][0]["projected_cost_usd"] == "3.00"
    serialized = json.dumps(record, sort_keys=True)
    for secret in (
        "pacer-user-secret",
        "pacer-password-secret",
        "courtlistener-secret",
    ):
        assert secret not in serialized


def test_confirmed_menu_never_dispatches_a_second_paid_post(tmp_path: Path) -> None:
    journal_path = tmp_path / "menus.sqlite3"
    first_transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 2}
            ),
        ]
    )
    with AttachmentPageFetchJournal(journal_path) as journal:
        _run(
            journal,
            first_transport,
            _FakeMetadataClient(
                listings=[(), (_document("900100246", attachment_number=1),)]
            ),
        )

    # A second run may make free GETs, but no further charge-bearing POST.
    second_transport = _FakeTransport([])
    with AttachmentPageFetchJournal(journal_path) as journal:
        result = _run(
            journal,
            second_transport,
            _FakeMetadataClient(
                listings=[(_document("900100246", attachment_number=1),)]
            ),
        )

    assert len(first_transport.paid_calls) == 1
    assert second_transport.paid_calls == []
    outcome = result.outcomes[0]
    assert (outcome.state, outcome.reason) == ("confirmed", "already_confirmed")
    assert outcome.dispatched is False
    assert [selector.source_document_id for selector in outcome.selectors] == [
        "900100246"
    ]
    assert result.committed_usd == "0.30"


def test_ambiguous_prior_dispatch_refuses_to_repeat_the_charge(tmp_path: Path) -> None:
    journal_path = tmp_path / "menus.sqlite3"
    with AttachmentPageFetchJournal(journal_path) as journal:
        journal.reserve(
            _MAIN_DOCUMENT,
            operation_key="00000000-0000-4000-8000-000000000000",
            reservation_usd="0.30",
            cycle_id="cycle-1-attachment-menus",
            authorization_sha256=_AUTHORIZATION_SHA256,
            docket_entry_id=_DOCKET_ENTRY,
            now=_clock(),
        )
        journal.update(
            _MAIN_DOCUMENT,
            state="unknown",
            reason="dispatch_outcome_unknown",
            now=_clock(),
        )

    transport = _FakeTransport([])
    with AttachmentPageFetchJournal(journal_path) as journal:
        result = _run(journal, transport, _FakeMetadataClient())

    assert transport.calls == []
    outcome = result.outcomes[0]
    assert outcome.state == "unknown"
    assert outcome.reason == "prior_unknown_requires_owner_resolution"
    assert result.committed_usd == "0.30"


def test_queue_lag_waits_and_completes_without_a_second_post(tmp_path: Path) -> None:
    transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(status_code=404, payload={}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 1}
            ),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 2}
            ),
        ]
    )
    metadata_client = _FakeMetadataClient(
        listings=[(), (_document("900100246", attachment_number=1, page_count=1),)]
    )
    sleeps: list[float] = []

    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        result = _run(
            journal, transport, metadata_client, sleeps=sleeps, poll_attempts=4
        )

    assert len(transport.paid_calls) == 1
    assert sleeps == [0.5, 0.5]
    outcome = result.outcomes[0]
    assert (outcome.state, outcome.queue_status) == ("confirmed", 2)
    assert outcome.selectors[0].projected_cost_usd == "0.10"


def test_queue_still_pending_stays_resumable_without_repeating_the_post(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "menus.sqlite3"
    first_transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 1}
            ),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 1}
            ),
        ]
    )
    with AttachmentPageFetchJournal(journal_path) as journal:
        first = _run(
            journal,
            first_transport,
            _FakeMetadataClient(listings=[()]),
            poll_attempts=2,
        )

    second_transport = _FakeTransport(
        [RecapFetchHTTPResponse(status_code=200, payload={"id": "4242", "status": 2})]
    )
    with AttachmentPageFetchJournal(journal_path) as journal:
        second = _run(
            journal,
            second_transport,
            _FakeMetadataClient(
                listings=[(_document("900100246", attachment_number=1),)]
            ),
        )

    assert first.outcomes[0].state == "queued"
    assert first.outcomes[0].reason == "queue_pending_status_1"
    assert second_transport.paid_calls == []
    assert second.outcomes[0].state == "confirmed"
    assert second.outcomes[0].dispatched is False


def test_terminal_queue_failure_is_journalled_and_not_retried(tmp_path: Path) -> None:
    journal_path = tmp_path / "menus.sqlite3"
    first_transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 3}
            ),
        ]
    )
    with AttachmentPageFetchJournal(journal_path) as journal:
        first = _run(journal, first_transport, _FakeMetadataClient(listings=[()]))

    second_transport = _FakeTransport([])
    with AttachmentPageFetchJournal(journal_path) as journal:
        second = _run(journal, second_transport, _FakeMetadataClient())

    assert first.outcomes[0].state == "failed"
    assert first.outcomes[0].reason == "queue_status_3"
    assert second_transport.calls == []
    assert second.outcomes[0].reason == "prior_failed_requires_owner_resolution"


def test_existing_attachment_rows_skip_the_purchase(tmp_path: Path) -> None:
    transport = _FakeTransport([])
    metadata_client = _FakeMetadataClient(
        listings=[(_document("900100246", attachment_number=1, page_count=2),)]
    )

    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        result = _run(journal, transport, metadata_client)

    assert transport.calls == []
    outcome = result.outcomes[0]
    assert (outcome.state, outcome.reason) == (
        "skipped",
        "attachment_rows_already_present",
    )
    assert result.committed_usd == "0.00"


def test_prospective_ceiling_breach_halts_before_dispatch(tmp_path: Path) -> None:
    transport = _FakeTransport([])
    metadata_client = _FakeMetadataClient(listings=[()])

    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        result = _run(journal, transport, metadata_client, max_total_usd="0.20")

    assert transport.calls == []
    assert result.halted is True
    assert result.outcomes[0].reason == "prospective_ceiling_breach"
    assert result.committed_usd == "0.00"


def test_pre_dispatch_rejection_stays_redispatchable(tmp_path: Path) -> None:
    journal_path = tmp_path / "menus.sqlite3"

    with AttachmentPageFetchJournal(journal_path) as journal:
        result = fetch_attachment_pages(
            [_MAIN_DOCUMENT],
            journal=journal,
            broker=_RejectingBroker(),
            metadata_client=_FakeMetadataClient(listings=[()]),
            queue_reader=RecapFetchQueueReader(
                transport=_FakeTransport([]), api_token="courtlistener-secret"
            ),
            cycle_id="cycle-1-attachment-menus",
            authorization_sha256=_AUTHORIZATION_SHA256,
            max_total_usd="75.00",
            clock=_clock,
        )
        assert result.outcomes[0].state == "refused"
        assert result.outcomes[0].dispatched is False
        assert journal.record(_MAIN_DOCUMENT) is not None
        assert journal.committed_usd() == 0

    transport = _FakeTransport(
        [
            RecapFetchHTTPResponse(status_code=201, payload={"id": 4242}),
            RecapFetchHTTPResponse(
                status_code=200, payload={"id": "4242", "status": 2}
            ),
        ]
    )
    with AttachmentPageFetchJournal(journal_path) as journal:
        retried = _run(
            journal,
            transport,
            _FakeMetadataClient(
                listings=[(), (_document("900100246", attachment_number=1),)]
            ),
        )

    assert len(transport.paid_calls) == 1
    assert retried.outcomes[0].state == "confirmed"


def test_invalid_run_inputs_fail_closed(tmp_path: Path) -> None:
    with AttachmentPageFetchJournal(tmp_path / "menus.sqlite3") as journal:
        for documents, authorization, ceiling, message in (
            ((_MAIN_DOCUMENT,), "not-hex", "75.00", "invalid authorization digest"),
            ((), _AUTHORIZATION_SHA256, "75.00", "at least one RECAP document"),
            (
                (_MAIN_DOCUMENT, _MAIN_DOCUMENT),
                _AUTHORIZATION_SHA256,
                "75.00",
                "duplicate attachment menu request",
            ),
            (
                (_MAIN_DOCUMENT,),
                _AUTHORIZATION_SHA256,
                "0.005",
                "invalid maximum total amount",
            ),
        ):
            with pytest.raises(AttachmentPageFetchError, match=message):
                fetch_attachment_pages(
                    list(documents),
                    journal=journal,
                    broker=DirectCourtListenerRecapFetchPurchaseBroker(
                        _config(), transport=_FakeTransport([])
                    ),
                    metadata_client=_FakeMetadataClient(),
                    queue_reader=RecapFetchQueueReader(
                        transport=_FakeTransport([]), api_token="courtlistener-secret"
                    ),
                    cycle_id="cycle-1-attachment-menus",
                    authorization_sha256=authorization,
                    max_total_usd=ceiling,
                    clock=_clock,
                )


def _client_code(operation_key: str | None) -> str:
    assert operation_key is not None
    return recap_fetch_client_code(operation_key)


def test_cli_surface_requires_the_explicit_fee_acknowledgment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = argparse.ArgumentParser()
    register_cli(parser.add_subparsers(dest="command"))
    argv = [
        "fetch-recap-attachment-pages",
        "--recap-document",
        _MAIN_DOCUMENT,
        "--journal",
        str(tmp_path / "menus.sqlite3"),
        "--cycle-id",
        "cycle-1-attachment-menus",
        "--authorization-sha256",
        _AUTHORIZATION_SHA256,
        "--max-total-usd",
        "75.00",
    ]
    parsed = parser.parse_args(argv)

    assert parsed.recap_documents == [_MAIN_DOCUMENT]
    with pytest.raises(SystemExit, match="requires --live"):
        run_cli(parsed)
    with pytest.raises(SystemExit, match="requires --live"):
        run_cli(parser.parse_args([*argv, "--live"]))
    assert capsys.readouterr().out == ""
