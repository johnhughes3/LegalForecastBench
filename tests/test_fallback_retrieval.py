from __future__ import annotations

from datetime import UTC, datetime

from legalforecast.ingestion import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    DocumentRole,
    FallbackRetrievalDiagnostics,
    RecapClient,
    RecapConfig,
    RecapFixtureTransport,
    RecordedCourtListenerResponse,
    RecordedRecapResponse,
)
from legalforecast.selection.case_mix_diagnostics import (
    CaseMixCandidate,
    DocumentCompleteness,
    FallbackSource,
    build_case_mix_diagnostics,
)
from legalforecast.selection.fallback_rules import FallbackGap


def test_courtlistener_recap_fallback_feeds_case_mix_diagnostics() -> None:
    courtlistener = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                RecordedCourtListenerResponse(
                    method="GET",
                    path="/docket-entries/",
                    params={"docket": "123"},
                    status_code=200,
                    payload={
                        "results": [
                            {
                                "id": 7001,
                                "docket": 123,
                                "entry_number": 12,
                                "description": "Motion to dismiss complaint",
                                "recap_documents": [{"id": 9001}],
                            }
                        ]
                    },
                ),
            )
        ),
    )
    recap = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                RecordedRecapResponse(
                    method="GET",
                    path="/recap-documents/9001/",
                    params={},
                    status_code=200,
                    payload={
                        "id": 9001,
                        "docket": 123,
                        "docket_entry": 7001,
                        "plain_text": "Motion to dismiss complaint",
                    },
                ),
            )
        ),
    )

    entries = courtlistener.list_docket_entries("123").items
    document = recap.get_document(entries[0].recap_document_ids[0])
    provenance = document.to_provenance(
        source_case_id="123",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        docket_entry_number=12,
        document_role=DocumentRole.MTD_MEMORANDUM,
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )
    fallback = FallbackRetrievalDiagnostics(
        candidate_id="cand-1",
        case_id="case-1",
        gap=FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE,
        source=FallbackSource.COURTLISTENER_RECAP,
        docket_entry_count=len(entries),
        documents=(provenance,),
        request_count=courtlistener.request_count + recap.request_count,
    )
    candidate = _candidate("cand-1", **fallback.to_case_mix_fields())

    diagnostics = build_case_mix_diagnostics((candidate,))
    record = diagnostics.to_record()

    assert fallback.decision.fallback_used is True
    assert fallback.to_record()["request_count"] == 2
    assert candidate.source_class == "case.dev-plus-fallback"
    assert record["source_class_distribution"][0]["bucket"] == (
        "case.dev-plus-fallback"
    )
    assert record["tables"]["fallback_source"][0]["bucket"] == "courtlistener_recap"


def test_failed_fallback_retrieval_maps_to_excluded_case_mix_fields() -> None:
    fallback = FallbackRetrievalDiagnostics(
        candidate_id="cand-1",
        case_id="case-1",
        gap=FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE,
        source=FallbackSource.COURTLISTENER_RECAP,
        missing_reasons=("courtlistener_docket_unavailable",),
        request_count=1,
    )
    candidate = _candidate("cand-1", units=0, **fallback.to_case_mix_fields())

    assert fallback.decision.included_in_benchmark is False
    assert fallback.decision.exclusion_reason == (
        "fallback_unavailable_docket_entry_listing"
    )
    assert candidate.source_class == "excluded"


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
