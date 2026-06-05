from __future__ import annotations

import pytest
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex

SHA256 = "sha256:" + "a" * 64


def test_selection_filters_lfb_case_candidate_and_ablation() -> None:
    index = _task_index(
        _task(
            "lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            metadata={
                "case_id": "case-1",
                "candidate_id": "cand-1",
                "ablation": "full_packet",
            },
        ),
        _task(
            "lfb:case-2:metadata_only",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            metadata={
                "case_id": "case-2",
                "candidate_id": "cand-2",
                "ablation": "metadata_only",
            },
        ),
    )

    result = TaskSelection(
        families=("legalforecast_mtd",),
        case_ids=("case-1",),
        candidate_ids=("cand-1",),
        ablations=("full_packet",),
    ).select(index)

    assert [task.task_id for task in result.tasks] == ["lfb:case-1:full_packet"]
    assert result.comparison_groups[0].family == "legalforecast_mtd"
    assert result.comparison_groups[0].scoring_mode == "lfb_brier"


def test_selection_filters_lab_module_practice_area_and_tags() -> None:
    index = _task_index(
        _task(
            "harvey_lab:corporate/merger",
            family="harvey_lab",
            scoring_mode="lab_native",
            metadata={
                "module": "corporate",
                "practice_area": "m-and-a",
                "tags": ["drafting", "contract"],
            },
        ),
        _task(
            "harvey_lab:litigation/motion",
            family="harvey_lab",
            scoring_mode="lab_native",
            metadata={
                "module": "litigation",
                "practice_area": "motion-practice",
                "tags": ["research"],
            },
        ),
    )

    result = TaskSelection(
        modules=("corporate",),
        practice_areas=("m-and-a",),
        tags=("contract",),
    ).select(index)

    assert [task.task_id for task in result.tasks] == ["harvey_lab:corporate/merger"]
    assert result.comparison_groups[0].family == "harvey_lab"
    assert result.comparison_groups[0].scoring_mode == "lab_native"


def test_duplicate_selectors_do_not_duplicate_tasks() -> None:
    index = _task_index(
        _task(
            "lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            metadata={"case_id": "case-1"},
        )
    )

    selection = TaskSelection(case_ids=("case-1", "case-1"))
    result = selection.select(index)

    assert selection.normalized().case_ids == ("case-1",)
    assert [task.task_id for task in result.tasks] == ["lfb:case-1:full_packet"]


def test_seeded_limit_is_deterministic_and_changes_selection_hash() -> None:
    index = _task_index(
        *(
            _task(
                f"lfb:case-{number}:full_packet",
                family="legalforecast_mtd",
                scoring_mode="lfb_brier",
                metadata={"case_id": f"case-{number}"},
            )
            for number in range(10)
        )
    )

    first = TaskSelection(limit=3, seed="alpha").select(index)
    second = TaskSelection(limit=3, seed="alpha").select(index)
    different = TaskSelection(limit=3, seed="beta").select(index)

    assert [task.task_id for task in first.tasks] == [
        task.task_id for task in second.tasks
    ]
    assert first.selection_sha256 == second.selection_sha256
    assert first.selection_sha256 != different.selection_sha256


def test_empty_selection_fails_unless_allowed() -> None:
    index = _task_index(
        _task(
            "lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            metadata={"case_id": "case-1"},
        )
    )

    with pytest.raises(ValueError, match="matched no tasks"):
        TaskSelection(case_ids=("missing",)).select(index)

    result = TaskSelection(case_ids=("missing",), allow_empty=True).select(index)

    assert result.tasks == ()
    assert result.selection_sha256


def test_selection_result_groups_by_family_scoring_mode_and_selection_hash() -> None:
    index = _task_index(
        _task(
            "lfb:case-1:full_packet",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            metadata={},
        ),
        _task(
            "harvey_lab:corporate/merger",
            family="harvey_lab",
            scoring_mode="lab_native",
            metadata={},
        ),
    )

    result = TaskSelection.full().select(index)

    assert {group.family for group in result.comparison_groups} == {
        "legalforecast_mtd",
        "harvey_lab",
    }
    assert {group.selection_sha256 for group in result.comparison_groups} == {
        result.selection_sha256
    }


def _task_index(*tasks: CanonicalTask) -> TaskIndex:
    return TaskIndex(
        index_id="fixture-index",
        selection_namespace="fixture",
        tasks=tasks,
        index_sha256=SHA256,
    )


def _task(
    task_id: str,
    *,
    family: str,
    scoring_mode: str,
    metadata: dict[str, object],
) -> CanonicalTask:
    return CanonicalTask(
        task_id=task_id,
        family=family,
        scoring_mode=scoring_mode,
        suite_version="fixture-suite",
        source_id=task_id,
        task_sha256=SHA256,
        metadata=metadata,
    )
