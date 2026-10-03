"""Public summary comparison inputs reproduce the displayed native exports."""

import importlib.util
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "reproduce_summary_comparisons",
    Path(__file__).parents[1] / "scripts/reproduce_summary_comparisons.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_summary_comparisons_reproduce_displayed_exports(tmp_path: Path) -> None:
    """Exercise frozen registries, prediction census, canonical scoring and export."""
    site = Path(__file__).parents[1] / "site"
    MODULE.reproduce(site / "public/data/summary-comparison", tmp_path)
    exports = sorted(tmp_path.glob("*.json"))
    assert len(exports) == 3
    for export in exports:
        expected = site / "src/data/exports" / export.name
        reproduced = json.loads(export.read_text())
        assert reproduced == json.loads(expected.read_text())
        costs = reproduced["results"][0]["costs"]
        assert costs["basis"] == "unavailable"
        assert "cost_scope" not in costs
        assert "missing_response_usage_case_count" not in costs


def test_cli_refresh_then_summary_reproduction(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(
        root / "site/public/data/summary-comparison", source / "summary-comparison"
    )
    shutil.copytree(root / "site/src/data/significance", source / "significance")
    shutil.copytree(root / "site/src/data/exports", source / "exports")
    # Use one reconstructable selected native model with the full saved public cohort.
    native = json.loads((source / "exports/gpt-6-sol.json").read_text())
    row = native["results"][0]
    case = row["units"][0]["case_id"]
    snapshot = json.loads(
        (root / "site/src/data/snapshots/beta-2026-09-18.json").read_text()
    )
    model = snapshot["models"][0]
    model.update(
        slug="gpt-6-sol",
        model_key=row["model_id"],
        micro_brier=row["micro_brier"],
        equal_case_brier=row["equal_case_brier"],
    )
    second = deepcopy(model)
    second_row = json.loads((source / "exports/gpt-6-luna.json").read_text())[
        "results"
    ][0]
    second.update(
        slug="gpt-6-luna",
        model_key=second_row["model_id"],
        micro_brier=second_row["micro_brier"],
        equal_case_brier=second_row["equal_case_brier"],
    )
    snapshot["models"] = [model, second]
    snapshot["cohort"].update(
        case_count=row["case_count"], unit_count=row["unit_count"]
    )
    (source / "current.json").write_text(json.dumps(snapshot))
    (source / "sources.json").write_text(
        json.dumps([{"slug": "gpt-6-sol"}, {"slug": "gpt-6-luna"}])
    )
    inputs_path = source / "significance/inputs.json"
    inputs = json.loads(inputs_path.read_text())
    inputs["models"] = {
        slug: inputs["models"][slug] for slug in ["gpt-6-sol", "gpt-6-luna"]
    }
    inputs_path.write_text(json.dumps(inputs))
    refreshed = tmp_path / "refreshed"
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from legalforecast.cli import main; main()",
            "site",
            "refresh",
            "--input-dir",
            str(source),
            "--output-dir",
            str(refreshed),
            "--withdrawn-case",
            case,
            "--replicates",
            "10",
        ],
        cwd=root,
        check=True,
    )
    catalog = json.loads((refreshed / "summary-comparison/catalog.json").read_text())
    output = tmp_path / "reproduced"
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/reproduce_summary_comparisons.py"),
            str(refreshed / "summary-comparison"),
            str(output),
            "--expected-case-count",
            str(catalog[0]["forecast_case_count"]),
            "--expected-scored-unit-count",
            str(catalog[0]["scored_unit_count"]),
            "--expected-forecast-unit-count",
            str(catalog[0]["forecast_unit_count"]),
        ],
        cwd=root,
        check=True,
    )
    for item in catalog:
        actual = json.loads((output / f"{item['slug']}.json").read_text())["results"][0]
        expected = json.loads((refreshed / f"exports/{item['slug']}.json").read_text())[
            "results"
        ][0]
        for field in (
            "case_count",
            "unit_count",
            "micro_brier",
            "equal_case_brier",
            "units",
            "calibration",
        ):
            assert actual[field] == expected[field]
        assert case not in json.dumps(actual)
