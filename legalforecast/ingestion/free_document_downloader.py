"""Fixture-safe downloader for free CourtListener/RECAP documents."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.path_safety import safe_path_component

_ALLOWED_DOCUMENT_HOSTS = frozenset(
    {"www.courtlistener.com", "storage.courtlistener.com"}
)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_DEFAULT_USER_AGENT = (
    "LegalForecastBench/0.1 "
    "(public CourtListener/RECAP free-document retrieval; no PACER purchase)"
)


class FreeDocumentDownloadError(RuntimeError):
    """Raised when a free document cannot be retrieved or stored."""


@dataclass(frozen=True, slots=True)
class FreeDocumentFetch:
    """Bytes and retry facts returned by a free-document source."""

    content: bytes
    retry_count: int = 0
    rate_limited: bool = False


class FreeDocumentSource(Protocol):
    """Explicit source dependency for free-document downloads."""

    def fetch(self, source_url: str) -> FreeDocumentFetch: ...


class FixtureFreeDocumentSource:
    """In-memory document source for offline tests and fixtures."""

    def __init__(self, documents_by_url: Mapping[str, bytes]) -> None:
        self._documents_by_url = dict(documents_by_url)
        self._requested_urls: list[str] = []

    @property
    def requested_urls(self) -> tuple[str, ...]:
        return tuple(self._requested_urls)

    def fetch(self, source_url: str) -> FreeDocumentFetch:
        self._requested_urls.append(source_url)
        try:
            return FreeDocumentFetch(content=self._documents_by_url[source_url])
        except KeyError as exc:
            raise FreeDocumentDownloadError(
                f"no fixture document registered for {source_url}"
            ) from exc


@dataclass(frozen=True, slots=True)
class UrlLibFreeDocumentSource:
    """Explicit live source for free public CourtListener/RECAP documents."""

    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    user_agent: str = _DEFAULT_USER_AGENT

    def fetch(self, source_url: str) -> FreeDocumentFetch:
        _validate_public_document_url(source_url)
        retry_count = 0
        rate_limited = False
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                retry_count += 1
                time.sleep(self.retry_backoff_seconds * attempt)
            try:
                return self._fetch_once(
                    source_url,
                    retry_count=retry_count,
                    rate_limited=rate_limited,
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    rate_limited = True
                if (
                    exc.code not in _RETRYABLE_STATUS_CODES
                    or attempt >= self.max_retries
                ):
                    break
            except (TimeoutError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
        raise FreeDocumentDownloadError(
            f"failed to download free public document {source_url}: {last_error}"
        ) from last_error

    def _fetch_once(
        self,
        source_url: str,
        *,
        retry_count: int,
        rate_limited: bool,
        allow_landing_resolution: bool = True,
    ) -> FreeDocumentFetch:
        request = urllib.request.Request(
            source_url,
            headers={
                "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
                "User-Agent": self.user_agent,
            },
        )
        # URL host is allowlisted above; urllib follows CourtListener redirects.
        with urllib.request.urlopen(  # nosec B310
            request,
            timeout=self.timeout_seconds,
        ) as response:
            final_url = response.geturl()
            _validate_public_document_url(final_url)
            content = response.read()
            content_type = response.headers.get_content_type().lower()
        if (
            allow_landing_resolution
            and _looks_like_html_content(content)
            and _is_courtlistener_document_landing_url(final_url)
        ):
            resolved_url = _free_pdf_url_from_landing_page(final_url, content)
            if resolved_url is not None and resolved_url != final_url:
                _validate_public_document_url(resolved_url)
                return self._fetch_once(
                    resolved_url,
                    retry_count=retry_count,
                    rate_limited=rate_limited,
                    allow_landing_resolution=False,
                )
        _validate_public_document_content(
            source_url=source_url,
            content=content,
            content_type=content_type,
        )
        return FreeDocumentFetch(
            content=content,
            retry_count=retry_count,
            rate_limited=rate_limited,
        )


@dataclass(frozen=True, slots=True)
class FreeDocumentDownloadRequest:
    """One free public document that should be present in the local store."""

    candidate_id: str
    source_provider: str
    source_document_id: str
    docket_entry_number: int | None
    document_role: DocumentRole
    source_url: str
    file_extension: str = "pdf"

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_provider": self.source_provider,
            "source_document_id": self.source_document_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url,
            "file_extension": self.file_extension,
        }


@dataclass(frozen=True, slots=True)
class FreeDocumentDownloadRecord:
    """Stored-document metadata for acquisition manifests."""

    candidate_id: str
    source_provider: str
    source_document_id: str
    docket_entry_number: int | None
    document_role: DocumentRole
    source_url: str
    local_path: str
    sha256: str
    byte_count: int
    free_or_purchased: str
    retry_count: int
    rate_limited: bool
    reused_existing: bool

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_provider": self.source_provider,
            "source_document_id": self.source_document_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url,
            "local_path": self.local_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "free_or_purchased": self.free_or_purchased,
            "retry_count": self.retry_count,
            "rate_limited": self.rate_limited,
            "reused_existing": self.reused_existing,
        }


def download_free_docket_documents(
    requests: tuple[FreeDocumentDownloadRequest, ...],
    *,
    output_root: str | Path,
    source: FreeDocumentSource,
    allow_existing: bool = True,
) -> tuple[FreeDocumentDownloadRecord, ...]:
    """Download or reuse free docket documents under deterministic safe paths."""

    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not allow_existing:
        _reject_existing_outputs(requests, output_root=root)
    return tuple(
        _download_one(
            request,
            output_root=root,
            source=source,
            allow_existing=allow_existing,
        )
        for request in requests
    )


def _reject_existing_outputs(
    requests: tuple[FreeDocumentDownloadRequest, ...],
    *,
    output_root: Path,
) -> None:
    existing: list[Path] = []
    for request in requests:
        output_path = _document_output_path(output_root, request)
        if output_path.exists():
            existing.append(output_path)
    if existing:
        sample = ", ".join(
            path.relative_to(output_root).as_posix() for path in existing
        )
        raise FreeDocumentDownloadError(
            f"existing document artifact(s) present while resume is disabled: {sample}"
        )


def _download_one(
    request: FreeDocumentDownloadRequest,
    *,
    output_root: Path,
    source: FreeDocumentSource,
    allow_existing: bool,
) -> FreeDocumentDownloadRecord:
    _validate_public_document_url(request.source_url)
    output_path = _document_output_path(output_root, request)
    if output_path.exists():
        if not allow_existing:
            raise FreeDocumentDownloadError(
                "existing document artifact present while resume is disabled: "
                f"{output_path.relative_to(output_root).as_posix()}"
            )
        content = output_path.read_bytes()
        return _record_for_content(
            request,
            output_root=output_root,
            output_path=output_path,
            content=content,
            fetch=FreeDocumentFetch(content=content),
            reused_existing=True,
        )
    fetch = source.fetch(request.source_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(fetch.content)
    return _record_for_content(
        request,
        output_root=output_root,
        output_path=output_path,
        content=fetch.content,
        fetch=fetch,
        reused_existing=False,
    )


def _record_for_content(
    request: FreeDocumentDownloadRequest,
    *,
    output_root: Path,
    output_path: Path,
    content: bytes,
    fetch: FreeDocumentFetch,
    reused_existing: bool,
) -> FreeDocumentDownloadRecord:
    return FreeDocumentDownloadRecord(
        candidate_id=request.candidate_id,
        source_provider=request.source_provider,
        source_document_id=request.source_document_id,
        docket_entry_number=request.docket_entry_number,
        document_role=request.document_role,
        source_url=request.source_url,
        local_path=output_path.relative_to(output_root).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        byte_count=len(content),
        free_or_purchased="free",
        retry_count=fetch.retry_count,
        rate_limited=fetch.rate_limited,
        reused_existing=reused_existing,
    )


def _document_output_path(
    output_root: Path,
    request: FreeDocumentDownloadRequest,
) -> Path:
    candidate_id = safe_path_component(request.candidate_id, field_name="candidate_id")
    provider = safe_path_component(
        request.source_provider,
        field_name="source_provider",
    )
    document_id = safe_path_component(
        request.source_document_id,
        field_name="source_document_id",
    )
    extension = safe_path_component(
        request.file_extension.removeprefix("."),
        field_name="file_extension",
    )
    entry_prefix = (
        "entry-unknown"
        if request.docket_entry_number is None
        else f"entry-{request.docket_entry_number}"
    )
    filename = f"{entry_prefix}_{document_id}.{extension}"
    output_path = (output_root / candidate_id / provider / filename).resolve()
    output_path.relative_to(output_root)
    return output_path


def _validate_public_document_url(source_url: str) -> None:
    parsed = urllib.parse.urlparse(source_url)
    hostname = parsed.hostname.lower() if parsed.hostname is not None else None
    if parsed.scheme != "https" or hostname not in _ALLOWED_DOCUMENT_HOSTS:
        allowed = ", ".join(sorted(_ALLOWED_DOCUMENT_HOSTS))
        raise ValueError(
            "source_url must be an HTTPS CourtListener document URL "
            f"hosted on one of: {allowed}"
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("source_url must not include credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("source_url port must be valid") from exc
    if port not in {None, 443}:
        raise ValueError("source_url must not specify a non-default port")


def _free_pdf_url_from_landing_page(source_url: str, content: bytes) -> str | None:
    parser = _CourtListenerLandingPageParser(base_url=source_url)
    parser.feed(content.decode("utf-8", errors="ignore"))
    parser.close()
    return parser.best_url


def _looks_like_html_content(content: bytes) -> bool:
    prefix = content[:512].lstrip().lower()
    return prefix.startswith((b"<!doctype html", b"<html"))


def _is_courtlistener_document_landing_url(source_url: str) -> bool:
    parsed = urllib.parse.urlparse(source_url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.courtlistener.com"
        and parsed.path.startswith("/docket/")
    )


def _validate_public_document_content(
    *,
    source_url: str,
    content: bytes,
    content_type: str,
) -> None:
    if not content:
        raise FreeDocumentDownloadError(f"free public document was empty: {source_url}")
    if _looks_like_html_content(content):
        raise FreeDocumentDownloadError(
            "free public document URL returned HTML instead of a document: "
            f"{source_url}"
        )
    if content.lstrip().startswith(b"%PDF"):
        return
    if "pdf" in content_type:
        return
    parsed = urllib.parse.urlparse(source_url)
    if parsed.path.lower().endswith(".pdf") and content_type in {
        "",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return
    raise FreeDocumentDownloadError(
        "free public document response did not look like a PDF "
        f"(content-type={content_type or 'unknown'}): {source_url}"
    )


class _CourtListenerLandingPageParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._active_href: str | None = None
        self._active_title = ""
        self._active_text_parts: list[str] = []
        self._candidates: list[tuple[int, str]] = []

    @property
    def best_url(self) -> str | None:
        if not self._candidates:
            return None
        return sorted(self._candidates)[0][1]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        href = attrs_dict.get("href")
        if not href:
            return
        self._active_href = urllib.parse.urljoin(self._base_url, href)
        self._active_title = attrs_dict.get("title", "")
        self._active_text_parts = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._active_href is None:
            return
        score = _courtlistener_landing_link_score(
            self._active_href,
            " ".join((*self._active_text_parts, self._active_title)),
        )
        if score is not None:
            self._candidates.append((score, self._active_href))
        self._active_href = None
        self._active_title = ""
        self._active_text_parts = []


def _courtlistener_landing_link_score(href: str, text: str) -> int | None:
    normalized_text = " ".join(text.lower().split())
    parsed = urllib.parse.urlparse(href)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_DOCUMENT_HOSTS
        or "buy on pacer" in normalized_text
        or href.startswith("https://ecf.")
    ):
        return None
    if parsed.hostname == "storage.courtlistener.com":
        return 0
    if "download pdf" in normalized_text:
        return 1
    if parsed.path.lower().endswith(".pdf"):
        return 2
    return None
