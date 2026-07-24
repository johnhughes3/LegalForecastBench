"""Durable pre-call spend authorization for official provider attempts.

This module intentionally separates spend-control identity from the labeling
provider-journal v2 schema.  The SQLite implementation is the reference
transactional contract for one lock-capable shared filesystem; official
multi-runner execution must use a remote implementation of the same protocol.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self

PROVIDER_SPEND_CONTROL_SCHEMA_VERSION = "legalforecast.provider_spend_control.v2"


class ProviderSpendControlError(RuntimeError):
    """Base error for provider spend authorization and reconciliation."""


class ProviderCapExceededError(ProviderSpendControlError):
    """Raised before an attempt would exceed the frozen provider/account cap."""


class AttemptLimitExceededError(ProviderSpendControlError):
    """Raised before a logical cell would exceed its frozen attempt count."""


class CircuitBreakerOpenError(ProviderSpendControlError):
    """Raised before a call while the frozen provider failure window is open."""


class AuthorityIdentityMismatchError(ProviderSpendControlError):
    """Raised when an existing authority differs from frozen identity or policy."""


class AuthorityPoisonedError(ProviderSpendControlError):
    """Raised after observed usage disproves the frozen reservation bound."""


class AttemptStateError(ProviderSpendControlError):
    """Raised when an attempt cannot transition from its durable current state."""


class SettlementError(ProviderSpendControlError):
    """Raised when provider usage cannot safely settle an attempt reservation."""


class ReconciliationMismatchError(ProviderSpendControlError):
    """Raised when immutable provider-usage reconciliation evidence changes."""


@dataclass(frozen=True, slots=True)
class FrozenAttemptPolicy:
    """Hash-bound attempt and circuit-breaker policy for one official cycle."""

    reservation_ledger_sha256: str
    max_billable_attempts: int
    failure_threshold: int
    failure_window_seconds: int

    def __post_init__(self) -> None:
        _sha256(self.reservation_ledger_sha256, "reservation_ledger_sha256")
        _positive_int(self.max_billable_attempts, "max_billable_attempts")
        _positive_int(self.failure_threshold, "failure_threshold")
        _positive_int(self.failure_window_seconds, "failure_window_seconds")


@dataclass(frozen=True, slots=True)
class ProviderSpendKey:
    """Stable logical-cell identity that deliberately survives workflow reruns."""

    cycle_id: str
    provider: str
    account: str
    stage: str
    model_key: str
    case_id: str
    ablation: str
    repeat_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "cycle_id", _identity(self.cycle_id, "cycle_id"))
        object.__setattr__(
            self,
            "provider",
            _identity(self.provider, "provider").lower(),
        )
        object.__setattr__(self, "account", _identity(self.account, "account"))
        object.__setattr__(self, "stage", _identity(self.stage, "stage"))
        object.__setattr__(self, "model_key", _identity(self.model_key, "model_key"))
        object.__setattr__(self, "case_id", _identity(self.case_id, "case_id"))
        object.__setattr__(self, "ablation", _identity(self.ablation, "ablation"))
        _positive_int(self.repeat_index, "repeat_index")

    @property
    def logical_call_key(self) -> str:
        payload = {
            "ablation": self.ablation,
            "account": self.account,
            "case_id": self.case_id,
            "cycle_id": self.cycle_id,
            "model_key": self.model_key,
            "provider": self.provider,
            "repeat_index": self.repeat_index,
            "stage": self.stage,
        }
        return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AttemptLease:
    """Durable authorization persisted before one provider HTTP attempt."""

    attempt_id: str
    authority_identity_sha256: str
    logical_call_key: str
    attempt_ordinal: int
    reservation_microusd: int

    def __post_init__(self) -> None:
        _sha256(self.attempt_id, "attempt_id")
        _sha256(self.authority_identity_sha256, "authority_identity_sha256")
        _sha256(self.logical_call_key, "logical_call_key")
        _positive_int(self.attempt_ordinal, "attempt_ordinal")
        _positive_int(self.reservation_microusd, "reservation_microusd")


@dataclass(frozen=True, slots=True)
class SpendControlSnapshot:
    """Private provider/account accounting summary without prompts or responses."""

    authority_identity_sha256: str
    cycle_id: str
    provider: str
    account: str
    cap_microusd: int
    committed_microusd: int
    attempt_count: int
    reserved_attempt_count: int
    ambiguous_attempt_count: int
    settled_attempt_count: int
    failure_count_in_window: int
    breaker_open: bool
    authority_poisoned: bool


class ProviderSpendAuthority(Protocol):
    """Atomic authority required immediately before every provider HTTP call."""

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease: ...

    def adopt_attempt(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int | None = None,
    ) -> AttemptLease: ...

    def record_response(
        self,
        lease: AttemptLease,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_microusd: int,
        response_sha256: str,
    ) -> None: ...

    def record_failure(
        self,
        lease: AttemptLease,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None: ...

    def reconcile_ambiguous(
        self,
        lease: AttemptLease,
        *,
        usage_record_id: str,
        usage_record_sha256: str,
        billed_microusd: int | None,
    ) -> None: ...


class SqliteProviderSpendAuthority:
    """Reference authority for processes sharing one lock-capable filesystem."""

    def __init__(
        self,
        path: str | Path,
        *,
        authority_identity_sha256: str,
        cycle_id: str,
        provider: str,
        account: str,
        cap_microusd: int,
        policy: FrozenAttemptPolicy,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.authority_identity_sha256 = _sha256(
            authority_identity_sha256,
            "authority_identity_sha256",
        )
        self.cycle_id = _identity(cycle_id, "cycle_id")
        self.provider = _identity(provider, "provider").lower()
        self.account = _identity(account, "account")
        self.cap_microusd = _positive_int(cap_microusd, "cap_microusd")
        self.policy = policy
        self._clock = clock or time.time
        self._connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=30.0,
        )
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._create_schema()
            self._ensure_identity()
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

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        """Atomically check policy, allocate identity, and reserve exact money."""

        self._verify_key_scope(key)
        reservation = _positive_int(
            reservation_microusd,
            "reservation_microusd",
        )
        now = self._clock()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            attempt_count = self._attempt_count(key.logical_call_key)
            if attempt_count >= self.policy.max_billable_attempts:
                raise AttemptLimitExceededError(
                    "logical provider call reached its frozen billable-attempt limit"
                )
            if self._failure_count(now) >= self.policy.failure_threshold:
                raise CircuitBreakerOpenError(
                    f"provider/account circuit breaker is open for "
                    f"{self.provider}/{self.account}"
                )
            self._raise_if_poisoned()
            committed = self._committed_microusd()
            if committed + reservation > self.cap_microusd:
                raise ProviderCapExceededError(
                    f"provider reservation would exceed frozen {self.provider}/"
                    f"{self.account} cap"
                )
            ordinal = attempt_count + 1
            attempt_id = hashlib.sha256(
                f"{self.authority_identity_sha256}\0{key.logical_call_key}\0{ordinal}".encode()
            ).hexdigest()
            self._connection.execute(
                """
                INSERT INTO provider_attempts(
                    attempt_id, logical_call_key, attempt_ordinal, cycle_id,
                    provider, account, stage, model_key, case_id, ablation,
                    repeat_index, reservation_microusd, status, authorized_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
                """,
                (
                    attempt_id,
                    key.logical_call_key,
                    ordinal,
                    key.cycle_id,
                    key.provider,
                    key.account,
                    key.stage,
                    key.model_key,
                    key.case_id,
                    key.ablation,
                    key.repeat_index,
                    reservation,
                    now,
                ),
            )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        return AttemptLease(
            attempt_id=attempt_id,
            authority_identity_sha256=self.authority_identity_sha256,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=ordinal,
            reservation_microusd=reservation,
        )

    def adopt_attempt(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int | None = None,
    ) -> AttemptLease:
        """Adopt one durable reserved attempt after a process crash."""

        self._verify_key_scope(key)
        self._raise_if_poisoned()
        if attempt_ordinal is None:
            rows = self._connection.execute(
                "SELECT * FROM provider_attempts "
                "WHERE logical_call_key = ? ORDER BY attempt_ordinal DESC LIMIT 1",
                (key.logical_call_key,),
            ).fetchall()
            if len(rows) != 1 or str(rows[0]["status"]) not in {
                "reserved",
                "settled",
            }:
                raise AttemptStateError("latest provider attempt is not replayable")
            row = rows[0]
        else:
            ordinal = _positive_int(attempt_ordinal, "attempt_ordinal")
            row = self._connection.execute(
                "SELECT * FROM provider_attempts "
                "WHERE logical_call_key = ? AND attempt_ordinal = ?",
                (key.logical_call_key, ordinal),
            ).fetchone()
            if row is None or str(row["status"]) not in {"reserved", "settled"}:
                raise AttemptStateError(
                    "provider attempt adoption requires a replayable attempt"
                )
        return self._lease_from_row(row)

    def record_response(
        self,
        lease: AttemptLease,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_microusd: int,
        response_sha256: str,
    ) -> None:
        """Settle a validated response without weakening its prior reservation."""

        if input_tokens < 0 or output_tokens < 0:
            raise SettlementError("provider token counts cannot be negative")
        if actual_microusd < 0:
            raise SettlementError("provider actual cost cannot be negative")
        response_digest = _sha256(response_sha256, "response_sha256")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._lease_row(lease)
            stored_reservation = int(row["reservation_microusd"])
            if actual_microusd > stored_reservation:
                self._poison_authority(
                    "observed provider cost exceeds frozen reservation"
                )
                self._connection.commit()
                raise SettlementError(
                    "provider actual cost exceeds the frozen conservative reservation; "
                    "authority is poisoned"
                )
            if row["status"] == "settled":
                expected = (
                    input_tokens,
                    output_tokens,
                    actual_microusd,
                    response_digest,
                )
                actual = (
                    int(row["input_tokens"]),
                    int(row["output_tokens"]),
                    int(row["actual_microusd"]),
                    str(row["response_sha256"]),
                )
                if actual != expected:
                    raise SettlementError("settled provider response evidence changed")
            elif row["status"] != "reserved":
                raise AttemptStateError(
                    f"provider response cannot settle attempt in {row['status']} state"
                )
            else:
                self._connection.execute(
                    """
                    UPDATE provider_attempts
                    SET status = 'settled', input_tokens = ?, output_tokens = ?,
                        actual_microusd = ?, response_sha256 = ?, completed_at_epoch = ?
                    WHERE attempt_id = ?
                    """,
                    (
                        input_tokens,
                        output_tokens,
                        actual_microusd,
                        response_digest,
                        self._clock(),
                        lease.attempt_id,
                    ),
                )
        except SettlementError:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def record_failure(
        self,
        lease: AttemptLease,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        """Persist failure evidence; ambiguous attempts retain their reservation."""

        normalized_failure = _identity(failure_type, "failure_type")
        target = "ambiguous" if ambiguous else "failed_nonbillable"
        now = self._clock()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._lease_row(lease)
            if row["status"] == target and row["failure_type"] == normalized_failure:
                self._connection.commit()
                return
            if row["status"] != "reserved":
                raise AttemptStateError(
                    "provider failure cannot transition attempt in "
                    f"{row['status']} state"
                )
            self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = ?, failure_type = ?, completed_at_epoch = ?
                WHERE attempt_id = ?
                """,
                (target, normalized_failure, now, lease.attempt_id),
            )
            self._connection.execute(
                """
                INSERT INTO provider_failure_events(attempt_id, failed_at_epoch)
                VALUES (?, ?)
                """,
                (lease.attempt_id, now),
            )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def reconcile_ambiguous(
        self,
        lease: AttemptLease,
        *,
        usage_record_id: str,
        usage_record_sha256: str,
        billed_microusd: int | None,
    ) -> None:
        """Replace an ambiguous reservation only with immutable usage evidence."""

        usage_id = _identity(usage_record_id, "usage_record_id")
        usage_sha256 = _sha256(usage_record_sha256, "usage_record_sha256")
        if billed_microusd is not None:
            if billed_microusd < 0:
                raise SettlementError("reconciled provider cost cannot be negative")
        target = "reconciled_unbilled" if billed_microusd is None else "settled"
        actual_cost = 0 if billed_microusd is None else billed_microusd
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._lease_row(lease)
            stored_reservation = int(row["reservation_microusd"])
            if billed_microusd is not None and billed_microusd > stored_reservation:
                self._poison_authority(
                    "reconciled provider cost exceeds frozen reservation"
                )
                self._connection.commit()
                raise SettlementError(
                    "reconciled provider cost exceeds the frozen reservation; "
                    "authority is poisoned"
                )
            if row["status"] in {"settled", "reconciled_unbilled"}:
                expected = (usage_id, usage_sha256, actual_cost, target)
                actual = (
                    str(row["usage_record_id"]),
                    str(row["usage_record_sha256"]),
                    int(row["actual_microusd"]),
                    str(row["status"]),
                )
                if actual != expected:
                    raise ReconciliationMismatchError(
                        "provider usage reconciliation evidence changed"
                    )
            elif row["status"] not in {"ambiguous", "reserved"}:
                raise AttemptStateError(
                    "only ambiguous or crash-reserved attempts can be reconciled, "
                    f"got {row['status']}"
                )
            else:
                evidence = self._connection.execute(
                    "SELECT * FROM provider_usage_evidence WHERE usage_record_id = ?",
                    (usage_id,),
                ).fetchone()
                if evidence is not None:
                    if (
                        str(evidence["attempt_id"]),
                        str(evidence["usage_record_sha256"]),
                    ) != (lease.attempt_id, usage_sha256):
                        raise ReconciliationMismatchError(
                            "provider usage evidence is already bound to another "
                            "attempt"
                        )
                else:
                    self._connection.execute(
                        "INSERT INTO provider_usage_evidence("
                        "usage_record_id, usage_record_sha256, attempt_id"
                        ") VALUES (?, ?, ?)",
                        (usage_id, usage_sha256, lease.attempt_id),
                    )
                self._connection.execute(
                    """
                    UPDATE provider_attempts
                    SET status = ?, actual_microusd = ?, usage_record_id = ?,
                        usage_record_sha256 = ?, completed_at_epoch = ?
                    WHERE attempt_id = ?
                    """,
                    (
                        target,
                        actual_cost,
                        usage_id,
                        usage_sha256,
                        self._clock(),
                        lease.attempt_id,
                    ),
                )
        except SettlementError:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def snapshot(self) -> SpendControlSnapshot:
        """Return a private exact-money summary of current authority state."""

        now = self._clock()
        rows = self._connection.execute(
            "SELECT status, COUNT(*) AS count FROM provider_attempts GROUP BY status"
        ).fetchall()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        failure_count = self._failure_count(now)
        poisoned = self._is_poisoned()
        return SpendControlSnapshot(
            authority_identity_sha256=self.authority_identity_sha256,
            cycle_id=self.cycle_id,
            provider=self.provider,
            account=self.account,
            cap_microusd=self.cap_microusd,
            committed_microusd=self._committed_microusd(),
            attempt_count=sum(counts.values()),
            reserved_attempt_count=counts.get("reserved", 0),
            ambiguous_attempt_count=counts.get("ambiguous", 0),
            settled_attempt_count=counts.get("settled", 0),
            failure_count_in_window=failure_count,
            breaker_open=(failure_count >= self.policy.failure_threshold or poisoned),
            authority_poisoned=poisoned,
        )

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS provider_spend_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version TEXT NOT NULL,
                authority_identity_sha256 TEXT NOT NULL,
                canonical_path TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                account TEXT NOT NULL,
                cap_microusd INTEGER NOT NULL CHECK (cap_microusd > 0),
                reservation_ledger_sha256 TEXT NOT NULL,
                max_billable_attempts INTEGER NOT NULL
                    CHECK (max_billable_attempts > 0),
                failure_threshold INTEGER NOT NULL CHECK (failure_threshold > 0),
                failure_window_seconds INTEGER NOT NULL
                    CHECK (failure_window_seconds > 0),
                authority_poisoned INTEGER NOT NULL DEFAULT 0
                    CHECK (authority_poisoned IN (0, 1)),
                poison_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS provider_attempts (
                attempt_id TEXT PRIMARY KEY,
                logical_call_key TEXT NOT NULL,
                attempt_ordinal INTEGER NOT NULL CHECK (attempt_ordinal > 0),
                cycle_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                account TEXT NOT NULL,
                stage TEXT NOT NULL,
                model_key TEXT NOT NULL,
                case_id TEXT NOT NULL,
                ablation TEXT NOT NULL,
                repeat_index INTEGER NOT NULL CHECK (repeat_index > 0),
                reservation_microusd INTEGER NOT NULL
                    CHECK (reservation_microusd > 0),
                status TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                actual_microusd INTEGER,
                response_sha256 TEXT,
                failure_type TEXT,
                usage_record_id TEXT,
                usage_record_sha256 TEXT,
                authorized_at_epoch REAL NOT NULL,
                completed_at_epoch REAL,
                UNIQUE (logical_call_key, attempt_ordinal)
            );
            CREATE TABLE IF NOT EXISTS provider_failure_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT NOT NULL,
                failed_at_epoch REAL NOT NULL,
                FOREIGN KEY (attempt_id) REFERENCES provider_attempts(attempt_id)
            );
            CREATE INDEX IF NOT EXISTS provider_failure_window_idx
                ON provider_failure_events(failed_at_epoch);
            CREATE TABLE IF NOT EXISTS provider_usage_evidence (
                usage_record_id TEXT PRIMARY KEY,
                usage_record_sha256 TEXT NOT NULL,
                attempt_id TEXT NOT NULL UNIQUE,
                FOREIGN KEY (attempt_id) REFERENCES provider_attempts(attempt_id)
            );
            """
        )

    def _ensure_identity(self) -> None:
        expected: tuple[object, ...] = (
            PROVIDER_SPEND_CONTROL_SCHEMA_VERSION,
            self.authority_identity_sha256,
            str(self.path.resolve()),
            self.cycle_id,
            self.provider,
            self.account,
            self.cap_microusd,
            self.policy.reservation_ledger_sha256,
            self.policy.max_billable_attempts,
            self.policy.failure_threshold,
            self.policy.failure_window_seconds,
        )
        with self._connection:
            row = self._connection.execute(
                "SELECT * FROM provider_spend_metadata WHERE singleton = 1"
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO provider_spend_metadata(
                        singleton, schema_version, authority_identity_sha256,
                        canonical_path, cycle_id, provider, account, cap_microusd,
                        reservation_ledger_sha256, max_billable_attempts,
                        failure_threshold, failure_window_seconds
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    expected,
                )
                return
            actual = tuple(
                row[name]
                for name in (
                    "schema_version",
                    "authority_identity_sha256",
                    "canonical_path",
                    "cycle_id",
                    "provider",
                    "account",
                    "cap_microusd",
                    "reservation_ledger_sha256",
                    "max_billable_attempts",
                    "failure_threshold",
                    "failure_window_seconds",
                )
            )
            if actual != expected:
                raise AuthorityIdentityMismatchError(
                    "provider spend authority identity or frozen policy differs"
                )

    def _verify_key_scope(self, key: ProviderSpendKey) -> None:
        expected = (self.cycle_id, self.provider, self.account)
        actual = (key.cycle_id, key.provider, key.account)
        if actual != expected:
            raise AuthorityIdentityMismatchError(
                "provider attempt key differs from authority cycle/provider/account"
            )

    def _attempt_count(self, logical_call_key: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM provider_attempts "
            "WHERE logical_call_key = ?",
            (logical_call_key,),
        ).fetchone()
        assert row is not None
        return int(row["count"])

    def _failure_count(self, now: float) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS count FROM provider_failure_events
            WHERE failed_at_epoch >= ?
            """,
            (now - self.policy.failure_window_seconds,),
        ).fetchone()
        assert row is not None
        return int(row["count"])

    def _committed_microusd(self) -> int:
        row = self._connection.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN status = 'settled' THEN actual_microusd
                    WHEN status IN ('failed_nonbillable', 'reconciled_unbilled') THEN 0
                    ELSE reservation_microusd
                END
            ), 0) AS committed
            FROM provider_attempts
            """
        ).fetchone()
        assert row is not None
        return int(row["committed"])

    def _lease_row(self, lease: AttemptLease) -> sqlite3.Row:
        if lease.authority_identity_sha256 != self.authority_identity_sha256:
            raise AttemptStateError("provider attempt authority identity differs")
        row = self._connection.execute(
            "SELECT * FROM provider_attempts WHERE attempt_id = ?",
            (lease.attempt_id,),
        ).fetchone()
        if row is None:
            raise AttemptStateError("provider attempt lease does not exist")
        expected = (
            lease.logical_call_key,
            lease.attempt_ordinal,
            lease.reservation_microusd,
        )
        actual = (
            str(row["logical_call_key"]),
            int(row["attempt_ordinal"]),
            int(row["reservation_microusd"]),
        )
        if actual != expected:
            raise AttemptStateError("provider attempt lease identity differs")
        return row

    def _lease_from_row(self, row: sqlite3.Row) -> AttemptLease:
        return AttemptLease(
            attempt_id=str(row["attempt_id"]),
            authority_identity_sha256=self.authority_identity_sha256,
            logical_call_key=str(row["logical_call_key"]),
            attempt_ordinal=int(row["attempt_ordinal"]),
            reservation_microusd=int(row["reservation_microusd"]),
        )

    def _is_poisoned(self) -> bool:
        row = self._connection.execute(
            "SELECT authority_poisoned FROM provider_spend_metadata WHERE singleton = 1"
        ).fetchone()
        assert row is not None
        return bool(int(row["authority_poisoned"]))

    def _raise_if_poisoned(self) -> None:
        if self._is_poisoned():
            raise AuthorityPoisonedError(
                "provider spend authority is poisoned by an integrity violation"
            )

    def _poison_authority(self, reason: str) -> None:
        self._connection.execute(
            "UPDATE provider_spend_metadata "
            "SET authority_poisoned = 1, poison_reason = ? WHERE singleton = 1",
            (_identity(reason, "poison_reason"),),
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _identity(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _sha256(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return normalized
