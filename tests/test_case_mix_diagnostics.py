from __future__ import annotations

import json

import pytest
from legalforecast.selection.case_mix_diagnostics import (
    CandidateSourceClass,
    CaseMixCandidate,
    DocumentCompleteness,
    DominanceDimension,
    FallbackSource,
    build_case_mix_diagnostics,
)
from legalforecast.selection.eligibility import PressPublicityTag


def test_diagnostics_serializes_mandatory_case_mix_fields() -> None:
    diagnostics = build_case_mix_diagnostics(
        (
            _candidate(
                "cand-1",
                district="S.D.N.Y.",
                circuit="2d",
                nos_code="190",
                nos_macro_category="contract",
                units=3,
                document_completeness=DocumentCompleteness.COMPLETE,
                motion_available=True,
                opposition_available=True,
                reply_available=True,
            ),
            _candidate(
                "cand-2",
                district="D. Del.",
                circuit="3d",
                nos_code="850",
                nos_macro_category="securities",
                units=3,
                represented_party_status="all_represented",
                government_party_status="no_government_party",
                document_completeness=DocumentCompleteness.MISSING_REPLY,
                public_company_flag=True,
                fallback_used=True,
                fallback_source=FallbackSource.RECAP,
                fallback_reason="missing_reply_document",
                press_publicity_tags=(
                    PressPublicityTag.HIGH_NEWS_VOLUME,
                    PressPublicityTag.MAJOR_PUBLIC_COMPANY_PARTY,
                ),
            ),
            _candidate(
                "cand-excluded",
                district="D. Del.",
                circuit="3d",
                included=False,
                exclusion_reason="missing_core_filing",
                units=0,
            ),
        ),
        cycle_id="cycle-2026-05",
        dominance_threshold=0.75,
    )

    record = diagnostics.to_record()
    tables = record["tables"]

    assert record["cycle_id"] == "cycle-2026-05"
    assert record["candidate_count"] == 3
    assert record["included_candidate_count"] == 2
    assert record["excluded_candidate_count"] == 1
    assert record["benchmark_unit_count"] == 6
    assert (
        _bucket(record["source_class_distribution"], "case.dev-only")["candidate_count"]
        == 1
    )
    assert (
        _bucket(record["source_class_distribution"], "case.dev-plus-fallback")[
            "candidate_count"
        ]
        == 1
    )
    assert (
        _bucket(record["source_class_distribution"], "excluded")["candidate_count"] == 1
    )
    assert set(tables) >= {
        "district",
        "circuit",
        "nos_code",
        "nos_macro_category",
        "represented_party_status",
        "government_party_status",
        "mdl_flag",
        "public_company_flag",
        "claim_count",
        "defendant_count",
        "defendant_group_count",
        "prediction_unit_count",
        "document_completeness",
        "motion_available",
        "opposition_available",
        "reply_available",
        "fallback_used",
        "fallback_source",
        "fallback_reason",
        "press_publicity_sensitivity_flag",
        "press_publicity_tags",
        "related_family_id",
        "mdl_family_id",
    }
    assert _bucket(tables["document_completeness"], "complete")["unit_count"] == 3
    assert _bucket(tables["fallback_used"], "true")["candidate_count"] == 1
    assert _bucket(tables["fallback_source"], "case.dev-only")["candidate_count"] == 1
    assert _bucket(tables["fallback_source"], "recap")["candidate_count"] == 1
    assert (
        _bucket(tables["fallback_reason"], "missing_reply_document")["candidate_count"]
        == 1
    )
    assert (
        _bucket(tables["press_publicity_sensitivity_flag"], "true")["candidate_count"]
        == 1
    )
    assert (
        _bucket(tables["press_publicity_tags"], "high_news_volume")["unit_count"] == 3
    )
    assert (
        _bucket(tables["press_publicity_tags"], "major_public_company_party")[
            "candidate_count"
        ]
        == 1
    )
    assert _bucket(tables["press_publicity_tags"], "none")["candidate_count"] == 1
    assert record["candidates"][0]["source_class"] == CandidateSourceClass.CASE_DEV_ONLY
    assert record["candidates"][0]["nos_macro_category"] == "contract"
    assert record["candidates"][0]["motion_available"] is True
    assert record["candidates"][0]["fallback_source"] == "case.dev-only"
    assert record["candidates"][0]["fallback_reason"] is None
    assert record["candidates"][0]["press_publicity_sensitivity_flag"] is False
    assert (
        record["candidates"][1]["source_class"]
        == CandidateSourceClass.CASE_DEV_PLUS_FALLBACK
    )
    assert record["candidates"][1]["press_publicity_sensitivity_flag"] is True
    assert record["candidates"][1]["press_publicity_tags"] == [
        "high_news_volume",
        "major_public_company_party",
    ]
    assert record["candidates"][2]["source_class"] == CandidateSourceClass.EXCLUDED
    json.dumps(record)


def test_dominance_rule_triggers_prespecified_sensitivity_buckets() -> None:
    diagnostics = build_case_mix_diagnostics(
        (
            _candidate(
                "dominant",
                district="S.D.N.Y.",
                nos_macro_category="civil_rights",
                related_family_id="related-1",
                mdl_family_id="mdl-1",
                units=7,
            ),
            _candidate(
                "same-pattern",
                district="D. Del.",
                nos_macro_category="civil_rights",
                related_family_id="related-1",
                mdl_family_id="mdl-1",
                units=2,
            ),
            _candidate(
                "minority",
                district="N.D. Cal.",
                nos_macro_category="contract",
                units=1,
            ),
        ),
        dominance_threshold=0.60,
    )

    findings = diagnostics.to_record()["dominance_findings"]
    dimensions = {finding["dimension"] for finding in findings}

    assert dimensions == {
        DominanceDimension.DISTRICT.value,
        DominanceDimension.NOS_MACRO_CATEGORY.value,
        DominanceDimension.RELATED_CASE_FAMILY.value,
        DominanceDimension.MDL_FAMILY.value,
    }
    district_finding = next(
        finding for finding in findings if finding["dimension"] == "district"
    )
    assert district_finding["bucket"] == "S.D.N.Y."
    assert district_finding["unit_share"] == pytest.approx(0.7)
    assert district_finding["recommended_sensitivity"] == "exclude_or_cap_bucket"


def test_exclusion_and_document_completeness_distributions_are_reported() -> None:
    diagnostics = build_case_mix_diagnostics(
        (
            _candidate(
                "complete",
                document_completeness=DocumentCompleteness.COMPLETE,
                units=2,
            ),
            _candidate(
                "missing-reply",
                document_completeness=DocumentCompleteness.MISSING_REPLY,
                reply_available=False,
                units=1,
            ),
            _candidate(
                "excluded-leakage",
                included=False,
                exclusion_reason="outcome_leakage",
                units=0,
            ),
            _candidate(
                "excluded-ambiguous",
                included=False,
                exclusion_reason="ambiguous_order",
                units=0,
            ),
        ),
        dominance_threshold=0.95,
    )

    record = diagnostics.to_record()

    assert (
        _bucket(record["tables"]["document_completeness"], "complete")[
            "candidate_count"
        ]
        == 1
    )
    assert _bucket(record["tables"]["reply_available"], "false")["candidate_count"] == 1
    assert (
        _bucket(record["exclusion_reason_distribution"], "outcome_leakage")[
            "candidate_count"
        ]
        == 1
    )
    assert (
        _bucket(record["exclusion_reason_distribution"], "ambiguous_order")[
            "candidate_count"
        ]
        == 1
    )


def test_unassigned_related_and_mdl_families_do_not_trigger_dominance() -> None:
    diagnostics = build_case_mix_diagnostics(
        (
            _candidate(
                "unassigned-large",
                district="S.D.N.Y.",
                nos_macro_category="contract",
                units=9,
            ),
            _candidate(
                "assigned-small",
                district="D. Del.",
                nos_macro_category="securities",
                related_family_id="related-small",
                mdl_family_id="mdl-small",
                units=1,
            ),
        ),
        dominance_threshold=0.95,
    )

    assert diagnostics.dominance_findings == ()
    related_table = diagnostics.table_named("related_family_id").to_records()
    assert _bucket(related_table, "none")["unit_count"] == 9
    assert _bucket(related_table, "related-small")["unit_share"] == pytest.approx(0.1)


def test_validation_rejects_invalid_counts_and_threshold() -> None:
    with pytest.raises(ValueError, match="claim_count must be positive"):
        _candidate("bad-claim", claim_count=0)

    with pytest.raises(ValueError, match="prediction_unit_count must be positive"):
        _candidate("bad-units", units=0)

    with pytest.raises(ValueError, match="excluded candidates require"):
        _candidate("bad-exclusion", included=False, units=0)

    with pytest.raises(ValueError, match="dominance_threshold"):
        build_case_mix_diagnostics((), dominance_threshold=1.0)


def test_fallback_validation_requires_source_and_reason() -> None:
    with pytest.raises(ValueError, match="fallback_source must identify"):
        _candidate(
            "missing-source",
            fallback_used=True,
            fallback_source=FallbackSource.CASE_DEV_ONLY,
            fallback_reason="missing_motion_document",
        )

    with pytest.raises(ValueError, match="fallback_reason"):
        _candidate(
            "missing-reason",
            fallback_used=True,
            fallback_source=FallbackSource.COURTLISTENER_RECAP,
        )

    with pytest.raises(ValueError, match=r"case\.dev-only candidates"):
        _candidate(
            "source-without-fallback",
            fallback_source=FallbackSource.PACER,
        )

    with pytest.raises(ValueError, match="fallback_reason"):
        _candidate(
            "reason-without-fallback",
            fallback_reason="missing_motion_document",
        )


def test_press_publicity_tags_must_be_unique() -> None:
    with pytest.raises(ValueError, match="press_publicity_tags"):
        _candidate(
            "duplicate-publicity",
            press_publicity_tags=(
                PressPublicityTag.WIKIPEDIA_PAGE,
                PressPublicityTag.WIKIPEDIA_PAGE,
            ),
        )


def _bucket(records: list[dict[str, object]], bucket: str) -> dict[str, object]:
    return next(record for record in records if record["bucket"] == bucket)


def _candidate(
    candidate_id: str,
    *,
    district: str = "S.D.N.Y.",
    circuit: str = "2d",
    nos_code: str = "190",
    nos_macro_category: str = "contract",
    represented_party_status: str = "mixed_representation",
    government_party_status: str = "no_government_party",
    mdl_flag: bool = False,
    public_company_flag: bool = False,
    claim_count: int = 2,
    defendant_count: int = 2,
    defendant_group_count: int = 1,
    units: int = 2,
    document_completeness: DocumentCompleteness = DocumentCompleteness.COMPLETE,
    motion_available: bool = True,
    opposition_available: bool = True,
    reply_available: bool = True,
    fallback_used: bool = False,
    fallback_source: FallbackSource = FallbackSource.CASE_DEV_ONLY,
    fallback_reason: str | None = None,
    press_publicity_tags: tuple[PressPublicityTag, ...] = (),
    included: bool = True,
    related_family_id: str | None = None,
    mdl_family_id: str | None = None,
    exclusion_reason: str | None = None,
) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id=candidate_id,
        case_id=f"case-{candidate_id}",
        district=district,
        circuit=circuit,
        nos_code=nos_code,
        nos_macro_category=nos_macro_category,
        represented_party_status=represented_party_status,
        government_party_status=government_party_status,
        mdl_flag=mdl_flag,
        public_company_flag=public_company_flag,
        claim_count=claim_count,
        defendant_count=defendant_count,
        defendant_group_count=defendant_group_count,
        prediction_unit_count=units,
        document_completeness=document_completeness,
        motion_available=motion_available,
        opposition_available=opposition_available,
        reply_available=reply_available,
        fallback_used=fallback_used,
        fallback_source=fallback_source,
        fallback_reason=fallback_reason,
        press_publicity_tags=press_publicity_tags,
        included_in_benchmark=included,
        related_family_id=related_family_id,
        mdl_family_id=mdl_family_id,
        exclusion_reason=exclusion_reason,
    )
