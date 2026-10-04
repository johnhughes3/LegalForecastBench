"""Markdown rendering for the GPT-6 Sol / Claude Opus 5.5 dual audit.

See ``build_harvey_dual_audit.py`` for the command-line entry point."""

from __future__ import annotations

import re
from pathlib import Path

from harvey_dual_audit_core import (
    AUDIT_DIR,
    BANNER,
    BUCKETS,
    COMPARISON_NOTE,
    END,
    METHOD_NOTE,
    OPUS_MD,
    PINNED,
    START,
    TASKS_URL,
    Json,
    as_dict,
    as_list,
    dump,
)
from harvey_model_runs import CONDITIONS, RUNS_DIR, SHORT, run_grades


def crit_link(record: Json, crit: str) -> str:
    line = as_dict(record.get("criterion_lines")).get(crit)
    anchor = f"#L{line}" if line else ""
    return f"[{crit}]({TASKS_URL}/{record['task']}/task.json{anchor})"


def row(*cells: object) -> str:
    """One Markdown table row."""
    return "| " + " | ".join(str(c) for c in cells) + " |"


def cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def sol_report_name(task_dir: Path) -> str:
    return (
        "gpt-6-sol-audit.md"
        if (task_dir / "gpt-6-sol-audit.md").exists()
        else "README.md"
    )


def render_opus_report(record: Json, task_dir: Path) -> None:
    final = as_dict(record["final"])
    blind = as_dict(record["blind"])
    findings = [as_dict(f) for f in as_list(final.get("findings"))]
    out: list[str] = [
        f"# Claude Opus 5.5 audit: {record['title']}",
        "",
        BANNER.format(up="../../"),
        "",
        " · ".join(
            [
                "[Task landing page](README.md)",
                f"[GPT-6 Sol report]({sol_report_name(task_dir)})",
                f"[Pinned rubric]({TASKS_URL}/{record['task']}/task.json)",
                f"Harvey commit `{PINNED[:12]}`",
            ]
        ),
        "",
        f"**Model:** {record['model']}, "
        f"reasoning effort `{record['reasoning_effort']}`. "
        f"**Rubric criteria:** {record['criteria_total']}. "
        f"**Workflow run:** `{record['workflow_run_id']}`.",
        "",
        METHOD_NOTE,
        "",
        "## Overall assessment",
        "",
        str(final.get("overall", "")),
        "",
        "## Findings",
        "",
    ]
    if not findings:
        out += [
            "No defect established. That is not certification that every "
            "criterion is correct.",
            "",
        ]
    else:
        out += [
            "| ID | Status | Category | Criteria | Finding | Origin |",
            "|---|---|---|---|---|---|",
        ]
        for f in findings:
            crits = (
                ", ".join(crit_link(record, str(c)) for c in as_list(f.get("criteria")))
                or "—"
            )
            fid = str(f["id"])
            out.append(
                row(
                    f"[{fid}](#{fid.lower()})",
                    f["status"],
                    f["category"],
                    crits,
                    cell(f["title"]),
                    cell(f.get("origin", "blind")),
                )
            )
        out.append("")
        for f in findings:
            out += render_finding(record, f)
    out += render_sol_verdicts(record, final)
    out += [
        "## Blind pass and what changed",
        "",
        str(final.get("changes_from_blind", "")),
        "",
        "Blind-pass findings (before reading GPT-6 Sol):",
        "",
    ]
    blind_findings = [as_dict(f) for f in as_list(blind.get("findings"))]
    if not blind_findings:
        out.append("- None.")
    for f in blind_findings:
        crits = ", ".join(str(c) for c in as_list(f.get("criteria"))) or "no criterion"
        out.append(f"- **{f['id']}** ({f['status']}; {crits}): {f['title']}")
    out += [
        "",
        "## Coverage and limits",
        "",
        f"Blind pass: {blind.get('coverage', '')}",
        "",
        f"Reconciliation: {final.get('coverage', '')}",
        "",
    ]
    (task_dir / OPUS_MD).write_text("\n".join(out), encoding="utf-8")


def render_finding(record: Json, f: Json) -> list[str]:
    crits = (
        ", ".join(crit_link(record, str(c)) for c in as_list(f.get("criteria")))
        or "none"
    )
    out = [
        f'<a id="{str(f["id"]).lower()}"></a>',
        f"### {f['id']}. {f['title']}",
        "",
        f"**Status:** {f['status']} · **Category:** {f['category']} · "
        f"**Criteria:** {crits}",
        "",
        str(f.get("explanation", "")),
        "",
    ]
    evidence = [as_dict(e) for e in as_list(f.get("evidence"))]
    if evidence:
        out.append("Evidence:")
        out += [
            f"- `{e.get('source', '')}`: “{cell(e.get('quote', ''))}”" for e in evidence
        ]
        out.append("")
    authorities = [as_dict(a) for a in as_list(f.get("authorities"))]
    if authorities:
        out.append("Authorities (✓ = primary text checked in the auditing session):")
        for a in authorities:
            mark = "✓" if a.get("verified") else "unverified"
            out.append(
                f"- {a.get('citation', '')} ({mark}): {cell(a.get('proposition', ''))}"
            )
        out.append("")
    if f.get("suggested_fix"):
        out += [f"Suggested fix: {f['suggested_fix']}", ""]
    related = as_list(f.get("sol_locators"))
    if related:
        out += [
            f"Related GPT-6 Sol findings: {', '.join(str(r) for r in related)}.",
            "",
        ]
    return out


def render_sol_verdicts(record: Json, final: Json) -> list[str]:
    verdicts = [as_dict(v) for v in as_list(final.get("sol_verdicts"))]
    out = ["## Verdicts on GPT-6 Sol's findings", ""]
    if not verdicts:
        return [*out, "GPT-6 Sol reported no findings for this task.", ""]
    out += [
        "| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |",
        "|---|---|---|---|---|",
    ]
    for v in verdicts:
        per = {
            str(p["criterion"]): str(p["verdict"])
            for p in map(as_dict, as_list(v.get("per_criterion")))
        }
        links: list[str] = []
        for c in as_list(v.get("sol_criteria")):
            link = crit_link(record, str(c))
            if v.get("verdict") == "mixed" and str(c) in per:
                link += f" ({per[str(c)]})"
            links.append(link)
        out.append(
            row(
                cell(v["sol_locator"]),
                cell(v["sol_status"]),
                ", ".join(links) or "—",
                cell(v["verdict"]),
                cell(v["reason"]),
            )
        )
    return [*out, ""]


def status_word(value: object) -> str:
    return str(value) if value else "—"


def render_task_section(record: Json, rows: list[Json], task_dir: Path) -> None:
    readme = task_dir / "README.md"
    text = readme.read_text(encoding="utf-8")
    flagged = [r for r in rows if r["bucket"] or r["claude_opus_5_5_blind"]]
    counts = {key: sum(1 for r in rows if r["bucket"] == key) for key, _ in BUCKETS}
    section = [
        START,
        "## Dual-audit comparison",
        "",
        f"Reports: [GPT-6 Sol]({sol_report_name(task_dir)}) · "
        f"[Claude Opus 5.5]({OPUS_MD}). Criteria flagged by either model: "
        f"{sum(counts.values())} of {record['criteria_total']}. "
        + "; ".join(f"{label.lower()}: {counts[key]}" for key, label in BUCKETS)
        + ".",
        "",
    ]
    task = str(record["task"])
    if (RUNS_DIR / task).is_dir():
        section += [
            "Model runs: "
            + " · ".join(
                f"[{label}](../../model-runs/{task}/{slug}/README.md)"
                for slug, label, *_ in CONDITIONS
            )
            + ". The Runs column gives each run's native verdicts (P pass, F fail) "
            "from Sonnet 4.6 / GPT-5.5 and links to the judges' reasoning.",
            "",
        ]
    if flagged:
        section += [
            "| Criterion | GPT-6 Sol | Claude Opus 5.5 | Opus blind pass | Agreement "
            "| Runs |",
            "|---|---|---|---|---|---|",
        ]
        labels = dict(BUCKETS)
        for r in flagged:
            agreement = (
                labels.get(str(r["bucket"]), "neither (final)")
                if r["bucket"]
                else "neither (final)"
            )
            section.append(
                row(
                    crit_link(record, str(r["criterion"])),
                    status_word(r["gpt_6_sol"]),
                    status_word(r["claude_opus_5_5"]),
                    status_word(r["claude_opus_5_5_blind"]),
                    agreement,
                    run_grades(task, str(r["criterion"]), "../../"),
                )
            )
        section.append("")
    section.append(END)
    block = "\n".join(section)
    text = text.replace(
        f"[Read the audit report]({sol_report_name(task_dir)})",
        f"[Read the GPT-6 Sol report]({sol_report_name(task_dir)}) · "
        f"[Read the Claude Opus 5.5 report]({OPUS_MD})",
    )
    if START in text:
        text = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            lambda _m: block,
            text,
            flags=re.S,
        )
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    readme.write_text(text, encoding="utf-8")


def bucket_page(key: str) -> str:
    return f"comparison/{key.replace('_', '-')}.md"


def render_bucket_page(
    key: str, label: str, rows: list[Json], records: dict[str, Json]
) -> None:
    """One page per agreement group, so each stays within GitHub's render limit."""
    out = [
        f"# {label}",
        "",
        BANNER.format(up="../"),
        "",
        f"[Back to the comparison overview](../comparison.md). {len(rows)} criteria "
        f"across {len({r['task'] for r in rows})} tasks.",
        "",
    ]
    if not rows:
        out.append("None.")
    else:
        out += [
            "| Task | Criterion | GPT-6 Sol | Claude Opus 5.5 |",
            "|---|---|---|---|",
        ]
        for r in rows:
            record = records[str(r["task"])]
            sol_text = f"**{status_word(r['gpt_6_sol'])}**: " + "; ".join(
                r["sol_findings"]
            )
            if key == "sol_only" and r["opus_on_sol"]:
                opus_text = "**not a defect**: " + "; ".join(r["opus_on_sol"])
            else:
                opus_status = status_word(r["claude_opus_5_5"])
                opus_text = f"**{opus_status}**: " + "; ".join(r["opus_findings"])
            out.append(
                row(
                    f"[{r['task']}](../tasks/{r['task']}/README.md)",
                    crit_link(record, str(r["criterion"])),
                    cell(sol_text),
                    cell(opus_text),
                )
            )
    out.append("")
    path = AUDIT_DIR / bucket_page(key)
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


def render_comparison(
    all_rows: list[Json], records: dict[str, Json], warnings: list[str]
) -> None:
    flagged = [r for r in all_rows if r["bucket"]]
    out = [
        "# GPT-6 Sol and Claude Opus 5.5: where the two audits agree and differ",
        "",
        BANNER.format(up=""),
        "",
        COMPARISON_NOTE,
        "",
        "## Totals",
        "",
        "| Agreement | Criteria | Tasks |",
        "|---|---:|---:|",
    ]
    for key, label in BUCKETS:
        rows = [r for r in flagged if r["bucket"] == key]
        tasks = {r["task"] for r in rows}
        out.append(row(f"[{label}]({bucket_page(key)})", len(rows), len(tasks)))
    total_criteria = sum(int(r["criteria_total"]) for r in records.values())
    blind_flagged = sum(1 for r in all_rows if r["claude_opus_5_5_blind"])
    adopted = sum(
        1 for r in all_rows if r["claude_opus_5_5"] and not r["claude_opus_5_5_blind"]
    )
    dropped = sum(
        1 for r in all_rows if r["claude_opus_5_5_blind"] and not r["claude_opus_5_5"]
    )
    out += [
        "",
        f"Denominator: {total_criteria} criteria across {len(records)} tasks. "
        "Counts are criterion-level flags, not a verified error rate or a score "
        f"correction. Claude Opus 5.5 flagged {blind_flagged} criteria in its "
        f"blind pass; after reading GPT-6 Sol it added {adopted} and withdrew "
        f"{dropped}.",
        "",
        "## By task",
        "",
        row(
            "Task",
            "Criteria",
            "Both problematic",
            "Both arguable",
            "Split",
            "Sol only",
            "Opus only",
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for task in sorted(records):
        rows = [r for r in flagged if r["task"] == task]
        c = {key: sum(1 for r in rows if r["bucket"] == key) for key, _ in BUCKETS}
        title = cell(records[task]["title"])
        out.append(
            row(
                f"[{title}](tasks/{task}/README.md)",
                records[task]["criteria_total"],
                *(c[key] for key, _ in BUCKETS),
            )
        )
    for key, label in BUCKETS:
        in_bucket = [r for r in flagged if r["bucket"] == key]
        render_bucket_page(key, label, in_bucket, records)
    if warnings:
        out += [
            "",
            "## Same criterion, different grounds",
            "",
            "These criteria count as flagged by both models, but Claude Opus 5.5 "
            "rejected GPT-6 Sol's reason and flags them for a reason of its own.",
            "",
        ]
        out += [f"- {w}" for w in warnings]
    out.append("")
    (AUDIT_DIR / "comparison.md").write_text("\n".join(out), encoding="utf-8")
    dump(
        AUDIT_DIR / "comparison.json",
        {
            "harvey_commit": PINNED,
            "buckets": {key: label for key, label in BUCKETS},
            "status_notes": (
                "GPT-6 Sol 'confirmed' is shown as 'problematic'. Rows list only "
                "criteria flagged by either model or by Opus's blind pass."
            ),
            "rows": all_rows,
        },
    )


DOCS_INDEX = Path("docs/README.md")

INDEX_OPEN = "<summary>Audit report file index (AI-generated and unverified)</summary>"

LINK_NAMES = {
    "README.md": "README",
    "comparison.md": "comparison",
    "gpt-6-sol-audit.md": "GPT-6 Sol",
    "gpt-6-sol-summary.md": "GPT-6 Sol summary",
    OPUS_MD: "Claude Opus 5.5",
}


def index_label(path: Path) -> str:
    rel = path.relative_to(AUDIT_DIR)
    if rel.parts[0] == "model-runs" and len(rel.parts) > 3:
        short = SHORT.get(rel.parts[2], rel.parts[2])
        return f"{short} run" if path.name == "README.md" else f"{short}: {path.stem}"
    return LINK_NAMES.get(path.name, path.stem)


def render_docs_index() -> None:
    """Rewrite the audit file index in docs/README.md from the files on disk."""
    groups: dict[str, list[Path]] = {}
    for md in sorted(AUDIT_DIR.rglob("*.md")):
        rel = md.relative_to(AUDIT_DIR)
        # One line per task for its model runs, rather than one per run folder.
        nested = rel.parts[0] == "model-runs" and len(rel.parts) > 2
        key = "/".join(rel.parts[:2]) if nested else ""
        groups.setdefault(key or rel.parent.as_posix(), []).append(md)
    order = sorted(groups, key=lambda g: (g != ".", g.startswith("tasks/"), g))
    lines = ["", INDEX_OPEN, ""]
    for group in order:
        rank = list(LINK_NAMES)
        files = sorted(
            groups[group],
            key=lambda p: (rank.index(p.name) if p.name in rank else len(rank), p.name),
        )
        links = " · ".join(
            f"[{index_label(p)}]({p.relative_to(DOCS_INDEX.parent).as_posix()})"
            for p in files
        )
        label = "Audit overview" if group == "." else group
        lines.append(f"- **{label}:** {links}")
    text = DOCS_INDEX.read_text(encoding="utf-8")
    start = text.index(INDEX_OPEN)
    end = text.index("</details>", start)
    head = text[:start].rstrip("\n")
    DOCS_INDEX.write_text(
        head + "\n".join(lines) + "\n\n" + text[end:], encoding="utf-8"
    )
