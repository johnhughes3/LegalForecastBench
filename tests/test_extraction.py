from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from legalforecast.extraction import (
    ExtractionMethod,
    OCRPage,
    OCRResult,
    PDFExtractionError,
    extract_pdf_text,
    extract_pdf_text_with_ocr_fallback,
    normalize_extracted_text,
)


def _pdf_with_streams(*streams: str) -> bytes:
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        f"2 0 obj << /Type /Pages /Count {len(streams)} /Kids [] >> endobj",
    ]
    for index, stream in enumerate(streams, start=3):
        body = stream.encode("utf-8")
        objects.append(
            f"{index} 0 obj << /Type /Page /Contents {index + 20} 0 R >> endobj"
        )
        objects.append(
            f"{index + 20} 0 obj << /Length {len(body)} >> stream\n"
            f"{stream}\n"
            "endstream endobj"
        )
    return ("%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF").encode("utf-8")


def _text_stream(text: str) -> str:
    return f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"


def test_pdf_text_extraction_preserves_pages_and_hashes() -> None:
    pdf_bytes = _pdf_with_streams(
        _text_stream("Motion to dismiss Count I."),
        _text_stream("Opposition says Count II survives."),
    )

    result = extract_pdf_text(pdf_bytes)

    assert result.source_sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    assert result.method is ExtractionMethod.PDF_TEXT
    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Motion to dismiss Count I." in result.text
    assert "\f" in result.text
    assert "text_layer_extracted" in result.quality_flags
    assert "ocr_not_needed" in result.quality_flags


def test_pdf_text_artifact_matches_provenance_schema() -> None:
    result = extract_pdf_text(_pdf_with_streams(_text_stream("Complaint text.")))

    artifact = result.to_text_artifact(
        source_document_id="doc-12",
        extracted_at=datetime(2026, 5, 14, 13, 0, tzinfo=UTC),
    )
    record = artifact.to_record()

    assert record["source_document_id"] == "doc-12"
    assert record["extraction_method"] == "pdf_text"
    assert record["text_sha256"] == result.text_sha256
    assert record["page_count"] == 1
    assert record["quality_flags"] == list(result.quality_flags)


def test_scanned_pdf_uses_injected_ocr_fallback() -> None:
    scanned_pdf = _pdf_with_streams("q 100 0 0 100 0 0 cm /Im1 Do Q")

    def fake_ocr(document_bytes: bytes) -> OCRResult:
        return OCRResult(
            pages=(OCRPage(page_number=1, text="Scanned m0t10n t0 dism1ss."),),
            source_sha256=hashlib.sha256(document_bytes).hexdigest(),
            quality_flags=("synthetic_ocr_fixture",),
            engine_name="fixture-ocr",
        )

    result = extract_pdf_text_with_ocr_fallback(scanned_pdf, ocr_engine=fake_ocr)

    assert result.method is ExtractionMethod.OCR
    assert result.page_count == 1
    assert result.text == "Scanned motion to dismiss."
    assert "no_text_layer" in result.quality_flags
    assert "ocr_applied" in result.quality_flags
    assert "synthetic_ocr_fixture" in result.quality_flags
    assert result.notes == "OCR fallback applied with fixture-ocr."


def test_empty_text_layer_reports_quality_flags_without_ocr_engine() -> None:
    result = extract_pdf_text_with_ocr_fallback(
        _pdf_with_streams("q 100 0 0 100 0 0 cm /Im1 Do Q")
    )

    assert result.method is ExtractionMethod.PDF_TEXT
    assert result.text == ""
    assert result.page_count == 0
    assert "no_text_layer" in result.quality_flags
    assert "ocr_recommended" in result.quality_flags
    assert "ocr_engine_unavailable" in result.quality_flags


def test_malformed_document_is_rejected() -> None:
    with pytest.raises(PDFExtractionError, match="PDF header"):
        extract_pdf_text(b"not a pdf")


def test_normalization_repairs_common_ocr_noise_and_whitespace() -> None:
    result = normalize_extracted_text(
        "  Defendant's   m0t10n   t0   dism1ss\r\n\r\nCount I.  "
    )

    assert result.text == "Defendant's motion to dismiss\nCount I."
    assert "whitespace_normalized" in result.quality_flags
    assert "ocr_noise_repaired" in result.quality_flags
    assert result.line_count == 2
