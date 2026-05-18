"""OCR fallback interfaces for extracted court filings."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from legalforecast.extraction.normalize_text import normalize_extracted_text


@dataclass(frozen=True, slots=True)
class OCRPage:
    """One page returned by an OCR engine."""

    page_number: int
    text: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.page_number <= 0:
            raise ValueError("page_number must be positive")
        if not 0 <= (self.confidence if self.confidence is not None else 1) <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class OCRResult:
    """Normalized OCR fallback output and quality flags."""

    pages: tuple[OCRPage, ...]
    source_sha256: str
    quality_flags: tuple[str, ...]
    engine_name: str = "unknown"

    def __post_init__(self) -> None:
        _require_sha256(self.source_sha256)
        if not self.engine_name.strip():
            raise ValueError("engine_name is required")
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
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


OCREngine = Callable[[bytes], OCRResult]


def run_ocr_fallback(
    document_bytes: bytes,
    *,
    engine: OCREngine | None = None,
    engine_name: str = "unavailable",
) -> OCRResult:
    """Run an injected OCR engine or return an explicit unavailable result."""

    source_sha256 = hashlib.sha256(document_bytes).hexdigest()
    if engine is None:
        return OCRResult(
            pages=(),
            source_sha256=source_sha256,
            quality_flags=("ocr_engine_unavailable",),
            engine_name=engine_name,
        )

    result = engine(document_bytes)
    if result.source_sha256 != source_sha256:
        raise ValueError("OCR result source hash does not match input document")

    normalized_pages = tuple(
        OCRPage(
            page_number=page.page_number,
            text=normalize_extracted_text(page.text).text,
            confidence=page.confidence,
        )
        for page in result.pages
    )
    return OCRResult(
        pages=normalized_pages,
        source_sha256=result.source_sha256,
        quality_flags=tuple(
            dict.fromkeys(("ocr_applied", *result.quality_flags)).keys()
        ),
        engine_name=result.engine_name,
    )


def _require_sha256(value: str) -> None:
    if not re_fullmatch_sha256(value):
        raise ValueError("source_sha256 must be a lowercase SHA-256 hex digest")


def re_fullmatch_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
