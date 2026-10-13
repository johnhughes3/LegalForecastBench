"""Regenerate the paper's public figure inputs and inline TikZ bodies.

The paper keeps its figures inline so the standalone manuscript has no runtime
dependency on Matplotlib or a private corpus checkout.  This stdlib-only
generator reads the cleaned aggregate in ``../data/empirical.json`` and writes
the four plotted CSVs plus ``figures-inline.tex``.  The coordinate transforms
match the current manuscript bodies; they are deliberately not the historical
Matplotlib/PGFPlots figures in the research workspace.

Use ``--check`` in CI to verify committed generated artifacts.  Add
``--manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex``
to compare every generated TikZ block with the standalone manuscript.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any, cast

FIGURES_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = FIGURES_DIR.parents[3]
DATA_PATH = FIGURES_DIR.parent / "data" / "empirical.json"
INLINE_PATH = FIGURES_DIR / "figures-inline.tex"

SHORT = {
    "gpt-6-sol": "GPT-6 Sol",
    "claude-fable-5-1": "Fable 5.1",
    "grok-4-6": "Grok 4.6",
    "claude-opus-5": "Opus 5",
    "gpt-5-6-sol": "GPT-5.6 Sol",
    "kimi-k3": "Kimi K3",
    "gpt-5-6-luna": "GPT-5.6 Luna",
    "claude-opus-5-5": "Opus 5.5",
    "gpt-6-1-sol": "GPT-6.1 Sol",
    "gpt-6-astra": "GPT-6 Astra",
    "gemini-3-8-flash": "Gemini 3.8 Flash",
    "grok-4-7": "Grok 4.7",
    "claude-sonnet-5": "Sonnet 5",
    "gpt-6-luna": "GPT-6 Luna",
    "muse-wonder-1-0": "Muse Wonder",
    "claude-sonnet-5-5": "Sonnet 5.5",
    "muse-spark-1-3": "Muse Spark 1.3",
    "gemini-3-1-pro-preview": "Gemini 3.1 Pro",
}

PROVIDER_ALIASES = {"openai": "OpenAI", "vercel_ai_gateway": "vercel_ai_gateway"}

EXPECTED_MODELS = tuple(SHORT)
F1_XMIN = 0.105
F1_XSCALE = 87.0
F2_XMIN = 0.80
F2_XSCALE = 40.78125
ROW_STEP = 0.4
F3_XMIN = 0.10
F3_XSCALE = 29.0
# Cost-quality scatter: log-cost across 12cm, micro-Brier over 7cm with the
# better (lower) scores at the top, as on the website.
F4_WIDTH = 12.0
F4_HEIGHT = 7.0
F4_LOG_MIN = math.log10(0.4)
F4_LOG_MAX = math.log10(150.0)
F4_YMIN = 0.11
F4_YMAX = 0.20
F4_COST_TICKS = (0.5, 1, 2, 5, 10, 20, 50, 100)
F4_BRIER_TICKS = (0.11, 0.13, 0.15, 0.17, 0.19)
# Approximate \scriptsize Latin Modern glyph advance and line height, in cm,
# for the greedy label placement.
F4_CHAR_WIDTH = 0.15
F4_LABEL_HEIGHT = 0.28


def load_data(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {path}")
    return cast(dict[str, Any], value)


def provider_name(model: dict[str, Any]) -> str:
    raw = str(model.get("provider", ""))
    return PROVIDER_ALIASES.get(raw, raw)


def f5(value: float) -> str:
    return f"{value:.5f}"


def x1(value: float) -> float:
    return (value - F1_XMIN) * F1_XSCALE


def x2(value: float) -> float:
    return (value - F2_XMIN) * F2_XSCALE


def x3(value: float) -> float:
    return (value - F3_XMIN) * F3_XSCALE


def x4(cost_usd: float) -> float:
    return (math.log10(cost_usd) - F4_LOG_MIN) / (F4_LOG_MAX - F4_LOG_MIN) * F4_WIDTH


def y4(micro_brier: float) -> float:
    return (F4_YMAX - micro_brier) / (F4_YMAX - F4_YMIN) * F4_HEIGHT


def csv_text(fields: list[str], rows: list[dict[str, Any]]) -> str:
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def figure1_rows(
    models: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    fields = [
        "slug",
        "display_name",
        "provider",
        "micro_brier",
        "equal_case_brier",
        "accuracy",
        "correct_units",
        "unit_count",
        "high_confidence_count",
        "high_confidence_share",
        "cost_usd_estimate",
    ]
    rows: list[dict[str, Any]] = []
    for model in sorted(models, key=lambda row: float(row["micro_brier"])):
        high = model["high_confidence"]
        rows.append(
            {
                "slug": model["slug"],
                "display_name": model["display_name"],
                "provider": provider_name(model),
                "micro_brier": f"{float(model['micro_brier']):.12f}",
                "equal_case_brier": f"{float(model['equal_case_brier']):.12f}",
                "accuracy": f"{float(model['accuracy']):.12f}",
                "correct_units": model["correct"],
                "unit_count": model["unit_count"],
                "high_confidence_count": high["count"],
                "high_confidence_share": f"{float(high['share']):.12f}",
                "cost_usd_estimate": (
                    ""
                    if model["cost"]["usd"] is None
                    else f"{float(model['cost']['usd']):.6f}"
                ),
            }
        )
    return fields, rows


def figure2_rows(
    models: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    fields = [
        "slug",
        "display_name",
        "provider",
        "mean_stated_confidence",
        "empirical_accuracy",
        "high_confidence_count",
        "high_confidence_share",
        "high_confidence_wrong",
    ]
    rows: list[dict[str, Any]] = []
    for model in models:
        high = model["high_confidence"]
        rows.append(
            {
                "slug": model["slug"],
                "display_name": model["display_name"],
                "provider": provider_name(model),
                "mean_stated_confidence": f"{float(high['mean_confidence']):.12f}",
                "empirical_accuracy": f"{float(high['accuracy']):.12f}",
                "high_confidence_count": high["count"],
                "high_confidence_share": f"{float(high['share']):.12f}",
                "high_confidence_wrong": high["wrong"],
            }
        )
    return fields, rows


def constant_brier(data: dict[str, Any], probability: float) -> float:
    base_rate = float(data["cohort"]["majority_class_accuracy"])
    return base_rate * (1.0 - probability) ** 2 + (1.0 - base_rate) * probability**2


def summary_means(data: dict[str, Any]) -> dict[str, float]:
    means: dict[str, float] = {}
    sources = data["summary_experiment"]["unit_sources"]
    for slug, source in sources.items():
        source_path = Path(str(source))
        if not source_path.is_absolute():
            source_path = REPOSITORY_ROOT / source_path
        if not source_path.exists():
            raise FileNotFoundError(f"summary unit source is missing: {source_path}")
        probabilities: list[float] = []
        with source_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    probabilities.append(
                        float(json.loads(line)["probability_fully_dismissed"])
                    )
        if probabilities:
            means[slug] = sum(probabilities) / len(probabilities)
    expected = (
        "gpt-5-6-luna-summaries-high",
        "gpt-6-luna-summaries-none",
        "jev-luna-summaries",
        "jev-grok-short-summaries",
    )
    missing = [slug for slug in expected if slug not in means]
    if missing:
        raise ValueError(f"summary unit sources contain no probabilities: {missing}")
    return {slug: means[slug] for slug in expected}


def figure3_rows(
    data: dict[str, Any], models: list[dict[str, Any]]
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    fields = [
        "condition",
        "display_label",
        "micro_brier",
        "equal_case_brier",
        "accuracy",
        "mean_predicted_dismissal",
        "observed_dismissal_rate",
        "protocol",
    ]
    full = next(row for row in models if row["slug"] == "gpt-5-6-luna")
    summary = data["summary_experiment"]["metrics"]
    means = summary_means(data)
    base_rate = float(data["cohort"]["majority_class_accuracy"])
    conditions = [
        {
            "key": "full_luna",
            "label": "GPT-5.6 Luna full documents",
            "short": "GPT-5.6 Luna full",
            "micro_brier": float(full["micro_brier"]),
            "equal_case_brier": float(full["equal_case_brier"]),
            "accuracy": float(full["accuracy"]),
            "mean_predicted_dismissal": math.nan,
            "protocol": "full-document agentic",
        },
        {
            "key": "gpt-5-6-luna-summaries-high",
            "label": "GPT-5.6 Luna summary + high reasoning",
            "short": "GPT-5.6 Luna summaries",
            "micro_brier": float(summary["gpt-5-6-luna-summaries-high"]["micro_brier"]),
            "equal_case_brier": float(
                summary["gpt-5-6-luna-summaries-high"]["equal_case_brier"]
            ),
            "accuracy": float(summary["gpt-5-6-luna-summaries-high"]["accuracy"]),
            "mean_predicted_dismissal": means["gpt-5-6-luna-summaries-high"],
            "protocol": "summary cache, one-shot",
        },
        {
            "key": "gpt-6-luna-summaries-none",
            "label": "GPT-6 Luna summary + no reasoning",
            "short": "GPT-6 Luna summaries",
            "micro_brier": float(summary["gpt-6-luna-summaries-none"]["micro_brier"]),
            "equal_case_brier": float(
                summary["gpt-6-luna-summaries-none"]["equal_case_brier"]
            ),
            "accuracy": float(summary["gpt-6-luna-summaries-none"]["accuracy"]),
            "mean_predicted_dismissal": means["gpt-6-luna-summaries-none"],
            "protocol": "summary cache, one-shot",
        },
        {
            "key": "jev-luna-summaries",
            "label": "Jev Luna summary + one-shot",
            "short": "Jev Luna summaries",
            "micro_brier": float(summary["jev-luna-summaries"]["micro_brier"]),
            "equal_case_brier": float(
                summary["jev-luna-summaries"]["equal_case_brier"]
            ),
            "accuracy": float(summary["jev-luna-summaries"]["accuracy"]),
            "mean_predicted_dismissal": means["jev-luna-summaries"],
            "protocol": "summary cache, one-shot",
        },
        {
            # Grok wrote different, shorter summaries: a pipeline comparison.
            "key": "jev-grok-short-summaries",
            "label": "Jev Grok summary + one-shot",
            "short": "Jev Grok summaries",
            "micro_brier": float(summary["jev-grok-short-summaries"]["micro_brier"]),
            "equal_case_brier": float(
                summary["jev-grok-short-summaries"]["equal_case_brier"]
            ),
            "accuracy": float(summary["jev-grok-short-summaries"]["accuracy"]),
            "mean_predicted_dismissal": means["jev-grok-short-summaries"],
            "protocol": "Grok summary cache, one-shot",
        },
    ]
    rows = [
        {
            "condition": condition["key"],
            "display_label": condition["label"],
            "micro_brier": f"{condition['micro_brier']:.12f}",
            "equal_case_brier": f"{condition['equal_case_brier']:.12f}",
            "accuracy": f"{condition['accuracy']:.12f}",
            "mean_predicted_dismissal": (
                ""
                if math.isnan(float(condition["mean_predicted_dismissal"]))
                else f"{float(condition['mean_predicted_dismissal']):.12f}"
            ),
            "observed_dismissal_rate": f"{base_rate:.12f}",
            "protocol": condition["protocol"],
        }
        for condition in conditions
    ]
    p_half = constant_brier(data, 0.5)
    rows.append(
        {
            "condition": "constant-p-0.50",
            "display_label": "Constant p = 0.50",
            "micro_brier": f"{p_half:.12f}",
            "equal_case_brier": "",
            "accuracy": "",
            "mean_predicted_dismissal": "0.500000000000",
            "observed_dismissal_rate": f"{base_rate:.12f}",
            "protocol": "constant probability baseline",
        }
    )
    return fields, rows, conditions


def pareto_frontier(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Priced configurations no other priced one matches on cost and micro-Brier
    while beating on at least one. Unpriced models are omitted, not free. The
    rule matches the website's ``paretoFrontier``."""

    priced = [model for model in models if model["cost"]["usd"] is not None]

    def dominated(model: dict[str, Any]) -> bool:
        cost = float(model["cost"]["usd"])
        brier = float(model["micro_brier"])
        for other in priced:
            if other is model:
                continue
            other_cost = float(other["cost"]["usd"])
            other_brier = float(other["micro_brier"])
            no_worse = other_cost <= cost and other_brier <= brier
            strictly = other_cost < cost or other_brier < brier
            if no_worse and strictly:
                return True
        return False

    return sorted(
        (model for model in priced if not dominated(model)),
        key=lambda model: float(model["cost"]["usd"]),
    )


def figure4_rows(
    models: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    fields = [
        "slug",
        "display_name",
        "provider",
        "cost_usd",
        "cost_basis",
        "micro_brier",
        "on_frontier",
    ]
    frontier = {model["slug"] for model in pareto_frontier(models)}
    rows: list[dict[str, Any]] = []
    for model in sorted(models, key=lambda row: float(row["micro_brier"])):
        rows.append(
            {
                "slug": model["slug"],
                "display_name": model["display_name"],
                "provider": provider_name(model),
                "cost_usd": (
                    ""
                    if model["cost"]["usd"] is None
                    else f"{float(model['cost']['usd']):.6f}"
                ),
                "cost_basis": model["cost"].get("basis", ""),
                "micro_brier": f"{float(model['micro_brier']):.12f}",
                "on_frontier": "true" if model["slug"] in frontier else "false",
            }
        )
    return fields, rows


Box = tuple[float, float, float, float]  # x0, x1, y0, y1 in cm


def _overlap(box: Box, others: list[Box]) -> float:
    total = 0.0
    for other in others:
        width = min(box[1], other[1]) - max(box[0], other[0])
        height = min(box[3], other[3]) - max(box[2], other[2])
        if width > 0 and height > 0:
            total += width * height
    return total


def _label_box(x: float, y: float, anchor: str, width: float) -> Box:
    """Bounding box of a TikZ node of the given anchor placed at (x, y)."""

    height = F4_LABEL_HEIGHT
    if "west" in anchor:
        x0 = x
    elif "east" in anchor:
        x0 = x - width
    else:
        x0 = x - width / 2
    if "south" in anchor:
        y0 = y
    elif "north" in anchor:
        y0 = y - height
    else:
        y0 = y - height / 2
    return (x0, x0 + width, y0, y0 + height)


def place_labels(
    points: list[tuple[float, float, str, bool]], line: list[tuple[float, float]]
) -> list[tuple[float, float, str, bool]]:
    """Greedy label placement for the scatter: try eight offsets around each
    point and keep the one that least covers marks, the frontier line, earlier
    labels, or the margin. Frontier points are placed first. Deterministic, so
    the generated TikZ is reproducible."""

    # Generous boxes around every mark: a label brushing a neighbour's mark
    # reads as that neighbour's name. A point's own mark is excluded below,
    # so labels still sit close to the point they name.
    marks: list[Box] = [
        (x - 0.26, x + 0.26, y - 0.22, y + 0.22) for x, y, _, _ in points
    ]
    obstacles: list[Box] = []
    for (ax, ay), (bx, by) in itertools.pairwise(line):
        steps = max(1, math.ceil(math.hypot(bx - ax, by - ay) / 0.15))
        for k in range(steps + 1):
            px = ax + (bx - ax) * k / steps
            py = ay + (by - ay) * k / steps
            obstacles.append((px - 0.05, px + 0.05, py - 0.05, py + 0.05))
    near = (
        (0.16, 0.0, "west"),
        (-0.16, 0.0, "east"),
        (0.0, 0.17, "south"),
        (0.0, -0.17, "north"),
        (0.12, 0.12, "south west"),
        (-0.12, 0.12, "south east"),
        (0.12, -0.12, "north west"),
        (-0.12, -0.12, "north east"),
    )
    # A farther ring, drawn with a leader line, for points boxed in by
    # neighbours on every side. The flat penalty keeps it a last resort.
    far = tuple((dx * 3.4, dy * 3.2, anchor) for dx, dy, anchor in near)
    candidates = tuple((dx, dy, anchor, False) for dx, dy, anchor in near) + tuple(
        (dx, dy, anchor, True) for dx, dy, anchor in far
    )
    order = sorted(range(len(points)), key=lambda i: (not points[i][3], points[i][1]))
    placed: dict[int, tuple[float, float, str, bool]] = {}
    labels_placed: list[Box] = []
    for index in order:
        x, y, label, _ = points[index]
        width = len(label) * F4_CHAR_WIDTH
        other_marks = [mark for i, mark in enumerate(marks) if i != index]
        best: tuple[float, tuple[float, float, str], Box] | None = None
        for rank, (dx, dy, anchor, leader) in enumerate(candidates):
            box = _label_box(x + dx, y + dy, anchor, width)
            outside = (
                max(0.0, -box[0])
                + max(0.0, box[1] - F4_WIDTH)
                + max(0.0, -box[2])
                + max(0.0, box[3] - F4_HEIGHT)
            )
            # Covering a point misattributes it, and two labels on top of each
            # other read as one; both cost more than brushing the frontier line.
            score = (
                _overlap(box, obstacles)
                + 3 * _overlap(box, labels_placed)
                + 6 * _overlap(box, other_marks)
                + outside * 50
                + (0.02 if leader else 0.0)
                + rank * 1e-3
            )
            if best is None or score < best[0]:
                best = (score, (x + dx, y + dy, anchor, leader), box)
        assert best is not None
        placed[index] = best[1]
        labels_placed.append(best[2])
    return [placed[i] for i in range(len(points))]


def render_figure4(data: dict[str, Any], models: list[dict[str, Any]]) -> str:
    """Cost against micro-Brier with the observed Pareto frontier."""

    priced = [model for model in models if model["cost"]["usd"] is not None]
    frontier = pareto_frontier(models)
    frontier_slugs = {model["slug"] for model in frontier}
    width = f5(F4_WIDTH)
    height = f5(F4_HEIGHT)
    lines = [r"\begin{tikzpicture}[every node/.style={font=\small}]"]
    for tick in F4_COST_TICKS:
        coordinate = f5(x4(float(tick)))
        label = f"\\${tick:.2f}" if tick < 1 else f"\\${tick:d}"
        lines += [
            rf"\draw[gray!18] ({coordinate},-.2)--({coordinate},{height});",
            rf"\node[anchor=north] at ({coordinate},-.3) {{{label}}};",
        ]
    for tick in F4_BRIER_TICKS:
        coordinate = f5(y4(tick))
        lines += [
            rf"\draw[gray!18] (-.2,{coordinate})--({width},{coordinate});",
            rf"\node[anchor=east] at (-.3,{coordinate}) {{{tick:.2f}}};",
        ]
    baseline = y4(float(data["cohort"]["constant_forecast_micro_brier"]))
    lines.append(
        rf"\draw[dashed,gray!70] (-.2,{f5(baseline)})--({width},{f5(baseline)});"
    )
    path = [
        (x4(float(m["cost"]["usd"])), y4(float(m["micro_brier"]))) for m in frontier
    ]
    lines.append(
        r"\draw[dashed,blue!65!black,line width=.8pt] "
        + "--".join(f"({f5(px)},{f5(py)})" for px, py in path)
        + ";"
    )
    points = [
        (
            x4(float(model["cost"]["usd"])),
            y4(float(model["micro_brier"])),
            SHORT[model["slug"]],
            model["slug"] in frontier_slugs,
        )
        for model in priced
    ]
    labels = place_labels(points, path)
    for (px, py, label, on_frontier), (lx, ly, anchor, leader) in zip(
        points, labels, strict=True
    ):
        if leader:
            lines.append(
                rf"\draw[gray!60,line width=.4pt] ({f5(px)},{f5(py)})--({f5(lx)},{f5(ly)});"  # noqa: E501
            )
        if on_frontier:
            lines.append(rf"\fill[blue!65!black] ({f5(px)},{f5(py)}) circle (2.2pt);")
        else:
            lines.append(
                rf"\draw[blue!65!black,fill=white,line width=.7pt] ({f5(px)},{f5(py)}) circle (2pt);"  # noqa: E501
            )
        lines.append(
            rf"\node[anchor={anchor},font=\scriptsize] at ({f5(lx)},{f5(ly)}) {{{label}}};"  # noqa: E501
        )
    case_count = int(data["cohort"]["case_count"])
    lines += [
        rf"\node[anchor=north] at ({f5(F4_WIDTH / 2)},-.78) {{Standard-rate cost for the {case_count}-case cohort, USD (log scale)}};",  # noqa: E501
        rf"\node[rotate=90,anchor=south] at (-1.05,{f5(F4_HEIGHT / 2)}) {{Micro Brier (lower is better) $\uparrow$}};",  # noqa: E501
        r"\fill[blue!65!black] (.2,-1.5) circle(2.2pt);\node[anchor=west] at (.4,-1.5) {On the observed frontier};",  # noqa: E501
        r"\draw[blue!65!black,fill=white,line width=.7pt] (5.0,-1.5) circle(2pt);\node[anchor=west] at (5.2,-1.5) {Other configurations};",  # noqa: E501
        r"\draw[dashed,gray!70] (9.0,-1.5)--(9.4,-1.5);\node[anchor=west,font=\scriptsize] at (9.6,-1.5) {Cohort rate};\end{tikzpicture}",  # noqa: E501
    ]
    return "\n".join(lines)


def panel_top(model_count: int, step: float = 0.5) -> str:
    """Top of the ranking grid: one step above the highest row."""

    return f5((model_count - 1) * step + 0.25)


def render_figure1(data: dict[str, Any], models: list[dict[str, Any]]) -> str:
    baseline = float(data["cohort"]["constant_forecast_micro_brier"])
    top = panel_top(len(models), ROW_STEP)
    lines = [r"\begin{tikzpicture}[every node/.style={font=\small}]"]
    for tick in (0.11, 0.13, 0.15, 0.17, 0.19):
        coordinate = x1(tick)
        lines += [
            rf"\draw[gray!18] ({f5(coordinate)},-.2)--({f5(coordinate)},{top});",
            rf"\node[anchor=north] at ({f5(coordinate)},-.3) {{{tick:.2f}}};",
        ]
    # The manuscript's existing five-decimal coordinate was produced from the
    # seven-decimal displayed baseline; retain that coordinate while the CSV
    # and data file preserve the full aggregate value.
    baseline_coordinate = x1(round(baseline, 7))
    lines.append(
        rf"\draw[dashed,gray!70] ({f5(baseline_coordinate)},-.2)--({f5(baseline_coordinate)},{top});"  # noqa: E501
    )
    for row_number, model in enumerate(
        reversed(sorted(models, key=lambda row: float(row["micro_brier"]))), 0
    ):
        y = row_number * ROW_STEP
        micro = x1(float(model["micro_brier"]))
        equal = x1(float(model["equal_case_brier"]))
        lines += [
            rf"\node[anchor=east] at (-.18,{y:.3f}) {{{SHORT[model['slug']]}}};",
            rf"\draw[gray!50] ({f5(micro)},{y:.3f})--({f5(equal)},{y:.3f});",
            rf"\fill[blue!65!black] ({f5(micro)},{y:.3f}) circle (2pt);",
            rf"\draw[blue!65!black,fill=white,line width=.7pt] ({f5(equal)},{y:.3f}) circle (2pt);",  # noqa: E501
        ]
    lines += [
        r"\node[anchor=north] at (4.35,-.78) {Brier loss (lower is better)};",
        r"\fill[blue!65!black] (.2,-1.5) circle(2pt);\node[anchor=west] at (.4,-1.5) {Micro Brier};",  # noqa: E501
        r"\draw[blue!65!black,fill=white] (4.0,-1.5) circle(2pt);\node[anchor=west] at (4.2,-1.5) {Equal-case Brier};",  # noqa: E501
        r"\draw[dashed,gray!70] (.2,-2.05)--(.6,-2.05);\node[anchor=west,font=\scriptsize] at (.8,-2.05) {Cohort rate (micro only)};\end{tikzpicture}",  # noqa: E501
    ]
    return "\n".join(lines)


def render_figure2(models: list[dict[str, Any]]) -> str:
    top = panel_top(len(models), ROW_STEP)
    lines = [r"\begin{tikzpicture}[every node/.style={font=\small}]"]
    for tick in (0.80, 0.85, 0.90, 0.95, 1.00):
        coordinate = x2(tick)
        lines += [
            rf"\draw[gray!18] ({f5(coordinate)},-.2)--({f5(coordinate)},{top});",
            rf"\node[anchor=north] at ({f5(coordinate)},-.3) {{{tick:.2f}}};",
        ]
    for row_number, model in enumerate(models[::-1], 0):
        y = row_number * ROW_STEP
        high = model["high_confidence"]
        confidence = x2(float(high["mean_confidence"]))
        accuracy = x2(float(high["accuracy"]))
        lines += [
            rf"\node[anchor=east] at (-.18,{y:.3f}) {{{SHORT[model['slug']]}}};",
            rf"\draw[gray!50] ({f5(confidence)},{y:.3f})--({f5(accuracy)},{y:.3f});",
            rf"\fill[blue!65!black] ({f5(confidence)},{y:.3f}) circle (2pt);",
            rf"\fill[orange!80!black] ({f5(accuracy - 0.055)},{y - 0.055:.3f}) rectangle ({f5(accuracy + 0.055)},{y + 0.055:.3f});",  # noqa: E501
        ]
    lines += [
        r"\node[anchor=north] at (4.35,-.78) {Probability / empirical fraction};",
        r"\fill[blue!65!black] (-.4,-1.5) circle(2pt);\node[anchor=west] at (-.2,-1.5) {Mean stated confidence};",  # noqa: E501
        r"\fill[orange!80!black] (5.05,-1.555) rectangle(5.16,-1.445);\node[anchor=west] at (5.35,-1.5) {Empirical accuracy};\end{tikzpicture}",  # noqa: E501
    ]
    return "\n".join(lines)


def render_figure3(data: dict[str, Any], conditions: list[dict[str, Any]]) -> str:
    lines = [r"\begin{tikzpicture}[every node/.style={font=\small}]"]
    top = f"{(len(conditions) - 1) * 0.75 + 0.25:.3f}"
    for tick in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
        coordinate = x3(tick)
        lines += [
            rf"\draw[gray!18] ({f5(coordinate)},-.2)--({f5(coordinate)},{top});",
            rf"\node[anchor=north] at ({f5(coordinate)},-.3) {{{tick:.2f}}};",
        ]
    base = float(data["cohort"]["constant_forecast_micro_brier"])
    p_half = constant_brier(data, 0.5)
    lines += [
        rf"\draw[dashed,gray!70] ({f5(x3(base))},-.2)--({f5(x3(base))},{top});",
        rf"\draw[dotted,gray!70] ({f5(x3(p_half))},-.2)--({f5(x3(p_half))},{top});",
    ]
    for y, condition in enumerate(reversed(conditions), 0):
        micro = x3(float(condition["micro_brier"]))
        equal = x3(float(condition["equal_case_brier"]))
        lines += [
            rf"\node[anchor=east] at (-.18,{y * 0.75:.3f}) {{{condition['short']}}};",
            rf"\draw[gray!50] ({f5(micro)},{y * 0.75:.3f})--({f5(equal)},{y * 0.75:.3f});",  # noqa: E501
            rf"\fill[blue!65!black] ({f5(micro)},{y * 0.75:.3f}) circle (2pt);",
            rf"\draw[blue!65!black,fill=white,line width=.7pt] ({f5(equal)},{y * 0.75:.3f}) circle (2pt);",  # noqa: E501
        ]
    lines += [
        r"\node[anchor=north] at (4.35,-.78) {Brier loss (lower is better)};",
        r"\fill[blue!65!black] (.2,-1.5) circle(2pt);\node[anchor=west] at (.4,-1.5) {Micro Brier};",  # noqa: E501
        r"\draw[blue!65!black,fill=white] (4.0,-1.5) circle(2pt);\node[anchor=west] at (4.2,-1.5) {Equal-case Brier};",  # noqa: E501
        r"\draw[dashed,gray!70] (.2,-2.05)--(.6,-2.05);\node[anchor=west,font=\scriptsize] at (.8,-2.05) {Cohort rate (micro only)};\draw[dotted,gray!70] (5.1,-2.05)--(5.5,-2.05);\node[anchor=west,font=\scriptsize] at (5.7,-2.05) {Constant $p=.5$};\end{tikzpicture}",  # noqa: E501
    ]
    return "\n".join(lines)


def render_all(data: dict[str, Any]) -> str:
    models = data["models"]
    if tuple(model["slug"] for model in models) != EXPECTED_MODELS:
        raise ValueError("empirical model panel does not match the manuscript order")
    _, _, conditions = figure3_rows(data, models)
    # Manuscript order: ranking, cost frontier, confidence, summary experiment.
    blocks = [
        render_figure1(data, models),
        render_figure4(data, models),
        render_figure2(models),
        render_figure3(data, conditions),
    ]
    return (
        "% Generated by make_figures.py; do not edit by hand.\n\n"
        + "\n\n".join(blocks)
        + "\n"
    )


def generated_artifacts(data: dict[str, Any]) -> dict[Path, str]:
    models = data["models"]
    fields1, rows1 = figure1_rows(models)
    fields2, rows2 = figure2_rows(models)
    fields3, rows3, _ = figure3_rows(data, models)
    fields4, rows4 = figure4_rows(models)
    return {
        FIGURES_DIR / "figure1_brier_ranked.csv": csv_text(fields1, rows1),
        FIGURES_DIR / "figure2_high_confidence_diagnostic.csv": csv_text(
            fields2, rows2
        ),
        FIGURES_DIR / "figure3_summary_experiment.csv": csv_text(fields3, rows3),
        FIGURES_DIR / "figure4_cost_frontier.csv": csv_text(fields4, rows4),
        INLINE_PATH: render_all(data),
    }


def extract_tikz_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    marker = r"\begin{tikzpicture}"
    end = r"\end{tikzpicture}"
    cursor = 0
    while True:
        start = text.find(marker, cursor)
        if start < 0:
            return blocks
        finish = text.find(end, start)
        if finish < 0:
            raise ValueError("unterminated tikzpicture block")
        finish += len(end)
        blocks.append(text[start:finish])
        cursor = finish


def validate_public_data(data: dict[str, Any]) -> None:
    strings: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in cast(dict[Any, Any], value).values():
                collect(item)
        elif isinstance(value, list):
            for item in cast(list[Any], value):
                collect(item)
        elif isinstance(value, str):
            strings.append(value)

    collect(data)
    forbidden = [value for value in strings if value.startswith("/")]
    if forbidden:
        raise ValueError(f"public data contains absolute paths: {forbidden[:2]}")
    if any("LegalForecastCorpus/docs/" in value for value in strings):
        raise ValueError("public data contains a private Corpus path")
    if (
        len(data["models"]) != len(EXPECTED_MODELS)
        or data["cohort"]["case_count"] != 91
    ):
        raise ValueError("unexpected fixed-panel counts")
    if data["cohort"]["unit_count"] != 387:
        raise ValueError("unexpected scored-unit count")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument(
        "--check", action="store_true", help="check generated files without writing"
    )
    parser.add_argument(
        "--manuscript",
        type=Path,
        help="compare generated TikZ blocks with this manuscript",
    )
    args = parser.parse_args(argv)
    data = load_data(args.data)
    validate_public_data(data)
    artifacts = generated_artifacts(data)
    mismatches: list[str] = []
    for path, content in artifacts.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                mismatches.append(str(path.relative_to(REPOSITORY_ROOT)))
        else:
            path.write_text(content, encoding="utf-8")
    if args.manuscript:
        manuscript_blocks = extract_tikz_blocks(
            args.manuscript.read_text(encoding="utf-8")
        )
        generated_blocks = extract_tikz_blocks(artifacts[INLINE_PATH])
        if (
            len(manuscript_blocks) < len(generated_blocks)
            or manuscript_blocks[-len(generated_blocks) :] != generated_blocks
        ):
            mismatches.append(str(args.manuscript) + " (TikZ blocks)")
    if mismatches:
        print("figure artifacts differ:", file=sys.stderr)
        for mismatch in mismatches:
            print(f"- {mismatch}", file=sys.stderr)
        return 1
    print("figure data and inline TikZ artifacts are reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
