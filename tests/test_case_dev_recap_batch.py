from __future__ import annotations

import pytest
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_recap_batch import (
    RecapDocketRecordError,
    enrich_recap_discovery_batch,
    recap_discovered_docket_from_record,
)


def test_batch_ranks_successes_and_reports_reconciled_counts() -> None:
    client, transport = _client(
        _lookup("101", entries=[]),
        _lookup(
            "102",
            entries=[
                _entry(
                    "entry-1",
                    "Complaint",
                    pdf_url="https://storage.courtlistener.com/complaint.pdf",
                )
            ],
        ),
    )

    result = enrich_recap_discovery_batch(
        client=client,
        records=(_record("101"), _record("102")),
        page_size=5,
    )

    assert [item.courtlistener_docket_id for item in result.successes] == [
        "102",
        "101",
    ]
    assert result.failures == ()
    assert result.reconciled is True
    assert result.summary.to_record() == {
        "input_record_count": 2,
        "converted_docket_count": 2,
        "enrichment_attempt_count": 2,
        "successful_docket_count": 2,
        "failure_count": 0,
        "conversion_failure_count": 0,
        "enrichment_failure_count": 0,
        "failure_reason_counts": {},
        "actual_free_required_document_count": 1,
        "missing_required_document_count": 5,
        "reconciled": True,
    }
    assert len(transport.requests) == 2
    assert all(
        params
        == {
            "type": "lookup",
            "docketId": docket_id,
            "includeEntries": True,
            "limit": 5,
        }
        for (_method, _path, params), docket_id in zip(
            transport.requests,
            ("101", "102"),
            strict=True,
        )
    )


def test_malformed_record_becomes_structured_failure_without_provider_call() -> None:
    client, transport = _client(_lookup("102", entries=[]))
    malformed = _record("101")
    malformed["eligibility_status"] = "clean"

    result = enrich_recap_discovery_batch(
        client=client,
        records=(malformed, _record("102")),
        page_size=5,
    )

    assert [item.courtlistener_docket_id for item in result.successes] == ["102"]
    [failure] = result.failures
    assert failure.input_index == 0
    assert failure.candidate_id == "courtlistener-docket-101"
    assert failure.docket_id == "101"
    assert failure.stage == "discovery_record"
    assert failure.reason == "eligibility_status_invalid"
    assert result.summary.conversion_failure_count == 1
    assert result.summary.enrichment_failure_count == 0
    assert result.summary.failure_reason_counts == (("eligibility_status_invalid", 1),)
    assert result.reconciled is True
    assert len(transport.requests) == 1


def test_enrichment_failure_is_retained_and_later_dockets_continue() -> None:
    client, transport = _client(
        _lookup("999", request_docket_id="101", entries=[]),
        _lookup("102", entries=[]),
    )

    result = enrich_recap_discovery_batch(
        client=client,
        records=(_record("101"), _record("102")),
        page_size=5,
    )

    assert [item.courtlistener_docket_id for item in result.successes] == ["102"]
    [failure] = result.failures
    assert failure.stage == "case_dev_enrichment"
    assert failure.reason == "case_dev_id_mismatch"
    assert failure.docket_id == "101"
    assert result.summary.enrichment_failure_count == 1
    assert result.reconciled is True
    assert len(transport.requests) == 2


def test_duplicate_docket_is_failed_before_duplicate_provider_spend() -> None:
    client, transport = _client(_lookup("101", entries=[]))

    result = enrich_recap_discovery_batch(
        client=client,
        records=(_record("101"), _record("101")),
        page_size=5,
    )

    assert len(result.successes) == 1
    [failure] = result.failures
    assert failure.input_index == 1
    assert failure.stage == "discovery_record"
    assert failure.reason == "duplicate_discovered_docket"
    assert len(transport.requests) == 1
    assert result.reconciled is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("candidate_id", "wrong", "candidate_id_mismatch"),
        ("docket_id", "not-numeric", "docket_id_invalid"),
        ("docket_url", "https://example.com/docket/101/x/", "docket_url_invalid"),
        ("entry_keys", [], "entry_keys_invalid"),
        ("entry_keys", ["101:1", "101:1"], "entry_keys_duplicate"),
        ("matched_terms", [], "matched_terms_invalid"),
    ],
)
def test_record_conversion_fails_closed(
    field: str,
    value: object,
    reason: str,
) -> None:
    record = _record("101")
    record[field] = value

    with pytest.raises(RecapDocketRecordError) as error:
        recap_discovered_docket_from_record(record)

    assert error.value.reason == reason


def _record(docket_id: str) -> dict[str, object]:
    return {
        "candidate_id": f"courtlistener-docket-{docket_id}",
        "docket_id": docket_id,
        "docket_url": (
            f"https://www.courtlistener.com/docket/{docket_id}/fixture-v-example/"
        ),
        "entry_keys": [f"{docket_id}:entry-10"],
        "matched_terms": ["motion to dismiss"],
        "eligibility_status": "potential_unverified",
    }


def _client(
    *responses: RecordedCaseDevResponse,
) -> tuple[CaseDevClient, CaseDevFixtureTransport]:
    transport = CaseDevFixtureTransport(responses)
    return CaseDevClient(
        config=CaseDevConfig(api_key=None), transport=transport
    ), transport


def _lookup(
    docket_id: str,
    *,
    entries: list[dict[str, object]],
    request_docket_id: str | None = None,
) -> RecordedCaseDevResponse:
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={
            "type": "lookup",
            "docketId": request_docket_id or docket_id,
            "includeEntries": True,
            "limit": 5,
        },
        status_code=200,
        payload={
            "docket": {
                "id": docket_id,
                "url": (
                    f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
                ),
                "entries": entries,
            }
        },
    )


def _entry(
    entry_id: str,
    description: str,
    *,
    pdf_url: str,
) -> dict[str, object]:
    return {
        "id": entry_id,
        "entryNumber": 1,
        "date": "2026-07-01",
        "description": description,
        "documents": [
            {
                "id": f"document-{entry_id}",
                "description": description,
                "type": "main_document",
                "pdfUrl": pdf_url,
                "isAvailable": True,
            }
        ],
    }
