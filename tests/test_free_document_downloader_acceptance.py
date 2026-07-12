from __future__ import annotations

import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

from legalforecast.ingestion.free_document_downloader import UrlLibFreeDocumentSource


class _Response:
    def __init__(self, *, url: str, content_type: str, chunks: tuple[bytes, ...]) -> None:
        self._url = url
        self._chunks = iter(chunks)
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, _size: int = -1) -> bytes:
        return next(self._chunks, b"")


def test_streaming_fetch_retries_rate_limit_and_records_retry(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    attempts = 0

    def open_response(*_args: object, **_kwargs: object) -> _Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise urllib.error.HTTPError(
                "https://storage.courtlistener.com/doc.pdf",
                429,
                "rate limited",
                Message(),
                None,
            )
        return _Response(
            url="https://storage.courtlistener.com/doc.pdf",
            content_type="application/pdf",
            chunks=(b"%PDF complete",),
        )

    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader._open_allowlisted",
        open_response,
    )
    source = UrlLibFreeDocumentSource(max_retries=1, retry_backoff_seconds=0)

    result = source.fetch_to(
        "https://storage.courtlistener.com/doc.pdf",
        tmp_path / "document.partial",
    )

    assert attempts == 2
    assert result.retry_count == 1
    assert result.rate_limited is True


def test_streaming_fetch_resolves_landing_page_before_publishing_pdf(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    requested_urls: list[str] = []

    def open_response(request: Any, **_kwargs: object) -> _Response:
        requested_urls.append(request.full_url)
        if request.full_url.endswith("/docket/1/5/example/"):
            return _Response(
                url=request.full_url,
                content_type="text/html",
                chunks=(
                    b'<html><a href="https://storage.courtlistener.com/doc.pdf">'
                    b"Download PDF</a></html>",
                ),
            )
        return _Response(
            url="https://storage.courtlistener.com/doc.pdf",
            content_type="application/pdf",
            chunks=(b"%PDF complete",),
        )

    monkeypatch.setattr(
        "legalforecast.ingestion.free_document_downloader._open_allowlisted",
        open_response,
    )
    destination = tmp_path / "document.partial"

    UrlLibFreeDocumentSource(max_retries=0).fetch_to(
        "https://www.courtlistener.com/docket/1/5/example/",
        destination,
    )

    assert destination.read_bytes() == b"%PDF complete"
    assert requested_urls == [
        "https://www.courtlistener.com/docket/1/5/example/",
        "https://storage.courtlistener.com/doc.pdf",
    ]
