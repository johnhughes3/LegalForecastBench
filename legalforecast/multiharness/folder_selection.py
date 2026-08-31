"""Folder-mode task selection over a real projected Harvey LAB layout.

Folder mode used to demand a ``projection-manifest.json`` sidecar that nothing
ever wrote: ``tasks project`` emits ``harvey-lab-projection.v1.json``, whose
``relative_path`` names a task *directory* and whose ``task_sha256`` is a record
hash rather than a file hash, and which carries neither ``family`` nor
``scoring_mode``. The two contracts could not meet, so folder mode had never
consumed a real projection (GitHub #845).

This module now delegates authentication to ``verify_harvey_lab_projection``,
which already re-hashes every listed solver-visible file, refuses unlisted ones,
and scans for evaluator-private markers — so there is exactly one implementation
of "are these bytes the projection they claim to be". ``family`` and
``scoring_mode`` are derived from the canonical index rather than restated in a
second file, and ``task_sha256`` is carried through from the projection manifest
unchanged.

A folder may be the projection root or any directory inside it, which is what
makes "run this category" a single argument. Absolute folder paths never enter
public records.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from legalforecast.multiharness.harvey_lab_projection import (
    ROOT_MANIFEST_NAME,
    HarveyLabProjectedTask,
    HarveyLabProjectionError,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.selection import TaskSelection
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
    """Return the projected-layout root that owns ``folder``.

    ``folder`` may be the root itself or any directory beneath it, so a caller
    can name one category directory and still get an authenticated layout.
    """

    if not folder.is_dir():
        raise FolderSelectionError(f"task folder does not exist: {folder.name}")
    candidate = folder.resolve()
    while True:
        if (candidate / ROOT_MANIFEST_NAME).is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            raise FolderSelectionError(
                f"folder mode requires a projected Harvey LAB layout: no "
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


def narrow_selection_to_folder(
    selection: TaskSelection,
    task_index: TaskIndex,
    folder: Path | None,
) -> tuple[TaskSelection, FolderSelection | None]:
    """Intersect ``selection`` with a folder's authenticated task ids."""

    if folder is None:
        return selection, None
    resolved = select_tasks_from_folder(folder, task_index)
    task_ids = resolved.task_ids
    if selection.task_ids:
        allowed = set(selection.task_ids)
        task_ids = tuple(task_id for task_id in task_ids if task_id in allowed)
    if not task_ids:
        raise FolderSelectionError(
            "folder mode matched no tasks after applying --task-id filters"
        )
    narrowed = replace(
        selection,
        task_ids=task_ids,
        label=selection.label or "folder",
    )
    return narrowed, resolved


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
