from __future__ import annotations

import csv
import json
from io import StringIO

import pytest
from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    BootstrapInferenceResult,
    ModelRank,
    PairwiseDelta,
)
from legalforecast.evals.scorers import CalibrationBin, ScoreSummary
from legalforecast.reporting.calibration import (
    calibration_curve_records,
    calibration_svg,
)
from legalforecast.reporting.leaderboard import (
    AccountingLeaderboardRow,
    build_benchmark_leaderboard_report,
)
from legalforecast.reporting.pareto import (
    ParetoPoint,
    pareto_frontier_records,
    pareto_records,
)


def test_leaderboard_report_emits_json_csv_markdown_and_html() -> None:
    report = build_benchmark_leaderboard_report(
        (
            _summary("model-a", micro_brier=0.10, ece=0.03),
            _summary("model-b", micro_brier=0.12, ece=0.04),
            _summary("model-c", micro_brier=0.20, ece=0.10),
        ),
        accounting_rows=(
            _accounting("model-a", cost_per_case=0.030, tool_calls=2.0),
            _accounting("model-b", cost_per_case=0.010, tool_calls=1.0),
            _accounting("model-c", cost_per_case=0.040, tool_calls=5.0),
        ),
        inference=_inference(),
        repeat_variance_rows=(
            {
                "model_id": "model-a",
                "repeated_case_count": 2,
                "repeat_run_count": 6,
                "root_mean_within_case_variance": 0.015,
            },
        ),
    )

    record = report.to_record()
    rows = record["rows"]
    model_a = rows[0]
    model_b = rows[1]

    assert [row["model_id"] for row in rows] == ["model-a", "model-b", "model-c"]
    assert model_a["rank"] == 1
    assert model_a["rank_tier"] == 1
    assert model_a["row_type"] == "model"
    assert model_a["micro_brier"] == 0.10
    assert model_a["cost_per_case"] == 0.030
    assert model_a["mean_tool_calls_per_case"] == 2.0
    assert model_a["capped_case_micro_brier"] == 0.11
    assert model_a["repeat_sample_case_count"] == 2
    assert model_a["repeat_sample_run_count"] == 6
    assert model_a["within_model_micro_brier_stddev"] == 0.015
    assert model_b["delta_vs_best"] == 0.02
    assert model_b["delta_vs_best_ci_low"] == -0.01
    assert model_b["delta_vs_best_ci_high"] == 0.05
    assert {row["model_id"] for row in record["pareto_accuracy_cost"]} == {
        "model-a",
        "model-b",
    }
    assert record["rank_tier_method"] == (
        "bonferroni_pairwise_bootstrap_confidence_intervals"
    )
    assert "not a full simultaneous ranking model" in record["rank_tier_caveat"]

    assert json.loads(report.to_json())["rows"][0]["model_id"] == "model-a"

    csv_rows = tuple(csv.DictReader(StringIO(report.to_csv())))
    assert csv_rows[0]["model_id"] == "model-a"
    assert csv_rows[0]["row_type"] == "model"
    assert csv_rows[0]["micro_brier"] == "0.1"
    assert "delta_vs_best_ci_low" in csv_rows[0]
    assert csv_rows[0]["within_model_micro_brier_stddev"] == "0.015"

    markdown = report.to_markdown()
    assert "| Rank | Tier | Model | Type | Micro-Brier | BSS |" in markdown
    assert "Repeat stddev" in markdown
    assert "Rank tiers use Bonferroni-adjusted pairwise bootstrap" in markdown
    assert "## Pareto Frontier" in markdown
    assert "model-b" in markdown

    html = report.to_html()
    assert "<table" in html
    assert "<svg" in html
    assert "Repeat stddev" in html
    assert "Rank tiers use Bonferroni-adjusted pairwise bootstrap" in html
    assert "Pareto Frontier" in html


def test_calibration_records_and_svg_preserve_bin_data() -> None:
    summary = _summary("model-a", micro_brier=0.10, ece=0.03)

    records = calibration_curve_records((summary,))
    svg = calibration_svg((summary,))

    assert records[0] == {
        "model_id": "model-a",
        "bin_index": 0,
        "lower": 0.0,
        "upper": 0.5,
        "unit_count": 3,
        "mean_probability": 0.2,
        "observed_rate": 0.25,
        "absolute_calibration_error": 0.05,
    }
    assert svg.startswith("<svg")
    assert "model-a" in svg
    assert "calibration-diagonal" in svg


def test_baseline_rows_keep_separate_rank_sequence_and_row_type() -> None:
    report = build_benchmark_leaderboard_report(
        (
            _summary("baseline:judge_history", micro_brier=0.05, ece=0.01),
            _summary("model-a", micro_brier=0.10, ece=0.03),
            _summary("model-b", micro_brier=0.12, ece=0.04),
            _summary("baseline:global_base_rate", micro_brier=0.20, ece=0.08),
        )
    )

    records = report.to_record()["rows"]
    assert [row["model_id"] for row in records] == [
        "model-a",
        "model-b",
        "baseline:judge_history",
        "baseline:global_base_rate",
    ]
    assert [row["row_type"] for row in records] == [
        "model",
        "model",
        "baseline",
        "baseline",
    ]
    assert [row["rank"] for row in records] == [1, 2, 1, 2]
    assert records[0]["delta_vs_best"] is None
    assert records[1]["delta_vs_best"] is None
    assert records[2]["delta_vs_best"] is None


def test_pareto_frontier_excludes_cost_and_quality_dominated_models() -> None:
    frontier = pareto_frontier_records(
        (
            {"model_id": "model-a", "micro_brier": 0.10, "cost_per_case": 0.030},
            {"model_id": "model-b", "micro_brier": 0.12, "cost_per_case": 0.010},
            {"model_id": "model-c", "micro_brier": 0.20, "cost_per_case": 0.040},
        ),
        objective_fields=("micro_brier", "cost_per_case"),
    )

    assert [row["model_id"] for row in frontier] == ["model-a", "model-b"]


def test_pareto_frontier_ignores_incomplete_or_nonnumeric_objectives() -> None:
    frontier = pareto_frontier_records(
        (
            {"model_id": "model-a", "micro_brier": 0.10, "cost_per_case": 0.020},
            {"model_id": "missing-cost", "micro_brier": 0.08},
            {
                "model_id": "boolean-cost",
                "micro_brier": 0.08,
                "cost_per_case": False,
            },
            {"model_id": "dominated", "micro_brier": 0.12, "cost_per_case": 0.030},
        ),
        objective_fields=("micro_brier", "cost_per_case"),
    )

    assert [row["model_id"] for row in frontier] == ["model-a"]


def test_pareto_frontier_requires_rows_and_objectives() -> None:
    with pytest.raises(ValueError, match="rows must not be empty"):
        pareto_frontier_records(())

    with pytest.raises(ValueError, match="objective_fields must not be empty"):
        pareto_frontier_records(
            ({"model_id": "model-a", "micro_brier": 0.1},), objective_fields=()
        )


def test_pareto_point_records_validate_and_wrap_frontier() -> None:
    records = pareto_records(
        (
            ParetoPoint("model-a", micro_brier=0.10, cost_per_case=0.030),
            ParetoPoint("model-b", micro_brier=0.12, cost_per_case=0.010),
            ParetoPoint("dominated", micro_brier=0.20, cost_per_case=0.040),
        )
    )

    assert [record["model_id"] for record in records] == ["model-a", "model-b"]

    with pytest.raises(ValueError, match="model_id is required"):
        ParetoPoint(" ", micro_brier=0.10)

    with pytest.raises(ValueError, match="micro_brier cannot be negative"):
        ParetoPoint("model-a", micro_brier=-0.01)

    with pytest.raises(ValueError, match="cost_per_case cannot be negative"):
        ParetoPoint("model-a", micro_brier=0.10, cost_per_case=-0.01)


def _summary(model_id: str, *, micro_brier: float, ece: float) -> ScoreSummary:
    return ScoreSummary(
        model_id=model_id,
        case_count=2,
        unit_count=5,
        micro_brier=micro_brier,
        macro_brier=micro_brier + 0.01,
        brier_skill_score=1 - (micro_brier / 0.25),
        log_loss=0.50 + micro_brier,
        ece=ece,
        capped_case_micro_brier=micro_brier + 0.01,
        related_family_capped_micro_brier=micro_brier + 0.02,
        mdl_family_capped_micro_brier=micro_brier + 0.03,
        case_unit_cap=10,
        family_unit_cap=10,
        dominance_threshold=0.40,
        dominance_sensitivity_reports=(),
        invalid_output_rate=0.0,
        refusal_rate=0.0,
        defaulted_prediction_rate=0.0,
        base_rate=0.5,
        base_rate_brier=0.25,
        ece_bins=(
            CalibrationBin(
                bin_index=0,
                lower=0.0,
                upper=0.5,
                unit_count=3,
                mean_probability=0.2,
                observed_rate=0.25,
                absolute_calibration_error=0.05,
            ),
            CalibrationBin(
                bin_index=1,
                lower=0.5,
                upper=1.0,
                unit_count=2,
                mean_probability=0.7,
                observed_rate=0.6,
                absolute_calibration_error=0.1,
            ),
        ),
        unit_scores=(),
    )


def _accounting(
    model_id: str,
    *,
    cost_per_case: float,
    tool_calls: float,
) -> AccountingLeaderboardRow:
    return AccountingLeaderboardRow(
        solver_id=f"solver-{model_id}",
        provider="fixture-provider",
        model_id=model_id,
        model_version_or_snapshot="2026-05-14",
        run_label="full_packet",
        run_count=2,
        case_count=2,
        prediction_unit_count=5,
        mean_tool_calls_per_case=tool_calls,
        median_tool_calls_per_case=tool_calls,
        p95_tool_calls_per_case=tool_calls + 1,
        mean_latency_ms=1000 * tool_calls,
        p95_latency_ms=1200 * tool_calls,
        total_estimated_cost=cost_per_case * 2,
        cost_per_case=cost_per_case,
        cost_per_prediction_unit=(cost_per_case * 2) / 5,
        invalid_output_rate=0.0,
        refusal_rate=0.0,
        content_filter_rate=0.0,
    )


def _inference() -> BootstrapInferenceResult:
    return BootstrapInferenceResult(
        config=BootstrapConfig(replicates=10, seed=1),
        case_ids=("case-1", "case-2"),
        observed_micro_briers={
            "model-a": 0.10,
            "model-b": 0.12,
            "model-c": 0.20,
        },
        pairwise_deltas=(
            PairwiseDelta(
                model_a="model-a",
                model_b="model-b",
                observed_delta=-0.02,
                ci_low=-0.05,
                ci_high=0.01,
                probability_a_better=0.9,
            ),
            PairwiseDelta(
                model_a="model-a",
                model_b="model-c",
                observed_delta=-0.10,
                ci_low=-0.13,
                ci_high=-0.06,
                probability_a_better=1.0,
            ),
            PairwiseDelta(
                model_a="model-b",
                model_b="model-c",
                observed_delta=-0.08,
                ci_low=-0.11,
                ci_high=-0.04,
                probability_a_better=1.0,
            ),
        ),
        ranks=(
            ModelRank(
                model_id="model-a",
                observed_micro_brier=0.10,
                rank=1,
                tier=1,
            ),
            ModelRank(
                model_id="model-b",
                observed_micro_brier=0.12,
                rank=2,
                tier=1,
            ),
            ModelRank(
                model_id="model-c",
                observed_micro_brier=0.20,
                rank=3,
                tier=2,
            ),
        ),
        replicates=(),
    )
