from __future__ import annotations

import pytest
from legalforecast.ingestion import CoreDocumentFilterResult
from legalforecast.ingestion.missing_core_budget import (
    PurchaseBudgetExceededError,
    plan_missing_core_document_budget,
    rank_missing_core_document_plans,
)


def test_budget_planner_allows_exactly_at_case_cap() -> None:
    result = _filter_result("case-cap", core_missing_count=24, audit_only_count=50)

    plan = plan_missing_core_document_budget([result], dry_run=True)

    assert plan.total_missing_core_documents == 24
    assert plan.total_estimated_cost_usd == "73.20"
    assert plan.case_plans[0].missing_core_document_count == 24
    assert plan.case_plans[0].estimated_cost_usd == "73.20"
    assert plan.to_record()["dry_run"] is True
    assert plan.to_record()["case_plans"][0]["audit_only_document_count"] == 50


def test_budget_planner_ledger_excludes_over_case_cap() -> None:
    result = _filter_result("too-many-docs", core_missing_count=25)

    plan = plan_missing_core_document_budget([result])

    assert plan.case_plans == ()
    [excluded] = plan.excluded_case_plans
    assert excluded.candidate_id == "too-many-docs"
    assert excluded.exclusion_reasons == ("missing_core_document_cap_exceeded",)


def test_budget_planner_allows_exactly_at_budget() -> None:
    result = _filter_result("case-budget", core_missing_count=2)

    plan = plan_missing_core_document_budget(
        [result],
        max_projected_budget_usd="6.10",
    )

    assert plan.total_missing_core_documents == 2
    assert plan.total_estimated_cost_usd == "6.10"
    assert plan.case_plans[0].purchase_document_ids == (
        "case-budget-core-001",
        "case-budget-core-002",
    )


def test_budget_planner_rejects_over_budget() -> None:
    result = _filter_result("over-budget", core_missing_count=3)

    with pytest.raises(
        PurchaseBudgetExceededError,
        match=r"projected total \$9\.15 exceeds budget \$9\.14",
    ):
        plan_missing_core_document_budget(
            [result],
            max_projected_budget_usd="9.14",
        )


def test_budget_frontier_ranks_deterministically_and_emits_threshold_table() -> None:
    results = [
        _filter_result(
            "case-two-b", core_missing_count=2, missing_roles=("opposition",)
        ),
        _filter_result("case-zero", core_missing_count=0),
        _filter_result("case-one", core_missing_count=1, missing_roles=("complaint",)),
        _filter_result("case-two-a", core_missing_count=2, missing_roles=("decision",)),
    ]

    plan = plan_missing_core_document_budget(results)

    assert [case.candidate_id for case in plan.case_plans] == [
        "case-zero",
        "case-one",
        "case-two-a",
        "case-two-b",
    ]
    assert plan.case_plans[1].estimated_purchase_count == 1
    assert plan.case_plans[1].missing_core_roles == ("complaint",)
    assert [row.to_record() for row in plan.frontier_rows] == [
        {
            "max_missing_core_documents_per_case": 0,
            "complete_case_count": 1,
            "incremental_case_count": 1,
            "purchase_document_count": 0,
            "estimated_spend_usd": "0.00",
        },
        {
            "max_missing_core_documents_per_case": 1,
            "complete_case_count": 2,
            "incremental_case_count": 1,
            "purchase_document_count": 1,
            "estimated_spend_usd": "3.05",
        },
        {
            "max_missing_core_documents_per_case": 2,
            "complete_case_count": 4,
            "incremental_case_count": 2,
            "purchase_document_count": 5,
            "estimated_spend_usd": "15.25",
        },
    ]


def test_budget_frontier_can_truncate_at_exact_cap_boundary() -> None:
    results = [
        _filter_result("case-one", core_missing_count=1),
        _filter_result("case-two", core_missing_count=2),
        _filter_result("case-three", core_missing_count=3),
    ]

    plan = plan_missing_core_document_budget(
        results,
        max_projected_budget_usd="9.15",
        truncate_to_budget=True,
    )

    assert [case.candidate_id for case in plan.case_plans] == [
        "case-one",
        "case-two",
    ]
    assert plan.total_estimated_cost_usd == "9.15"
    assert plan.frontier_truncated is True
    assert plan.omitted_candidate_ids == ("case-three",)


def test_budget_frontier_excludes_uncompletable_cases_from_counts_and_prefix() -> None:
    excluded = _filter_result(
        "excluded-zero",
        core_missing_count=0,
        exclusion_reasons=("missing_operative_complaint",),
    )
    eligible = _filter_result("eligible-one", core_missing_count=1)

    plan = plan_missing_core_document_budget(
        [excluded, eligible],
        max_projected_budget_usd="3.05",
        truncate_to_budget=True,
    )

    assert [case.candidate_id for case in plan.case_plans] == ["eligible-one"]
    assert [case.candidate_id for case in plan.excluded_case_plans] == ["excluded-zero"]
    assert plan.omitted_candidate_ids == ()
    assert plan.total_missing_core_documents == 1
    assert plan.total_estimated_cost_usd == "3.05"
    assert [row.to_record() for row in plan.frontier_rows] == [
        {
            "max_missing_core_documents_per_case": 0,
            "complete_case_count": 0,
            "incremental_case_count": 0,
            "purchase_document_count": 0,
            "estimated_spend_usd": "0.00",
        },
        {
            "max_missing_core_documents_per_case": 1,
            "complete_case_count": 1,
            "incremental_case_count": 1,
            "purchase_document_count": 1,
            "estimated_spend_usd": "3.05",
        },
    ]


def test_untruncated_ranking_retains_selected_tail_and_excluded_candidates() -> None:
    results = [
        _filter_result("eligible-zero", core_missing_count=0),
        _filter_result("eligible-tail", core_missing_count=2),
        _filter_result(
            "intrinsic-exclusion",
            core_missing_count=1,
            exclusion_reasons=("missing_operative_complaint",),
        ),
        _filter_result("cap-exclusion", core_missing_count=25),
    ]

    ranked = rank_missing_core_document_plans(results, dry_run=False)
    truncated = plan_missing_core_document_budget(
        results,
        dry_run=False,
        target_case_count=1,
        truncate_to_budget=True,
    )

    assert [row.candidate_id for row in ranked] == [
        "eligible-zero",
        "intrinsic-exclusion",
        "eligible-tail",
        "cap-exclusion",
    ]
    assert ranked[1].exclusion_reasons == ("missing_operative_complaint",)
    assert ranked[3].exclusion_reasons == ("missing_core_document_cap_exceeded",)
    assert [row.candidate_id for row in truncated.case_plans] == ["eligible-zero"]
    assert truncated.omitted_candidate_ids == ("eligible-tail",)
    assert "full_candidate_frontier" not in truncated.to_record()


def _filter_result(
    candidate_id: str,
    *,
    core_missing_count: int,
    audit_only_count: int = 0,
    missing_roles: tuple[str, ...] = (),
    exclusion_reasons: tuple[str, ...] = (),
) -> CoreDocumentFilterResult:
    core_missing_documents = tuple(
        f"{candidate_id}-core-{index:03d}" for index in range(1, core_missing_count + 1)
    )
    audit_only_document_ids = tuple(
        f"{candidate_id}-audit-{index:03d}" for index in range(1, audit_only_count + 1)
    )
    return CoreDocumentFilterResult(
        candidate_id=candidate_id,
        purchase_document_ids=core_missing_documents,
        core_mtd_documents=core_missing_documents,
        core_exhibit_documents=(),
        model_visible_document_ids=core_missing_documents,
        operative_complaint_document_id=(
            core_missing_documents[0] if core_missing_documents else None
        ),
        operative_complaint_documents=core_missing_documents[:1],
        audit_only_document_ids=audit_only_document_ids,
        core_missing_documents=core_missing_documents,
        exclusion_reasons=exclusion_reasons,
        missing_core_roles=missing_roles,
    )
