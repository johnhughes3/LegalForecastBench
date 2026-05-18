from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from legalforecast.selection import (
    ContaminationMetadata,
    ContaminationRisk,
    EligibilityStatus,
    ModelRunMetadata,
    PressPublicityTag,
    SeriesCaseTiming,
    TrainingCutoffStatus,
)
from legalforecast.selection.case_mix_diagnostics import (
    CaseMixCandidate,
    DocumentCompleteness,
    build_case_mix_diagnostics,
)
from legalforecast.selection.contamination_filters import (
    LeakageSource,
    LeakageSourceKind,
    detect_outcome_leakage,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedger,
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)


def test_selection_controls_compose_without_leaking_or_overclaiming_scope() -> None:
    evaluation_time = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    leakage = detect_outcome_leakage(
        (
            LeakageSource(
                source_id="article-leak",
                source_kind=LeakageSourceKind.PUBLIC_REPORTING,
                text=(
                    "News story reported that the motion to dismiss was "
                    "granted before model evaluation."
                ),
                observed_at=evaluation_time - timedelta(hours=1),
            ),
        ),
        evaluation_timestamp=evaluation_time,
    )
    ordinary_development = detect_outcome_leakage(
        (
            LeakageSource(
                source_id="article-1",
                source_kind=LeakageSourceKind.PUBLIC_REPORTING,
                text=(
                    "News story reports that an appellate pleading-standard "
                    "decision issued while the motion remains pending."
                ),
                observed_at=evaluation_time - timedelta(hours=1),
            ),
        ),
        evaluation_timestamp=evaluation_time,
    )

    leaked_metadata = _contamination_metadata(
        evaluation_time=evaluation_time,
        outcome_leakage_detected=leakage.outcome_leakage_detected,
    )
    clean_metadata = _contamination_metadata(
        evaluation_time=evaluation_time,
        outcome_leakage_detected=ordinary_development.outcome_leakage_detected,
        contamination_risk=ContaminationRisk.PUBLIC_REPORTING,
        press_publicity_tags=(PressPublicityTag.HIGH_NEWS_VOLUME,),
    )

    leakage_entry = ExclusionLedgerEntry.from_outcome_leakage(
        candidate_id="cand-leak",
        case_id="case-leak",
        court="S.D.N.Y.",
        decision_date=date(2026, 5, 13),
        leakage_result=leakage,
    )
    ledger = ExclusionLedger(
        (
            leakage_entry,
            ExclusionLedgerEntry(
                candidate_id="cand-missing",
                case_id="case-missing",
                court="D. Del.",
                decision_date=date(2026, 5, 12),
                stage=ExclusionStage.RETRIEVAL,
                reason=ExclusionReason.MISSING_CORE_FILING.value,
                source_entry_ids=("entry-12",),
                source_document_ids=("doc-12",),
                notes="Target MTD memorandum was unavailable.",
            ),
        )
    )
    diagnostics = build_case_mix_diagnostics(
        (
            _candidate(
                "cand-clean",
                units=2,
                press_publicity_tags=(PressPublicityTag.HIGH_NEWS_VOLUME,),
            ),
            _candidate("cand-family-a", related_family_id="family-a", units=5),
            _candidate("cand-family-b", related_family_id="family-a", units=4),
            _candidate(
                "cand-leak",
                included=False,
                units=0,
                exclusion_reason=ExclusionReason.OUTCOME_LEAKAGE.value,
            ),
            _candidate(
                "cand-missing",
                included=False,
                units=0,
                exclusion_reason=ExclusionReason.MISSING_CORE_FILING.value,
            ),
        ),
        cycle_id="cycle-2026-05",
        dominance_threshold=0.50,
    )

    record = diagnostics.to_record()
    primary_reasons = [
        entry["primary_exclusion_reason"] for entry in ledger.to_records()
    ]

    assert leaked_metadata.eligibility_status is (
        EligibilityStatus.INELIGIBLE_OUTCOME_LEAKAGE
    )
    assert clean_metadata.eligibility_status is EligibilityStatus.ELIGIBLE
    assert ordinary_development.outcome_leakage_detected is False
    assert clean_metadata.to_manifest_record()["press_publicity_tags"] == [
        "high_news_volume"
    ]
    assert primary_reasons == ["outcome_leakage", "missing_core_filing"]
    assert all("primary_exclusion_reason" in entry for entry in ledger.to_records())
    assert record["scope_note"].endswith("not_population_representativeness")
    assert record["included_candidate_count"] == 3
    assert record["excluded_candidate_count"] == 2
    assert record["dominance_triggered"] is True
    assert record["tables"]["district"]
    assert record["tables"]["document_completeness"]
    assert (
        _bucket(record["tables"]["press_publicity_tags"], "high_news_volume")[
            "candidate_count"
        ]
        == 1
    )
    assert (
        _bucket(record["tables"]["press_publicity_sensitivity_flag"], "true")[
            "unit_count"
        ]
        == 2
    )
    assert record["exclusion_reason_distribution"]


def _contamination_metadata(
    *,
    evaluation_time: datetime,
    outcome_leakage_detected: bool,
    contamination_risk: ContaminationRisk = ContaminationRisk.NONE_DETECTED,
    press_publicity_tags: tuple[PressPublicityTag, ...] = (),
) -> ContaminationMetadata:
    return ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=evaluation_time - timedelta(days=1),
            decision_entered_at=evaluation_time + timedelta(days=1),
            case_filed_at=date(2026, 4, 1),
            motion_filed_at=date(2026, 4, 15),
            briefing_completed_at=date(2026, 5, 1),
        ),
        model_run=ModelRunMetadata(
            provider="example",
            model_name="frontier-model",
            model_version_or_snapshot="2026-05-14",
            evaluation_timestamp=evaluation_time,
            network_disabled=True,
            search_disabled=True,
            provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
            provider_training_cutoff=date(2026, 4, 1),
        ),
        publicity_or_related_case_risk=contamination_risk,
        press_publicity_tags=press_publicity_tags,
        outcome_leakage_detected=outcome_leakage_detected,
    )


def _candidate(
    candidate_id: str,
    *,
    included: bool = True,
    units: int = 2,
    related_family_id: str | None = None,
    press_publicity_tags: tuple[PressPublicityTag, ...] = (),
    exclusion_reason: str | None = None,
) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id=candidate_id,
        case_id=f"case-{candidate_id}",
        district="S.D.N.Y.",
        circuit="2d",
        nos_code="850",
        nos_macro_category="securities",
        represented_party_status="all_represented",
        government_party_status="no_government_party",
        mdl_flag=False,
        public_company_flag=True,
        claim_count=2,
        defendant_count=2,
        defendant_group_count=1,
        prediction_unit_count=units,
        document_completeness=DocumentCompleteness.COMPLETE,
        motion_available=True,
        opposition_available=True,
        reply_available=False,
        fallback_used=False,
        press_publicity_tags=press_publicity_tags,
        included_in_benchmark=included,
        related_family_id=related_family_id,
        exclusion_reason=exclusion_reason,
    )


def _bucket(records: list[dict[str, object]], bucket: str) -> dict[str, object]:
    return next(record for record in records if record["bucket"] == bucket)
