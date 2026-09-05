from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from legalforecast.multiharness.folder_selection import (
    FolderSelectionError,
    projection_root_for,
    select_tasks_from_folder,
)
from legalforecast.multiharness.harvey_lab_projected_tasks import (
    HarveyLabProjectionTaskLoader,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabProjectionResult,
    project_harvey_lab_suite,
)
from legalforecast.multiharness.run_progress import require_honest_coverage_claim
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex

from test_harvey_lab_projection import (
    FIXTURE_PIN,
    ISSUE_196_LAB_TASK_ID,
    _add_unselected_task,
    _issue_196_source,
)

SHA256 = "sha256:" + "a" * 64
DECOY_LAB_TASK_ID = "aaa-practice/decoy-task"


def test_task_id_list_is_labeled_scoped() -> None:
    index = _task_index(_task("harvey_lab:corporate/merger", module="corporate"))
    result = TaskSelection(task_ids=("harvey_lab:corporate/merger",)).select(index)

    assert result.coverage_kind == "scoped"
    assert result.selection_label.startswith("scoped:")
    assert [task.task_id for task in result.tasks] == ["harvey_lab:corporate/merger"]


def test_category_alias_selects_lab_module() -> None:
    index = _task_index(
        _task("harvey_lab:corporate/merger", module="corporate"),
        _task("harvey_lab:litigation/motion", module="litigation"),
    )
    result = TaskSelection(modules=("corporate",)).select(index)

    assert [task.task_id for task in result.tasks] == ["harvey_lab:corporate/merger"]
    assert result.coverage_kind == "scoped"


def test_folder_mode_consumes_a_real_projected_layout(tmp_path: Path) -> None:
    result, index = _projected_lab_layout(tmp_path)
    selected = select_tasks_from_folder(result.solver_root, index)

    assert selected.selection_method == "folder"
    assert selected.subtree == ""
    assert set(selected.task_ids) == {task.task_id for task in index.tasks}
    assert {ref.family for ref in selected.refs} == {"harvey_lab"}
    assert {ref.scoring_mode for ref in selected.refs} == {"lab_native"}
    by_id = {task.task_id: task.task_sha256 for task in index.tasks}
    assert all(ref.task_sha256 == by_id[ref.task_id] for ref in selected.refs)
    public = json.dumps(selected.to_public_record())
    assert str(result.solver_root.resolve()) not in public
    assert str(tmp_path) not in public
    assert "relative_path" in public


def test_folder_mode_selects_one_category_folder(tmp_path: Path) -> None:
    result, index = _projected_lab_layout(tmp_path)
    category_folder = result.solver_root / "tasks" / DECOY_LAB_TASK_ID.split("/")[0]
    selected = select_tasks_from_folder(category_folder, index)

    assert selected.subtree == f"tasks/{DECOY_LAB_TASK_ID.split('/')[0]}"
    assert selected.task_ids == (f"harvey_lab:{DECOY_LAB_TASK_ID}",)
    assert projection_root_for(category_folder) == result.solver_root.resolve()


def test_folder_mode_refuses_a_folder_outside_any_projection(tmp_path: Path) -> None:
    folder = tmp_path / "not-a-projection"
    folder.mkdir()
    index = _task_index(_task("harvey_lab:corporate/merger", module="corporate"))

    with pytest.raises(FolderSelectionError, match=r"harvey-lab-projection\.v1\.json"):
        select_tasks_from_folder(folder, index)


def test_folder_mode_refuses_tampered_projected_bytes(tmp_path: Path) -> None:
    result, index = _projected_lab_layout(tmp_path)
    target = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "instructions.txt"
    _make_writable(result.solver_root)
    target.write_bytes(target.read_bytes() + b"x")

    with pytest.raises(FolderSelectionError, match="projected file hash mismatch"):
        select_tasks_from_folder(result.solver_root, index)


def test_folder_mode_refuses_a_task_absent_from_the_index(tmp_path: Path) -> None:
    result, index = _projected_lab_layout(tmp_path)
    partial = TaskIndex(
        index_id=index.index_id,
        selection_namespace=index.selection_namespace,
        tasks=(index.tasks[0],),
        index_sha256=index.index_sha256,
    )

    with pytest.raises(FolderSelectionError, match="is not in the task index"):
        select_tasks_from_folder(result.solver_root, partial)


def test_honest_coverage_claim_rejects_deleted_scoped_label() -> None:
    with pytest.raises(ValueError, match="scoped selection_label"):
        require_honest_coverage_claim(
            selection_label="full",
            coverage_kind="scoped",
            interrupted=False,
        )


def test_honest_coverage_claim_rejects_unlabeled_interrupt() -> None:
    with pytest.raises(ValueError, match="labeled partial"):
        require_honest_coverage_claim(
            selection_label="full",
            coverage_kind="full",
            interrupted=True,
        )


def test_honest_coverage_claim_rejects_unknown_coverage_kind() -> None:
    with pytest.raises(ValueError, match="coverage_kind"):
        require_honest_coverage_claim(
            selection_label="full",
            coverage_kind="scope",
            interrupted=False,
        )


def test_impartial_label_is_not_a_partial_claim() -> None:
    with pytest.raises(ValueError, match="labeled partial"):
        require_honest_coverage_claim(
            selection_label="impartial-analysis",
            coverage_kind="full",
            interrupted=True,
        )


def _projected_lab_layout(
    tmp_path: Path,
) -> tuple[HarveyLabProjectionResult, TaskIndex]:
    source = _issue_196_source(tmp_path / "lab")
    _add_unselected_task(source)
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "projected",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    index = HarveyLabProjectionTaskLoader(
        result.solver_root,
        suite_version="fixture-suite",
    ).load_task_index()
    return result, index


def _make_writable(root: Path) -> None:
    for path in [root, *root.rglob("*")]:
        path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR)


def _task_index(*tasks: CanonicalTask) -> TaskIndex:
    return TaskIndex(
        index_id="fixture-index",
        selection_namespace="fixture",
        tasks=tasks,
        index_sha256=SHA256,
    )


def _task(task_id: str, *, module: str) -> CanonicalTask:
    return CanonicalTask(
        task_id=task_id,
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="fixture-suite",
        source_id=task_id,
        task_sha256=SHA256,
        metadata={"module": module},
    )
