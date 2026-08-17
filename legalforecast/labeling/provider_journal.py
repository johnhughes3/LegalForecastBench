"""Durable provider-attempt journaling and cycle-wide spend reservations."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import stat
import tempfile
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
_PROVIDER_JOURNAL_SIDECAR_SUFFIXES = ("-wal", "-journal")
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
class ReconstructionFailureEvidence:
    """Exact provider evidence for the latest recoverable reconstruction failure."""

    attempt_ordinal: int
    raw_response_json: str
    normalized_response_json: str


@dataclass(frozen=True, slots=True)
class RepeatedReconstructionFailureEvidence:
    """Two byte-identical failed reconstructions for one logical call.

    This is deliberately evidence only.  It neither settles an invalid provider
    response nor changes the attempt ledger; callers may use it only to build a
    provider-free human-review escalation.
    """

    attempts: tuple[ReconstructionFailureEvidence, ...]
    failure_type: str
    failure_message: str


@dataclass(frozen=True, slots=True)
class ExhaustedReconstructionFailureEvidence:
    """Three durable failed reconstructions at the fixed retry ceiling.

    Unlike the early two-attempt shortcut, the validator evidence may differ
    from attempt to attempt.  The evidence remains provider-free: it records
    every exhausted attempt for a later human-review escalation and never
    changes the journal.
    """

    attempts: tuple[ReconstructionFailureEvidence, ...]
    failure_types: tuple[str, ...]
    failure_messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderCycleCap:
    """One provider reservation cap plus optional legacy evidence annotations."""

    provider: str
    cycle_reservation_cap_usd: Decimal
    external_spend_limit_usd: Decimal | None
    external_limit_scope: str | None
    external_limit_source: str | None
    verified_at: str | None
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


def _provider_journal_durable_bytes(source: Path) -> tuple[bytes, dict[str, bytes]]:
    """Capture the journal database plus every durable sidecar it commits to.

    The volatile ``-shm`` index is deliberately excluded: SQLite rebuilds it
    from the WAL, and its read marks change whenever any other process merely
    reads the journal, so it is evidence of nothing.
    """

    try:
        main_payload = source.read_bytes()
        sidecars: dict[str, bytes] = {}
        for suffix in _PROVIDER_JOURNAL_SIDECAR_SUFFIXES:
            sidecar = Path(f"{source}{suffix}")
            try:
                status = sidecar.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(status.st_mode):
                raise ProviderJournalError(
                    f"provider journal sidecar is not a regular file: {sidecar}"
                )
            sidecars[suffix] = sidecar.read_bytes()
    except OSError as exc:
        raise ProviderJournalError(f"cannot read provider journal: {exc}") from exc
    return main_payload, sidecars


def open_provider_journal_snapshot(path: str | Path) -> sqlite3.Connection:
    """Return a query-only in-memory copy of one never-opened canonical journal.

    Opening the canonical journal with SQLite is not a non-writing read even
    for SELECT-only work: a read/write connection creates the ``-wal``/``-shm``
    sidecars, checkpoints committed WAL frames back into the database on close,
    and runs hot-journal recovery, while a ``mode=ro`` connection still leaves
    fresh sidecars behind.  Copying the database and its durable sidecars into
    a private scratch directory first means SQLite only ever opens the copy, so
    every authentication path that replays a journal is non-writing by
    construction rather than by SELECT-only convention.  The copy carries the
    sidecars because only SQLite can apply committed WAL frames, and it is
    removed before this returns.  The canonical bytes are re-read after the copy
    so a concurrent write fails closed instead of authenticating a torn
    snapshot.
    """

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ProviderJournalError(f"provider journal is not a regular file: {source}")
    durable_before = _provider_journal_durable_bytes(source)
    snapshot = sqlite3.connect(":memory:")
    try:
        with tempfile.TemporaryDirectory(prefix="lfb-provider-journal-") as scratch:
            replica_path = Path(scratch) / source.name
            main_payload, sidecars = durable_before
            try:
                replica_path.write_bytes(main_payload)
                for suffix, payload in sidecars.items():
                    Path(f"{replica_path}{suffix}").write_bytes(payload)
            except OSError as exc:
                raise ProviderJournalError(
                    f"cannot copy provider journal for reading: {exc}"
                ) from exc
            if _provider_journal_durable_bytes(source) != durable_before:
                raise ProviderJournalError(
                    f"provider journal changed while it was read: {source}"
                )
            replica: sqlite3.Connection | None = None
            try:
                replica = sqlite3.connect(replica_path, isolation_level=None)
                replica.backup(snapshot)
            except sqlite3.Error as exc:
                raise ProviderJournalError(
                    f"cannot read provider journal: {exc}"
                ) from exc
            finally:
                if replica is not None:
                    replica.close()
        snapshot.row_factory = sqlite3.Row
        snapshot.execute("PRAGMA query_only = ON")
    except BaseException:
        snapshot.close()
        raise
    return snapshot


def verify_provider_journal_identity(
    path: str | Path,
    *,
    cycle_id: str,
    provider_cycle_caps_sha256: str,
    snapshot: sqlite3.Connection | None = None,
) -> ProviderJournalIdentity:
    """Read and verify a journal's immutable cycle, caps, and path identity.

    ``snapshot`` reuses one already-open query-only journal copy so a caller
    can authenticate identity and attempt rows against the same journal state;
    without it this opens and closes its own snapshot.
    """

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ProviderJournalError(f"provider journal is not a regular file: {source}")
    connection = (
        snapshot if snapshot is not None else open_provider_journal_snapshot(source)
    )
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT schema_version, cycle_id, provider_cycle_caps_sha256, "
            "canonical_path FROM provider_journal_metadata"
        ).fetchall()
    except sqlite3.Error as exc:
        raise ProviderJournalError(
            f"cannot read provider journal identity: {exc}"
        ) from exc
    finally:
        if snapshot is None:
            connection.close()
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
    """Load and fail-closed validate provider cycle reservation caps."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise ProviderJournalError(
            f"cannot load provider cycle caps artifact {source}: {exc}"
        ) from exc
    return load_provider_cycle_caps_bytes(payload, source=source)


def load_provider_cycle_caps_bytes(
    payload: bytes, *, source: str | Path
) -> ProviderCycleCaps:
    """Validate provider caps from one caller-captured immutable byte snapshot."""

    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderJournalError(
            f"cannot load provider cycle caps artifact {source}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ProviderJournalError("provider cycle caps artifact must be a JSON object")
    record = cast(Mapping[str, object], loaded)
    _exact_schema_keys(
        record,
        required={"schema_version", "cycle_id", "providers"},
        optional={"spend_authority"},
        label="artifact",
    )
    if record.get("schema_version") != PROVIDER_CYCLE_CAPS_SCHEMA_VERSION:
        raise ProviderJournalError(
            "provider cycle caps artifact has unsupported schema_version"
        )
    cycle_id = _required_nonempty_string(record, "cycle_id")
    spend_authority = _load_spend_authority(record.get("spend_authority"))
    raw_providers = record.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        raise ProviderJournalError(
            "provider cycle caps artifact providers must be a non-empty array"
        )
    providers: dict[str, ProviderCycleCap] = {}
    for index, raw_value in enumerate(cast(list[object], raw_providers)):
        if not isinstance(raw_value, dict):
            raise ProviderJournalError(f"providers[{index}] must be an object")
        raw = cast(Mapping[str, object], raw_value)
        required_provider_keys = {"provider", "cycle_reservation_cap_usd"}
        _exact_schema_keys(
            raw,
            required=required_provider_keys,
            optional=_PROVIDER_CAP_KEYS - required_provider_keys,
            label=f"providers[{index}]",
        )
        provider = _required_nonempty_string(raw, "provider").lower()
        if provider in providers:
            raise ProviderJournalError(f"duplicate provider cap for {provider!r}")
        cap = _positive_decimal(raw, "cycle_reservation_cap_usd")
        external_limit = _optional_positive_decimal(raw, "external_spend_limit_usd")
        verified_at = _optional_nonempty_string(raw, "verified_at")
        if verified_at is not None:
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
            external_limit_scope=_optional_nonempty_string(raw, "external_limit_scope"),
            external_limit_source=_optional_nonempty_string(
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
    prompt_contract: str | None = None
    logical_call_scope: str | None = None

    @property
    def logical_call_key(self) -> str:
        parts = (self.stage, self.candidate_id, self.model_key)
        if self.prompt_contract is None:
            payload = "\0".join(parts)
        else:
            payload = "\0".join(
                (*parts, "stage-a-prompt-contract", self.prompt_contract)
            )
        if self.logical_call_scope is not None:
            payload = "\0".join(
                (payload, "provider-logical-call-scope", self.logical_call_scope)
            )
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt.encode()).hexdigest()


def provider_prompt_logical_call_scope(prompt: str) -> str:
    """Return the opt-in logical-call scope for one exact provider prompt."""

    return "prompt-sha256:" + hashlib.sha256(prompt.encode()).hexdigest()


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

    def prepare_reconstruction_retry(self, *, max_attempts: int) -> int:
        """Map retries past invalid reconstructed responses within a fixed limit.

        Reconstruction failures remain replayable by default so corrected local
        reconstruction code can reuse a valid provider response. Callers that
        require a fresh provider response must opt in here. Every existing
        journal attempt consumes the same fixed attempt allowance, and the
        returned value is the number of provider attempts still available.
        """

        if type(max_attempts) is not int or max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        rows = self._connection.execute(
            """
            SELECT attempt_ordinal, status, failure_type FROM provider_attempts
            WHERE logical_call_key = ?
            ORDER BY attempt_ordinal
            """,
            (self.identity.logical_call_key,),
        ).fetchall()
        recovered = next(
            (
                row
                for row in reversed(rows)
                if row["status"] == "settled" and row["failure_type"] is not None
            ),
            None,
        )
        if not any(row["status"] == "reconstruction_failed" for row in rows):
            if recovered is not None:
                self._durable_ordinals[1] = int(recovered["attempt_ordinal"])
                return 1
            return max_attempts
        replayable = next(
            (
                row
                for status in ("settled", "validated_response", "response_received")
                for row in reversed(rows)
                if row["status"] == status
            ),
            None,
        )
        if replayable is not None:
            self._durable_ordinals[1] = int(replayable["attempt_ordinal"])
            return 1
        remaining = max_attempts - len(rows)
        if remaining <= 0:
            raise ProviderJournalError(
                "provider reconstruction retry attempt limit is exhausted"
            )
        next_ordinal = max(int(row["attempt_ordinal"]) for row in rows) + 1
        for local_ordinal in range(1, remaining + 1):
            self._durable_ordinals[local_ordinal] = next_ordinal + local_ordinal - 1
        return remaining

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

        durable_ordinal = self._settlement_durable_ordinal(attempt_ordinal)
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

    def _settlement_durable_ordinal(self, attempt_ordinal: int) -> int:
        """Resolve either the local or already-durable ordinal used for settlement.

        The live solver settles the durable ordinal returned by
        :meth:`durable_attempt_ordinal`.  Reconstruction retry planning maps the
        remaining local attempts in advance, so a durable response ordinal can
        also be the *local* ordinal of a future attempt.  Prefer a value of an
        existing local-to-durable binding before consulting that future mapping;
        otherwise durable ordinal 2 would incorrectly settle planned ordinal 3.
        This stays correct after a response becomes reconstruction-failed,
        because durable identity is independent of its current status.
        """

        if attempt_ordinal in self._durable_ordinals.values():
            return attempt_ordinal
        return self._durable_ordinals.get(attempt_ordinal, attempt_ordinal)

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        """Retain a received response whose parsing or verification failed."""

        normalized_failure = _nonempty_identity(failure_type, "failure_type")
        failure_message = "provider response failed post-transport validation"
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
                    failure_message,
                    _now(),
                    self.identity.logical_call_key,
                    durable_attempt_ordinal,
                ),
            )
            if cursor.rowcount == 1:
                return
            row = self._attempt(durable_attempt_ordinal)
            if row is not None and row["status"] == "ambiguous":
                actual = (row["failure_type"], row["failure_message"])
                expected = (normalized_failure, failure_message)
                if actual == expected:
                    return
                raise ProviderJournalError(
                    "post-response failure evidence changed for provider attempt "
                    f"{durable_attempt_ordinal}"
                )
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

    def commit_reconstruction_recovery(
        self,
        durable_attempt_ordinal: int,
        *,
        raw_response_json: str,
        normalized_response_json: str,
        record: Mapping[str, object],
    ) -> None:
        """Settle a previously rejected response after provider-free revalidation.

        The caller must present the exact journaled provider envelope and normalized
        accounting record it revalidated. This transition never creates an attempt
        or changes captured provider/accounting evidence; it only adopts a corrected
        local reconstruction for that exact response.
        """

        if isinstance(durable_attempt_ordinal, bool) or durable_attempt_ordinal <= 0:
            raise ProviderJournalError(
                "reconstruction recovery attempt ordinal must be positive"
            )
        if not raw_response_json or not normalized_response_json:
            raise ProviderJournalError(
                "reconstruction recovery requires exact response evidence"
            )
        reconstructed_result_json = _canonical_json(record)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._attempt(durable_attempt_ordinal)
            if row is None:
                raise ProviderJournalError(
                    "reconstruction recovery attempt does not exist"
                )
            self._validate_replay(row)
            if (
                row["raw_response_json"] != raw_response_json
                or row["normalized_response_json"] != normalized_response_json
            ):
                raise ProviderJournalError(
                    "reconstruction recovery response evidence changed"
                )
            competing = self._connection.execute(
                """
                SELECT 1 FROM provider_attempts
                WHERE logical_call_key = ? AND attempt_ordinal != ?
                  AND status IN (
                      'settled', 'validated_response', 'response_received',
                      'reserved', 'ambiguous'
                  )
                LIMIT 1
                """,
                (self.identity.logical_call_key, durable_attempt_ordinal),
            ).fetchone()
            if competing is not None:
                raise ProviderJournalError(
                    "reconstruction recovery conflicts with another authoritative "
                    "response"
                )
            status = str(row["status"])
            if status == "settled":
                if row["reconstructed_result_json"] != reconstructed_result_json:
                    raise ProviderJournalError("reconstruction recovery result changed")
                self._connection.commit()
                return
            if status != "reconstruction_failed":
                raise ProviderJournalError(
                    "reconstruction recovery requires a failed reconstruction"
                )
            cursor = self._connection.execute(
                """
                UPDATE provider_attempts
                SET reconstructed_result_json = ?, status = 'settled'
                WHERE logical_call_key = ? AND attempt_ordinal = ?
                  AND status = 'reconstruction_failed'
                  AND raw_response_json = ? AND normalized_response_json = ?
                """,
                (
                    reconstructed_result_json,
                    self.identity.logical_call_key,
                    durable_attempt_ordinal,
                    raw_response_json,
                    normalized_response_json,
                ),
            )
            if cursor.rowcount != 1:
                raise ProviderJournalError(
                    "reconstruction recovery response evidence changed"
                )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def latest_reconstruction_recovery_evidence(
        self,
    ) -> ReconstructionFailureEvidence:
        """Return the latest failed or already-recovered response for replay."""

        rows = self._connection.execute(
            """
            SELECT attempt_ordinal, status, raw_response_json,
                   normalized_response_json, failure_type
            FROM provider_attempts
            WHERE logical_call_key = ?
            ORDER BY attempt_ordinal DESC
            """,
            (self.identity.logical_call_key,),
        ).fetchall()
        recoverable = next(
            (
                row
                for row in rows
                if row["status"] == "reconstruction_failed"
                or (row["status"] == "settled" and row["failure_type"] is not None)
            ),
            None,
        )
        if recoverable is None:
            raise ProviderJournalError(
                "provider journal has no failed reconstruction to recover"
            )
        if any(
            row["attempt_ordinal"] != recoverable["attempt_ordinal"]
            and row["status"]
            in {
                "settled",
                "validated_response",
                "response_received",
                "reserved",
                "ambiguous",
            }
            for row in rows
        ):
            raise ProviderJournalError(
                "reconstruction recovery conflicts with another authoritative response"
            )
        raw_response_json = recoverable["raw_response_json"]
        normalized_response_json = recoverable["normalized_response_json"]
        if not isinstance(raw_response_json, str) or not isinstance(
            normalized_response_json, str
        ):
            raise ProviderJournalError(
                "failed reconstruction lacks exact provider response evidence"
            )
        return ReconstructionFailureEvidence(
            attempt_ordinal=int(recoverable["attempt_ordinal"]),
            raw_response_json=raw_response_json,
            normalized_response_json=normalized_response_json,
        )

    def repeated_identical_reconstruction_failure_evidence(
        self,
        *,
        required_attempt_count: int = 2,
    ) -> RepeatedReconstructionFailureEvidence:
        """Return narrowly qualifying failed attempts without changing the ledger.

        An escalation is intentionally stricter than ordinary reconstruction
        recovery: it requires exactly two terminal reconstruction failures for
        the current, already-authenticated logical call; matching validator
        failure evidence; and byte-identical normalized response envelopes.
        Any different status, count, missing evidence, or changed identity
        remains a normal retry/fail-closed case.
        """

        if type(required_attempt_count) is not int or required_attempt_count < 2:
            raise ValueError("required_attempt_count must be an integer of at least 2")
        rows = self._connection.execute(
            """
            SELECT *
            FROM provider_attempts
            WHERE logical_call_key = ?
            ORDER BY attempt_ordinal
            """,
            (self.identity.logical_call_key,),
        ).fetchall()
        if len(rows) != required_attempt_count or any(
            row["status"] != "reconstruction_failed" for row in rows
        ):
            raise ProviderJournalError(
                "terminal escalation requires exactly repeated failed reconstructions"
            )
        for row in rows:
            self._validate_replay(row)
        normalized = rows[0]["normalized_response_json"]
        failure_type = rows[0]["failure_type"]
        failure_message = rows[0]["failure_message"]
        if (
            not isinstance(normalized, str)
            or not isinstance(failure_type, str)
            or not failure_type
            or not isinstance(failure_message, str)
            or not failure_message
            or any(
                row["normalized_response_json"] != normalized
                or row["failure_type"] != failure_type
                or row["failure_message"] != failure_message
                or row["reconstructed_result_json"] is not None
                or not isinstance(row["raw_response_json"], str)
                for row in rows
            )
        ):
            raise ProviderJournalError(
                "terminal escalation requires byte-identical normalized failure "
                "evidence"
            )
        return RepeatedReconstructionFailureEvidence(
            attempts=tuple(
                ReconstructionFailureEvidence(
                    attempt_ordinal=int(row["attempt_ordinal"]),
                    raw_response_json=cast(str, row["raw_response_json"]),
                    normalized_response_json=cast(str, row["normalized_response_json"]),
                )
                for row in rows
            ),
            failure_type=failure_type,
            failure_message=failure_message,
        )

    def exhausted_reconstruction_failure_evidence(
        self,
    ) -> ExhaustedReconstructionFailureEvidence:
        """Return exactly three failed attempts at the normal retry ceiling.

        This deliberately does not accept a fourth provider attempt, nor does
        it relax the narrower two-identical shortcut.  All three journal rows
        must still replay to the current frozen logical-call identity and carry
        their own complete raw, normalized, and validator-failure evidence.
        """

        rows = self._connection.execute(
            """
            SELECT *
            FROM provider_attempts
            WHERE logical_call_key = ?
            ORDER BY attempt_ordinal
            """,
            (self.identity.logical_call_key,),
        ).fetchall()
        if len(rows) != 3 or any(
            int(row["attempt_ordinal"]) != ordinal
            or row["status"] != "reconstruction_failed"
            for ordinal, row in enumerate(rows, start=1)
        ):
            raise ProviderJournalError(
                "terminal escalation requires exactly three exhausted failed "
                "reconstructions"
            )
        for row in rows:
            self._validate_replay(row)
        first, second = rows[:2]
        if (
            isinstance(first["normalized_response_json"], str)
            and isinstance(first["failure_type"], str)
            and bool(first["failure_type"])
            and isinstance(first["failure_message"], str)
            and bool(first["failure_message"])
            and first["normalized_response_json"] == second["normalized_response_json"]
            and first["failure_type"] == second["failure_type"]
            and first["failure_message"] == second["failure_message"]
            and first["reconstructed_result_json"] is None
            and second["reconstructed_result_json"] is None
            and isinstance(first["raw_response_json"], str)
            and isinstance(second["raw_response_json"], str)
        ):
            raise ProviderJournalError(
                "terminal escalation rejects a third attempt after the early "
                "two-identical route qualified"
            )
        if any(
            row["reconstructed_result_json"] is not None
            or not isinstance(row["raw_response_json"], str)
            or not cast(str, row["raw_response_json"])
            or not isinstance(row["normalized_response_json"], str)
            or not cast(str, row["normalized_response_json"])
            or not isinstance(row["failure_type"], str)
            or not cast(str, row["failure_type"])
            or not isinstance(row["failure_message"], str)
            or not cast(str, row["failure_message"])
            for row in rows
        ):
            raise ProviderJournalError(
                "terminal escalation requires complete exhausted failure evidence"
            )
        return ExhaustedReconstructionFailureEvidence(
            attempts=tuple(
                ReconstructionFailureEvidence(
                    attempt_ordinal=int(row["attempt_ordinal"]),
                    raw_response_json=cast(str, row["raw_response_json"]),
                    normalized_response_json=cast(str, row["normalized_response_json"]),
                )
                for row in rows
            ),
            failure_types=tuple(cast(str, row["failure_type"]) for row in rows),
            failure_messages=tuple(cast(str, row["failure_message"]) for row in rows),
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

    @property
    def has_reconstruction_failure(self) -> bool:
        """Return whether this call has an exact response eligible for recovery."""

        row = self._connection.execute(
            """SELECT COUNT(*) AS count FROM provider_attempts
            WHERE logical_call_key = ? AND status = 'reconstruction_failed'""",
            (self.identity.logical_call_key,),
        ).fetchone()
        assert row is not None
        return int(row["count"]) > 0

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
            settled = self._connection.execute(
                """
                SELECT 1 FROM provider_attempts
                WHERE logical_call_key = ? AND status = 'settled'
                LIMIT 1
                """,
                (self.identity.logical_call_key,),
            ).fetchone()
            if settled is not None:
                raise ProviderJournalError(
                    "provider call already has an authoritative settled response"
                )
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


def _optional_nonempty_string(record: Mapping[str, object], field: str) -> str | None:
    if field not in record:
        return None
    return _required_nonempty_string(record, field)


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


def _optional_positive_decimal(
    record: Mapping[str, object], field: str
) -> Decimal | None:
    if field not in record:
        return None
    return _positive_decimal(record, field)


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
