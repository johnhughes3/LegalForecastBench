from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_docs_use_consolidated_acquisition_reference() -> None:
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    acquisition = (ROOT / "docs" / "acquisition.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Acquisition" in docs_index
    assert "no-paid defaults" in readme
    assert "Live or paid acquisition must be explicitly opted in" in acquisition
    assert "fixture leaderboard is a synthetic smoke artifact" in acquisition


def test_acquisition_doc_owns_official_readiness_gate() -> None:
    acquisition = (ROOT / "docs" / "acquisition.md").read_text(encoding="utf-8")

    for expected in (
        "complete packet retrieval, not just credentials",
        "discovery-first surface",
        "CourtListener/RECAP/PACER fallback reconstruction",
        "reviewed or retained packets, not search hits",
        "at least 50 clean packets",
        "credible path to 50-100 clean packets",
        "separate discovery, fallback reconstruction, and live purchase cost totals",
    ):
        assert expected in acquisition
