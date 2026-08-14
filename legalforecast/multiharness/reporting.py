"""Reporting helpers for community multi-harness comparisons."""

from __future__ import annotations

import csv
import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Any

from legalforecast.publication.metric_propagation import MetricTrace, PublishedMetrics
from legalforecast.reporting.contamination_tiers import (
    ContaminationTier,
    preliminary_caveat_if_needed,
    reported_model_label,
)


@dataclass(frozen=True, slots=True)
class CommunityComparisonRow:
    """One public community comparison row."""

    row_id: str
    row_type: str
    submission_ids: tuple[str, ...]
    shard_ids: tuple[str, ...]
    family: str
    scoring_mode: str
    selection_sha256: str
    selection_label: str
    suite_version: str
    adapter_id: str
    adapter_version: str
    model_key: str
    conformance_status: str
    task_count: int
    coverage_percentage: float
    status_counts: Mapping[str, int]
    contributor_credit: tuple[Mapping[str, Any], ...]
    artifact_ids: tuple[str, ...]
    published_metrics: PublishedMetrics | None = None

    def to_record(self) -> dict[str, Any]:
        record = {
            "row_id": self.row_id,
            "row_type": self.row_type,
            "submission_ids": list(self.submission_ids),
            "shard_ids": list(self.shard_ids),
            "family": self.family,
            "scoring_mode": self.scoring_mode,
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "suite_version": self.suite_version,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_key": self.model_key,
            "conformance_status": self.conformance_status,
            "task_count": self.task_count,
            "coverage_percentage": self.coverage_percentage,
            "status_counts": dict(sorted(self.status_counts.items())),
            "contributor_credit": [dict(item) for item in self.contributor_credit],
            "artifact_ids": list(self.artifact_ids),
        }
        if self.published_metrics is not None:
            record["published_metrics"] = self.published_metrics.to_record()
        return record


def render_community_comparison_json(rows: Sequence[CommunityComparisonRow]) -> str:
    """Render comparison rows as stable JSON text."""

    return json.dumps(
        {
            "schema_version": "legalforecast.multiharness.community_report.v1",
            "rows": [row.to_record() for row in rows],
        },
        indent=2,
        sort_keys=True,
    )


def render_community_comparison_csv(rows: Sequence[CommunityComparisonRow]) -> str:
    """Render comparison rows as CSV text."""

    output = StringIO()
    fieldnames = [
        "row_id",
        "row_type",
        "family",
        "scoring_mode",
        "selection_label",
        "adapter_id",
        "adapter_version",
        "model_key",
        "conformance_status",
        "task_count",
        "coverage_percentage",
        "submission_ids",
        "shard_ids",
    ]
    if any(row.published_metrics is not None for row in rows):
        fieldnames[11:11] = [
            "score_value",
            "cost_usd",
            "token_total",
            "wall_elapsed_ms",
            "attempt_count",
            "failure_count",
        ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        record = row.to_record()
        metrics = row.published_metrics
        writer.writerow(
            {field: _csv_cell(record, field, metrics) for field in fieldnames}
        )
    return output.getvalue()


def render_community_comparison_markdown(
    rows: Sequence[CommunityComparisonRow],
    *,
    contamination_tiers: Mapping[str, ContaminationTier] | None = None,
) -> str:
    """Render comparison rows as a plain Markdown report."""

    lines = [
        "# LegalForecastBench Community Harness Comparisons",
        "",
        (
            "Community results are non-official. LegalForecastBench/LFB rows use "
            "forecast scoring such as Brier-style metrics; Harvey LAB rows use "
            "rubric/native task criteria. Compatible composites are grouped by "
            "family, scoring mode, and suite version and are not ranked across "
            "incompatible metrics."
        ),
    ]
    include_metrics = any(row.published_metrics is not None for row in rows)
    header = (
        (
            "| Row | Type | Model | Adapter | Tasks | Coverage | Score | Cost | "
            "Tokens | Time | Attempts | Failures | Conformance |"
        )
        if include_metrics
        else "| Row | Type | Model | Adapter | Tasks | Coverage | Conformance |"
    )
    divider = (
        (
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | --- |"
        )
        if include_metrics
        else "| --- | --- | --- | --- | ---: | ---: | --- |"
    )
    for family, scoring_mode in _family_sections(rows):
        title = _section_title(family, scoring_mode)
        lines.extend(["", f"## {title}", "", header, divider])
        for row in rows:
            if row.family != family or row.scoring_mode != scoring_mode:
                continue
            lines.append(_markdown_row(row, include_metrics, contamination_tiers))
    caveat = preliminary_caveat_if_needed(contamination_tiers)
    if caveat is not None:
        lines.extend(["", caveat])
    return "\n".join(lines) + "\n"


def render_community_comparison_html(
    rows: Sequence[CommunityComparisonRow],
    *,
    contamination_tiers: Mapping[str, ContaminationTier] | None = None,
) -> str:
    """Render comparison rows as a simple static HTML report."""

    include_metrics = any(row.published_metrics is not None for row in rows)
    sections: list[str] = []
    for family, scoring_mode in _family_sections(rows):
        section_rows = "\n".join(
            _html_row(row, include_metrics, contamination_tiers)
            for row in rows
            if row.family == family and row.scoring_mode == scoring_mode
        )
        metric_headers = (
            "<th>Score</th><th>Cost</th><th>Tokens</th><th>Time</th>"
            "<th>Attempts</th><th>Failures</th>"
            if include_metrics
            else ""
        )
        sections.append(
            "<section>"
            f"<h2>{html.escape(_section_title(family, scoring_mode))}</h2>"
            "<table><thead><tr>"
            "<th>Row</th><th>Type</th><th>Model</th><th>Adapter</th>"
            "<th>Tasks</th><th>Coverage</th>"
            f"{metric_headers}"
            "<th>Conformance</th>"
            "</tr></thead>"
            f"<tbody>{section_rows}</tbody></table>"
            "</section>"
        )
    caveat = preliminary_caveat_if_needed(contamination_tiers)
    caveat_html = (
        f"<p>{html.escape(caveat, quote=False)}</p>" if caveat is not None else ""
    )
    return (
        "<!doctype html><html><body>"
        "<h1>LegalForecastBench Community Harness Comparisons</h1>"
        "<p>Community results are non-official. Compatible composites are grouped "
        "by family, scoring mode, and suite version.</p>"
        f"{''.join(sections)}{caveat_html}"
        "</body></html>"
    )


def _family_sections(
    rows: Sequence[CommunityComparisonRow],
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted({(row.family, row.scoring_mode) for row in rows}))


def _csv_cell(
    record: Mapping[str, Any],
    field: str,
    metrics: PublishedMetrics | None,
) -> Any:
    if field in {"submission_ids", "shard_ids"}:
        return ";".join(record[field])
    if metrics is None:
        return record[field]
    metric_values = {
        "score_value": metrics.score_value,
        "cost_usd": metrics.cost_usd,
        "token_total": metrics.token_total,
        "wall_elapsed_ms": metrics.wall_elapsed_ms,
        "attempt_count": metrics.attempt_count,
        "failure_count": metrics.failure_count,
    }
    if field in metric_values:
        value = metric_values[field]
        return "" if value is None else value
    return record[field]


def _markdown_row(
    row: CommunityComparisonRow,
    include_metrics: bool,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> str:
    cells = [
        row.row_id,
        row.row_type,
        reported_model_label(row.model_key, contamination_tiers),
        f"{row.adapter_id}@{row.adapter_version}",
        str(row.task_count),
        f"{row.coverage_percentage:.1f}%",
    ]
    if include_metrics:
        metrics = row.published_metrics
        cells.extend(
            [
                _display_number(None if metrics is None else metrics.score_value),
                _display_number(None if metrics is None else metrics.cost_usd),
                _display_number(None if metrics is None else metrics.token_total),
                _display_number(None if metrics is None else metrics.wall_elapsed_ms),
                _display_number(None if metrics is None else metrics.attempt_count),
                _display_number(None if metrics is None else metrics.failure_count),
            ]
        )
    cells.append(row.conformance_status)
    return "| " + " | ".join(cells) + " |"


def _html_row(
    row: CommunityComparisonRow,
    include_metrics: bool,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> str:
    metric_cells = ""
    if include_metrics:
        metrics = row.published_metrics
        traces = () if metrics is None else metrics.traces
        metric_cells = "".join(
            _traced_cell(metrics, field_name, traces)
            for field_name in (
                "score_value",
                "cost_usd",
                "token_total",
                "wall_elapsed_ms",
                "attempt_count",
                "failure_count",
            )
        )
    return (
        "<tr>"
        f"<td>{html.escape(row.row_id)}</td>"
        f"<td>{html.escape(row.row_type)}</td>"
        "<td>"
        f"{html.escape(reported_model_label(row.model_key, contamination_tiers))}"
        "</td>"
        f"<td>{html.escape(row.adapter_id)}@{html.escape(row.adapter_version)}</td>"
        f"<td>{row.task_count}</td>"
        f"<td>{row.coverage_percentage:.1f}%</td>"
        f"{metric_cells}"
        f"<td>{html.escape(row.conformance_status)}</td>"
        "</tr>"
    )


def _traced_cell(
    metrics: PublishedMetrics | None,
    field_name: str,
    traces: Sequence[MetricTrace],
) -> str:
    value = None if metrics is None else getattr(metrics, field_name)
    digest = ""
    for trace in traces:
        if trace.field_name == field_name and trace.source_artifact_sha256s:
            digest = trace.source_artifact_sha256s[0]
            break
    displayed = html.escape(_display_number(value))
    if digest:
        return f"<td data-artifact='{html.escape(digest)}'>{displayed}</td>"
    return f"<td>{displayed}</td>"


def _display_number(value: int | float | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _section_title(family: str, scoring_mode: str) -> str:
    if family == "harvey_lab":
        return f"Harvey LAB ({scoring_mode})"
    if family == "legalforecast_mtd":
        return f"LegalForecastBench/LFB ({scoring_mode})"
    return f"{family} ({scoring_mode})"
