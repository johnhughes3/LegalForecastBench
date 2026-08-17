"""Cross-process claims for authorization-bound Stage A executor outputs."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from pathlib import Path

from legalforecast.ingestion.stage_a_replay_executor.contract import (
    ReplayOutputClaimError,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import ReplaySpec

_OUTPUT_LABELS = {
    "plan_path": "replay plan",
    "execution_path": "replay execution",
    "stage_a_receipt_path": "Stage A receipt",
    "invocation_journal_path": "invocation journal",
    "executor_receipt_path": "executor receipt",
    "terminal_evidence_root": "terminal evidence",
}


class OutputClaimSet:
    """Held cross-process claims for every signed executor output path."""

    def __init__(self, spec: ReplaySpec) -> None:
        self._spec = spec
        self._descriptors: list[int] = []

    def acquire(self) -> None:
        """Acquire every path claim in canonical order or release them all."""

        try:
            for name, path in sorted(
                self._spec.output_paths.items(), key=lambda item: str(item[1])
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                lock_path = _output_lock_path(path)
                flags = os.O_CREAT | os.O_RDWR
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor = os.open(lock_path, flags, 0o600)
                except OSError as exc:
                    raise ReplayOutputClaimError(
                        f"{_OUTPUT_LABELS[name]} output lock is unavailable: {path}"
                    ) from exc
                try:
                    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                        raise ReplayOutputClaimError(
                            f"{_OUTPUT_LABELS[name]} output lock is not regular: {path}"
                        )
                    os.fchmod(descriptor, 0o600)
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    _assert_held_lock(descriptor, lock_path)
                except BlockingIOError as exc:
                    os.close(descriptor)
                    raise ReplayOutputClaimError(
                        f"{_OUTPUT_LABELS[name]} output already exists or is claimed: "
                        f"{path}"
                    ) from exc
                except Exception:
                    os.close(descriptor)
                    raise
                self._descriptors.append(descriptor)
            for name, path in self._spec.output_paths.items():
                if path.exists() or path.is_symlink():
                    raise ReplayOutputClaimError(
                        f"{_OUTPUT_LABELS[name]} output already exists: {path}"
                    )
        except Exception:
            self.release()
            raise

    def release(self) -> None:
        """Release every held output claim; persistent lock files stay reusable."""

        while self._descriptors:
            descriptor = self._descriptors.pop()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def acquire_output_claims(spec: ReplaySpec) -> OutputClaimSet:
    """Atomically exclude canonical executors sharing any signed output path."""

    claims = OutputClaimSet(spec)
    claims.acquire()
    return claims


def _assert_held_lock(descriptor: int, lock_path: Path) -> None:
    """Reject a lock fd that no longer names a single live lock inode."""

    held = os.fstat(descriptor)
    try:
        named = os.lstat(lock_path)
    except OSError as exc:
        raise ReplayOutputClaimError(
            f"output lock path disappeared after acquire: {lock_path}"
        ) from exc
    if (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
        raise ReplayOutputClaimError(
            f"output lock was replaced after acquire: {lock_path}"
        )
    if held.st_nlink != 1:
        raise ReplayOutputClaimError(
            f"output lock is not exclusively linked: {lock_path}"
        )


def _output_lock_path(path: Path) -> Path:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return path.parent / f".stage-a-replay-output-{digest}.lock"
