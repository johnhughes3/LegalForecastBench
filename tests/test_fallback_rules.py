from __future__ import annotations

import json

from legalforecast.selection.case_mix_diagnostics import (
    CaseMixCandidate,
    DocumentCompleteness,
    FallbackSource,
)
from legalforecast.selection.fallback_rules import (
    FallbackDecisionStatus,
    FallbackGap,
    decide_targeted_fallback,
    targeted_fallback_rules,
)


def test_docket_listing_gap_uses_courtlistener_recap_before_pacer() -> None:
    decision = decide_targeted_fallback(
        FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE,
        available_sources=(FallbackSource.PACER, FallbackSource.COURTLISTENER_RECAP),
    )

    assert decision.status is FallbackDecisionStatus.CASE_DEV_PLUS_FALLBACK
    assert decision.fallback_source is FallbackSource.COURTLISTENER_RECAP
    assert decision.fallback_reason == "docket_entry_listing_unavailable"
    assert decision.exclusion_reason is None
    assert decision.to_case_mix_fields() == {
        "fallback_used": True,
        "fallback_source": FallbackSource.COURTLISTENER_RECAP,
        "fallback_reason": "docket_entry_listing_unavailable",
        "included_in_benchmark": True,
        "exclusion_reason": None,
    }


def test_pacer_is_last_resort_for_missing_public_document() -> None:
    decision = decide_targeted_fallback(
        "missing_motion_document",
        available_sources=("pacer",),
    )

    assert decision.status is FallbackDecisionStatus.CASE_DEV_PLUS_FALLBACK
    assert decision.fallback_source is FallbackSource.PACER
    assert decision.fallback_reason == FallbackGap.MISSING_MOTION_DOCUMENT.value


def test_fallback_unavailable_excludes_with_gap_specific_reason() -> None:
    decision = decide_targeted_fallback(
        FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE,
        available_sources=(),
    )

    assert decision.status is FallbackDecisionStatus.EXCLUDED
    assert decision.included_in_benchmark is False
    assert decision.fallback_used is False
    assert decision.exclusion_reason == "fallback_unavailable_docket_entry_listing"


def test_hard_exclusion_gaps_do_not_use_available_provider_fallback() -> None:
    for gap in (
        FallbackGap.OUTCOME_LEAKAGE,
        FallbackGap.SEALED_OR_RESTRICTED_MATERIAL,
        FallbackGap.AMBIGUOUS_MOTION_ORDER_LINKAGE,
    ):
        decision = decide_targeted_fallback(
            gap,
            available_sources=(
                FallbackSource.COURTLISTENER_RECAP,
                FallbackSource.PACER,
            ),
        )

        assert decision.status is FallbackDecisionStatus.EXCLUDED
        assert decision.fallback_source is FallbackSource.CASE_DEV_ONLY
        assert decision.fallback_reason is None


def test_case_dev_only_and_fallback_decisions_feed_case_mix_fields() -> None:
    case_dev_only = _candidate(
        "case-dev-only",
        **decide_targeted_fallback(None).to_case_mix_fields(),
    )
    fallback = _candidate(
        "case-dev-plus-fallback",
        **decide_targeted_fallback(
            FallbackGap.MISSING_COMPLAINT_DOCUMENT,
            available_sources=(FallbackSource.RECAP,),
        ).to_case_mix_fields(),
    )
    excluded = _candidate(
        "excluded",
        units=0,
        **decide_targeted_fallback(
            FallbackGap.MISSING_COMPLAINT_DOCUMENT,
            available_sources=(),
        ).to_case_mix_fields(),
    )

    assert case_dev_only.source_class == "case.dev-only"
    assert fallback.source_class == "case.dev-plus-fallback"
    assert excluded.source_class == "excluded"
    json.dumps([case_dev_only.to_record(), fallback.to_record(), excluded.to_record()])


def test_rule_table_is_machine_readable_for_docs_and_protocols() -> None:
    records = [rule.to_record() for rule in targeted_fallback_rules()]
    gaps = {record["gap"] for record in records}

    assert "docket_entry_listing_unavailable" in gaps
    assert "outcome_leakage" in gaps
    assert next(
        record
        for record in records
        if record["gap"] == "docket_entry_listing_unavailable"
    )["preferred_sources"] == [
        "courtlistener_recap",
        "courtlistener",
        "recap",
        "pacer",
    ]
    assert (
        next(record for record in records if record["gap"] == "outcome_leakage")[
            "fallback_allowed"
        ]
        is False
    )


def _candidate(
    candidate_id: str,
    *,
    fallback_used: bool,
    fallback_source: FallbackSource,
    fallback_reason: str | None,
    included_in_benchmark: bool,
    exclusion_reason: str | None,
    units: int = 2,
) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id=candidate_id,
        case_id=f"case-{candidate_id}",
        district="S.D.N.Y.",
        circuit="2d",
        nos_code="190",
        nos_macro_category="contract",
        represented_party_status="all_represented",
        government_party_status="no_government_party",
        mdl_flag=False,
        public_company_flag=False,
        claim_count=2,
        defendant_count=2,
        defendant_group_count=1,
        prediction_unit_count=units,
        document_completeness=DocumentCompleteness.COMPLETE,
        motion_available=True,
        opposition_available=True,
        reply_available=True,
        fallback_used=fallback_used,
        fallback_source=fallback_source,
        fallback_reason=fallback_reason,
        included_in_benchmark=included_in_benchmark,
        exclusion_reason=exclusion_reason,
    )
