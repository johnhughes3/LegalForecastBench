"""Crash-durable pre-dispatch journal for attachment-menu charges.

A receipt assembled in memory and written after the loop is not a record of
spend. Three failure modes destroy it while the charges have already gone out:
an ``--output`` path that already exists, a provider budget refusal raised from
outside the executor's handlers, and an ordinary crash. This journal moves the
durable write to the only place it is honest -- *before* the POST -- and
updates the same row with the observed disposition afterwards, so the record
can never lag the money.

The same rows are the re-charge guard. A row keyed on
``(plan_sha256, docket_entry_id)`` means a charge for that entry was already
dispatched under that plan, whatever became of it. That deliberately includes
a row left at ``intended`` by a crash: from here, a request that was written
but never sent is indistinguishable from one PACER already billed, so both
refuse a second charge. Recovering an entry that genuinely never reached the
wire is a new plan and a new owner decision, not a silent retry.

The store is SQLite in WAL mode with ``synchronous=FULL`` -- the same shape the
request-budget ledger uses -- because each intent must survive a power loss
between the write and the POST it authorizes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Final

from legalforecast._datetime import format_utc_iso_z
from legalforecast.contracts import ATTACHMENT_PAGE_DISPATCH_JOURNAL_V1
from legalforecast.ingestion.attachment_page.plan import (
    AttachmentPageFetchPlan,
    AttachmentPageTarget,
)

JOURNAL_SCHEMA_VERSION: Final = str(ATTACHMENT_PAGE_DISPATCH_JOURNAL_V1)

#: The disposition a row carries between the pre-dispatch write and the
#: observed outcome. A row still holding it has an unknown charge state.
INTENDED: Final = "intended"

_TABLE: Final = "attachment_page_dispatch"


class AttachmentPageJournalError(RuntimeError):
    """Raised when the dispatch journal cannot be opened, read, or written."""


class AttachmentPageAlreadyDispatched(AttachmentPageJournalError):
    """Raised when an entry already carries a dispatched charge for this plan."""


@dataclass(frozen=True, slots=True)
class AttachmentPageDispatchRecord:
    """One durable statement that a charge for this entry was dispatched."""

    plan_id: str
    plan_sha256: str
    candidate_id: str
    docket_entry_id: str
    main_source_document_id: str
    intended_at_utc: str
    disposition: str
    queue_id: str | None
    status: int | None
    message: str
    resolved_at_utc: str | None

    @property
    def resolved(self) -> bool:
        """Whether an outcome was observed, as opposed to only intended."""

        return self.disposition != INTENDED

    def to_record(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "candidate_id": self.candidate_id,
            "docket_entry_id": self.docket_entry_id,
            "main_source_document_id": self.main_source_document_id,
            "intended_at_utc": self.intended_at_utc,
            "disposition": self.disposition,
            "queue_id": self.queue_id,
            "status": self.status,
            "message": self.message,
            "resolved_at_utc": self.resolved_at_utc,
        }


def _now() -> str:
    return format_utc_iso_z(datetime.now(UTC))


def _record_from_row(row: sqlite3.Row) -> AttachmentPageDispatchRecord:
    return AttachmentPageDispatchRecord(
        plan_id=str(row["plan_id"]),
        plan_sha256=str(row["plan_sha256"]),
        candidate_id=str(row["candidate_id"]),
        docket_entry_id=str(row["docket_entry_id"]),
        main_source_document_id=str(row["main_source_document_id"]),
        intended_at_utc=str(row["intended_at_utc"]),
        disposition=str(row["disposition"]),
        queue_id=None if row["queue_id"] is None else str(row["queue_id"]),
        status=None if row["status"] is None else int(row["status"]),
        message=str(row["message"] or ""),
        resolved_at_utc=(
            None if row["resolved_at_utc"] is None else str(row["resolved_at_utc"])
        ),
    )


class AttachmentPageDispatchJournal:
    """Durable record of every attachment-menu charge this repo intends."""

    def __init__(self, path: str | Path, *, now: Callable[[], str] = _now) -> None:
        self.path = Path(path)
        self._now = now
        self._closed = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path, isolation_level=None)
        except (OSError, sqlite3.Error) as exc:
            raise AttachmentPageJournalError(
                f"could not open the attachment-menu dispatch journal at "
                f"{self.path}: {exc}"
            ) from exc
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA journal_mode=WAL")
            # An intent that is not on disk before the POST is not an intent.
            self._connection.execute("PRAGMA synchronous=FULL")
            self._create_schema()
        except sqlite3.Error as exc:
            self._connection.close()
            self._closed = True
            raise AttachmentPageJournalError(
                f"attachment-menu dispatch journal is unusable: {exc}"
            ) from exc

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                f"""CREATE TABLE IF NOT EXISTS {_TABLE}(
                    plan_sha256 TEXT NOT NULL,
                    docket_entry_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    main_source_document_id TEXT NOT NULL,
                    intended_at_utc TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    queue_id TEXT,
                    status INTEGER,
                    message TEXT NOT NULL DEFAULT '',
                    resolved_at_utc TEXT,
                    PRIMARY KEY (plan_sha256, docket_entry_id)
                )"""
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS journal_meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO journal_meta(key, value) VALUES ('schema', ?)",
                (JOURNAL_SCHEMA_VERSION,),
            )
        stored = self._connection.execute(
            "SELECT value FROM journal_meta WHERE key='schema'"
        ).fetchone()
        if stored is None or str(stored["value"]) != JOURNAL_SCHEMA_VERSION:
            raise AttachmentPageJournalError(
                "attachment-menu dispatch journal has an unexpected schema version"
            )

    def __enter__(self) -> AttachmentPageDispatchJournal:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._connection.close()

    def _execute(self, statement: str, parameters: tuple[Any, ...]) -> sqlite3.Cursor:
        try:
            return self._connection.execute(statement, parameters)
        except sqlite3.Error as exc:
            raise AttachmentPageJournalError(
                f"attachment-menu dispatch journal write failed: {exc}"
            ) from exc

    def dispatched(
        self, plan_sha256: str, docket_entry_id: str
    ) -> AttachmentPageDispatchRecord | None:
        """Return the durable dispatch row for this entry, if one exists."""

        row = self._execute(
            f"""SELECT * FROM {_TABLE}
            WHERE plan_sha256=? AND docket_entry_id=?""",
            (plan_sha256, str(docket_entry_id)),
        ).fetchone()
        return None if row is None else _record_from_row(row)

    def record_intent(
        self, *, plan: AttachmentPageFetchPlan, target: AttachmentPageTarget
    ) -> AttachmentPageDispatchRecord:
        """Commit the intent to charge for this entry, before the POST.

        Refuses rather than overwriting: an existing row is a charge this repo
        already dispatched under this plan, and the second one is the failure
        this journal exists to prevent.
        """

        intended_at = self._now()
        try:
            with self._connection:
                self._connection.execute(
                    f"""INSERT INTO {_TABLE}(
                        plan_sha256, docket_entry_id, plan_id, candidate_id,
                        main_source_document_id, intended_at_utc, disposition,
                        queue_id, status, message, resolved_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, '', NULL)""",
                    (
                        plan.plan_sha256,
                        str(target.docket_entry_id),
                        plan.plan_id,
                        target.candidate_id,
                        target.main_source_document_id,
                        intended_at,
                        INTENDED,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise AttachmentPageAlreadyDispatched(
                f"a charge for docket entry {target.docket_entry_id} was already "
                "dispatched under this plan"
            ) from exc
        except sqlite3.Error as exc:
            raise AttachmentPageJournalError(
                f"attachment-menu dispatch journal write failed: {exc}"
            ) from exc
        return AttachmentPageDispatchRecord(
            plan_id=plan.plan_id,
            plan_sha256=plan.plan_sha256,
            candidate_id=target.candidate_id,
            docket_entry_id=str(target.docket_entry_id),
            main_source_document_id=target.main_source_document_id,
            intended_at_utc=intended_at,
            disposition=INTENDED,
            queue_id=None,
            status=None,
            message="",
            resolved_at_utc=None,
        )

    def record_disposition(
        self,
        *,
        plan_sha256: str,
        docket_entry_id: str,
        disposition: str,
        queue_id: str | None = None,
        status: int | None = None,
        message: str = "",
    ) -> None:
        """Record what became of one already-dispatched charge."""

        if disposition == INTENDED:
            raise AttachmentPageJournalError(
                "a dispatch disposition cannot be recorded as still intended"
            )
        with self._connection:
            cursor = self._execute(
                f"""UPDATE {_TABLE}
                SET disposition=?, queue_id=?, status=?, message=?, resolved_at_utc=?
                WHERE plan_sha256=? AND docket_entry_id=?""",
                (
                    disposition,
                    queue_id,
                    status,
                    message,
                    self._now(),
                    plan_sha256,
                    str(docket_entry_id),
                ),
            )
        if cursor.rowcount != 1:
            raise AttachmentPageJournalError(
                f"no pre-dispatch journal row exists for docket entry "
                f"{docket_entry_id} under this plan"
            )

    def records_for(self, plan_sha256: str) -> tuple[AttachmentPageDispatchRecord, ...]:
        """Return every dispatch row for one plan, oldest intent first."""

        rows = self._execute(
            f"""SELECT * FROM {_TABLE} WHERE plan_sha256=?
            ORDER BY intended_at_utc, docket_entry_id""",
            (plan_sha256,),
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def dispatched_count(self, plan_sha256: str) -> int:
        """Count the charges durably recorded as dispatched under one plan."""

        row = self._execute(
            f"SELECT COUNT(*) AS total FROM {_TABLE} WHERE plan_sha256=?",
            (plan_sha256,),
        ).fetchone()
        return 0 if row is None else int(row["total"])


def read_dispatch_records(
    path: str | Path, plan_sha256: str
) -> tuple[AttachmentPageDispatchRecord, ...]:
    """Read one plan's dispatch rows without holding the journal open."""

    with closing(AttachmentPageDispatchJournal(path)) as journal:
        return journal.records_for(plan_sha256)
