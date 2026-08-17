"""Generation-safe publication for the paired Stage A review queue.

The v1 review queue and its v2 sidecar describe the same review work, but they
are two files.  Writing them one after another leaves a window in which a
forced process termination can strand a fresh v1 beside a stale or missing v2.
No supported Cycle 1 path reads the pair -- authenticated commitments and Stage
B consume v1 only, and the v2 sidecar is explicitly observational -- so the
window cannot affect adjudication today.  It becomes a real hazard the moment
v2 is promoted to a consumed interface.

This module closes it before that happens.  Each publication writes both
payloads into an immutable, content-addressed *generation* directory and then
switches a single manifest with one atomic rename.  The manifest is the only
mutable name in the scheme, so a reader that resolves both members through it
either sees the complete previous generation or the complete new one, never a
mixed pair.  Any future pair reader must go through
:func:`read_review_queue_generation` rather than opening the two canonical
files directly.

The canonical v1 queue and v2 sidecar are still written at their existing
paths by the CLI: the v1 byte contract is frozen for Cycle 1, and the sidecar
keeps its documented location.  Those files mirror the current generation;
this manifest is what makes the *pair* atomic.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    RAW_BYTES_RAW_SHA256_V1,
    UNITIZATION_REVIEW_QUEUE_GENERATION_V1,
)
from legalforecast.contracts.schemas import RAW_BYTES_RAW_SHA256_COMMITMENT_V1
from legalforecast.unitization.review_queue import ReviewQueueError

_V1_MEMBER_NAME = "unitization-review-queue.jsonl"
_V2_MEMBER_NAME = "unitization-review-queue-v2.jsonl"
_MEMBER_NAMES = ("v1", "v2")


class _PostCommitFsyncError(ReviewQueueError):
    """A directory fsync failed after the named file was atomically replaced."""

    def __init__(self, path: Path, cause: OSError) -> None:
        super().__init__(f"{path}: {cause}")
        self.path = path


class ReviewQueueGenerationCommitError(ReviewQueueError):
    """The generation manifest changed, but its final durability fsync failed."""

    committed = True


@dataclass(frozen=True, slots=True)
class ReviewQueueGeneration:
    """One immutable, digest-verified v1/v2 review-queue pair."""

    generation_id: str
    v1_path: Path
    v1_bytes: bytes
    v2_path: Path
    v2_bytes: bytes


def review_queue_generation_root(queue_path: Path) -> Path:
    """Return the directory holding every published generation of a queue."""

    return queue_path.with_name(f"{queue_path.stem}-generations")


def review_queue_generation_manifest_path(queue_path: Path) -> Path:
    """Return the single mutable pointer naming the current generation."""

    return queue_path.with_name(f"{queue_path.stem}-generation.json")


def review_queue_generation_id(v1_bytes: bytes, v2_bytes: bytes) -> str:
    """Return the content address of one exact v1/v2 pair.

    Both digests are bound together so a generation names the *pair*: two
    publications that share a v1 payload but differ in v2 are different
    generations, which is the whole point of the paired contract.
    """

    return _raw_digest(
        ARTIFACT_CANONICAL_JSON_V1.encode(
            {
                "schema_version": str(UNITIZATION_REVIEW_QUEUE_GENERATION_V1),
                "v1_sha256": _raw_digest(v1_bytes),
                "v2_sha256": _raw_digest(v2_bytes),
            }
        )
    )


def publish_review_queue_generation(
    queue_path: Path, *, v1_bytes: bytes, v2_bytes: bytes
) -> ReviewQueueGeneration:
    """Publish an immutable pair and switch the manifest in one atomic step.

    Members are written and fsynced first; the manifest rename is the single
    commit point.  An interruption before that rename leaves the previous
    generation current and only orphans content-addressed member files, which
    are harmless because their names are their digests.

    Durability is stated in terms of directory entries, not just file bytes: a
    renamed file whose *parent directory* was never fsynced can vanish after a
    host crash even though ``os.replace`` returned.  So every directory entry
    the committed manifest will depend on is persisted before the rename --
    the generations root, the generation directory inside it, and the two
    member files inside that -- walking outward-in and then inside-out.  The
    manifest's own entry is persisted by the ``_atomic_write`` that renames it.
    """

    generation_id = review_queue_generation_id(v1_bytes, v2_bytes)
    generations_root = review_queue_generation_root(queue_path)
    if generations_root.is_symlink():
        raise ReviewQueueError(
            f"review queue generation root is a symlink: {generations_root}"
        )
    generation_root = generations_root / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    if generation_root.is_symlink():
        raise ReviewQueueError(
            f"review queue generation directory is a symlink: {generation_root}"
        )
    manifest_path = review_queue_generation_manifest_path(queue_path)
    _fsync_directory(manifest_path.parent)
    v1_member = generation_root / _V1_MEMBER_NAME
    v2_member = generation_root / _V2_MEMBER_NAME
    _write_immutable_member(v1_member, v1_bytes)
    _write_immutable_member(v2_member, v2_bytes)
    _fsync_directory(generation_root)
    _fsync_directory(generations_root)
    manifest: dict[str, object] = {
        "schema_version": str(UNITIZATION_REVIEW_QUEUE_GENERATION_V1),
        "generation_id": generation_id,
        "members": {
            "v1": _member_record(v1_member, manifest_path, v1_bytes),
            "v2": _member_record(v2_member, manifest_path, v2_bytes),
        },
    }
    try:
        _atomic_write(manifest_path, ARTIFACT_CANONICAL_JSON_V1.encode(manifest))
    except _PostCommitFsyncError as exc:
        if exc.path == manifest_path:
            raise ReviewQueueGenerationCommitError(
                "review queue generation manifest committed, but its directory "
                f"fsync failed: {exc}"
            ) from exc
        raise
    return ReviewQueueGeneration(
        generation_id=generation_id,
        v1_path=v1_member,
        v1_bytes=v1_bytes,
        v2_path=v2_member,
        v2_bytes=v2_bytes,
    )


def read_review_queue_generation(queue_path: Path) -> ReviewQueueGeneration:
    """Resolve both queue members through the manifest and verify their bytes.

    This is the only supported way to read the pair.  Opening the canonical v1
    queue and v2 sidecar directly reintroduces exactly the torn-pair window
    the generation contract exists to close.
    """

    manifest_path = review_queue_generation_manifest_path(queue_path)
    try:
        raw_manifest = _read_direct_child_no_follow(manifest_path)
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue generation manifest is unreadable: {exc}"
        ) from exc
    try:
        parsed = json.loads(raw_manifest)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewQueueError(
            f"review queue generation manifest is invalid JSON: {manifest_path}"
        ) from exc
    manifest = _object(parsed, "review queue generation manifest")
    if set(manifest) != {"schema_version", "generation_id", "members"}:
        raise ReviewQueueError("review queue generation manifest fields differ")
    if manifest.get("schema_version") != str(UNITIZATION_REVIEW_QUEUE_GENERATION_V1):
        raise ReviewQueueError("review queue generation manifest schema differs")
    generation_id = manifest.get("generation_id")
    if not isinstance(generation_id, str) or not is_lowercase_sha256(generation_id):
        raise ReviewQueueError("review queue generation id is invalid")
    members = _object(manifest.get("members"), "review queue generation members")
    if set(members) != set(_MEMBER_NAMES):
        raise ReviewQueueError("review queue generation members differ")
    payloads: dict[str, tuple[Path, bytes]] = {}
    for name in _MEMBER_NAMES:
        payloads[name] = _read_member(
            _object(members.get(name), f"review queue generation member {name}"),
            manifest_path=manifest_path,
            generation_id=generation_id,
            label=name,
        )
    v1_path, v1_bytes = payloads["v1"]
    v2_path, v2_bytes = payloads["v2"]
    if review_queue_generation_id(v1_bytes, v2_bytes) != generation_id:
        raise ReviewQueueError(
            "review queue generation id does not bind its own member bytes"
        )
    return ReviewQueueGeneration(
        generation_id=generation_id,
        v1_path=v1_path,
        v1_bytes=v1_bytes,
        v2_path=v2_path,
        v2_bytes=v2_bytes,
    )


def _read_member(
    record: dict[str, object], *, manifest_path: Path, generation_id: str, label: str
) -> tuple[Path, bytes]:
    if set(record) != {"path", "sha256", "byte_count"}:
        raise ReviewQueueError(f"review queue generation member {label} fields differ")
    relative = record.get("path")
    digest = record.get("sha256")
    byte_count = record.get("byte_count")
    if (
        not isinstance(relative, str)
        or not relative
        or not isinstance(digest, str)
        or not is_lowercase_sha256(digest)
        or type(byte_count) is not int
        or byte_count < 0
    ):
        raise ReviewQueueError(f"review queue generation member {label} is invalid")
    resolved_member = _resolve_member_path(
        relative, manifest_path=manifest_path, generation_id=generation_id
    )
    try:
        payload = _read_direct_child_no_follow(resolved_member)
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue generation member {label} is unreadable: {exc}"
        ) from exc
    if len(payload) != byte_count or _raw_digest(payload) != digest:
        raise ReviewQueueError(
            f"review queue generation member {label} changed after publication"
        )
    return resolved_member, payload


def _resolve_member_path(
    relative: str, *, manifest_path: Path, generation_id: str
) -> Path:
    """Resolve a manifest-relative member name inside the generation root.

    Members are named relative to the manifest so a published tree can be
    moved or copied whole.  A member that is absolute or escapes the manifest's
    directory is rejected rather than followed: the manifest is the trust
    anchor for the pair, not a redirection mechanism.

    Rejecting a literal ``..`` is not enough on its own, because any component
    of the name can be a symlink that leaves the directory once opened.  So
    containment is decided on the *resolved* target, against a base that is
    resolved the same way -- a published tree reached through a symlinked
    parent stays legal, while a member that leaves the manifest's directory
    does not, whatever its recorded digest says.
    """

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReviewQueueError(
            f"review queue generation member path escapes the manifest: {relative}"
        )
    member_path = manifest_path.parent / candidate
    base = manifest_path.parent.resolve()
    expected_root = (
        base
        / f"{manifest_path.name.removesuffix('-generation.json')}-generations"
        / generation_id
    )
    resolved = member_path.resolve()
    if not resolved.is_relative_to(base):
        raise ReviewQueueError(
            f"review queue generation member path escapes the manifest: {relative}"
        )
    if not resolved.is_relative_to(expected_root) or resolved.parent != expected_root:
        raise ReviewQueueError(
            "review queue generation id does not bind its own member bytes or "
            "immutable generation path: "
            f"{relative}"
        )
    return resolved


def _read_direct_child_no_follow(path: Path) -> bytes:
    """Read one regular file through no-follow handles for every path component."""

    directory_descriptor = _open_directory_path_no_follow(path.parent)
    try:
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | no_follow,
            dir_fd=directory_descriptor,
        )
    finally:
        os.close(directory_descriptor)
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise OSError(
                "review queue generation member must be a regular file with one link"
            )
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        return stream.read()


def _open_directory_path_no_follow(path: Path) -> int:
    """Open every absolute directory component without following symlinks."""

    absolute = path if path.is_absolute() else Path.cwd() / path
    parts = absolute.parts
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open(Path(parts[0]), flags)
    try:
        for part in parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_descriptor
        return current
    except BaseException:
        os.close(current)
        raise


def _member_record(
    member_path: Path, manifest_path: Path, payload: bytes
) -> dict[str, object]:
    return {
        "path": member_path.relative_to(manifest_path.parent).as_posix(),
        "sha256": _raw_digest(payload),
        "byte_count": len(payload),
    }


def _write_immutable_member(path: Path, payload: bytes) -> None:
    """Write one content-addressed member, refusing to change existing bytes."""

    if path.is_symlink():
        raise ReviewQueueError(f"review queue generation member is a symlink: {path}")
    if path.exists():
        try:
            existing = _read_direct_child_no_follow(path)
        except OSError as exc:
            raise ReviewQueueError(
                f"review queue generation member is unreadable: {path}: {exc}"
            ) from exc
        if existing != payload:
            raise ReviewQueueError(
                f"review queue generation member is not immutable: {path}"
            )
        return
    _atomic_write(path, payload)


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write ``payload`` to ``path`` so a crash leaves it whole or absent.

    The directory fsync after the rename is not optional bookkeeping: without
    it the new name is only in the page cache, so a host crash can expose the
    previous file -- or no file at all -- after ``os.replace`` already returned
    and the caller reported the publication committed.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    try:
        _fsync_directory(path.parent)
    except OSError as exc:
        raise _PostCommitFsyncError(path, exc) from exc


def _fsync_directory(path: Path) -> None:
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if directory_flag is None:  # pragma: no cover - POSIX-only durability step
        return
    descriptor = os.open(path, os.O_RDONLY | directory_flag)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReviewQueueError(f"{label} must be an object")
    untyped = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in untyped):
        raise ReviewQueueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _raw_digest(payload: bytes) -> str:
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload, domain=RAW_BYTES_RAW_SHA256_COMMITMENT_V1
        ).digest
    )
