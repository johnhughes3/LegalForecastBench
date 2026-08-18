from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.attachment_page import (
    INTENDED,
    AttachmentPageAuthorizationError,
    AttachmentPageFetchPlan,
    build_attachment_page_fetch_plan,
    ceiling_upper_bound_usd,
    execute_attachment_page_fetches,
    record_attachment_page_authorization,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.courtlistener_recap_fetch import (
    DirectCourtListenerRecapFetchConfig,
    RecapFetchHTTPResponse,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudgetExhausted,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_ID,
    ENTRY_NUMBER,
    MAIN_DOCUMENT_ID,
    BudgetTrippingClient,
    attachment_document,
    client_for,
    docket_entries_response,
    journal_at,
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

    def __init__(
        self,
        responses: list[RecapFetchHTTPResponse | Exception],
        *,
        on_post: Any = None,
    ) -> None:
        self._responses = list(responses)
        self._on_post = on_post
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
        # Runs while the charge is in flight, which is the only moment at which
        # "was the intent durable before the money moved?" is answerable.
        if self._on_post is not None:
            self._on_post()
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


def _journal(tmp_path: Path) -> Any:
    return journal_at(tmp_path / "journal.sqlite3")


def test_a_completed_fetch_that_creates_rows_is_recorded_as_fetched(
    tmp_path: Path,
) -> None:
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

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )
        row = journal.dispatched(plan.plan_sha256, str(ENTRY_ID))

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
    assert row is not None
    assert row.disposition == "fetched"
    assert row.queue_id == str(QUEUE_ID)


def test_the_intent_is_durable_before_the_charge_is_dispatched(tmp_path: Path) -> None:
    """The point of the journal: the row is committed while the POST is live."""

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
    observed: list[Any] = []

    def _read_through_a_second_connection() -> None:
        # A separate connection proves the row is committed to disk rather than
        # merely staged inside the writer's open transaction.
        with _journal(tmp_path) as reader:
            observed.append(reader.dispatched(plan.plan_sha256, str(ENTRY_ID)))

    transport = _RecordingTransport(
        [_dispatch_accepted()], on_post=_read_through_a_second_connection
    )

    with _journal(tmp_path) as journal:
        execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert len(observed) == 1
    row = observed[0]
    assert row is not None, "the charge dispatched with no durable record of intent"
    assert row.disposition == INTENDED
    assert row.resolved is False
    assert row.main_source_document_id == str(MAIN_DOCUMENT_ID)


def test_a_menu_ingested_between_signing_and_dispatch_costs_nothing(
    tmp_path: Path,
) -> None:
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
    consumed: list[str] = []

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_first_dispatch=lambda: consumed.append("consumed"),
            sleep=lambda _: None,
        )
        assert journal.dispatched_count(plan.plan_sha256) == 0

    assert transport.posts == []
    assert receipt.recap_fetch_post_count == 0
    assert receipt.outcomes[0].disposition == "already_ingested"
    assert receipt.outcomes[0].charge_dispatched is False
    assert ceiling_upper_bound_usd(plan, receipt) == "0.00"
    # A run that spends nothing must not burn the owner's signature.
    assert consumed == []


def test_the_authorization_is_consumed_once_before_the_first_charge(
    tmp_path: Path,
) -> None:
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
            recap_fetch_response(queue_id=QUEUE_ID, status=2, message="ok"),
            recap_documents_response(
                documents=[
                    main_document(),
                    attachment_document(document_id=9001, attachment_number=1),
                ]
            ),
            recap_documents_response(documents=[main_document()], entry_id=555),
            recap_fetch_response(queue_id=6161, status=2, message="ok"),
            recap_documents_response(
                documents=[
                    main_document(entry_id=555),
                    attachment_document(
                        document_id=9002, attachment_number=1, entry_id=555
                    ),
                ],
                entry_id=555,
            ),
        ]
    )
    events: list[str] = []
    transport = _RecordingTransport(
        [_dispatch_accepted(), _dispatch_accepted(queue_id=6161)],
        on_post=lambda: events.append("post"),
    )

    with _journal(tmp_path) as journal:
        execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_first_dispatch=lambda: events.append("consume"),
            sleep=lambda _: None,
        )

    assert len(transport.posts) == 2
    assert events == ["consume", "post", "post"]


def test_a_completed_fetch_that_creates_no_rows_is_a_failure_not_a_success(
    tmp_path: Path,
) -> None:
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

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    outcome = receipt.outcomes[0]
    assert outcome.disposition == "failed"
    assert outcome.charge_dispatched is True
    assert "created no attachment rows" in outcome.message


def test_a_terminal_provider_failure_is_recorded_and_never_retried(
    tmp_path: Path,
) -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=3, message="PACER refused"),
        ]
    )
    transport = _RecordingTransport([_dispatch_accepted()])

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert len(transport.posts) == 1
    outcome = receipt.outcomes[0]
    assert outcome.disposition == "failed"
    assert outcome.status == 3
    assert outcome.message == "PACER refused"


def test_a_failed_menu_is_not_recharged_by_a_later_run(tmp_path: Path) -> None:
    """The re-charge guard end to end: run once with a failure, run again."""

    plan = _plan_for(_plan_only_client())
    first_client, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=3, message="PACER refused"),
        ]
    )
    first_transport = _RecordingTransport([_dispatch_accepted()])
    with _journal(tmp_path) as journal:
        first = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=first_transport,
            client=first_client,
            journal=journal,
            sleep=lambda _: None,
        )
    assert first.outcomes[0].disposition == "failed"
    assert len(first_transport.posts) == 1

    # A failed fetch creates no attachment rows, so nothing but the journal
    # stands between the rerun and a second charge for the same entry.
    second_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    second_transport = _RecordingTransport([])
    with _journal(tmp_path) as journal:
        second = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=second_transport,
            client=second_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert second_transport.posts == []
    assert second.recap_fetch_post_count == 0
    outcome = second.outcomes[0]
    assert outcome.disposition == "already_dispatched"
    assert outcome.charge_dispatched is False
    assert "refusing a second charge" in outcome.message


def test_a_charge_left_unresolved_by_a_crash_is_not_recharged(tmp_path: Path) -> None:
    """A row still at ``intended`` may already have been billed; refuse it."""

    plan = _plan_for(_plan_only_client())
    with _journal(tmp_path) as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])

    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([])
    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert transport.posts == []
    assert receipt.outcomes[0].disposition == "already_dispatched"
    assert INTENDED in receipt.outcomes[0].message


def test_a_fetch_that_never_settles_halts_and_leaves_later_targets_untouched(
    tmp_path: Path,
) -> None:
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

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
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


def test_a_dispatch_that_raises_halts_with_the_charge_recorded_as_unknown(
    tmp_path: Path,
) -> None:
    plan = _plan_for(_plan_only_client())
    authorization = _authorized(plan)
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([TimeoutError("connection reset")])
    cancelled: list[str] = []

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_request=lambda method, path: (
                lambda: cancelled.append(f"{method} {path}")
            ),
            sleep=lambda _: None,
        )
        row = journal.dispatched(plan.plan_sha256, str(ENTRY_ID))

    assert receipt.outcomes[0].disposition == "unknown"
    assert receipt.outcomes[0].charge_dispatched is True
    assert receipt.recap_fetch_post_count == 1
    assert "charge state unknown" in (receipt.halted_reason or "")
    assert cancelled == ["POST /recap-fetch/"]
    assert row is not None and row.disposition == "unknown"


def test_a_rejected_dispatch_halts_without_a_second_charge(tmp_path: Path) -> None:
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

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert len(transport.posts) == 1
    assert receipt.outcomes[0].disposition == "failed"
    assert receipt.outcomes[0].message == "no PACER access"
    assert receipt.halted_reason is not None


def test_an_authorization_for_a_different_plan_spends_nothing(tmp_path: Path) -> None:
    signed_plan = _plan_for(_plan_only_client(), plan_id="cycle-1-attachment-menus-old")
    current_plan = _plan_for(
        _plan_only_client(), plan_id="cycle-1-attachment-menus-new"
    )
    transport = _RecordingTransport([_dispatch_accepted()])
    execution_client, _ = client_for([])

    with _journal(tmp_path) as journal:
        with pytest.raises(AttachmentPageAuthorizationError):
            execute_attachment_page_fetches(
                plan=current_plan,
                authorization=_authorized(signed_plan),
                config=CONFIG,
                transport=transport,
                client=execution_client,
                journal=journal,
                sleep=lambda _: None,
            )

    assert transport.posts == []


def test_a_budget_refusal_before_dispatch_returns_a_receipt_and_spends_nothing(
    tmp_path: Path,
) -> None:
    """Budget exhaustion is a sibling exception; it must not escape the loop."""

    plan = _plan_for(_plan_only_client())
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([])
    consumed: list[str] = []

    def _exhausted(method: str, path: str) -> Any:
        del method, path
        raise CourtListenerRequestBudgetExhausted("rolling minute exhausted")

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_request=_exhausted,
            before_first_dispatch=lambda: consumed.append("consumed"),
            sleep=lambda _: None,
        )
        # Nothing was transmitted, so nothing may block a later attempt.
        assert journal.dispatched_count(plan.plan_sha256) == 0

    assert transport.posts == []
    assert receipt.recap_fetch_post_count == 0
    assert receipt.outcomes[0].disposition == "not_attempted"
    assert receipt.outcomes[0].charge_dispatched is False
    assert "request budget refused" in (receipt.halted_reason or "")
    assert consumed == []


def test_a_budget_refusal_during_pre_dispatch_verification_returns_a_receipt(
    tmp_path: Path,
) -> None:
    plan = _plan_for(_plan_only_client())
    inner, _ = client_for([recap_documents_response(documents=[main_document()])])
    execution_client = cast(
        CourtListenerClient, BudgetTrippingClient(inner, fail_on="iter_recap_documents")
    )
    transport = _RecordingTransport([])

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )

    assert transport.posts == []
    assert receipt.outcomes[0].disposition == "not_attempted"
    assert receipt.outcomes[0].charge_dispatched is False
    assert "pre-dispatch verification failed" in (receipt.halted_reason or "")


def test_a_budget_refusal_while_polling_leaves_the_charge_journaled_as_unknown(
    tmp_path: Path,
) -> None:
    plan = _plan_for(_plan_only_client())
    inner, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=1),
        ]
    )
    execution_client = cast(
        CourtListenerClient, BudgetTrippingClient(inner, fail_on="get_recap_fetch")
    )
    transport = _RecordingTransport([_dispatch_accepted()])
    waits: list[float] = []

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            poll_attempts=4,
            sleep=waits.append,
        )
        row = journal.dispatched(plan.plan_sha256, str(ENTRY_ID))

    assert len(transport.posts) == 1
    assert receipt.outcomes[0].disposition == "unknown"
    assert receipt.outcomes[0].charge_dispatched is True
    # Polling stops rather than burning every remaining attempt and its backoff
    # on a budget that cannot clear inside this run.
    assert waits == []
    assert row is not None and row.disposition == "unknown"


def test_a_budget_refusal_after_a_completed_fetch_still_returns_a_receipt(
    tmp_path: Path,
) -> None:
    plan = _plan_for(_plan_only_client())
    inner, _ = client_for(
        [
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=2, message="ok"),
        ]
    )
    execution_client = cast(
        CourtListenerClient,
        BudgetTrippingClient(inner, fail_on="iter_recap_documents", after=1),
    )
    transport = _RecordingTransport([_dispatch_accepted()])

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            sleep=lambda _: None,
        )
        row = journal.dispatched(plan.plan_sha256, str(ENTRY_ID))

    assert receipt.outcomes[0].disposition == "unknown"
    assert receipt.outcomes[0].charge_dispatched is True
    assert "post-dispatch verification failed" in (receipt.halted_reason or "")
    assert row is not None and row.disposition == "unknown"


def test_a_journal_that_cannot_record_the_intent_dispatches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_for(_plan_only_client())
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([])

    cancelled: list[str] = []

    def _unwritable(**kwargs: Any) -> Any:
        del kwargs
        raise OSError("read-only file system")

    with _journal(tmp_path) as journal:
        monkeypatch.setattr(journal, "record_intent", _unwritable)
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_request=lambda method, path: (
                lambda: cancelled.append(f"{method} {path}")
            ),
            sleep=lambda _: None,
        )

    assert transport.posts == []
    assert receipt.outcomes[0].disposition == "not_attempted"
    assert "pre-dispatch journal write failed" in (receipt.halted_reason or "")
    # Nothing was transmitted, so the reserved slot goes back to the budget
    # rather than being spent against the rolling ceiling for no request.
    assert cancelled == ["POST /recap-fetch/"]


def test_an_ambiguous_dispatch_still_leaves_a_durable_journal_row(
    tmp_path: Path,
) -> None:
    """The charge state is unknown; the record of having tried is not."""

    plan = _plan_for(_plan_only_client())
    execution_client, _ = client_for(
        [recap_documents_response(documents=[main_document()])]
    )
    transport = _RecordingTransport([TimeoutError("connection reset")])
    cancelled: list[str] = []

    with _journal(tmp_path) as journal:
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=_authorized(plan),
            config=CONFIG,
            transport=transport,
            client=execution_client,
            journal=journal,
            before_request=lambda method, path: (
                lambda: cancelled.append(f"{method} {path}")
            ),
            sleep=lambda _: None,
        )

    assert receipt.outcomes[0].charge_dispatched is True
    assert (
        journal_at(tmp_path / "journal.sqlite3").dispatched_count(plan.plan_sha256) == 1
    )
