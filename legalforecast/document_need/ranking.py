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

    Stratification, when enabled, uses a quota of
    ``floor(target_n * bottom_decile_share_cap)`` bottom-decile seats in the
    intended cohort so cheapest-first does not treat the first cheap case as
    100% of a one-case set.
    """

    if type(target_n) is not int or target_n <= 0:
        raise ValueError("cohort_target_n must be a positive integer")
    if spend_ceiling is not None and spend_ceiling < _ZERO:
        raise ValueError("spend_ceiling_usd must be nonnegative")
    if max_per_case is not None and max_per_case < _ZERO:
        raise ValueError("max_per_case_usd must be nonnegative")
    bottom_quota = (
        _bottom_decile_quota(target_n, stratification.bottom_decile_share_cap)
        if stratification.enabled
        else 0
    )
    decisions: list[AdmissionDecision] = []
    admitted_ids: set[str] = set()
    spent = _ZERO
    admitted_bottom = 0
    for case in ranked:
        reason: str | None = None
        if len(admitted_ids) >= target_n:
            reason = "cohort_target_reached"
        elif case.restricted_required:
            reason = "restricted_required_document"
        elif max_per_case is not None and case.max_cost > max_per_case:
            reason = "max_per_case"
        elif spend_ceiling is not None and spent + case.max_cost > spend_ceiling:
            reason = "spend_ceiling"
        elif (
            stratification.enabled
            and case.bottom_decile
            and admitted_bottom >= bottom_quota
        ):
            reason = "stratification_bottom_decile_cap"
        admitted = reason is None
        if admitted:
            admitted_ids.add(case.candidate_id)
            spent += case.max_cost
            if case.bottom_decile:
                admitted_bottom += 1
        decisions.append(
            AdmissionDecision(ranked=case, admitted=admitted, reject_reason=reason)
        )
    return tuple(decisions)


def _bottom_decile_quota(target_n: int, cap: Decimal) -> int:
    if cap <= 0:
        return 0
    return int(Decimal(target_n) * cap)


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
