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

    @property
    def estimated_cost_usd(self) -> str:
        return _money(self.estimated_cost)

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "purchase_document_ids": list(self.purchase_document_ids),
            "missing_core_document_count": self.missing_core_document_count,
            "estimated_cost_usd": self.estimated_cost_usd,
            "audit_only_document_count": self.audit_only_document_count,
            "dry_run": self.dry_run,
            "exclusion_reasons": list(self.exclusion_reasons),
        }


@dataclass(frozen=True, slots=True)
class MissingCoreBudgetPlan:
    """Run-level missing-core purchase budget summary."""

    case_plans: tuple[CaseMissingCorePurchasePlan, ...]
    cost_per_document: Decimal
    max_projected_budget: Decimal
    max_missing_core_documents_per_case: int
    dry_run: bool

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
            "case_plans": [plan.to_record() for plan in self.case_plans],
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

    case_plans = tuple(
        _case_purchase_plan(
            result,
            dry_run=dry_run,
            cost_per_document=cost_per_document,
            max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        )
        for result in filter_results
    )
    plan = MissingCoreBudgetPlan(
        case_plans=case_plans,
        cost_per_document=cost_per_document,
        max_projected_budget=max_projected_budget,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        dry_run=dry_run,
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
    )


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
