"""Prediction-unit schemas for LegalForecast-MTD."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ChallengeScope(StrEnum):
    """How much of a claim the motion challenges for the unit."""

    ENTIRE_CLAIM = "entire_claim"
    PARTIAL_THEORY_ONLY = "partial_theory_only"
    SEPARABLE_SUBCLAIM = "separable_subclaim"
    UNCLEAR = "unclear"


class DefendantGrouping(StrEnum):
    """Whether the unit covers one defendant or a legally grouped set."""

    INDIVIDUAL = "individual"
    GROUPED = "grouped"


def _require_non_empty(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
    return value


def _optional_non_empty(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty(value, field_name)


def _positive_int(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class SourceCitation:
    """Pointer to pre-decision materials supporting a prediction unit."""

    document_id: str
    docket_entry_number: int | None = None
    page: int | None = None
    paragraph: int | None = None
    excerpt: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        _positive_int(self.docket_entry_number, "docket_entry_number")
        _positive_int(self.page, "page")
        _positive_int(self.paragraph, "paragraph")
        _optional_non_empty(self.excerpt, "excerpt")

    def to_record(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "docket_entry_number": self.docket_entry_number,
            "page": self.page,
            "paragraph": self.paragraph,
            "excerpt": self.excerpt,
        }


@dataclass(frozen=True, slots=True)
class PredictionUnit:
    """Claim-defendant unit that must be frozen before outcome labeling."""

    unit_id: str
    count: str
    claim_name: str
    defendant_group: str
    challenged_by_motion: bool
    challenge_scope: ChallengeScope
    unit_confidence: float
    source_citations: tuple[SourceCitation, ...]
    grouping: DefendantGrouping = DefendantGrouping.INDIVIDUAL
    grouping_rationale: str | None = None
    separable_subclaim: str | None = None
    uncertainty_notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(self.count, "count")
        _require_non_empty(self.claim_name, "claim_name")
        _require_non_empty(self.defendant_group, "defendant_group")

        if not 0 <= self.unit_confidence <= 1:
            raise ValueError("unit_confidence must be between 0 and 1")

        if not self.source_citations:
            raise ValueError("source_citations must include at least one citation")

        if self.grouping is DefendantGrouping.GROUPED:
            _require_non_empty(
                self.grouping_rationale or "",
                "grouping_rationale",
            )

        if self.grouping is DefendantGrouping.INDIVIDUAL and self.grouping_rationale:
            raise ValueError(
                "grouping_rationale should be omitted for individual defendants"
            )

        if self.challenge_scope is ChallengeScope.SEPARABLE_SUBCLAIM:
            _require_non_empty(self.separable_subclaim or "", "separable_subclaim")

        if (
            self.challenge_scope is not ChallengeScope.SEPARABLE_SUBCLAIM
            and self.separable_subclaim is not None
        ):
            raise ValueError(
                "separable_subclaim is only allowed for separable_subclaim scope"
            )

        if self.challenge_scope is ChallengeScope.UNCLEAR:
            _require_non_empty(self.uncertainty_notes or "", "uncertainty_notes")

        _optional_non_empty(self.uncertainty_notes, "uncertainty_notes")

    @property
    def should_score(self) -> bool:
        """Whether the unit is suitable for scoring before outcome labels exist."""

        return (
            self.challenged_by_motion
            and self.challenge_scope is not ChallengeScope.UNCLEAR
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "count": self.count,
            "claim_name": self.claim_name,
            "defendant_group": self.defendant_group,
            "challenged_by_motion": self.challenged_by_motion,
            "challenge_scope": self.challenge_scope.value,
            "unit_confidence": self.unit_confidence,
            "source_citations": [
                citation.to_record() for citation in self.source_citations
            ],
            "grouping": self.grouping.value,
            "grouping_rationale": self.grouping_rationale,
            "separable_subclaim": self.separable_subclaim,
            "uncertainty_notes": self.uncertainty_notes,
            "should_score": self.should_score,
        }
