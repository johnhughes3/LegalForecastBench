"""Reader-facing official report page built from public aggregate artifacts."""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.publication.official_report_validation import (
    OfficialBundle,
    load_official_bundle,
    validate_official_arithmetic,
)

ArtifactLink = tuple[str, str]


@dataclass(frozen=True, slots=True)
class OfficialReportPage:
    """Rendered official report body and document title."""

    body: str
    title: str


def build_official_report_page(
    *,
    official_artifacts_dir: Path,
    artifact_links: Sequence[ArtifactLink],
    bundle: OfficialBundle | None = None,
) -> OfficialReportPage:
    """Build the official report body from canonical public aggregate fields."""

    validated_bundle = bundle or load_official_bundle(official_artifacts_dir)
    report = validated_bundle.report
    rows = _mapping_rows(report.get("rows", ()))
    model_rows, baseline_rows = _partition_official_rows(rows)
    score_rows = _mapping_rows(validated_bundle.scores.get("summaries", ()))
    score_rows_by_model = {
        _required_text(row, "model_id", label="score summary"): row
        for row in score_rows
    }
    run_card = validated_bundle.run_card
    cycle_power = validated_bundle.cycle_power
    prevalence = validate_official_arithmetic(
        rows,
        report=report,
        score_summary=validated_bundle.scores,
        unit_scores=validated_bundle.unit_scores,
        run_card=run_card,
        cycle_power=cycle_power,
    )
    title = _display_title(report)
    best_model = _best_model_row(model_rows)
    body = [
        "<a class='skip-link' href='#main-content'>Skip to results</a>",
        "<main id='main-content'>",
        "<p class='eyebrow'>Official evidence tier</p>",
        f"<h1>{html.escape(title)}</h1>",
        (
            "<p class='lede'>Official benchmark results are produced only by the "
            "protected LegalForecastBench evaluation workflow and official "
            "aggregation artifacts.</p>"
        ),
        (
            "<p class='notice official-notice'><strong>Separate result "
            "surfaces.</strong> Official and community results are published "
            "separately; community harness rows are never mixed into this "
            "leaderboard.</p>"
        ),
        _report_navigation(artifact_links),
        "<section id='headline' aria-labelledby='headline-title'>",
        "<h2 id='headline-title'>At a glance</h2>",
        _headline_cards(best_model, prevalence=prevalence, run_card=run_card),
        "</section>",
        "<section id='results' aria-labelledby='results-title'>",
        "<h2 id='results-title'>Evaluated models</h2>",
        _official_table(
            model_rows,
            score_rows_by_model=score_rows_by_model,
            caption="Evaluated model results",
        ),
        _uncertainty(report),
        "</section>",
        "<section id='calibration' aria-labelledby='calibration-title'>",
        "<h2 id='calibration-title'>Calibration and operational reliability</h2>",
        _calibration_summary(report),
        _operational_summary(best_model),
        "</section>",
        "<section id='baseline' aria-labelledby='baseline-title'>",
        "<h2 id='baseline-title'>Prevalence and baseline context</h2>",
        _baseline_context(
            baseline_rows,
            prevalence=prevalence,
            run_card=run_card,
            score_rows_by_model=score_rows_by_model,
        ),
        "</section>",
        "<section id='interpretation' aria-labelledby='interpretation-title'>",
        "<h2 id='interpretation-title'>How to interpret this result</h2>",
        (
            "<p><strong>Contamination.</strong> Eligibility is anchored to model "
            "release dates and decision timing. That design reduces temporal "
            "contamination risk; it does not prove immunity from memorization, "
            "pretraining overlap, or other contamination.</p>"
        ),
        (
            "<h3>Limitations</h3><p>This benchmark measures probabilistic forecasts "
            "for a frozen legal task and cohort. Results do not establish general "
            "legal competence, product quality, or performance outside the audited "
            "models, prompts, packets, and scoring protocol.</p>"
        ),
        _cycle_limitations(cycle_power),
        "</section>",
        "<section id='independence' aria-labelledby='independence-title'>",
        "<h2 id='independence-title'>Independence</h2>",
        (
            "<p>LegalForecastBench is an independent project. Harvey AI, Harvey LAB, "
            "and LegalQuants are not sponsors, partners, or endorsers of this "
            "work.</p>"
        ),
        "</section>",
        "<details class='audit-panel' id='artifacts'>",
        (
            "<summary><strong>Methods, audit, and downloadable "
            "artifacts</strong></summary>"
        ),
        (
            "<p>Use the linked run cards and methodology artifacts to inspect the "
            "frozen cycle, model registry, scoring configuration, and release "
            "bundle.</p>"
        ),
        _link_list(artifact_links),
        "<p><a href='artifact-index.json'>Rendered-site artifact index</a></p>",
        "</details>",
        "</main>",
    ]
    return OfficialReportPage(body="\n".join(body), title=title)


def _display_title(report: Mapping[str, Any]) -> str:
    title = _first_str(report, ("title",))
    return title if title != "unknown" else "LegalForecastBench Official Results"


def _partition_official_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    models: list[Mapping[str, Any]] = []
    baselines: list[Mapping[str, Any]] = []
    for row in rows:
        if _first_str(row, ("row_type",)) == "baseline":
            baselines.append(row)
        else:
            models.append(row)
    return tuple(models), tuple(baselines)


def _best_model_row(
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    scored = [row for row in rows if _optional_number(row, "micro_brier") is not None]
    if not scored:
        return rows[0] if rows else None
    return min(
        scored,
        key=lambda row: (
            cast(float, _optional_number(row, "micro_brier")),
            _first_str(row, ("model_id", "model_key", "solver_id")),
        ),
    )


def _headline_cards(
    best_model: Mapping[str, Any] | None,
    *,
    prevalence: float | None,
    run_card: Mapping[str, Any],
) -> str:
    if best_model is None:
        return (
            "<p>No official score rows were found in the supplied artifacts. "
            "This shell does not infer or invent results.</p>"
        )
    case_count = _first_value(run_card, ("case_count",))
    cards = (
        (
            "Lowest model micro-Brier",
            _fmt_number(_optional_number(best_model, "micro_brier")),
            _first_str(best_model, ("model_id", "model_key", "solver_id")),
        ),
        (
            "Expected calibration error",
            _fmt_number(_optional_number(best_model, "ece")),
            "Lower is better; inspect the calibration section.",
        ),
        (
            "Realized prevalence",
            _fmt_percent(prevalence),
            "Observed positive-outcome share in the scored cohort.",
        ),
        (
            "Cases",
            str(case_count) if case_count != "" else "Not reported",
            "See the run card for matrix and unit accounting.",
        ),
    )
    return (
        "<div class='grid'>"
        + "".join(
            "<article class='card'>"
            f"<h3>{html.escape(label)}</h3>"
            f"<p class='metric'>{html.escape(value)}</p>"
            f"<p class='muted'>{html.escape(note)}</p>"
            "</article>"
            for label, value, note in cards
        )
        + "</div>"
    )


def _official_table(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_rows_by_model: Mapping[str, Mapping[str, Any]],
    caption: str,
) -> str:
    if not rows:
        return "<p>No official score rows were found in the supplied artifacts.</p>"
    table_rows: list[str] = []
    for row in rows:
        model = _first_str(row, ("model_id", "model_key", "solver_id"))
        score_row = score_rows_by_model[model]
        score = _optional_number(row, "micro_brier")
        invalid_rate = _optional_number(row, "invalid_output_rate")
        refusal_rate = _optional_number(row, "refusal_rate")
        total_tokens = _required_int(score_row, "total_tokens", label="score summary")
        latency = _fmt_latency(_optional_number(score_row, "mean_latency_ms"))
        table_rows.append(
            "<tr>"
            f"<th scope='row'>{html.escape(model)}</th>"
            "<td><span class='tier-badge'>Official</span></td>"
            f"<td>{html.escape(_provider_snapshot(score_row))}</td>"
            f"<td>{_required_int(score_row, 'case_count', label='score summary')}</td>"
            f"<td>{_required_int(score_row, 'unit_count', label='score summary')}</td>"
            f"<td>{html.escape(_fmt_number(score))}</td>"
            f"<td>{html.escape(_delta_interval(row))}</td>"
            f"<td>{html.escape(_fmt_number(_optional_number(row, 'ece')))}</td>"
            f"<td>{html.escape(_fmt_percent(invalid_rate))}</td>"
            f"<td>{html.escape(_fmt_percent(refusal_rate))}</td>"
            "<td>"
            f"{html.escape(_fmt_currency(_optional_number(row, 'cost_per_case')))}"
            "</td>"
            f"<td>{total_tokens:,}</td>"
            f"<td>{html.escape(latency)}</td>"
            "</tr>"
        )
    return (
        "<p class='table-hint'>Scroll horizontally to inspect all columns.</p>"
        "<div class='table-scroll' role='region' tabindex='0' aria-label='"
        f"{html.escape(caption)} table'><table>"
        f"<caption>{html.escape(caption)}</caption>"
        "<thead><tr><th scope='col'>Model</th><th scope='col'>Tier</th>"
        "<th scope='col'>Provider / snapshot</th><th scope='col'>N cases</th>"
        "<th scope='col'>N units</th><th scope='col'>Micro-Brier</th>"
        "<th scope='col'>Delta vs best (95% CI)</th>"
        "<th scope='col'>ECE</th><th scope='col'>Invalid outputs</th>"
        "<th scope='col'>Refusals</th><th scope='col'>Cost per case</th>"
        "<th scope='col'>Tokens</th><th scope='col'>Latency</th>"
        f"</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>"
    )


def _uncertainty(report: Mapping[str, Any]) -> str:
    deltas = _mapping_rows(report.get("pairwise_deltas", ()))
    if not deltas:
        warning = _first_str(report, ("small_cluster_warning",))
        detail = (
            html.escape(warning)
            if warning != "unknown"
            else "No pairwise interval is available in this aggregate."
        )
        return f"<p><strong>Intervals:</strong> {detail}</p>"
    items: list[str] = []
    for delta in deltas:
        model_a = _first_str(delta, ("model_a",))
        model_b = _first_str(delta, ("model_b",))
        observed = _fmt_number(_optional_number(delta, "observed_delta"))
        low = _fmt_number(_optional_number(delta, "ci_low"))
        high = _fmt_number(_optional_number(delta, "ci_high"))
        items.append(
            "<li>"
            f"{html.escape(model_a)} minus {html.escape(model_b)}: "
            f"{html.escape(observed)} [{html.escape(low)}, {html.escape(high)}]"
            "</li>"
        )
    caveat = _first_str(report, ("rank_tier_caveat",))
    caveat_html = (
        f"<p class='muted'>{html.escape(caveat)}</p>" if caveat != "unknown" else ""
    )
    return (
        "<h3>Paired micro-Brier difference intervals</h3>"
        f"<ul>{''.join(items)}</ul>{caveat_html}"
    )


def _calibration_summary(report: Mapping[str, Any]) -> str:
    tables = _mapping_rows(report.get("calibration_tables", ()))
    if not tables:
        return "<p>No calibration table is available in this aggregate.</p>"
    rows = "".join(_calibration_summary_row(table) for table in tables)
    bin_tables = "".join(_calibration_bin_table(table) for table in tables)
    return (
        "<div class='table-scroll' role='region' tabindex='0' "
        "aria-label='Calibration summary table'><table>"
        "<caption>Calibration summary</caption>"
        "<thead><tr><th scope='col'>Model</th>"
        "<th scope='col'>Expected calibration error</th>"
        "<th scope='col'>Populated bins</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>{bin_tables}"
    )


def _calibration_summary_row(table: Mapping[str, Any]) -> str:
    populated = sum(
        1
        for item in _mapping_rows(table.get("bins", ()))
        if _optional_number(item, "unit_count") != 0
    )
    return (
        "<tr>"
        f"<th scope='row'>{html.escape(_first_str(table, ('model_id',)))}</th>"
        f"<td>{html.escape(_fmt_number(_optional_number(table, 'ece')))}</td>"
        f"<td>{populated}</td>"
        "</tr>"
    )


def _calibration_bin_table(table: Mapping[str, Any]) -> str:
    model_id = _required_text(table, "model_id", label="calibration table")
    bins = _mapping_rows(table.get("bins", ()))
    body = "".join(_calibration_bin_row(item) for item in bins)
    return (
        "<details class='audit-panel calibration-detail'>"
        "<summary><strong>Calibration bins for "
        f"{html.escape(model_id)}</strong></summary>"
        "<div class='table-scroll' role='region' tabindex='0' aria-label='"
        f"Calibration bins for {html.escape(model_id)} table'><table>"
        f"<caption>Calibration bins for {html.escape(model_id)}</caption>"
        "<thead><tr><th scope='col'>Bin</th><th scope='col'>Forecast range</th>"
        "<th scope='col'>N units</th><th scope='col'>Mean forecast</th>"
        "<th scope='col'>Observed rate</th><th scope='col'>Absolute error</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div></details>"
    )


def _calibration_bin_row(item: Mapping[str, Any]) -> str:
    index = _required_int(item, "bin_index", label="calibration bin")
    unit_count = _required_int(item, "unit_count", label="calibration bin")
    lower = _fmt_number(_optional_number(item, "lower"))
    upper = _fmt_number(_optional_number(item, "upper"))
    mean = _fmt_number(_optional_number(item, "mean_probability"))
    observed = _fmt_number(_optional_number(item, "observed_rate"))
    error = _fmt_number(_optional_number(item, "absolute_calibration_error"))
    return (
        "<tr>"
        f"<th scope='row'>{index}</th>"
        f"<td>[{lower}, {upper})</td>"
        f"<td>{unit_count}</td>"
        f"<td>{html.escape(mean)}</td>"
        f"<td>{html.escape(observed)}</td>"
        f"<td>{html.escape(error)}</td>"
        "</tr>"
    )


def _operational_summary(best_model: Mapping[str, Any] | None) -> str:
    if best_model is None:
        return ""
    cards = (
        (
            "Invalid outputs",
            _fmt_percent(_optional_number(best_model, "invalid_output_rate")),
        ),
        ("Refusals", _fmt_percent(_optional_number(best_model, "refusal_rate"))),
        ("Cost per case", _fmt_currency(_optional_number(best_model, "cost_per_case"))),
        (
            "Mean tool calls per case",
            _fmt_number(_optional_number(best_model, "mean_tool_calls_per_case")),
        ),
    )
    return (
        "<div class='grid'>"
        + "".join(
            "<article class='card'>"
            f"<h3>{html.escape(label)}</h3><p class='metric'>{html.escape(value)}</p>"
            "</article>"
            for label, value in cards
        )
        + "</div>"
    )


def _baseline_context(
    rows: Sequence[Mapping[str, Any]],
    *,
    prevalence: float | None,
    run_card: Mapping[str, Any],
    score_rows_by_model: Mapping[str, Mapping[str, Any]],
) -> str:
    prevalence_copy = (
        f"The realized prevalence is {_fmt_percent(prevalence)}."
        if prevalence is not None
        else "Realized prevalence is not reported in the supplied aggregate."
    )
    if not rows:
        return (
            f"<p>{html.escape(prevalence_copy)}</p>"
            "<p class='notice baseline-notice'>No frozen empirical baseline is "
            "present; no Brier skill claim is shown.</p>"
        )
    reference = _first_str(run_card, ("brier_skill_score_reference_model_id",))
    reference_copy = (
        f"The aggregate identifies {reference} as its frozen skill reference."
        if reference != "unknown"
        else (
            "The aggregate includes frozen baseline rows without naming a skill "
            "reference."
        )
    )
    period = cast(Mapping[str, Any], run_card["baseline_training_period"])
    training_count = _required_int(
        run_card,
        "cycle_baseline_training_example_count",
        label="aggregate run card",
    )
    period_start = _required_text(
        period,
        "training_period_start",
        label="baseline training period",
    )
    period_end = _required_text(
        period,
        "training_period_end",
        label="baseline training period",
    )
    training_copy = (
        f"Frozen historical training period: {period_start} through {period_end}. "
        f"Public cycle baseline evidence rows: {training_count}."
    )
    return (
        f"<p>{html.escape(prevalence_copy)} {html.escape(reference_copy)}</p>"
        f"<p>{html.escape(training_copy)}</p>"
        + _official_table(
            rows,
            score_rows_by_model=score_rows_by_model,
            caption="Frozen empirical baseline context",
        )
    )


def _required_text(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} requires non-empty {key}")
    return value


def _required_int(
    record: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} requires integer {key}")
    return value


def _provider_snapshot(row: Mapping[str, Any]) -> str:
    provider = _required_text(row, "provider", label="score summary")
    snapshot = _required_text(
        row,
        "model_version_or_snapshot",
        label="score summary",
    )
    return f"{provider} / {snapshot}"


def _delta_interval(row: Mapping[str, Any]) -> str:
    if row.get("row_type") == "baseline":
        return "Not ranked"
    delta = _optional_number(row, "delta_vs_best")
    low = _optional_number(row, "delta_vs_best_ci_low")
    high = _optional_number(row, "delta_vs_best_ci_high")
    if delta is None and low is None and high is None:
        return "Reference (best observed model)"
    if delta is None or low is None or high is None:
        raise ValueError("leaderboard row has an incomplete delta-vs-best interval")
    return f"{delta:.4f} [{low:.4f}, {high:.4f}]"


def _fmt_latency(value: float | None) -> str:
    return "Not reported" if value is None else f"{value:,.0f} ms"


def _cycle_limitations(cycle_power: Mapping[str, Any]) -> str:
    raw_record: object = cycle_power.get("cycle_power", cycle_power)
    if not isinstance(raw_record, Mapping):
        return "<p class='muted'>Cycle-power limitations were not reported.</p>"
    record = cast(Mapping[str, Any], raw_record)
    claim_strength = _first_str(record, ("claim_strength",))
    raw_warnings: object = record.get("warnings", ())
    warning_items = (
        tuple(
            str(item)
            for item in cast(Sequence[object], raw_warnings)
            if isinstance(item, str) and item.strip()
        )
        if isinstance(raw_warnings, Sequence)
        and not isinstance(raw_warnings, str | bytes)
        else ()
    )
    parts: list[str] = []
    if claim_strength != "unknown":
        parts.append(
            "<p><strong>Permitted claim strength:</strong> "
            f"{html.escape(claim_strength)}</p>"
        )
    if warning_items:
        parts.append(
            "<ul>"
            + "".join(f"<li>{html.escape(item)}</li>" for item in warning_items)
            + "</ul>"
        )
    return "".join(parts)


def _report_navigation(links: Sequence[ArtifactLink]) -> str:
    detailed_report = _artifact_href(links, "report/leaderboard.html")
    audit = _artifact_href(links, "artifact-index.json")
    run_card = _artifact_href(links, "run-cards/aggregate-run-card.json")
    reproduce = _artifact_href(links, "unit-scores.jsonl")
    items = [
        ("#results", "Results"),
        ("#calibration", "Calibration"),
        ("#baseline", "Baseline context"),
        (
            "https://github.com/johnhughes3/LegalForecastBench/blob/main/docs/METHODS.md",
            "Methods",
        ),
    ]
    if detailed_report is not None:
        items.append((detailed_report, "Detailed report"))
    if audit is not None:
        items.append((audit, "Audit"))
    if run_card is not None:
        items.append((run_card, "Run card"))
    if reproduce is not None:
        items.append((reproduce, "Reproduce arithmetic"))
    return (
        "<nav class='report-nav' aria-label='Report navigation'><ul>"
        + "".join(
            f"<li><a href='{html.escape(href)}'>{html.escape(label)}</a></li>"
            for href, label in items
        )
        + "</ul></nav>"
    )


def _artifact_href(
    links: Sequence[ArtifactLink],
    label: str,
) -> str | None:
    return next((href for href, candidate in links if candidate == label), None)


def _link_list(links: Sequence[ArtifactLink]) -> str:
    if not links:
        return "<p>No downloadable public artifacts were found.</p>"
    return (
        "<ul>"
        + "".join(
            f"<li><a href='{html.escape(href)}'>{html.escape(label)}</a></li>"
            for href, label in links
        )
        + "</ul>"
    )


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, Mapping):
            records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _first_str(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _first_value(record: Mapping[str, Any], keys: Sequence[str]) -> object:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return ""


def _optional_number(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _fmt_number(value: float | None) -> str:
    return "Not reported" if value is None else f"{value:.4f}"


def _fmt_percent(value: float | None) -> str:
    return "Not reported" if value is None else f"{value:.2%}"


def _fmt_currency(value: float | None) -> str:
    return "Not reported" if value is None else f"${value:.4f}"
