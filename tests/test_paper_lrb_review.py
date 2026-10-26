"""The LAB paper's LegalReasonBench review appendix stays in sync with its worksheet."""

from __future__ import annotations

import functools
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAB_PAPER = ROOT / "docs/papers/lab-audit/LAB-audit-paper.tex"
NUMBERS = "% BEGIN GENERATED LRB REVIEW NUMBERS\n% END GENERATED LRB REVIEW NUMBERS\n"
LSQUO, RSQUO = "\N{LEFT SINGLE QUOTATION MARK}", "\N{RIGHT SINGLE QUOTATION MARK}"
MINUS = "\N{MINUS SIGN}"


def _load() -> ModuleType:
    path = ROOT / "docs/papers/lab-audit/analysis/lrb_review.py"
    spec = importlib.util.spec_from_file_location("lrb_review", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lrb_review = _load()


@functools.cache
def _parsed() -> tuple[Any, list[Any]]:
    sampler, _model_runs, _lab_review = lrb_review._scripts()
    return sampler, lrb_review.items(sampler)


def test_the_lab_paper_matches_the_worksheet_from_any_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert lrb_review.main(["--check", "--manuscript", str(LAB_PAPER)]) == 0


def test_numbers_and_table_follow_the_worksheet() -> None:
    sampler, parsed = _parsed()
    stats = lrb_review.statistics(sampler, parsed)
    assert (stats["population"], stats["sample"]) == (63, 25)
    assert (stats["defective"], stats["arguable"], stats["not_defective"]) == (21, 0, 4)
    assert (stats["objective"], stats["judgment"], stats["from_env"]) == (7, 14, 6)
    assert (stats["env_items"], stats["env_assignments"]) == (12, 5)
    assert (stats["defective_point"], stats["defective_lb"]) == (53, 45)
    assert (stats["objective_point"], stats["objective_lb"]) == (18, 11)
    assert (stats["both_flagged"], stats["both_defective"]) == (12, 12)
    table = lrb_review.render_table(stats, parsed)
    assert "Defective & 10 & 11 & 21\\\\" in table
    assert "Total & 12 & 13 & 25\\\\" in table
    assert "Unresolved" not in table


def test_a_stale_numbers_block_fails_the_check_until_rewritten(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(
        NUMBERS.replace("\n% END", "\n\\newcommand{\\lrbDefective}{20}\n% END"),
        encoding="utf-8",
    )
    assert lrb_review.main(["--check", "--manuscript", str(manuscript)]) == 1
    assert lrb_review.main(["--write-manuscript", "--manuscript", str(manuscript)]) == 0
    text = manuscript.read_text(encoding="utf-8")
    assert "\\newcommand{\\lrbDefective}{21}" in text
    assert "\\newcommand{\\lrbDefectiveLB}{45}" in text
    assert lrb_review.main(["--check", "--manuscript", str(manuscript)]) == 0


def test_entry_verdicts_must_agree_with_the_worksheet() -> None:
    _sampler, parsed = _parsed()
    manuscript = LAB_PAPER.read_text(encoding="utf-8")
    assert lrb_review.entry_mismatches(manuscript, parsed) == []
    first = manuscript.index("\\lrbitem{1}")
    head, tail = manuscript[:first], manuscript[first:]
    edits = {
        "Defective --- unambiguous objective error": (
            "Defective --- professional judgment",
            "entry 1: defect basis is not 'Unambiguous objective error'",
        ),
        "does not arise from the task environment": (
            "arises from the task environment",
            "entry 1: defect origin is not 'No' (arises from the task environment)",
        ),
        "Task environment & Correct": (
            "Task environment & Defective: changed",
            "entry 1: environment verdict is not 'Correct'",
        ),
        "Criterion & Defective ---": (
            "Criterion & Not defective ---",
            "entry 1: rubric verdict is not 'Defective'",
        ),
    }
    for old, (new, problem) in edits.items():
        edited = head + tail.replace(old, new, 1)
        assert lrb_review.entry_mismatches(edited, parsed) == [problem]


def test_check_fails_when_an_entry_disagrees(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    text = LAB_PAPER.read_text(encoding="utf-8")
    first = text.index("\\lrbitem{2}")
    manuscript.write_text(
        text[:first]
        + text[first:].replace("Criterion & Defective", "Criterion & Arguable", 1),
        encoding="utf-8",
    )
    assert lrb_review.main(["--check", "--manuscript", str(manuscript)]) == 1


def test_seeding_fills_an_empty_region_once(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(
        NUMBERS + f"{lrb_review.ENTRIES_BEGIN}\n{lrb_review.ENTRIES_END}\n",
        encoding="utf-8",
    )
    assert lrb_review.main(["--check", "--manuscript", str(manuscript)]) == 1
    assert lrb_review.main(["--seed-entries", "--manuscript", str(manuscript)]) == 0
    seeded = manuscript.read_text(encoding="utf-8")
    assert seeded.count("\\lrbitem{") == 25
    assert seeded.count("% BEGIN AI-PREPARED") == seeded.count("% END AI-PREPARED")
    assert lrb_review.main(["--write-manuscript", "--manuscript", str(manuscript)]) == 0
    assert lrb_review.main(["--check", "--manuscript", str(manuscript)]) == 0


def test_seeding_never_overwrites_hand_edits(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.tex"
    region = f"{lrb_review.ENTRIES_BEGIN}\nA hand edit.\n{lrb_review.ENTRIES_END}\n"
    manuscript.write_text(NUMBERS + region, encoding="utf-8")
    with pytest.raises(SystemExit, match="refuses to overwrite"):
        lrb_review.main(["--seed-entries", "--manuscript", str(manuscript)])
    assert manuscript.read_text(encoding="utf-8") == NUMBERS + region


def test_markdown_note_converts_to_latex_without_rewording() -> None:
    note = (
        'The award says "two of four" and _Douglas v. VA_, 5 M.S.P.R. 280, '
        "*held* the burden is on the agency (§ 7513; ¶ 7) — see "
        "[the order](https://example.org/a%20b#p4) and "
        "[run](../model-runs/x/response.md). It said “[i]f” and "
        f"{LSQUO}no{RSQUO} at 60.5% for `criterion_4`, a {MINUS}15 penalty & "
        "'ops' notes."
    )
    assert lrb_review.tex(note) == (
        "The award says ``two of four'' and \\emph{Douglas v. VA}, 5 M.S.P.R. 280, "
        "\\emph{held} the burden is on the agency (§ 7513; ¶ 7) — see "
        "\\href{https://example.org/a\\%20b\\#p4}{the order} and "
        "\\href{https://github.com/johnhughes3/LegalForecastBench/blob/main/"
        "docs/legalreasonbench-audit/litigation/model-runs/x/response.md}{run}. "
        f"It said “[i]f” and {LSQUO}no{RSQUO} at 60.5\\% for "
        "\\texttt{criterion\\_\\allowbreak{}4}, a $-$15 penalty \\& `ops' notes."
    )


def test_untypesettable_characters_fail_loudly() -> None:
    with pytest.raises(SystemExit, match="untypeset"):
        lrb_review.tex("a snowman \u2603")


def test_note_splits_analysis_paragraphs_from_source_bullets() -> None:
    analysis, sources = lrb_review._note(
        "First paragraph.\n\n  Second paragraph.\n- Sources: a.\n- Native runs: b."
    )
    assert analysis == ["First paragraph.", "Second paragraph."]
    assert sources == ["Sources: a.", "Native runs: b."]
