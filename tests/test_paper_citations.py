"""Each paper cites exactly what its bibliography lists, and nothing else.

The LaTeX build already fails on a citation with no bibliography entry. This
also catches the reverse, an entry the text never cites, and keeps each
paper's ``references.json`` metadata in step with its bibliography. It needs
no TeX, so it runs with the ordinary test suite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PAPERS = Path(__file__).resolve().parents[1] / "docs" / "papers"
CITE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")
BIBITEM = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}")
COMMENT = re.compile(r"(?<!\\)%.*")


def citations(tex: str) -> tuple[set[str], list[str]]:
    """Cited keys and bibliography keys, ignoring commented-out text."""
    text = "\n".join(COMMENT.sub("", line) for line in tex.splitlines())
    cited = {
        key.strip()
        for match in CITE.finditer(text)
        for key in match.group(1).split(",")
        if key.strip()
    }
    return cited, [key.strip() for key in BIBITEM.findall(text)]


MANUSCRIPTS = sorted(PAPERS.glob("*/*-paper.tex"))


def test_every_paper_is_checked() -> None:
    assert {path.parent.name for path in MANUSCRIPTS} >= {
        "legalforecastbench",
        "lab-audit",
    }


@pytest.mark.parametrize("manuscript", MANUSCRIPTS, ids=lambda p: p.parent.name)
def test_citations_and_bibliography_match(manuscript: Path) -> None:
    cited, listed = citations(manuscript.read_text(encoding="utf-8"))
    duplicates = sorted({key for key in listed if listed.count(key) > 1})
    assert duplicates == [], "listed more than once in the bibliography"
    assert sorted(cited - set(listed)) == [], "cited but not in the bibliography"
    assert sorted(set(listed) - cited) == [], "in the bibliography but never cited"
    references = manuscript.parent / "references.json"
    keys = [entry["key"] for entry in json.loads(references.read_text("utf-8"))]
    assert sorted(set(keys) ^ set(listed)) == [], (
        "references.json and the bibliography list different keys"
    )


def test_the_parser_reads_options_lists_and_comments() -> None:
    cited, listed = citations(
        r"""
See \citep[p.~16]{alpha, beta} and \citet{gamma}.
Accuracy was 84.5\% \citealp{delta}. % \cite{commented} is ignored
% \citep{whole_line_comment}
\begin{thebibliography}{9}
\bibitem{alpha} A.
\bibitem[Beta(2020)]{beta} B.
\end{thebibliography}
"""
    )
    assert cited == {"alpha", "beta", "gamma", "delta"}
    assert listed == ["alpha", "beta"]
