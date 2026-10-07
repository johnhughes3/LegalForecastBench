"""The Pangram check sends only the author-written prose of the working paper."""

from __future__ import annotations

import functools
import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "docs/paper/LegalForecastBench-paper.tex"

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc is not installed"
)

FIXTURE = r"""\documentclass{article}
\newcommand{\labFlagged}{835}
\newcommand{\labitem}[3]{\subsubsection*{#1. #2 (#3)}}
\begin{document}
\begin{abstract}
The auditors flagged \labFlagged{} criteria.
\end{abstract}
\section{Introduction}
Outcome feedback works \citep{alpha,beta}. It also scales. \citep[p.~2]{gamma}.
A claim.\footnote{The footnote is prose.} See Table~\ref{tab:x} for \textbf{bold}
and \emph{emphasis}. % a source comment
\begin{table}\begin{tabular}{l}Secret row\\\end{tabular}
\caption{Hidden caption.}\label{tab:x}\end{table}
The reward is
\begin{equation} p = q \end{equation}
for valid output.
\section{Methods}
% BEGIN AI-PREPARED (disclosed)
Protocol prose.
% BEGIN GENERATED CLUSTERING
Generated sentence.
% END GENERATED CLUSTERING
% END AI-PREPARED
\section{Discussion}
Discussion prose.
% BEGIN AI-PREPARED
Assistant paragraph.
% END AI-PREPARED
Author again.
\section*{AI use disclosure}
Disclosure prose.
\begin{thebibliography}{9}
\bibitem{alpha} Bibliography entry.
\end{thebibliography}
\appendix
\section{Review}
\labitem{1}{Harvey Task Title}{C-049}
\begin{labquote}{Harvey LAB}Quoted rubric.\end{labquote}

\noindent\begin{tabular}{ll}Criterion & Defective\\\end{tabular}

\noindent\textbf{My analysis.} The rubric is wrong.
\end{document}
"""


def _load() -> ModuleType:
    path = ROOT / "docs/paper/analysis/pangram_check.py"
    spec = importlib.util.spec_from_file_location("pangram_check", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pangram_check = _load()
GAP = pangram_check.OMITTED


@functools.cache
def _paper() -> str:
    """The document the check would send for the real manuscript."""
    units = pangram_check.manuscript_units(MANUSCRIPT.read_text(encoding="utf-8"))
    return pangram_check.document(units)[0]


def _fixture(tex: str = FIXTURE) -> dict[str, Any]:
    return {u.key: u for u in pangram_check.manuscript_units(tex)}


def test_disclosed_sections_are_left_out_and_shown_as_omitted() -> None:
    paper = _paper()
    assert "3. LegalForecastBench: Dataset and evaluation protocol\n\n[...]" in paper
    assert "4. Results\n\n[...]\n\n5. " in paper
    assert "micro-Brier" not in paper.split("4. Results")[1].split("5. ")[0]


def test_harvey_text_is_left_out_and_the_authors_analysis_is_kept() -> None:
    paper = _paper()
    assert "Calculates budget overage percentage" not in paper
    assert "Assess Reasonableness of Staffing Levels" not in paper
    assert "Sonnet 4.6 judge: " not in paper
    assert "1. [...] (C-049)" in paper
    assert "internally inconsistent" in paper


def test_non_prose_and_markup_do_not_leak() -> None:
    paper = _paper()
    for leaked in ("Cohort-rate reference", "bibitem", "\\draw", "TODO", "\\cite"):
        assert leaked not in paper
    assert "PANGRAMOMISSION" not in paper
    assert f"{GAP}\n\n{GAP}" not in paper


def test_preamble_macros_are_expanded() -> None:
    assert "2,858" in _paper()


def test_fixture_segmentation_and_cleaning() -> None:
    units = _fixture()
    assert list(units) == ["abstract", "1", "2", "3", "-", "A"]
    assert units["abstract"].text == "The auditors flagged 835 criteria."
    intro = units["1"].text
    assert intro.startswith("Outcome feedback works. It also scales.")
    assert "bold and emphasis." in intro
    assert f"The reward is\n\n{GAP}\n\nfor valid output." in intro
    assert intro.endswith("The footnote is prose.")
    for hidden in ("Secret row", "Hidden caption", "source comment", "alpha"):
        assert hidden not in intro
    assert units["2"].text == GAP and units["2"].words == 0
    assert units["3"].text == f"Discussion prose.\n\n{GAP}\n\nAuthor again."
    assert units["-"].text == f"Disclosure prose.\n\n{GAP}"
    assert units["A"].text == (
        f"1. {GAP} (C-049)\n\n{GAP}\n\nMy analysis. The rubric is wrong."
    )


def test_unpaired_marker_fails() -> None:
    broken = FIXTURE.replace("% END AI-PREPARED\nAuthor again.", "Author again.")
    with pytest.raises(SystemExit, match="AI-PREPARED"):
        pangram_check.manuscript_units(broken)


def test_exclude_section_replaces_the_section_with_an_omission() -> None:
    units = pangram_check.manuscript_units(FIXTURE)
    kept = {u.key: u for u in pangram_check.exclude(units, ["review"])}
    assert kept["A"].text == GAP and kept["A"].excluded
    assert kept["1"].text == units[1].text
    with pytest.raises(SystemExit, match="matches no section"):
        pangram_check.exclude(units, ["nonexistent"])


def test_extract_only_needs_no_key_and_reports_what_was_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(pangram_check.KEY_VARIABLE, raising=False)
    monkeypatch.setattr(pangram_check, "MIN_WORDS", 3)
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(FIXTURE, encoding="utf-8")
    out = tmp_path / "out"
    arguments = ["--manuscript", str(manuscript), "--out", str(out)]

    assert pangram_check.main([*arguments, "--extract-only"]) == 0
    printed = capsys.readouterr().out
    assert "nothing sent (all of it is left out)" in printed
    assert "not a check of the whole paper" in printed
    sent = (out / "paper.txt").read_text(encoding="utf-8")
    assert sent.startswith("Abstract\n\nThe auditors flagged 835 criteria.")
    assert "Protocol prose" not in sent and "Assistant paragraph" not in sent
    assert not (out / "response.json").exists()

    with pytest.raises(SystemExit, match=pangram_check.KEY_VARIABLE):
        pangram_check.main(arguments)


def test_one_document_is_scored_and_windows_are_reported_by_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stub stands in for Pangram, returning the documented response shape."""
    sent: list[str] = []

    class Stub:
        def predict(self, text: str, *, model: str) -> dict[str, Any]:
            sent.append(text)
            return {
                "headline": "AI Assisted",
                "prediction_short": "Mixed",
                "fraction_ai": 0.0,
                "fraction_ai_assisted": 0.4,
                "fraction_human": 0.6,
                "windows": [
                    {"text": "Outcome feedback works.", "label": "Human Written"},
                    {"text": "Discussion prose.", "label": "AI-Assisted"},
                    {"text": "My analysis. The rubric", "label": "Human Written"},
                ],
            }

    monkeypatch.setenv(pangram_check.KEY_VARIABLE, "placeholder")
    monkeypatch.setattr(pangram_check, "_client", Stub)
    monkeypatch.setattr(pangram_check, "MIN_WORDS", 3)
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(FIXTURE, encoding="utf-8")
    out = tmp_path / "out"

    arguments = ["--manuscript", str(manuscript), "--out", str(out), "--verbose"]
    assert pangram_check.main(arguments) == 0
    printed = capsys.readouterr().out
    assert len(sent) == 1
    assert "Whole document: AI Assisted [Mixed]" in printed
    assert "1 of 3 windows flagged" in printed
    rows = {line.split()[0]: line for line in printed.splitlines() if line.strip()}
    assert "0 of 1 windows flagged" in rows["1"]
    assert "1 of 1 windows flagged" in rows["3"]
    assert "0 of 1 windows flagged" in rows["A"]
    assert "[3] AI-Assisted" in printed and "Discussion prose." in printed
    assert "placeholder" not in printed
    saved = json.loads((out / "response.json").read_text(encoding="utf-8"))
    assert saved["prediction_short"] == "Mixed"


def test_cost_ceiling_refuses_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Refuse:
        def predict(self, text: str, *, model: str) -> dict[str, Any]:
            raise AssertionError("no request may be sent over the ceiling")

    monkeypatch.setenv(pangram_check.KEY_VARIABLE, "placeholder")
    monkeypatch.setattr(pangram_check, "_client", Refuse)
    monkeypatch.setattr(pangram_check, "MIN_WORDS", 3)
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(FIXTURE, encoding="utf-8")
    arguments = ["--manuscript", str(manuscript), "--out", str(tmp_path / "out")]
    with pytest.raises(SystemExit, match="exceeds --max-usd"):
        pangram_check.main([*arguments, "--max-usd", "0"])


def test_draft_notes_are_not_scored() -> None:
    marked = FIXTURE.replace(
        "Discussion prose.",
        r"Discussion prose.\checkcite{; confirm this source} "
        r"\draft{[[Placeholder: results to come]]}",
    )
    text = {u.key: u for u in pangram_check.manuscript_units(marked)}["3"].text
    assert "confirm this source" not in text
    assert "Placeholder" not in text
    assert text.startswith(f"Discussion prose.\n\n{GAP}")


def test_saved_response_is_reported_and_gated_without_a_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(pangram_check.KEY_VARIABLE, raising=False)
    monkeypatch.setattr(pangram_check, "MIN_WORDS", 3)

    def refuse() -> Any:
        raise AssertionError("a saved response must not call Pangram")

    monkeypatch.setattr(pangram_check, "_client", refuse)
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text(FIXTURE, encoding="utf-8")
    response = tmp_path / "saved.json"
    response.write_text(
        json.dumps(
            {
                "headline": "Mostly Human Written",
                "prediction_short": "Human",
                "fraction_ai": 0.04,
                "fraction_ai_assisted": 0.0,
                "fraction_human": 0.96,
                "windows": [{"text": "Discussion prose.", "label": "AI-Generated"}],
            }
        ),
        encoding="utf-8",
    )
    arguments = [
        "--manuscript",
        str(manuscript),
        "--out",
        str(tmp_path / "out"),
        "--response",
        str(response),
    ]
    assert pangram_check.main([*arguments, "--fail-above", "0.10"]) == 0
    assert "PASS: Pangram classifies 0.04" in capsys.readouterr().out
    assert pangram_check.main([*arguments, "--fail-above", "0.02"]) == 1
    assisted = json.loads(response.read_text(encoding="utf-8"))
    assisted.update(fraction_ai=0.0, fraction_ai_assisted=0.05, fraction_human=0.95)
    response.write_text(json.dumps(assisted), encoding="utf-8")
    assert pangram_check.main([*arguments, "--fail-above", "0.03"]) == 1
    assert "FAIL: Pangram classifies 0.04" in capsys.readouterr().out
