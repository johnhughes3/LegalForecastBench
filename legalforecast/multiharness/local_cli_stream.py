"""Mid-stream stdout/stderr drain for contained local CLI processes.

Capture is truncated while the child is still running so a runaway solver
cannot fill the historic 256 MiB disk cap. The receipt records truncation;
silent truncation is a defect.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import IO

_TRUNCATION_MARKER = b"\n[truncated]\n"
_READ_CHUNK_BYTES = 65_536


@dataclass
class StreamDrain:
    """In-memory capture with a rolling tail, truncated at ``max_capture_bytes``."""

    max_capture_bytes: int
    tail_bytes: int
    captured: bytearray = field(default_factory=bytearray)
    tail: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    total: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def feed(self, chunk: bytes) -> None:
        """Accept one pipe chunk, keeping capture and tail bounded."""

        if not chunk:
            return
        with self._lock:
            self.total += len(chunk)
            self.tail.extend(chunk)
            overflow = len(self.tail) - self.tail_bytes
            if overflow > 0:
                del self.tail[:overflow]
            room = self.max_capture_bytes - len(self.captured)
            if room > 0:
                self.captured.extend(chunk[:room])
                if len(chunk) > room:
                    self.truncated = True
            else:
                self.truncated = True

    def finish(self) -> tuple[bytes, bool]:
        """Return bounded capture bytes and whether truncation occurred."""

        with self._lock:
            raw = bytes(self.captured)
            truncated = self.truncated or self.total > self.max_capture_bytes
            if truncated:
                marker = _TRUNCATION_MARKER[: self.max_capture_bytes]
                raw = raw[: max(0, self.max_capture_bytes - len(marker))] + marker
                raw = raw[: self.max_capture_bytes]
            return raw, truncated

    def tail_bytes_copy(self) -> bytes:
        """Return the rolling tail used for cost-envelope parsing."""

        with self._lock:
            return bytes(self.tail)


def start_pipe_drain(pipe: IO[bytes], drain: StreamDrain) -> threading.Thread:
    """Read ``pipe`` on a daemon thread until EOF."""

    thread = threading.Thread(
        target=_drain_pipe,
        args=(pipe, drain),
        daemon=True,
        name="local-cli-stream-drain",
    )
    thread.start()
    return thread


def join_pipe_drains(
    threads: Sequence[threading.Thread],
    *,
    timeout_seconds: float,
) -> None:
    """Wait for drain threads after the child has exited or been killed."""

    for thread in threads:
        thread.join(timeout=timeout_seconds)


def _drain_pipe(pipe: IO[bytes], drain: StreamDrain) -> None:
    try:
        while True:
            chunk = pipe.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            drain.feed(chunk)
    finally:
        pipe.close()
