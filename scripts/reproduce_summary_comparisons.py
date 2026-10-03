"""Reproduce summary comparisons from public forecast extracts and published outcomes.

Run: uv run python scripts/reproduce_summary_comparisons.py INPUT_DIR OUTPUT_DIR
The input directory contains catalog.json, published-outcomes.json, and each
condition's forecasts.json and original frozen registry.json. No model calls.
"""

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import TypedDict, cast

from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_sha256,
)
from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    ParsedPrediction,
    ParserStatus,
)
from legalforecast.evals.run_record_scoring import ReleaseOutcomeLabel
from legalforecast.evals.scorers import ScoringCase, score_cases
from legalforecast.publication.site_export import build_site_export


class CatalogEntry(TypedDict):
    slug: str
    model_key: str
    run_identity_sha256: str
    model_registry_sha256: str
    summary_cache_sha256: str
    recomputed_at: str


class OutcomeRecord(TypedDict):
    case_id: str
    unit_id: str
    outcome: int


class PredictionRecord(TypedDict):
    unit_id: str
    probability_fully_dismissed: float


class ForecastRecord(TypedDict):
    case_id: str
    raw_output_sha256: str
    predictions: list[PredictionRecord]


class RegistryBinding(TypedDict):
    jev_summaries_sha256: str
    tool_policy: str


def reproduce(source: Path, output: Path) -> None:
    catalog = cast(
        list[CatalogEntry], json.loads((source / "catalog.json").read_text())
    )
    labels = cast(
        list[OutcomeRecord],
        json.loads((source / "published-outcomes.json").read_text()),
    )
    assert len(labels) == 387 and len({x["unit_id"] for x in labels}) == 387
    assert len({x["case_id"] for x in labels}) == 91
    by_case: defaultdict[str, list[OutcomeRecord]] = defaultdict(list)
    for row in labels:
        by_case[row["case_id"]].append(row)
    output.mkdir(parents=True, exist_ok=True)
    for item in catalog:
        root = source / item["slug"]
        raw_registry = (root / "registry.json").read_bytes()
        assert model_registry_sha256(raw_registry) == item["model_registry_sha256"]
        registry = load_model_registry_bytes(raw_registry)
        original = cast(list[RegistryBinding], json.loads(raw_registry))[0]
        assert original["jev_summaries_sha256"] == item["summary_cache_sha256"]
        assert original["tool_policy"] == "no_tools"
        forecasts = cast(
            list[ForecastRecord], json.loads((root / "forecasts.json").read_text())
        )
        assert len(forecasts) == 91
        forecast_case_ids = {row["case_id"] for row in forecasts}
        assert len(forecast_case_ids) == 91 and forecast_case_ids == set(by_case)
        all_ids = [p["unit_id"] for row in forecasts for p in row["predictions"]]
        assert len(all_ids) == len(set(all_ids)) == 409
        cases: list[ScoringCase] = []
        for row in forecasts:
            case_id = row["case_id"]
            predictions = {p["unit_id"]: p for p in row["predictions"]}
            units = sorted(by_case[case_id], key=lambda p: p["unit_id"])
            assert units and all(p["unit_id"] in predictions for p in units)
            ids = tuple(p["unit_id"] for p in units)
            parsed = ParsedModelOutput(
                status=ParserStatus.VALID,
                raw_output_sha256=row["raw_output_sha256"],
                required_unit_ids=ids,
                predictions=tuple(
                    ParsedPrediction(
                        unit_id=uid,
                        probability_fully_dismissed=predictions[uid][
                            "probability_fully_dismissed"
                        ],
                        defaulted=False,
                        invalid_reason=None,
                    )
                    for uid in ids
                ),
                issues=(),
            )
            cases.append(
                ScoringCase(
                    case_id=case_id,
                    model_id=item["model_key"],
                    parsed_output=parsed,
                    outcome_labels=tuple(
                        ReleaseOutcomeLabel(p["unit_id"], p["outcome"], None)
                        for p in units
                    ),
                )
            )
        summary = score_cases(
            tuple(cases), base_rate=sum(p["outcome"] for p in labels) / len(labels)
        )
        payload = {
            "generated_at": catalog[0]["recomputed_at"],
            "identity": {
                "run_identity_sha256": item["run_identity_sha256"],
                "model_registry_sha256": item["model_registry_sha256"],
            },
            "summaries": [summary.to_record()],
        }
        export = build_site_export(
            payload, registry=registry, contamination_boundary=date(2026, 6, 30)
        )
        # This reproducer has no receipt accounting input. Preserve the original
        # no-cost-evidence contract rather than minting default accounting claims
        # that were absent from the published experiment.
        historical_cost_fields = {
            "currency",
            "basis",
            "total_cost",
            "cost_per_case",
            "covered_case_count",
            "missing_case_count",
            "standard_rate_total_cost",
            "standard_rate_status",
        }
        historical = export.model_dump(mode="json")
        for row in historical["results"]:
            assert row["costs"]["basis"] == "unavailable"
            row["costs"] = {
                key: value
                for key, value in row["costs"].items()
                if key in historical_cost_fields
            }
        (output / (item["slug"] + ".json")).write_text(
            json.dumps(historical, indent=2) + "\n"
        )
        print(
            item["slug"],
            summary.case_count,
            summary.unit_count,
            summary.micro_brier,
            summary.macro_brier,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    reproduce(cast(Path, args.input_directory), cast(Path, args.output_directory))
