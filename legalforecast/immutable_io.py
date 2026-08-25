"""Descriptor-anchored reads and create-only tree publication."""

from __future__ import annotations

import ctypes
import errno
import os
import secrets
import shutil
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath


class ImmutableIOError(OSError):
    """Raised when a path cannot satisfy immutable single-link semantics."""


def ensure_private_directory(path: Path) -> Path:
    """Create one owner-private directory and refuse unsafe existing paths."""

    if path.parent != path and not path.parent.exists():
        ensure_private_directory(path.parent)
    try:
        parent_fd = _open_directory_path_no_follow(path.parent)
    except OSError as exc:
        raise ImmutableIOError(f"private directory parent is unsafe: {path}") from exc
    descriptor = -1
    try:
        try:
            os.mkdir(path.name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            # The descriptor and ownership checks below validate existing paths.
            pass
        descriptor = _open_directory_at(parent_fd, path.name)
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ImmutableIOError(
                f"private directory must be owner-only and owner-controlled: {path}"
            )
    except OSError as exc:
        if isinstance(exc, ImmutableIOError):
            raise
        raise ImmutableIOError(f"private directory is unsafe: {path}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)
    return path


def read_single_link_file(path: Path, *, label: str) -> bytes:
    """Read a regular, single-link file through an anchored parent descriptor."""

    parent = path.parent
    try:
        parent_fd = _open_directory_path_no_follow(parent)
    except OSError as exc:
        raise ImmutableIOError(f"{label} parent is unsafe: {parent}") from exc
    try:
        return _read_regular_at(parent_fd, path.name, path, label=label)
    finally:
        os.close(parent_fd)


def publish_tree_create_only(
    root: Path,
    payloads: Mapping[str, bytes],
    *,
    file_modes: Mapping[str, int] | None = None,
) -> None:
    """Atomically install a new tree without replacing a racing destination."""

    if not payloads:
        raise ImmutableIOError("create-only tree must contain at least one file")
    modes = dict(file_modes or {})
    unknown_modes = sorted(set(modes).difference(payloads))
    if unknown_modes:
        raise ImmutableIOError(
            f"file modes reference unknown payloads: {unknown_modes}"
        )
    if any(mode not in {0o400, 0o600} for mode in modes.values()):
        raise ImmutableIOError("create-only tree file modes must be 0400 or 0600")
    try:
        parent_fd = _open_directory_path_no_follow(root.parent)
    except OSError as exc:
        raise ImmutableIOError(f"output parent is unsafe: {root.parent}") from exc
    temporary_name = f".{root.name}.{secrets.token_hex(12)}.tmp"
    temporary_fd = -1
    installed = False
    try:
        try:
            os.mkdir(temporary_name, 0o700, dir_fd=parent_fd)
            temporary_fd = _open_directory_at(parent_fd, temporary_name)
        except OSError as exc:
            raise ImmutableIOError(f"cannot create output tree: {root}") from exc
        for relative_name, payload in sorted(payloads.items()):
            parts = _safe_parts(relative_name)
            directory_fd = os.dup(temporary_fd)
            try:
                for part in parts[:-1]:
                    directory_fd = _descend_or_create(directory_fd, part)
                _write_file_create_only(
                    directory_fd,
                    parts[-1],
                    payload,
                    mode=modes.get(relative_name, 0o600),
                )
            finally:
                os.close(directory_fd)
        os.fsync(temporary_fd)
        _rename_noreplace_at(parent_fd, temporary_name, root.name, root)
        installed = True
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise ImmutableIOError(f"output already exists: {root}") from exc
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)
        if not installed:
            try:
                shutil.rmtree(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                # The staging tree was already absent, so cleanup is complete.
                pass
        os.close(parent_fd)


def write_file_create_only(
    path: Path,
    payload: bytes,
    *,
    mode: int = 0o600,
) -> None:
    """Durably create one file through an anchored parent without replacement."""

    try:
        parent_fd = _open_directory_path_no_follow(path.parent)
    except OSError as exc:
        raise ImmutableIOError(f"output parent is unsafe: {path.parent}") from exc
    try:
        _write_file_create_only(parent_fd, path.name, payload, mode=mode)
    except FileExistsError as exc:
        raise ImmutableIOError(f"output already exists: {path}") from exc
    finally:
        os.close(parent_fd)


def write_file_replace_safe(
    path: Path,
    payload: bytes,
    *,
    mode: int = 0o600,
) -> None:
    """Replace one owner-controlled regular file without following links.

    Resume-aware runtime records are intentionally replaceable, but a
    preexisting symlink or hardlink must never become a write-through path.
    The destination is opened through its anchored parent and validated before
    its contents are truncated.
    """

    try:
        parent_fd = _open_directory_path_no_follow(path.parent)
    except OSError as exc:
        raise ImmutableIOError(f"output parent is unsafe: {path.parent}") from exc
    descriptor = -1
    try:
        no_follow, _, cloexec = _required_open_flags()
        try:
            descriptor = os.open(
                path.name,
                os.O_WRONLY | os.O_CREAT | os.O_NONBLOCK | no_follow | cloexec,
                mode,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise ImmutableIOError(
                f"output is not a writable regular file: {path}"
            ) from exc
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
        ):
            raise ImmutableIOError(
                f"output must be a private, single-link regular file: {path}"
            )
        os.fchmod(descriptor, mode)
        os.ftruncate(descriptor, 0)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _required_open_flags() -> tuple[int, int, int]:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None:
        raise ImmutableIOError("safe immutable I/O requires O_NOFOLLOW and O_DIRECTORY")
    return no_follow, directory, getattr(os, "O_CLOEXEC", 0)


def _open_directory_path_no_follow(path: Path) -> int:
    no_follow, directory, cloexec = _required_open_flags()
    absolute = Path(os.path.abspath(os.fspath(path)))
    flags = os.O_RDONLY | directory | no_follow | cloexec
    current = os.open(absolute.parts[0], flags)
    try:
        for part in absolute.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


def _open_directory_at(parent_fd: int, name: str) -> int:
    no_follow, directory, cloexec = _required_open_flags()
    return os.open(
        name,
        os.O_RDONLY | directory | no_follow | cloexec,
        dir_fd=parent_fd,
    )


def _descend_or_create(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        # The no-follow directory open below validates the existing component.
        pass
    child_fd = _open_directory_at(parent_fd, name)
    os.fsync(parent_fd)
    os.close(parent_fd)
    return child_fd


def _read_regular_at(parent_fd: int, name: str, path: Path, *, label: str) -> bytes:
    no_follow, _, cloexec = _required_open_flags()
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | no_follow | cloexec,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ImmutableIOError(f"cannot read {label}: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ImmutableIOError(
                f"{label} must be a regular file with one link: {path}"
            )
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        return stream.read()


def _write_file_create_only(
    parent_fd: int,
    name: str,
    payload: bytes,
    *,
    mode: int = 0o600,
) -> None:
    no_follow, _, cloexec = _required_open_flags()
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow | cloexec,
        mode,
        dir_fd=parent_fd,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(parent_fd)


def _rename_noreplace_at(
    parent_fd: int, source_name: str, destination_name: str, path: Path
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    rename_noreplace = getattr(libc, "renameat2", None)
    flag = 1
    if rename_noreplace is None:
        raise ImmutableIOError("safe create-only publication requires renameat2")
    rename_noreplace.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename_noreplace.restype = ctypes.c_int
    result = rename_noreplace(
        parent_fd,
        os.fsencode(source_name),
        parent_fd,
        os.fsencode(destination_name),
        flag,
    )
    if result == 0:
        return
    number = ctypes.get_errno()
    if number == errno.EEXIST:
        raise FileExistsError(number, os.strerror(number), path)
    raise ImmutableIOError(number, os.strerror(number), path)


def _safe_parts(relative_name: str) -> tuple[str, ...]:
    path = PurePosixPath(relative_name)
    parts = path.parts
    if (
        not parts
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ImmutableIOError(f"unsafe output member path: {relative_name}")
    return parts
