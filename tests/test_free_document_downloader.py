from __future__ import annotations

import hashlib
import json
import os
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
    reuse_authenticated_free_documents,
    verify_completed_free_document_manifest,
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
    assert second == first
    assert source.requested_urls == ("https://www.courtlistener.com/recap/doc-1.pdf",)


def test_corrupt_existing_document_fails_closed_without_refetch(tmp_path: Path) -> None:
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

    with pytest.raises(
        FreeDocumentDownloadError,
        match="differs from its download checkpoint",
    ):
        download_free_docket_documents((request,), output_root=tmp_path, source=source)

    assert path.read_bytes() == b"%PDF corrupt"
    assert source.requested_urls == (request.source_url,)


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


@pytest.mark.parametrize("substitution", ("symlink", "hardlink"))
def test_downloader_rejects_substituted_checkpoint_file(
    tmp_path: Path,
    substitution: str,
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
    download_free_docket_documents((request,), output_root=tmp_path, source=source)
    checkpoint = tmp_path / ".download-checkpoint.jsonl"
    alias = tmp_path / "checkpoint-alias.jsonl"
    if substitution == "symlink":
        checkpoint.rename(alias)
        checkpoint.symlink_to(alias)
    else:
        os.link(checkpoint, alias)

    with pytest.raises(
        FreeDocumentDownloadError,
        match="download checkpoint must be a singly linked regular non-symlink file",
    ):
        download_free_docket_documents((request,), output_root=tmp_path, source=source)

    assert source.requested_urls == (request.source_url,)


def test_downloader_rejects_blank_checkpoint_row_with_domain_error(
    tmp_path: Path,
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
    download_free_docket_documents((request,), output_root=tmp_path, source=source)
    checkpoint = tmp_path / ".download-checkpoint.jsonl"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"\n")

    with pytest.raises(
        FreeDocumentDownloadError,
        match="download checkpoint is unreadable or invalid",
    ):
        download_free_docket_documents((request,), output_root=tmp_path, source=source)

    assert source.requested_urls == (request.source_url,)


@pytest.mark.parametrize("substitution", ("symlink", "hardlink"))
def test_partial_resume_rejects_substituted_document_file(
    tmp_path: Path,
    substitution: str,
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
    [record] = download_free_docket_documents(
        (request,),
        output_root=tmp_path,
        source=source,
    )
    document = tmp_path / record.local_path
    alias = tmp_path / "document-alias.pdf"
    if substitution == "symlink":
        document.rename(alias)
        document.symlink_to(alias)
    else:
        os.link(document, alias)

    with pytest.raises(
        FreeDocumentDownloadError,
        match="existing document artifact must be a singly linked regular "
        "non-symlink file",
    ):
        download_free_docket_documents((request,), output_root=tmp_path, source=source)

    assert source.requested_urls == (request.source_url,)


def test_downloader_rejects_intermediate_symlink_escape_with_domain_error(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "downloads"
    output_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (output_root / "cand-1").symlink_to(outside, target_is_directory=True)
    source = FixtureFreeDocumentSource(
        {"https://www.courtlistener.com/recap/doc-1.pdf": b"%PDF complete"}
    )
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )

    with pytest.raises(
        FreeDocumentDownloadError,
        match="document output path escapes the output root",
    ):
        download_free_docket_documents(
            (request,),
            output_root=output_root,
            source=source,
        )

    assert source.requested_urls == ()
    assert tuple(outside.iterdir()) == ()


def test_completed_manifest_accepts_authenticated_shared_checkpoint_extras(
    tmp_path: Path,
) -> None:
    first_request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
        candidate_id="cand-1",
    )
    extra_request = _request(
        "doc-2",
        docket_entry_number=2,
        role=DocumentRole.MTD_MEMORANDUM,
        url="https://www.courtlistener.com/recap/doc-2.pdf",
        candidate_id="cand-2",
    )
    records = download_free_docket_documents(
        (first_request, extra_request),
        output_root=tmp_path,
        source=FixtureFreeDocumentSource(
            {
                first_request.source_url: b"%PDF first",
                extra_request.source_url: b"%PDF extra",
            }
        ),
    )
    manifest = tmp_path / "stage-02-manifest.jsonl"
    manifest.write_text(
        json.dumps(records[0].to_record(), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    verified = verify_completed_free_document_manifest(
        (first_request,),
        output_root=tmp_path,
        manifest_path=manifest,
    )

    assert verified == (records[0],)


def test_completed_manifest_rejects_duplicate_requested_identity(
    tmp_path: Path,
) -> None:
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    records = download_free_docket_documents(
        (request, request),
        output_root=tmp_path,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF first"}),
    )
    manifest = tmp_path / "duplicate-manifest.jsonl"
    manifest.write_text(
        "".join(
            json.dumps(record.to_record(), sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        FreeDocumentDownloadError,
        match="current requests repeat a request identity",
    ):
        verify_completed_free_document_manifest(
            (request, request),
            output_root=tmp_path,
            manifest_path=manifest,
        )


@pytest.mark.parametrize("substitution", ("bytes", "symlink", "hardlink"))
def test_completed_manifest_rejects_invalid_shared_checkpoint_extra(
    tmp_path: Path,
    substitution: str,
) -> None:
    first_request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
        candidate_id="cand-1",
    )
    extra_request = _request(
        "doc-2",
        docket_entry_number=2,
        role=DocumentRole.MTD_MEMORANDUM,
        url="https://www.courtlistener.com/recap/doc-2.pdf",
        candidate_id="cand-2",
    )
    records = download_free_docket_documents(
        (first_request, extra_request),
        output_root=tmp_path,
        source=FixtureFreeDocumentSource(
            {
                first_request.source_url: b"%PDF first",
                extra_request.source_url: b"%PDF extra",
            }
        ),
    )
    manifest = tmp_path / "stage-02-manifest.jsonl"
    manifest.write_text(
        json.dumps(records[0].to_record(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    extra_document = tmp_path / records[1].local_path
    alias = tmp_path / "extra-alias.pdf"
    if substitution == "bytes":
        extra_document.write_bytes(b"%PDF tampered")
    elif substitution == "symlink":
        extra_document.rename(alias)
        extra_document.symlink_to(alias)
    else:
        os.link(extra_document, alias)

    with pytest.raises(
        FreeDocumentDownloadError,
        match=r"completed free-download (document|checkpoint)",
    ):
        verify_completed_free_document_manifest(
            (first_request,),
            output_root=tmp_path,
            manifest_path=manifest,
        )


def test_reuses_authenticated_documents_without_constructing_a_provider(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    [source_record] = download_free_docket_documents(
        (request,),
        output_root=source_root,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF source"}),
    )
    source_path = source_root / source_record.local_path
    source_identity = source_path.stat().st_dev, source_path.stat().st_ino

    result = reuse_authenticated_free_documents(
        (request,),
        authenticated_source_records=(source_record,),
        source_output_root=source_root,
        destination_output_root=destination_root,
    )

    assert len(result.records) == 1
    assert result.source_checkpoint_record_count == 1
    assert result.records[0].reused_existing is True
    destination_path = destination_root / result.records[0].local_path
    assert destination_path.read_bytes() == b"%PDF source"
    assert (destination_path.stat().st_dev, destination_path.stat().st_ino) != (
        source_identity
    )
    assert source_path.read_bytes() == b"%PDF source"
    assert (
        result.source_checkpoint_sha256
        == hashlib.sha256(
            (source_root / ".download-checkpoint.jsonl").read_bytes()
        ).hexdigest()
    )
    assert (
        result.destination_checkpoint_sha256
        == hashlib.sha256(
            (destination_root / ".download-checkpoint.jsonl").read_bytes()
        ).hexdigest()
    )


def test_reuse_requires_the_complete_authenticated_source_checkpoint(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    requests = (
        _request(
            "doc-1",
            docket_entry_number=1,
            role=DocumentRole.COMPLAINT,
            url="https://www.courtlistener.com/recap/doc-1.pdf",
            candidate_id="cand-1",
        ),
        _request(
            "doc-2",
            docket_entry_number=2,
            role=DocumentRole.MTD_MEMORANDUM,
            url="https://www.courtlistener.com/recap/doc-2.pdf",
            candidate_id="cand-2",
        ),
    )
    records = download_free_docket_documents(
        requests,
        output_root=source_root,
        source=FixtureFreeDocumentSource(
            {request.source_url: b"%PDF source" for request in requests}
        ),
    )

    with pytest.raises(
        FreeDocumentDownloadError,
        match="authenticated source records do not exactly match",
    ):
        reuse_authenticated_free_documents(
            (requests[0],),
            authenticated_source_records=(records[0],),
            source_output_root=source_root,
            destination_output_root=tmp_path / "destination",
        )


def test_reuse_preserves_shared_destination_checkpoint_extras(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    requests = (
        _request(
            "doc-1",
            docket_entry_number=1,
            role=DocumentRole.COMPLAINT,
            url="https://www.courtlistener.com/recap/doc-1.pdf",
            candidate_id="cand-1",
        ),
        _request(
            "doc-2",
            docket_entry_number=2,
            role=DocumentRole.MTD_MEMORANDUM,
            url="https://www.courtlistener.com/recap/doc-2.pdf",
            candidate_id="cand-2",
        ),
    )
    source_records = download_free_docket_documents(
        requests,
        output_root=source_root,
        source=FixtureFreeDocumentSource(
            {request.source_url: b"%PDF source" for request in requests}
        ),
    )

    first = reuse_authenticated_free_documents(
        (requests[0],),
        authenticated_source_records=source_records,
        source_output_root=source_root,
        destination_output_root=destination_root,
    )
    first_path = destination_root / first.records[0].local_path
    first_identity = first_path.stat().st_dev, first_path.stat().st_ino
    second = reuse_authenticated_free_documents(
        (requests[1],),
        authenticated_source_records=source_records,
        source_output_root=source_root,
        destination_output_root=destination_root,
    )

    checkpoint_rows = [
        json.loads(line)
        for line in (destination_root / ".download-checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(checkpoint_rows) == 2
    assert (first_path.stat().st_dev, first_path.stat().st_ino) == first_identity
    assert second.records[0].source_document_id == "doc-2"


def test_reuse_rejects_conflicting_existing_destination_bytes(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    source_records = download_free_docket_documents(
        (request,),
        output_root=source_root,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF source"}),
    )
    download_free_docket_documents(
        (request,),
        output_root=destination_root,
        source=FixtureFreeDocumentSource(
            {request.source_url: b"%PDF conflicting destination"}
        ),
    )

    with pytest.raises(
        FreeDocumentDownloadError,
        match="destination checkpoint conflicts with authenticated source",
    ):
        reuse_authenticated_free_documents(
            (request,),
            authenticated_source_records=source_records,
            source_output_root=source_root,
            destination_output_root=destination_root,
        )


@pytest.mark.parametrize("aliased_root", ("source", "destination"))
def test_reuse_rejects_lexical_symlink_parent_traversal(
    tmp_path: Path,
    aliased_root: str,
) -> None:
    base = tmp_path / "base"
    outside = tmp_path / "outside"
    branch = outside / "branch"
    base.mkdir()
    branch.mkdir(parents=True)
    (base / "link").symlink_to(branch, target_is_directory=True)
    source_root = outside / "source"
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    records = download_free_docket_documents(
        (request,),
        output_root=source_root,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF source"}),
    )
    source_argument = (
        base / "link" / ".." / "source" if aliased_root == "source" else source_root
    )
    destination_argument = (
        base / "link" / ".." / "destination"
        if aliased_root == "destination"
        else tmp_path / "destination"
    )

    with pytest.raises(FreeDocumentDownloadError, match="must not traverse a symlink"):
        reuse_authenticated_free_documents(
            (request,),
            authenticated_source_records=records,
            source_output_root=source_argument,
            destination_output_root=destination_argument,
        )


def test_reuse_recovers_owned_linked_temporary_after_publish_crash(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    [source_record] = download_free_docket_documents(
        (request,),
        output_root=source_root,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF source"}),
    )
    destination = destination_root / source_record.local_path
    destination.parent.mkdir(parents=True)
    temporary = destination.parent / f".{destination.name}.crash.reuse-partial"
    temporary.write_bytes(b"%PDF source")
    os.link(temporary, destination)
    assert destination.stat().st_nlink == 2

    result = reuse_authenticated_free_documents(
        (request,),
        authenticated_source_records=(source_record,),
        source_output_root=source_root,
        destination_output_root=destination_root,
    )

    assert result.records[0].sha256 == source_record.sha256
    assert destination.stat().st_nlink == 1
    assert not temporary.exists()


def test_reuse_rejects_overlapping_source_and_destination_roots(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    request = _request(
        "doc-1",
        docket_entry_number=1,
        role=DocumentRole.COMPLAINT,
        url="https://www.courtlistener.com/recap/doc-1.pdf",
    )
    records = download_free_docket_documents(
        (request,),
        output_root=source_root,
        source=FixtureFreeDocumentSource({request.source_url: b"%PDF source"}),
    )

    with pytest.raises(FreeDocumentDownloadError, match="must be disjoint"):
        reuse_authenticated_free_documents(
            (request,),
            authenticated_source_records=records,
            source_output_root=source_root,
            destination_output_root=source_root / "nested",
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
    candidate_id: str = "cand-1",
) -> FreeDocumentDownloadRequest:
    return FreeDocumentDownloadRequest(
        candidate_id=candidate_id,
        source_provider="courtlistener",
        source_document_id=source_document_id,
        docket_entry_number=docket_entry_number,
        document_role=role,
        source_url=url,
        file_extension="pdf",
    )
