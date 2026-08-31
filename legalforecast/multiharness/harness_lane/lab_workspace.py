"""Stage one projected Harvey LAB task into a container's workspace.

The LAB corpus reaches this lane only through a *projection*: a tree whose
bytes ``verify_harvey_lab_projection`` re-hashes and which carries none of the
evaluator's gold ``criteria``.  A raw LAB clone is not an input here, and there
is deliberately no parameter that would let one become one.

Unlike the LFB path there is no private solver-input store to read from -- the
store's file set is closed at ``{prompt.txt, source packet}`` and a LAB task is
a directory of documents.  So the task's own ``instructions`` artifact is the
prompt and its documents are copied in beside it, through the repository's own
``materialize_task``: it classifies every canonical artifact exactly once as
solver-visible or evaluator-private, verifies each copy against the digest and
size the indexed task declared, and refuses a destination that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.immutable_io import ImmutableIOError, read_single_link_file
from legalforecast.multiharness.materialization import (
    TaskArtifactProjection,
    TaskMaterializationError,
    TaskMaterializationLayout,
    materialize_task,
)
from legalforecast.multiharness.spec import CanonicalTask

INSTRUCTIONS_ARTIFACT_ID: Final = "instructions"
# A materialization layout name, not a persisted record schema: it must carry a
# ``.vN`` suffix, and the manifest it produces is returned, never written.
LAB_WORKSPACE_LAYOUT_ID: Final = (
    # contract-ratchet: allow non-persisted materialization layout name
    "legalforecast.harness-lane.lab-workspace.v1"
)
# The descriptor is the projection's own index of the task, not task content;
# staging it would put a manifest of the corpus in front of the solver.
EVALUATOR_PRIVATE_ARTIFACT_IDS: Final = ("task_descriptor",)


class LabWorkspaceError(ValueError):
    """Raised when a projected LAB task cannot be staged for a harness."""


@dataclass(frozen=True, slots=True)
class StagedLabTask:
    """What the harness will see, and the prompt it was handed."""

    prompt: str
    staged_paths: tuple[str, ...]


def stage_projected_lab_task(
    task: CanonicalTask,
    *,
    projection_root: Path,
    destination: Path,
) -> StagedLabTask:
    """Copy a projected task's solver-visible bytes in and return its prompt."""

    layout = _layout(task)
    try:
        manifest = materialize_task(
            task,
            source_root=projection_root,
            destination_root=destination,
            layout=layout,
        )
    except TaskMaterializationError as exc:
        raise LabWorkspaceError(
            f"could not stage projected Harvey LAB task {task.task_id}: {exc}"
        ) from exc
    entries = {entry.artifact_id: entry for entry in manifest.entries}
    instructions = entries.get(INSTRUCTIONS_ARTIFACT_ID)
    if instructions is None:
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} has no "
            f"{INSTRUCTIONS_ARTIFACT_ID!r} artifact to use as the prompt"
        )
    prompt = _prompt_text(destination / instructions.destination_path)
    if not prompt.strip():
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} has an empty prompt"
        )
    return StagedLabTask(
        prompt=prompt,
        staged_paths=tuple(
            sorted(entry.destination_path for entry in manifest.entries)
        ),
    )


def _layout(task: CanonicalTask) -> TaskMaterializationLayout:
    if not task.artifacts:
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} carries no artifacts; "
            "run `multiharness tasks project` and index the projected root"
        )
    prefix = _task_prefix(task)
    return TaskMaterializationLayout(
        layout_id=LAB_WORKSPACE_LAYOUT_ID,
        solver_artifacts=tuple(
            TaskArtifactProjection(
                artifact.artifact_id,
                artifact.path.removeprefix(prefix),
            )
            for artifact in task.artifacts
            if artifact.artifact_id not in EVALUATOR_PRIVATE_ARTIFACT_IDS
        ),
        evaluator_private_artifact_ids=tuple(
            artifact.artifact_id
            for artifact in task.artifacts
            if artifact.artifact_id in EVALUATOR_PRIVATE_ARTIFACT_IDS
        ),
    )


def _task_prefix(task: CanonicalTask) -> str:
    value = task.metadata.get("lab_task_path")
    if not isinstance(value, str) or not value.strip():
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} has no lab_task_path; "
            "the projection manifest names the task directory every artifact "
            "path is relative to"
        )
    return f"{value.rstrip('/')}/"


def _prompt_text(path: Path) -> str:
    try:
        payload = read_single_link_file(path, label="projected LAB instructions")
    except ImmutableIOError as exc:
        raise LabWorkspaceError("staged LAB instructions are unreadable") from exc
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LabWorkspaceError("LAB instructions must be strict UTF-8") from exc
