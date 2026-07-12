"""Durable provider-attempt journaling and cycle-wide spend reservations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from legalforecast.evals.live_model_solver import LiveModelProviderError

JsonRecord = Mapping[str, object]
DEFAULT_CYCLE_PROVIDER_CAP_USD = 1_000.0


class ProviderJournalError(RuntimeError):
    """Base error for provider journaling and reservation failures."""


class ProviderBudgetExceededError(ProviderJournalError):
    """Raised before a provider attempt would exceed its frozen cycle cap."""


class ProviderJournalReplayMismatchError(ProviderJournalError):
    """Raised when a logical call is replayed with different frozen inputs."""


@dataclass(frozen=True, slots=True)
class ProviderCallIdentity:
    """Immutable identity and policy commitment for one logical provider call."""

    stage: str
    candidate_id: str
    model_key: str
    prompt: str
    model_registry_sha256: str
    account: str = "default"

    @property
    def logical_call_key(self) -> str:
        payload = "\0".join((self.stage, self.candidate_id, self.model_key))
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt.encode()).hexdigest()


class ProviderAttemptJournal:
    """SQLite journal shared by labeling now and evaluation in a later bead."""

    def __init__(
        self,
        path: str | Path,
        *,
        identity: ProviderCallIdentity,
        provider: str,
        reservation_usd: float,
        cycle_cap_usd: float = DEFAULT_CYCLE_PROVIDER_CAP_USD,
    ) -> None:
        if reservation_usd < 0 or cycle_cap_usd <= 0:
            raise ValueError("provider reservation and cap must be non-negative")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.identity = identity
        self.provider = provider
        self.reservation_usd = reservation_usd
        self.cycle_cap_usd = cycle_cap_usd
        self._durable_ordinals: dict[int, int] = {}
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._create_schema()
        self._ensure_ledger()

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

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], JsonRecord],
    ) -> JsonRecord:
        """Replay a captured response or reserve and execute one HTTP attempt."""

        durable_ordinal = self._durable_ordinal(attempt_ordinal)
        row = self._attempt(durable_ordinal)
        if row is not None:
            self._validate_replay(row)
            raw_response = row["raw_response_json"]
            if raw_response is not None:
                loaded = json.loads(str(raw_response))
                if not isinstance(loaded, dict):
                    raise ProviderJournalError(
                        "journaled provider response is not an object"
                    )
                return cast(dict[str, object], loaded)
            if row["status"] == "failed":
                durable_ordinal = self._next_attempt_ordinal()
                self._durable_ordinals[attempt_ordinal] = durable_ordinal
                self._reserve(durable_ordinal)
            elif row["status"] == "ambiguous":
                raise ProviderJournalError(
                    f"provider attempt {durable_ordinal} has no replayable response "
                    f"and status {row['status']}"
                )
        else:
            self._reserve(durable_ordinal)
        try:
            payload = call()
        except LiveModelProviderError as exc:
            self._record_failure(durable_ordinal, exc)
            raise
        self._record_raw_response(durable_ordinal, payload)
        return payload

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        """Map the current process retry ordinal to its durable identity."""

        return self._durable_ordinals.get(local_ordinal, local_ordinal)

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        """Persist validated provider accounting while retaining the reservation."""

        durable_ordinal = self._durable_ordinals.get(attempt_ordinal, attempt_ordinal)
        normalized = {
            "raw_output": raw_output,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": actual_cost_usd,
        }
        with self._connection:
            self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'validated_response', normalized_response_json = ?,
                    input_tokens = ?, output_tokens = ?, actual_cost_usd = ?,
                    completed_at = NULL
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                  AND status IN ('response_received', 'validated_response')
                """,
                (
                    _canonical_json(normalized),
                    input_tokens,
                    output_tokens,
                    actual_cost_usd,
                    self.identity.logical_call_key,
                    durable_ordinal,
                ),
            )

    def commit_reconstruction(self, record: Mapping[str, object]) -> None:
        """Atomically settle cost with normalized units or reconstructed votes."""

        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET reconstructed_result_json = ?, status = 'settled', completed_at = ?
                WHERE logical_call_key = ? AND status = 'validated_response'
                """,
                (_canonical_json(record), _now(), self.identity.logical_call_key),
            )
            if cursor.rowcount != 1:
                raise ProviderJournalError(
                    "normalized reconstruction requires exactly one validated response"
                )

    def stage_cost_total(self, stage: str) -> float:
        row = self._connection.execute(
            """
            SELECT COALESCE(SUM(actual_cost_usd), 0.0) AS total
            FROM provider_attempts WHERE stage = ? AND status = 'settled'
            """,
            (stage,),
        ).fetchone()
        assert row is not None
        return float(row["total"])

    @property
    def has_settled_attempt(self) -> bool:
        """Return whether this logical call has a settled replayable attempt."""

        row = self._connection.execute(
            """SELECT COUNT(*) AS count FROM provider_attempts
            WHERE logical_call_key = ? AND status = 'settled'""",
            (self.identity.logical_call_key,),
        ).fetchone()
        assert row is not None
        return int(row["count"]) == 1

    @property
    def has_validated_response(self) -> bool:
        """Return whether provider accounting awaits normalized reconstruction."""

        row = self._connection.execute(
            """SELECT COUNT(*) AS count FROM provider_attempts
            WHERE logical_call_key = ? AND status = 'validated_response'""",
            (self.identity.logical_call_key,),
        ).fetchone()
        assert row is not None
        return int(row["count"]) == 1

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS provider_ledgers (
                provider TEXT NOT NULL,
                account TEXT NOT NULL,
                cycle_cap_usd REAL NOT NULL CHECK (cycle_cap_usd > 0),
                PRIMARY KEY (provider, account)
            );
            CREATE TABLE IF NOT EXISTS provider_attempts (
                logical_call_key TEXT NOT NULL,
                attempt_ordinal INTEGER NOT NULL CHECK (attempt_ordinal > 0),
                stage TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                model_key TEXT NOT NULL,
                provider TEXT NOT NULL,
                account TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                prompt_sha256 TEXT NOT NULL,
                model_registry_sha256 TEXT NOT NULL,
                reservation_usd REAL NOT NULL CHECK (reservation_usd >= 0),
                status TEXT NOT NULL,
                raw_response_json TEXT,
                normalized_response_json TEXT,
                reconstructed_result_json TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                actual_cost_usd REAL,
                failure_type TEXT,
                failure_message TEXT,
                reserved_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (logical_call_key, attempt_ordinal),
                FOREIGN KEY (provider, account)
                    REFERENCES provider_ledgers(provider, account)
            );
            """
        )

    def _ensure_ledger(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO provider_ledgers(provider, account, cycle_cap_usd)
                VALUES (?, ?, ?)
                """,
                (self.provider, self.identity.account, self.cycle_cap_usd),
            )
            row = self._connection.execute(
                """SELECT cycle_cap_usd FROM provider_ledgers
                WHERE provider = ? AND account = ?""",
                (self.provider, self.identity.account),
            ).fetchone()
            assert row is not None
            if float(row["cycle_cap_usd"]) != self.cycle_cap_usd:
                raise ProviderJournalReplayMismatchError(
                    "provider/account cycle cap differs from the frozen ledger"
                )

    def _attempt(self, attempt_ordinal: int) -> sqlite3.Row | None:
        return self._connection.execute(
            """SELECT * FROM provider_attempts
            WHERE logical_call_key = ? AND attempt_ordinal = ?""",
            (self.identity.logical_call_key, attempt_ordinal),
        ).fetchone()

    def _durable_ordinal(self, local_ordinal: int) -> int:
        mapped = self._durable_ordinals.get(local_ordinal)
        if mapped is not None:
            return mapped
        replayable = self._connection.execute(
            """
            SELECT attempt_ordinal FROM provider_attempts
            WHERE logical_call_key = ?
              AND status IN ('settled', 'validated_response', 'response_received')
            ORDER BY CASE status
                         WHEN 'settled' THEN 0
                         WHEN 'validated_response' THEN 1
                         ELSE 2
                     END,
                     attempt_ordinal DESC
            LIMIT 1
            """,
            (self.identity.logical_call_key,),
        ).fetchone()
        if replayable is not None:
            durable = int(replayable["attempt_ordinal"])
            self._durable_ordinals[local_ordinal] = durable
            return durable
        self._durable_ordinals[local_ordinal] = local_ordinal
        return local_ordinal

    def _next_attempt_ordinal(self) -> int:
        row = self._connection.execute(
            """SELECT COALESCE(MAX(attempt_ordinal), 0) AS maximum
            FROM provider_attempts WHERE logical_call_key = ?""",
            (self.identity.logical_call_key,),
        ).fetchone()
        assert row is not None
        return int(row["maximum"]) + 1

    def _validate_replay(self, row: sqlite3.Row) -> None:
        expected = (
            self.identity.stage,
            self.identity.candidate_id,
            self.identity.model_key,
            self.identity.prompt_sha256,
            self.identity.model_registry_sha256,
            self.provider,
            self.identity.account,
        )
        actual = tuple(
            row[key]
            for key in (
                "stage",
                "candidate_id",
                "model_key",
                "prompt_sha256",
                "model_registry_sha256",
                "provider",
                "account",
            )
        )
        if actual != expected:
            raise ProviderJournalReplayMismatchError(
                "provider attempt identity or frozen input changed on replay"
            )

    def _reserve(self, attempt_ordinal: int) -> None:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN status = 'settled' THEN actual_cost_usd
                         ELSE reservation_usd END
                ), 0.0) AS committed
                FROM provider_attempts
                WHERE provider = ? AND account = ? AND status != 'failed'
                """,
                (self.provider, self.identity.account),
            ).fetchone()
            assert row is not None
            committed = float(row["committed"])
            if committed + self.reservation_usd > self.cycle_cap_usd:
                raise ProviderBudgetExceededError(
                    f"provider reservation would exceed frozen {self.provider}/"
                    f"{self.identity.account} cycle cap"
                )
            self._connection.execute(
                """
                INSERT INTO provider_attempts(
                    logical_call_key, attempt_ordinal, stage, candidate_id,
                    model_key, provider, account, prompt_sha256,
                    prompt_text, model_registry_sha256, reservation_usd,
                    status, reserved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
                """,
                (
                    self.identity.logical_call_key,
                    attempt_ordinal,
                    self.identity.stage,
                    self.identity.candidate_id,
                    self.identity.model_key,
                    self.provider,
                    self.identity.account,
                    self.identity.prompt_sha256,
                    self.identity.prompt,
                    self.identity.model_registry_sha256,
                    self.reservation_usd,
                    _now(),
                ),
            )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def _record_raw_response(self, attempt_ordinal: int, payload: JsonRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'response_received', raw_response_json = ?
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                """,
                (
                    _canonical_json(payload),
                    self.identity.logical_call_key,
                    attempt_ordinal,
                ),
            )

    def _record_failure(
        self, attempt_ordinal: int, error: LiveModelProviderError
    ) -> None:
        ambiguous = error.status_code is None or bool(error.retryable)
        with self._connection:
            self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = ?, failure_type = ?, failure_message = ?, completed_at = ?
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                """,
                (
                    "ambiguous" if ambiguous else "failed",
                    type(error).__name__,
                    str(error),
                    _now(),
                    self.identity.logical_call_key,
                    attempt_ordinal,
                ),
            )


def maximum_call_cost_usd(
    *,
    context_limit: int,
    max_output_tokens: int,
    input_token_price: float,
    output_token_price: float,
) -> float:
    """Return a conservative per-attempt reservation from frozen registry prices."""

    max_input_tokens = max(context_limit - max_output_tokens, 0)
    return (
        max_input_tokens * input_token_price + max_output_tokens * output_token_price
    ) / 1_000_000


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()
