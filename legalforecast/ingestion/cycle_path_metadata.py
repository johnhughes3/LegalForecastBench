"""Materialize private, machine-local paths for a frozen acquisition cycle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

SCHEMA_VERSION = "legalforecast.cycle_path_metadata.v1"
METADATA_NAME = "cycle-path-metadata.json"
_TARGET_DIRECTORY = "05-target-cohort-v4"
_APPROVAL_DIRECTORY = "purchase-approval"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class CyclePathMetadataError(ValueError):
    """Raised when local cycle paths are ambiguous, unsafe, or inconsistent."""


def materialize_cycle_path_metadata(
    *,
    approval_checkpoint: Path,
    expected_approval_checkpoint_sha256: str,
    parser_root: Path,
    expected_parser_commit: str,
    output: Path,
) -> dict[str, object]:
    """Derive, verify, and immutably publish the v4 cycle's local path map."""

    checkpoint_path = _existing_normalized_path(
        approval_checkpoint,
        "approval checkpoint",
        directory=False,
    )
    parser_path = _existing_normalized_path(
        parser_root,
        "parser root",
        directory=True,
    )
    expected_commit = _commit(expected_parser_commit)
    checkpoint_bytes = _read_unique(checkpoint_path, "approval checkpoint")
    checkpoint_sha256 = _digest(
        expected_approval_checkpoint_sha256,
        "expected approval checkpoint SHA-256",
    )
    if hashlib.sha256(checkpoint_bytes).hexdigest() != checkpoint_sha256:
        raise CyclePathMetadataError("approval checkpoint SHA-256 differs")
    checkpoint = _json_object(checkpoint_bytes, "approval checkpoint")
    target_root = _target_cohort_root(checkpoint)
    if target_root.name != _TARGET_DIRECTORY:
        raise CyclePathMetadataError(
            f"target cohort root must end in {_TARGET_DIRECTORY}"
        )
    target_root = _existing_normalized_path(
        target_root,
        "target cohort root",
        directory=True,
    )

    approval_root = checkpoint_path.parent
    if approval_root.name != _APPROVAL_DIRECTORY:
        raise CyclePathMetadataError(
            f"approval checkpoint must be below {_APPROVAL_DIRECTORY}"
        )
    successor_artifact_root = target_root.parent
    successor_private_root = approval_root.parent
    _validate_root_boundaries(
        target_root=target_root,
        approval_root=approval_root,
        successor_artifact_root=successor_artifact_root,
        successor_private_root=successor_private_root,
    )
    parser_commit = _verify_parser_checkout(parser_path, expected_commit)

    output_path = _normalized_absolute(output, "output")
    expected_output = successor_private_root / METADATA_NAME
    if output_path != expected_output:
        raise CyclePathMetadataError(
            "output must be the canonical private cycle metadata path"
        )

    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "approval_checkpoint": str(checkpoint_path),
        "approval_checkpoint_sha256": checkpoint_sha256,
        "successor_artifact_root": str(successor_artifact_root),
        "successor_private_root": str(successor_private_root),
        "parser_root": str(parser_path),
        "parser_commit": parser_commit,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    payload = canonical_json_bytes(
        record,
        error_type=CyclePathMetadataError,
        error_message="cycle path metadata is not canonical JSON",
    )
    _publish_exact(output_path, payload)
    return record


def _target_cohort_root(checkpoint: Mapping[str, object]) -> Path:
    checkpoint_value = checkpoint.get("checkpoint")
    if not isinstance(checkpoint_value, Mapping):
        raise CyclePathMetadataError("approval checkpoint lacks checkpoint object")
    checkpoint_object = cast(Mapping[str, object], checkpoint_value)
    verification_inputs = checkpoint_object.get("verification_inputs")
    if not isinstance(verification_inputs, Mapping):
        raise CyclePathMetadataError(
            "approval checkpoint lacks verification_inputs object"
        )
    verification_object = cast(Mapping[str, object], verification_inputs)
    target = verification_object.get("target_cohort_root")
    if not isinstance(target, str) or not target:
        raise CyclePathMetadataError(
            "approval checkpoint lacks target_cohort_root path"
        )
    return Path(target)


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CyclePathMetadataError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise CyclePathMetadataError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _normalized_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise CyclePathMetadataError(f"{label} must be an absolute normalized path")
    return path


def _existing_normalized_path(
    path: Path,
    label: str,
    *,
    directory: bool,
) -> Path:
    normalized = _normalized_absolute(path, label)
    try:
        resolved = normalized.resolve(strict=True)
    except OSError as exc:
        raise CyclePathMetadataError(f"{label} does not exist") from exc
    if resolved != normalized:
        raise CyclePathMetadataError(f"{label} must not traverse symlinks")
    if directory and not resolved.is_dir():
        raise CyclePathMetadataError(f"{label} must be a directory")
    if not directory and not resolved.is_file():
        raise CyclePathMetadataError(f"{label} must be a regular file")
    return resolved


def _validate_root_boundaries(
    *,
    target_root: Path,
    approval_root: Path,
    successor_artifact_root: Path,
    successor_private_root: Path,
) -> None:
    roots = {
        target_root,
        approval_root,
        successor_artifact_root,
        successor_private_root,
    }
    if len(roots) != 4:
        raise CyclePathMetadataError("cycle evidence and successor roots must differ")
    if target_root.parent != successor_artifact_root:
        raise CyclePathMetadataError("target cohort root is not below successor root")
    if approval_root.parent != successor_private_root:
        raise CyclePathMetadataError("approval root is not below private cycle root")
    if successor_artifact_root.is_relative_to(successor_private_root) or (
        successor_private_root.is_relative_to(successor_artifact_root)
    ):
        raise CyclePathMetadataError(
            "public and private successor roots must not overlap"
        )


def _commit(value: str) -> str:
    if not _SHA40.fullmatch(value):
        raise CyclePathMetadataError(
            "expected parser commit must be a lowercase 40-character SHA"
        )
    return value


def _digest(value: str, label: str) -> str:
    if not _SHA256.fullmatch(value):
        raise CyclePathMetadataError(f"{label} must be a lowercase 64-character digest")
    return value


def _verify_parser_checkout(parser_root: Path, expected_commit: str) -> str:
    top_level = _git(parser_root, "rev-parse", "--show-toplevel")
    if Path(top_level) != parser_root:
        raise CyclePathMetadataError("parser root must be the Git checkout root")
    head = _git(parser_root, "rev-parse", "HEAD")
    if head != expected_commit:
        raise CyclePathMetadataError("parser HEAD differs from expected commit")
    if _git(parser_root, "status", "--porcelain", "--untracked-files=normal"):
        raise CyclePathMetadataError("parser checkout must be clean")
    return head


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CyclePathMetadataError("parser root is not a valid Git checkout") from exc
    return completed.stdout.strip()


def _read_unique(path: Path, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CyclePathMetadataError(f"{label} must be a unique regular file") from exc


def _publish_exact(output: Path, payload: bytes) -> None:
    parent = output.parent
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise CyclePathMetadataError("safe metadata publication requires O_NOFOLLOW")
    parent_fd = -1
    stage_name = f".{output.name}.{hashlib.sha256(payload).hexdigest()}.partial"
    stage_fd = -1
    try:
        if parent.resolve(strict=True) != parent:
            raise CyclePathMetadataError(
                "metadata output directory must not use symlinks"
            )
        parent_fd = os.open(
            parent,
            os.O_RDONLY | os.O_CLOEXEC | nofollow | directory,
        )
        try:
            stage_fd = os.open(
                stage_name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | nofollow,
                0o600,
                dir_fd=parent_fd,
            )
            fcntl.flock(stage_fd, fcntl.LOCK_EX)
            _write_all(stage_fd, payload)
            os.fsync(stage_fd)
        except FileExistsError:
            stage_fd = os.open(
                stage_name,
                os.O_RDWR | os.O_CLOEXEC | nofollow,
                dir_fd=parent_fd,
            )
            fcntl.flock(stage_fd, fcntl.LOCK_EX)
            stage_metadata = _require_recoverable_stage(
                stage_fd,
                stage_name,
                expected_size=len(payload),
                directory_fd=parent_fd,
                output_name=output.name,
                allow_incomplete_single_link=True,
            )
            if stage_metadata.st_size < len(payload):
                os.ftruncate(stage_fd, 0)
                _write_all(stage_fd, payload)
                os.fsync(stage_fd)
                stage_metadata = _require_recoverable_stage(
                    stage_fd,
                    stage_name,
                    expected_size=len(payload),
                    directory_fd=parent_fd,
                    output_name=output.name,
                )
            if _read_fd(stage_fd, stage_name) != payload:
                raise CyclePathMetadataError(
                    "existing metadata staging file differs"
                ) from None
            os.fsync(stage_fd)
        else:
            stage_metadata = _require_recoverable_stage(
                stage_fd,
                stage_name,
                expected_size=len(payload),
                directory_fd=parent_fd,
                output_name=output.name,
            )
        try:
            os.link(
                stage_name,
                output.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except (FileExistsError, FileNotFoundError):
            if _read_at(parent_fd, output.name, linked_to=stage_metadata) != payload:
                raise CyclePathMetadataError(
                    "cycle path metadata already exists with different content"
                ) from None
        else:
            if _read_at(parent_fd, output.name, linked_to=stage_metadata) != payload:
                raise CyclePathMetadataError("published cycle path metadata differs")
        _unlink_if_same_inode(parent_fd, stage_name, stage_metadata)
        os.fsync(parent_fd)
        if _read_at(parent_fd, output.name) != payload:
            raise CyclePathMetadataError("published cycle path metadata differs")
    except OSError as exc:
        raise CyclePathMetadataError(str(exc)) from exc
    finally:
        if stage_fd >= 0:
            os.close(stage_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise CyclePathMetadataError("metadata staging write made no progress")
        offset += written


def _read_at(
    directory_fd: int,
    name: str,
    *,
    linked_to: os.stat_result | None = None,
) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=directory_fd,
    )
    try:
        metadata = os.fstat(descriptor)
        recoverable_link = (
            linked_to is not None
            and metadata.st_nlink == 2
            and _same_inode(metadata, linked_to)
        )
        if not stat.S_ISREG(metadata.st_mode) or (
            metadata.st_nlink != 1 and not recoverable_link
        ):
            raise CyclePathMetadataError(
                "cycle path metadata must be a unique regular file"
            )
        return _read_fd(descriptor, name)
    finally:
        os.close(descriptor)


def _read_fd(descriptor: int, label: str) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    before = os.fstat(descriptor)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    after = os.fstat(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise CyclePathMetadataError(f"{label} changed while reading")
    payload = b"".join(chunks)
    if len(payload) != after.st_size:
        raise CyclePathMetadataError(f"{label} changed while reading")
    return payload


def _require_recoverable_stage(
    descriptor: int,
    label: str,
    *,
    expected_size: int,
    directory_fd: int,
    output_name: str,
    allow_incomplete_single_link: bool = False,
) -> os.stat_result:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise CyclePathMetadataError(f"{label} must be a recoverable regular file")
    if metadata.st_nlink == 1:
        if metadata.st_size == expected_size or (
            allow_incomplete_single_link and metadata.st_size < expected_size
        ):
            return metadata
        raise CyclePathMetadataError(f"{label} must be a recoverable regular file")
    if metadata.st_size != expected_size:
        raise CyclePathMetadataError(f"{label} must be a recoverable regular file")
    if metadata.st_nlink == 2:
        try:
            output_metadata = os.stat(
                output_name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            if _same_inode(metadata, output_metadata):
                return metadata
    raise CyclePathMetadataError(f"{label} must be a recoverable regular file")


def _unlink_if_same_inode(
    directory_fd: int,
    name: str,
    expected: os.stat_result,
) -> None:
    try:
        current = os.stat(
            name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    if not _same_inode(current, expected):
        return
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        # A concurrent publisher may remove the same verified staging link.
        pass


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


__all__ = [
    "METADATA_NAME",
    "SCHEMA_VERSION",
    "CyclePathMetadataError",
    "materialize_cycle_path_metadata",
]
