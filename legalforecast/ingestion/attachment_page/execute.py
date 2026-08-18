"""Fail-closed execution of one authorized attachment-menu fetch plan.

Every charge here is bounded by a plan an owner signed by digest. The executor
will not fetch a menu the plan does not name, will not fetch one twice, and
will not retry a charge-bearing POST -- a failed menu is a recorded outcome
that needs fresh authorization, never a silent second charge.

One assumption is deliberately not trusted. CourtListener's documentation says
attachment pages are fetched "same as PDFs, but with request_type set to 3",
and the observable evidence agrees: entries whose menus were ingested carry
attachment rows with descriptions and page counts but ``is_available: false``,
data obtainable only from parsing a menu rather than buying the documents.
That is strong but circumstantial, so a completed fetch that produces no
attachment rows is recorded as a failure rather than a success.

Two properties make those promises durable rather than merely intended. Every
charge is written to the dispatch journal *before* it is dispatched and updated
with its disposition afterwards, so a crash cannot leave money spent with
nothing on disk to say so; and every provider failure is handled here, so this
function returns a receipt rather than raising once a charge is possible. The
only refusal that still raises is an authorization that does not bind this
plan, which is settled before anything can be spent.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from legalforecast.contracts import ATTACHMENT_PAGE_FETCH_RECEIPT_V1
from legalforecast.ingestion.attachment_page.authorization import (
    AttachmentPageAuthorization,
    verify_authorization_binds_plan,
)
from legalforecast.ingestion.attachment_page.journal import (
    AttachmentPageDispatchJournal,
    AttachmentPageJournalError,
)
from legalforecast.ingestion.attachment_page.plan import (
    ATTACHMENT_PAGE_REQUEST_TYPE,
    AttachmentPageFetchPlan,
    AttachmentPageTarget,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerClientError,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    DirectCourtListenerRecapFetchConfig,
    RecapFetchTransport,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudgetError,
)

RECEIPT_SCHEMA_VERSION: Final = str(ATTACHMENT_PAGE_FETCH_RECEIPT_V1)
_FETCH_PATH: Final = "/recap-fetch/"
_TERMINAL_SUCCESS: Final = 2
_TERMINAL_FAILURES: Final = frozenset({3, 6, 7})
_IN_FLIGHT: Final = frozenset({1, 4, 5})

# A rolling request budget refuses through its own exception tree, which is a
# sibling of the client's rather than a subclass of it. Catching only one lets
# the other escape mid-run -- the failure that loses a charge-bearing receipt.
_PROVIDER_ERRORS: Final = (CourtListenerClientError, CourtListenerRequestBudgetError)
_JOURNAL_ERRORS: Final = (AttachmentPageJournalError, OSError)


class AttachmentPageExecutionError(RuntimeError):
    """Raised when execution cannot proceed safely."""


class AttachmentPageOutcomeUnknown(AttachmentPageExecutionError):
    """Raised when a dispatched charge has no durable observed disposition."""


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    source_document_id: str
    attachment_number: str
    description: str
    is_available: bool | None

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "attachment_number": self.attachment_number,
            "description": self.description,
            "is_available": self.is_available,
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageOutcome:
    candidate_id: str
    docket_entry_number: int
    docket_entry_id: str
    main_source_document_id: str
    disposition: str
    charge_dispatched: bool
    queue_id: str | None
    status: int | None
    message: str
    attachments: tuple[ResolvedAttachment, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "docket_entry_number": self.docket_entry_number,
            "docket_entry_id": self.docket_entry_id,
            "main_source_document_id": self.main_source_document_id,
            "disposition": self.disposition,
            "charge_dispatched": self.charge_dispatched,
            "queue_id": self.queue_id,
            "status": self.status,
            "message": self.message,
            "attachment_count": len(self.attachments),
            "attachments": [item.to_record() for item in self.attachments],
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageFetchReceipt:
    plan_id: str
    plan_sha256: str
    outcomes: tuple[AttachmentPageOutcome, ...]
    recap_fetch_post_count: int
    halted_reason: str | None

    def to_record(self) -> dict[str, Any]:
        charged = sum(1 for outcome in self.outcomes if outcome.charge_dispatched)
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "request_type": ATTACHMENT_PAGE_REQUEST_TYPE,
            "recap_fetch_post_count": self.recap_fetch_post_count,
            "charge_dispatched_count": charged,
            "resolved_entry_count": sum(
                1 for outcome in self.outcomes if outcome.attachments
            ),
            "halted_reason": self.halted_reason,
            "outcomes": [outcome.to_record() for outcome in self.outcomes],
        }


def _resolved(documents: Sequence[Any]) -> tuple[ResolvedAttachment, ...]:
    return tuple(
        ResolvedAttachment(
            source_document_id=str(document.document_id),
            attachment_number=str(document.attachment_number),
            description=str(document.description or ""),
            is_available=document.is_available,
        )
        for document in documents
        if document.attachment_number is not None
    )


def _list_attachments(
    client: CourtListenerClient, docket_entry_id: str
) -> tuple[ResolvedAttachment, ...]:
    return _resolved(tuple(client.iter_recap_documents(docket_entry_id, page_size=100)))


def _queue_id(payload: Mapping[str, object]) -> str:
    identifier = payload.get("id")
    if isinstance(identifier, int) and identifier > 0:
        return str(identifier)
    if isinstance(identifier, str) and identifier.strip().isdigit():
        return identifier.strip()
    raise AttachmentPageOutcomeUnknown(
        "attachment-menu dispatch returned no usable queue identifier"
    )


def _status(payload: Mapping[str, object]) -> int | None:
    value = payload.get("status")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _message(payload: Mapping[str, object]) -> str:
    value = payload.get("message")
    return value if isinstance(value, str) else ""


def execute_attachment_page_fetches(
    *,
    plan: AttachmentPageFetchPlan,
    authorization: AttachmentPageAuthorization,
    config: DirectCourtListenerRecapFetchConfig,
    transport: RecapFetchTransport,
    client: CourtListenerClient,
    journal: AttachmentPageDispatchJournal,
    before_request: Callable[[str, str], Callable[[], None] | None] | None = None,
    before_first_dispatch: Callable[[], None] | None = None,
    poll_attempts: int = 6,
    poll_backoff_seconds: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
) -> AttachmentPageFetchReceipt:
    """Fetch exactly the menus this authorized plan names, once each.

    ``journal`` is required, not optional: it is the durable record written
    before each charge, and without it a charge can exist with nothing on disk
    that says so. ``before_first_dispatch`` runs once, immediately before the
    first charge-bearing POST, and is how the caller consumes the single-use
    authorization -- consuming it any earlier would burn an owner decision on a
    run that turns out to spend nothing.
    """

    verify_authorization_binds_plan(authorization=authorization, plan=plan)
    if poll_attempts < 1:
        raise AttachmentPageExecutionError("poll_attempts must be at least one")

    outcomes: list[AttachmentPageOutcome] = []
    posts = 0
    halted: str | None = None
    consumed = before_first_dispatch is None

    for target in plan.targets:
        if halted is not None:
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message="execution halted before this target",
                )
            )
            continue

        # Time-of-check: a menu ingested since the plan was signed is free.
        try:
            existing = _list_attachments(client, target.docket_entry_id)
        except _PROVIDER_ERRORS as exc:
            halted = f"pre-dispatch verification failed: {exc}"
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message=str(exc),
                )
            )
            continue
        if existing:
            outcomes.append(
                _outcome(
                    target,
                    disposition="already_ingested",
                    charge_dispatched=False,
                    message="attachment rows existed before dispatch; no charge",
                    attachments=existing,
                )
            )
            continue

        # Single use: a durable row means a charge for this entry was already
        # dispatched under this plan, whatever became of it.
        try:
            prior = journal.dispatched(plan.plan_sha256, target.docket_entry_id)
        except _JOURNAL_ERRORS as exc:
            halted = f"dispatch journal is unreadable: {exc}"
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message=str(exc),
                )
            )
            continue
        if prior is not None:
            outcomes.append(
                _outcome(
                    target,
                    disposition="already_dispatched",
                    charge_dispatched=False,
                    queue_id=prior.queue_id,
                    status=prior.status,
                    message=(
                        "a charge for this entry was already dispatched under this "
                        f"plan and journaled as {prior.disposition}; refusing a "
                        "second charge"
                    ),
                )
            )
            continue

        if posts >= len(plan.targets):
            halted = "dispatch count reached the authorized menu count"
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message=halted,
                )
            )
            continue

        # Reserve the rate-limit slot first: a budget refusal is the one
        # failure that provably costs nothing, so it must land before the two
        # durable writes below rather than after them.
        try:
            cancel = before_request("POST", _FETCH_PATH) if before_request else None
        except CourtListenerRequestBudgetError as exc:
            halted = f"request budget refused the dispatch: {exc}"
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message=str(exc),
                )
            )
            continue

        # Consume the authorization, then journal the intent. Both are durable
        # and both precede the POST: if the journal write fails the owner
        # re-signs, but once it succeeds no rerun can charge this entry again.
        if not consumed and before_first_dispatch is not None:
            try:
                before_first_dispatch()
            except Exception as exc:  # broad on purpose: reported, never swallowed
                _release(cancel)
                halted = f"could not consume the authorization before spending: {exc}"
                outcomes.append(
                    _outcome(
                        target,
                        disposition="not_attempted",
                        charge_dispatched=False,
                        message=str(exc),
                    )
                )
                continue
            consumed = True
        try:
            journal.record_intent(plan=plan, target=target)
        except _JOURNAL_ERRORS as exc:
            # Nothing was transmitted, so the reserved slot is genuinely unused
            # and belongs back in the rolling budget.
            _release(cancel)
            halted = f"pre-dispatch journal write failed: {exc}"
            outcomes.append(
                _outcome(
                    target,
                    disposition="not_attempted",
                    charge_dispatched=False,
                    message=str(exc),
                )
            )
            continue

        posts += 1
        outcome, dispatch_halt = _dispatch_one(
            target,
            config=config,
            transport=transport,
            client=client,
            cancel=cancel,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
            sleep=sleep,
        )
        outcomes.append(outcome)
        # The disposition is journaled on every path, including a halting one:
        # short-circuiting past it would leave the charge durably recorded but
        # permanently unresolved.
        journal_halt = _record(journal, plan, outcome)
        halted = dispatch_halt or journal_halt

    return AttachmentPageFetchReceipt(
        plan_id=plan.plan_id,
        plan_sha256=plan.plan_sha256,
        outcomes=tuple(outcomes),
        recap_fetch_post_count=posts,
        halted_reason=halted,
    )


def _release(cancel: Callable[[], None] | None) -> None:
    """Return an unused reservation to the budget, if it is cancellable.

    Only called where nothing was transmitted -- a pre-dispatch write that
    failed before the POST. Note that the production wiring passes
    ``budget.before_request``, which reserves without returning a canceller,
    so this is a no-op there; it matters to a caller that supplies
    ``reserve_cancellable``.
    """

    if cancel is not None:
        cancel()


def _record(
    journal: AttachmentPageDispatchJournal,
    plan: AttachmentPageFetchPlan,
    outcome: AttachmentPageOutcome,
) -> str | None:
    """Update the durable row for one dispatched charge, or say why not.

    A failure here is not a lost charge -- the pre-dispatch row survives and
    still refuses a second one. It is a lost *disposition*, which is worth
    halting the run over.
    """

    try:
        journal.record_disposition(
            plan_sha256=plan.plan_sha256,
            docket_entry_id=outcome.docket_entry_id,
            disposition=outcome.disposition,
            queue_id=outcome.queue_id,
            status=outcome.status,
            message=outcome.message,
        )
    except _JOURNAL_ERRORS as exc:
        return (
            "a dispatched charge could not be journaled with its disposition; "
            f"its pre-dispatch row remains the durable record: {exc}"
        )
    return None


def _dispatch_one(
    target: AttachmentPageTarget,
    *,
    config: DirectCourtListenerRecapFetchConfig,
    transport: RecapFetchTransport,
    client: CourtListenerClient,
    cancel: Callable[[], None] | None,
    poll_attempts: int,
    poll_backoff_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[AttachmentPageOutcome, str | None]:
    """Dispatch one charge and resolve it, returning its outcome and any halt."""

    form = {
        "request_type": ATTACHMENT_PAGE_REQUEST_TYPE,
        "pacer_username": config.pacer_username,
        "pacer_password": config.pacer_password,
        "recap_document": target.main_source_document_id,
    }
    headers = {
        "Authorization": f"Token {config.api_token}",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        response = transport.request(
            method="POST",
            path=_FETCH_PATH,
            form=form,
            headers=headers,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:  # broad on purpose: any failure here is charge-unknown
        if cancel is not None:
            # The reservation is released, but the charge state is not
            # knowable from here; halting is the only safe response.
            cancel()
        return (
            _outcome(
                target,
                disposition="unknown",
                charge_dispatched=True,
                message=str(exc),
            ),
            "attachment-menu dispatch raised before a durable response; "
            f"charge state unknown: {exc}",
        )

    if response.status_code >= 400:
        halted = f"attachment-menu dispatch rejected with HTTP {response.status_code}"
        return (
            _outcome(
                target,
                disposition="failed",
                charge_dispatched=True,
                message=_message(response.payload) or halted,
                status=_status(response.payload),
            ),
            halted,
        )

    try:
        queue_id = _queue_id(response.payload)
    except AttachmentPageOutcomeUnknown as exc:
        return (
            _outcome(
                target,
                disposition="unknown",
                charge_dispatched=True,
                message=str(exc),
            ),
            str(exc),
        )

    status, message = _await_terminal_status(
        queue_id=queue_id,
        client=client,
        poll_attempts=poll_attempts,
        poll_backoff_seconds=poll_backoff_seconds,
        sleep=sleep,
    )
    if status != _TERMINAL_SUCCESS:
        terminal = status in _TERMINAL_FAILURES
        return (
            _outcome(
                target,
                disposition="failed" if terminal else "unknown",
                charge_dispatched=True,
                queue_id=queue_id,
                status=status,
                message=message or "attachment-menu fetch did not complete",
            ),
            None
            if terminal
            else (
                "attachment-menu fetch has no terminal disposition; "
                "halting rather than dispatching further charges"
            ),
        )

    # Time-of-use: a completed fetch is only a success if rows appeared.
    try:
        created = _list_attachments(client, target.docket_entry_id)
    except _PROVIDER_ERRORS as exc:
        return (
            _outcome(
                target,
                disposition="unknown",
                charge_dispatched=True,
                queue_id=queue_id,
                status=status,
                message=str(exc),
            ),
            f"post-dispatch verification failed: {exc}",
        )
    if not created:
        return (
            _outcome(
                target,
                disposition="failed",
                charge_dispatched=True,
                queue_id=queue_id,
                status=status,
                message=(
                    "fetch completed but CourtListener created no attachment "
                    "rows for this entry"
                ),
            ),
            None,
        )
    return (
        _outcome(
            target,
            disposition="fetched",
            charge_dispatched=True,
            queue_id=queue_id,
            status=status,
            message=message,
            attachments=created,
        ),
        None,
    )


def _await_terminal_status(
    *,
    queue_id: str,
    client: CourtListenerClient,
    poll_attempts: int,
    poll_backoff_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[int | None, str]:
    """Poll one queued fetch until it settles, without a tight loop."""

    status: int | None = None
    message = ""
    for attempt in range(poll_attempts):
        if attempt:
            sleep(poll_backoff_seconds)
        try:
            payload = client.get_recap_fetch(queue_id)
        except CourtListenerRequestBudgetError as exc:
            # More polling cannot clear an exhausted budget, and swallowing it
            # into the retry would hide the reason the charge stays unresolved.
            return status, str(exc)
        except CourtListenerClientError as exc:
            message = str(exc)
            continue
        status = _status(payload)
        message = _message(payload) or message
        if status == _TERMINAL_SUCCESS or status in _TERMINAL_FAILURES:
            return status, message
        if status is not None and status not in _IN_FLIGHT:
            return status, message
    return status, message


def ceiling_upper_bound_usd(
    plan: AttachmentPageFetchPlan, receipt: AttachmentPageFetchReceipt
) -> str:
    """Return the ceiling-based upper bound on what PACER may bill.

    The RECAP Fetch API does not report the PACER charge, so this is an upper
    bound derived from the authorized per-menu ceiling and the number of
    charge-bearing dispatches -- never a claim about the actual invoice.
    """

    charged = sum(1 for outcome in receipt.outcomes if outcome.charge_dispatched)
    return f"{Decimal(plan.per_menu_ceiling_usd) * charged:.2f}"


def _outcome(
    target: AttachmentPageTarget,
    *,
    disposition: str,
    charge_dispatched: bool,
    message: str,
    queue_id: str | None = None,
    status: int | None = None,
    attachments: tuple[ResolvedAttachment, ...] = (),
) -> AttachmentPageOutcome:
    return AttachmentPageOutcome(
        candidate_id=target.candidate_id,
        docket_entry_number=target.docket_entry_number,
        docket_entry_id=target.docket_entry_id,
        main_source_document_id=target.main_source_document_id,
        disposition=disposition,
        charge_dispatched=charge_dispatched,
        queue_id=queue_id,
        status=status,
        message=message,
        attachments=attachments,
    )
