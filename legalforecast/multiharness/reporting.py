"""Reporting helpers for community multi-harness comparisons."""

from __future__ import annotations

import csv
import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Any


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

    def to_record(self) -> dict[str, Any]:
        return {
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
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        record = row.to_record()
        writer.writerow(
            {
                field: (
                    ";".join(record[field])
                    if field in {"submission_ids", "shard_ids"}
                    else record[field]
                )
                for field in fieldnames
            }
        )
    return output.getvalue()


def render_community_comparison_markdown(
    rows: Sequence[CommunityComparisonRow],
) -> str:
    """Render comparison rows as a plain Markdown report."""

    lines = [
        "# LegalForecastBench Community Harness Comparisons",
        "",
        (
            "Community results are non-official. LegalForecastBench/LFB rows use "
            "forecast scoring such as Brier-style metrics; Harvey LAB rows use "
            "rubric/native task criteria. Rows are grouped by family, scoring mode, "
            "and selection hash and are not ranked across incompatible metrics."
        ),
    ]
    for family, scoring_mode in _family_sections(rows):
        title = _section_title(family, scoring_mode)
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| Row | Type | Model | Adapter | Tasks | Coverage | Conformance |",
                "| --- | --- | --- | --- | ---: | ---: | --- |",
            ]
        )
        for row in rows:
            if row.family != family or row.scoring_mode != scoring_mode:
                continue
            lines.append(
                "| "
                f"{row.row_id} | "
                f"{row.row_type} | "
                f"{row.model_key} | "
                f"{row.adapter_id}@{row.adapter_version} | "
                f"{row.task_count} | "
                f"{row.coverage_percentage:.1f}% | "
                f"{row.conformance_status} |"
            )
    return "\n".join(lines) + "\n"


def render_community_comparison_html(rows: Sequence[CommunityComparisonRow]) -> str:
    """Render comparison rows as a simple static HTML report."""

    sections: list[str] = []
    for family, scoring_mode in _family_sections(rows):
        section_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(row.row_id)}</td>"
            f"<td>{html.escape(row.row_type)}</td>"
            f"<td>{html.escape(row.model_key)}</td>"
            f"<td>{html.escape(row.adapter_id)}@{html.escape(row.adapter_version)}</td>"
            f"<td>{row.task_count}</td>"
            f"<td>{row.coverage_percentage:.1f}%</td>"
            f"<td>{html.escape(row.conformance_status)}</td>"
            "</tr>"
            for row in rows
            if row.family == family and row.scoring_mode == scoring_mode
        )
        sections.append(
            "<section>"
            f"<h2>{html.escape(_section_title(family, scoring_mode))}</h2>"
            "<table><thead><tr>"
            "<th>Row</th><th>Type</th><th>Model</th><th>Adapter</th>"
            "<th>Tasks</th><th>Coverage</th><th>Conformance</th>"
            "</tr></thead>"
            f"<tbody>{section_rows}</tbody></table>"
            "</section>"
        )
    return (
        "<!doctype html><html><body>"
        "<h1>LegalForecastBench Community Harness Comparisons</h1>"
        "<p>Community results are non-official and are grouped by compatible "
        "family, scoring mode, and selection hash.</p>"
        f"{''.join(sections)}"
        "</body></html>"
    )


def _family_sections(
    rows: Sequence[CommunityComparisonRow],
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted({(row.family, row.scoring_mode) for row in rows}))


def _section_title(family: str, scoring_mode: str) -> str:
    if family == "harvey_lab":
        return f"Harvey LAB ({scoring_mode})"
    if family == "legalforecast_mtd":
        return f"LegalForecastBench/LFB ({scoring_mode})"
    return f"{family} ({scoring_mode})"
