"""Leaderboard and report helpers for benchmark outputs."""

from __future__ import annotations

import csv
import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from math import ceil
from statistics import median
from typing import Any

from legalforecast._record_validation import (
    optional_number as _optional_number,
)
from legalforecast._record_validation import (
    optional_str as _optional_str,
)
from legalforecast._record_validation import (
    require_non_empty as _require_non_empty,
)
from legalforecast._record_validation import (
    require_non_negative_float as _require_non_negative_float,
)
from legalforecast._record_validation import (
    require_positive as _require_positive,
)
from legalforecast._record_validation import (
    required_bool as _required_bool,
)
from legalforecast._record_validation import (
    required_float as _required_float,
)
from legalforecast._record_validation import (
    required_int as _required_int,
)
from legalforecast._record_validation import (
    required_str as _required_str,
)
from legalforecast.evals.bootstrap import BootstrapInferenceResult, PairwiseDelta
from legalforecast.evals.scorers import ScoreSummary
from legalforecast.reporting.calibration import calibration_records, calibration_svg
from legalforecast.reporting.pareto import pareto_frontier_records

OBSERVED_RANK_TIER_METHOD = "observed_micro_brier_order"
OBSERVED_RANK_TIER_CAVEAT = (
    "No bootstrap inference was supplied; rank tiers equal observed micro-Brier "
    "rank order only."
)


@dataclass(frozen=True, slots=True)
class AccountingLeaderboardRow:
    """Cost, latency, and tool-use rollup for one model/run label."""

    solver_id: str
    provider: str
    model_id: str
    model_version_or_snapshot: str
    run_label: str | None
    run_count: int
    case_count: int
    prediction_unit_count: int
    mean_tool_calls_per_case: float
    median_tool_calls_per_case: float
    p95_tool_calls_per_case: float
    mean_latency_ms: float
    p95_latency_ms: float
    total_estimated_cost: float
    cost_per_case: float
    cost_per_prediction_unit: float
    invalid_output_rate: float
    refusal_rate: float
    content_filter_rate: float

    def __post_init__(self) -> None:
        for field_name in (
            "solver_id",
            "provider",
            "model_id",
            "model_version_or_snapshot",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.run_label is not None:
            _require_non_empty(self.run_label, "run_label")
        _require_positive(self.run_count, "run_count")
        _require_positive(self.case_count, "case_count")
        _require_positive(self.prediction_unit_count, "prediction_unit_count")
        for field_name in (
            "mean_tool_calls_per_case",
            "median_tool_calls_per_case",
            "p95_tool_calls_per_case",
            "mean_latency_ms",
            "p95_latency_ms",
            "total_estimated_cost",
            "cost_per_case",
            "cost_per_prediction_unit",
            "invalid_output_rate",
            "refusal_rate",
            "content_filter_rate",
        ):
            _require_non_negative_float(getattr(self, field_name), field_name)
        for field_name in (
            "invalid_output_rate",
            "refusal_rate",
            "content_filter_rate",
        ):
            _require_at_most_one(getattr(self, field_name), field_name)

    def to_record(self) -> dict[str, Any]:
        return {
            "solver_id": self.solver_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "model_version_or_snapshot": self.model_version_or_snapshot,
            "run_label": self.run_label,
            "run_count": self.run_count,
            "case_count": self.case_count,
            "prediction_unit_count": self.prediction_unit_count,
            "mean_tool_calls_per_case": self.mean_tool_calls_per_case,
            "median_tool_calls_per_case": self.median_tool_calls_per_case,
            "p95_tool_calls_per_case": self.p95_tool_calls_per_case,
            "mean_latency_ms": self.mean_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "total_estimated_cost": self.total_estimated_cost,
            "cost_per_case": self.cost_per_case,
            "cost_per_prediction_unit": self.cost_per_prediction_unit,
            "invalid_output_rate": self.invalid_output_rate,
            "refusal_rate": self.refusal_rate,
            "content_filter_rate": self.content_filter_rate,
        }


def summarize_accounting_leaderboard(
    accounting_records: Sequence[Mapping[str, Any]],
) -> tuple[AccountingLeaderboardRow, ...]:
    """Compute leaderboard-ready cost, latency, and tool-use summaries."""

    if not accounting_records:
        raise ValueError("at least one accounting record is required")

    groups: dict[tuple[str, str, str, str, str | None], list[Mapping[str, Any]]] = {}
    for record in accounting_records:
        key = (
            _required_str(record, "solver_id"),
            _required_str(record, "provider"),
            _required_str(record, "model_id"),
            _required_str(record, "model_version_or_snapshot"),
            _optional_str(record, "run_label"),
        )
        groups.setdefault(key, []).append(record)

    rows: list[AccountingLeaderboardRow] = []
    for (
        _solver_id,
        _provider,
        _model_id,
        _model_version,
        _run_label,
    ), records in sorted(groups.items()):
        tool_calls = [_required_int(record, "tool_call_count") for record in records]
        latencies = [_required_float(record, "latency_ms") for record in records]
        total_cost = sum(
            _required_float(record, "estimated_cost") for record in records
        )
        case_count = len({_required_str(record, "case_id") for record in records})
        prediction_unit_count = sum(
            _required_int(record, "prediction_unit_count") for record in records
        )
        first = records[0]
        rows.append(
            AccountingLeaderboardRow(
                solver_id=_required_str(first, "solver_id"),
                provider=_required_str(first, "provider"),
                model_id=_required_str(first, "model_id"),
                model_version_or_snapshot=_required_str(
                    first,
                    "model_version_or_snapshot",
                ),
                run_label=_optional_str(first, "run_label"),
                run_count=len(records),
                case_count=case_count,
                prediction_unit_count=prediction_unit_count,
                mean_tool_calls_per_case=sum(tool_calls) / len(tool_calls),
                median_tool_calls_per_case=float(median(tool_calls)),
                p95_tool_calls_per_case=float(_nearest_rank_percentile(tool_calls, 95)),
                mean_latency_ms=sum(latencies) / len(latencies),
                p95_latency_ms=_nearest_rank_percentile(latencies, 95),
                total_estimated_cost=total_cost,
                cost_per_case=total_cost / case_count,
                cost_per_prediction_unit=total_cost / prediction_unit_count,
                invalid_output_rate=_rate(records, "invalid_output"),
                refusal_rate=_rate(records, "refusal"),
                content_filter_rate=_rate(records, "content_filter"),
            )
        )
    return tuple(rows)


def accounting_leaderboard_records(
    accounting_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return JSON-serializable leaderboard accounting rows."""

    return [
        row.to_record() for row in summarize_accounting_leaderboard(accounting_records)
    ]


@dataclass(frozen=True, slots=True)
class HeadlineLeaderboardRow:
    """One report row combining scoring, inference, and operational metrics."""

    rank: int
    rank_tier: int
    model_id: str
    micro_brier: float
    brier_skill_score: float
    log_loss: float
    ece: float
    macro_brier: float
    capped_case_micro_brier: float
    related_family_capped_micro_brier: float
    mdl_family_capped_micro_brier: float
    invalid_output_rate: float
    refusal_rate: float
    defaulted_prediction_rate: float
    cost_per_case: float | None = None
    cost_per_prediction_unit: float | None = None
    mean_tool_calls_per_case: float | None = None
    p95_tool_calls_per_case: float | None = None
    mean_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    delta_vs_best: float | None = None
    delta_vs_best_ci_low: float | None = None
    delta_vs_best_ci_high: float | None = None
    repeat_sample_case_count: int = 0
    repeat_sample_run_count: int = 0
    within_model_micro_brier_stddev: float | None = None
    brier_skill_score_reference_model_id: str | None = None
    brier_skill_score_over_reference: float | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "rank_tier": self.rank_tier,
            "model_id": self.model_id,
            "micro_brier": self.micro_brier,
            "brier_skill_score": self.brier_skill_score,
            "brier_skill_score_reference_model_id": (
                self.brier_skill_score_reference_model_id
            ),
            "brier_skill_score_over_reference": (self.brier_skill_score_over_reference),
            "log_loss": self.log_loss,
            "ece": self.ece,
            "macro_brier": self.macro_brier,
            "capped_case_micro_brier": self.capped_case_micro_brier,
            "related_family_capped_micro_brier": (
                self.related_family_capped_micro_brier
            ),
            "mdl_family_capped_micro_brier": self.mdl_family_capped_micro_brier,
            "invalid_output_rate": self.invalid_output_rate,
            "refusal_rate": self.refusal_rate,
            "defaulted_prediction_rate": self.defaulted_prediction_rate,
            "cost_per_case": self.cost_per_case,
            "cost_per_prediction_unit": self.cost_per_prediction_unit,
            "mean_tool_calls_per_case": self.mean_tool_calls_per_case,
            "p95_tool_calls_per_case": self.p95_tool_calls_per_case,
            "mean_latency_ms": self.mean_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "delta_vs_best": self.delta_vs_best,
            "delta_vs_best_ci_low": self.delta_vs_best_ci_low,
            "delta_vs_best_ci_high": self.delta_vs_best_ci_high,
            "repeat_sample_case_count": self.repeat_sample_case_count,
            "repeat_sample_run_count": self.repeat_sample_run_count,
            "within_model_micro_brier_stddev": self.within_model_micro_brier_stddev,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkLeaderboardReport:
    """Complete machine- and human-readable leaderboard report."""

    title: str
    rows: tuple[HeadlineLeaderboardRow, ...]
    rank_tier_method: str = OBSERVED_RANK_TIER_METHOD
    rank_tier_caveat: str = OBSERVED_RANK_TIER_CAVEAT
    pairwise_deltas: tuple[PairwiseDelta, ...] = ()
    calibration_tables: tuple[Mapping[str, Any], ...] = ()
    calibration_plot_svg: str = ""
    pareto_accuracy_cost: tuple[Mapping[str, Any], ...] = ()
    pareto_accuracy_tool_calls: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.title, "title")
        if not self.rows:
            raise ValueError("leaderboard report requires at least one row")

    def to_record(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "rank_tier_method": self.rank_tier_method,
            "rank_tier_caveat": self.rank_tier_caveat,
            "rows": [row.to_record() for row in self.rows],
            "pairwise_deltas": [delta.to_record() for delta in self.pairwise_deltas],
            "calibration_tables": [dict(table) for table in self.calibration_tables],
            "calibration_plot_svg": self.calibration_plot_svg,
            "pareto_accuracy_cost": [
                dict(point) for point in self.pareto_accuracy_cost
            ],
            "pareto_accuracy_tool_calls": [
                dict(point) for point in self.pareto_accuracy_tool_calls
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, sort_keys=True)

    def to_csv(self) -> str:
        output = StringIO()
        fieldnames = list(self.rows[0].to_record())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row.to_record())
        return output.getvalue()

    def to_markdown(self) -> str:
        headers = (
            "Rank",
            "Tier",
            "Model",
            "Micro-Brier",
            "BSS",
            "BSS vs Ref",
            "Log loss",
            "ECE",
            "Cost/case",
            "Tool calls/case",
            "Repeat stddev",
            "Invalid %",
        )
        lines = [
            f"# {self.title}",
            "",
            "| " + " | ".join(headers) + " |",
            "| "
            + " | ".join(
                (
                    "---:",
                    "---:",
                    "---",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                    "---:",
                )
            )
            + " |",
        ]
        for row in self.rows:
            lines.append(
                "| "
                f"{row.rank} | "
                f"{row.rank_tier} | "
                f"{row.model_id} | "
                f"{row.micro_brier:.4f} | "
                f"{row.brier_skill_score:.4f} | "
                f"{_fmt_optional(row.brier_skill_score_over_reference)} | "
                f"{row.log_loss:.4f} | "
                f"{row.ece:.4f} | "
                f"{_fmt_optional(row.cost_per_case)} | "
                f"{_fmt_optional(row.mean_tool_calls_per_case)} | "
                f"{_fmt_optional(row.within_model_micro_brier_stddev)} | "
                f"{row.invalid_output_rate:.2%} |"
            )
        if self.rank_tier_caveat:
            lines.extend(["", f"_Rank tier note: {self.rank_tier_caveat}_"])
        if self.pairwise_deltas:
            lines.extend(["", "## Pairwise CIs", ""])
            for delta in self.pairwise_deltas:
                lines.append(
                    "- "
                    f"{delta.model_a} - {delta.model_b}: "
                    f"{delta.observed_delta:.4f} "
                    f"[{delta.ci_low:.4f}, {delta.ci_high:.4f}]"
                )
        if self.pareto_accuracy_cost:
            lines.extend(["", "## Pareto Frontier", ""])
            for point in self.pareto_accuracy_cost:
                lines.append(
                    "- "
                    f"{point['model_id']}: micro-Brier "
                    f"{float(point['micro_brier']):.4f}, cost/case "
                    f"{_fmt_optional(_optional_number(point, 'cost_per_case'))}"
                )
        return "\n".join(lines)

    def to_html(self) -> str:
        rows = "\n".join(
            "<tr>"
            f"<td>{row.rank}</td>"
            f"<td>{row.rank_tier}</td>"
            f"<td>{html.escape(row.model_id)}</td>"
            f"<td>{row.micro_brier:.4f}</td>"
            f"<td>{row.brier_skill_score:.4f}</td>"
            f"<td>{_fmt_optional(row.brier_skill_score_over_reference)}</td>"
            f"<td>{row.log_loss:.4f}</td>"
            f"<td>{row.ece:.4f}</td>"
            f"<td>{_fmt_optional(row.cost_per_case)}</td>"
            f"<td>{_fmt_optional(row.mean_tool_calls_per_case)}</td>"
            f"<td>{_fmt_optional(row.within_model_micro_brier_stddev)}</td>"
            f"<td>{row.invalid_output_rate:.2%}</td>"
            "</tr>"
            for row in self.rows
        )
        pareto_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(point['model_id']))}</td>"
            f"<td>{float(point['micro_brier']):.4f}</td>"
            f"<td>{_fmt_optional(_optional_number(point, 'cost_per_case'))}</td>"
            "</tr>"
            for point in self.pareto_accuracy_cost
        )
        return (
            "<!doctype html><html><body>"
            f"<h1>{html.escape(self.title)}</h1>"
            "<table>"
            "<thead><tr>"
            "<th>Rank</th><th>Tier</th><th>Model</th><th>Micro-Brier</th>"
            "<th>BSS</th><th>BSS vs Ref</th><th>Log loss</th><th>ECE</th>"
            "<th>Cost/case</th>"
            "<th>Tool calls/case</th><th>Repeat stddev</th><th>Invalid %</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table>"
            "<p><strong>Rank tier note:</strong> "
            f"{html.escape(self.rank_tier_caveat)}</p>"
            "<h2>Calibration</h2>"
            f"{self.calibration_plot_svg}"
            "<h2>Pareto Frontier</h2>"
            "<table><thead><tr><th>Model</th><th>Micro-Brier</th>"
            "<th>Cost/case</th></tr></thead>"
            f"<tbody>{pareto_rows}</tbody></table>"
            "</body></html>"
        )


def build_benchmark_leaderboard_report(
    score_summaries: Sequence[ScoreSummary],
    *,
    accounting_rows: Sequence[AccountingLeaderboardRow] = (),
    inference: BootstrapInferenceResult | None = None,
    repeat_variance_rows: Sequence[Mapping[str, Any]] = (),
    title: str = "LegalForecast-MTD Leaderboard",
) -> BenchmarkLeaderboardReport:
    """Join scoring, inference, calibration, Pareto, and accounting outputs."""

    if not score_summaries:
        raise ValueError("score_summaries must not be empty")
    accounting_by_model = {row.model_id: row for row in accounting_rows}
    repeat_variance_by_model = {
        _required_str(row, "model_id"): row for row in repeat_variance_rows
    }
    ranks = _rank_lookup(score_summaries, inference)
    sorted_summaries = sorted(
        score_summaries,
        key=lambda summary: (ranks[summary.model_id].rank, summary.model_id),
    )
    best_model_id = sorted_summaries[0].model_id
    reference_summary = _baseline_reference_summary(score_summaries)
    rows = tuple(
        _headline_row(
            summary,
            rank=ranks[summary.model_id].rank,
            rank_tier=ranks[summary.model_id].tier,
            accounting=accounting_by_model.get(summary.model_id),
            repeat_variance=repeat_variance_by_model.get(summary.model_id),
            best_model_id=best_model_id,
            reference_summary=reference_summary,
            inference=inference,
        )
        for summary in sorted_summaries
    )
    row_records = tuple(row.to_record() for row in rows)
    return BenchmarkLeaderboardReport(
        title=title,
        rows=rows,
        rank_tier_method=(
            inference.rank_tier_method
            if inference is not None
            else OBSERVED_RANK_TIER_METHOD
        ),
        rank_tier_caveat=(
            inference.rank_tier_caveat
            if inference is not None
            else OBSERVED_RANK_TIER_CAVEAT
        ),
        pairwise_deltas=inference.pairwise_deltas if inference is not None else (),
        calibration_tables=tuple(calibration_records(tuple(score_summaries))),
        calibration_plot_svg=calibration_svg(tuple(score_summaries)),
        pareto_accuracy_cost=tuple(
            pareto_frontier_records(
                row_records,
                objective_fields=("micro_brier", "cost_per_case"),
            )
        ),
        pareto_accuracy_tool_calls=tuple(
            pareto_frontier_records(
                row_records,
                objective_fields=("micro_brier", "mean_tool_calls_per_case"),
            )
        ),
    )


def benchmark_leaderboard_records(
    score_summaries: Sequence[ScoreSummary],
    *,
    accounting_rows: Sequence[AccountingLeaderboardRow] = (),
    inference: BootstrapInferenceResult | None = None,
    repeat_variance_rows: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Return leaderboard rows as JSON-serializable records."""

    report = build_benchmark_leaderboard_report(
        score_summaries,
        accounting_rows=accounting_rows,
        inference=inference,
        repeat_variance_rows=repeat_variance_rows,
    )
    return [row.to_record() for row in report.rows]


def _nearest_rank_percentile(values: Sequence[int | float], percentile: int) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if percentile <= 0 or percentile > 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(float(value) for value in values)
    index = ceil((percentile / 100) * len(ordered)) - 1
    return ordered[index]


@dataclass(frozen=True, slots=True)
class _RankFacts:
    rank: int
    tier: int


def _rank_lookup(
    summaries: Sequence[ScoreSummary],
    inference: BootstrapInferenceResult | None,
) -> dict[str, _RankFacts]:
    if inference is not None:
        return {
            rank.model_id: _RankFacts(rank=rank.rank, tier=rank.tier)
            for rank in inference.ranks
        }
    sorted_summaries = sorted(
        summaries,
        key=lambda summary: (summary.micro_brier, summary.model_id),
    )
    return {
        summary.model_id: _RankFacts(rank=index + 1, tier=index + 1)
        for index, summary in enumerate(sorted_summaries)
    }


def _headline_row(
    summary: ScoreSummary,
    *,
    rank: int,
    rank_tier: int,
    accounting: AccountingLeaderboardRow | None,
    repeat_variance: Mapping[str, Any] | None,
    best_model_id: str,
    reference_summary: ScoreSummary | None,
    inference: BootstrapInferenceResult | None,
) -> HeadlineLeaderboardRow:
    delta = _delta_against_best(
        summary.model_id,
        best_model_id=best_model_id,
        inference=inference,
    )
    return HeadlineLeaderboardRow(
        rank=rank,
        rank_tier=rank_tier,
        model_id=summary.model_id,
        micro_brier=summary.micro_brier,
        brier_skill_score=summary.brier_skill_score,
        log_loss=summary.log_loss,
        ece=summary.ece,
        macro_brier=summary.macro_brier,
        capped_case_micro_brier=summary.capped_case_micro_brier,
        related_family_capped_micro_brier=(summary.related_family_capped_micro_brier),
        mdl_family_capped_micro_brier=summary.mdl_family_capped_micro_brier,
        invalid_output_rate=summary.invalid_output_rate,
        refusal_rate=summary.refusal_rate,
        defaulted_prediction_rate=summary.defaulted_prediction_rate,
        cost_per_case=accounting.cost_per_case if accounting is not None else None,
        cost_per_prediction_unit=(
            accounting.cost_per_prediction_unit if accounting is not None else None
        ),
        mean_tool_calls_per_case=(
            accounting.mean_tool_calls_per_case if accounting is not None else None
        ),
        p95_tool_calls_per_case=(
            accounting.p95_tool_calls_per_case if accounting is not None else None
        ),
        mean_latency_ms=accounting.mean_latency_ms if accounting is not None else None,
        p95_latency_ms=accounting.p95_latency_ms if accounting is not None else None,
        delta_vs_best=delta[0],
        delta_vs_best_ci_low=delta[1],
        delta_vs_best_ci_high=delta[2],
        repeat_sample_case_count=(
            _required_int(repeat_variance, "repeated_case_count")
            if repeat_variance is not None
            else 0
        ),
        repeat_sample_run_count=(
            _required_int(repeat_variance, "repeat_run_count")
            if repeat_variance is not None
            else 0
        ),
        within_model_micro_brier_stddev=(
            _optional_number(repeat_variance, "root_mean_within_case_variance")
            if repeat_variance is not None
            else None
        ),
        brier_skill_score_reference_model_id=(
            reference_summary.model_id if reference_summary is not None else None
        ),
        brier_skill_score_over_reference=_skill_over_reference(
            summary,
            reference_summary,
        ),
    )


def _baseline_reference_summary(
    summaries: Sequence[ScoreSummary],
) -> ScoreSummary | None:
    by_model = {summary.model_id: summary for summary in summaries}
    for model_id in (
        "judge_history",
        "metadata_only",
        "court_nos_motion_base_rate",
        "global_base_rate",
    ):
        if model_id in by_model:
            return by_model[model_id]
    return None


def _skill_over_reference(
    summary: ScoreSummary,
    reference_summary: ScoreSummary | None,
) -> float | None:
    if reference_summary is None or reference_summary.micro_brier == 0:
        return None
    return 1 - (summary.micro_brier / reference_summary.micro_brier)


def _delta_against_best(
    model_id: str,
    *,
    best_model_id: str,
    inference: BootstrapInferenceResult | None,
) -> tuple[float | None, float | None, float | None]:
    if model_id == best_model_id or inference is None:
        return (None, None, None)
    for delta in inference.pairwise_deltas:
        if delta.model_a == model_id and delta.model_b == best_model_id:
            return (delta.observed_delta, delta.ci_low, delta.ci_high)
        if delta.model_a == best_model_id and delta.model_b == model_id:
            return (-delta.observed_delta, -delta.ci_high, -delta.ci_low)
    return (None, None, None)


def _fmt_optional(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def _rate(records: Sequence[Mapping[str, Any]], field_name: str) -> float:
    positives = sum(1 for record in records if _required_bool(record, field_name))
    return positives / len(records)


def _require_at_most_one(value: float, field_name: str) -> None:
    if value > 1:
        raise ValueError(f"{field_name} cannot exceed 1")
