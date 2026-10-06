"""Generate the paper's Harvey LAB human-review appendix from the review worksheet.

The worksheet (docs/harvey-lab-audit/litigation-dispute-resolution/human-review/
worksheet.md) is the source of truth for the 25 sampled criteria and the reviewer's
verdicts, categories, environment verdicts, and notes. This script writes two marked
blocks in the standalone manuscript:

``% BEGIN GENERATED LAB REVIEW NUMBERS`` (preamble)
    LaTeX macros holding every count and confidence bound the prose cites, so the
    hand-written text cannot drift from the worksheet.

``% BEGIN GENERATED LAB REVIEW ITEMS`` (appendix)
    The rubric-verdict by environment-verdict table and, for each sampled criterion,
    the rubric text, verdicts, model-run grades, and the reviewer's analysis.

Run from the repository root::

    uv run --frozen python docs/paper/analysis/lab_review.py --check \\
        --manuscript docs/paper/LegalForecastBench-paper.tex
    uv run --frozen python docs/paper/analysis/lab_review.py --write-manuscript \\
        --manuscript docs/paper/LegalForecastBench-paper.tex
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "docs/harvey-lab-audit/litigation-dispute-resolution"
REVIEW = AUDIT / "human-review"
BLOCKS = ("LAB REVIEW NUMBERS", "LAB REVIEW ITEMS")
HARVEY_COMMIT = "1dd81403b2fbb60596f7aea3fcecafad7bf73143"

# Characters pdfLaTeX's default UTF-8 input cannot typeset, mapped to LaTeX.
UNICODE = {
    "\u2265": r"$\geq$",
    "\u2264": r"$\leq$",
    "\u2212": "$-$",
    "\u2192": r"$\rightarrow$",
    "\u00d7": r"$\times$",
    "\u2026": r"\ldots{}",
    "\u2122": r"\texttrademark{}",
    "\u2248": r"$\approx$",
    "\u00b1": r"$\pm$",
    "\u03bc": r"$\mu$",
    "\u00a0": "~",
}
# Curly quotes, dashes, section and paragraph signs, and common accented letters.
SAFE_NON_ASCII = set(
    "\u201c\u201d\u2018\u2019\u2014\u2013\u00a7\u00b6"
    "\u00e9\u00e8\u00e1\u00e0\u00ed\u00f3\u00fa\u00f1\u00fc\u00f6\u00e4\u00e7"
)
OPENING_QUOTE = re.compile('(^|[\\s(\\[{\u2014\u2013/-])"')


def _scripts() -> tuple[Any, Any]:
    """The review sampler and model-run helpers, shared with the audit tooling."""
    sys.path.insert(0, str(ROOT / "scripts"))
    return (
        importlib.import_module("harvey_review_sample"),
        importlib.import_module("harvey_model_runs"),
    )


def tex(text: str) -> str:
    """Escape worksheet Markdown for LaTeX, keeping emphasis, code, and URLs."""
    urls: list[str] = []

    def keep_url(match: re.Match[str]) -> str:
        urls.append(match.group(0).rstrip(".,;)"))
        trailing = match.group(0)[len(urls[-1]) :]
        return f"\x00{len(urls) - 1}\x00{trailing}"

    text = re.sub(r"https?://\S+", keep_url, text)
    text = text.replace("\\", r"\textbackslash{}")
    for char in "&%$#_{}":
        text = text.replace(char, "\\" + char)
    text = text.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", text)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    text = OPENING_QUOTE.sub(r"\1``", text)
    text = text.replace('"', "''")
    for char, replacement in UNICODE.items():
        text = text.replace(char, replacement)
    bad = {c for c in text if ord(c) > 127 and c not in SAFE_NON_ASCII}
    if bad:
        raise SystemExit(f"untypeset characters in worksheet text: {sorted(bad)}")
    return re.sub(r"\x00(\d+)\x00", lambda m: rf"\url{{{urls[int(m.group(1))]}}}", text)


def items(worksheet: str) -> list[dict[str, Any]]:
    """Parse each sampled item's rubric text, verdict fields, and note."""
    out: list[dict[str, Any]] = []
    for block in re.split(r"(?m)^(?=## \d+\. )", worksheet)[1:]:
        head = re.match(r"## (\d+)\. (.+) — (C-\d+)", block)
        rubric = re.search(r"(?m)^\*\*(.+?)\*\*\s*\n\n((?:>.*\n?)+)", block)
        note_start = block.index("- **Note and source locator:**")
        note_lines: list[str] = []
        category = ""
        for line in block[note_start:].splitlines():
            if line.startswith("- **Category**:"):
                category = line.split(":", 1)[1].strip()
            elif line.startswith("<!--"):
                break
            elif line.strip():
                note_lines.append(line)

        def field(name: str, block: str = block) -> str:
            found = re.search(rf"(?m)^- \*\*{name}:\*\* (.*)$", block)
            return found.group(1).strip() if found else ""

        if not (head and rubric):
            raise SystemExit("worksheet item is missing its heading or rubric text")
        out.append(
            {
                "n": int(head.group(1)),
                "title": head.group(2).strip(),
                "criterion": head.group(3),
                "rubric_title": rubric.group(1).strip(),
                "rubric_text": " ".join(
                    re.sub(r"^>\s?", "", ln).strip()
                    for ln in rubric.group(2).splitlines()
                ).strip(),
                "verdict": field("Verdict"),
                "ai": field("AI reasoning"),
                "environment": field("Environment"),
                "category": category,
                "note": note_lines,
            }
        )
    return out


def clean_note(lines: list[str]) -> tuple[str, list[str]]:
    """Split the note into its opening paragraph and its bullets, minus the label."""
    first = lines[0].removeprefix("- **Note and source locator:**").strip()
    bullets = [ln.removeprefix("- ").strip() for ln in lines[1:]]
    return first.strip(), bullets


def statistics(sampler: Any) -> dict[str, Any]:
    rows: list[dict[str, Any]] = json.loads(
        (AUDIT / "comparison.json").read_text(encoding="utf-8")
    )["rows"]
    flags = ("problematic", "arguable")
    criteria_total = sum(
        json.loads(p.read_text(encoding="utf-8"))["criteria_total"]
        for p in sorted((AUDIT / "tasks").glob("*/claude-opus-5-5-audit.json"))
    )
    sample: list[dict[str, Any]] = json.loads(
        (REVIEW / "sample.json").read_text(encoding="utf-8")
    )["sample"]
    worksheet = (REVIEW / "worksheet.md").read_text(encoding="utf-8")
    parsed = items(worksheet)
    env = {i["n"]: i["environment"].split(":", 1)[0].strip() for i in parsed}
    verdict = {i["n"]: i["verdict"] for i in parsed}
    objective = sampler.objective_errors(worksheet)
    flagged = sum(1 for r in rows if r["bucket"])
    n = len(parsed)

    def count(test: Callable[[int], bool]) -> int:
        return sum(1 for i in verdict if test(i))

    both = {
        i
        for i, r in enumerate(sample, 1)
        if r["bucket"] in ("both_problematic", "both_arguable", "split")
    }
    stats: dict[str, Any] = {
        "tasks": len(list((AUDIT / "tasks").glob("*/claude-opus-5-5-audit.json"))),
        "criteria_total": criteria_total,
        "sol_flagged": sum(1 for r in rows if r["gpt_6_sol"] in flags),
        "opus_blind": sum(1 for r in rows if r["claude_opus_5_5_blind"] in flags),
        "opus_final": sum(1 for r in rows if r["claude_opus_5_5"] in flags),
        "flagged": flagged,
        "sample": n,
        "sample_tasks": len({r["task"] for r in sample}),
        "defective": count(lambda i: verdict[i] == "Defective"),
        "arguable": count(lambda i: verdict[i] == "Arguable"),
        "not_defective": count(lambda i: verdict[i] == "Not defective"),
        "objective": len(objective),
        "env_items": count(lambda i: env[i] == "Defective"),
        "env_tasks": len(
            {r["task"] for i, r in enumerate(sample, 1) if env[i] == "Defective"}
        ),
        "any_defect": count(
            lambda i: verdict[i] == "Defective" or env[i] == "Defective"
        ),
        "no_defect": count(
            lambda i: verdict[i] == "Not defective" and env[i] == "Correct"
        ),
        "both_flagged": len(both),
        "both_defective": count(lambda i: i in both and verdict[i] == "Defective"),
        "single_flagged": n - len(both),
        "single_defective": count(
            lambda i: i not in both and verdict[i] == "Defective"
        ),
    }
    for key in ("defective", "objective", "env_items", "any_defect"):
        stats[f"{key}_lb"] = sampler.lower_bound(flagged, n, stats[key])
        stats[f"{key}_point"] = round(stats[key] * flagged / n)
    stats["flagged_pct"] = f"{100 * flagged / criteria_total:.1f}"
    for key in ("defective", "objective", "env_items"):
        # Truncate, not round: these shares are lower bounds, cited as "more than".
        tenths = 1000 * stats[f"{key}_lb"] // criteria_total
        stats[f"{key}_share"] = f"{tenths // 10}.{tenths % 10}"
    return stats


MACROS = {
    "tasks": "labTasks",
    "criteria_total": "labCriteria",
    "sol_flagged": "labSolFlagged",
    "opus_blind": "labOpusBlind",
    "opus_final": "labOpusFinal",
    "flagged": "labFlagged",
    "flagged_pct": "labFlaggedPct",
    "sample": "labSample",
    "sample_tasks": "labSampleTasks",
    "defective": "labDefective",
    "arguable": "labArguable",
    "not_defective": "labNotDefective",
    "objective": "labObjective",
    "env_items": "labEnvItems",
    "env_tasks": "labEnvTasks",
    "any_defect": "labAnyDefect",
    "no_defect": "labNoDefect",
    "both_flagged": "labBothFlagged",
    "both_defective": "labBothDefective",
    "single_flagged": "labSingleFlagged",
    "single_defective": "labSingleDefective",
    "defective_lb": "labDefectiveLB",
    "defective_point": "labDefectivePoint",
    "defective_share": "labDefectiveShare",
    "objective_lb": "labObjectiveLB",
    "objective_point": "labObjectivePoint",
    "objective_share": "labObjectiveShare",
    "env_items_lb": "labEnvLB",
    "env_items_share": "labEnvShare",
    "env_items_point": "labEnvPoint",
    "any_defect_lb": "labAnyLB",
    "any_defect_point": "labAnyPoint",
}


def number(value: Any) -> str:
    return f"{value:,}".replace(",", "{,}") if isinstance(value, int) else str(value)


def render_numbers(stats: dict[str, Any]) -> str:
    lines = ["% Counts from the human review of sampled Harvey LAB criteria."]
    lines += [
        rf"\newcommand{{\{macro}}}{{{number(stats[key])}}}"
        for key, macro in MACROS.items()
    ]
    return "\n".join(lines)


def render_items(stats: dict[str, Any], model_runs: Any) -> str:
    parsed = items((REVIEW / "worksheet.md").read_text(encoding="utf-8"))
    sample: list[dict[str, Any]] = json.loads(
        (REVIEW / "sample.json").read_text(encoding="utf-8")
    )["sample"]
    env = {i["n"]: i["environment"].split(":", 1)[0].strip() for i in parsed}
    rows = ("Defective", "Arguable", "Not defective")
    out = [
        r"\begin{table}[ht]\centering\small",
        r"\begin{tabular}{lrrr}\toprule",
        r"Criterion verdict & Environment defective & Environment correct"
        r" & Total\\\midrule",
    ]
    for verdict in rows:
        d = sum(
            1 for i in parsed if i["verdict"] == verdict and env[i["n"]] == "Defective"
        )
        c = sum(
            1 for i in parsed if i["verdict"] == verdict and env[i["n"]] == "Correct"
        )
        out.append(rf"{verdict} & {d} & {c} & {d + c}\\")
    total_d = sum(1 for i in parsed if env[i["n"]] == "Defective")
    out += [
        r"\midrule",
        rf"Total & {total_d} & {len(parsed) - total_d} & {len(parsed)}\\",
        r"\bottomrule\end{tabular}",
        r"\caption{Reviewer verdicts on the "
        + str(stats["sample"])
        + r" sampled criteria, by whether the task environment itself"
        r" contains a defect.}",
        r"\label{tab:labreview}\end{table}",
        "",
        r"\subsection*{The sampled criteria}",
        "Each entry gives the criterion as written, the reviewer's verdicts, how "
        "LAB's two native judges (Claude Sonnet 4.6 and GPT-5.5) graded the "
        "GPT-6 Luna and Claude Opus 5.5 runs on that criterion, and the "
        "reviewer's analysis. Harvey task "
        rf"files are cited at commit \texttt{{{HARVEY_COMMIT[:8]}}}.",
        "",
    ]
    labels = {"pass": "P", "fail": "F"}
    for item, drawn in zip(parsed, sample, strict=True):
        verdicts = model_runs.run_verdicts(drawn["task"], item["criterion"])
        runs = "; ".join(
            f"{name}: " + "/".join(labels.get(v, "?") for v in verdicts[slug].values())
            for slug, name in (
                ("gpt6luna-xhigh", "GPT-6 Luna"),
                ("opus55-low", "Claude Opus 5.5"),
            )
            if slug in verdicts
        )
        intro, bullets = clean_note(item["note"])
        env_text = item["environment"]
        out += [
            rf"\subsubsection*{{{item['n']}. {tex(item['title'])}"
            rf" ({item['criterion']})}}",
            r"\textit{Criterion.} \textbf{"
            + tex(item["rubric_title"].rstrip("."))
            + ".} "
            rf"{tex(item['rubric_text'])}",
            "",
            rf"\textit{{Verdict.}} {tex(item['verdict'])}"
            + (rf" ({tex(item['category'].rstrip('.'))})" if item["category"] else "")
            + rf". \textit{{Environment.}} {tex(env_text)}"
            + ("" if env_text.endswith(".") else ".")
            + r" \textit{AI auditors' reasoning (reviewer's assessment).} "
            + f"{tex(item['ai'])}."
            + r" \textit{Native grades} (Sonnet 4.6/GPT-5.5; P pass, F fail): "
            + f"{runs}.",
            "",
        ]
        if intro:
            out += [rf"\textit{{Analysis.}} {tex(intro)}", ""]
        if bullets:
            out.append(r"\begin{itemize}")
            out += [rf"\item {tex(b)}" for b in bullets]
            out += [r"\end{itemize}", ""]
    return "\n".join(out).rstrip()


def _block(text: str, name: str) -> tuple[int, int]:
    begin, end = f"% BEGIN GENERATED {name}", f"% END GENERATED {name}"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit(f"manuscript must contain exactly one {begin} / {end} block")
    start = text.index(begin) + len(begin) + 1
    return start, text.index(end)


def render_all() -> dict[str, str]:
    sampler, model_runs = _scripts()
    stats = statistics(sampler)
    return {
        BLOCKS[0]: render_numbers(stats),
        BLOCKS[1]: render_items(stats, model_runs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--manuscript", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if a block is stale")
    mode.add_argument(
        "--write-manuscript", action="store_true", help="rewrite the blocks"
    )
    args = parser.parse_args(argv)
    text = args.manuscript.read_text(encoding="utf-8")
    blocks = render_all()
    stale: list[str] = []
    for name, body in blocks.items():
        start, end = _block(text, name)
        if text[start:end] != body + "\n":
            stale.append(name)
            text = text[:start] + body + "\n" + text[end:]
    if args.check:
        if stale:
            print(f"stale generated blocks: {', '.join(stale)}", file=sys.stderr)
            return 1
        print("LAB review blocks match the worksheet")
        return 0
    args.manuscript.write_text(text, encoding="utf-8")
    print(f"updated: {', '.join(stale) or 'nothing (already current)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
