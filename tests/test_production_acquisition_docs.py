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
