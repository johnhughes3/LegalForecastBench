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

Two things are added to what the projection alone provides, and both are what
makes the LAB leg scoreable rather than merely runnable.  ``output/`` is
created before the harness starts, because :func:`discover_harvey_lab_outputs`
requires the solver's output directory to resolve strictly inside its sandbox
and refuses the layout afterwards otherwise -- by which point the harness has
already written somewhere.  And the prompt names the expected deliverable and
that directory, because a projected ``instructions`` file describes the legal
task, not this lane's file layout: without the directive the harness answers
in prose, discovery finds no deliverable, and the row is unscoreable for a
reason that has nothing to do with the model.
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
# The one directory ``discover_harvey_lab_outputs`` walks. It must resolve
# strictly inside the harness workspace, and it is the only place a scored
# deliverable may appear.
LAB_OUTPUT_DIRECTORY: Final = "output"
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
    expected_deliverable: str
    output_directory: str = LAB_OUTPUT_DIRECTORY


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
    instructions_text = _prompt_text(destination / instructions.destination_path)
    if not instructions_text.strip():
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} has an empty prompt"
        )
    expected_deliverable = _expected_deliverable(task)
    _make_output_directory(destination)
    return StagedLabTask(
        prompt=_lab_prompt(instructions_text, expected_deliverable),
        staged_paths=tuple(
            sorted(entry.destination_path for entry in manifest.entries)
        ),
        expected_deliverable=expected_deliverable,
    )


def _lab_prompt(instructions: str, expected_deliverable: str) -> str:
    """Return the projected instructions plus this lane's delivery contract."""

    return (
        f"{instructions.strip()}\n\n"
        "The task materials are in your working directory. Write the expected "
        f"deliverable {expected_deliverable} into the "
        f"{LAB_OUTPUT_DIRECTORY}/ directory of your working directory. Only "
        f"that file is scored, and anything else left in {LAB_OUTPUT_DIRECTORY}/"
        " is quarantined rather than graded."
    )


def _expected_deliverable(task: CanonicalTask) -> str:
    value = task.metadata.get("expected_deliverable")
    if not isinstance(value, str) or not value.strip():
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} names no "
            "expected_deliverable; the projection manifest carries it and the "
            "harness cannot be told what to produce without it"
        )
    if "/" in value or value in {".", ".."}:
        raise LabWorkspaceError(
            f"projected Harvey LAB task {task.task_id} expected_deliverable must "
            f"be a basename inside {LAB_OUTPUT_DIRECTORY}/: {value}"
        )
    return value


def _make_output_directory(destination: Path) -> Path:
    output = destination / LAB_OUTPUT_DIRECTORY
    if output.is_symlink() or output.exists():
        raise LabWorkspaceError(
            f"harness workspace already has a {LAB_OUTPUT_DIRECTORY}/ entry; the "
            "scored output directory must be created fresh for each row"
        )
    output.mkdir(mode=0o700)
    return output


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
