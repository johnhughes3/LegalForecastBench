#!/usr/bin/env python3
"""synthetic: true

Hand-authored fixture LAB evaluator for the Claude clean-native E2E. Reads
the explicit evaluation-input JSON from stdin and writes canonical authorized
verdict bytes (legalforecast.multiharness.harvey_lab_verdicts.v1). Shared
``tests/fixtures/harvey_lab/fake_evaluator.py`` stays on the stub score
shape; this file is Claude-owned so G1a does not change that shared seam.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

ALLOWED_PATH_FIELDS = (
    "deliverable_path",
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
    allowed = _allowed_paths(payload)
    return _write_authorized_scores(payload, allowed, n_criteria=23)


def _allowed_paths(record: Mapping[str, Any]) -> set[Path]:
    allowed: set[Path] = set()
    for field_name in ALLOWED_PATH_FIELDS:
        value = record.get(field_name)
        if not isinstance(value, str) or not value:
            continue
        allowed.add(Path(value).resolve())
    return allowed


def _write_authorized_scores(
    record: Mapping[str, Any],
    allowed: set[Path],
    *,
    n_criteria: int,
) -> int:
    deliverable = Path(str(record["deliverable_path"])).resolve()
    private = Path(str(record["private_task_json_path"])).resolve()
    scores = Path(str(record["scores_output_path"])).resolve()
    if deliverable not in allowed or private not in allowed or scores not in allowed:
        print("refusing path outside the evaluation input manifest", file=sys.stderr)
        return 2
    if not deliverable.is_file() or not private.is_file():
        print("listed evaluation inputs are missing", file=sys.stderr)
        return 2
    deliverable.read_bytes()
    private.read_bytes()
    scores.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_criteria": n_criteria,
        "n_passed": n_criteria,
        "schema_version": VERDICT_SCHEMA,
        "score": 1,
        "verdicts": [
            {"ordinal": index, "verdict": "pass"} for index in range(1, n_criteria + 1)
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
