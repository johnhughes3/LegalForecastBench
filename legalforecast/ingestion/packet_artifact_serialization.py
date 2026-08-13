"""Incremental, byte-stable packet artifact serialization."""

from __future__ import annotations

import errno
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_HARDLINK_UNSUPPORTED_ERRNOS = frozenset(
    {
        errno.EXDEV,
        errno.EPERM,
        errno.ENOTSUP,
        errno.EOPNOTSUPP,
        errno.EMLINK,
    }
)


@dataclass(frozen=True, slots=True)
class PacketArtifactPaths:
    """Destinations for the three packet projections emitted by acquisition."""

    packets: Path
    case_packets: Path
    audit: Path


@dataclass(frozen=True, slots=True)
class PacketArtifactRecords:
    """One case's byte-preserving packet artifact projections."""

    packet: Mapping[str, Any]
    case_packet: Mapping[str, Any]
    audit: Mapping[str, Any]


def write_packet_artifacts_incrementally[Record](
    *,
    paths: PacketArtifactPaths,
    source_records: Iterable[Record],
    build_artifacts: Callable[[Record], PacketArtifactRecords],
) -> None:
    """Write packet projections one case at a time and publish only if complete.

    Each row keeps the established JSONL codec: object conversion, sorted keys,
    ``allow_nan=False``, UTF-8, and exactly one trailing newline.  All three
    temporary files are fully serialized and synced before any destination is
    replaced, so an assembly or serialization error leaves prior artifacts
    untouched and removes staged files.  Catchable publication failures roll
    back the complete prior set.  The established three independent output
    paths do not provide crash-atomic publication across process termination.
    """

    destinations = (paths.packets, paths.case_packets, paths.audit)
    temporary_paths: list[Path] = []
    backup_paths: dict[Path, Path | None] = {}
    handles: list[Any] = []
    try:
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            temporary_paths.append(Path(temporary_name))
            handles.append(os.fdopen(descriptor, "wb"))

        for source_record in source_records:
            artifacts = build_artifacts(source_record)
            _write_jsonl_record(handles[0], artifacts.packet)
            _write_jsonl_record(handles[1], artifacts.case_packet)
            _write_jsonl_record(handles[2], artifacts.audit)
            # Do not accidentally retain a case's packet trees until the next row.
            del artifacts

        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
        handles.clear()

        backup_paths = _snapshot_destinations(destinations)
        try:
            for temporary_path, destination in zip(
                temporary_paths, destinations, strict=True
            ):
                os.replace(temporary_path, destination)
        except OSError as publication_error:
            try:
                _restore_destinations(backup_paths, cause=publication_error)
            except OSError:
                # Preserve any surviving backup links for operator recovery.
                backup_paths.clear()
                raise
            raise
        temporary_paths.clear()
        _remove_backups(backup_paths)
        backup_paths.clear()
    finally:
        for handle in handles:
            handle.close()
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        _remove_backups(backup_paths)


def _snapshot_destinations(
    destinations: tuple[Path, ...],
) -> dict[Path, Path | None]:
    """Retain cheap same-filesystem snapshots for publication rollback.

    Hardlinks are preferred.  When the filesystem cannot create them, a
    byte-for-byte copy preserves the same rollback and cleanup contract.
    """

    backups: dict[Path, Path | None] = {}
    try:
        for destination in destinations:
            if not destination.exists():
                backups[destination] = None
                continue
            descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".backup",
                dir=destination.parent,
            )
            os.close(descriptor)
            backup = Path(backup_name)
            backup.unlink()
            try:
                os.link(destination, backup)
            except OSError as exc:
                if not _hardlink_snapshot_unsupported(exc):
                    raise
                try:
                    shutil.copyfile(destination, backup, follow_symlinks=False)
                except OSError:
                    backup.unlink(missing_ok=True)
                    raise
            backups[destination] = backup
    except OSError:
        _remove_backups(backups)
        raise
    return backups


def _hardlink_snapshot_unsupported(exc: OSError) -> bool:
    """Return True when creating a rollback hardlink is not possible."""

    return exc.errno in _HARDLINK_UNSUPPORTED_ERRNOS


def _restore_destinations(
    backups: Mapping[Path, Path | None], *, cause: OSError
) -> None:
    rollback_errors: list[str] = []
    for destination, backup in backups.items():
        try:
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                os.replace(backup, destination)
                # POSIX rename may be a no-op when both hard links still name
                # the same inode, so remove the redundant backup name.
                backup.unlink(missing_ok=True)
        except OSError as rollback_error:
            rollback_errors.append(f"{destination}: {rollback_error}")
    if rollback_errors:
        raise OSError(
            f"packet artifact publication failed ({cause}); rollback also failed: "
            + "; ".join(rollback_errors)
        ) from cause


def _remove_backups(backups: Mapping[Path, Path | None]) -> None:
    for backup in backups.values():
        if backup is not None:
            backup.unlink(missing_ok=True)


def _write_jsonl_record(handle: Any, record: Mapping[str, Any]) -> None:
    handle.write(
        (json.dumps(dict(record), sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    )
