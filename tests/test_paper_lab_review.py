"""The paper's LAB human-review appendix stays in sync with the review worksheet."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "docs/paper/LegalForecastBench-paper.tex"


def _load() -> ModuleType:
    path = ROOT / "docs/paper/analysis/lab_review.py"
    spec = importlib.util.spec_from_file_location("lab_review", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lab_review = _load()


def test_manuscript_blocks_match_the_worksheet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    assert lab_review.main(["--check", "--manuscript", str(MANUSCRIPT)]) == 0


def test_tex_escapes_markdown_and_specials() -> None:
    text = 'Costs $14,200 & 17% of *Daubert* "rule" at https://example.com/a_b.'
    assert lab_review.tex(text) == (
        r"Costs \$14,200 \& 17\% of \emph{Daubert} ``rule'' at "
        r"\url{https://example.com/a_b}."
    )


def test_tex_rejects_characters_pdflatex_cannot_set() -> None:
    with pytest.raises(SystemExit):
        lab_review.tex("emoji \U0001f600")
