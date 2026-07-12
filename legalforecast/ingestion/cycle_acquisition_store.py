"""Durable, resumable state for one LegalForecastBench acquisition cycle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermProgress,
    TermTerminalStatus,
)

SCHEMA_VERSION = "legalforecast-cycle-acquisition-v1"
_SOURCE_NEUTRAL_POLICY_SCHEMA = "legalforecast.cycle_acquisition_policy.v1"
_LEGACY_SOURCE_POLICY_SCHEMAS = frozenset(
    {
        "legalforecast.case_dev_discovery_policy.v1",
        "legalforecast.firecrawl_recap_discovery_policy.v1",
    }
)
_IMMUTABLE_REASON_CODES = frozenset(
    {
        "decision_before_release_anchor",
        "bankruptcy_court",
        "not_federal_district_court",
        "missing_docket_number",
        "placeholder_or_sealed_docket_number",
        "not_civil_cv_docket",
        "criminal_style_caption",
        "non_civil_case",
        "non_civil_metadata",
        "criminal_case",
        "bankruptcy_case",
        "administrative_case",
        "appellate_case",
        "missing_civil_case_metadata",
        "invalid_civil_case_metadata",
    }
)
_EVIDENCED_STATES = frozenset({"accepted", "newly_free", "excluded"})
_OBSERVATION_STATES = _EVIDENCED_STATES | frozenset(
    {"transient_failure", "skipped_immutable"}
)
_SNAPSHOT_FILES = (
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
)
_SAFE_SNAPSHOT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_REASON_POLICIES: dict[str, tuple[frozenset[str], str, int]] = {
    **{
        reason: (frozenset({"excluded"}), "immutable", 100)
        for reason in _IMMUTABLE_REASON_CODES
    },
    "strict_clean_screen_failed": (frozenset({"excluded"}), "refreshable", 10),
    "bankruptcy_posture": (frozenset({"excluded"}), "refreshable", 10),
    "criminal_posture": (frozenset({"excluded"}), "refreshable", 10),
    "habeas_or_immigration_detention_posture": (
        frozenset({"excluded"}),
        "refreshable",
        10,
    ),
    "strict_clean_screen_passed": (frozenset({"accepted"}), "accepted", 20),
    "required_documents_complete": (frozenset({"accepted"}), "accepted", 20),
    "newly_free": (frozenset({"newly_free"}), "newly_free", 30),
    "required_documents_newly_free": (
        frozenset({"newly_free"}),
        "newly_free",
        30,
    ),
    "fetch_error": (frozenset({"transient_failure"}), "transient", 0),
    "parse_failure": (frozenset({"transient_failure"}), "transient", 0),
    "temporarily_unavailable": (
        frozenset({"transient_failure"}),
        "transient",
        0,
    ),
    "courtlistener_docket_unavailable": (
        frozenset({"transient_failure"}),
        "transient",
        0,
    ),
    "courtlistener_docket_html_unavailable": (
        frozenset({"transient_failure"}),
        "transient",
        0,
    ),
    "case_dev_provider_blocker": (
        frozenset({"transient_failure"}),
        "transient",
        0,
    ),
    "firecrawl_provider_blocker": (
        frozenset({"transient_failure"}),
        "transient",
        0,
    ),
}


class CycleAcquisitionStoreError(RuntimeError):
    """Base class for durable acquisition-state errors."""


class StoreLockedError(CycleAcquisitionStoreError):
    """Raised when another writer already owns the cycle store."""


class ConfigMismatchError(CycleAcquisitionStoreError):
    """Raised when resumed work does not match its frozen configuration."""


class PageReplayMismatchError(CycleAcquisitionStoreError):
    """Raised when a cursor is reused with non-identical page content."""


class ImmutableCandidateStateError(CycleAcquisitionStoreError):
    """Raised when an immutable exclusion is improperly reconsidered."""


class ImmutableArtifactError(CycleAcquisitionStoreError):
    """Raised when content conflicts with a committed raw artifact."""


class SnapshotVerificationError(CycleAcquisitionStoreError):
    """Raised when a snapshot is partial, mismatched, or corrupt."""


class FirecrawlBudgetExceededError(CycleAcquisitionStoreError):
    """Raised before a request that could exceed the frozen cycle credit cap."""


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    """One append-only candidate-state observation."""

    observation_id: int
    candidate_id: str
    batch_id: str
    state: str
    reason_code: str
    evidence: Mapping[str, Any]
    observed_at: str
    supersedes_observation_id: int | None


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """A content commitment for one atomically published raw artifact."""

    artifact_id: int
    candidate_id: str
    path: Path
    sha256: str
    byte_count: int
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class FirecrawlAttempt:
    """One permanently reserved Firecrawl request attempt."""

    attempt_id: int
    run_id: str
    target_id: str
    page_number: int
    attempt_number: int
    request_url: str
    reserved_credits: int
    status: str
    reported_credits: int | None
    proxy_used: str | None
    provider_http_status: int | None
    target_http_status: int | None
    failure_code: str | None
    failure_message: str | None
    failure_transient: bool | None
    failure_response_sha256: str | None
    artifact_path: Path | None
    artifact_sha256: str | None
    artifact_byte_count: int | None
    authorized_at: str
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class FirecrawlTarget:
    """One immutable Firecrawl URL target within a frozen run."""

    run_id: str
    target_id: str
    target_kind: str
    source_url: str
    ordinal: int
    status: str


class CycleAcquisitionStore:
    """Single-writer SQLite store for resumable cycle acquisition."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = Path(f"{self.path}.lock")
        self._lock_fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(self._lock_fd)
            raise StoreLockedError(
                f"cycle store is already locked: {self.path}"
            ) from error
        try:
            _trim_torn_wal_tail(self.path)
            self._connection = sqlite3.connect(self.path, isolation_level=None)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=0")
            self._create_schema()
            integrity = self._connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise CycleAcquisitionStoreError(
                    f"SQLite integrity check failed for {self.path}: {integrity!r}"
                )
        except BaseException:
            os.close(self._lock_fd)
            raise
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close SQLite and release the process-lifetime writer lock."""

        if self._closed:
            return
        self._connection.close()
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._closed = True

    @property
    def cycle_hash(self) -> str:
        """Return the frozen cycle-policy hash."""

        row = self._connection.execute(
            "SELECT policy_hash FROM cycle_identity WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise CycleAcquisitionStoreError("cycle policy has not been initialized")
        return str(row[0])

    @property
    def cycle_policy(self) -> Mapping[str, object]:
        """Return a detached copy of the frozen cycle policy."""

        row = self._connection.execute(
            "SELECT policy_json FROM cycle_identity WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise CycleAcquisitionStoreError("cycle policy has not been initialized")
        parsed = cast(object, json.loads(row[0]))
        if not isinstance(parsed, dict):
            raise CycleAcquisitionStoreError("stored cycle policy is not an object")
        return dict(cast(dict[str, object], parsed))

    def ensure_cycle(self, policy: Mapping[str, object]) -> str:
        """Freeze or validate the canonical cycle-policy identity."""

        policy_json = _canonical_json(policy)
        policy_hash = _sha256_text(
            _canonical_json({"schema_version": SCHEMA_VERSION, "policy": policy})
        )
        with self._transaction():
            row = self._connection.execute(
                """
                SELECT schema_version, policy_json, policy_hash
                FROM cycle_identity WHERE singleton = 1
                """
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO cycle_identity(
                        singleton, schema_version, policy_json, policy_hash, created_at
                    ) VALUES(1, ?, ?, ?, ?)
                    """,
                    (SCHEMA_VERSION, policy_json, policy_hash, _utc_now()),
                )
            elif row["schema_version"] != SCHEMA_VERSION:
                raise ConfigMismatchError(
                    "cycle policy mismatch: refusing to resume with changed identity"
                )
            elif row["policy_hash"] != policy_hash:
                previous = cast(object, json.loads(row["policy_json"]))
                if not isinstance(previous, dict) or not _is_safe_policy_upgrade(
                    cast(dict[str, object], previous),
                    policy,
                ):
                    raise ConfigMismatchError(
                        "cycle policy mismatch: refusing to resume with "
                        "changed identity"
                    )
                if (
                    self._connection.execute(
                        "SELECT 1 FROM snapshots LIMIT 1"
                    ).fetchone()
                    is not None
                ):
                    raise ConfigMismatchError(
                        "cycle policy migration refused after a published snapshot"
                    )
                previous_hash = str(row["policy_hash"])
                migrated_at = _utc_now()
                self._connection.execute(
                    "UPDATE batches SET cycle_hash = ? WHERE cycle_hash = ?",
                    (policy_hash, previous_hash),
                )
                self._connection.execute(
                    "UPDATE firecrawl_budget SET cycle_hash = ? WHERE cycle_hash = ?",
                    (policy_hash, previous_hash),
                )
                self._connection.execute(
                    """
                    UPDATE cycle_identity
                    SET policy_json = ?, policy_hash = ?
                    WHERE singleton = 1
                    """,
                    (policy_json, policy_hash),
                )
                self._connection.execute(
                    """
                    INSERT INTO cycle_policy_migrations(
                        old_policy_hash, new_policy_hash, migrated_at
                    ) VALUES(?, ?, ?)
                    """,
                    (previous_hash, policy_hash, migrated_at),
                )
        return policy_hash

    def ensure_batch(self, batch_id: str, config: Mapping[str, object]) -> str:
        """Freeze or validate one batch's resumable configuration digest."""

        _require_text(batch_id, "batch_id")
        cycle_hash = self.cycle_hash
        config_json = _canonical_json(config)
        digest = _sha256_text(config_json)
        with self._transaction():
            row = self._connection.execute(
                "SELECT config_digest FROM batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO batches(
                        batch_id, cycle_hash, config_json, config_digest, created_at
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (batch_id, cycle_hash, config_json, digest, _utc_now()),
                )
            elif row[0] != digest:
                raise ConfigMismatchError(
                    f"batch config mismatch for {batch_id}: refusing unsafe resume"
                )
        return digest

    def batch_digest(self, batch_id: str) -> str:
        """Return the frozen digest for ``batch_id``."""

        row = self._connection.execute(
            "SELECT config_digest FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown batch: {batch_id}")
        return str(row[0])

    def ensure_firecrawl_run(
        self,
        run_id: str,
        *,
        batch_id: str,
        config: Mapping[str, object],
        credit_cap: int,
        reserved_credits_per_attempt: int,
    ) -> str:
        """Freeze a Firecrawl run and its cycle-wide authorization envelope.

        The budget is deliberately cycle-scoped rather than run-scoped. Search,
        docket acquisition, retries, and later batches therefore cannot each
        authorize an independent copy of the cap.
        """

        run_id = _require_text(run_id, "run_id")
        batch_id = _require_text(batch_id, "batch_id")
        self.batch_digest(batch_id)
        credit_cap = _require_positive_int(credit_cap, "credit_cap")
        reserved_credits_per_attempt = _require_positive_int(
            reserved_credits_per_attempt, "reserved_credits_per_attempt"
        )
        if credit_cap > 45_000:
            raise ValueError("credit_cap must not exceed the 45,000-credit safety cap")
        if reserved_credits_per_attempt > 5:
            raise ValueError("reserved_credits_per_attempt must not exceed 5")
        if reserved_credits_per_attempt > credit_cap:
            raise ValueError("reserved_credits_per_attempt exceeds credit_cap")
        config_json = _canonical_json(config)
        config_digest = _sha256_text(config_json)
        now = _utc_now()
        with self._transaction():
            budget = self._connection.execute(
                "SELECT * FROM firecrawl_budget WHERE singleton = 1"
            ).fetchone()
            if budget is None:
                self._connection.execute(
                    """
                    INSERT INTO firecrawl_budget(
                        singleton, cycle_hash, credit_cap,
                        reserved_credits_per_attempt, created_at
                    ) VALUES(1, ?, ?, ?, ?)
                    """,
                    (
                        self.cycle_hash,
                        credit_cap,
                        reserved_credits_per_attempt,
                        now,
                    ),
                )
            elif (
                int(budget["credit_cap"]) != credit_cap
                or int(budget["reserved_credits_per_attempt"])
                != reserved_credits_per_attempt
                or str(budget["cycle_hash"]) != self.cycle_hash
            ):
                raise ConfigMismatchError(
                    "Firecrawl cycle budget mismatch: refusing unsafe resume"
                )

            existing = self._connection.execute(
                "SELECT * FROM firecrawl_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO firecrawl_runs(
                        run_id, batch_id, config_json, config_digest,
                        status, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (run_id, batch_id, config_json, config_digest, now, now),
                )
            elif (
                str(existing["batch_id"]) != batch_id
                or str(existing["config_digest"]) != config_digest
            ):
                raise ConfigMismatchError(
                    f"Firecrawl run config mismatch for {run_id}: "
                    "refusing unsafe resume"
                )
        return config_digest

    def ensure_firecrawl_target(
        self,
        run_id: str,
        *,
        target_id: str,
        target_kind: str,
        source_url: str,
        ordinal: int,
    ) -> None:
        """Create or validate one deterministic search/docket target."""

        run_id = _require_text(run_id, "run_id")
        target_id = _require_text(target_id, "target_id")
        source_url = _require_text(source_url, "source_url")
        if target_kind not in {"search", "docket"}:
            raise ValueError("target_kind must be search or docket")
        if isinstance(ordinal, bool) or ordinal < 0:
            raise ValueError("ordinal must be a non-negative integer")
        with self._transaction():
            if (
                self._connection.execute(
                    "SELECT 1 FROM firecrawl_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                raise KeyError(f"unknown Firecrawl run: {run_id}")
            row = self._connection.execute(
                """
                SELECT * FROM firecrawl_targets
                WHERE run_id = ? AND target_id = ?
                """,
                (run_id, target_id),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO firecrawl_targets(
                        run_id, target_id, target_kind, source_url,
                        ordinal, status, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        run_id,
                        target_id,
                        target_kind,
                        source_url,
                        ordinal,
                        _utc_now(),
                        _utc_now(),
                    ),
                )
            elif (
                str(row["target_kind"]) != target_kind
                or str(row["source_url"]) != source_url
                or int(row["ordinal"]) != ordinal
            ):
                raise ConfigMismatchError(
                    f"Firecrawl target mismatch for {target_id}: refusing unsafe resume"
                )

    def authorize_firecrawl_attempt(
        self,
        run_id: str,
        *,
        target_id: str,
        page_number: int,
        request_url: str,
    ) -> FirecrawlAttempt:
        """Permanently reserve worst-case credits before any wire request."""

        run_id = _require_text(run_id, "run_id")
        target_id = _require_text(target_id, "target_id")
        request_url = _require_text(request_url, "request_url")
        page_number = _require_positive_int(page_number, "page_number")
        with self._transaction():
            target = self._connection.execute(
                """
                SELECT 1 FROM firecrawl_targets
                WHERE run_id = ? AND target_id = ?
                """,
                (run_id, target_id),
            ).fetchone()
            if target is None:
                raise KeyError(f"unknown Firecrawl target: {run_id}/{target_id}")
            budget = self._connection.execute(
                "SELECT * FROM firecrawl_budget WHERE singleton = 1"
            ).fetchone()
            assert budget is not None
            reserved_per_attempt = int(budget["reserved_credits_per_attempt"])
            reserved_total = int(
                self._connection.execute(
                    "SELECT COALESCE(SUM(reserved_credits), 0) FROM firecrawl_attempts"
                ).fetchone()[0]
            )
            if reserved_total + reserved_per_attempt > int(budget["credit_cap"]):
                raise FirecrawlBudgetExceededError(
                    "Firecrawl credit cap would be exceeded; request not dispatched"
                )
            attempt_number = int(
                self._connection.execute(
                    """
                    SELECT COALESCE(MAX(attempt_number), 0) + 1
                    FROM firecrawl_attempts
                    WHERE run_id = ? AND target_id = ? AND page_number = ?
                    """,
                    (run_id, target_id, page_number),
                ).fetchone()[0]
            )
            cursor = self._connection.execute(
                """
                INSERT INTO firecrawl_attempts(
                    run_id, target_id, page_number, attempt_number,
                    request_url, reserved_credits, status, authorized_at
                ) VALUES(?, ?, ?, ?, ?, ?, 'authorized', ?)
                """,
                (
                    run_id,
                    target_id,
                    page_number,
                    attempt_number,
                    request_url,
                    reserved_per_attempt,
                    _utc_now(),
                ),
            )
            if cursor.lastrowid is None:
                raise CycleAcquisitionStoreError(
                    "Firecrawl attempt authorization returned no row ID"
                )
            attempt_id = cursor.lastrowid
            self._connection.execute(
                """
                UPDATE firecrawl_targets
                SET status = 'in_progress', updated_at = ?
                WHERE run_id = ? AND target_id = ?
                """,
                (_utc_now(), run_id, target_id),
            )
        return self.firecrawl_attempt(attempt_id)

    def finalize_firecrawl_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        reported_credits: object | None = None,
        proxy_used: str | None = None,
        provider_http_status: object | None = None,
        target_http_status: object | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        failure_transient: object | None = None,
        failure_response_sha256: str | None = None,
        artifact_path: str | Path | None = None,
        artifact_sha256: str | None = None,
        artifact_byte_count: object | None = None,
    ) -> FirecrawlAttempt:
        """Finalize an attempt without ever refunding its authorization."""

        allowed_statuses = {
            "succeeded",
            "provider_error",
            "target_error",
            "transport_error",
            "interrupted",
        }
        if status not in allowed_statuses:
            raise ValueError(f"invalid Firecrawl attempt status: {status}")
        existing = self.firecrawl_attempt(attempt_id)
        if existing.status != "authorized":
            if existing.status == status:
                return existing
            raise ConfigMismatchError(
                f"Firecrawl attempt {attempt_id} is already finalized"
            )
        if reported_credits is not None:
            if (
                isinstance(reported_credits, bool)
                or not isinstance(reported_credits, int)
                or reported_credits < 0
                or reported_credits > existing.reserved_credits
            ):
                raise ValueError(
                    "reported_credits must be an integer within the reservation"
                )
        if status == "succeeded" and reported_credits is None:
            raise ValueError("reported_credits is required for a successful attempt")
        for value, name in (
            (provider_http_status, "provider_http_status"),
            (target_http_status, "target_http_status"),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 100
                or value > 599
            ):
                raise ValueError(f"{name} must be a valid HTTP status")
        failure_values = (failure_code, failure_message, failure_transient)
        if any(value is not None for value in failure_values) and not all(
            value is not None for value in failure_values
        ):
            raise ValueError(
                "failure_code, failure_message, and failure_transient must be "
                "supplied together"
            )
        if (
            failure_code is not None
            and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", failure_code) is None
        ):
            raise ValueError("failure_code must be canonical snake_case")
        if failure_message is not None and (
            not failure_message.strip()
            or failure_message != " ".join(failure_message.split())
            or len(failure_message) > 300
        ):
            raise ValueError("failure_message must be normalized bounded text")
        if failure_transient is not None and not isinstance(failure_transient, bool):
            raise ValueError("failure_transient must be a boolean")
        if (
            failure_response_sha256 is not None
            and re.fullmatch(r"[0-9a-f]{64}", failure_response_sha256) is None
        ):
            raise ValueError("failure_response_sha256 must be lowercase SHA-256")
        if status == "succeeded" and (
            any(value is not None for value in failure_values)
            or failure_response_sha256 is not None
        ):
            raise ValueError("successful attempts cannot carry failure evidence")
        normalized_path = (
            str(Path(artifact_path)) if artifact_path is not None else None
        )
        if (
            artifact_sha256 is not None
            and re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None
        ):
            raise ValueError("artifact_sha256 must be lowercase SHA-256")
        if artifact_byte_count is not None and (
            isinstance(artifact_byte_count, bool)
            or not isinstance(artifact_byte_count, int)
            or artifact_byte_count < 0
        ):
            raise ValueError("artifact_byte_count must be a non-negative integer")
        artifact_fields = (
            normalized_path,
            artifact_sha256,
            artifact_byte_count,
        )
        if any(value is not None for value in artifact_fields) and not all(
            value is not None for value in artifact_fields
        ):
            raise ValueError(
                "artifact path, sha256, and byte_count must be supplied together"
            )
        if status != "succeeded" and any(
            value is not None for value in artifact_fields
        ):
            raise ValueError("only successful attempts may commit an artifact")
        with self._transaction():
            row = self._connection.execute(
                "SELECT status FROM firecrawl_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown Firecrawl attempt: {attempt_id}")
            if str(row["status"]) != "authorized":
                raise ConfigMismatchError(
                    f"Firecrawl attempt {attempt_id} changed during finalization"
                )
            self._connection.execute(
                """
                UPDATE firecrawl_attempts SET
                    status = ?, reported_credits = ?, proxy_used = ?,
                    provider_http_status = ?, target_http_status = ?,
                    failure_code = ?, failure_message = ?, failure_transient = ?,
                    failure_response_sha256 = ?,
                    artifact_path = ?, artifact_sha256 = ?, artifact_byte_count = ?,
                    completed_at = ?
                WHERE attempt_id = ?
                """,
                (
                    status,
                    reported_credits,
                    proxy_used,
                    provider_http_status,
                    target_http_status,
                    failure_code,
                    failure_message,
                    int(failure_transient) if failure_transient is not None else None,
                    failure_response_sha256,
                    normalized_path,
                    artifact_sha256,
                    artifact_byte_count,
                    _utc_now(),
                    attempt_id,
                ),
            )
        return self.firecrawl_attempt(attempt_id)

    def commit_firecrawl_artifact(
        self,
        attempt_id: int,
        destination: str | Path,
        content: bytes,
        *,
        reported_credits: object,
        proxy_used: str | None,
        target_http_status: object,
        validator: Callable[[bytes], None] | None = None,
    ) -> FirecrawlAttempt:
        """Atomically publish one search/docket page and finalize its attempt.

        An orphan file after a process crash is trusted only when a later,
        separately authorized response reproduces the exact bytes. Permanent
        reservations therefore remain conservative across every crash window.
        """

        attempt = self.firecrawl_attempt(attempt_id)
        destination_path = Path(destination).resolve()
        digest = hashlib.sha256(content).hexdigest()
        if validator is not None:
            validator(content)
        if (
            isinstance(reported_credits, bool)
            or not isinstance(reported_credits, int)
            or reported_credits < 0
            or reported_credits > attempt.reserved_credits
        ):
            raise ValueError(
                "reported_credits must be an integer within the reservation"
            )
        if (
            isinstance(target_http_status, bool)
            or not isinstance(target_http_status, int)
            or target_http_status < 100
            or target_http_status > 599
        ):
            raise ValueError("target_http_status must be a valid HTTP status")
        if attempt.status == "succeeded":
            if (
                attempt.artifact_path != destination_path
                or attempt.artifact_sha256 != digest
                or attempt.artifact_byte_count != len(content)
            ):
                raise ImmutableArtifactError(
                    f"Firecrawl attempt {attempt_id} has a different "
                    "artifact commitment"
                )
            try:
                existing_content = destination_path.read_bytes()
            except OSError as error:
                raise ImmutableArtifactError(
                    f"committed Firecrawl artifact is missing: {destination_path}"
                ) from error
            if existing_content != content:
                raise ImmutableArtifactError(
                    f"committed Firecrawl artifact was modified: {destination_path}"
                )
            return attempt
        if attempt.status != "authorized":
            raise ConfigMismatchError(
                f"Firecrawl attempt {attempt_id} cannot commit an artifact from "
                f"status {attempt.status}"
            )
        conflicting = self._connection.execute(
            """
            SELECT attempt_id FROM firecrawl_attempts
            WHERE artifact_path = ? AND attempt_id != ?
            """,
            (str(destination_path), attempt_id),
        ).fetchone()
        if conflicting is not None:
            raise ImmutableArtifactError(
                f"Firecrawl artifact path is already committed: {destination_path}"
            )
        if destination_path.exists():
            if destination_path.read_bytes() != content:
                raise ImmutableArtifactError(
                    f"untracked Firecrawl artifact conflicts with content: "
                    f"{destination_path}"
                )
        else:
            _atomic_write_bytes(destination_path, content)
        committed = self.finalize_firecrawl_attempt(
            attempt_id,
            status="succeeded",
            reported_credits=reported_credits,
            proxy_used=proxy_used,
            target_http_status=target_http_status,
            artifact_path=destination_path,
            artifact_sha256=digest,
            artifact_byte_count=len(content),
        )
        self.set_firecrawl_target_status(
            committed.run_id, committed.target_id, "succeeded"
        )
        return self.firecrawl_attempt(attempt_id)

    def firecrawl_attempt(self, attempt_id: int) -> FirecrawlAttempt:
        """Return one Firecrawl attempt."""

        row = self._connection.execute(
            "SELECT * FROM firecrawl_attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Firecrawl attempt: {attempt_id}")
        return _firecrawl_attempt_from_row(row)

    def firecrawl_attempts(self, run_id: str) -> tuple[FirecrawlAttempt, ...]:
        """Return a run's attempt ledger in authorization order."""

        rows = self._connection.execute(
            """
            SELECT * FROM firecrawl_attempts
            WHERE run_id = ? ORDER BY attempt_id
            """,
            (_require_text(run_id, "run_id"),),
        )
        return tuple(_firecrawl_attempt_from_row(row) for row in rows)

    def firecrawl_targets(self, run_id: str) -> tuple[FirecrawlTarget, ...]:
        """Return a run's targets in deterministic scheduling order."""

        rows = self._connection.execute(
            """
            SELECT * FROM firecrawl_targets
            WHERE run_id = ? ORDER BY ordinal, target_id
            """,
            (_require_text(run_id, "run_id"),),
        )
        return tuple(_firecrawl_target_from_row(row) for row in rows)

    def set_firecrawl_target_status(
        self, run_id: str, target_id: str, status: str
    ) -> FirecrawlTarget:
        """Checkpoint a target outcome independently of export files."""

        allowed = {
            "pending",
            "in_progress",
            "succeeded",
            "retry_exhausted",
            "terminal_error",
        }
        if status not in allowed:
            raise ValueError(f"invalid Firecrawl target status: {status}")
        with self._transaction():
            cursor = self._connection.execute(
                """
                UPDATE firecrawl_targets SET status = ?, updated_at = ?
                WHERE run_id = ? AND target_id = ?
                """,
                (status, _utc_now(), run_id, target_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown Firecrawl target: {run_id}/{target_id}")
        row = self._connection.execute(
            """
            SELECT * FROM firecrawl_targets
            WHERE run_id = ? AND target_id = ?
            """,
            (run_id, target_id),
        ).fetchone()
        assert row is not None
        return _firecrawl_target_from_row(row)

    def firecrawl_run_status(self, run_id: str) -> str:
        """Return the durable scheduler state for one Firecrawl run."""

        row = self._connection.execute(
            "SELECT status FROM firecrawl_runs WHERE run_id = ?",
            (_require_text(run_id, "run_id"),),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Firecrawl run: {run_id}")
        return str(row["status"])

    def firecrawl_run_config(self, run_id: str) -> Mapping[str, object]:
        """Return one run's immutable decoded configuration."""

        row = self._connection.execute(
            "SELECT config_json FROM firecrawl_runs WHERE run_id = ?",
            (_require_text(run_id, "run_id"),),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Firecrawl run: {run_id}")
        decoded = json.loads(str(row["config_json"]))
        if not isinstance(decoded, dict):
            raise CycleAcquisitionStoreError("Firecrawl run config is not an object")
        return cast(Mapping[str, object], decoded)

    def set_firecrawl_run_status(self, run_id: str, status: str) -> None:
        """Persist a fail-closed run-level scheduler state."""

        run_id = _require_text(run_id, "run_id")
        if status not in {"active", "circuit_open"}:
            raise ValueError(f"invalid Firecrawl run status: {status}")
        with self._transaction():
            cursor = self._connection.execute(
                """
                UPDATE firecrawl_runs SET status = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, _utc_now(), run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown Firecrawl run: {run_id}")

    def firecrawl_run_summary(self, run_id: str) -> Mapping[str, object]:
        """Return reconcilable run and cycle-wide credit accounting."""

        run = self._connection.execute(
            "SELECT * FROM firecrawl_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if run is None:
            raise KeyError(f"unknown Firecrawl run: {run_id}")
        budget = self._connection.execute(
            "SELECT * FROM firecrawl_budget WHERE singleton = 1"
        ).fetchone()
        assert budget is not None
        totals = self._connection.execute(
            """
            SELECT COALESCE(SUM(reserved_credits), 0) AS reserved,
                   COALESCE(SUM(reported_credits), 0) AS reported
            FROM firecrawl_attempts
            """
        ).fetchone()
        statuses = self._connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM firecrawl_attempts WHERE run_id = ?
            GROUP BY status ORDER BY status
            """,
            (run_id,),
        )
        failure_codes = self._connection.execute(
            """
            SELECT failure_code, COUNT(*) AS count
            FROM firecrawl_attempts
            WHERE run_id = ? AND failure_code IS NOT NULL
            GROUP BY failure_code ORDER BY failure_code
            """,
            (run_id,),
        )
        reserved = int(totals["reserved"])
        cap = int(budget["credit_cap"])
        return {
            "run_id": run_id,
            "batch_id": str(run["batch_id"]),
            "status": str(run["status"]),
            "config_digest": str(run["config_digest"]),
            "credit_cap": cap,
            "reserved_credits_per_attempt": int(budget["reserved_credits_per_attempt"]),
            "reserved_credits": reserved,
            "reported_credits": int(totals["reported"]),
            "remaining_authorization": cap - reserved,
            "attempt_status_counts": {
                str(row["status"]): int(row["count"]) for row in statuses
            },
            "failure_code_counts": {
                str(row["failure_code"]): int(row["count"]) for row in failure_codes
            },
        }

    def ensure_terms(self, batch_id: str, terms: Sequence[str]) -> None:
        """Materialize independent progress rows for every unique query term."""

        self.batch_digest(batch_id)
        normalized = tuple(_require_text(term, "term") for term in terms)
        if len(set(normalized)) != len(normalized):
            raise ValueError("terms must be unique")
        with self._transaction():
            for ordinal, term in enumerate(normalized):
                self._connection.execute(
                    """
                    INSERT INTO term_progress(batch_id, term, ordinal)
                    VALUES(?, ?, ?)
                    ON CONFLICT(batch_id, term) DO NOTHING
                    """,
                    (batch_id, term, ordinal),
                )

    def term_progress(self, batch_id: str, term: str) -> TermProgress:
        """Read durable cursor and completion state for one term."""

        row = self._connection.execute(
            """
            SELECT cursor, hit_count, terminal_status
            FROM term_progress WHERE batch_id = ? AND term = ?
            """,
            (batch_id, term),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown term {term!r} in batch {batch_id!r}")
        return TermProgress(
            cursor=row["cursor"],
            hit_count=int(row["hit_count"]),
            terminal_status=TermTerminalStatus(row["terminal_status"])
            if row["terminal_status"] is not None
            else None,
        )

    def commit_search_page(
        self,
        batch_id: str,
        term: str,
        request_cursor: str | None,
        hits: Iterable[DiscoveryHit | Mapping[str, object]],
        *,
        next_cursor: str | None,
        terminal_status: TermTerminalStatus | str | None,
    ) -> TermProgress:
        """Atomically commit all hits from a page and only then advance its cursor."""

        normalized_hits = tuple(_normalize_hit(hit) for hit in hits)
        if next_cursor is not None:
            _require_text(next_cursor, "next_cursor")
        if terminal_status is not None:
            _require_text(terminal_status, "terminal_status")
        if next_cursor is not None and terminal_status is not None:
            raise ValueError("a page cannot have both next_cursor and terminal_status")
        commitment = _sha256_text(
            _canonical_json(
                {
                    "hits": normalized_hits,
                    "next_cursor": next_cursor,
                    "terminal_status": terminal_status,
                }
            )
        )
        cursor_key = _cursor_key(request_cursor)
        with self._transaction():
            progress = self.term_progress(batch_id, term)
            prior = self._connection.execute(
                """
                SELECT response_hash FROM search_pages
                WHERE batch_id = ? AND term = ? AND request_cursor_key = ?
                """,
                (batch_id, term, cursor_key),
            ).fetchone()
            if prior is not None:
                if prior[0] != commitment:
                    raise PageReplayMismatchError(
                        f"non-identical replay for {batch_id}/{term}/{request_cursor!r}"
                    )
                return progress
            if progress.terminal_status is not None:
                raise PageReplayMismatchError(
                    f"term {term!r} is already terminal: {progress.terminal_status}"
                )
            if progress.cursor != request_cursor:
                raise PageReplayMismatchError(
                    f"cursor mismatch for {batch_id}/{term}: expected "
                    f"{progress.cursor!r}, got {request_cursor!r}"
                )
            seen_provider_ids: set[str] = set()
            for provider_hit_id, candidate_id, payload_json in normalized_hits:
                if provider_hit_id in seen_provider_ids:
                    raise ValueError(
                        f"duplicate provider_hit_id within page: {provider_hit_id}"
                    )
                seen_provider_ids.add(provider_hit_id)
                self._connection.execute(
                    """
                    INSERT INTO candidates(candidate_id, first_batch_id, discovered_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(candidate_id) DO NOTHING
                    """,
                    (candidate_id, batch_id, _utc_now()),
                )
                existing = self._connection.execute(
                    """
                    SELECT candidate_id, payload_json FROM discovery_hits
                    WHERE batch_id = ? AND term = ? AND provider_hit_id = ?
                    """,
                    (batch_id, term, provider_hit_id),
                ).fetchone()
                if existing is not None and (
                    existing["candidate_id"] != candidate_id
                    or existing["payload_json"] != payload_json
                ):
                    raise PageReplayMismatchError(
                        f"provider hit identity changed: {provider_hit_id}"
                    )
                self._connection.execute(
                    """
                    INSERT INTO discovery_hits(
                        batch_id, term, provider_hit_id, candidate_id, payload_json,
                        request_cursor_key, discovered_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(batch_id, term, provider_hit_id) DO NOTHING
                    """,
                    (
                        batch_id,
                        term,
                        provider_hit_id,
                        candidate_id,
                        payload_json,
                        cursor_key,
                        _utc_now(),
                    ),
                )
            self._connection.execute(
                """
                INSERT INTO search_pages(
                    batch_id, term, request_cursor_key, request_cursor, next_cursor,
                    terminal_status, response_hash, committed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    term,
                    cursor_key,
                    request_cursor,
                    next_cursor,
                    terminal_status,
                    commitment,
                    _utc_now(),
                ),
            )
            hit_count = int(
                self._connection.execute(
                    """
                    SELECT COUNT(*) FROM discovery_hits
                    WHERE batch_id = ? AND term = ?
                    """,
                    (batch_id, term),
                ).fetchone()[0]
            )
            self._connection.execute(
                """
                UPDATE term_progress
                SET cursor = ?, hit_count = ?, terminal_status = ?, updated_at = ?
                WHERE batch_id = ? AND term = ?
                """,
                (next_cursor, hit_count, terminal_status, _utc_now(), batch_id, term),
            )
        return self.term_progress(batch_id, term)

    def candidate_ids(self, batch_id: str) -> tuple[str, ...]:
        """Return the order-neutral deduplicated union of all term hit sets."""

        self.batch_digest(batch_id)
        rows = self._connection.execute(
            """
            SELECT DISTINCT candidate_id FROM discovery_hits
            WHERE batch_id = ? ORDER BY candidate_id
            """,
            (batch_id,),
        )
        return tuple(str(row[0]) for row in rows)

    def candidate_discovery_hits(self, batch_id: str) -> tuple[DiscoveryHit, ...]:
        """Return one deterministic raw provider hit for each candidate."""

        self.batch_digest(batch_id)
        rows = self._connection.execute(
            """
            WITH ranked AS (
                SELECT h.provider_hit_id, h.candidate_id, h.payload_json,
                       ROW_NUMBER() OVER (
                           PARTITION BY h.candidate_id
                           ORDER BY h.term, h.provider_hit_id
                       ) AS candidate_rank
                FROM discovery_hits h
                WHERE h.batch_id = ?
            )
            SELECT provider_hit_id, candidate_id, payload_json
            FROM ranked WHERE candidate_rank = 1
            ORDER BY candidate_id
            """,
            (batch_id,),
        )
        hits: list[DiscoveryHit] = []
        for row in rows:
            parsed_payload = cast(object, json.loads(row["payload_json"]))
            if not isinstance(parsed_payload, dict):
                raise CycleAcquisitionStoreError(
                    f"provider payload is not an object for {row['provider_hit_id']}"
                )
            hits.append(
                DiscoveryHit(
                    provider_hit_id=str(row["provider_hit_id"]),
                    candidate_id=str(row["candidate_id"]),
                    payload=cast(dict[str, object], parsed_payload),
                )
            )
        return tuple(hits)

    def record_observation(
        self,
        candidate_id: str,
        *,
        batch_id: str,
        state: str,
        reason_code: str,
        evidence: Mapping[str, object],
        observed_at: str | None = None,
        audit_immutable_skip: bool = True,
    ) -> CandidateObservation:
        """Append evidence while preserving immutable and transient precedence."""

        candidate_id = _require_text(candidate_id, "candidate_id")
        reason_code = _require_text(reason_code, "reason_code")
        if state not in _OBSERVATION_STATES - {"skipped_immutable"}:
            raise ValueError(f"unsupported candidate observation state: {state}")
        policy = _REASON_POLICIES.get(reason_code)
        if policy is None:
            raise ValueError(
                f"unknown candidate observation reason code: {reason_code}"
            )
        allowed_states, _evidence_class, precedence = policy
        if state not in allowed_states:
            raise ValueError(
                f"reason code {reason_code!r} does not permit state {state!r}"
            )
        self.batch_digest(batch_id)
        evidence_json = _canonical_json(evidence)
        timestamp = observed_at or _utc_now()
        with self._transaction():
            discovery = self._connection.execute(
                """
                SELECT 1 FROM discovery_hits
                WHERE batch_id = ? AND candidate_id = ? LIMIT 1
                """,
                (batch_id, candidate_id),
            ).fetchone()
            if discovery is None:
                raise KeyError(
                    f"candidate {candidate_id} was not discovered in batch {batch_id}"
                )
            current = self._current_observation_row(candidate_id)
            current_is_immutable = bool(
                current is not None
                and current["state"] == "excluded"
                and current["reason_code"] in _IMMUTABLE_REASON_CODES
            )
            inserted_state = state
            supersedes = int(current["observation_id"]) if current else None
            current_precedence = (
                _reason_precedence(str(current["reason_code"])) if current else -1
            )
            update_current = (
                state in _EVIDENCED_STATES and precedence >= current_precedence
            )
            if current_is_immutable:
                assert current is not None
                if not audit_immutable_skip:
                    raise ImmutableCandidateStateError(
                        f"candidate {candidate_id} has immutable exclusion "
                        f"{current['reason_code']}"
                    )
                inserted_state = "skipped_immutable"
                update_current = False
            observation_id = int(
                self._connection.execute(
                    """
                    INSERT INTO candidate_observations(
                        candidate_id, batch_id, state, reason_code, evidence_json,
                        observed_at, supersedes_observation_id
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    RETURNING observation_id
                    """,
                    (
                        candidate_id,
                        batch_id,
                        inserted_state,
                        reason_code,
                        evidence_json,
                        timestamp,
                        supersedes,
                    ),
                ).fetchone()[0]
            )
            if update_current:
                self._connection.execute(
                    """
                    UPDATE candidates SET current_observation_id = ?
                    WHERE candidate_id = ?
                    """,
                    (observation_id, candidate_id),
                )
        return self._observation_by_id(observation_id)

    def current_observation(self, candidate_id: str) -> CandidateObservation | None:
        """Return the canonical evidenced state, excluding transient audit events."""

        row = self._current_observation_row(candidate_id)
        return None if row is None else _observation_from_row(row)

    def observations(self, candidate_id: str) -> tuple[CandidateObservation, ...]:
        """Return the full append-only observation history for a candidate."""

        rows = self._connection.execute(
            """
            SELECT * FROM candidate_observations
            WHERE candidate_id = ? ORDER BY observation_id
            """,
            (candidate_id,),
        )
        return tuple(_observation_from_row(row) for row in rows)

    def write_raw_artifact(
        self,
        candidate_id: str,
        destination: str | Path,
        content: bytes,
        *,
        retrieved_at: str,
        validator: Callable[[bytes], None] | None = None,
    ) -> RawArtifact:
        """Validate, hash, fsync, atomically publish, and commit a raw artifact."""

        candidate_id = _require_text(candidate_id, "candidate_id")
        retrieved_at = _require_text(retrieved_at, "retrieved_at")
        destination_path = Path(destination).resolve()
        digest = hashlib.sha256(content).hexdigest()
        candidate = self._connection.execute(
            "SELECT 1 FROM candidates WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if candidate is None:
            raise KeyError(f"unknown candidate: {candidate_id}")
        if validator is not None:
            validator(content)
        existing = self._connection.execute(
            "SELECT * FROM raw_artifacts WHERE path = ?", (str(destination_path),)
        ).fetchone()
        if existing is not None:
            if (
                existing["candidate_id"] != candidate_id
                or existing["sha256"] != digest
                or int(existing["byte_count"]) != len(content)
            ):
                raise ImmutableArtifactError(
                    f"raw artifact path already has a different commitment: "
                    f"{destination_path}"
                )
            return _raw_artifact_from_row(existing)
        if destination_path.exists():
            if destination_path.read_bytes() != content:
                raise ImmutableArtifactError(
                    f"untracked raw artifact conflicts with content: {destination_path}"
                )
        else:
            _atomic_write_bytes(destination_path, content)
        with self._transaction():
            try:
                artifact_id = int(
                    self._connection.execute(
                        """
                        INSERT INTO raw_artifacts(
                            candidate_id, path, sha256, byte_count, retrieved_at
                        ) VALUES(?, ?, ?, ?, ?)
                        RETURNING artifact_id
                        """,
                        (
                            candidate_id,
                            str(destination_path),
                            digest,
                            len(content),
                            retrieved_at,
                        ),
                    ).fetchone()[0]
                )
            except sqlite3.IntegrityError as error:
                raise ImmutableArtifactError(
                    f"raw artifact commitment raced for {destination_path}"
                ) from error
        row = self._connection.execute(
            "SELECT * FROM raw_artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        assert row is not None
        return _raw_artifact_from_row(row)

    def raw_artifacts(self, candidate_id: str | None = None) -> tuple[RawArtifact, ...]:
        """Return committed raw artifacts in stable order."""

        if candidate_id is None:
            rows = self._connection.execute("SELECT * FROM raw_artifacts ORDER BY path")
        else:
            rows = self._connection.execute(
                "SELECT * FROM raw_artifacts WHERE candidate_id = ? ORDER BY path",
                (candidate_id,),
            )
        return tuple(_raw_artifact_from_row(row) for row in rows)

    def export_snapshot(
        self,
        destination: str | Path,
        *,
        snapshot_id: str,
        batch_id: str,
        complete: bool,
    ) -> Path:
        """Atomically publish a complete snapshot or isolated checkpoint export."""

        if _SAFE_SNAPSHOT_ID.fullmatch(snapshot_id) is None:
            raise ValueError("snapshot_id contains unsafe characters")
        cycle_hash = self.cycle_hash
        batch_digest = self.batch_digest(batch_id)
        saturated = self._snapshot_completion(batch_id) if complete else False
        root = Path(destination).resolve()
        root.mkdir(parents=True, exist_ok=True)
        name = snapshot_id if complete else f"{snapshot_id}.partial"
        target = root / name
        if target.exists():
            raise FileExistsError(f"snapshot already exists: {target}")
        staging = root / f".{name}.{uuid.uuid4().hex}.tmp"
        staging.mkdir(mode=0o700)
        try:
            payloads = self._snapshot_payloads(batch_id)
            if complete:
                _validate_snapshot_target_motion_invariant(
                    payloads["screened-cases.jsonl"]
                )
            files: dict[str, dict[str, object]] = {}
            for filename in _SNAPSHOT_FILES:
                payload = payloads[filename]
                _write_fsynced(staging / filename, payload)
                files[filename] = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "byte_count": len(payload),
                    "row_count": payload.count(b"\n"),
                }
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "complete": complete,
                "saturated": saturated,
                "cycle_hash": cycle_hash,
                "batch_id": batch_id,
                "batch_digest": batch_digest,
                "created_at": _utc_now(),
                "files": files,
            }
            _write_fsynced(
                staging / "manifest.json",
                f"{_canonical_json(manifest)}\n".encode(),
            )
            _fsync_directory(staging)
            os.rename(staging, target)
            _fsync_directory(root)
        except BaseException:
            _remove_staging_directory(staging)
            raise
        with self._transaction():
            self._connection.execute(
                """
                INSERT INTO snapshots(
                    snapshot_id, batch_id, complete, path, manifest_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    batch_id,
                    int(complete),
                    str(target),
                    _canonical_json(manifest),
                    manifest["created_at"],
                ),
            )
        return target

    def _snapshot_payloads(self, batch_id: str) -> dict[str, bytes]:
        candidate_rows = self._connection.execute(
            """
            SELECT c.candidate_id, o.state, o.reason_code, o.evidence_json,
                   o.observed_at, o.observation_id
            FROM candidates c
            JOIN discovery_hits h ON h.candidate_id = c.candidate_id
            LEFT JOIN candidate_observations o
              ON o.observation_id = c.current_observation_id
            WHERE h.batch_id = ?
            GROUP BY c.candidate_id
            ORDER BY c.candidate_id
            """,
            (batch_id,),
        ).fetchall()
        candidate_records: list[dict[str, object]] = [
            {
                "candidate_id": row["candidate_id"],
                "state": row["state"] or "discovered",
                "reason_code": row["reason_code"],
                "evidence": cast(object, json.loads(row["evidence_json"]))
                if row["evidence_json"]
                else {},
                "observed_at": row["observed_at"],
                "observation_id": row["observation_id"],
            }
            for row in candidate_rows
        ]
        screened_cases: list[dict[str, object]] = []
        exclusions: list[dict[str, object]] = []
        for record in candidate_records:
            state = record["state"]
            if state == "discovered":
                continue
            evidence = record["evidence"]
            if not isinstance(evidence, dict):
                raise CycleAcquisitionStoreError(
                    f"candidate {record['candidate_id']} evidence is not an object"
                )
            current_record = dict(cast(dict[str, object], evidence))
            evidence_candidate_id = current_record.get("candidate_id")
            if evidence_candidate_id is not None and (
                evidence_candidate_id != record["candidate_id"]
            ):
                raise CycleAcquisitionStoreError(
                    f"candidate evidence identity mismatch for {record['candidate_id']}"
                )
            current_record["candidate_id"] = record["candidate_id"]
            if state in {"accepted", "newly_free"}:
                screened_cases.append(current_record)
            elif state == "excluded":
                reason_code = record["reason_code"]
                current_record.setdefault("reason", reason_code)
                current_record.setdefault("primary_exclusion_reason", reason_code)
                exclusions.append(current_record)
            else:
                raise CycleAcquisitionStoreError(
                    f"unsupported canonical candidate state: {state}"
                )
        observation_rows = self._connection.execute(
            """
            SELECT DISTINCT o.* FROM candidate_observations o
            JOIN discovery_hits h ON h.candidate_id = o.candidate_id
            WHERE h.batch_id = ? ORDER BY o.observation_id
            """,
            (batch_id,),
        )
        observations: Iterable[Mapping[str, object]] = (
            {
                "observation_id": row["observation_id"],
                "candidate_id": row["candidate_id"],
                "batch_id": row["batch_id"],
                "state": row["state"],
                "reason_code": row["reason_code"],
                "evidence": cast(object, json.loads(row["evidence_json"])),
                "observed_at": row["observed_at"],
                "supersedes_observation_id": row["supersedes_observation_id"],
            }
            for row in observation_rows
        )
        artifact_rows = self._connection.execute(
            """
            SELECT DISTINCT a.* FROM raw_artifacts a
            JOIN discovery_hits h ON h.candidate_id = a.candidate_id
            WHERE h.batch_id = ? ORDER BY a.path
            """,
            (batch_id,),
        )
        artifacts: Iterable[Mapping[str, object]] = (
            {
                "artifact_id": row["artifact_id"],
                "candidate_id": row["candidate_id"],
                "path": row["path"],
                "sha256": row["sha256"],
                "byte_count": row["byte_count"],
                "retrieved_at": row["retrieved_at"],
            }
            for row in artifact_rows
        )
        summary = {
            "batch_id": batch_id,
            "processed_count": len(candidate_records),
            "accepted_count": len(screened_cases),
            "excluded_count": len(exclusions),
            "reconciliation_complete": (
                len(candidate_records) == len(screened_cases) + len(exclusions)
            ),
        }
        return {
            "screened-cases.jsonl": _jsonl_bytes(screened_cases),
            "exclusions.jsonl": _jsonl_bytes(exclusions),
            "summary.json": f"{_canonical_json(summary)}\n".encode(),
            "candidates.jsonl": _jsonl_bytes(candidate_records),
            "observations.jsonl": _jsonl_bytes(observations),
            "raw-artifacts.jsonl": _jsonl_bytes(artifacts),
        }

    def _snapshot_completion(self, batch_id: str) -> bool:
        terms = self._connection.execute(
            """
            SELECT term, terminal_status FROM term_progress
            WHERE batch_id = ? ORDER BY term
            """,
            (batch_id,),
        ).fetchall()
        if not terms:
            raise CycleAcquisitionStoreError(
                "cannot publish a complete snapshot without query terms"
            )
        incomplete_terms = [
            row["term"]
            for row in terms
            if row["terminal_status"]
            in {None, TermTerminalStatus.LIMIT_BOUND_UNPAGEABLE}
        ]
        if incomplete_terms:
            raise CycleAcquisitionStoreError(
                "cannot publish a complete snapshot with incomplete terms: "
                + ", ".join(incomplete_terms)
            )
        unresolved = self._connection.execute(
            """
            SELECT DISTINCT h.candidate_id FROM discovery_hits h
            JOIN candidates c ON c.candidate_id = h.candidate_id
            WHERE h.batch_id = ? AND c.current_observation_id IS NULL
            ORDER BY h.candidate_id
            """,
            (batch_id,),
        ).fetchall()
        if unresolved:
            raise CycleAcquisitionStoreError(
                "cannot publish a complete snapshot with unresolved candidates: "
                + ", ".join(str(row[0]) for row in unresolved)
            )
        return all(
            row["terminal_status"] == TermTerminalStatus.EXHAUSTED for row in terms
        )

    def _current_observation_row(self, candidate_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT o.* FROM candidates c
            JOIN candidate_observations o
              ON o.observation_id = c.current_observation_id
            WHERE c.candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

    def _observation_by_id(self, observation_id: int) -> CandidateObservation:
        row = self._connection.execute(
            "SELECT * FROM candidate_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
        assert row is not None
        return _observation_from_row(row)

    def _transaction(self) -> _Transaction:
        return _Transaction(self._connection)

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cycle_identity(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                schema_version TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                policy_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS batches(
                batch_id TEXT PRIMARY KEY,
                cycle_hash TEXT NOT NULL,
                config_json TEXT NOT NULL,
                config_digest TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cycle_policy_migrations(
                migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                old_policy_hash TEXT NOT NULL,
                new_policy_hash TEXT NOT NULL,
                migrated_at TEXT NOT NULL,
                UNIQUE(old_policy_hash, new_policy_hash)
            );
            CREATE TABLE IF NOT EXISTS term_progress(
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                term TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                cursor TEXT,
                hit_count INTEGER NOT NULL DEFAULT 0,
                terminal_status TEXT,
                updated_at TEXT,
                PRIMARY KEY(batch_id, term)
            );
            CREATE TABLE IF NOT EXISTS candidates(
                candidate_id TEXT PRIMARY KEY,
                first_batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                discovered_at TEXT NOT NULL,
                current_observation_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS discovery_hits(
                batch_id TEXT NOT NULL,
                term TEXT NOT NULL,
                provider_hit_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                payload_json TEXT NOT NULL,
                request_cursor_key TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                PRIMARY KEY(batch_id, term, provider_hit_id),
                FOREIGN KEY(batch_id, term) REFERENCES term_progress(batch_id, term)
            );
            CREATE INDEX IF NOT EXISTS discovery_hits_candidate
            ON discovery_hits(batch_id, candidate_id);
            CREATE TABLE IF NOT EXISTS search_pages(
                batch_id TEXT NOT NULL,
                term TEXT NOT NULL,
                request_cursor_key TEXT NOT NULL,
                request_cursor TEXT,
                next_cursor TEXT,
                terminal_status TEXT,
                response_hash TEXT NOT NULL,
                committed_at TEXT NOT NULL,
                PRIMARY KEY(batch_id, term, request_cursor_key),
                FOREIGN KEY(batch_id, term) REFERENCES term_progress(batch_id, term)
            );
            CREATE TABLE IF NOT EXISTS candidate_observations(
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                state TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                supersedes_observation_id INTEGER
                    REFERENCES candidate_observations(observation_id)
            );
            CREATE INDEX IF NOT EXISTS candidate_observation_history
            ON candidate_observations(candidate_id, observation_id);
            CREATE TABLE IF NOT EXISTS raw_artifacts(
                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                path TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                byte_count INTEGER NOT NULL,
                retrieved_at TEXT NOT NULL,
                UNIQUE(candidate_id, sha256)
            );
            CREATE TABLE IF NOT EXISTS firecrawl_budget(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                cycle_hash TEXT NOT NULL,
                credit_cap INTEGER NOT NULL CHECK(credit_cap BETWEEN 1 AND 45000),
                reserved_credits_per_attempt INTEGER NOT NULL
                    CHECK(reserved_credits_per_attempt BETWEEN 1 AND 5),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS firecrawl_runs(
                run_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                config_json TEXT NOT NULL,
                config_digest TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS firecrawl_targets(
                run_id TEXT NOT NULL REFERENCES firecrawl_runs(run_id),
                target_id TEXT NOT NULL,
                target_kind TEXT NOT NULL CHECK(target_kind IN ('search', 'docket')),
                source_url TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(run_id, target_id),
                UNIQUE(run_id, source_url),
                UNIQUE(run_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS firecrawl_attempts(
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                page_number INTEGER NOT NULL CHECK(page_number > 0),
                attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
                request_url TEXT NOT NULL,
                reserved_credits INTEGER NOT NULL
                    CHECK(reserved_credits BETWEEN 1 AND 5),
                status TEXT NOT NULL,
                reported_credits INTEGER,
                proxy_used TEXT,
                provider_http_status INTEGER,
                target_http_status INTEGER,
                failure_code TEXT,
                failure_message TEXT,
                failure_transient INTEGER,
                failure_response_sha256 TEXT,
                artifact_path TEXT,
                artifact_sha256 TEXT,
                artifact_byte_count INTEGER,
                authorized_at TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(run_id, target_id, page_number, attempt_number),
                FOREIGN KEY(run_id, target_id)
                    REFERENCES firecrawl_targets(run_id, target_id)
            );
            CREATE INDEX IF NOT EXISTS firecrawl_attempt_run_status
            ON firecrawl_attempts(run_id, status, attempt_id);
            CREATE TABLE IF NOT EXISTS snapshots(
                snapshot_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                complete INTEGER NOT NULL CHECK(complete IN (0, 1)),
                path TEXT NOT NULL UNIQUE,
                manifest_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reason_policies(
                reason_code TEXT PRIMARY KEY,
                allowed_states_json TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                precedence INTEGER NOT NULL
            );
            """
        )
        self._ensure_firecrawl_failure_columns()
        for reason_code, (allowed_states, evidence_class, precedence) in sorted(
            _REASON_POLICIES.items()
        ):
            serialized_states = _canonical_json(sorted(allowed_states))
            existing = self._connection.execute(
                "SELECT * FROM reason_policies WHERE reason_code = ?", (reason_code,)
            ).fetchone()
            if existing is not None and (
                existing["allowed_states_json"] != serialized_states
                or existing["evidence_class"] != evidence_class
                or int(existing["precedence"]) != precedence
            ):
                raise CycleAcquisitionStoreError(
                    f"stored reason policy mismatch for {reason_code}"
                )
            self._connection.execute(
                """
                INSERT INTO reason_policies(
                    reason_code, allowed_states_json, evidence_class, precedence
                ) VALUES(?, ?, ?, ?)
                ON CONFLICT(reason_code) DO NOTHING
                """,
                (reason_code, serialized_states, evidence_class, precedence),
            )

    def _ensure_firecrawl_failure_columns(self) -> None:
        """Add sanitized failure-evidence columns to pre-change cycle stores."""

        existing = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(firecrawl_attempts)")
        }
        additions = {
            "failure_code": "TEXT",
            "failure_message": "TEXT",
            "failure_transient": "INTEGER",
            "failure_response_sha256": "TEXT",
        }
        for name, sql_type in additions.items():
            if name not in existing:
                self._connection.execute(
                    f"ALTER TABLE firecrawl_attempts ADD COLUMN {name} {sql_type}"
                )


class _Transaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._connection.execute("COMMIT" if exc_type is None else "ROLLBACK")


def verify_snapshot(
    snapshot_path: str | Path,
    *,
    expected_cycle_hash: str | None = None,
    expected_batch_digest: str | None = None,
    require_complete: bool = True,
    require_saturated: bool = False,
) -> Mapping[str, Any]:
    """Verify completeness, config identity, and every exported file commitment."""

    path = Path(snapshot_path)
    try:
        manifest_raw = (path / "manifest.json").read_text(encoding="utf-8")
        parsed_manifest = cast(object, json.loads(manifest_raw))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotVerificationError(
            f"invalid snapshot manifest: {error}"
        ) from error
    if not isinstance(parsed_manifest, dict):
        raise SnapshotVerificationError("snapshot manifest must be a JSON object")
    manifest = cast(dict[str, object], parsed_manifest)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotVerificationError("snapshot schema version mismatch")
    if require_complete and manifest.get("complete") is not True:
        raise SnapshotVerificationError("snapshot is not complete")
    if require_saturated and manifest.get("saturated") is not True:
        raise SnapshotVerificationError("snapshot discovery is not saturated")
    if (
        expected_cycle_hash is not None
        and manifest.get("cycle_hash") != expected_cycle_hash
    ):
        raise SnapshotVerificationError("snapshot cycle hash mismatch")
    if expected_batch_digest is not None and (
        manifest.get("batch_digest") != expected_batch_digest
    ):
        raise SnapshotVerificationError("snapshot batch digest mismatch")
    parsed_files = manifest.get("files")
    if not isinstance(parsed_files, dict):
        raise SnapshotVerificationError("snapshot file manifest is incomplete")
    files = cast(dict[str, object], parsed_files)
    if set(files) != set(_SNAPSHOT_FILES):
        raise SnapshotVerificationError("snapshot file manifest is incomplete")
    for filename in _SNAPSHOT_FILES:
        parsed_commitment = files[filename]
        if not isinstance(parsed_commitment, dict):
            raise SnapshotVerificationError(f"invalid commitment for {filename}")
        commitment = cast(dict[str, object], parsed_commitment)
        try:
            payload = (path / filename).read_bytes()
        except OSError as error:
            raise SnapshotVerificationError(
                f"missing snapshot file {filename}"
            ) from error
        if (
            commitment.get("sha256") != hashlib.sha256(payload).hexdigest()
            or commitment.get("byte_count") != len(payload)
            or commitment.get("row_count") != payload.count(b"\n")
        ):
            raise SnapshotVerificationError(
                f"snapshot file commitment mismatch: {filename}"
            )
    _verify_snapshot_raw_artifacts(path)
    _verify_snapshot_reconciliation(path)
    return manifest


def _verify_snapshot_raw_artifacts(path: Path) -> None:
    artifacts = _read_jsonl_records(path / "raw-artifacts.jsonl")
    for line_number, artifact in enumerate(artifacts, start=1):
        raw_path = artifact.get("path")
        expected_byte_count = artifact.get("byte_count")
        expected_sha256 = artifact.get("sha256")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise SnapshotVerificationError(
                f"raw-artifacts.jsonl line {line_number} has an invalid path"
            )
        if (
            not isinstance(expected_byte_count, int)
            or isinstance(expected_byte_count, bool)
            or expected_byte_count < 0
        ):
            raise SnapshotVerificationError(
                f"raw-artifacts.jsonl line {line_number} has an invalid byte_count"
            )
        if (
            not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        ):
            raise SnapshotVerificationError(
                f"raw-artifacts.jsonl line {line_number} has an invalid sha256"
            )
        artifact_path = Path(raw_path)
        try:
            payload = artifact_path.read_bytes()
        except OSError as error:
            raise SnapshotVerificationError(
                f"missing committed raw artifact: {artifact_path}"
            ) from error
        if len(payload) != expected_byte_count:
            raise SnapshotVerificationError(
                f"raw artifact byte_count mismatch: {artifact_path}"
            )
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise SnapshotVerificationError(
                f"raw artifact sha256 mismatch: {artifact_path}"
            )


def _verify_snapshot_reconciliation(path: Path) -> None:
    screened = _read_jsonl_records(path / "screened-cases.jsonl")
    exclusions = _read_jsonl_records(path / "exclusions.jsonl")
    candidates = _read_jsonl_records(path / "candidates.jsonl")
    observations = _read_jsonl_records(path / "observations.jsonl")
    raw_artifacts = _read_jsonl_records(path / "raw-artifacts.jsonl")
    screened_ids = _snapshot_candidate_ids(screened, "screened-cases.jsonl")
    exclusion_ids = _snapshot_candidate_ids(exclusions, "exclusions.jsonl")
    candidate_ids = _snapshot_candidate_ids(candidates, "candidates.jsonl")
    overlap = screened_ids & exclusion_ids
    if overlap:
        raise SnapshotVerificationError(
            "accepted and excluded candidate IDs overlap: " + ", ".join(sorted(overlap))
        )
    accepted_candidate_ids: set[str] = set()
    excluded_candidate_ids: set[str] = set()
    for candidate in candidates:
        candidate_id = cast(str, candidate["candidate_id"])
        state = candidate.get("state")
        if state in {"accepted", "newly_free"}:
            accepted_candidate_ids.add(candidate_id)
        elif state == "excluded":
            excluded_candidate_ids.add(candidate_id)
        else:
            raise SnapshotVerificationError(
                f"candidates.jsonl contains invalid canonical state for {candidate_id}"
            )
    if (
        candidate_ids != screened_ids | exclusion_ids
        or accepted_candidate_ids != screened_ids
        or excluded_candidate_ids != exclusion_ids
    ):
        raise SnapshotVerificationError(
            "candidate IDs and states do not reconcile with screened cases and "
            "exclusions"
        )
    _require_snapshot_links(observations, "observations.jsonl", candidate_ids)
    _require_snapshot_links(raw_artifacts, "raw-artifacts.jsonl", candidate_ids)
    try:
        parsed_summary = cast(
            object, json.loads((path / "summary.json").read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotVerificationError(f"invalid snapshot summary: {error}") from error
    if not isinstance(parsed_summary, dict):
        raise SnapshotVerificationError("snapshot summary must be a JSON object")
    summary = cast(dict[str, object], parsed_summary)
    accepted_count = len(screened_ids)
    excluded_count = len(exclusion_ids)
    processed_count = accepted_count + excluded_count
    if (
        summary.get("accepted_count") != accepted_count
        or summary.get("excluded_count") != excluded_count
        or summary.get("processed_count") != processed_count
        or summary.get("reconciliation_complete") is not True
    ):
        raise SnapshotVerificationError("snapshot summary counts do not reconcile")


def _require_snapshot_links(
    records: Iterable[Mapping[str, object]],
    filename: str,
    candidate_ids: set[str],
) -> None:
    for record in records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise SnapshotVerificationError(
                f"{filename} contains a missing candidate_id"
            )
        if candidate_id not in candidate_ids:
            raise SnapshotVerificationError(
                f"{filename} references unknown candidate_id {candidate_id}"
            )


def _read_jsonl_records(path: Path) -> tuple[Mapping[str, object], ...]:
    records: list[Mapping[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SnapshotVerificationError(
            f"cannot read snapshot file {path.name}"
        ) from error
    for line_number, line in enumerate(lines, start=1):
        try:
            parsed = cast(object, json.loads(line))
        except json.JSONDecodeError as error:
            raise SnapshotVerificationError(
                f"invalid JSON in {path.name} line {line_number}"
            ) from error
        if not isinstance(parsed, dict):
            raise SnapshotVerificationError(
                f"{path.name} line {line_number} must be a JSON object"
            )
        records.append(cast(dict[str, object], parsed))
    return tuple(records)


def _snapshot_candidate_ids(
    records: Iterable[Mapping[str, object]], filename: str
) -> set[str]:
    candidate_ids: set[str] = set()
    for record in records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise SnapshotVerificationError(
                f"{filename} contains a missing candidate_id"
            )
        if candidate_id in candidate_ids:
            raise SnapshotVerificationError(
                f"{filename} contains duplicate candidate_id {candidate_id}"
            )
        candidate_ids.add(candidate_id)
    return candidate_ids


def _validate_snapshot_target_motion_invariant(payload: bytes) -> None:
    """Fail a production freeze if a screened candidate selects multiple motions."""

    for line in payload.splitlines():
        record = cast(object, json.loads(line))
        if not isinstance(record, dict):
            continue
        typed_record = cast(dict[str, object], record)
        ai = typed_record.get("ai")
        if not isinstance(ai, dict):
            continue  # Legacy synthetic store records predate screened-case schema.
        typed_ai = cast(dict[str, object], ai)
        numbers = typed_ai.get("target_motion_entry_numbers")
        if not isinstance(numbers, list) or len(cast(list[object], numbers)) != 1:
            candidate_id = typed_record.get("candidate_id", "unknown")
            raise SnapshotVerificationError(
                f"screened candidate {candidate_id} must select exactly one "
                "target motion"
            )


def _normalize_hit(
    hit: DiscoveryHit | Mapping[str, object],
) -> tuple[str, str, str]:
    if isinstance(hit, Mapping):
        provider_hit_id = _require_text(hit.get("provider_hit_id"), "provider_hit_id")
        candidate_id = _require_text(hit.get("candidate_id"), "candidate_id")
        payload = hit.get("payload", {})
    else:
        provider_hit_id = _require_text(hit.provider_hit_id, "provider_hit_id")
        candidate_id = _require_text(hit.candidate_id, "candidate_id")
        payload = hit.payload
    return provider_hit_id, candidate_id, _canonical_json(payload)


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _require_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"value is not canonical JSON: {error}") from error


def _is_safe_policy_upgrade(
    previous: Mapping[str, object],
    requested: Mapping[str, object],
) -> bool:
    """Recognize the one audited source-specific to source-neutral migration."""

    if previous.get("schema_version") not in _LEGACY_SOURCE_POLICY_SCHEMAS:
        return False
    if requested.get("schema_version") != _SOURCE_NEUTRAL_POLICY_SCHEMA:
        return False
    if set(requested) != {
        "schema_version",
        "eligibility_anchor",
        "screening_source_sha256",
    }:
        return False
    return previous.get("eligibility_anchor") == requested.get(
        "eligibility_anchor"
    ) and previous.get("screening_source_sha256") == requested.get(
        "screening_source_sha256"
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _cursor_key(cursor: str | None) -> str:
    return "null" if cursor is None else f"value:{cursor}"


def _reason_precedence(reason_code: str) -> int:
    policy = _REASON_POLICIES.get(reason_code)
    if policy is None:
        raise CycleAcquisitionStoreError(
            f"stored observation has unknown reason code: {reason_code}"
        )
    return policy[2]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _observation_from_row(row: sqlite3.Row) -> CandidateObservation:
    return CandidateObservation(
        observation_id=int(row["observation_id"]),
        candidate_id=str(row["candidate_id"]),
        batch_id=str(row["batch_id"]),
        state=str(row["state"]),
        reason_code=str(row["reason_code"]),
        evidence=json.loads(row["evidence_json"]),
        observed_at=str(row["observed_at"]),
        supersedes_observation_id=row["supersedes_observation_id"],
    )


def _raw_artifact_from_row(row: sqlite3.Row) -> RawArtifact:
    return RawArtifact(
        artifact_id=int(row["artifact_id"]),
        candidate_id=str(row["candidate_id"]),
        path=Path(row["path"]),
        sha256=str(row["sha256"]),
        byte_count=int(row["byte_count"]),
        retrieved_at=str(row["retrieved_at"]),
    )


def _firecrawl_attempt_from_row(row: sqlite3.Row) -> FirecrawlAttempt:
    artifact_path = row["artifact_path"]
    return FirecrawlAttempt(
        attempt_id=int(row["attempt_id"]),
        run_id=str(row["run_id"]),
        target_id=str(row["target_id"]),
        page_number=int(row["page_number"]),
        attempt_number=int(row["attempt_number"]),
        request_url=str(row["request_url"]),
        reserved_credits=int(row["reserved_credits"]),
        status=str(row["status"]),
        reported_credits=(
            int(row["reported_credits"])
            if row["reported_credits"] is not None
            else None
        ),
        proxy_used=(str(row["proxy_used"]) if row["proxy_used"] is not None else None),
        provider_http_status=(
            int(row["provider_http_status"])
            if row["provider_http_status"] is not None
            else None
        ),
        target_http_status=(
            int(row["target_http_status"])
            if row["target_http_status"] is not None
            else None
        ),
        failure_code=(
            str(row["failure_code"]) if row["failure_code"] is not None else None
        ),
        failure_message=(
            str(row["failure_message"]) if row["failure_message"] is not None else None
        ),
        failure_transient=(
            bool(row["failure_transient"])
            if row["failure_transient"] is not None
            else None
        ),
        failure_response_sha256=(
            str(row["failure_response_sha256"])
            if row["failure_response_sha256"] is not None
            else None
        ),
        artifact_path=Path(str(artifact_path)) if artifact_path is not None else None,
        artifact_sha256=(
            str(row["artifact_sha256"]) if row["artifact_sha256"] is not None else None
        ),
        artifact_byte_count=(
            int(row["artifact_byte_count"])
            if row["artifact_byte_count"] is not None
            else None
        ),
        authorized_at=str(row["authorized_at"]),
        completed_at=(
            str(row["completed_at"]) if row["completed_at"] is not None else None
        ),
    )


def _firecrawl_target_from_row(row: sqlite3.Row) -> FirecrawlTarget:
    return FirecrawlTarget(
        run_id=str(row["run_id"]),
        target_id=str(row["target_id"]),
        target_kind=str(row["target_kind"]),
        source_url=str(row["source_url"]),
        ordinal=int(row["ordinal"]),
        status=str(row["status"]),
    )


def _atomic_write_bytes(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _write_fsynced(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_staging_directory(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        child.unlink(missing_ok=True)
    path.rmdir()


def _jsonl_bytes(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(f"{_canonical_json(record)}\n".encode() for record in records)


def _trim_torn_wal_tail(database: Path) -> None:
    """Trim only bytes that cannot form a complete SQLite WAL frame."""

    wal = Path(f"{database}-wal")
    if not wal.exists():
        return
    size = wal.stat().st_size
    if size == 0:
        return
    if size < 32:
        with wal.open("r+b") as handle:
            handle.truncate(0)
            handle.flush()
            os.fsync(handle.fileno())
        return
    with wal.open("rb") as handle:
        header = handle.read(32)
    page_size = int.from_bytes(header[8:12], "big")
    if page_size == 1:
        page_size = 65_536
    if page_size < 512 or page_size > 65_536 or page_size & (page_size - 1):
        raise CycleAcquisitionStoreError("invalid SQLite WAL page size")
    frame_size = 24 + page_size
    complete_size = 32 + ((size - 32) // frame_size) * frame_size
    if complete_size == size:
        return
    with wal.open("r+b") as handle:
        handle.truncate(complete_size)
        handle.flush()
        os.fsync(handle.fileno())
