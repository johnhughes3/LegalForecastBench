"""The ``legalforecast site`` public data export commands."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import cast

from legalforecast import cli_support
from legalforecast.publication.site_export import export_site
from legalforecast.publication.site_export_models import SiteExport
from legalforecast.publication.site_refresh import refresh_site


def _iso_date(value: str) -> date:
    """Parse a decision date with a stable callable identity for CLI manifests."""

    return date.fromisoformat(value)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register the site data command without introducing frontend dependencies."""

    site = subparsers.add_parser(
        "site", help="Export public data for the results site."
    )
    commands = site.add_subparsers(
        dest="site_command", metavar="COMMAND", required=True
    )
    export = commands.add_parser(
        "export", help="Export native score JSON to the site contract."
    )
    export.add_argument(
        "--scores",
        type=Path,
        required=True,
        help="JSON produced by legalforecast score (also published by fan-in).",
    )
    export.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination public JSON bundle; parent directories are created.",
    )
    export.add_argument(
        "--report",
        type=Path,
        help=(
            "Matching native leaderboard report; supplies the verified "
            "decision-date boundary."
        ),
    )
    export.add_argument(
        "--model-registry",
        type=Path,
        help=(
            "Optional frozen registry; must match the score artifact's "
            "registry identity."
        ),
    )
    export.add_argument(
        "--contamination-boundary",
        type=_iso_date,
        help=(
            "Earliest scored decision date (YYYY-MM-DD). Omit if unknown; "
            "release date is not a substitute."
        ),
    )
    export.add_argument(
        "--withdrawal-ledger",
        type=Path,
        help=(
            "Current withdrawal JSONL; affected cases are removed and metrics "
            "recomputed. Unmapped document/artifact withdrawals require "
            "replacement scores."
        ),
    )
    export.add_argument("--cycle-id", help="Cycle to select from --withdrawal-ledger.")
    export.add_argument(
        "--withdrawn-case",
        action="append",
        default=[],
        help=(
            "Public case ID to exclude (repeatable); metrics and calibration "
            "are recomputed."
        ),
    )
    export.add_argument(
        "--accounting",
        type=Path,
        help=(
            "Optional existing accounting JSON/JSONL records; model_id must "
            "exactly match score summaries. Costs are labeled estimates with "
            "missing-case coverage."
        ),
    )
    export.set_defaults(handler=run_export)
    refresh = commands.add_parser(
        "refresh",
        help="Rebuild all selected public data after explicit case withdrawals.",
    )
    refresh.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Built public data directory produced by pnpm site:build "
        "(site/dist/data).",
    )
    refresh.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New output directory outside the input tree; original "
        "inputs stay untouched.",
    )
    refresh.add_argument(
        "--withdrawn-case",
        action="append",
        required=True,
        help="Case ID to remove from all current data; repeat for "
        "multiple cases. No hosted changes are performed.",
    )
    refresh.add_argument(
        "--replicates",
        type=int,
        default=1_000_000,
        help="Paired case-cluster bootstrap replicates (default: 1000000).",
    )
    refresh.set_defaults(handler=run_refresh)
    schema = commands.add_parser(
        "schema",
        help=(
            "Generate the JSON Schema used by frontend types and runtime validation."
        ),
    )
    schema.add_argument("--output", type=Path, required=True)
    schema.set_defaults(handler=run_schema)


def run_refresh(args: argparse.Namespace) -> int:
    """Generate a superseding public tree without provider calls or publication."""
    result = refresh_site(
        cast(Path, args.input_dir),
        cast(Path, args.output_dir),
        excluded_case_ids=cast(list[str], args.withdrawn_case),
        replicates=cast(int, args.replicates),
    )
    cli_support.log_event(
        "site refresh", "artifact_written", args.output_dir, len(result["models"])
    )
    return 0


def run_export(args: argparse.Namespace) -> int:
    """Execute the export with optional metadata and withdrawals."""

    result = export_site(
        scores_path=cast(Path, args.scores),
        output_path=cast(Path, args.output),
        registry_path=cast(Path | None, args.model_registry),
        report_path=cast(Path | None, args.report),
        contamination_boundary=cast(date | None, args.contamination_boundary),
        withdrawal_ledger_path=cast(Path | None, args.withdrawal_ledger),
        cycle_id=cast(str | None, args.cycle_id),
        excluded_case_ids=cast(list[str], args.withdrawn_case),
        accounting_path=cast(Path | None, args.accounting),
    )
    cli_support.log_event(
        "site export", "artifact_written", args.output, len(result.results)
    )
    return 0


def run_schema(args: argparse.Namespace) -> int:
    """Write the generated schema for cross-language validation."""

    cli_support.write_json(cast(Path, args.output), SiteExport.model_json_schema())
    return 0
