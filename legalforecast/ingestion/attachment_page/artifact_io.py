"""Crash-safe writes for the attachment-menu artifacts.

Every artifact this package produces is evidence about money: a plan an owner
signs against, the authorization that consumes, and the receipt that reports
what was charged. ``Path.write_bytes`` is not adequate for any of them -- a
crash mid-write leaves a truncated file that an exclusive-create policy then
refuses to replace, which loses the evidence and blocks the recovery in one
step.

The two operations here are deliberately separate. Reserving a path is how a
command proves *before* spending that its output slot is free and writable;
replacing is how the bytes land atomically once they exist. A command that
does both at the end has already spent the money it was supposed to report on.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from legalforecast.ingestion.canonical_json import canonical_json_bytes

_CREATE_FLAGS: Final = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_MODE: Final = 0o600


def canonical_artifact_bytes(record: object, *, error: type[ValueError]) -> bytes:
    """Serialize one artifact under the repo's canonical JSON profile."""

    return canonical_json_bytes(
        record,
        error_type=error,
        error_message="artifact is not canonically serializable",
    )


def reserve_artifact_path(path: Path, *, error: type[ValueError]) -> None:
    """Claim an output path exclusively, or refuse before anything is spent.

    The empty file this leaves behind is the reservation: a concurrent writer
    or a re-run against the same ``--output`` refuses here rather than after
    the charges have gone out.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, _CREATE_FLAGS, _MODE)
    except FileExistsError as exc:
        raise error(f"refusing to overwrite an existing artifact at {path}") from exc
    except OSError as exc:
        raise error(f"could not reserve an artifact path at {path}: {exc}") from exc
    os.close(descriptor)


def replace_artifact(path: Path, payload: bytes, *, error: type[ValueError]) -> None:
    """Write bytes to ``path`` atomically, replacing whatever is there.

    The temporary lands in the destination directory so ``os.replace`` stays on
    one filesystem, and the payload is flushed to disk before the rename, so a
    crash leaves either the previous file or the complete new one.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        descriptor = os.open(temporary, _CREATE_FLAGS, _MODE)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        os.replace(temporary, path)
    except OSError as exc:
        raise error(f"could not write the artifact at {path}: {exc}") from exc


def write_new_artifact(
    path: Path, record: Mapping[str, object] | object, *, error: type[ValueError]
) -> None:
    """Reserve a fresh path and land one canonical artifact in it."""

    payload = canonical_artifact_bytes(record, error=error)
    reserve_artifact_path(path, error=error)
    replace_artifact(path, payload, error=error)
