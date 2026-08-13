# pyright: reportPrivateUsage=false

"""The ``legalforecast report`` command adapter."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
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
    if cast(bool, args.dry_run):
        return _cli_ns._write_dry_run_plan(
            "report",
            output_dir / "report.plan.json",
            input_path=scores_path,
            output_paths=_cli_ns._report_paths(output_dir),
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
    json_path, csv_path, markdown_path, html_path = _cli_ns._report_paths(output_dir)
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
    for path in (json_path, csv_path, markdown_path, html_path):
        _cli_ns._log_event("report", "artifact_written", path, len(report.rows))
    return 0
