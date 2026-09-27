from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from legalforecast.evals.output_parser import parse_model_output, public_parser_record
from legalforecast.evals.rationale_audit import build_rationale_audit, main
from legalforecast.runner.ledger import RunnerLedger
from legalforecast.runner.managed_execution import ForecastEnvelope, ForecastPrediction


def _record() -> dict[str, object]:
    return {
        "case_id": "synthetic-case",
        "solver_id": "synthetic:model-a",
        "run_label": "synthetic-run",
        "ablation": "full_packet",
        "required_unit_ids": ["unit-a", "unit-b"],
        "raw_output": json.dumps(
            {
                "predictions": [
                    {
                        "unit_id": "unit-a",
                        "probability_fully_dismissed": 0.7,
                        "rationale": (
                            "The complaint does not plead the required element."
                        ),
                    },
                    {"unit_id": "unit-b", "probability_fully_dismissed": 0.2},
                ]
            }
        ),
        "outcome": 1,
        "metadata": {"provider": "do-not-export"},
    }


def test_export_retains_rationales_and_blinds_metadata() -> None:
    result = build_rationale_audit([_record()])
    rows = {row["unit_id"]: row for row in result["review_rows"]}
    assert rows["unit-a"]["rationale"] == (
        "The complaint does not plead the required element."
    )
    assert rows["unit-b"]["rationale"] is None
    assert result["coverage"] == {
        "prediction_count": 2,
        "with_rationale": 1,
        "missing_rationale": 1,
        "defaulted_predictions": 0,
        "case_record_count": 1,
        "with_case_assessment": 0,
        "missing_case_assessment": 1,
    }
    assert all(
        set(row)
        == {"review_id", "case_id", "unit_id", "scope", "rationale", "defaulted"}
        for row in rows.values()
    )
    assert {row["review_id"] for row in result["private_key"]} == {
        row["review_id"] for row in rows.values()
    }
    assert result["private_key"][0]["solver_id"] == "synthetic:model-a"


def test_public_receipts_explicitly_report_missing_prose() -> None:
    record = _record()
    raw = str(record.pop("raw_output"))
    record["parser_output"] = public_parser_record(
        parse_model_output(raw, required_unit_ids=("unit-a", "unit-b"))
    )
    result = build_rationale_audit([record])
    assert result["coverage"]["missing_rationale"] == 2
    assert all(row["rationale"] is None for row in result["review_rows"])
    assert result["coverage"]["with_case_assessment"] == 0


def test_invalid_predictions_remain_in_denominator() -> None:
    record = _record()
    record["raw_output"] = "I cannot predict this."
    result = build_rationale_audit([record])
    assert result["coverage"]["prediction_count"] == 2
    assert result["coverage"]["defaulted_predictions"] == 2


def test_duplicates_fail_but_distinct_repeats_are_retained() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_rationale_audit([_record(), _record()])
    repeated = {**_record(), "repeat_index": 2}
    assert (
        build_rationale_audit([_record(), repeated])["coverage"]["prediction_count"]
        == 4
    )


@pytest.mark.parametrize("units", [[], ["unit-a", "unit-a"], "unit-a", [1]])
def test_invalid_unit_sets_fail(units: object) -> None:
    with pytest.raises(ValueError, match="required_unit_ids"):
        build_rationale_audit([{**_record(), "required_unit_ids": units}])


def test_cli_separates_private_key_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "runs.jsonl"
    source.write_text(json.dumps(_record()) + "\n")
    output = tmp_path / "review"
    args = ["--runs", str(source), "--output-dir", str(output)]
    assert main(args) == 0
    reviewer = (output / "review.jsonl").read_text()
    assert "synthetic:model-a" not in reviewer
    assert "synthetic:model-a" in (output / "private-key.jsonl").read_text()
    assert main(args) == 2
    assert (output / "review.jsonl").read_text() == reviewer


def test_native_ledger_export_uses_completed_saved_responses(tmp_path: Path) -> None:
    ledger_path = tmp_path / "run.sqlite3"
    with RunnerLedger(ledger_path):
        pass
    source = _record()
    envelope = ForecastEnvelope(
        case_assessment="The complaint omits an element only for the first claim.",
        predictions=(
            ForecastPrediction(unit_id="unit-a", probability_fully_dismissed=0.7),
            ForecastPrediction(unit_id="unit-b", probability_fully_dismissed=0.2),
        ),
    )
    raw = envelope.model_dump_json()
    receipt = {
        "case_id": source["case_id"],
        "model_key": source["solver_id"],
        "run_identity_sha256": "synthetic-run-identity",
        "ablation": source["ablation"],
        "required_unit_ids": source["required_unit_ids"],
        "parser_output": public_parser_record(
            parse_model_output(raw, required_unit_ids=("unit-a", "unit-b"))
        ),
    }
    with sqlite3.connect(ledger_path) as connection:
        connection.executemany(
            "INSERT INTO public_runner_cells "
            "(cell_id, run_identity_sha256, case_id, unit_id, repeat_index, "
            "status, receipt_payload, response_payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "cell-a",
                    "synthetic-run-identity",
                    "synthetic-case",
                    "unit-a",
                    1,
                    "completed",
                    json.dumps(receipt).encode(),
                    json.dumps({"raw_output": raw}).encode(),
                ),
                (
                    "cell-b",
                    "synthetic-run-identity",
                    "synthetic-case",
                    "unit-a",
                    2,
                    "blocked",
                    None,
                    None,
                ),
            ],
        )
    before = ledger_path.read_bytes()
    output = tmp_path / "review"
    assert main(["--ledger", str(ledger_path), "--output-dir", str(output)]) == 0
    assert ledger_path.read_bytes() == before
    coverage = json.loads((output / "coverage.json").read_text())
    assert coverage["prediction_count"] == 2
    assert coverage["with_rationale"] == 0
    assert coverage["missing_rationale"] == 2
    assert coverage["with_case_assessment"] == 1
    assert coverage["missing_case_assessment"] == 0
    rows = (output / "review.jsonl").read_text()
    decoded_rows = [json.loads(line) for line in rows.splitlines()]
    case_rows = [row for row in decoded_rows if row["scope"] == "case"]
    unit_rows = [row for row in decoded_rows if row["scope"] == "unit"]
    assert len(case_rows) == 1
    assert case_rows[0]["unit_id"] is None
    assert case_rows[0]["rationale"] == envelope.case_assessment
    assert len(unit_rows) == 2
    assert all(row["rationale"] is None for row in unit_rows)
    assert {row["unit_id"] for row in unit_rows} == {"unit-a", "unit-b"}
    keys = [
        json.loads(line)
        for line in (output / "private-key.jsonl").read_text().splitlines()
    ]
    case_key = next(row for row in keys if row["scope"] == "case")
    assert case_key["review_id"] == case_rows[0]["review_id"]
    assert case_key["unit_id"] is None
    assert case_key["probability_fully_dismissed"] is None
    assert "synthetic:model-a" not in rows


def test_saved_raw_response_must_match_receipt_projection() -> None:
    record = _record()
    record["parser_output"] = public_parser_record(
        parse_model_output(
            str(record["raw_output"]), required_unit_ids=("unit-a", "unit-b")
        )
    )
    record["raw_output"] = str(record["raw_output"]).replace("0.7", "0.8")
    with pytest.raises(ValueError, match="does not match"):
        build_rationale_audit([record])
