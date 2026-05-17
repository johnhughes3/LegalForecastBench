from __future__ import annotations

import pytest
from legalforecast.ingestion import CoreDocumentFilterResult
from legalforecast.ingestion.missing_core_budget import (
    CaseDocumentCapExceededError,
    PurchaseBudgetExceededError,
    plan_missing_core_document_budget,
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


def test_budget_planner_rejects_over_case_cap() -> None:
    result = _filter_result("too-many-docs", core_missing_count=25)

    with pytest.raises(
        CaseDocumentCapExceededError,
        match="too-many-docs has 25 missing core documents; cap is 24",
    ):
        plan_missing_core_document_budget([result])


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


def _filter_result(
    candidate_id: str,
    *,
    core_missing_count: int,
    audit_only_count: int = 0,
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
        exclusion_reasons=(),
    )
