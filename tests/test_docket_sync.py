from __future__ import annotations

from datetime import UTC, datetime

from legalforecast.ingestion import CaseDevClient, CaseDevFixtureTransport, DocumentRole
from legalforecast.ingestion.case_dev_client import RecordedCaseDevResponse
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    classify_document_role,
)


def _client() -> CaseDevClient:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "lookup", "docketId": "case-1"},
                status_code=200,
                payload={
                    "docket": {
                        "id": "case-1",
                        "caseName": "Example v. Issuer",
                        "court": "S.D.N.Y.",
                        "docketNumber": "1:26-cv-00001",
                    },
                },
            ),
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={
                    "type": "lookup",
                    "docketId": "case-1",
                    "includeEntries": True,
                },
                status_code=200,
                payload={
                    "docket": {
                        "id": "case-1",
                        "entries": [
                            {
                                "entryNumber": 1,
                                "description": "Complaint",
                                "documents": [{"id": "doc-1"}],
                            },
                            {
                                "entryNumber": 34,
                                "description": (
                                    "Memorandum in support of motion to dismiss"
                                ),
                                "documents": [{"id": "doc-34"}],
                            },
                            {
                                "entryNumber": 41,
                                "description": "Opposition to motion to dismiss",
                            },
                            {
                                "entryNumber": 99,
                                "description": (
                                    "Opinion and order granting motion to dismiss"
                                ),
                                "documents": [{"id": "doc-99"}],
                            },
                        ],
                    }
                },
            ),
            RecordedCaseDevResponse(
                method="GET",
                path="/v1/documents/doc-1",
                params={},
                status_code=200,
                payload={
                    "document_id": "doc-1",
                    "case_id": "case-1",
                    "document_type": "complaint",
                    "text": "Complaint text",
                },
            ),
            RecordedCaseDevResponse(
                method="GET",
                path="/v1/documents/doc-34",
                params={},
                status_code=200,
                payload={
                    "document_id": "doc-34",
                    "case_id": "case-1",
                    "document_type": "motion",
                    "text": "Motion to dismiss memorandum",
                },
            ),
            RecordedCaseDevResponse(
                method="GET",
                path="/v1/documents/doc-99",
                params={},
                status_code=200,
                payload={
                    "document_id": "doc-99",
                    "case_id": "case-1",
                    "document_type": "order",
                    "text": "The motion is granted.",
                },
            ),
        ]
    )
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=transport,
    )


def test_docket_retrieval_normalizes_entries_filings_and_missing_docs() -> None:
    pipeline = DocketRetrievalPipeline(_client())

    result = pipeline.retrieve_candidate(
        candidate_id="cand-1",
        case_id="case-1",
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )

    assert result.court == "S.D.N.Y."
    assert result.docket_number == "1:26-cv-00001"
    assert [entry.document_role for entry in result.docket_entries] == [
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert [filing.source_document_id for filing in result.filings] == [
        "doc-1",
        "doc-34",
        "doc-99",
    ]
    assert result.missing_filings[0].docket_entry_id.startswith("entry-41-")
    assert result.missing_filings[0].reason == "no_source_document_id"


def test_retrieval_tracks_outcome_order_without_mounting_it() -> None:
    pipeline = DocketRetrievalPipeline(_client())

    result = pipeline.retrieve_candidate(candidate_id="cand-1", case_id="case-1")
    decision_provenance = result.filings[-1].provenance

    assert decision_provenance.document_role is DocumentRole.DECISION
    assert decision_provenance.contains_target_outcome is True
    assert decision_provenance.is_mounted_for_model is False
    assert decision_provenance.is_predecision_material is False


def test_retrieval_record_preserves_source_ids_and_hashes() -> None:
    pipeline = DocketRetrievalPipeline(_client())

    record = pipeline.retrieve_candidate(
        candidate_id="cand-1",
        case_id="case-1",
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    ).to_record()

    assert record["docket_entries"][1]["source_document_ids"] == ["doc-34"]
    assert record["filings"][0]["provenance"]["source_document_id"] == "doc-1"
    assert record["filings"][0]["provenance"]["sha256"]
    assert record["missing_filings"][0]["reason"] == "no_source_document_id"


def test_classify_document_role_handles_core_packet_roles() -> None:
    assert classify_document_role("Complaint") is DocumentRole.COMPLAINT
    assert (
        classify_document_role("Memorandum in support of motion to dismiss")
        is DocumentRole.MTD_MEMORANDUM
    )
    assert (
        classify_document_role("Opposition to motion to dismiss")
        is DocumentRole.OPPOSITION
    )
    assert classify_document_role("Reply in support of MTD") is DocumentRole.REPLY
    assert classify_document_role("Opinion and order") is DocumentRole.DECISION
