from __future__ import annotations

from typing import Any

import pytest
from legalforecast.ingestion.attachment_page import (
    AttachmentPageAuthorizationError,
    AttachmentPageFetchPlan,
    build_attachment_page_fetch_plan,
    ceiling_upper_bound_usd,
    execute_attachment_page_fetches,
    record_attachment_page_authorization,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    DirectCourtListenerRecapFetchConfig,
    RecapFetchHTTPResponse,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_NUMBER,
    MAIN_DOCUMENT_ID,
    attachment_document,
    client_for,
    docket_entries_response,
    main_document,
    recap_documents_response,
    recap_fetch_response,
)

RECORDED_AT = "2026-08-17T21:00:00Z"
QUEUE_ID = 5150

CONFIG = DirectCourtListenerRecapFetchConfig(
    api_token="token",
    pacer_username="user",
    pacer_password="secret",
)


class _RecordingTransport:
    """Record every charge-bearing POST and reply from a script."""

    def __init__(self, responses: list[RecapFetchHTTPResponse | Exception]) -> None:
        self._responses = list(responses)
        self.posts: list[dict[str, str]] = []

    def request(
        self,
        *,
        method: str,
        path: str,
        form: Any,
        headers: Any,
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse:
        del headers, timeout_seconds
        assert method == "POST"
        assert path == "/recap-fetch/"
        self.posts.append(dict(form))
        if not self._responses:
            raise AssertionError("transport received an unscripted POST")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _dispatch_accepted(queue_id: int = QUEUE_ID) -> RecapFetchHTTPResponse:
    return RecapFetchHTTPResponse(
        status_code=201, payload={"id": queue_id, "status": 1, "message": ""}
    )


def _plan_for(
    client: Any, *, plan_id: str = "cycle-1-attachment-menus-test"
) -> AttachmentPageFetchPlan:
    return build_attachment_page_fetch_plan(
        plan_id=plan_id,
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=client,
        per_menu_ceiling_usd="0.10",
    )


def _authorized(plan: AttachmentPageFetchPlan) -> Any:
    return record_attachment_page_authorization(
        plan=plan,
        typed_confirmation=plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc=RECORDED_AT,
    )


def _plan_only_client() -> Any:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    return client


def test_a_completed_fetch_that_creates_rows_is_recorded_as_fetched() -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=2, message="ok"),
            recap_documents_response(
                documents=[
                    main_document(),
                    attachment_document(document_id=9001, attachment_number=1),
                ]
            ),
        ]
    )
    transport = _RecordingTransport([_dispatch_accepted()])

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        sleep=lambda _: None,
    )

    assert receipt.recap_fetch_post_count == 1
    assert len(transport.posts) == 1
    assert transport.posts[0]["request_type"] == "3"
    assert transport.posts[0]["recap_document"] == str(MAIN_DOCUMENT_ID)
    assert transport.posts[0]["pacer_username"] == "user"
    outcome = receipt.outcomes[0]
    assert outcome.disposition == "fetched"
    assert outcome.charge_dispatched is True
    assert [item.attachment_number for item in outcome.attachments] == ["1"]
    assert receipt.halted_reason is None
    assert ceiling_upper_bound_usd(plan, receipt) == "0.10"


def test_a_menu_ingested_between_signing_and_dispatch_costs_nothing() -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(
                documents=[
                    main_document(),
                    attachment_document(document_id=9001, attachment_number=1),
                ]
            ),
        ]
    )
    transport = _RecordingTransport([])

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        sleep=lambda _: None,
    )

    assert transport.posts == []
    assert receipt.recap_fetch_post_count == 0
    assert receipt.outcomes[0].disposition == "already_ingested"
    assert receipt.outcomes[0].charge_dispatched is False
    assert ceiling_upper_bound_usd(plan, receipt) == "0.00"


def test_a_completed_fetch_that_creates_no_rows_is_a_failure_not_a_success() -> None:
    """The documented behaviour is not assumed; it is checked per row."""

    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=2, message="ok"),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    transport = _RecordingTransport([_dispatch_accepted()])

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        sleep=lambda _: None,
    )

    outcome = receipt.outcomes[0]
    assert outcome.disposition == "failed"
    assert outcome.charge_dispatched is True
    assert "created no attachment rows" in outcome.message


def test_a_terminal_provider_failure_is_recorded_and_never_retried() -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=3, message="PACER refused"),
        ]
    )
    transport = _RecordingTransport([_dispatch_accepted()])

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        sleep=lambda _: None,
    )

    assert len(transport.posts) == 1
    outcome = receipt.outcomes[0]
    assert outcome.disposition == "failed"
    assert outcome.status == 3
    assert outcome.message == "PACER refused"


def test_a_fetch_that_never_settles_halts_and_leaves_later_targets_untouched() -> None:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
            docket_entries_response(docket_id="71280017", entry_number=9, entry_id=555),
            recap_documents_response(documents=[main_document()], entry_id=555),
        ]
    )
    plan = build_attachment_page_fetch_plan(
        plan_id="cycle-1-attachment-menus-test",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER), ("71280017", 9)],
        client=client,
        per_menu_ceiling_usd="0.10",
    )
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=1),
            recap_fetch_response(queue_id=QUEUE_ID, status=4),
        ]
    )
    transport = _RecordingTransport([_dispatch_accepted()])
    waits: list[float] = []

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        poll_attempts=2,
        poll_backoff_seconds=20.0,
        sleep=waits.append,
    )

    assert len(transport.posts) == 1
    assert receipt.outcomes[0].disposition == "unknown"
    assert receipt.outcomes[1].disposition == "not_attempted"
    assert receipt.outcomes[1].charge_dispatched is False
    assert receipt.halted_reason is not None
    assert waits == [20.0]


def test_a_dispatch_that_raises_halts_with_the_charge_recorded_as_unknown() -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([TimeoutError("connection reset")])
    cancelled: list[str] = []

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        before_request=lambda method, path: (
            lambda: cancelled.append(f"{method} {path}")
        ),
        sleep=lambda _: None,
    )

    assert receipt.outcomes[0].disposition == "unknown"
    assert receipt.outcomes[0].charge_dispatched is True
    assert receipt.recap_fetch_post_count == 1
    assert "charge state unknown" in (receipt.halted_reason or "")
    assert cancelled == ["POST /recap-fetch/"]


def test_a_rejected_dispatch_halts_without_a_second_charge() -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport(
        [
            RecapFetchHTTPResponse(
                status_code=403, payload={"message": "no PACER access"}
            )
        ]
    )

    receipt = execute_attachment_page_fetches(
        plan=plan,
        authorization=authorization,
        config=CONFIG,
        transport=transport,
        client=execution_client,
        sleep=lambda _: None,
    )

    assert len(transport.posts) == 1
    assert receipt.outcomes[0].disposition == "failed"
    assert receipt.outcomes[0].message == "no PACER access"
    assert receipt.halted_reason is not None


def test_an_authorization_for_a_different_plan_spends_nothing() -> None:
    signed_plan = _plan_for(_plan_only_client(), plan_id="cycle-1-attachment-menus-old")
    current_plan = _plan_for(
        _plan_only_client(), plan_id="cycle-1-attachment-menus-new"
    )
    transport = _RecordingTransport([_dispatch_accepted()])
    execution_client, _ = client_for([])

    with pytest.raises(AttachmentPageAuthorizationError):
        execute_attachment_page_fetches(
            plan=current_plan,
            authorization=_authorized(signed_plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            sleep=lambda _: None,
        )

    assert transport.posts == []
