from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_acquisition_doc_covers_operator_contract() -> None:
    doc = (ROOT / "docs" / "acquisition.md").read_text(encoding="utf-8")

    for expected in (
        "does not yet publish a live benchmark corpus",
        "Development and CI must stay offline by default",
        "acquisition plan",
        "download-free",
        "purchase-missing",
        "parse-documents",
        "build-packets",
        "CASE_DEV_API_KEY",
        "missing core documents",
        "Federal district courts",
    ):
        assert expected in doc


def test_readme_links_acquisition_doc() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/acquisition.md" in readme
    assert "uv run legalforecast acquisition --help" in readme
