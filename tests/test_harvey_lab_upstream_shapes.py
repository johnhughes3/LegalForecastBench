"""Projection behavior against the task shapes the pinned LAB corpus actually has.

Every task at the recorded pin declares deliverables as a ``deliverables``
mapping, never as one of the singular basename fields the projector originally
read, so nothing in that corpus projected at all (GitHub #842). These tests fix
the real shapes in place: single-entry mappings project, and the shapes this
contract cannot carry are refused by name and are skippable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    HarveyLabProjectionError,
    HarveyLabUnsupportedTaskShapeError,
    project_harvey_lab_suite,
    remove_projected_tree,
)

FIXTURE_PIN = HarveyLabPin(
    repository="https://example.com/legalforecast-lab-fixture",
    commit="a" * 40,
    tree="b" * 40,
)


def test_upstream_deliverables_mapping_projects(tmp_path: Path) -> None:
    source = _lab_source(
        tmp_path,
        {"corporate/merger": {"deliverables": {"memo.docx": "memo.docx"}}},
    )

    result = _project(source, tmp_path)

    assert [task.record.lab_task_id for task in result.tasks] == ["corporate/merger"]
    assert result.manifest.tasks[0].expected_deliverables == ("memo.docx",)
    assert result.skipped == ()


def test_singular_deliverable_field_still_projects(tmp_path: Path) -> None:
    source = _lab_source(
        tmp_path,
        {"corporate/merger": {"expected_deliverable": "memo.docx"}},
    )

    result = _project(source, tmp_path)

    assert result.manifest.tasks[0].expected_deliverables == ("memo.docx",)


def test_multiple_declared_deliverables_project_in_stable_order(tmp_path: Path) -> None:
    source = _lab_source(
        tmp_path,
        {
            "corporate/merger": {
                "deliverables": {"b.docx": "b.docx", "a.docx": "a.docx"}
            }
        },
    )

    result = _project(source, tmp_path)

    assert result.manifest.tasks[0].expected_deliverables == (
        "a.docx",
        "b.docx",
    )


@pytest.mark.parametrize("record", [{}, {"deliverables": {}}])
def test_no_declared_deliverables_projects_as_score_all_outputs(
    tmp_path: Path,
    record: dict[str, object],
) -> None:
    source = _lab_source(tmp_path, {"contracts/scenario": record})

    result = _project(source, tmp_path)

    assert result.manifest.tasks[0].expected_deliverables == ()


def test_disagreeing_deliverables_key_and_value_is_not_a_skippable_shape(
    tmp_path: Path,
) -> None:
    source = _lab_source(
        tmp_path,
        {"corporate/merger": {"deliverables": {"declared.docx": "written.docx"}}},
    )

    with pytest.raises(HarveyLabProjectionError) as exc_info:
        _project(source, tmp_path, skip_unsupported_tasks=True)

    assert "key and value disagree" in str(exc_info.value)
    assert not isinstance(exc_info.value, HarveyLabUnsupportedTaskShapeError)


def test_skipping_never_swallows_a_tampering_refusal(tmp_path: Path) -> None:
    source = _lab_source(
        tmp_path,
        {"corporate/merger": {"deliverables": {"memo.docx": "memo.docx"}}},
    )
    (source / "tasks" / "corporate" / "merger" / "documents" / "gold.json").write_text(
        json.dumps({"answers": ["sealed"]}), encoding="utf-8"
    )

    with pytest.raises(HarveyLabProjectionError) as exc_info:
        _project(source, tmp_path, skip_unsupported_tasks=True)

    assert "private material" in str(exc_info.value)


def test_remove_projected_tree_undoes_the_read_only_seal(tmp_path: Path) -> None:
    source = _lab_source(
        tmp_path,
        {"corporate/merger": {"deliverables": {"memo.docx": "memo.docx"}}},
    )
    result = _project(source, tmp_path)
    sealed = result.solver_root / "tasks" / "corporate" / "merger"
    assert not sealed.stat().st_mode & 0o200

    remove_projected_tree(result.solver_root)

    assert not result.solver_root.exists()


def _project(
    source: Path,
    tmp_path: Path,
    *,
    skip_unsupported_tasks: bool = False,
):
    return project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "projected",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
        skip_unsupported_tasks=skip_unsupported_tasks,
    )


def _lab_source(tmp_path: Path, tasks: dict[str, dict[str, object]]) -> Path:
    """Build a LAB checkout whose task.json fields mirror the pinned corpus."""

    lab_root = tmp_path / "lab"
    for lab_task_id, extra in tasks.items():
        task_dir = lab_root / "tasks" / lab_task_id
        (task_dir / "documents").mkdir(parents=True)
        (task_dir / "documents" / "record.txt").write_text(
            f"{lab_task_id} record\n", encoding="utf-8"
        )
        record: dict[str, object] = {
            "title": lab_task_id,
            "work_type": "draft",
            "instructions": f"Do {lab_task_id}.",
            "criteria": [{"id": "C-001", "match_criteria": "private rubric"}],
        }
        record.update(extra)
        (task_dir / "task.json").write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )
    return lab_root
