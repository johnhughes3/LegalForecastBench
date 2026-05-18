from __future__ import annotations

import json

import pytest
from legalforecast.labeling import (
    AdjudicatedReview,
    AmendmentClass,
    LawyerReviewPacket,
    LawyerReviewResponse,
    OutcomeCitation,
    OutcomeLabel,
    ReviewDisagreementState,
    ReviewerExpertise,
    ReviewMaterial,
    ReviewMaterialKind,
    ReviewPacketAudience,
)


def _label(unit_id: str, fully_dismissed: bool) -> OutcomeLabel:
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
                document_id="decision-42",
                excerpt="The court resolves the challenged claim.",
            ),
        ),
        first_written_disposition_id="decision-42",
        first_written_disposition_date="2026-05-18",
    )


def _packet() -> LawyerReviewPacket:
    return LawyerReviewPacket(
        review_id="review-1",
        candidate_id="cand-1",
        unit_id="unit-1",
        blind_reliability_study=True,
        review_reason="low-confidence label disagreement",
        materials=(
            ReviewMaterial(
                material_id="unit",
                kind=ReviewMaterialKind.UNIT_TEXT,
                text="Count I against Issuer",
            ),
            ReviewMaterial(
                material_id="motion-excerpt",
                kind=ReviewMaterialKind.PREDECISION_SOURCE_EXCERPT,
                text="Issuer moves to dismiss Count I.",
                source_document_id="mtd-34",
                source_hash="sha256:abc",
            ),
            ReviewMaterial(
                material_id="decision-excerpt",
                kind=ReviewMaterialKind.DECISION_EXCERPT,
                text="The motion is granted as to Count I.",
                source_document_id="decision-42",
            ),
        ),
    )


def test_review_packet_serializes_unit_source_and_decision_materials() -> None:
    packet = _packet()
    record = packet.to_record()

    assert record["contains_decision_material"] is True
    assert record["blind_reliability_study"] is True
    assert len(record["materials"]) == 3
    json.dumps(record)


def test_stage_a_unitizer_view_strips_decision_material() -> None:
    packet = _packet()

    blinded = packet.for_stage_a_unitizer()

    assert blinded.audience is ReviewPacketAudience.STAGE_A_UNITIZER
    assert blinded.contains_decision_material is False
    assert [material.kind for material in blinded.materials] == [
        ReviewMaterialKind.UNIT_TEXT,
        ReviewMaterialKind.PREDECISION_SOURCE_EXCERPT,
    ]


def test_stage_a_packet_rejects_decision_excerpts() -> None:
    with pytest.raises(ValueError, match="Stage A unitizers"):
        LawyerReviewPacket(
            review_id="review-1",
            candidate_id="cand-1",
            unit_id="unit-1",
            audience=ReviewPacketAudience.STAGE_A_UNITIZER,
            materials=(
                ReviewMaterial(
                    material_id="decision",
                    kind=ReviewMaterialKind.DECISION_EXCERPT,
                    text="The claim is dismissed.",
                ),
            ),
        )


def test_review_response_requires_identity_time_confidence_and_notes() -> None:
    response = LawyerReviewResponse(
        review_id="review-1",
        reviewer_id="lawyer-a",
        reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        proposed_label=_label("unit-1", fully_dismissed=True),
        confidence=0.82,
        minutes_spent=14.5,
        notes="Decision text cleanly resolves the unit.",
    )

    assert response.to_record()["reviewer_id"] == "lawyer-a"

    with pytest.raises(ValueError, match="minutes_spent"):
        LawyerReviewResponse(
            review_id="review-1",
            reviewer_id="lawyer-b",
            reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
            proposed_label=_label("unit-1", fully_dismissed=True),
            confidence=0.8,
            minutes_spent=0,
            notes="bad",
        )


def test_adjudication_detects_senior_lawyer_disagreement_and_exports_trail() -> None:
    response_a = LawyerReviewResponse(
        review_id="review-1",
        reviewer_id="lawyer-a",
        reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        proposed_label=_label("unit-1", fully_dismissed=True),
        confidence=0.84,
        minutes_spent=11.0,
        notes="Reads as full dismissal.",
    )
    response_b = LawyerReviewResponse(
        review_id="review-1",
        reviewer_id="lawyer-b",
        reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        proposed_label=_label("unit-1", fully_dismissed=False),
        confidence=0.76,
        minutes_spent=13.0,
        notes="One theory survived.",
    )

    adjudication = AdjudicatedReview(
        review_id="review-1",
        candidate_id="cand-1",
        unit_id="unit-1",
        reviewer_responses=(response_a, response_b),
        adjudicated_label=_label("unit-1", fully_dismissed=False),
        adjudicator_id="senior-adjudicator",
        adjudication_notes="The claim survived in material respect.",
    )

    assert adjudication.disagreement_state is ReviewDisagreementState.DISAGREEMENT
    assert adjudication.total_minutes_spent == 24.0
    record = adjudication.to_record()
    assert record["adjudicator_id"] == "senior-adjudicator"
    assert record["adjudicated_label"]["primary_outcome"] == 0
    assert len(record["reviewer_responses"]) == 2


def test_adjudication_rejects_duplicate_reviewer_ids() -> None:
    response = LawyerReviewResponse(
        review_id="review-1",
        reviewer_id="lawyer-a",
        reviewer_expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        proposed_label=_label("unit-1", fully_dismissed=True),
        confidence=0.84,
        minutes_spent=11.0,
        notes="Reads as full dismissal.",
    )

    with pytest.raises(ValueError, match="unique"):
        AdjudicatedReview(
            review_id="review-1",
            candidate_id="cand-1",
            unit_id="unit-1",
            reviewer_responses=(response, response),
            adjudicated_label=_label("unit-1", fully_dismissed=True),
            adjudicator_id="senior-adjudicator",
            adjudication_notes="duplicate reviewer",
        )
