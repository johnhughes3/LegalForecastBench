from __future__ import annotations

import pytest
from legalforecast.labeling import (
    AdjudicatedReview,
    AmendmentClass,
    LawyerReviewResponse,
    OutcomeCitation,
    OutcomeLabel,
    ReviewDisagreementState,
    ReviewerExpertise,
    build_human_reliability_report,
)


def _label(unit_id: str, fully_dismissed: bool | None) -> OutcomeLabel:
    if fully_dismissed is None:
        return OutcomeLabel(
            unit_id=unit_id,
            fully_dismissed=None,
            amendment_class=AmendmentClass.AMBIGUOUS,
            ambiguous=True,
            label_confidence=0.65,
            supporting_citations=(
                OutcomeCitation(
                    document_id="decision-fixture",
                    excerpt="The order is ambiguous as to the unit.",
                ),
            ),
            first_written_disposition_id="decision-fixture",
            first_written_disposition_date="2026-05-18",
        )

    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=fully_dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if fully_dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.9,
        supporting_citations=(
            OutcomeCitation(
                document_id="decision-fixture",
                excerpt="The court resolves the challenged claim.",
            ),
        ),
        first_written_disposition_id="decision-fixture",
        first_written_disposition_date="2026-05-18",
    )


def _response(
    *,
    review_id: str,
    unit_id: str,
    reviewer_id: str,
    fully_dismissed: bool,
    confidence: float = 0.9,
) -> LawyerReviewResponse:
    return LawyerReviewResponse(
        review_id=review_id,
        reviewer_id=reviewer_id,
        reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        proposed_label=_label(unit_id, fully_dismissed),
        confidence=confidence,
        minutes_spent=12.0,
        notes="Fixture senior-litigator label.",
    )


def _review(
    *,
    number: int,
    left_label: bool,
    right_label: bool,
    adjudicated_label: bool | None,
    right_confidence: float = 0.9,
) -> AdjudicatedReview:
    review_id = f"review-{number}"
    unit_id = f"unit-{number}"
    return AdjudicatedReview(
        review_id=review_id,
        candidate_id=f"candidate-{number}",
        unit_id=unit_id,
        reviewer_responses=(
            _response(
                review_id=review_id,
                unit_id=unit_id,
                reviewer_id="senior-a",
                fully_dismissed=left_label,
            ),
            _response(
                review_id=review_id,
                unit_id=unit_id,
                reviewer_id="senior-b",
                fully_dismissed=right_label,
                confidence=right_confidence,
            ),
        ),
        adjudicated_label=_label(unit_id, adjudicated_label),
        adjudicator_id="expert-panel",
        adjudication_notes="Fixture adjudication for reliability reporting.",
    )


def test_fixture_human_reliability_report_establishes_floor_and_pain_points() -> None:
    report = build_human_reliability_report(
        (
            _review(
                number=1, left_label=True, right_label=True, adjudicated_label=True
            ),
            _review(
                number=2,
                left_label=True,
                right_label=False,
                adjudicated_label=False,
                right_confidence=0.72,
            ),
            _review(
                number=3, left_label=False, right_label=False, adjudicated_label=False
            ),
            _review(
                number=4, left_label=False, right_label=True, adjudicated_label=None
            ),
        ),
        study_id="fixture-human-reliability",
        source_note="Fixture-only pilot because live clean packets are unavailable.",
        complexity_by_unit_id={
            "unit-1": "simple_single_claim",
            "unit-2": "partial_theory_survival",
            "unit-3": "simple_survival",
            "unit-4": "leave_to_amend_boundary",
        },
        schema_pain_points_by_unit_id={
            "unit-2": ("partial_theory_survival",),
            "unit-4": ("leave_to_amend_boundary",),
        },
    )

    assert report.unit_count == 4
    assert report.senior_pair_unit_count == 4
    assert report.raw_disagreement_rate == 0.5
    assert report.human_floor_error_rate == 0.5
    assert report.cohen_kappa == pytest.approx(0.0)
    assert report.ambiguous_unit_share == 0.25
    assert report.schema_pain_point_counts == {
        "ambiguous_adjudication": 1,
        "leave_to_amend_boundary": 1,
        "low_reviewer_confidence": 1,
        "partial_theory_survival": 1,
        "senior_reviewer_disagreement": 2,
    }
    assert "fixture-only pilot" in report.recommendation
    assert "schema guidance" in report.recommendation

    markdown = report.to_markdown()

    assert "Senior raw disagreement rate: 0.500" in markdown
    assert "Cohen kappa: 0.000" in markdown
    assert "partial_theory_survival: 1" in markdown


def test_human_reliability_report_requires_senior_pair_review() -> None:
    review = AdjudicatedReview(
        review_id="review-1",
        candidate_id="candidate-1",
        unit_id="unit-1",
        reviewer_responses=(
            LawyerReviewResponse(
                review_id="review-1",
                reviewer_id="junior-a",
                reviewer_expertise=ReviewerExpertise.JUNIOR_LITIGATOR,
                proposed_label=_label("unit-1", fully_dismissed=True),
                confidence=0.8,
                minutes_spent=9.0,
                notes="Junior review only.",
            ),
        ),
        adjudicated_label=_label("unit-1", fully_dismissed=True),
        adjudicator_id="expert-panel",
        adjudication_notes="No paired senior review.",
    )

    with pytest.raises(ValueError, match="two senior litigator reviews"):
        build_human_reliability_report(
            (review,),
            study_id="bad-fixture",
            source_note="No paired senior reviewers.",
        )


def test_human_reliability_unit_records_senior_disagreement_state() -> None:
    report = build_human_reliability_report(
        (
            _review(
                number=1,
                left_label=True,
                right_label=False,
                adjudicated_label=False,
            ),
        ),
        study_id="single-disagreement",
        source_note="One paired senior review.",
    )

    unit = report.unit_results[0]

    assert unit.senior_disagreement_state is ReviewDisagreementState.DISAGREEMENT
    assert unit.has_senior_disagreement is True
    assert unit.to_record()["senior_disagreement_state"] == "disagreement"
