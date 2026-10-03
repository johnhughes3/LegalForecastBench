"""Withdrawal refresh keeps current metrics and every unit download coherent."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from legalforecast.publication.site_refresh import refresh_site

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def public_fixture(root: Path) -> None:
    data = json.loads((ROOT / "site/src/data/fixtures/site-export.json").read_text())
    original = json.loads(
        (ROOT / "site/src/data/snapshots/beta-2026-09-18.json").read_text()
    )
    original["models"] = [deepcopy(original["models"][0]) for _ in range(3)]
    slugs = ["alpha", "beta", "missing"]
    for slug, row in zip(slugs, original["models"], strict=True):
        row.update(
            slug=slug,
            model_key=slug,
            display_name=f"Synthetic {slug}",
            provider="Synthetic",
            correct=2,
            high_confidence={"count": 0, "wrong": 0, "mean_confidence": None},
            micro_brier=data["results"][0]["micro_brier"],
            equal_case_brier=data["results"][0]["equal_case_brier"],
        )
    original.update(
        snapshot_id="synthetic", title="Synthetic fixture", significant_pairs=[]
    )
    original["cohort"].update(case_count=2, unit_count=3, dismissed_unit_count=1)
    write(root / "current.json", original)
    write(root / "costs.json", [])
    write(
        root / "sources.json",
        [
            {
                "slug": slug,
                "release_date": "2026-01-01",
                "forecast_run": "123",
                "scoring_run": "124",
                "access": "Synthetic",
                "provider": "Synthetic",
                "release": original["provenance"]["release"],
                "release_digest": original["provenance"]["release_digest"],
                "display_name": f"Synthetic {slug}",
                "reasoning": "None",
            }
            for slug in slugs[:2]
        ],
    )
    for slug in ["alpha", "beta", "summary-one", "summary-two"]:
        item = deepcopy(data)
        item["results"][0]["model_id"] = slug
        item["results"][0]["metadata"]["condition"] = (
            "summary" if slug.startswith("summary") else "agentic"
        )
        write(root / "exports" / f"{slug}.json", item)
    for directory, models, family in [
        (root / "significance", slugs[:2], 18),
        (root / "significance/summary", ["summary-one", "summary-two"], 3),
    ]:
        write(
            directory / "inputs.json",
            {
                "models": {slug: f"{slug}.jsonl" for slug in models},
                "family_model_count": family,
                "missing_models": ["missing"] if family == 18 else [],
                "provenance": {"release": "synthetic"},
            },
        )
        for slug in models:
            (directory / f"{slug}.jsonl").write_text(
                "".join(json.dumps(unit) + "\n" for unit in data["results"][0]["units"])
            )
    write(
        root / "summary-comparison/catalog.json",
        [
            {
                "slug": slug,
                "inference_cost_caveat": "Original workload.",
                "forecast_run_id": "125",
                "model_key": slug,
                "summary_cache_sha256": "2" * 64,
                "run_identity_sha256": "0" * 64,
                "model_registry_sha256": "1" * 64,
                "summary_preparation_estimated_usd": 0.1,
                "successful_inference_estimated_usd": 0.2,
                "forecast_case_count": 2,
                "forecast_unit_count": 3,
                "scored_unit_count": 3,
            }
            for slug in ["summary-one", "summary-two"]
        ],
    )
    write(
        root / "summary-comparison/published-outcomes.json", data["results"][0]["units"]
    )
    for slug in ["summary-one", "summary-two"]:
        write(
            root / "summary-comparison" / slug / "forecasts.json",
            [
                {
                    "case_id": case,
                    "predictions": [
                        unit
                        for unit in data["results"][0]["units"]
                        if unit["case_id"] == case
                    ],
                }
                for case in ["synthetic-case-a", "synthetic-case-b"]
            ],
        )


def test_one_withdrawal_refreshes_all_current_data(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "refreshed"
    public_fixture(source)
    result = refresh_site(
        source, output, excluded_case_ids=["synthetic-case-b"], replicates=100
    )
    assert result["cohort"]["case_count"] == 1
    assert result["cohort"]["unit_count"] == 2
    assert {model["slug"] for model in result["models"]} == {"alpha", "beta"}
    for model in result["models"]:
        assert model["micro_brier"] == pytest.approx(0.1)
        assert model["equal_case_brier"] == pytest.approx(0.1)
    historical = json.loads((output / "historical-aggregates.json").read_text())
    assert historical["status"] == "superseded"
    assert [model["slug"] for model in historical["models"]] == ["missing"]
    for path in output.rglob("*.json*"):
        assert "synthetic-case-b" not in path.read_text(), str(path)
        assert "synthetic-unit-b1" not in path.read_text(), str(path)
    for path in (output / "exports").glob("*.json"):
        data = json.loads(path.read_text())
        row = data["results"][0]
        assert data["excluded_case_count"] == 1
        assert (row["case_count"], row["unit_count"]) == (1, 2)
        assert row["costs"]["missing_case_count"] == 2  # Original workload evidence.
        assert "original successful workload" in row["costs"]["caveats"][-1]
    comparison = json.loads((output / "significance/comparison.json").read_text())
    assert comparison["family_model_count"] == 18
    assert comparison["interval_confidence"] == pytest.approx(1 - 0.05 / (153 * 3))
    assert comparison["case_count"] == 1
    summaries = json.loads(
        (output / "significance/summary/comparison.json").read_text()
    )
    assert summaries["family_model_count"] == 3 and summaries["case_count"] == 1
    assert "synthetic-case-b" in (source / "exports/alpha.json").read_text()


def test_unknown_withdrawal_does_not_write_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    public_fixture(source)
    with pytest.raises(ValueError, match="belong"):
        refresh_site(source, tmp_path / "output", excluded_case_ids=["unknown"])
    assert not (tmp_path / "output").exists()


def test_successive_withdrawals_preserve_history_and_cumulative_counts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    public_fixture(source)
    # Add a third synthetic case to every current prediction source.
    for path in (source / "exports").glob("*.json"):
        data = json.loads(path.read_text())
        row = data["results"][0]
        unit = deepcopy(row["units"][-1])
        unit.update(case_id="synthetic-case-c", unit_id="synthetic-unit-c1")
        row["units"].append(unit)
        row.update(case_count=3, unit_count=4, micro_brier=0.295, equal_case_brier=0.36)
        write(path, data)
    for path in (source / "significance").rglob("*.jsonl"):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        unit = deepcopy(rows[-1])
        unit.update(case_id="synthetic-case-c", unit_id="synthetic-unit-c1")
        rows.append(unit)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    snapshot = json.loads((source / "current.json").read_text())
    snapshot["cohort"].update(case_count=3, unit_count=4)
    for model in snapshot["models"]:
        model.update(micro_brier=0.295, equal_case_brier=0.36)
    write(source / "current.json", snapshot)
    outcomes = json.loads(
        (source / "summary-comparison/published-outcomes.json").read_text()
    )
    unit = deepcopy(outcomes[-1])
    unit.update(case_id="synthetic-case-c", unit_id="synthetic-unit-c1")
    outcomes.append(unit)
    write(source / "summary-comparison/published-outcomes.json", outcomes)
    for path in (source / "summary-comparison").rglob("forecasts.json"):
        rows = json.loads(path.read_text())
        case = deepcopy(rows[-1])
        case["case_id"] = "synthetic-case-c"
        case["predictions"][0].update(
            case_id="synthetic-case-c", unit_id="synthetic-unit-c1"
        )
        rows.append(case)
        write(path, rows)
    first, second = tmp_path / "first", tmp_path / "second"
    refresh_site(source, first, excluded_case_ids=["synthetic-case-b"], replicates=10)
    refresh_site(first, second, excluded_case_ids=["synthetic-case-c"], replicates=10)
    assert json.loads(
        (second / "historical-aggregates.json").read_text()
    ) == json.loads((first / "historical-aggregates.json").read_text())
    for path in (second / "exports").glob("*.json"):
        data = json.loads(path.read_text())
        assert data["excluded_case_count"] == 2
        assert data["results"][0]["case_count"] == 1
    for path in second.rglob("*.json*"):
        assert "synthetic-case-b" not in path.read_text()
        assert "synthetic-case-c" not in path.read_text()
