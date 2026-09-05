#!/usr/bin/env python3
"""Fixture LAB evaluator CLI for contained-runtime tests.

Reads an explicit evaluation-input JSON document from stdin. The only files
it may open are the overlay paths listed in that document. It never runs a
solver and never follows document bytes as paths.
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
    allowed = _allowed_paths(payload)
    if mode == "escape":
        deliverable = Path(str(payload.get("deliverable_root", "")))
        try:
            (deliverable.parent.parent / "solver-canary.txt").read_bytes()
        except OSError:
            print("escape probe could not read solver material", file=sys.stderr)
            return 2
        print("escape probe read solver material", file=sys.stderr)
        return 2
    if mode == "parser-bomb":
        deliverable = Path(str(payload["deliverable_paths"][0]))
        if deliverable.resolve() not in allowed:
            print(
                "parser-bomb path is not listed in the input manifest", file=sys.stderr
            )
            return 2
        # Opaque read only; never import, exec, or follow embedded paths.
        deliverable.read_bytes()
        return _write_scores(payload, allowed, n_criteria=_criterion_count(payload))
    return _write_scores(payload, allowed, n_criteria=_criterion_count(payload))


def _criterion_count(record: Mapping[str, Any]) -> int:
    task_path = Path(str(record["private_task_json_path"]))
    task = json.loads(task_path.read_text(encoding="utf-8"))
    criteria = task.get("criteria") if isinstance(task, dict) else None
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("fixture task must contain criteria")
    return len(criteria)


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


def _write_scores(
    record: Mapping[str, Any],
    allowed: set[Path],
    *,
    n_criteria: int,
) -> int:
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
    private.read_bytes()
    scores.parent.mkdir(parents=True, exist_ok=True)
    scores.write_text(
        json.dumps(
            {
                "score": 1.0,
                "n_passed": n_criteria,
                "n_criteria": n_criteria,
                "verdicts": ["pass"] * n_criteria,
                "entrypoint": "evaluation.run_eval.evaluate_run",
                "judge": "deterministic local stub",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
