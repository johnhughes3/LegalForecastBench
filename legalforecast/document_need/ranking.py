"""Cheapest-first admission with optional bottom-decile mix cap."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from legalforecast.document_need.costs import CaseCosts
from legalforecast.document_need.cycle_config import (
    CaseMixStratification,
    format_usd,
)

_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class RankedCase:
    """One priced candidate with a 1-based cost rank (1 = cheapest max_cost)."""

    costs: CaseCosts
    cost_rank: int
    bottom_decile: bool

    @property
    def candidate_id(self) -> str:
        return self.costs.candidate_id

    @property
    def min_cost(self) -> Decimal:
        return self.costs.min_cost

    @property
    def max_cost(self) -> Decimal:
        return self.costs.max_cost

    @property
    def restricted_required(self) -> bool:
        return self.costs.restricted_required


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """Admit/reject for one ranked candidate."""

    ranked: RankedCase
    admitted: bool
    reject_reason: str | None

    def to_record(self) -> dict[str, object]:
        return {
            **self.ranked.costs.to_record(),
            "cost_rank": self.ranked.cost_rank,
            "bottom_decile": self.ranked.bottom_decile,
            "admitted": self.admitted,
            "reject_reason": self.reject_reason,
        }


def rank_cases(cases: Sequence[CaseCosts]) -> tuple[RankedCase, ...]:
    """Rank by max_cost, then min_cost, then candidate_id (all ascending)."""

    if not cases:
        raise ValueError("ranking requires at least one case")
    ids = [case.candidate_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("ranking requires unique candidate_id values")
    ordered = sorted(
        cases,
        key=lambda case: (case.max_cost, case.min_cost, case.candidate_id),
    )
    decile_count = max(1, math.ceil(len(ordered) * 0.1))
    bottom_ids = {case.candidate_id for case in ordered[:decile_count]}
    return tuple(
        RankedCase(
            costs=case,
            cost_rank=index,
            bottom_decile=case.candidate_id in bottom_ids,
        )
        for index, case in enumerate(ordered, start=1)
    )


def admit_cheapest(
    ranked: Sequence[RankedCase],
    *,
    target_n: int,
    spend_ceiling: Decimal | None,
    stratification: CaseMixStratification,
    max_per_case: Decimal | None = None,
) -> tuple[AdmissionDecision, ...]:
    """Admit cheapest cases up to the cohort target and spend ceilings.

    When stratification is enabled, bottom-decile share is measured against the
    *admitted* cohort: extra cheapest bottom-decile cases are dropped until
    ``floor(len(admitted) * cap)`` is respected, then non-bottom cases may
    backfill remaining target/spend room.
    """

    if type(target_n) is not int or target_n <= 0:
        raise ValueError("cohort_target_n must be a positive integer")
    if spend_ceiling is not None and spend_ceiling < _ZERO:
        raise ValueError("spend_ceiling_usd must be nonnegative")
    if max_per_case is not None and max_per_case < _ZERO:
        raise ValueError("max_per_case_usd must be nonnegative")
    reasons: dict[str, str | None] = {}
    admitted: list[RankedCase] = []
    spent = _ZERO
    for case in ranked:
        if len(admitted) >= target_n:
            reasons[case.candidate_id] = "cohort_target_reached"
            continue
        reason = _hard_reject(
            case,
            spent=spent,
            spend_ceiling=spend_ceiling,
            max_per_case=max_per_case,
        )
        if reason is not None:
            reasons[case.candidate_id] = reason
            continue
        admitted.append(case)
        spent += case.max_cost
        reasons[case.candidate_id] = None
    if stratification.enabled:
        admitted, spent, reasons = _apply_bottom_decile_cap(
            ranked,
            admitted,
            spent=spent,
            reasons=reasons,
            target_n=target_n,
            spend_ceiling=spend_ceiling,
            max_per_case=max_per_case,
            cap=stratification.bottom_decile_share_cap,
        )
    admitted_ids = {case.candidate_id for case in admitted}
    return tuple(
        AdmissionDecision(
            ranked=case,
            admitted=case.candidate_id in admitted_ids,
            reject_reason=reasons.get(case.candidate_id),
        )
        for case in ranked
    )


def _hard_reject(
    case: RankedCase,
    *,
    spent: Decimal,
    spend_ceiling: Decimal | None,
    max_per_case: Decimal | None,
) -> str | None:
    if case.restricted_required:
        return "restricted_required_document"
    if max_per_case is not None and case.max_cost > max_per_case:
        return "max_per_case"
    if spend_ceiling is not None and spent + case.max_cost > spend_ceiling:
        return "spend_ceiling"
    return None


def _apply_bottom_decile_cap(
    ranked: Sequence[RankedCase],
    admitted: list[RankedCase],
    *,
    spent: Decimal,
    reasons: dict[str, str | None],
    target_n: int,
    spend_ceiling: Decimal | None,
    max_per_case: Decimal | None,
    cap: Decimal,
) -> tuple[list[RankedCase], Decimal, dict[str, str | None]]:
    while admitted:
        quota = _bottom_decile_quota(len(admitted), cap)
        bottoms = [case for case in admitted if case.bottom_decile]
        if len(bottoms) <= quota:
            break
        dropped = bottoms[quota]
        admitted = [
            case for case in admitted if case.candidate_id != dropped.candidate_id
        ]
        spent -= dropped.max_cost
        reasons[dropped.candidate_id] = "stratification_bottom_decile_cap"
    admitted_ids = {case.candidate_id for case in admitted}
    for case in ranked:
        if len(admitted) >= target_n:
            if (
                case.candidate_id not in admitted_ids
                and reasons.get(case.candidate_id) is None
            ):
                reasons[case.candidate_id] = "cohort_target_reached"
            continue
        if case.candidate_id in admitted_ids:
            continue
        if reasons.get(case.candidate_id) in {
            "restricted_required_document",
            "max_per_case",
        }:
            continue
        if case.bottom_decile:
            quota = _bottom_decile_quota(len(admitted) + 1, cap)
            bottoms = sum(1 for row in admitted if row.bottom_decile)
            if bottoms + 1 > quota:
                reasons[case.candidate_id] = "stratification_bottom_decile_cap"
                continue
        reason = _hard_reject(
            case, spent=spent, spend_ceiling=spend_ceiling, max_per_case=max_per_case
        )
        if reason is not None:
            reasons[case.candidate_id] = reason
            continue
        admitted.append(case)
        admitted_ids.add(case.candidate_id)
        spent += case.max_cost
        reasons[case.candidate_id] = None
    return admitted, spent, reasons


def _bottom_decile_quota(cohort_n: int, cap: Decimal) -> int:
    if cap <= 0:
        return 0
    return int(Decimal(cohort_n) * cap)


def provenance_record(decisions: Sequence[AdmissionDecision]) -> dict[str, object]:
    """Cohort provenance sidecar: cost-rank is recorded for mix analysis."""

    return {
        # contract-ratchet: allow observational post-Cycle-1 document-need sidecar
        "schema_version": "legalforecast.document_need_cohort_provenance.v1",
        "cases": [
            {
                "candidate_id": decision.ranked.candidate_id,
                "cost_rank": decision.ranked.cost_rank,
                "min_cost_usd": format_usd(decision.ranked.min_cost),
                "max_cost_usd": format_usd(decision.ranked.max_cost),
                "bottom_decile": decision.ranked.bottom_decile,
                "admitted": decision.admitted,
                "reject_reason": decision.reject_reason,
            }
            for decision in decisions
        ],
    }
