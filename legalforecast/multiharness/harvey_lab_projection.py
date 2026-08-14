"""Deterministic Harvey LAB solver-visible projection.

This is the live-bridge projection for the pinned upstream CLI (GitHub #48 /
issue-196). It sends only validated solver-visible bytes through the generic
materializer and writes a self-describing manifest in the projected tree so
folder-scoped runs (``dm0g.4.6.8``) can resolve tasks and verify bytes without
reaching evaluator-private state.

The older ``harvey_lab_adapter`` assumed ``--lab-root`` / ``--output-dir`` and
copied mixed-boundary ``task.json`` into the solver workspace. That invocation
contract is not the pinned CLI; this module replaces it for projection.
"""

from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.material_separation import (
    MaterialSeparationError,
    MaterialSeparationLayout,
    SeparatedTaskMaterialization,
    materialize_separated_task,
)
from legalforecast.multiharness.materialization import (
    MaterializationLimits,
    TaskArtifactProjection,
    TaskMaterializationError,
)
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
)

PROJECTION_SCHEMA_VERSION = (
    # contract-ratchet: allow LAB1 projection schema until contracts registry
    "legalforecast.harvey_lab_projection.v1"
)
TASK_PROJECTION_SCHEMA_VERSION = (
    # contract-ratchet: allow LAB1 task-projection schema until contracts registry
    "legalforecast.harvey_lab_task_projection.v1"
)
SOLVER_VISIBLE_LAYOUT_ID = "harvey-lab-solver-visible.v1"
NATIVE_LAYOUT_ID = "harvey-lab-native.v1"
ROOT_MANIFEST_NAME = "harvey-lab-projection.v1.json"
TASK_DESCRIPTOR_NAME = "task-projection.json"
INSTRUCTIONS_NAME = "instructions.txt"
EXPECTED_DELIVERABLE_NAME = "expected-deliverable.json"
PINNED_REPOSITORY = "https://github.com/harveyai/harvey-labs"
PINNED_COMMIT = "73feb91d63d53b1a44151d99329779c4defcdb72"
PINNED_TREE = "944913ee8cdeaef4930a106e5e16d74aa93a29d7"
ISSUE_196_LAB_TASK_ID = "employment-labor/identify-issues-in-counterparty-motion-brief"
PRIVATE_CONTENT_MARKERS = (
    "GOLD_ANSWER_PRIVATE",
    "match_criteria",
    "EVALUATOR_PRIVATE_CANARY",
)
_PRIVATE_FILENAMES = frozenset(
    {
        "gold.json",
        "gold-answers.json",
        "gold_answers.json",
        "rubric.json",
    }
)
_TEXT_SUFFIXES = frozenset({".json", ".txt", ".md", ".html", ".csv"})
_GIT_SHA_LENGTH = 40
_FILE_ROLES = frozenset(
    {"instructions", "document", "expected_deliverable", "task_descriptor"}
)
_MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "layout_id",
        "pin",
        "layout_map",
        "tasks",
        "manifest_sha256",
    }
)
_PIN_REQUIRED_FIELDS = frozenset({"repository", "commit", "tree"})
_TASK_REQUIRED_FIELDS = frozenset(
    {
        "task_id",
        "lab_task_id",
        "category",
        "relative_path",
        "task_sha256",
        "expected_deliverable",
        "files",
    }
)
_FILE_REQUIRED_FIELDS = frozenset({"path", "sha256", "size_bytes", "role"})


class HarveyLabProjectionError(ValueError):
    """Raised when LAB tasks cannot be projected without leaking private bytes."""


@dataclass(frozen=True, slots=True)
class HarveyLabPin:
    """Pinned upstream identity recorded on a projection manifest."""

    repository: str
    commit: str
    tree: str

    def __post_init__(self) -> None:
        _require_https_repository(self.repository)
        _require_git_sha(self.commit, "commit")
        _require_git_sha(self.tree, "tree")

    def to_record(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "tree": self.tree,
        }


@dataclass(frozen=True, slots=True)
class HarveyLabProjectedFile:
    """One solver-visible file in a projected task directory."""

    path: str
    sha256: str
    size_bytes: int
    role: str

    def __post_init__(self) -> None:
        try:
            validate_safe_relative_path(self.path, "path")
            validate_sha256(self.sha256, "sha256", allow_prefix=False)
        except MultiHarnessValidationError as exc:
            raise HarveyLabProjectionError(str(exc)) from exc
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise HarveyLabProjectionError("size_bytes must be a non-negative integer")
        if self.role not in _FILE_ROLES:
            raise HarveyLabProjectionError("unsupported projected file role")

    def to_record(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class HarveyLabProjectedTask:
    """Self-describing record for one projected LAB task."""

    task_id: str
    lab_task_id: str
    category: str
    relative_path: str
    task_sha256: str
    expected_deliverable: str
    files: tuple[HarveyLabProjectedFile, ...]

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.lab_task_id.strip():
            raise HarveyLabProjectionError("task_id and lab_task_id are required")
        if not self.category.strip():
            raise HarveyLabProjectionError("category must be a non-empty string")
        try:
            validate_safe_relative_path(self.relative_path, "relative_path")
            validate_sha256(self.task_sha256, "task_sha256", allow_prefix=False)
        except MultiHarnessValidationError as extra:
            raise HarveyLabProjectionError(str(extra)) from extra
        if "/" in self.expected_deliverable or not self.expected_deliverable.endswith(
            ".docx"
        ):
            raise HarveyLabProjectionError(
                "expected_deliverable must be a .docx basename"
            )
        if not self.files:
            raise HarveyLabProjectionError("projected task has no files")

    def to_record(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "lab_task_id": self.lab_task_id,
            "category": self.category,
            "relative_path": self.relative_path,
            "task_sha256": self.task_sha256,
            "expected_deliverable": self.expected_deliverable,
            "files": [item.to_record() for item in self.files],
        }

    def descriptor_record(self) -> dict[str, object]:
        """Return the per-task descriptor without the descriptor file itself."""

        return {
            "schema_version": TASK_PROJECTION_SCHEMA_VERSION,
            "task_id": self.task_id,
            "lab_task_id": self.lab_task_id,
            "category": self.category,
            "relative_path": self.relative_path,
            "task_sha256": self.task_sha256,
            "expected_deliverable": self.expected_deliverable,
            "files": [
                item.to_record()
                for item in self.files
                if item.role != "task_descriptor"
            ],
        }


@dataclass(frozen=True, slots=True)
class HarveyLabProjectionManifest:
    """Folder-scoped index of solver-visible LAB tasks and content hashes."""

    layout_id: str
    pin: HarveyLabPin
    layout_map: Mapping[str, Mapping[str, str]]
    tasks: tuple[HarveyLabProjectedTask, ...]
    manifest_sha256: str
    schema_version: str = PROJECTION_SCHEMA_VERSION

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "layout_id": self.layout_id,
            "pin": self.pin.to_record(),
            "layout_map": {
                name: dict(mapping) for name, mapping in self.layout_map.items()
            },
            "tasks": [task.to_record() for task in self.tasks],
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class HarveyLabTaskProjection:
    """One task's disjoint material planes plus the public projected record."""

    record: HarveyLabProjectedTask
    materialization: SeparatedTaskMaterialization


@dataclass(frozen=True, slots=True)
class HarveyLabProjectionResult:
    """Suite projection: disjoint roots plus the self-describing index."""

    solver_root: Path
    evaluator_private_root: Path
    manifest: HarveyLabProjectionManifest
    tasks: tuple[HarveyLabTaskProjection, ...]


@dataclass(frozen=True, slots=True)
class ClassifiedHarveyLabTask:
    """Staging tree ready for the generic materializer."""

    task: CanonicalTask
    lab_task_id: str
    category: str
    expected_deliverable: str
    staging_root: Path
    solver_artifacts: tuple[TaskArtifactProjection, ...]
    evaluator_private_artifacts: tuple[TaskArtifactProjection, ...]
    projected_files: tuple[HarveyLabProjectedFile, ...]


def issue_196_pin() -> HarveyLabPin:
    """Return the retained issue-196 Harvey LAB pin."""

    return HarveyLabPin(
        repository=PINNED_REPOSITORY,
        commit=PINNED_COMMIT,
        tree=PINNED_TREE,
    )


def harvey_lab_layout_map() -> dict[str, dict[str, str]]:
    """Return the versioned native/external path map for solver-visible bytes."""

    return {
        "native": {
            "instructions": "tasks/{lab_task_id}/task.json#instructions",
            "documents": "tasks/{lab_task_id}/documents/{name}",
            "expected_deliverable": ("tasks/{lab_task_id}/task.json expected basename"),
        },
        "external": {
            "instructions": f"tasks/{{lab_task_id}}/{INSTRUCTIONS_NAME}",
            "documents": "tasks/{lab_task_id}/documents/{name}",
            "expected_deliverable": (
                f"tasks/{{lab_task_id}}/{EXPECTED_DELIVERABLE_NAME}"
            ),
            "task_descriptor": f"tasks/{{lab_task_id}}/{TASK_DESCRIPTOR_NAME}",
        },
    }


def solver_visible_layout(
    classified: ClassifiedHarveyLabTask,
    *,
    layout_id: str = SOLVER_VISIBLE_LAYOUT_ID,
    destination_prefix: str = "",
) -> MaterialSeparationLayout:
    """Return native or external solver/private layouts for the same artifacts."""

    prefix = destination_prefix.strip("/")
    solver = tuple(
        TaskArtifactProjection(
            item.artifact_id,
            _prefixed_destination(prefix, item.destination_path),
        )
        for item in classified.solver_artifacts
    )
    return MaterialSeparationLayout(
        layout_id=layout_id,
        solver_artifacts=solver,
        evaluator_private_artifacts=classified.evaluator_private_artifacts,
    )


def classify_harvey_lab_task(
    task_dir: Path,
    *,
    lab_root: Path,
    staging_root: Path,
) -> ClassifiedHarveyLabTask:
    """Split one LAB task into solver-visible staging bytes and private files."""

    task_json_path = task_dir / "task.json"
    documents_dir = task_dir / "documents"
    if not task_json_path.is_file() or task_json_path.is_symlink():
        raise HarveyLabProjectionError(
            f"Harvey LAB task is missing a regular task.json: {task_dir}"
        )
    if not documents_dir.is_dir() or documents_dir.is_symlink():
        raise HarveyLabProjectionError(
            f"Harvey LAB task is missing documents/: {task_dir}"
        )
    lab_task_id = _relative_posix(task_dir, lab_root / "tasks")
    task_record = cast(
        Mapping[str, object],
        read_json_object(
            task_json_path,
            error_factory=HarveyLabProjectionError,
            missing_message=lambda item: f"Harvey LAB task JSON does not exist: {item}",
            non_object_message=lambda item: (
                f"Harvey LAB task JSON must be an object: {item}"
            ),
        ),
    )
    instructions = _required_instructions(task_record)
    expected_deliverable = _required_expected_deliverable(task_record)
    category = lab_task_id.split("/", 1)[0]
    _reset_directory(staging_root)
    document_files = _regular_files(documents_dir)
    if not document_files:
        raise HarveyLabProjectionError(
            f"Harvey LAB task documents/ is empty: {documents_dir}"
        )
    solver_projections: list[TaskArtifactProjection] = []
    private_projections: list[TaskArtifactProjection] = []
    artifacts: list[ArtifactRecord] = []
    projected: list[HarveyLabProjectedFile] = []

    instructions_path = staging_root / INSTRUCTIONS_NAME
    _write_bytes(instructions_path, instructions.encode("utf-8"))
    artifacts.append(_artifact("instructions", instructions_path, staging_root))
    solver_projections.append(TaskArtifactProjection("instructions", INSTRUCTIONS_NAME))
    projected.append(_projected_file(instructions_path, staging_root, "instructions"))

    for document in document_files:
        relative = _relative_posix(document, documents_dir)
        if _is_private_filename(Path(relative).name):
            raise HarveyLabProjectionError(
                f"solver-visible documents/ contains private material: {relative}"
            )
        destination = staging_root / "documents" / relative
        _copy_regular_file(document, destination)
        artifact_id = f"document:{relative}"
        artifacts.append(_artifact(artifact_id, destination, staging_root))
        solver_projections.append(
            TaskArtifactProjection(artifact_id, f"documents/{relative}")
        )
        projected.append(_projected_file(destination, staging_root, "document"))

    expected_path = staging_root / EXPECTED_DELIVERABLE_NAME
    _write_bytes(expected_path, _canonical_json({"basename": expected_deliverable}))
    artifacts.append(_artifact("expected_deliverable", expected_path, staging_root))
    solver_projections.append(
        TaskArtifactProjection("expected_deliverable", EXPECTED_DELIVERABLE_NAME)
    )
    projected.append(
        _projected_file(expected_path, staging_root, "expected_deliverable")
    )

    private_files = _private_source_files(task_dir, task_json_path, documents_dir)
    staged_task_json = staging_root / "task.json"
    _copy_regular_file(task_json_path, staged_task_json)
    artifacts.append(_artifact("task_json", staged_task_json, staging_root))
    private_projections.append(TaskArtifactProjection("task_json", "task.json"))
    for private_path in private_files:
        relative = _relative_posix(private_path, task_dir)
        destination = staging_root / relative
        _copy_regular_file(private_path, destination)
        artifact_id = f"private:{relative}"
        artifacts.append(_artifact(artifact_id, destination, staging_root))
        private_projections.append(TaskArtifactProjection(artifact_id, relative))

    task_id = f"harvey_lab:{lab_task_id}"
    relative_path = f"tasks/{lab_task_id}"
    semantic_files = tuple(projected)
    task_sha256 = _record_sha256(
        [
            {
                "path": item.path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
                "role": item.role,
            }
            for item in semantic_files
            if item.role != "task_descriptor"
        ]
    )
    draft = HarveyLabProjectedTask(
        task_id=task_id,
        lab_task_id=lab_task_id,
        category=category,
        relative_path=relative_path,
        task_sha256=task_sha256,
        expected_deliverable=expected_deliverable,
        files=semantic_files,
    )
    descriptor_path = staging_root / TASK_DESCRIPTOR_NAME
    _write_bytes(descriptor_path, _canonical_json(draft.descriptor_record()))
    artifacts.append(_artifact("task_descriptor", descriptor_path, staging_root))
    solver_projections.append(
        TaskArtifactProjection("task_descriptor", TASK_DESCRIPTOR_NAME)
    )
    projected.append(_projected_file(descriptor_path, staging_root, "task_descriptor"))
    canonical = CanonicalTask(
        task_id=task_id,
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="harvey-lab",
        source_id=lab_task_id,
        task_sha256=task_sha256,
        metadata={
            "suite": "harvey_lab",
            "lab_task_id": lab_task_id,
            "category": category,
            "expected_deliverable": expected_deliverable,
        },
        artifacts=tuple(artifacts),
    )
    return ClassifiedHarveyLabTask(
        task=canonical,
        lab_task_id=lab_task_id,
        category=category,
        expected_deliverable=expected_deliverable,
        staging_root=staging_root,
        solver_artifacts=tuple(solver_projections),
        evaluator_private_artifacts=tuple(private_projections),
        projected_files=tuple(projected),
    )


def project_harvey_lab_suite(
    *,
    source_root: Path,
    solver_root: Path,
    evaluator_private_root: Path,
    pin: HarveyLabPin | None = None,
    lab_task_ids: Sequence[str] | None = None,
    limits: MaterializationLimits | None = None,
) -> HarveyLabProjectionResult:
    """Project solver-visible LAB bytes into a self-describing folder tree."""

    source = _existing_directory(source_root, "LAB source root")
    tasks_root = source / "tasks"
    if not tasks_root.is_dir():
        raise HarveyLabProjectionError(f"LAB root is missing tasks/: {tasks_root}")
    solver = _fresh_root(solver_root, "solver projection root")
    private = _fresh_root(evaluator_private_root, "evaluator-private root")
    _require_disjoint(solver, private)
    selected = None if lab_task_ids is None else frozenset(lab_task_ids)
    task_dirs = _discover_task_directories(tasks_root)
    if selected is not None:
        task_dirs = [
            path for path in task_dirs if _relative_posix(path, tasks_root) in selected
        ]
    if not task_dirs:
        raise HarveyLabProjectionError("no Harvey LAB tasks matched the projection")
    applied_pin = pin or issue_196_pin()
    projected_tasks: list[HarveyLabTaskProjection] = []
    for task_dir in task_dirs:
        lab_task_id = _relative_posix(task_dir, tasks_root)
        staging = solver.parent / f".harvey-lab-staging-{_safe_token(lab_task_id)}"
        try:
            classified = classify_harvey_lab_task(
                task_dir,
                lab_root=source,
                staging_root=staging,
            )
            solver_dest = solver / "tasks" / lab_task_id
            private_dest = private / "tasks" / lab_task_id
            _ensure_parent_directory(solver_dest)
            _ensure_parent_directory(private_dest)
            try:
                materialization = materialize_separated_task(
                    classified.task,
                    source_root=classified.staging_root,
                    solver_root=solver_dest,
                    evaluator_private_root=private_dest,
                    layout=solver_visible_layout(classified),
                    limits=limits,
                )
            except (MaterialSeparationError, TaskMaterializationError) as exc:
                raise HarveyLabProjectionError(str(exc)) from exc
            record = HarveyLabProjectedTask(
                task_id=classified.task.task_id,
                lab_task_id=classified.lab_task_id,
                category=classified.category,
                relative_path=f"tasks/{classified.lab_task_id}",
                task_sha256=classified.task.task_sha256,
                expected_deliverable=classified.expected_deliverable,
                files=classified.projected_files,
            )
            projected_tasks.append(
                HarveyLabTaskProjection(
                    record=record,
                    materialization=materialization,
                )
            )
        finally:
            _remove_tree(staging)
    manifest = _write_root_manifest(
        solver,
        pin=applied_pin,
        tasks=tuple(item.record for item in projected_tasks),
    )
    scan_projection_for_private_markers(solver)
    _require_disjoint(solver, private)
    return HarveyLabProjectionResult(
        solver_root=solver,
        evaluator_private_root=private,
        manifest=manifest,
        tasks=tuple(projected_tasks),
    )


def load_harvey_lab_projection_manifest(
    projection_root: Path,
) -> HarveyLabProjectionManifest:
    """Load and authenticate the self-describing projection index."""

    return _manifest_from_root(projection_root)


def verify_harvey_lab_projection(projection_root: Path) -> HarveyLabProjectionManifest:
    """Re-hash every listed solver-visible file against the projection manifest."""

    manifest = _manifest_from_root(projection_root)
    root = projection_root.resolve()
    listed = {ROOT_MANIFEST_NAME}
    for task in manifest.tasks:
        task_root = root / task.relative_path
        for item in task.files:
            relative = f"{task.relative_path}/{item.path}"
            listed.add(relative)
            path = task_root / item.path
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise HarveyLabProjectionError(
                    f"projected file is missing: {relative}"
                ) from exc
            digest = hashlib.sha256(payload).hexdigest()
            if digest != item.sha256:
                raise HarveyLabProjectionError(
                    f"projected file hash mismatch: {relative}"
                )
            if len(payload) != item.size_bytes:
                raise HarveyLabProjectionError(
                    f"projected file size mismatch: {relative}"
                )
        descriptor_path = task_root / TASK_DESCRIPTOR_NAME
        try:
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarveyLabProjectionError(
                f"task descriptor is missing or invalid: {task.relative_path}"
            ) from exc
        if not isinstance(descriptor, dict):
            raise HarveyLabProjectionError(
                f"task descriptor must be a JSON object: {task.relative_path}"
            )
        typed_descriptor = cast(Mapping[str, object], descriptor)
        if typed_descriptor.get("task_sha256") != task.task_sha256:
            raise HarveyLabProjectionError(
                f"task descriptor task_sha256 diverges from root manifest: "
                f"{task.relative_path}"
            )
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative not in listed:
            raise HarveyLabProjectionError(
                f"unlisted file in solver projection: {relative}"
            )
    scan_projection_for_private_markers(projection_root)
    return manifest


def scan_projection_for_private_markers(projection_root: Path) -> None:
    """Fail closed if evaluator-private markers appear in the solver tree."""

    root = _existing_directory(projection_root, "projection root")
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if _is_private_filename(path.name):
            hits.append(relative)
            continue
        payload = path.read_bytes()
        text_scan = path.suffix.casefold() in _TEXT_SUFFIXES or b"\0" not in payload
        if not text_scan:
            continue
        for marker in PRIVATE_CONTENT_MARKERS:
            if marker.encode("utf-8") in payload:
                hits.append(f"{relative} ({marker})")
    if hits:
        joined = ", ".join(hits)
        raise HarveyLabProjectionError(
            f"evaluator-private material present in solver projection: {joined}"
        )


def _manifest_from_root(projection_root: Path) -> HarveyLabProjectionManifest:
    path = projection_root / ROOT_MANIFEST_NAME
    record = read_json_object(
        path,
        error_factory=HarveyLabProjectionError,
        missing_message=lambda item: f"projection manifest does not exist: {item}",
        non_object_message=lambda item: (
            f"projection manifest must be a JSON object: {item}"
        ),
    )
    return _manifest_from_record(cast(Mapping[str, object], record))


def _manifest_from_record(record: Mapping[str, object]) -> HarveyLabProjectionManifest:
    try:
        require_known_fields(
            record,
            required=_MANIFEST_REQUIRED_FIELDS,
            field_name="projection manifest",
        )
    except MultiHarnessValidationError as exc:
        raise HarveyLabProjectionError(str(exc)) from exc
    schema = record.get("schema_version")
    if schema != PROJECTION_SCHEMA_VERSION:
        raise HarveyLabProjectionError("unsupported projection schema_version")
    layout_id = _required_str(record, "layout_id")
    if layout_id != SOLVER_VISIBLE_LAYOUT_ID:
        raise HarveyLabProjectionError("layout_id must be harvey-lab-solver-visible.v1")
    pin_record = _as_object_map(record.get("pin"), "pin")
    try:
        require_known_fields(
            pin_record,
            required=_PIN_REQUIRED_FIELDS,
            field_name="pin",
        )
    except MultiHarnessValidationError as exc:
        raise HarveyLabProjectionError(str(exc)) from exc
    pin = HarveyLabPin(
        repository=_required_str(pin_record, "repository"),
        commit=_required_str(pin_record, "commit"),
        tree=_required_str(pin_record, "tree"),
    )
    layout_map = _layout_map_from_record(record.get("layout_map"))
    tasks_value = record.get("tasks")
    if not isinstance(tasks_value, list) or not tasks_value:
        raise HarveyLabProjectionError("tasks must be a non-empty array")
    tasks = tuple(_task_from_record(item) for item in cast(list[object], tasks_value))
    content = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "layout_id": layout_id,
        "pin": pin.to_record(),
        "layout_map": layout_map,
        "tasks": [task.to_record() for task in tasks],
    }
    expected = _record_sha256(content)
    actual = _required_str(record, "manifest_sha256")
    validate_sha256(actual, "manifest_sha256", allow_prefix=False)
    if actual != expected:
        raise HarveyLabProjectionError("manifest_sha256 does not match content")
    manifest = HarveyLabProjectionManifest(
        layout_id=layout_id,
        pin=pin,
        layout_map=layout_map,
        tasks=tasks,
        manifest_sha256=actual,
    )
    validate_public_record(manifest.to_record(), "harvey lab projection manifest")
    return manifest


def _task_from_record(value: object) -> HarveyLabProjectedTask:
    record = _as_object_map(value, "projection task")
    try:
        require_known_fields(
            record,
            required=_TASK_REQUIRED_FIELDS,
            field_name="projected task",
        )
    except MultiHarnessValidationError as exc:
        raise HarveyLabProjectionError(str(exc)) from exc
    files_value = record.get("files")
    if not isinstance(files_value, list) or not files_value:
        raise HarveyLabProjectionError(
            "projection task files must be a non-empty array"
        )
    files = tuple(_file_from_record(item) for item in cast(list[object], files_value))
    return HarveyLabProjectedTask(
        task_id=_required_str(record, "task_id"),
        lab_task_id=_required_str(record, "lab_task_id"),
        category=_required_str(record, "category"),
        relative_path=validate_safe_relative_path(
            _required_str(record, "relative_path"),
            "relative_path",
        ),
        task_sha256=_required_str(record, "task_sha256"),
        expected_deliverable=_required_str(record, "expected_deliverable"),
        files=files,
    )


def _file_from_record(value: object) -> HarveyLabProjectedFile:
    record = _as_object_map(value, "projection file")
    try:
        require_known_fields(
            record,
            required=_FILE_REQUIRED_FIELDS,
            field_name="projected file",
        )
    except MultiHarnessValidationError as extra:
        raise HarveyLabProjectionError(str(extra)) from extra
    path = validate_safe_relative_path(_required_str(record, "path"), "path")
    digest = _required_str(record, "sha256")
    validate_sha256(digest, "sha256", allow_prefix=False)
    size = record.get("size_bytes")
    if type(size) is not int or size < 0:
        raise HarveyLabProjectionError("size_bytes must be a non-negative integer")
    return HarveyLabProjectedFile(
        path=path,
        sha256=digest,
        size_bytes=size,
        role=_required_str(record, "role"),
    )


def _write_root_manifest(
    solver_root: Path,
    *,
    pin: HarveyLabPin,
    tasks: tuple[HarveyLabProjectedTask, ...],
) -> HarveyLabProjectionManifest:
    layout_map = harvey_lab_layout_map()
    content = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "layout_id": SOLVER_VISIBLE_LAYOUT_ID,
        "pin": pin.to_record(),
        "layout_map": layout_map,
        "tasks": [task.to_record() for task in tasks],
    }
    manifest = HarveyLabProjectionManifest(
        layout_id=SOLVER_VISIBLE_LAYOUT_ID,
        pin=pin,
        layout_map=layout_map,
        tasks=tasks,
        manifest_sha256=_record_sha256(content),
    )
    validate_public_record(manifest.to_record(), "harvey lab projection manifest")
    write_json_object(solver_root / ROOT_MANIFEST_NAME, manifest.to_record())
    return manifest


def _discover_task_directories(tasks_root: Path) -> list[Path]:
    found = [
        path.parent
        for path in sorted(tasks_root.rglob("task.json"))
        if path.is_file() and not path.is_symlink()
    ]
    if not found:
        raise HarveyLabProjectionError(
            f"Harvey LAB tasks directory has no task.json files: {tasks_root}"
        )
    return found


def _private_source_files(
    task_dir: Path,
    task_json_path: Path,
    documents_dir: Path,
) -> tuple[Path, ...]:
    extras: list[Path] = []
    for path in sorted(task_dir.iterdir()):
        if path in {task_json_path, documents_dir}:
            continue
        if path.is_symlink():
            raise HarveyLabProjectionError(
                f"Harvey LAB task contains a symlink: {path.name}"
            )
        if path.is_dir():
            raise HarveyLabProjectionError(
                f"Harvey LAB task contains an unexpected directory: {path.name}"
            )
        if not path.is_file():
            raise HarveyLabProjectionError(
                f"Harvey LAB task contains an unsupported entry: {path.name}"
            )
        if _is_private_filename(path.name):
            extras.append(path)
            continue
        raise HarveyLabProjectionError(
            f"unclassified Harvey LAB source file: {path.name}"
        )
    return tuple(extras)


def _required_instructions(record: Mapping[str, object]) -> str:
    for field_name in ("instructions", "prompt", "instruction"):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    raise HarveyLabProjectionError("task.json is missing solver-visible instructions")


def _required_expected_deliverable(record: Mapping[str, object]) -> str:
    for field_name in (
        "expected_deliverable",
        "expected_output",
        "output_file",
        "deliverable",
    ):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return Path(value).name
    output = record.get("output")
    if isinstance(output, str) and output.strip():
        return Path(output).name
    raise HarveyLabProjectionError(
        "task.json is missing the expected deliverable basename"
    )


def _is_private_filename(name: str) -> bool:
    lowered = name.casefold()
    if lowered in _PRIVATE_FILENAMES:
        return True
    return lowered.startswith("gold-") or lowered.startswith("gold_")


def _regular_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise HarveyLabProjectionError(
                f"Harvey LAB documents/ must not contain symlinks: {path.name}"
            )
        if path.is_file():
            files.append(path)
    return tuple(files)


def _copy_regular_file(source: Path, destination: Path) -> None:
    source_stat = source.lstat()
    if source.is_symlink() or not stat.S_ISREG(source_stat.st_mode):
        raise HarveyLabProjectionError(
            f"Harvey LAB source must be a regular file: {source.name}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(destination, source.read_bytes())


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _artifact(artifact_id: str, path: Path, root: Path) -> ArtifactRecord:
    payload = path.read_bytes()
    return ArtifactRecord(
        artifact_id=artifact_id,
        path=_relative_posix(path, root),
        sha256=hashlib.sha256(payload).hexdigest(),
        media_type="application/octet-stream",
        size_bytes=len(payload),
    )


def _projected_file(
    path: Path,
    root: Path,
    role: str,
) -> HarveyLabProjectedFile:
    payload = path.read_bytes()
    return HarveyLabProjectedFile(
        path=_relative_posix(path, root),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        role=role,
    )


def _prefixed_destination(prefix: str, destination: str) -> str:
    if not prefix:
        return destination
    return f"{prefix}/{destination}"


def _existing_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise HarveyLabProjectionError(f"{label} must be a real directory")
    return path.resolve()


def _fresh_root(path: Path, label: str) -> Path:
    if path.exists() or path.is_symlink():
        raise HarveyLabProjectionError(f"{label} must be a fresh, absent path")
    path.mkdir(parents=True)
    if path.is_symlink() or not path.is_dir():
        raise HarveyLabProjectionError(f"{label} must be a real directory")
    return path.resolve()


def _ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise HarveyLabProjectionError(
            "projection destination parent is not a directory"
        )


def _reset_directory(path: Path) -> None:
    _remove_tree(path)
    path.mkdir(parents=True)


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.exists():
        return
    for child in sorted(path.iterdir(), reverse=True):
        _remove_tree(child)
    path.rmdir()


def _require_disjoint(first: Path, second: Path) -> None:
    left = first.resolve(strict=False)
    right = second.resolve(strict=False)
    if left == right or left.is_relative_to(right) or right.is_relative_to(left):
        raise HarveyLabProjectionError(
            "solver-visible and evaluator-private roots must be disjoint"
        )


def _relative_posix(path: Path, root: Path) -> str:
    return validate_safe_relative_path(path.relative_to(root).as_posix(), "path")


def _require_git_sha(value: str, field_name: str) -> None:
    if len(value) != _GIT_SHA_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise HarveyLabProjectionError(
            f"{field_name} must be a lowercase 40-character Git SHA"
        )


def _require_https_repository(value: str) -> None:
    if not value.startswith("https://") or "@" in value or " " in value:
        raise HarveyLabProjectionError(
            "upstream repository must be a canonical HTTPS URL"
        )


def _as_object_map(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise HarveyLabProjectionError(f"{field_name} must be an object")
    return cast(Mapping[str, object], value)


def _layout_map_from_record(value: object) -> dict[str, dict[str, str]]:
    record = _as_object_map(value, "layout_map")
    layout_map: dict[str, dict[str, str]] = {}
    for name, mapping in record.items():
        inner = _as_object_map(mapping, f"layout_map.{name}")
        layout_map[str(name)] = {
            str(key): _require_layout_value(key, item) for key, item in inner.items()
        }
    if not layout_map:
        raise HarveyLabProjectionError("layout_map must be a non-empty object")
    return layout_map


def _require_layout_value(key: object, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise HarveyLabProjectionError(f"layout_map.{key} must be a non-empty string")
    return value


def _required_str(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HarveyLabProjectionError(f"{field_name} must be a non-empty string")
    return value


def _safe_token(value: str) -> str:
    return value.replace("/", "-")


def _canonical_json(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


# contract-ratchet: allow non-persisted projection content hash
def _record_sha256(record: object) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
