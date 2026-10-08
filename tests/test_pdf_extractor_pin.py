"""Keep public-release PDF extraction on a reviewed, patched version."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pypdf

PINNED_PDF_EXTRACTOR_VERSION = "6.19.0"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_pdf_text_extractor_stays_on_the_reviewed_version() -> None:
    """Changing extractors can change model-visible text for identical bytes.

    Legacy disclosure acquisition/replay moved to LegalForecastCorpus. The
    public package retains an exact pin for reproducible release extraction,
    using a version patched for the PDF denial-of-service advisories.
    """
    assert pypdf.__version__ == PINNED_PDF_EXTRACTOR_VERSION


def test_pyproject_pins_the_extractor_exactly_rather_than_flooring_it() -> None:
    """Extractor changes require review, including their text-extraction effects."""
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    assert f"pypdf=={PINNED_PDF_EXTRACTOR_VERSION}" in dependencies
