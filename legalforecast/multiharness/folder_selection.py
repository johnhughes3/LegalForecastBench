"""Folder-mode task selection from a self-describing projected layout.

Lane W3 (``LegalForecastBench-dm0g.4.3.2``) owns the Harvey LAB projection.
This module consumes the projected layout's manifest and fail-closes on
unrecognized or tampered bytes. Absolute folder paths never enter public
records.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex
from legalforecast.multiharness.validation import (
    require_schema_version,
    require_sequence,
    require_str,
    validate_safe_relative_path,
    validate_sha256,
)

PROJECTED_LAYOUT_MANIFEST_NAME = "projection-manifest.json"
PROJECTED_LAYOUT_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative projected-layout sidecar
    "legalforecast.multiharness.projected_task_layout.v1"
)
_TASK_FILE_NAMES = frozenset({"task.json", "task.md", "prompt.txt"})


class FolderSelectionError(ValueError):
    """The folder is not a verified projected layout, or its bytes drifted."""


@dataclass(frozen=True, slots=True)
class FolderTaskRef:
    """One projected task listed by the folder manifest."""

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
    selection_method: str = "folder"

    def to_public_record(self) -> dict[str, Any]:
        return {
            "selection_method": self.selection_method,
            "task_ids": list(self.task_ids),
            "tasks": [ref.to_public_record() for ref in self.refs],
        }


def select_tasks_from_folder(
    folder: Path,
    task_index: TaskIndex,
) -> FolderSelection:
    """Resolve a projected folder against a canonical index, fail-closed."""

    if not folder.is_dir():
        raise FolderSelectionError(f"task folder does not exist: {folder.name}")
    manifest_path = folder / PROJECTED_LAYOUT_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FolderSelectionError(
            "folder mode requires projection-manifest.json; "
            "unrecognized layouts are refused"
        )
    record = read_json_object(
        manifest_path,
        error_factory=FolderSelectionError,
        missing_message=lambda item: f"projection manifest does not exist: {item}",
        non_object_message=lambda item: (
            f"projection manifest must be a JSON object: {item}"
        ),
    )
    try:
        require_schema_version(record, PROJECTED_LAYOUT_SCHEMA_VERSION)
        raw_tasks = require_sequence(record, "tasks")
    except ValueError as exc:
        raise FolderSelectionError(str(exc)) from exc
    if not raw_tasks:
        raise FolderSelectionError("projection manifest lists no tasks")

    refs = tuple(_parse_task_ref(item, index) for index, item in enumerate(raw_tasks))
    listed_paths = {ref.relative_path for ref in refs}
    _refuse_unlisted_task_files(folder, listed_paths)
    index_by_id = {task.task_id: task for task in task_index.tasks}
    selected: list[CanonicalTask] = []
    for ref in refs:
        _verify_task_bytes(folder, ref)
        indexed = index_by_id.get(ref.task_id)
        if indexed is None:
            raise FolderSelectionError(
                f"folder task {ref.task_id} is not in the task index"
            )
        if _normalize_digest(indexed.task_sha256) != _normalize_digest(ref.task_sha256):
            raise FolderSelectionError(
                f"folder task {ref.task_id} bytes do not match the task index; "
                "refusing tampered or unrecognized content"
            )
        selected.append(indexed)
    return FolderSelection(
        task_ids=tuple(ref.task_id for ref in refs),
        tasks=tuple(selected),
        refs=refs,
    )


def _parse_task_ref(record: object, index: int) -> FolderTaskRef:
    if not isinstance(record, Mapping):
        raise FolderSelectionError(
            f"projection manifest tasks[{index}] must be an object"
        )
    payload = cast(Mapping[str, Any], record)
    try:
        relative_path = validate_safe_relative_path(
            require_str(payload, "relative_path"),
            "relative_path",
        )
        task_sha256 = require_str(payload, "task_sha256")
        validate_sha256(task_sha256, "task_sha256", allow_prefix=True)
        raw_category = payload.get("category")
        category: str | None
        if raw_category is None:
            category = None
        elif isinstance(raw_category, str) and raw_category.strip():
            category = raw_category
        else:
            raise FolderSelectionError("category must be a non-empty string")
        return FolderTaskRef(
            task_id=require_str(payload, "task_id"),
            relative_path=relative_path,
            task_sha256=task_sha256,
            family=require_str(payload, "family"),
            scoring_mode=require_str(payload, "scoring_mode"),
            category=category,
        )
    except ValueError as exc:
        raise FolderSelectionError(str(exc)) from exc


def _verify_task_bytes(folder: Path, ref: FolderTaskRef) -> None:
    path = folder / ref.relative_path
    if not path.is_file():
        raise FolderSelectionError(
            f"projected task file is missing: {ref.relative_path}"
        )
    digest = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    if _normalize_digest(digest) != _normalize_digest(ref.task_sha256):
        raise FolderSelectionError(
            f"folder task {ref.task_id} bytes do not match the projection manifest; "
            "refusing tampered or unrecognized content"
        )


def _refuse_unlisted_task_files(folder: Path, listed_paths: set[str]) -> None:
    extras: list[str] = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.name == PROJECTED_LAYOUT_MANIFEST_NAME:
            continue
        relative = path.relative_to(folder).as_posix()
        if relative in listed_paths:
            continue
        if path.name in _TASK_FILE_NAMES or relative.endswith("/task.json"):
            extras.append(relative)
    if extras:
        extra_list = ", ".join(sorted(extras))
        raise FolderSelectionError(
            "folder contains unrecognized task files not listed in the "
            f"projection manifest: {extra_list}"
        )


def _normalize_digest(value: str) -> str:
    return value.removeprefix("sha256:")
