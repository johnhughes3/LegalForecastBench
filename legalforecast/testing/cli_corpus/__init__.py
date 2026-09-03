"""CLI characterization corpus for behavior-preserving reorganization."""

from __future__ import annotations

from legalforecast.testing.cli_corpus.command_manifest import (
    build_command_manifest,
    command_paths,
)
from legalforecast.testing.cli_corpus.differential import CASES, run_case
from legalforecast.testing.cli_corpus.entry_points import (
    ENTRY_POINTS,
    checkout_entry_points,
)
from legalforecast.testing.cli_corpus.help_snapshots import HELP_SNAPSHOTS, capture_help
from legalforecast.testing.cli_corpus.path_identity import scan_path_identity
from legalforecast.testing.cli_corpus.reporting import main
from legalforecast.testing.cli_corpus.xdist_timing import (
    parse_collect_only,
    parse_duration_lines,
)

__all__ = [
    "CASES",
    "ENTRY_POINTS",
    "HELP_SNAPSHOTS",
    "build_command_manifest",
    "capture_help",
    "checkout_entry_points",
    "command_paths",
    "main",
    "parse_collect_only",
    "parse_duration_lines",
    "run_case",
    "scan_path_identity",
]
