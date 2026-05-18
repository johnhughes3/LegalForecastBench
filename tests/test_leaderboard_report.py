from __future__ import annotations

import json
from datetime import UTC, datetime

from legalforecast.evals.accounting import ModelRunAccountingRecord
from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    ModelScoreInput,
    paired_clustered_bootstrap,
)
from legalforecast.evals.output_parser import parse_model_output
from legalforecast.evals.scorers import ScoringCase, score_cases
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.reporting.calibration import calibration_markdown
from legalforecast.reporting.leaderboard import (
    build_benchmark_leaderboard_report,
    summarize_accounting_leaderboard,
)
from legalforecast.reporting.pareto import pareto_frontier_records


def test_benchmark_leaderboard_report_combines_headline_metrics() -> None:
    model_a = _summary("model-a", 0.9, 0.1)
    model_b = _summary("model-b", 0.6, 0.4)
    inference = paired_clustered_bootstrap(
        (
            ModelScoreInput("model-a", model_a.unit_scores),
            ModelScoreInput("model-b", model_b.unit_scores),
        ),
        config=BootstrapConfig(replicates=20, seed=7),
    )
    accounting_rows = summarize_accounting_leaderboard(
        tuple(record.to_record() for record in _accounting_records())
    )

    report = build_benchmark_leaderboard_report(
        (model_b, model_a),
        accounting_rows=accounting_rows,
        inference=inference,
        title="Fixture Leaderboard",
    )
    record = report.to_record()

    assert [row.model_id for row in report.rows] == ["model-a", "model-b"]
    assert report.rows[0].rank == 1
    assert report.rows[0].rank_tier == 1
    assert report.rows[0].cost_per_case == 0.05
    assert report.rows[1].delta_vs_best is not None
    assert record["rows"][0]["micro_brier"] == model_a.micro_brier
    assert record["pairwise_deltas"]
    assert record["calibration_tables"]
    assert {point["model_id"] for point in record["pareto_accuracy_cost"]} == {
        "model-a",
        "model-b",
    }
    json.dumps(record)


def test_benchmark_report_renders_csv_markdown_and_html() -> None:
    report = build_benchmark_leaderboard_report(
        (_summary("model-a", 0.9, 0.1),),
        accounting_rows=summarize_accounting_leaderboard(
            tuple(record.to_record() for record in _accounting_records()[:1])
        ),
        title="Fixture Leaderboard",
    )

    csv_output = report.to_csv()
    markdown = report.to_markdown()
    html = report.to_html()

    assert "micro_brier" in csv_output
    assert "# Fixture Leaderboard" in markdown
    assert "model-a" in markdown
    assert "<table>" in html
    assert "model-a" in html


def test_calibration_markdown_and_pareto_helpers_are_report_ready() -> None:
    summary = _summary("model-a", 0.9, 0.1)
    frontier = pareto_frontier_records(
        (
            {"model_id": "model-a", "micro_brier": 0.1, "cost_per_case": 0.05},
            {"model_id": "model-b", "micro_brier": 0.2, "cost_per_case": 0.10},
            {"model_id": "model-c", "micro_brier": 0.3, "cost_per_case": 0.01},
        ),
        objective_fields=("micro_brier", "cost_per_case"),
    )

    assert "Mean p" in calibration_markdown(summary)
    assert [point["model_id"] for point in frontier] == ["model-a", "model-c"]


def _summary(model_id: str, dismissed_probability: float, survive_probability: float):
    return score_cases(
        (
            ScoringCase(
                case_id="case-1",
                model_id=model_id,
                parsed_output=parse_model_output(
                    json.dumps(
                        {
                            "case_assessment": "Fixture.",
                            "predictions": [
                                {
                                    "unit_id": "unit-dismissed",
                                    "probability_fully_dismissed": (
                                        dismissed_probability
                                    ),
                                },
                                {
                                    "unit_id": "unit-survives",
                                    "probability_fully_dismissed": (
                                        survive_probability
                                    ),
                                },
                            ],
                        }
                    ),
                    required_unit_ids=("unit-dismissed", "unit-survives"),
                ),
                outcome_labels=(
                    _label("unit-dismissed", True),
                    _label("unit-survives", False),
                ),
            ),
        ),
        base_rate=0.5,
    )


def _label(unit_id: str, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.97,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )


def _accounting_records() -> tuple[ModelRunAccountingRecord, ...]:
    timestamp = datetime(2026, 5, 14, tzinfo=UTC)
    return (
        _accounting_record(
            model_id="model-a",
            timestamp=timestamp,
            estimated_cost=0.05,
            tool_call_count=2,
            latency_ms=100,
        ),
        _accounting_record(
            model_id="model-b",
            timestamp=timestamp,
            estimated_cost=0.01,
            tool_call_count=0,
            latency_ms=80,
        ),
    )


def _accounting_record(
    *,
    model_id: str,
    timestamp: datetime,
    estimated_cost: float,
    tool_call_count: int,
    latency_ms: float,
) -> ModelRunAccountingRecord:
    return ModelRunAccountingRecord(
        sample_id=f"sample-{model_id}",
        candidate_id=f"candidate-{model_id}",
        case_id=f"case-{model_id}",
        solver_id=f"provider:{model_id}",
        solver_kind="configured_model_stub",
        provider="provider",
        model_id=model_id,
        model_version_or_snapshot="2026-05-14",
        evaluation_timestamp=timestamp,
        raw_output_sha256="sha256:" + model_id.replace("-", "") + ("0" * 57),
        prediction_unit_count=2,
        request_count=1,
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        tool_call_count=tool_call_count,
        allowed_tool_call_count=tool_call_count,
        denied_tool_call_count=0,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        cost_per_case=estimated_cost,
        cost_per_prediction_unit=estimated_cost / 2,
        invalid_output=False,
        refusal=False,
        content_filter=False,
        invalid_output_reason=None,
        run_label="full_packet",
        ablation="full_packet",
    )
