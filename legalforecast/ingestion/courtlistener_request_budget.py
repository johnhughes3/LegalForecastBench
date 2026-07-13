"""Crash-durable rolling request budgets for CourtListener REST calls.

Process-local sleeps are insufficient for provider ceilings: retries, crashes,
resumes, and concurrent workers can otherwise forget or race one another.  This
ledger reserves each physical HTTP attempt in SQLite before transmission.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final[str] = "legalforecast.courtlistener_request_budget.v1"
_WINDOWS: Final[tuple[tuple[str, float], ...]] = (
    ("minute", 60.0),
    ("hour", 3_600.0),
    ("day", 86_400.0),
)
_BOUNDARY_EPSILON_SECONDS: Final[float] = 0.001


class CourtListenerRequestBudgetError(RuntimeError):
    """Base class for request-budget failures."""


class CourtListenerRequestBudgetExhausted(CourtListenerRequestBudgetError):
    """Raised when capacity cannot become available within the allowed wait."""


@dataclass(frozen=True, slots=True)
class CourtListenerRequestLimits:
    """Rolling provider-attempt ceilings with conservative headroom."""

    per_minute: int = 48
    per_hour: int = 580
    per_day: int = 2_700

    def __post_init__(self) -> None:
        if min(self.per_minute, self.per_hour, self.per_day) <= 0:
            raise ValueError("CourtListener request limits must be positive")
        if self.per_hour < self.per_minute:
            raise ValueError("hour limit cannot be lower than minute limit")
        if self.per_day < self.per_hour:
            raise ValueError("day limit cannot be lower than hour limit")

    def value_for(self, window: str) -> int:
        if window == "minute":
            return self.per_minute
        if window == "hour":
            return self.per_hour
        if window == "day":
            return self.per_day
        raise KeyError(window)


@dataclass(frozen=True, slots=True)
class CourtListenerRequestReservation:
    """One durable pre-wire request reservation."""

    reservation_id: int
    reserved_at: float
    method: str
    endpoint: str


class CourtListenerRequestBudget:
    """Serialize and reserve CourtListener attempts across processes."""

    def __init__(
        self,
        path: Path,
        *,
        limits: CourtListenerRequestLimits | None = None,
        max_wait_seconds: float = 120.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_wait_seconds < 0:
            raise ValueError("max_wait_seconds cannot be negative")
        self.path = path
        self.limits = limits or CourtListenerRequestLimits()
        self.max_wait_seconds = max_wait_seconds
        self._clock = clock
        self._sleep = sleep
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def reserve(self, method: str, endpoint: str) -> CourtListenerRequestReservation:
        """Reserve one physical request attempt before it is transmitted."""

        normalized_method = method.strip().upper()
        normalized_endpoint = endpoint.strip()
        if not normalized_method or not normalized_endpoint.startswith("/"):
            raise ValueError("method and absolute API endpoint are required")

        waited = 0.0
        while True:
            now = float(self._clock())
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                required_wait, limiting_window = self._required_wait(connection, now)
                if required_wait <= 0:
                    cursor = connection.execute(
                        """
                        INSERT INTO courtlistener_request_attempts(
                            reserved_at, method, endpoint
                        ) VALUES (?, ?, ?)
                        """,
                        (now, normalized_method, normalized_endpoint),
                    )
                    reservation_id = cursor.lastrowid
                    assert reservation_id is not None
                    connection.commit()
                    return CourtListenerRequestReservation(
                        reservation_id=reservation_id,
                        reserved_at=now,
                        method=normalized_method,
                        endpoint=normalized_endpoint,
                    )
                connection.rollback()

            remaining_wait = self.max_wait_seconds - waited
            if required_wait > remaining_wait:
                raise CourtListenerRequestBudgetExhausted(
                    "CourtListener request budget exhausted for rolling "
                    f"{limiting_window} window; needs {required_wait:.3f}s wait, "
                    f"but only {remaining_wait:.3f}s remains"
                )
            self._sleep(required_wait)
            waited += required_wait

    def before_request(self, method: str, endpoint: str) -> None:
        """CourtListenerClient-compatible pre-attempt callback."""

        self.reserve(method, endpoint)

    def total_reservations(self) -> int:
        """Return the immutable all-time attempt count for audit summaries."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM courtlistener_request_attempts"
            ).fetchone()
        assert row is not None
        return int(row[0])

    def _required_wait(
        self, connection: sqlite3.Connection, now: float
    ) -> tuple[float, str | None]:
        longest_wait = 0.0
        limiting_window: str | None = None
        for window, seconds in _WINDOWS:
            cutoff = now - seconds
            row = connection.execute(
                """
                SELECT COUNT(*), MIN(reserved_at)
                FROM courtlistener_request_attempts
                WHERE reserved_at > ?
                """,
                (cutoff,),
            ).fetchone()
            assert row is not None
            if int(row[0]) < self.limits.value_for(window):
                continue
            oldest = float(row[1])
            wait = oldest + seconds - now + _BOUNDARY_EPSILON_SECONDS
            if wait > longest_wait:
                longest_wait = wait
                limiting_window = window
        return longest_wait, limiting_window

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS courtlistener_request_budget_config (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version TEXT NOT NULL,
                    per_minute INTEGER NOT NULL,
                    per_hour INTEGER NOT NULL,
                    per_day INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS courtlistener_request_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reserved_at REAL NOT NULL,
                    method TEXT NOT NULL,
                    endpoint TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS
                    courtlistener_request_attempts_reserved_at
                ON courtlistener_request_attempts(reserved_at);
                """
            )
            expected = (
                SCHEMA_VERSION,
                self.limits.per_minute,
                self.limits.per_hour,
                self.limits.per_day,
            )
            row = connection.execute(
                """
                SELECT schema_version, per_minute, per_hour, per_day
                FROM courtlistener_request_budget_config WHERE singleton = 1
                """
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO courtlistener_request_budget_config(
                        singleton, schema_version, per_minute, per_hour, per_day
                    ) VALUES (1, ?, ?, ?, ?)
                    """,
                    expected,
                )
            elif tuple(row) != expected:
                raise CourtListenerRequestBudgetError(
                    "CourtListener request ledger configuration mismatch: "
                    f"stored={tuple(row)!r}, requested={expected!r}"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection
