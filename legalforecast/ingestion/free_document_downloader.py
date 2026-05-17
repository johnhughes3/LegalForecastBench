"""Fixture-safe downloader for free CourtListener/RECAP documents."""

from __future__ import annotations

import hashlib
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.path_safety import safe_path_component

_ALLOWED_DOCUMENT_HOSTS = frozenset({"www.courtlistener.com"})


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
class FreeDocumentDownloadRequest:
    """One free public document that should be present in the local store."""

    candidate_id: str
    source_provider: str
    source_document_id: str
    docket_entry_number: int | None
    document_role: DocumentRole
    source_url: str
    file_extension: str = "pdf"


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
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_DOCUMENT_HOSTS:
        raise ValueError("source_url must be an HTTPS CourtListener document URL")
