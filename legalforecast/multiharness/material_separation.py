"""Physical material planes and role-scoped read-only access contracts."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from legalforecast.multiharness.materialization import (
    MaterializationLimits,
    MaterializedArtifact,
    TaskArtifactProjection,
    TaskMaterializationLayout,
    TaskMaterializationManifest,
    materialize_task,
)
from legalforecast.multiharness.spec import CanonicalTask
from legalforecast.multiharness.validation import (
    validate_safe_relative_path,
    validate_sha256,
)

MATERIAL_SEPARATION_SCHEMA_VERSION = "legalforecast.multiharness.material_separation.v1"
SOLVER_INPUT_TARGET = "/workspace/input"
EVALUATOR_DELIVERABLE_TARGET = "/evaluation/deliverable"
EVALUATOR_PRIVATE_TARGET = "/evaluation/private"

_LAYOUT_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*\.v[1-9][0-9]*\Z")


class MaterialAccessError(ValueError):
    """A role attempted to use material outside its declared read-only mounts."""


class MaterialSeparationError(MaterialAccessError):
    """Task material could not be split into disjoint physical planes."""


@dataclass(frozen=True, slots=True)
class MaterialSeparationLayout:
    """Versioned mappings for solver-visible and evaluator-private artifacts."""

    layout_id: str
    solver_artifacts: tuple[TaskArtifactProjection, ...]
    evaluator_private_artifacts: tuple[TaskArtifactProjection, ...]

    def __post_init__(self) -> None:
        if _LAYOUT_ID_RE.fullmatch(self.layout_id) is None:
            raise ValueError(
                "layout_id must be a lowercase identifier ending in a version "
                "such as '.v1'"
            )
        solver_ids = tuple(item.artifact_id for item in self.solver_artifacts)
        private_ids = tuple(
            item.artifact_id for item in self.evaluator_private_artifacts
        )
        if len(set(solver_ids)) != len(solver_ids):
            raise ValueError("solver artifact IDs must be unique")
        if len(set(private_ids)) != len(private_ids):
            raise ValueError("evaluator-private artifact IDs must be unique")
        overlap = set(solver_ids) & set(private_ids)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(
                "artifacts cannot be both solver-visible and evaluator-private: "
                f"{names}"
            )


@dataclass(frozen=True, slots=True)
class MaterialPlaneManifest:
    """Host-only byte manifest for one physical material plane."""

    plane: str
    task_id: str
    task_sha256: str
    layout_id: str
    entries: tuple[MaterializedArtifact, ...]
    semantic_bytes_sha256: str
    total_size_bytes: int
    manifest_sha256: str

    def __post_init__(self) -> None:
        if self.plane not in {"solver", "evaluator_private"}:
            raise ValueError("material plane must be solver or evaluator_private")
        if self.total_size_bytes != sum(entry.size_bytes for entry in self.entries):
            raise ValueError("material plane total size does not match its entries")
        if len({entry.artifact_id for entry in self.entries}) != len(self.entries):
            raise ValueError("material plane artifact IDs must be unique")
        if len({entry.destination_path for entry in self.entries}) != len(self.entries):
            raise ValueError("material plane destination paths must be unique")
        validate_sha256(self.semantic_bytes_sha256, "semantic_bytes_sha256")
        validate_sha256(self.manifest_sha256, "manifest_sha256")
        if self.manifest_sha256 != _record_sha256(
            _plane_content(
                plane=self.plane,
                task_id=self.task_id,
                task_sha256=self.task_sha256,
                layout_id=self.layout_id,
                entries=self.entries,
                semantic_bytes_sha256=self.semantic_bytes_sha256,
                total_size_bytes=self.total_size_bytes,
            )
        ):
            raise ValueError("material plane manifest sha256 does not match content")

    def to_record(self) -> dict[str, object]:
        """Return a deterministic record without host filesystem paths."""

        return {
            "plane": self.plane,
            "task_id": self.task_id,
            "task_sha256": self.task_sha256,
            "layout_id": self.layout_id,
            "entries": [entry.to_record() for entry in self.entries],
            "semantic_bytes_sha256": self.semantic_bytes_sha256,
            "total_size_bytes": self.total_size_bytes,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class SeparatedTaskMaterialization:
    """Two disjoint, sealed task-material roots plus their host-only manifests."""

    solver_root: Path
    evaluator_private_root: Path
    solver_manifest: MaterialPlaneManifest
    evaluator_private_manifest: MaterialPlaneManifest
    separation_sha256: str

    def __post_init__(self) -> None:
        _require_disjoint_roots(self.solver_root, self.evaluator_private_root)
        if self.solver_manifest.plane != "solver":
            raise ValueError("solver_manifest must describe the solver plane")
        if self.evaluator_private_manifest.plane != "evaluator_private":
            raise ValueError(
                "evaluator_private_manifest must describe the evaluator-private plane"
            )
        for field_name in ("task_id", "task_sha256", "layout_id"):
            if getattr(self.solver_manifest, field_name) != getattr(
                self.evaluator_private_manifest,
                field_name,
            ):
                raise ValueError(f"material plane {field_name} values must match")
        validate_sha256(self.separation_sha256, "separation_sha256")
        if self.separation_sha256 != _record_sha256(
            _separation_content(
                self.solver_manifest,
                self.evaluator_private_manifest,
            )
        ):
            raise ValueError("separation_sha256 does not match material planes")

    def to_record(self) -> dict[str, object]:
        """Return the separation commitment without disclosing host paths."""

        return {
            "schema_version": MATERIAL_SEPARATION_SCHEMA_VERSION,
            "task_id": self.solver_manifest.task_id,
            "task_sha256": self.solver_manifest.task_sha256,
            "layout_id": self.solver_manifest.layout_id,
            "solver": self.solver_manifest.to_record(),
            "evaluator_private": self.evaluator_private_manifest.to_record(),
            "separation_sha256": self.separation_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReadOnlyMaterialMount:
    """One host-owned source exposed read-only at a role-specific target."""

    purpose: str
    source: Path
    target: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        expected_targets = {
            "solver_input": SOLVER_INPUT_TARGET,
            "sealed_deliverable": EVALUATOR_DELIVERABLE_TARGET,
            "evaluator_private": EVALUATOR_PRIVATE_TARGET,
        }
        expected_target = expected_targets.get(self.purpose)
        if expected_target is None or self.target != expected_target:
            raise ValueError("material mount purpose and target do not match")
        validate_sha256(self.manifest_sha256, "manifest_sha256")


@dataclass(frozen=True, slots=True)
class MaterialAccessPlan:
    """Exact read-only mounts available to one isolated runtime role."""

    role: str
    mounts: tuple[ReadOnlyMaterialMount, ...]

    def __post_init__(self) -> None:
        expected_purposes = {
            "solver": ("solver_input",),
            "evaluator": ("sealed_deliverable", "evaluator_private"),
        }
        expected = expected_purposes.get(self.role)
        actual = tuple(mount.purpose for mount in self.mounts)
        if expected is None or actual != expected:
            raise ValueError("material access role has unexpected mounts")

    def read_bytes(self, runtime_path: str) -> bytes:
        """Read a mounted regular file for deterministic boundary canaries."""

        current = _mounted_host_path(self.mounts, runtime_path, allow_root=False)
        try:
            file_stat = current.stat()
        except OSError as exc:
            raise MaterialAccessError(
                f"mounted path does not exist: {runtime_path}"
            ) from exc
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise MaterialAccessError(
                f"mounted path must be a single-link regular file: {runtime_path}"
            )
        if file_stat.st_mode & 0o222:
            raise MaterialAccessError(f"mounted path must be read-only: {runtime_path}")
        return current.read_bytes()

    def list_directory(self, runtime_path: str) -> tuple[str, ...]:
        """Enumerate one mounted directory for deterministic boundary canaries."""

        current = _mounted_host_path(self.mounts, runtime_path, allow_root=True)
        try:
            directory_stat = current.stat()
        except OSError as exc:
            raise MaterialAccessError(
                f"mounted path does not exist: {runtime_path}"
            ) from exc
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise MaterialAccessError(
                f"mounted path must be a directory: {runtime_path}"
            )
        if directory_stat.st_mode & 0o222:
            raise MaterialAccessError(f"mounted path must be read-only: {runtime_path}")
        return tuple(sorted(path.name for path in current.iterdir()))


def materialize_separated_task(
    task: CanonicalTask,
    *,
    source_root: Path,
    solver_root: Path,
    evaluator_private_root: Path,
    layout: MaterialSeparationLayout,
    limits: MaterializationLimits | None = None,
) -> SeparatedTaskMaterialization:
    """Materialize and seal disjoint solver and evaluator-private roots.

    The source root, both destination parents, and both fresh roots require
    exclusive coordination from other same-UID processes for this call. The
    read-only modes are runtime hygiene, not isolation from a malicious same-UID
    process; runtime isolation comes from mounting only a role's access plan.
    Failures can leave partial fresh roots for coordinated caller cleanup.
    """

    _require_disjoint_roots(solver_root, evaluator_private_root)
    _require_complete_classification(task, layout)
    solver_ids = tuple(item.artifact_id for item in layout.solver_artifacts)
    private_ids = tuple(item.artifact_id for item in layout.evaluator_private_artifacts)
    solver_materialization = materialize_task(
        task,
        source_root=source_root,
        destination_root=solver_root,
        layout=TaskMaterializationLayout(
            layout_id=layout.layout_id,
            solver_artifacts=layout.solver_artifacts,
            evaluator_private_artifact_ids=private_ids,
        ),
        limits=limits,
    )
    private_materialization = materialize_task(
        task,
        source_root=source_root,
        destination_root=evaluator_private_root,
        layout=TaskMaterializationLayout(
            layout_id=layout.layout_id,
            solver_artifacts=layout.evaluator_private_artifacts,
            evaluator_private_artifact_ids=solver_ids,
        ),
        limits=limits,
    )
    solver_manifest = _plane_manifest("solver", solver_materialization)
    private_manifest = _plane_manifest(
        "evaluator_private",
        private_materialization,
    )
    _seal_read_only_tree(
        solver_root,
        directory_mode=0o555,
        file_mode=0o444,
    )
    _seal_read_only_tree(
        evaluator_private_root,
        directory_mode=0o500,
        file_mode=0o400,
    )
    _verify_material_plane(solver_root, solver_manifest)
    _verify_material_plane(evaluator_private_root, private_manifest)
    separation_sha256 = _record_sha256(
        _separation_content(solver_manifest, private_manifest)
    )
    return SeparatedTaskMaterialization(
        solver_root=solver_root,
        evaluator_private_root=evaluator_private_root,
        solver_manifest=solver_manifest,
        evaluator_private_manifest=private_manifest,
        separation_sha256=separation_sha256,
    )


def solver_material_access(
    materialization: SeparatedTaskMaterialization,
) -> MaterialAccessPlan:
    """Expose only solver-visible bytes to the solver/tool runtime."""

    _require_disjoint_roots(
        materialization.solver_root,
        materialization.evaluator_private_root,
    )
    _verify_material_plane(
        materialization.solver_root,
        materialization.solver_manifest,
    )
    _verify_material_plane(
        materialization.evaluator_private_root,
        materialization.evaluator_private_manifest,
    )
    return MaterialAccessPlan(
        role="solver",
        mounts=(
            ReadOnlyMaterialMount(
                purpose="solver_input",
                source=materialization.solver_root,
                target=SOLVER_INPUT_TARGET,
                manifest_sha256=materialization.solver_manifest.manifest_sha256,
            ),
        ),
    )


def evaluator_material_access(
    materialization: SeparatedTaskMaterialization,
    *,
    sealed_deliverable_root: Path,
    sealed_deliverable_sha256: str,
) -> MaterialAccessPlan:
    """Expose only a sealed deliverable and private inputs to the evaluator."""

    validate_sha256(sealed_deliverable_sha256, "sealed_deliverable_sha256")
    _require_pairwise_disjoint(
        materialization.solver_root,
        materialization.evaluator_private_root,
        sealed_deliverable_root,
    )
    _verify_material_plane(
        materialization.solver_root,
        materialization.solver_manifest,
    )
    _verify_material_plane(
        materialization.evaluator_private_root,
        materialization.evaluator_private_manifest,
    )
    _verify_read_only_tree(sealed_deliverable_root, "sealed deliverable")
    return MaterialAccessPlan(
        role="evaluator",
        mounts=(
            ReadOnlyMaterialMount(
                purpose="sealed_deliverable",
                source=sealed_deliverable_root,
                target=EVALUATOR_DELIVERABLE_TARGET,
                manifest_sha256=sealed_deliverable_sha256,
            ),
            ReadOnlyMaterialMount(
                purpose="evaluator_private",
                source=materialization.evaluator_private_root,
                target=EVALUATOR_PRIVATE_TARGET,
                manifest_sha256=(
                    materialization.evaluator_private_manifest.manifest_sha256
                ),
            ),
        ),
    )


def _require_complete_classification(
    task: CanonicalTask,
    layout: MaterialSeparationLayout,
) -> None:
    artifact_ids = {artifact.artifact_id for artifact in task.artifacts}
    solver_ids = {item.artifact_id for item in layout.solver_artifacts}
    private_ids = {item.artifact_id for item in layout.evaluator_private_artifacts}
    classified_ids = solver_ids | private_ids
    unknown = classified_ids - artifact_ids
    if unknown:
        names = ", ".join(sorted(unknown))
        raise MaterialSeparationError(f"layout references unknown artifacts: {names}")
    unclassified = artifact_ids - classified_ids
    if unclassified:
        names = ", ".join(sorted(unclassified))
        raise MaterialSeparationError(
            f"task artifacts must be classified exactly once: {names}"
        )


def _plane_manifest(
    plane: str,
    materialization: TaskMaterializationManifest,
) -> MaterialPlaneManifest:
    manifest_sha256 = _record_sha256(
        _plane_content(
            plane=plane,
            task_id=materialization.task_id,
            task_sha256=materialization.task_sha256,
            layout_id=materialization.layout_id,
            entries=materialization.entries,
            semantic_bytes_sha256=materialization.semantic_bytes_sha256,
            total_size_bytes=materialization.total_size_bytes,
        )
    )
    return MaterialPlaneManifest(
        plane=plane,
        task_id=materialization.task_id,
        task_sha256=materialization.task_sha256,
        layout_id=materialization.layout_id,
        entries=materialization.entries,
        semantic_bytes_sha256=materialization.semantic_bytes_sha256,
        total_size_bytes=materialization.total_size_bytes,
        manifest_sha256=manifest_sha256,
    )


def _seal_read_only_tree(
    root: Path,
    *,
    directory_mode: int,
    file_mode: int,
) -> None:
    paths = sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in paths:
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode):
            raise MaterialSeparationError("material plane contains a symlink")
        if stat.S_ISDIR(path_stat.st_mode):
            path.chmod(directory_mode)
            continue
        if not stat.S_ISREG(path_stat.st_mode) or path_stat.st_nlink != 1:
            raise MaterialSeparationError(
                "material plane must contain only single-link regular files"
            )
        path.chmod(file_mode)
    root.chmod(directory_mode)


def _verify_material_plane(root: Path, manifest: MaterialPlaneManifest) -> None:
    _verify_read_only_tree(root, f"{manifest.plane} material")
    expected = {entry.destination_path: entry for entry in manifest.entries}
    actual: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            actual[path.relative_to(root).as_posix()] = path
    if set(actual) != set(expected):
        raise MaterialAccessError(
            f"{manifest.plane} material paths do not match its manifest"
        )
    total_size = 0
    for relative_path, entry in expected.items():
        path = actual[relative_path]
        payload = path.read_bytes()
        total_size += len(payload)
        if len(payload) != entry.size_bytes:
            raise MaterialAccessError(
                f"{manifest.plane} material size changed: {relative_path}"
            )
        if hashlib.sha256(payload).hexdigest() != entry.sha256:
            raise MaterialAccessError(
                f"{manifest.plane} material bytes changed: {relative_path}"
            )
    if total_size != manifest.total_size_bytes:
        raise MaterialAccessError(f"{manifest.plane} material total size changed")


def _verify_read_only_tree(root: Path, field_name: str) -> None:
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise MaterialAccessError(f"{field_name} root does not exist") from exc
    if not stat.S_ISDIR(root_stat.st_mode) or root.is_symlink():
        raise MaterialAccessError(f"{field_name} root must be a real directory")
    for path in (root, *root.rglob("*")):
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode):
            raise MaterialAccessError(f"{field_name} must not contain symlinks")
        if path_stat.st_mode & 0o222:
            raise MaterialAccessError(f"{field_name} must be read-only")
        if stat.S_ISDIR(path_stat.st_mode):
            continue
        if not stat.S_ISREG(path_stat.st_mode) or path_stat.st_nlink != 1:
            raise MaterialAccessError(
                f"{field_name} must contain only single-link regular files"
            )


def _mounted_host_path(
    mounts: tuple[ReadOnlyMaterialMount, ...],
    runtime_path: str,
    *,
    allow_root: bool,
) -> Path:
    decoded = unquote(runtime_path)
    if decoded != runtime_path:
        raise MaterialAccessError("runtime path must not use percent encoding")
    candidate = PurePosixPath(decoded)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise MaterialAccessError("runtime path must be absolute without traversal")
    for mount in mounts:
        target = PurePosixPath(mount.target)
        try:
            relative = candidate.relative_to(target)
        except ValueError:
            continue
        relative_path = relative.as_posix()
        if relative_path == ".":
            if allow_root:
                return mount.source
            raise MaterialAccessError("runtime path must name a mounted file")
        try:
            validate_safe_relative_path(relative_path, "runtime path")
        except ValueError as exc:
            raise MaterialAccessError(str(exc)) from exc
        current = mount.source
        for part in relative.parts:
            current = current / part
            try:
                current_stat = current.lstat()
            except OSError as exc:
                raise MaterialAccessError(
                    f"mounted path does not exist: {runtime_path}"
                ) from exc
            if stat.S_ISLNK(current_stat.st_mode):
                raise MaterialAccessError(
                    f"mounted path contains a symlink: {runtime_path}"
                )
        return current
    raise MaterialAccessError(
        f"runtime path is not mounted for this role: {runtime_path}"
    )


def _require_disjoint_roots(first: Path, second: Path) -> None:
    _require_pairwise_disjoint(first, second)


def _require_pairwise_disjoint(*roots: Path) -> None:
    normalized = tuple(_normalized_root(root) for root in roots)
    for index, first in enumerate(normalized):
        for second in normalized[index + 1 :]:
            if (
                first == second
                or first.is_relative_to(second)
                or second.is_relative_to(first)
            ):
                raise MaterialSeparationError(
                    "material roots must be physically disjoint and non-nested"
                )


def _normalized_root(root: Path) -> Path:
    return (root if root.is_absolute() else Path.cwd() / root).resolve(strict=False)


def _plane_content(
    *,
    plane: str,
    task_id: str,
    task_sha256: str,
    layout_id: str,
    entries: tuple[MaterializedArtifact, ...],
    semantic_bytes_sha256: str,
    total_size_bytes: int,
) -> dict[str, object]:
    return {
        "plane": plane,
        "task_id": task_id,
        "task_sha256": task_sha256,
        "layout_id": layout_id,
        "entries": [entry.to_record() for entry in entries],
        "semantic_bytes_sha256": semantic_bytes_sha256,
        "total_size_bytes": total_size_bytes,
    }


def _separation_content(
    solver_manifest: MaterialPlaneManifest,
    evaluator_private_manifest: MaterialPlaneManifest,
) -> dict[str, object]:
    return {
        "schema_version": MATERIAL_SEPARATION_SCHEMA_VERSION,
        "task_id": solver_manifest.task_id,
        "task_sha256": solver_manifest.task_sha256,
        "layout_id": solver_manifest.layout_id,
        "solver": solver_manifest.to_record(),
        "evaluator_private": evaluator_private_manifest.to_record(),
    }


def _record_sha256(record: object) -> str:
    payload = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
