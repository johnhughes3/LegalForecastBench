"""Cost guardrails for missing core-document recovery plans."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from legalforecast.ingestion.core_document_filter import CoreDocumentFilterResult

DEFAULT_MAX_MISSING_CORE_DOCUMENTS_PER_CASE = 24
DEFAULT_PURCHASE_COST_USD = Decimal("3.05")
DEFAULT_MAX_PROJECTED_BUDGET_USD = Decimal("2250.00")


class MissingCoreBudgetError(ValueError):
    """Raised when a missing-core purchase plan violates budget guardrails."""


class CaseDocumentCapExceededError(MissingCoreBudgetError):
    """Raised when one candidate exceeds the per-case missing-core cap."""


class PurchaseBudgetExceededError(MissingCoreBudgetError):
    """Raised when a run exceeds the configured total purchase budget."""


@dataclass(frozen=True, slots=True)
class CaseMissingCorePurchasePlan:
    """Machine-readable paid-recovery plan for one candidate case."""

    candidate_id: str
    purchase_document_ids: tuple[str, ...]
    missing_core_document_count: int
    estimated_cost: Decimal
    audit_only_document_count: int
    dry_run: bool
    exclusion_reasons: tuple[str, ...] = ()
    missing_core_roles: tuple[str, ...] = ()

    @property
    def estimated_purchase_count(self) -> int:
        """Return the number of paid documents needed to complete the case."""

        return self.missing_core_document_count

    @property
    def estimated_cost_usd(self) -> str:
        return _money(self.estimated_cost)

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "purchase_document_ids": list(self.purchase_document_ids),
            "missing_core_document_count": self.missing_core_document_count,
            "estimated_purchase_count": self.estimated_purchase_count,
            "missing_core_roles": list(self.missing_core_roles),
            "estimated_cost_usd": self.estimated_cost_usd,
            "audit_only_document_count": self.audit_only_document_count,
            "dry_run": self.dry_run,
            "exclusion_reasons": list(self.exclusion_reasons),
        }


@dataclass(frozen=True, slots=True)
class PurchaseFrontierRow:
    """Cumulative N1(k) and spend(k) values for one missing-document threshold."""

    max_missing_core_documents_per_case: int
    complete_case_count: int
    incremental_case_count: int
    purchase_document_count: int
    estimated_spend: Decimal

    @property
    def estimated_spend_usd(self) -> str:
        return _money(self.estimated_spend)

    def to_record(self) -> dict[str, Any]:
        return {
            "max_missing_core_documents_per_case": (
                self.max_missing_core_documents_per_case
            ),
            "complete_case_count": self.complete_case_count,
            "incremental_case_count": self.incremental_case_count,
            "purchase_document_count": self.purchase_document_count,
            "estimated_spend_usd": self.estimated_spend_usd,
        }


@dataclass(frozen=True, slots=True)
class MissingCoreBudgetPlan:
    """Run-level missing-core purchase budget summary."""

    case_plans: tuple[CaseMissingCorePurchasePlan, ...]
    cost_per_document: Decimal
    max_projected_budget: Decimal
    max_missing_core_documents_per_case: int
    dry_run: bool
    frontier_rows: tuple[PurchaseFrontierRow, ...] = ()
    omitted_candidate_ids: tuple[str, ...] = ()
    excluded_case_plans: tuple[CaseMissingCorePurchasePlan, ...] = ()

    @property
    def frontier_truncated(self) -> bool:
        return bool(self.omitted_candidate_ids)

    @property
    def total_missing_core_documents(self) -> int:
        return sum(plan.missing_core_document_count for plan in self.case_plans)

    @property
    def total_estimated_cost(self) -> Decimal:
        return sum((plan.estimated_cost for plan in self.case_plans), Decimal("0"))

    @property
    def total_estimated_cost_usd(self) -> str:
        return _money(self.total_estimated_cost)

    @property
    def cost_per_document_usd(self) -> str:
        return _money(self.cost_per_document)

    @property
    def max_projected_budget_usd(self) -> str:
        return _money(self.max_projected_budget)

    def to_record(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "cost_per_document_usd": self.cost_per_document_usd,
            "max_projected_budget_usd": self.max_projected_budget_usd,
            "max_missing_core_documents_per_case": (
                self.max_missing_core_documents_per_case
            ),
            "total_missing_core_documents": self.total_missing_core_documents,
            "total_estimated_cost_usd": self.total_estimated_cost_usd,
            "frontier_truncated": self.frontier_truncated,
            "omitted_candidate_ids": list(self.omitted_candidate_ids),
            "frontier_rows": [row.to_record() for row in self.frontier_rows],
            "case_plans": [plan.to_record() for plan in self.case_plans],
            "excluded_case_plans": [
                plan.to_record() for plan in self.excluded_case_plans
            ],
        }


def plan_missing_core_document_budget(
    filter_results: Iterable[CoreDocumentFilterResult],
    *,
    dry_run: bool = True,
    max_missing_core_documents_per_case: int = (
        DEFAULT_MAX_MISSING_CORE_DOCUMENTS_PER_CASE
    ),
    cost_per_document_usd: Decimal | str = DEFAULT_PURCHASE_COST_USD,
    max_projected_budget_usd: Decimal | str = DEFAULT_MAX_PROJECTED_BUDGET_USD,
    truncate_to_budget: bool = False,
) -> MissingCoreBudgetPlan:
    """Build a paid-recovery budget plan from core-document filter results."""

    _require_positive_int(
        max_missing_core_documents_per_case,
        "max_missing_core_documents_per_case",
    )
    cost_per_document = _decimal_money(
        cost_per_document_usd,
        "cost_per_document_usd",
    )
    max_projected_budget = _decimal_money(
        max_projected_budget_usd,
        "max_projected_budget_usd",
    )

    ranked_case_plans = tuple(
        sorted(
            (
                _case_purchase_plan(
                    result,
                    dry_run=dry_run,
                    cost_per_document=cost_per_document,
                    max_missing_core_documents_per_case=max_missing_core_documents_per_case,
                )
                for result in filter_results
            ),
            key=lambda plan: (
                plan.missing_core_document_count,
                plan.estimated_cost,
                plan.candidate_id,
            ),
        )
    )
    completable_case_plans = tuple(
        plan for plan in ranked_case_plans if not plan.exclusion_reasons
    )
    excluded_case_plans = tuple(
        plan for plan in ranked_case_plans if plan.exclusion_reasons
    )
    frontier_rows = _purchase_frontier_rows(completable_case_plans)
    case_plans, omitted_candidate_ids = _truncate_frontier(
        completable_case_plans,
        max_projected_budget=max_projected_budget,
        truncate_to_budget=truncate_to_budget,
    )
    plan = MissingCoreBudgetPlan(
        case_plans=case_plans,
        cost_per_document=cost_per_document,
        max_projected_budget=max_projected_budget,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        dry_run=dry_run,
        frontier_rows=frontier_rows,
        omitted_candidate_ids=omitted_candidate_ids,
        excluded_case_plans=excluded_case_plans,
    )
    if plan.total_estimated_cost > max_projected_budget:
        raise PurchaseBudgetExceededError(
            "projected total "
            f"${plan.total_estimated_cost_usd} exceeds budget "
            f"${plan.max_projected_budget_usd}"
        )
    return plan


def write_missing_core_budget_plan(
    plan: MissingCoreBudgetPlan,
    path: str | Path,
) -> Path:
    """Write a machine-readable missing-core budget plan as JSON."""

    output_path = Path(path)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(plan.to_record(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return output_path


def _case_purchase_plan(
    result: CoreDocumentFilterResult,
    *,
    dry_run: bool,
    cost_per_document: Decimal,
    max_missing_core_documents_per_case: int,
) -> CaseMissingCorePurchasePlan:
    purchase_document_ids = tuple(result.core_missing_documents)
    missing_core_document_count = len(purchase_document_ids)
    if missing_core_document_count > max_missing_core_documents_per_case:
        raise CaseDocumentCapExceededError(
            f"{result.candidate_id} has {missing_core_document_count} "
            "missing core documents; cap is "
            f"{max_missing_core_documents_per_case}"
        )
    return CaseMissingCorePurchasePlan(
        candidate_id=result.candidate_id,
        purchase_document_ids=purchase_document_ids,
        missing_core_document_count=missing_core_document_count,
        estimated_cost=cost_per_document * missing_core_document_count,
        audit_only_document_count=len(result.audit_only_document_ids),
        dry_run=dry_run,
        exclusion_reasons=tuple(result.exclusion_reasons),
        missing_core_roles=tuple(result.missing_core_roles),
    )


def _purchase_frontier_rows(
    case_plans: tuple[CaseMissingCorePurchasePlan, ...],
) -> tuple[PurchaseFrontierRow, ...]:
    if not case_plans:
        return ()
    rows: list[PurchaseFrontierRow] = []
    prior_count = 0
    for threshold in range(
        max(plan.missing_core_document_count for plan in case_plans) + 1
    ):
        eligible = tuple(
            plan for plan in case_plans if plan.missing_core_document_count <= threshold
        )
        complete_case_count = len(eligible)
        rows.append(
            PurchaseFrontierRow(
                max_missing_core_documents_per_case=threshold,
                complete_case_count=complete_case_count,
                incremental_case_count=complete_case_count - prior_count,
                purchase_document_count=sum(
                    plan.missing_core_document_count for plan in eligible
                ),
                estimated_spend=sum(
                    (plan.estimated_cost for plan in eligible), Decimal("0")
                ),
            )
        )
        prior_count = complete_case_count
    return tuple(rows)


def _truncate_frontier(
    case_plans: tuple[CaseMissingCorePurchasePlan, ...],
    *,
    max_projected_budget: Decimal,
    truncate_to_budget: bool,
) -> tuple[tuple[CaseMissingCorePurchasePlan, ...], tuple[str, ...]]:
    if not truncate_to_budget:
        return case_plans, ()
    selected: list[CaseMissingCorePurchasePlan] = []
    omitted: list[str] = []
    spend = Decimal("0")
    for index, plan in enumerate(case_plans):
        if spend + plan.estimated_cost <= max_projected_budget:
            selected.append(plan)
            spend += plan.estimated_cost
        else:
            omitted.extend(item.candidate_id for item in case_plans[index:])
            break
    return tuple(selected), tuple(omitted)


def _decimal_money(value: Decimal | str, field_name: str) -> Decimal:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a decimal dollar amount") from exc
    if decimal_value < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return decimal_value.quantize(Decimal("0.01"))


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
