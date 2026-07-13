"""Outcome-label schemas for frozen prediction units."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.unitization.schemas import PredictionUnit


class AmendmentClass(StrEnum):
    """Secondary amendment label for fully dismissed units."""

    NOT_FULLY_DISMISSED = "not_fully_dismissed"
    DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY = (
        "dismissed_with_express_amendment_opportunity"
    )
    DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY = (
        "dismissed_without_express_amendment_opportunity"
    )
    DISMISSED_WITH_EXPRESS_DENIAL_OF_LEAVE = "dismissed_with_express_denial_of_leave"
    AMBIGUOUS = "ambiguous"


class LaterProceduralChange(StrEnum):
    """Post-disposition events that do not change the locked primary label."""

    RECONSIDERATION = "reconsideration"
    APPEAL = "appeal"
    AMENDED_COMPLAINT = "amended_complaint"
    SETTLEMENT_OR_VOLUNTARY_DISMISSAL = "settlement_or_voluntary_dismissal"
    OTHER = "other"


class UnitResolution(StrEnum):
    """Decision-stage classification for one frozen prediction unit."""

    FULLY_DISMISSED = "fully_dismissed"
    SURVIVES_IN_MATERIAL_RESPECT = "survives_in_material_respect"
    PARTIAL_DISMISSAL_ONLY = "partial_dismissal_only"
    NOT_ADDRESSED_BY_THIS_DISPOSITION = "not_addressed_by_this_disposition"
    AMBIGUOUS = "ambiguous"


class AmendmentSignal(StrEnum):
    """Raw leave-to-amend signal observed in the first written disposition."""

    NOT_APPLICABLE = "not_applicable"
    EXPRESS_LEAVE_TO_AMEND = "express_leave_to_amend"
    EXPRESS_INVITATION_TO_SEEK_LEAVE = "express_invitation_to_seek_leave"
    EXPRESS_DENIAL_OF_LEAVE = "express_denial_of_leave"
    SILENT = "silent"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class StageBDecisionText:
    """First written disposition text available to Stage B outcome labelers."""

    document_id: str
    entered_date: str
    text: str
    is_first_written_disposition: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        _require_non_empty(self.entered_date, "entered_date")
        _require_non_empty(self.text, "text")
        if not self.is_first_written_disposition:
            raise ValueError("Stage B labels must use the first written disposition")

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def contains_excerpt(self, excerpt: str) -> bool:
        return excerpt.strip() in self.text

    def to_record(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "entered_date": self.entered_date,
            "text_sha256": self.text_sha256,
            "is_first_written_disposition": self.is_first_written_disposition,
        }


@dataclass(frozen=True, slots=True)
class StageBUnitFinding:
    """Structured decision-stage finding for one frozen prediction unit."""

    unit_id: str
    resolution: UnitResolution
    amendment_signal: AmendmentSignal
    supporting_excerpt: str
    labeler_confidence: float
    page: int | None = None
    paragraph: int | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(self.supporting_excerpt, "supporting_excerpt")
        _positive_int(self.page, "page")
        _positive_int(self.paragraph, "paragraph")
        if not 0 <= self.labeler_confidence <= 1:
            raise ValueError("labeler_confidence must be between 0 and 1")
        if self.notes is not None:
            _require_non_empty(self.notes, "notes")

        if self.resolution is UnitResolution.FULLY_DISMISSED:
            if self.amendment_signal in {
                AmendmentSignal.NOT_APPLICABLE,
                AmendmentSignal.AMBIGUOUS,
            }:
                raise ValueError(
                    "fully dismissed findings require a non-ambiguous amendment_signal"
                )
            return

        if self.resolution is UnitResolution.AMBIGUOUS:
            if self.amendment_signal is not AmendmentSignal.AMBIGUOUS:
                raise ValueError(
                    "ambiguous findings must use ambiguous amendment_signal"
                )
            return

        if self.resolution is UnitResolution.NOT_ADDRESSED_BY_THIS_DISPOSITION:
            if self.amendment_signal is not AmendmentSignal.NOT_APPLICABLE:
                raise ValueError(
                    "not-addressed findings must use not_applicable amendment_signal"
                )
            return

        if self.amendment_signal is not AmendmentSignal.NOT_APPLICABLE:
            raise ValueError(
                "surviving or partially dismissed findings must use "
                "not_applicable amendment_signal"
            )

    def to_record(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "resolution": self.resolution.value,
            "amendment_signal": self.amendment_signal.value,
            "supporting_excerpt": self.supporting_excerpt,
            "labeler_confidence": self.labeler_confidence,
            "page": self.page,
            "paragraph": self.paragraph,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class StageBMissingUnitFlag:
    """Decision-stage signal that a material unit was missing from Stage A."""

    missing_unit_description: str
    supporting_excerpt: str
    page: int | None = None
    paragraph: int | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.missing_unit_description, "missing_unit_description")
        _require_non_empty(self.supporting_excerpt, "supporting_excerpt")
        _positive_int(self.page, "page")
        _positive_int(self.paragraph, "paragraph")
        if self.notes is not None:
            _require_non_empty(self.notes, "notes")

    @property
    def routed_to_frozen_unit_workflow(self) -> bool:
        return True

    def to_record(self, decision_text: StageBDecisionText) -> dict[str, object]:
        return {
            "missing_unit_description": self.missing_unit_description,
            "decision_document_id": decision_text.document_id,
            "supporting_excerpt": self.supporting_excerpt,
            "page": self.page,
            "paragraph": self.paragraph,
            "notes": self.notes,
            "route": "frozen_unit_repair_or_exclusion",
            "routed_to_frozen_unit_workflow": (self.routed_to_frozen_unit_workflow),
        }


@dataclass(frozen=True, slots=True)
class StageBLabelingInput:
    """All material needed to label frozen units from one decision."""

    candidate_id: str
    case_id: str
    frozen_units: tuple[PredictionUnit, ...]
    decision_text: StageBDecisionText
    unit_findings: tuple[StageBUnitFinding, ...]
    missing_unit_flags: tuple[StageBMissingUnitFlag, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if not self.frozen_units:
            raise ValueError("frozen_units must not be empty")


@dataclass(frozen=True, slots=True)
class StageBLabelingResult:
    """Locked labels and repair-routing flags produced by Stage B."""

    candidate_id: str
    case_id: str
    decision_text: StageBDecisionText
    labels: tuple[OutcomeLabel, ...]
    missing_unit_flags: tuple[StageBMissingUnitFlag, ...]

    @property
    def labels_by_unit_id(self) -> dict[str, OutcomeLabel]:
        return {label.unit_id: label for label in self.labels}

    @property
    def requires_frozen_unit_workflow(self) -> bool:
        return bool(self.missing_unit_flags)

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "decision_text": self.decision_text.to_record(),
            "label_count": len(self.labels),
            "labels": [label.to_record() for label in self.labels],
            "missing_unit_flags": [
                flag.to_record(self.decision_text) for flag in self.missing_unit_flags
            ],
            "requires_frozen_unit_workflow": self.requires_frozen_unit_workflow,
        }


@dataclass(frozen=True, slots=True)
class OutcomeCitation:
    """Citation or short excerpt from the first written disposition."""

    document_id: str
    page: int | None = None
    paragraph: int | None = None
    excerpt: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.document_id, "document_id")
        _positive_int(self.page, "page")
        _positive_int(self.paragraph, "paragraph")
        if self.excerpt is not None:
            _require_non_empty(self.excerpt, "excerpt")

    def to_record(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "page": self.page,
            "paragraph": self.paragraph,
            "excerpt": self.excerpt,
        }


@dataclass(frozen=True, slots=True)
class OutcomeLabel:
    """Locked Stage B outcome label for a frozen prediction unit."""

    unit_id: str
    fully_dismissed: bool | None
    amendment_class: AmendmentClass
    ambiguous: bool
    label_confidence: float
    supporting_citations: tuple[OutcomeCitation, ...]
    first_written_disposition_id: str
    first_written_disposition_date: str
    first_written_disposition_locked: bool = True
    later_procedural_changes: tuple[LaterProceduralChange, ...] = ()
    notes: str | None = None
    unit_resolution: UnitResolution | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_non_empty(
            self.first_written_disposition_id,
            "first_written_disposition_id",
        )
        _require_non_empty(
            self.first_written_disposition_date,
            "first_written_disposition_date",
        )
        if not self.first_written_disposition_locked:
            raise ValueError("labels must lock to the first written disposition")
        if not 0 <= self.label_confidence <= 1:
            raise ValueError("label_confidence must be between 0 and 1")
        if not self.supporting_citations:
            raise ValueError("supporting_citations must include at least one citation")
        if self.notes is not None:
            _require_non_empty(self.notes, "notes")

        resolution = self.unit_resolution
        if resolution is None:
            resolution = _legacy_unit_resolution(
                fully_dismissed=self.fully_dismissed,
                ambiguous=self.ambiguous,
            )
            object.__setattr__(
                self,
                "unit_resolution",
                resolution,
            )

        if resolution is UnitResolution.FULLY_DISMISSED:
            if self.fully_dismissed is not True or self.ambiguous:
                raise ValueError(
                    "fully_dismissed resolution requires a non-ambiguous true label"
                )
        elif resolution in {
            UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
            UnitResolution.PARTIAL_DISMISSAL_ONLY,
        }:
            if self.fully_dismissed is not False or self.ambiguous:
                raise ValueError(
                    "survival/partial resolution requires a non-ambiguous false label"
                )
        elif self.fully_dismissed is not None or not self.ambiguous:
            raise ValueError(
                "ambiguous/not-addressed resolution requires an ambiguous label "
                "that must omit fully_dismissed"
            )

        if self.ambiguous:
            if self.fully_dismissed is not None:
                raise ValueError("ambiguous labels must omit fully_dismissed")
            if self.amendment_class is not AmendmentClass.AMBIGUOUS:
                raise ValueError("ambiguous labels must use ambiguous amendment_class")
            return

        if self.fully_dismissed is None:
            raise ValueError("non-ambiguous labels require fully_dismissed")

        if self.fully_dismissed:
            if self.amendment_class in {
                AmendmentClass.NOT_FULLY_DISMISSED,
                AmendmentClass.AMBIGUOUS,
            }:
                raise ValueError(
                    "fully dismissed labels require a dismissal amendment class"
                )
            return

        if self.amendment_class is not AmendmentClass.NOT_FULLY_DISMISSED:
            raise ValueError(
                "surviving units must use not_fully_dismissed amendment_class"
            )

    @property
    def canonical_unit_resolution(self) -> UnitResolution:
        """Return the explicit or schema-migrated raw disposition resolution."""

        if self.unit_resolution is None:  # pragma: no cover - guarded by __post_init__
            raise AssertionError("unit_resolution was not initialized")
        return self.unit_resolution

    @property
    def primary_outcome(self) -> int | None:
        """Return the scoring target y_u: 1 dismissed, 0 survived, or None."""

        if self.fully_dismissed is None:
            return None
        return 1 if self.fully_dismissed else 0

    @property
    def amendment_target_applicable(self) -> bool:
        return self.fully_dismissed is True and not self.ambiguous

    @property
    def conditional_amendment_target(self) -> bool | None:
        """Return the secondary target among fully dismissed units only."""

        if not self.amendment_target_applicable:
            return None
        return (
            self.amendment_class
            is AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY
        )

    def with_later_procedural_change(
        self,
        change: LaterProceduralChange,
    ) -> OutcomeLabel:
        """Return a copy tagged with a later event without changing y_u."""

        return OutcomeLabel(
            unit_id=self.unit_id,
            unit_resolution=self.unit_resolution,
            fully_dismissed=self.fully_dismissed,
            amendment_class=self.amendment_class,
            ambiguous=self.ambiguous,
            label_confidence=self.label_confidence,
            supporting_citations=self.supporting_citations,
            first_written_disposition_id=self.first_written_disposition_id,
            first_written_disposition_date=self.first_written_disposition_date,
            first_written_disposition_locked=self.first_written_disposition_locked,
            later_procedural_changes=(*self.later_procedural_changes, change),
            notes=self.notes,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "unit_resolution": self.canonical_unit_resolution.value,
            "fully_dismissed": self.fully_dismissed,
            "primary_outcome": self.primary_outcome,
            "amendment_class": self.amendment_class.value,
            "amendment_target_applicable": self.amendment_target_applicable,
            "conditional_amendment_target": self.conditional_amendment_target,
            "ambiguous": self.ambiguous,
            "label_confidence": self.label_confidence,
            "supporting_citations": [
                citation.to_record() for citation in self.supporting_citations
            ],
            "first_written_disposition_id": self.first_written_disposition_id,
            "first_written_disposition_date": self.first_written_disposition_date,
            "first_written_disposition_locked": (self.first_written_disposition_locked),
            "later_procedural_changes": [
                change.value for change in self.later_procedural_changes
            ],
            "notes": self.notes,
        }


def label_stage_b_outcomes(labeling_input: StageBLabelingInput) -> StageBLabelingResult:
    """Label every scoreable frozen unit from the first written disposition."""

    units_by_id = _index_units(labeling_input.frozen_units)
    findings_by_unit_id = _index_findings(labeling_input.unit_findings)
    scorable_unit_ids = {
        unit.unit_id for unit in labeling_input.frozen_units if unit.should_score
    }

    unknown_unit_ids = sorted(set(findings_by_unit_id) - set(units_by_id))
    if unknown_unit_ids:
        raise ValueError(
            "decision-stage findings may not create prediction units; route "
            f"unknown unit_id values as missing-unit flags: {unknown_unit_ids}"
        )

    unscored_unit_ids = sorted(
        unit_id
        for unit_id in findings_by_unit_id
        if not units_by_id[unit_id].should_score
    )
    if unscored_unit_ids:
        raise ValueError(
            "Stage B findings are only allowed for scoreable frozen units: "
            f"{unscored_unit_ids}"
        )

    missing_label_ids = sorted(scorable_unit_ids - set(findings_by_unit_id))
    if missing_label_ids:
        raise ValueError(
            f"missing outcome findings for frozen units: {missing_label_ids}"
        )

    _validate_excerpts(
        labeling_input.decision_text,
        labeling_input.unit_findings,
        labeling_input.missing_unit_flags,
    )

    labels = tuple(
        _label_from_finding(
            finding=findings_by_unit_id[unit.unit_id],
            decision_text=labeling_input.decision_text,
        )
        for unit in labeling_input.frozen_units
        if unit.unit_id in findings_by_unit_id
    )
    return StageBLabelingResult(
        candidate_id=labeling_input.candidate_id,
        case_id=labeling_input.case_id,
        decision_text=labeling_input.decision_text,
        labels=labels,
        missing_unit_flags=labeling_input.missing_unit_flags,
    )


def _label_from_finding(
    *,
    finding: StageBUnitFinding,
    decision_text: StageBDecisionText,
) -> OutcomeLabel:
    fully_dismissed = _fully_dismissed(finding.resolution)
    return OutcomeLabel(
        unit_id=finding.unit_id,
        unit_resolution=finding.resolution,
        fully_dismissed=fully_dismissed,
        amendment_class=_amendment_class(finding),
        ambiguous=finding.resolution
        in {
            UnitResolution.AMBIGUOUS,
            UnitResolution.NOT_ADDRESSED_BY_THIS_DISPOSITION,
        },
        label_confidence=_label_confidence(finding),
        supporting_citations=(
            OutcomeCitation(
                document_id=decision_text.document_id,
                page=finding.page,
                paragraph=finding.paragraph,
                excerpt=finding.supporting_excerpt,
            ),
        ),
        first_written_disposition_id=decision_text.document_id,
        first_written_disposition_date=decision_text.entered_date,
        notes=finding.notes,
    )


def _fully_dismissed(resolution: UnitResolution) -> bool | None:
    if resolution is UnitResolution.FULLY_DISMISSED:
        return True
    if resolution in {
        UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
        UnitResolution.PARTIAL_DISMISSAL_ONLY,
    }:
        return False
    return None


def _amendment_class(finding: StageBUnitFinding) -> AmendmentClass:
    if finding.resolution in {
        UnitResolution.AMBIGUOUS,
        UnitResolution.NOT_ADDRESSED_BY_THIS_DISPOSITION,
    }:
        return AmendmentClass.AMBIGUOUS
    if finding.resolution is not UnitResolution.FULLY_DISMISSED:
        return AmendmentClass.NOT_FULLY_DISMISSED

    if finding.amendment_signal in {
        AmendmentSignal.EXPRESS_LEAVE_TO_AMEND,
        AmendmentSignal.EXPRESS_INVITATION_TO_SEEK_LEAVE,
    }:
        return AmendmentClass.DISMISSED_WITH_EXPRESS_AMENDMENT_OPPORTUNITY
    if finding.amendment_signal is AmendmentSignal.EXPRESS_DENIAL_OF_LEAVE:
        return AmendmentClass.DISMISSED_WITH_EXPRESS_DENIAL_OF_LEAVE
    if finding.amendment_signal is AmendmentSignal.SILENT:
        return AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
    raise ValueError(f"unsupported amendment signal: {finding.amendment_signal.value}")


def _label_confidence(finding: StageBUnitFinding) -> float:
    if finding.resolution in {
        UnitResolution.AMBIGUOUS,
        UnitResolution.NOT_ADDRESSED_BY_THIS_DISPOSITION,
    }:
        return min(finding.labeler_confidence, 0.5)
    return finding.labeler_confidence


def _index_units(units: tuple[PredictionUnit, ...]) -> dict[str, PredictionUnit]:
    indexed: dict[str, PredictionUnit] = {}
    for unit in units:
        if unit.unit_id in indexed:
            raise ValueError(f"duplicate frozen unit_id: {unit.unit_id}")
        indexed[unit.unit_id] = unit
    return indexed


def _index_findings(
    findings: tuple[StageBUnitFinding, ...],
) -> dict[str, StageBUnitFinding]:
    indexed: dict[str, StageBUnitFinding] = {}
    for finding in findings:
        if finding.unit_id in indexed:
            raise ValueError(
                f"duplicate Stage B finding for unit_id: {finding.unit_id}"
            )
        indexed[finding.unit_id] = finding
    return indexed


def _validate_excerpts(
    decision_text: StageBDecisionText,
    findings: tuple[StageBUnitFinding, ...],
    missing_unit_flags: tuple[StageBMissingUnitFlag, ...],
) -> None:
    for finding in findings:
        if not decision_text.contains_excerpt(finding.supporting_excerpt):
            raise ValueError(
                "supporting_excerpt must appear in decision text for "
                f"unit_id {finding.unit_id}"
            )
    for flag in missing_unit_flags:
        if not decision_text.contains_excerpt(flag.supporting_excerpt):
            raise ValueError(
                "missing-unit supporting_excerpt must appear in decision text"
            )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _legacy_unit_resolution(
    *, fully_dismissed: bool | None, ambiguous: bool
) -> UnitResolution:
    """Migrate pre-resolution records without collapsing new explicit values."""

    if fully_dismissed is True and not ambiguous:
        return UnitResolution.FULLY_DISMISSED
    if fully_dismissed is False and not ambiguous:
        return UnitResolution.SURVIVES_IN_MATERIAL_RESPECT
    return UnitResolution.AMBIGUOUS


def _positive_int(value: int | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive")
