"""Score the author-written prose of the working paper with Pangram's AI-text detector.

The command renders the manuscript to the plain text a reader sees and sends it to
Pangram as one document. Text the author did not write is left out, and every
omission is shown as ``[...]`` so the document does not pretend to be complete:

* passages between ``% BEGIN AI-PREPARED`` and ``% END AI-PREPARED`` comment lines in
  the manuscript source, which mark what the paper's AI-use statement discloses as
  prepared with AI;
* criteria quoted from Harvey LAB (the ``labquote`` environment) and Harvey's task
  titles in the appendix headings;
* tables, figures, display equations, the bibliography, and blocks between
  ``% BEGIN GENERATED`` and ``% END GENERATED`` markers.

LaTeX commands and source comments never reach Pangram. The result is reported for
the whole document and for each section.

Scoring is opt-in and spends Pangram credits. It needs ``pandoc``, the Pangram SDK,
and an API key in the ``PANGRAM_API_KEY`` environment variable. Run from the
repository root::

    uv run --frozen python docs/paper/analysis/pangram_check.py --extract-only \\
        --manuscript docs/paper/LegalForecastBench-paper.tex
    uv run --frozen --with "pangram-sdk>=1.0" python \\
        docs/paper/analysis/pangram_check.py \\
        --manuscript docs/paper/LegalForecastBench-paper.tex

``--extract-only`` needs neither the SDK nor a key: it writes the exact document and
prints the section table, for inspection or for pasting into Pangram's web app.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "build" / "pangram"
KEY_VARIABLE = "PANGRAM_API_KEY"

# Pangram's published limits (docs/paper/README.md links the sources): a minimum
# input of 50 words, and 18,725 words per scan in the web app, which is used here
# as the per-request ceiling because the API documentation states none.
MIN_WORDS = 50
MAX_WORDS = 18_725
# Published realtime API rate: one billable block per started 100 words.
BLOCK_WORDS = 100
USD_PER_BLOCK = 0.05

TITLE_WIDTH = 44
# What a reader of the sent document sees where text was left out.
OMITTED = "[...]"
# Stands in for an omission until pandoc has run, so it survives as its own paragraph.
_GAP = "PANGRAMOMISSION"
AI_PREPARED = re.compile(
    r"(?ms)^% BEGIN AI-PREPARED\b[^\n]*\n.*?^% END AI-PREPARED[ \t]*$"
)
GENERATED_BLOCK = re.compile(
    r"(?ms)^% BEGIN GENERATED (.+?)[ \t]*$.*?^% END GENERATED \1[ \t]*$"
)
# Outer environments first, so a table is removed before the tabular inside it.
NON_PROSE_ENVIRONMENTS = (
    "thebibliography",
    "table",
    "figure",
    "longtable",
    "tikzpicture",
    "tabular",
    "labquote",
    "equation",
    "align",
    "gather",
    "multline",
    "eqnarray",
    "displaymath",
)
REMOVED = (
    "passages marked AI-prepared in the source; criteria and task titles quoted "
    "from Harvey LAB; tables, figures, and captions; display equations; the "
    "bibliography; generated blocks; and citations, cross-references, and URLs"
)
# A citation, with the space before it. The periods are captured so that
# "sentence. \citep{x}." does not leave two.
CITATION = re.compile(r"(\.?)[~\s]*\\cite[A-Za-z]*\*?(?:\[[^\]]*\])*\{[^}]*\}(\.?)")
REFERENCE = re.compile(r"[~\s]*\\(?:eq|page|auto|c|C)?ref\{[^}]*\}")
# pandoc's plain writer upper-cases bold text and underscores emphasis. The appendix
# heading macro carries Harvey's task title, which is not the author's text.
OVERRIDES = "\n".join(
    [
        *(
            rf"\renewcommand{{\{name}}}[1]{{#1}}"
            for name in ("textbf", "emph", "textit", "texttt", "textsc", "underline")
        ),
        rf"\renewcommand{{\labitem}}[3]{{\subsubsection*{{#1. {_GAP} (#3)}}}}",
    ]
)


class Unit(NamedTuple):
    """One section of the paper, as the plain text sent for it."""

    key: str
    title: str
    text: str
    excluded: str | None = None

    @property
    def words(self) -> int:
        return len(self.text.replace(OMITTED, " ").split())


def _closing_brace(text: str, opening: int) -> int:
    """Index of the brace that closes the one at ``opening``."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] in "{}" and text[index - 1 : index] != "\\":
            depth += 1 if text[index] == "{" else -1
            if depth == 0:
                return index
    raise SystemExit(f"unbalanced braces near: {text[opening : opening + 60]!r}")


def _take_commands(text: str, name: str) -> tuple[str, list[str]]:
    r"""Remove every ``\name[option]{argument}``; return the text and the arguments."""
    pattern = re.compile(rf"\\{name}(?![A-Za-z])\s*(?:\[[^\]]*\]\s*)*\{{")
    kept: list[str] = []
    arguments: list[str] = []
    position = 0
    while found := pattern.search(text, position):
        end = _closing_brace(text, found.end() - 1)
        kept.append(text[position : found.start()])
        arguments.append(text[found.end() : end])
        position = end + 1
    kept.append(text[position:])
    return "".join(kept), arguments


def _replace_commands(text: str, name: str, replacement: str) -> str:
    r"""Replace every ``\name{argument}`` with ``replacement``."""
    pattern = re.compile(rf"\\{name}(?![A-Za-z])\s*\{{")
    while found := pattern.search(text):
        end = _closing_brace(text, found.end() - 1)
        text = text[: found.start()] + replacement + text[end + 1 :]
    return text


def _tidy(text: str) -> str:
    """Drop URLs and list markers, show omissions, and collapse whitespace."""
    text = re.sub(r"https?://\S+", "", text).replace(_GAP, OMITTED)
    lines = [re.sub(r"^\s*-\s+", "", line) for line in text.splitlines()]
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Adjacent omissions read as one.
    gap = re.escape(OMITTED)
    return re.sub(rf"{gap}(?:\s*{gap})+", OMITTED, text)


def plain_latex(latex: str, macros: str) -> str:
    """Convert LaTeX to the plain prose a reader would see, with omissions marked."""
    gap = f"\n\n{_GAP}\n\n"
    latex = AI_PREPARED.sub(lambda _: gap, latex)
    latex = GENERATED_BLOCK.sub(lambda _: gap, latex)
    for environment in NON_PROSE_ENVIRONMENTS:
        name = rf"\{{{environment}\*?\}}"
        latex = re.sub(rf"(?s)\\begin{name}.*?\\end{name}", lambda _: gap, latex)
    latex = re.sub(r"(?s)(?<!\\)\\\[.*?\\\]|\$\$.*?\$\$", lambda _: gap, latex)
    for command in ("caption", "todo", "label", "url", "checkcite"):
        latex, _ = _take_commands(latex, command)
    # Provisional red-draft text is a placeholder, not finished prose.
    latex = _replace_commands(latex, "draft", gap)

    # A footnote is prose: it follows its section as a paragraph, without a marker.
    latex, footnotes = _take_commands(latex, "footnote")
    latex = "\n\n".join([latex, *footnotes])
    latex = CITATION.sub(
        lambda m: "." if m.group(1) and m.group(2) else m.group(1) + m.group(2), latex
    )
    latex = REFERENCE.sub("", latex)
    latex = re.sub(r"\s*\[\[cite\b.*?\]\]", "", latex)
    done = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "plain", "--wrap=none"],
        input=f"{macros}\n{OVERRIDES}\n\n{latex}",
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if done.returncode != 0:
        raise SystemExit(f"pandoc could not convert the manuscript: {done.stderr}")
    return _tidy(done.stdout)


def manuscript_units(tex: str) -> list[Unit]:
    """Split the manuscript into its abstract, sections, and appendix sections."""
    preamble, begin, rest = tex.partition(r"\begin{document}")
    if not begin:
        raise SystemExit(r"manuscript has no \begin{document}")
    macros = "\n".join(
        line for line in preamble.splitlines() if line.startswith(r"\newcommand")
    )
    body = rest.partition(r"\end{document}")[0]
    for kind, pattern in (("AI-PREPARED", AI_PREPARED), ("GENERATED", GENERATED_BLOCK)):
        opened, closed = body.count(f"% BEGIN {kind}"), body.count(f"% END {kind}")
        if not opened == closed == len(pattern.findall(body)):
            raise SystemExit(f"manuscript has an unpaired % BEGIN/END {kind} marker")

    units: list[Unit] = []
    abstract = re.search(r"(?s)\\begin\{abstract\}(.*?)\\end\{abstract\}", body)
    if abstract:
        units.append(Unit("abstract", "Abstract", plain_latex(abstract[1], macros)))

    appendix = re.search(r"(?m)^\\appendix\b", body)
    appendix_at = appendix.start() if appendix else len(body)
    headings = list(re.finditer(r"(?m)^\\section(\*?)\{", body))
    numbered = letters = 0
    for index, heading in enumerate(headings):
        title_end = _closing_brace(body, heading.end() - 1)
        title = plain_latex(body[heading.end() : title_end], macros)
        ends = [h.start() for h in headings[index + 1 :]] + [len(body)]
        if heading.start() < appendix_at:
            ends.append(appendix_at)
        if heading[1]:
            key = "-"
        elif heading.start() < appendix_at:
            numbered += 1
            key = str(numbered)
        else:
            key = chr(ord("A") + letters)
            letters += 1
        raw = body[title_end + 1 : min(ends)]
        units.append(Unit(key, title, plain_latex(raw, macros)))
    return units


def exclude(units: list[Unit], selectors: list[str]) -> list[Unit]:
    """Leave out the sections named by --exclude-section."""
    dropped: set[str] = set()
    for selector in selectors:
        wanted = selector.casefold()
        found = [u for u in units if u.key.casefold() == wanted] or [
            u for u in units if wanted in u.title.casefold()
        ]
        if not found:
            keys = ", ".join(u.key for u in units)
            raise SystemExit(
                f"--exclude-section {selector!r} matches no section (keys: {keys})"
            )
        dropped |= {u.key for u in found}
    return [
        u._replace(text=OMITTED, excluded="by --exclude-section")
        if u.key in dropped
        else u
        for u in units
    ]


def document(units: list[Unit]) -> tuple[str, list[tuple[int, int]]]:
    """The one text sent to Pangram, and each unit's character span within it."""
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    position = 0
    for unit in units:
        label = "" if unit.key in ("abstract", "-") else f"{unit.key}. "
        part = f"{label}{unit.title}\n\n{unit.text}"
        spans.append((position, position + len(part)))
        parts.append(part)
        position += len(part) + 2
    return "\n\n".join(parts), spans


def _client() -> Any:
    """Pangram's SDK client, which reads the key from the environment itself."""
    try:
        sdk: Any = importlib.import_module("pangram")
    except ImportError as exc:
        raise SystemExit(
            "the Pangram SDK is not installed; rerun with: uv run --frozen "
            '--with "pangram-sdk>=1.0" python docs/paper/analysis/pangram_check.py ...'
        ) from exc
    return sdk.Pangram()


def is_flagged(window: dict[str, Any]) -> bool:
    """Whether Pangram labelled a window anything other than human-written."""
    return not str(window.get("label", "")).startswith("Human")


def locate(text: str, window: dict[str, Any], after: int) -> int:
    """Character offset of a window in the sent text, or -1 if it cannot be placed."""
    snippet = str(window.get("text", ""))[:60]
    found = text.find(snippet, after) if snippet.strip() else -1
    if found < 0 and snippet.strip():
        found = text.find(snippet)
    start = window.get("start_index")
    return found if found >= 0 else start if isinstance(start, int) else -1


def describe(result: dict[str, Any]) -> str:
    """Pangram's verdict on the whole document, in one line."""
    windows: list[dict[str, Any]] = result.get("windows") or []
    return (
        f"{result.get('headline')} [{result.get('prediction_short')}]; "
        f"AI {result.get('fraction_ai', 0):.2f} / "
        f"AI-assisted {result.get('fraction_ai_assisted', 0):.2f} / "
        f"human {result.get('fraction_human', 0):.2f}; "
        f"{sum(map(is_flagged, windows))} of {len(windows)} windows flagged"
    )


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n")[0],
        epilog=(
            f"Left out of the document and shown as {OMITTED}: {REMOVED}. To leave "
            "out more of the paper, wrap it in % BEGIN AI-PREPARED / "
            "% END AI-PREPARED comment lines in the manuscript, or pass "
            f"--exclude-section. Scoring reads the key from {KEY_VARIABLE} and "
            "spends credits."
        ),
    )
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="directory for the document sent and Pangram's raw response "
        "(default: docs/paper/build/pangram, which Git ignores)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="write the document and print the section table without calling Pangram",
    )
    parser.add_argument(
        "--exclude-section",
        action="append",
        default=[],
        metavar="SELECTOR",
        help="leave out a section, by its key in the printed table (such as A) or "
        "part of its title (repeatable)",
    )
    parser.add_argument(
        "--max-usd",
        type=float,
        default=10.0,
        help="refuse to send if the estimated cost exceeds this many dollars "
        "(default: 10)",
    )
    parser.add_argument(
        "--response",
        type=Path,
        help="report a saved Pangram response for this exact document instead of "
        "calling the API (needs no key; used by CI to reuse a cached result)",
    )
    parser.add_argument(
        "--fail-above",
        type=float,
        metavar="FRACTION",
        help="exit 1 if the share of the document Pangram does not classify as "
        "human-written (AI plus AI-assisted) exceeds this value (for example 0.03)",
    )
    parser.add_argument(
        "--model",
        default="default",
        help="Pangram model selector (default: Pangram's current default model)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="print an excerpt of each flagged window"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    sending = not args.extract_only and args.response is None
    if sending and not os.environ.get(KEY_VARIABLE):
        raise SystemExit(f"{KEY_VARIABLE} is not set; set it or pass --extract-only")
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required to convert the manuscript to plain text")
    client = _client() if sending else None

    units = exclude(
        manuscript_units(args.manuscript.read_text(encoding="utf-8")),
        args.exclude_section,
    )
    text, spans = document(units)
    words = sum(u.words for u in units)
    if words < MIN_WORDS:
        raise SystemExit(f"only {words} words of author prose; nothing to score")
    if words > MAX_WORDS:
        raise SystemExit(
            f"{words:,} words is over Pangram's {MAX_WORDS:,}-word ceiling; leave "
            "out a section with --exclude-section"
        )
    blocks = -(-len(text.split()) // BLOCK_WORDS)
    print(
        f"One document, {words:,} words of author prose: about {blocks} billable "
        f"{BLOCK_WORDS}-word blocks, or ${blocks * USD_PER_BLOCK:.2f} at Pangram's "
        "published realtime rate (an estimate; Pangram's own count governs).\n"
    )
    if sending and blocks * USD_PER_BLOCK > args.max_usd:
        raise SystemExit(
            f"estimated ${blocks * USD_PER_BLOCK:.2f} exceeds --max-usd "
            f"{args.max_usd:.2f}; raise it to send"
        )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "paper.txt").write_text(text + "\n", encoding="utf-8")

    details: list[str] = []
    result: dict[str, Any] | None = None
    if args.response is not None:
        result = json.loads(args.response.read_text(encoding="utf-8"))
        print(f"Reusing the saved response in {args.response}.\n")
    elif client is not None:
        try:
            result = client.predict(text, model=args.model)
        except (ValueError, TimeoutError) as exc:
            print(f"Pangram request failed: {exc}")
            return 1
        (args.out / "response.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if result is None:
        outcomes = ["extracted, not sent" if u.words else "nothing sent" for u in units]
    else:
        print(f"Whole document: {describe(result)}\n")
        counts = [[0, 0] for _ in units]
        unplaced = position = 0
        windows: list[dict[str, Any]] = result.get("windows") or []
        for window in windows:
            at = locate(text, window, position)
            owner = next((i for i, (a, b) in enumerate(spans) if a <= at < b), None)
            if owner is None:
                unplaced += 1
                continue
            position = at
            counts[owner][0] += 1
            if is_flagged(window):
                counts[owner][1] += 1
                details.append(
                    f"[{units[owner].key}] {window.get('label')} "
                    f"(score {window.get('ai_assistance_score')}, "
                    f"confidence {window.get('confidence')}): "
                    f"{' '.join(str(window.get('text', '')).split())[:300]}"
                )
        outcomes = [
            f"{flagged} of {total} windows flagged" if u.words else "nothing sent"
            for u, (total, flagged) in zip(units, counts, strict=True)
        ]
        if unplaced:
            print(f"{unplaced} windows could not be matched to a section.\n")

    width = max(len(u.key) for u in units)
    print(f"{'Sec':<{width}}  {'Words':>6}  {'Title':<{TITLE_WIDTH}}  Result")
    for unit, outcome in zip(units, outcomes, strict=True):
        title = unit.title
        if len(title) > TITLE_WIDTH:
            title = title[: TITLE_WIDTH - 3] + "..."
        if unit.excluded:
            outcome += f" ({unit.excluded})"
        elif not unit.words:
            outcome += " (all of it is left out)"
        print(
            f"{unit.key:<{width}}  {unit.words:>6,}  {title:<{TITLE_WIDTH}}  {outcome}"
        )
    if args.verbose and details:
        print("\nFlagged windows\n" + "\n".join(details))
    print(
        f"\nThis is not a check of the whole paper. Left out and shown as {OMITTED} "
        f"in the document: {REMOVED}."
    )
    print(f"Document sent and any raw response: {args.out}")
    if result is not None and args.fail_above is not None:
        fraction = float(result.get("fraction_ai") or 0) + float(
            result.get("fraction_ai_assisted") or 0
        )
        if fraction > args.fail_above:
            print(
                f"\nFAIL: Pangram classifies {fraction:.2f} of the text as AI or "
                f"AI-assisted, above {args.fail_above:.2f}. Rewrite the flagged "
                "windows above, or mark disclosed passages with "
                "% BEGIN/END AI-PREPARED."
            )
            return 1
        print(
            f"\nPASS: Pangram classifies {fraction:.2f} of the text as AI or "
            f"AI-assisted, at most {args.fail_above:.2f}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
