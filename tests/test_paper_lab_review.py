"""The paper's LAB human-review counts stay in sync with the review worksheet."""

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


def test_entry_verdicts_must_agree_with_the_worksheet() -> None:
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    assert lab_review.entry_mismatches(manuscript) == []
    edited = manuscript.replace(
        "Task environment & Correct", "Task environment & Defective: changed", 1
    )
    assert lab_review.entry_mismatches(edited) == [
        "entry 2: environment verdict is not 'Correct'"
    ]
