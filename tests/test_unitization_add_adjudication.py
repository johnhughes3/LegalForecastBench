"""Regressions for the ADD adjudication that repairs a structural omission.

A structural reviewer can only flag; when it reports that a separately
challenged claim-defendant unit is missing from Stage A, every pre-ADD
disposition resolves that review by consuming the neighbouring unit the flag
happens to name. ACCEPT discards the finding, SPLIT and AMEND forge a hash link
claiming the missing unit was derived from an unrelated raw unit, and
CANDIDATE-EXCLUSION throws away a usable candidate. ADD is the narrow action
that adds the omitted unit while leaving every raw unit intact.

These tests pin both halves of the contract: the applicator that consumes the
authenticated omitted review, and the independent verifier that has to
reproduce the added unit's evidence chain from the raw, review, and
adjudication inputs alone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    FINALIZED_SCHEMA_VERSION,
    STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION,
    UnitizationReviewError,
    apply_unitization_reviews,
    canonical_sha256,
    require_finalized_envelopes,
    verify_finalized_prediction_units,
)


def test_add_binds_the_omitted_unit_without_consuming_a_raw_unit() -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    adjudication = _add_adjudication(
        "cand", [review], _unit("a-omitted", documents=("motion",))
    )

    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw],
        review_records=[review],
        adjudication_records=[adjudication],
    )

    assert finalized["schema_version"] == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
    assert finalized["dropped_units"] == []
    units = {unit["unit_id"]: unit for unit in finalized["prediction_units"]}
    # The flagged unit is untouched: ADD neither consumes it nor rewrites it.
    assert units["a"]["disposition"] == "ACCEPT"
    assert units["a"]["adjudication_id"].startswith("automatic:")
    added = units["a-omitted"]
    assert added["disposition"] == "ADD"
    assert added["source_unit_sha256s"] == []
    assert added["adjudication_id"] == adjudication["adjudication_id"]
    assert added["adjudication_sha256"] == canonical_sha256(adjudication)
    assert added["added_from_review_ids"] == [review["review_id"]]
    assert added["structural_flag_sha256"] == review["structural_flag_sha256"]
    assert added["raw_prediction_units_sha256"] == canonical_sha256(raw)
    assert added["predecision_source_document_ids"] == ["motion"]
    verify_finalized_prediction_units([finalized], [raw], [adjudication], [review])
    require_finalized_envelopes([finalized])


def test_add_and_drop_share_one_successor_schema() -> None:
    raw = _candidate("cand", [_unit("a"), _unit("b")])
    omission = _omission_review(raw, "a")
    spurious = _omission_review(raw, "b", flag="flag-drop", route="structural_spurious")
    add = _add_adjudication("cand", [omission], _unit("a-omitted", ("motion",)))
    drop = {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": "adj-drop",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "review_ids": [spurious["review_id"]],
        "source_unit_ids": ["b"],
        "disposition": "DROP",
        "finalized_units": [],
        "drop_reason": "spurious_nonunit",
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Not a claim-defendant unit.",
    }

    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw],
        review_records=[omission, spurious],
        adjudication_records=[add, drop],
    )

    assert finalized["schema_version"] == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
    assert [row["unit_id"] for row in finalized["dropped_units"]] == ["b"]
    assert [unit["unit_id"] for unit in finalized["prediction_units"]] == [
        "a",
        "a-omitted",
    ]
    verify_finalized_prediction_units(
        [finalized], [raw], [add, drop], [omission, spurious]
    )


def test_add_rejects_a_review_from_another_candidate() -> None:
    raw = _candidate("cand", [_unit("a")])
    other = _candidate("other", [_unit("a")])
    review = _omission_review(other, "a")
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))

    with pytest.raises(UnitizationReviewError, match="unknown review"):
        apply_unitization_reviews(
            prediction_unit_records=[raw, other],
            review_records=[review],
            adjudication_records=[adjudication],
        )


def test_add_rejects_evidence_raised_against_another_raw_envelope() -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    review["raw_prediction_units_sha256"] = canonical_sha256(
        _candidate("cand", [_unit("a"), _unit("b")])
    )
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))

    with pytest.raises(UnitizationReviewError, match="another raw candidate"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[adjudication],
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"route_reason": "structural_combined"}, "omitted structural review"),
        ({"structural_flag_sha256": ""}, "structural_flag_sha256 is required"),
        ({"review_item": {"source_document_ids": []}}, "predecision citations"),
        ({"review_item": None}, "predecision citations"),
    ],
)
def test_add_requires_an_authenticated_omission_review(
    mutation: dict[str, Any], message: str
) -> None:
    raw = _candidate("cand", [_unit("a")])
    review = {**_omission_review(raw, "a"), **mutation}
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))

    with pytest.raises(UnitizationReviewError, match=message):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[adjudication],
        )


def test_add_rejects_an_uncited_or_unauthenticated_added_unit() -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    uncited = _unit("a-omitted")
    uncited["source_citations"] = []

    with pytest.raises(UnitizationReviewError, match="lacks predecision citations"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[_add_adjudication("cand", [review], uncited)],
        )
    with pytest.raises(UnitizationReviewError, match="unauthenticated predecision"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[
                _add_adjudication(
                    "cand", [review], _unit("a-omitted", ("uncited-exhibit",))
                )
            ],
        )


def test_add_rejects_incomplete_coverage_of_the_flagged_documents() -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a", documents=("motion", "opposition"))
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))

    with pytest.raises(UnitizationReviewError, match="every flagged document"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[adjudication],
        )


def test_add_rejects_reviews_from_two_different_structural_flags() -> None:
    raw = _candidate("cand", [_unit("a"), _unit("b")])
    first = _omission_review(raw, "a")
    second = _omission_review(raw, "b", flag="flag-2")
    adjudication = _add_adjudication(
        "cand", [first, second], _unit("a-omitted", ("motion",))
    )

    with pytest.raises(UnitizationReviewError, match="one structural omission flag"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[first, second],
            adjudication_records=[adjudication],
        )


def test_one_add_resolves_every_review_row_of_the_same_flag() -> None:
    raw = _candidate("cand", [_unit("a"), _unit("b")])
    first = _omission_review(raw, "a")
    second = _omission_review(raw, "b")
    adjudication = _add_adjudication(
        "cand", [first, second], _unit("a-omitted", ("motion",))
    )

    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw],
        review_records=[first, second],
        adjudication_records=[adjudication],
    )

    added = _added_unit(finalized)
    assert added["added_from_review_ids"] == [first["review_id"], second["review_id"]]
    assert [unit["unit_id"] for unit in finalized["prediction_units"]] == [
        "a",
        "a-omitted",
        "b",
    ]
    verify_finalized_prediction_units(
        [finalized], [raw], [adjudication], [first, second]
    )


@pytest.mark.parametrize("added_unit_id", ["a", "a-omitted"])
def test_add_rejects_duplicate_unit_ids(added_unit_id: str) -> None:
    raw = _candidate("cand", [_unit("a")])
    first = _omission_review(raw, "a")
    second = _omission_review(raw, "a", review_suffix="-second")
    adjudications = [
        _add_adjudication(
            "cand", [first], _unit("a-omitted", ("motion",)), suffix="-first"
        ),
        _add_adjudication(
            "cand",
            [second],
            _unit(added_unit_id, ("motion",)),
            suffix="-second",
        ),
    ]

    with pytest.raises(UnitizationReviewError, match="duplicate added unit_id"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[first, second],
            adjudication_records=adjudications,
        )


def test_add_may_not_consume_units_or_declare_its_own_provenance() -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    consuming = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))
    consuming["source_unit_ids"] = ["a"]
    forged_unit = _unit("a-omitted", ("motion",))
    forged_unit["source_unit_sha256s"] = [canonical_sha256(_unit("a"))]

    with pytest.raises(UnitizationReviewError, match="must not consume source units"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[consuming],
        )
    with pytest.raises(UnitizationReviewError, match="may not declare its own"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[_add_adjudication("cand", [review], forged_unit)],
        )


@pytest.mark.parametrize("unit_count", [0, 2])
def test_add_must_emit_exactly_one_unit(unit_count: int) -> None:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))
    adjudication["finalized_units"] = [
        _unit(f"omitted-{index}", ("motion",)) for index in range(unit_count)
    ]

    with pytest.raises(UnitizationReviewError, match="invalid ADD output count"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[adjudication],
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"source_unit_sha256s": ["a" * 64]}, "must not derive from raw units"),
        ({"structural_flag_sha256": "b" * 64}, "broken added-unit evidence link"),
        ({"raw_prediction_units_sha256": "c" * 64}, "broken added-unit evidence link"),
        (
            {"predecision_source_document_ids": ["motion", "opposition"]},
            "broken added-unit evidence link",
        ),
        ({"added_from_review_ids": []}, "broken added-unit review link"),
        ({"adjudication_sha256": "d" * 64}, "broken added-unit hash link"),
        ({"adjudication_id": "adj-unknown"}, "broken added-unit hash link"),
    ],
)
def test_verifier_rejects_a_tampered_added_unit(
    mutation: dict[str, Any], message: str
) -> None:
    raw, review, adjudication, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    _added_unit(broken).update(mutation)

    with pytest.raises(UnitizationReviewError, match=message):
        verify_finalized_prediction_units([broken], [raw], [adjudication], [review])


def test_verifier_rejects_a_hand_written_add_that_consumes_a_source_unit() -> None:
    """The verifier enforces the no-consumption rule on artifacts it did not build."""

    raw, review, adjudication, finalized = _finalized_add_fixture()
    consuming = deepcopy(adjudication)
    consuming["source_unit_ids"] = ["a"]
    broken = deepcopy(finalized)
    _added_unit(broken)["adjudication_sha256"] = canonical_sha256(consuming)

    with pytest.raises(UnitizationReviewError, match="consumes source units"):
        verify_finalized_prediction_units([broken], [raw], [consuming], [review])


def test_verifier_rejects_an_added_unit_smuggled_into_the_v2_schema() -> None:
    raw, review, adjudication, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    broken["schema_version"] = FINALIZED_SCHEMA_VERSION

    with pytest.raises(UnitizationReviewError, match="requires the v3 schema"):
        verify_finalized_prediction_units([broken], [raw], [adjudication], [review])
    with pytest.raises(UnitizationReviewError, match="requires the v3 schema"):
        require_finalized_envelopes([broken])


def test_verifier_rejects_an_added_unit_that_shadows_a_raw_unit() -> None:
    raw, review, adjudication, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    _added_unit(broken)["unit_id"] = "a"
    broken["prediction_units"] = [
        unit for unit in broken["prediction_units"] if unit["disposition"] == "ADD"
    ]

    with pytest.raises(UnitizationReviewError, match="shadows a raw unit"):
        verify_finalized_prediction_units([broken], [raw], [adjudication], [review])


def test_verifier_rejects_a_removed_added_unit_with_a_live_adjudication() -> None:
    raw, review, adjudication, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    broken["prediction_units"] = [
        unit for unit in broken["prediction_units"] if unit["disposition"] != "ADD"
    ]

    with pytest.raises(UnitizationReviewError, match="does not consume adjudications"):
        verify_finalized_prediction_units([broken], [raw], [adjudication], [review])


def test_verifier_rejects_an_added_unit_moved_to_another_candidate() -> None:
    raw = _candidate("cand", [_unit("a")])
    other_raw = _candidate("other", [_unit("z")])
    review = _omission_review(raw, "a")
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))
    finalized = apply_unitization_reviews(
        prediction_unit_records=[raw, other_raw],
        review_records=[review],
        adjudication_records=[adjudication],
    )
    by_candidate = {record["candidate_id"]: deepcopy(record) for record in finalized}
    source = by_candidate["cand"]
    moved = by_candidate["other"]
    moved["prediction_units"].append(deepcopy(_added_unit(source)))
    source["prediction_units"] = [
        unit for unit in source["prediction_units"] if unit["disposition"] != "ADD"
    ]

    with pytest.raises(UnitizationReviewError, match="broken added-unit hash link"):
        verify_finalized_prediction_units(
            [source, moved], [raw, other_raw], [adjudication], [review]
        )


def test_boundary_rejects_an_added_unit_bound_to_another_raw_envelope() -> None:
    _, _, _, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    _added_unit(broken)["raw_prediction_units_sha256"] = "e" * 64

    with pytest.raises(UnitizationReviewError, match="another raw candidate"):
        require_finalized_envelopes([broken])


def test_boundary_rejects_an_added_unit_without_review_links() -> None:
    _, _, _, finalized = _finalized_add_fixture()
    broken = deepcopy(finalized)
    _added_unit(broken)["added_from_review_ids"] = []

    with pytest.raises(UnitizationReviewError, match="lacks review links"):
        require_finalized_envelopes([broken])


def _finalized_add_fixture() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    raw = _candidate("cand", [_unit("a")])
    review = _omission_review(raw, "a")
    adjudication = _add_adjudication("cand", [review], _unit("a-omitted", ("motion",)))
    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw],
        review_records=[review],
        adjudication_records=[adjudication],
    )
    return raw, review, adjudication, finalized


def _added_unit(record: dict[str, Any]) -> dict[str, Any]:
    [added] = [
        unit for unit in record["prediction_units"] if unit["disposition"] == "ADD"
    ]
    return added


def _candidate(candidate_id: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "prediction_units": units,
    }


def _omission_review(
    raw_record: dict[str, Any],
    unit_id: str,
    *,
    flag: str = "flag-1",
    documents: tuple[str, ...] = ("motion",),
    route: str = "structural_omitted",
    review_suffix: str = "",
) -> dict[str, Any]:
    """Build a queue row shaped exactly like a merged structural-flag review."""

    candidate_id = raw_record["candidate_id"]
    flag_sha256 = canonical_sha256({"flag": flag})
    return {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": candidate_id,
        "case_id": raw_record["case_id"],
        "unit_id": unit_id,
        "review_id": (
            f"{candidate_id}:{unit_id}:structural:{flag_sha256[:16]}{review_suffix}"
        ),
        "route_reason": route,
        "review_item": {
            "unit_id": unit_id,
            "reason": route,
            "notes": "A separately challenged theory is absent.",
            "citation_excerpt": "dismiss the alternative theory",
            "source_document_ids": list(documents),
        },
        "structural_flag_sha256": flag_sha256,
        "raw_prediction_units_sha256": canonical_sha256(raw_record),
        "reviewer_model_key": "google:gemini-flash",
        "model_registry_sha256": "registry-hash",
    }


def _add_adjudication(
    candidate_id: str,
    reviews: list[dict[str, Any]],
    added_unit: dict[str, Any],
    *,
    suffix: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": f"adj-{candidate_id}-add{suffix}",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "review_ids": [review["review_id"] for review in reviews],
        "disposition": "ADD",
        "finalized_units": [added_unit],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Added the omitted unit from the predecision record.",
    }


def _unit(unit_id: str, documents: tuple[str, ...] = ("complaint",)) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [
            {"document_id": document_id, "page": 1} for document_id in documents
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }
