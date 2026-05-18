from __future__ import annotations

from datetime import UTC, datetime

import pytest
from legalforecast.ingestion import (
    AvailabilityStatus,
    DocumentRole,
    RecapAuthError,
    RecapClient,
    RecapConfig,
    RecapDocumentUnavailableError,
    RecapFixtureTransport,
    RecapRateLimitError,
    RecapResponseError,
    RecordedRecapResponse,
    sha256_text,
)
from legalforecast.ingestion.recap_client import RECAP_BASE_URL_ENV


def test_recap_document_lookup_and_provenance() -> None:
    client = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                _response(
                    path="/recap-documents/9001/",
                    payload={
                        "id": 9001,
                        "docket": 123,
                        "docket_entry": 7001,
                        "description": "Motion to dismiss memorandum",
                        "plain_text": "Motion to dismiss text",
                        "filepath_local": (
                            "https://www.courtlistener.com/recap/gov.uscourts/"
                            "nysd.123/gov.uscourts.nysd.123.12.0.pdf"
                        ),
                    },
                ),
            )
        ),
    )

    document = client.get_document("9001")
    provenance = document.to_provenance(
        source_case_id="123",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        docket_entry_number=12,
        document_role=DocumentRole.MTD_MEMORANDUM,
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )

    assert document.recap_document_id == "9001"
    assert document.is_available is True
    assert provenance.source_provider == "recap"
    assert provenance.source_document_id == "9001"
    assert provenance.sha256 == sha256_text("Motion to dismiss text")
    assert provenance.availability_status is AvailabilityStatus.AVAILABLE
    assert provenance.is_mounted_for_model is True
    assert client.request_count == 1


def test_recap_metadata_without_content_is_not_mountable() -> None:
    client = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                _response(
                    path="/recap-documents/9002/",
                    payload={
                        "id": 9002,
                        "docket": 123,
                        "docket_entry": 7002,
                        "description": "Unavailable reply",
                    },
                ),
            )
        ),
    )

    document = client.get_document("9002")

    assert document.is_available is False
    assert document.to_record()["availability_status"] == "unavailable"
    with pytest.raises(RecapDocumentUnavailableError, match="cannot be mounted"):
        document.to_provenance(
            source_case_id="123",
            court="S.D.N.Y.",
            docket_number="1:26-cv-00001",
            document_role=DocumentRole.REPLY,
            retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        )
    metadata_provenance = document.to_provenance(
        source_case_id="123",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        document_role=DocumentRole.REPLY,
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        is_mounted_for_model=False,
    )
    assert metadata_provenance.availability_status is AvailabilityStatus.UNAVAILABLE


def test_recap_unavailable_auth_and_rate_errors() -> None:
    unavailable = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                _response(
                    path="/recap-documents/missing/",
                    status_code=404,
                    payload={"detail": "missing"},
                ),
            )
        ),
    )
    with pytest.raises(RecapDocumentUnavailableError, match="missing"):
        unavailable.get_document("missing")

    auth = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                _response(
                    path="/recap-documents/9001/",
                    status_code=401,
                    payload={"detail": "auth required"},
                ),
            )
        ),
    )
    with pytest.raises(RecapAuthError, match="auth required"):
        auth.get_document("9001")

    limited = RecapClient(
        config=RecapConfig(),
        transport=RecapFixtureTransport(
            (
                _response(
                    path="/recap-documents/9001/",
                    status_code=429,
                    payload={"detail": "slow down"},
                ),
            )
        ),
        max_retries=0,
    )
    with pytest.raises(RecapRateLimitError, match="slow down"):
        limited.get_document("9001")


def test_recap_config_reuses_courtlistener_token_when_specific_token_absent() -> None:
    config = RecapConfig.from_env({"COURTLISTENER_API_TOKEN": " shared-token "})

    assert config.api_token == "shared-token"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://www.courtlistener.com/api/rest/v4",
        "https://www.courtlistener.com@evil.example/api/rest/v4",
        "https://evil.example/api/rest/v4",
        "https://www.courtlistener.com:444/api/rest/v4",
    ],
)
def test_recap_config_rejects_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(RecapResponseError, match=RECAP_BASE_URL_ENV):
        RecapConfig.from_env({RECAP_BASE_URL_ENV: base_url})


def _response(
    *,
    method: str = "GET",
    path: str,
    params: dict[str, object] | None = None,
    status_code: int = 200,
    payload: dict[str, object],
) -> RecordedRecapResponse:
    return RecordedRecapResponse(
        method=method,
        path=path,
        params={} if params is None else params,
        status_code=status_code,
        payload=payload,
    )
