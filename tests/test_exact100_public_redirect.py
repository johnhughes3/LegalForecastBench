"""Identity-bound urllib redirects for exact-100 public recovery."""

from __future__ import annotations

import urllib.request
from email.message import Message
from typing import Any, cast

import pytest
from legalforecast.ingestion.exact100_zero_cost_recovery import (
    Exact100ZeroCostRecoveryError,
    require_exact100_public_document_url,
)
from legalforecast.ingestion.free_document_downloader import (
    UrlLibFreeDocumentSource,
    _AllowlistedRedirectHandler,
)

_EXACT100_DOCUMENT_ID = "480673755"
_EXACT100_STORAGE_URL = (
    f"https://storage.courtlistener.com/recap/2026/08/09/{_EXACT100_DOCUMENT_ID}.pdf"
)
_WRONG_DOCUMENT_STORAGE_URL = (
    "https://storage.courtlistener.com/recap/2026/08/09/999999999.pdf"
)


def _require_exact100_document(url: str) -> None:
    require_exact100_public_document_url(url, document_id=_EXACT100_DOCUMENT_ID)


def _request(url: str) -> urllib.request.Request:
    request = urllib.request.Request(url)
    request.url_validator = _require_exact100_document  # type: ignore[attr-defined]
    return request


def test_allowlisted_redirect_handler_rejects_wrong_document_before_follow() -> None:
    handler = _AllowlistedRedirectHandler()
    with pytest.raises(
        Exact100ZeroCostRecoveryError,
        match=r"allowlisted and document-bound|changed during bounded retrieval",
    ):
        handler.redirect_request(
            _request(_EXACT100_STORAGE_URL),
            object(),
            302,
            "Found",
            Message(),
            _WRONG_DOCUMENT_STORAGE_URL,
        )


def test_allowlisted_redirect_handler_allows_same_document_host_change() -> None:
    handler = _AllowlistedRedirectHandler()
    redirected = handler.redirect_request(
        _request(
            f"https://www.courtlistener.com/recap/2026/08/09/{_EXACT100_DOCUMENT_ID}.pdf"
        ),
        object(),
        302,
        "Found",
        Message(),
        _EXACT100_STORAGE_URL,
    )
    assert redirected is not None
    assert redirected.full_url == _EXACT100_STORAGE_URL


def test_live_source_rejects_wrong_document_redirect_before_issuing_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_urls: list[str] = []

    class _Opener:
        def __init__(
            self, redirect_handler: urllib.request.HTTPRedirectHandler
        ) -> None:
            self.redirect_handler = redirect_handler

        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> object:
            del timeout
            opened_urls.append(request.full_url)
            return cast(
                object,
                cast(Any, self.redirect_handler).redirect_request(
                    request,
                    object(),
                    302,
                    "Found",
                    Message(),
                    _WRONG_DOCUMENT_STORAGE_URL,
                ),
            )

    def _build_redirecting_opener(
        redirect_handler: urllib.request.BaseHandler,
        *_args: object,
        **_kwargs: object,
    ) -> _Opener:
        del _args, _kwargs
        return _Opener(cast(urllib.request.HTTPRedirectHandler, redirect_handler))

    monkeypatch.setattr("urllib.request.build_opener", _build_redirecting_opener)

    source = UrlLibFreeDocumentSource(
        max_retries=0, final_url_validator=_require_exact100_document
    )
    with pytest.raises(
        Exact100ZeroCostRecoveryError,
        match=r"allowlisted and document-bound|changed during bounded retrieval",
    ):
        source.fetch(_EXACT100_STORAGE_URL)
    assert opened_urls == [_EXACT100_STORAGE_URL]
