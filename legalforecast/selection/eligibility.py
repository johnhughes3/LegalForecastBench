"""Eligibility and contamination metadata for benchmark manifests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any


class TrainingCutoffStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    NOT_DISCLOSED = "not_disclosed"


class ContaminationRisk(StrEnum):
    NONE_DETECTED = "none_detected"
    RELATED_CASE = "related_case_risk"
    PUBLIC_REPORTING = "public_reporting_risk"
    RELATED_CASE_AND_PUBLIC_REPORTING = "related_case_and_public_reporting_risk"
    UNKNOWN = "unknown"


class PressPublicityTag(StrEnum):
    HIGH_NEWS_VOLUME = "high_news_volume"
    WIKIPEDIA_PAGE = "wikipedia_page"
    MAJOR_PUBLIC_COMPANY_PARTY = "major_public_company_party"
    MAJOR_MASS_TORT_OR_MDL = "major_mass_tort_or_mdl"
    CONSTITUTIONAL_OR_POLITICAL_SALIENCE = "constitutional_or_political_salience"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE_DECISION_BEFORE_DEPLOYMENT = "ineligible_decision_before_deployment"
    INELIGIBLE_OUTCOME_LEAKAGE = "ineligible_outcome_leakage"


def _require_non_empty(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
    return value


def _require_aware(timestamp: datetime, field_name: str) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return timestamp


def _iso_datetime(timestamp: datetime) -> str:
    utc_timestamp = timestamp.astimezone(UTC)
    return utc_timestamp.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ModelRunMetadata:
    """Model-specific run metadata needed for cutoff sensitivity analysis."""

    provider: str
    model_name: str
    model_version_or_snapshot: str
    evaluation_timestamp: datetime
    network_disabled: bool
    search_disabled: bool
    provider_training_cutoff_status: TrainingCutoffStatus
    provider_training_cutoff: date | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, "provider")
        _require_non_empty(self.model_name, "model_name")
        _require_non_empty(self.model_version_or_snapshot, "model_version_or_snapshot")
        _require_aware(self.evaluation_timestamp, "evaluation_timestamp")

        if self.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN:
            if self.provider_training_cutoff is None:
                raise ValueError(
                    "provider_training_cutoff is required when cutoff status is known"
                )
            return

        if self.provider_training_cutoff is not None:
            raise ValueError(
                "provider_training_cutoff must be omitted when cutoff status is "
                "not known"
            )

    @property
    def post_cutoff_sensitivity_available(self) -> bool:
        return self.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN

    def date_after_training_cutoff(self, value: date | None) -> bool | None:
        if value is None or self.provider_training_cutoff is None:
            return None
        return value > self.provider_training_cutoff

    def to_manifest_fields(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "model_version_or_snapshot": self.model_version_or_snapshot,
            "evaluation_timestamp": _iso_datetime(self.evaluation_timestamp),
            "network_disabled": self.network_disabled,
            "search_disabled": self.search_disabled,
            "provider_training_cutoff_status": (
                self.provider_training_cutoff_status.value
            ),
            "provider_training_cutoff_if_known": (
                self.provider_training_cutoff.isoformat()
                if self.provider_training_cutoff is not None
                else None
            ),
            "post_cutoff_sensitivity_available": (
                self.post_cutoff_sensitivity_available
            ),
        }


@dataclass(frozen=True, slots=True)
class SeriesCaseTiming:
    """Case timing metadata used to decide eligibility and cutoff strata."""

    series_release_timestamp: datetime
    decision_entered_at: datetime
    case_filed_at: date | None = None
    motion_filed_at: date | None = None
    briefing_completed_at: date | None = None

    def __post_init__(self) -> None:
        _require_aware(self.series_release_timestamp, "series_release_timestamp")
        _require_aware(self.decision_entered_at, "decision_entered_at")

    @property
    def decision_entered_on_or_after_model_deployment(self) -> bool:
        """Whether the decision falls on or after the UTC deployment date."""

        return self.decision_entered_at.astimezone(UTC).date() >= (
            self.series_release_timestamp.astimezone(UTC).date()
        )

    def to_manifest_fields(self, model_run: ModelRunMetadata) -> dict[str, Any]:
        return {
            "series_release_timestamp": _iso_datetime(self.series_release_timestamp),
            "decision_entered_at": _iso_datetime(self.decision_entered_at),
            "decision_on_or_after_deployment": (
                self.decision_entered_on_or_after_model_deployment
            ),
            "case_filed_at": (
                self.case_filed_at.isoformat() if self.case_filed_at else None
            ),
            "motion_filed_at": (
                self.motion_filed_at.isoformat() if self.motion_filed_at else None
            ),
            "briefing_completed_at": (
                self.briefing_completed_at.isoformat()
                if self.briefing_completed_at
                else None
            ),
            "filed_after_cutoff": model_run.date_after_training_cutoff(
                self.case_filed_at
            ),
            "motion_after_cutoff": model_run.date_after_training_cutoff(
                self.motion_filed_at
            ),
            "briefing_completed_after_cutoff": model_run.date_after_training_cutoff(
                self.briefing_completed_at
            ),
        }


@dataclass(frozen=True, slots=True)
class ContaminationMetadata:
    """Complete contamination metadata emitted into candidate manifests."""

    case_timing: SeriesCaseTiming
    model_run: ModelRunMetadata
    publicity_or_related_case_risk: ContaminationRisk = ContaminationRisk.NONE_DETECTED
    press_publicity_tags: tuple[PressPublicityTag, ...] = ()
    outcome_leakage_detected: bool = False
    related_case_family_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if (
            self.publicity_or_related_case_risk
            in {
                ContaminationRisk.RELATED_CASE,
                ContaminationRisk.RELATED_CASE_AND_PUBLIC_REPORTING,
            }
            and self.related_case_family_id is None
        ):
            raise ValueError(
                "related_case_family_id is required for related-case contamination risk"
            )
        _require_unique_press_publicity_tags(self.press_publicity_tags)

    @property
    def eligibility_status(self) -> EligibilityStatus:
        if self.outcome_leakage_detected:
            return EligibilityStatus.INELIGIBLE_OUTCOME_LEAKAGE
        if not self.case_timing.decision_entered_on_or_after_model_deployment:
            return EligibilityStatus.INELIGIBLE_DECISION_BEFORE_DEPLOYMENT
        return EligibilityStatus.ELIGIBLE

    @property
    def is_eligible(self) -> bool:
        return self.eligibility_status is EligibilityStatus.ELIGIBLE

    def to_manifest_record(self) -> dict[str, Any]:
        record = {
            "eligibility_status": self.eligibility_status.value,
            "is_eligible": self.is_eligible,
            "outcome_leakage_detected": self.outcome_leakage_detected,
            "publicity_or_related_case_risk": (
                self.publicity_or_related_case_risk.value
            ),
            "press_publicity_tags": [tag.value for tag in self.press_publicity_tags],
            "press_publicity_sensitivity_required": bool(self.press_publicity_tags),
            "related_case_family_id": self.related_case_family_id,
            "contamination_notes": self.notes,
        }
        record.update(self.case_timing.to_manifest_fields(self.model_run))
        record.update(self.model_run.to_manifest_fields())
        return record


def _require_unique_press_publicity_tags(
    tags: tuple[PressPublicityTag, ...],
) -> None:
    tag_values = [tag.value for tag in tags]
    if len(set(tag_values)) != len(tag_values):
        raise ValueError("press_publicity_tags must be unique")
