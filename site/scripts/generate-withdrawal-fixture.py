"""Generate fictional two-case data with the site's real configuration names.

Run after a default site build, then use `legalforecast site refresh` on this
fixture. Only shape and display metadata are reused; all predictions are synthetic.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def generate(output: Path) -> None:
    built = ROOT / "site/dist/data"
    snapshot = read(built / "current.json")
    sources = read(built / "sources.json")
    assert len(snapshot["models"]) == 18
    assert (
        len([model for model in snapshot["models"] if model["slug"] != "gpt-4-1"]) == 17
    )
    assert len(sources) == 11
    catalog = read(built / "summary-comparison/catalog.json")
    template = read(ROOT / "site/src/data/fixtures/site-export.json")
    units = template["results"][0]["units"]
    snapshot.update(
        snapshot_id="synthetic",
        title="Synthetic withdrawal fixture",
        significant_pairs=[],
    )
    snapshot["provenance"]["method"] = (
        "Synthetic test predictions; no model executions."
    )
    snapshot["cohort"].update(case_count=2, unit_count=3, dismissed_unit_count=1)
    for model in snapshot["models"]:
        model.update(
            micro_brier=0.23,
            equal_case_brier=0.295,
            correct=2,
            high_confidence={"count": 0, "wrong": 0, "mean_confidence": None},
            cost={"usd": None, "basis": "unavailable", "note": "Synthetic test."},
        )
    write(output / "current.json", snapshot)
    write(output / "sources.json", sources)
    write(output / "costs.json", [])
    for group, entries in [("", sources), ("/summary", catalog)]:
        models = {}
        for source in entries:
            slug = source["slug"]
            original = read(built / "exports" / f"{slug}.json")
            data = deepcopy(template)
            data["source"] = original["source"]
            data["contamination_boundary"] = original["contamination_boundary"]
            data["results"][0]["metadata"] = original["results"][0]["metadata"]
            data["results"][0]["model_id"] = original["results"][0]["model_id"]
            write(output / "exports" / f"{slug}.json", data)
            directory = output / f"significance{group}"
            directory.mkdir(parents=True, exist_ok=True)
            models[slug] = f"{slug}.jsonl"
            (directory / f"{slug}.jsonl").write_text(
                "".join(json.dumps(unit) + "\n" for unit in units)
            )
        manifest = read(built / f"significance{group}/inputs.json")
        manifest["models"] = models
        write(output / f"significance{group}/inputs.json", manifest)
    for source in catalog:
        source.update(forecast_case_count=2, forecast_unit_count=3, scored_unit_count=3)
        forecasts = [
            {
                "case_id": case,
                "raw_output_sha256": "sha256:" + "0" * 64,
                "predictions": [unit for unit in units if unit["case_id"] == case],
            }
            for case in ["synthetic-case-a", "synthetic-case-b"]
        ]
        write(
            output / "summary-comparison" / source["slug"] / "forecasts.json", forecasts
        )
        registry_source = (
            built / "summary-comparison" / source["slug"] / "registry.json"
        )
        registry_target = (
            output / "summary-comparison" / source["slug"] / "registry.json"
        )
        registry_target.write_bytes(registry_source.read_bytes())
    write(output / "summary-comparison/catalog.json", catalog)
    write(output / "summary-comparison/published-outcomes.json", units)
    historical = read(built / "historical-comparison/inputs.json")
    historical["labels"] = [
        {key: unit[key] for key in ("case_id", "unit_id", "outcome")} for unit in units
    ]
    for condition in historical["conditions"]:
        condition["cases"] = [
            {
                "case_id": case,
                "raw_output_sha256": "sha256:" + "0" * 64,
                "required_unit_ids": [
                    unit["unit_id"] for unit in units if unit["case_id"] == case
                ],
                "status": "valid",
                "predictions": [
                    {
                        "unit_id": unit["unit_id"],
                        "probability_fully_dismissed": unit[
                            "probability_fully_dismissed"
                        ],
                    }
                    for unit in units
                    if unit["case_id"] == case
                ],
                "input_tokens": 10,
                "output_tokens": 5,
                "estimated_cost_usd": 0.01,
            }
            for case in ["synthetic-case-a", "synthetic-case-b"]
        ]
    write(output / "historical-comparison/inputs.json", historical)


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
