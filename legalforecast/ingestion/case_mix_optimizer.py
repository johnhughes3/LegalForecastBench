"""Exact, deterministic cost selection under intersecting case-mix caps."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from ortools.sat.python import cp_model

MODEL_SCHEMA_VERSION = "legalforecast-case-mix-cp-sat-v1"
NULL_BUCKET_POLICY = "uncapped"
_MAX_INT64 = (1 << 63) - 1
_BUCKET_FIELDS = (
    "court",
    "nos_macro_category",
    "related_family_id",
    "mdl_family_id",
)


class CaseMixOptimizationError(RuntimeError):
    """Base class for exact case-mix optimization failures."""


class SolverDidNotProveOptimalError(CaseMixOptimizationError):
    """Raised unless CP-SAT proves an objective phase optimal."""


class InvalidSelectionResultError(CaseMixOptimizationError):
    """Raised when independent validation rejects a solver result."""


@dataclass(frozen=True, slots=True)
class CaseMixCandidate:
    """Solver-neutral candidate data used by the exact selector."""

    candidate_id: str
    cost_cents: int
    missing_document_count: int
    court: str | None = None
    nos_macro_category: str | None = None
    related_family_id: str | None = None
    mdl_family_id: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.candidate_id.strip():
            raise ValueError("candidate_id must be non-empty")
        _require_nonnegative_int(self.cost_cents, field="cost_cents")
        _require_nonnegative_int(
            self.missing_document_count,
            field="missing_document_count",
        )
        for field in _BUCKET_FIELDS:
            value = getattr(self, field)
            if value is not None and (not value or not value.strip()):
                raise ValueError(f"{field} must be None or a non-empty string")

    def to_record(self) -> dict[str, str | int | None]:
        """Return the canonical solver-neutral candidate record."""

        return {
            "candidate_id": self.candidate_id,
            "cost_cents": self.cost_cents,
            "missing_document_count": self.missing_document_count,
            "court": self.court,
            "nos_macro_category": self.nos_macro_category,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
        }


@dataclass(frozen=True, slots=True)
class SolverPhaseAudit:
    """One exact CP-SAT objective phase and its proven result."""

    phase: str
    status: str
    value: int

    def to_record(self) -> dict[str, str | int]:
        """Serialize the phase for durable audit artifacts."""

        return {"phase": self.phase, "status": self.status, "value": self.value}


@dataclass(frozen=True, slots=True)
class CaseMixOptimizationAudit:
    """Reproducibility metadata for an exact selection."""

    model_schema_version: str
    model_sha256: str
    ortools_version: str
    num_search_workers: int
    null_bucket_policy: str
    null_bucket_counts: Mapping[str, int]
    phases: tuple[SolverPhaseAudit, ...]

    def to_record(self) -> dict[str, Any]:
        """Serialize stable solver and model evidence."""

        return {
            "model_schema_version": self.model_schema_version,
            "model_sha256": self.model_sha256,
            "ortools_version": self.ortools_version,
            "num_search_workers": self.num_search_workers,
            "null_bucket_policy": self.null_bucket_policy,
            "null_bucket_counts": dict(sorted(self.null_bucket_counts.items())),
            "phases": [phase.to_record() for phase in self.phases],
        }


@dataclass(frozen=True, slots=True)
class CaseMixSelectionResult:
    """Exact selection and independently checkable aggregate values."""

    selected_candidate_ids: tuple[str, ...]
    selected_count: int
    total_cost_cents: int
    total_missing_document_count: int
    audit: CaseMixOptimizationAudit

    def to_record(self) -> dict[str, Any]:
        """Serialize the result without exposing solver-specific objects."""

        return {
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "selected_count": self.selected_count,
            "total_cost_cents": self.total_cost_cents,
            "total_missing_document_count": self.total_missing_document_count,
            "audit": self.audit.to_record(),
        }


@dataclass(frozen=True, slots=True)
class _ModelState:
    model: cp_model.CpModel
    selected: Mapping[str, cp_model.IntVar]


def select_exact_case_mix(
    candidates: Sequence[CaseMixCandidate],
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> CaseMixSelectionResult:
    """Select the exact lexicographic optimum under intersecting bucket caps.

    The objectives, in order, are maximum cardinality up to ``target_count``,
    minimum exact integer cost, minimum missing-document count, and the
    lexicographically smallest sorted candidate-ID tuple. Null bucket values do
    not participate in caps. Every objective phase must be proven ``OPTIMAL``.
    """

    normalized = _normalize_inputs(
        candidates,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    phases: list[SolverPhaseAudit] = []

    cardinality_state = _build_model(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    cardinality_expression = sum(cardinality_state.selected.values())
    cardinality_state.model.maximize(cardinality_expression)
    cardinality_solver = _solve_optimal(cardinality_state.model, phase="cardinality")
    optimal_count = cardinality_solver.value(cardinality_expression)
    phases.append(_phase_audit("cardinality", cardinality_solver, optimal_count))

    cost_state = _build_model(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
        exact_count=optimal_count,
    )
    cost_expression = sum(
        candidate.cost_cents * cost_state.selected[candidate.candidate_id]
        for candidate in normalized
    )
    cost_state.model.minimize(cost_expression)
    cost_solver = _solve_optimal(cost_state.model, phase="cost")
    optimal_cost = cost_solver.value(cost_expression)
    phases.append(_phase_audit("cost", cost_solver, optimal_cost))

    missing_state = _build_model(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
        exact_count=optimal_count,
        exact_cost=optimal_cost,
    )
    missing_expression = sum(
        candidate.missing_document_count
        * missing_state.selected[candidate.candidate_id]
        for candidate in normalized
    )
    missing_state.model.minimize(missing_expression)
    missing_solver = _solve_optimal(missing_state.model, phase="missing_documents")
    optimal_missing = missing_solver.value(missing_expression)
    phases.append(_phase_audit("missing_documents", missing_solver, optimal_missing))

    canonical_state = _build_model(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
        exact_count=optimal_count,
        exact_cost=optimal_cost,
        exact_missing=optimal_missing,
    )
    ordered_variables = [
        canonical_state.selected[candidate.candidate_id] for candidate in normalized
    ]
    # With fixed cardinality, the lexicographically smallest selected-ID tuple is
    # exactly the lexicographically largest 0/1 incidence vector in ascending ID
    # order. Fixed DFS with 1 before 0 therefore returns the canonical tuple as
    # its first feasible solution, without an O(candidate_count) solve loop.
    canonical_state.model.add_decision_strategy(
        ordered_variables,
        cp_model.CHOOSE_FIRST,
        cp_model.SELECT_MAX_VALUE,
    )
    canonical_solver = _solve_optimal(
        canonical_state.model,
        phase="lexicographic",
        fixed_search=True,
    )
    selected_values = {
        candidate.candidate_id: canonical_solver.value(
            canonical_state.selected[candidate.candidate_id]
        )
        for candidate in normalized
    }
    if any(value not in (0, 1) for value in selected_values.values()):
        raise SolverDidNotProveOptimalError(
            "lexicographic phase returned a non-Boolean value"
        )
    phases.append(_phase_audit("lexicographic", canonical_solver, optimal_count))

    selected_ids = tuple(
        candidate.candidate_id
        for candidate in normalized
        if selected_values[candidate.candidate_id] == 1
    )
    by_id = {candidate.candidate_id: candidate for candidate in normalized}
    result = CaseMixSelectionResult(
        selected_candidate_ids=selected_ids,
        selected_count=len(selected_ids),
        total_cost_cents=sum(by_id[item].cost_cents for item in selected_ids),
        total_missing_document_count=sum(
            by_id[item].missing_document_count for item in selected_ids
        ),
        audit=CaseMixOptimizationAudit(
            model_schema_version=MODEL_SCHEMA_VERSION,
            model_sha256=_model_sha256(
                normalized,
                target_count=target_count,
                max_per_bucket=max_per_bucket,
            ),
            ortools_version=version("ortools"),
            num_search_workers=1,
            null_bucket_policy=NULL_BUCKET_POLICY,
            null_bucket_counts={
                field: sum(
                    getattr(candidate, field) is None for candidate in normalized
                )
                for field in _BUCKET_FIELDS
            },
            phases=tuple(phases),
        ),
    )
    _validate_case_mix_selection_integrity(
        normalized,
        result,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    return result


def validate_case_mix_selection(
    candidates: Sequence[CaseMixCandidate],
    result: CaseMixSelectionResult,
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> None:
    """Replay the optimizer and validate integrity, feasibility, and audit evidence.

    Arithmetic, caps, commitments, and audit shape are checked without trusting
    solver objects. The exact deterministic optimizer is then rerun and its
    canonical selected IDs must match, so self-consistent but suboptimal forged
    results fail closed rather than being accepted on status strings alone.
    """

    normalized = _normalize_inputs(
        candidates,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    _validate_case_mix_selection_integrity(
        normalized,
        result,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    expected = select_exact_case_mix(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    if result.selected_candidate_ids != expected.selected_candidate_ids:
        raise InvalidSelectionResultError(
            "selection is not the canonical exact optimum"
        )


def _validate_case_mix_selection_integrity(
    candidates: Sequence[CaseMixCandidate],
    result: CaseMixSelectionResult,
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> None:
    """Validate result arithmetic and audit shape without invoking CP-SAT."""

    normalized = _normalize_inputs(
        candidates,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    by_id = {candidate.candidate_id: candidate for candidate in normalized}
    selected_ids = result.selected_candidate_ids
    if selected_ids != tuple(
        sorted(selected_ids, key=lambda item: (item.casefold(), item))
    ):
        raise InvalidSelectionResultError("selected candidate IDs are not sorted")
    if len(selected_ids) != len(set(selected_ids)):
        raise InvalidSelectionResultError("selected candidate IDs are not unique")
    unknown = sorted(set(selected_ids) - by_id.keys())
    if unknown:
        raise InvalidSelectionResultError(f"selection contains unknown IDs: {unknown}")
    if len(selected_ids) > target_count:
        raise InvalidSelectionResultError("selection exceeds target_count")
    if result.selected_count != len(selected_ids):
        raise InvalidSelectionResultError("selected_count does not reconcile")
    expected_cost = sum(by_id[item].cost_cents for item in selected_ids)
    if result.total_cost_cents != expected_cost:
        raise InvalidSelectionResultError("total_cost_cents does not reconcile")
    expected_missing = sum(by_id[item].missing_document_count for item in selected_ids)
    if result.total_missing_document_count != expected_missing:
        raise InvalidSelectionResultError(
            "total_missing_document_count does not reconcile"
        )
    if max_per_bucket is not None:
        for field in _BUCKET_FIELDS:
            bucket_counts: dict[str, int] = defaultdict(int)
            for candidate_id in selected_ids:
                bucket = getattr(by_id[candidate_id], field)
                if bucket is not None:
                    bucket_counts[bucket] += 1
            if any(count > max_per_bucket for count in bucket_counts.values()):
                raise InvalidSelectionResultError(f"selection violates {field} cap")

    audit = result.audit
    expected_hash = _model_sha256(
        normalized,
        target_count=target_count,
        max_per_bucket=max_per_bucket,
    )
    if audit.model_schema_version != MODEL_SCHEMA_VERSION:
        raise InvalidSelectionResultError("unexpected model schema version")
    if audit.model_sha256 != expected_hash:
        raise InvalidSelectionResultError("model SHA-256 does not match inputs")
    if audit.num_search_workers != 1:
        raise InvalidSelectionResultError("selection was not solved with one worker")
    if audit.null_bucket_policy != NULL_BUCKET_POLICY:
        raise InvalidSelectionResultError("null bucket policy is not uncapped")
    expected_null_counts = {
        field: sum(getattr(candidate, field) is None for candidate in normalized)
        for field in _BUCKET_FIELDS
    }
    if dict(audit.null_bucket_counts) != expected_null_counts:
        raise InvalidSelectionResultError("null bucket counts do not reconcile")
    if not audit.ortools_version:
        raise InvalidSelectionResultError("OR-Tools version is missing")
    expected_phase_values = (
        ("cardinality", result.selected_count),
        ("cost", result.total_cost_cents),
        ("missing_documents", result.total_missing_document_count),
        ("lexicographic", result.selected_count),
    )
    actual_phase_values = tuple((phase.phase, phase.value) for phase in audit.phases)
    if actual_phase_values != expected_phase_values:
        raise InvalidSelectionResultError("solver phase values do not reconcile")
    if any(phase.status != "OPTIMAL" for phase in audit.phases):
        raise InvalidSelectionResultError("not every solver phase is OPTIMAL")


def _normalize_inputs(
    candidates: Sequence[CaseMixCandidate],
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> tuple[CaseMixCandidate, ...]:
    _require_nonnegative_int(target_count, field="target_count")
    _require_optional_bucket_cap(max_per_bucket)
    normalized = tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.candidate_id.casefold(),
                candidate.candidate_id,
            ),
        )
    )
    candidate_ids = [candidate.candidate_id for candidate in normalized]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id values must be unique")
    total_cost = sum(candidate.cost_cents for candidate in normalized)
    total_missing = sum(candidate.missing_document_count for candidate in normalized)
    if total_cost > _MAX_INT64:
        raise ValueError("aggregate cost_cents exceeds CP-SAT int64 range")
    if total_missing > _MAX_INT64:
        raise ValueError("aggregate missing_document_count exceeds CP-SAT int64 range")
    return normalized


def _build_model(
    candidates: Sequence[CaseMixCandidate],
    *,
    target_count: int,
    max_per_bucket: int | None,
    exact_count: int | None = None,
    exact_cost: int | None = None,
    exact_missing: int | None = None,
) -> _ModelState:
    model = cp_model.CpModel()
    selected = {
        candidate.candidate_id: model.new_bool_var(f"selected_{index}")
        for index, candidate in enumerate(candidates)
    }
    cardinality = sum(selected.values())
    model.add(cardinality <= target_count)
    if exact_count is not None:
        model.add(cardinality == exact_count)
    if exact_cost is not None:
        model.add(
            sum(
                candidate.cost_cents * selected[candidate.candidate_id]
                for candidate in candidates
            )
            == exact_cost
        )
    if exact_missing is not None:
        model.add(
            sum(
                candidate.missing_document_count * selected[candidate.candidate_id]
                for candidate in candidates
            )
            == exact_missing
        )
    if max_per_bucket is not None:
        for field in _BUCKET_FIELDS:
            buckets: dict[str, list[cp_model.IntVar]] = defaultdict(list)
            for candidate in candidates:
                bucket = getattr(candidate, field)
                if bucket is not None:
                    buckets[bucket].append(selected[candidate.candidate_id])
            for variables in buckets.values():
                model.add(sum(variables) <= max_per_bucket)
    return _ModelState(model=model, selected=selected)


def _solve_optimal(
    model: cp_model.CpModel,
    *,
    phase: str,
    fixed_search: bool = False,
) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    if fixed_search:
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
        solver.parameters.cp_model_presolve = False
        solver.parameters.symmetry_level = 0
    status = solver.solve(model)
    _require_optimal_status(status, phase=phase)
    return solver


def _require_optimal_status(status: cp_model.CpSolverStatus, *, phase: str) -> None:
    if status != cp_model.OPTIMAL:
        raise SolverDidNotProveOptimalError(
            f"CP-SAT did not prove phase {phase!r} optimal: {status.name}"
        )


def _phase_audit(
    phase: str,
    _solver: cp_model.CpSolver,
    value: int,
) -> SolverPhaseAudit:
    return SolverPhaseAudit(
        phase=phase,
        # _solve_optimal rejects every other status before this is constructed.
        status=cp_model.OPTIMAL.name,
        value=value,
    )


def _model_sha256(
    candidates: Sequence[CaseMixCandidate],
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> str:
    payload = {
        "model_schema_version": MODEL_SCHEMA_VERSION,
        "target_count": target_count,
        "max_per_bucket": max_per_bucket,
        "null_bucket_policy": NULL_BUCKET_POLICY,
        "candidates": [candidate.to_record() for candidate in candidates],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _require_nonnegative_int(value: object, *, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")
    if value > _MAX_INT64:
        raise ValueError(f"{field} exceeds CP-SAT int64 range")


def _require_optional_bucket_cap(value: object) -> None:
    if value is None:
        return
    try:
        _require_nonnegative_int(value, field="max_per_bucket")
    except ValueError as exc:
        raise ValueError(
            "max_per_bucket must be a positive CP-SAT int64 integer or None"
        ) from exc
    if value == 0:
        raise ValueError("max_per_bucket must be positive when supplied")
