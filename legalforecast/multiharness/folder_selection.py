"""Folder-mode task selection over a verified Harvey LAB projection.

The projection verifier owns byte authentication. Folder selection only maps
its authenticated task records to the canonical index and optionally narrows
the result to a directory inside the projected tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast.multiharness.harvey_lab_projection import (
    ROOT_MANIFEST_NAME,
    HarveyLabProjectedTask,
    HarveyLabProjectionError,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex


class FolderSelectionError(ValueError):
    """The folder is not a verified projected layout, or its bytes drifted."""


@dataclass(frozen=True, slots=True)
class FolderTaskRef:
    """One projected task the folder resolved to, in public-safe fields only."""

    task_id: str
    relative_path: str
    task_sha256: str
    family: str
    scoring_mode: str
    category: str | None = None

    def to_public_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "task_id": self.task_id,
            "relative_path": self.relative_path,
            "task_sha256": self.task_sha256,
            "family": self.family,
            "scoring_mode": self.scoring_mode,
        }
        if self.category is not None:
            record["category"] = self.category
        return record


@dataclass(frozen=True, slots=True)
class FolderSelection:
    """Resolved folder selection with public-safe provenance only."""

    task_ids: tuple[str, ...]
    tasks: tuple[CanonicalTask, ...]
    refs: tuple[FolderTaskRef, ...]
    subtree: str = ""
    selection_method: str = "folder"

    def to_public_record(self) -> dict[str, Any]:
        return {
            "selection_method": self.selection_method,
            "subtree": self.subtree,
            "task_ids": list(self.task_ids),
            "tasks": [ref.to_public_record() for ref in self.refs],
        }


def projection_root_for(folder: Path) -> Path:
    """Return the projected-layout root that owns ``folder``."""

    if not folder.is_dir():
        raise FolderSelectionError(f"task folder does not exist: {folder.name}")
    candidate = folder.resolve()
    while True:
        if (candidate / ROOT_MANIFEST_NAME).is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            raise FolderSelectionError(
                "folder mode requires a projected Harvey LAB layout: no "
                f"{ROOT_MANIFEST_NAME} in {folder.name} or any parent directory. "
                "Run `multiharness tasks project` and point --task-folder at the "
                "projected tree, or at one category directory inside it."
            )
        candidate = parent


def select_tasks_from_folder(
    folder: Path,
    task_index: TaskIndex,
) -> FolderSelection:
    """Resolve a projected folder against a canonical index, fail-closed."""

    root = projection_root_for(folder)
    subtree = _subtree_prefix(folder.resolve(), root)
    try:
        manifest = verify_harvey_lab_projection(root)
    except HarveyLabProjectionError as exc:
        raise FolderSelectionError(str(exc)) from exc

    index_by_id = {task.task_id: task for task in task_index.tasks}
    refs: list[FolderTaskRef] = []
    selected: list[CanonicalTask] = []
    for record in manifest.tasks:
        if not _within_subtree(record.relative_path, subtree):
            continue
        indexed = _indexed_task(record, index_by_id)
        refs.append(
            FolderTaskRef(
                task_id=record.task_id,
                relative_path=record.relative_path,
                task_sha256=record.task_sha256,
                family=indexed.family,
                scoring_mode=indexed.scoring_mode,
                category=record.category,
            )
        )
        selected.append(indexed)
    if not refs:
        raise FolderSelectionError(
            f"folder mode matched no projected tasks under {subtree or '.'}; "
            f"the projection lists {len(manifest.tasks)} task(s)"
        )
    return FolderSelection(
        task_ids=tuple(ref.task_id for ref in refs),
        tasks=tuple(selected),
        refs=tuple(refs),
        subtree=subtree,
    )


def _indexed_task(
    record: HarveyLabProjectedTask,
    index_by_id: dict[str, CanonicalTask],
) -> CanonicalTask:
    indexed = index_by_id.get(record.task_id)
    if indexed is None:
        raise FolderSelectionError(
            f"folder task {record.task_id} is not in the task index; "
            "index the same projected root the folder belongs to"
        )
    if _normalize_digest(indexed.task_sha256) != _normalize_digest(record.task_sha256):
        raise FolderSelectionError(
            f"folder task {record.task_id} bytes do not match the task index; "
            "refusing tampered or unrecognized content"
        )
    return indexed


def _subtree_prefix(folder: Path, root: Path) -> str:
    relative = folder.relative_to(root).as_posix()
    return "" if relative == "." else relative


def _within_subtree(relative_path: str, subtree: str) -> bool:
    if not subtree:
        return True
    return relative_path == subtree or relative_path.startswith(f"{subtree}/")


def _normalize_digest(value: str) -> str:
    return value.removeprefix("sha256:")
