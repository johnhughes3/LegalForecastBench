"""Render saved LegalReasonBench audit findings without calling any model."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import quote

from build_harvey_dual_audit import scrub
from harvey_dual_audit_core import BUCKETS, Json, dump, load
from harvey_dual_audit_render import cell, row
from legalreasonbench_citations import citation_pages, citation_summary, rubric_intent
from legalreasonbench_extract import redact, upstream_url
from legalreasonbench_report import (
    CATEGORIES,
    COMPARISON_NOTE,
    REPORTS,
    compare,
    summarize,
)

LABELS = {
    "gpt_6_sol": "GPT-6 Sol (blind)",
    "claude_opus_5_5": "Claude Opus 5.5 (blind)",
    "reconciliation": "Final reconciliation",
}
WARNING = (
    "> AI-generated audit judgments; no human verification or benchmark score "
    "correction is established. Authority verification labels are the auditors' "
    "assertions; citation-check results are separate."
)


def write_md(path: Path, lines: list[str]) -> None:
    path.write_text(redact(scrub("\n".join(lines).rstrip() + "\n")))


def shown(value: object) -> str:
    return "unavailable" if value is None else str(value)


def rate(numerator: int | None, denominator: int | None) -> str:
    """Show a count with its actual denominator, never inventing a missing rate."""
    if numerator is None or not denominator:
        return "unavailable"
    return f"{numerator} / {denominator} ({100 * numerator / denominator:.1f}%)"


def status(record: Json, name: str) -> str:
    return (
        shown(record[name])
        if not record["report_availability"][name]
        else record[name] or "unflagged"
    )


def criterion_table(rows: list[Json]) -> list[str]:
    lines = [
        "| Task / criterion | GPT-6 Sol blind | Opus blind | Blind bucket | "
        "Final reconciliation |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            row(
                cell(f"{r['task']} / {r['criterion']}"),
                status(r, "gpt_6_sol"),
                status(r, "claude_opus_5_5"),
                r["bucket"] or "—",
                status(r, "reconciliation"),
            )
        )
    return lines


def counts_table(counts: Json) -> list[str]:
    lines = [
        "| Report | Available / expected | Criteria with report | Findings | "
        "Flagged criteria | Problematic | Arguable |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in REPORTS:
        c = counts[name]
        lines.append(
            row(
                LABELS[name],
                f"{c['reports_available']} / {c['reports_expected']}",
                c["criteria_with_reports"],
                shown(c["findings"]),
                rate(c["flagged_criteria"], c["criteria_with_reports"]),
                rate(c["status_counts"]["problematic"], c["criteria_with_reports"]),
                rate(c["status_counts"]["arguable"], c["criteria_with_reports"]),
            )
        )
    lines += [
        "",
        "Category totals count distinct task-criterion pairs within each category. "
        "They may sum above the overall flagged-criterion count.",
        "",
        "| Category | Sol blind flagged criteria | Opus blind flagged criteria | "
        "Final flagged criteria |",
        "|---|---|---|---|",
    ]
    for category in CATEGORIES:
        lines.append(
            row(
                category,
                *(
                    rate(
                        counts[n]["categories"][category]["flagged_criteria"],
                        counts[n]["criteria_with_reports"],
                    )
                    for n in REPORTS
                ),
            )
        )
    return lines


def render_report(path: Path, record: Json | None, label: str) -> None:
    lines = [f"# {label}", "", WARNING, ""]
    if record is None:
        write_md(
            path, [*lines, "Report unavailable. No zero-finding result is inferred."]
        )
        return
    coverage = record.get("coverage", "Not supplied; see blind reports.")
    lines += [
        f"Model: {record['model']}; reasoning effort: `{record['reasoning_effort']}`.",
        "",
        f"Coverage: {coverage}",
        "",
    ]
    if not record["findings"]:
        lines += [
            "The saved report records no findings. "
            "This does not certify the rubric as correct.",
            "",
        ]
    for f in record["findings"]:
        lines += [
            f"## {f['id']}: {f['title']}",
            "",
            f"Status: **{f['status']}**; category: `{f['category']}`; "
            f"criteria: {', '.join(f['criteria']) or 'none'}.",
            "",
            f["explanation"],
            "",
            "Evidence:",
            "",
        ]
        lines += [f"- `{e['source']}`: “{cell(e['quote'])}”" for e in f["evidence"]]
        lines += ["", "Authorities (verification is asserted by the auditor):", ""]
        for a in f["authorities"]:
            citation = (
                f"[{a['citation']}]({a['url']})" if a.get("url") else a["citation"]
            )
            lines.append(
                f"- {citation}; auditor verification: {a['verified']}. "
                f"{a['proposition']}"
            )
        lines.append("")
    if "verdicts" in record:
        lines += [
            "## Verdicts on blind findings",
            "",
            "| Model | Finding | Verdict | Reason | Per-criterion verdicts |",
            "|---|---|---|---|---|",
        ]
        lines += [
            row(
                cell(v["model"]),
                cell(v["finding_id"]),
                cell(v["verdict"]),
                cell(v["reason"]),
                cell(v.get("per_criterion", [])),
            )
            for v in record["verdicts"]
        ]
    write_md(path, lines)


def render_scope(out: Path) -> None:
    census = load(out / "in-scope.json")
    selected = [t for t in census["tasks"] if t["in_scope"]]
    lines = [
        "# LegalReasonBench sample scope",
        "",
        f"Revision: `{census['revision']}`. "
        f"Classification: {census.get('classification_status', 'See census')}.",
        "",
        f"{len(selected)} of {len(census['tasks'])} assignments are in scope, with "
        f"{sum(t['criteria_total'] for t in selected)} criteria including penalties. "
        "Counts below derive from `in-scope.json`.",
        "",
        "| Assignment | In scope | Criteria (including penalties) | "
        "Penalties | Reason |",
        "|---|---|---|---|---|",
    ]
    for t in census["tasks"]:
        matter, _, assignment = t["task"].rpartition("-assignment-")
        source = upstream_url(
            f"tasks/{matter}/steps/assignment-{assignment}/instruction.md"
        )
        lines.append(
            row(
                f"[{t['task']}]({source})",
                t["in_scope"],
                t["criteria_total"],
                t["penalty_count"],
                cell(t["scope_reason"]),
            )
        )
    write_md(out / "in-scope.md", lines)


def harvey_comparison(
    out: Path, comparison: Json, harvey: Path, citations: Json | None = None
) -> None:
    """Compare derived JSON counts, explicitly retaining the method mismatch."""
    if not (harvey / "comparison.json").exists():
        return
    old = load(harvey / "comparison.json")
    index = load(harvey / "gpt-6-sol/index.json")
    old_tasks = index["tasks"]
    totals = {t["task"]: t["criteria_total"] for t in old_tasks}
    opus: dict[str, Json | None] = {}
    for task in totals:
        path = harvey / "tasks" / task / REPORTS["claude_opus_5_5"]
        opus[task] = load(path)["final"] if path.exists() else None
    old_counts = summarize(opus, totals)
    old_rows = old["rows"]
    counts = Counter(r["bucket"] for r in old_rows if r.get("bucket"))
    note = (
        "LegalReasonBench agreement uses two blind reports. Harvey agreement uses "
        "Sol's original report and Opus's final reconciled report, which saw Sol. "
        "These agreement counts are not directly comparable. Category comparisons "
        "below use Harvey's final Opus findings versus LegalReasonBench's separate "
        "final reconciliation. Neither is human verification; the corpora and "
        "denominators also differ. Harvey Sol reports lack the common category "
        "taxonomy and are not assigned invented categories."
    )
    citation_path = harvey / "citation-check/summary.json"
    old_citations = load(citation_path) if citation_path.exists() else None
    census = load(out / "in-scope.json")
    data: Json = {
        "comparability_limit": note,
        "legalreasonbench": {
            "criteria_total": comparison["criteria_total"],
            "sample_criteria_total": census.get("criteria_total"),
            "citations": citations,
            "blind_agreement": comparison["blind_agreement"],
            "final_reconciliation": comparison["report_counts"]["reconciliation"],
        },
        "harvey": {
            "criteria_total": sum(totals.values()),
            "citations": old_citations,
            "flagged_criteria": len(
                {(r["task"], r["criterion"]) for r in old_rows if r.get("bucket")}
            ),
            "agreement_buckets": {b: counts[b] for b, _ in BUCKETS},
            "final_opus": old_counts,
        },
    }
    dump(out / "comparison-to-harvey.json", data)
    lines = [
        "# Comparison with the Harvey LAB audit",
        "",
        WARNING,
        "",
        note,
        "",
        "| Audit | Criteria | Flagged criteria in agreement comparison |",
        "|---|---|---|",
        row(
            "LegalReasonBench (paired blind reports)",
            comparison["blind_agreement"]["criteria_with_both_reports"],
            rate(
                comparison["blind_agreement"]["flagged_criteria"],
                comparison["blind_agreement"]["criteria_with_both_reports"],
            ),
        ),
        row(
            "Harvey (original Sol / reconciled Opus)",
            sum(totals.values()),
            rate(data["harvey"]["flagged_criteria"], sum(totals.values())),
        ),
        "",
        "| Category | Harvey final Opus flagged criteria | "
        "LegalReasonBench final flagged criteria |",
        "|---|---|---|",
    ]
    lines += [
        row(
            c,
            rate(
                old_counts["categories"][c]["flagged_criteria"],
                old_counts["criteria_with_reports"],
            ),
            rate(
                comparison["report_counts"]["reconciliation"]["categories"][c][
                    "flagged_criteria"
                ],
                comparison["report_counts"]["reconciliation"]["criteria_with_reports"],
            ),
        )
        for c in CATEGORIES
    ]
    lines += [
        "",
        "Category denominators are criteria covered by each final report; "
        "categories overlap and do not sum to an error rate.",
        "",
        "| Agreement bucket | LegalReasonBench blind | Harvey original / reconciled |",
        "|---|---|---|",
    ]
    lines += [
        row(
            label,
            rate(
                comparison["blind_agreement"]["buckets"][b],
                comparison["blind_agreement"]["criteria_with_both_reports"],
            ),
            rate(data["harvey"]["agreement_buckets"][b], sum(totals.values())),
        )
        for b, label in BUCKETS
    ]
    lines += [
        "",
        "| Citation check | Problem citations / checked real citations |",
        "|---|---|",
        row(
            "Harvey",
            rate(old_citations["problems"], old_citations["checked"])
            if old_citations
            else "unavailable",
        ),
        row(
            "LegalReasonBench",
            rate(citations["problems"], citations["checked"])
            if citations and citations["complete"]
            else "unavailable; coverage or checks pending",
        ),
        "",
        "Harvey counts citation occurrences in task environments, including "
        "repeated documents across tasks; LegalReasonBench counts citations in "
        "unique matter documents and avoids repeated assignment copies. "
        "These citation denominators are different counting units. Fictional "
        "authorities are excluded; unable-to-verify results remain disclosed "
        "in each citation summary, not treated as verified successes.",
        "",
        f"The LegalReasonBench public sample has {shown(census.get('criteria_total'))} "
        f"criteria, with {comparison['criteria_total']} in litigation scope, "
        "clustered in a few sequential matters. This small sample does not "
        "support full-benchmark extrapolation or a causal comparison. Neither "
        "audit supplies a verified error rate or benchmark score corrections.",
    ]
    write_md(out / "comparison-to-harvey.md", lines)


def render(
    out: Path,
    harvey: Path = Path("docs/harvey-lab-audit/litigation-dispute-resolution"),
) -> None:
    comparison, reports = compare(out)
    dump(out / "comparison.json", comparison)
    render_scope(out)
    for task in reports["gpt_6_sol"]:
        task_dir = out / "tasks" / task
        for name, filename in REPORTS.items():
            render_report(
                task_dir / Path(filename).with_suffix(".md"),
                reports[name][task],
                LABELS[name],
            )
        selected = [r for r in comparison["rows"] if r["task"] == task]
        counts = {
            name: summarize({task: records[task]}, {task: len(selected)})
            for name, records in reports.items()
        }
        lines = [
            f"# Audit: {task}",
            "",
            WARNING,
            "",
            "[Source inputs](input.json) · "
            "[Instructions and prior prompts](instruction.md) · "
            "[Native upstream instructions](upstream-instruction.md)",
            "",
            COMPARISON_NOTE,
            "",
            *counts_table(counts),
            "",
            "Reports:",
            "",
        ]
        lines += [
            f"- [{LABELS[n]}]({Path(f).with_suffix('.md')})" for n, f in REPORTS.items()
        ]
        lines += ["", "## Per-criterion comparison", "", *criterion_table(selected)]
        write_md(task_dir / "README.md", lines)
    lines = [
        "# LegalReasonBench blind audit comparison",
        "",
        WARNING,
        "",
        COMPARISON_NOTE,
        "",
        f"Scope: {comparison['tasks_total']} assignments, "
        f"{comparison['criteria_total']} criteria including penalties.",
        "",
        *counts_table(comparison["report_counts"]),
        "",
        "## Blind agreement",
        "",
        f"Paired reports cover {comparison['blind_agreement']['paired_tasks']} "
        f"assignments and "
        f"{comparison['blind_agreement']['criteria_with_both_reports']} criteria.",
        "",
        "| Bucket | Criteria |",
        "|---|---|",
    ]
    lines += [
        row(label, shown(comparison["blind_agreement"]["buckets"][b]))
        for b, label in BUCKETS
    ]
    lines += [
        row(
            "Unflagged by both blind reports",
            shown(comparison["blind_agreement"]["unflagged_criteria"]),
        ),
        "",
        "## Per-criterion comparison",
        "",
        *criterion_table(comparison["rows"]),
    ]
    write_md(out / "comparison.md", lines)
    citations, records = citation_summary(out)
    check_dir = out / "citation-check"
    check_dir.mkdir(exist_ok=True)
    dump(check_dir / "summary.json", citations)
    dump(check_dir / "rubric-intent.json", rubric_intent(out, citations, records))
    for relative, content in citation_pages(citations, records).items():
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_md(destination, content)
    harvey_comparison(out, comparison, harvey, citations)
    render_index(out)


def render_index(out: Path) -> None:
    """Replace only the README index, preserving parent-authored prose verbatim."""
    path = out / "README.md"
    start, end = "<!-- file-index:start -->", "<!-- file-index:end -->"
    original = (
        path.read_text()
        if path.exists()
        else "# LegalReasonBench audit\n\n" + start + "\n" + end + "\n"
    )
    if original.count(start) != 1 or original.count(end) != 1:
        raise ValueError("Audit README needs exactly one file-index marker pair")
    before, tail = original.split(start)
    _, after = tail.split(end)
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.md"))
    if "README.md" not in files:
        files = sorted(["README.md", *files])
    lines = ["", "<details>", "<summary>Audit document index</summary>", ""]
    lines += [f"- [{cell(p)}]({quote(p, safe='/')})" for p in files]
    lines += ["", "</details>", ""]
    path.write_text(before + start + "\n".join(lines) + end + after)
