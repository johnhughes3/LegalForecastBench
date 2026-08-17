"""Attachment-page (RECAP Fetch request type 3) menu acquisition.

CourtListener creates attachment-level ``RECAPDocument`` rows only when it has
parsed a docket entry's PACER attachment menu. Where that menu was never
ingested, no authenticated attachment selector exists and no GET can invent
one, so the only supported way to obtain the selector is to buy the menu page.

This module owns that narrow lane: one charge-bearing POST per docket entry,
journalled exactly once, followed by a free listing refresh that reads the
attachment rows the menu created. It deliberately does not reuse the
individual-document purchase client, whose confirmation semantics (document
availability plus a verified download URL) do not apply to a menu page.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    RECAP_ATTACHMENT_PAGE_FETCH_RECEIPT_V1,
    RECAP_ATTACHMENT_SELECTOR_V1,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerRecapDocument
from legalforecast.ingestion.courtlistener_recap_fetch import (
    RECAP_FETCH_PENDING_STATUSES,
    RECAP_FETCH_RETRYABLE_STATUS_CODES,
    RECAP_FETCH_SUCCESS_STATUS,
    RECAP_FETCH_TERMINAL_FAILURE_STATUSES,
    CourtListenerRecapFetchError,
    CourtListenerRecapFetchOutcomeUnknown,
    RecapFetchPurchaseBroker,
    RecapFetchTransport,
    recap_fetch_identifier,
    recap_fetch_queue_id,
    recap_fetch_queue_status,
)
from legalforecast.ingestion.recap_fetch_broker import (
    ATTACHMENT_PAGE_REQUEST_TYPE,
    BrokerDefiniteRejection,
    BrokerOutcomeUnknown,
)

ATTACHMENT_PAGE_FETCH_RECEIPT_SCHEMA = str(RECAP_ATTACHMENT_PAGE_FETCH_RECEIPT_V1)
# Published PACER prices, used only to project what the attachment rows a menu
# revealed would cost to buy. This lane's own spend is bounded by the caller's
# per-menu reservation and aggregate ceiling, not by these values, so they are
# reporting inputs rather than acquisition knobs.
PACER_PAGE_FEE_USD = Decimal("0.10")  # acquisition-config-fence: allow
PACER_DOCUMENT_FEE_CAP_USD = Decimal("3.00")
_MONEY_PLACES = Decimal("0.01")
_SHA256_HEX_LENGTH = 64
# States that prove the paid POST never reached CourtListener, so a later run
# may dispatch again. Every other non-terminal state is deliberately sticky:
# an ambiguous menu POST is resolved by a human reading the PACER statement,
# never by a second charge.
_REDISPATCHABLE_STATES = frozenset({"refused"})


class AttachmentPageFetchError(RuntimeError):
    """Raised when the attachment-menu lane cannot proceed safely."""


class RecapDocumentMetadataClient(Protocol):
    """Free GET surface used to bind and refresh attachment identities."""

    def get_recap_document(self, document_id: str) -> CourtListenerRecapDocument: ...

    def iter_recap_documents(
        self, docket_entry_id: str, *, page_size: int | None = None
    ) -> Iterator[CourtListenerRecapDocument]: ...


@dataclass(frozen=True, slots=True)
class AttachmentSelector:
    """One authenticated attachment row created by a fetched menu."""

    source_document_id: str
    attachment_number: str | None
    description: str | None
    page_count: int | None
    is_available: bool | None
    has_filepath_local: bool
    pacer_doc_id: str | None
    record_sha256: str
    projected_cost_usd: str | None

    @classmethod
    def from_document(cls, document: CourtListenerRecapDocument) -> AttachmentSelector:
        """Bind one listing row to the exact bytes CourtListener returned."""

        record = document.raw
        page_count = _optional_positive_int(record.get("page_count"))
        filepath_local = record.get("filepath_local")
        has_filepath_local = isinstance(filepath_local, str) and bool(
            filepath_local.strip()
        )
        pacer_doc_id = record.get("pacer_doc_id")
        return cls(
            source_document_id=document.document_id,
            attachment_number=document.attachment_number,
            description=document.description,
            page_count=page_count,
            is_available=document.is_available,
            has_filepath_local=has_filepath_local,
            pacer_doc_id=str(pacer_doc_id) if pacer_doc_id is not None else None,
            record_sha256=str(
                ARTIFACT_RAW_SHA256_V1.commit(
                    dict(record), domain=RECAP_ATTACHMENT_SELECTOR_V1
                ).digest
            ),
            projected_cost_usd=_projected_cost_usd(
                page_count=page_count,
                is_available=document.is_available,
                has_filepath_local=has_filepath_local,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "attachment_number": self.attachment_number,
            "description": self.description,
            "page_count": self.page_count,
            "is_available": self.is_available,
            "has_filepath_local": self.has_filepath_local,
            "pacer_doc_id": self.pacer_doc_id,
            "record_sha256": self.record_sha256,
            "projected_cost_usd": self.projected_cost_usd,
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageFetchOutcome:
    """Terminal per-menu result, safe to publish outside the private tree."""

    recap_document: str
    state: str
    reason: str
    docket_entry_id: str | None = None
    operation_key: str | None = None
    queue_id: str | None = None
    queue_status: int | None = None
    reservation_usd: str | None = None
    dispatched: bool = False
    selectors: tuple[AttachmentSelector, ...] = ()

    @property
    def halted(self) -> bool:
        return self.state == "halted"

    def to_record(self) -> dict[str, Any]:
        return {
            "recap_document": self.recap_document,
            "state": self.state,
            "reason": self.reason,
            "docket_entry_id": self.docket_entry_id,
            "operation_key": self.operation_key,
            "queue_id": self.queue_id,
            "queue_status": self.queue_status,
            "reservation_usd": self.reservation_usd,
            "dispatched": self.dispatched,
            "selector_count": len(self.selectors),
            "selectors": [selector.to_record() for selector in self.selectors],
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageFetchResult:
    """Whole-run result including the journal's committed reservations."""

    outcomes: tuple[AttachmentPageFetchOutcome, ...]
    committed_usd: str
    max_total_usd: str
    cycle_id: str
    authorization_sha256: str

    @property
    def halted(self) -> bool:
        return any(outcome.halted for outcome in self.outcomes)

    @property
    def dispatched_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.dispatched)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": ATTACHMENT_PAGE_FETCH_RECEIPT_SCHEMA,
            "cycle_id": self.cycle_id,
            "authorization_sha256": self.authorization_sha256,
            "committed_usd": self.committed_usd,
            "max_total_usd": self.max_total_usd,
            "dispatched_count": self.dispatched_count,
            "halted": self.halted,
            "outcomes": [outcome.to_record() for outcome in self.outcomes],
        }


class AttachmentPageFetchJournal:
    """Crash-durable exactly-once journal for attachment-menu purchases."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_page_fetches (
                recap_document TEXT PRIMARY KEY,
                operation_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                reason TEXT NOT NULL,
                reservation_usd TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                authorization_sha256 TEXT NOT NULL,
                docket_entry_id TEXT,
                queue_id TEXT,
                queue_status INTEGER,
                submitted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def __enter__(self) -> AttachmentPageFetchJournal:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    def close(self) -> None:
        self._connection.close()

    def record(self, recap_document: str) -> Mapping[str, Any] | None:
        row = self._connection.execute(
            "SELECT * FROM attachment_page_fetches WHERE recap_document = ?",
            (recap_document,),
        ).fetchone()
        return None if row is None else dict(row)

    def records(self) -> tuple[Mapping[str, Any], ...]:
        rows = self._connection.execute(
            "SELECT * FROM attachment_page_fetches ORDER BY recap_document"
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def committed_usd(self) -> Decimal:
        """Return every reservation that a PACER statement could still bill."""

        rows = self._connection.execute(
            "SELECT reservation_usd FROM attachment_page_fetches "
            "WHERE state NOT IN ('refused')"
        ).fetchall()
        total = Decimal("0.00")
        for row in rows:
            total += Decimal(str(row["reservation_usd"]))
        return total.quantize(_MONEY_PLACES)

    def reserve(
        self,
        recap_document: str,
        *,
        operation_key: str,
        reservation_usd: str,
        cycle_id: str,
        authorization_sha256: str,
        docket_entry_id: str,
        now: datetime,
    ) -> None:
        """Commit the charge-bearing intent before the POST leaves the process."""

        timestamp = _timestamp(now)
        try:
            self._connection.execute(
                """
                INSERT INTO attachment_page_fetches (
                    recap_document, operation_key, state, reason, reservation_usd,
                    cycle_id, authorization_sha256, docket_entry_id, queue_id,
                    queue_status, submitted_at, updated_at
                ) VALUES (?, ?, 'submitted', 'dispatch_in_flight', ?, ?, ?, ?,
                    NULL, NULL, ?, ?)
                """,
                (
                    recap_document,
                    operation_key,
                    reservation_usd,
                    cycle_id,
                    authorization_sha256,
                    docket_entry_id,
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise AttachmentPageFetchError(
                f"attachment menu {recap_document} is already journalled"
            ) from exc

    def update(
        self,
        recap_document: str,
        *,
        state: str,
        reason: str,
        now: datetime,
        queue_id: str | None = None,
        queue_status: int | None = None,
    ) -> None:
        cursor = self._connection.execute(
            """
            UPDATE attachment_page_fetches
            SET state = ?,
                reason = ?,
                queue_id = COALESCE(?, queue_id),
                queue_status = COALESCE(?, queue_status),
                updated_at = ?
            WHERE recap_document = ?
            """,
            (state, reason, queue_id, queue_status, _timestamp(now), recap_document),
        )
        if cursor.rowcount != 1:
            raise AttachmentPageFetchError(
                f"attachment menu {recap_document} is not journalled"
            )

    def clear_refused(self, recap_document: str) -> None:
        """Drop a never-dispatched row so a later run may reserve it again."""

        self._connection.execute(
            "DELETE FROM attachment_page_fetches "
            "WHERE recap_document = ? AND state = 'refused'",
            (recap_document,),
        )


@dataclass(slots=True)
class RecapFetchQueueReader:
    """Free queue-detail reader with the #706 not-yet-visible semantics."""

    transport: RecapFetchTransport
    api_token: str = field(repr=False)
    timeout_seconds: float = 30.0

    def read(self, queue_id: str) -> Mapping[str, Any] | None:
        """Return the queue payload, or ``None`` while it is not yet visible."""

        response = self.transport.request(
            method="GET",
            path=f"/recap-fetch/{recap_fetch_identifier(queue_id)}/",
            form={},
            headers={
                "Authorization": f"Token {self.api_token}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout_seconds=self.timeout_seconds,
        )
        if 200 <= response.status_code < 300:
            return response.payload
        if (
            response.status_code == 404
            or response.status_code in RECAP_FETCH_RETRYABLE_STATUS_CODES
        ):
            return None
        raise CourtListenerRecapFetchError(
            f"CourtListener returned HTTP {response.status_code}"
        )


def fetch_attachment_pages(
    recap_documents: Sequence[str],
    *,
    journal: AttachmentPageFetchJournal,
    broker: RecapFetchPurchaseBroker,
    metadata_client: RecapDocumentMetadataClient,
    queue_reader: RecapFetchQueueReader,
    cycle_id: str,
    authorization_sha256: str,
    max_total_usd: str,
    reservation_usd: str = "0.30",
    poll_attempts: int = 6,
    poll_backoff_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
) -> AttachmentPageFetchResult:
    """Buy each missing attachment menu once and resolve its selectors.

    ``authorization_sha256`` is the digest of the owner authorization governing
    the spend; it is committed into the canonical submission body's
    ``purchase_policy_sha256`` field so every dispatched menu is bound to the
    authority that permitted it.
    """

    _require_hex(authorization_sha256, "authorization digest")
    ceiling = _money(max_total_usd, "maximum total")
    reservation = _money(reservation_usd, "per-menu reservation")
    if reservation <= 0:
        raise AttachmentPageFetchError("per-menu reservation must be positive")
    if not cycle_id or "\n" in cycle_id:
        raise AttachmentPageFetchError("cycle ID must be a single non-empty line")
    ordered = _unique_identifiers(recap_documents)
    outcomes: list[AttachmentPageFetchOutcome] = []
    for recap_document in ordered:
        outcome = _fetch_one(
            recap_document,
            journal=journal,
            broker=broker,
            metadata_client=metadata_client,
            queue_reader=queue_reader,
            cycle_id=cycle_id,
            authorization_sha256=authorization_sha256,
            ceiling=ceiling,
            reservation=reservation,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
            sleep=sleep,
            clock=clock,
        )
        outcomes.append(outcome)
        if outcome.halted:
            break
    return AttachmentPageFetchResult(
        outcomes=tuple(outcomes),
        committed_usd=_format_money(journal.committed_usd()),
        max_total_usd=_format_money(ceiling),
        cycle_id=cycle_id,
        authorization_sha256=authorization_sha256,
    )


def execute_attachment_page_fetch_run(
    *,
    recap_documents: Sequence[str],
    journal_path: str | Path,
    cycle_id: str,
    authorization_sha256: str,
    max_total_usd: str,
    reservation_usd: str = "0.30",
    poll_attempts: int = 6,
    poll_backoff_seconds: float = 5.0,
) -> dict[str, Any]:
    """Compose the live direct lane from the environment and run it once.

    This is the console entry point: it owns credential loading and transport
    construction so the CLI adapter stays free of ingestion imports.
    """

    from legalforecast.ingestion.courtlistener_client import (
        CourtListenerClient,
        CourtListenerConfig,
    )
    from legalforecast.ingestion.courtlistener_recap_fetch import (
        DirectCourtListenerRecapFetchConfig,
        DirectCourtListenerRecapFetchPurchaseBroker,
        UrlLibRecapFetchTransport,
    )

    config = DirectCourtListenerRecapFetchConfig.from_env()
    transport = UrlLibRecapFetchTransport(config.base_url)
    with AttachmentPageFetchJournal(journal_path) as journal:
        result = fetch_attachment_pages(
            list(recap_documents),
            journal=journal,
            broker=DirectCourtListenerRecapFetchPurchaseBroker(
                config, transport=transport
            ),
            metadata_client=CourtListenerClient(
                config=CourtListenerConfig(api_token=config.api_token)
            ),
            queue_reader=RecapFetchQueueReader(
                transport=transport,
                api_token=config.api_token,
                timeout_seconds=config.timeout_seconds,
            ),
            cycle_id=cycle_id,
            authorization_sha256=authorization_sha256,
            max_total_usd=max_total_usd,
            reservation_usd=reservation_usd,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
        )
    return result.to_record()


@dataclass(slots=True)
class _MenuOperation:
    """Per-menu identity plus the journal writes every branch shares."""

    recap_document: str
    journal: AttachmentPageFetchJournal
    clock: Callable[[], datetime]
    docket_entry_id: str | None = None
    operation_key: str | None = None
    reservation_usd: str | None = None
    dispatched: bool = False

    def settle(
        self,
        state: str,
        reason: str,
        *,
        journal_reason: str | None = None,
        journalled: bool = True,
        queue_id: str | None = None,
        queue_status: int | None = None,
        selectors: tuple[AttachmentSelector, ...] = (),
    ) -> AttachmentPageFetchOutcome:
        """Record the terminal state for this menu and describe it."""

        if journalled:
            self.journal.update(
                self.recap_document,
                state=state,
                reason=journal_reason or reason,
                queue_id=queue_id,
                queue_status=queue_status,
                now=self.clock(),
            )
        return AttachmentPageFetchOutcome(
            recap_document=self.recap_document,
            state=state,
            reason=reason,
            docket_entry_id=self.docket_entry_id,
            operation_key=self.operation_key,
            queue_id=queue_id,
            queue_status=queue_status,
            reservation_usd=self.reservation_usd,
            dispatched=self.dispatched,
            selectors=selectors,
        )


def _fetch_one(
    recap_document: str,
    *,
    journal: AttachmentPageFetchJournal,
    broker: RecapFetchPurchaseBroker,
    metadata_client: RecapDocumentMetadataClient,
    queue_reader: RecapFetchQueueReader,
    cycle_id: str,
    authorization_sha256: str,
    ceiling: Decimal,
    reservation: Decimal,
    poll_attempts: int,
    poll_backoff_seconds: float,
    sleep: Callable[[float], None],
    clock: Callable[[], datetime],
) -> AttachmentPageFetchOutcome:
    operation = _MenuOperation(recap_document, journal, clock)
    existing = journal.record(recap_document)
    if existing is not None:
        resumed = _resume(
            existing,
            operation=operation,
            metadata_client=metadata_client,
            queue_reader=queue_reader,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
            sleep=sleep,
        )
        if resumed is not None:
            return resumed
        journal.clear_refused(recap_document)

    document = metadata_client.get_recap_document(recap_document)
    if document.document_id != recap_document:
        raise AttachmentPageFetchError(
            f"CourtListener returned a different document for {recap_document}"
        )
    if document.docket_entry_id is None:
        raise AttachmentPageFetchError(
            f"RECAP document {recap_document} has no parent docket entry"
        )
    docket_entry_id = document.docket_entry_id
    operation.docket_entry_id = docket_entry_id
    existing_selectors = _selectors(metadata_client, docket_entry_id)
    if existing_selectors:
        # The menu is already ingested; paying for it again buys nothing.
        return operation.settle(
            "skipped",
            "attachment_rows_already_present",
            journalled=False,
            selectors=existing_selectors,
        )
    operation.reservation_usd = _format_money(reservation)
    if journal.committed_usd() + reservation > ceiling:
        return operation.settle(
            "halted", "prospective_ceiling_breach", journalled=False
        )

    operation.operation_key = str(uuid.uuid4())
    prepared = broker.prepare_submission()
    try:
        # The journal row is committed before the POST so a crash between the
        # two can never look like an unattempted menu.
        journal.reserve(
            recap_document,
            operation_key=operation.operation_key,
            reservation_usd=operation.reservation_usd,
            cycle_id=cycle_id,
            authorization_sha256=authorization_sha256,
            docket_entry_id=docket_entry_id,
            now=clock(),
        )
    except BaseException as exc:
        try:
            prepared.cancel()
        except BaseException as cleanup_exc:  # pragma: no cover - defensive
            exc.add_note(f"submission cancellation failed: {cleanup_exc}")
        raise
    submission = {
        "request_type": ATTACHMENT_PAGE_REQUEST_TYPE,
        "recap_document": recap_document,
        "cycle_id": cycle_id,
        "purchase_policy_sha256": authorization_sha256,
        "operation_key": operation.operation_key,
        "reservation_usd": operation.reservation_usd,
    }
    try:
        response = prepared(submission)
    except (ValueError, BrokerDefiniteRejection) as exc:
        return operation.settle(
            "refused",
            "pre_dispatch_rejection",
            journal_reason=f"pre_dispatch_rejection:{type(exc).__name__}",
        )
    except (
        BrokerOutcomeUnknown,
        CourtListenerRecapFetchOutcomeUnknown,
        TimeoutError,
        ConnectionError,
        OSError,
    ):
        operation.dispatched = True
        return operation.settle("unknown", "dispatch_outcome_unknown")
    operation.dispatched = True
    try:
        queue_id = recap_fetch_queue_id(response)
    except CourtListenerRecapFetchOutcomeUnknown:
        return operation.settle("unknown", "queue_receipt_incomplete")
    journal.update(
        recap_document,
        state="queued",
        reason="awaiting_queue_completion",
        queue_id=queue_id,
        now=clock(),
    )
    return _await_queue(
        operation=operation,
        metadata_client=metadata_client,
        queue_reader=queue_reader,
        queue_id=queue_id,
        poll_attempts=poll_attempts,
        poll_backoff_seconds=poll_backoff_seconds,
        sleep=sleep,
    )


def _resume(
    existing: Mapping[str, Any],
    *,
    operation: _MenuOperation,
    metadata_client: RecapDocumentMetadataClient,
    queue_reader: RecapFetchQueueReader,
    poll_attempts: int,
    poll_backoff_seconds: float,
    sleep: Callable[[float], None],
) -> AttachmentPageFetchOutcome | None:
    """Return the resumed outcome, or ``None`` to allow a fresh dispatch."""

    state = str(existing["state"])
    if state in _REDISPATCHABLE_STATES:
        return None
    operation.docket_entry_id = _optional_str(existing.get("docket_entry_id"))
    operation.operation_key = _optional_str(existing.get("operation_key"))
    operation.reservation_usd = _optional_str(existing.get("reservation_usd"))
    queue_id = _optional_str(existing.get("queue_id"))
    if state == "queued" and queue_id is not None:
        return _await_queue(
            operation=operation,
            metadata_client=metadata_client,
            queue_reader=queue_reader,
            queue_id=queue_id,
            poll_attempts=poll_attempts,
            poll_backoff_seconds=poll_backoff_seconds,
            sleep=sleep,
        )
    queue_status = _optional_positive_int(existing.get("queue_status"))
    if state == "confirmed":
        return operation.settle(
            "confirmed",
            "already_confirmed",
            journalled=False,
            queue_id=queue_id,
            queue_status=queue_status,
            selectors=_resumed_selectors(metadata_client, operation.docket_entry_id),
        )
    return operation.settle(
        state,
        f"prior_{state}_requires_owner_resolution",
        journalled=False,
        queue_id=queue_id,
        queue_status=queue_status,
    )


def _await_queue(
    *,
    operation: _MenuOperation,
    metadata_client: RecapDocumentMetadataClient,
    queue_reader: RecapFetchQueueReader,
    queue_id: str,
    poll_attempts: int,
    poll_backoff_seconds: float,
    sleep: Callable[[float], None],
) -> AttachmentPageFetchOutcome:
    """Poll one queued menu, tolerating the documented queue-visibility lag."""

    if poll_attempts < 1:
        raise AttachmentPageFetchError("poll attempts must be positive")
    last_status: int | None = None
    for index in range(poll_attempts):
        payload = queue_reader.read(queue_id)
        if payload is not None:
            last_status = recap_fetch_queue_status(payload)
            if last_status == RECAP_FETCH_SUCCESS_STATUS:
                return operation.settle(
                    "confirmed",
                    "queue_completed",
                    queue_id=queue_id,
                    queue_status=last_status,
                    selectors=_resumed_selectors(
                        metadata_client, operation.docket_entry_id
                    ),
                )
            if last_status in RECAP_FETCH_TERMINAL_FAILURE_STATUSES:
                return operation.settle(
                    "failed",
                    f"queue_status_{last_status}",
                    queue_id=queue_id,
                    queue_status=last_status,
                )
            if last_status not in RECAP_FETCH_PENDING_STATUSES:
                return operation.settle(
                    "unknown",
                    f"unknown_queue_status_{last_status}",
                    queue_id=queue_id,
                    queue_status=last_status,
                )
        if index + 1 < poll_attempts and poll_backoff_seconds:
            sleep(poll_backoff_seconds)
    return operation.settle(
        "queued",
        (
            "queue_not_yet_visible"
            if last_status is None
            else f"queue_pending_status_{last_status}"
        ),
        queue_id=queue_id,
        queue_status=last_status,
    )


def _resumed_selectors(
    metadata_client: RecapDocumentMetadataClient, docket_entry_id: str | None
) -> tuple[AttachmentSelector, ...]:
    if docket_entry_id is None:
        return ()
    return _selectors(metadata_client, docket_entry_id)


def _selectors(
    metadata_client: RecapDocumentMetadataClient, docket_entry_id: str
) -> tuple[AttachmentSelector, ...]:
    """Read the free listing view and keep only attachment-level rows."""

    return tuple(
        AttachmentSelector.from_document(document)
        for document in metadata_client.iter_recap_documents(docket_entry_id)
        if document.attachment_number is not None
    )


def _projected_cost_usd(
    *, page_count: int | None, is_available: bool | None, has_filepath_local: bool
) -> str | None:
    if is_available is True and has_filepath_local:
        return _format_money(Decimal("0.00"))
    if page_count is None:
        return None
    cost = min(PACER_PAGE_FEE_USD * page_count, PACER_DOCUMENT_FEE_CAP_USD)
    return _format_money(cost)


def _unique_identifiers(values: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for value in values:
        identifier = recap_fetch_identifier(value)
        if identifier in ordered:
            raise AttachmentPageFetchError(
                f"duplicate attachment menu request for {identifier}"
            )
        ordered.append(identifier)
    if not ordered:
        raise AttachmentPageFetchError("at least one RECAP document is required")
    return tuple(ordered)


def _money(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except ArithmeticError as exc:
        raise AttachmentPageFetchError(f"invalid {label} amount") from exc
    if parsed < 0 or parsed != parsed.quantize(_MONEY_PLACES):
        raise AttachmentPageFetchError(f"invalid {label} amount")
    return parsed


def _format_money(value: Decimal) -> str:
    return f"{value.quantize(_MONEY_PLACES):f}"


def _require_hex(value: str, label: str) -> str:
    if len(value) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise AttachmentPageFetchError(f"invalid {label}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _timestamp(now: datetime) -> str:
    moment = now.astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
