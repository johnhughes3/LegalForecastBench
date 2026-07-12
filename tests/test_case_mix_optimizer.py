from __future__ import annotations

import itertools
import random
from dataclasses import replace

import pytest
from legalforecast.ingestion import case_mix_optimizer
from legalforecast.ingestion.case_mix_optimizer import (
    NULL_BUCKET_POLICY,
    CaseMixCandidate,
    InvalidSelectionResultError,
    SolverDidNotProveOptimalError,
    select_exact_case_mix,
    validate_case_mix_selection,
)
from ortools.sat.python import cp_model

_BUCKET_FIELDS = (
    "court",
    "nos_macro_category",
    "related_family_id",
    "mdl_family_id",
)


def test_exact_selector_avoids_greedy_false_shortfall() -> None:
    candidates = (
        _candidate("a", 0, court="court-a", nos_macro_category="nos-x"),
        _candidate("b", 1, court="court-a", nos_macro_category="nos-y"),
        _candidate("c", 1, court="court-b", nos_macro_category="nos-x"),
    )

    result = select_exact_case_mix(candidates, target_count=2, max_per_bucket=1)

    assert result.selected_candidate_ids == ("b", "c")
    assert result.selected_count == 2
    assert result.total_cost_cents == 2


def test_exact_selector_avoids_greedy_nonminimal_cost() -> None:
    candidates = (
        _candidate("a", 0, court="court-a", nos_macro_category="nos-x"),
        _candidate("b", 1, court="court-a", nos_macro_category="nos-y"),
        _candidate("c", 1, court="court-b", nos_macro_category="nos-x"),
        _candidate("d", 3, court="court-b", nos_macro_category="nos-y"),
    )

    result = select_exact_case_mix(candidates, target_count=2, max_per_bucket=1)

    assert result.selected_candidate_ids == ("b", "c")
    assert result.total_cost_cents == 2


def test_null_buckets_are_uncapped_and_audited() -> None:
    candidates = tuple(_candidate(f"case-{index}", index) for index in range(4))

    result = select_exact_case_mix(candidates, target_count=4, max_per_bucket=1)

    assert result.selected_count == 4
    assert result.audit.null_bucket_policy == NULL_BUCKET_POLICY
    assert result.audit.null_bucket_counts == {
        "court": 4,
        "nos_macro_category": 4,
        "related_family_id": 4,
        "mdl_family_id": 4,
    }


def test_objective_order_uses_missing_count_then_canonical_ids() -> None:
    candidates = (
        _candidate("Beta", 10, missing=2),
        _candidate("alpha", 10, missing=1),
        _candidate("Alpha", 10, missing=1),
    )

    result = select_exact_case_mix(candidates, target_count=1, max_per_bucket=None)

    assert result.selected_candidate_ids == ("Alpha",)
    assert result.total_missing_document_count == 1
    assert [phase.phase for phase in result.audit.phases] == [
        "cardinality",
        "cost",
        "missing_documents",
        "lexicographic",
    ]
    assert {phase.status for phase in result.audit.phases} == {"OPTIMAL"}
    assert result.audit.num_search_workers == 1
    assert result.audit.ortools_version


def test_input_permutations_have_identical_result_and_model_hash() -> None:
    candidates = (
        _candidate("z", 2, court="one"),
        _candidate("A", 1, court="two"),
        _candidate("a", 1, court="three"),
        _candidate("m", 0, court="one"),
    )
    expected = select_exact_case_mix(
        candidates,
        target_count=3,
        max_per_bucket=2,
    )

    for permutation in itertools.permutations(candidates):
        actual = select_exact_case_mix(
            permutation,
            target_count=3,
            max_per_bucket=2,
        )
        assert actual.selected_candidate_ids == expected.selected_candidate_ids
        assert actual.audit.model_sha256 == expected.audit.model_sha256


def test_random_small_instances_match_brute_force_oracle() -> None:
    rng = random.Random(20260712)
    bucket_values = (None, "x", "y", "z")
    for _ in range(50):
        size = rng.randint(0, 12)
        candidates = tuple(
            CaseMixCandidate(
                candidate_id=f"case-{index:02d}",
                cost_cents=rng.randint(0, 8),
                missing_document_count=rng.randint(0, 4),
                court=rng.choice(bucket_values),
                nos_macro_category=rng.choice(bucket_values),
                related_family_id=rng.choice(bucket_values),
                mdl_family_id=rng.choice(bucket_values),
            )
            for index in range(size)
        )
        target_count = rng.randint(0, size)
        max_per_bucket = rng.choice((None, 1, 2, 3))
        shuffled = list(candidates)
        rng.shuffle(shuffled)

        result = select_exact_case_mix(
            shuffled,
            target_count=target_count,
            max_per_bucket=max_per_bucket,
        )

        expected = _brute_force(
            candidates,
            target_count=target_count,
            max_per_bucket=max_per_bucket,
        )
        assert result.selected_candidate_ids == expected


def test_duplicate_candidate_ids_fail_closed() -> None:
    candidates = (_candidate("duplicate", 1), _candidate("duplicate", 2))

    with pytest.raises(ValueError, match="candidate_id values must be unique"):
        select_exact_case_mix(candidates, target_count=1, max_per_bucket=None)


def test_candidate_allows_zero_exact_cost_and_missing_count() -> None:
    candidate = _candidate("valid", 0)

    assert candidate.cost_cents == 0
    assert candidate.missing_document_count == 0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"cost_cents": -1, "missing_document_count": 0}, "cost_cents"),
        (
            {"cost_cents": 0, "missing_document_count": -1},
            "missing_document_count",
        ),
        (
            {"cost_cents": 0, "missing_document_count": 0, "court": " "},
            "court",
        ),
    ],
)
def test_invalid_candidate_values_fail_closed(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CaseMixCandidate(candidate_id="bad", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("max_per_bucket", [0, -1, True, 1 << 63])
def test_invalid_bucket_cap_fails_closed(max_per_bucket: int) -> None:
    with pytest.raises(ValueError, match="max_per_bucket"):
        select_exact_case_mix((), target_count=0, max_per_bucket=max_per_bucket)


def test_independent_validator_detects_tampered_aggregate() -> None:
    candidates = (_candidate("a", 10), _candidate("b", 20))
    result = select_exact_case_mix(candidates, target_count=1, max_per_bucket=None)

    with pytest.raises(InvalidSelectionResultError, match="does not reconcile"):
        validate_case_mix_selection(
            candidates,
            replace(result, total_cost_cents=result.total_cost_cents + 1),
            target_count=1,
            max_per_bucket=None,
        )


def test_independent_validator_detects_tampered_model_hash() -> None:
    candidates = (_candidate("a", 10),)
    result = select_exact_case_mix(candidates, target_count=1, max_per_bucket=None)
    tampered = replace(result, audit=replace(result.audit, model_sha256="0" * 64))

    with pytest.raises(InvalidSelectionResultError, match="SHA-256"):
        validate_case_mix_selection(
            candidates,
            tampered,
            target_count=1,
            max_per_bucket=None,
        )


def test_validator_detects_self_consistent_suboptimal_forgery() -> None:
    candidates = (_candidate("a", 10), _candidate("b", 20))
    optimal = select_exact_case_mix(
        candidates,
        target_count=1,
        max_per_bucket=None,
    )
    forged = replace(
        optimal,
        selected_candidate_ids=("b",),
        total_cost_cents=20,
        audit=replace(
            optimal.audit,
            phases=tuple(
                replace(phase, value=20) if phase.phase == "cost" else phase
                for phase in optimal.audit.phases
            ),
        ),
    )

    with pytest.raises(
        InvalidSelectionResultError,
        match="not the canonical exact optimum",
    ):
        validate_case_mix_selection(
            candidates,
            forged,
            target_count=1,
            max_per_bucket=None,
        )


def test_validator_detects_self_consistent_noncanonical_forgery() -> None:
    candidates = (_candidate("a", 10), _candidate("b", 10))
    optimal = select_exact_case_mix(
        candidates,
        target_count=1,
        max_per_bucket=None,
    )
    forged = replace(optimal, selected_candidate_ids=("b",))

    with pytest.raises(
        InvalidSelectionResultError,
        match="not the canonical exact optimum",
    ):
        validate_case_mix_selection(
            candidates,
            forged,
            target_count=1,
            max_per_bucket=None,
        )


def test_nonoptimal_solver_status_fails_closed() -> None:
    with pytest.raises(SolverDidNotProveOptimalError, match="did not prove"):
        case_mix_optimizer._require_optimal_status(
            cp_model.FEASIBLE,
            phase="injected",
        )


def test_result_record_contains_auditable_solver_metadata() -> None:
    result = select_exact_case_mix(
        (_candidate("a", 1, court="court"),),
        target_count=1,
        max_per_bucket=1,
    )

    record = result.to_record()

    assert record["selected_candidate_ids"] == ["a"]
    audit = record["audit"]
    assert isinstance(audit, dict)
    assert audit["model_sha256"] == result.audit.model_sha256
    assert audit["null_bucket_policy"] == "uncapped"
    assert audit["num_search_workers"] == 1
    assert [phase["status"] for phase in audit["phases"]] == ["OPTIMAL"] * 4


def _candidate(
    candidate_id: str,
    cost: int,
    *,
    missing: int = 0,
    court: str | None = None,
    nos_macro_category: str | None = None,
    related_family_id: str | None = None,
    mdl_family_id: str | None = None,
) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id=candidate_id,
        cost_cents=cost,
        missing_document_count=missing,
        court=court,
        nos_macro_category=nos_macro_category,
        related_family_id=related_family_id,
        mdl_family_id=mdl_family_id,
    )


def _brute_force(
    candidates: tuple[CaseMixCandidate, ...],
    *,
    target_count: int,
    max_per_bucket: int | None,
) -> tuple[str, ...]:
    ordered = tuple(
        sorted(
            candidates,
            key=lambda item: (item.candidate_id.casefold(), item.candidate_id),
        )
    )
    feasible: list[tuple[CaseMixCandidate, ...]] = []
    for size in range(target_count + 1):
        for subset in itertools.combinations(ordered, size):
            if _within_caps(subset, max_per_bucket=max_per_bucket):
                feasible.append(subset)
    best = min(
        feasible,
        key=lambda subset: (
            -len(subset),
            sum(item.cost_cents for item in subset),
            sum(item.missing_document_count for item in subset),
            tuple((item.candidate_id.casefold(), item.candidate_id) for item in subset),
        ),
    )
    return tuple(candidate.candidate_id for candidate in best)


def _within_caps(
    subset: tuple[CaseMixCandidate, ...],
    *,
    max_per_bucket: int | None,
) -> bool:
    if max_per_bucket is None:
        return True
    for field in _BUCKET_FIELDS:
        values = [getattr(candidate, field) for candidate in subset]
        for bucket in {value for value in values if value is not None}:
            if values.count(bucket) > max_per_bucket:
                return False
    return True
