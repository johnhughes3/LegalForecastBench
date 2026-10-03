"""Historical extracts reproduce scores without inventing failed predictions."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reproduce_historical_comparison",
    ROOT / "scripts/reproduce_historical_comparison.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / "site/public/data/historical-comparison/inputs.json"


def test_saved_results_reproduce_with_failure_and_null_coverage(tmp_path: Path) -> None:
    """Exercise original saved probabilities through the shared scoring code."""
    output = tmp_path / "results.json"
    MODULE.reproduce(SOURCE, output)
    result = json.loads(output.read_text())
    expected = json.loads(SOURCE.with_name("results.json").read_text())
    assert result == expected
    gemini, luna = result["conditions"]
    assert (
        gemini["accepted_cases"],
        gemini["scored_cases"],
        gemini["scored_units"],
    ) == (100, 94, 385)
    assert (luna["accepted_cases"], luna["scored_cases"], luna["scored_units"]) == (
        98,
        92,
        367,
    )
    assert luna["dropped_labelled_units"] == 18
    assert len(luna["failed_cases"]) == 2
    assert (
        luna["estimated_all_execution_cost_usd"]
        > luna["estimated_accepted_case_cost_usd"]
    )
    # Direct independent arithmetic checks exclude null labels and entire failed cases.
    source = json.loads(SOURCE.read_text())
    outcomes = {label["unit_id"]: label["outcome"] for label in source["labels"]}
    for condition, actual in zip(
        source["conditions"], result["conditions"], strict=True
    ):
        case_errors = []
        all_errors = []
        for case in condition["cases"]:
            if case["status"] != "valid":
                continue
            errors = [
                (p["probability_fully_dismissed"] - outcomes[p["unit_id"]]) ** 2
                for p in case["predictions"]
                if outcomes[p["unit_id"]] is not None
            ]
            if errors:
                case_errors.append(sum(errors) / len(errors))
                all_errors.extend(errors)
        assert actual["micro_brier"] == pytest.approx(sum(all_errors) / len(all_errors))
        assert actual["equal_case_brier"] == pytest.approx(
            sum(case_errors) / len(case_errors)
        )


@pytest.mark.parametrize(
    "damage",
    [
        "missing_prediction",
        "duplicate_case",
        "private_field",
        "invented_outcome",
        "boolean_outcome",
    ],
)
def test_malformed_extracts_fail_instead_of_scoring_defaults(
    tmp_path: Path, damage: str
) -> None:
    """Public reproduction cannot silently score incomplete or augmented inputs."""
    data = json.loads(SOURCE.read_text())
    if damage == "missing_prediction":
        data["conditions"][0]["cases"][0]["predictions"].pop()
    elif damage == "duplicate_case":
        data["conditions"][0]["cases"][0] = data["conditions"][0]["cases"][1]
    elif damage == "private_field":
        data["conditions"][0]["cases"][0]["raw_document"] = "private payload"
    elif damage == "boolean_outcome":
        data["labels"][0]["outcome"] = True
    else:
        data["labels"][0]["outcome"] = 2
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        MODULE.reproduce(source, tmp_path / "output.json")


def test_withdrawal_filters_appendix_and_remains_reproducible(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text())
    removed = source["labels"][0]["case_id"]
    output = tmp_path / "results.json"
    MODULE.reproduce(SOURCE, output, excluded_case_ids={removed})
    refreshed = json.loads(output.read_text())
    assert refreshed["available_cases"] == 99
    assert removed not in output.read_text()
    source["labels"] = [row for row in source["labels"] if row["case_id"] != removed]
    for condition in source["conditions"]:
        condition["cases"] = [
            row for row in condition["cases"] if row["case_id"] != removed
        ]
    filtered = tmp_path / "inputs.json"
    filtered.write_text(json.dumps(source))
    independent = tmp_path / "independent.json"
    MODULE.reproduce(
        filtered,
        independent,
        expected_case_count=99,
        expected_unit_count=refreshed["available_units"],
    )
    assert json.loads(independent.read_text()) == refreshed


def test_case_absent_from_appendix_preserves_original_results(tmp_path: Path) -> None:
    output = tmp_path / "results.json"
    MODULE.reproduce(SOURCE, output, excluded_case_ids={"synthetic-absent-case"})
    assert json.loads(output.read_text()) == json.loads(
        SOURCE.with_name("results.json").read_text()
    )
