"""Export saved forecasts for private, model-blinded rationale review.

Run with ``python -m legalforecast.evals.rationale_audit --help``. This is
qualitative review preparation, not a reasoning score or publication command.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from legalforecast.cli_support import read_records, write_json, write_jsonl
from legalforecast.evals.output_parser import (
    parse_model_output,
    parsed_output_from_public_record,
    public_parser_record,
)


class AuditExport(TypedDict):
    """Separate reviewer material from the private source join key."""

    review_rows: list[dict[str, object]]
    private_key: list[dict[str, object]]
    coverage: dict[str, int]


def build_rationale_audit(records: Sequence[Mapping[str, object]]) -> AuditExport:
    """Preserve unit rationales and separately scoped case assessments.

    IDs and order are randomized so input/model ordering is not a blinding cue.
    Prose is untouched: stylistic or explicit self-identification still requires
    the audit coordinator's review before distributing the reviewer material.
    """
    if not records:
        raise ValueError("run records must not be empty")
    rows: list[dict[str, object]] = []
    key: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    missing = defaulted = prediction_count = case_assessments = 0
    for source_index, record in enumerate(records, start=1):
        identity = {
            "case_id": _required_text(record, "case_id"),
            "solver_id": _required_text(
                record, "solver_id" if "solver_id" in record else "model_key"
            ),
            "run_label": _required_text(
                record, "run_label" if "run_label" in record else "run_identity_sha256"
            ),
            "ablation": _required_text(record, "ablation"),
        }
        repeat = record.get("repeat_index", 1)
        if type(repeat) is not int or repeat < 1:
            raise ValueError("repeat_index must be a positive integer")
        subject = (
            identity["case_id"],
            identity["solver_id"],
            identity["run_label"],
            identity["ablation"],
            repeat,
        )
        if subject in seen:
            raise ValueError("duplicate case/solver/run/ablation/repeat record")
        seen.add(subject)
        units = record.get("required_unit_ids")
        if not isinstance(units, list | tuple) or not units:
            raise ValueError("required_unit_ids must be a non-empty list")
        values = cast(Sequence[object], units)
        if any(not isinstance(unit, str) or not unit.strip() for unit in values):
            raise ValueError("required_unit_ids must contain non-empty strings")
        required = tuple(cast(str, unit) for unit in values)
        if len(set(required)) != len(required):
            raise ValueError("required_unit_ids must be unique")
        projection = record.get("parser_output")
        raw = record.get("raw_output")
        if raw is not None:
            if not isinstance(raw, str):
                raise ValueError("raw_output must be a string")
            parsed = parse_model_output(raw, required_unit_ids=required)
            if projection is not None and projection != public_parser_record(parsed):
                raise ValueError("parser_output does not match raw_output")
        elif isinstance(projection, Mapping):
            parsed = parsed_output_from_public_record(
                cast(Mapping[str, object], projection)
            )
            if parsed.required_unit_ids != required:
                raise ValueError("parser_output required_unit_ids do not match")
        else:
            raise ValueError("raw_output or public parser_output is required")
        if parsed.case_assessment is not None:
            review_id = str(uuid4())
            rows.append(
                {
                    "review_id": review_id,
                    "case_id": identity["case_id"],
                    "unit_id": None,
                    "scope": "case",
                    "rationale": parsed.case_assessment,
                    "defaulted": None,
                }
            )
            key.append(
                {
                    "review_id": review_id,
                    **identity,
                    "unit_id": None,
                    "scope": "case",
                    "repeat_index": repeat,
                    "source_record": source_index,
                    "probability_fully_dismissed": None,
                    "parser_status": parsed.status.value,
                }
            )
            case_assessments += 1
        for prediction in parsed.predictions:
            review_id = str(uuid4())
            rows.append(
                {
                    "review_id": review_id,
                    "case_id": identity["case_id"],
                    "unit_id": prediction.unit_id,
                    "scope": "unit",
                    "rationale": prediction.rationale,
                    "defaulted": prediction.defaulted,
                }
            )
            key.append(
                {
                    "review_id": review_id,
                    **identity,
                    "unit_id": prediction.unit_id,
                    "scope": "unit",
                    "repeat_index": repeat,
                    "source_record": source_index,
                    "probability_fully_dismissed": (
                        prediction.probability_fully_dismissed
                    ),
                    "parser_status": parsed.status.value,
                }
            )
            missing += prediction.rationale is None
            defaulted += prediction.defaulted
            prediction_count += 1
    random.SystemRandom().shuffle(rows)
    return {
        "review_rows": rows,
        "private_key": key,
        "coverage": {
            "prediction_count": prediction_count,
            "with_rationale": prediction_count - missing,
            "missing_rationale": missing,
            "defaulted_predictions": defaulted,
            "case_record_count": len(records),
            "with_case_assessment": case_assessments,
            "missing_case_assessment": len(records) - case_assessments,
        },
    }


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def read_ledger_records(path: Path) -> list[dict[str, object]]:
    """Read completed native managed responses without mutating the ledger.

    Public parser projections are checked against the saved raw response by
    ``build_rationale_audit``. Provider payloads without a normalized raw_output
    retain the prose-free projection and are counted as missing explanations.
    """
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT receipt_payload, response_payload FROM public_runner_cells "
            "WHERE status = 'completed' ORDER BY cell_id"
        ).fetchall()
    finally:
        connection.close()
    records: list[dict[str, object]] = []
    for receipt, response in rows:
        if not isinstance(receipt, bytes | str):
            raise ValueError("completed ledger cell has no receipt_payload")
        decoded: object = json.loads(receipt)
        if not isinstance(decoded, dict):
            raise ValueError("ledger receipt_payload must be an object")
        record = dict(cast(dict[str, object], decoded))
        if response is not None:
            if not isinstance(response, bytes | str):
                raise ValueError("ledger response_payload must be JSON bytes")
            payload: object = json.loads(response)
            if not isinstance(payload, dict):
                raise ValueError("ledger response_payload must be an object")
            raw = cast(dict[str, object], payload).get("raw_output")
            if raw is not None:
                if not isinstance(raw, str):
                    raise ValueError("ledger raw_output must be a string")
                record["raw_output"] = raw
        records.append(record)
    return records


def main(argv: Sequence[str] | None = None) -> int:
    """Write review rows and a separate coordinator key without provider calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--runs",
        type=Path,
        help="Saved JSONL case-run records with raw_output or public parser_output.",
    )
    inputs.add_argument(
        "--ledger",
        type=Path,
        help="Read completed cells from a native runner SQLite ledger (read-only).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New private directory; refuses to overwrite an existing directory.",
    )
    args = parser.parse_args(argv)
    source = cast(Path | None, args.runs)
    ledger = cast(Path | None, args.ledger)
    output = cast(Path, args.output_dir)
    try:
        records = (
            read_records(source)
            if source is not None
            else read_ledger_records(cast(Path, ledger))
        )
        result = build_rationale_audit(records)
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        write_jsonl(output / "review.jsonl", result["review_rows"])
        write_jsonl(output / "private-key.jsonl", result["private_key"])
        write_json(output / "coverage.json", result["coverage"])
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"rationale-audit: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result["coverage"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
