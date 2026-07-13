"""LLM-assisted outcome-label ensemble and audit gates."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from legalforecast.labeling.label_outcomes import OutcomeLabel

DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_REQUIRED_MODEL_COUNT = 3
DEFAULT_ABSOLUTE_AUDIT_ERROR_CEILING = 0.10

LabelSignature = tuple[object, ...]


class LabelingModel(Protocol):
    """Protocol implemented by cheap LLM labelers used for ensemble labeling."""

    model_id: str

    def label_units(self, labeling_inputs: object) -> Sequence[OutcomeLabel]:
        """Return proposed labels for the supplied Stage B labeling inputs."""
        ...


class EnsembleDecisionStatus(StrEnum):
    """Final routing state for one unit after ensemble voting."""

    AUTO_LABEL = "auto_label"
    LAWYER_ADJUDICATION = "lawyer_adjudication"
    EXCLUDED_AMBIGUOUS = "excluded_ambiguous"


class EnsembleRouteReason(StrEnum):
    """Reason an ensemble unit was auto-labeled, reviewed, or excluded."""

    UNANIMOUS_HIGH_CONFIDENCE = "unanimous_high_confidence"
    DISAGREEMENT = "disagreement"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class EnsembleLabelVote:
    """One model's proposed label for one frozen prediction unit."""

    model_id: str
    unit_id: str
    label: OutcomeLabel
    confidence: float
    rationale: str
    raw_response_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.model_id, "model_id")
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(self.rationale, "rationale")
        if self.raw_response_id is not None:
            _require_non_empty(self.raw_response_id, "raw_response_id")
        if self.label.unit_id != self.unit_id:
            raise ValueError("vote unit_id must match label unit_id")
        _require_probability(self.confidence, "confidence")

    @property
    def signature(self) -> LabelSignature:
        return _label_signature(self.label)

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "unit_id": self.unit_id,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "raw_response_id": self.raw_response_id,
            "label": self.label.to_record(),
            "signature": list(self.signature),
        }


@dataclass(frozen=True, slots=True)
class EnsembleUnitDecision:
    """Ensemble routing decision for one prediction unit."""

    unit_id: str
    votes: tuple[EnsembleLabelVote, ...]
    status: EnsembleDecisionStatus
    route_reason: EnsembleRouteReason
    unanimous_label: OutcomeLabel | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        if not self.votes:
            raise ValueError("votes must not be empty")
        for vote in self.votes:
            if vote.unit_id != self.unit_id:
                raise ValueError("all votes must match decision unit_id")
        if self.status is EnsembleDecisionStatus.AUTO_LABEL:
            if self.unanimous_label is None:
                raise ValueError("auto-label decisions require unanimous_label")
            if self.unanimous_label.unit_id != self.unit_id:
                raise ValueError("unanimous_label unit_id must match decision")
        elif self.unanimous_label is not None:
            raise ValueError("review or exclusion decisions must omit unanimous_label")

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(vote.model_id for vote in self.votes)

    @property
    def mean_confidence(self) -> float:
        return sum(vote.confidence for vote in self.votes) / len(self.votes)

    @property
    def min_confidence(self) -> float:
        return min(vote.confidence for vote in self.votes)

    @property
    def requires_lawyer_adjudication(self) -> bool:
        return self.status is EnsembleDecisionStatus.LAWYER_ADJUDICATION

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "status": self.status.value,
            "route_reason": self.route_reason.value,
            "model_ids": list(self.model_ids),
            "mean_confidence": self.mean_confidence,
            "min_confidence": self.min_confidence,
            "unanimous_label": (
                self.unanimous_label.to_record()
                if self.unanimous_label is not None
                else None
            ),
            "votes": [vote.to_record() for vote in self.votes],
        }


@dataclass(frozen=True, slots=True)
class EnsembleRunResult:
    """Complete ensemble output with routing metrics for reporting."""

    decisions: tuple[EnsembleUnitDecision, ...]
    high_confidence_threshold: float
    required_model_count: int

    def __post_init__(self) -> None:
        if not self.decisions:
            raise ValueError("decisions must not be empty")
        _require_probability(
            self.high_confidence_threshold,
            "high_confidence_threshold",
        )
        if self.required_model_count <= 0:
            raise ValueError("required_model_count must be positive")
        unit_ids = [decision.unit_id for decision in self.decisions]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("decision unit_id values must be unique")

    @property
    def auto_labels(self) -> tuple[OutcomeLabel, ...]:
        labels: list[OutcomeLabel] = []
        for decision in self.decisions:
            if decision.unanimous_label is not None:
                labels.append(decision.unanimous_label)
        return tuple(labels)

    @property
    def auto_label_count(self) -> int:
        return len(self.auto_labels)

    @property
    def lawyer_adjudicated_share(self) -> float:
        review_count = sum(
            1
            for decision in self.decisions
            if decision.status is EnsembleDecisionStatus.LAWYER_ADJUDICATION
        )
        return review_count / len(self.decisions)

    @property
    def ambiguous_unit_count(self) -> int:
        return sum(
            1
            for decision in self.decisions
            if decision.route_reason is EnsembleRouteReason.AMBIGUOUS
        )

    @property
    def ambiguous_exclusion_count(self) -> int:
        return sum(
            1
            for decision in self.decisions
            if decision.status is EnsembleDecisionStatus.EXCLUDED_AMBIGUOUS
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "high_confidence_threshold": self.high_confidence_threshold,
            "required_model_count": self.required_model_count,
            "unit_count": len(self.decisions),
            "auto_label_count": self.auto_label_count,
            "lawyer_adjudicated_share": self.lawyer_adjudicated_share,
            "ambiguous_unit_count": self.ambiguous_unit_count,
            "ambiguous_exclusion_count": self.ambiguous_exclusion_count,
            "decisions": [decision.to_record() for decision in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class LabelAuditSummary:
    """Acceptance report for audited unanimous LLM labels."""

    audited_unit_count: int
    unanimous_auto_label_count: int
    human_blind_disagreement_rate: float
    llm_audited_error_rate: float
    lawyer_adjudicated_share: float
    ambiguous_unit_count: int
    ambiguous_exclusion_count: int
    absolute_error_ceiling: float = DEFAULT_ABSOLUTE_AUDIT_ERROR_CEILING

    def __post_init__(self) -> None:
        if self.audited_unit_count <= 0:
            raise ValueError("audited_unit_count must be positive")
        if self.unanimous_auto_label_count < 0:
            raise ValueError("unanimous_auto_label_count must be nonnegative")
        if self.ambiguous_unit_count < 0:
            raise ValueError("ambiguous_unit_count must be nonnegative")
        if self.ambiguous_exclusion_count < 0:
            raise ValueError("ambiguous_exclusion_count must be nonnegative")
        for field_name, value in (
            ("human_blind_disagreement_rate", self.human_blind_disagreement_rate),
            ("llm_audited_error_rate", self.llm_audited_error_rate),
            ("lawyer_adjudicated_share", self.lawyer_adjudicated_share),
            ("absolute_error_ceiling", self.absolute_error_ceiling),
        ):
            _require_probability(value, field_name)

    @property
    def passes_acceptance(self) -> bool:
        return (
            self.llm_audited_error_rate <= self.human_blind_disagreement_rate
            and self.llm_audited_error_rate <= self.absolute_error_ceiling
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "audited_unit_count": self.audited_unit_count,
            "unanimous_auto_label_count": self.unanimous_auto_label_count,
            "human_blind_disagreement_rate": self.human_blind_disagreement_rate,
            "llm_audited_error_rate": self.llm_audited_error_rate,
            "lawyer_adjudicated_share": self.lawyer_adjudicated_share,
            "ambiguous_unit_count": self.ambiguous_unit_count,
            "ambiguous_exclusion_count": self.ambiguous_exclusion_count,
            "absolute_error_ceiling": self.absolute_error_ceiling,
            "passes_acceptance": self.passes_acceptance,
        }


def run_labeling_models(
    models: Sequence[LabelingModel],
    labeling_inputs: object,
    *,
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    exclude_ambiguous: bool = False,
) -> EnsembleRunResult:
    """Run all labeler models and evaluate their proposed labels as an ensemble."""

    if not models:
        raise ValueError("models must not be empty")
    votes: list[EnsembleLabelVote] = []
    for model in models:
        _require_non_empty(model.model_id, "model_id")
        labels = tuple(model.label_units(labeling_inputs))
        if not labels:
            raise ValueError(f"model produced no labels: {model.model_id}")
        votes.extend(
            EnsembleLabelVote(
                model_id=model.model_id,
                unit_id=label.unit_id,
                label=label,
                confidence=label.label_confidence,
                rationale=f"Label proposed by {model.model_id}.",
            )
            for label in labels
        )
    return evaluate_labeling_ensemble(
        votes,
        high_confidence_threshold=high_confidence_threshold,
        required_model_count=len(models),
        exclude_ambiguous=exclude_ambiguous,
    )


def evaluate_labeling_ensemble(
    votes: Sequence[EnsembleLabelVote],
    *,
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    required_model_count: int = DEFAULT_REQUIRED_MODEL_COUNT,
    exclude_ambiguous: bool = False,
) -> EnsembleRunResult:
    """Route units based on unanimity, confidence, and ambiguity."""

    if not votes:
        raise ValueError("votes must not be empty")
    _require_probability(high_confidence_threshold, "high_confidence_threshold")
    if required_model_count <= 0:
        raise ValueError("required_model_count must be positive")

    votes_by_unit_id: dict[str, list[EnsembleLabelVote]] = defaultdict(list)
    for vote in votes:
        votes_by_unit_id[vote.unit_id].append(vote)

    decisions = tuple(
        _decision_for_unit(
            unit_id,
            tuple(sorted(unit_votes, key=lambda vote: vote.model_id)),
            high_confidence_threshold=high_confidence_threshold,
            required_model_count=required_model_count,
            exclude_ambiguous=exclude_ambiguous,
        )
        for unit_id, unit_votes in sorted(votes_by_unit_id.items())
    )
    return EnsembleRunResult(
        decisions=decisions,
        high_confidence_threshold=high_confidence_threshold,
        required_model_count=required_model_count,
    )


def sample_unanimous_labels_for_audit(
    result: EnsembleRunResult,
    *,
    sample_size: int,
    strata_by_unit_id: Mapping[str, str] | None = None,
    seed: int = 0,
) -> tuple[EnsembleUnitDecision, ...]:
    """Deterministically sample auto-labeled units, balanced across strata."""

    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    auto_decisions = tuple(
        decision
        for decision in result.decisions
        if decision.status is EnsembleDecisionStatus.AUTO_LABEL
    )
    if not auto_decisions:
        return ()

    strata = strata_by_unit_id or {}
    decisions_by_stratum: dict[str, list[EnsembleUnitDecision]] = defaultdict(list)
    for decision in auto_decisions:
        stratum = strata.get(decision.unit_id, "all")
        decisions_by_stratum[stratum].append(decision)
    for decisions in decisions_by_stratum.values():
        decisions.sort(key=lambda decision: _sample_key(seed, decision.unit_id))

    selected: list[EnsembleUnitDecision] = []
    stratum_ids = sorted(decisions_by_stratum)
    while len(selected) < sample_size:
        progressed = False
        for stratum_id in stratum_ids:
            decisions = decisions_by_stratum[stratum_id]
            if decisions:
                selected.append(decisions.pop(0))
                progressed = True
                if len(selected) == sample_size:
                    break
        if not progressed:
            break
    return tuple(selected)


def audit_ensemble_labels(
    result: EnsembleRunResult,
    *,
    adjudicated_labels_by_unit_id: Mapping[str, OutcomeLabel],
    human_blind_disagreement_rate: float,
    absolute_error_ceiling: float = DEFAULT_ABSOLUTE_AUDIT_ERROR_CEILING,
) -> LabelAuditSummary:
    """Compare audited unanimous LLM labels to lawyer-adjudicated labels."""

    _require_probability(
        human_blind_disagreement_rate,
        "human_blind_disagreement_rate",
    )
    _require_probability(absolute_error_ceiling, "absolute_error_ceiling")
    audited_pairs = tuple(
        (label, adjudicated_labels_by_unit_id[label.unit_id])
        for label in result.auto_labels
        if label.unit_id in adjudicated_labels_by_unit_id
    )
    if not audited_pairs:
        raise ValueError("at least one unanimous auto-label must be audited")

    error_count = sum(
        1
        for auto_label, adjudicated_label in audited_pairs
        if _label_signature(auto_label) != _label_signature(adjudicated_label)
    )
    return LabelAuditSummary(
        audited_unit_count=len(audited_pairs),
        unanimous_auto_label_count=result.auto_label_count,
        human_blind_disagreement_rate=human_blind_disagreement_rate,
        llm_audited_error_rate=error_count / len(audited_pairs),
        lawyer_adjudicated_share=result.lawyer_adjudicated_share,
        ambiguous_unit_count=result.ambiguous_unit_count,
        ambiguous_exclusion_count=result.ambiguous_exclusion_count,
        absolute_error_ceiling=absolute_error_ceiling,
    )


def enforce_label_audit_acceptance(summary: LabelAuditSummary) -> None:
    """Fail closed unless LLM audit error is human-relative and below 10%."""

    if not summary.passes_acceptance:
        raise ValueError(
            "LLM label audit failed closed: audited error "
            f"{summary.llm_audited_error_rate:.3f} exceeds human disagreement "
            f"{summary.human_blind_disagreement_rate:.3f} or absolute ceiling "
            f"{summary.absolute_error_ceiling:.3f}"
        )


def _decision_for_unit(
    unit_id: str,
    votes: tuple[EnsembleLabelVote, ...],
    *,
    high_confidence_threshold: float,
    required_model_count: int,
    exclude_ambiguous: bool,
) -> EnsembleUnitDecision:
    model_ids = [vote.model_id for vote in votes]
    if len(set(model_ids)) != len(model_ids):
        raise ValueError(f"duplicate model vote for unit: {unit_id}")
    if len(votes) < required_model_count:
        raise ValueError(f"unit has fewer than required model votes: {unit_id}")

    if any(vote.label.ambiguous for vote in votes):
        return EnsembleUnitDecision(
            unit_id=unit_id,
            votes=votes,
            status=(
                EnsembleDecisionStatus.EXCLUDED_AMBIGUOUS
                if exclude_ambiguous
                else EnsembleDecisionStatus.LAWYER_ADJUDICATION
            ),
            route_reason=EnsembleRouteReason.AMBIGUOUS,
        )

    signatures = {vote.signature for vote in votes}
    if len(signatures) != 1:
        return EnsembleUnitDecision(
            unit_id=unit_id,
            votes=votes,
            status=EnsembleDecisionStatus.LAWYER_ADJUDICATION,
            route_reason=EnsembleRouteReason.DISAGREEMENT,
        )

    if min(vote.confidence for vote in votes) < high_confidence_threshold:
        return EnsembleUnitDecision(
            unit_id=unit_id,
            votes=votes,
            status=EnsembleDecisionStatus.LAWYER_ADJUDICATION,
            route_reason=EnsembleRouteReason.LOW_CONFIDENCE,
        )

    return EnsembleUnitDecision(
        unit_id=unit_id,
        votes=votes,
        status=EnsembleDecisionStatus.AUTO_LABEL,
        route_reason=EnsembleRouteReason.UNANIMOUS_HIGH_CONFIDENCE,
        unanimous_label=votes[0].label,
    )


def _label_signature(label: OutcomeLabel) -> LabelSignature:
    return (
        label.canonical_unit_resolution.value,
        label.fully_dismissed,
        label.amendment_class.value,
        label.ambiguous,
        label.primary_outcome,
        label.conditional_amendment_target,
    )


def _sample_key(seed: int, unit_id: str) -> str:
    return hashlib.sha256(f"{seed}:{unit_id}".encode()).hexdigest()


def _require_probability(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be in [0, 1]")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
