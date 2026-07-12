from __future__ import annotations

import hashlib
import json
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadError,
    FreeDocumentDownloadRequest,
    UrlLibFreeDocumentSource,
    _AllowlistedRedirectHandler,
    download_free_docket_documents,
)
from legalforecast.ingestion.provenance import DocumentRole


def test_downloads_free_courtlistener_documents_to_safe_paths(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {
            "https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complaint",
            "https://www.courtlistener.com/recap/doc-34.pdf": b"%PDF motion",
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
    assert records[0].sha256 == hashlib.sha256(b"%PDF complaint").hexdigest()
    assert records[0].document_role is DocumentRole.COMPLAINT
    assert records[0].docket_entry_number == 1
    assert records[0].free_or_purchased == "free"
    assert records[0].retry_count == 0
    assert records[0].rate_limited is False
    assert (tmp_path / records[1].local_path).read_bytes() == b"%PDF motion"
    assert source.requested_urls == (
        "https://www.courtlistener.com/recap/doc-1.pdf",
        "https://www.courtlistener.com/recap/doc-34.pdf",
    )


def test_downloader_resumes_existing_documents_without_refetch(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complaint"}
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


def test_corrupt_existing_document_is_refetched(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF original"}
    )
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    [first] = download_free_docket_documents(
        (request,), output_root=tmp_path, source=source
    )
    path = tmp_path / first.local_path
    path.write_bytes(b"%PDF corrupt")

    [resumed] = download_free_docket_documents(
        (request,), output_root=tmp_path, source=source
    )

    assert resumed.reused_existing is False
    assert path.read_bytes() == b"%PDF original"
    assert source.requested_urls == (request.source_url, request.source_url)


def test_failed_atomic_publish_leaves_no_final_named_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complete"}
    )
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )

    def fail_replace(*_args: object) -> None:
        raise OSError("simulated crash")

    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader.os.replace", fail_replace
    )
    with pytest.raises(OSError, match="simulated crash"):
        download_free_docket_documents((request,), output_root=tmp_path, source=source)
    assert not (tmp_path / "cand-1/courtlistener/entry-1_doc-1.pdf").exists()


def test_checkpoint_rows_hash_bytes_on_disk(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complete"}
    )
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    [record] = download_free_docket_documents(
        (request,), output_root=tmp_path, source=source
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / ".download-checkpoint.jsonl").read_text().splitlines()
    ]
    assert rows == [record.to_record()]
    assert (
        rows[0]["sha256"]
        == hashlib.sha256((tmp_path / record.local_path).read_bytes()).hexdigest()
    )


def test_live_source_aborts_oversize_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        headers = Message()

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://storage.courtlistener.com/doc.pdf"

        def read(self, _size: int = -1) -> bytes:
            return b"%PDF-too-large"

    _Response.headers["Content-Type"] = "application/pdf"
    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader._open_allowlisted",
        lambda *_a, **_kw: _Response(),
    )
    with pytest.raises(FreeDocumentDownloadError, match="byte ceiling"):
        UrlLibFreeDocumentSource(max_retries=0, max_bytes=4).fetch(
            "https://storage.courtlistener.com/doc.pdf"
        )


def test_live_source_refuses_off_allowlist_redirect_hop() -> None:
    handler = _AllowlistedRedirectHandler()
    with pytest.raises(ValueError, match="CourtListener document URL"):
        handler.redirect_request(
            urllib.request.Request("https://www.courtlistener.com/doc.pdf"),
            object(),
            302,
            "Found",
            Message(),
            "https://evil.example/doc.pdf",
        )


def test_downloader_accepts_courtlistener_storage_pdf_urls(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://storage.courtlistener.com/recap/doc-1.pdf": b"%PDF complaint"}
    )

    records = download_free_docket_documents(
        (
            _request(
                "doc-1",
                docket_entry_number=1,
                role=DocumentRole.COMPLAINT,
                url="https://storage.courtlistener.com/recap/doc-1.pdf",
            ),
        ),
        output_root=tmp_path,
        source=source,
    )

    assert records[0].byte_count == len(b"%PDF complaint")


def test_live_source_rejects_html_landing_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        status = 200
        headers = Message()

        def __enter__(self) -> _Response:
            self.headers["Content-Type"] = "text/html"
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://www.courtlistener.com/docket/1/5/example/"

        def read(self, _size: int = -1) -> bytes:
            return b"<html>not a pdf</html>"

    def _urlopen(*_args: Any, **_kwargs: Any) -> _Response:
        return _Response()

    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader._open_allowlisted",
        _urlopen,
    )

    source = UrlLibFreeDocumentSource(max_retries=0)
    with pytest.raises(FreeDocumentDownloadError, match="returned HTML"):
        source.fetch("https://www.courtlistener.com/docket/1/5/example/")


def test_live_source_resolves_courtlistener_landing_page_to_free_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        def __init__(
            self,
            *,
            final_url: str,
            content_type: str,
            content: bytes,
        ) -> None:
            self._final_url = final_url
            self._content = content
            self.headers = Message()
            self.headers["Content-Type"] = content_type

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return self._final_url

        def read(self, _size: int = -1) -> bytes:
            return self._content

    requested_urls: list[str] = []

    def _urlopen(request: Any, **_kwargs: Any) -> _Response:
        requested_urls.append(request.full_url)
        if request.full_url == "https://www.courtlistener.com/docket/1/5/example/":
            return _Response(
                final_url=request.full_url,
                content_type="text/html",
                content=b"""
                <html>
                  <body>
                    <a href="https://ecf.example.invalid/doc1">Buy on PACER</a>
                    <a href="https://storage.courtlistener.com/recap/doc-5.pdf">
                      Download PDF
                    </a>
                  </body>
                </html>
                """,
            )
        return _Response(
            final_url="https://storage.courtlistener.com/recap/doc-5.pdf",
            content_type="application/pdf",
            content=b"%PDF resolved",
        )

    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader._open_allowlisted",
        _urlopen,
    )

    source = UrlLibFreeDocumentSource(max_retries=0)
    fetch = source.fetch("https://www.courtlistener.com/docket/1/5/example/")

    assert fetch.content == b"%PDF resolved"
    assert requested_urls == [
        "https://www.courtlistener.com/docket/1/5/example/",
        "https://storage.courtlistener.com/recap/doc-5.pdf",
    ]


def test_downloader_rejects_path_traversal_ids(tmp_path: Path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complaint"}
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
