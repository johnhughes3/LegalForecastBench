"""Dependency-free PDF text-layer extraction for benchmark fixtures."""

from __future__ import annotations

import hashlib
import re
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from legalforecast.extraction.normalize_text import normalize_extracted_text
from legalforecast.extraction.ocr import OCREngine, OCRResult, run_ocr_fallback
from legalforecast.ingestion import ExtractedTextArtifact, sha256_text


class PDFExtractionError(ValueError):
    """Raised when a document cannot be treated as a PDF."""


class ExtractionMethod(StrEnum):
    PDF_TEXT = "pdf_text"
    OCR = "ocr"


@dataclass(frozen=True, slots=True)
class ExtractedPDFPage:
    """Text extracted from one PDF page or page-like content stream."""

    page_number: int
    text: str

    def __post_init__(self) -> None:
        if self.page_number <= 0:
            raise ValueError("page_number must be positive")

    @property
    def text_sha256(self) -> str:
        return sha256_text(self.text)


@dataclass(frozen=True, slots=True)
class PDFTextExtractionResult:
    """Extracted text plus provenance-oriented quality metadata."""

    source_sha256: str
    method: ExtractionMethod
    pages: tuple[ExtractedPDFPage, ...]
    quality_flags: tuple[str, ...]
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.source_sha256)
        for flag in self.quality_flags:
            if not flag.strip():
                raise ValueError("quality_flags must contain non-empty strings")

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\f".join(page.text for page in self.pages).strip()

    @property
    def text_sha256(self) -> str:
        return sha256_text(self.text)

    @property
    def needs_ocr(self) -> bool:
        return (
            "no_text_layer" in self.quality_flags or "empty_text" in self.quality_flags
        )

    def to_text_artifact(
        self,
        *,
        source_document_id: str,
        extracted_at: datetime | None = None,
    ) -> ExtractedTextArtifact:
        return ExtractedTextArtifact(
            source_document_id=source_document_id,
            extracted_at=extracted_at or datetime.now(UTC),
            extraction_method=self.method.value,
            text_sha256=self.text_sha256,
            page_count=self.page_count or None,
            quality_flags=self.quality_flags,
            notes=self.notes,
        )


def extract_pdf_text(pdf_bytes: bytes) -> PDFTextExtractionResult:
    """Extract a simple PDF text layer with page boundaries and quality flags."""

    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    if not pdf_bytes.startswith(b"%PDF"):
        raise PDFExtractionError("document does not start with a PDF header")

    declared_page_count = _count_declared_pages(pdf_bytes)
    pages = _extract_text_pages(pdf_bytes)
    normalized_pages = tuple(
        ExtractedPDFPage(
            page_number=index,
            text=normalize_extracted_text(page_text).text,
        )
        for index, page_text in enumerate(pages, start=1)
        if normalize_extracted_text(page_text).text
    )

    quality_flags = _quality_flags(
        declared_page_count=declared_page_count,
        extracted_pages=normalized_pages,
    )

    return PDFTextExtractionResult(
        source_sha256=source_sha256,
        method=ExtractionMethod.PDF_TEXT,
        pages=normalized_pages,
        quality_flags=quality_flags,
    )


def extract_pdf_text_with_ocr_fallback(
    pdf_bytes: bytes,
    *,
    ocr_engine: OCREngine | None = None,
) -> PDFTextExtractionResult:
    """Extract PDF text and run OCR when the text layer is empty."""

    text_result = extract_pdf_text(pdf_bytes)
    if not text_result.needs_ocr:
        return text_result

    ocr_result = run_ocr_fallback(pdf_bytes, engine=ocr_engine)
    if not ocr_result.pages:
        return PDFTextExtractionResult(
            source_sha256=text_result.source_sha256,
            method=ExtractionMethod.PDF_TEXT,
            pages=text_result.pages,
            quality_flags=tuple(
                dict.fromkeys((*text_result.quality_flags, *ocr_result.quality_flags))
            ),
            notes="OCR fallback was requested but no OCR text was returned.",
        )

    return _result_from_ocr(text_result, ocr_result)


def _result_from_ocr(
    text_result: PDFTextExtractionResult,
    ocr_result: OCRResult,
) -> PDFTextExtractionResult:
    return PDFTextExtractionResult(
        source_sha256=text_result.source_sha256,
        method=ExtractionMethod.OCR,
        pages=tuple(
            ExtractedPDFPage(page_number=page.page_number, text=page.text)
            for page in ocr_result.pages
        ),
        quality_flags=tuple(
            dict.fromkeys((*text_result.quality_flags, *ocr_result.quality_flags))
        ),
        notes=f"OCR fallback applied with {ocr_result.engine_name}.",
    )


def _count_declared_pages(pdf_bytes: bytes) -> int:
    page_markers = re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    return len(page_markers)


def _extract_text_pages(pdf_bytes: bytes) -> tuple[str, ...]:
    pages: list[str] = []
    for stream in _iter_streams(pdf_bytes):
        text = _extract_text_from_stream(stream)
        if text.strip():
            pages.append(text)
    return tuple(pages)


def _iter_streams(pdf_bytes: bytes) -> tuple[bytes, ...]:
    streams: list[bytes] = []
    stream_pattern = re.compile(
        rb"<<(?P<dictionary>.*?)>>\s*stream\r?\n(?P<body>.*?)\r?\nendstream", re.S
    )
    for match in stream_pattern.finditer(pdf_bytes):
        dictionary = match.group("dictionary")
        body = match.group("body")
        if b"/FlateDecode" in dictionary:
            try:
                body = zlib.decompress(body)
            except zlib.error:
                continue
        streams.append(body)
    return tuple(streams)


def _extract_text_from_stream(stream: bytes) -> str:
    if not _looks_like_text_stream(stream):
        return ""
    strings = [
        _decode_pdf_literal(match.group(1)) for match in _literal_re().finditer(stream)
    ]
    return "\n".join(text for text in strings if text.strip())


def _looks_like_text_stream(stream: bytes) -> bool:
    return any(operator in stream for operator in (b"Tj", b"TJ", b"'", b'"'))


def _literal_re() -> re.Pattern[bytes]:
    return re.compile(rb"\(((?:\\.|[^\\()])*)\)")


def _decode_pdf_literal(value: bytes) -> str:
    replacements = {
        b"\\n": b"\n",
        b"\\r": b"\r",
        b"\\t": b"\t",
        b"\\b": b"\b",
        b"\\f": b"\f",
        b"\\(": b"(",
        b"\\)": b")",
        b"\\\\": b"\\",
    }
    decoded = value
    for needle, replacement in replacements.items():
        decoded = decoded.replace(needle, replacement)
    return decoded.decode("utf-8", errors="replace")


def _quality_flags(
    *,
    declared_page_count: int,
    extracted_pages: tuple[ExtractedPDFPage, ...],
) -> tuple[str, ...]:
    flags: list[str] = []
    if extracted_pages:
        flags.append("text_layer_extracted")
        flags.append("ocr_not_needed")
    else:
        flags.append("no_text_layer")
        flags.append("ocr_recommended")
        flags.append("empty_text")
    if declared_page_count and declared_page_count != len(extracted_pages):
        flags.append("page_count_mismatch")
    if declared_page_count:
        flags.append("declared_page_count_detected")
    return tuple(flags)


def _require_sha256(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("source_sha256 must be a lowercase SHA-256 hex digest")
