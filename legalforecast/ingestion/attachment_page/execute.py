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
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from legalforecast.ingestion.attachment_page.authorization import (
    AttachmentPageAuthorization,
    verify_authorization_binds_plan,
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

RECEIPT_SCHEMA_VERSION: Final = "legalforecast.attachment_page_fetch_receipt.v1"
_FETCH_PATH: Final = "/recap-fetch/"
_TERMINAL_SUCCESS: Final = 2
_TERMINAL_FAILURES: Final = frozenset({3, 6, 7})
_IN_FLIGHT: Final = frozenset({1, 4, 5})


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
    before_request: Callable[[str, str], Callable[[], None] | None] | None = None,
    poll_attempts: int = 6,
    poll_backoff_seconds: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
) -> AttachmentPageFetchReceipt:
    """Fetch exactly the menus this authorized plan names, once each."""

    verify_authorization_binds_plan(authorization=authorization, plan=plan)
    if poll_attempts < 1:
        raise AttachmentPageExecutionError("poll_attempts must be at least one")

    outcomes: list[AttachmentPageOutcome] = []
    posts = 0
    halted: str | None = None

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
        except CourtListenerClientError as exc:
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

        cancel = before_request("POST", _FETCH_PATH) if before_request else None
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
        posts += 1
        try:
            response = transport.request(
                method="POST",
                path=_FETCH_PATH,
                form=form,
                headers=headers,
                timeout_seconds=config.timeout_seconds,
            )
        except Exception as exc:
            if cancel is not None:
                # The reservation is released, but the charge state is not
                # knowable from here; halting is the only safe response.
                cancel()
            halted = (
                "attachment-menu dispatch raised before a durable response; "
                f"charge state unknown: {exc}"
            )
            outcomes.append(
                _outcome(
                    target,
                    disposition="unknown",
                    charge_dispatched=True,
                    message=str(exc),
                )
            )
            continue

        if response.status_code >= 400:
            halted = (
                f"attachment-menu dispatch rejected with HTTP {response.status_code}"
            )
            outcomes.append(
                _outcome(
                    target,
                    disposition="failed",
                    charge_dispatched=True,
                    message=_message(response.payload) or halted,
                    status=_status(response.payload),
                )
            )
            continue

        try:
            queue_id = _queue_id(response.payload)
        except AttachmentPageOutcomeUnknown as exc:
            halted = str(exc)
            outcomes.append(
                _outcome(
                    target,
                    disposition="unknown",
                    charge_dispatched=True,
                    message=str(exc),
                )
            )
            continue

        status, message = _await_terminal_status(
            queue_id=queue_id,
            client=client,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
            sleep=sleep,
        )
        if status != _TERMINAL_SUCCESS:
            outcomes.append(
                _outcome(
                    target,
                    disposition="failed" if status in _TERMINAL_FAILURES else "unknown",
                    charge_dispatched=True,
                    queue_id=queue_id,
                    status=status,
                    message=message or "attachment-menu fetch did not complete",
                )
            )
            if status not in _TERMINAL_FAILURES:
                halted = (
                    "attachment-menu fetch has no terminal disposition; "
                    "halting rather than dispatching further charges"
                )
            continue

        # Time-of-use: a completed fetch is only a success if rows appeared.
        try:
            created = _list_attachments(client, target.docket_entry_id)
        except CourtListenerClientError as exc:
            halted = f"post-dispatch verification failed: {exc}"
            outcomes.append(
                _outcome(
                    target,
                    disposition="unknown",
                    charge_dispatched=True,
                    queue_id=queue_id,
                    status=status,
                    message=str(exc),
                )
            )
            continue
        if not created:
            outcomes.append(
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
                )
            )
            continue
        outcomes.append(
            _outcome(
                target,
                disposition="fetched",
                charge_dispatched=True,
                queue_id=queue_id,
                status=status,
                message=message,
                attachments=created,
            )
        )

    return AttachmentPageFetchReceipt(
        plan_id=plan.plan_id,
        plan_sha256=plan.plan_sha256,
        outcomes=tuple(outcomes),
        recap_fetch_post_count=posts,
        halted_reason=halted,
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
