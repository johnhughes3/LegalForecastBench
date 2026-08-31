"""Command line entry point for the public LegalForecast benchmark.

Corpus construction is owned by LegalForecastCorpus. This package accepts
already-issued public releases and locked run manifests, executes forecasts,
scores results, renders reports, and hosts the community multi-harness tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from legalforecast import __version__
from legalforecast import cli_support as _support
from legalforecast.cli_commands import manifest as _manifest_cmd
from legalforecast.cli_commands import release as _release_cmd
from legalforecast.cli_commands import report as _report_cmd
from legalforecast.cli_commands import run as _run_cmd
from legalforecast.cli_commands import score as _score_cmd
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.publication.official_aggregate import main as _aggregate_main
from legalforecast.publication.static_sites import render_official_results_site


class CommandError(RuntimeError):
    """Raised when a public CLI command receives invalid input."""


def build_parser() -> argparse.ArgumentParser:
    """Build the supported public command tree."""

    parser = argparse.ArgumentParser(
        prog="legalforecast",
        description="LegalForecast-MTD benchmark utilities.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"legalforecast-mtd {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    _manifest_cmd.register(subparsers)
    _release_cmd.register(subparsers)
    _run_cmd.register(subparsers)
    _score_cmd.register(subparsers)
    _report_cmd.register(subparsers)
    _register_publish(subparsers)
    add_multiharness_parser(subparsers)
    return parser


def _register_publish(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register public publication aggregation and site rendering."""

    publish = subparsers.add_parser(
        "publish",
        help="Aggregate and render official publication artifacts.",
    )
    commands = publish.add_subparsers(dest="publish_command", metavar="COMMAND")
    commands.add_parser(
        "aggregate",
        add_help=False,
        help="Aggregate downloaded official per-case artifacts locally.",
    )
    site = commands.add_parser(
        "site",
        help="Render the official results site from public aggregate artifacts.",
    )
    site.add_argument(
        "--official-artifacts-dir",
        type=Path,
        required=True,
        help="Public directory written by publish aggregate.",
    )
    site.add_argument("--output-dir", type=Path, required=True)
    site.add_argument(
        "--supplementary-artifacts-dir",
        type=Path,
        help="Optional public supplementary aggregate to render beside official rows.",
    )
    site.set_defaults(handler=_run_publish_site)


def _run_publish_site(args: argparse.Namespace) -> int:
    result = render_official_results_site(
        official_artifacts_dir=cast(Path, args.official_artifacts_dir),
        output_dir=cast(Path, args.output_dir),
        supplementary_artifacts_dir=cast(Path | None, args.supplementary_artifacts_dir),
    )
    print(
        json.dumps(
            {
                "artifact_index": str(result.artifact_index_path),
                "index": str(result.index_path),
                "output_dir": str(result.output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run one supported public command."""

    args = list(argv) if argv is not None else sys.argv[1:]
    if args[:2] == ["publish", "aggregate"]:
        return _aggregate_main(args[2:])

    parser = build_parser()
    parsed = parser.parse_args(args)
    handler = getattr(parsed, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return cast(Callable[[argparse.Namespace], int], handler)(parsed)
    except CommandError as exc:
        print(f"legalforecast: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"legalforecast: {exc}", file=sys.stderr)
        return 2


# Explicit public-data helpers retained for downstream command adapters.
read_records = _support.read_records
read_json_object = _support.read_json_object
write_json = _support.write_json
write_jsonl = _support.write_jsonl
write_dry_run_plan = _support.write_dry_run_plan
log_event = _support.log_event
iso_datetime = _support.iso_datetime
