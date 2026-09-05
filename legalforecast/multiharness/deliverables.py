"""Canonical, layout-independent sealed deliverable artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Self, cast
from urllib.parse import unquote

from legalforecast.multiharness.material_separation import (
    DELIVERABLE_TREE_COMMITMENT_SCHEMA_VERSION,
)
from legalforecast.multiharness.materialization import (
    MaterializationLimits,
    TaskArtifactProjection,
    TaskMaterializationError,
    TaskMaterializationLayout,
    materialize_task,
)
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask
from legalforecast.multiharness.validation import (
    require_schema_version,
    validate_safe_relative_path,
    validate_sha256,
)

DELIVERABLE_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.deliverable_manifest.v1"
)

_MEDIA_TYPE_RE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z")
_MANIFEST_FIELDS = {
    "schema_version",
    "task_sha256",
    "run_sha256",
    "config_sha256",
    "artifacts",
    "total_size_bytes",
    "max_files",
    "max_total_size_bytes",
    "tree_sha256",
    "manifest_sha256",
}
_ARTIFACT_FIELDS = {
    "artifact_id",
    "path",
    "media_type",
    "sha256",
    "size_bytes",
    "max_size_bytes",
}


class DeliverableValidationError(ValueError):
    """A deliverable could not be normalized or did not match its manifest."""


@dataclass(frozen=True, slots=True)
class DeliverableLimits:
    """Host-owned aggregate limits for one sealed deliverable."""

    max_files: int = 100
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
class _DiscoveredFile:
    path: str
    file_stat: os.stat_result


@dataclass(frozen=True, slots=True)
class _TreeSnapshot:
    files: Mapping[str, tuple[str, int]]
    total_size_bytes: int
    tree_sha256: str


@dataclass(frozen=True, slots=True)
class DeliverableArtifactProjection:
    """Map one harness-specific output path into the canonical deliverable tree."""

    artifact_id: str
    source_path: str
    path: str
    media_type: str
    max_size_bytes: int

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        _decoded_safe_path(self.source_path, "source_path")
        _decoded_safe_path(self.path, "path")
        _validate_media_type(self.media_type)
        if type(self.max_size_bytes) is not int or self.max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be a positive integer")


@dataclass(frozen=True, slots=True)
class SealedDeliverableArtifact:
    """One canonical deliverable file and its allowed media/byte bounds."""

    artifact_id: str
    path: str
    media_type: str
    sha256: str
    size_bytes: int
    max_size_bytes: int

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        _decoded_safe_path(self.path, "path")
        _validate_media_type(self.media_type)
        if self.media_type != self.media_type.lower():
            raise ValueError("media_type must be lowercase")
        _require_canonical_sha256(self.sha256, "sha256")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if type(self.max_size_bytes) is not int or self.max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be a positive integer")
        if self.size_bytes > self.max_size_bytes:
            raise ValueError("artifact size exceeds max_size_bytes")

    def to_record(self) -> dict[str, str | int]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "max_size_bytes": self.max_size_bytes,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _ARTIFACT_FIELDS, "deliverable artifact")
        return cls(
            artifact_id=_required_string(record, "artifact_id"),
            path=_required_string(record, "path"),
            media_type=_required_string(record, "media_type"),
            sha256=_required_string(record, "sha256"),
            size_bytes=_required_non_negative_int(record, "size_bytes"),
            max_size_bytes=_required_positive_int(record, "max_size_bytes"),
        )


@dataclass(frozen=True, slots=True)
class DeliverableManifest:
    """Canonical commitment to a complete sealed deliverable tree."""

    task_sha256: str
    run_sha256: str
    config_sha256: str
    artifacts: tuple[SealedDeliverableArtifact, ...]
    total_size_bytes: int
    max_files: int
    max_total_size_bytes: int
    tree_sha256: str
    manifest_sha256: str
    schema_version: str = DELIVERABLE_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DELIVERABLE_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DELIVERABLE_MANIFEST_SCHEMA_VERSION!r}"
            )
        for field_name in (
            "task_sha256",
            "run_sha256",
            "config_sha256",
            "tree_sha256",
            "manifest_sha256",
        ):
            _require_canonical_sha256(getattr(self, field_name), field_name)
        if not self.artifacts:
            raise ValueError("deliverable manifest requires at least one artifact")
        _require_unique(
            tuple(artifact.artifact_id for artifact in self.artifacts),
            "artifact IDs",
        )
        _require_casefold_unique(
            tuple(artifact.path for artifact in self.artifacts),
            "artifact paths",
        )
        _require_no_path_prefix_collisions(
            tuple(artifact.path for artifact in self.artifacts)
        )
        if tuple(sorted(self.artifacts, key=lambda item: item.artifact_id)) != (
            self.artifacts
        ):
            raise ValueError("deliverable artifacts must be ordered by artifact_id")
        if type(self.total_size_bytes) is not int or self.total_size_bytes < 0:
            raise ValueError("total_size_bytes must be a non-negative integer")
        if type(self.max_files) is not int or self.max_files <= 0:
            raise ValueError("max_files must be a positive integer")
        if len(self.artifacts) > self.max_files:
            raise ValueError("deliverable artifact count exceeds max_files")
        if type(self.max_total_size_bytes) is not int or self.max_total_size_bytes <= 0:
            raise ValueError("max_total_size_bytes must be a positive integer")
        if self.total_size_bytes != sum(
            artifact.size_bytes for artifact in self.artifacts
        ):
            raise ValueError("total_size_bytes does not match artifacts")
        if self.total_size_bytes > self.max_total_size_bytes:
            raise ValueError("deliverable size exceeds max_total_size_bytes")
        if self.manifest_sha256 != _record_sha256(self._content_record()):
            raise ValueError("manifest_sha256 does not match manifest content")

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_sha256": self.task_sha256,
            "run_sha256": self.run_sha256,
            "config_sha256": self.config_sha256,
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "total_size_bytes": self.total_size_bytes,
            "max_files": self.max_files,
            "max_total_size_bytes": self.max_total_size_bytes,
            "tree_sha256": self.tree_sha256,
        }

    def to_record(self) -> dict[str, object]:
        return {
            **self._content_record(),
            "manifest_sha256": self.manifest_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _MANIFEST_FIELDS, "deliverable manifest")
        require_schema_version(record, DELIVERABLE_MANIFEST_SCHEMA_VERSION)
        raw_artifacts = record.get("artifacts")
        if not isinstance(raw_artifacts, Sequence) or isinstance(
            raw_artifacts, str | bytes
        ):
            raise ValueError("artifacts must be an array")
        artifacts = tuple(
            SealedDeliverableArtifact.from_record(
                _required_mapping(item, f"artifacts[{index}]")
            )
            for index, item in enumerate(cast(Sequence[object], raw_artifacts))
        )
        return cls(
            schema_version=_required_string(record, "schema_version"),
            task_sha256=_required_string(record, "task_sha256"),
            run_sha256=_required_string(record, "run_sha256"),
            config_sha256=_required_string(record, "config_sha256"),
            artifacts=artifacts,
            total_size_bytes=_required_non_negative_int(
                record,
                "total_size_bytes",
            ),
            max_files=_required_positive_int(record, "max_files"),
            max_total_size_bytes=_required_positive_int(
                record,
                "max_total_size_bytes",
            ),
            tree_sha256=_required_string(record, "tree_sha256"),
            manifest_sha256=_required_string(record, "manifest_sha256"),
        )


def seal_deliverable(
    *,
    source_root: Path,
    sealed_root: Path,
    task_sha256: str,
    run_sha256: str,
    config_sha256: str,
    artifacts: Sequence[DeliverableArtifactProjection],
    limits: DeliverableLimits | None = None,
) -> DeliverableManifest:
    """Normalize declared producer outputs into one fresh read-only tree.

    ``source_root``, ``sealed_root.parent``, and the fresh ``sealed_root`` require
    exclusive coordination from other same-UID processes for the duration of
    this call. The function reads contributor files as opaque bytes; it never
    imports, parses, renders, or executes them. A failure may leave a partial
    fresh root for the coordinated caller to remove.
    """

    canonical_task_sha256 = _canonical_sha256(task_sha256, "task_sha256")
    canonical_run_sha256 = _canonical_sha256(run_sha256, "run_sha256")
    canonical_config_sha256 = _canonical_sha256(config_sha256, "config_sha256")
    applied_limits = limits or DeliverableLimits()
    declared = tuple(artifacts)
    _validate_projections(declared, applied_limits)
    normalized_source = _existing_real_directory(source_root, "source_root")
    normalized_sealed = _fresh_child_path(sealed_root)
    _require_disjoint_roots(normalized_source, normalized_sealed)
    source_bounds = {
        projection.source_path: min(
            projection.max_size_bytes,
            applied_limits.max_file_bytes,
        )
        for projection in declared
    }
    source_snapshot = _bounded_tree_snapshot(
        normalized_source,
        file_bounds=source_bounds,
        max_files=applied_limits.max_files,
        max_total_bytes=applied_limits.max_total_bytes,
        field_name="deliverable source",
        require_read_only=False,
    )

    source_records: list[ArtifactRecord] = []
    sizes: dict[str, int] = {}
    for projection in declared:
        digest, size_bytes = source_snapshot.files[projection.source_path]
        sizes[projection.artifact_id] = size_bytes
        source_records.append(
            ArtifactRecord(
                artifact_id=projection.artifact_id,
                path=projection.source_path,
                sha256=digest,
                media_type=projection.media_type.lower(),
                size_bytes=size_bytes,
            )
        )

    task = CanonicalTask(
        task_id="canonical-deliverable",
        source_id="canonical-deliverable",
        family="contract_only",
        suite_version="v1",
        scoring_mode="contract_only",
        task_sha256=canonical_task_sha256,
        artifacts=tuple(source_records),
    )
    projections_by_id = {projection.artifact_id: projection for projection in declared}
    try:
        materialized = materialize_task(
            task,
            source_root=normalized_source,
            destination_root=normalized_sealed,
            layout=TaskMaterializationLayout(
                layout_id="canonical-deliverable.v1",
                solver_artifacts=tuple(
                    TaskArtifactProjection(
                        artifact_id=projection.artifact_id,
                        destination_path=projection.path,
                    )
                    for projection in declared
                ),
            ),
            limits=MaterializationLimits(
                max_files=applied_limits.max_files,
                max_file_bytes=applied_limits.max_file_bytes,
                max_total_bytes=applied_limits.max_total_bytes,
            ),
        )
    except TaskMaterializationError as exc:
        raise DeliverableValidationError(str(exc)) from exc

    sealed_artifacts = tuple(
        SealedDeliverableArtifact(
            artifact_id=entry.artifact_id,
            path=entry.destination_path,
            media_type=projections_by_id[entry.artifact_id].media_type.lower(),
            sha256=_canonical_sha256(entry.sha256, "artifact sha256"),
            size_bytes=sizes[entry.artifact_id],
            max_size_bytes=min(
                projections_by_id[entry.artifact_id].max_size_bytes,
                applied_limits.max_file_bytes,
            ),
        )
        for entry in materialized.entries
    )
    canonical_bounds = {
        artifact.path: artifact.max_size_bytes for artifact in sealed_artifacts
    }
    unsealed_snapshot = _bounded_tree_snapshot(
        normalized_sealed,
        file_bounds=canonical_bounds,
        max_files=applied_limits.max_files,
        max_total_bytes=applied_limits.max_total_bytes,
        field_name="unsealed deliverable",
        require_read_only=False,
    )
    for artifact in sealed_artifacts:
        actual_sha256, actual_size = unsealed_snapshot.files[artifact.path]
        if actual_sha256 != artifact.sha256 or actual_size != artifact.size_bytes:
            raise DeliverableValidationError(
                f"deliverable changed before sealing: {artifact.path}"
            )
    _seal_read_only(normalized_sealed, tuple(canonical_bounds))
    sealed_snapshot = _bounded_tree_snapshot(
        normalized_sealed,
        file_bounds=canonical_bounds,
        max_files=applied_limits.max_files,
        max_total_bytes=applied_limits.max_total_bytes,
        field_name="sealed deliverable",
        require_read_only=True,
    )
    for artifact in sealed_artifacts:
        actual_sha256, actual_size = sealed_snapshot.files[artifact.path]
        if actual_sha256 != artifact.sha256 or actual_size != artifact.size_bytes:
            raise DeliverableValidationError(
                f"sealed deliverable changed during sealing: {artifact.path}"
            )
    content = {
        "schema_version": DELIVERABLE_MANIFEST_SCHEMA_VERSION,
        "task_sha256": canonical_task_sha256,
        "run_sha256": canonical_run_sha256,
        "config_sha256": canonical_config_sha256,
        "artifacts": [artifact.to_record() for artifact in sealed_artifacts],
        "total_size_bytes": sealed_snapshot.total_size_bytes,
        "max_files": applied_limits.max_files,
        "max_total_size_bytes": applied_limits.max_total_bytes,
        "tree_sha256": sealed_snapshot.tree_sha256,
    }
    return DeliverableManifest(
        task_sha256=canonical_task_sha256,
        run_sha256=canonical_run_sha256,
        config_sha256=canonical_config_sha256,
        artifacts=sealed_artifacts,
        total_size_bytes=sealed_snapshot.total_size_bytes,
        max_files=applied_limits.max_files,
        max_total_size_bytes=applied_limits.max_total_bytes,
        tree_sha256=sealed_snapshot.tree_sha256,
        manifest_sha256=_record_sha256(content),
    )


def validate_sealed_deliverable(
    sealed_root: Path,
    manifest: DeliverableManifest,
) -> DeliverableManifest:
    """Revalidate a complete read-only tree against its canonical manifest.

    Contributor files are streamed as opaque bytes only. The caller must hold
    exclusive same-UID coordination from validation until the root is mounted.
    """

    # Reconstructing catches forged dataclass instances created without __init__.
    canonical_manifest = DeliverableManifest.from_record(manifest.to_record())
    normalized_root = _existing_real_directory(sealed_root, "sealed_root")
    snapshot = _bounded_tree_snapshot(
        normalized_root,
        file_bounds={
            artifact.path: artifact.max_size_bytes
            for artifact in canonical_manifest.artifacts
        },
        max_files=canonical_manifest.max_files,
        max_total_bytes=canonical_manifest.max_total_size_bytes,
        field_name="sealed deliverable",
        require_read_only=True,
    )
    if snapshot.tree_sha256 != canonical_manifest.tree_sha256:
        raise DeliverableValidationError(
            "sealed deliverable tree does not match its manifest"
        )

    for artifact in canonical_manifest.artifacts:
        digest, size_bytes = snapshot.files[artifact.path]
        if digest != artifact.sha256:
            raise DeliverableValidationError(
                f"sealed deliverable hash mismatch: {artifact.path}"
            )
        if size_bytes != artifact.size_bytes:
            raise DeliverableValidationError(
                f"sealed deliverable size mismatch: {artifact.path}"
            )
    if snapshot.total_size_bytes != canonical_manifest.total_size_bytes:
        raise DeliverableValidationError(
            "sealed deliverable total size does not match its manifest"
        )
    return canonical_manifest


# contract-ratchet: allow recomputation of the existing deliverable tree commitment
def single_artifact_tree_sha256(artifact_path: str, payload: bytes) -> str:
    if not artifact_path or artifact_path != PurePosixPath(artifact_path).name:
        raise DeliverableValidationError(
            "single-artifact tree path must be a bare filename"
        )
    return artifact_tree_sha256({artifact_path: payload})


# contract-ratchet: allow recomputation of the existing deliverable tree commitment
def artifact_tree_sha256(artifacts: Mapping[str, bytes]) -> str:
    if not artifacts:
        raise DeliverableValidationError("artifact tree requires at least one file")
    entries_by_path: dict[str, dict[str, object]] = {}
    for artifact_path, payload in artifacts.items():
        safe_path = _decoded_safe_path(artifact_path, "artifact_path")
        if type(payload) is not bytes:
            raise DeliverableValidationError("artifact payload must be bytes")
        path = PurePosixPath(safe_path)
        for parent in reversed(path.parents[:-1]):
            name = parent.as_posix()
            entries_by_path.setdefault(name, {"path": name, "type": "directory"})
        entries_by_path[safe_path] = {
            "path": safe_path,
            "type": "file",
            "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    return _record_sha256(
        {
            "schema_version": DELIVERABLE_TREE_COMMITMENT_SCHEMA_VERSION,
            "entries": [entries_by_path[path] for path in sorted(entries_by_path)],
        }
    )


def _validate_projections(
    artifacts: tuple[DeliverableArtifactProjection, ...],
    limits: DeliverableLimits,
) -> None:
    if not artifacts:
        raise ValueError("deliverable requires at least one artifact")
    if len(artifacts) > limits.max_files:
        raise DeliverableValidationError("deliverable exceeds the file-count limit")
    _require_unique(
        tuple(artifact.artifact_id for artifact in artifacts),
        "artifact IDs",
    )
    _require_casefold_unique(
        tuple(artifact.source_path for artifact in artifacts),
        "source paths",
    )
    _require_casefold_unique(
        tuple(artifact.path for artifact in artifacts),
        "canonical paths",
    )
    _require_no_path_prefix_collisions(
        tuple(artifact.source_path for artifact in artifacts)
    )
    _require_no_path_prefix_collisions(tuple(artifact.path for artifact in artifacts))


def _bounded_tree_snapshot(
    root: Path,
    *,
    file_bounds: Mapping[str, int],
    max_files: int,
    max_total_bytes: int,
    field_name: str,
    require_read_only: bool,
) -> _TreeSnapshot:
    expected_files = set(file_bounds)
    expected_directories: set[str] = set()
    for expected_path in expected_files:
        parent = PurePosixPath(expected_path).parent
        while parent != PurePosixPath("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    max_entries = len(expected_files) + len(expected_directories)
    root_fd = _open_root_fd(root, field_name)
    discovered_files: dict[str, _DiscoveredFile] = {}
    actual_directories: set[str] = set()
    counters = {"entries": 0, "files": 0}
    try:
        root_stat = os.fstat(root_fd)
        if require_read_only and root_stat.st_mode & 0o222:
            raise DeliverableValidationError(f"{field_name} must be read-only")
        _discover_bounded_tree(
            root_fd,
            prefix="",
            expected_files=expected_files,
            expected_directories=expected_directories,
            max_entries=max_entries,
            max_files=max_files,
            require_read_only=require_read_only,
            field_name=field_name,
            discovered_files=discovered_files,
            actual_directories=actual_directories,
            counters=counters,
        )
        missing_files = expected_files - discovered_files.keys()
        missing_directories = expected_directories - actual_directories
        if missing_files or missing_directories:
            missing = sorted(set(missing_files) | missing_directories)
            raise DeliverableValidationError(
                f"{field_name} is missing declared paths: {missing}"
            )

        remaining_precheck = max_total_bytes
        for path in sorted(expected_files):
            size_bytes = discovered_files[path].file_stat.st_size
            max_file_bytes = file_bounds[path]
            if size_bytes > max_file_bytes:
                raise DeliverableValidationError(
                    f"{field_name} exceeds the per-file byte limit: {path}"
                )
            if size_bytes > remaining_precheck:
                raise DeliverableValidationError(
                    f"{field_name} exceeds the total byte limit"
                )
            remaining_precheck -= size_bytes

        files: dict[str, tuple[str, int]] = {}
        total_size = 0
        for path in sorted(expected_files):
            file_fd = _open_relative_file_fd(root_fd, path, field_name)
            try:
                opened_stat = os.fstat(file_fd)
                expected_stat = discovered_files[path].file_stat
                if not _same_file(opened_stat, expected_stat):
                    raise DeliverableValidationError(
                        f"{field_name} changed during validation: {path}"
                    )
                digest, size_bytes = _hash_open_file(
                    file_fd,
                    path,
                    max_bytes=file_bounds[path],
                    remaining_total_bytes=max_total_bytes - total_size,
                    expected_stat=expected_stat,
                    field_name=field_name,
                )
            finally:
                os.close(file_fd)
            files[path] = (digest, size_bytes)
            total_size += size_bytes

        entries: list[dict[str, object]] = [
            {"path": path, "type": "directory"} for path in sorted(actual_directories)
        ]
        entries.extend(
            {
                "path": path,
                "type": "file",
                "sha256": digest,
                "size_bytes": size_bytes,
            }
            for path, (digest, size_bytes) in sorted(files.items())
        )
        return _TreeSnapshot(
            files=files,
            total_size_bytes=total_size,
            tree_sha256=_record_sha256(
                {
                    "schema_version": DELIVERABLE_TREE_COMMITMENT_SCHEMA_VERSION,
                    "entries": sorted(
                        entries, key=lambda item: cast(str, item["path"])
                    ),
                }
            ),
        )
    finally:
        os.close(root_fd)


def _discover_bounded_tree(
    directory_fd: int,
    *,
    prefix: str,
    expected_files: set[str],
    expected_directories: set[str],
    max_entries: int,
    max_files: int,
    require_read_only: bool,
    field_name: str,
    discovered_files: dict[str, _DiscoveredFile],
    actual_directories: set[str],
    counters: dict[str, int],
) -> None:
    try:
        iterator = os.scandir(directory_fd)
    except OSError as exc:
        raise DeliverableValidationError(f"could not enumerate {field_name}") from exc
    with iterator:
        for entry in iterator:
            path = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise DeliverableValidationError(
                    f"{field_name} changed during discovery: {path}"
                ) from exc
            is_directory = stat.S_ISDIR(entry_stat.st_mode)
            expected_paths = expected_directories if is_directory else expected_files
            if path not in expected_paths:
                raise DeliverableValidationError(
                    f"{field_name} contains unexpected paths: {path}"
                )
            counters["entries"] += 1
            if counters["entries"] > max_entries:
                raise DeliverableValidationError(
                    f"{field_name} exceeds its exact entry-count bound"
                )
            if is_directory:
                if require_read_only and entry_stat.st_mode & 0o222:
                    raise DeliverableValidationError(
                        f"{field_name} must be read-only: {path}"
                    )
                actual_directories.add(path)
                child_fd = _open_child_directory_fd(
                    directory_fd, entry.name, field_name
                )
                try:
                    if not _same_file(os.fstat(child_fd), entry_stat):
                        raise DeliverableValidationError(
                            f"{field_name} changed during discovery: {path}"
                        )
                    _discover_bounded_tree(
                        child_fd,
                        prefix=path,
                        expected_files=expected_files,
                        expected_directories=expected_directories,
                        max_entries=max_entries,
                        max_files=max_files,
                        require_read_only=require_read_only,
                        field_name=field_name,
                        discovered_files=discovered_files,
                        actual_directories=actual_directories,
                        counters=counters,
                    )
                finally:
                    os.close(child_fd)
                continue
            counters["files"] += 1
            if counters["files"] > max_files:
                raise DeliverableValidationError(
                    f"{field_name} exceeds the file-count limit"
                )
            if not stat.S_ISREG(entry_stat.st_mode) or entry_stat.st_nlink != 1:
                raise DeliverableValidationError(
                    f"{field_name} must contain only single-link regular files"
                )
            if require_read_only and entry_stat.st_mode & 0o222:
                raise DeliverableValidationError(
                    f"{field_name} must be read-only: {path}"
                )
            discovered_files[path] = _DiscoveredFile(path, entry_stat)


def _hash_open_file(
    file_fd: int,
    display_path: str,
    *,
    max_bytes: int,
    remaining_total_bytes: int,
    expected_stat: os.stat_result,
    field_name: str,
) -> tuple[str, int]:
    opened_stat = os.fstat(file_fd)
    if opened_stat.st_size > max_bytes:
        raise DeliverableValidationError(
            f"{field_name} exceeds the per-file byte limit: {display_path}"
        )
    if opened_stat.st_size > remaining_total_bytes:
        raise DeliverableValidationError(f"{field_name} exceeds the total byte limit")
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with os.fdopen(os.dup(file_fd), "rb") as handle:
            while True:
                remaining_file_bytes = max_bytes - size_bytes
                remaining_aggregate_bytes = remaining_total_bytes - size_bytes
                read_size = min(
                    1024 * 1024,
                    min(remaining_file_bytes, remaining_aggregate_bytes) + 1,
                )
                chunk = handle.read(read_size)
                if not chunk:
                    break
                if size_bytes + len(chunk) > max_bytes:
                    raise DeliverableValidationError(
                        f"{field_name} exceeds the per-file byte limit: {display_path}"
                    )
                if size_bytes + len(chunk) > remaining_total_bytes:
                    raise DeliverableValidationError(
                        f"{field_name} exceeds the total byte limit"
                    )
                size_bytes += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise DeliverableValidationError(
            f"could not read {field_name} path: {display_path}"
        ) from exc
    final_stat = os.fstat(file_fd)
    if (
        not _same_file(final_stat, expected_stat)
        or final_stat.st_size != size_bytes
        or opened_stat.st_size != size_bytes
    ):
        raise DeliverableValidationError(
            f"{field_name} changed while hashing: {display_path}"
        )
    return "sha256:" + digest.hexdigest(), size_bytes


def _open_root_fd(root: Path, field_name: str) -> int:
    try:
        return os.open(root, _directory_flags())
    except OSError as exc:
        raise DeliverableValidationError(
            f"{field_name} must be a real directory"
        ) from exc


def _open_child_directory_fd(parent_fd: int, name: str, field_name: str) -> int:
    try:
        return os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise DeliverableValidationError(
            f"{field_name} contains a symlink or changed directory"
        ) from exc


def _open_relative_file_fd(root_fd: int, relative_path: str, field_name: str) -> int:
    parts = PurePosixPath(relative_path).parts
    current_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = _open_child_directory_fd(current_fd, part, field_name)
            os.close(current_fd)
            current_fd = next_fd
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            return os.open(parts[-1], flags, dir_fd=current_fd)
        except OSError as exc:
            raise DeliverableValidationError(
                f"{field_name} path changed: {relative_path}"
            ) from exc
    finally:
        os.close(current_fd)


def _open_relative_directory_fd(
    root_fd: int,
    relative_path: str,
    field_name: str,
) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in PurePosixPath(relative_path).parts:
            next_fd = _open_child_directory_fd(current_fd, part, field_name)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _seal_read_only(root: Path, file_paths: tuple[str, ...]) -> None:
    root_fd = _open_root_fd(root, "deliverable root")
    try:
        for path in file_paths:
            file_fd = _open_relative_file_fd(root_fd, path, "deliverable root")
            try:
                os.fchmod(file_fd, 0o444)
            finally:
                os.close(file_fd)
        directories: set[str] = set()
        for path in file_paths:
            parent = PurePosixPath(path).parent
            while parent != PurePosixPath("."):
                directories.add(parent.as_posix())
                parent = parent.parent
        for path in sorted(
            directories,
            key=lambda value: len(PurePosixPath(value).parts),
            reverse=True,
        ):
            directory_fd = _open_relative_directory_fd(
                root_fd,
                path,
                "deliverable root",
            )
            try:
                os.fchmod(directory_fd, 0o555)
            finally:
                os.close(directory_fd)
        os.fchmod(root_fd, 0o555)
    finally:
        os.close(root_fd)


def _existing_real_directory(path: Path, field_name: str) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    try:
        path_stat = absolute.lstat()
    except OSError as exc:
        raise DeliverableValidationError(f"{field_name} must exist") from exc
    if not stat.S_ISDIR(path_stat.st_mode) or stat.S_ISLNK(path_stat.st_mode):
        raise DeliverableValidationError(f"{field_name} must be a real directory")
    return absolute.resolve(strict=True)


def _fresh_child_path(path: Path) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    if not absolute.name or absolute.name in {".", ".."}:
        raise DeliverableValidationError("sealed_root must name a fresh child")
    try:
        parent = absolute.parent.resolve(strict=True)
    except OSError as exc:
        raise DeliverableValidationError("sealed_root parent must exist") from exc
    normalized = parent / absolute.name
    if normalized.exists() or normalized.is_symlink():
        raise DeliverableValidationError("sealed_root must be a fresh, absent path")
    return normalized


def _require_disjoint_roots(left: Path, right: Path) -> None:
    if left == right or left in right.parents or right in left.parents:
        raise DeliverableValidationError(
            "deliverable source and sealed roots must be disjoint"
        )


def _decoded_safe_path(value: str, field_name: str) -> str:
    decoded = unquote(value)
    if decoded != value:
        try:
            validate_safe_relative_path(decoded, field_name)
        except ValueError as exc:
            raise ValueError(f"{field_name} is unsafe after percent-decoding") from exc
        raise ValueError(f"{field_name} must not contain percent-encoded path bytes")
    return validate_safe_relative_path(value, field_name)


def _validate_media_type(value: str) -> None:
    if _MEDIA_TYPE_RE.fullmatch(value) is None:
        raise ValueError("media_type must be an IANA-style type/subtype")


def _record_sha256(record: object) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _canonical_sha256(value: str, field_name: str) -> str:
    validate_sha256(value, field_name)
    return "sha256:" + value.removeprefix("sha256:")


def _require_canonical_sha256(value: str, field_name: str) -> None:
    validate_sha256(value, field_name)
    if not value.startswith("sha256:"):
        raise ValueError(f"{field_name} must use the sha256:<hex> representation")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def _require_casefold_unique(values: tuple[str, ...], field_name: str) -> None:
    if len({value.casefold() for value in values}) != len(values):
        raise ValueError(f"{field_name} must be unique ignoring case")


def _require_no_path_prefix_collisions(paths: tuple[str, ...]) -> None:
    path_parts = tuple((path, PurePosixPath(path).parts) for path in paths)
    for path, parts in path_parts:
        for other_path, other_parts in path_parts:
            if path == other_path:
                continue
            if len(parts) < len(other_parts) and other_parts[: len(parts)] == parts:
                raise ValueError(
                    "artifact paths must not use another artifact as a directory: "
                    f"{path!r}, {other_path!r}"
                )


def _require_exact_fields(
    record: Mapping[str, Any],
    expected: set[str],
    field_name: str,
) -> None:
    actual = set(record)
    if actual != expected:
        raise ValueError(
            f"{field_name} fields do not match schema: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_non_negative_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _required_positive_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _required_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)
