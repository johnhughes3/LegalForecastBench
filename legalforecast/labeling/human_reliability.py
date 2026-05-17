"""Human reliability reporting for outcome-label review pilots."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from legalforecast.labeling.label_outcomes import OutcomeLabel
from legalforecast.labeling.lawyer_review import (
    AdjudicatedReview,
    LawyerReviewResponse,
    ReviewDisagreementState,
    ReviewerExpertise,
)

LOW_CONFIDENCE_PAIN_POINT_THRESHOLD = 0.75


@dataclass(frozen=True, slots=True)
class HumanReliabilityUnitResult:
    """Reliability metrics for one adjudicated claim-defendant unit."""

    review_id: str
    candidate_id: str
    unit_id: str
    complexity_stratum: str | None
    reviewer_ids: tuple[str, ...]
    reviewer_count: int
    senior_reviewer_count: int
    senior_disagreement_state: ReviewDisagreementState
    adjudicated_fully_dismissed: bool | None
    adjudicated_ambiguous: bool
    total_minutes_spent: float
    low_confidence_reviewer_count: int
    schema_pain_points: tuple[str, ...]

    @property
    def has_senior_disagreement(self) -> bool:
        return self.senior_disagreement_state is ReviewDisagreementState.DISAGREEMENT

    def to_record(self) -> dict[str, object]:
        return {
            "review_id": self.review_id,
            "candidate_id": self.candidate_id,
            "unit_id": self.unit_id,
            "complexity_stratum": self.complexity_stratum,
            "reviewer_ids": list(self.reviewer_ids),
            "reviewer_count": self.reviewer_count,
            "senior_reviewer_count": self.senior_reviewer_count,
            "senior_disagreement_state": self.senior_disagreement_state.value,
            "adjudicated_fully_dismissed": self.adjudicated_fully_dismissed,
            "adjudicated_ambiguous": self.adjudicated_ambiguous,
            "total_minutes_spent": self.total_minutes_spent,
            "low_confidence_reviewer_count": self.low_confidence_reviewer_count,
            "schema_pain_points": list(self.schema_pain_points),
        }


@dataclass(frozen=True, slots=True)
class HumanReliabilityReport:
    """Aggregate human-floor report for senior-litigator label review."""

    study_id: str
    source_note: str
    target_case_count: int
    reviewer_ids: tuple[str, ...]
    unit_results: tuple[HumanReliabilityUnitResult, ...]
    senior_pair_unit_count: int
    raw_disagreement_rate: float
    cohen_kappa: float | None

    def __post_init__(self) -> None:
        _require_non_empty(self.study_id, "study_id")
        _require_non_empty(self.source_note, "source_note")
        if self.target_case_count <= 0:
            raise ValueError("target_case_count must be positive")
        if not self.unit_results:
            raise ValueError("unit_results must not be empty")
        if self.senior_pair_unit_count <= 0:
            raise ValueError("senior_pair_unit_count must be positive")

    @property
    def unit_count(self) -> int:
        return len(self.unit_results)

    @property
    def reviewer_count(self) -> int:
        return len(self.reviewer_ids)

    @property
    def human_floor_error_rate(self) -> float:
        """Senior blind disagreement rate used as the provisional human floor."""

        return self.raw_disagreement_rate

    @property
    def ambiguous_unit_share(self) -> float:
        ambiguous_count = sum(
            1 for result in self.unit_results if result.adjudicated_ambiguous
        )
        return ambiguous_count / self.unit_count

    @property
    def mean_minutes_per_unit(self) -> float:
        return (
            sum(result.total_minutes_spent for result in self.unit_results)
            / self.unit_count
        )

    @property
    def schema_pain_point_counts(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for result in self.unit_results:
            counter.update(result.schema_pain_points)
        return dict(sorted(counter.items()))

    @property
    def recommendation(self) -> str:
        if self.unit_count < self.target_case_count:
            schema_clause = (
                " Observed schema pain points should be converted into "
                "schema guidance or exclusion-rule clarifications before the "
                "live pilot."
                if self.schema_pain_point_counts
                else ""
            )
            return (
                "Treat this as a fixture-only pilot, not the final empirical "
                "human floor. The live pilot should still run on 50-100 clean "
                "MTD packets before the human-relative LLM label gate is "
                "relaxed."
                f"{schema_clause}"
            )
        if self.schema_pain_point_counts or self.raw_disagreement_rate > 0.10:
            return (
                "Revise the label schema or exclusion rules around the observed "
                "pain points before relying on automated labels."
            )
        return (
            "Use the measured senior disagreement rate as the human floor, "
            "subject to the existing absolute safety ceiling."
        )

    def to_record(self) -> dict[str, object]:
        return {
            "study_id": self.study_id,
            "source_note": self.source_note,
            "target_case_count": self.target_case_count,
            "unit_count": self.unit_count,
            "reviewer_count": self.reviewer_count,
            "reviewer_ids": list(self.reviewer_ids),
            "senior_pair_unit_count": self.senior_pair_unit_count,
            "raw_disagreement_rate": self.raw_disagreement_rate,
            "human_floor_error_rate": self.human_floor_error_rate,
            "cohen_kappa": self.cohen_kappa,
            "ambiguous_unit_share": self.ambiguous_unit_share,
            "mean_minutes_per_unit": self.mean_minutes_per_unit,
            "schema_pain_point_counts": self.schema_pain_point_counts,
            "recommendation": self.recommendation,
            "unit_results": [result.to_record() for result in self.unit_results],
        }

    def to_markdown(self) -> str:
        kappa = (
            "not available" if self.cohen_kappa is None else f"{self.cohen_kappa:.3f}"
        )
        pain_points = self.schema_pain_point_counts
        if pain_points:
            pain_point_lines = "\n".join(
                f"- {pain_point}: {count}" for pain_point, count in pain_points.items()
            )
        else:
            pain_point_lines = "- none"

        return "\n".join(
            [
                f"# Human Reliability Pilot: {self.study_id}",
                "",
                self.source_note,
                "",
                "## Human Floor",
                "",
                f"- Target live pilot size: {self.target_case_count} MTDs",
                f"- Fixture/adjudicated units reviewed: {self.unit_count}",
                f"- Senior paired units: {self.senior_pair_unit_count}",
                f"- Senior raw disagreement rate: {self.raw_disagreement_rate:.3f}",
                "- Provisional human floor error rate: "
                f"{self.human_floor_error_rate:.3f}",
                f"- Cohen kappa: {kappa}",
                f"- Adjudicated ambiguous unit share: {self.ambiguous_unit_share:.3f}",
                "- Mean total lawyer minutes per unit: "
                f"{self.mean_minutes_per_unit:.1f}",
                "",
                "## Schema Pain Points",
                "",
                pain_point_lines,
                "",
                "## Recommendation",
                "",
                self.recommendation,
                "",
            ]
        )


def build_human_reliability_report(
    reviews: Sequence[AdjudicatedReview],
    *,
    study_id: str,
    source_note: str,
    target_case_count: int = 50,
    complexity_by_unit_id: Mapping[str, str] | None = None,
    schema_pain_points_by_unit_id: Mapping[str, Sequence[str]] | None = None,
) -> HumanReliabilityReport:
    """Build a senior-litigator reliability report from adjudicated reviews."""

    _require_non_empty(study_id, "study_id")
    _require_non_empty(source_note, "source_note")
    if target_case_count <= 0:
        raise ValueError("target_case_count must be positive")
    if not reviews:
        raise ValueError("reviews must not be empty")

    _validate_unique_review_units(reviews)
    complexity_lookup = complexity_by_unit_id or {}
    explicit_pain_points = schema_pain_points_by_unit_id or {}
    unit_results = tuple(
        _unit_result(
            review,
            complexity_stratum=complexity_lookup.get(review.unit_id),
            explicit_pain_points=explicit_pain_points.get(review.unit_id, ()),
        )
        for review in reviews
    )
    senior_pair_results = tuple(
        result for result in unit_results if result.senior_reviewer_count >= 2
    )
    if not senior_pair_results:
        raise ValueError("at least one unit must include two senior litigator reviews")

    reviewer_ids = tuple(
        sorted(
            {
                response.reviewer_id
                for review in reviews
                for response in review.reviewer_responses
            }
        )
    )
    raw_disagreement_rate = sum(
        1 for result in senior_pair_results if result.has_senior_disagreement
    ) / len(senior_pair_results)
    binary_pairs = tuple(
        pair for review in reviews if (pair := _senior_binary_pair(review)) is not None
    )
    cohen_kappa = (
        _cohen_kappa(binary_pairs) if _single_reviewer_pair(binary_pairs) else None
    )

    return HumanReliabilityReport(
        study_id=study_id,
        source_note=source_note,
        target_case_count=target_case_count,
        reviewer_ids=reviewer_ids,
        unit_results=unit_results,
        senior_pair_unit_count=len(senior_pair_results),
        raw_disagreement_rate=raw_disagreement_rate,
        cohen_kappa=cohen_kappa,
    )


def _unit_result(
    review: AdjudicatedReview,
    *,
    complexity_stratum: str | None,
    explicit_pain_points: Sequence[str],
) -> HumanReliabilityUnitResult:
    senior_responses = _senior_responses(review)
    senior_state = _senior_disagreement_state(senior_responses)
    low_confidence_count = sum(
        1
        for response in review.reviewer_responses
        if response.confidence < LOW_CONFIDENCE_PAIN_POINT_THRESHOLD
    )
    pain_points = set(explicit_pain_points)
    if senior_state is ReviewDisagreementState.DISAGREEMENT:
        pain_points.add("senior_reviewer_disagreement")
    if review.adjudicated_label.ambiguous:
        pain_points.add("ambiguous_adjudication")
    if low_confidence_count:
        pain_points.add("low_reviewer_confidence")

    return HumanReliabilityUnitResult(
        review_id=review.review_id,
        candidate_id=review.candidate_id,
        unit_id=review.unit_id,
        complexity_stratum=complexity_stratum,
        reviewer_ids=tuple(
            sorted(response.reviewer_id for response in review.reviewer_responses)
        ),
        reviewer_count=len(review.reviewer_responses),
        senior_reviewer_count=len(senior_responses),
        senior_disagreement_state=senior_state,
        adjudicated_fully_dismissed=review.adjudicated_label.fully_dismissed,
        adjudicated_ambiguous=review.adjudicated_label.ambiguous,
        total_minutes_spent=review.total_minutes_spent,
        low_confidence_reviewer_count=low_confidence_count,
        schema_pain_points=tuple(sorted(_validate_pain_points(pain_points))),
    )


def _senior_disagreement_state(
    senior_responses: tuple[LawyerReviewResponse, ...],
) -> ReviewDisagreementState:
    if len(senior_responses) <= 1:
        return ReviewDisagreementState.SINGLE_REVIEWER
    signatures = {
        _label_signature(response.proposed_label) for response in senior_responses
    }
    if len(signatures) == 1:
        return ReviewDisagreementState.UNANIMOUS
    return ReviewDisagreementState.DISAGREEMENT


def _senior_responses(
    review: AdjudicatedReview,
) -> tuple[LawyerReviewResponse, ...]:
    return tuple(
        response
        for response in review.reviewer_responses
        if response.reviewer_expertise is ReviewerExpertise.SENIOR_LITIGATOR
    )


def _senior_binary_pair(
    review: AdjudicatedReview,
) -> tuple[tuple[str, str], int, int] | None:
    senior_responses = tuple(
        sorted(_senior_responses(review), key=lambda response: response.reviewer_id)
    )
    if len(senior_responses) != 2:
        return None

    left, right = senior_responses
    left_category = _binary_category(left.proposed_label)
    right_category = _binary_category(right.proposed_label)
    if left_category is None or right_category is None:
        return None
    return ((left.reviewer_id, right.reviewer_id), left_category, right_category)


def _single_reviewer_pair(
    binary_pairs: tuple[tuple[tuple[str, str], int, int], ...],
) -> bool:
    if not binary_pairs:
        return False
    reviewer_pairs = {pair[0] for pair in binary_pairs}
    return len(reviewer_pairs) == 1


def _cohen_kappa(binary_pairs: tuple[tuple[tuple[str, str], int, int], ...]) -> float:
    category_pairs = tuple((left, right) for _, left, right in binary_pairs)
    observed_agreement = sum(
        1 for left, right in category_pairs if left == right
    ) / len(category_pairs)
    left_yes = sum(left for left, _ in category_pairs) / len(category_pairs)
    right_yes = sum(right for _, right in category_pairs) / len(category_pairs)
    expected_agreement = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    if expected_agreement == 1:
        return 1.0 if observed_agreement == 1 else 0.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def _binary_category(label: OutcomeLabel) -> int | None:
    if label.fully_dismissed is None:
        return None
    return 1 if label.fully_dismissed else 0


def _label_signature(label: OutcomeLabel) -> tuple[object, ...]:
    return (
        label.fully_dismissed,
        label.amendment_class,
        label.ambiguous,
        label.primary_outcome,
    )


def _validate_pain_points(pain_points: set[str]) -> tuple[str, ...]:
    for pain_point in pain_points:
        _require_non_empty(pain_point, "schema_pain_point")
    return tuple(pain_points)


def _validate_unique_review_units(reviews: Sequence[AdjudicatedReview]) -> None:
    keys = [(review.candidate_id, review.unit_id) for review in reviews]
    if len(set(keys)) != len(keys):
        raise ValueError("candidate_id/unit_id review pairs must be unique")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
