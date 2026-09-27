"""Shared constants, loaders, and status logic for the GPT-6 Sol / Claude Opus 5.5
dual audit of Harvey LAB litigation tasks. See ``build_harvey_dual_audit.py``."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

AUDIT_DIR = Path("docs/harvey-lab-audit/litigation-dispute-resolution")

PINNED = "1dd81403b2fbb60596f7aea3fcecafad7bf73143"

TASKS_URL = f"https://github.com/harveyai/harvey-labs/blob/{PINNED}/tasks/litigation-dispute-resolution"

OPUS_JSON = "claude-opus-5-5-audit.json"

OPUS_MD = "claude-opus-5-5-audit.md"

START = "<!-- dual-audit:start -->"

END = "<!-- dual-audit:end -->"

RANK = {"problematic": 2, "arguable": 1}

SOL_STATUS = {"confirmed": "problematic", "arguable": "arguable"}

BUCKETS = [
    ("both_problematic", "Both models: problematic"),
    ("both_arguable", "Both models: arguable"),
    ("split", "Both flagged, different strength (one problematic, one arguable)"),
    ("sol_only", "Flagged by GPT-6 Sol only"),
    ("opus_only", "Flagged by Claude Opus 5.5 only"),
]

BANNER = (
    "> [!WARNING]\n"
    "> **AI-generated, unverified analysis — for reference only.** Labels such as "
    "“problematic” or “verified” are AI reviewer judgments, not human sign-off or "
    "accepted score corrections. Agreement between two AI models is not independent "
    "verification. See the [audit overview]({up}README.md)."
)

METHOD_NOTE = (
    "Method: a blind pass that saw only the task instructions, rubric, and "
    "supplied documents, followed by a reconciliation pass that checked every "
    "GPT-6 Sol finding against the record and law. The findings below are the "
    "final position."
)

COMPARISON_NOTE = (
    "Each row is one rubric criterion that at least one model flagged. A model's "
    "status for a criterion is the strongest status among its findings that cite "
    "it. GPT-6 Sol's statuses come from its [structured index](gpt-6-sol/index.json) "
    "(“confirmed” is shown as problematic); its `unverified` and `qualified_check` "
    "entries are not counted as flags. Claude Opus 5.5's statuses are its final "
    "position after a blind pass and a reconciliation pass that reviewed every "
    "GPT-6 Sol finding. Because Opus saw Sol's findings before finalizing, "
    "agreement is not independent confirmation; the blind-pass column on each "
    "task page shows what Opus found before reading Sol. Agreement on a criterion "
    "does not always mean agreement on the reason; each row lists both models' "
    "findings, and the last section lists criteria flagged on different grounds."
)

Json = dict[str, Any]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def as_list(value: object) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def as_dict(value: object) -> Json:
    return cast(Json, value) if isinstance(value, dict) else {}


def sol_statuses(entry: Json) -> dict[str, str]:
    """GPT-6 Sol's per-criterion status from its structured index."""
    affected = as_dict(entry.get("affected_criteria"))
    status: dict[str, str] = {}
    for raw_status in ("unverified", "qualified_check"):
        for crit in as_list(affected.get(raw_status)):
            status[str(crit)] = raw_status
    for raw_status in ("arguable", "confirmed"):
        for crit in as_list(affected.get(raw_status)):
            status[str(crit)] = SOL_STATUS[raw_status]
    return status


def opus_statuses(findings: list[Any]) -> dict[str, str]:
    status: dict[str, str] = {}
    for finding in findings:
        f = as_dict(finding)
        for crit in as_list(f.get("criteria")):
            current = status.get(str(crit))
            new = str(f["status"])
            if current is None or RANK[new] > RANK[current]:
                status[str(crit)] = new
    return status


def bucket(sol: str | None, opus: str | None) -> str | None:
    sol_flag = sol if sol in RANK else None
    if sol_flag and opus:
        if sol_flag == opus:
            return f"both_{opus}"
        return "split"
    if sol_flag:
        return "sol_only"
    if opus:
        return "opus_only"
    return None


def crit_key(crit: str) -> tuple[int, str]:
    match = re.search(r"\d+", crit)
    return (int(match.group()) if match else 10**6, crit)


SOL_TEXT_KEYS = ("title", "issue", "description", "summary", "finding")


def sol_report_texts(task_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Issue text from GPT-6 Sol's JSON report, keyed by id, pointer, criteria."""
    by_id: dict[str, str] = {}
    by_criteria: dict[str, str] = {}
    path = task_dir / "gpt-6-sol-audit.json"
    if not path.exists():
        return by_id, by_criteria

    def walk(node: object, pointer: str) -> None:
        if isinstance(node, list):
            for i, item in enumerate(cast(list[Any], node)):
                walk(item, f"{pointer}/{i}".lstrip("/"))
        elif isinstance(node, dict):
            d = cast(Json, node)
            text = next(
                (d[k] for k in SOL_TEXT_KEYS if isinstance(d.get(k), str)), None
            )
            crits = as_list(d.get("criteria"))
            if text and crits:
                short = text if len(text) <= 160 else text[:157].rstrip() + "…"
                if isinstance(d.get("id"), str):
                    by_id.setdefault(str(d["id"]), short)
                by_id.setdefault(pointer, short)
                by_criteria.setdefault(",".join(str(c) for c in crits), short)
            for key, value in d.items():
                walk(value, f"{pointer}/{key}".lstrip("/"))

    walk(load(path), "")
    return by_id, by_criteria


def sol_label(finding: Json, texts: tuple[dict[str, str], dict[str, str]]) -> str:
    """Display text for a GPT-6 Sol index finding."""
    label = str(finding.get("label") or "")
    if not label:
        by_id, by_criteria = texts
        crit_key_ = ",".join(str(c) for c in as_list(finding.get("criteria")))
        label = by_id.get(str(finding.get("locator"))) or by_criteria.get(crit_key_, "")
        classification = finding.get("reported_classification") or finding.get("status")
        if classification:
            label = f"{label} ({classification})" if label else str(classification)
    return f"{finding.get('locator', '?')}: {label}".rstrip(": ")


def compare_task(record: Json, entry: Json, task_dir: Path | None = None) -> list[Json]:
    final = as_dict(record["final"])
    findings = [as_dict(f) for f in as_list(final.get("findings"))]
    opus = opus_statuses(findings)
    blind = opus_statuses(as_list(as_dict(record["blind"]).get("findings")))
    sol = sol_statuses(entry)
    texts: tuple[dict[str, str], dict[str, str]] = (
        sol_report_texts(task_dir) if task_dir else ({}, {})
    )
    sol_by_crit: dict[str, list[str]] = {}
    for finding in map(as_dict, as_list(entry.get("findings"))):
        for crit in as_list(finding.get("criteria")):
            sol_by_crit.setdefault(str(crit), []).append(sol_label(finding, texts))
    opus_by_crit: dict[str, list[str]] = {}
    for f in findings:
        for crit in as_list(f.get("criteria")):
            opus_by_crit.setdefault(str(crit), []).append(f"{f['id']}: {f['title']}")
    reasons: dict[str, list[str]] = {}
    for v in map(as_dict, as_list(final.get("sol_verdicts"))):
        per = {
            str(p["criterion"]): str(p["verdict"])
            for p in map(as_dict, as_list(v.get("per_criterion")))
        }
        for crit in as_list(v.get("sol_criteria")):
            verdict = per.get(str(crit), str(v.get("verdict")))
            reasons.setdefault(str(crit), []).append(
                f"{v['sol_locator']} → {verdict}: {v['reason']}"
            )
    rows: list[Json] = []
    for crit in sorted(set(sol) | set(opus) | set(blind), key=crit_key):
        rows.append(
            {
                "task": record["task"],
                "criterion": crit,
                "gpt_6_sol": sol.get(crit),
                "claude_opus_5_5": opus.get(crit),
                "claude_opus_5_5_blind": blind.get(crit),
                "bucket": bucket(sol.get(crit), opus.get(crit)),
                "sol_findings": sol_by_crit.get(crit, []),
                "opus_findings": opus_by_crit.get(crit, []),
                "opus_on_sol": reasons.get(crit, []),
            }
        )
    return rows


def consistency_warnings(record: Json, rows: list[Json]) -> list[str]:
    """List criteria where Opus rejects Sol's ground but flags on its own ground."""
    warnings: list[str] = []
    final_status = {str(r["criterion"]): r["claude_opus_5_5"] for r in rows}
    for v in map(as_dict, as_list(as_dict(record["final"]).get("sol_verdicts"))):
        for p in map(as_dict, as_list(v.get("per_criterion"))):
            crit, verdict = str(p["criterion"]), str(p["verdict"])
            want = verdict if verdict in RANK else None
            if final_status.get(crit) != want and not (
                want and final_status.get(crit) in RANK
            ):
                warnings.append(
                    f"[{record['task']}](tasks/{record['task']}/README.md) "
                    f"{crit}: Opus rejects GPT-6 Sol's {v['sol_locator']} as "
                    f"{verdict}, but flags the criterion as "
                    f"{final_status.get(crit)} on a different ground"
                )
    return warnings
