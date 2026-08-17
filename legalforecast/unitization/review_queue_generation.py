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

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast.unitization.review_queue import ReviewQueueError

GENERATION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.unitization_review_queue_generation.v1"
)

_V1_MEMBER_NAME = "unitization-review-queue.jsonl"
_V2_MEMBER_NAME = "unitization-review-queue-v2.jsonl"
_MEMBER_NAMES = ("v1", "v2")


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

    return _sha256_hex(
        _canonical_json_bytes(
            {
                "schema_version": GENERATION_MANIFEST_SCHEMA_VERSION,
                "v1_sha256": _sha256_hex(v1_bytes),
                "v2_sha256": _sha256_hex(v2_bytes),
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
    """

    generation_id = review_queue_generation_id(v1_bytes, v2_bytes)
    generation_root = review_queue_generation_root(queue_path) / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    v1_member = generation_root / _V1_MEMBER_NAME
    v2_member = generation_root / _V2_MEMBER_NAME
    _write_immutable_member(v1_member, v1_bytes)
    _write_immutable_member(v2_member, v2_bytes)
    _fsync_directory(generation_root)
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest: dict[str, object] = {
        "schema_version": GENERATION_MANIFEST_SCHEMA_VERSION,
        "generation_id": generation_id,
        "members": {
            "v1": _member_record(v1_member, manifest_path, v1_bytes),
            "v2": _member_record(v2_member, manifest_path, v2_bytes),
        },
    }
    _atomic_write(manifest_path, _canonical_json_bytes(manifest))
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
        raw_manifest = manifest_path.read_bytes()
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
    if manifest.get("schema_version") != GENERATION_MANIFEST_SCHEMA_VERSION:
        raise ReviewQueueError("review queue generation manifest schema differs")
    generation_id = manifest.get("generation_id")
    if not isinstance(generation_id, str) or not _is_sha256_hex(generation_id):
        raise ReviewQueueError("review queue generation id is invalid")
    members = _object(manifest.get("members"), "review queue generation members")
    if set(members) != set(_MEMBER_NAMES):
        raise ReviewQueueError("review queue generation members differ")
    payloads: dict[str, tuple[Path, bytes]] = {}
    for name in _MEMBER_NAMES:
        payloads[name] = _read_member(
            _object(members.get(name), f"review queue generation member {name}"),
            manifest_path=manifest_path,
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
    record: dict[str, object], *, manifest_path: Path, label: str
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
        or not _is_sha256_hex(digest)
        or type(byte_count) is not int
        or byte_count < 0
    ):
        raise ReviewQueueError(f"review queue generation member {label} is invalid")
    member_path = _resolve_member_path(relative, manifest_path=manifest_path)
    try:
        payload = member_path.read_bytes()
    except OSError as exc:
        raise ReviewQueueError(
            f"review queue generation member {label} is unreadable: {exc}"
        ) from exc
    if len(payload) != byte_count or _sha256_hex(payload) != digest:
        raise ReviewQueueError(
            f"review queue generation member {label} changed after publication"
        )
    return member_path, payload


def _resolve_member_path(relative: str, *, manifest_path: Path) -> Path:
    """Resolve a manifest-relative member name inside the generation root.

    Members are named relative to the manifest so a published tree can be
    moved or copied whole.  A member that is absolute or escapes the manifest's
    directory is rejected rather than followed: the manifest is the trust
    anchor for the pair, not a redirection mechanism.
    """

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReviewQueueError(
            f"review queue generation member path escapes the manifest: {relative}"
        )
    return manifest_path.parent / candidate


def _member_record(
    member_path: Path, manifest_path: Path, payload: bytes
) -> dict[str, object]:
    return {
        "path": member_path.relative_to(manifest_path.parent).as_posix(),
        "sha256": _sha256_hex(payload),
        "byte_count": len(payload),
    }


def _write_immutable_member(path: Path, payload: bytes) -> None:
    """Write one content-addressed member, refusing to change existing bytes."""

    if path.exists():
        if path.read_bytes() != payload:
            raise ReviewQueueError(
                f"review queue generation member is not immutable: {path}"
            )
        return
    _atomic_write(path, payload)


def _atomic_write(path: Path, payload: bytes) -> None:
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


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
