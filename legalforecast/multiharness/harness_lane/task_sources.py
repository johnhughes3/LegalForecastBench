"""Pick which corpus a harness-lane run measures: Harvey LAB or LFB.

The lane's question is whether an agentic CLI harness beats the bare API, and
that question is worth asking on more than one corpus. Two task sources are
therefore first-class and symmetrical:

* ``harvey-lab`` — a *projected* LAB tree, selected whole, by explicit task id,
  by category, or by pointing at one folder of tasks inside it.
* ``lfb`` — the LegalForecastBench motion-to-dismiss forecast packets.

Both resolve to the same pair the run matrix already consumes, a ``TaskIndex``
plus a ``TaskSelection``, so this adds a front door rather than a parallel
selection system: ``TaskSelection`` still does the filtering and still stamps
the scoped-coverage label.

Safety property, enforced structurally: there is no raw-LAB parameter here. A
raw Harvey LAB clone is not a contributor input, because upstream ``task.json``
carries the evaluator's gold ``criteria``; only a projected root — whose bytes
``verify_harvey_lab_projection`` re-hashes and scans for private markers — can
reach a solver through this function.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast.multiharness.folder_selection import (
    FolderSelection,
    narrow_selection_to_folder,
    projection_root_for,
)
from legalforecast.multiharness.harvey_lab_projected_tasks import (
    DEFAULT_PROJECTED_SUITE_VERSION,
    HarveyLabProjectionTaskLoader,
)
from legalforecast.multiharness.selection import SelectionResult, TaskSelection
from legalforecast.multiharness.spec import TaskIndex
from legalforecast.multiharness.task_loaders import (
    DEFAULT_LFB_SUITE_VERSION,
    LfbTaskLoader,
)

TASK_SOURCE_HARVEY_LAB = "harvey-lab"
TASK_SOURCE_LFB = "lfb"
TASK_SOURCES = (TASK_SOURCE_HARVEY_LAB, TASK_SOURCE_LFB)


class TaskSourceError(ValueError):
    """The requested task source cannot be resolved from these arguments."""


@dataclass(frozen=True, slots=True)
class ResolvedTaskSource:
    """One task source resolved into what ``MultiHarnessRunConfig`` accepts."""

    source: str
    task_index: TaskIndex
    selection: TaskSelection
    folder: FolderSelection | None = None

    def select(self) -> SelectionResult:
        """Apply the selection, raising if it matched nothing."""

        return self.selection.select(self.task_index)

    def to_public_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "task_source": self.source,
            "index_id": self.task_index.index_id,
            "selection_namespace": self.task_index.selection_namespace,
            "index_sha256": self.task_index.index_sha256,
            "indexed_task_count": len(self.task_index.tasks),
            "selection": self.selection.to_record(),
        }
        if self.folder is not None:
            record["folder"] = self.folder.to_public_record()
        return record


def resolve_task_source(
    *,
    source: str,
    packets: Path | None = None,
    projected_root: Path | None = None,
    task_folder: Path | None = None,
    task_ids: Sequence[str] = (),
    categories: Sequence[str] = (),
    limit: int | None = None,
    seed: str | None = None,
    label: str | None = None,
    suite_version: str | None = None,
    solver_input_root: Path | None = None,
) -> ResolvedTaskSource:
    """Resolve one task source into a task index plus a task selection.

    ``categories`` is the Harvey LAB module selector (``--category``/
    ``--module``); it matches nothing on an LFB index and is refused there
    rather than silently returning an empty selection.
    """

    if source not in TASK_SOURCES:
        raise TaskSourceError(
            f"unsupported task source: {source}; expected one of "
            + ", ".join(TASK_SOURCES)
        )
    if source == TASK_SOURCE_LFB:
        return _resolve_lfb(
            packets=packets,
            projected_root=projected_root,
            task_folder=task_folder,
            categories=categories,
            selection=_selection(
                task_ids=task_ids,
                categories=(),
                limit=limit,
                seed=seed,
                label=label,
            ),
            suite_version=suite_version,
            solver_input_root=solver_input_root,
        )
    return _resolve_harvey_lab(
        packets=packets,
        projected_root=projected_root,
        task_folder=task_folder,
        solver_input_root=solver_input_root,
        selection=_selection(
            task_ids=task_ids,
            categories=categories,
            limit=limit,
            seed=seed,
            label=label,
        ),
        suite_version=suite_version,
    )


def _resolve_lfb(
    *,
    packets: Path | None,
    projected_root: Path | None,
    task_folder: Path | None,
    categories: Sequence[str],
    selection: TaskSelection,
    suite_version: str | None,
    solver_input_root: Path | None,
) -> ResolvedTaskSource:
    if packets is None:
        raise TaskSourceError(
            "task source 'lfb' needs the model-packet JSONL; pass packets=<path> "
            "(`legalforecast fixture e2e` writes one)"
        )
    _refuse(projected_root, "projected_root", TASK_SOURCE_LFB)
    _refuse(task_folder, "task_folder", TASK_SOURCE_LFB)
    if tuple(categories):
        raise TaskSourceError(
            "category/module is a Harvey LAB selector and matches nothing on an "
            "LFB packet index; select LFB tasks with task_ids instead"
        )
    task_index = LfbTaskLoader(
        suite_version=suite_version or DEFAULT_LFB_SUITE_VERSION,
    ).load_packet_jsonl(packets, solver_input_root=solver_input_root)
    return ResolvedTaskSource(
        source=TASK_SOURCE_LFB,
        task_index=task_index,
        selection=selection,
    )


def _resolve_harvey_lab(
    *,
    packets: Path | None,
    projected_root: Path | None,
    task_folder: Path | None,
    solver_input_root: Path | None,
    selection: TaskSelection,
    suite_version: str | None,
) -> ResolvedTaskSource:
    _refuse(packets, "packets", TASK_SOURCE_HARVEY_LAB)
    _refuse(solver_input_root, "solver_input_root", TASK_SOURCE_HARVEY_LAB)
    if projected_root is not None:
        root = projected_root
    elif task_folder is not None:
        root = projection_root_for(task_folder)
    else:
        raise TaskSourceError(
            "task source 'harvey-lab' needs a projected layout; pass "
            "projected_root=<dir> or task_folder=<dir inside it>. A raw Harvey "
            "LAB clone is not an input: its task.json carries the evaluator's "
            "gold criteria. Run `multiharness tasks project` first."
        )
    task_index = HarveyLabProjectionTaskLoader(
        root,
        suite_version=suite_version or DEFAULT_PROJECTED_SUITE_VERSION,
    ).load_task_index()
    # Both the loader and the folder narrowing authenticate the projection, so a
    # folder selection hashes the tree twice. That is deliberate: one shared
    # entry point with no skip-verification seam, and one extra hash pass is
    # noise next to the provider calls the run is about to make.
    narrowed, folder = narrow_selection_to_folder(selection, task_index, task_folder)
    return ResolvedTaskSource(
        source=TASK_SOURCE_HARVEY_LAB,
        task_index=task_index,
        selection=narrowed,
        folder=folder,
    )


def _selection(
    *,
    task_ids: Sequence[str],
    categories: Sequence[str],
    limit: int | None,
    seed: str | None,
    label: str | None,
) -> TaskSelection:
    try:
        return TaskSelection(
            task_ids=tuple(task_ids),
            modules=tuple(categories),
            limit=limit,
            seed=seed,
            label=label,
        )
    except ValueError as exc:
        raise TaskSourceError(str(exc)) from exc


def _refuse(value: object, field_name: str, source: str) -> None:
    if value is not None:
        raise TaskSourceError(f"{field_name} is not supported for task source {source}")
