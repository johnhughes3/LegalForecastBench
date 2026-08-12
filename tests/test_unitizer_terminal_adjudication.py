"""Provider-free adjudication of exhausted Stage A unitizer candidates."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

import pytest
from legalforecast.unitization.review import (
    TERMINAL_UNITIZER_ADJUDICATION_SCHEMA_VERSION,
    TERMINAL_UNITIZER_FINALIZED_SCHEMA_VERSION,
    UnitizationReviewError,
    apply_terminal_unitizer_reviews,
    canonical_records_sha256,
    canonical_sha256,
    verify_terminal_unitizer_finalized_units,
)
from legalforecast.unitization.unitizer_terminal_review import (
    build_unitizer_terminal_review_queue_record,
)


def test_terminal_add_emits_multiple_units_from_one_candidate_decision() -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = _adjudication(
        receipt,
        review,
        "ADD",
        finalized_units=[_unit("contract"), _unit("fraud", ("motion",))],
    )

    [finalized] = apply_terminal_unitizer_reviews(
        terminal_review_records=[review],
        terminal_escalation_records=[receipt],
        adjudication_records=[adjudication],
    )

    receipt_sha256 = canonical_sha256(receipt)
    assert finalized == {
        "schema_version": TERMINAL_UNITIZER_FINALIZED_SCHEMA_VERSION,
        "status": "finalized",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "unitizer_terminal_escalation_sha256": receipt_sha256,
        "unitizer_terminal_review_queue_sha256": canonical_records_sha256([review]),
        "prediction_units": finalized["prediction_units"],
        "exclusion": None,
        "added_units": finalized["added_units"],
    }
    assert [unit["unit_id"] for unit in finalized["prediction_units"]] == [
        "contract",
        "fraud",
    ]
    assert len(finalized["added_units"]) == 2
    assert {unit["adjudication_id"] for unit in finalized["prediction_units"]} == {
        adjudication["adjudication_id"]
    }
    for unit in finalized["prediction_units"]:
        assert unit["source_unit_sha256s"] == []
        assert unit["added_from_review_ids"] == [review["review_id"]]
        assert unit["unitizer_terminal_escalation_sha256"] == receipt_sha256
        assert unit["predecision_source_document_ids"] == ["complaint", "motion"]
    verify_terminal_unitizer_finalized_units(
        [finalized], [review], [receipt], [adjudication]
    )


def test_terminal_candidate_exclusion_needs_no_frozen_source_units() -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = _adjudication(receipt, review, "CANDIDATE-EXCLUSION")

    [finalized] = apply_terminal_unitizer_reviews(
        terminal_review_records=[review],
        terminal_escalation_records=[receipt],
        adjudication_records=[adjudication],
    )

    assert finalized["status"] == "candidate_excluded"
    assert finalized["prediction_units"] == []
    assert finalized["added_units"] == []
    assert finalized["exclusion"] == {
        "reason": "stage_a_unitization_unresolvable",
        "adjudication_id": adjudication["adjudication_id"],
        "adjudication_sha256": canonical_sha256(adjudication),
    }
    verify_terminal_unitizer_finalized_units(
        [finalized], [review], [receipt], [adjudication]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"terminal_escalation_sha256": "0" * 64}, "terminal escalation"),
        ({"source_unit_ids": []}, "omit source_unit_ids"),
        ({"review_ids": []}, "exactly one terminal review"),
        ({"finalized_units": []}, "one or more units"),
    ],
)
def test_terminal_add_fails_closed_on_invalid_decision_shape(
    mutation: dict[str, Any], message: str
) -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = {
        **_adjudication(receipt, review, "ADD", finalized_units=[_unit("contract")]),
        **mutation,
    }

    with pytest.raises(UnitizationReviewError, match=message):
        apply_terminal_unitizer_reviews(
            terminal_review_records=[review],
            terminal_escalation_records=[receipt],
            adjudication_records=[adjudication],
        )


def test_terminal_add_rejects_unauthenticated_citation() -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = _adjudication(
        receipt,
        review,
        "ADD",
        finalized_units=[_unit("contract", ("outcome-order",))],
    )

    with pytest.raises(UnitizationReviewError, match="unauthenticated predecision"):
        apply_terminal_unitizer_reviews(
            terminal_review_records=[review],
            terminal_escalation_records=[receipt],
            adjudication_records=[adjudication],
        )


def test_terminal_apply_rejects_tampered_receipt_or_queue_binding() -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = _adjudication(
        receipt, review, "ADD", finalized_units=[_unit("contract")]
    )
    tampered_receipt = deepcopy(receipt)
    tampered_receipt["failed_attempts"][0]["failure_message"] = "different"

    with pytest.raises(UnitizationReviewError, match="authenticated escalation"):
        apply_terminal_unitizer_reviews(
            terminal_review_records=[review],
            terminal_escalation_records=[tampered_receipt],
            adjudication_records=[adjudication],
        )


def test_terminal_verifier_rejects_added_unit_substitution() -> None:
    receipt = _receipt()
    review = _review(receipt)
    adjudication = _adjudication(
        receipt, review, "ADD", finalized_units=[_unit("contract")]
    )
    [finalized] = apply_terminal_unitizer_reviews(
        terminal_review_records=[review],
        terminal_escalation_records=[receipt],
        adjudication_records=[adjudication],
    )
    finalized["prediction_units"][0]["claim_name"] = "Substituted"

    with pytest.raises(UnitizationReviewError, match="adjudication output"):
        verify_terminal_unitizer_finalized_units(
            [finalized], [review], [receipt], [adjudication]
        )


def test_normal_structural_add_still_rejects_multiple_units() -> None:
    """The terminal exception must not broaden ordinary omission ADD."""

    from legalforecast.unitization.review import apply_unitization_reviews

    raw = {
        "candidate_id": "cand",
        "case_id": "case-cand",
        "prediction_units": [_unit("existing")],
    }
    review = {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "unit_id": "existing",
        "review_id": "cand:existing:structural:1234567890abcdef",
        "route_reason": "structural_omitted",
        "review_item": {"source_document_ids": ["motion"]},
        "structural_flag_sha256": "1" * 64,
        "raw_prediction_units_sha256": canonical_sha256(raw),
    }
    adjudication = {
        "schema_version": "legalforecast.unitization_adjudication.v2",
        "adjudication_id": "adj-normal-add",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "review_ids": [review["review_id"]],
        "disposition": "ADD",
        "finalized_units": [_unit("new-1"), _unit("new-2")],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "ordinary omission",
    }

    with pytest.raises(UnitizationReviewError, match="invalid ADD output count"):
        apply_unitization_reviews(
            prediction_unit_records=[raw],
            review_records=[review],
            adjudication_records=[adjudication],
        )


def _receipt() -> dict[str, Any]:
    prompt = "Use only the supplied predecision sources."
    return {
        "schema_version": "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "provider_attempt_namespace": "claim-ontology-v5",
        "unitizer_model_key": "anthropic:claude-sonnet-4-6",
        "model_registry_sha256": "1" * 64,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "predecision_source_commitments": [
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "docket_entry_number": 1,
                "description": "Complaint",
                "markdown_sha256": "sha256:" + "2" * 64,
            },
            {
                "source_document_id": "motion",
                "document_role": "motion_to_dismiss_memorandum",
                "docket_entry_number": 8,
                "description": "Motion to dismiss",
                "markdown_sha256": "sha256:" + "3" * 64,
            },
        ],
        "failed_attempts": [
            {
                "attempt_ordinal": attempt,
                "raw_response_sha256": "sha256:" + f"{attempt}" * 64,
                "normalized_response_sha256": "sha256:" + f"{attempt + 3}" * 64,
                "failure_type": "LlmResponseValidationError",
                "failure_message": "reconstruction failed",
            }
            for attempt in (1, 2, 3)
        ],
    }


def _review(receipt: dict[str, Any]) -> dict[str, Any]:
    return build_unitizer_terminal_review_queue_record(receipt)


def _adjudication(
    receipt: dict[str, Any],
    review: dict[str, Any],
    disposition: str,
    *,
    finalized_units: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record = {
        "schema_version": TERMINAL_UNITIZER_ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": f"adj-{disposition.lower()}",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "review_ids": [review["review_id"]],
        "terminal_escalation_sha256": canonical_sha256(receipt),
        "disposition": disposition,
        "finalized_units": finalized_units or [],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Resolved the exhausted unitizer candidate.",
    }
    if disposition == "CANDIDATE-EXCLUSION":
        record["exclusion_reason"] = "stage_a_unitization_unresolvable"
    return record


def _unit(
    unit_id: str, documents: tuple[str, ...] = ("complaint", "motion")
) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [
            {
                "document_id": document_id,
                "docket_entry_number": None,
                "page": 1,
                "paragraph": None,
                "excerpt": None,
            }
            for document_id in documents
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }
