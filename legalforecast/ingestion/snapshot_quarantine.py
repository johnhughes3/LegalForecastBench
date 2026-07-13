"""Fail-closed quarantine for unregistered acquisition snapshot directories."""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    SnapshotVerificationError,
    verify_snapshot,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_SNAPSHOT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_RECEIPT_SCHEMA = "legalforecast.snapshot_orphan_quarantine.v1"


class SnapshotQuarantineError(RuntimeError):
    """Raised when an orphan snapshot cannot be proven safe to quarantine."""


def quarantine_orphan_snapshot(
    *,
    cycle_store: Path,
    orphan_snapshot: Path,
    quarantine_root: Path,
    receipt_output: Path,
    expected_snapshot_id: str,
    expected_orphan_manifest_sha256: str,
    expected_canonical_manifest_sha256: str,
    execute: bool,
) -> dict[str, Any]:
    """Verify and optionally atomically quarantine one unregistered snapshot.

    The cycle database is opened read-only and is never changed. Both the orphan
    and registered canonical snapshot must independently verify against explicit
    manifest hashes before the orphan is moved on the same filesystem.
    """

    store_path = cycle_store.resolve()
    lock_path = Path(f"{store_path}.lock")
    if not lock_path.is_file():
        raise SnapshotQuarantineError(f"cycle store lock file is missing: {lock_path}")
    lock_descriptor = os.open(lock_path, os.O_RDONLY)
    try:
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SnapshotQuarantineError(
                "cycle store is active; refusing concurrent quarantine"
            ) from error
        return _quarantine_orphan_snapshot_locked(
            cycle_store=store_path,
            orphan_snapshot=orphan_snapshot,
            quarantine_root=quarantine_root,
            receipt_output=receipt_output,
            expected_snapshot_id=expected_snapshot_id,
            expected_orphan_manifest_sha256=expected_orphan_manifest_sha256,
            expected_canonical_manifest_sha256=(expected_canonical_manifest_sha256),
            execute=execute,
        )
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def _quarantine_orphan_snapshot_locked(
    *,
    cycle_store: Path,
    orphan_snapshot: Path,
    quarantine_root: Path,
    receipt_output: Path,
    expected_snapshot_id: str,
    expected_orphan_manifest_sha256: str,
    expected_canonical_manifest_sha256: str,
    execute: bool,
) -> dict[str, Any]:
    store_path = cycle_store.resolve()
    store_root = store_path.parent
    orphan_path = orphan_snapshot.resolve()
    quarantine_directory = quarantine_root.resolve()
    receipt_path = receipt_output.resolve()
    if _SNAPSHOT_ID.fullmatch(expected_snapshot_id) is None:
        raise SnapshotQuarantineError("expected snapshot ID contains unsafe characters")
    orphan_manifest_hash = _normalize_sha256(
        expected_orphan_manifest_sha256,
        field="expected orphan manifest SHA-256",
    )
    canonical_manifest_hash = _normalize_sha256(
        expected_canonical_manifest_sha256,
        field="expected canonical manifest SHA-256",
    )
    if not store_path.is_file():
        raise SnapshotQuarantineError(f"cycle store is missing: {store_path}")
    wal_path = store_path.with_name(f"{store_path.name}-wal")
    if wal_path.exists() and wal_path.stat().st_size:
        raise SnapshotQuarantineError(
            "cycle store has a nonempty WAL; immutable read-only verification "
            "would not observe all committed state"
        )
    if not orphan_path.is_relative_to(store_root):
        raise SnapshotQuarantineError(
            "orphan snapshot must be inside the cycle store root"
        )
    if not quarantine_directory.is_dir():
        raise SnapshotQuarantineError(
            f"quarantine root must already exist: {quarantine_directory}"
        )
    target = quarantine_directory / (
        f"{expected_snapshot_id}--orphan--{orphan_manifest_hash[:16]}"
    )
    orphan_exists = orphan_path.is_dir()
    target_exists = target.is_dir()
    recovering_completed_move = not orphan_exists and target_exists
    if not orphan_exists and not recovering_completed_move:
        raise SnapshotQuarantineError(
            f"orphan snapshot directory is missing: {orphan_path}"
        )
    if orphan_exists and target.exists():
        raise SnapshotQuarantineError(f"quarantine target already exists: {target}")
    if quarantine_directory.is_relative_to(store_root):
        raise SnapshotQuarantineError(
            "quarantine root must be outside the cycle store root"
        )
    if receipt_path.is_relative_to(store_root):
        raise SnapshotQuarantineError(
            "quarantine receipt must be outside the cycle store root"
        )
    if not receipt_path.parent.is_dir():
        raise SnapshotQuarantineError(
            f"receipt parent must already exist: {receipt_path.parent}"
        )
    verified_orphan_path = target if recovering_completed_move else orphan_path
    if verified_orphan_path.stat().st_dev != quarantine_directory.stat().st_dev:
        raise SnapshotQuarantineError(
            "orphan and quarantine root must be on the same filesystem"
        )
    cycle_store_hash = _sha256_file(store_path)

    connection = _open_immutable_store(store_path)
    try:
        canonical_row = connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            (expected_snapshot_id,),
        ).fetchone()
        if canonical_row is None:
            raise SnapshotQuarantineError(
                f"snapshot ID is not registered: {expected_snapshot_id}"
            )
        canonical_path = Path(str(canonical_row["path"])).resolve()
        path_rows = connection.execute(
            "SELECT snapshot_id, path FROM snapshots ORDER BY snapshot_id"
        ).fetchall()
        controlled_paths = {
            "orphan source": orphan_path,
            "quarantine target": target,
            "receipt": receipt_path,
        }
        for row in path_rows:
            registered_path = Path(str(row["path"])).resolve()
            for controlled_name, controlled_path in controlled_paths.items():
                if _paths_overlap(registered_path, controlled_path):
                    raise SnapshotQuarantineError(
                        f"{controlled_name} path is not disjoint from registered "
                        f"snapshot {row['snapshot_id']}"
                    )
        if not canonical_path.is_relative_to(store_root):
            raise SnapshotQuarantineError(
                "registered canonical snapshot is outside the cycle store root"
            )
        if int(canonical_row["complete"]) != 1:
            raise SnapshotQuarantineError(
                "registered canonical snapshot is not complete"
            )
        try:
            parsed_database_manifest = cast(
                object, json.loads(str(canonical_row["manifest_json"]))
            )
        except json.JSONDecodeError as error:
            raise SnapshotQuarantineError(
                "registered database manifest is invalid"
            ) from error
        if not isinstance(parsed_database_manifest, dict):
            raise SnapshotQuarantineError(
                "registered database manifest is not an object"
            )
        database_manifest = cast(dict[str, Any], parsed_database_manifest)
    except sqlite3.Error as error:
        raise SnapshotQuarantineError(
            f"cannot verify cycle store snapshot registry: {error}"
        ) from error
    finally:
        connection.close()

    canonical_disk_hash = _sha256_file(canonical_path / "manifest.json")
    if canonical_disk_hash != canonical_manifest_hash:
        raise SnapshotQuarantineError(
            "canonical snapshot manifest SHA-256 does not match expected commitment"
        )
    orphan_disk_hash = _sha256_file(verified_orphan_path / "manifest.json")
    if orphan_disk_hash != orphan_manifest_hash:
        raise SnapshotQuarantineError(
            "orphan snapshot manifest SHA-256 does not match expected commitment"
        )
    try:
        canonical_manifest = dict(
            verify_snapshot(canonical_path, require_complete=True)
        )
        orphan_manifest = dict(
            verify_snapshot(verified_orphan_path, require_complete=True)
        )
    except SnapshotVerificationError as error:
        raise SnapshotQuarantineError(str(error)) from error
    if canonical_manifest != database_manifest:
        raise SnapshotQuarantineError(
            "canonical disk manifest does not match its registered database manifest"
        )
    if canonical_manifest.get("snapshot_id") != expected_snapshot_id:
        raise SnapshotQuarantineError(
            "canonical snapshot ID does not match expected ID"
        )
    if orphan_manifest.get("snapshot_id") != expected_snapshot_id:
        raise SnapshotQuarantineError("orphan snapshot ID does not match expected ID")
    for field in ("cycle_hash", "batch_id", "batch_digest"):
        if orphan_manifest.get(field) != canonical_manifest.get(field):
            raise SnapshotQuarantineError(
                f"orphan and canonical snapshot {field} commitments differ"
            )

    operation_fields = {
        "cycle_store": str(store_path),
        "cycle_store_sha256": cycle_store_hash,
        "snapshot_id": expected_snapshot_id,
        "orphan_source_path": str(orphan_path),
        "registered_canonical_path": str(canonical_path),
        "quarantine_target_path": str(target),
        "orphan_manifest_sha256": orphan_manifest_hash,
        "canonical_manifest_sha256": canonical_manifest_hash,
    }
    operation_id = hashlib.sha256(
        _canonical_json(operation_fields).encode()
    ).hexdigest()
    receipt_base: dict[str, Any] = {
        "schema_version": _RECEIPT_SCHEMA,
        "operation_id": operation_id,
        **operation_fields,
        "orphan_snapshots_path_reference_count": 0,
        "canonical_database_manifest_verified": True,
        "canonical_snapshot_files_verified": True,
        "orphan_snapshot_files_verified": True,
        "same_filesystem_verified": True,
        "database_mutated": False,
        "observations_preserved": True,
        "canonical_files": canonical_manifest["files"],
        "orphan_files": orphan_manifest["files"],
    }
    prior_receipt = _read_prior_receipt(receipt_path, operation_id=operation_id)
    verified_at = datetime.now(UTC).isoformat()
    if recovering_completed_move:
        if not execute:
            raise SnapshotQuarantineError(
                "quarantine move already occurred; rerun with --execute to finalize "
                "the pending receipt"
            )
        if prior_receipt is None or prior_receipt.get("status") not in {
            "move_authorized",
            "quarantined",
        }:
            raise SnapshotQuarantineError(
                "quarantined target exists without a matching authorized receipt"
            )
        if prior_receipt.get("status") == "quarantined":
            return prior_receipt
        _fsync_directory(orphan_path.parent)
        _fsync_directory(quarantine_directory)
        completed_receipt = {
            **receipt_base,
            "status": "quarantined",
            "execute": True,
            "verified_at": prior_receipt.get("verified_at", verified_at),
            "move_recovery_verified_at": datetime.now(UTC).isoformat(),
            "recovered_after_completed_move": True,
        }
        _write_receipt(receipt_path, completed_receipt, allow_replace=True)
        return completed_receipt
    if not execute:
        if prior_receipt is not None:
            if prior_receipt.get("status") != "dry_run_verified":
                raise SnapshotQuarantineError(
                    "existing receipt is not a reusable dry-run receipt"
                )
            return prior_receipt
        receipt = {
            **receipt_base,
            "status": "dry_run_verified",
            "execute": False,
            "verified_at": verified_at,
        }
        _write_receipt(receipt_path, receipt)
        return receipt

    prior_status = None if prior_receipt is None else prior_receipt.get("status")
    if prior_status not in {None, "dry_run_verified", "move_authorized"}:
        raise SnapshotQuarantineError(
            "existing receipt is not an eligible move authorization receipt"
        )
    pending_receipt = {
        **receipt_base,
        "status": "move_authorized",
        "execute": True,
        "verified_at": verified_at,
    }
    if prior_status == "move_authorized":
        pending_receipt["resumed_move_authorization"] = True
        pending_receipt["initial_move_authorized_at"] = cast(
            dict[str, Any], prior_receipt
        ).get("verified_at")
    _write_receipt(
        receipt_path, pending_receipt, allow_replace=prior_receipt is not None
    )
    if _sha256_file(orphan_path / "manifest.json") != orphan_manifest_hash:
        raise SnapshotQuarantineError(
            "orphan manifest changed after verification; refusing move"
        )
    try:
        repeated_orphan_manifest = dict(
            verify_snapshot(orphan_path, require_complete=True)
        )
    except SnapshotVerificationError as error:
        raise SnapshotQuarantineError(
            "orphan snapshot changed after verification: " + str(error)
        ) from error
    if repeated_orphan_manifest != orphan_manifest:
        raise SnapshotQuarantineError(
            "orphan snapshot manifest changed after verification; refusing move"
        )
    if _sha256_file(store_path) != cycle_store_hash:
        raise SnapshotQuarantineError(
            "cycle store changed after read-only verification; refusing move"
        )
    if target.exists():
        raise SnapshotQuarantineError(
            f"quarantine target appeared after verification: {target}"
        )
    _rename_noreplace(orphan_path, target)
    _fsync_directory(orphan_path.parent)
    _fsync_directory(quarantine_directory)
    if _sha256_file(store_path) != cycle_store_hash:
        raise SnapshotQuarantineError(
            "cycle store changed during quarantine; completion cannot be certified"
        )
    completed_receipt = {
        **pending_receipt,
        "status": "quarantined",
        "moved_at": datetime.now(UTC).isoformat(),
    }
    _write_receipt(receipt_path, completed_receipt, allow_replace=True)
    return completed_receipt


def _open_immutable_store(path: Path) -> sqlite3.Connection:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro&immutable=1",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error as error:
        if connection is not None:
            connection.close()
        raise SnapshotQuarantineError(
            f"cannot open cycle store read-only: {error}"
        ) from error


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _normalize_sha256(value: str, *, field: str) -> str:
    normalized = value.removeprefix("sha256:")
    if _SHA256.fullmatch(normalized) is None:
        raise SnapshotQuarantineError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return normalized


def _sha256_file(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError as error:
        raise SnapshotQuarantineError(f"cannot hash {path}: {error}") from error


def _read_prior_receipt(
    path: Path,
    *,
    operation_id: str,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        parsed = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotQuarantineError(
            f"existing receipt is unreadable: {path}"
        ) from error
    if not isinstance(parsed, dict):
        raise SnapshotQuarantineError("existing receipt is not a JSON object")
    receipt = cast(dict[str, Any], parsed)
    if receipt.get("schema_version") != _RECEIPT_SCHEMA:
        raise SnapshotQuarantineError("existing receipt schema does not match")
    if receipt.get("operation_id") != operation_id:
        raise SnapshotQuarantineError("existing receipt operation does not match")
    return receipt


def _write_receipt(
    path: Path,
    receipt: dict[str, Any],
    *,
    allow_replace: bool = False,
) -> None:
    if path.exists() and not allow_replace:
        raise SnapshotQuarantineError(f"receipt already exists: {path}")
    payload = f"{_canonical_json(receipt)}\n".encode()
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically rename a directory without ever replacing a destination."""

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise SnapshotQuarantineError(
            "renameat2(RENAME_NOREPLACE) is unavailable; refusing unsafe move"
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    result = renameat2(
        at_fdcwd,
        os.fsencode(source),
        at_fdcwd,
        os.fsencode(destination),
        rename_noreplace,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise SnapshotQuarantineError(
            f"quarantine target appeared before move: {destination}"
        )
    raise SnapshotQuarantineError(
        f"atomic no-replace quarantine move failed: {os.strerror(error_number)}"
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
