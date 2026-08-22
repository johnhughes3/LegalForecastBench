"""Descriptor-pinned I/O for manifest cost projection issuance."""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from legalforecast.protocol.manifest import hash_payload


def normalized_absolute(path: Path) -> Path:
    """Return an absolute lexical path without following filesystem links."""

    return Path(os.path.abspath(os.fspath(path)))


def verify_receipt_self_hash(
    receipt: Mapping[str, Any], *, error_type: type[ValueError]
) -> None:
    """Verify the canonical top-level self-hash before publication."""

    content = dict(receipt)
    claimed = content.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or not _is_lowercase_sha256(claimed):
        raise error_type("receipt_sha256 is missing or invalid")
    if hash_payload(content) != claimed:
        raise error_type("receipt_sha256 does not match receipt body")


def write_create_only(
    path: Path, payload: bytes, *, error_type: type[ValueError]
) -> None:
    """Stage and atomically install one receipt without replacing a peer."""

    output = normalized_absolute(path)
    if output.name in {"", ".", ".."}:
        raise error_type("cost projection output name is invalid")
    parent_fd = _open_directory_no_symlinks(output.parent, error_type=error_type)
    temporary = f".{output.name}.{secrets.token_hex(12)}.partial"
    temporary_fd: int | None = None
    linked = False
    try:
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise error_type(
                f"output already exists; refusing create-only issuance: {path}"
            )
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        temporary_fd = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
        _write_all(temporary_fd, payload, error_type=error_type)
        os.fsync(temporary_fd)
        metadata = os.fstat(temporary_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != len(payload)
            or _read_descriptor(temporary_fd) != payload
        ):
            raise error_type("staged cost projection receipt failed byte verification")
        confirmation_fd = _open_directory_no_symlinks(
            output.parent, error_type=error_type
        )
        try:
            if _directory_identity(
                parent_fd, error_type=error_type
            ) != _directory_identity(confirmation_fd, error_type=error_type):
                raise error_type(
                    "cost projection output parent changed before installation"
                )
        finally:
            os.close(confirmation_fd)
        try:
            os.link(
                temporary,
                output.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise error_type(
                f"output appeared concurrently; refusing create-only issuance: {path}"
            ) from exc
        linked = True
    except OSError as exc:
        raise error_type(f"cannot create cost projection receipt: {path}") from exc
    finally:
        cleanup_error: OSError | None = None
        if temporary_fd is not None:
            try:
                os.close(temporary_fd)
            except OSError as exc:
                cleanup_error = exc
        try:
            os.unlink(temporary, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            cleanup_error = cleanup_error or exc
        if linked:
            try:
                os.fsync(parent_fd)
            except OSError:
                pass
        try:
            os.close(parent_fd)
        except OSError as exc:
            cleanup_error = cleanup_error or exc
        if cleanup_error is not None and not linked:
            raise error_type(
                f"cannot clean staged cost projection receipt: {path}"
            ) from cleanup_error


def _open_directory_no_symlinks(path: Path, *, error_type: type[ValueError]) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise error_type("safe receipt publication requires O_NOFOLLOW and O_DIRECTORY")
    absolute = normalized_absolute(path)
    traversal = getattr(os, "O_PATH", getattr(os, "O_SEARCH", os.O_RDONLY))
    flags = traversal | directory | nofollow | getattr(os, "O_CLOEXEC", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise error_type(
            f"cost projection output parent is unsafe or missing: {path}"
        ) from exc


def _directory_identity(
    descriptor: int, *, error_type: type[ValueError]
) -> tuple[int, int, int]:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise error_type("cost projection output parent is not a directory")
    return metadata.st_dev, metadata.st_ino, metadata.st_mode


def _write_all(
    descriptor: int, payload: bytes, *, error_type: type[ValueError]
) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise error_type("short write while staging cost receipt")
        view = view[written:]


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def _is_lowercase_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
