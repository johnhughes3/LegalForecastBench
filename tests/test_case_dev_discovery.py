from __future__ import annotations

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_discovery import (
    CaseDevDiscoverySource,
    case_dev_firecrawl_candidate_record,
)


def test_case_dev_source_propagates_explicit_offset_and_raw_identity() -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={
                    "type": "search",
                    "query": "order on motion to dismiss",
                    "limit": 1,
                },
                status_code=200,
                payload={
                    "dockets": [
                        {
                            "id": "case-dev-abc",
                            "caseName": "Fixture v. Example",
                            "courtId": "nysd",
                            "docketNumber": "1:26-cv-00001",
                            "url": (
                                "https://www.courtlistener.com/api/rest/v4/dockets/123/"
                            ),
                        }
                    ],
                    "nextOffset": 1,
                },
            )
        ]
    )
    source = CaseDevDiscoverySource(
        CaseDevClient(
            config=CaseDevConfig(api_key="fixture-token"),
            transport=transport,
        )
    )

    page = source.fetch_page(
        term="order on motion to dismiss",
        cursor=None,
        page_size=1,
    )

    assert page.next_cursor == "1"
    [hit] = page.hits
    assert hit.candidate_id == "case-dev-abc"
    assert hit.payload["legal_docket"]["id"] == "case-dev-abc"


def test_candidate_record_keeps_case_dev_and_courtlistener_ids_distinct() -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "search", "query": "MTD", "limit": 1},
                status_code=200,
                payload={
                    "dockets": [
                        {
                            "id": "case-dev-abc",
                            "caseName": "Fixture v. Example",
                            "courtId": "nysd",
                            "docketNumber": "1:26-cv-00001",
                            "url": (
                                "https://www.courtlistener.com/api/rest/v4/dockets/123/"
                            ),
                        }
                    ]
                },
            )
        ]
    )
    source = CaseDevDiscoverySource(
        CaseDevClient(
            config=CaseDevConfig(api_key="fixture-token"),
            transport=transport,
        )
    )
    [hit] = source.fetch_page(term="MTD", cursor=None, page_size=1).hits

    record = case_dev_firecrawl_candidate_record(hit)

    assert record["case_dev_case_id"] == "case-dev-abc"
    assert record["courtlistener_docket_id"] == "123"
    assert record["courtlistener_url"] == (
        "https://www.courtlistener.com/docket/123/fixture-v-example/"
    )
    assert record["metadata_exclusion_reasons"] == []
