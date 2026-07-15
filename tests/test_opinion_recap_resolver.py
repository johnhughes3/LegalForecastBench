"""Strict, resumable opinion-lead to RECAP docket resolution."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.opinion_recap_resolver import (
    OPINION_RECAP_RESOLUTION_SCHEMA,
    OpinionRecapResolutionError,
    read_resolution_outcomes,
    resolve_opinion_recap_batch,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    read_saturated_direct_search_leads,
    seed_direct_search_leads,
)

_BULLOCK_QUERY = '"Bullock v. PHH Mortgage Services"'


def _source_store(tmp_path: Path, *leads: dict[str, object]) -> Path:
    path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch(
            "opinion-source",
            {
                "schema_version": "legalforecast.courtlistener_opinion_discovery.v1",
                "provider": "courtlistener",
                "search_type": "o",
                "query_terms": ['"motion to dismiss"'],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-15",
            },
        )
        store.ensure_terms("opinion-source", ('"motion to dismiss"',))
        store.commit_search_page(
            "opinion-source",
            '"motion to dismiss"',
            None,
            leads,
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _lead(
    *,
    opinion_docket_id: str = "73614335",
    cluster_id: str = "10927691",
    court_id: str = "dcd",
    docket_number: str = "1:25-cv-03820",
    case_name: str = "Bullock v. PHH Mortgage Services",
) -> dict[str, object]:
    return {
        "provider_hit_id": cluster_id,
        "candidate_id": opinion_docket_id,
        "payload": {
            "docket_id": opinion_docket_id,
            "court_id": court_id,
            "docket_number": docket_number,
            "case_name": case_name,
            "provider": "courtlistener",
            "opinion_discovery_evidence": {
                "schema_version": "legalforecast.courtlistener_opinion_hit.v1",
                "cluster_id": cluster_id,
                "absolute_url": f"/opinion/{cluster_id}/bullock-v-phh/",
                "date_filed": "2026-07-14",
                "status": "Unpublished",
                "sub_opinions": [
                    {
                        "opinion_id": "11395231",
                        "absolute_url": "/api/rest/v4/opinions/11395231/",
                        "download_url": "https://ecf.dcd.uscourts.gov/doc1/0451",
                        "local_path": "pdf/2026/07/14/bullock_v_phh.pdf",
                    }
                ],
            },
        },
    }


def _case_dev_response(*dockets: dict[str, object]) -> RecordedCaseDevResponse:
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "search",
            "query": _BULLOCK_QUERY,
            "limit": 100,
        },
        status_code=200,
        payload={"dockets": list(dockets)},
    )


def _case_dev(*responses: RecordedCaseDevResponse) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key="fixture"),
        transport=CaseDevFixtureTransport(responses),
        max_retries=0,
    )


def _courtlistener(*responses: RecordedCourtListenerResponse) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(api_token="fixture"),
        transport=CourtListenerFixtureTransport(responses),
        max_retries=0,
    )


def _recap_docket(
    docket_id: str = "71878956",
    *,
    court_id: str = "dcd",
    docket_number: str = "1:25-cv-03820",
    case_name: str = "Bullock v. PHH Mortgage Services, LLC",
) -> dict[str, object]:
    return {
        "id": docket_id,
        "courtId": court_id,
        "docketNumber": docket_number,
        "caseName": case_name,
        "url": f"https://www.courtlistener.com/docket/{docket_id}/example/",
    }


def _courtlistener_recap_docket(**overrides: object) -> dict[str, object]:
    record = _recap_docket()
    record["docket_id"] = record.pop("id")
    record.update(overrides)
    return record


def test_case_dev_exact_identity_resolves_without_courtlistener_quota(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    case_dev = _case_dev(
        _case_dev_response(
            _recap_docket("70000000", docket_number="1:24-cv-00001"),
            _recap_docket(),
        )
    )
    courtlistener = _courtlistener()

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    assert summary.excluded == 0
    assert case_dev.request_count == 1
    assert courtlistener.request_count == 0
    resolved = read_saturated_direct_search_leads(
        source, source_batch_id="resolved-opinion-source"
    )
    assert [lead.docket_id for lead in resolved.leads] == ["71878956"]
    evidence = resolved.leads[0].opinion_resolution_evidence
    assert evidence is not None
    assert evidence["schema_version"] == OPINION_RECAP_RESOLUTION_SCHEMA
    assert evidence["source_opinion"]["candidate_id"] == "73614335"
    assert evidence["source_opinion"]["cluster_id"] == "10927691"
    assert evidence["source_opinion"]["sub_opinions"][0]["opinion_id"] == ("11395231")
    assert evidence["resolved_recap"]["docket_id"] == "71878956"
    assert evidence["resolver"]["provider"] == "case.dev"
    assert evidence["resolver"]["match_method"] == ("exact_court_normalized_docket")
    assert evidence["ambiguity_proof"]["provider_result_count"] == 2
    assert len(evidence["commitments"]["provider_response_sha256"]) == 64

    with CycleAcquisitionStore(source) as store:
        seeded = seed_direct_search_leads(
            store,
            batch_id="resolved-rest-screen",
            source=resolved,
        )
        assert seeded.leads_seeded == 1
        payload = store.candidate_discovery_hits("resolved-rest-screen")[0].payload
        assert payload["opinion_resolution_evidence"] == evidence
        assert payload["candidate_id"] == "courtlistener-docket-71878956"


def test_provider_query_quotes_valid_caption_syntax_as_one_exact_phrase(
    tmp_path: Path,
) -> None:
    case_name = "In re: David A. Stewart and Terry P. Stewart"
    source = _source_store(tmp_path, _lead(case_name=case_name))
    response = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "search",
            "query": f'"{case_name}"',
            "limit": 100,
        },
        status_code=200,
        payload={"dockets": [_recap_docket(case_name=case_name)], "found": 1},
    )

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=_case_dev(response),
        courtlistener_client=_courtlistener(),
    )

    assert summary.resolved == 1
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    resolver = outcome["evidence"]["opinion_resolution_evidence"]["resolver"]
    assert resolver["query"] == f'"{case_name}"'
    assert resolver["provider"] == "case.dev"


def test_case_dev_found_total_proves_cursorless_page_is_incomplete(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    case_dev_response = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": _BULLOCK_QUERY, "limit": 100},
        status_code=200,
        payload={"dockets": [_recap_docket()], "found": 2},
    )
    params: dict[str, Any] = {
        "type": "r",
        "q": _BULLOCK_QUERY,
        "order_by": "score desc",
        "page_size": 20,
    }
    courtlistener = _courtlistener(
        RecordedCourtListenerResponse(
            method="GET",
            path="/search/",
            params=params,
            status_code=200,
            payload={"results": [_courtlistener_recap_docket()], "next": None},
        )
    )

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=_case_dev(case_dev_response),
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    assert courtlistener.request_count == 1
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    assert (
        outcome["evidence"]["opinion_resolution_evidence"]["resolver"]["provider"]
        == "courtlistener_rest"
    )


@pytest.mark.parametrize("found", (-1, True, "1", 0))
def test_case_dev_malformed_or_contradictory_found_total_fails_closed(
    tmp_path: Path,
    found: object,
) -> None:
    source = _source_store(tmp_path, _lead())
    response = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": _BULLOCK_QUERY, "limit": 100},
        status_code=200,
        payload={"dockets": [_recap_docket()], "found": found},
    )

    with pytest.raises(OpinionRecapResolutionError, match="found total"):
        resolve_opinion_recap_batch(
            source_store_path=source,
            source_batch_id="opinion-source",
            journal_path=tmp_path / "resolver.sqlite3",
            output_store_path=source,
            output_batch_id="resolved-opinion-source",
            case_dev_client=_case_dev(response),
            courtlistener_client=_courtlistener(),
        )


def test_case_dev_matching_found_total_proves_full_cursorless_page_complete(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    dockets = [
        _recap_docket(
            str(70000000 + index),
            docket_number=f"1:24-cv-{index:05d}",
            case_name=f"Unrelated Case {index}",
        )
        for index in range(99)
    ]
    dockets.append(_recap_docket())
    response = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": _BULLOCK_QUERY, "limit": 100},
        status_code=200,
        payload={"dockets": dockets, "found": 100},
    )
    courtlistener = _courtlistener()

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=_case_dev(response),
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    assert courtlistener.request_count == 0
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    assert (
        outcome["evidence"]["opinion_resolution_evidence"]["resolver"]["provider"]
        == "case.dev"
    )


def test_case_dev_duplicate_ids_across_pages_fail_closed(tmp_path: Path) -> None:
    source = _source_store(tmp_path, _lead())
    first = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": _BULLOCK_QUERY, "limit": 100},
        status_code=200,
        payload={
            "dockets": [_recap_docket()],
            "found": 2,
            "next_offset": 1,
        },
    )
    second = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "search",
            "query": _BULLOCK_QUERY,
            "offset": 1,
            "limit": 100,
        },
        status_code=200,
        payload={"dockets": [_recap_docket()], "found": 2},
    )

    with pytest.raises(OpinionRecapResolutionError, match="duplicate docket IDs"):
        resolve_opinion_recap_batch(
            source_store_path=source,
            source_batch_id="opinion-source",
            journal_path=tmp_path / "resolver.sqlite3",
            output_store_path=source,
            output_batch_id="resolved-opinion-source",
            case_dev_client=_case_dev(first, second),
            courtlistener_client=_courtlistener(),
        )


def test_case_dev_cursor_after_reported_total_fails_closed(tmp_path: Path) -> None:
    source = _source_store(tmp_path, _lead())
    response = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "search", "query": _BULLOCK_QUERY, "limit": 100},
        status_code=200,
        payload={
            "dockets": [_recap_docket()],
            "found": 1,
            "next_offset": 1,
        },
    )

    with pytest.raises(OpinionRecapResolutionError, match="continuation after"):
        resolve_opinion_recap_batch(
            source_store_path=source,
            source_batch_id="opinion-source",
            journal_path=tmp_path / "resolver.sqlite3",
            output_store_path=source,
            output_batch_id="resolved-opinion-source",
            case_dev_client=_case_dev(response),
            courtlistener_client=_courtlistener(),
        )


@pytest.mark.parametrize("control", ("\x7f", "\x9f", "\u200b"))
def test_provider_query_excludes_unicode_control_and_format_characters(
    tmp_path: Path,
    control: str,
) -> None:
    source = _source_store(
        tmp_path,
        _lead(case_name=f"Alpha{control}Beta v. Gamma"),
    )
    case_dev = _case_dev()
    courtlistener = _courtlistener()

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=courtlistener,
    )

    assert summary.excluded == 1
    assert case_dev.request_count == 0
    assert courtlistener.request_count == 0
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    assert outcome["reason_code"] == "source_query_unrepresentable"
    assert outcome["evidence"]["query_error"] == "unicode_category_c_character"


def test_unrepresentable_caption_is_excluded_and_next_lead_resolves(
    tmp_path: Path,
) -> None:
    source = _source_store(
        tmp_path,
        _lead(case_name="A" * 501),
        _lead(opinion_docket_id="73614336", cluster_id="10927692"),
    )
    case_dev = _case_dev(_case_dev_response(_recap_docket()))
    courtlistener = _courtlistener()

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=courtlistener,
    )

    assert summary.excluded == 1
    assert summary.resolved == 1
    assert case_dev.request_count == 1
    assert courtlistener.request_count == 0
    outcomes = read_resolution_outcomes(tmp_path / "resolver.sqlite3")
    assert [outcome["reason_code"] for outcome in outcomes] == [
        "source_query_unrepresentable",
        "strict_recap_identity_resolved",
    ]
    assert outcomes[0]["evidence"] == {
        "case_name_length": 501,
        "court_id": "dcd",
        "docket_number": "1:25-cv-03820",
        "query_error": "query_length_out_of_range",
    }


def test_full_cursorless_case_dev_page_falls_back_to_proven_courtlistener_search(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    case_dev_dockets = [
        _recap_docket(
            str(70000000 + index),
            docket_number=f"1:24-cv-{index:05d}",
            case_name=f"Unrelated Case {index}",
        )
        for index in range(99)
    ]
    case_dev_dockets.append(_recap_docket())
    case_dev = _case_dev(_case_dev_response(*case_dev_dockets))
    params: dict[str, Any] = {
        "type": "r",
        "q": _BULLOCK_QUERY,
        "order_by": "score desc",
        "page_size": 20,
    }
    courtlistener = _courtlistener(
        RecordedCourtListenerResponse(
            method="GET",
            path="/search/",
            params=params,
            status_code=200,
            payload={"results": [_courtlistener_recap_docket()], "next": None},
        )
    )

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    assert case_dev.request_count == 1
    assert courtlistener.request_count == 1
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    resolution = outcome["evidence"]["opinion_resolution_evidence"]
    assert resolution["resolver"]["provider"] == "courtlistener_rest"


def test_exact_identity_ambiguity_is_ledgered_and_fails_closed(tmp_path: Path) -> None:
    source = _source_store(tmp_path, _lead())
    case_dev = _case_dev(_case_dev_response(_recap_docket("1"), _recap_docket("2")))

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=_courtlistener(),
    )

    assert summary.excluded == 1
    assert summary.resolved == 0
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    assert outcome["state"] == "excluded"
    assert outcome["reason_code"] == "exact_identity_ambiguous"
    assert outcome["evidence"]["ambiguity_proof"]["matching_docket_ids"] == [
        "1",
        "2",
    ]


def test_courtlistener_fallback_rejects_generic_id_without_recap_docket_id(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    params: dict[str, Any] = {
        "type": "r",
        "q": _BULLOCK_QUERY,
        "order_by": "score desc",
        "page_size": 20,
    }
    courtlistener = _courtlistener(
        RecordedCourtListenerResponse(
            method="GET",
            path="/search/",
            params=params,
            status_code=200,
            payload={"results": [_recap_docket()], "next": None},
        )
    )

    with pytest.raises(
        OpinionRecapResolutionError,
        match="positive numeric RECAP docket ID",
    ):
        resolve_opinion_recap_batch(
            source_store_path=source,
            source_batch_id="opinion-source",
            journal_path=tmp_path / "resolver.sqlite3",
            output_store_path=source,
            output_batch_id="resolved-opinion-source",
            case_dev_client=_case_dev(_case_dev_response()),
            courtlistener_client=courtlistener,
        )


def test_courtlistener_fallback_omits_available_only_and_uses_similarity(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead(docket_number="UNKNOWN"))
    params: dict[str, Any] = {
        "type": "r",
        "q": _BULLOCK_QUERY,
        "order_by": "score desc",
        "page_size": 20,
    }
    response = RecordedCourtListenerResponse(
        method="GET",
        path="/search/",
        params=params,
        status_code=200,
        payload={"results": [_courtlistener_recap_docket()], "next": None},
    )
    case_dev = _case_dev(_case_dev_response())
    courtlistener = _courtlistener(response)

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    resolver = outcome["evidence"]["opinion_resolution_evidence"]["resolver"]
    assert resolver["provider"] == "courtlistener_rest"
    assert resolver["match_method"] == ("unique_court_case_name_similarity_fallback")
    assert resolver["case_name_similarity"] >= 0.9
    assert "available_only" not in params


def test_case_dev_server_error_is_journaled_then_falls_back_to_courtlistener(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    failed = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "search",
            "query": _BULLOCK_QUERY,
            "limit": 100,
        },
        status_code=502,
        payload={"message": "Docket provider is unavailable"},
    )
    params: dict[str, Any] = {
        "type": "r",
        "q": _BULLOCK_QUERY,
        "order_by": "score desc",
        "page_size": 20,
    }
    courtlistener = _courtlistener(
        RecordedCourtListenerResponse(
            method="GET",
            path="/search/",
            params=params,
            status_code=200,
            payload={"results": [_courtlistener_recap_docket()], "next": None},
        )
    )

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=_case_dev(failed),
        courtlistener_client=courtlistener,
    )

    assert summary.resolved == 1
    connection = sqlite3.connect(tmp_path / "resolver.sqlite3")
    try:
        assert connection.execute(
            "SELECT provider, state, error_type FROM request_attempts "
            "ORDER BY attempt_id"
        ).fetchall() == [
            ("case.dev", "failed", "CaseDevServerError"),
            ("courtlistener_rest", "succeeded", None),
        ]
    finally:
        connection.close()
    outcome = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]
    assert (
        outcome["evidence"]["opinion_resolution_evidence"]["resolver"]["provider"]
        == "courtlistener_rest"
    )


def test_prior_candidate_is_deferred_after_free_mapping_and_not_emitted(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=_case_dev(_case_dev_response(_recap_docket())),
        courtlistener_client=_courtlistener(),
        prior_candidate_ids=frozenset({"courtlistener-docket-71878956"}),
        prior_snapshot_commitment_sha256="a" * 64,
    )

    assert summary.deferred == 1
    assert summary.resolved == 0
    assert (
        read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]["reason_code"]
        == "seen_in_prior_screening_snapshot"
    )
    output = read_saturated_direct_search_leads(
        source, source_batch_id="resolved-opinion-source"
    )
    assert output.leads == ()


def test_multiple_opinion_leads_for_one_recap_docket_preserve_all_resolution_evidence(
    tmp_path: Path,
) -> None:
    second = _lead(opinion_docket_id="73614336", cluster_id="10927692")
    second_payload = second["payload"]
    assert isinstance(second_payload, dict)
    second_payload["case_name"] = "Bullock v. PHH Mortgage Services"
    source = _source_store(tmp_path, _lead(), second)
    case_dev = _case_dev(
        _case_dev_response(_recap_docket()),
        _case_dev_response(_recap_docket()),
    )

    summary = resolve_opinion_recap_batch(
        source_store_path=source,
        source_batch_id="opinion-source",
        journal_path=tmp_path / "resolver.sqlite3",
        output_store_path=source,
        output_batch_id="resolved-opinion-source",
        case_dev_client=case_dev,
        courtlistener_client=_courtlistener(),
    )

    assert summary.resolved == 2
    resolved = read_saturated_direct_search_leads(
        source, source_batch_id="resolved-opinion-source"
    )
    assert len(resolved.leads) == 1
    evidence = resolved.leads[0].opinion_resolution_evidence
    assert evidence is not None
    assert evidence["source_opinion"]["cluster_id"] == "10927691"
    assert [
        item["source_opinion"]["cluster_id"]
        for item in evidence["additional_resolutions"]
    ] == ["10927692"]


def test_source_must_be_opinion_authoritative_and_saturated(tmp_path: Path) -> None:
    source = _source_store(tmp_path, _lead())
    with CycleAcquisitionStore(source) as store:
        store._connection.execute("UPDATE term_progress SET terminal_status = NULL")
        store._connection.commit()

    with pytest.raises(OpinionRecapResolutionError, match="fully exhausted"):
        resolve_opinion_recap_batch(
            source_store_path=source,
            source_batch_id="opinion-source",
            journal_path=tmp_path / "resolver.sqlite3",
            output_store_path=source,
            output_batch_id="resolved-opinion-source",
            case_dev_client=_case_dev(),
            courtlistener_client=_courtlistener(),
        )


def test_response_commitment_is_canonical_and_outcome_resume_is_zero_request(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    response = _case_dev_response(_recap_docket())
    first_case_dev = _case_dev(response)
    kwargs = {
        "source_store_path": source,
        "source_batch_id": "opinion-source",
        "journal_path": tmp_path / "resolver.sqlite3",
        "output_store_path": source,
        "output_batch_id": "resolved-opinion-source",
    }
    first = resolve_opinion_recap_batch(
        **kwargs,
        case_dev_client=first_case_dev,
        courtlistener_client=_courtlistener(),
    )
    second_case_dev = _case_dev()
    second = resolve_opinion_recap_batch(
        **kwargs,
        case_dev_client=second_case_dev,
        courtlistener_client=_courtlistener(),
    )

    assert second.outcome_set_sha256 == first.outcome_set_sha256
    assert second.resolver_policy_sha256 == first.resolver_policy_sha256
    assert second.resolved == first.resolved == 1
    assert second_case_dev.request_count == 0
    assert second.case_dev_requests == 0
    evidence = read_resolution_outcomes(tmp_path / "resolver.sqlite3")[0]["evidence"]
    expected = hashlib.sha256(
        json.dumps(
            response.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()
    assert (
        evidence["opinion_resolution_evidence"]["commitments"][
            "provider_response_sha256"
        ]
        == expected
    )


def test_nonfallback_auth_failure_is_durable_and_resume_retries_unresolved_lead(
    tmp_path: Path,
) -> None:
    source = _source_store(tmp_path, _lead())
    failed = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "search",
            "query": _BULLOCK_QUERY,
            "limit": 100,
        },
        status_code=401,
        payload={"error": "invalid API key"},
    )
    kwargs = {
        "source_store_path": source,
        "source_batch_id": "opinion-source",
        "journal_path": tmp_path / "resolver.sqlite3",
        "output_store_path": source,
        "output_batch_id": "resolved-opinion-source",
        "courtlistener_client": _courtlistener(),
    }

    with pytest.raises(CaseDevAuthError, match="invalid API key"):
        resolve_opinion_recap_batch(
            **kwargs,
            case_dev_client=_case_dev(failed),
        )
    assert read_resolution_outcomes(tmp_path / "resolver.sqlite3") == ()
    connection = sqlite3.connect(tmp_path / "resolver.sqlite3")
    try:
        assert connection.execute(
            "SELECT state, error_type FROM request_attempts"
        ).fetchone() == ("failed", "CaseDevAuthError")
    finally:
        connection.close()

    resumed = resolve_opinion_recap_batch(
        **kwargs,
        case_dev_client=_case_dev(_case_dev_response(_recap_docket())),
    )
    assert resumed.resolved == 1
    assert len(read_resolution_outcomes(tmp_path / "resolver.sqlite3")) == 1


def test_cli_resolves_fixture_and_reports_nonpaid_source_bound_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _source_store(tmp_path, _lead())
    case_dev_fixture = tmp_path / "case-dev.jsonl"
    courtlistener_fixture = tmp_path / "courtlistener.jsonl"
    response = _case_dev_response(_recap_docket())
    case_dev_fixture.write_text(
        json.dumps(
            {
                "method": response.method,
                "path": response.path,
                "params": response.params,
                "status_code": response.status_code,
                "payload": response.payload,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    courtlistener_fixture.write_text("", encoding="utf-8")
    summary_path = tmp_path / "summary.json"

    assert (
        main(
            [
                "batch-002",
                "resolve-opinion-recap-dockets",
                "--source-store",
                str(source),
                "--source-batch-id",
                "opinion-source",
                "--resolver-journal",
                str(tmp_path / "resolver.sqlite3"),
                "--cycle-store",
                str(source),
                "--batch-id",
                "resolved-opinion-source",
                "--case-dev-fixture",
                str(case_dev_fixture),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--summary-output",
                str(summary_path),
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["resolved"] == 1
    assert output["complete"] is True
    assert output["saturated"] is True
    assert output["paid_activity_requested"] is False
    assert output["paid_activity_executed"] is False
    assert json.loads(summary_path.read_text(encoding="utf-8")) == output


def test_cli_help_freezes_no_paid_and_unrestricted_fallback_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["batch-002", "resolve-opinion-recap-dockets", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert "CourtListener queries use type=r and omit available_only" in help_text
    assert "No PACER, RECAP Fetch, live Case.dev fetch, or purchase" in help_text
