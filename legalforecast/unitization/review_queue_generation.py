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
import secrets
import stat
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
_MEMBER_NAMES_TO_FILES = {"v1": _V1_MEMBER_NAME, "v2": _V2_MEMBER_NAME}


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
    manifest_path = review_queue_generation_manifest_path(queue_path)
    generations_root = review_queue_generation_root(queue_path)
    manifest_parent = manifest_path.parent
    manifest_parent.mkdir(parents=True, exist_ok=True)
    resolved_parent, parent_descriptor = _open_directory_anchor(manifest_parent)
    root_descriptor: int | None = None
    generation_descriptor: int | None = None
    try:
        root_descriptor, root_created = _open_or_create_directory_at(
            parent_descriptor,
            generations_root.name,
            generations_root,
        )
        if root_created:
            _fsync_directory_descriptor(parent_descriptor)
        generation_root = resolved_parent / generations_root.name / generation_id
        generation_descriptor, generation_created = _open_or_create_directory_at(
            root_descriptor, generation_id, generation_root
        )
        if generation_created:
            _fsync_directory_descriptor(root_descriptor)

        v1_member = generation_root / _V1_MEMBER_NAME
        v2_member = generation_root / _V2_MEMBER_NAME
        _write_immutable_member(
            generation_descriptor, _V1_MEMBER_NAME, v1_member, v1_bytes
        )
        _write_immutable_member(
            generation_descriptor, _V2_MEMBER_NAME, v2_member, v2_bytes
        )
        _fsync_directory_descriptor(generation_descriptor)
        _fsync_directory_descriptor(root_descriptor)
        _require_publication_anchors(
            manifest_parent,
            resolved_parent,
            parent_descriptor,
            generations_root.name,
            root_descriptor,
            generation_id,
            generation_descriptor,
        )
        manifest: dict[str, object] = {
            "schema_version": str(UNITIZATION_REVIEW_QUEUE_GENERATION_V1),
            "generation_id": generation_id,
            "members": {
                "v1": _member_record(
                    v1_member, resolved_parent / manifest_path.name, v1_bytes
                ),
                "v2": _member_record(
                    v2_member, resolved_parent / manifest_path.name, v2_bytes
                ),
            },
        }
        try:
            _atomic_write_at(
                parent_descriptor,
                manifest_path.name,
                ARTIFACT_CANONICAL_JSON_V1.encode(manifest),
                resolved_parent / manifest_path.name,
            )
        except _PostCommitFsyncError as exc:
            if exc.path == resolved_parent / manifest_path.name:
                raise ReviewQueueGenerationCommitError(
                    "review queue generation manifest committed, but its directory "
                    f"fsync failed: {exc}"
                ) from exc
            raise
        try:
            _require_publication_anchors(
                manifest_parent,
                resolved_parent,
                parent_descriptor,
                generations_root.name,
                root_descriptor,
                generation_id,
                generation_descriptor,
            )
        except ReviewQueueError as exc:
            raise ReviewQueueGenerationCommitError(
                "review queue generation manifest committed, but its directory "
                f"changed during publication: {exc}"
            ) from exc
        return ReviewQueueGeneration(
            generation_id=generation_id,
            v1_path=v1_member,
            v1_bytes=v1_bytes,
            v2_path=v2_member,
            v2_bytes=v2_bytes,
        )
    except FileNotFoundError as exc:
        raise ReviewQueueError(
            f"review queue generation directory is unavailable: {exc}"
        ) from exc
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue generation publication is unsafe: {exc}"
        ) from exc
    finally:
        if generation_descriptor is not None:
            os.close(generation_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)
        os.close(parent_descriptor)


def read_review_queue_generation(queue_path: Path) -> ReviewQueueGeneration:
    """Resolve both queue members through the manifest and verify their bytes.

    This is the only supported way to read the pair.  Opening the canonical v1
    queue and v2 sidecar directly reintroduces exactly the torn-pair window
    the generation contract exists to close.
    """

    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest_parent = manifest_path.parent
    resolved_parent, parent_descriptor = _open_directory_anchor(manifest_parent)
    root_descriptor: int | None = None
    generation_descriptor: int | None = None
    try:
        root_name = review_queue_generation_root(queue_path).name
        try:
            root_descriptor = _open_directory_at(
                parent_descriptor,
                root_name,
                resolved_parent / root_name,
            )
            raw_manifest = _read_regular_file_at(
                parent_descriptor,
                manifest_path.name,
                resolved_parent / manifest_path.name,
            )
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
        if manifest.get("schema_version") != str(
            UNITIZATION_REVIEW_QUEUE_GENERATION_V1
        ):
            raise ReviewQueueError("review queue generation manifest schema differs")
        generation_id = manifest.get("generation_id")
        if not isinstance(generation_id, str) or not is_lowercase_sha256(generation_id):
            raise ReviewQueueError("review queue generation id is invalid")
        members = _object(manifest.get("members"), "review queue generation members")
        if set(members) != set(_MEMBER_NAMES):
            raise ReviewQueueError("review queue generation members differ")
        member_records: dict[str, dict[str, object]] = {}
        for name in _MEMBER_NAMES:
            record = _object(
                members.get(name), f"review queue generation member {name}"
            )
            relative = record.get("path")
            if not isinstance(relative, str) or not relative:
                raise ReviewQueueError(
                    f"review queue generation member {name} is invalid"
                )
            # Validate the manifest's lexical binding before opening the
            # generation directory.  This keeps a forged generation_id from
            # being reported merely as a missing directory.
            _resolve_member_path(
                relative,
                manifest_path=resolved_parent / manifest_path.name,
                generation_id=generation_id,
            )
            member_records[name] = record
        generation_root = resolved_parent / root_name / generation_id
        try:
            generation_descriptor = _open_directory_at(
                root_descriptor, generation_id, generation_root
            )
        except OSError as exc:
            raise ReviewQueueError(
                f"review queue generation directory is unreadable: {exc}"
            ) from exc
        payloads: dict[str, tuple[Path, bytes]] = {}
        for name in _MEMBER_NAMES:
            payloads[name] = _read_member(
                member_records[name],
                manifest_path=resolved_parent / manifest_path.name,
                generation_id=generation_id,
                generation_descriptor=generation_descriptor,
                label=name,
            )
        _require_reader_anchors(
            manifest_parent,
            resolved_parent,
            parent_descriptor,
            root_name,
            root_descriptor,
            generation_id,
            generation_descriptor,
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
    finally:
        if generation_descriptor is not None:
            os.close(generation_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)
        os.close(parent_descriptor)


def _read_member(
    record: dict[str, object],
    *,
    manifest_path: Path,
    generation_id: str,
    generation_descriptor: int,
    label: str,
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
        member_name = _MEMBER_NAMES_TO_FILES[label]
        if resolved_member.name != member_name:
            raise ReviewQueueError(
                "review queue generation member path does not name its declared member"
            )
        metadata = os.stat(
            member_name, dir_fd=generation_descriptor, follow_symlinks=False
        )
        if stat.S_ISLNK(metadata.st_mode):
            raise ReviewQueueError(
                f"review queue generation member {label} path escapes the manifest "
                "through a symlink"
            )
        payload = _read_regular_file_at(
            generation_descriptor, member_name, resolved_member
        )
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

    The returned path is only a display/identity path.  The actual read is
    relative to an already-open generation directory descriptor, so a later
    rename or symlink swap cannot redirect it.
    """

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReviewQueueError(
            f"review queue generation member path escapes the manifest: {relative}"
        )
    base = manifest_path.parent
    expected_root = (
        base
        / f"{manifest_path.name.removesuffix('-generation.json')}-generations"
        / generation_id
    )
    member_path = base / candidate
    if member_path.parent != expected_root:
        raise ReviewQueueError(
            "review queue generation id does not bind its own member bytes or "
            "immutable generation path: "
            f"{relative}"
        )
    return member_path


def _required_open_flags() -> tuple[int, int, int]:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None:
        raise ReviewQueueError(
            "safe review queue generation I/O requires O_NOFOLLOW and O_DIRECTORY"
        )
    return no_follow, directory, getattr(os, "O_CLOEXEC", 0)


def _open_directory_path_no_follow(path: Path) -> int:
    """Open every component of an already-resolved absolute directory path."""

    no_follow, directory, cloexec = _required_open_flags()
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    flags = os.O_RDONLY | directory | no_follow | cloexec
    current = os.open(parts[0], flags)
    try:
        for part in parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_descriptor
        return current
    except BaseException:
        os.close(current)
        raise


def _open_directory_anchor(path: Path) -> tuple[Path, int]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue directory is unavailable: {path}"
        ) from exc
    try:
        descriptor = _open_directory_path_no_follow(resolved)
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue directory is unsafe: {path}: {exc}"
        ) from exc
    return resolved, descriptor


def _open_directory_at(parent_descriptor: int, name: str, path: Path) -> int:
    _, directory, cloexec = _required_open_flags()
    try:
        return os.open(
            name,
            os.O_RDONLY | directory | os.O_NOFOLLOW | cloexec,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue directory is unsafe: {path}: {exc}"
        ) from exc


def _open_or_create_directory_at(
    parent_descriptor: int, name: str, path: Path
) -> tuple[int, bool]:
    _, directory, cloexec = _required_open_flags()
    created = False
    try:
        os.mkdir(name, 0o755, dir_fd=parent_descriptor)
        created = True
    except FileExistsError:
        pass
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | directory | os.O_NOFOLLOW | cloexec,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue directory is unsafe: {path}: {exc}"
        ) from exc
    return descriptor, created


def _read_regular_file_at(directory_descriptor: int, name: str, path: Path) -> bytes:
    no_follow, _, cloexec = _required_open_flags()
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NONBLOCK | no_follow | cloexec,
        dir_fd=directory_descriptor,
    )
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


def _directory_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _require_directory_entry(
    parent_descriptor: int, name: str, descriptor: int, label: str
) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue generation tree changed: {label}"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode) or _directory_identity(descriptor) != (
        metadata.st_dev,
        metadata.st_ino,
    ):
        raise ReviewQueueError(f"review queue generation tree changed: {label}")


def _require_parent_anchor(path: Path, resolved: Path, descriptor: int) -> None:
    try:
        if path.resolve(strict=True) != resolved:
            raise ReviewQueueError("review queue generation tree changed: parent alias")
        current = _open_directory_path_no_follow(resolved)
    except (OSError, ReviewQueueError) as exc:
        if isinstance(exc, ReviewQueueError):
            raise
        raise ReviewQueueError("review queue generation tree changed: parent") from exc
    try:
        if _directory_identity(current) != _directory_identity(descriptor):
            raise ReviewQueueError("review queue generation tree changed: parent")
    finally:
        os.close(current)


def _require_publication_anchors(
    manifest_parent: Path,
    resolved_parent: Path,
    parent_descriptor: int,
    root_name: str,
    root_descriptor: int,
    generation_id: str,
    generation_descriptor: int,
) -> None:
    _require_parent_anchor(manifest_parent, resolved_parent, parent_descriptor)
    _require_directory_entry(parent_descriptor, root_name, root_descriptor, "root")
    _require_directory_entry(
        root_descriptor, generation_id, generation_descriptor, "generation"
    )


def _require_reader_anchors(
    manifest_parent: Path,
    resolved_parent: Path,
    parent_descriptor: int,
    root_name: str,
    root_descriptor: int,
    generation_id: str,
    generation_descriptor: int,
) -> None:
    _require_publication_anchors(
        manifest_parent,
        resolved_parent,
        parent_descriptor,
        root_name,
        root_descriptor,
        generation_id,
        generation_descriptor,
    )


def _member_record(
    member_path: Path, manifest_path: Path, payload: bytes
) -> dict[str, object]:
    return {
        "path": member_path.relative_to(manifest_path.parent).as_posix(),
        "sha256": _raw_digest(payload),
        "byte_count": len(payload),
    }


def _write_immutable_member(
    directory_descriptor: int, name: str, path: Path, payload: bytes
) -> None:
    """Write one content-addressed member, refusing to change existing bytes."""

    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        metadata = None
    if metadata is not None:
        if stat.S_ISLNK(metadata.st_mode):
            raise ReviewQueueError(
                f"review queue generation member is a symlink: {path}"
            )
        try:
            existing = _read_regular_file_at(directory_descriptor, name, path)
        except OSError as exc:
            raise ReviewQueueError(
                f"review queue generation member is unreadable: {path}: {exc}"
            ) from exc
        if existing != payload:
            raise ReviewQueueError(
                f"review queue generation member is not immutable: {path}"
            )
        return
    _atomic_write_at(directory_descriptor, name, payload, path)


def _atomic_write_at(
    directory_descriptor: int,
    name: str,
    payload: bytes,
    path: Path,
    *,
    mode: int = 0o600,
) -> None:
    """Write bytes relative to an anchored directory and persist the rename.

    The directory fsync after the rename is not optional bookkeeping: without
    it the new name is only in the page cache, so a host crash can expose the
    previous file -- or no file at all -- after ``os.replace`` already returned
    and the caller reported the publication committed.
    """

    no_follow, _, cloexec = _required_open_flags()
    temporary_name = ""
    descriptor = -1
    for _ in range(32):
        candidate = f".{name}.{secrets.token_hex(12)}.tmp"
        try:
            descriptor = os.open(
                candidate,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow | cloexec,
                mode,
                dir_fd=directory_descriptor,
            )
        except FileExistsError:
            continue
        temporary_name = candidate
        break
    if descriptor < 0:
        raise OSError(f"could not allocate a temporary file for {path}")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(
            temporary_name,
            name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
    except BaseException:
        try:
            os.unlink(temporary_name, dir_fd=directory_descriptor)
        except FileNotFoundError:
            pass
        raise
    try:
        _fsync_directory_descriptor(directory_descriptor)
    except OSError as exc:
        raise _PostCommitFsyncError(path, exc) from exc


def write_review_queue_file_durably(path: Path, payload: bytes) -> None:
    """Atomically replace one canonical queue file and persist its directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent, descriptor = _open_directory_anchor(path.parent)
    try:
        _require_parent_anchor(path.parent, resolved_parent, descriptor)
        _atomic_write_at(
            descriptor,
            path.name,
            payload,
            resolved_parent / path.name,
            mode=0o666,
        )
        _require_parent_anchor(path.parent, resolved_parent, descriptor)
    finally:
        os.close(descriptor)


def remove_review_queue_file_durably(path: Path) -> None:
    """Remove one canonical queue file and persist the directory entry."""

    if not path.parent.exists():
        return
    resolved_parent, descriptor = _open_directory_anchor(path.parent)
    try:
        _require_parent_anchor(path.parent, resolved_parent, descriptor)
        try:
            os.unlink(path.name, dir_fd=descriptor)
        except FileNotFoundError:
            return
        _fsync_directory_descriptor(descriptor)
        _require_parent_anchor(path.parent, resolved_parent, descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory_descriptor(descriptor: int) -> None:
    os.fsync(descriptor)


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
