"""Durable provider-attempt journaling and cycle-wide spend reservations."""

from __future__ import annotations

import hashlib
import json
import math
import re
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
PROVIDER_JOURNAL_SCHEMA_VERSION = "legalforecast.provider_attempt_journal.v3"
_REPLAYABLE_RESPONSE_STATUSES = frozenset(
    {"settled", "reconstruction_failed", "validated_response", "response_received"}
)
_PROVIDER_CAP_KEYS = frozenset(
    {
        "provider",
        "account",
        "cycle_reservation_cap_usd",
        "external_spend_limit_usd",
        "external_limit_scope",
        "external_limit_source",
        "verified_at",
    }
)
_SPEND_AUTHORITY_KEYS = frozenset(
    {
        "backend",
        "resource_identity_sha256",
        "ledger_scope_fields",
        "max_billable_attempts",
        "failure_threshold",
        "failure_window_seconds",
    }
)
_PUBLIC_ACCOUNT_ALIAS = re.compile(r"[a-z](?:[a-z0-9-]{0,30}[a-z0-9])?\Z")
_CREDENTIAL_ALIAS_PREFIXES = (
    "aida",
    "akia",
    "aroa",
    "asia",
    "eyj",
    "ghp-",
    "github-pat-",
    "pk-",
    "sk-",
    "xox",
)
_CREDENTIAL_ALIAS_SEGMENTS = frozenset(
    {"credential", "key", "password", "secret", "token"}
)


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
    account: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderSpendAuthorityPolicy:
    """Pre-labeling commitment to the shared remote spend authority."""

    backend: str
    resource_identity_sha256: str
    ledger_scope_fields: tuple[str, ...]
    max_billable_attempts: int
    failure_threshold: int
    failure_window_seconds: int


@dataclass(frozen=True, slots=True)
class ProviderCycleCaps:
    """Frozen per-provider caps consumed by paid LLM acquisition stages."""

    cycle_id: str
    providers: Mapping[str, ProviderCycleCap]
    spend_authority: ProviderSpendAuthorityPolicy | None = None

    def cap_usd(self, provider: str) -> float:
        return float(self._provider(provider).cycle_reservation_cap_usd)

    def cap_microusd(self, provider: str) -> int:
        """Return the exact integer micro-USD cap used by the remote ledger."""

        cap = self._provider(provider).cycle_reservation_cap_usd * Decimal(1_000_000)
        integral = cap.to_integral_value()
        if cap != integral:
            raise ProviderJournalError(
                f"provider cycle cap for {provider!r} is finer than one micro-USD"
            )
        return int(integral)

    def account(self, provider: str) -> str:
        """Return the public account alias committed before paid labeling."""

        cap = self._provider(provider)
        if cap.account is None:
            raise ProviderJournalError(
                f"provider cycle caps entry for {provider!r} lacks account alias"
            )
        return cap.account

    def require_spend_authority(self) -> ProviderSpendAuthorityPolicy:
        """Return the remote policy or fail closed for a legacy caps artifact."""

        if self.spend_authority is None:
            raise ProviderJournalError(
                "provider cycle caps artifact lacks spend_authority"
            )
        return self.spend_authority

    def execution_attempt_policy(self, reservation_ledger_sha256: str) -> JsonRecord:
        """Render the exact at-freeze policy bound to this pre-labeling ledger."""

        ledger_sha256 = _sha256_digest(
            reservation_ledger_sha256,
            "reservation_ledger_sha256",
        )
        authority = self.require_spend_authority()
        return {
            "authority_backend": authority.backend,
            "authority_resource_identity_sha256": (authority.resource_identity_sha256),
            "ledger_scope_fields": list(authority.ledger_scope_fields),
            "provider_account_caps": [
                {
                    "provider": provider,
                    "account": self.account(provider),
                    "cap_microusd": self.cap_microusd(provider),
                }
                for provider in sorted(self.providers)
            ],
            "reservation_ledger_sha256": ledger_sha256,
            "max_billable_attempts": authority.max_billable_attempts,
            "failure_threshold": authority.failure_threshold,
            "failure_window_seconds": authority.failure_window_seconds,
        }

    def _provider(self, provider: str) -> ProviderCycleCap:
        try:
            cap = self.providers[provider.lower()]
        except KeyError as exc:
            raise ProviderJournalError(
                f"provider cycle caps artifact has no entry for {provider!r}"
            ) from exc
        return cap


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
    _exact_schema_keys(
        payload,
        required={"schema_version", "cycle_id", "providers"},
        optional={"spend_authority"},
        label="artifact",
    )
    if payload.get("schema_version") != PROVIDER_CYCLE_CAPS_SCHEMA_VERSION:
        raise ProviderJournalError(
            "provider cycle caps artifact has unsupported schema_version"
        )
    cycle_id = _required_nonempty_string(payload, "cycle_id")
    spend_authority = _load_spend_authority(payload.get("spend_authority"))
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
        _exact_schema_keys(
            raw,
            required=_PROVIDER_CAP_KEYS - {"account"},
            optional={"account"},
            label=f"providers[{index}]",
        )
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
            account=(
                _public_account_alias(raw, "account") if "account" in raw else None
            ),
        )
    return ProviderCycleCaps(
        cycle_id=cycle_id,
        providers=providers,
        spend_authority=spend_authority,
    )


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
            status = str(row["status"])
            if raw_response is not None and status in _REPLAYABLE_RESPONSE_STATUSES:
                loaded = json.loads(str(raw_response))
                if not isinstance(loaded, dict):
                    raise ProviderJournalError(
                        "journaled provider response is not an object"
                    )
                return cast(dict[str, object], loaded)
            if status in {
                "failed",
                "ambiguous",
                "reserved",
            }:
                durable_ordinal = self._next_attempt_ordinal()
                self._durable_ordinals[attempt_ordinal] = durable_ordinal
                self._reserve(durable_ordinal)
            else:
                raise ProviderJournalError(
                    f"provider attempt {durable_ordinal} has no replayable response "
                    f"and status {status}"
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

    def adopt_attempt(
        self,
        local_ordinal: int,
        *,
        durable_attempt_ordinal: int | None = None,
    ) -> None:
        """Bind a restarted process to its replayable local response identity."""

        durable_ordinal = self._durable_ordinal(local_ordinal)
        if (
            durable_attempt_ordinal is not None
            and durable_attempt_ordinal != durable_ordinal
        ):
            raise ProviderJournalError("provider journal attempt binding differs")
        row = self._attempt(durable_ordinal)
        if row is None or row["raw_response_json"] is None:
            raise ProviderJournalError(
                "provider journal has no replayable attempt to adopt"
            )
        self._validate_replay(row)

    def bind_authority_attempt(
        self,
        local_ordinal: int,
        authority_attempt_ordinal: int,
    ) -> None:
        """Persist the exact shared-authority attempt before the raw response."""

        if (
            isinstance(authority_attempt_ordinal, bool)
            or authority_attempt_ordinal <= 0
        ):
            raise ProviderJournalError(
                "authority_attempt_ordinal must be a positive integer"
            )
        durable_ordinal = self._durable_ordinal(local_ordinal)
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET authority_attempt_ordinal = ?
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                  AND status = 'reserved'
                  AND (authority_attempt_ordinal IS NULL
                       OR authority_attempt_ordinal = ?)
                """,
                (
                    authority_attempt_ordinal,
                    self.identity.logical_call_key,
                    durable_ordinal,
                    authority_attempt_ordinal,
                ),
            )
            if cursor.rowcount == 1:
                return
            row = self._attempt(durable_ordinal)
            if row is None:
                raise ProviderJournalError(
                    f"provider attempt {durable_ordinal} does not exist"
                )
            raise ProviderJournalError(
                "provider journal cannot bind the shared authority attempt from "
                f"status {row['status']}"
            )

    def authority_attempt_ordinal(self, local_ordinal: int) -> int:
        """Return the exact shared-authority attempt persisted with a response."""

        durable_ordinal = self._durable_ordinal(local_ordinal)
        row = self._attempt(durable_ordinal)
        if row is None or row["raw_response_json"] is None:
            raise ProviderJournalError(
                "provider journal has no replayable authority attempt binding"
            )
        self._validate_replay(row)
        value = row["authority_attempt_ordinal"]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ProviderJournalError(
                "provider journal replay lacks an exact authority attempt binding"
            )
        return value

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
        normalized_json = _canonical_json(normalized)
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
                    normalized_json,
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
            if row["status"] == "reconstruction_failed":
                actual = (
                    row["normalized_response_json"],
                    row["input_tokens"],
                    row["output_tokens"],
                    row["actual_cost_usd"],
                )
                expected = (
                    normalized_json,
                    input_tokens,
                    output_tokens,
                    actual_cost_usd,
                )
                if actual == expected:
                    return
                raise ProviderJournalError(
                    "reconstruction-failed provider accounting evidence changed"
                )
            raise ProviderJournalError(
                f"provider attempt {durable_ordinal} cannot be settled from "
                f"status {row['status']}"
            )

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        """Retain a received response whose parsing or verification failed."""

        normalized_failure = _nonempty_identity(failure_type, "failure_type")
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'ambiguous', failure_type = ?, failure_message = ?,
                    completed_at = ?
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                  AND status = 'response_received'
                """,
                (
                    normalized_failure,
                    "provider response failed post-transport validation",
                    _now(),
                    self.identity.logical_call_key,
                    durable_attempt_ordinal,
                ),
            )
            if cursor.rowcount == 1:
                return
            row = self._attempt(durable_attempt_ordinal)
            if row is not None and row["status"] == "ambiguous":
                return
            raise ProviderJournalError(
                f"provider attempt {durable_attempt_ordinal} cannot record a "
                "post-response failure"
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
        """Terminalize a known-cost response that failed reconstruction."""

        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET status = 'reconstruction_failed',
                    failure_type = ?, failure_message = ?,
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
            FROM provider_attempts
            WHERE stage = ? AND status IN ('settled', 'reconstruction_failed')
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
                authority_attempt_ordinal INTEGER
                    CHECK (authority_attempt_ordinal > 0),
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
              AND status IN (
                  'settled', 'reconstruction_failed',
                  'validated_response', 'response_received'
              )
            ORDER BY CASE status
                         WHEN 'settled' THEN 0
                         WHEN 'reconstruction_failed' THEN 1
                         WHEN 'validated_response' THEN 2
                         ELSE 3
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
                    CASE WHEN status IN ('settled', 'reconstruction_failed')
                         THEN actual_cost_usd
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


def _exact_schema_keys(
    record: Mapping[str, object],
    *,
    required: set[str] | frozenset[str],
    optional: set[str] | frozenset[str],
    label: str,
) -> None:
    actual = set(record)
    allowed = set(required) | set(optional)
    missing = set(required) - actual
    unknown = actual - allowed
    if missing or unknown:
        raise ProviderJournalError(
            f"provider cycle caps {label} keys mismatch; "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )


def _public_account_alias(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str):
        raise ProviderJournalError(
            "provider cycle caps account must be a public account alias"
        )
    segments = frozenset(value.split("-"))
    credential_like = value.startswith(_CREDENTIAL_ALIAS_PREFIXES) or bool(
        segments & _CREDENTIAL_ALIAS_SEGMENTS
    )
    if (
        _PUBLIC_ACCOUNT_ALIAS.fullmatch(value) is None
        or re.search(r"\d{12}", value) is not None
        or credential_like
    ):
        raise ProviderJournalError(
            "provider cycle caps account must be a public account alias"
        )
    return value


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


def _load_spend_authority(value: object) -> ProviderSpendAuthorityPolicy | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ProviderJournalError(
            "provider cycle caps spend_authority must be an object"
        )
    record = cast(Mapping[str, object], value)
    _exact_schema_keys(
        record,
        required=_SPEND_AUTHORITY_KEYS,
        optional=set(),
        label="spend_authority",
    )
    backend = _required_nonempty_string(record, "backend").lower()
    if backend != "dynamodb":
        raise ProviderJournalError(
            "provider cycle caps spend_authority backend must be dynamodb"
        )
    resource_identity = _required_nonempty_string(
        record, "resource_identity_sha256"
    ).lower()
    if len(resource_identity) != 64 or any(
        character not in "0123456789abcdef" for character in resource_identity
    ):
        raise ProviderJournalError(
            "provider cycle caps resource_identity_sha256 must be a lowercase "
            "SHA-256 digest"
        )
    raw_scope = record.get("ledger_scope_fields")
    if not isinstance(raw_scope, list):
        raise ProviderJournalError(
            "provider cycle caps ledger_scope_fields must be a string array"
        )
    raw_scope_values = cast(list[object], raw_scope)
    if not all(isinstance(field, str) and field.strip() for field in raw_scope_values):
        raise ProviderJournalError(
            "provider cycle caps ledger_scope_fields must be a string array"
        )
    scope = tuple(cast(list[str], raw_scope_values))
    if scope != ("cycle_id", "provider", "account"):
        raise ProviderJournalError(
            "provider cycle caps spend_authority must share one ledger across stages"
        )
    return ProviderSpendAuthorityPolicy(
        backend=backend,
        resource_identity_sha256=resource_identity,
        ledger_scope_fields=scope,
        max_billable_attempts=_positive_integer(record, "max_billable_attempts"),
        failure_threshold=_positive_integer(record, "failure_threshold"),
        failure_window_seconds=_positive_integer(record, "failure_window_seconds"),
    )


def _positive_integer(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProviderJournalError(
            f"provider cycle caps {field} must be a positive integer"
        )
    return value


def _sha256_digest(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ProviderJournalError(
            f"provider cycle caps {field} must be a lowercase SHA-256 digest"
        )
    return normalized


def _now() -> str:
    return datetime.now(UTC).isoformat()
