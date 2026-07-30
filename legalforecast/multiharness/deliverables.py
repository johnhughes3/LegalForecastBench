"""Canonical, layout-independent sealed deliverable artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Self, cast
from urllib.parse import unquote

from legalforecast.multiharness.material_separation import (
    MaterialAccessError,
    deliverable_tree_sha256,
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
        validate_sha256(self.sha256, "sha256")
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
            validate_sha256(getattr(self, field_name), field_name)
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

    for field_name, value in (
        ("task_sha256", task_sha256),
        ("run_sha256", run_sha256),
        ("config_sha256", config_sha256),
    ):
        validate_sha256(value, field_name)
    applied_limits = limits or DeliverableLimits()
    declared = tuple(artifacts)
    _validate_projections(declared, applied_limits)
    normalized_source = _existing_real_directory(source_root, "source_root")
    normalized_sealed = _fresh_child_path(sealed_root)
    _require_disjoint_roots(normalized_source, normalized_sealed)
    _verify_exact_source_tree(normalized_source, declared)

    source_records: list[ArtifactRecord] = []
    sizes: dict[str, int] = {}
    total_size = 0
    for projection in declared:
        source_path = normalized_source / PurePosixPath(projection.source_path)
        digest, size_bytes = _hash_regular_file(source_path, projection.source_path)
        effective_max = min(projection.max_size_bytes, applied_limits.max_file_bytes)
        if size_bytes > effective_max:
            raise DeliverableValidationError(
                f"artifact {projection.artifact_id!r} exceeds the per-file "
                "deliverable limit"
            )
        total_size += size_bytes
        if total_size > applied_limits.max_total_bytes:
            raise DeliverableValidationError("deliverable exceeds the total byte limit")
        sizes[projection.artifact_id] = size_bytes
        source_records.append(
            ArtifactRecord(
                artifact_id=projection.artifact_id,
                path=projection.source_path,
                sha256=digest,
                media_type=projection.media_type,
                size_bytes=size_bytes,
            )
        )

    task = CanonicalTask(
        task_id="canonical-deliverable",
        source_id="canonical-deliverable",
        family="contract_only",
        suite_version="v1",
        scoring_mode="contract_only",
        task_sha256=task_sha256,
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

    _seal_read_only(normalized_sealed)
    sealed_artifacts = tuple(
        SealedDeliverableArtifact(
            artifact_id=entry.artifact_id,
            path=entry.destination_path,
            media_type=projections_by_id[entry.artifact_id].media_type,
            sha256="sha256:" + entry.sha256.removeprefix("sha256:"),
            size_bytes=sizes[entry.artifact_id],
            max_size_bytes=min(
                projections_by_id[entry.artifact_id].max_size_bytes,
                applied_limits.max_file_bytes,
            ),
        )
        for entry in materialized.entries
    )
    tree_sha256 = deliverable_tree_sha256(normalized_sealed)
    content = {
        "schema_version": DELIVERABLE_MANIFEST_SCHEMA_VERSION,
        "task_sha256": task_sha256,
        "run_sha256": run_sha256,
        "config_sha256": config_sha256,
        "artifacts": [artifact.to_record() for artifact in sealed_artifacts],
        "total_size_bytes": total_size,
        "max_total_size_bytes": applied_limits.max_total_bytes,
        "tree_sha256": tree_sha256,
    }
    return DeliverableManifest(
        task_sha256=task_sha256,
        run_sha256=run_sha256,
        config_sha256=config_sha256,
        artifacts=sealed_artifacts,
        total_size_bytes=total_size,
        max_total_size_bytes=applied_limits.max_total_bytes,
        tree_sha256=tree_sha256,
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
    try:
        actual_tree_sha256 = deliverable_tree_sha256(normalized_root)
    except (MaterialAccessError, ValueError) as exc:
        raise DeliverableValidationError(str(exc)) from exc
    _verify_exact_tree(
        normalized_root,
        {artifact.path for artifact in canonical_manifest.artifacts},
        "sealed deliverable",
    )
    if actual_tree_sha256 != canonical_manifest.tree_sha256:
        raise DeliverableValidationError(
            "sealed deliverable tree does not match its manifest"
        )

    total_size = 0
    for artifact in canonical_manifest.artifacts:
        path = normalized_root / PurePosixPath(artifact.path)
        digest, size_bytes = _hash_regular_file(path, artifact.path)
        if digest != artifact.sha256:
            raise DeliverableValidationError(
                f"sealed deliverable hash mismatch: {artifact.path}"
            )
        if size_bytes != artifact.size_bytes:
            raise DeliverableValidationError(
                f"sealed deliverable size mismatch: {artifact.path}"
            )
        if size_bytes > artifact.max_size_bytes:
            raise DeliverableValidationError(
                f"sealed deliverable exceeds artifact bound: {artifact.path}"
            )
        total_size += size_bytes
    if total_size != canonical_manifest.total_size_bytes:
        raise DeliverableValidationError(
            "sealed deliverable total size does not match its manifest"
        )
    if total_size > canonical_manifest.max_total_size_bytes:
        raise DeliverableValidationError(
            "sealed deliverable exceeds its total size bound"
        )
    return canonical_manifest


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


def _verify_exact_source_tree(
    root: Path,
    artifacts: tuple[DeliverableArtifactProjection, ...],
) -> None:
    _verify_exact_tree(
        root,
        {artifact.source_path for artifact in artifacts},
        "deliverable source",
    )


def _verify_exact_tree(
    root: Path,
    expected_files: set[str],
    field_name: str,
) -> None:
    expected_directories: set[str] = set()
    for source_path in expected_files:
        parent = PurePosixPath(source_path).parent
        while parent != PurePosixPath("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent

    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in root.rglob("*"):
        relative_path = path.relative_to(root).as_posix()
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode):
            raise DeliverableValidationError(
                f"{field_name} contains a symlink: {relative_path}"
            )
        if stat.S_ISDIR(path_stat.st_mode):
            actual_directories.add(relative_path)
            continue
        if not stat.S_ISREG(path_stat.st_mode) or path_stat.st_nlink != 1:
            raise DeliverableValidationError(
                f"{field_name} must contain only single-link regular files"
            )
        actual_files.add(relative_path)
    missing = expected_files - actual_files
    if missing:
        raise DeliverableValidationError(
            f"{field_name} is missing declared paths: {sorted(missing)}"
        )
    extra_files = actual_files - expected_files
    extra_directories = actual_directories - expected_directories
    if extra_files or extra_directories:
        unexpected = sorted(extra_files | extra_directories)
        raise DeliverableValidationError(
            f"{field_name} contains unexpected paths: {unexpected}"
        )


def _hash_regular_file(path: Path, display_path: str) -> tuple[str, int]:
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise DeliverableValidationError(
            f"deliverable path is missing: {display_path}"
        ) from exc
    if (
        not stat.S_ISREG(path_stat.st_mode)
        or stat.S_ISLNK(path_stat.st_mode)
        or path_stat.st_nlink != 1
    ):
        raise DeliverableValidationError(
            f"deliverable path must be a single-link regular file: {display_path}"
        )
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size_bytes += len(chunk)
    except OSError as exc:
        raise DeliverableValidationError(
            f"could not read deliverable path: {display_path}"
        ) from exc
    return "sha256:" + digest.hexdigest(), size_bytes


def _seal_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
        else:
            path.chmod(0o444)
    root.chmod(0o555)


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
