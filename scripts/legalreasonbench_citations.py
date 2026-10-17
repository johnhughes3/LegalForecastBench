"""Summarize saved citation and rubric-intent checks; never adjudicate citations."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import cast

from harvey_citation_check import ORDER, PROBLEMS, final_status
from harvey_dual_audit_core import Json, load
from harvey_dual_audit_render import cell, row
from legalreasonbench_extract import REVISION

CITATION_NOTE = (
    "AI-generated citation checks, not human legal verification or score corrections. "
    "The counting unit is a citation in a unique matter document, not each repeated "
    "assignment packet. Worker file lists and limits are reproduced below; absence "
    "of a stated limit does not independently establish exhaustive coverage. Every "
    "first-check problem requires an independent second check, including overturned "
    "findings. Missing files and pending checks never establish a zero-problem result."
)


def citation_summary(out: Path) -> tuple[Json, list[Json]]:
    """Count only saved rows, retaining real worker coverage and pending states."""
    census = load(out / "in-scope.json")
    matters = sorted(
        {
            t.get("matter_id", t["task"].rsplit("-assignment-", 1)[0])
            for t in census["tasks"]
            if t["in_scope"]
        }
    )
    records: list[Json] = []
    per_matter: list[Json] = []
    by_status: Counter[str] = Counter()
    pending = fictional = checked = first_problems = 0
    for matter in matters:
        path = out / "citation-check/results" / f"{matter}.json"
        if not path.exists():
            per_matter.append(
                {
                    "matter": matter,
                    "available": False,
                    "complete": False,
                    "coverage": None,
                    "citations": None,
                }
            )
            continue
        report = load(path)
        if report["matter"] != matter or report["dataset_revision"] != REVISION:
            raise ValueError(f"Citation matter/revision mismatch: {matter}")
        coverage = report["coverage"]
        for field in ("files_read", "limits"):
            if not isinstance(coverage[field], list):
                raise ValueError(f"Invalid citation coverage: {matter}/{field}")
        unique: dict[str, Json] = {}
        matter_pending = 0
        for citation in report["citations"]:
            ref = citation["ref"]
            if ref in unique:
                if unique[ref] != citation:
                    raise ValueError(f"Conflicting citation ref: {matter}/{ref}")
                continue
            unique[ref] = citation
            first = citation.get("first_check")
            second = citation.get("second_check")
            evidence = {"explanation", "source_urls", "excerpt_read"}
            if first and not evidence | {"status"} <= first.keys():
                raise ValueError(f"Incomplete first check: {matter}/{ref}")
            if (
                second
                and not evidence | {"revised_status", "model", "reasoning_effort"}
                <= second.keys()
            ):
                raise ValueError(f"Incomplete second check: {matter}/{ref}")
            if first and first["status"] not in ORDER:
                raise ValueError(f"Unknown citation status: {matter}/{ref}")
            if second and (not first or second["revised_status"] not in ORDER):
                raise ValueError(f"Unknown second-check status: {matter}/{ref}")
            fictional_row = citation["fictional_by_design"]
            needs_second = bool(
                not fictional_row and first and first["status"] in PROBLEMS
            )
            first_problems += int(needs_second)
            waiting = not fictional_row and (not first or (needs_second and not second))
            matter_pending += int(waiting)
            if citation["fictional_by_design"]:
                fictional += 1
            elif first:
                checked += 1
                if not waiting:
                    by_status[final_status(citation)] += 1
            records.append({"matter": matter, **citation, "pending": waiting})
        pending += matter_pending
        per_matter.append(
            {
                "matter": matter,
                "available": True,
                "model": report["model"],
                "reasoning_effort": report["reasoning_effort"],
                "coverage": coverage,
                "citations": len(unique),
                "pending_checks": matter_pending,
                "complete": bool(coverage["files_read"])
                and not coverage["limits"]
                and matter_pending == 0,
            }
        )
    complete = bool(per_matter) and all(m["complete"] for m in per_matter)
    available = any(m["available"] for m in per_matter)
    observed = sum(by_status[s] for s in PROBLEMS)
    return {
        "dataset_revision": REVISION,
        "counting_unit": "citation in a unique matter document",
        "matters_expected": len(matters),
        "matters_available": sum(m["available"] for m in per_matter),
        "complete": complete,
        "citation_instances": len(records) if available else None,
        "fictional_by_design": fictional if available else None,
        "checked": checked if available else None,
        "first_check_problems": first_problems if available else None,
        "pending_checks": pending if available else None,
        "by_final_status": {s: by_status[s] for s in ORDER} if available else None,
        "observed_final_problems": observed if available else None,
        "problems": observed if complete else None,
        "problem_rate": observed / checked if complete and checked else None,
        "per_matter": per_matter,
    }, records


def rubric_intent(out: Path, summary: Json, citations: list[Json]) -> Json:
    """Link saved intent judgments without inferring intent from errors."""
    by_ref = {(c["matter"], c["ref"]): c for c in citations}
    records: list[Json] = []
    missing: list[str] = []
    unavailable = {m["matter"] for m in summary["per_matter"] if not m["available"]}
    for matter in (m["matter"] for m in summary["per_matter"]):
        path = out / "citation-check/intent" / f"{matter}.json"
        if not path.exists():
            missing.append(matter)
            continue
        report = load(path)
        if report["matter"] != matter:
            raise ValueError(f"Intent matter mismatch: {matter}")
        seen: set[str] = set()
        for record in report["records"]:
            key = (matter, record["ref"])
            if (key not in by_ref and matter not in unavailable) or record[
                "ref"
            ] in seen:
                raise ValueError(
                    f"Unknown or duplicate intent citation: {matter}/{record['ref']}"
                )
            seen.add(record["ref"])
            citation = by_ref.get(key)
            records.append(
                {
                    "matter": matter,
                    **record,
                    "first_check_status": cast(
                        Json, citation.get("first_check") or {}
                    ).get("status")
                    if citation
                    else None,
                    "final_status": None
                    if not citation or citation["pending"]
                    else final_status(citation),
                }
            )
    mapped = {(r["matter"], r["ref"]) for r in records}
    unmapped = [
        {"matter": c["matter"], "ref": c["ref"]}
        for c in citations
        if (c["matter"], c["ref"]) not in mapped
        and not c["fictional_by_design"]
        and cast(Json, c.get("first_check") or {}).get("status") in PROBLEMS
    ]
    return {
        "complete": summary["complete"] and not missing and not unmapped,
        "missing_matters": missing,
        "first_check_problems_without_intent": unmapped,
        "records_available": len(records) if records else None,
        "targeted_by_instructions": sum(
            r["targeted_by_instructions"] is True for r in records
        )
        if records
        else None,
        "targeted_by_criteria": sum(bool(r["targeted_by_criteria"]) for r in records)
        if records
        else None,
        "rewards_reliance": sum(bool(r["rewards_reliance"]) for r in records)
        if records
        else None,
        "records": records,
    }


def citation_pages(summary: Json, records: list[Json]) -> dict[Path, list[str]]:
    """Render all worker evidence and an explicit pending/overturned problem list."""
    display = {k: "unavailable" if v is None else v for k, v in summary.items()}
    overview = [
        "# LegalReasonBench citation check",
        "",
        CITATION_NOTE,
        "",
        "[Summary JSON](summary.json) · [Problems and second checks](problems.md) · "
        "[Rubric intent](rubric-intent.json)",
        "",
        f"Complete: {summary['complete']}. Available matter reports: "
        f"{summary['matters_available']} / {summary['matters_expected']}.",
        "",
        f"Checked real citations in available reports: {display['checked']}. "
        f"Fictional by design (excluded): {display['fictional_by_design']}. "
        f"Pending checks: {display['pending_checks']}.",
        "",
        "Problem rate: "
        + (
            f"{100 * summary['problem_rate']:.1f}% "
            f"({summary['problems']} / {summary['checked']})."
            if summary["problem_rate"] is not None
            else "unavailable; coverage or checks pending."
        ),
        "",
        "Final statuses for completed real-citation checks only:",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    overview += [
        row(s, cast(Json, summary["by_final_status"] or {}).get(s, "unavailable"))
        for s in ORDER
    ]
    problems = [
        "# Citation problems and independent second checks",
        "",
        CITATION_NOTE,
        "",
        "Includes every first-check problem, even if overturned, plus later problems. "
        "Unavailable reports or pending checks prevent a complete result.",
        "",
        "| Matter / ref | Document / location | First status | "
        "Second status | Explanation |",
        "|---|---|---|---|---|",
    ]
    pages: dict[Path, list[str]] = {}
    for m in summary["per_matter"]:
        overview += ["", f"## {m['matter']}", ""]
        if not m["available"]:
            overview += ["Report unavailable; coverage and findings pending."]
            continue
        coverage = m["coverage"]
        overview += [
            f"Model: {m['model']}; reasoning effort: {m['reasoning_effort']}.",
            "",
            f"Worker counting unit: {coverage['counting_unit']}",
            "",
            "Files read (worker reported):",
            "",
        ]
        overview += [f"- {cell(f)}" for f in coverage["files_read"]] or [
            "- unavailable"
        ]
        overview += ["", "Coverage limits:", ""]
        overview += [f"- {cell(limit)}" for limit in coverage["limits"]] or [
            "- No limits stated by worker; "
            "exhaustive coverage not independently verified."
        ]
        overview += ["", f"[Full citation evidence](results/{m['matter']}.md)"]
        lines = [
            f"# Citation checks: {m['matter']}",
            "",
            CITATION_NOTE,
            "",
            f"Model: {m['model']}; reasoning effort: {m['reasoning_effort']}.",
            "",
            f"Worker coverage: {coverage}",
            "",
        ]
        for c in [c for c in records if c["matter"] == m["matter"]]:
            first, second = c.get("first_check"), c.get("second_check")
            first_status = (
                first["status"]
                if first
                else "excluded by design"
                if c["fictional_by_design"]
                else "pending"
            )
            second_status = (
                second["revised_status"]
                if second
                else "pending"
                if first_status in PROBLEMS and not c["fictional_by_design"]
                else "not required"
            )
            lines += [
                f"## {c['ref']}: {c['authority']}",
                "",
                f"Document: {c['document']}; location: {c['location']}.",
                "",
                f"Authority type: {c['authority_type']}; "
                f"as written: {c['citation_as_written']}; "
                f"pincite: {c['pincite']}.",
                "",
                f"Cited for: {c['cited_for']}",
                "",
                f"Quotes: {c['quotes']}",
                "",
                f"Context: {c['context']}",
                "",
                f"Fictional by design: {c['fictional_by_design']}; "
                f"{c['fictional_reason']}",
                "",
            ]
            for label, check, status in (
                ("First check", first, first_status),
                ("Second check", second, second_status),
            ):
                lines += [f"### {label}: {status}", ""]
                if check:
                    lines += [
                        check["explanation"],
                        "",
                        f"Excerpt read: {check['excerpt_read']}",
                        "",
                    ]
                    lines += [f"- {url}" for url in check["source_urls"]]
                    if label == "Second check":
                        lines += [
                            "",
                            f"Model: {check['model']}; "
                            f"reasoning effort: {check['reasoning_effort']}.",
                        ]
                lines.append("")
            if not c["fictional_by_design"] and (
                first_status in PROBLEMS or (second and second_status in PROBLEMS)
            ):
                explanation = cast(Json, second or first or {}).get(
                    "explanation", "pending"
                )
                problems.append(
                    row(
                        cell(f"{m['matter']} / {c['ref']}"),
                        cell(f"{c['document']} / {c['location']}"),
                        first_status,
                        second_status,
                        cell(explanation),
                    )
                )
        pages[Path("citation-check/results") / f"{m['matter']}.md"] = lines
    pages[Path("citation-check/README.md")] = overview
    pages[Path("citation-check/problems.md")] = problems
    return pages
