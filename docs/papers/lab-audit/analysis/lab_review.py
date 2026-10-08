"""Generate the counts in the paper's Harvey LAB human-review appendix.

The review worksheet (docs/harvey-lab-audit/litigation-dispute-resolution/human-review/
worksheet.md) records the reviewer's verdict, category, and environment verdict for
each of the 25 sampled criteria. This script writes two marked blocks, in whichever
manuscript contains them (the LAB audit paper has both; the LegalForecastBench
paper cites some of the counts and has only the first):

``% BEGIN GENERATED LAB REVIEW NUMBERS`` (preamble)
    LaTeX macros holding every count and confidence bound the prose cites, so the
    hand-written text cannot drift from the verdicts.

``% BEGIN GENERATED LAB REVIEW TABLE`` (appendix)
    The criterion-verdict by environment-verdict table.

The per-criterion entries in the appendix (quoted criterion, assessment, LAB's
grades, analysis) are edited by hand in the manuscript, which is their source of
truth. When a manuscript has those entries, ``--check`` also fails if a verdict in
them disagrees with the worksheet, because the counts above would then contradict
the entries.

Run from the repository root::

    uv run --frozen python \\
        docs/papers/lab-audit/analysis/lab_review.py --check \\
        --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
    uv run --frozen python \\
        docs/papers/lab-audit/analysis/lab_review.py --write-manuscript \\
        --manuscript docs/papers/lab-audit/LAB-audit-paper.tex

Run each command once per manuscript: the LegalForecastBench paper is
docs/papers/legalforecastbench/LegalForecastBench-paper.tex.
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

ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/harvey-lab-audit/litigation-dispute-resolution"
REVIEW = AUDIT / "human-review"
BLOCKS = ("LAB REVIEW NUMBERS", "LAB REVIEW TABLE")


def _sampler() -> Any:
    """The review sampler, shared with the audit tooling."""
    sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module("harvey_review_sample")


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


def render_table(stats: dict[str, Any]) -> str:
    parsed = items((REVIEW / "worksheet.md").read_text(encoding="utf-8"))
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
        r"\caption{My verdicts on the "
        + str(stats["sample"])
        + r" sampled criteria, by whether the task environment itself"
        r" contains a defect.}",
        r"\label{tab:labreview}\end{table}",
    ]
    return "\n".join(out)


ENTRY = re.compile(
    r"(?s)\\labitem\{(\d+)\}.*?^Criterion & (.+?)\\\\$"
    r".*?^Task environment & (.+?)\\\\$",
    re.M,
)


def entry_mismatches(manuscript: str) -> list[str]:
    """Entries whose verdicts in the manuscript disagree with the worksheet."""
    parsed = {
        i["n"]: i for i in items((REVIEW / "worksheet.md").read_text(encoding="utf-8"))
    }
    found = {int(m[1]): (m[2], m[3]) for m in ENTRY.finditer(manuscript)}
    problems = [f"entry {n} is missing" for n in parsed if n not in found]
    for n, (criterion, environment) in sorted(found.items()):
        want = parsed.get(n)
        if want is None:
            problems.append(f"entry {n} is not in the worksheet")
            continue
        if (
            re.split(r" --- |\\,|$", criterion, maxsplit=1)[0].strip()
            != want["verdict"]
        ):
            problems.append(f"entry {n}: criterion verdict is not {want['verdict']!r}")
        expected = want["environment"].split(":", 1)[0].strip()
        if environment.split(":", 1)[0].strip().rstrip(".") != expected:
            problems.append(f"entry {n}: environment verdict is not {expected!r}")
    return problems


def _block(text: str, name: str) -> tuple[int, int] | None:
    """The span of a marked block's body, or None if the manuscript lacks it."""
    begin, end = f"% BEGIN GENERATED {name}", f"% END GENERATED {name}"
    if text.count(begin) == text.count(end) == 0:
        return None
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit(f"manuscript must contain at most one {begin} / {end} block")
    start = text.index(begin) + len(begin) + 1
    return start, text.index(end)


def render_all() -> dict[str, str]:
    stats = statistics(_sampler())
    return {BLOCKS[0]: render_numbers(stats), BLOCKS[1]: render_table(stats)}


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
    present = 0
    for name, body in blocks.items():
        span = _block(text, name)
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
    # Only the paper with the per-criterion appendix has entries to compare.
    mismatches = entry_mismatches(text) if "\\labitem{" in text else []
    for problem in mismatches:
        print(
            f"appendix entry disagrees with the worksheet: {problem}", file=sys.stderr
        )
    if args.check:
        if stale:
            print(f"stale generated blocks: {', '.join(stale)}", file=sys.stderr)
        if stale or mismatches:
            return 1
        print("LAB review blocks match the worksheet")
        return 0
    args.manuscript.write_text(text, encoding="utf-8")
    print(f"updated: {', '.join(stale) or 'nothing (already current)'}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
