"""Lawyer review and adjudication workflow schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.labeling.label_outcomes import OutcomeLabel


class ReviewMaterialKind(StrEnum):
    """Kinds of material shown in lawyer-review packets."""

    UNIT_TEXT = "unit_text"
    PREDECISION_SOURCE_EXCERPT = "predecision_source_excerpt"
    DECISION_EXCERPT = "decision_excerpt"
    DISAGREEMENT_SUMMARY = "disagreement_summary"


class ReviewPacketAudience(StrEnum):
    """Audience controls whether decision material may be included."""

    LABEL_REVIEWER = "label_reviewer"
    STAGE_A_UNITIZER = "stage_a_unitizer"


class ReviewerExpertise(StrEnum):
    """Reviewer expertise strata used for reliability studies."""

    LAW_STUDENT = "law_student"
    JUNIOR_LITIGATOR = "junior_litigator"
    MIDLEVEL_LITIGATOR = "midlevel_litigator"
    SENIOR_LITIGATOR = "senior_litigator"
    EXPERT_PANEL = "expert_panel"


class ReviewDisagreementState(StrEnum):
    """Whether reviewer labels agree before adjudication."""

    SINGLE_REVIEWER = "single_reviewer"
    UNANIMOUS = "unanimous"
    DISAGREEMENT = "disagreement"


@dataclass(frozen=True, slots=True)
class ReviewMaterial:
    """One source excerpt or unit text shown to a reviewer."""

    material_id: str
    kind: ReviewMaterialKind
    text: str
    source_document_id: str | None = None
    source_hash: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.material_id, "material_id")
        _require_non_empty(self.text, "text")
        if self.source_document_id is not None:
            _require_non_empty(self.source_document_id, "source_document_id")
        if self.source_hash is not None:
            _require_non_empty(self.source_hash, "source_hash")

    @property
    def is_decision_material(self) -> bool:
        return self.kind is ReviewMaterialKind.DECISION_EXCERPT

    def to_record(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "kind": self.kind.value,
            "text": self.text,
            "source_document_id": self.source_document_id,
            "source_hash": self.source_hash,
            "is_decision_material": self.is_decision_material,
        }


@dataclass(frozen=True, slots=True)
class LawyerReviewPacket:
    """Review packet for ambiguous units, label disagreement, or reliability."""

    review_id: str
    candidate_id: str
    unit_id: str
    materials: tuple[ReviewMaterial, ...]
    audience: ReviewPacketAudience = ReviewPacketAudience.LABEL_REVIEWER
    blind_reliability_study: bool = False
    review_reason: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.review_id, "review_id")
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.unit_id, "unit_id")
        if not self.materials:
            raise ValueError("materials must not be empty")
        if self.review_reason is not None:
            _require_non_empty(self.review_reason, "review_reason")
        if (
            self.audience is ReviewPacketAudience.STAGE_A_UNITIZER
            and self.contains_decision_material
        ):
            raise ValueError("Stage A unitizers must not see decision material")

    @property
    def contains_decision_material(self) -> bool:
        return any(material.is_decision_material for material in self.materials)

    def for_stage_a_unitizer(self) -> LawyerReviewPacket:
        """Return a blinded packet with decision material removed."""

        return LawyerReviewPacket(
            review_id=self.review_id,
            candidate_id=self.candidate_id,
            unit_id=self.unit_id,
            materials=tuple(
                material
                for material in self.materials
                if not material.is_decision_material
            ),
            audience=ReviewPacketAudience.STAGE_A_UNITIZER,
            blind_reliability_study=self.blind_reliability_study,
            review_reason=self.review_reason,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "review_id": self.review_id,
            "candidate_id": self.candidate_id,
            "unit_id": self.unit_id,
            "audience": self.audience.value,
            "blind_reliability_study": self.blind_reliability_study,
            "review_reason": self.review_reason,
            "contains_decision_material": self.contains_decision_material,
            "materials": [material.to_record() for material in self.materials],
        }


@dataclass(frozen=True, slots=True)
class LawyerReviewResponse:
    """One lawyer's proposed label and review metadata."""

    review_id: str
    reviewer_id: str
    reviewer_expertise: ReviewerExpertise
    proposed_label: OutcomeLabel
    confidence: float
    minutes_spent: float
    notes: str

    def __post_init__(self) -> None:
        _require_non_empty(self.review_id, "review_id")
        _require_non_empty(self.reviewer_id, "reviewer_id")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.minutes_spent <= 0:
            raise ValueError("minutes_spent must be positive")
        _require_non_empty(self.notes, "notes")

    def to_record(self) -> dict[str, object]:
        return {
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_expertise": self.reviewer_expertise.value,
            "proposed_label": self.proposed_label.to_record(),
            "confidence": self.confidence,
            "minutes_spent": self.minutes_spent,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class AdjudicatedReview:
    """Final adjudication record with exportable reviewer audit trail."""

    review_id: str
    candidate_id: str
    unit_id: str
    reviewer_responses: tuple[LawyerReviewResponse, ...]
    adjudicated_label: OutcomeLabel
    adjudicator_id: str
    adjudication_notes: str

    def __post_init__(self) -> None:
        _require_non_empty(self.review_id, "review_id")
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(self.adjudicator_id, "adjudicator_id")
        _require_non_empty(self.adjudication_notes, "adjudication_notes")
        if not self.reviewer_responses:
            raise ValueError("reviewer_responses must not be empty")
        reviewer_ids = [response.reviewer_id for response in self.reviewer_responses]
        if len(set(reviewer_ids)) != len(reviewer_ids):
            raise ValueError("reviewer_id values must be unique")
        for response in self.reviewer_responses:
            if response.review_id != self.review_id:
                raise ValueError("reviewer response review_id must match adjudication")
            if response.proposed_label.unit_id != self.unit_id:
                raise ValueError("reviewer label unit_id must match adjudication unit")
        if self.adjudicated_label.unit_id != self.unit_id:
            raise ValueError("adjudicated label unit_id must match adjudication unit")

    @property
    def disagreement_state(self) -> ReviewDisagreementState:
        if len(self.reviewer_responses) == 1:
            return ReviewDisagreementState.SINGLE_REVIEWER
        signatures = {
            _label_signature(response.proposed_label)
            for response in self.reviewer_responses
        }
        if len(signatures) == 1:
            return ReviewDisagreementState.UNANIMOUS
        return ReviewDisagreementState.DISAGREEMENT

    @property
    def total_minutes_spent(self) -> float:
        return sum(response.minutes_spent for response in self.reviewer_responses)

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "candidate_id": self.candidate_id,
            "unit_id": self.unit_id,
            "disagreement_state": self.disagreement_state.value,
            "adjudicated_label": self.adjudicated_label.to_record(),
            "adjudicator_id": self.adjudicator_id,
            "adjudication_notes": self.adjudication_notes,
            "total_minutes_spent": self.total_minutes_spent,
            "reviewer_responses": [
                response.to_record() for response in self.reviewer_responses
            ],
        }


def _label_signature(label: OutcomeLabel) -> tuple[object, ...]:
    return (
        label.fully_dismissed,
        label.amendment_class,
        label.ambiguous,
        label.primary_outcome,
    )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
