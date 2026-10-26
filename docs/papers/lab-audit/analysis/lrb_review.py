"""Generate the LAB audit paper's LegalReasonBench human-review appendix.

The review worksheet (docs/legalreasonbench-audit/litigation/human-review/
worksheet.md) records the reviewer's rubric verdict, defect basis and origin,
environment verdict, and note for each of the 25 sampled criteria. This script is the
LegalReasonBench counterpart of ``lab_review.py`` and writes two marked blocks in the
LAB audit manuscript:

``% BEGIN GENERATED LRB REVIEW NUMBERS`` (preamble)
    LaTeX macros (prefix ``\\lrb``) holding the counts and the exact one-sided 95%
    hypergeometric lower bounds from the review's fixed-in-advance analysis.

``% BEGIN GENERATED LRB REVIEW TABLE`` (appendix)
    The rubric-verdict by environment-verdict table.

The per-criterion entries (``\\lrbitem``: quoted criterion, assessment, the
benchmark's own judge votes, the reviewer's analysis) live between
``% BEGIN LRB REVIEW ENTRIES`` and ``% END LRB REVIEW ENTRIES``. ``--seed-entries``
renders them once from the worksheet, and only into an empty region; after that the
manuscript is their source of truth and is edited by hand. ``--check`` fails if a
generated block is stale or if an entry's rubric verdict, defect basis, defect origin,
or environment verdict disagrees with the worksheet.

Run from the repository root::

    uv run --frozen python \\
        docs/papers/lab-audit/analysis/lrb_review.py --seed-entries \\
        --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
    uv run --frozen python \\
        docs/papers/lab-audit/analysis/lrb_review.py --write-manuscript \\
        --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
    uv run --frozen python \\
        docs/papers/lab-audit/analysis/lrb_review.py --check \\
        --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/legalreasonbench-audit/litigation"
REVIEW = AUDIT / "human-review"
RUNS = AUDIT / "model-runs"
BLOCKS = ("LRB REVIEW NUMBERS", "LRB REVIEW TABLE")
ENTRIES_BEGIN = "% BEGIN LRB REVIEW ENTRIES (hand-edited after seeding)"
ENTRIES_END = "% END LRB REVIEW ENTRIES"
REVISION_SHORT = "1bfa904c"
REPOSITORY = "https://github.com/johnhughes3/LegalForecastBench"
WORKSHEET_DIR = "docs/legalreasonbench-audit/litigation/human-review"
RUN_ORDER = ("gpt6luna-xhigh", "opus55-low")
AI_PREPARED_BEGIN = (
    "% BEGIN AI-PREPARED (source lists assembled with AI assistance; "
    "not sent to the Pangram check)"
)

# Characters pdfLaTeX's UTF-8 input cannot typeset, mapped to LaTeX.
UNICODE = {
    "\N{MINUS SIGN}": "$-$",
    "\N{GREATER-THAN OR EQUAL TO}": r"$\geq$",
    "\N{LESS-THAN OR EQUAL TO}": r"$\leq$",
    "\N{RIGHTWARDS ARROW}": r"$\rightarrow$",
    "\N{MULTIPLICATION SIGN}": r"$\times$",
    "\N{HORIZONTAL ELLIPSIS}": r"\ldots{}",
    "\N{NO-BREAK SPACE}": "~",
}
DASHES = "\N{EM DASH}\N{EN DASH}"
# Curly quotes, dashes, section and paragraph signs, and common accented letters.
SAFE_NON_ASCII = set(
    "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    "\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
    f"{DASHES}\N{SECTION SIGN}\N{PILCROW SIGN}"
    "\N{LATIN SMALL LETTER E WITH ACUTE}\N{LATIN SMALL LETTER E WITH GRAVE}"
    "\N{LATIN SMALL LETTER A WITH ACUTE}\N{LATIN SMALL LETTER A WITH GRAVE}"
    "\N{LATIN SMALL LETTER I WITH ACUTE}\N{LATIN SMALL LETTER O WITH ACUTE}"
    "\N{LATIN SMALL LETTER U WITH ACUTE}\N{LATIN SMALL LETTER N WITH TILDE}"
    "\N{LATIN SMALL LETTER U WITH DIAERESIS}\N{LATIN SMALL LETTER O WITH DIAERESIS}"
    "\N{LATIN SMALL LETTER A WITH DIAERESIS}\N{LATIN SMALL LETTER C WITH CEDILLA}"
)
OPENING_DOUBLE = re.compile(rf'(^|[\s(\[{{{DASHES}/-])"')
OPENING_SINGLE = re.compile(rf"(^|[\s(\[{{{DASHES}/-])'")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
URL = re.compile(r"https?://\S+")
CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
STAR_EMPHASIS = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
UNDERSCORE_EMPHASIS = re.compile(r"(?<![\w\\])_(?![\s_])(.+?)(?<![\s_])_(?!\w)")
# Private-use stand-ins for markup decided before escaping; never in worksheet text.
EMPH_OPEN, EMPH_CLOSE, BOLD_OPEN, BOLD_CLOSE, SLOT, BACKSLASH = (
    chr(0xE000 + offset) for offset in range(6)
)


def _scripts() -> tuple[Any, Any, Any]:
    """The review sampler, model-run helpers, and the Harvey generator's helpers."""
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return (
        importlib.import_module("legalreasonbench_review_sample"),
        importlib.import_module("legalreasonbench_model_runs"),
        importlib.import_module("lab_review"),
    )


def _escape(text: str) -> str:
    text = text.replace("\\", BACKSLASH)
    for char in "&%$#_{}":
        text = text.replace(char, "\\" + char)
    text = text.replace(BACKSLASH, r"\textbackslash{}")
    return text.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")


def _url(url: str) -> str:
    """A URL as the first argument of ``\\href``, safe inside another argument."""
    return url.replace("\\", "/").replace("%", r"\%").replace("#", r"\#")


def _absolute(target: str) -> str:
    """A worksheet link target as a URL; repository-relative paths go to GitHub."""
    if re.match(r"https?://", target):
        return target
    path = posixpath.normpath(posixpath.join(WORKSHEET_DIR, target))
    if path.startswith("../"):
        raise SystemExit(f"worksheet link leaves the repository: {target}")
    return f"{REPOSITORY}/blob/main/{path}"


def texttt(code: str) -> str:
    """Code or an identifier in typewriter type, breakable after underscores."""
    return r"\texttt{" + _escape(code).replace(r"\_", r"\_\allowbreak{}") + "}"


def tex(markdown: str) -> str:
    """Convert worksheet Markdown to LaTeX without changing any of its words.

    Handles links, bare URLs, code spans, bold, ``*``/``_`` emphasis, straight
    quotes, and the LaTeX special characters. Fails on a character pdfLaTeX could
    not typeset rather than dropping it.
    """
    slots: list[str] = []

    def keep(latex: str) -> str:
        slots.append(latex)
        return f"{SLOT}{len(slots) - 1}{SLOT}"

    text = CODE.sub(lambda m: keep(texttt(m[1])), markdown)
    text = LINK.sub(
        lambda m: keep(rf"\href{{{_url(_absolute(m[2]))}}}{{") + m[1] + keep("}"),
        text,
    )

    def bare(match: re.Match[str]) -> str:
        url = match[0].rstrip(".,;:)")
        return keep(rf"\url{{{url}}}") + match[0][len(url) :]

    text = URL.sub(bare, text)
    text = BOLD.sub(rf"{BOLD_OPEN}\1{BOLD_CLOSE}", text)
    text = STAR_EMPHASIS.sub(rf"{EMPH_OPEN}\1{EMPH_CLOSE}", text)
    text = UNDERSCORE_EMPHASIS.sub(rf"{EMPH_OPEN}\1{EMPH_CLOSE}", text)
    text = _escape(text)
    text = OPENING_DOUBLE.sub(r"\1``", text).replace('"', "''")
    text = OPENING_SINGLE.sub(r"\1`", text)
    for char, replacement in UNICODE.items():
        text = text.replace(char, replacement)
    for marker, latex in (
        (EMPH_OPEN, r"\emph{"),
        (BOLD_OPEN, r"\textbf{"),
        (EMPH_CLOSE, "}"),
        (BOLD_CLOSE, "}"),
    ):
        text = text.replace(marker, latex)
    bad = {c for c in text if ord(c) > 127 and c not in SAFE_NON_ASCII and c != SLOT}
    if bad:
        raise SystemExit(f"untypeset characters in worksheet text: {sorted(bad)}")
    return re.sub(rf"{SLOT}(\d+){SLOT}", lambda m: slots[int(m[1])], text)


class Item(NamedTuple):
    """One sampled criterion as the worksheet records it."""

    n: int
    title: str
    criterion: str
    task: str
    rubric_url: str
    polarity: str
    points: str
    rubric_text: str
    review: dict[str, str]
    analysis: list[str]
    sources: list[str]


def _note(note: str) -> tuple[list[str], list[str]]:
    """The reviewer's analysis paragraphs, then the trailing ``- `` source bullets."""
    paragraphs: list[list[str]] = [[]]
    bullets: list[str] = []
    for line in note.splitlines():
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif bullets and line.strip():
            raise SystemExit(f"note text after its source bullets: {line[:60]!r}")
        elif line.strip():
            paragraphs[-1].append(line.strip())
        elif paragraphs[-1]:
            paragraphs.append([])
    return [" ".join(p) for p in paragraphs if p], bullets


def items(sampler: Any) -> list[Item]:
    """Every sampled item, after the sampler confirms the worksheet matches the draw."""
    with contextlib.chdir(ROOT):
        _record, sample = sampler.frozen_sample()
        blocks: list[str] = sampler.checked_reviews(sample)
    worksheet = (REVIEW / "worksheet.md").read_text(encoding="utf-8")
    sections = re.split(r"(?m)^(?=## \d+\. )", worksheet)[1:]
    out: list[Item] = []
    for section, row, block in zip(sections, sample, blocks, strict=True):
        head = re.match(
            r"## (\d+)\. (.+) \N{EM DASH} (\S+)\s*$", section.splitlines()[0]
        )
        link = re.search(r"\[Criterion in pinned rubric\]\((\S+?)\)", section)
        rubric = re.search(
            r"(?m)^\*\*(Penalty|Reward) criterion, ([-+]\d+) points\*\*.*\n\n"
            r"((?:>.*\n?)+)",
            section,
        )
        if not (head and link and rubric) or head[3] != row["criterion"]:
            raise SystemExit(f"worksheet item for {row['criterion']} is malformed")
        review: dict[str, str] = sampler.parse_review(block)
        analysis, sources = _note(review["Note and source locator"])
        out.append(
            Item(
                n=int(head[1]),
                title=head[2].strip(),
                criterion=head[3],
                task=row["task"],
                rubric_url=link[1],
                polarity=rubric[1],
                points=rubric[2],
                rubric_text=" ".join(
                    re.sub(r"^>\s?", "", ln).strip() for ln in rubric[3].splitlines()
                ).strip(),
                review=review,
                analysis=analysis,
                sources=sources,
            )
        )
    return out


def statistics(sampler: Any, parsed: list[Item]) -> dict[str, Any]:
    comparison = json.loads((AUDIT / "comparison.json").read_text(encoding="utf-8"))
    record = json.loads((REVIEW / "sample.json").read_text(encoding="utf-8"))
    population: int = record["population_size"]
    rows: list[dict[str, Any]] = record["sample"]
    n = len(parsed)

    def count(field: str, value: str) -> int:
        return sum(1 for i in parsed if i.review[field] == value)

    defective = [i for i in parsed if i.review["Rubric verdict"] == "Defective"]
    env_bad = [r for r, i in zip(rows, parsed, strict=True) if _env(i) == "Defective"]
    both = [
        i
        for r, i in zip(rows, parsed, strict=True)
        if r["bucket"] in ("both_problematic", "both_arguable", "split")
    ]
    stats: dict[str, Any] = {
        "assignments": comparison["tasks_total"],
        "criteria_total": comparison["criteria_total"],
        "population": population,
        "sample": n,
        "sample_assignments": len({r["task"] for r in rows}),
        "defective": len(defective),
        "arguable": count("Rubric verdict", "Arguable"),
        "not_defective": count("Rubric verdict", "Not defective"),
        "unresolved": count("Rubric verdict", "Unresolved"),
        "objective": sum(
            1
            for i in defective
            if i.review["Defect basis (Defective only)"]
            == "Unambiguous objective error"
        ),
        "judgment": sum(
            1
            for i in defective
            if i.review["Defect basis (Defective only)"] == "Professional judgment"
        ),
        "from_env": sum(
            1
            for i in defective
            if i.review["Defect arises from environment (Defective only)"] == "Yes"
        ),
        "env_items": len(env_bad),
        "env_assignments": len({r["task"] for r in env_bad}),
        "ai_correct": count("AI reasoning", "Correct"),
        "ai_partly": count("AI reasoning", "Partly correct"),
        "ai_wrong": count("AI reasoning", "Wrong"),
        "both_flagged": len(both),
        "both_defective": sum(
            1 for i in both if i.review["Rubric verdict"] == "Defective"
        ),
    }
    stats["single_flagged"] = n - stats["both_flagged"]
    stats["single_defective"] = stats["defective"] - stats["both_defective"]
    stats["defective_pct"] = round(100 * stats["defective"] / n)
    for key in ("defective", "objective"):
        stats[f"{key}_lb"] = sampler.lower_bound(population, n, stats[key])
        stats[f"{key}_point"] = round(stats[key] * population / n)
    return stats


MACROS = {
    "assignments": "lrbAssignments",
    "criteria_total": "lrbCriteria",
    "population": "lrbFlagged",
    "sample": "lrbSample",
    "sample_assignments": "lrbSampleAssignments",
    "defective": "lrbDefective",
    "defective_pct": "lrbDefectivePct",
    "arguable": "lrbArguable",
    "not_defective": "lrbNotDefective",
    "unresolved": "lrbUnresolved",
    "objective": "lrbObjective",
    "judgment": "lrbJudgment",
    "from_env": "lrbFromEnv",
    "env_items": "lrbEnvItems",
    "env_assignments": "lrbEnvAssignments",
    "ai_correct": "lrbAiCorrect",
    "ai_partly": "lrbAiPartly",
    "ai_wrong": "lrbAiWrong",
    "both_flagged": "lrbBothFlagged",
    "both_defective": "lrbBothDefective",
    "single_flagged": "lrbSingleFlagged",
    "single_defective": "lrbSingleDefective",
    "defective_lb": "lrbDefectiveLB",
    "defective_point": "lrbDefectivePoint",
    "objective_lb": "lrbObjectiveLB",
    "objective_point": "lrbObjectivePoint",
}


def render_numbers(stats: dict[str, Any], number: Any) -> str:
    lines = ["% Counts from the human review of sampled LegalReasonBench criteria."]
    lines += [
        rf"\newcommand{{\{macro}}}{{{number(stats[key])}}}"
        for key, macro in MACROS.items()
    ]
    return "\n".join(lines)


def _env(item: Item) -> str:
    return item.review["Environment"]


def render_table(stats: dict[str, Any], parsed: list[Item]) -> str:
    out = [
        r"\begin{table}[ht]\centering\small",
        r"\begin{tabular}{lrrr}\toprule",
        r"Rubric verdict & Environment defective & Environment correct"
        r" & Total\\\midrule",
    ]
    verdicts = ["Defective", "Arguable", "Not defective"]
    if stats["unresolved"]:
        verdicts.append("Unresolved")
    for verdict in verdicts:
        cells = [
            sum(
                1
                for i in parsed
                if i.review["Rubric verdict"] == verdict and _env(i) == env
            )
            for env in ("Defective", "Correct")
        ]
        out.append(rf"{verdict} & {cells[0]} & {cells[1]} & {sum(cells)}\\")
    bad = sum(1 for i in parsed if _env(i) == "Defective")
    out += [
        r"\midrule",
        rf"Total & {bad} & {len(parsed) - bad} & {len(parsed)}\\",
        r"\bottomrule\end{tabular}",
        r"\caption{My verdicts on the "
        + str(stats["sample"])
        + r" sampled LegalReasonBench criteria, by whether the task environment"
        r" itself contains a defect.}",
        r"\label{tab:lrbreview}\end{table}",
    ]
    return "\n".join(out)


def criterion_cell(item: Item) -> str:
    """The assessment table's criterion row, which ``--check`` parses back."""
    verdict = item.review["Rubric verdict"]
    if verdict != "Defective":
        return verdict
    basis = item.review["Defect basis (Defective only)"]
    origin = item.review["Defect arises from environment (Defective only)"]
    where = "arises from" if origin == "Yes" else "does not arise from"
    return f"{verdict} --- {basis[0].lower()}{basis[1:]}; {where} the task environment"


def judge_row(item: Item, slug: str, model_runs: Any) -> str:
    """One model run's judge votes on the criterion, as an assessment-table row."""
    labels: dict[str, str] = {
        s: label for s, label, _model, _effort in model_runs.CONDITIONS
    }
    judges: dict[str, str] = dict(model_runs.JUDGES)
    path = RUNS / item.task / slug / "reward-details.json"
    if not path.is_file():
        return rf"{labels[slug]} & No published run\\"
    details: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    criteria: list[dict[str, Any]] = details["correctness"]["criteria"]
    found = [c for c in criteria if c["name"] == item.criterion]
    if len(found) != 1:
        return rf"{labels[slug]} & Not graded on this criterion\\"
    penalty = item.polarity == "Penalty"
    words = ("fires", "clear") if penalty else ("met", "not met")
    votes: list[str] = []
    yes = 0
    panel: list[dict[str, Any]] = found[0].get("votes") or []
    for vote in panel:
        model: str = vote["judge"]["model"]
        judge = judges.get(model, model)
        value = vote.get("value")
        if value is None:
            votes.append(f"{judge}: no vote")
            continue
        yes += int(bool(value))
        votes.append(f"{judge}: {words[0] if value else words[1]}")
    if len(votes) != 3 or any(v.endswith("no vote") for v in votes):
        result = "panel incomplete"
    elif penalty:
        result = f"penalty {'applied' if yes >= 2 else 'not applied'} ({yes}/3)"
    else:
        result = f"{'met' if yes >= 2 else 'not met'} ({yes}/3)"
    return rf"{labels[slug]} & {'; '.join(votes)}. Result: {result}\\"


def render_entry(item: Item, model_runs: Any) -> str:
    env = _env(item)
    explanation = item.review["Environment explanation"]
    env_cell = f"{env}: {tex(explanation)}" if env == "Defective" else env
    sign = "$-$" if item.points.startswith("-") else "+"
    lines = [
        rf"\lrbitem{{{item.n}}}{{{tex(item.title)}}}{{{texttt(item.criterion)}}}",
        r"\begin{lrbquote}{micro1 LegalReasonBench, "
        + texttt(item.criterion)
        + rf", \href{{{_url(item.rubric_url)}}}{{rubric at revision"
        rf" \texttt{{{REVISION_SHORT}}}}}}}",
        rf"\textbf{{{item.polarity} criterion, {sign}{item.points[1:]} points.}}"
        rf" {tex(item.rubric_text)}",
        r"\end{lrbquote}",
        "",
        r"\noindent\begin{tabular}{@{}>{\raggedright\arraybackslash}p{.25\linewidth}"
        r">{\raggedright\arraybackslash}p{.71\linewidth}@{}}",
        r"\toprule",
        r"\multicolumn{2}{@{}l@{}}{\textbf{My assessment}}\\",
        rf"Criterion & {criterion_cell(item)}\\",
        rf"Task environment & {env_cell}\\",
        rf"AI auditors' reasoning & {item.review['AI reasoning']}\\",
        r"\midrule",
        r"\multicolumn{2}{@{}l@{}}{\textbf{LegalReasonBench's own grading of two"
        r" model runs} (its judges, not my assessment)}\\",
        *(judge_row(item, slug, model_runs) for slug in RUN_ORDER),
        r"\bottomrule",
        r"\end{tabular}",
        "",
    ]
    for index, paragraph in enumerate(item.analysis):
        lead = r"\noindent\textbf{My analysis.} " if index == 0 else ""
        lines += [lead + tex(paragraph), ""]
    if item.sources:
        lines += [AI_PREPARED_BEGIN, r"\begin{itemize}"]
        for bullet in item.sources:
            label, colon, rest = bullet.partition(":")
            body = (
                rf"\textit{{{tex(label)}:}}{tex(rest)}"
                if colon and len(label.split()) <= 3
                else tex(bullet)
            )
            lines.append(rf"\item{{}} {body}")
        lines += [r"\end{itemize}", "% END AI-PREPARED", ""]
    return "\n".join(lines)


def render_entries(parsed: list[Item], model_runs: Any) -> str:
    return "\n".join(render_entry(i, model_runs) for i in parsed).rstrip()


ENTRY = re.compile(
    r"(?s)\\lrbitem\{(\d+)\}.*?^Criterion & (.+?)\\\\$"
    r".*?^Task environment & (.+?)\\\\$",
    re.M,
)


def entry_mismatches(manuscript: str, parsed: list[Item]) -> list[str]:
    """Entries whose verdicts in the manuscript disagree with the worksheet."""
    want = {i.n: i for i in parsed}
    found = {int(m[1]): (m[2], m[3]) for m in ENTRY.finditer(manuscript)}
    problems = [f"entry {n} is missing" for n in want if n not in found]
    for n, (criterion, environment) in sorted(found.items()):
        item = want.get(n)
        if item is None:
            problems.append(f"entry {n} is not in the worksheet")
            continue
        verdict, _, detail = criterion.partition(" --- ")
        if verdict.strip() != item.review["Rubric verdict"]:
            problems.append(
                f"entry {n}: rubric verdict is not {item.review['Rubric verdict']!r}"
            )
        elif verdict.strip() == "Defective":
            basis, _, origin = detail.partition(";")
            expected = item.review["Defect basis (Defective only)"]
            if basis.strip().casefold() != expected.casefold():
                problems.append(f"entry {n}: defect basis is not {expected!r}")
            arises = "does not arise" not in origin and "arises" in origin
            expected = item.review["Defect arises from environment (Defective only)"]
            if arises != (expected == "Yes"):
                problems.append(
                    f"entry {n}: defect origin is not {expected!r} "
                    "(arises from the task environment)"
                )
        expected = _env(item)
        if environment.split(":", 1)[0].strip().rstrip(".") != expected:
            problems.append(f"entry {n}: environment verdict is not {expected!r}")
    return problems


def _entries_span(text: str) -> tuple[int, int] | None:
    """The span of the hand-edited entries region's body, or None if absent."""
    if text.count(ENTRIES_BEGIN) == text.count(ENTRIES_END) == 0:
        return None
    if text.count(ENTRIES_BEGIN) != 1 or text.count(ENTRIES_END) != 1:
        raise SystemExit(f"manuscript must contain at most one {ENTRIES_BEGIN} region")
    start = text.index(ENTRIES_BEGIN) + len(ENTRIES_BEGIN) + 1
    return start, text.index(ENTRIES_END)


def seed(text: str, entries: str) -> str:
    """Fill the empty entries region; refuse if it already holds anything."""
    span = _entries_span(text)
    if span is None:
        raise SystemExit(f"manuscript has no {ENTRIES_BEGIN} / {ENTRIES_END} region")
    start, end = span
    if text[start:end].strip():
        raise SystemExit(
            "the LRB review entries region is not empty; it is edited by hand after "
            "seeding, so --seed-entries refuses to overwrite it"
        )
    return text[:start] + entries + "\n" + text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n")[0],
        epilog="Run from the repository root; see the module docstring for examples.",
    )
    parser.add_argument("--manuscript", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail if a generated block is stale or an entry disagrees with the "
        "worksheet",
    )
    mode.add_argument(
        "--write-manuscript", action="store_true", help="rewrite the generated blocks"
    )
    mode.add_argument(
        "--seed-entries",
        action="store_true",
        help="render the per-criterion entries into the empty entries region "
        "(refuses if it is not empty)",
    )
    args = parser.parse_args(argv)
    sampler, model_runs, lab_review = _scripts()
    parsed = items(sampler)
    text = args.manuscript.read_text(encoding="utf-8")
    if args.seed_entries:
        args.manuscript.write_text(
            seed(text, render_entries(parsed, model_runs)), encoding="utf-8"
        )
        print(f"seeded {len(parsed)} entries; edit them by hand from now on")
        return 0
    stats = statistics(sampler, parsed)
    blocks = {
        BLOCKS[0]: render_numbers(stats, lab_review.number),
        BLOCKS[1]: render_table(stats, parsed),
    }
    stale: list[str] = []
    present = 0
    for name, body in blocks.items():
        span = lab_review._block(text, name)
        if span is None:
            continue
        present += 1
        start, end = span
        if text[start:end] != body + "\n":
            stale.append(name)
            text = text[:start] + body + "\n" + text[end:]
    if not present:
        raise SystemExit(
            f"{args.manuscript} has no % BEGIN GENERATED {' or '.join(BLOCKS)} block"
        )
    has_entries = "\\lrbitem{" in text or _entries_span(text) is not None
    mismatches = entry_mismatches(text, parsed) if has_entries else []
    for problem in mismatches:
        print(
            f"appendix entry disagrees with the worksheet: {problem}", file=sys.stderr
        )
    if args.check:
        if stale:
            print(f"stale generated blocks: {', '.join(stale)}", file=sys.stderr)
        if stale or mismatches:
            return 1
        print("LRB review blocks match the worksheet")
        return 0
    args.manuscript.write_text(text, encoding="utf-8")
    print(f"updated: {', '.join(stale) or 'nothing (already current)'}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
