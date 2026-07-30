"""Deterministic, fail-closed task materialization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask
from legalforecast.multiharness.validation import validate_safe_relative_path

TASK_MATERIALIZATION_SCHEMA_VERSION = (
    "legalforecast.multiharness.task_materialization.v1"
)


class TaskMaterializationError(ValueError):
    """Raised when task bytes cannot be materialized without ambiguity."""


@dataclass(frozen=True, slots=True)
class MaterializationLimits:
    """Resource bounds applied before solver-visible files are copied."""

    max_files: int = 1_000
    max_file_bytes: int = 100 * 1024 * 1024
    max_total_bytes: int = 500 * 1024 * 1024

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_files", self.max_files),
            ("max_file_bytes", self.max_file_bytes),
            ("max_total_bytes", self.max_total_bytes),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class TaskArtifactProjection:
    """Map one canonical task artifact into a solver-visible relative path."""

    artifact_id: str
    destination_path: str

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact_id must be non-empty")
        _decoded_safe_path(self.destination_path, "destination_path")


@dataclass(frozen=True, slots=True)
class TaskMaterializationLayout:
    """Versioned visibility classification and solver workspace layout."""

    layout_id: str
    solver_artifacts: tuple[TaskArtifactProjection, ...]
    evaluator_private_artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*\.v[1-9][0-9]*", self.layout_id) is None:
            raise ValueError(
                "layout_id must be a lowercase identifier ending in a version "
                "such as '.v1'"
            )
        solver_ids = tuple(item.artifact_id for item in self.solver_artifacts)
        _require_unique(solver_ids, "solver artifact IDs")
        _require_unique(
            self.evaluator_private_artifact_ids,
            "evaluator-private artifact IDs",
        )


@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    """One verified source-to-destination mapping."""

    artifact_id: str
    source_path: str
    destination_path: str
    sha256: str
    size_bytes: int

    def to_record(self) -> dict[str, str | int]:
        """Return the canonical mapping record."""

        return {
            "artifact_id": self.artifact_id,
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class TaskMaterializationManifest:
    """Canonical proof that a layout preserved the selected semantic bytes."""

    task_id: str
    task_sha256: str
    layout_id: str
    entries: tuple[MaterializedArtifact, ...]
    evaluator_private_artifact_ids: tuple[str, ...]
    semantic_bytes_sha256: str
    total_size_bytes: int
    manifest_sha256: str

    def to_record(self) -> dict[str, object]:
        """Return a deterministic manifest record."""

        return {
            "schema_version": TASK_MATERIALIZATION_SCHEMA_VERSION,
            "task_id": self.task_id,
            "task_sha256": self.task_sha256,
            "layout_id": self.layout_id,
            "entries": [entry.to_record() for entry in self.entries],
            "evaluator_private_artifact_ids": list(self.evaluator_private_artifact_ids),
            "semantic_bytes_sha256": self.semantic_bytes_sha256,
            "total_size_bytes": self.total_size_bytes,
            "manifest_sha256": self.manifest_sha256,
        }


def materialize_task(
    task: CanonicalTask,
    *,
    source_root: Path,
    destination_root: Path,
    layout: TaskMaterializationLayout,
    limits: MaterializationLimits | None = None,
) -> TaskMaterializationManifest:
    """Copy explicitly solver-visible task bytes into one fresh workspace.

    Every canonical artifact must be classified exactly once as solver-visible
    or evaluator-private. The returned manifest stays outside the solver tree so
    materialization does not add semantic bytes.
    """

    applied_limits = limits or MaterializationLimits()
    artifacts = _artifact_index(task.artifacts)
    projections = _validated_projections(layout, artifacts)
    if len(projections) > applied_limits.max_files:
        raise TaskMaterializationError(
            "solver-visible task exceeds the materialization file-count limit"
        )
    if destination_root.exists() or destination_root.is_symlink():
        raise TaskMaterializationError(
            "materialization destination must be a fresh, absent path"
        )
    _validate_existing_directory_chain(destination_root.parent)

    destination_root.mkdir(mode=0o700)
    destination_root_fd = _open_directory(
        destination_root,
        "materialization destination root",
    )
    destination_root_stat = os.fstat(destination_root_fd)
    entries: list[MaterializedArtifact] = []
    destination_identities: list[tuple[str, os.stat_result, str, int]] = []
    total_size = 0
    try:
        for projection in projections:
            artifact = artifacts[projection.artifact_id]
            source_path = _decoded_safe_path(artifact.path, "artifact source path")
            destination_path = _decoded_safe_path(
                projection.destination_path,
                "artifact destination path",
            )
            source_fd = _open_source_fd(source_root, source_path)
            destination_fd: int | None = None
            try:
                source_size = os.fstat(source_fd).st_size
                if source_size > applied_limits.max_file_bytes:
                    raise TaskMaterializationError(
                        f"artifact {artifact.artifact_id!r} exceeds the per-file "
                        "materialization limit"
                    )
                remaining_total_bytes = applied_limits.max_total_bytes - total_size
                if source_size > remaining_total_bytes:
                    raise TaskMaterializationError(
                        "solver-visible task exceeds the total materialization limit"
                    )
                destination_fd = _open_destination_fd(
                    destination_root_fd,
                    destination_path,
                )
                digest, copied_size = _copy_verified(
                    source_fd,
                    destination_fd,
                    artifact=artifact,
                    max_bytes=min(
                        applied_limits.max_file_bytes,
                        remaining_total_bytes,
                    ),
                )
                destination_identities.append(
                    (
                        destination_path,
                        os.fstat(destination_fd),
                        digest,
                        copied_size,
                    )
                )
            finally:
                os.close(source_fd)
                if destination_fd is not None:
                    os.close(destination_fd)
            total_size += copied_size
            entries.append(
                MaterializedArtifact(
                    artifact_id=artifact.artifact_id,
                    source_path=source_path,
                    destination_path=destination_path,
                    sha256=digest,
                    size_bytes=copied_size,
                )
            )
        if not _path_matches_stat(destination_root, destination_root_stat):
            raise TaskMaterializationError(
                "materialization destination root changed during copying"
            )
        for (
            destination_path,
            expected_stat,
            expected_sha256,
            expected_size,
        ) in destination_identities:
            _verify_destination_identity(
                destination_root_fd,
                destination_path,
                expected_stat,
                expected_sha256,
                expected_size,
            )
    except Exception:
        _remove_owned_destination(destination_root, destination_root_stat)
        raise
    finally:
        os.close(destination_root_fd)

    ordered_entries = tuple(sorted(entries, key=lambda item: item.artifact_id))
    private_ids = tuple(sorted(layout.evaluator_private_artifact_ids))
    semantic_bytes_sha256 = _record_sha256(
        [
            {
                "artifact_id": entry.artifact_id,
                "sha256": entry.sha256,
                "size_bytes": entry.size_bytes,
            }
            for entry in ordered_entries
        ]
    )
    content: dict[str, object] = {
        "schema_version": TASK_MATERIALIZATION_SCHEMA_VERSION,
        "task_id": task.task_id,
        "task_sha256": task.task_sha256,
        "layout_id": layout.layout_id,
        "entries": [entry.to_record() for entry in ordered_entries],
        "evaluator_private_artifact_ids": list(private_ids),
        "semantic_bytes_sha256": semantic_bytes_sha256,
        "total_size_bytes": total_size,
    }
    return TaskMaterializationManifest(
        task_id=task.task_id,
        task_sha256=task.task_sha256,
        layout_id=layout.layout_id,
        entries=ordered_entries,
        evaluator_private_artifact_ids=private_ids,
        semantic_bytes_sha256=semantic_bytes_sha256,
        total_size_bytes=total_size,
        manifest_sha256=_record_sha256(content),
    )


def _artifact_index(
    artifacts: tuple[ArtifactRecord, ...],
) -> dict[str, ArtifactRecord]:
    if not artifacts:
        raise TaskMaterializationError("task has no source artifacts")
    indexed: dict[str, ArtifactRecord] = {}
    source_paths: set[str] = set()
    for artifact in artifacts:
        if artifact.artifact_id in indexed:
            raise TaskMaterializationError(
                f"task contains duplicate artifact ID {artifact.artifact_id!r}"
            )
        source_path = _decoded_safe_path(artifact.path, "artifact source path")
        collision_key = source_path.casefold()
        if collision_key in source_paths:
            raise TaskMaterializationError(
                f"task contains a source path collision at {source_path!r}"
            )
        source_paths.add(collision_key)
        indexed[artifact.artifact_id] = artifact
    return indexed


def _validated_projections(
    layout: TaskMaterializationLayout,
    artifacts: dict[str, ArtifactRecord],
) -> tuple[TaskArtifactProjection, ...]:
    solver_ids = {item.artifact_id for item in layout.solver_artifacts}
    private_ids = set(layout.evaluator_private_artifact_ids)
    overlap = solver_ids & private_ids
    if overlap:
        names = ", ".join(sorted(overlap))
        raise TaskMaterializationError(
            "artifacts classified as both solver-visible and evaluator-private: "
            f"{names}"
        )
    classified_ids = solver_ids | private_ids
    unknown = classified_ids - artifacts.keys()
    if unknown:
        names = ", ".join(sorted(unknown))
        raise TaskMaterializationError(f"layout references unknown artifacts: {names}")
    unclassified = artifacts.keys() - classified_ids
    if unclassified:
        names = ", ".join(sorted(unclassified))
        raise TaskMaterializationError(f"task contains unclassified artifacts: {names}")

    destinations: set[str] = set()
    for projection in layout.solver_artifacts:
        destination = _decoded_safe_path(
            projection.destination_path,
            "artifact destination path",
        )
        collision_key = destination.casefold()
        if collision_key in destinations:
            raise TaskMaterializationError(
                f"layout contains a destination path collision at {destination!r}"
            )
        destinations.add(collision_key)
    return tuple(sorted(layout.solver_artifacts, key=lambda item: item.artifact_id))


def _decoded_safe_path(value: str, field_name: str) -> str:
    decoded = unquote(value)
    if decoded != value:
        try:
            validate_safe_relative_path(decoded, field_name)
        except ValueError as exc:
            raise TaskMaterializationError(
                f"{field_name} is unsafe after percent-decoding"
            ) from exc
        raise TaskMaterializationError(
            f"{field_name} must not contain percent-encoded path bytes"
        )
    try:
        return validate_safe_relative_path(decoded, field_name)
    except ValueError as exc:
        raise TaskMaterializationError(str(exc)) from exc


def _validate_existing_directory_chain(path: Path) -> None:
    for candidate in (path, *path.parents):
        try:
            candidate_stat = candidate.lstat()
        except OSError as exc:
            raise TaskMaterializationError(
                "materialization destination parent must already exist"
            ) from exc
        if stat.S_ISLNK(candidate_stat.st_mode):
            raise TaskMaterializationError(
                "materialization destination parent must not contain a symlink"
            )
        if not stat.S_ISDIR(candidate_stat.st_mode):
            raise TaskMaterializationError(
                "materialization destination parent must be a directory"
            )


def _copy_verified(
    source_fd: int,
    destination_fd: int,
    *,
    artifact: ArtifactRecord,
    max_bytes: int,
) -> tuple[str, int]:
    source_stat = os.fstat(source_fd)
    if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_nlink != 1:
        raise TaskMaterializationError(
            f"task artifact changed type or link count: {artifact.path}"
        )
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with (
            os.fdopen(source_fd, "rb", closefd=False) as source_handle,
            os.fdopen(destination_fd, "wb", closefd=False) as destination_handle,
        ):
            for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                if size_bytes + len(chunk) > max_bytes:
                    raise TaskMaterializationError(
                        f"task artifact exceeds materialization byte limits: "
                        f"{artifact.path}"
                    )
                digest.update(chunk)
                size_bytes += len(chunk)
                destination_handle.write(chunk)
    except OSError as exc:
        raise TaskMaterializationError(
            f"could not materialize task artifact: {artifact.path}"
        ) from exc

    actual_digest = digest.hexdigest()
    expected_digest = artifact.sha256.removeprefix("sha256:")
    if actual_digest != expected_digest:
        raise TaskMaterializationError(f"task artifact hash mismatch: {artifact.path}")
    if artifact.size_bytes is not None and size_bytes != artifact.size_bytes:
        raise TaskMaterializationError(f"task artifact size mismatch: {artifact.path}")
    return actual_digest, size_bytes


def _open_source_fd(source_root: Path, relative_path: str) -> int:
    root_fd = _open_directory(source_root, "materialization source root")
    try:
        return _open_relative_file(
            root_fd,
            relative_path,
            destination=False,
        )
    finally:
        os.close(root_fd)


def _open_destination_fd(root_fd: int, relative_path: str) -> int:
    return _open_relative_file(root_fd, relative_path, destination=True)


def _open_relative_file(
    root_fd: int,
    relative_path: str,
    *,
    destination: bool,
) -> int:
    parts = PurePosixPath(relative_path).parts
    current_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            if destination:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        flags = _destination_file_flags() if destination else _source_file_flags()
        mode = 0o600 if destination else 0
        try:
            file_fd = os.open(parts[-1], flags, mode, dir_fd=current_fd)
        except OSError as exc:
            action = "create destination for" if destination else "open"
            raise TaskMaterializationError(
                f"could not {action} task artifact: {relative_path}"
            ) from exc
        file_stat = os.fstat(file_fd)
        if not stat.S_ISREG(file_stat.st_mode):
            os.close(file_fd)
            raise TaskMaterializationError(
                f"task artifact must be a regular file: {relative_path}"
            )
        if not destination and file_stat.st_nlink != 1:
            os.close(file_fd)
            raise TaskMaterializationError(
                f"task artifact must not be a hard link: {relative_path}"
            )
        return file_fd
    except OSError as exc:
        raise TaskMaterializationError(
            f"task artifact path contains a symlink or non-directory: {relative_path}"
        ) from exc
    finally:
        os.close(current_fd)


def _open_directory(path: Path, field_name: str) -> int:
    try:
        return os.open(path, _directory_flags())
    except OSError as exc:
        raise TaskMaterializationError(
            f"{field_name} must be a real directory"
        ) from exc


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _source_file_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _destination_file_flags() -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _verify_destination_identity(
    root_fd: int,
    relative_path: str,
    expected_stat: os.stat_result,
    expected_sha256: str,
    expected_size: int,
) -> None:
    file_fd = _open_relative_file(root_fd, relative_path, destination=False)
    try:
        if not _same_file(os.fstat(file_fd), expected_stat):
            raise TaskMaterializationError(
                f"materialized destination changed during copying: {relative_path}"
            )
        digest = hashlib.sha256()
        size_bytes = 0
        with os.fdopen(file_fd, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size_bytes += len(chunk)
        if digest.hexdigest() != expected_sha256 or size_bytes != expected_size:
            raise TaskMaterializationError(
                f"materialized destination bytes changed during copying: "
                f"{relative_path}"
            )
    finally:
        os.close(file_fd)


def _path_matches_stat(path: Path, expected_stat: os.stat_result) -> bool:
    try:
        actual_stat = path.lstat()
    except OSError:
        return False
    return _same_file(actual_stat, expected_stat)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _remove_owned_destination(
    destination_root: Path,
    expected_stat: os.stat_result,
) -> None:
    if _path_matches_stat(destination_root, expected_stat):
        shutil.rmtree(destination_root)


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{field_name} must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def _record_sha256(record: object) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
