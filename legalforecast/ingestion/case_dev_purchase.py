"""Guarded case.dev PACER purchase orchestration."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any, cast
from urllib.parse import quote

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevClientError,
    CaseDevPurchaseOutcomeUnknownError,
    CaseDevResponseError,
    CaseDevServerError,
)
from legalforecast.ingestion.cohort_policy import verify_cohort_policy
from legalforecast.ingestion.missing_core_budget import (
    CaseDocumentCapExceededError,
    MissingCoreBudgetPlan,
    PurchaseBudgetExceededError,
)

CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION = "legalforecast.case_dev_purchase_policy.v1"
PURCHASE_LEDGER_INITIALIZATION_SCHEMA_VERSION = (
    "legalforecast.purchase_ledger_initialization.v1"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CANONICAL_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")

_PURCHASE_LEDGER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS purchase_ledger (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    cycle_id TEXT NOT NULL,
    cohort_policy_sha256 TEXT NOT NULL,
    purchase_policy_sha256 TEXT NOT NULL,
    canonical_ledger_path TEXT NOT NULL,
    hard_cap_usd TEXT NOT NULL,
    opening_committed_spend_usd TEXT NOT NULL,
    max_per_case_usd TEXT NOT NULL,
    per_document_reservation_usd TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_operations (
    source_document_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    reservation_usd TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN
        ('planned','submitted','queued','confirmed','failed','unknown')),
    operation_key TEXT UNIQUE,
    actual_usd TEXT,
    response_json TEXT,
    error TEXT,
    reconciliation_json TEXT
);
CREATE TABLE IF NOT EXISTS replacement_events (
    sequence INTEGER PRIMARY KEY CHECK(sequence >= 0),
    event_key TEXT NOT NULL UNIQUE,
    record_json TEXT NOT NULL,
    record_sha256 TEXT NOT NULL UNIQUE
);
"""

_PURCHASE_MATERIAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS purchase_material_state (
    source_document_id TEXT PRIMARY KEY
        REFERENCES purchase_operations(source_document_id) ON DELETE RESTRICT,
    authority TEXT NOT NULL CHECK(authority IN
        ('ordinary_public','unknown_status_attempt')),
    status TEXT NOT NULL CHECK(status IN
        ('not_recovered','available_pending_quarantine',
         'recovered_pending_clearance','cleared_public')),
    attempt_policy_sha256 TEXT,
    attempt_document_sha256 TEXT,
    provider_detail_sha256 TEXT,
    queue_response_sha256 TEXT,
    download_url_sha256 TEXT,
    content_sha256 TEXT,
    byte_count INTEGER,
    clearance_record_sha256 TEXT,
    resolved_record_sha256 TEXT
);
"""


class CaseDevPurchasePolicyError(ValueError):
    """Raised when the immutable cycle purchase policy is invalid or conflicts."""


class CaseDevPurchaseLedgerError(RuntimeError):
    """Raised when a purchase journal cannot make a safe state transition."""


class CaseDevPurchaseLedgerBusyError(CaseDevPurchaseLedgerError):
    """Raised when another process owns the cycle purchase journal."""


@dataclass(frozen=True, slots=True)
class CaseDevPurchaseSnapshot:
    """Authenticated purchase state read without mutating the canonical ledger."""

    operations: tuple[Mapping[str, Any], ...]
    purchase_state_sha256: str


class CaseDevPurchaseReconciliationRequired(CaseDevPurchaseLedgerError):
    """Raised when an ambiguous paid request needs provider-side evidence."""


class PurchaseMaterialState(StrEnum):
    """Usability of purchased bytes, independent of their billing outcome."""

    NOT_RECOVERED = "not_recovered"
    AVAILABLE_PENDING_QUARANTINE = "available_pending_quarantine"
    RECOVERED_PENDING_CLEARANCE = "recovered_pending_clearance"
    CLEARED_PUBLIC = "cleared_public"


@dataclass(frozen=True, slots=True)
class CaseDevPurchasePolicy:
    """Verified immutable policy controlling one cycle's document purchases."""

    cycle_id: str
    cohort_policy_sha256: str
    canonical_ledger_path: Path
    hard_cap_usd: Decimal
    opening_committed_spend_usd: Decimal
    opening_case_committed_spend_usd: Mapping[str, Decimal]
    max_per_case_usd: Decimal
    per_document_reservation_usd: Decimal
    policy_sha256: str
    fee_schedule: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PurchaseLedgerInitialization:
    """Authenticated identity of one pristine, policy-bound purchase ledger."""

    canonical_ledger_path: Path
    ledger_file_sha256: str
    purchase_state_sha256: str
    ledger_byte_count: int

    def to_record(self, *, policy: CaseDevPurchasePolicy) -> dict[str, object]:
        return {
            "schema_version": PURCHASE_LEDGER_INITIALIZATION_SCHEMA_VERSION,
            "cycle_id": policy.cycle_id,
            "cohort_policy_sha256": policy.cohort_policy_sha256,
            "purchase_policy_sha256": policy.policy_sha256,
            "canonical_ledger_path": str(self.canonical_ledger_path),
            "ledger_file_sha256": self.ledger_file_sha256,
            "purchase_state_sha256": self.purchase_state_sha256,
            "ledger_byte_count": self.ledger_byte_count,
        }


def generate_case_dev_purchase_policy(
    decisions: Mapping[str, object],
) -> dict[str, object]:
    """Validate and hash a pre-committed cycle document-purchase policy."""

    policy = _validated_purchase_policy(decisions)
    return {
        "schema_version": CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION,
        "policy": policy,
        "policy_sha256": _hash(policy),
    }


def verify_case_dev_purchase_policy(
    artifact: Mapping[str, object],
) -> CaseDevPurchasePolicy:
    """Verify a purchase policy artifact and return its typed immutable identity."""

    _exact_keys(
        artifact,
        {"schema_version", "policy", "policy_sha256"},
        "purchase policy artifact",
    )
    if artifact.get("schema_version") != CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION:
        raise CaseDevPurchasePolicyError("unsupported purchase policy schema")
    raw_policy = artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise CaseDevPurchasePolicyError("purchase policy must be an object")
    policy = _validated_purchase_policy(cast(Mapping[str, object], raw_policy))
    committed = _required_sha(artifact.get("policy_sha256"), "policy_sha256")
    if _hash(policy) != committed:
        raise CaseDevPurchasePolicyError("purchase policy hash does not match content")
    fee_schedule = cast(Mapping[str, Any], policy["fee_schedule"])
    return CaseDevPurchasePolicy(
        cycle_id=cast(str, policy["cycle_id"]),
        cohort_policy_sha256=cast(str, policy["cohort_policy_sha256"]),
        canonical_ledger_path=Path(cast(str, policy["canonical_ledger_path"])),
        hard_cap_usd=Decimal(cast(str, policy["hard_cap_usd"])),
        opening_committed_spend_usd=Decimal(
            cast(str, policy["opening_committed_spend_usd"])
        ),
        opening_case_committed_spend_usd=MappingProxyType(
            {
                case_id: Decimal(amount)
                for case_id, amount in cast(
                    Mapping[str, str], policy["opening_case_committed_spend_usd"]
                ).items()
            }
        ),
        max_per_case_usd=Decimal(cast(str, policy["max_per_case_usd"])),
        per_document_reservation_usd=Decimal(
            cast(str, policy["per_document_reservation_usd"])
        ),
        policy_sha256=committed,
        fee_schedule=fee_schedule,
    )


def write_case_dev_purchase_policy(
    path: str | Path,
    artifact: Mapping[str, object],
) -> Path:
    """Atomically publish an immutable verified purchase policy artifact."""

    verify_case_dev_purchase_policy(artifact)
    target = Path(path)
    payload = f"{json.dumps(artifact, indent=2, sort_keys=True)}\n".encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != payload:
            raise CaseDevPurchasePolicyError(
                "refusing to overwrite a different purchase policy artifact"
            )
        return target
    fd, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise CaseDevPurchasePolicyError(
                "purchase policy was concurrently created with different content"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def verify_case_dev_purchase_policy_cohort_binding(
    policy: CaseDevPurchasePolicy,
    cohort_artifact: Mapping[str, Any],
) -> None:
    """Require the purchase envelope to consume the frozen cohort policy caps."""

    cohort_hash = verify_cohort_policy(cohort_artifact)
    if policy.cohort_policy_sha256 != cohort_hash:
        raise CaseDevPurchasePolicyError(
            "purchase policy is bound to a different cohort policy hash"
        )
    raw_policy = cohort_artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise CaseDevPurchasePolicyError("cohort policy content must be an object")
    typed_policy = cast(Mapping[str, object], raw_policy)
    raw_purchase = typed_policy.get("purchase_policy")
    if not isinstance(raw_purchase, Mapping):
        raise CaseDevPurchasePolicyError(
            "cohort purchase policy content must be an object"
        )
    typed_purchase = cast(Mapping[str, object], raw_purchase)
    cohort_cap = _policy_money(
        typed_purchase.get("cycle_budget_usd"), "cohort cycle_budget_usd"
    )
    cohort_per_case = _policy_money(
        typed_purchase.get("max_per_case_usd"), "cohort max_per_case_usd"
    )
    if policy.hard_cap_usd != cohort_cap:
        raise CaseDevPurchasePolicyError(
            "purchase hard cap must equal the frozen cohort cycle budget"
        )
    if policy.max_per_case_usd != cohort_per_case:
        raise CaseDevPurchasePolicyError(
            "purchase per-case cap must equal the frozen cohort per-case cap"
        )


def initialize_case_dev_purchase_journal(
    path: str | Path,
    *,
    policy: CaseDevPurchasePolicy,
    receipt_path: str | Path,
    purchase_policy_file_sha256: str,
    cohort_policy_file_sha256: str,
    initialized_at: str,
) -> dict[str, object]:
    """Exclusively create one pristine ledger under its canonical lock.

    Any failure after the exclusive file creation deliberately leaves the file in
    place. A later invocation therefore refuses to guess whether initialization
    completed; an operator must preserve and investigate the partial artifact.
    """

    ledger_path = _canonical_requested_ledger_path(path, policy=policy)
    receipt = _validated_purchase_ledger_receipt_path(
        ledger_path,
        receipt_path,
        prepare_parent=True,
    )
    _prepare_canonical_ledger_parent(ledger_path)
    lock_fd = _acquire_purchase_ledger_lock(ledger_path)
    try:
        _refuse_existing_purchase_ledger(ledger_path)
        _refuse_existing_sqlite_sidecars(ledger_path)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        ledger_fd = os.open(ledger_path, flags, 0o600)
        try:
            ledger_stat = os.fstat(ledger_fd)
            if not stat.S_ISREG(ledger_stat.st_mode) or ledger_stat.st_nlink != 1:
                raise CaseDevPurchaseLedgerError(
                    "new purchase ledger must be a singly linked regular file"
                )
            os.fsync(ledger_fd)
        finally:
            os.close(ledger_fd)

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(ledger_path, isolation_level=None)
            connection.row_factory = sqlite3.Row
            # Keep the pristine initialization artifact self-contained. The
            # runtime journal enables WAL on its first operational open.
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            _create_purchase_ledger_schema(connection)
            _bind_purchase_ledger_policy(connection, policy, insert=True)
            _require_pristine_purchase_ledger(connection)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or str(integrity[0]) != "ok":
                raise CaseDevPurchaseLedgerError(
                    "new purchase ledger failed SQLite integrity verification"
                )
        finally:
            if connection is not None:
                connection.close()

        _fsync_directory(ledger_path.parent)
        initialization = _purchase_ledger_initialization_identity(
            ledger_path,
            policy=policy,
            require_pristine=True,
        )
        record = _purchase_ledger_initialization_receipt(
            initialization,
            policy=policy,
            purchase_policy_file_sha256=purchase_policy_file_sha256,
            cohort_policy_file_sha256=cohort_policy_file_sha256,
            initialized_at=initialized_at,
        )
        _write_immutable_purchase_ledger_receipt(receipt, record)
        published_record = _read_purchase_ledger_initialization_receipt(receipt)
        if published_record != record:
            raise CaseDevPurchaseLedgerError(
                "purchase ledger initialization receipt changed during publication"
            )
        final_identity = _purchase_ledger_initialization_identity(
            ledger_path,
            policy=policy,
            require_pristine=True,
        )
        if final_identity != initialization:
            raise CaseDevPurchaseLedgerError(
                "purchase ledger changed while publishing initialization receipt"
            )
        final_record = _read_purchase_ledger_initialization_receipt(receipt)
        if final_record != record:
            raise CaseDevPurchaseLedgerError(
                "purchase ledger initialization receipt changed during publication"
            )
        return record
    except FileExistsError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger already exists; refusing initialization or repair"
        ) from exc
    finally:
        _release_purchase_ledger_lock(lock_fd)


def verify_case_dev_purchase_journal_initialization(
    path: str | Path,
    *,
    policy: CaseDevPurchasePolicy,
    receipt_path: str | Path,
    purchase_policy_file_sha256: str,
    cohort_policy_file_sha256: str,
) -> dict[str, object]:
    """Read-only verify a previously initialized, still-pristine ledger."""

    ledger_path = _canonical_requested_ledger_path(path, policy=policy)
    receipt = _validated_purchase_ledger_receipt_path(
        ledger_path,
        receipt_path,
        prepare_parent=False,
    )
    if ledger_path.parent.resolve() != ledger_path.parent:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger parent path must not traverse a symlink"
        )
    lock_fd = _acquire_purchase_ledger_lock(ledger_path)
    try:
        initialization = _purchase_ledger_initialization_identity(
            ledger_path,
            policy=policy,
            require_pristine=True,
        )
        record = _read_purchase_ledger_initialization_receipt(receipt)
        _verify_purchase_ledger_initialization_receipt(
            record,
            initialization=initialization,
            policy=policy,
            purchase_policy_file_sha256=purchase_policy_file_sha256,
            cohort_policy_file_sha256=cohort_policy_file_sha256,
        )
        final_identity = _purchase_ledger_initialization_identity(
            ledger_path,
            policy=policy,
            require_pristine=True,
        )
        if final_identity != initialization:
            raise CaseDevPurchaseLedgerError(
                "purchase ledger changed while verifying initialization receipt"
            )
        final_record = _read_purchase_ledger_initialization_receipt(receipt)
        if final_record != record:
            raise CaseDevPurchaseLedgerError(
                "purchase ledger initialization receipt changed during verification"
            )
        return record
    finally:
        _release_purchase_ledger_lock(lock_fd)


def _canonical_requested_ledger_path(
    path: str | Path,
    *,
    policy: CaseDevPurchasePolicy,
) -> Path:
    requested = Path(path)
    if not requested.is_absolute() or requested != policy.canonical_ledger_path:
        raise CaseDevPurchasePolicyError(
            "purchase ledger path conflicts with canonical policy locator"
        )
    return requested


def _purchase_ledger_reserved_paths(path: Path) -> tuple[Path, ...]:
    return (
        path,
        Path(f"{path}.lock"),
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    )


def _validate_purchase_ledger_receipt_namespace(
    ledger_path: Path,
    receipt_path: Path,
) -> None:
    if receipt_path.is_symlink():
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt must not be a symlink"
        )
    ledger = ledger_path.absolute()
    receipt = receipt_path.absolute()
    for reserved_path in _purchase_ledger_reserved_paths(ledger):
        reserved = reserved_path.absolute()
        if (
            receipt == reserved
            or receipt in reserved.parents
            or reserved in receipt.parents
        ):
            raise CaseDevPurchaseLedgerError(
                "purchase ledger initialization receipt conflicts with a reserved "
                f"ledger path: {reserved_path}"
            )


def _validated_purchase_ledger_receipt_path(
    ledger_path: Path,
    receipt_path: str | Path,
    *,
    prepare_parent: bool,
) -> Path:
    """Return an absolute receipt path only after rejecting symlink traversal."""

    requested_receipt = Path(receipt_path)
    if ".." in requested_receipt.parts:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt path must not contain "
            "dot-dot components"
        )
    receipt = requested_receipt.absolute()
    if receipt.is_symlink():
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt must not be a symlink"
        )
    _validate_existing_path_parent(
        receipt,
        label="purchase ledger initialization receipt",
    )
    _validate_purchase_ledger_receipt_namespace(ledger_path, receipt)
    _validate_or_prepare_path_parent(
        receipt,
        create_missing=prepare_parent,
        label="purchase ledger initialization receipt",
    )
    return receipt


def _refuse_existing_sqlite_sidecars(path: Path) -> None:
    for sidecar in (Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal")):
        try:
            sidecar.lstat()
        except FileNotFoundError:
            continue
        raise CaseDevPurchaseLedgerError(
            f"purchase ledger SQLite sidecar already exists: {sidecar}"
        )


def _prepare_canonical_ledger_parent(path: Path) -> None:
    _validate_or_prepare_path_parent(
        path,
        create_missing=True,
        label="purchase ledger",
    )


def _validate_existing_path_parent(path: Path, *, label: str) -> None:
    current = Path(path.anchor)
    for component in path.parent.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(metadata.st_mode):
            raise CaseDevPurchaseLedgerError(
                f"{label} parent path must not traverse a symlink"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise CaseDevPurchaseLedgerError(f"{label} parent must be a directory")


def _validate_or_prepare_path_parent(
    path: Path,
    *,
    create_missing: bool,
    label: str,
) -> None:
    current = Path(path.anchor)
    for component in path.parent.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if not create_missing:
                raise CaseDevPurchaseLedgerError(
                    f"{label} parent path is missing: {current}"
                ) from None
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                metadata = current.lstat()
            else:
                metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise CaseDevPurchaseLedgerError(
                f"{label} parent path must not traverse a symlink"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise CaseDevPurchaseLedgerError(f"{label} parent must be a directory")


def _acquire_purchase_ledger_lock(path: Path) -> int:
    lock_path = Path(f"{path}.lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock must be a regular non-symlink file"
        ) from exc
    lock_stat = os.fstat(lock_fd)
    if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
        os.close(lock_fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock must be a singly linked regular file"
        )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise CaseDevPurchaseLedgerBusyError(
            f"cycle purchase journal is already locked: {path}"
        ) from exc
    try:
        locked_stat = os.fstat(lock_fd)
        path_stat = lock_path.lstat()
    except OSError as exc:
        _release_purchase_ledger_lock(lock_fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock path changed while acquiring the lock"
        ) from exc
    if (
        not stat.S_ISREG(locked_stat.st_mode)
        or locked_stat.st_nlink != 1
        or not stat.S_ISREG(path_stat.st_mode)
        or path_stat.st_nlink != 1
        or (locked_stat.st_dev, locked_stat.st_ino)
        != (path_stat.st_dev, path_stat.st_ino)
    ):
        _release_purchase_ledger_lock(lock_fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock path changed while acquiring the lock"
        )
    return lock_fd


def _acquire_existing_purchase_ledger_lock(path: Path) -> int:
    """Acquire the canonical lock without creating or writing any path."""

    lock_path = Path(f"{path}.lock")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        lock_fd = os.open(lock_path, flags)
    except OSError as exc:
        raise CaseDevPurchaseLedgerError(
            "read-only purchase audit requires the existing canonical lock file"
        ) from exc
    lock_stat = os.fstat(lock_fd)
    try:
        path_stat = lock_path.lstat()
    except OSError as exc:
        os.close(lock_fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock path changed while opening read-only"
        ) from exc
    if (
        not stat.S_ISREG(lock_stat.st_mode)
        or lock_stat.st_nlink != 1
        or not stat.S_ISREG(path_stat.st_mode)
        or path_stat.st_nlink != 1
        or (lock_stat.st_dev, lock_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino)
    ):
        os.close(lock_fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger lock must be a singly linked regular file"
        )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise CaseDevPurchaseLedgerBusyError(
            f"cycle purchase journal is already locked: {path}"
        ) from exc
    return lock_fd


def _release_purchase_ledger_lock(lock_fd: int) -> None:
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)


def _refuse_existing_purchase_ledger(path: Path) -> None:
    try:
        existing = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(existing.st_mode):
        detail = "symlink"
    elif existing.st_nlink != 1:
        detail = "hard-linked path"
    elif existing.st_size == 0:
        detail = "empty path"
    else:
        detail = "existing path"
    raise CaseDevPurchaseLedgerError(
        f"purchase ledger {detail} already exists; refusing initialization or repair"
    )


def _purchase_ledger_initialization_identity(
    path: Path,
    *,
    policy: CaseDevPurchasePolicy,
    require_pristine: bool,
) -> PurchaseLedgerInitialization:
    ledger_stat = path.lstat()
    if not stat.S_ISREG(ledger_stat.st_mode) or ledger_stat.st_nlink != 1:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger must be a singly linked regular file"
        )
    for sidecar in (
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    ):
        try:
            sidecar.lstat()
        except FileNotFoundError:
            continue
        raise CaseDevPurchaseLedgerError(
            "purchase ledger has an unexpected SQLite sidecar during "
            "initialization verification"
        )
    uri = f"file:{quote(path.as_posix(), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or str(integrity[0]) != "ok":
            raise CaseDevPurchaseLedgerError(
                "purchase ledger failed SQLite integrity verification"
            )
        _bind_purchase_ledger_policy(connection, policy, insert=False)
        if require_pristine:
            _require_pristine_purchase_ledger(connection)
    except sqlite3.Error as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger is missing a complete authenticated schema"
        ) from exc
    finally:
        connection.close()
    file_sha256, byte_count = _hash_regular_single_link_file(path)
    return PurchaseLedgerInitialization(
        canonical_ledger_path=path,
        ledger_file_sha256=file_sha256,
        purchase_state_sha256=_initial_purchase_state_sha256(policy),
        ledger_byte_count=byte_count,
    )


def _purchase_ledger_initialization_receipt(
    initialization: PurchaseLedgerInitialization,
    *,
    policy: CaseDevPurchasePolicy,
    purchase_policy_file_sha256: str,
    cohort_policy_file_sha256: str,
    initialized_at: str,
) -> dict[str, object]:
    _required_sha256_commitment(
        purchase_policy_file_sha256, "purchase_policy_file_sha256"
    )
    _required_sha256_commitment(cohort_policy_file_sha256, "cohort_policy_file_sha256")
    if not initialized_at:
        raise CaseDevPurchaseLedgerError("initialized_at must be nonempty")
    return {
        **initialization.to_record(policy=policy),
        "purchase_policy_file_sha256": purchase_policy_file_sha256,
        "cohort_policy_file_sha256": cohort_policy_file_sha256,
        "initialized_at": initialized_at,
        "dry_run": False,
        "initialized_or_verified": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_paid_activity_requested": False,
        "pacer_paid_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }


def _required_sha256_commitment(value: str, label: str) -> None:
    if not value.startswith("sha256:") or _SHA256.fullmatch(value[7:]) is None:
        raise CaseDevPurchaseLedgerError(f"{label} must be a sha256: commitment")


def _write_immutable_purchase_ledger_receipt(
    path: Path,
    record: Mapping[str, object],
) -> None:
    _prepare_canonical_ledger_parent(path)
    payload = f"{json.dumps(dict(record), indent=2, sort_keys=True)}\n".encode()
    temporary_path: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, path)
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt already exists"
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_purchase_ledger_initialization_receipt(
    path: Path,
) -> dict[str, object]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt is missing"
        ) from exc
    except OSError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt must be a regular non-symlink file"
        ) from exc
    try:
        metadata = os.fstat(fd)
        path_metadata = path.lstat()
    except OSError as exc:
        os.close(fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt path changed while opening"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or not stat.S_ISREG(path_metadata.st_mode)
        or path_metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino)
        != (path_metadata.st_dev, path_metadata.st_ino)
    ):
        os.close(fd)
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt must be a singly linked "
            "regular file"
        )
    try:
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt is not valid JSON"
        ) from exc
    try:
        final_metadata = path.lstat()
    except OSError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt path changed while reading"
        ) from exc
    if (
        not stat.S_ISREG(final_metadata.st_mode)
        or final_metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino)
        != (final_metadata.st_dev, final_metadata.st_ino)
    ):
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt path changed while reading"
        )
    if not isinstance(loaded, dict):
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt must be an object"
        )
    return cast(dict[str, object], loaded)


def _verify_purchase_ledger_initialization_receipt(
    receipt: Mapping[str, object],
    *,
    initialization: PurchaseLedgerInitialization,
    policy: CaseDevPurchasePolicy,
    purchase_policy_file_sha256: str,
    cohort_policy_file_sha256: str,
) -> None:
    initialized_at = receipt.get("initialized_at")
    if not isinstance(initialized_at, str) or not initialized_at:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt is missing initialized_at"
        )
    expected = _purchase_ledger_initialization_receipt(
        initialization,
        policy=policy,
        purchase_policy_file_sha256=purchase_policy_file_sha256,
        cohort_policy_file_sha256=cohort_policy_file_sha256,
        initialized_at=initialized_at,
    )
    if dict(receipt) != expected:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger initialization receipt does not match ledger state"
        )


def _require_pristine_purchase_ledger(connection: sqlite3.Connection) -> None:
    operations = connection.execute(
        "SELECT COUNT(*) FROM purchase_operations"
    ).fetchone()
    replacements = connection.execute(
        "SELECT COUNT(*) FROM replacement_events"
    ).fetchone()
    if (
        operations is None
        or replacements is None
        or int(operations[0]) != 0
        or int(replacements[0]) != 0
    ):
        raise CaseDevPurchaseLedgerError(
            "purchase ledger is no longer in its pristine initialized state"
        )


def _initial_purchase_state_sha256(policy: CaseDevPurchasePolicy) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "cycle_id": policy.cycle_id,
                "cohort_policy_sha256": policy.cohort_policy_sha256,
                "purchase_policy_sha256": policy.policy_sha256,
                "committed_amount_usd": _money(policy.opening_committed_spend_usd),
                "operations": [],
            }
        ).encode()
    ).hexdigest()


def _hash_regular_single_link_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    digest = hashlib.sha256()
    byte_count = 0
    try:
        opened = os.fstat(fd)
        current = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise CaseDevPurchaseLedgerError(
                "purchase ledger identity changed during verification"
            )
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            byte_count += len(chunk)
    finally:
        os.close(fd)
    return digest.hexdigest(), byte_count


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _require_existing_purchase_ledger_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger is missing; run init-purchase-ledger first"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size == 0
    ):
        raise CaseDevPurchaseLedgerError(
            "purchase ledger must be a nonempty singly linked regular file "
            "created by init-purchase-ledger"
        )


def _verify_existing_purchase_ledger_under_lock(
    path: Path,
    *,
    policy: CaseDevPurchasePolicy,
) -> None:
    _require_existing_purchase_ledger_file(path)
    uri = f"file:{quote(path.as_posix(), safe='/')}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity is None or str(integrity[0]) != "ok":
                raise CaseDevPurchaseLedgerError(
                    "purchase ledger failed SQLite quick_check"
                )
            _bind_purchase_ledger_policy(connection, policy, insert=False)
            required_tables = {
                "purchase_ledger",
                "purchase_operations",
                "replacement_events",
            }
            rows = connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table'"
            ).fetchall()
            tables = {str(row["name"]): str(row["sql"]) for row in rows}
            if not required_tables.issubset(tables):
                raise CaseDevPurchaseLedgerError(
                    "purchase ledger is missing the authenticated runtime schema"
                )
            expected_operation_columns = {
                "source_document_id",
                "candidate_id",
                "reservation_usd",
                "status",
                "operation_key",
                "actual_usd",
                "response_json",
                "error",
                "reconciliation_json",
            }
            actual_operation_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(purchase_operations)"
                ).fetchall()
            }
            if actual_operation_columns != expected_operation_columns:
                raise CaseDevPurchaseLedgerError(
                    "purchase operations schema is not an exact supported version"
                )
            # A legacy initialized ledger may predate asynchronous `queued`.
            # The caller still holds the canonical external lock and performs
            # the only accepted in-place migration before any provider action.
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger is not a complete authenticated SQLite journal"
        ) from exc


def _create_purchase_ledger_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(_PURCHASE_LEDGER_SCHEMA_SQL)
    connection.executescript(_PURCHASE_MATERIAL_SCHEMA_SQL)
    connection.execute("PRAGMA user_version=2")


def _purchase_ledger_policy_identity(
    policy: CaseDevPurchasePolicy,
) -> tuple[str, ...]:
    return (
        policy.cycle_id,
        policy.cohort_policy_sha256,
        policy.policy_sha256,
        str(policy.canonical_ledger_path),
        _money(policy.hard_cap_usd),
        _money(policy.opening_committed_spend_usd),
        _money(policy.max_per_case_usd),
        _money(policy.per_document_reservation_usd),
    )


def _bind_purchase_ledger_policy(
    connection: sqlite3.Connection,
    policy: CaseDevPurchasePolicy,
    *,
    insert: bool,
) -> None:
    expected = _purchase_ledger_policy_identity(policy)
    if insert:
        with connection:
            connection.execute(
                """INSERT OR IGNORE INTO purchase_ledger(
                singleton, cycle_id, cohort_policy_sha256, purchase_policy_sha256,
                canonical_ledger_path, hard_cap_usd, opening_committed_spend_usd,
                max_per_case_usd, per_document_reservation_usd)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                expected,
            )
    row = connection.execute(
        "SELECT * FROM purchase_ledger WHERE singleton=1"
    ).fetchone()
    if row is None:
        raise CaseDevPurchaseLedgerError(
            "purchase journal is missing its immutable policy identity"
        )
    actual = tuple(
        str(row[field])
        for field in (
            "cycle_id",
            "cohort_policy_sha256",
            "purchase_policy_sha256",
            "canonical_ledger_path",
            "hard_cap_usd",
            "opening_committed_spend_usd",
            "max_per_case_usd",
            "per_document_reservation_usd",
        )
    )
    if actual != expected:
        raise CaseDevPurchasePolicyError(
            "purchase journal identity conflicts with immutable cycle policy"
        )


class CaseDevPurchaseJournal:
    """Single-writer durable state machine for non-idempotent paid POSTs."""

    def __init__(
        self,
        path: str | Path,
        *,
        policy: CaseDevPurchasePolicy,
        allow_create: bool = False,
    ) -> None:
        self.path = Path(path).resolve()
        if self.path != policy.canonical_ledger_path:
            raise CaseDevPurchasePolicyError(
                "purchase ledger path conflicts with canonical policy locator"
            )
        self.policy = policy
        self._closed = False
        if allow_create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            _require_existing_purchase_ledger_file(self.path)
        self._lock_path = Path(f"{self.path}.lock")
        self._lock_fd = _acquire_purchase_ledger_lock(self.path)
        try:
            if not self.path.exists():
                if not allow_create:
                    raise CaseDevPurchaseLedgerError(
                        "purchase ledger is missing; run init-purchase-ledger first"
                    )
                fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            elif not allow_create:
                _verify_existing_purchase_ledger_under_lock(
                    self.path,
                    policy=policy,
                )
            self._connection: sqlite3.Connection = sqlite3.connect(
                self.path, isolation_level=None
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._create_schema()
            self._bind_policy()
        except BaseException:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            _release_purchase_ledger_lock(self._lock_fd)
            raise

    def __enter__(self) -> CaseDevPurchaseJournal:
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
        self._connection.close()
        _release_purchase_ledger_lock(self._lock_fd)
        self._closed = True

    def plan(self, plan: MissingCoreBudgetPlan) -> None:
        """Persist every intent as planned before any submission can occur."""

        reservation = self.policy.per_document_reservation_usd
        with self._connection:
            for case_plan in plan.case_plans:
                existing_ids = {
                    str(row["source_document_id"])
                    for row in self._connection.execute(
                        """SELECT source_document_id FROM purchase_operations
                        WHERE candidate_id=?""",
                        (case_plan.candidate_id,),
                    ).fetchall()
                }
                new_ids = set(case_plan.purchase_document_ids) - existing_ids
                cumulative_reservation = self._candidate_cap_amount(
                    case_plan.candidate_id
                ) + reservation * len(new_ids)
                if cumulative_reservation > self.policy.max_per_case_usd:
                    raise CaseDevPurchaseLedgerError(
                        f"{case_plan.candidate_id} cumulative reservation exceeds "
                        "per-case cap"
                    )
                for document_id in case_plan.purchase_document_ids:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO purchase_operations(
                        source_document_id, candidate_id, reservation_usd, status)
                        VALUES (?, ?, ?, 'planned')""",
                        (document_id, case_plan.candidate_id, _money(reservation)),
                    )
                    self._connection.execute(
                        """INSERT OR IGNORE INTO purchase_material_state(
                        source_document_id, authority, status)
                        VALUES (?, 'ordinary_public', 'not_recovered')""",
                        (document_id,),
                    )
                    row = self._operation(document_id)
                    assert row is not None
                    if str(row["candidate_id"]) != case_plan.candidate_id or str(
                        row["reservation_usd"]
                    ) != _money(reservation):
                        raise CaseDevPurchaseLedgerError(
                            f"purchase intent conflicts for document {document_id}"
                        )

    def authorize_unknown_material_attempts(
        self,
        allowed_documents: Mapping[str, Mapping[str, str]],
        *,
        attempt_policy_sha256: str,
    ) -> None:
        """Bind exact unknown-status attempt authority before any paid submit.

        This changes only the material-clearance track. Billing reservations and
        operation keys remain owned by this journal's ordinary purchase state
        machine and single-writer lock.
        """

        if _SHA256.fullmatch(attempt_policy_sha256) is None:
            raise CaseDevPurchaseLedgerError(
                "attempt policy SHA-256 must be lowercase hexadecimal"
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            for document_id, authority_record in sorted(allowed_documents.items()):
                candidate_id = authority_record.get("case_id")
                document_sha256 = authority_record.get("selection_document_sha256")
                if (
                    not isinstance(candidate_id, str)
                    or _SHA256.fullmatch(str(document_sha256)) is None
                ):
                    raise CaseDevPurchaseLedgerError(
                        "unknown-attempt document authority is invalid"
                    )
                row = self._operation(document_id)
                if row is None:
                    raise CaseDevPurchaseLedgerError(
                        f"unknown-attempt document is not planned: {document_id}"
                    )
                if str(row["candidate_id"]) != candidate_id:
                    raise CaseDevPurchaseLedgerError(
                        f"unknown-attempt candidate identity conflicts: {document_id}"
                    )
                if str(row["status"]) != "planned":
                    raise CaseDevPurchaseLedgerError(
                        "unknown-attempt authority must be bound before submit"
                    )
                material = self._material(document_id)
                if material is None:
                    raise CaseDevPurchaseLedgerError(
                        f"purchase material state is missing: {document_id}"
                    )
                authority = str(material["authority"])
                prior_policy = material["attempt_policy_sha256"]
                prior_document = material["attempt_document_sha256"]
                if authority == "unknown_status_attempt":
                    if (
                        prior_policy != attempt_policy_sha256
                        or prior_document != document_sha256
                    ):
                        raise CaseDevPurchaseLedgerError(
                            "unknown-attempt authority is immutable"
                        )
                    continue
                if authority != "ordinary_public" or prior_policy is not None:
                    raise CaseDevPurchaseLedgerError(
                        "purchase material authority is invalid"
                    )
                cursor = self._connection.execute(
                    """UPDATE purchase_material_state
                    SET authority='unknown_status_attempt',
                        attempt_policy_sha256=?, attempt_document_sha256=?
                    WHERE source_document_id=? AND status='not_recovered'
                      AND authority='ordinary_public'
                      AND attempt_policy_sha256 IS NULL
                      AND attempt_document_sha256 IS NULL""",
                    (attempt_policy_sha256, document_sha256, document_id),
                )
                if cursor.rowcount != 1:
                    raise CaseDevPurchaseLedgerError(
                        "unknown-attempt authority transition failed"
                    )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def require_reconciled(self) -> None:
        row = self._connection.execute(
            """SELECT source_document_id, status FROM purchase_operations
            WHERE status='submitted' OR
              (status='unknown' AND reconciliation_json IS NULL)
            ORDER BY source_document_id LIMIT 1"""
        ).fetchone()
        if row is not None:
            identity = row["source_document_id"]
            status = row["status"]
            raise CaseDevPurchaseReconciliationRequired(
                f"document {identity} has {status} paid outcome; "
                "billing receipt, statement export, support confirmation, or a "
                "counted write-off is required before any reissue"
            )

    def submit(
        self,
        document_id: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Reserve cap and durably commit submitted immediately before one POST."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._operation(document_id)
            if row is None:
                raise CaseDevPurchaseLedgerError("purchase intent was not planned")
            status = str(row["status"])
            if status == "confirmed":
                self._connection.commit()
                return False
            if status != "planned":
                raise CaseDevPurchaseReconciliationRequired(
                    f"document {document_id} has {status} paid outcome"
                )
            reservation = Decimal(str(row["reservation_usd"]))
            candidate_id = str(row["candidate_id"])
            if self._candidate_cap_amount(candidate_id) > self.policy.max_per_case_usd:
                raise CaseDevPurchaseLedgerError(
                    f"{candidate_id} cumulative reservation exceeds per-case cap"
                )
            if (
                Decimal(self.committed_amount_usd) + reservation
                > self.policy.hard_cap_usd
            ):
                raise CaseDevPurchaseLedgerError(
                    f"document {document_id} reservation would exceed cycle cap"
                )
            operation_key = str(uuid.uuid4())
            cursor = self._connection.execute(
                """UPDATE purchase_operations
                SET status='submitted', operation_key=?, response_json=?
                WHERE source_document_id=? AND status='planned'""",
                (
                    operation_key,
                    None if context is None else _canonical(context),
                    document_id,
                ),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("purchase submit transition failed")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        return True

    def confirm(
        self,
        document_id: str,
        *,
        response: Mapping[str, Any],
        fees: Mapping[str, str],
    ) -> None:
        actual = Decimal(fees["total_usd"])
        row = self._operation(document_id)
        if row is None:
            raise CaseDevPurchaseLedgerError("purchase operation is missing")
        material = self._material(document_id)
        if material is None:
            raise CaseDevPurchaseLedgerError("purchase material state is missing")
        if str(material["authority"]) == "unknown_status_attempt":
            raise CaseDevPurchaseLedgerError(
                "unknown-status billing must use URL-free broker reconciliation"
            )
        if actual > Decimal(str(row["reservation_usd"])):
            with self._connection:
                cursor = self._connection.execute(
                    """UPDATE purchase_operations SET status='unknown',
                    actual_usd=?, response_json=?, error=?
                    WHERE source_document_id=? AND status='submitted'""",
                    (
                        _money(actual),
                        _canonical(response),
                        "provider fee exceeded verified worst-case reservation",
                        document_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CaseDevPurchaseLedgerError("over-cap fee transition failed")
            raise CaseDevPurchaseLedgerError(
                "provider fee exceeds the verified worst-case reservation"
            )
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='confirmed',
                actual_usd=?, response_json=?, error=NULL
                WHERE source_document_id=? AND status='submitted'""",
                (_money(actual), _canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot confirm unsubmitted purchase")

    def queue(self, document_id: str, *, response: Mapping[str, Any]) -> None:
        """Durably record the provider queue identity after the one paid POST."""

        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='queued', response_json=?,
                error=NULL WHERE source_document_id=? AND status='submitted'""",
                (_canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot queue unsubmitted purchase")

    def confirm_reserved(
        self,
        document_id: str,
        *,
        response: Mapping[str, Any],
    ) -> None:
        """Confirm delivery while retaining the worst-case reservation as spend."""

        row = self._operation(document_id)
        if row is None:
            raise CaseDevPurchaseLedgerError("purchase operation is missing")
        material = self._material(document_id)
        if material is None:
            raise CaseDevPurchaseLedgerError("purchase material state is missing")
        if str(material["authority"]) == "unknown_status_attempt":
            raise CaseDevPurchaseLedgerError(
                "unknown-status recovery must remain quarantined"
            )

        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='confirmed',
                actual_usd=NULL, response_json=?, error=NULL
                WHERE source_document_id=? AND status='queued'""",
                (_canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("cannot confirm unqueued purchase")

    def mark_material_available_for_quarantine(
        self,
        document_id: str,
        *,
        provider_detail_sha256: str,
        queue_response_sha256: str,
        download_url_sha256: str,
    ) -> None:
        """Record available unknown material without changing billing state."""

        for label, digest in (
            ("provider detail", provider_detail_sha256),
            ("queue response", queue_response_sha256),
            ("download URL", download_url_sha256),
        ):
            if _SHA256.fullmatch(digest) is None:
                raise CaseDevPurchaseLedgerError(
                    f"{label} digest must be lowercase SHA-256"
                )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            operation = self._operation(document_id)
            material = self._material(document_id)
            if operation is None or material is None:
                raise CaseDevPurchaseLedgerError("purchase operation is missing")
            if operation["operation_key"] is None or str(operation["status"]) not in {
                "submitted",
                "queued",
                "unknown",
                "confirmed",
            }:
                raise CaseDevPurchaseLedgerError(
                    "unknown material availability requires consumed submit authority"
                )
            if str(material["status"]) == (
                PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE.value
            ):
                expected = (
                    provider_detail_sha256,
                    queue_response_sha256,
                    download_url_sha256,
                )
                actual = (
                    material["provider_detail_sha256"],
                    material["queue_response_sha256"],
                    material["download_url_sha256"],
                )
                if actual != expected:
                    raise CaseDevPurchaseLedgerError(
                        "unknown material availability replay conflicts"
                    )
                self._connection.commit()
                return
            cursor = self._connection.execute(
                """UPDATE purchase_material_state
                SET status=?, provider_detail_sha256=?, queue_response_sha256=?,
                    download_url_sha256=?
                WHERE source_document_id=?
                  AND authority='unknown_status_attempt'
                  AND status=?""",
                (
                    PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE.value,
                    provider_detail_sha256,
                    queue_response_sha256,
                    download_url_sha256,
                    document_id,
                    PurchaseMaterialState.NOT_RECOVERED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "cannot mark unavailable or already-recovered material available"
                )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def record_quarantined_material_bytes(
        self,
        document_id: str,
        *,
        content_sha256: str,
        byte_count: int,
    ) -> None:
        """Commit quarantined bytes without making them parser-eligible."""

        if (
            _SHA256.fullmatch(content_sha256) is None
            or isinstance(byte_count, bool)
            or byte_count <= 0
        ):
            raise CaseDevPurchaseLedgerError(
                "quarantined bytes require canonical SHA-256 and positive size"
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            operation = self._operation(document_id)
            material = self._material(document_id)
            if operation is None or material is None:
                raise CaseDevPurchaseLedgerError("purchase operation is missing")
            if operation["operation_key"] is None or str(operation["status"]) not in {
                "submitted",
                "queued",
                "unknown",
                "confirmed",
            }:
                raise CaseDevPurchaseLedgerError(
                    "quarantined bytes require consumed submit authority"
                )
            if str(material["status"]) == (
                PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE.value
            ):
                if (
                    material["content_sha256"] != content_sha256
                    or material["byte_count"] != byte_count
                ):
                    raise CaseDevPurchaseLedgerError(
                        "quarantined material replay conflicts"
                    )
                self._connection.commit()
                return
            cursor = self._connection.execute(
                """UPDATE purchase_material_state
                SET status=?, content_sha256=?, byte_count=?
                WHERE source_document_id=?
                  AND authority='unknown_status_attempt'
                  AND status=?""",
                (
                    PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE.value,
                    content_sha256,
                    byte_count,
                    document_id,
                    PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE.value,
                ),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "quarantined bytes require available unknown-status material"
                )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def clear_unknown_material(
        self,
        document_id: str,
        *,
        resolved_record: Mapping[str, Any],
    ) -> None:
        """Make exact cleared bytes usable without changing billing state."""

        record_sha256 = resolved_record.get("record_sha256")
        if (
            not isinstance(record_sha256, str)
            or _SHA256.fullmatch(record_sha256) is None
        ):
            raise CaseDevPurchaseLedgerError("resolved material record hash is invalid")
        unhashed = {
            key: value
            for key, value in resolved_record.items()
            if key != "record_sha256"
        }
        if hashlib.sha256(_canonical(unhashed).encode()).hexdigest() != record_sha256:
            raise CaseDevPurchaseLedgerError("resolved material record hash changed")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            operation = self._operation(document_id)
            material = self._material(document_id)
            if operation is None or material is None:
                raise CaseDevPurchaseLedgerError("purchase operation is missing")
            expected = {
                "candidate_id": str(operation["candidate_id"]),
                "source_document_id": document_id,
                "recovery_origin": "unknown_status_attempt",
                "attempt_policy_sha256": material["attempt_policy_sha256"],
                "selection_document_sha256": material["attempt_document_sha256"],
                "queue_response_sha256": material["queue_response_sha256"],
                "fresh_recap_detail_sha256": material["provider_detail_sha256"],
                "download_url_sha256": material["download_url_sha256"],
                "content_sha256": material["content_sha256"],
                "byte_count": material["byte_count"],
                "parser_eligible": True,
                "packet_eligible": True,
            }
            if any(
                resolved_record.get(key) != value for key, value in expected.items()
            ):
                raise CaseDevPurchaseLedgerError(
                    "resolved material does not bind canonical purchase lineage"
                )
            clearance_sha256 = resolved_record.get("clearance_record_sha256")
            if (
                not isinstance(clearance_sha256, str)
                or _SHA256.fullmatch(clearance_sha256) is None
            ):
                raise CaseDevPurchaseLedgerError(
                    "resolved material clearance hash is invalid"
                )
            if str(material["status"]) == PurchaseMaterialState.CLEARED_PUBLIC.value:
                if (
                    material["resolved_record_sha256"] != record_sha256
                    or material["clearance_record_sha256"] != clearance_sha256
                ):
                    raise CaseDevPurchaseLedgerError(
                        "resolved material replay conflicts"
                    )
                self._connection.commit()
                return
            cursor = self._connection.execute(
                """UPDATE purchase_material_state SET status=?,
                clearance_record_sha256=?, resolved_record_sha256=?
                WHERE source_document_id=? AND authority='unknown_status_attempt'
                  AND status=?""",
                (
                    PurchaseMaterialState.CLEARED_PUBLIC.value,
                    clearance_sha256,
                    record_sha256,
                    document_id,
                    PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE.value,
                ),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "unknown material is not awaiting clearance"
                )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()

    def queued_response(self, document_id: str) -> Mapping[str, Any] | None:
        """Return durable asynchronous provider state without mutating the ledger."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) != "queued":
            return None
        response_json = row["response_json"]
        if response_json is None:
            raise CaseDevPurchaseLedgerError("queued purchase lacks provider evidence")
        return cast(Mapping[str, Any], json.loads(str(response_json)))

    def operation_evidence(self, document_id: str) -> Mapping[str, Any] | None:
        """Return the durable row needed by provider-specific resume logic."""

        row = self._operation(document_id)
        if row is None:
            return None
        material = self._material(document_id)
        if material is None:
            raise CaseDevPurchaseLedgerError("purchase material state is missing")
        response = (
            None
            if row["response_json"] is None
            else cast(Mapping[str, Any], json.loads(str(row["response_json"])))
        )
        return {
            "candidate_id": str(row["candidate_id"]),
            "status": str(row["status"]),
            "operation_key": (
                None if row["operation_key"] is None else str(row["operation_key"])
            ),
            "reservation_usd": str(row["reservation_usd"]),
            "actual_usd": (
                None if row["actual_usd"] is None else str(row["actual_usd"])
            ),
            "response": response,
            "reconciliation": (
                None
                if row["reconciliation_json"] is None
                else cast(
                    Mapping[str, Any], json.loads(str(row["reconciliation_json"]))
                )
            ),
            "error": None if row["error"] is None else str(row["error"]),
            "material_authority": str(material["authority"]),
            "material_state": PurchaseMaterialState(str(material["status"])),
            "attempt_policy_sha256": (
                None
                if material["attempt_policy_sha256"] is None
                else str(material["attempt_policy_sha256"])
            ),
            "attempt_document_sha256": (
                None
                if material["attempt_document_sha256"] is None
                else str(material["attempt_document_sha256"])
            ),
            "material_evidence": (
                {
                    key: material[key]
                    for key in (
                        "provider_detail_sha256",
                        "queue_response_sha256",
                        "download_url_sha256",
                        "content_sha256",
                        "byte_count",
                        "clearance_record_sha256",
                    )
                    if material[key] is not None
                }
            ),
            "resolved_document_sha256": (
                None
                if material["resolved_record_sha256"] is None
                else str(material["resolved_record_sha256"])
            ),
        }

    def record_broker_receipt(
        self, document_id: str, receipt: Mapping[str, Any]
    ) -> None:
        """Durably append a validated nonsecret broker receipt to provider evidence."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) not in {
            "submitted",
            "queued",
            "confirmed",
            "failed",
            "unknown",
        }:
            raise CaseDevPurchaseLedgerError(
                "broker receipt requires a paid or reserved operation"
            )
        prior = (
            {}
            if row["response_json"] is None
            else cast(dict[str, Any], json.loads(str(row["response_json"])))
        )
        canonical_receipt = _canonical(receipt)
        digest = hashlib.sha256(canonical_receipt.encode()).hexdigest()
        raw_history: object = prior.get("broker_receipts", [])
        if not isinstance(raw_history, list):
            raise CaseDevPurchaseLedgerError("broker receipt history is invalid")
        history = cast(list[object], raw_history)
        for item in history:
            if isinstance(item, Mapping):
                record = cast(Mapping[str, object], item)
                if record.get("sha256") == digest:
                    return
                prior_receipt = record.get("receipt")
                if isinstance(prior_receipt, Mapping):
                    prior_record = cast(Mapping[str, object], prior_receipt)
                    immutable_fields = (
                        "operation_key",
                        "reservation_id",
                        "cycle_id",
                        "purchase_policy_sha256",
                        "recap_document",
                        "case_id",
                        "client_code",
                        "reservation_usd",
                    )
                    if any(
                        prior_record.get(field_name) != receipt.get(field_name)
                        for field_name in immutable_fields
                    ):
                        raise CaseDevPurchaseLedgerError(
                            "broker receipt immutable identity changed"
                        )
                    prior_queue = prior_record.get("id")
                    if prior_queue is not None and prior_queue != receipt.get("id"):
                        raise CaseDevPurchaseLedgerError(
                            "broker receipt queue identity changed"
                        )
        updated: dict[str, Any] = {
            **prior,
            "broker_receipts": [
                *history,
                {"sha256": digest, "receipt": dict(receipt)},
            ],
        }
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET response_json=?
                WHERE source_document_id=?""",
                (_canonical(updated), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "broker receipt persistence transition failed"
                )

    def fail_before_dispatch(self, document_id: str, error: object) -> None:
        """Release a local hold after a definite broker pre-provider rejection."""

        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='failed',
                response_json=NULL, reconciliation_json=NULL, actual_usd=NULL, error=?
                WHERE source_document_id=? AND status='submitted'""",
                (str(error), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "definite failure requires a submitted operation"
                )

    def recover_broker_queue(
        self, document_id: str, *, queue_id: str, reservation_id: str
    ) -> None:
        """Resolve submitted or unknown local state from a durable broker queue ID."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) not in {"submitted", "unknown"}:
            raise CaseDevPurchaseLedgerError(
                "broker queue recovery requires submitted or unknown state"
            )
        prior = (
            {}
            if row["response_json"] is None
            else cast(dict[str, Any], json.loads(str(row["response_json"])))
        )
        response = {
            **prior,
            "source_provider": "courtlistener.recap-fetch+pacer",
            "reservation_usd": str(row["reservation_usd"]),
            "queue_id": queue_id,
            "reservation_id": reservation_id,
        }
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='queued', response_json=?,
                error=NULL WHERE source_document_id=? AND status IN
                ('submitted','unknown')""",
                (_canonical(response), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "broker queue recovery transition failed"
                )

    def fail(self, document_id: str, error: BaseException) -> None:
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='failed', error=?
                WHERE source_document_id=? AND status IN ('submitted','queued')""",
                (f"{type(error).__name__}: {error}", document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("failed purchase transition failed")

    def mark_unknown(self, document_id: str, error: object) -> None:
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='unknown', error=?
                WHERE source_document_id=? AND status IN ('submitted','queued')""",
                (str(error), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError("unknown purchase transition failed")

    def reconcile(self, evidence: Mapping[str, object]) -> None:
        """Resolve or write off an ambiguous row using recorded provider evidence."""

        _exact_keys(
            evidence,
            {
                "source_document_id",
                "disposition",
                "source_type",
                "source_reference",
                "pacer_fees",
                "download_url",
            },
            "purchase reconciliation evidence",
        )
        document_id = _required_text(
            evidence.get("source_document_id"), "source_document_id"
        )
        disposition = _required_text(evidence.get("disposition"), "disposition")
        source_type = _required_text(evidence.get("source_type"), "source_type")
        if source_type not in {
            "billing_receipt",
            "statement_export",
            "support_confirmation",
        }:
            raise CaseDevPurchasePolicyError(
                "reconciliation source must be provider-side billing evidence"
            )
        _required_text(evidence.get("source_reference"), "source_reference")
        row = self._operation(document_id)
        reconcilable_statuses = {
            "submitted",
            "queued",
            "confirmed",
            "failed",
            "unknown",
        }
        if row is None or str(row["status"]) not in reconcilable_statuses:
            raise CaseDevPurchaseLedgerError(
                "reconciliation requires a paid or reserved operation"
            )
        material = self._material(document_id)
        if material is None:
            raise CaseDevPurchaseLedgerError("purchase material state is missing")
        if (
            str(material["authority"]) == "unknown_status_attempt"
            and disposition == "confirmed"
        ):
            raise CaseDevPurchaseLedgerError(
                "unknown-status billing must use URL-free broker reconciliation"
            )
        reconciliation = _canonical(evidence)
        if disposition == "confirmed":
            fees = _pacer_fees(evidence.get("pacer_fees"))
            download_url = _required_text(evidence.get("download_url"), "download_url")
            actual = Decimal(fees["total_usd"])
            if actual > Decimal(str(row["reservation_usd"])):
                raise CaseDevPurchaseLedgerError(
                    "reconciled fee exceeds verified worst-case reservation"
                )
            with self._connection:
                prior_response: Mapping[str, Any] = (
                    cast(Mapping[str, Any], {})
                    if row["response_json"] is None
                    else cast(Mapping[str, Any], json.loads(str(row["response_json"])))
                )
                if prior_response.get("source_provider") == (
                    "courtlistener.recap-fetch+pacer"
                ):
                    response = {
                        **prior_response,
                        "actual_fees": dict(fees),
                        "download_url": download_url,
                    }
                else:
                    response = {
                        "acknowledgePacerFees": True,
                        "pacerFees": evidence["pacer_fees"],
                        "downloadUrl": download_url,
                    }
                cursor = self._connection.execute(
                    """UPDATE purchase_operations SET status='confirmed',
                    actual_usd=?, response_json=?, reconciliation_json=?, error=NULL
                    WHERE source_document_id=? AND status IN
                    ('submitted','queued','confirmed','failed','unknown')""",
                    (
                        _money(actual),
                        _canonical(response),
                        reconciliation,
                        document_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CaseDevPurchaseLedgerError(
                        "confirmed reconciliation transition failed"
                    )
            return
        if (
            evidence.get("pacer_fees") is not None
            or evidence.get("download_url") is not None
        ):
            raise CaseDevPurchasePolicyError(
                "failed or written-off reconciliation cannot assert fees or a URL"
            )
        if disposition == "failed":
            with self._connection:
                cursor = self._connection.execute(
                    """UPDATE purchase_operations SET status='failed',
                    actual_usd=NULL, reconciliation_json=?, error=NULL
                    WHERE source_document_id=? AND status IN
                    ('submitted','queued','confirmed','failed','unknown')""",
                    (reconciliation, document_id),
                )
                if cursor.rowcount != 1:
                    raise CaseDevPurchaseLedgerError(
                        "failed reconciliation transition failed"
                    )
            return
        if disposition == "write_off":
            with self._connection:
                cursor = self._connection.execute(
                    """UPDATE purchase_operations SET status='unknown',
                    reconciliation_json=?
                    WHERE source_document_id=? AND status IN
                    ('submitted','queued','confirmed','failed','unknown')""",
                    (reconciliation, document_id),
                )
                if cursor.rowcount != 1:
                    raise CaseDevPurchaseLedgerError(
                        "write-off reconciliation transition failed"
                    )
            return
        raise CaseDevPurchasePolicyError(
            "reconciliation disposition must be confirmed, failed, or write_off"
        )

    def reconcile_unknown_broker_billing(
        self,
        document_id: str,
        *,
        actual_usd: str,
        evidence_sha256: str,
        source_reference: str,
    ) -> None:
        """Settle unknown-origin billing without persisting a material locator."""

        try:
            actual = Decimal(actual_usd)
        except InvalidOperation as exc:
            raise CaseDevPurchaseLedgerError(
                "broker billing amount is invalid"
            ) from exc
        if _money(actual) != actual_usd or actual <= 0:
            raise CaseDevPurchaseLedgerError(
                "broker billing amount must be canonical positive USD"
            )
        if _SHA256.fullmatch(evidence_sha256) is None or not source_reference:
            raise CaseDevPurchaseLedgerError(
                "broker billing evidence identity is invalid"
            )
        row = self._operation(document_id)
        material = self._material(document_id)
        if row is None or material is None:
            raise CaseDevPurchaseLedgerError("purchase operation is missing")
        if str(material["authority"]) != "unknown_status_attempt":
            raise CaseDevPurchaseLedgerError(
                "URL-free broker reconciliation requires unknown attempt authority"
            )
        if actual > Decimal(str(row["reservation_usd"])):
            raise CaseDevPurchaseLedgerError(
                "broker fee exceeds verified worst-case reservation"
            )
        expected_reference = (
            f"recap-fetch-broker:{row['operation_key']}:{evidence_sha256}"
        )
        if source_reference != expected_reference:
            raise CaseDevPurchaseLedgerError(
                "broker billing source does not bind the operation key"
            )
        response: Mapping[str, Any] = (
            cast(Mapping[str, Any], {})
            if row["response_json"] is None
            else cast(Mapping[str, Any], json.loads(str(row["response_json"])))
        )
        receipt_history_raw: object = response.get("broker_receipts")
        receipt_matches = False
        if isinstance(receipt_history_raw, list):
            for item in cast(list[object], receipt_history_raw):
                if not isinstance(item, Mapping):
                    continue
                item_record = cast(Mapping[str, object], item)
                receipt_raw: object = item_record.get("receipt")
                if not isinstance(receipt_raw, Mapping):
                    continue
                receipt = cast(Mapping[str, Any], receipt_raw)
                billing_raw: object = receipt.get("billing_evidence")
                billing = (
                    cast(Mapping[str, Any], billing_raw)
                    if isinstance(billing_raw, Mapping)
                    else None
                )
                if (
                    receipt.get("state") == "confirmed"
                    and receipt.get("operation_key") == row["operation_key"]
                    and receipt.get("authoritative_fee_usd") == actual_usd
                    and billing is not None
                    and billing.get("evidence_sha256") == evidence_sha256
                ):
                    receipt_matches = True
                    break
        if not receipt_matches:
            raise CaseDevPurchaseLedgerError(
                "broker billing lacks a matching persisted validated receipt"
            )
        evidence = {
            "source_document_id": document_id,
            "disposition": "confirmed",
            "source_type": "statement_export",
            "source_reference": source_reference,
            "pacer_fees": {
                "pacerFee": actual_usd,
                "serviceFee": "0.00",
                "total": actual_usd,
            },
            "download_url": None,
            "billing_evidence_sha256": evidence_sha256,
        }
        if str(row["status"]) == "confirmed":
            if row["actual_usd"] == actual_usd and row[
                "reconciliation_json"
            ] == _canonical(evidence):
                return
            raise CaseDevPurchaseLedgerError(
                "broker billing reconciliation is immutable"
            )
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE purchase_operations SET status='confirmed', actual_usd=?,
                reconciliation_json=?, error=NULL
                WHERE source_document_id=? AND status IN
                    ('submitted','queued','confirmed','unknown')""",
                (_money(actual), _canonical(evidence), document_id),
            )
            if cursor.rowcount != 1:
                raise CaseDevPurchaseLedgerError(
                    "broker billing reconciliation transition failed"
                )

    def statuses(self) -> dict[str, str]:
        rows = self._connection.execute(
            """SELECT source_document_id, status FROM purchase_operations
            ORDER BY source_document_id"""
        ).fetchall()
        return {str(row["source_document_id"]): str(row["status"]) for row in rows}

    def operation_records(self) -> tuple[Mapping[str, Any], ...]:
        """Return canonical purchase rows for offline audit and replacement logic."""

        rows = self._connection.execute(
            """SELECT o.source_document_id, o.candidate_id, o.reservation_usd,
            o.status, o.operation_key, o.actual_usd, o.response_json, o.error,
            o.reconciliation_json, m.authority AS material_authority,
            m.status AS material_status, m.attempt_policy_sha256,
            m.attempt_document_sha256,
            m.provider_detail_sha256, m.queue_response_sha256,
            m.download_url_sha256, m.content_sha256, m.byte_count,
            m.clearance_record_sha256, m.resolved_record_sha256
            FROM purchase_operations AS o
            JOIN purchase_material_state AS m USING(source_document_id)
            ORDER BY o.source_document_id"""
        ).fetchall()
        return tuple(
            MappingProxyType(
                {
                    "source_document_id": str(row["source_document_id"]),
                    "candidate_id": str(row["candidate_id"]),
                    "reservation_usd": str(row["reservation_usd"]),
                    "status": str(row["status"]),
                    "operation_key": (
                        None
                        if row["operation_key"] is None
                        else str(row["operation_key"])
                    ),
                    "actual_usd": (
                        None if row["actual_usd"] is None else str(row["actual_usd"])
                    ),
                    "response": (
                        None
                        if row["response_json"] is None
                        else json.loads(str(row["response_json"]))
                    ),
                    "error": None if row["error"] is None else str(row["error"]),
                    "reconciliation": (
                        None
                        if row["reconciliation_json"] is None
                        else json.loads(str(row["reconciliation_json"]))
                    ),
                    "material_authority": str(row["material_authority"]),
                    "material_state": str(row["material_status"]),
                    "attempt_policy_sha256": (
                        None
                        if row["attempt_policy_sha256"] is None
                        else str(row["attempt_policy_sha256"])
                    ),
                    "attempt_document_sha256": (
                        None
                        if row["attempt_document_sha256"] is None
                        else str(row["attempt_document_sha256"])
                    ),
                    "material_evidence": (
                        {
                            key: row[key]
                            for key in (
                                "provider_detail_sha256",
                                "queue_response_sha256",
                                "download_url_sha256",
                                "content_sha256",
                                "byte_count",
                                "clearance_record_sha256",
                            )
                            if row[key] is not None
                        }
                    ),
                    "resolved_document_sha256": (
                        None
                        if row["resolved_record_sha256"] is None
                        else str(row["resolved_record_sha256"])
                    ),
                }
            )
            for row in rows
        )

    def candidate_committed_amount_usd(self, candidate_id: str) -> str:
        """Return journal-derived committed spend for one candidate.

        Planned rows are intentionally excluded. Confirmed charges, live holds,
        ambiguous outcomes, and counted write-offs remain committed exactly as
        they do at the Cycle cap. This is the disclosure write-off authority;
        replacement planning must not mutate provider reconciliation state.
        """

        amount = self.policy.opening_case_committed_spend_usd.get(
            candidate_id, Decimal("0")
        )
        rows = self._connection.execute(
            """SELECT status, reservation_usd, actual_usd, response_json,
            reconciliation_json FROM purchase_operations WHERE candidate_id=?""",
            (candidate_id,),
        ).fetchall()
        for row in rows:
            status = str(row["status"])
            reservation = Decimal(str(row["reservation_usd"]))
            actual = (
                Decimal(str(row["actual_usd"]))
                if row["actual_usd"] is not None
                else Decimal("0")
            )
            if status == "confirmed":
                amount += actual if row["actual_usd"] is not None else reservation
            elif status in {"submitted", "queued", "unknown"} or (
                status == "failed"
                and row["response_json"] is not None
                and row["reconciliation_json"] is None
            ):
                amount += max(reservation, actual)
        return _money(amount)

    def purchase_state_sha256(self) -> str:
        """Commit the immutable policy identity and current purchase operations."""

        return hashlib.sha256(
            _canonical(
                {
                    "cycle_id": self.policy.cycle_id,
                    "cohort_policy_sha256": self.policy.cohort_policy_sha256,
                    "purchase_policy_sha256": self.policy.policy_sha256,
                    "committed_amount_usd": self.committed_amount_usd,
                    "operations": [dict(row) for row in self.operation_records()],
                }
            ).encode()
        ).hexdigest()

    def replacement_events(self) -> tuple[Mapping[str, Any], ...]:
        """Read and verify the append-only clearance-replacement hash chain."""

        rows = self._connection.execute(
            """SELECT sequence, event_key, record_json, record_sha256
            FROM replacement_events
            ORDER BY sequence"""
        ).fetchall()
        records: list[Mapping[str, Any]] = []
        previous: str | None = None
        for expected_sequence, row in enumerate(rows):
            record_value = json.loads(str(row["record_json"]))
            if not isinstance(record_value, dict):
                raise CaseDevPurchaseLedgerError(
                    "replacement event record must be an object"
                )
            record = cast(dict[str, Any], record_value)
            if (
                row["sequence"] != expected_sequence
                or record.get("sequence") != expected_sequence
                or record.get("event_key") != row["event_key"]
            ):
                raise CaseDevPurchaseLedgerError(
                    "replacement event sequence or identity is invalid"
                )
            if record.get("previous_record_sha256") != previous:
                raise CaseDevPurchaseLedgerError(
                    "replacement event hash chain is broken"
                )
            committed = record.get("record_sha256")
            if (
                not isinstance(committed, str)
                or not committed.startswith("sha256:")
                or _SHA256.fullmatch(committed.removeprefix("sha256:")) is None
            ):
                raise CaseDevPurchaseLedgerError(
                    "replacement event record hash is invalid"
                )
            payload = {
                key: value for key, value in record.items() if key != "record_sha256"
            }
            actual = (
                "sha256:" + hashlib.sha256(_canonical(payload).encode()).hexdigest()
            )
            if actual != committed:
                raise CaseDevPurchaseLedgerError(
                    "replacement event hash does not match its content"
                )
            if row["record_sha256"] != committed:
                raise CaseDevPurchaseLedgerError(
                    "replacement event stored hash column does not match its record"
                )
            records.append(MappingProxyType(record))
            previous = committed
        return tuple(records)

    def append_replacement_event(
        self, event_key: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Append one idempotent, hash-chained replacement decision."""

        if not event_key or event_key.strip() != event_key:
            raise CaseDevPurchaseLedgerError(
                "replacement event_key must be a canonical non-empty string"
            )
        if any(
            field in payload
            for field in (
                "event_key",
                "sequence",
                "previous_record_sha256",
                "record_sha256",
            )
        ):
            raise CaseDevPurchaseLedgerError(
                "replacement event payload contains journal-owned fields"
            )
        # Refuse to extend even a self-consistently encoded tail when any prior
        # sequence, link, or content hash has been corrupted.
        self.replacement_events()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self._connection.execute(
                "SELECT record_json FROM replacement_events WHERE event_key=?",
                (event_key,),
            ).fetchone()
            if existing is not None:
                record_value = json.loads(str(existing["record_json"]))
                if not isinstance(record_value, dict):
                    raise CaseDevPurchaseLedgerError(
                        "replacement event record must be an object"
                    )
                record = cast(dict[str, Any], record_value)
                prior_payload = {
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "event_key",
                        "sequence",
                        "previous_record_sha256",
                        "record_sha256",
                    }
                }
                if _canonical(prior_payload) != _canonical(payload):
                    raise CaseDevPurchaseLedgerError(
                        "replacement event replay conflicts with durable content"
                    )
                self._connection.commit()
                self.replacement_events()
                return MappingProxyType(record)

            tail = self._connection.execute(
                """SELECT sequence, record_json FROM replacement_events
                ORDER BY sequence DESC LIMIT 1"""
            ).fetchone()
            sequence = 0 if tail is None else int(tail["sequence"]) + 1
            previous: str | None = None
            if tail is not None:
                tail_value: object = json.loads(str(tail["record_json"]))
                if not isinstance(tail_value, dict):
                    raise CaseDevPurchaseLedgerError(
                        "replacement event record must be an object"
                    )
                tail_record = cast(dict[str, Any], tail_value)
                previous_value = tail_record.get("record_sha256")
                if not isinstance(previous_value, str):
                    raise CaseDevPurchaseLedgerError(
                        "replacement event tail hash is invalid"
                    )
                previous = previous_value
            record: dict[str, Any] = {
                **dict(payload),
                "event_key": event_key,
                "sequence": sequence,
                "previous_record_sha256": previous,
            }
            record["record_sha256"] = (
                "sha256:" + hashlib.sha256(_canonical(record).encode()).hexdigest()
            )
            self._connection.execute(
                """INSERT INTO replacement_events(
                sequence, event_key, record_json, record_sha256)
                VALUES (?, ?, ?, ?)""",
                (
                    sequence,
                    event_key,
                    _canonical(record),
                    record["record_sha256"],
                ),
            )
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        self.replacement_events()
        return MappingProxyType(record)

    def replay_attempt(
        self,
        candidate_id: str,
        document_id: str,
    ) -> CaseDevPacerPurchaseAttempt | None:
        """Reconstruct a terminal result without another provider call."""

        row = self._operation(document_id)
        if row is None or str(row["status"]) == "planned":
            return None
        status = str(row["status"])
        if status == "confirmed":
            material = self._material(document_id)
            if material is None:
                raise CaseDevPurchaseLedgerError("purchase material state is missing")
            if (
                str(material["authority"]) == "unknown_status_attempt"
                and str(material["status"])
                != PurchaseMaterialState.CLEARED_PUBLIC.value
            ):
                return CaseDevPacerPurchaseAttempt(
                    candidate_id=candidate_id,
                    source_document_id=document_id,
                    status=CaseDevPacerPurchaseStatus.QUARANTINED,
                    reason="unknown_status_material_pending_clearance",
                    source_provider="courtlistener.recap-fetch+pacer",
                )
            response_json = row["response_json"]
            if response_json is not None:
                response = cast(Mapping[str, Any], json.loads(str(response_json)))
                return _successful_attempt(candidate_id, document_id, response)
            reconciliation_json = row["reconciliation_json"]
            if reconciliation_json is None:
                raise CaseDevPurchaseLedgerError(
                    "confirmed purchase lacks durable provider evidence"
                )
            evidence = cast(Mapping[str, Any], json.loads(str(reconciliation_json)))
            fees = _pacer_fees(evidence.get("pacer_fees"))
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.PURCHASED,
                reason="confirmed_purchase_replayed_from_provider_evidence",
                pacer_fees=fees,
            )
        if status == "failed":
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                reason=str(row["error"] or "provider_evidence_confirmed_failure"),
            )
        if status == "unknown" and row["reconciliation_json"] is not None:
            return CaseDevPacerPurchaseAttempt(
                candidate_id=candidate_id,
                source_document_id=document_id,
                status=CaseDevPacerPurchaseStatus.UNKNOWN,
                reason="purchase_written_off_and_counted_against_cycle_cap",
            )
        return None

    @property
    def committed_amount_usd(self) -> str:
        rows = self._connection.execute(
            """SELECT status, reservation_usd, actual_usd, response_json,
            reconciliation_json
            FROM purchase_operations"""
        ).fetchall()
        amount = Decimal("0")
        for row in rows:
            status = str(row["status"])
            if status == "confirmed":
                amount += (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal(str(row["reservation_usd"]))
                )
            elif status in {"submitted", "queued", "unknown"} or (
                status == "failed"
                and row["response_json"] is not None
                and row["reconciliation_json"] is None
            ):
                reservation = Decimal(str(row["reservation_usd"]))
                actual = (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal("0")
                )
                amount += max(reservation, actual)
        return _money(self.policy.opening_committed_spend_usd + amount)

    def _operation(self, document_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """SELECT * FROM purchase_operations WHERE source_document_id=?""",
            (document_id,),
        ).fetchone()

    def _material(self, document_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            """SELECT * FROM purchase_material_state WHERE source_document_id=?""",
            (document_id,),
        ).fetchone()

    def _candidate_cap_amount(self, candidate_id: str) -> Decimal:
        rows = self._connection.execute(
            """SELECT status, reservation_usd, actual_usd, response_json,
            reconciliation_json
            FROM purchase_operations WHERE candidate_id=?""",
            (candidate_id,),
        ).fetchall()
        amount = self.policy.opening_case_committed_spend_usd.get(
            candidate_id, Decimal("0")
        )
        for row in rows:
            status = str(row["status"])
            reservation = Decimal(str(row["reservation_usd"]))
            if status == "confirmed":
                amount += (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else reservation
                )
            elif status in {"planned", "submitted", "queued", "unknown"} or (
                status == "failed"
                and row["response_json"] is not None
                and row["reconciliation_json"] is None
            ):
                actual = (
                    Decimal(str(row["actual_usd"]))
                    if row["actual_usd"] is not None
                    else Decimal("0")
                )
                amount += max(reservation, actual)
        return amount

    def _create_schema(self) -> None:
        self._connection.executescript(_PURCHASE_LEDGER_SCHEMA_SQL)
        schema_row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='purchase_operations'"
        ).fetchone()
        if schema_row is not None and "'queued'" not in str(schema_row["sql"]):
            self._migrate_purchase_operations_for_queued_state()
        self._connection.executescript(_PURCHASE_MATERIAL_SCHEMA_SQL)
        self._migrate_purchase_material_state()

    def _migrate_purchase_material_state(self) -> None:
        """Backfill the one-to-one material track under the canonical lock."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                """INSERT INTO purchase_material_state(
                source_document_id, authority, status)
                SELECT source_document_id, 'ordinary_public', 'not_recovered'
                FROM purchase_operations
                WHERE source_document_id NOT IN (
                    SELECT source_document_id FROM purchase_material_state
                )"""
            )
            operation_count = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM purchase_operations"
                ).fetchone()[0]
            )
            material_count = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM purchase_material_state"
                ).fetchone()[0]
            )
            if operation_count != material_count:
                raise CaseDevPurchaseLedgerError(
                    "purchase material state does not exactly cover operations"
                )
            expected_columns = {
                "source_document_id",
                "authority",
                "status",
                "attempt_policy_sha256",
                "attempt_document_sha256",
                "provider_detail_sha256",
                "queue_response_sha256",
                "download_url_sha256",
                "content_sha256",
                "byte_count",
                "clearance_record_sha256",
                "resolved_record_sha256",
            }
            actual_columns = {
                str(row["name"])
                for row in self._connection.execute(
                    "PRAGMA table_info(purchase_material_state)"
                ).fetchall()
            }
            if actual_columns != expected_columns:
                raise CaseDevPurchaseLedgerError(
                    "purchase material state schema is invalid"
                )
            foreign_keys = self._connection.execute(
                "PRAGMA foreign_key_list(purchase_material_state)"
            ).fetchall()
            if len(foreign_keys) != 1 or str(foreign_keys[0]["table"]) != (
                "purchase_operations"
            ):
                raise CaseDevPurchaseLedgerError(
                    "purchase material state foreign key is invalid"
                )
            if (
                self._connection.execute("PRAGMA foreign_key_check").fetchone()
                is not None
            ):
                raise CaseDevPurchaseLedgerError(
                    "purchase material state failed foreign-key validation"
                )
            self._validate_material_state_rows()
            self._connection.execute("PRAGMA user_version=2")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        self._validate_material_state_rows()

    def _validate_material_state_rows(self) -> None:
        """Refuse malformed or contradictory material state after migration."""
        _validate_purchase_material_state_rows(self._connection)

    def _migrate_purchase_operations_for_queued_state(self) -> None:
        """Add the asynchronous state without losing an existing cycle ledger."""

        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            ALTER TABLE purchase_operations RENAME TO purchase_operations_legacy;
            CREATE TABLE purchase_operations (
                source_document_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                reservation_usd TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('planned','submitted','queued','confirmed','failed','unknown')),
                operation_key TEXT UNIQUE,
                actual_usd TEXT,
                response_json TEXT,
                error TEXT,
                reconciliation_json TEXT
            );
            INSERT INTO purchase_operations SELECT * FROM purchase_operations_legacy;
            DROP TABLE purchase_operations_legacy;
            COMMIT;
            """
        )

    def _bind_policy(self) -> None:
        _bind_purchase_ledger_policy(self._connection, self.policy, insert=True)


def _validate_purchase_material_state_rows(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """SELECT source_document_id, authority, status,
        attempt_policy_sha256, attempt_document_sha256, provider_detail_sha256,
        queue_response_sha256, download_url_sha256, content_sha256, byte_count,
        clearance_record_sha256, resolved_record_sha256
        FROM purchase_material_state"""
    ).fetchall()
    allowed_states = {state.value for state in PurchaseMaterialState}
    for row in rows:
        document_id = str(row["source_document_id"])
        authority = str(row["authority"])
        material_status = str(row["status"])
        attempt_policy = row["attempt_policy_sha256"]
        attempt_document = row["attempt_document_sha256"]
        resolved = row["resolved_record_sha256"]
        if authority not in {"ordinary_public", "unknown_status_attempt"}:
            raise CaseDevPurchaseLedgerError(
                f"purchase material authority is invalid: {document_id}"
            )
        if material_status not in allowed_states:
            raise CaseDevPurchaseLedgerError(
                f"purchase material state is invalid: {document_id}"
            )
        if authority == "ordinary_public" and (
            attempt_policy is not None or attempt_document is not None
        ):
            raise CaseDevPurchaseLedgerError(
                f"ordinary-public material has attempt authority: {document_id}"
            )
        if authority == "unknown_status_attempt" and (
            not isinstance(attempt_policy, str)
            or _SHA256.fullmatch(attempt_policy) is None
            or not isinstance(attempt_document, str)
            or _SHA256.fullmatch(attempt_document) is None
        ):
            raise CaseDevPurchaseLedgerError(
                f"unknown-status material lacks attempt authority: {document_id}"
            )
        for field in (
            "provider_detail_sha256",
            "queue_response_sha256",
            "download_url_sha256",
            "content_sha256",
            "clearance_record_sha256",
        ):
            value = row[field]
            if value is not None and (
                not isinstance(value, str) or _SHA256.fullmatch(value) is None
            ):
                raise CaseDevPurchaseLedgerError(
                    f"purchase material {field} is invalid: {document_id}"
                )
        if resolved is not None and (
            not isinstance(resolved, str) or _SHA256.fullmatch(resolved) is None
        ):
            raise CaseDevPurchaseLedgerError(
                f"resolved material digest is invalid: {document_id}"
            )
        byte_count = row["byte_count"]
        if byte_count is not None and (
            isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count <= 0
        ):
            raise CaseDevPurchaseLedgerError(
                f"purchase material byte_count is invalid: {document_id}"
            )
        evidence_fields = (
            "provider_detail_sha256",
            "queue_response_sha256",
            "download_url_sha256",
        )
        has_availability = all(row[field] is not None for field in evidence_fields)
        has_any_availability = any(row[field] is not None for field in evidence_fields)
        has_bytes = row["content_sha256"] is not None and byte_count is not None
        has_clearance = (
            row["clearance_record_sha256"] is not None and resolved is not None
        )
        if authority == "ordinary_public" and (
            material_status != PurchaseMaterialState.NOT_RECOVERED.value
            or any(row[field] is not None for field in evidence_fields)
            or has_bytes
            or has_clearance
        ):
            raise CaseDevPurchaseLedgerError(
                f"ordinary-public material has quarantine state: {document_id}"
            )
        expected_presence = {
            PurchaseMaterialState.NOT_RECOVERED.value: (False, False, False),
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE.value: (
                True,
                False,
                False,
            ),
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE.value: (
                True,
                True,
                False,
            ),
            PurchaseMaterialState.CLEARED_PUBLIC.value: (True, True, True),
        }
        expected = expected_presence.get(material_status)
        if (
            authority == "unknown_status_attempt"
            and expected is not None
            and (
                (has_availability, has_bytes, has_clearance) != expected
                or has_any_availability != has_availability
                or (row["content_sha256"] is None) != (byte_count is None)
                or (row["clearance_record_sha256"] is None) != (resolved is None)
            )
        ):
            raise CaseDevPurchaseLedgerError(
                f"purchase material state evidence is contradictory: {document_id}"
            )
        if material_status == PurchaseMaterialState.CLEARED_PUBLIC.value and (
            resolved is None or row["clearance_record_sha256"] is None
        ):
            raise CaseDevPurchaseLedgerError(
                f"cleared material lacks confirmed immutable lineage: {document_id}"
            )


def read_case_dev_purchase_snapshot(
    path: str | Path,
    *,
    policy: CaseDevPurchasePolicy,
) -> CaseDevPurchaseSnapshot:
    """Read authenticated purchase state without changing ledger filesystem state."""

    ledger_path = _canonical_requested_ledger_path(path, policy=policy)
    _require_existing_purchase_ledger_file(ledger_path)
    sidecars = tuple(
        Path(f"{ledger_path}{suffix}") for suffix in ("-wal", "-shm", "-journal")
    )
    present_sidecars = [sidecar for sidecar in sidecars if sidecar.exists()]
    if present_sidecars:
        raise CaseDevPurchaseLedgerBusyError(
            "read-only purchase audit requires a checkpointed ledger without "
            "SQLite sidecars"
        )
    observed_paths = (ledger_path, Path(f"{ledger_path}.lock"), *sidecars)
    before = _purchase_snapshot_filesystem_identity(observed_paths)
    lock_fd = _acquire_existing_purchase_ledger_lock(ledger_path)
    try:
        if any(sidecar.exists() for sidecar in sidecars):
            raise CaseDevPurchaseLedgerBusyError(
                "purchase ledger gained SQLite sidecars before read-only audit"
            )
        uri = f"file:{quote(ledger_path.as_posix(), safe='/')}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity is None or str(integrity[0]) != "ok":
                raise CaseDevPurchaseLedgerError(
                    "purchase ledger failed read-only SQLite quick_check"
                )
            _bind_purchase_ledger_policy(connection, policy, insert=False)
            _verify_purchase_snapshot_schema(connection)
            operations = _read_purchase_operation_records(connection)
            committed = _read_committed_amount(connection, policy=policy)
            if Decimal(committed) > policy.hard_cap_usd:
                raise CaseDevPurchaseLedgerError(
                    "purchase ledger committed amount exceeds the immutable hard cap"
                )
            for candidate_id in {str(row["candidate_id"]) for row in operations}:
                candidate_amount = _read_candidate_committed_amount(
                    connection,
                    policy=policy,
                    candidate_id=candidate_id,
                )
                if candidate_amount > policy.max_per_case_usd:
                    raise CaseDevPurchaseLedgerError(
                        f"{candidate_id} committed amount exceeds the per-case cap"
                    )
            digest = hashlib.sha256(
                _canonical(
                    {
                        "cycle_id": policy.cycle_id,
                        "cohort_policy_sha256": policy.cohort_policy_sha256,
                        "purchase_policy_sha256": policy.policy_sha256,
                        "committed_amount_usd": committed,
                        "operations": [dict(row) for row in operations],
                    }
                ).encode()
            ).hexdigest()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger is not a complete authenticated SQLite journal"
        ) from exc
    finally:
        # Keep the descriptor close explicit in this read-only path. Besides
        # making its lifetime obvious to static analysis, the nested finally
        # guarantees close even if unlocking itself reports an OS error.
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
    after = _purchase_snapshot_filesystem_identity(observed_paths)
    if after != before:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger filesystem state changed during read-only audit"
        )
    return CaseDevPurchaseSnapshot(
        operations=operations,
        purchase_state_sha256=digest,
    )


def _purchase_snapshot_filesystem_identity(
    paths: tuple[Path, ...],
) -> tuple[tuple[str, int, int, int, int, str], ...]:
    identities: list[tuple[str, int, int, int, int, str]] = []
    for path in paths:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise CaseDevPurchaseLedgerError(
                f"purchase ledger path is not a singly linked regular file: {path}"
            )
        identities.append(
            (
                str(path),
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return tuple(identities)


def _verify_purchase_snapshot_schema(connection: sqlite3.Connection) -> None:
    required_columns = {
        "purchase_operations": {
            "source_document_id",
            "candidate_id",
            "reservation_usd",
            "status",
            "operation_key",
            "actual_usd",
            "response_json",
            "error",
            "reconciliation_json",
        },
        "purchase_material_state": {
            "source_document_id",
            "authority",
            "status",
            "attempt_policy_sha256",
            "attempt_document_sha256",
            "provider_detail_sha256",
            "queue_response_sha256",
            "download_url_sha256",
            "content_sha256",
            "byte_count",
            "clearance_record_sha256",
            "resolved_record_sha256",
        },
    }
    for table, expected in required_columns.items():
        actual = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if actual != expected:
            raise CaseDevPurchaseLedgerError(
                f"purchase ledger {table} schema is not an exact supported version"
            )
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise CaseDevPurchaseLedgerError(
            "purchase ledger failed foreign-key validation"
        )
    operation_count = int(
        connection.execute("SELECT COUNT(*) FROM purchase_operations").fetchone()[0]
    )
    material_count = int(
        connection.execute("SELECT COUNT(*) FROM purchase_material_state").fetchone()[0]
    )
    if operation_count != material_count:
        raise CaseDevPurchaseLedgerError(
            "purchase material state does not exactly cover operations"
        )
    _validate_purchase_material_state_rows(connection)
    rows = connection.execute("SELECT * FROM purchase_operations").fetchall()
    allowed_statuses = {
        "planned",
        "submitted",
        "queued",
        "confirmed",
        "failed",
        "unknown",
    }
    for row in rows:
        document_id = row["source_document_id"]
        candidate_id = row["candidate_id"]
        if not isinstance(document_id, str) or not document_id.strip():
            raise CaseDevPurchaseLedgerError(
                "purchase operation document ID is invalid"
            )
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise CaseDevPurchaseLedgerError(
                f"purchase operation candidate ID is invalid: {document_id}"
            )
        if row["status"] not in allowed_statuses:
            raise CaseDevPurchaseLedgerError(
                f"purchase operation status is invalid: {document_id}"
            )
        if row["status"] == "confirmed" and (
            not isinstance(row["operation_key"], str)
            or not str(row["operation_key"]).strip()
        ):
            raise CaseDevPurchaseLedgerError(
                f"confirmed purchase operation lacks operation key: {document_id}"
            )
        for field in ("reservation_usd", "actual_usd"):
            value = row[field]
            if value is not None and (
                not isinstance(value, str) or _CANONICAL_USD.fullmatch(value) is None
            ):
                raise CaseDevPurchaseLedgerError(
                    f"purchase operation {field} is invalid: {document_id}"
                )
        for field in ("response_json", "reconciliation_json"):
            value = row[field]
            if value is None:
                continue
            try:
                decoded = json.loads(str(value))
            except (TypeError, ValueError) as exc:
                raise CaseDevPurchaseLedgerError(
                    f"purchase operation {field} is invalid: {document_id}"
                ) from exc
            if not isinstance(decoded, Mapping):
                raise CaseDevPurchaseLedgerError(
                    f"purchase operation {field} must be an object: {document_id}"
                )


def _read_purchase_operation_records(
    connection: sqlite3.Connection,
) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(
        """SELECT o.source_document_id, o.candidate_id, o.reservation_usd,
        o.status, o.operation_key, o.actual_usd, o.response_json, o.error,
        o.reconciliation_json, m.authority AS material_authority,
        m.status AS material_status, m.attempt_policy_sha256,
        m.attempt_document_sha256, m.provider_detail_sha256,
        m.queue_response_sha256, m.download_url_sha256, m.content_sha256,
        m.byte_count, m.clearance_record_sha256, m.resolved_record_sha256
        FROM purchase_operations AS o
        JOIN purchase_material_state AS m USING(source_document_id)
        ORDER BY o.source_document_id"""
    ).fetchall()
    return tuple(_purchase_operation_record(row) for row in rows)


def _purchase_operation_record(row: sqlite3.Row) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "source_document_id": str(row["source_document_id"]),
            "candidate_id": str(row["candidate_id"]),
            "reservation_usd": str(row["reservation_usd"]),
            "status": str(row["status"]),
            "operation_key": _optional_row_str(row, "operation_key"),
            "actual_usd": _optional_row_str(row, "actual_usd"),
            "response": _optional_row_json(row, "response_json"),
            "error": _optional_row_str(row, "error"),
            "reconciliation": _optional_row_json(row, "reconciliation_json"),
            "material_authority": str(row["material_authority"]),
            "material_state": str(row["material_status"]),
            "attempt_policy_sha256": _optional_row_str(row, "attempt_policy_sha256"),
            "attempt_document_sha256": _optional_row_str(
                row, "attempt_document_sha256"
            ),
            "material_evidence": {
                key: row[key]
                for key in (
                    "provider_detail_sha256",
                    "queue_response_sha256",
                    "download_url_sha256",
                    "content_sha256",
                    "byte_count",
                    "clearance_record_sha256",
                )
                if row[key] is not None
            },
            "resolved_document_sha256": _optional_row_str(
                row, "resolved_record_sha256"
            ),
        }
    )


def _optional_row_str(row: sqlite3.Row, field: str) -> str | None:
    value = row[field]
    return None if value is None else str(value)


def _optional_row_json(row: sqlite3.Row, field: str) -> Any:
    value = row[field]
    return None if value is None else json.loads(str(value))


def _read_committed_amount(
    connection: sqlite3.Connection,
    *,
    policy: CaseDevPurchasePolicy,
) -> str:
    rows = connection.execute(
        """SELECT status, reservation_usd, actual_usd, response_json,
        reconciliation_json FROM purchase_operations"""
    ).fetchall()
    amount = Decimal("0")
    for row in rows:
        status_value = str(row["status"])
        if status_value == "confirmed":
            amount += (
                Decimal(str(row["actual_usd"]))
                if row["actual_usd"] is not None
                else Decimal(str(row["reservation_usd"]))
            )
        elif status_value in {"submitted", "queued", "unknown"} or (
            status_value == "failed"
            and row["response_json"] is not None
            and row["reconciliation_json"] is None
        ):
            reservation = Decimal(str(row["reservation_usd"]))
            actual = (
                Decimal(str(row["actual_usd"]))
                if row["actual_usd"] is not None
                else Decimal("0")
            )
            amount += max(reservation, actual)
    return _money(policy.opening_committed_spend_usd + amount)


def _read_candidate_committed_amount(
    connection: sqlite3.Connection,
    *,
    policy: CaseDevPurchasePolicy,
    candidate_id: str,
) -> Decimal:
    amount = policy.opening_case_committed_spend_usd.get(candidate_id, Decimal("0"))
    rows = connection.execute(
        """SELECT status, reservation_usd, actual_usd, response_json,
        reconciliation_json FROM purchase_operations WHERE candidate_id=?""",
        (candidate_id,),
    ).fetchall()
    for row in rows:
        status_value = str(row["status"])
        reservation = Decimal(str(row["reservation_usd"]))
        actual = (
            Decimal(str(row["actual_usd"]))
            if row["actual_usd"] is not None
            else Decimal("0")
        )
        if status_value == "confirmed":
            amount += actual if row["actual_usd"] is not None else reservation
        elif status_value in {"submitted", "queued", "unknown"} or (
            status_value == "failed"
            and row["response_json"] is not None
            and row["reconciliation_json"] is None
        ):
            amount += max(reservation, actual)
    return amount


class CaseDevPacerCapability(StrEnum):
    """Known case.dev PACER recovery behavior for selected packet documents."""

    DOCUMENT_LEVEL_PURCHASE = "document_level_purchase"
    DOCKET_LEVEL_LIVE_FETCH_ONLY = "docket_level_live_fetch_only"
    UNKNOWN = "unknown"


class CaseDevPacerPurchaseStatus(StrEnum):
    """Machine-readable status for one intended paid document recovery."""

    PLANNED_DRY_RUN = "planned_dry_run"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    CAPABILITY_BLOCKED = "capability_blocked"
    PURCHASED = "purchased"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"
    PROVIDER_ERROR = "provider_error"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseAttempt:
    """Recorded intent and outcome for one missing core-document purchase."""

    candidate_id: str
    source_document_id: str
    status: CaseDevPacerPurchaseStatus
    reason: str | None = None
    fee_acknowledged: bool | None = None
    pacer_fees: Mapping[str, str] | None = None
    download_url: str | None = None
    source_provider: str = "case.dev+pacer"

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "reason": self.reason,
            "fee_acknowledged": self.fee_acknowledged,
            "pacer_fees": dict(self.pacer_fees) if self.pacer_fees else None,
            "download_url": self.download_url,
            "source_provider": self.source_provider,
        }


@dataclass(frozen=True, slots=True)
class CaseDevPacerPurchaseResult:
    """Run-level result for a guarded case.dev PACER purchase plan."""

    live: bool
    acknowledge_pacer_fees: bool
    capability: CaseDevPacerCapability
    dry_run: bool
    projected_cost_usd: str
    max_projected_budget_usd: str
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...]

    @property
    def intended_purchase_count(self) -> int:
        return len(self.attempts)

    @property
    def executed_purchase_count(self) -> int:
        return sum(
            1
            for attempt in self.attempts
            if attempt.status is CaseDevPacerPurchaseStatus.PURCHASED
        )

    @property
    def quarantined_material_count(self) -> int:
        """Count paid recoveries intentionally withheld from downstream use."""

        return sum(
            1
            for attempt in self.attempts
            if attempt.status is CaseDevPacerPurchaseStatus.QUARANTINED
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "live": self.live,
            "acknowledge_pacer_fees": self.acknowledge_pacer_fees,
            "capability": self.capability.value,
            "dry_run": self.dry_run,
            "projected_cost_usd": self.projected_cost_usd,
            "max_projected_budget_usd": self.max_projected_budget_usd,
            "intended_purchase_count": self.intended_purchase_count,
            "executed_purchase_count": self.executed_purchase_count,
            "quarantined_material_count": self.quarantined_material_count,
            "attempts": [attempt.to_record() for attempt in self.attempts],
        }


class CaseDevPacerPurchaseClient:
    """Execute missing-core purchase plans only after explicit safety gates."""

    def __init__(
        self,
        client: CaseDevClient,
        *,
        capability: CaseDevPacerCapability = CaseDevPacerCapability.UNKNOWN,
        journal: CaseDevPurchaseJournal | None = None,
    ) -> None:
        self.client = client
        self.capability = capability
        self.journal = journal

    def execute_purchase_plan(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        """Execute or block a missing-core document purchase plan."""

        _validate_plan_budget(plan)
        if plan.dry_run:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.PLANNED_DRY_RUN,
                reason="dry_run_no_paid_request",
            )
        if not live:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="live_flag_required",
            )
        if not acknowledge_pacer_fees:
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.GUARDRAIL_BLOCKED,
                reason="acknowledge_pacer_fees_required",
            )
        if self.capability is not CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE:
            reason = (
                "document_level_purchase_unavailable"
                if self.capability
                is CaseDevPacerCapability.DOCKET_LEVEL_LIVE_FETCH_ONLY
                else "document_level_purchase_capability_unknown"
            )
            return self._blocked_result(
                plan,
                live=live,
                acknowledge_pacer_fees=acknowledge_pacer_fees,
                status=CaseDevPacerPurchaseStatus.CAPABILITY_BLOCKED,
                reason=reason,
            )

        if self.journal is None:
            raise CaseDevPurchaseLedgerError(
                "live document purchase requires the canonical cycle journal"
            )

        return self._execute_document_purchases(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
        )

    def _blocked_result(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
        status: CaseDevPacerPurchaseStatus,
        reason: str,
    ) -> CaseDevPacerPurchaseResult:
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(
                CaseDevPacerPurchaseAttempt(
                    candidate_id=case_plan.candidate_id,
                    source_document_id=document_id,
                    status=status,
                    reason=reason,
                )
                for case_plan in plan.case_plans
                for document_id in case_plan.purchase_document_ids
            ),
        )

    def _execute_document_purchases(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        assert self.journal is not None
        intended = tuple(
            (case_plan.candidate_id, document_id)
            for case_plan in plan.case_plans
            for document_id in case_plan.purchase_document_ids
        )
        self.journal.plan(plan)
        self.journal.require_reconciled()
        attempts: list[CaseDevPacerPurchaseAttempt] = []
        for index, (candidate_id, document_id) in enumerate(intended):
            replayed = self.journal.replay_attempt(candidate_id, document_id)
            if replayed is not None:
                attempts.append(replayed)
                continue
            if not self.journal.submit(document_id):
                replayed = self.journal.replay_attempt(candidate_id, document_id)
                if replayed is None:
                    raise CaseDevPurchaseLedgerError(
                        "purchase submit was skipped without a replayable result"
                    )
                attempts.append(replayed)
                continue
            try:
                payload = self.client.purchase_pacer_document(
                    document_id,
                    acknowledge_pacer_fees=acknowledge_pacer_fees,
                )
            except (
                CaseDevPurchaseOutcomeUnknownError,
                CaseDevServerError,
                CaseDevResponseError,
                ValueError,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                self.journal.mark_unknown(document_id, exc)
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.UNKNOWN,
                        reason="purchase_outcome_unknown",
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            except CaseDevClientError as exc:
                self.journal.fail(document_id, exc)
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                        reason=str(exc),
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="provider_error_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            try:
                attempt = _successful_attempt(candidate_id, document_id, payload)
                if attempt.pacer_fees is None:
                    raise ValueError("successful purchase is missing validated fees")
                self.journal.confirm(
                    document_id,
                    response=payload,
                    fees=attempt.pacer_fees,
                )
            except (ValueError, CaseDevPurchaseLedgerError) as exc:
                operation = self.journal.operation_evidence(document_id)
                if operation is None:
                    raise CaseDevPurchaseLedgerError(
                        "purchase disappeared while recording unknown fees"
                    ) from exc
                if operation["status"] in {"submitted", "queued"}:
                    self.journal.mark_unknown(document_id, exc)
                elif operation["status"] != "unknown":
                    raise CaseDevPurchaseLedgerError(
                        "fee failure did not retain a reconcilable purchase state"
                    ) from exc
                attempts.append(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=candidate_id,
                        source_document_id=document_id,
                        status=CaseDevPacerPurchaseStatus.UNKNOWN,
                        reason="unparseable_provider_fees",
                    )
                )
                attempts.extend(
                    CaseDevPacerPurchaseAttempt(
                        candidate_id=remaining_candidate_id,
                        source_document_id=remaining_document_id,
                        status=CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        reason="unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
            attempts.append(attempt)
        return _result(
            plan,
            live=live,
            acknowledge_pacer_fees=acknowledge_pacer_fees,
            capability=self.capability,
            attempts=tuple(attempts),
        )


def _validate_plan_budget(plan: MissingCoreBudgetPlan) -> None:
    for case_plan in plan.case_plans:
        if (
            case_plan.missing_core_document_count
            > plan.max_missing_core_documents_per_case
        ):
            raise CaseDocumentCapExceededError(
                f"{case_plan.candidate_id} has "
                f"{case_plan.missing_core_document_count} missing core documents; "
                f"cap is {plan.max_missing_core_documents_per_case}"
            )
    if plan.total_estimated_cost > plan.max_projected_budget:
        raise PurchaseBudgetExceededError(
            "projected total "
            f"${plan.total_estimated_cost_usd} exceeds budget "
            f"${plan.max_projected_budget_usd}"
        )


def _successful_attempt(
    candidate_id: str,
    document_id: str,
    payload: Mapping[str, Any],
) -> CaseDevPacerPurchaseAttempt:
    fee_acknowledged = _optional_bool(
        payload,
        "acknowledgePacerFees",
        "feeAcknowledged",
    )
    if fee_acknowledged is not True:
        raise ValueError("purchase response must confirm PACER fee acknowledgment")
    return CaseDevPacerPurchaseAttempt(
        candidate_id=candidate_id,
        source_document_id=document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        fee_acknowledged=fee_acknowledged,
        pacer_fees=_pacer_fees(payload.get("pacerFees", payload.get("pacer_fees"))),
        download_url=_optional_string(payload, "downloadUrl", "download_url", "url"),
    )


def _result(
    plan: MissingCoreBudgetPlan,
    *,
    live: bool,
    acknowledge_pacer_fees: bool,
    capability: CaseDevPacerCapability,
    attempts: tuple[CaseDevPacerPurchaseAttempt, ...],
) -> CaseDevPacerPurchaseResult:
    return CaseDevPacerPurchaseResult(
        live=live,
        acknowledge_pacer_fees=acknowledge_pacer_fees,
        capability=capability,
        dry_run=plan.dry_run,
        projected_cost_usd=plan.total_estimated_cost_usd,
        max_projected_budget_usd=plan.max_projected_budget_usd,
        attempts=attempts,
    )


def _pacer_fees(value: object) -> Mapping[str, str]:
    if value is None:
        raise ValueError("purchase response must include PACER fees")
    if not isinstance(value, Mapping):
        raise ValueError("purchase response PACER fees must be an object")
    fees = cast(Mapping[object, object], value)
    parsed = {
        "pacer_fee_usd": _money_field(fees, "pacerFee", "pacer_fee"),
        "service_fee_usd": _money_field(fees, "serviceFee", "service_fee"),
        "total_usd": _money_field(fees, "total", "totalFee", "total_fee"),
    }
    if Decimal(parsed["pacer_fee_usd"]) + Decimal(parsed["service_fee_usd"]) != Decimal(
        parsed["total_usd"]
    ):
        raise ValueError("PACER fee total must equal PACER plus service fees")
    return parsed


def _money_field(record: Mapping[object, object], *field_names: str) -> str:
    for field_name in field_names:
        value = record.get(field_name)
        if value is not None:
            return _money(value)
    raise ValueError(f"PACER fee response is missing {field_names[0]}")


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("PACER fee values must be decimal dollar amounts") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("PACER fee values cannot be negative")
    quantized = amount.quantize(Decimal("0.01"))
    if amount != quantized:
        raise ValueError("PACER fee values cannot use sub-cent precision")
    return f"{quantized:.2f}"


def _validated_purchase_policy(
    decisions: Mapping[str, object],
) -> dict[str, object]:
    _exact_keys(
        decisions,
        {
            "cycle_id",
            "cohort_policy_sha256",
            "canonical_ledger_path",
            "hard_cap_usd",
            "opening_committed_spend_usd",
            "opening_case_committed_spend_usd",
            "max_per_case_usd",
            "per_document_reservation_usd",
            "fee_schedule",
        },
        "purchase policy",
    )
    cycle_id = _required_text(decisions.get("cycle_id"), "cycle_id")
    cohort_hash = _required_sha(
        decisions.get("cohort_policy_sha256"), "cohort_policy_sha256"
    )
    ledger_text = _required_text(
        decisions.get("canonical_ledger_path"), "canonical_ledger_path"
    )
    ledger_path = Path(ledger_text)
    if not ledger_path.is_absolute() or ledger_path != ledger_path.resolve():
        raise CaseDevPurchasePolicyError(
            "canonical_ledger_path must be an absolute normalized path"
        )
    hard_cap = _policy_money(decisions.get("hard_cap_usd"), "hard_cap_usd")
    opening_committed = _policy_money(
        decisions.get("opening_committed_spend_usd"),
        "opening_committed_spend_usd",
    )
    max_per_case = _policy_money(decisions.get("max_per_case_usd"), "max_per_case_usd")
    reservation = _policy_money(
        decisions.get("per_document_reservation_usd"),
        "per_document_reservation_usd",
    )
    if hard_cap <= 0 or max_per_case <= 0 or reservation <= 0:
        raise CaseDevPurchasePolicyError("purchase policy amounts must be positive")
    if opening_committed < 0 or opening_committed > hard_cap:
        raise CaseDevPurchasePolicyError(
            "opening committed spend must be within the cycle hard cap"
        )
    if max_per_case > hard_cap:
        raise CaseDevPurchasePolicyError("max per-case cap exceeds cycle hard cap")
    if reservation > max_per_case:
        raise CaseDevPurchasePolicyError("document reservation exceeds per-case cap")
    raw_opening_cases = decisions.get("opening_case_committed_spend_usd")
    if not isinstance(raw_opening_cases, Mapping):
        raise CaseDevPurchasePolicyError(
            "opening_case_committed_spend_usd must be an object"
        )
    typed_opening_cases = cast(Mapping[object, object], raw_opening_cases)
    opening_cases: dict[str, str] = {}
    opening_case_total = Decimal("0")
    for raw_case_id in sorted(typed_opening_cases, key=str):
        if (
            not isinstance(raw_case_id, str)
            or not raw_case_id
            or raw_case_id.strip() != raw_case_id
        ):
            raise CaseDevPurchasePolicyError(
                "opening commitment case ID must be a non-empty canonical string"
            )
        raw_amount = typed_opening_cases[raw_case_id]
        if (
            not isinstance(raw_amount, str)
            or _CANONICAL_USD.fullmatch(raw_amount) is None
        ):
            raise CaseDevPurchasePolicyError(
                "opening case commitment must be canonical nonnegative USD"
            )
        amount = Decimal(raw_amount)
        if amount > max_per_case:
            raise CaseDevPurchasePolicyError(
                "opening case commitment exceeds per-case cap"
            )
        opening_cases[raw_case_id] = raw_amount
        opening_case_total += amount
    if opening_case_total != opening_committed:
        raise CaseDevPurchasePolicyError(
            "opening case commitments must exactly equal opening committed spend"
        )
    raw_schedule = decisions.get("fee_schedule")
    if not isinstance(raw_schedule, Mapping):
        raise CaseDevPurchasePolicyError("fee_schedule must be an object")
    schedule = cast(Mapping[str, object], raw_schedule)
    _exact_keys(
        schedule,
        {
            "source_citation",
            "verified_at_utc",
            "includes_pacer_fees",
            "includes_service_fees",
            "includes_rounding",
        },
        "fee_schedule",
    )
    source = _required_text(schedule.get("source_citation"), "source_citation")
    verified_at = _required_text(schedule.get("verified_at_utc"), "verified_at_utc")
    try:
        parsed_verified_at = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaseDevPurchasePolicyError("verified_at_utc must be ISO-8601") from exc
    if parsed_verified_at.tzinfo is None:
        raise CaseDevPurchasePolicyError("verified_at_utc must include a timezone")
    for field in (
        "includes_pacer_fees",
        "includes_service_fees",
        "includes_rounding",
    ):
        if schedule.get(field) is not True:
            raise CaseDevPurchasePolicyError(f"fee_schedule {field} must be true")
    return {
        "cycle_id": cycle_id,
        "cohort_policy_sha256": cohort_hash,
        "canonical_ledger_path": str(ledger_path),
        "hard_cap_usd": _money(hard_cap),
        "opening_committed_spend_usd": _money(opening_committed),
        "opening_case_committed_spend_usd": opening_cases,
        "max_per_case_usd": _money(max_per_case),
        "per_document_reservation_usd": _money(reservation),
        "fee_schedule": {
            "source_citation": source,
            "verified_at_utc": verified_at,
            "includes_pacer_fees": True,
            "includes_service_fees": True,
            "includes_rounding": True,
        },
    }


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise CaseDevPurchasePolicyError(
            f"{label} keys mismatch; missing={missing}, unexpected={unexpected}"
        )


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseDevPurchasePolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _required_sha(value: object, label: str) -> str:
    text = _required_text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise CaseDevPurchasePolicyError(f"{label} must be a lowercase SHA-256")
    return text


def _policy_money(value: object, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise CaseDevPurchasePolicyError(f"{label} must be decimal money") from exc
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise CaseDevPurchasePolicyError(f"{label} must have at most two decimals")
    return amount


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _optional_bool(record: Mapping[str, Any], *field_names: str) -> bool | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, bool):
            return value
    return None


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None
