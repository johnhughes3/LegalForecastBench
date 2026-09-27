"""Build the GPT-6 Sol / Claude Opus 5.5 dual audit of Harvey LAB litigation tasks.

The audit lives in ``docs/harvey-lab-audit/litigation-dispute-resolution``. GPT-6 Sol's
reports and structured index were produced first; this script adds the Claude Opus 5.5
audit and renders the side-by-side comparison. It never edits GPT-6 Sol's findings.

Subcommands:

``ingest``
    Store Claude Opus 5.5 workflow results (blind pass + reconciliation) as
    ``tasks/<task>/claude-opus-5-5-audit.json``. Criterion line numbers are read once
    from a Harvey LAB checkout at the pinned commit so rendered links point at the
    exact rubric line.

``render``
    Regenerate every Claude Opus 5.5 report, the comparison section of each task
    landing page, the top-level ``comparison.md``/``comparison.json``, and the audit
    file index in ``docs/README.md`` from files already in the audit directory.
    Rendering is deterministic, so the published counts can be reproduced from the
    repository alone.

Example::

    uv run python scripts/build_harvey_dual_audit.py ingest \
        --results tmp/opus-results.json --harvey-checkout ../harvey-labs \
        --run-id wf_example --effort high
    uv run python scripts/build_harvey_dual_audit.py render"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from harvey_dual_audit_core import (
    AUDIT_DIR,
    OPUS_JSON,
    PINNED,
    Json,
    as_dict,
    as_list,
    compare_task,
    consistency_warnings,
    dump,
    load,
)
from harvey_dual_audit_render import (
    render_comparison,
    render_docs_index,
    render_opus_report,
    render_task_section,
)


def criterion_lines(task_json: Path) -> dict[str, int]:
    """Map criterion id to its 1-based line in the pinned task.json."""
    lines: dict[str, int] = {}
    for number, line in enumerate(
        task_json.read_text(encoding="utf-8").splitlines(), 1
    ):
        match = re.search(r'"id"\s*:\s*"(C-\d+)"', line)
        if match:
            lines.setdefault(match.group(1), number)
    return lines


LOCAL_PATH = re.compile(
    r"(?:/tmp|/home|/work|/Users|/var|/private|/mnt|/Volumes|/opt|/srv)"
    r"/[^\s\"'`)\]]+"
)


def scrub(value: object) -> Any:
    """Reduce machine-local absolute paths in worker text to their file names."""
    if isinstance(value, str):
        return LOCAL_PATH.sub(lambda m: Path(m.group()).name, value)
    if isinstance(value, list):
        return [scrub(v) for v in cast(list[Any], value)]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in cast(Json, value).items()}
    return value


def checkout_commit(checkout: Path) -> str:
    """HEAD commit of the Harvey LAB checkout used for criterion line numbers."""
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def ingest(results_path: Path, checkout: Path, run_id: str, effort: str) -> None:
    # Rendered links point at PINNED, so line numbers must come from that commit.
    head = checkout_commit(checkout)
    if head != PINNED:
        raise SystemExit(f"Harvey checkout is at {head}, expected {PINNED}")
    raw = as_dict(load(results_path))
    results = as_list(raw.get("results", raw))
    for item in results:
        entry = as_dict(item)
        task = str(entry["task"])
        task_json = (
            checkout / "tasks/litigation-dispute-resolution" / task / "task.json"
        )
        spec = as_dict(load(task_json))
        record: Json = {
            "model": "Claude Opus 5.5 (claude-opus-5-5)",
            "reasoning_effort": effort,
            "workflow_run_id": run_id,
            "harvey_commit": PINNED,
            "task": task,
            "title": spec.get("title", task),
            "criteria_total": len(as_list(spec.get("criteria"))),
            "criterion_lines": criterion_lines(task_json),
            "blind": scrub(entry["blind"]),
            "final": scrub(entry["final"]),
        }
        out = AUDIT_DIR / "tasks" / task
        if not out.is_dir():
            raise SystemExit(f"unknown task directory: {out}")
        dump(out / OPUS_JSON, record)
    print(f"ingested {len(results)} task(s)")


def render() -> None:
    index = as_dict(load(AUDIT_DIR / "gpt-6-sol" / "index.json"))
    entries = {str(as_dict(t)["task"]): as_dict(t) for t in as_list(index.get("tasks"))}
    records: dict[str, Json] = {}
    all_rows: list[Json] = []
    warnings: list[str] = []
    task_dirs = sorted(p for p in (AUDIT_DIR / "tasks").iterdir() if p.is_dir())
    # A missing record or index entry would silently shrink the denominators or
    # turn shared flags into one-model flags, so refuse to render partial data.
    missing = [p.name for p in task_dirs if not (p / OPUS_JSON).exists()]
    missing += [
        f"{p.name} (GPT-6 Sol index)" for p in task_dirs if p.name not in entries
    ]
    if missing:
        raise SystemExit("cannot render; missing inputs: " + ", ".join(missing))
    for task_dir in task_dirs:
        record = as_dict(load(task_dir / OPUS_JSON))
        records[task_dir.name] = record
        rows = compare_task(record, entries[task_dir.name], task_dir)
        warnings += consistency_warnings(record, rows)
        all_rows += rows
        render_opus_report(record, task_dir)
        render_task_section(record, rows, task_dir)
    render_comparison(all_rows, records, warnings)
    render_docs_index()
    print(f"rendered {len(records)} task(s); {len(warnings)} different-ground row(s)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ing = sub.add_parser(
        "ingest", help="store Claude Opus 5.5 workflow results in the audit tree"
    )
    ing.add_argument(
        "--results",
        type=Path,
        required=True,
        help="workflow result JSON ({results: [...]})",
    )
    ing.add_argument(
        "--harvey-checkout",
        type=Path,
        required=True,
        help=f"harvey-labs checkout at {PINNED[:12]}",
    )
    ing.add_argument(
        "--run-id", required=True, help="workflow run id recorded in each report"
    )
    ing.add_argument(
        "--effort", required=True, help="reasoning effort the workers actually ran with"
    )
    sub.add_parser(
        "render", help="regenerate reports and comparison from the audit tree"
    )
    ns = parser.parse_args()
    if ns.command == "ingest":
        ingest(ns.results, ns.harvey_checkout, ns.run_id, ns.effort)
    else:
        render()


if __name__ == "__main__":
    main()
