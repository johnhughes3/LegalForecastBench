"""Calibration reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

from legalforecast.evals.scorers import CalibrationBin, ScoreSummary

_SVG_COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e")


@dataclass(frozen=True, slots=True)
class CalibrationTable:
    """Calibration-bin data for one model."""

    model_id: str
    ece: float
    bins: tuple[CalibrationBin, ...]

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if self.ece < 0:
            raise ValueError("ece cannot be negative")
        if not self.bins:
            raise ValueError("bins must not be empty")

    def to_record(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "ece": self.ece,
            "bins": [calibration_bin.to_record() for calibration_bin in self.bins],
        }


def calibration_table(summary: ScoreSummary) -> CalibrationTable:
    """Return calibration table data from a score summary."""

    return CalibrationTable(
        model_id=summary.model_id,
        ece=summary.ece,
        bins=summary.ece_bins,
    )


def calibration_records(summaries: tuple[ScoreSummary, ...]) -> list[dict[str, Any]]:
    """Return JSON-serializable calibration tables for score summaries."""

    return [calibration_table(summary).to_record() for summary in summaries]


def calibration_markdown(summary: ScoreSummary) -> str:
    """Render a compact Markdown calibration table."""

    rows = [
        "| Bin | Range | N | Mean p | Observed | Abs error |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for calibration_bin in summary.ece_bins:
        rows.append(
            "| "
            f"{calibration_bin.bin_index} | "
            f"[{calibration_bin.lower:.2f}, {calibration_bin.upper:.2f}) | "
            f"{calibration_bin.unit_count} | "
            f"{_fmt_optional(calibration_bin.mean_probability)} | "
            f"{_fmt_optional(calibration_bin.observed_rate)} | "
            f"{_fmt_optional(calibration_bin.absolute_calibration_error)} |"
        )
    return "\n".join(rows)


def calibration_curve_records(
    score_summaries: Sequence[ScoreSummary],
) -> list[dict[str, Any]]:
    """Flatten score-summary calibration bins for JSON/CSV reporting."""

    if not score_summaries:
        raise ValueError("score_summaries must not be empty")
    records: list[dict[str, Any]] = []
    for summary in score_summaries:
        for calibration_bin in summary.ece_bins:
            record = calibration_bin.to_record()
            records.append({"model_id": summary.model_id, **record})
    return records


def calibration_svg(
    score_summaries: Sequence[ScoreSummary],
    *,
    width: int = 520,
    height: int = 360,
) -> str:
    """Return a small self-contained SVG reliability plot."""

    if not score_summaries:
        raise ValueError("score_summaries must not be empty")
    if width < 240:
        raise ValueError("width must be at least 240")
    if height < 220:
        raise ValueError("height must be at least 220")

    padding = 48
    plot_width = width - (padding * 2)
    plot_height = height - (padding * 2)

    elements = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'role="img" aria-label="Calibration reliability plot">'
        ),
        '<rect width="100%" height="100%" fill="white" />',
        (
            f'<line class="calibration-diagonal" x1="{padding}" '
            f'y1="{height - padding}" x2="{width - padding}" y2="{padding}" '
            'stroke="#999" stroke-dasharray="5 5" />'
        ),
        (
            f'<line x1="{padding}" y1="{height - padding}" '
            f'x2="{width - padding}" y2="{height - padding}" stroke="#333" />'
        ),
        (
            f'<line x1="{padding}" y1="{padding}" x2="{padding}" '
            f'y2="{height - padding}" stroke="#333" />'
        ),
        (
            f'<text x="{width / 2:.0f}" y="{height - 10}" '
            'text-anchor="middle" font-size="12">Mean predicted probability</text>'
        ),
        (
            f'<text x="16" y="{height / 2:.0f}" transform="rotate(-90 16 '
            f'{height / 2:.0f})" text-anchor="middle" '
            'font-size="12">Observed rate</text>'
        ),
    ]

    for model_index, summary in enumerate(score_summaries):
        color = _SVG_COLORS[model_index % len(_SVG_COLORS)]
        points: list[str] = []
        for calibration_bin in summary.ece_bins:
            if (
                calibration_bin.mean_probability is None
                or calibration_bin.observed_rate is None
            ):
                continue
            x = padding + (calibration_bin.mean_probability * plot_width)
            y = height - padding - (calibration_bin.observed_rate * plot_height)
            points.append(f"{x:.2f},{y:.2f}")
            elements.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" '
                f'fill="{color}"><title>{escape(summary.model_id)} bin '
                f"{calibration_bin.bin_index}</title></circle>"
            )
        if points:
            elements.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="2" />'
            )
            legend_y = padding + (model_index * 18)
            elements.append(
                f'<text x="{width - padding + 8}" y="{legend_y}" '
                f'font-size="12" fill="{color}">{escape(summary.model_id)}</text>'
            )

    elements.append("</svg>")
    return "".join(elements)


def _fmt_optional(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"
