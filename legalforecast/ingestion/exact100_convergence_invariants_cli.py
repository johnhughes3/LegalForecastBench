"""Runnable command for the exact-100 final invariant suite.

Run it as the ``legalforecast-exact100-convergence`` console script, or as
``uv run python -m legalforecast.ingestion.exact100_convergence_invariants_cli``.

It is deliberately a standalone entry point rather than a ``legalforecast``
subcommand: the repository's architecture ratchet holds ``legalforecast/cli.py``
at a fixed size to stop CLI sprawl, and a read-only convergence report has no
reason to grow it. :func:`add_parser` is still exported so the suite can be
mounted as a subcommand later without a second implementation.

Every artifact is passed in by path, so the command carries no environment
assumptions and no private-tree locations. Exit status 0 means the corpus has
converged; 1 means at least one invariant named a blocker; 2 means the command
could not read what it was given.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.exact100_convergence_invariants import (
    ConvergenceReport,
    evaluate_convergence,
    load_inputs,
)

__all__ = [
    "EXIT_BLOCKED",
    "EXIT_CONVERGED",
    "EXIT_UNREADABLE",
    "add_parser",
    "main",
    "run",
]

EXIT_CONVERGED = 0
EXIT_BLOCKED = 1
EXIT_UNREADABLE = 2

COMMAND = "check-exact100-convergence"


class Exact100ConvergenceCliError(ValueError):
    """Raised when a required convergence artifact cannot be read."""


DESCRIPTION = (
    "Deterministic convergence gate. Joins the exact-100 manifest projection, "
    "the adjudication overlay, and the owner disposition overlay, and reports "
    "every case and document that blocks convergence. Performs no acquisition, "
    "provider call, or model selection."
)


def add_parser(subparsers: Any) -> None:
    """Mount the suite as a subcommand of an existing parser."""

    parser = subparsers.add_parser(
        COMMAND,
        help="Run the nine final exact-100 corpus convergence invariants.",
        description=DESCRIPTION,
    )
    _add_arguments(parser)
    parser.set_defaults(handler=run)


def build_standalone_parser() -> argparse.ArgumentParser:
    """Build the parser used by the standalone console entry point."""

    parser = argparse.ArgumentParser(prog=COMMAND, description=DESCRIPTION)
    _add_arguments(parser)
    return parser


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="JSONL: exact-100 normalized manifest projection.",
    )
    parser.add_argument(
        "--adjudication",
        type=Path,
        required=True,
        help="JSONL: adjudication worksheet overlay carrying validation evidence.",
    )
    parser.add_argument(
        "--dispositions",
        type=Path,
        required=True,
        help="JSONL: owner disposition overlay with per-row execution state.",
    )
    parser.add_argument(
        "--parse-quality",
        type=Path,
        default=None,
        help="JSON: parse-quality rejections. Omitting it fails invariant 7.",
    )
    parser.add_argument(
        "--replacements",
        type=Path,
        default=None,
        help="JSONL: replacement-validation records for owner-excluded slots.",
    )
    parser.add_argument(
        "--acquisitions",
        type=Path,
        default=None,
        help=(
            "JSONL: corpus-wide held-document records. Without it, cases outside "
            "the adjudication overlay read as unheld."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit the machine-readable report instead of the text summary.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the JSON report to this path in addition to stdout.",
    )


def _read(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise Exact100ConvergenceCliError(
            f"cannot read the {label} artifact at {path.name}: {error.strerror}"
        ) from error


def build_report(
    *,
    corpus: Path,
    adjudication: Path,
    dispositions: Path,
    parse_quality: Path | None = None,
    replacements: Path | None = None,
    acquisitions: Path | None = None,
) -> ConvergenceReport:
    """Read every artifact and evaluate the suite."""

    inputs = load_inputs(
        corpus_text=_read(corpus, label="corpus"),
        adjudication_text=_read(adjudication, label="adjudication"),
        dispositions_text=_read(dispositions, label="dispositions"),
        parse_quality_text=(
            None
            if parse_quality is None
            else _read(parse_quality, label="parse-quality")
        ),
        replacements_text=(
            None if replacements is None else _read(replacements, label="replacements")
        ),
        acquisitions_text=(
            None if acquisitions is None else _read(acquisitions, label="acquisitions")
        ),
    )
    return evaluate_convergence(inputs)


def run(args: argparse.Namespace) -> int:
    try:
        report = build_report(
            corpus=cast(Path, args.corpus),
            adjudication=cast(Path, args.adjudication),
            dispositions=cast(Path, args.dispositions),
            parse_quality=cast("Path | None", args.parse_quality),
            replacements=cast("Path | None", args.replacements),
            acquisitions=cast("Path | None", getattr(args, "acquisitions", None)),
        )
    except (Exact100ConvergenceCliError, json.JSONDecodeError) as error:
        print(f"exact-100 convergence: unreadable input — {error}")
        return EXIT_UNREADABLE

    payload = report.to_json()
    if bool(getattr(args, "emit_json", False)):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(report.render_text())
    output = cast("Path | None", getattr(args, "output", None))
    if output is not None:
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return EXIT_CONVERGED if report.passed else EXIT_BLOCKED


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for ``legalforecast-exact100-convergence``."""

    return run(build_standalone_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
