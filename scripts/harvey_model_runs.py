"""Publish and read Harvey LAB litigation model runs: deliverables and native grades.

Two solver conditions ran all 52 litigation-dispute-resolution tasks, and LAB's standard
judge pair graded every run. The complete experiment is preserved privately as
``ARCHIVE``. This script copies the parts readers need into
``docs/harvey-lab-audit/litigation-dispute-resolution/model-runs/``: each run's
deliverables exactly as produced, a Markdown rendering of each DOCX/XLSX deliverable
for reading on GitHub, both judges' raw score files, and a run page listing every
criterion's verdicts and the judges' reasoning. Transcripts, solver workspaces, usage
logs, and HTML reports stay in the archive.

Subcommand:

``import``
    Rebuild ``model-runs/`` from the ``results/`` directory of the extracted archive.
    Refuses partial data: every task needs exactly one run per condition, and each
    judge must have graded every criterion. Rendering DOCX needs ``pandoc``.

Example::

    uv run python scripts/harvey_model_runs.py import --results /path/to/archive/results

The task pages and the human-review worksheet read the published copies, so they can
be regenerated from the repository alone."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import openpyxl
from harvey_dual_audit_core import (
    AUDIT_DIR,
    OPUS_JSON,
    TASKS_URL,
    Json,
    as_dict,
    as_list,
    load,
)

RUNS_DIR = AUDIT_DIR / "model-runs"

ARCHIVE = "harvey-lab-litigation-complete-2026-10-03"

ARCHIVE_SHA256 = "8c30498e76325e924d3e9174fde9e994fa39c59b967af9c2483f8cf1f79897b1"

# Directory slug, display label, provider model id, reasoning effort.
CONDITIONS = (
    ("gpt6luna-xhigh", "GPT-6 Luna (xhigh)", "gpt-6-luna", "xhigh"),
    ("opus55-low", "Claude Opus 5.5 (low)", "claude-opus-5-5", "low"),
)

JUDGES = (("claude-sonnet-4-6", "Sonnet 4.6"), ("gpt-5.5", "GPT-5.5"))

SHORT = {"gpt6luna-xhigh": "Luna", "opus55-low": "Opus"}

BANNER = (
    "> [!NOTE]\n"
    "> **Unedited model output and AI judge grades.** The deliverables are "
    "AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts "
    "are the native "
    "LAB judges' AI judgments, not human review or accepted corrections. See the "
    "[model-runs overview]({up}README.md)."
)


def run_dir(task: str, condition: str) -> Path:
    return RUNS_DIR / task / condition


def scores(task: str, condition: str) -> dict[str, Json]:
    """Published score file per judge; empty when the run is not published."""
    out: dict[str, Json] = {}
    for judge, _label in JUDGES:
        path = run_dir(task, condition) / f"scores_{judge}.json"
        if path.exists():
            out[judge] = as_dict(load(path))
    return out


def results_by_criterion(score: Json) -> dict[str, Json]:
    return {
        str(r["id"]): r for r in map(as_dict, as_list(score.get("criteria_results")))
    }


def verdict_word(result: Json | None) -> str:
    return str(result.get("verdict", "?")).capitalize() if result else "—"


def run_grades(task: str, crit: str, up: str) -> str:
    """Compact per-run verdicts for one criterion, e.g. ``Luna F/P · Opus P/P``.

    ``up`` is the relative path from the calling page to the audit directory. Each
    entry links to that criterion's judge reasoning on the run page."""
    cells: list[str] = []
    for slug, *_ in CONDITIONS:
        judged = scores(task, slug)
        if not judged:
            continue
        marks = "/".join(
            verdict_word(results_by_criterion(judged[j]).get(crit))[:1]
            for j, _ in JUDGES
        )
        link = f"{up}model-runs/{task}/{slug}/README.md#{crit.lower()}"
        cells.append(f"{SHORT[slug]} [{marks}]({link})")
    return " · ".join(cells) or "—"


def one_line(text: object) -> str:
    return " ".join(str(text).split())


def render_docx(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", "-f", "docx", "-t", "gfm", "--wrap=none", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def render_xlsx(path: Path) -> str:
    out: list[str] = []
    for sheet in openpyxl.load_workbook(path).worksheets:
        out += [f"## Sheet: {sheet.title}", ""]
        rows = [
            ["" if v is None else str(v).replace("|", "\\|") for v in row]
            for row in sheet.iter_rows(values_only=True)
            if any(v is not None for v in row)
        ]
        if not rows:
            out += ["(empty)", ""]
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + "---|" * width)
        out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        out.append("")
    return "\n".join(out)


def publish_output(src: Path, dest_dir: Path) -> list[str]:
    """Copy one deliverable and, for DOCX/XLSX, write a readable rendering beside it."""
    shutil.copy2(src, dest_dir / src.name)
    renderers = {".docx": render_docx, ".xlsx": render_xlsx}
    renderer = renderers.get(src.suffix.lower())
    link = f"[{src.name}](output/{src.name})"
    if renderer is None:
        return [f"- {link}"]
    rendered = dest_dir / f"{src.name}.md"
    rendered.write_text(
        f"<!-- Rendered from {src.name} for reading; the original file is the "
        f"deliverable. -->\n\n{renderer(src).rstrip()}\n",
        encoding="utf-8",
    )
    return [f"- {link} ([read as Markdown](output/{rendered.name}))"]


def run_page(
    record: Json, condition: tuple[str, str, str, str], run_id: str, outputs: list[str]
) -> str:
    task = str(record["task"])
    slug, label, model, effort = condition
    judged = scores(task, slug)
    other = next(c for c in CONDITIONS if c[0] != slug)
    lines = as_dict(record.get("criterion_lines"))
    by_judge = {j: results_by_criterion(judged[j]) for j, _ in JUDGES}
    all_pass = [bool(judged[j].get("all_pass")) for j, _ in JUDGES]
    out = [
        f"# {label}: {record['title']}",
        "",
        BANNER.format(up="../../"),
        "",
        " · ".join(
            [
                f"[Task audit page](../../../tasks/{task}/README.md)",
                f"[Pinned task and rubric]({TASKS_URL}/{task}/task.json)",
                f"[{other[1]} run](../{other[0]}/README.md)",
                "[All runs](../../README.md)",
            ]
        ),
        "",
        f"**Model:** `{model}`, reasoning effort `{effort}`. **Run:** `{run_id}`.",
        "",
        "**Native grades:** "
        + "; ".join(
            f"{jl} passed {judged[j]['n_passed']} of {judged[j]['n_criteria']} criteria"
            for j, jl in JUDGES
        )
        + f". LAB all-pass score: {sum(all_pass) / len(all_pass):g} (mean of the "
        "judges' all-pass results; a task scores 1 with a judge only if every "
        "criterion passes).",
        "",
        "## Deliverables",
        "",
        *outputs,
        "",
        "## Grades",
        "",
        "Failures are in bold. Each criterion links to both judges' reasoning below.",
        "",
        "| Criterion | Title | " + " | ".join(jl for _, jl in JUDGES) + " |",
        "|---|---|" + "---|" * len(JUDGES),
    ]
    crits = sorted(by_judge[JUDGES[0][0]], key=lambda c: int(c.split("-")[1]))
    for crit in crits:
        words = [verdict_word(by_judge[j].get(crit)) for j, _ in JUDGES]
        cells = [f"**{w}**" if w == "Fail" else w for w in words]
        title = one_line(by_judge[JUDGES[0][0]][crit].get("title", "")).replace(
            "|", "\\|"
        )
        out.append(
            f"| [{crit}](#{crit.lower()}) | {title} | " + " | ".join(cells) + " |"
        )
    out += ["", "## Judge reasoning", ""]
    for crit in crits:
        line = lines.get(crit)
        rubric = f"{TASKS_URL}/{task}/task.json" + (f"#L{line}" if line else "")
        out += [
            f"### {crit}",
            "",
            f"{one_line(by_judge[JUDGES[0][0]][crit].get('title', ''))} "
            f"([rubric]({rubric}))",
            "",
        ]
        for j, jl in JUDGES:
            result = by_judge[j].get(crit)
            reasoning = one_line(result.get("reasoning", "")) if result else ""
            out.append(f"- **{jl}: {verdict_word(result)}.** {reasoning}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def index_page(records: list[Json]) -> str:
    out = [
        "# Harvey LAB litigation model runs: deliverables and native grades",
        "",
        BANNER.format(up="").replace(
            " See the [model-runs overview](README.md).",
            " See the [audit overview](../README.md).",
        ),
        "",
        "Two solver conditions ran all 52 tasks in Harvey LAB's "
        "litigation-dispute-resolution folder with the original instructions, "
        "documents, and rubrics. LAB's standard judge pair graded every run.",
        "",
        "| Condition | Model | Reasoning effort |",
        "|---|---|---|",
        *[
            f"| {label} | `{model}` | `{effort}` |"
            for _, label, model, effort in CONDITIONS
        ],
        "",
        "Judges: " + " and ".join(f"{jl} (`{j}`)" for j, jl in JUDGES) + ". "
        "Each run page lists the deliverables as produced, a Markdown rendering of "
        "each DOCX/XLSX deliverable, both judges' raw score files, and every "
        "criterion's verdicts with the judges' reasoning.",
        "",
        f"Copied from the complete private experiment archive `{ARCHIVE}` "
        f"(SHA-256 `{ARCHIVE_SHA256}`) by "
        "[`scripts/harvey_model_runs.py`](../../../../scripts/harvey_model_runs.py). "
        "Solver transcripts, workspaces, usage logs, and HTML reports remain in that "
        "archive. Nothing here was edited; no grade was replaced with an audit "
        "conclusion.",
        "",
        "Cells show criteria passed by Sonnet 4.6 / GPT-5.5.",
        "",
        "| Task | Criteria | " + " | ".join(c[1] for c in CONDITIONS) + " |",
        "|---|---:|" + "---|" * len(CONDITIONS),
    ]
    for record in records:
        task = str(record["task"])
        cells: list[str] = []
        for slug, *_ in CONDITIONS:
            judged = scores(task, slug)
            passed = " / ".join(str(judged[j]["n_passed"]) for j, _ in JUDGES)
            cells.append(f"[{passed}]({task}/{slug}/README.md)")
        out.append(
            f"| [{record['title']}](../tasks/{task}/README.md) | "
            f"{record['criteria_total']} | " + " | ".join(cells) + " |"
        )
    return "\n".join(out) + "\n"


def import_runs(results: Path) -> None:
    base = results / "litigation-dispute-resolution"
    tasks = sorted(p.name for p in base.iterdir() if p.is_dir())
    expected = sorted(p.name for p in (AUDIT_DIR / "tasks").iterdir() if p.is_dir())
    if tasks != expected:
        raise SystemExit("archive tasks do not match the audit's task directories")
    if RUNS_DIR.exists():
        shutil.rmtree(RUNS_DIR)
    records: list[Json] = []
    for task in tasks:
        record = as_dict(load(AUDIT_DIR / "tasks" / task / OPUS_JSON))
        records.append(record)
        for condition in CONDITIONS:
            runs = sorted(p for p in (base / task / condition[0]).iterdir())
            if len(runs) != 1:
                raise SystemExit(f"{task}/{condition[0]}: expected one run")
            src, dest = runs[0], run_dir(task, condition[0])
            (dest / "output").mkdir(parents=True)
            for judge, _label in JUDGES:
                score = as_dict(load(src / f"scores_{judge}.json"))
                graded = results_by_criterion(score)
                if len(graded) != record["criteria_total"]:
                    raise SystemExit(f"{task}/{condition[0]}: {judge} is incomplete")
                shutil.copy2(src / f"scores_{judge}.json", dest)
            outputs: list[str] = []
            for path in sorted((src / "output").iterdir()):
                outputs += publish_output(path, dest / "output")
            page = run_page(record, condition, src.name, outputs)
            (dest / "README.md").write_text(page, encoding="utf-8")
    (RUNS_DIR / "README.md").write_text(index_page(records), encoding="utf-8")
    print(f"published {len(tasks) * len(CONDITIONS)} runs into {RUNS_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="rebuild model-runs/ from an archive")
    imp.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    import_runs(args.results)


if __name__ == "__main__":
    main()
