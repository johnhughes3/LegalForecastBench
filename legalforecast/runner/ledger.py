"""Small crash-durable SQLite run and cell ledger."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from legalforecast.evals.provider_spend_control import (
    RETRYABLE_HTTP_429_FAILURE_TYPE,
)


class RunValidationError(ValueError):
    """Raised when a public run input or durable output is invalid."""


class RunIdentityError(RunValidationError):
    """Raised when a ledger is reused for a different frozen run."""


class RunBlockedError(RunValidationError):
    """Raised when fail-closed state forbids another provider call."""


@dataclass(frozen=True, slots=True)
class CellRecord:
    """Durable state for one exact release/model/unit/repeat cell."""

    cell_id: str
    run_identity_sha256: str
    case_id: str
    unit_id: str
    repeat_index: int
    status: str
    provider_attempt_id: str | None
    receipt_sha256: str | None
    receipt_payload: bytes | None


class RunnerLedger:
    """Reference local ledger with transactional cell reservation."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, isolation_level=None, timeout=30.0)
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._create_schema()
        except BaseException:
            self._connection.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def ensure_run(
        self,
        *,
        identity_sha256: str,
        identity_json: str,
        release_digest: str,
        harness: str,
        model_key: str,
        ceiling_microusd: int,
        approval_reference: str,
    ) -> None:
        """Create the singleton run row or verify its exact frozen identity."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT * FROM public_runner_run WHERE singleton = 1"
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO public_runner_run(
                        singleton, identity_sha256, identity_json, release_digest,
                        harness, model_key, ceiling_microusd, approval_reference,
                        status
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, 'running')
                    """,
                    (
                        identity_sha256,
                        identity_json,
                        release_digest,
                        harness,
                        model_key,
                        ceiling_microusd,
                        approval_reference,
                    ),
                )
            elif (
                str(row["identity_sha256"]) != identity_sha256
                or str(row["identity_json"]) != identity_json
            ):
                raise RunIdentityError(
                    "existing ledger identity differs from requested release "
                    "or engine set"
                )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def inspect_cell(
        self,
        *,
        cell_id: str,
        run_identity_sha256: str,
        case_id: str,
        unit_id: str,
        repeat_index: int,
        allow_retryable_nonbillable: bool = False,
    ) -> CellRecord | None:
        """Inspect an exact cell without creating pre-authorization state."""

        row = self._connection.execute(
            "SELECT * FROM public_runner_cells WHERE cell_id = ?",
            (cell_id,),
        ).fetchone()
        if row is None:
            return None
        record = self._cell_record(row)
        self._verify_cell_identity(
            record,
            run_identity_sha256=run_identity_sha256,
            case_id=case_id,
            unit_id=unit_id,
            repeat_index=repeat_index,
        )
        retryable_nonbillable = False
        if (
            allow_retryable_nonbillable
            and record.status == "reserved"
            and record.provider_attempt_id is not None
        ):
            prior_attempt = self._connection.execute(
                "SELECT status, failure_type FROM provider_attempts "
                "WHERE attempt_id = ?",
                (record.provider_attempt_id,),
            ).fetchone()
            retryable_nonbillable = (
                prior_attempt is not None
                and str(prior_attempt["status"]) == "failed_nonbillable"
                and str(prior_attempt["failure_type"])
                == RETRYABLE_HTTP_429_FAILURE_TYPE
            )
        if record.status not in {"blocked", "completed"} and not retryable_nonbillable:
            raise RunBlockedError(
                f"cell {cell_id} has {record.status} provider state; "
                "another call is forbidden"
            )
        return record

    def reserve_cell_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        cell_id: str,
        run_identity_sha256: str,
        case_id: str,
        unit_id: str,
        repeat_index: int,
        provider_attempt_id: str,
        allow_nonbillable_replacement: bool = False,
    ) -> None:
        """Bind a cell reservation to spend authorization before one commit."""

        row = connection.execute(
            "SELECT * FROM public_runner_cells WHERE cell_id = ?",
            (cell_id,),
        ).fetchone()
        if row is None:
            connection.execute(
                """
                INSERT INTO public_runner_cells(
                    cell_id, run_identity_sha256, case_id, unit_id,
                    repeat_index, status, provider_attempt_id
                ) VALUES (?, ?, ?, ?, ?, 'reserved', ?)
                """,
                (
                    cell_id,
                    run_identity_sha256,
                    case_id,
                    unit_id,
                    repeat_index,
                    provider_attempt_id,
                ),
            )
            return
        record = self._cell_record(row)
        self._verify_cell_identity(
            record,
            run_identity_sha256=run_identity_sha256,
            case_id=case_id,
            unit_id=unit_id,
            repeat_index=repeat_index,
        )
        if (
            allow_nonbillable_replacement
            and record.status == "reserved"
            and record.provider_attempt_id is not None
        ):
            prior_attempt = connection.execute(
                "SELECT status, failure_type FROM provider_attempts "
                "WHERE attempt_id = ?",
                (record.provider_attempt_id,),
            ).fetchone()
            if (
                prior_attempt is not None
                and str(prior_attempt["status"]) == "failed_nonbillable"
                and str(prior_attempt["failure_type"])
                == RETRYABLE_HTTP_429_FAILURE_TYPE
            ):
                connection.execute(
                    """
                    UPDATE public_runner_cells
                    SET provider_attempt_id = ?, failure_type = NULL
                    WHERE cell_id = ? AND status = 'reserved'
                    """,
                    (provider_attempt_id, cell_id),
                )
                return
        if record.status != "blocked":
            raise RunBlockedError(
                f"cell {cell_id} has {record.status} provider state; "
                "another call is forbidden"
            )
        connection.execute(
            """
            UPDATE public_runner_cells
            SET status = 'reserved', provider_attempt_id = ?, failure_type = NULL
            WHERE cell_id = ? AND status = 'blocked'
            """,
            (provider_attempt_id, cell_id),
        )

    def mark_blocked(
        self,
        cell_id: str,
        *,
        provider_attempt_id: str,
        failure_type: str,
    ) -> None:
        """Record a pre-transport failure that must be repaired before retry."""

        self._transition_failure(
            cell_id,
            provider_attempt_id=provider_attempt_id,
            status="blocked",
            failure_type=failure_type,
        )

    def mark_ambiguous(
        self,
        cell_id: str,
        *,
        provider_attempt_id: str,
        failure_type: str,
    ) -> None:
        """Retain a cell after transport may have become billable."""

        self._transition_failure(
            cell_id,
            provider_attempt_id=provider_attempt_id,
            status="ambiguous",
            failure_type=failure_type,
        )

    def mark_completed(
        self,
        cell_id: str,
        *,
        request_body_sha256: str,
        receipt_sha256: str,
        receipt_payload: bytes,
    ) -> None:
        """Bind an immutable receipt to its previously reserved cell."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._connection.execute(
                """
                UPDATE public_runner_cells
                SET status = 'completed', request_body_sha256 = ?,
                    receipt_sha256 = ?, receipt_payload = ?, failure_type = NULL
                WHERE cell_id = ? AND status = 'reserved'
                """,
                (
                    request_body_sha256,
                    receipt_sha256,
                    receipt_payload,
                    cell_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RunBlockedError("cell is not reserved for completion")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def mark_run_completed(self) -> None:
        """Mark the singleton run complete after every requested cell is durable."""

        self._connection.execute(
            "UPDATE public_runner_run SET status = 'completed' WHERE singleton = 1"
        )

    def _transition_failure(
        self,
        cell_id: str,
        *,
        provider_attempt_id: str,
        status: str,
        failure_type: str,
    ) -> None:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._connection.execute(
                """
                UPDATE public_runner_cells
                SET status = ?, failure_type = ?
                WHERE cell_id = ? AND provider_attempt_id = ?
                    AND status = 'reserved'
                """,
                (status, failure_type, cell_id, provider_attempt_id),
            )
            if cursor.rowcount != 1:
                raise RunBlockedError("cell failure state cannot be changed")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS public_runner_run(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                identity_sha256 TEXT NOT NULL,
                identity_json TEXT NOT NULL,
                release_digest TEXT NOT NULL,
                harness TEXT NOT NULL,
                model_key TEXT NOT NULL,
                ceiling_microusd INTEGER NOT NULL CHECK(ceiling_microusd > 0),
                approval_reference TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('running', 'completed'))
            );
            CREATE TABLE IF NOT EXISTS public_runner_cells(
                cell_id TEXT PRIMARY KEY,
                run_identity_sha256 TEXT NOT NULL,
                case_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                repeat_index INTEGER NOT NULL CHECK(repeat_index > 0),
                status TEXT NOT NULL CHECK(
                    status IN ('reserved', 'blocked', 'ambiguous', 'completed')
                ),
                provider_attempt_id TEXT,
                request_body_sha256 TEXT,
                receipt_sha256 TEXT,
                receipt_payload BLOB,
                failure_type TEXT
            );
            """
        )
        columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(public_runner_cells)"
            ).fetchall()
        }
        if "provider_attempt_id" not in columns:
            self._connection.execute(
                "ALTER TABLE public_runner_cells ADD COLUMN provider_attempt_id TEXT"
            )

    @staticmethod
    def _verify_cell_identity(
        record: CellRecord,
        *,
        run_identity_sha256: str,
        case_id: str,
        unit_id: str,
        repeat_index: int,
    ) -> None:
        expected = (run_identity_sha256, case_id, unit_id, repeat_index)
        actual = (
            record.run_identity_sha256,
            record.case_id,
            record.unit_id,
            record.repeat_index,
        )
        if actual != expected:
            raise RunIdentityError("existing cell identity differs")

    @staticmethod
    def _cell_record(row: sqlite3.Row) -> CellRecord:
        receipt = row["receipt_sha256"]
        receipt_payload = row["receipt_payload"]
        provider_attempt = row["provider_attempt_id"]
        return CellRecord(
            cell_id=str(row["cell_id"]),
            run_identity_sha256=str(row["run_identity_sha256"]),
            case_id=str(row["case_id"]),
            unit_id=str(row["unit_id"]),
            repeat_index=int(row["repeat_index"]),
            status=str(row["status"]),
            provider_attempt_id=(
                None if provider_attempt is None else str(provider_attempt)
            ),
            receipt_sha256=None if receipt is None else str(receipt),
            receipt_payload=(
                None if receipt_payload is None else bytes(receipt_payload)
            ),
        )
