"""Canonical task index over an authenticated projected Harvey LAB layout.

``tasks index --suite harvey-lab --lab-root`` reads ``tasks/<id>/task.json``,
which a projection deliberately keeps evaluator-private because it carries the
gold ``criteria``. A contributor therefore had no way to turn the one layout
they are allowed to consume into a task index (GitHub #844).

This module closes that gap. It delegates authentication to
``verify_harvey_lab_projection`` — which already re-hashes every listed
solver-visible file and refuses unlisted ones — and builds canonical tasks
straight from the manifest records, so the index, the projected bytes, and the
``task_sha256`` that flows into receipts agree by construction rather than by a
second implementation of the same hashing.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabProjectedFile,
    HarveyLabProjectedTask,
    HarveyLabProjectionManifest,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask, TaskIndex
from legalforecast.multiharness.task_loaders import task_index_sha256
from legalforecast.multiharness.validation import (
    validate_safe_relative_path,
    validate_unique_ids,
)

DEFAULT_PROJECTED_SUITE_VERSION = "harvey-lab"


def canonical_task_from_projection(
    record: HarveyLabProjectedTask,
    manifest: HarveyLabProjectionManifest,
    *,
    suite_version: str = DEFAULT_PROJECTED_SUITE_VERSION,
) -> CanonicalTask:
    """Derive one canonical task from authenticated projection data."""

    if not suite_version.strip():
        raise ValueError("suite_version must be non-empty")
    documents = tuple(item for item in record.files if item.role == "document")
    metadata: dict[str, Any] = {
        "suite": "harvey_lab",
        "lab_task_id": record.lab_task_id,
        "lab_task_path": record.relative_path,
        "lab_commit": manifest.pin.commit,
        # `module` is what --category/--module matches on; `category` mirrors
        # the projection manifest's own field name.
        "module": record.category,
        "practice_area": record.category,
        "category": record.category,
        "expected_deliverable": record.expected_deliverable,
        "projected_layout_id": manifest.layout_id,
        # `document_hashes` keyed by document filename is the shape the raw
        # LAB loader publishes, and the only one the public-record secret
        # scanner exempts from its filename-looks-like-a-credential rule.
        "document_hashes": {
            item.path.removeprefix("documents/"): item.sha256 for item in documents
        },
        "document_count": len(documents),
    }
    return CanonicalTask(
        task_id=record.task_id,
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version=suite_version,
        source_id=record.lab_task_id,
        task_sha256=record.task_sha256,
        metadata=metadata,
        artifacts=tuple(
            _artifact(item, task_relative_path=record.relative_path)
            for item in record.files
        ),
    )


class HarveyLabProjectionTaskLoader:
    """Load an authenticated projected LAB layout into canonical tasks."""

    def __init__(
        self,
        projection_root: Path,
        *,
        suite_version: str = DEFAULT_PROJECTED_SUITE_VERSION,
    ) -> None:
        if not suite_version.strip():
            raise ValueError("suite_version must be non-empty")
        self.projection_root = projection_root
        self.suite_version = suite_version

    def load_task_index(
        self,
        *,
        index_id: str = "harvey-lab",
        selection_namespace: str = "harvey_lab",
    ) -> TaskIndex:
        if not self.projection_root.is_dir():
            raise ValueError(
                f"projected Harvey LAB root does not exist: {self.projection_root}"
            )
        manifest = verify_harvey_lab_projection(self.projection_root)
        tasks = tuple(
            canonical_task_from_projection(
                record,
                manifest,
                suite_version=self.suite_version,
            )
            for record in manifest.tasks
        )
        validate_unique_ids((task.task_id for task in tasks), "tasks")
        return TaskIndex(
            index_id=index_id,
            selection_namespace=selection_namespace,
            tasks=tasks,
            index_sha256=task_index_sha256(tasks),
        )


def _artifact(
    item: HarveyLabProjectedFile,
    *,
    task_relative_path: str,
) -> ArtifactRecord:
    relative_path = f"{task_relative_path}/{item.path}"
    media_type = (
        mimetypes.guess_type(Path(item.path).name)[0] or "application/octet-stream"
    )
    return ArtifactRecord(
        artifact_id=_artifact_id(item.role, item.path),
        path=validate_safe_relative_path(relative_path, "path"),
        sha256=item.sha256,
        media_type=media_type,
        public=False,
        size_bytes=item.size_bytes,
    )


def _artifact_id(role: str, path: str) -> str:
    """Mirror the ids the projector assigned when it classified the task."""

    if role == "document":
        return f"document:{path.removeprefix('documents/')}"
    return role
