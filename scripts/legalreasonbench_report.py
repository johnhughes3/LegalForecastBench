"""Deterministic counts for separate blind LegalReasonBench audit reports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import cast

from harvey_dual_audit_core import (
    BUCKETS,
    RANK,
    Json,
    as_dict,
    as_list,
    bucket,
    load,
    opus_statuses,
)

REPORTS = {
    "gpt_6_sol": "gpt-6-sol-audit.json",
    "claude_opus_5_5": "claude-opus-5-5-audit.json",
    "reconciliation": "reconciliation.json",
}
CATEGORIES = (
    "legal_error",
    "unsupported_fact",
    "source_conflict",
    "internal_inconsistency",
    "ambiguous_or_unjudgeable",
    "unrequested_requirement",
    "document_defect",
)
COMPARISON_NOTE = (
    "Agreement buckets use the two saved blind reports only. Reconciliation is "
    "counted separately and never replaces a blind report. Each criterion takes "
    "the strongest status among that report's findings. A criterion can occur in "
    "multiple categories; category counts deduplicate within task and category. "
    "Missing reports are unavailable, never zero findings. Counts describe AI "
    "reviewer judgments, not human-verified errors or corrected benchmark scores."
)


def read_report(path: Path, task: str, criteria: set[str]) -> Json | None:
    """Read available reports, rejecting status/schema mistakes that corrupt counts."""
    if not path.exists():
        return None
    record: Json = load(path)
    required = {"model", "reasoning_effort", "findings"}
    if path.name != REPORTS["reconciliation"]:
        required |= {"task", "criteria_total", "coverage"}
        if record.get("task") != task or record.get("criteria_total") != len(criteria):
            raise ValueError(
                f"Task or rubric denominator mismatch in {path.name}: {task}"
            )
    else:
        required.add("verdicts")
    if not required <= record.keys() or not isinstance(record["findings"], list):
        raise ValueError(f"Incomplete report envelope: {task}/{path.name}")
    ids: set[str] = set()
    for finding in cast(list[Json], record["findings"]):
        needed = {
            "id",
            "status",
            "category",
            "criteria",
            "title",
            "explanation",
            "evidence",
            "authorities",
        }
        if not needed <= finding.keys() or finding["id"] in ids:
            raise ValueError(f"Incomplete or duplicate finding: {task}/{path.name}")
        ids.add(finding["id"])
        if finding["status"] not in RANK or finding["category"] not in CATEGORIES:
            raise ValueError(f"Unknown finding status/category: {task}/{finding['id']}")
        if (
            not isinstance(finding["criteria"], list)
            or not set(cast(list[str], finding["criteria"])) <= criteria
        ):
            raise ValueError(f"Unknown criterion: {task}/{finding['id']}")
    return record


def summarize(reports: dict[str, Json | None], totals: dict[str, int]) -> Json:
    """Count findings and strongest statuses, including per-category deduplication."""
    available = {task: report for task, report in reports.items() if report is not None}
    all_findings = [(task, f) for task, r in available.items() for f in r["findings"]]
    statuses = {
        (task, c): s
        for task, r in available.items()
        for c, s in opus_statuses(r["findings"]).items()
    }
    counts: Json = {
        "reports_available": len(available),
        "reports_expected": len(reports),
        "criteria_with_reports": sum(totals[t] for t in available),
        "findings": len(all_findings) if available else None,
        "flagged_criteria": len(statuses) if available else None,
        "status_counts": {
            s: list(statuses.values()).count(s) if available else None for s in RANK
        },
        "categories": {},
    }
    for category in CATEGORIES:
        selected = [(t, f) for t, f in all_findings if f["category"] == category]
        per = {
            (t, c): s
            for t, r in available.items()
            for c, s in opus_statuses(
                [f for f in r["findings"] if f["category"] == category]
            ).items()
        }
        counts["categories"][category] = {
            "findings": len(selected) if available else None,
            "flagged_criteria": len(per) if available else None,
            **{s: list(per.values()).count(s) if available else None for s in RANK},
        }
    return counts


def compare(out: Path) -> tuple[Json, dict[str, dict[str, Json | None]]]:
    census: Json = load(out / "in-scope.json")
    selected = [t for t in census["tasks"] if t["in_scope"]]
    reports: dict[str, dict[str, Json | None]] = {name: {} for name in REPORTS}
    totals = {t["task"]: t["criteria_total"] for t in selected}
    rows: list[Json] = []
    paired_tasks: list[str] = []
    for item in selected:
        task = item["task"]
        task_dir = out / "tasks" / task
        inputs = load(task_dir / "input.json")
        rubric = inputs["rubric"]
        criteria = {c["criterion_id"] for c in rubric}
        if len(criteria) != item["criteria_total"]:
            raise ValueError(f"Census/input criterion mismatch: {task}")
        statuses: dict[str, dict[str, str]] = {}
        for name, filename in REPORTS.items():
            record = read_report(task_dir / filename, task, criteria)
            reports[name][task] = record
            statuses[name] = (
                opus_statuses(record["findings"]) if record is not None else {}
            )
        paired = all(
            reports[name][task] is not None for name in ("gpt_6_sol", "claude_opus_5_5")
        )
        if paired:
            paired_tasks.append(task)
        for criterion in rubric:
            cid = criterion["criterion_id"]
            row: Json = {
                "task": task,
                "criterion": cid,
                "criterion_text": criterion["criterion"],
                "polarity": criterion["polarity"],
                "report_availability": {
                    name: reports[name][task] is not None for name in REPORTS
                },
            }
            for name in REPORTS:
                record = reports[name][task]
                findings = (
                    [as_dict(f) for f in as_list(record["findings"])]
                    if record is not None
                    else []
                )
                row[name] = statuses[name].get(cid)
                row[f"{name}_findings"] = (
                    [f["id"] for f in findings if cid in f["criteria"]]
                    if record is not None
                    else None
                )
                row[f"{name}_categories"] = (
                    sorted({f["category"] for f in findings if cid in f["criteria"]})
                    if record is not None
                    else None
                )
            row["bucket"] = (
                bucket(
                    statuses["gpt_6_sol"].get(cid), statuses["claude_opus_5_5"].get(cid)
                )
                if paired
                else None
            )
            rows.append(row)
    bucket_counts = Counter(r["bucket"] for r in rows if r["bucket"])
    paired_total = sum(totals[t] for t in paired_tasks)
    result = {
        "dataset": census["dataset"],
        "revision": census["revision"],
        "status_notes": COMPARISON_NOTE,
        "tasks_total": len(selected),
        "criteria_total": sum(totals.values()),
        "blind_agreement": {
            "paired_tasks": len(paired_tasks),
            "criteria_with_both_reports": paired_total,
            "flagged_criteria": sum(bucket_counts.values()) if paired_tasks else None,
            "unflagged_criteria": paired_total - sum(bucket_counts.values())
            if paired_tasks
            else None,
            "buckets": {
                b: bucket_counts[b] if paired_tasks else None for b, _ in BUCKETS
            },
        },
        "report_counts": {
            name: summarize(records, totals) for name, records in reports.items()
        },
        "rows": rows,
    }
    return result, reports
