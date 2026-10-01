"""Regenerate the paper's public figure inputs and inline TikZ bodies.

The paper keeps its figures inline so the standalone manuscript has no runtime
dependency on Matplotlib or a private corpus checkout.  This stdlib-only
generator reads the cleaned aggregate in ``../data/empirical.json`` and writes
the three plotted CSVs plus ``figures-inline.tex``.  The coordinate transforms
match the current manuscript bodies; they are deliberately not the historical
Matplotlib/PGFPlots figures in the research workspace.

Use ``--check`` in CI to verify committed generated artifacts.  Add
``--manuscript docs/paper/LegalForecastBench-paper.tex`` to compare every
generated TikZ block with the standalone manuscript.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, cast

FIGURES_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = FIGURES_DIR.parents[2]
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
            "label": "Jev summary + one-shot",
            "short": "Jev summaries",
            "micro_brier": float(summary["jev-luna-summaries"]["micro_brier"]),
            "equal_case_brier": float(
                summary["jev-luna-summaries"]["equal_case_brier"]
            ),
            "accuracy": float(summary["jev-luna-summaries"]["accuracy"]),
            "mean_predicted_dismissal": means["jev-luna-summaries"],
            "protocol": "summary cache, one-shot",
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
    for tick in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
        coordinate = x3(tick)
        lines += [
            rf"\draw[gray!18] ({f5(coordinate)},-.2)--({f5(coordinate)},2.500);",
            rf"\node[anchor=north] at ({f5(coordinate)},-.3) {{{tick:.2f}}};",
        ]
    base = float(data["cohort"]["constant_forecast_micro_brier"])
    p_half = constant_brier(data, 0.5)
    lines += [
        rf"\draw[dashed,gray!70] ({f5(x3(base))},-.2)--({f5(x3(base))},2.500);",
        rf"\draw[dotted,gray!70] ({f5(x3(p_half))},-.2)--({f5(x3(p_half))},2.500);",
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
    blocks = [
        render_figure1(data, models),
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
    return {
        FIGURES_DIR / "figure1_brier_ranked.csv": csv_text(fields1, rows1),
        FIGURES_DIR / "figure2_high_confidence_diagnostic.csv": csv_text(
            fields2, rows2
        ),
        FIGURES_DIR / "figure3_summary_experiment.csv": csv_text(fields3, rows3),
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
            or manuscript_blocks[-3:] != generated_blocks
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
