"""Shared fixtures for the attachment-menu acquisition tests."""

from __future__ import annotations

from typing import Any

from legalforecast.ingestion.attachment_page import AttachmentPageDispatchJournal
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudgetExhausted,
)

DOCKET_ID = "70308595"
ENTRY_NUMBER = 8
ENTRY_ID = 429596666
MAIN_DOCUMENT_ID = 443855896
MAIN_PACER_DOC_ID = "19105207438"


def entry_uri(docket_entry_id: int) -> str:
    return (
        f"https://www.courtlistener.com/api/rest/v4/docket-entries/{docket_entry_id}/"
    )


def response(
    *,
    method: str = "GET",
    path: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any],
    status_code: int = 200,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method=method,
        path=path,
        params={} if params is None else params,
        status_code=status_code,
        payload=payload,
    )


def docket_entries_response(
    *,
    docket_id: str = DOCKET_ID,
    entry_number: int = ENTRY_NUMBER,
    entry_id: int = ENTRY_ID,
    description: str = "MOTION to Dismiss (Attachments: # 1 Memorandum in Support)",
) -> RecordedCourtListenerResponse:
    return response(
        path="/docket-entries/",
        params={"docket": docket_id, "page_size": 100},
        payload={
            "results": [
                {
                    "id": entry_id,
                    "docket": int(docket_id),
                    "entry_number": entry_number,
                    "description": description,
                }
            ],
            "next": None,
        },
    )


def main_document(
    *,
    document_id: int = MAIN_DOCUMENT_ID,
    entry_id: int = ENTRY_ID,
    pacer_doc_id: str = MAIN_PACER_DOC_ID,
) -> dict[str, Any]:
    return {
        "id": document_id,
        "docket_entry": entry_uri(entry_id),
        "document_number": "8",
        "attachment_number": None,
        "document_type": 1,
        "description": "Dismiss",
        "pacer_doc_id": pacer_doc_id,
        "is_available": True,
    }


def attachment_document(
    *,
    document_id: int,
    attachment_number: int,
    entry_id: int = ENTRY_ID,
    description: str = "Memorandum in Support",
    is_available: bool = False,
) -> dict[str, Any]:
    return {
        "id": document_id,
        "docket_entry": entry_uri(entry_id),
        "document_number": "8",
        "attachment_number": attachment_number,
        "document_type": 2,
        "description": description,
        "pacer_doc_id": f"1910520743{attachment_number}",
        "is_available": is_available,
    }


def recap_documents_response(
    *,
    documents: list[dict[str, Any]],
    entry_id: int = ENTRY_ID,
) -> RecordedCourtListenerResponse:
    return response(
        path="/recap-documents/",
        params={"docket_entry": str(entry_id), "page_size": 100},
        payload={"results": documents, "next": None},
    )


def recap_fetch_response(
    *,
    queue_id: int,
    status: int,
    message: str = "",
) -> RecordedCourtListenerResponse:
    return response(
        path=f"/recap-fetch/{queue_id}/",
        payload={"id": queue_id, "status": status, "message": message},
    )


def client_for(
    responses: list[RecordedCourtListenerResponse],
) -> tuple[CourtListenerClient, CourtListenerFixtureTransport]:
    transport = CourtListenerFixtureTransport(tuple(responses))
    return (
        CourtListenerClient(config=CourtListenerConfig(), transport=transport),
        transport,
    )


def journal_at(path: Any) -> AttachmentPageDispatchJournal:
    """Open a dispatch journal for a test, under the test's own tmp_path."""

    return AttachmentPageDispatchJournal(path)


class BudgetTrippingClient:
    """Delegate to a fixture client until a named call must exhaust the budget.

    The request budget refuses through ``CourtListenerRequestBudgetError``,
    which is a sibling of the client's error rather than a subclass, so a
    handler that catches only the client's lets this escape. These tests
    inject it at each point on the charge-bearing path.
    """

    def __init__(
        self,
        client: CourtListenerClient,
        *,
        fail_on: str,
        after: int = 0,
        message: str = "rolling day exhausted",
    ) -> None:
        self._client = client
        self._fail_on = fail_on
        self._after = after
        self._message = message
        self.calls: dict[str, int] = {}

    def _count(self, name: str) -> bool:
        seen = self.calls.get(name, 0)
        self.calls[name] = seen + 1
        return name == self._fail_on and seen >= self._after

    def iter_recap_documents(self, docket_entry_id: str, **kwargs: Any) -> Any:
        if self._count("iter_recap_documents"):
            raise CourtListenerRequestBudgetExhausted(self._message)
        return self._client.iter_recap_documents(docket_entry_id, **kwargs)

    def get_recap_fetch(self, queue_id: str) -> Any:
        if self._count("get_recap_fetch"):
            raise CourtListenerRequestBudgetExhausted(self._message)
        return self._client.get_recap_fetch(queue_id)
