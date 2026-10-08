"""The papers' LAB human-review counts stay in sync with the review worksheet."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
LFB_PAPER = ROOT / "docs/papers/legalforecastbench/LegalForecastBench-paper.tex"
LAB_PAPER = ROOT / "docs/papers/lab-audit/LAB-audit-paper.tex"


def _load() -> ModuleType:
    path = ROOT / "docs/papers/lab-audit/analysis/lab_review.py"
    spec = importlib.util.spec_from_file_location("lab_review", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lab_review = _load()


@pytest.mark.parametrize("manuscript", [LFB_PAPER, LAB_PAPER], ids=lambda p: p.stem)
def test_manuscript_blocks_match_the_worksheet(
    monkeypatch: pytest.MonkeyPatch, manuscript: Path
) -> None:
    monkeypatch.chdir(ROOT)
    assert lab_review.main(["--check", "--manuscript", str(manuscript)]) == 0


def test_the_forecasting_paper_carries_only_the_numbers() -> None:
    text = LFB_PAPER.read_text(encoding="utf-8")
    assert "% BEGIN GENERATED LAB REVIEW NUMBERS" in text
    assert "% BEGIN GENERATED LAB REVIEW TABLE" not in text
    assert "\\labitem{" not in text


def test_entry_verdicts_must_agree_with_the_worksheet() -> None:
    manuscript = LAB_PAPER.read_text(encoding="utf-8")
    assert lab_review.entry_mismatches(manuscript) == []
    edited = manuscript.replace(
        "Task environment & Correct", "Task environment & Defective: changed", 1
    )
    assert lab_review.entry_mismatches(edited) == [
        "entry 2: environment verdict is not 'Correct'"
    ]


def test_a_manuscript_without_any_block_is_an_error(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text("No generated blocks here.\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no % BEGIN GENERATED"):
        lab_review.main(["--check", "--manuscript", str(manuscript)])


def test_write_fills_only_the_blocks_present(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(
        "% BEGIN GENERATED LAB REVIEW NUMBERS\n"
        "% END GENERATED LAB REVIEW NUMBERS\n"
        "Prose cites \\labDefectiveShare.\n",
        encoding="utf-8",
    )
    assert lab_review.main(["--check", "--manuscript", str(manuscript)]) == 1
    assert lab_review.main(["--write-manuscript", "--manuscript", str(manuscript)]) == 0
    text = manuscript.read_text(encoding="utf-8")
    assert "\\newcommand{\\labDefectiveShare}" in text
    assert "LAB REVIEW TABLE" not in text
    assert lab_review.main(["--check", "--manuscript", str(manuscript)]) == 0
