"""Scoped observation of bytes read by an authenticated replay.

The observer is deliberately independent of any CLI or verifier.  A caller
opens one scope around the complete replay, and nested readers contribute the
exact bytes they read to the caller's map.  The map is later rechecked before
publication, closing the replay-to-publication TOCTOU interval without a
second recursive replay.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_AUTHENTICATED_READS: ContextVar[dict[Path, bytes] | None] = ContextVar(
    "authenticated_replay_reads", default=None
)


class AuthenticatedReadConflict(ValueError):
    """Raised when one authenticated replay reads conflicting bytes."""


@contextmanager
def authenticated_read_scope(
    captured: dict[Path, bytes],
) -> Generator[None]:
    """Collect authenticated replay reads into ``captured`` for this scope."""

    token = _AUTHENTICATED_READS.set(captured)
    try:
        yield
    finally:
        _AUTHENTICATED_READS.reset(token)


def record_authenticated_read(path: Path, payload: bytes) -> bool:
    """Record one read, returning ``False`` when the same path conflicts.

    ``Path.absolute`` preserves the lexical path identity while normalizing
    relative callers.  It intentionally does not resolve symlinks: readers
    that permit relocation must record the durable path they actually opened.
    """

    captured = _AUTHENTICATED_READS.get()
    if captured is None:
        return True
    absolute = path.absolute()
    previous = captured.get(absolute)
    if previous is not None and previous != payload:
        return False
    captured[absolute] = payload
    return True


def require_authenticated_read(path: Path, payload: bytes) -> bytes:
    """Record a read and raise the shared conflict when bytes disagree."""

    if not record_authenticated_read(path, payload):
        raise AuthenticatedReadConflict(
            f"authenticated input changed during replay: {path}"
        )
    return payload


def read_bytes(path: Path) -> bytes:
    """Read and record a path, raising on an intra-replay byte conflict."""

    payload = path.read_bytes()
    return require_authenticated_read(path, payload)


def read_text(path: Path) -> str:
    """Read UTF-8 text and record the exact bytes read."""

    return read_bytes(path).decode()
