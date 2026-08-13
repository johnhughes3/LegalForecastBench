# pyright: reportPrivateUsage=false

"""The ``legalforecast report`` command adapter."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from legalforecast.reporting.score_summary_codec import score_summary_from_record


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the report command on the root parser."""

    report = subparsers.add_parser(
        "report",
        help="Render leaderboard artifacts from score summaries.",
    )
    report.add_argument("--scores", type=Path, required=True)
    report.add_argument("--output-dir", type=Path, required=True)
    report.add_argument("--accounting", type=Path)
    report.add_argument("--title", default="LegalForecast-MTD Leaderboard")
    report.add_argument("--bootstrap-replicates", type=int, default=5000)
    report.add_argument("--bootstrap-seed", type=int, default=20260514)
    report.add_argument("--dry-run", action="store_true")
    report.add_argument("--model-registry", type=Path)
    report.add_argument("--contamination-boundary")
    report.add_argument("--cohort-id")
    report.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Render leaderboard artifacts from score summaries."""

    from legalforecast import cli as _cli_ns

    scores_path = cast(Path, args.scores)
    output_dir = cast(Path, args.output_dir)
    score_payload = _cli_ns._read_json_object(scores_path)
    summary_records = _cli_ns._required_record_sequence(score_payload, "summaries")
    accounting_records = (
        _cli_ns._read_records(cast(Path, args.accounting))
        if cast(Path | None, args.accounting) is not None
        else []
    )
    json_path, csv_path, markdown_path, html_path = _cli_ns._report_paths(output_dir)
    sidecar_path = output_dir / "contamination-tier-sidecar.json"
    registry_path, contamination_boundary, cohort_id = _contamination_inputs(args)
    if cast(bool, args.dry_run):
        planned_outputs = _cli_ns._report_paths(output_dir)
        if registry_path is not None:
            planned_outputs = (*planned_outputs, sidecar_path)
        return _cli_ns._write_dry_run_plan(
            "report",
            output_dir / "report.plan.json",
            input_path=scores_path,
            output_paths=planned_outputs,
            record_count=len(summary_records),
            accounting_count=len(accounting_records),
        )

    summaries = tuple(score_summary_from_record(record) for record in summary_records)
    accounting_rows = (
        _cli_ns.summarize_accounting_leaderboard(accounting_records)
        if accounting_records
        else ()
    )
    inference = _cli_ns.infer_leaderboard_score_comparisons(
        summaries,
        replicates=cast(int, args.bootstrap_replicates),
        seed=cast(int, args.bootstrap_seed),
    )
    title = cast(str, args.title)
    report = _cli_ns.build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=accounting_rows,
        inference=inference,
        title=title,
    )
    _cli_ns._write_report_artifacts(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        html_path=html_path,
        generated_at=datetime.now(UTC),
    )
    written = [json_path, csv_path, markdown_path, html_path]
    if (
        registry_path is not None
        and contamination_boundary is not None
        and cohort_id is not None
    ):
        from legalforecast.evals.model_registry import load_model_registry
        from legalforecast.reporting.contamination_tiers import (
            build_contamination_tier_sidecar,
            classify_leaderboard_models,
            frozen_result_digest,
            sidecar_rows_from_registry,
            write_contamination_tier_sidecar,
        )

        registry = load_model_registry(registry_path)
        model_ids = tuple(
            row.model_id for row in report.rows if row.row_type == "model"
        )
        tiers = classify_leaderboard_models(
            model_ids,
            registry=registry,
            contamination_boundary=contamination_boundary,
        )
        sidecar = build_contamination_tier_sidecar(
            result_digest=frozen_result_digest(json_path.read_bytes()),
            cohort_id=cohort_id,
            contamination_boundary=contamination_boundary,
            rows=sidecar_rows_from_registry(
                model_ids,
                registry=registry,
                contamination_boundary=contamination_boundary,
            ),
        )
        write_contamination_tier_sidecar(sidecar_path, sidecar)
        markdown_path.write_text(
            report.to_markdown(contamination_tiers=tiers),
            encoding="utf-8",
        )
        html_path.write_text(
            report.to_html(contamination_tiers=tiers),
            encoding="utf-8",
        )
        written.append(sidecar_path)
    for path in written:
        _cli_ns._log_event("report", "artifact_written", path, len(report.rows))
    return 0


def _contamination_inputs(
    args: argparse.Namespace,
) -> tuple[Path | None, date | None, str | None]:
    registry_path = cast(Path | None, args.model_registry)
    boundary_raw = cast(str | None, args.contamination_boundary)
    cohort_id = cast(str | None, args.cohort_id)
    provided = (
        registry_path is not None,
        boundary_raw is not None,
        cohort_id is not None,
    )
    if not any(provided):
        return None, None, None
    if not all(provided):
        raise ValueError(
            "--model-registry, --contamination-boundary, and --cohort-id must "
            "be passed together"
        )
    return (
        registry_path,
        date.fromisoformat(cast(str, boundary_raw)),
        cohort_id,
    )
