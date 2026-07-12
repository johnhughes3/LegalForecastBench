from __future__ import annotations

import hashlib
import logging

from legalforecast.extraction import (
    OCRPage,
    OCRResult,
    extract_pdf_text_with_ocr_fallback,
)
from legalforecast.ingestion import CaseDevClient, CaseDevFixtureTransport
from legalforecast.ingestion.case_dev_client import RecordedCaseDevResponse
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    NormalizedDocketEntry,
    classify_document_role,
)
from legalforecast.selection.candidate_discovery import discover_mtd_candidates
from legalforecast.selection.motion_linkage import (
    MotionLinkageExclusionReason,
    link_mtd_dispositions,
    link_retrieved_candidate,
)
from legalforecast.testing.golden_fixtures import REQUIRED_PIPELINE_LOG_FIELDS


def test_ingestion_discovery_extraction_and_linkage_happy_path(caplog) -> None:
    client, document_texts = _case_dev_fixture_client()
    logger = logging.getLogger("legalforecast.tests.e2e")

    with caplog.at_level(logging.INFO, logger=logger.name):
        search_page = client.search_docket_entries("motion to dismiss", limit=10)
        candidates = discover_mtd_candidates(hit.raw for hit in search_page.items)
        candidate = candidates[0]
        _log_pipeline_decision(
            logger,
            case_id=candidate.case_id,
            candidate_id=f"cand_{candidate.case_id}",
            stage="discovery",
            decision="include",
            source_document_id="docket-search",
            source_hash=_hash_text("|".join(candidate.trigger_terms)),
            request_count=client.request_count,
            estimated_cost=client.usage_estimate().estimated_cost_usd,
        )

        retrieval = DocketRetrievalPipeline(client).retrieve_candidate(
            candidate_id=f"cand_{candidate.case_id}",
            case_id=candidate.case_id,
        )
        _log_pipeline_decision(
            logger,
            case_id=retrieval.case_id,
            candidate_id=retrieval.candidate_id,
            stage="retrieval",
            decision="include",
            source_document_id=retrieval.filings[0].source_document_id,
            source_hash=f"sha256:{retrieval.filings[0].provenance.sha256}",
            request_count=client.request_count,
            estimated_cost=client.usage_estimate().estimated_cost_usd,
        )

        extracted = {
            filing.source_document_id: extract_pdf_text_with_ocr_fallback(
                _pdf_for_document(filing.source_document_id, document_texts),
                ocr_engine=_fixture_ocr(document_texts[filing.source_document_id]),
            )
            for filing in retrieval.filings
        }
        _log_pipeline_decision(
            logger,
            case_id=retrieval.case_id,
            candidate_id=retrieval.candidate_id,
            stage="extraction",
            decision="include",
            source_document_id="doc-12",
            source_hash=f"sha256:{extracted['doc-12'].source_sha256}",
            request_count=client.request_count,
            estimated_cost=client.usage_estimate().estimated_cost_usd,
        )

        linkage = link_retrieved_candidate(retrieval)
        _log_pipeline_decision(
            logger,
            case_id=retrieval.case_id,
            candidate_id=retrieval.candidate_id,
            stage="linkage",
            decision="include",
            source_document_id="doc-35",
            source_hash=f"sha256:{retrieval.filings[-1].provenance.sha256}",
            request_count=client.request_count,
            estimated_cost=client.usage_estimate().estimated_cost_usd,
        )

    assert candidate.case_id == "case-1"
    assert retrieval.missing_filings == ()
    assert extracted["doc-12"].method.value == "ocr"
    assert "ocr_applied" in extracted["doc-12"].quality_flags
    assert extracted["doc-35"].method.value == "pdf_text"
    assert linkage.is_clean is True
    assert linkage.links[0].motion_entry_ids[0].startswith("entry-12-")
    assert linkage.links[0].disposition_entry_ids[0].startswith("entry-35-")
    _assert_structured_pipeline_logs(caplog.records, logger_name=logger.name)


def test_ingestion_failure_paths_log_exclude_and_review_decisions(caplog) -> None:
    logger = logging.getLogger("legalforecast.tests.e2e")

    with caplog.at_level(logging.INFO, logger=logger.name):
        false_positive_candidates = discover_mtd_candidates(
            (
                {
                    "case_id": "case-false",
                    "docket_entry_id": "entry-9",
                    "entry_text": "Notice of voluntary dismissal of Doe defendants",
                },
            )
        )
        _log_pipeline_decision(
            logger,
            case_id="case-false",
            candidate_id="cand_case_false",
            stage="discovery",
            decision="exclude",
            exclusion_reason="false_positive_dismissal",
            source_document_id="entry-9",
            source_hash=_hash_text("Notice of voluntary dismissal of Doe defendants"),
            request_count=0,
            estimated_cost=0.0,
        )

        ambiguous_linkage = link_mtd_dispositions(
            (
                _normalized_entry(12, "Defendant A motion to dismiss complaint"),
                _normalized_entry(13, "Defendant B motion to dismiss complaint"),
                _normalized_entry(30, "Order granting motion to dismiss"),
            ),
            candidate_id="cand_case_review",
            case_id="case-review",
        )
        _log_pipeline_decision(
            logger,
            case_id="case-review",
            candidate_id="cand_case_review",
            stage="linkage",
            decision="route_to_review",
            exclusion_reason=ambiguous_linkage.exclusion_entries[0].reason,
            source_document_id="entry-30",
            source_hash=_hash_text("Order granting motion to dismiss"),
            request_count=0,
            estimated_cost=0.0,
        )

    assert false_positive_candidates == ()
    assert ambiguous_linkage.links == ()
    assert ambiguous_linkage.exclusion_entries[0].reason == (
        MotionLinkageExclusionReason.AMBIGUOUS_MOTION_TO_ORDER_LINKAGE.value
    )
    decisions = [record.decision for record in caplog.records]
    assert decisions == ["exclude", "route_to_review"]
    _assert_structured_pipeline_logs(caplog.records, logger_name=logger.name)


def _case_dev_fixture_client() -> tuple[CaseDevClient, dict[str, str]]:
    document_texts = {
        "doc-1": "Complaint alleges breach of contract and fraud.",
        "doc-12": "Defendant's m0t10n t0 dism1ss challenges Count I.",
        "doc-18": "Plaintiff opposes the motion to dismiss.",
        "doc-35": "The motion to dismiss at ECF No. 12 is granted in part.",
    }
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "search", "query": "motion to dismiss", "limit": 10},
                status_code=200,
                payload={
                    "dockets": [
                        {
                            "id": "case-1",
                            "caseName": "Motion To Dismiss v. Fixture",
                            "docketNumber": "1:26-cv-00001",
                            "court": "S.D.N.Y.",
                            "dateFiled": "2026-05-14",
                        },
                    ]
                },
            ),
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "lookup", "docketId": "case-1"},
                status_code=200,
                payload={
                    "docket": {
                        "id": "case-1",
                        "caseName": "Fixture v. Example",
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
                            _case_dev_docket_payload(1, "Complaint", "doc-1"),
                            _case_dev_docket_payload(
                                12,
                                "Motion to dismiss complaint",
                                "doc-12",
                            ),
                            _case_dev_docket_payload(
                                18,
                                "Opposition to motion to dismiss",
                                "doc-18",
                            ),
                            _case_dev_docket_payload(
                                35,
                                (
                                    "Opinion and order granting motion to dismiss "
                                    "at ECF No. 12"
                                ),
                                "doc-35",
                            ),
                        ],
                    }
                },
            ),
            *(
                RecordedCaseDevResponse(
                    method="GET",
                    path=f"/v1/documents/{document_id}",
                    params={},
                    status_code=200,
                    payload={
                        "document_id": document_id,
                        "case_id": "case-1",
                        "text": text,
                    },
                )
                for document_id, text in document_texts.items()
            ),
        ]
    )
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key=None,
            base_url="https://api.case.dev",
            estimated_cost_per_request_usd=0.01,
        ),
        transport=transport,
    )
    return client, document_texts


def _case_dev_docket_payload(
    entry_number: int,
    text: str,
    document_id: str,
) -> dict[str, object]:
    return {
        "entryNumber": entry_number,
        "description": text,
        "date": "2026-05-14",
        "documents": [{"id": document_id}],
    }


def _normalized_entry(entry_number: int, text: str) -> NormalizedDocketEntry:
    return NormalizedDocketEntry(
        source_provider="case.dev",
        source_case_id="case-review",
        docket_entry_id=f"entry-{entry_number}",
        entry_number=str(entry_number),
        entry_text=text,
        filed_at="2026-05-14",
        document_role=classify_document_role(text),
        source_document_ids=(f"doc-{entry_number}",),
        source_url=None,
    )


def _pdf_for_document(document_id: str, document_texts: dict[str, str]) -> bytes:
    if document_id == "doc-12":
        return _pdf_with_streams("q 100 0 0 100 0 0 cm /Im1 Do Q")
    return _pdf_with_streams(_text_stream(document_texts[document_id]))


def _fixture_ocr(text: str):
    def run(document_bytes: bytes) -> OCRResult:
        return OCRResult(
            pages=(OCRPage(page_number=1, text=text),),
            source_sha256=hashlib.sha256(document_bytes).hexdigest(),
            quality_flags=("synthetic_ocr_fixture",),
            engine_name="fixture-ocr",
        )

    return run


def _pdf_with_streams(*streams: str) -> bytes:
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        f"2 0 obj << /Type /Pages /Count {len(streams)} /Kids [] >> endobj",
    ]
    for index, stream in enumerate(streams, start=3):
        body = stream.encode("utf-8")
        objects.append(
            f"{index} 0 obj << /Type /Page /Contents {index + 20} 0 R >> endobj"
        )
        objects.append(
            f"{index + 20} 0 obj << /Length {len(body)} >> stream\n"
            f"{stream}\n"
            "endstream endobj"
        )
    return ("%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF").encode("utf-8")


def _text_stream(text: str) -> str:
    return f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _log_pipeline_decision(
    logger: logging.Logger,
    *,
    case_id: str,
    candidate_id: str,
    stage: str,
    decision: str,
    source_document_id: str,
    source_hash: str,
    request_count: int,
    estimated_cost: float | None,
    exclusion_reason: str | None = None,
) -> None:
    cost = 0.0 if estimated_cost is None else estimated_cost
    logger.info(
        "fixture pipeline decision",
        extra={
            "case_id": case_id,
            "candidate_id": candidate_id,
            "stage": stage,
            "source_provider": "case.dev",
            "source_document_id": source_document_id,
            "source_hash": source_hash,
            "decision": decision,
            "exclusion_reason": exclusion_reason,
            "elapsed_ms": 0,
            "duration_ms": 0,
            "request_count": request_count,
            "estimated_cost": cost,
            "cost_usd": cost,
        },
    )


def _assert_structured_pipeline_logs(
    records: list[logging.LogRecord],
    *,
    logger_name: str,
) -> None:
    pipeline_records = [record for record in records if record.name == logger_name]
    assert pipeline_records
    for record in pipeline_records:
        for field_name in REQUIRED_PIPELINE_LOG_FIELDS:
            assert field_name in record.__dict__
