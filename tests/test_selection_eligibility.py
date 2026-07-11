from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from legalforecast.selection import (
    ContaminationMetadata,
    ContaminationRisk,
    EligibilityStatus,
    ModelRunMetadata,
    PressPublicityTag,
    SeriesCaseTiming,
    TrainingCutoffStatus,
)


def _known_cutoff_run() -> ModelRunMetadata:
    return ModelRunMetadata(
        provider="example-provider",
        model_name="example-model",
        model_version_or_snapshot="2026-05-14",
        evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        network_disabled=True,
        search_disabled=True,
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=date(2026, 4, 1),
    )


def test_manifest_serialization_records_required_eligibility_fields() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            case_filed_at=date(2026, 3, 20),
            motion_filed_at=date(2026, 4, 15),
            briefing_completed_at=date(2026, 4, 30),
        ),
        model_run=_known_cutoff_run(),
    )

    record = metadata.to_manifest_record()

    assert record["eligibility_status"] == EligibilityStatus.ELIGIBLE.value
    assert record["is_eligible"] is True
    assert record["decision_on_or_after_deployment"] is True
    assert record["filed_after_cutoff"] is False
    assert record["motion_after_cutoff"] is True
    assert record["briefing_completed_after_cutoff"] is True
    assert record["provider_training_cutoff_if_known"] == "2026-04-01"
    assert record["post_cutoff_sensitivity_available"] is True
    assert record["network_disabled"] is True
    assert record["search_disabled"] is True
    json.dumps(record)


def test_unknown_provider_cutoff_keeps_cutoff_strata_unknown() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            case_filed_at=date(2026, 3, 20),
            motion_filed_at=date(2026, 4, 15),
            briefing_completed_at=date(2026, 4, 30),
        ),
        model_run=ModelRunMetadata(
            provider="unknown-cutoff-provider",
            model_name="frontier-model",
            model_version_or_snapshot="stable",
            evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
            network_disabled=True,
            search_disabled=True,
            provider_training_cutoff_status=TrainingCutoffStatus.UNKNOWN,
        ),
    )

    record = metadata.to_manifest_record()

    assert record["eligibility_status"] == EligibilityStatus.ELIGIBLE.value
    assert record["provider_training_cutoff_if_known"] is None
    assert record["post_cutoff_sensitivity_available"] is False
    assert record["filed_after_cutoff"] is None
    assert record["motion_after_cutoff"] is None
    assert record["briefing_completed_after_cutoff"] is None


def test_known_training_cutoff_requires_cutoff_date() -> None:
    with pytest.raises(ValueError, match="provider_training_cutoff is required"):
        ModelRunMetadata(
            provider="example-provider",
            model_name="example-model",
            model_version_or_snapshot="2026-05-14",
            evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
            network_disabled=True,
            search_disabled=True,
            provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        )


def test_decision_on_same_utc_date_as_deployment_is_eligible() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 23, 59, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 14, 0, 1, tzinfo=UTC),
        ),
        model_run=_known_cutoff_run(),
    )

    assert metadata.case_timing.decision_entered_on_or_after_model_deployment is True
    assert metadata.eligibility_status is EligibilityStatus.ELIGIBLE
    assert metadata.is_eligible is True


def test_decision_on_previous_utc_date_is_not_eligible() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 13, 23, 59, tzinfo=UTC),
        ),
        model_run=_known_cutoff_run(),
    )

    assert metadata.is_eligible is False
    assert (
        metadata.eligibility_status
        is EligibilityStatus.INELIGIBLE_DECISION_BEFORE_DEPLOYMENT
    )


def test_outcome_leakage_overrides_deployment_date_eligibility() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
        ),
        model_run=_known_cutoff_run(),
        press_publicity_tags=(PressPublicityTag.HIGH_NEWS_VOLUME,),
        outcome_leakage_detected=True,
    )

    assert metadata.is_eligible is False
    assert metadata.eligibility_status is EligibilityStatus.INELIGIBLE_OUTCOME_LEAKAGE


def test_non_leaking_publicity_tags_preserve_eligibility_and_manifest_slices() -> None:
    metadata = ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
        ),
        model_run=_known_cutoff_run(),
        publicity_or_related_case_risk=ContaminationRisk.PUBLIC_REPORTING,
        press_publicity_tags=(
            PressPublicityTag.HIGH_NEWS_VOLUME,
            PressPublicityTag.WIKIPEDIA_PAGE,
        ),
    )

    record = metadata.to_manifest_record()

    assert metadata.eligibility_status is EligibilityStatus.ELIGIBLE
    assert record["outcome_leakage_detected"] is False
    assert record["press_publicity_sensitivity_required"] is True
    assert record["press_publicity_tags"] == [
        "high_news_volume",
        "wikipedia_page",
    ]


def test_publicity_tags_must_be_unique() -> None:
    with pytest.raises(ValueError, match="press_publicity_tags"):
        ContaminationMetadata(
            case_timing=SeriesCaseTiming(
                series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
                decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            ),
            model_run=_known_cutoff_run(),
            press_publicity_tags=(
                PressPublicityTag.MAJOR_PUBLIC_COMPANY_PARTY,
                PressPublicityTag.MAJOR_PUBLIC_COMPANY_PARTY,
            ),
        )


def test_related_case_risk_requires_family_id() -> None:
    with pytest.raises(ValueError, match="related_case_family_id is required"):
        ContaminationMetadata(
            case_timing=SeriesCaseTiming(
                series_release_timestamp=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
                decision_entered_at=datetime(2026, 5, 15, 14, 30, tzinfo=UTC),
            ),
            model_run=_known_cutoff_run(),
            publicity_or_related_case_risk=ContaminationRisk.RELATED_CASE,
        )
