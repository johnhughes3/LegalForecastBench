"""Durable provider-attempt journaling and cycle-wide spend reservations."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from legalforecast.evals.live_model_solver import LiveModelProviderError

JsonRecord = Mapping[str, object]
DEFAULT_CYCLE_PROVIDER_CAP_USD = 1_000.0
PROVIDER_CYCLE_CAPS_SCHEMA_VERSION = "legalforecast.provider_cycle_caps.v1"
PROVIDER_JOURNAL_SCHEMA_VERSION = "legalforecast.provider_attempt_journal.v2"


class ProviderJournalError(RuntimeError):
    """Base error for provider journaling and reservation failures."""


class ProviderBudgetExceededError(ProviderJournalError):
    """Raised before a provider attempt would exceed its frozen cycle cap."""


class ProviderJournalReplayMismatchError(ProviderJournalError):
    """Raised when a logical call is replayed with different frozen inputs."""


@dataclass(frozen=True, slots=True)
class ProviderCycleCap:
    """One externally bounded provider reservation cap for an official cycle."""

    provider: str
    cycle_reservation_cap_usd: Decimal
    external_spend_limit_usd: Decimal
    external_limit_scope: str
    external_limit_source: str
    verified_at: str


@dataclass(frozen=True, slots=True)
class ProviderCycleCaps:
    """Frozen per-provider caps consumed by paid LLM acquisition stages."""

    cycle_id: str
    providers: Mapping[str, ProviderCycleCap]

    def cap_usd(self, provider: str) -> float:
        try:
            cap = self.providers[provider.lower()]
        except KeyError as exc:
            raise ProviderJournalError(
                f"provider cycle caps artifact has no entry for {provider!r}"
            ) from exc
        return float(cap.cycle_reservation_cap_usd)


@dataclass(frozen=True, slots=True)
class ProviderJournalIdentity:
    """Authenticated identity stored inside one canonical cycle journal."""

    schema_version: str
    cycle_id: str
    provider_cycle_caps_sha256: str
    canonical_path: str


def verify_provider_journal_identity(
    path: str | Path,
    *,
    cycle_id: str,
    provider_cycle_caps_sha256: str,
) -> ProviderJournalIdentity:
    """Read and verify a journal's immutable cycle, caps, and path identity."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ProviderJournalError(f"provider journal is not a regular file: {source}")
    try:
        with sqlite3.connect(source) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT schema_version, cycle_id, provider_cycle_caps_sha256, "
                "canonical_path FROM provider_journal_metadata"
            ).fetchall()
    except sqlite3.Error as exc:
        raise ProviderJournalError(
            f"cannot read provider journal identity: {exc}"
        ) from exc
    if len(rows) != 1:
        raise ProviderJournalReplayMismatchError(
            "provider journal must contain exactly one authenticated identity"
        )
    row = rows[0]
    identity = ProviderJournalIdentity(
        schema_version=str(row["schema_version"]),
        cycle_id=str(row["cycle_id"]),
        provider_cycle_caps_sha256=str(row["provider_cycle_caps_sha256"]),
        canonical_path=str(row["canonical_path"]),
    )
    if identity.schema_version != PROVIDER_JOURNAL_SCHEMA_VERSION:
        raise ProviderJournalReplayMismatchError(
            "provider journal schema identity differs"
        )
    if identity.cycle_id != _nonempty_identity(cycle_id, "cycle_id"):
        raise ProviderJournalReplayMismatchError(
            "provider journal cycle identity differs"
        )
    if identity.provider_cycle_caps_sha256 != _nonempty_identity(
        provider_cycle_caps_sha256, "provider_cycle_caps_sha256"
    ):
        raise ProviderJournalReplayMismatchError(
            "provider journal caps artifact identity differs"
        )
    if Path(identity.canonical_path) != source.resolve():
        raise ProviderJournalReplayMismatchError(
            "provider journal canonical path differs"
        )
    return identity


def load_provider_cycle_caps(path: str | Path) -> ProviderCycleCaps:
    """Load and fail-closed validate an externally bounded caps artifact."""

    source = Path(path)
    try:
        loaded: object = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderJournalError(
            f"cannot load provider cycle caps artifact {source}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ProviderJournalError("provider cycle caps artifact must be a JSON object")
    payload = cast(Mapping[str, object], loaded)
    if payload.get("schema_version") != PROVIDER_CYCLE_CAPS_SCHEMA_VERSION:
        raise ProviderJournalError(
            "provider cycle caps artifact has unsupported schema_version"
        )
    cycle_id = _required_nonempty_string(payload, "cycle_id")
    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        raise ProviderJournalError(
            "provider cycle caps artifact providers must be a non-empty array"
        )
    providers: dict[str, ProviderCycleCap] = {}
    for index, raw_value in enumerate(cast(list[object], raw_providers)):
        if not isinstance(raw_value, dict):
            raise ProviderJournalError(f"providers[{index}] must be an object")
        raw = cast(Mapping[str, object], raw_value)
        provider = _required_nonempty_string(raw, "provider").lower()
        if provider in providers:
            raise ProviderJournalError(f"duplicate provider cap for {provider!r}")
        cap = _positive_decimal(raw, "cycle_reservation_cap_usd")
        external_limit = _positive_decimal(raw, "external_spend_limit_usd")
        if cap > external_limit:
            raise ProviderJournalError(
                f"provider {provider!r} cycle reservation cap {cap} exceeds "
                f"documented external spend limit {external_limit}"
            )
        verified_at = _required_nonempty_string(raw, "verified_at")
        try:
            datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProviderJournalError(
                f"provider {provider!r} verified_at must be ISO 8601"
            ) from exc
        providers[provider] = ProviderCycleCap(
            provider=provider,
            cycle_reservation_cap_usd=cap,
            external_spend_limit_usd=external_limit,
            external_limit_scope=_required_nonempty_string(raw, "external_limit_scope"),
            external_limit_source=_required_nonempty_string(
                raw, "external_limit_source"
            ),
            verified_at=verified_at,
        )
    return ProviderCycleCaps(cycle_id=cycle_id, providers=providers)


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
        cycle_id: str,
        provider_cycle_caps_sha256: str,
    ) -> None:
        if reservation_usd < 0 or cycle_cap_usd <= 0:
            raise ValueError(
                "cycle cap must be positive and provider reservation must be "
                "non-negative"
            )
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.canonical_path = self.path.resolve()
        self.cycle_id = _nonempty_identity(cycle_id, "cycle_id")
        self.provider_cycle_caps_sha256 = _nonempty_identity(
            provider_cycle_caps_sha256, "provider_cycle_caps_sha256"
        )
        self.identity = identity
        self.provider = provider
        self.reservation_usd = reservation_usd
        self.cycle_cap_usd = cycle_cap_usd
        self._durable_ordinals: dict[int, int] = {}
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._create_schema()
            self._ensure_journal_identity()
            self._ensure_ledger()
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
            if row["status"] in {"failed", "ambiguous", "reserved"}:
                durable_ordinal = self._next_attempt_ordinal()
                self._durable_ordinals[attempt_ordinal] = durable_ordinal
                self._reserve(durable_ordinal)
            else:
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
        except Exception as exc:
            self._record_ambiguous_failure(durable_ordinal, exc)
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
            "actual_cost_usd": actual_cost_usd,
        }
        with self._connection:
            cursor = self._connection.execute(
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
            if cursor.rowcount == 1:
                return
            row = self._attempt(durable_ordinal)
            if row is None:
                raise ProviderJournalError(
                    f"provider attempt {durable_ordinal} does not exist"
                )
            if row["status"] == "settled":
                return
            raise ProviderJournalError(
                f"provider attempt {durable_ordinal} cannot be settled from "
                f"status {row['status']}"
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

    def record_reconstruction_failure(self, error: Exception) -> None:
        """Terminalize a paid response that failed deterministic reconstruction."""

        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'ambiguous', failure_type = ?, failure_message = ?,
                    completed_at = ?
                WHERE logical_call_key = ? AND status = 'validated_response'
                """,
                (
                    type(error).__name__,
                    str(error),
                    _now(),
                    self.identity.logical_call_key,
                ),
            )
            if cursor.rowcount != 1:
                raise ProviderJournalError(
                    "reconstruction failure requires exactly one validated response"
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
            CREATE TABLE IF NOT EXISTS provider_journal_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                provider_cycle_caps_sha256 TEXT NOT NULL,
                canonical_path TEXT NOT NULL
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

    def _ensure_journal_identity(self) -> None:
        expected = (
            PROVIDER_JOURNAL_SCHEMA_VERSION,
            self.cycle_id,
            self.provider_cycle_caps_sha256,
            str(self.canonical_path),
        )
        with self._connection:
            row = self._connection.execute(
                "SELECT schema_version, cycle_id, provider_cycle_caps_sha256, "
                "canonical_path FROM provider_journal_metadata WHERE singleton = 1"
            ).fetchone()
            if row is None:
                attempt_count = self._connection.execute(
                    "SELECT COUNT(*) AS count FROM provider_attempts"
                ).fetchone()
                assert attempt_count is not None
                if int(attempt_count["count"]) != 0:
                    raise ProviderJournalReplayMismatchError(
                        "existing provider journal lacks authenticated cycle identity"
                    )
                self._connection.execute(
                    "INSERT INTO provider_journal_metadata("
                    "singleton, schema_version, cycle_id, "
                    "provider_cycle_caps_sha256, canonical_path) "
                    "VALUES (1, ?, ?, ?, ?)",
                    expected,
                )
                return
            actual = tuple(row[key] for key in row.keys())
            if actual[0] != expected[0]:
                raise ProviderJournalReplayMismatchError(
                    "provider journal schema identity differs"
                )
            if actual[1] != expected[1]:
                raise ProviderJournalReplayMismatchError(
                    "provider journal cycle identity differs"
                )
            if actual[2] != expected[2]:
                raise ProviderJournalReplayMismatchError(
                    "provider journal caps artifact identity differs"
                )
            if actual[3] != expected[3]:
                raise ProviderJournalReplayMismatchError(
                    "provider journal canonical path differs"
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
            if not math.isclose(
                float(row["cycle_cap_usd"]),
                self.cycle_cap_usd,
                rel_tol=1e-9,
                abs_tol=1e-12,
            ):
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

    def _record_ambiguous_failure(self, attempt_ordinal: int, error: Exception) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'ambiguous', failure_type = ?, failure_message = ?,
                    completed_at = ?
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                """,
                (
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


def _required_nonempty_string(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProviderJournalError(f"provider cycle caps {field} must be non-empty")
    return value.strip()


def _nonempty_identity(value: str, field: str) -> str:
    if not value.strip():
        raise ValueError(f"provider journal {field} must be non-empty")
    return value.strip()


def _positive_decimal(record: Mapping[str, object], field: str) -> Decimal:
    value = record.get(field)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ProviderJournalError(f"provider cycle caps {field} must be a decimal")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProviderJournalError(
            f"provider cycle caps {field} must be a decimal"
        ) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ProviderJournalError(f"provider cycle caps {field} must be positive")
    return parsed


def _now() -> str:
    return datetime.now(UTC).isoformat()
