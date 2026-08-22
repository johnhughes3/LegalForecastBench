"""Create-only recovery of an authenticated published cohort snapshot."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    PublishedSnapshotRecoveryEvidence,
    verify_snapshot,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_RECOVERED_FILES = (
    "screened-cases.jsonl",
    "exclusions.jsonl",
    "summary.json",
    "candidates.jsonl",
    "observations.jsonl",
    "raw-artifacts.jsonl",
    "manifest.json",
)


class PublishedSnapshotRecoveryError(RuntimeError):
    """Raised when exact create-only snapshot recovery cannot be proven."""


@dataclass(frozen=True, slots=True)
class PublishedSnapshotRecoveryResult:
    """Authenticated identity of one recovered snapshot directory."""

    path: Path
    snapshot_id: str
    batch_id: str
    cycle_hash: str
    store_sha256: str
    manifest_sha256: str
    recovered_observation_row_count: int
    payload_sha256: dict[str, str]


@dataclass(frozen=True, slots=True)
class DisposableSnapshotStoreResult:
    """Identity of one create-only path-rebound disposable store copy."""

    root: Path
    cycle_store: Path
    source_store_sha256: str
    disposable_store_sha256: str
    snapshot_id: str
    recovered_snapshot_path: Path
    manifest_sha256: str


def recover_published_snapshot_from_store_commitment(
    *,
    cycle_store: Path,
    expected_store_sha256: str,
    snapshot_id: str,
    expected_manifest_sha256: str,
    output_root: Path,
) -> PublishedSnapshotRecoveryResult:
    """Republish exact committed snapshot bytes without changing the store.

    The source SQLite file and lock are opened through a no-follow parent
    descriptor. The store remains exclusively locked while its exact database
    bytes, stored manifest text, and projected payloads are verified. The
    output is staged in the already-existing output parent and atomically
    renamed without replacement only after :func:`verify_snapshot` succeeds.
    """

    store_digest = _normalize_sha256(
        expected_store_sha256, label="expected cycle-store SHA-256"
    )
    manifest_digest = _normalize_sha256(
        expected_manifest_sha256, label="expected manifest SHA-256"
    )
    store_path = _absolute(cycle_store)
    target = _absolute(output_root)
    if target.name in {"", ".", ".."}:
        raise PublishedSnapshotRecoveryError("output root has an invalid name")
    if _paths_overlap(store_path, target):
        raise PublishedSnapshotRecoveryError(
            "recovery output overlaps the immutable cycle store"
        )

    store_parent_fd = _open_directory_fd(store_path.parent)
    store_fd: int | None = None
    output_parent_fd: int | None = None
    staging_fd: int | None = None
    staging_name: str | None = None
    published = False
    completed = False
    evidence: PublishedSnapshotRecoveryEvidence | None = None
    try:
        store_fd = _open_unique_regular_at(
            store_parent_fd, store_path.name, label="cycle store"
        )
        source_before = _sha256_fd_stable(store_fd, label="cycle store")
        if source_before != store_digest:
            raise PublishedSnapshotRecoveryError("cycle-store SHA-256 mismatch")

        bound_store_path = Path(f"/proc/self/fd/{store_parent_fd}/{store_path.name}")
        with CycleAcquisitionStore(bound_store_path, read_only=True) as store:
            _require_named_identity(
                store_parent_fd, store_path.name, store_fd, label="cycle store"
            )
            evidence = store.published_snapshot_recovery_evidence(snapshot_id)
            if hashlib.sha256(evidence.manifest_bytes).hexdigest() != manifest_digest:
                raise PublishedSnapshotRecoveryError(
                    "stored snapshot manifest SHA-256 mismatch"
                )
            if _paths_overlap(evidence.registered_path, target):
                raise PublishedSnapshotRecoveryError(
                    "recovery output overlaps the registered historical snapshot path"
                )

            output_parent_fd = _open_directory_fd(target.parent)
            _require_absent_at(output_parent_fd, target.name)
            staging_name = f".{target.name}.{uuid.uuid4().hex}.tmp"
            try:
                os.mkdir(staging_name, mode=0o700, dir_fd=output_parent_fd)
            except OSError as error:
                raise PublishedSnapshotRecoveryError(
                    "recovery staging directory could not be created"
                ) from error
            staging_fd = _open_directory_at(output_parent_fd, staging_name)

            payloads = dict(evidence.payloads)
            payloads["manifest.json"] = evidence.manifest_bytes
            for filename in _RECOVERED_FILES:
                _write_unique_regular_at(staging_fd, filename, payloads[filename])
            os.fsync(staging_fd)

            verified = verify_snapshot(
                Path(f"/proc/self/fd/{staging_fd}"),
                expected_cycle_hash=store.cycle_hash,
                expected_batch_digest=store.batch_digest(evidence.batch_id),
                require_complete=True,
                require_saturated=True,
            )
            if dict(verified) != dict(evidence.manifest):
                raise PublishedSnapshotRecoveryError(
                    "recovered snapshot differs from the stored manifest"
                )
            _require_exact_directory_bytes(staging_fd, payloads)

            # Closing immutable SQLite cannot mutate the source; retain the
            # store lock while proving that and while publishing the output.
            store.close_database_for_locked_snapshot()
            _require_named_identity(
                store_parent_fd, store_path.name, store_fd, label="cycle store"
            )
            if _sha256_fd_stable(store_fd, label="cycle store") != store_digest:
                raise PublishedSnapshotRecoveryError(
                    "cycle store changed during recovery verification"
                )
            _require_directory_path_identity(target.parent, output_parent_fd)
            os.close(staging_fd)
            staging_fd = None
            _rename_noreplace_at(output_parent_fd, staging_name, target.name)
            published = True
            staging_name = None
            os.fsync(output_parent_fd)
            _require_directory_path_identity(target.parent, output_parent_fd)
            final_fd = _open_directory_at(output_parent_fd, target.name)
            try:
                _require_exact_directory_bytes(final_fd, payloads)
            finally:
                os.close(final_fd)
            _require_named_identity(
                store_parent_fd, store_path.name, store_fd, label="cycle store"
            )
            if _sha256_fd_stable(store_fd, label="cycle store") != store_digest:
                raise PublishedSnapshotRecoveryError(
                    "cycle store changed during recovery publication"
                )

        assert evidence is not None
        manifest_files = cast(dict[str, dict[str, object]], evidence.manifest["files"])
        result = PublishedSnapshotRecoveryResult(
            path=target,
            snapshot_id=evidence.snapshot_id,
            batch_id=evidence.batch_id,
            cycle_hash=cast(str, evidence.manifest["cycle_hash"]),
            store_sha256=store_digest,
            manifest_sha256=manifest_digest,
            recovered_observation_row_count=cast(
                int, manifest_files["observations.jsonl"]["row_count"]
            ),
            payload_sha256={
                filename: hashlib.sha256(payload).hexdigest()
                for filename, payload in evidence.payloads.items()
            },
        )
        completed = True
        return result
    except PublishedSnapshotRecoveryError:
        raise
    except (CycleAcquisitionStoreError, KeyError, OSError, ValueError) as error:
        raise PublishedSnapshotRecoveryError(str(error)) from error
    finally:
        if staging_fd is not None:
            os.close(staging_fd)
        if output_parent_fd is not None:
            cleanup_name = (
                None if completed else (target.name if published else staging_name)
            )
            if cleanup_name is not None:
                try:
                    _remove_owned_directory_at(output_parent_fd, cleanup_name)
                except (OSError, PublishedSnapshotRecoveryError):
                    # Preserve the original failure. A successful return never
                    # enters cleanup, and owned-directory removal is deliberately
                    # fail-closed if an unexpected entry appeared.
                    pass
            os.close(output_parent_fd)
        if store_fd is not None:
            os.close(store_fd)
        os.close(store_parent_fd)


def prepare_disposable_store_for_recovered_snapshot(
    *,
    cycle_store: Path,
    expected_store_sha256: str,
    snapshot_id: str,
    recovered_snapshot_root: Path,
    expected_manifest_sha256: str,
    output_root: Path,
) -> DisposableSnapshotStoreResult:
    """Create a byte-derived store copy and rebind only its snapshot path.

    The canonical source remains read-only and locked. The new root contains a
    private SQLite copy plus its empty lock file; the copy is then mutated only
    through :meth:`CycleAcquisitionStore.rebind_recovered_published_snapshot_path`.
    It is suitable for the supported ``export-cohort-observations`` command.
    """

    store_digest = _normalize_sha256(
        expected_store_sha256, label="expected cycle-store SHA-256"
    )
    manifest_digest = _normalize_sha256(
        expected_manifest_sha256, label="expected manifest SHA-256"
    )
    store_path = _absolute(cycle_store)
    recovered = _absolute(recovered_snapshot_root)
    target = _absolute(output_root)
    for left, right, label in (
        (store_path, target, "disposable store output overlaps the source store"),
        (recovered, target, "disposable store output overlaps the recovered snapshot"),
        (store_path, recovered, "recovered snapshot overlaps the source store"),
    ):
        if _paths_overlap(left, right):
            raise PublishedSnapshotRecoveryError(label)

    store_parent_fd = _open_directory_fd(store_path.parent)
    store_fd: int | None = None
    recovered_fd: int | None = None
    output_parent_fd: int | None = None
    staging_fd: int | None = None
    staging_name: str | None = None
    published = False
    completed = False
    copy_filename = "cycle-acquisition.sqlite3"
    copy_names = {copy_filename, f"{copy_filename}.lock"}
    disposable_digest = ""
    try:
        store_fd = _open_unique_regular_at(
            store_parent_fd, store_path.name, label="cycle store"
        )
        source_bytes = _read_fd_stable(store_fd, label="cycle store")
        if hashlib.sha256(source_bytes).hexdigest() != store_digest:
            raise PublishedSnapshotRecoveryError("cycle-store SHA-256 mismatch")
        recovered_fd = _open_directory_fd(recovered)

        bound_store_path = Path(f"/proc/self/fd/{store_parent_fd}/{store_path.name}")
        with CycleAcquisitionStore(bound_store_path, read_only=True) as source_store:
            evidence = source_store.published_snapshot_recovery_evidence(snapshot_id)
            if hashlib.sha256(evidence.manifest_bytes).hexdigest() != manifest_digest:
                raise PublishedSnapshotRecoveryError(
                    "stored snapshot manifest SHA-256 mismatch"
                )
            if _paths_overlap(evidence.registered_path, target):
                raise PublishedSnapshotRecoveryError(
                    "disposable store output overlaps the historical snapshot path"
                )
            recovered_payloads = {
                name: _read_unique_regular_at(recovered_fd, name)
                for name in _RECOVERED_FILES
            }
            if recovered_payloads["manifest.json"] != evidence.manifest_bytes:
                raise PublishedSnapshotRecoveryError(
                    "recovered snapshot manifest differs from the store commitment"
                )
            verified = verify_snapshot(
                Path(f"/proc/self/fd/{recovered_fd}"),
                expected_cycle_hash=source_store.cycle_hash,
                expected_batch_digest=source_store.batch_digest(evidence.batch_id),
                require_complete=True,
                require_saturated=True,
            )
            if dict(verified) != dict(evidence.manifest):
                raise PublishedSnapshotRecoveryError(
                    "recovered snapshot differs from the store commitment"
                )
            _require_exact_directory_bytes(recovered_fd, recovered_payloads)

            output_parent_fd = _open_directory_fd(target.parent)
            _require_absent_at(output_parent_fd, target.name)
            staging_name = f".{target.name}.{uuid.uuid4().hex}.tmp"
            os.mkdir(staging_name, mode=0o700, dir_fd=output_parent_fd)
            staging_fd = _open_directory_at(output_parent_fd, staging_name)
            _write_unique_regular_at(staging_fd, copy_filename, source_bytes)
            _write_unique_regular_at(staging_fd, f"{copy_filename}.lock", b"")
            os.fsync(staging_fd)

            copy_path = Path(f"/proc/self/fd/{staging_fd}/{copy_filename}")
            with CycleAcquisitionStore(copy_path) as disposable_store:
                disposable_store.rebind_recovered_published_snapshot_path(
                    snapshot_id,
                    recovered,
                    expected_manifest_sha256=manifest_digest,
                )
            _require_copy_directory(staging_fd, copy_names)
            copy_fd = _open_unique_regular_at(
                staging_fd, copy_filename, label="disposable cycle store"
            )
            try:
                disposable_digest = _sha256_fd_stable(
                    copy_fd, label="disposable cycle store"
                )
            finally:
                os.close(copy_fd)
            with CycleAcquisitionStore(copy_path, read_only=True) as verified_copy:
                rebound = {
                    snapshot.snapshot_id: snapshot.path
                    for snapshot in verified_copy.published_snapshots()
                }
                if rebound.get(snapshot_id) != recovered:
                    raise PublishedSnapshotRecoveryError(
                        "disposable store snapshot path rebind did not persist"
                    )

            source_store.close_database_for_locked_snapshot()
            _require_named_identity(
                store_parent_fd, store_path.name, store_fd, label="cycle store"
            )
            if _sha256_fd_stable(store_fd, label="cycle store") != store_digest:
                raise PublishedSnapshotRecoveryError(
                    "source cycle store changed while preparing disposable copy"
                )
            _require_directory_path_identity(target.parent, output_parent_fd)
            os.close(staging_fd)
            staging_fd = None
            _rename_noreplace_at(output_parent_fd, staging_name, target.name)
            published = True
            staging_name = None
            os.fsync(output_parent_fd)
            _require_directory_path_identity(target.parent, output_parent_fd)
            final_fd = _open_directory_at(output_parent_fd, target.name)
            try:
                _require_copy_directory(final_fd, copy_names)
            finally:
                os.close(final_fd)
            if _sha256_fd_stable(store_fd, label="cycle store") != store_digest:
                raise PublishedSnapshotRecoveryError(
                    "source cycle store changed during disposable-copy publication"
                )

        result = DisposableSnapshotStoreResult(
            root=target,
            cycle_store=target / copy_filename,
            source_store_sha256=store_digest,
            disposable_store_sha256=disposable_digest,
            snapshot_id=snapshot_id,
            recovered_snapshot_path=recovered,
            manifest_sha256=manifest_digest,
        )
        completed = True
        return result
    except PublishedSnapshotRecoveryError:
        raise
    except (CycleAcquisitionStoreError, KeyError, OSError, ValueError) as error:
        raise PublishedSnapshotRecoveryError(str(error)) from error
    finally:
        if staging_fd is not None:
            os.close(staging_fd)
        if output_parent_fd is not None:
            cleanup_name = (
                None if completed else (target.name if published else staging_name)
            )
            if cleanup_name is not None:
                try:
                    _remove_owned_directory_at(
                        output_parent_fd,
                        cleanup_name,
                        allowed_names=copy_names,
                    )
                except (OSError, PublishedSnapshotRecoveryError):
                    # Preserve the original failure; cleanup is best-effort and
                    # never permits publication into an occupied destination.
                    pass
            os.close(output_parent_fd)
        if recovered_fd is not None:
            os.close(recovered_fd)
        if store_fd is not None:
            os.close(store_fd)
        os.close(store_parent_fd)


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _normalize_sha256(value: str, *, label: str) -> str:
    normalized = value.removeprefix("sha256:")
    if _SHA256.fullmatch(normalized) is None:
        raise PublishedSnapshotRecoveryError(
            f"{label} must be 64 lowercase hexadecimal characters"
        )
    return normalized


def _paths_overlap(left: Path, right: Path) -> bool:
    left = _absolute(left)
    right = _absolute(right)
    return left == right or left in right.parents or right in left.parents


def _open_directory_fd(path: Path) -> int:
    absolute = _absolute(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(absolute.anchor, flags)
        try:
            for component in absolute.parts[1:]:
                child = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise
    except OSError as error:
        raise PublishedSnapshotRecoveryError(
            f"directory cannot be opened without symlinks: {absolute}"
        ) from error


def _open_directory_at(parent_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise PublishedSnapshotRecoveryError(
            "recovery directory is not a non-symlink directory"
        ) from error


def _open_unique_regular_at(parent_fd: int, name: str, *, label: str) -> int:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        _require_named_identity(parent_fd, name, descriptor, label=label)
        return descriptor
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise PublishedSnapshotRecoveryError(
            f"{label} must be a singly linked regular non-symlink file"
        ) from error
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _require_named_identity(
    parent_fd: int,
    name: str,
    descriptor: int,
    *,
    label: str,
) -> None:
    opened = os.fstat(descriptor)
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise PublishedSnapshotRecoveryError(
            f"{label} changed while its binding was active"
        ) from error
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or not stat.S_ISREG(named.st_mode)
        or named.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise PublishedSnapshotRecoveryError(
            f"{label} must be a singly linked regular non-symlink file"
        )


# contract-ratchet: allow descriptor-bound raw-byte immutability check, not a codec
def _sha256_fd_stable(descriptor: int, *, label: str) -> str:
    return hashlib.sha256(_read_fd_stable(descriptor, label=label)).hexdigest()


def _read_fd_stable(descriptor: int, *, label: str) -> bytes:
    before = os.fstat(descriptor)
    chunks: list[bytes] = []
    offset = 0
    while chunk := os.pread(descriptor, 1024 * 1024, offset):
        chunks.append(chunk)
        offset += len(chunk)
    after = os.fstat(descriptor)
    if _stat_identity(before) != _stat_identity(after) or offset != after.st_size:
        raise PublishedSnapshotRecoveryError(f"{label} changed while hashing")
    return b"".join(chunks)


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _require_absent_at(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as error:
        raise PublishedSnapshotRecoveryError(
            "recovery output cannot be safely inspected"
        ) from error
    raise PublishedSnapshotRecoveryError("recovery output already exists")


def _write_unique_regular_at(parent_fd: int, name: str, payload: bytes) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise PublishedSnapshotRecoveryError(
            f"recovered snapshot file cannot be created safely: {name}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_unique_regular_at(parent_fd: int, name: str) -> bytes:
    descriptor = _open_unique_regular_at(parent_fd, name, label=name)
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise PublishedSnapshotRecoveryError(
                f"recovered snapshot file changed while reading: {name}"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise PublishedSnapshotRecoveryError(
                f"recovered snapshot file changed while reading: {name}"
            )
        return payload
    finally:
        os.close(descriptor)


def _require_exact_directory_bytes(
    directory_fd: int,
    expected: dict[str, bytes],
) -> None:
    actual_names = {entry.name for entry in os.scandir(f"/proc/self/fd/{directory_fd}")}
    if actual_names != set(expected):
        raise PublishedSnapshotRecoveryError(
            "recovered snapshot directory contains unexpected entries"
        )
    for name, payload in expected.items():
        if _read_unique_regular_at(directory_fd, name) != payload:
            raise PublishedSnapshotRecoveryError(
                f"recovered snapshot file changed before publication: {name}"
            )


def _require_copy_directory(directory_fd: int, expected_names: set[str]) -> None:
    names = {entry.name for entry in os.scandir(f"/proc/self/fd/{directory_fd}")}
    if names != expected_names:
        raise PublishedSnapshotRecoveryError(
            "disposable store root contains unexpected sidecars or entries"
        )
    for name in names:
        descriptor = _open_unique_regular_at(
            directory_fd, name, label="disposable store file"
        )
        os.close(descriptor)


def _require_directory_path_identity(path: Path, descriptor: int) -> None:
    current = _open_directory_fd(path)
    try:
        opened = os.fstat(descriptor)
        named = os.fstat(current)
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise PublishedSnapshotRecoveryError(
                "recovery output ancestor changed during publication"
            )
    finally:
        os.close(current)


def _rename_noreplace_at(
    parent_fd: int,
    source_name: str,
    destination_name: str,
) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise PublishedSnapshotRecoveryError(
            "renameat2(RENAME_NOREPLACE) is unavailable"
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        parent_fd,
        os.fsencode(source_name),
        parent_fd,
        os.fsencode(destination_name),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise PublishedSnapshotRecoveryError("recovery output already exists")
    raise PublishedSnapshotRecoveryError(
        f"atomic no-replace recovery publication failed: {os.strerror(error_number)}"
    )


def _remove_owned_directory_at(
    parent_fd: int,
    name: str,
    *,
    allowed_names: set[str] | None = None,
) -> None:
    try:
        directory_fd = _open_directory_at(parent_fd, name)
    except PublishedSnapshotRecoveryError:
        return
    try:
        names = {entry.name for entry in os.scandir(f"/proc/self/fd/{directory_fd}")}
        permitted = set(_RECOVERED_FILES) if allowed_names is None else allowed_names
        if not names.issubset(permitted):
            raise PublishedSnapshotRecoveryError(
                "refusing to remove recovery directory with unexpected entries"
            )
        for child in names:
            metadata = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise PublishedSnapshotRecoveryError(
                    "refusing to remove nonregular recovery residue"
                )
        for child in names:
            os.unlink(child, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)
