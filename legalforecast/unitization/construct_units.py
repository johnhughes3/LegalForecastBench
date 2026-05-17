"""Stage A prediction-unit construction from pre-decision materials."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)


class StageADocumentRole(StrEnum):
    """Pre-decision document roles available to Stage A unit constructors."""

    COMPLAINT = "complaint"
    AMENDED_COMPLAINT = "amended_complaint"
    MTD_NOTICE = "motion_to_dismiss_notice"
    MTD_MEMORANDUM = "motion_to_dismiss_memorandum"
    OPPOSITION = "opposition"
    REPLY = "reply"
    DOCKET_HISTORY = "docket_history"
    CASE_METADATA = "case_metadata"
    DECISION = "decision"
    ORDER = "order"


class UnitizationReviewReason(StrEnum):
    """Reasons a Stage A unit must be routed to blinded review."""

    UNCLEAR_CLAIM_OR_DEFENDANT = "unclear_claim_or_defendant"
    UNCLEAR_GROUPING = "unclear_grouping"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True, slots=True)
class StageASourceDocument:
    """Document available to Stage A before any outcome materials are read."""

    document_id: str
    role: StageADocumentRole
    is_predecision_material: bool = True
    contains_target_outcome: bool = False
    docket_entry_number: int | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        if self.docket_entry_number is not None and self.docket_entry_number <= 0:
            raise ValueError("docket_entry_number must be positive")
        if self.title is not None:
            _require_non_empty(self.title, "title")


@dataclass(frozen=True, slots=True)
class StageAUnitSeed:
    """Structured pre-decision facts used to create one prediction unit."""

    count: str
    claim_name: str
    defendant_names: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    challenged_by_motion: bool = True
    challenge_scope: ChallengeScope = ChallengeScope.ENTIRE_CLAIM
    unit_confidence: float = 0.8
    grouping: DefendantGrouping = DefendantGrouping.INDIVIDUAL
    grouping_rationale: str | None = None
    group_label: str | None = None
    separable_subclaim: str | None = None
    uncertainty_notes: str | None = None
    unit_id: str | None = None
    citation_page: int | None = None
    citation_paragraph: int | None = None
    citation_excerpt: str | None = None
    review_reason: UnitizationReviewReason | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.count, "count")
        _require_non_empty(self.claim_name, "claim_name")
        _require_non_empty_tuple(self.defendant_names, "defendant_names")
        _require_non_empty_tuple(self.source_document_ids, "source_document_ids")
        if not 0 <= self.unit_confidence <= 1:
            raise ValueError("unit_confidence must be between 0 and 1")
        if self.grouping is DefendantGrouping.INDIVIDUAL:
            if len(self.defendant_names) != 1:
                raise ValueError(
                    "individual unit seeds must contain exactly one defendant"
                )
            if self.grouping_rationale is not None:
                raise ValueError(
                    "grouping_rationale should be omitted for individual defendants"
                )
        if self.grouping is DefendantGrouping.GROUPED:
            if len(self.defendant_names) < 2:
                raise ValueError("grouped unit seeds require multiple defendants")
            _require_non_empty(self.grouping_rationale or "", "grouping_rationale")
        if self.group_label is not None:
            _require_non_empty(self.group_label, "group_label")
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
        if self.uncertainty_notes is not None:
            _require_non_empty(self.uncertainty_notes, "uncertainty_notes")


@dataclass(frozen=True, slots=True)
class StageAConstructionInput:
    """Complete Stage A input bundle for one candidate case."""

    candidate_id: str
    case_id: str
    source_documents: tuple[StageASourceDocument, ...]
    unit_seeds: tuple[StageAUnitSeed, ...]
    metadata: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if not self.source_documents:
            raise ValueError("source_documents must not be empty")
        if not self.unit_seeds:
            raise ValueError("unit_seeds must not be empty")
        if self.metadata is not None:
            for key, value in self.metadata.items():
                _require_non_empty(key, "metadata key")
                _require_non_empty(value, f"metadata[{key}]")


@dataclass(frozen=True, slots=True)
class UnitizationReviewItem:
    """A Stage A ambiguity that must be reviewed without decision materials."""

    unit_id: str
    reason: UnitizationReviewReason
    notes: str
    source_document_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(self.notes, "notes")
        _require_non_empty_tuple(self.source_document_ids, "source_document_ids")

    def to_record(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "reason": self.reason.value,
            "notes": self.notes,
            "source_document_ids": list(self.source_document_ids),
        }


@dataclass(frozen=True, slots=True)
class StageAConstructionResult:
    """Prediction units and blinded-review routing from Stage A."""

    candidate_id: str
    case_id: str
    units: tuple[PredictionUnit, ...]
    review_items: tuple[UnitizationReviewItem, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.review_items and all(unit.should_score for unit in self.units)

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "is_clean": self.is_clean,
            "units": [unit.to_record() for unit in self.units],
            "review_items": [item.to_record() for item in self.review_items],
        }


def construct_stage_a_units(
    construction_input: StageAConstructionInput,
) -> StageAConstructionResult:
    """Construct prediction units using only pre-decision Stage A materials."""

    documents_by_id = _validate_sources(construction_input.source_documents)
    units: list[PredictionUnit] = []
    review_items: list[UnitizationReviewItem] = []

    for seed in construction_input.unit_seeds:
        unit_id = seed.unit_id or _unit_id(
            construction_input.candidate_id,
            seed.count,
            seed.claim_name,
            seed.group_label or " ".join(seed.defendant_names),
        )
        citations = tuple(
            _citation_for_seed(documents_by_id[document_id], seed)
            for document_id in seed.source_document_ids
        )
        unit = PredictionUnit(
            unit_id=unit_id,
            count=seed.count,
            claim_name=seed.claim_name,
            defendant_group=_defendant_group_label(seed),
            challenged_by_motion=seed.challenged_by_motion,
            challenge_scope=seed.challenge_scope,
            unit_confidence=seed.unit_confidence,
            source_citations=citations,
            grouping=seed.grouping,
            grouping_rationale=seed.grouping_rationale,
            separable_subclaim=seed.separable_subclaim,
            uncertainty_notes=seed.uncertainty_notes,
        )
        units.append(unit)

        review_reason = _review_reason(seed, unit)
        if review_reason is not None:
            review_items.append(
                UnitizationReviewItem(
                    unit_id=unit.unit_id,
                    reason=review_reason,
                    notes=seed.uncertainty_notes
                    or "Stage A unit requires blinded pre-decision review.",
                    source_document_ids=seed.source_document_ids,
                )
            )

    return StageAConstructionResult(
        candidate_id=construction_input.candidate_id,
        case_id=construction_input.case_id,
        units=tuple(units),
        review_items=tuple(review_items),
    )


def _validate_sources(
    source_documents: tuple[StageASourceDocument, ...],
) -> dict[str, StageASourceDocument]:
    documents_by_id: dict[str, StageASourceDocument] = {}
    has_complaint = False
    has_motion = False
    for document in source_documents:
        if document.document_id in documents_by_id:
            raise ValueError(f"duplicate source document: {document.document_id}")
        if document.role in {StageADocumentRole.DECISION, StageADocumentRole.ORDER}:
            raise ValueError("Stage A source documents must exclude decisions/orders")
        if not document.is_predecision_material:
            raise ValueError("Stage A source documents must be pre-decision material")
        if document.contains_target_outcome:
            raise ValueError("Stage A source documents must not contain outcomes")
        if document.role in {
            StageADocumentRole.COMPLAINT,
            StageADocumentRole.AMENDED_COMPLAINT,
        }:
            has_complaint = True
        if document.role in {
            StageADocumentRole.MTD_NOTICE,
            StageADocumentRole.MTD_MEMORANDUM,
        }:
            has_motion = True
        documents_by_id[document.document_id] = document
    if not has_complaint:
        raise ValueError("Stage A requires complaint or amended complaint material")
    if not has_motion:
        raise ValueError("Stage A requires MTD notice or memorandum material")
    return documents_by_id


def _citation_for_seed(
    document: StageASourceDocument,
    seed: StageAUnitSeed,
) -> SourceCitation:
    return SourceCitation(
        document_id=document.document_id,
        docket_entry_number=document.docket_entry_number,
        page=seed.citation_page,
        paragraph=seed.citation_paragraph,
        excerpt=seed.citation_excerpt,
    )


def _defendant_group_label(seed: StageAUnitSeed) -> str:
    if seed.group_label is not None:
        return seed.group_label
    if seed.grouping is DefendantGrouping.GROUPED:
        return ", ".join(seed.defendant_names)
    return seed.defendant_names[0]


def _review_reason(
    seed: StageAUnitSeed,
    unit: PredictionUnit,
) -> UnitizationReviewReason | None:
    if seed.review_reason is not None:
        return seed.review_reason
    if unit.challenge_scope is ChallengeScope.UNCLEAR:
        return UnitizationReviewReason.UNCLEAR_CLAIM_OR_DEFENDANT
    if seed.unit_confidence < 0.5:
        return UnitizationReviewReason.LOW_CONFIDENCE
    return None


def _unit_id(
    candidate_id: str,
    count: str,
    claim_name: str,
    defendant_group: str,
) -> str:
    return "_".join(
        slug
        for slug in (
            _slug(candidate_id),
            _slug(count),
            _slug(claim_name),
            _slug(defendant_group),
        )
        if slug
    )


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_empty_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        _require_non_empty(value, field_name)
