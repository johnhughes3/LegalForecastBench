"""Behavior of the GPT-6 Sol / Claude Opus 5.5 comparison builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("harvey_dual_audit_core")
cli = _load("build_harvey_dual_audit")


def test_bucket_assignment() -> None:
    assert builder.bucket("problematic", "problematic") == "both_problematic"
    assert builder.bucket("arguable", "arguable") == "both_arguable"
    assert builder.bucket("problematic", "arguable") == "split"
    assert builder.bucket("arguable", None) == "sol_only"
    assert builder.bucket(None, "problematic") == "opus_only"
    # Sol's unverified/qualified checks are not flags.
    assert builder.bucket("unverified", "arguable") == "opus_only"
    assert builder.bucket("qualified_check", None) is None


def test_strongest_status_wins_per_criterion() -> None:
    sol = builder.sol_statuses(
        {"affected_criteria": {"arguable": ["C-001", "C-002"], "confirmed": ["C-002"]}}
    )
    assert sol == {"C-001": "arguable", "C-002": "problematic"}
    opus = builder.opus_statuses(
        [
            {"status": "arguable", "criteria": ["C-003", "C-004"]},
            {"status": "problematic", "criteria": ["C-004"]},
        ]
    )
    assert opus == {"C-003": "arguable", "C-004": "problematic"}


def test_compare_task_rows_carry_blind_and_reasons() -> None:
    record = {
        "task": "t",
        "blind": {"findings": [{"status": "arguable", "criteria": ["C-009"]}]},
        "final": {
            "findings": [
                {
                    "id": "O1",
                    "status": "problematic",
                    "criteria": ["C-001"],
                    "title": "x",
                }
            ],
            "sol_verdicts": [
                {
                    "sol_locator": "F1",
                    "sol_criteria": ["C-002"],
                    "verdict": "not_a_defect",
                    "per_criterion": [
                        {"criterion": "C-002", "verdict": "not_a_defect"}
                    ],
                    "reason": "record supports it",
                }
            ],
        },
    }
    entry = {
        "affected_criteria": {"confirmed": ["C-001"], "arguable": ["C-002"]},
        "findings": [{"locator": "F1", "label": "y", "criteria": ["C-002"]}],
    }
    rows = {r["criterion"]: r for r in builder.compare_task(record, entry)}
    assert rows["C-001"]["bucket"] == "both_problematic"
    assert rows["C-002"]["bucket"] == "sol_only"
    assert rows["C-002"]["opus_on_sol"] == ["F1 → not_a_defect: record supports it"]
    assert rows["C-009"]["bucket"] is None
    assert rows["C-009"]["claude_opus_5_5_blind"] == "arguable"
    assert builder.consistency_warnings(record, list(rows.values())) == []


def test_scrub_removes_local_paths() -> None:
    text = (
        "read /tmp/x/extract/task/documents/a.docx.txt, /home/u/repo/b.md, "
        "and /var/folders/zz/T/c.txt."
    )
    assert cli.scrub({"k": [text]}) == {"k": ["read a.docx.txt, b.md, and c.txt."]}
