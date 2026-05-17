from __future__ import annotations

from datetime import UTC, datetime, timedelta

from legalforecast.selection.contamination_filters import (
    LeakageSource,
    LeakageSourceKind,
    OutcomeLeakageType,
    detect_outcome_leakage,
)


def _evaluation_time() -> datetime:
    return datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _source(
    text: str,
    *,
    source_id: str = "source-1",
    source_kind: LeakageSourceKind = LeakageSourceKind.DOCKET_ENTRY,
    observed_at: datetime | None = None,
    related_family_id: str | None = None,
) -> LeakageSource:
    return LeakageSource(
        source_id=source_id,
        source_kind=source_kind,
        text=text,
        observed_at=observed_at or _evaluation_time() - timedelta(hours=1),
        related_family_id=related_family_id,
    )


def test_minute_order_granting_or_denying_target_motion_is_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Minute order granting defendant's motion to dismiss complaint.",
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.outcome_leakage_detected is True
    assert result.exclusion_reason == "outcome_leakage"
    assert result.findings[0].leakage_type is OutcomeLeakageType.MINUTE_ORDER


def test_oral_ruling_transcript_is_hard_excluded() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Hearing transcript of oral ruling denying the Rule 12 motion.",
                source_kind=LeakageSourceKind.ORAL_RULING_TRANSCRIPT,
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.findings[0].leakage_type is (
        OutcomeLeakageType.ORAL_RULING_TRANSCRIPT
    )


def test_report_and_recommendation_resolving_target_is_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Report and recommendation recommends granting the motion to dismiss.",
                source_kind=LeakageSourceKind.REPORT_AND_RECOMMENDATION,
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.findings[0].leakage_type is (
        OutcomeLeakageType.REPORT_AND_RECOMMENDATION
    )


def test_tentative_ruling_and_written_questions_revealing_result_are_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Tentative ruling granting the MTD.",
                source_id="tentative",
                source_kind=LeakageSourceKind.TENTATIVE_RULING,
            ),
            _source(
                "Questions for oral argument: why the motion should not be denied.",
                source_id="questions",
                source_kind=LeakageSourceKind.WRITTEN_QUESTION,
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert [finding.leakage_type for finding in result.findings] == [
        OutcomeLeakageType.TENTATIVE_RULING,
        OutcomeLeakageType.WRITTEN_QUESTION,
    ]


def test_related_case_order_resolving_identical_units_is_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Related-case order granted the motion to dismiss the identical "
                "Section 10(b) claim units.",
                source_kind=LeakageSourceKind.RELATED_CASE_ORDER,
                related_family_id="family-1",
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.findings[0].leakage_type is OutcomeLeakageType.RELATED_CASE_ORDER
    assert result.findings[0].related_family_id == "family-1"


def test_public_reporting_before_evaluation_is_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Press report: the motion to dismiss was denied yesterday.",
                source_kind=LeakageSourceKind.PUBLIC_REPORTING,
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.findings[0].leakage_type is OutcomeLeakageType.PUBLIC_REPORTING
    assert result.to_manifest_fields()["outcome_leakage_source_ids"] == ["source-1"]


def test_post_evaluation_reporting_does_not_leak_pre_run_packet() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Article reported that the motion to dismiss was granted.",
                source_kind=LeakageSourceKind.PUBLIC_REPORTING,
                observed_at=_evaluation_time() + timedelta(minutes=1),
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.outcome_leakage_detected is False
    assert result.exclusion_reason is None


def test_ordinary_legal_development_is_not_outcome_leakage() -> None:
    result = detect_outcome_leakage(
        (
            _source(
                "Court of Appeals decided a relevant Rule 12 pleading standard "
                "before the district court ruling.",
                source_kind=LeakageSourceKind.DOCUMENT_TEXT,
            ),
            _source(
                "News story profiles the parties and says the motion to dismiss "
                "remains pending.",
                source_kind=LeakageSourceKind.PUBLIC_REPORTING,
            ),
        ),
        evaluation_timestamp=_evaluation_time(),
    )

    assert result.outcome_leakage_detected is False
    assert result.to_manifest_fields()["outcome_leakage_findings"] == []
