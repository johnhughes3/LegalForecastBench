#!/usr/bin/env python3
"""Codex-owned Harvey LAB evaluator fixture for clean-native E2E.

synthetic: true
command: hand-authored; emits authorized harvey_lab_verdicts.v1 bytes so the
Codex LAB composition can call verify_authorized_harvey_lab_receipt without
changing the shared fake_evaluator succeed payload.

Reads evaluation-input JSON from stdin. Opens only overlay paths listed in
that document. Never reruns a solver.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

ALLOWED_PATH_FIELDS = (
    "deliverable_root",
    "private_task_json_path",
    "scores_output_path",
)
VERDICT_SCHEMA = "legalforecast.multiharness.harvey_lab_verdicts.v1"


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        record = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print("evaluation input must be JSON", file=sys.stderr)
        return 2
    if not isinstance(record, dict):
        print("evaluation input must be an object", file=sys.stderr)
        return 2
    payload = cast(Mapping[str, Any], record)
    mode = payload.get("mode", "succeed")
    if mode == "dump-env":
        json.dump(dict(os.environ), sys.stdout, sort_keys=True)
        return 0
    return _write_authorized_scores(payload)


def _allowed_paths(record: Mapping[str, Any]) -> set[Path]:
    allowed: set[Path] = set()
    for field_name in ALLOWED_PATH_FIELDS:
        value = record.get(field_name)
        if not isinstance(value, str) or not value:
            continue
        allowed.add(Path(value).resolve())
    for value in record.get("deliverable_paths", []):
        if isinstance(value, str) and value:
            allowed.add(Path(value).resolve())
    return allowed


def _write_authorized_scores(record: Mapping[str, Any]) -> int:
    allowed = _allowed_paths(record)
    deliverables = [Path(str(item)).resolve() for item in record["deliverable_paths"]]
    private = Path(str(record["private_task_json_path"])).resolve()
    scores = Path(str(record["scores_output_path"])).resolve()
    if (
        any(item not in allowed for item in deliverables)
        or private not in allowed
        or scores not in allowed
    ):
        print("refusing path outside the evaluation input manifest", file=sys.stderr)
        return 2
    if not all(item.is_file() for item in deliverables) or not private.is_file():
        print("listed evaluation inputs are missing", file=sys.stderr)
        return 2
    for deliverable in deliverables:
        deliverable.read_bytes()
    task = json.loads(private.read_text(encoding="utf-8"))
    criteria = task.get("criteria") if isinstance(task, dict) else None
    if not isinstance(criteria, list) or not criteria:
        print("fixture task must contain criteria", file=sys.stderr)
        return 2
    criterion_count = len(criteria)
    scores.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_criteria": criterion_count,
        "n_passed": criterion_count,
        "schema_version": VERDICT_SCHEMA,
        "score": 1,
        "verdicts": [
            {"ordinal": index, "verdict": "pass"}
            for index in range(1, criterion_count + 1)
        ],
    }
    scores.write_bytes(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
