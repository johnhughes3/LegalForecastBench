"""Contributor-grade native whole-process boundary.

This is the strongest filesystem-plus-process boundary a contributor machine
can enforce without root or extra packages: Linux Landlock (kernel LSM) for
path scope, the landed local-CLI environment builder for env minimization,
POSIX process-group lifetime, and the #712 redaction path for transcripts.

bubblewrap is not used. Unprivileged user namespaces are often blocked by
AppArmor on contributor hosts; Landlock needs neither.
"""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.multiharness.validation import validate_public_record

CONTRIBUTOR_NATIVE_BOUNDARY: Final = "contributor_native_whole_process.v1"
LINUX_LANDLOCK_FS_SCOPE: Final = "linux_landlock_fs.v1"
HOSTILE_DENIED: Final = "denied"
HOSTILE_QUARANTINED: Final = "quarantined"
HOSTILE_REFUSED: Final = "refused"
HOSTILE_IN_SCOPE: Final = "in_scope"

_SYS_LANDLOCK_CREATE_RULESET = 444
_LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
_SYSTEM_READ_ROOTS = (
    "/usr",
    "/lib",
    "/lib64",
    "/bin",
    "/sbin",
    "/etc",
    "/proc",
    "/dev",
)


class ContributorBoundaryError(RuntimeError):
    """Raised when the contributor-grade boundary cannot be established."""

    def __init__(self, message: str, *, establishment: str = "failed") -> None:
        super().__init__(message)
        self.establishment = establishment


@dataclass(frozen=True, slots=True)
class ContributorBoundaryPlan:
    """Public, path-free identity of one contributor-grade boundary."""

    policy_id: str
    filesystem_scope: str
    host_process_containment: str
    isolated_environment: bool
    transcript_redaction: bool

    def to_public_record(self) -> dict[str, object]:
        """Return the only boundary fields allowed in public receipts."""

        record: dict[str, object] = {
            "policy_id": self.policy_id,
            "filesystem_scope": self.filesystem_scope,
            "host_process_containment": self.host_process_containment,
            "isolated_environment": self.isolated_environment,
            "transcript_redaction": self.transcript_redaction,
        }
        validate_public_record(record, "contributor boundary identity")
        return record


def contributor_boundary_plan(
    *,
    host_process_containment: str,
) -> ContributorBoundaryPlan:
    """Return the contributor-grade boundary identity for one run."""

    return ContributorBoundaryPlan(
        policy_id=CONTRIBUTOR_NATIVE_BOUNDARY,
        filesystem_scope=LINUX_LANDLOCK_FS_SCOPE,
        host_process_containment=host_process_containment,
        isolated_environment=True,
        transcript_redaction=True,
    )


def preflight_contributor_boundary() -> int:
    """Prove Landlock works before a contributor CLI is launched."""

    if sys.platform != "linux":
        raise ContributorBoundaryError(
            "contributor-grade filesystem scope requires Linux Landlock",
            establishment="unsupported",
        )
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    version = int(
        libc.syscall(
            _SYS_LANDLOCK_CREATE_RULESET,
            None,
            0,
            _LANDLOCK_CREATE_RULESET_VERSION,
        )
    )
    if version < 1:
        raise ContributorBoundaryError(
            "contributor-grade filesystem scope requires Landlock",
            establishment="unsupported",
        )
    return version


def wrap_argv_for_contributor_boundary(
    argv: tuple[str, ...],
    *,
    scratch_root: Path,
    extra_read_paths: Sequence[Path] = (),
    extra_write_paths: Sequence[Path] = (),
) -> tuple[tuple[str, ...], dict[str, object]]:
    """Wrap argv so the child applies Landlock before exec."""

    abi = preflight_contributor_boundary()
    if not argv:
        raise ContributorBoundaryError("contained command is empty")
    scratch = scratch_root.resolve()
    if not scratch.is_dir() or scratch.is_symlink():
        raise ContributorBoundaryError("scratch root must be a real directory")
    wrapper = Path(__file__).with_name("_landlock_exec.py")
    read_paths = _unique_existing(
        (
            *_system_read_roots(),
            *_launch_read_paths(argv),
            *extra_read_paths,
            wrapper,
        )
    )
    write_paths = _unique_existing((scratch, *extra_write_paths))
    if scratch not in write_paths:
        raise ContributorBoundaryError("scratch root must be writable in-scope")
    rules_path = scratch / f"landlock-rules.{secrets.token_hex(8)}.json"
    payload = {
        "read_paths": [str(path) for path in read_paths],
        "write_paths": [str(path) for path in write_paths],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(rules_path, flags, 0o600)
    except OSError as exc:
        raise ContributorBoundaryError("landlock rules could not be created") from exc
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(encoded)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    wrapped = (
        sys.executable,
        str(wrapper),
        "--rules",
        str(rules_path),
        "--",
        *argv,
    )
    identity = contributor_boundary_plan(
        host_process_containment="posix_process_group.v1",
    ).to_public_record()
    identity["landlock_abi"] = abi
    validate_public_record(identity, "contributor boundary identity")
    return wrapped, identity


def classify_hostile_probe(*, in_scope: bool, denied: bool, tampered: bool) -> str:
    """Return the closed classification for one hostile probe outcome."""

    if tampered:
        return HOSTILE_QUARANTINED
    if denied:
        return HOSTILE_DENIED
    if in_scope:
        return HOSTILE_IN_SCOPE
    return HOSTILE_REFUSED


def _system_read_roots() -> tuple[Path, ...]:
    return tuple(Path(root) for root in _SYSTEM_READ_ROOTS if Path(root).exists())


def _launch_read_paths(argv: Sequence[str]) -> tuple[Path, ...]:
    paths: list[Path] = []
    for token in argv[:2]:
        candidate = Path(token)
        if candidate.is_file():
            paths.extend(_executable_read_paths(candidate))
    paths.append(Path(sys.executable).resolve())
    prefix = getattr(sys, "base_prefix", sys.prefix)
    paths.append(Path(str(prefix)))
    paths.append(Path(sys.prefix))
    return tuple(paths)


def _executable_read_paths(executable: Path) -> tuple[Path, ...]:
    paths = [executable]
    try:
        resolved = executable.resolve()
    except OSError:
        return tuple(paths)
    paths.append(resolved)
    if resolved.parent.name in {"bin", "Scripts"}:
        paths.append(resolved.parent.parent)
    return tuple(paths)


def _unique_existing(paths: Sequence[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.exists():
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return tuple(unique)


def require_filesystem_scope(value: str | None) -> str:
    """Return a supported filesystem-scope id or fail closed."""

    if value != LINUX_LANDLOCK_FS_SCOPE:
        raise ContributorBoundaryError(
            "filesystem_scope must be linux_landlock_fs.v1",
            establishment="unsupported",
        )
    return value
