"""Fixture-safe downloader for free CourtListener/RECAP documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

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
    max_bytes: int = 100 * 1024 * 1024

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

    def fetch_to(self, source_url: str, destination: Path) -> FreeDocumentFetch:
        """Stream one validated PDF to a caller-owned temporary path."""
        _validate_public_document_url(source_url)
        retry_count = 0
        rate_limited = False
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                retry_count += 1
                time.sleep(self.retry_backoff_seconds * attempt)
            try:
                return self._fetch_to_once(
                    source_url,
                    destination,
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

    def _fetch_to_once(
        self,
        source_url: str,
        destination: Path,
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
        with _open_allowlisted(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            _validate_public_document_url(final_url)
            _validate_content_length(
                response.headers.get("Content-Length"),
                max_bytes=self.max_bytes,
                source_url=source_url,
            )
            byte_count = 0
            prefix = bytearray()
            content_type = response.headers.get_content_type().lower()
            landing_parser = (
                _CourtListenerLandingPageParser(base_url=final_url)
                if allow_landing_resolution
                and content_type == "text/html"
                and _is_courtlistener_document_landing_url(final_url)
                else None
            )
            with destination.open("wb") as handle:
                while chunk := response.read(min(1024 * 1024, self.max_bytes + 1)):
                    byte_count += len(chunk)
                    if byte_count > self.max_bytes:
                        raise _ceiling_error(self.max_bytes, source_url)
                    if len(prefix) < 512:
                        prefix.extend(chunk[: 512 - len(prefix)])
                    if landing_parser is not None:
                        landing_parser.feed(chunk.decode("utf-8", errors="ignore"))
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        if landing_parser is not None:
            landing_parser.close()
            resolved_url = landing_parser.best_url
            if resolved_url is not None and resolved_url != final_url:
                _validate_public_document_url(resolved_url)
                return self._fetch_to_once(
                    resolved_url,
                    destination,
                    retry_count=retry_count,
                    rate_limited=rate_limited,
                    allow_landing_resolution=False,
                )
        _validate_public_document_content(
            source_url=source_url,
            content=bytes(prefix),
            content_type=content_type,
        )
        return FreeDocumentFetch(
            content=b"",
            retry_count=retry_count,
            rate_limited=rate_limited,
        )

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
        with _open_allowlisted(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            _validate_public_document_url(final_url)
            _validate_content_length(
                response.headers.get("Content-Length"),
                max_bytes=self.max_bytes,
                source_url=source_url,
            )
            content = response.read(self.max_bytes + 1)
            if len(content) > self.max_bytes:
                raise _ceiling_error(self.max_bytes, source_url)
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


@dataclass(frozen=True, slots=True)
class FreeDocumentReuseResult:
    """Authenticated local-reuse evidence for a provider-free import."""

    records: tuple[FreeDocumentDownloadRecord, ...]
    source_checkpoint_sha256: str
    source_checkpoint_record_count: int
    destination_checkpoint_sha256: str


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
    _require_free_space(root, requests, source=source)
    checkpoint_path = root / ".download-checkpoint.jsonl"
    checkpoint = _read_checkpoint(checkpoint_path)
    if not allow_existing:
        _reject_existing_outputs(requests, output_root=root)
    records: list[FreeDocumentDownloadRecord] = []
    for request in requests:
        record = _download_one(
            request,
            output_root=root,
            source=source,
            allow_existing=allow_existing,
            expected=checkpoint.get(_request_key(request)),
        )
        records.append(record)
        checkpoint[_request_key(request)] = record
        _write_checkpoint(checkpoint_path, checkpoint.values())
    return tuple(records)


def reuse_authenticated_free_documents(
    requests: tuple[FreeDocumentDownloadRequest, ...],
    *,
    authenticated_source_records: tuple[FreeDocumentDownloadRecord, ...],
    source_output_root: str | Path,
    destination_output_root: str | Path,
) -> FreeDocumentReuseResult:
    """Materialize authenticated documents without constructing a provider."""

    source_root, destination_root = _validated_reuse_roots(
        source_output_root=source_output_root,
        destination_output_root=destination_output_root,
    )
    source_checkpoint_path = source_root / ".download-checkpoint.jsonl"
    source_checkpoint, source_checkpoint_payload = _read_checkpoint_payload(
        source_checkpoint_path
    )
    authenticated_by_key: dict[str, FreeDocumentDownloadRecord] = {}
    for record in authenticated_source_records:
        key = _record_key(record)
        if key in authenticated_by_key:
            raise FreeDocumentDownloadError(
                "authenticated source records repeat a request identity"
            )
        authenticated_by_key[key] = record
    if source_checkpoint != authenticated_by_key:
        raise FreeDocumentDownloadError(
            "authenticated source records do not exactly match the shared checkpoint"
        )
    _verify_completed_checkpoint_documents(
        source_root,
        source_checkpoint.values(),
    )
    source_checkpoint_sha256 = hashlib.sha256(source_checkpoint_payload).hexdigest()

    destination_checkpoint_path = destination_root / ".download-checkpoint.jsonl"
    destination_checkpoint, _ = _read_checkpoint_payload(destination_checkpoint_path)
    _verify_completed_checkpoint_documents(
        destination_root,
        destination_checkpoint.values(),
    )
    records: list[FreeDocumentDownloadRecord] = []
    seen_request_keys: set[str] = set()
    for request in requests:
        key = _request_key(request)
        if key in seen_request_keys:
            raise FreeDocumentDownloadError(
                "local reuse requests repeat a request identity"
            )
        seen_request_keys.add(key)
        source_record = source_checkpoint.get(key)
        if source_record is None or not _record_matches_request(
            source_record,
            request,
            output_root=source_root,
        ):
            raise FreeDocumentDownloadError(
                "authenticated source checkpoint does not match reuse request: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        existing = destination_checkpoint.get(key)
        if existing is not None:
            if not _record_matches_request(
                existing,
                request,
                output_root=destination_root,
            ):
                raise FreeDocumentDownloadError(
                    "destination checkpoint does not match reuse request: "
                    f"{request.candidate_id}/{request.source_document_id}"
                )
            if (
                existing.sha256 != source_record.sha256
                or existing.byte_count != source_record.byte_count
            ):
                raise FreeDocumentDownloadError(
                    "destination checkpoint conflicts with authenticated source: "
                    f"{request.candidate_id}/{request.source_document_id}"
                )
            _adopt_authenticated_destination(
                request,
                source_record=source_record,
                source_path=_checkpoint_document_path(source_root, source_record),
                source_root=source_root,
                destination_path=_document_output_path(destination_root, request),
                destination_root=destination_root,
            )
            record = existing
        else:
            record = _materialize_authenticated_document(
                request,
                source_record=source_record,
                source_root=source_root,
                destination_root=destination_root,
            )
            destination_checkpoint[key] = record
            expected_payload = _write_checkpoint(
                destination_checkpoint_path,
                destination_checkpoint.values(),
            )
            published_records, published_payload = _read_checkpoint_payload(
                destination_checkpoint_path
            )
            if (
                published_records != destination_checkpoint
                or published_payload != expected_payload
            ):
                raise FreeDocumentDownloadError(
                    "destination checkpoint changed during authenticated reuse"
                )
            _verify_completed_checkpoint_documents(destination_root, (record,))
        records.append(record)

    if destination_checkpoint_path.exists():
        published_checkpoint, destination_payload = _read_checkpoint_payload(
            destination_checkpoint_path
        )
        if published_checkpoint != destination_checkpoint:
            raise FreeDocumentDownloadError(
                "destination checkpoint changed after authenticated reuse"
            )
        _verify_completed_checkpoint_documents(
            destination_root,
            published_checkpoint.values(),
        )
    else:
        destination_payload = _write_checkpoint(destination_checkpoint_path, ())
        _verify_published_checkpoint(
            destination_checkpoint_path,
            expected_records={},
            expected_payload=destination_payload,
            output_root=destination_root,
        )
    destination_checkpoint_sha256 = hashlib.sha256(destination_payload).hexdigest()
    return FreeDocumentReuseResult(
        records=tuple(records),
        source_checkpoint_sha256=source_checkpoint_sha256,
        source_checkpoint_record_count=len(source_checkpoint),
        destination_checkpoint_sha256=destination_checkpoint_sha256,
    )


def verify_completed_free_document_manifest(
    requests: tuple[FreeDocumentDownloadRequest, ...],
    *,
    output_root: str | Path,
    manifest_path: str | Path,
) -> tuple[FreeDocumentDownloadRecord, ...]:
    """Verify and return immutable completed download evidence for resume."""

    configured_root = Path(output_root)
    if configured_root.is_symlink():
        raise FreeDocumentDownloadError(
            "completed free-download root must not be a symlink"
        )
    root = configured_root.resolve()
    request_keys = tuple(_request_key(request) for request in requests)
    if len(set(request_keys)) != len(request_keys):
        raise FreeDocumentDownloadError(
            "completed free-download current requests repeat a request identity"
        )
    manifest = Path(manifest_path)
    try:
        payload = _read_stable_regular_file(
            manifest,
            label="completed free-download manifest",
        )
        lines = payload.splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("completed free-download manifest contains a blank row")
        records = tuple(
            _download_record_from_mapping(
                json.loads(line),
                label=f"completed free-download manifest row {line_number}",
            )
            for line_number, line in enumerate(lines, start=1)
        )
    except (
        FreeDocumentDownloadError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        raise FreeDocumentDownloadError(
            "completed free-download manifest is unreadable or invalid"
        ) from exc
    if len(records) != len(requests) or any(
        not _record_matches_request(record, request, output_root=root)
        for record, request in zip(records, requests, strict=True)
    ):
        raise FreeDocumentDownloadError(
            "completed free-download manifest does not match current requests"
        )
    try:
        checkpoint = _read_checkpoint(root / ".download-checkpoint.jsonl")
    except (
        FreeDocumentDownloadError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        raise FreeDocumentDownloadError(
            "completed free-download checkpoint is unreadable or invalid"
        ) from exc
    if any(
        checkpoint.get(_request_key(request)) != record
        for request, record in zip(requests, records, strict=True)
    ):
        raise FreeDocumentDownloadError(
            "completed free-download manifest does not match its checkpoint"
        )
    _verify_completed_checkpoint_documents(root, checkpoint.values())
    return records


def verified_checkpoint_projection_sha256(
    records: tuple[FreeDocumentDownloadRecord, ...],
    *,
    checkpoint_path: str | Path,
) -> str:
    """Hash an authenticated checkpoint subset while allowing later appended rows."""

    checkpoint, _ = _read_checkpoint_payload(Path(checkpoint_path))
    projected: list[FreeDocumentDownloadRecord] = []
    seen: set[str] = set()
    for record in records:
        key = _record_key(record)
        if key in seen or checkpoint.get(key) != record:
            raise FreeDocumentDownloadError(
                "download checkpoint does not contain the authenticated projection"
            )
        seen.add(key)
        projected.append(record)
    return "sha256:" + hashlib.sha256(_checkpoint_payload(projected)).hexdigest()


def _verify_completed_checkpoint_documents(
    output_root: Path,
    records: Iterable[FreeDocumentDownloadRecord],
) -> None:
    """Authenticate every document named by a shared download checkpoint."""

    seen_paths: set[str] = set()
    for record in records:
        if record.local_path in seen_paths:
            raise FreeDocumentDownloadError(
                "completed free-download checkpoint repeats a document path: "
                f"{record.local_path}"
            )
        seen_paths.add(record.local_path)
        document_path = _checkpoint_document_path(output_root, record)
        _reject_document_parent_symlinks(
            output_root,
            document_path,
            label=f"{record.candidate_id}/{record.source_document_id}",
        )
        _recover_owned_reuse_temporary(
            document_path,
            expected_hash=record.sha256,
            expected_bytes=record.byte_count,
        )
        digest, byte_count, _ = _hash_verified_completed_document(
            output_root,
            document_path,
            label=f"{record.candidate_id}/{record.source_document_id}",
        )
        if digest != record.sha256 or byte_count != record.byte_count:
            raise FreeDocumentDownloadError(
                "completed free-download document bytes differ from the checkpoint: "
                f"{record.candidate_id}/{record.source_document_id}"
            )


def _checkpoint_document_path(
    output_root: Path,
    record: FreeDocumentDownloadRecord,
) -> Path:
    try:
        _validate_public_document_url(record.source_url)
        local_path = PurePosixPath(record.local_path)
        if (
            local_path.is_absolute()
            or len(local_path.parts) != 3
            or any(part in {"", ".", ".."} for part in local_path.parts)
        ):
            raise ValueError("local_path must be one canonical relative document path")
        extension = local_path.suffix.removeprefix(".")
        if not extension:
            raise ValueError("local_path must include a file extension")
        request = FreeDocumentDownloadRequest(
            candidate_id=record.candidate_id,
            source_provider=record.source_provider,
            source_document_id=record.source_document_id,
            docket_entry_number=record.docket_entry_number,
            document_role=record.document_role,
            source_url=record.source_url,
            file_extension=extension,
        )
        expected = _document_output_path(output_root, request)
        if expected.relative_to(output_root).as_posix() != record.local_path:
            raise ValueError("local_path does not match the record identity")
        return expected
    except (OSError, ValueError) as exc:
        raise FreeDocumentDownloadError(
            "completed free-download checkpoint has an invalid document identity/path: "
            f"{record.candidate_id}/{record.source_document_id}"
        ) from exc


def _hash_verified_completed_document(
    output_root: Path,
    path: Path,
    *,
    label: str,
    allowed_link_counts: frozenset[int] = frozenset({1}),
) -> tuple[str, int, tuple[int, ...]]:
    _reject_document_parent_symlinks(output_root, path, label=label)
    descriptor: int | None = None
    try:
        before_path = path.lstat()
        if (
            not stat.S_ISREG(before_path.st_mode)
            or before_path.st_nlink not in allowed_link_counts
        ):
            raise FreeDocumentDownloadError(
                "completed free-download document must be a singly linked regular "
                f"non-symlink file: {label}"
            )
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        before_fd = os.fstat(descriptor)
        if _stable_stat_identity(before_path) != _stable_stat_identity(before_fd):
            raise FreeDocumentDownloadError(
                f"completed free-download document changed while opening: {label}"
            )
        digest = hashlib.sha256()
        byte_count = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
        identity = _stable_stat_identity(before_fd)
        if identity != _stable_stat_identity(
            after_fd
        ) or identity != _stable_stat_identity(after_path):
            raise FreeDocumentDownloadError(
                f"completed free-download document changed while reading: {label}"
            )
        return digest.hexdigest(), byte_count, identity
    except FileNotFoundError as exc:
        raise FreeDocumentDownloadError(
            f"completed free-download document is missing: {label}"
        ) from exc
    except OSError as exc:
        raise FreeDocumentDownloadError(
            "completed free-download document must be a singly linked regular "
            f"non-symlink file: {label}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _recover_owned_reuse_temporary(
    destination: Path,
    *,
    expected_hash: str,
    expected_bytes: int,
) -> None:
    try:
        metadata = destination.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink == 1:
        return
    if metadata.st_nlink != 2:
        raise FreeDocumentDownloadError(
            "completed free-download document must be singly linked after reuse"
        )
    prefix = f".{destination.name}."
    candidates: list[Path] = []
    for sibling in destination.parent.iterdir():
        if not (
            sibling.name.startswith(prefix) and sibling.name.endswith(".reuse-partial")
        ):
            continue
        sibling_metadata = sibling.lstat()
        if (
            stat.S_ISREG(sibling_metadata.st_mode)
            and sibling_metadata.st_dev == metadata.st_dev
            and sibling_metadata.st_ino == metadata.st_ino
        ):
            candidates.append(sibling)
    if len(candidates) != 1:
        raise FreeDocumentDownloadError(
            "completed free-download document has unrecoverable link aliases"
        )
    digest, byte_count, _ = _hash_verified_completed_document(
        destination.parent,
        destination,
        label=destination.name,
        allowed_link_counts=frozenset({2}),
    )
    if digest != expected_hash or byte_count != expected_bytes:
        raise FreeDocumentDownloadError(
            "linked reuse temporary differs from the authenticated checkpoint"
        )
    candidates[0].unlink()
    _fsync_directory(destination.parent)


def _reject_document_parent_symlinks(
    output_root: Path,
    path: Path,
    *,
    label: str,
) -> None:
    try:
        relative = path.relative_to(output_root)
    except ValueError as exc:
        raise FreeDocumentDownloadError(
            f"completed free-download document escapes the output root: {label}"
        ) from exc
    current = output_root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise FreeDocumentDownloadError(
                "completed free-download document parent must not be a symlink: "
                f"{label}"
            )


def _stable_stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _validated_reuse_roots(
    *,
    source_output_root: str | Path,
    destination_output_root: str | Path,
) -> tuple[Path, Path]:
    source_configured = Path(source_output_root)
    destination_configured = Path(destination_output_root)
    _reject_existing_path_symlinks(source_configured, label="source document root")
    _reject_existing_path_symlinks(
        destination_configured,
        label="destination document root",
    )
    source_root = source_configured.resolve()
    destination_root = destination_configured.resolve()
    if not source_root.is_dir():
        raise FreeDocumentDownloadError(
            "authenticated source document root must be an existing directory"
        )
    if (
        source_root == destination_root
        or source_root.is_relative_to(destination_root)
        or destination_root.is_relative_to(source_root)
    ):
        raise FreeDocumentDownloadError(
            "source and destination document roots must be disjoint"
        )
    if destination_root.exists() and not destination_root.is_dir():
        raise FreeDocumentDownloadError("destination document root must be a directory")
    destination_root.mkdir(parents=True, exist_ok=True)
    if (
        source_root.stat().st_dev == destination_root.stat().st_dev
        and source_root.stat().st_ino == destination_root.stat().st_ino
    ):
        raise FreeDocumentDownloadError(
            "source and destination document roots must be disjoint"
        )
    return source_root, destination_root


def _reject_existing_path_symlinks(path: Path, *, label: str) -> None:
    if path.is_absolute():
        current = Path(path.anchor)
        components = path.parts[1:]
    else:
        current = Path.cwd()
        components = path.parts
    for part in components:
        if part in {"", "."}:
            continue
        if part == "..":
            current = current.parent
            continue
        current = current / part
        if current.is_symlink():
            raise FreeDocumentDownloadError(f"{label} must not traverse a symlink")


def _read_stable_regular_file(path: Path, *, label: str) -> bytes:
    _reject_existing_path_symlinks(path.parent, label=f"{label} parent")
    descriptor: int | None = None
    try:
        lexical_before = path.lstat()
        if not stat.S_ISREG(lexical_before.st_mode) or lexical_before.st_nlink != 1:
            raise FreeDocumentDownloadError(
                f"{label} must be a singly linked regular non-symlink file"
            )
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        before = os.fstat(descriptor)
        if _stable_stat_identity(lexical_before) != _stable_stat_identity(before):
            raise FreeDocumentDownloadError(f"{label} changed while opening")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        lexical_after = path.lstat()
        identity = _stable_stat_identity(before)
        if identity != _stable_stat_identity(
            after
        ) or identity != _stable_stat_identity(lexical_after):
            raise FreeDocumentDownloadError(f"{label} changed while reading")
        return b"".join(chunks)
    except OSError as exc:
        raise FreeDocumentDownloadError(
            f"{label} must be a singly linked regular non-symlink file"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _materialize_authenticated_document(
    request: FreeDocumentDownloadRequest,
    *,
    source_record: FreeDocumentDownloadRecord,
    source_root: Path,
    destination_root: Path,
) -> FreeDocumentDownloadRecord:
    source_path = _checkpoint_document_path(source_root, source_record)
    destination_path = _document_output_path(destination_root, request)
    if destination_path.is_symlink() or destination_path.exists():
        return _adopt_authenticated_destination(
            request,
            source_record=source_record,
            source_path=source_path,
            source_root=source_root,
            destination_path=destination_path,
            destination_root=destination_root,
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    _reject_document_parent_symlinks(
        destination_root,
        destination_path,
        label=f"{request.candidate_id}/{request.source_document_id}",
    )
    source_descriptor: int | None = None
    temporary: Path | None = None
    published = False
    completed = False
    try:
        before_source_path = source_path.lstat()
        if (
            not stat.S_ISREG(before_source_path.st_mode)
            or before_source_path.st_nlink != 1
        ):
            raise FreeDocumentDownloadError(
                "authenticated source document must be a singly linked regular "
                f"non-symlink file: {request.candidate_id}/{request.source_document_id}"
            )
        source_descriptor = os.open(
            source_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        before_source_fd = os.fstat(source_descriptor)
        if _stable_stat_identity(before_source_path) != _stable_stat_identity(
            before_source_fd
        ):
            raise FreeDocumentDownloadError(
                "authenticated source document changed while opening: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            dir=destination_path.parent,
            prefix=f".{destination_path.name}.",
            suffix=".reuse-partial",
        )
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        byte_count = 0
        with os.fdopen(temporary_descriptor, "wb") as destination_handle:
            while chunk := os.read(source_descriptor, 1024 * 1024):
                destination_handle.write(chunk)
                digest.update(chunk)
                byte_count += len(chunk)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
        after_source_fd = os.fstat(source_descriptor)
        after_source_path = source_path.lstat()
        source_identity = _stable_stat_identity(before_source_fd)
        if source_identity != _stable_stat_identity(
            after_source_fd
        ) or source_identity != _stable_stat_identity(after_source_path):
            raise FreeDocumentDownloadError(
                "authenticated source document changed while copying: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        if (
            digest.hexdigest() != source_record.sha256
            or byte_count != source_record.byte_count
        ):
            raise FreeDocumentDownloadError(
                "authenticated source document bytes differ from the checkpoint: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        os.link(temporary, destination_path, follow_symlinks=False)
        published = True
        temporary.unlink()
        temporary = None
        _fsync_directory(destination_path.parent)
        destination_digest, destination_byte_count, destination_identity = (
            _hash_verified_completed_document(
                destination_root,
                destination_path,
                label=f"{request.candidate_id}/{request.source_document_id}",
            )
        )
        if (
            destination_digest != source_record.sha256
            or destination_byte_count != source_record.byte_count
            or (
                destination_identity[0] == before_source_fd.st_dev
                and destination_identity[1] == before_source_fd.st_ino
            )
        ):
            raise FreeDocumentDownloadError(
                "materialized free document does not match its authenticated source: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        record = _reused_record_for_destination(
            request,
            source_record=source_record,
            destination_root=destination_root,
            destination_path=destination_path,
        )
        completed = True
        return record
    except FileExistsError as exc:
        raise FreeDocumentDownloadError(
            "destination document appeared during authenticated reuse: "
            f"{request.candidate_id}/{request.source_document_id}"
        ) from exc
    except OSError as exc:
        raise FreeDocumentDownloadError(
            "failed to materialize authenticated free document: "
            f"{request.candidate_id}/{request.source_document_id}"
        ) from exc
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if published and not completed:
            destination_path.unlink(missing_ok=True)


def _adopt_authenticated_destination(
    request: FreeDocumentDownloadRequest,
    *,
    source_record: FreeDocumentDownloadRecord,
    source_path: Path,
    source_root: Path,
    destination_path: Path,
    destination_root: Path,
) -> FreeDocumentDownloadRecord:
    label = f"{request.candidate_id}/{request.source_document_id}"
    _reject_document_parent_symlinks(
        destination_root,
        destination_path,
        label=label,
    )
    _recover_owned_reuse_temporary(
        destination_path,
        expected_hash=source_record.sha256,
        expected_bytes=source_record.byte_count,
    )
    source_digest, source_byte_count, source_identity = (
        _hash_verified_completed_document(
            source_root,
            source_path,
            label=label,
        )
    )
    destination_digest, destination_byte_count, destination_identity = (
        _hash_verified_completed_document(
            destination_root,
            destination_path,
            label=label,
        )
    )
    if (
        source_digest != source_record.sha256
        or source_byte_count != source_record.byte_count
        or destination_digest != source_record.sha256
        or destination_byte_count != source_record.byte_count
        or (
            source_identity[0] == destination_identity[0]
            and source_identity[1] == destination_identity[1]
        )
    ):
        raise FreeDocumentDownloadError(
            f"existing destination does not match authenticated source: {label}"
        )
    return _reused_record_for_destination(
        request,
        source_record=source_record,
        destination_root=destination_root,
        destination_path=destination_path,
    )


def _reused_record_for_destination(
    request: FreeDocumentDownloadRequest,
    *,
    source_record: FreeDocumentDownloadRecord,
    destination_root: Path,
    destination_path: Path,
) -> FreeDocumentDownloadRecord:
    return FreeDocumentDownloadRecord(
        candidate_id=request.candidate_id,
        source_provider=request.source_provider,
        source_document_id=request.source_document_id,
        docket_entry_number=request.docket_entry_number,
        document_role=request.document_role,
        source_url=request.source_url,
        local_path=destination_path.relative_to(destination_root).as_posix(),
        sha256=source_record.sha256,
        byte_count=source_record.byte_count,
        free_or_purchased="free",
        retry_count=source_record.retry_count,
        rate_limited=source_record.rate_limited,
        reused_existing=True,
    )


def is_free_document_dry_run_manifest(
    manifest_path: str | Path,
    *,
    request_count: int,
    document_output_root: str | Path,
) -> bool:
    """Recognize only the exact canonical planning stub written by the CLI."""

    manifest = Path(manifest_path)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_nlink != 1:
        raise FreeDocumentDownloadError(
            "free-download manifest must be a singly linked regular non-symlink file"
        )
    expected = (
        json.dumps(
            {
                "stage": "download-free",
                "dry_run": True,
                "request_count": request_count,
                "document_output_root": str(Path(document_output_root)),
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    return manifest.read_bytes() == expected


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
    expected: FreeDocumentDownloadRecord | None,
) -> FreeDocumentDownloadRecord:
    _validate_public_document_url(request.source_url)
    output_path = _document_output_path(output_root, request)
    if output_path.is_symlink() or output_path.exists():
        if (
            output_path.is_symlink()
            or not output_path.is_file()
            or output_path.stat().st_nlink != 1
        ):
            raise FreeDocumentDownloadError(
                "existing document artifact must be a singly linked regular "
                "non-symlink file: "
                f"{output_path.relative_to(output_root).as_posix()}"
            )
        if not allow_existing:
            raise FreeDocumentDownloadError(
                "existing document artifact present while resume is disabled: "
                f"{output_path.relative_to(output_root).as_posix()}"
            )
        if expected is None:
            raise FreeDocumentDownloadError(
                "existing document artifact lacks a matching download checkpoint: "
                f"{output_path.relative_to(output_root).as_posix()}"
            )
        if not _record_matches_request(expected, request, output_root=output_root):
            raise FreeDocumentDownloadError(
                "download checkpoint does not match current request: "
                f"{request.candidate_id}/{request.source_document_id}"
            )
        digest, byte_count = _hash_path(output_path)
        if expected.sha256 != digest or expected.byte_count != byte_count:
            raise FreeDocumentDownloadError(
                "existing document artifact differs from its download checkpoint: "
                f"{output_path.relative_to(output_root).as_posix()}"
            )
        return expected
    if isinstance(source, UrlLibFreeDocumentSource):
        fetch = _stream_live_document(source, request.source_url, output_path)
        return _record_for_path(
            request,
            output_root=output_root,
            output_path=output_path,
            fetch=fetch,
            reused_existing=False,
        )
    fetch = source.fetch(request.source_url)
    if not fetch.content:
        raise FreeDocumentDownloadError(
            f"free public document was empty: {request.source_url}"
        )
    if request.file_extension.removeprefix(".").lower() == "pdf" and not (
        fetch.content.lstrip().startswith(b"%PDF")
    ):
        raise FreeDocumentDownloadError(
            f"free public PDF is missing PDF magic: {request.source_url}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(output_path, fetch.content)
    return _record_for_content(
        request,
        output_root=output_root,
        output_path=output_path,
        content=fetch.content,
        fetch=fetch,
        reused_existing=False,
    )


def _stream_live_document(
    source: UrlLibFreeDocumentSource, source_url: str, output_path: Path
) -> FreeDocumentFetch:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".partial"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        fetch = source.fetch_to(source_url, temporary)
        os.replace(temporary, output_path)
        _fsync_directory(output_path.parent)
        return fetch
    finally:
        temporary.unlink(missing_ok=True)


def _request_key(request: FreeDocumentDownloadRequest) -> str:
    return "\0".join(
        (request.candidate_id, request.source_provider, request.source_document_id)
    )


def _record_key(record: FreeDocumentDownloadRecord) -> str:
    return "\0".join(
        (record.candidate_id, record.source_provider, record.source_document_id)
    )


def _require_free_space(
    root: Path,
    requests: tuple[FreeDocumentDownloadRequest, ...],
    *,
    source: FreeDocumentSource,
) -> None:
    per_document = (
        source.max_bytes
        if isinstance(source, UrlLibFreeDocumentSource)
        else 1024 * 1024
    )
    required = max(1, len(requests)) * per_document
    if shutil.disk_usage(root).free < required:
        raise FreeDocumentDownloadError(
            f"insufficient free space for {len(requests)} document download(s)"
        )


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".partial"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _record_for_path(
    request: FreeDocumentDownloadRequest,
    *,
    output_root: Path,
    output_path: Path,
    fetch: FreeDocumentFetch,
    reused_existing: bool,
) -> FreeDocumentDownloadRecord:
    digest, byte_count = _hash_path(output_path)
    return FreeDocumentDownloadRecord(
        candidate_id=request.candidate_id,
        source_provider=request.source_provider,
        source_document_id=request.source_document_id,
        docket_entry_number=request.docket_entry_number,
        document_role=request.document_role,
        source_url=request.source_url,
        local_path=output_path.relative_to(output_root).as_posix(),
        sha256=digest,
        byte_count=byte_count,
        free_or_purchased="free",
        retry_count=fetch.retry_count,
        rate_limited=fetch.rate_limited,
        reused_existing=reused_existing,
    )


def _hash_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _read_checkpoint(path: Path) -> dict[str, FreeDocumentDownloadRecord]:
    records, _ = _read_checkpoint_payload(path)
    return records


def _read_checkpoint_payload(
    path: Path,
) -> tuple[dict[str, FreeDocumentDownloadRecord], bytes]:
    if not path.exists() and not path.is_symlink():
        return {}, b""
    try:
        payload = _read_stable_regular_file(
            path,
            label="download checkpoint",
        )
        lines = payload.decode("utf-8").splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("download checkpoint contains a blank row")
        records: dict[str, FreeDocumentDownloadRecord] = {}
        for line_number, line in enumerate(lines, start=1):
            raw = json.loads(line)
            record = _download_record_from_mapping(
                raw,
                label=f"download checkpoint row {line_number}",
            )
            key = "\0".join(
                (
                    record.candidate_id,
                    record.source_provider,
                    record.source_document_id,
                )
            )
            if key in records:
                raise ValueError(f"download checkpoint repeats row identity: {key}")
            records[key] = record
        return records, payload
    except FreeDocumentDownloadError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise FreeDocumentDownloadError(
            "download checkpoint is unreadable or invalid"
        ) from exc


def _write_checkpoint(
    path: Path, records: Iterable[FreeDocumentDownloadRecord]
) -> bytes:
    payload = _checkpoint_payload(records)
    _atomic_write(path, payload)
    return payload


def _checkpoint_payload(records: Iterable[FreeDocumentDownloadRecord]) -> bytes:
    ordered = sorted(records, key=lambda record: record.local_path)
    return "".join(
        json.dumps(record.to_record(), sort_keys=True) + "\n" for record in ordered
    ).encode()


def _verify_published_checkpoint(
    path: Path,
    *,
    expected_records: Mapping[str, FreeDocumentDownloadRecord],
    expected_payload: bytes,
    output_root: Path,
) -> None:
    published_records, published_payload = _read_checkpoint_payload(path)
    if published_records != expected_records or published_payload != expected_payload:
        raise FreeDocumentDownloadError(
            "destination checkpoint changed during authenticated reuse"
        )
    _verify_completed_checkpoint_documents(
        output_root,
        published_records.values(),
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


def _download_record_from_mapping(
    raw: object,
    *,
    label: str,
) -> FreeDocumentDownloadRecord:
    expected_fields = frozenset(
        {
            "candidate_id",
            "source_provider",
            "source_document_id",
            "docket_entry_number",
            "document_role",
            "source_url",
            "local_path",
            "sha256",
            "byte_count",
            "free_or_purchased",
            "retry_count",
            "rate_limited",
            "reused_existing",
        }
    )
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} has invalid fields")
    mapping = cast(Mapping[object, object], raw)
    if (
        any(not isinstance(key, str) for key in mapping)
        or frozenset(cast(str, key) for key in mapping) != expected_fields
    ):
        raise ValueError(f"{label} has invalid fields")
    string_fields = (
        "candidate_id",
        "source_provider",
        "source_document_id",
        "document_role",
        "source_url",
        "local_path",
        "sha256",
        "free_or_purchased",
    )
    string_values: dict[str, str] = {}
    for field in string_fields:
        value = mapping[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} has invalid string fields")
        string_values[field] = value
    docket_entry_number = mapping["docket_entry_number"]
    if docket_entry_number is not None and (
        not isinstance(docket_entry_number, int)
        or isinstance(docket_entry_number, bool)
    ):
        raise ValueError(f"{label} has invalid docket entry number")
    byte_count = mapping["byte_count"]
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 0
    ):
        raise ValueError(f"{label} has invalid numeric fields")
    retry_count = mapping["retry_count"]
    if (
        not isinstance(retry_count, int)
        or isinstance(retry_count, bool)
        or retry_count < 0
    ):
        raise ValueError(f"{label} has invalid numeric fields")
    rate_limited = mapping["rate_limited"]
    reused_existing = mapping["reused_existing"]
    if not isinstance(rate_limited, bool) or not isinstance(reused_existing, bool):
        raise ValueError(f"{label} has invalid boolean fields")
    if (
        string_values["free_or_purchased"] != "free"
        or re.fullmatch(r"[0-9a-f]{64}", string_values["sha256"]) is None
    ):
        raise ValueError(f"{label} has invalid free-document commitment")
    return FreeDocumentDownloadRecord(
        candidate_id=string_values["candidate_id"],
        source_provider=string_values["source_provider"],
        source_document_id=string_values["source_document_id"],
        docket_entry_number=docket_entry_number,
        document_role=DocumentRole(string_values["document_role"]),
        source_url=string_values["source_url"],
        local_path=string_values["local_path"],
        sha256=string_values["sha256"],
        byte_count=byte_count,
        free_or_purchased=string_values["free_or_purchased"],
        retry_count=retry_count,
        rate_limited=rate_limited,
        reused_existing=reused_existing,
    )


def _record_matches_request(
    record: FreeDocumentDownloadRecord,
    request: FreeDocumentDownloadRequest,
    *,
    output_root: Path,
) -> bool:
    expected_path = _document_output_path(output_root, request)
    return (
        record.candidate_id == request.candidate_id
        and record.source_provider == request.source_provider
        and record.source_document_id == request.source_document_id
        and record.docket_entry_number == request.docket_entry_number
        and record.document_role is request.document_role
        and record.source_url == request.source_url
        and record.local_path == expected_path.relative_to(output_root).as_posix()
        and record.free_or_purchased == "free"
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
    output_path = output_root / candidate_id / provider / filename
    try:
        output_path.resolve().relative_to(output_root)
    except ValueError as exc:
        raise FreeDocumentDownloadError(
            "document output path escapes the output root: "
            f"{candidate_id}/{provider}/{filename}"
        ) from exc
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


def _ceiling_error(max_bytes: int, source_url: str) -> FreeDocumentDownloadError:
    return FreeDocumentDownloadError(
        f"free public document exceeds byte ceiling ({max_bytes}): {source_url}"
    )


def _validate_content_length(
    raw_value: str | None, *, max_bytes: int, source_url: str
) -> None:
    if raw_value is None:
        return
    try:
        content_length = int(raw_value)
    except ValueError as exc:
        raise FreeDocumentDownloadError(
            f"free public document returned invalid Content-Length: {source_url}"
        ) from exc
    if content_length < 0:
        raise FreeDocumentDownloadError(
            f"free public document returned invalid Content-Length: {source_url}"
        )
    if content_length > max_bytes:
        raise _ceiling_error(max_bytes, source_url)


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


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        _validate_public_document_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def _open_allowlisted(request: urllib.request.Request, *, timeout: float) -> Any:
    opener = urllib.request.build_opener(_AllowlistedRedirectHandler())
    return opener.open(request, timeout=timeout)  # nosec B310
