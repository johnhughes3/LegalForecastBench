from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.multiharness.folder_selection import (
    PROJECTED_LAYOUT_MANIFEST_NAME,
    PROJECTED_LAYOUT_SCHEMA_VERSION,
    FolderSelectionError,
    select_tasks_from_folder,
)
from legalforecast.multiharness.run_progress import require_honest_coverage_claim
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex

SHA256 = "sha256:" + "a" * 64


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


def test_folder_mode_resolves_projected_layout(tmp_path: Path) -> None:
    folder, index, task = _projected_folder(tmp_path)
    selected = select_tasks_from_folder(folder, index)

    assert selected.task_ids == (task.task_id,)
    assert selected.selection_method == "folder"
    public = json.dumps(selected.to_public_record())
    assert str(folder.resolve()) not in public
    assert "relative_path" in public


def test_folder_mode_refuses_missing_manifest(tmp_path: Path) -> None:
    folder = tmp_path / "empty-folder"
    folder.mkdir()
    index = _task_index(_task("harvey_lab:corporate/merger", module="corporate"))

    with pytest.raises(FolderSelectionError, match=r"projection-manifest\.json"):
        select_tasks_from_folder(folder, index)


def test_folder_mode_refuses_tampered_bytes(tmp_path: Path) -> None:
    folder, index, _task_ref = _projected_folder(tmp_path)
    listed = folder / "corporate" / "merger" / "task.json"
    listed.write_text(listed.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(
        FolderSelectionError, match="do not match the projection manifest"
    ):
        select_tasks_from_folder(folder, index)


def test_folder_mode_refuses_unrecognized_task_files(tmp_path: Path) -> None:
    folder, index, _task_ref = _projected_folder(tmp_path)
    extra = folder / "litigation" / "motion"
    extra.mkdir(parents=True)
    (extra / "task.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FolderSelectionError, match="unrecognized task files"):
        select_tasks_from_folder(folder, index)


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


def _projected_folder(tmp_path: Path) -> tuple[Path, TaskIndex, CanonicalTask]:
    folder = tmp_path / "projected-layout"
    relative_path = "corporate/merger/task.json"
    task_path = folder / relative_path
    task_path.parent.mkdir(parents=True)
    payload = {"id": "merger-review", "prompt": "fixture task"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    task_path.write_bytes(encoded)
    digest = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    task = CanonicalTask(
        task_id="harvey_lab:corporate/merger",
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="fixture-suite",
        source_id="merger-review",
        task_sha256=digest,
        metadata={"module": "corporate"},
    )
    write_json_object(
        folder / PROJECTED_LAYOUT_MANIFEST_NAME,
        {
            "schema_version": PROJECTED_LAYOUT_SCHEMA_VERSION,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "relative_path": relative_path,
                    "task_sha256": digest,
                    "family": task.family,
                    "scoring_mode": task.scoring_mode,
                    "category": "corporate",
                }
            ],
        },
    )
    return folder, _task_index(task), task


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
