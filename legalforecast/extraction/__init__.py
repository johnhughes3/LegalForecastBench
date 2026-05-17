"""Document extraction and text normalization."""

from legalforecast.extraction.normalize_text import (
    NormalizedText,
    normalize_extracted_text,
)
from legalforecast.extraction.ocr import OCRPage, OCRResult, run_ocr_fallback
from legalforecast.extraction.pdf_text import (
    ExtractedPDFPage,
    ExtractionMethod,
    PDFExtractionError,
    PDFTextExtractionResult,
    extract_pdf_text,
    extract_pdf_text_with_ocr_fallback,
)

__all__ = [
    "ExtractedPDFPage",
    "ExtractionMethod",
    "NormalizedText",
    "OCRPage",
    "OCRResult",
    "PDFExtractionError",
    "PDFTextExtractionResult",
    "extract_pdf_text",
    "extract_pdf_text_with_ocr_fallback",
    "normalize_extracted_text",
    "run_ocr_fallback",
]
