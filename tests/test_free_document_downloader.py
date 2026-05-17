from __future__ import annotations

import hashlib

import pytest
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadRequest,
    download_free_docket_documents,
)
from legalforecast.ingestion.provenance import DocumentRole


def test_downloads_free_courtlistener_documents_to_safe_paths(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {
            "https://www.courtlistener.com/recap/doc-1.pdf": b"complaint pdf",
            "https://www.courtlistener.com/recap/doc-34.pdf": b"motion pdf",
        }
    )

    records = download_free_docket_documents(
        (
            _request(
                "doc-1",
                docket_entry_number=1,
                role=DocumentRole.COMPLAINT,
                url="https://www.courtlistener.com/recap/doc-1.pdf",
            ),
            _request(
                "doc-34",
                docket_entry_number=34,
                role=DocumentRole.MTD_MEMORANDUM,
                url="https://www.courtlistener.com/recap/doc-34.pdf",
            ),
        ),
        output_root=tmp_path,
        source=source,
    )

    assert [record.source_document_id for record in records] == ["doc-1", "doc-34"]
    assert records[0].local_path == "cand-1/courtlistener/entry-1_doc-1.pdf"
    assert records[0].sha256 == hashlib.sha256(b"complaint pdf").hexdigest()
    assert records[0].document_role is DocumentRole.COMPLAINT
    assert records[0].docket_entry_number == 1
    assert records[0].free_or_purchased == "free"
    assert records[0].retry_count == 0
    assert records[0].rate_limited is False
    assert (tmp_path / records[1].local_path).read_bytes() == b"motion pdf"
    assert source.requested_urls == (
        "https://www.courtlistener.com/recap/doc-1.pdf",
        "https://www.courtlistener.com/recap/doc-34.pdf",
    )


def test_downloader_resumes_existing_documents_without_refetch(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"complaint pdf"}
    )
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )

    first = download_free_docket_documents(
        (request,), output_root=tmp_path, source=source
    )
    second = download_free_docket_documents(
        (request,),
        output_root=tmp_path,
        source=source,
    )

    assert first[0].reused_existing is False
    assert second[0].reused_existing is True
    assert source.requested_urls == ("https://www.courtlistener.com/recap/doc-1.pdf",)


def test_downloader_rejects_path_traversal_ids(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"complaint pdf"}
    )

    with pytest.raises(ValueError, match="source_document_id"):
        download_free_docket_documents(
            (
                _request(
                    "../doc-1",
                    docket_entry_number=1,
                    role=DocumentRole.COMPLAINT,
                    url="https://www.courtlistener.com/recap/doc-1.pdf",
                ),
            ),
            output_root=tmp_path,
            source=source,
        )


def _request(
    source_document_id: str,
    *,
    docket_entry_number: int,
    role: DocumentRole,
    url: str,
) -> FreeDocumentDownloadRequest:
    return FreeDocumentDownloadRequest(
        candidate_id="cand-1",
        source_provider="courtlistener",
        source_document_id=source_document_id,
        docket_entry_number=docket_entry_number,
        document_role=role,
        source_url=url,
        file_extension="pdf",
    )
