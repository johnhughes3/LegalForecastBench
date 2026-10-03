"""Build a superseding, coherent public data tree after explicit case withdrawals."""

from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legalforecast.evals.output_parser import (
    parse_model_output,
)
from legalforecast.evals.run_record_scoring import ReleaseOutcomeLabel
from legalforecast.evals.scorers import ScoringCase, score_cases
from legalforecast.publication.historical_comparison import reproduce
from legalforecast.publication.site_comparison import compare
from legalforecast.publication.site_export_models import (
    SiteCalibrationBin,
    SiteExport,
    SiteResult,
    SiteUnit,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _census(row: SiteResult) -> set[tuple[str, str, int]]:
    return {(unit.case_id, unit.unit_id, unit.outcome) for unit in row.units}


def _rescore(row: SiteResult, excluded: set[str]) -> SiteResult:
    grouped: dict[str, list[SiteUnit]] = defaultdict(list)
    if (
        row.unit_count != len(row.units)
        or row.case_count != len({unit.case_id for unit in row.units})
        or len({(unit.case_id, unit.unit_id) for unit in row.units}) != row.unit_count
    ):
        raise ValueError("public result counts or unique unit membership disagree")
    for unit in row.units:
        if not math.isclose(
            unit.brier,
            (unit.probability_fully_dismissed - unit.outcome) ** 2,
            abs_tol=1e-12,
        ):
            raise ValueError("public unit loss differs from saved probability/outcome")
        if unit.case_id not in excluded:
            grouped[unit.case_id].append(unit)
    if not grouped:
        raise ValueError("withdrawal removes the entire scored cohort")
    cases = tuple(
        ScoringCase(
            case_id=case_id,
            model_id=row.model_id,
            parsed_output=parse_model_output(
                json.dumps(
                    {
                        "case_assessment": "Rescoring saved public probabilities.",
                        "predictions": [
                            {
                                "unit_id": unit.unit_id,
                                "probability_fully_dismissed": (
                                    unit.probability_fully_dismissed
                                ),
                            }
                            for unit in units
                        ],
                    }
                ),
                required_unit_ids=tuple(unit.unit_id for unit in units),
            ),
            outcome_labels=tuple(
                ReleaseOutcomeLabel(unit.unit_id, unit.outcome, None) for unit in units
            ),
        )
        for case_id, units in sorted(grouped.items())
    )
    count = sum(len(units) for units in grouped.values())
    summary = score_cases(
        cases,
        base_rate=sum(unit.outcome for units in grouped.values() for unit in units)
        / count,
        ece_bin_count=len(row.calibration),
    )
    costs = row.costs.model_copy(deep=True)
    workload_cases = costs.covered_case_count + costs.missing_case_count
    costs.caveats.append(
        f"Costs cover the original successful workload "
        f"({workload_cases} cases), not the retained "
        f"{summary.case_count}-case cohort; no aggregate cost was "
        f"apportioned."
    )
    return row.model_copy(
        update={
            "case_count": summary.case_count,
            "unit_count": summary.unit_count,
            "micro_brier": summary.micro_brier,
            "equal_case_brier": summary.macro_brier,
            "units": [unit for unit in row.units if unit.case_id not in excluded],
            "calibration": [
                SiteCalibrationBin(
                    lower=bin.lower,
                    upper=bin.upper,
                    unit_count=bin.unit_count,
                    mean_probability=bin.mean_probability,
                    observed_rate=bin.observed_rate,
                )
                for bin in summary.ece_bins
            ],
            "costs": costs,
        }
    )


def _analysis(
    directory: Path, excluded: set[str], replicates: int, exports_dir: Path
) -> dict[str, Any]:
    inputs = _read(directory / "inputs.json")
    models: dict[str, list[dict[str, Any]]] = {}
    for slug, relative in inputs["models"].items():
        path = directory / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("significance inputs must use local relative paths")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        rows = [row for row in rows if row["case_id"] not in excluded]
        exported = SiteExport.model_validate(_read(exports_dir / f"{slug}.json"))
        if len(exported.results) != 1 or {
            (
                row["case_id"],
                row["unit_id"],
                row["outcome"],
                row["probability_fully_dismissed"],
            )
            for row in rows
        } != {
            (unit.case_id, unit.unit_id, unit.outcome, unit.probability_fully_dismissed)
            for unit in exported.results[0].units
        }:
            raise ValueError(
                "significance inputs differ from selected public predictions"
            )
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        models[slug] = rows
    result = compare(
        models, replicates=replicates, family_model_count=inputs["family_model_count"]
    )
    inputs["provenance"]["cohort_validation"] = (
        f"Superseding common cohort: {result['case_count']} cases "
        f"and {result['unit_count']} units after withdrawals. "
        f"Original run/release provenance is retained."
    )
    result.update(
        sources=inputs["models"],
        provenance=inputs["provenance"],
        missing_models=inputs["missing_models"],
    )
    _write(directory / "inputs.json", inputs)
    _write(directory / "comparison.json", result)
    return result


def refresh_site(
    input_dir: Path,
    output_dir: Path,
    *,
    excluded_case_ids: Sequence[str],
    replicates: int = 1_000_000,
) -> dict[str, Any]:
    """Refresh built public JSON/JSONL data; leave original files untouched.

    Produce input with ``pnpm site:build`` and supply ``site/dist/data``.
    Aggregate-only models remain superseded historical observations; they cannot
    be rescored without predictions and never join the new active cohort.
    """
    excluded = set(excluded_case_ids)
    if not excluded or any(not case.strip() for case in excluded):
        raise ValueError("explicit nonempty withdrawn case IDs are required")
    if output_dir.exists() or input_dir.resolve() in output_dir.resolve().parents:
        raise ValueError("refresh output must be a new directory outside its source")
    current = _read(input_dir / "current.json")
    sources = _read(input_dir / "sources.json")
    exports: dict[str, SiteExport] = {}
    original_census: set[tuple[str, str, int]] | None = None
    for source in sources:
        slug = source["slug"]
        if Path(slug).name != slug or slug in exports:
            raise ValueError("native source slugs must be unique safe names")
        data = SiteExport.model_validate(_read(input_dir / "exports" / f"{slug}.json"))
        if len(data.results) != 1 or data.results[0].metadata.condition != "agentic":
            raise ValueError("native source must contain one agentic result")
        row = data.results[0]
        original = _rescore(row, set())
        if not math.isclose(
            row.micro_brier, original.micro_brier, abs_tol=1e-12
        ) or not math.isclose(
            row.equal_case_brier, original.equal_case_brier, abs_tol=1e-12
        ):
            raise ValueError("public aggregate differs from saved predictions")
        census = _census(data.results[0])
        if original_census is not None and census != original_census:
            raise ValueError("selected native exports disagree on original cohort")
        if len(census) != data.results[0].unit_count:
            raise ValueError("native export has duplicate unit membership")
        original_census = census
        exports[slug] = data
    if not exports or not excluded.issubset(
        {case for case, _, _ in original_census or set()}
    ):
        raise ValueError("withdrawal cases must belong to the selected cohort")
    historical = [model for model in current["models"] if model["slug"] not in exports]
    selected = {
        model["slug"]: model for model in current["models"] if model["slug"] in exports
    }
    if set(selected) != set(exports):
        raise ValueError("selected native exports do not match current model rows")
    reference = next(iter(exports.values())).results[0]
    if (current["cohort"]["case_count"], current["cohort"]["unit_count"]) != (
        reference.case_count,
        reference.unit_count,
    ):
        raise ValueError("current aggregate and selected native cohorts disagree")
    shutil.copytree(input_dir, output_dir, ignore=shutil.ignore_patterns("*.html"))
    for slug, data in exports.items():
        row = _rescore(data.results[0], excluded)
        data = data.model_copy(
            update={
                "results": [row],
                "excluded_case_count": data.excluded_case_count + len(excluded),
            }
        )
        _write(output_dir / "exports" / f"{slug}.json", data.model_dump(mode="json"))
        model = selected[slug]
        model.update(
            micro_brier=row.micro_brier,
            equal_case_brier=row.equal_case_brier,
            correct=sum(
                (unit.probability_fully_dismissed >= 0.5) == bool(unit.outcome)
                for unit in row.units
            ),
        )
        high = [
            unit
            for unit in row.units
            if unit.probability_fully_dismissed <= 0.1
            or unit.probability_fully_dismissed >= 0.9
        ]
        model["high_confidence"] = {
            "count": len(high),
            "wrong": sum(
                (unit.probability_fully_dismissed >= 0.5) != bool(unit.outcome)
                for unit in high
            ),
            "mean_confidence": sum(
                max(
                    unit.probability_fully_dismissed,
                    1 - unit.probability_fully_dismissed,
                )
                for unit in high
            )
            / len(high)
            if high
            else None,
        }
        workload_cases = row.costs.covered_case_count + row.costs.missing_case_count
        model["cost"]["note"] = (
            f"{model['cost'].get('note') or ''} Original "
            f"{workload_cases}-case successful "
            f"workload; not apportioned to the retained cohort.".strip()
        )
    first = next(iter(exports.values())).results[0]
    remaining = [unit for unit in first.units if unit.case_id not in excluded]
    prevalence = sum(unit.outcome for unit in remaining) / len(remaining)
    current["models"] = list(selected.values())
    current["snapshot_id"] += "-withdrawal-refresh"
    current["title"] += " — superseding withdrawn cohort"
    current["as_of"] = datetime.now(UTC).date().isoformat()
    current["provenance"]["method"] += (
        "Superseding aggregate after case withdrawals; original "
        "release identity preserved."
    )
    current["cohort"].update(
        case_count=len({unit.case_id for unit in remaining}),
        unit_count=len(remaining),
        dismissed_unit_count=sum(unit.outcome for unit in remaining),
        constant_forecast_micro_brier=prevalence * (1 - prevalence),
        majority_class_accuracy=max(prevalence, 1 - prevalence),
    )
    analysis = _analysis(
        output_dir / "significance", excluded, replicates, output_dir / "exports"
    )
    if (analysis["case_count"], analysis["unit_count"]) != (
        current["cohort"]["case_count"],
        current["cohort"]["unit_count"],
    ):
        raise ValueError("significance and selected native cohorts disagree")
    current["significant_pairs"] = analysis["significant_pairs"]
    current["cohort"]["bootstrap"].update(
        replicates=replicates,
        correction=analysis["correction"],
        caveat=analysis["caveat"],
    )
    _write(output_dir / "current.json", current)
    _write(
        output_dir / "historical-aggregates.json",
        {
            "status": "superseded",
            "reason": "Unit-level evidence unavailable for rescoring "
            "the changed cohort; excluded from active rankings and "
            "significance.",
            "provenance": _read(input_dir / "current.json")["provenance"],
            "cohort": _read(input_dir / "current.json")["cohort"],
            "models": historical,
        },
    )
    _refresh_other_downloads(
        output_dir,
        excluded,
        replicates,
        {(unit.case_id, unit.unit_id, unit.outcome) for unit in remaining},
    )
    return current


def _refresh_other_downloads(
    output: Path, excluded: set[str], replicates: int, census: set[tuple[str, str, int]]
) -> None:
    """Keep summary experiment downloads on their own refreshed common cohort."""
    catalog_path = output / "summary-comparison" / "catalog.json"
    if catalog_path.exists():
        catalog = _read(catalog_path)
        for source in catalog:
            slug = source["slug"]
            path = output / "exports" / f"{slug}.json"
            data = SiteExport.model_validate(_read(path))
            row = _rescore(data.results[0], excluded)
            if _census(row) != census:
                raise ValueError(
                    "summary experiment differs from refreshed reference cohort"
                )
            count = len({unit.case_id for unit in data.results[0].units} & excluded)
            _write(
                path,
                data.model_copy(
                    update={
                        "results": [row],
                        "excluded_case_count": data.excluded_case_count + count,
                    }
                ).model_dump(mode="json"),
            )
            forecasts = output / "summary-comparison" / slug / "forecasts.json"
            records = [
                record
                for record in _read(forecasts)
                if record["case_id"] not in excluded
            ]
            _write(forecasts, records)
            source.update(
                forecast_case_count=len(records),
                forecast_unit_count=sum(
                    len(record["predictions"]) for record in records
                ),
                scored_unit_count=row.unit_count,
            )
            source["inference_cost_caveat"] += (
                "Costs retain the original successful workload and are not "
                "apportioned after withdrawal."
            )
        _write(catalog_path, catalog)
        outcomes = output / "summary-comparison" / "published-outcomes.json"
        _write(
            outcomes, [row for row in _read(outcomes) if row["case_id"] not in excluded]
        )
        _analysis(
            output / "significance" / "summary",
            excluded,
            replicates,
            output / "exports",
        )
    historical = output / "historical-comparison" / "inputs.json"
    if historical.exists():
        data = _read(historical)
        reproduce(
            historical,
            historical.with_name("results.json"),
            excluded_case_ids=excluded,
            expected_case_count=len({row["case_id"] for row in data["labels"]}),
            expected_unit_count=len(data["labels"]),
        )
        data["labels"] = [
            row for row in data["labels"] if row["case_id"] not in excluded
        ]
        for condition in data["conditions"]:
            condition["cases"] = [
                row for row in condition["cases"] if row["case_id"] not in excluded
            ]
        _write(historical, data)
