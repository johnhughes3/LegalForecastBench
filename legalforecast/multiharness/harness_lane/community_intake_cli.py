"""Module CLI for the community harness-lane intake.

Deliberately a module entry point rather than a ``legalforecast multiharness``
subcommand: the shared CLI facade is under a no-growth ratchet, and this lane
has no reason to spend that budget.  Run it as::

    uv run python -m legalforecast.multiharness.harness_lane.community_intake_cli \\
        package --run-dir ... --output-dir ...
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from legalforecast.multiharness.harness_lane.community_intake import (
    build_community_harness_submission,
    validate_community_harness_submission,
)

DESCRIPTION = (
    "Package a containerized harness-lane run as a community submission, or "
    "validate one before it is uploaded. A community submission is not an "
    "official LegalForecastBench result."
)


def build_parser() -> argparse.ArgumentParser:
    """Return the community-intake argument parser."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.multiharness.harness_lane.community_intake_cli",
        description=DESCRIPTION,
    )
    actions = parser.add_subparsers(dest="action", required=True)
    package = actions.add_parser(
        "package", help="Build a submission package from a completed run directory."
    )
    package.add_argument("--run-dir", type=Path, required=True)
    package.add_argument("--output-dir", type=Path, required=True)
    package.add_argument("--submission-id", required=True)
    package.add_argument("--submitter-name", required=True)
    package.add_argument("--submitter-github")
    package.add_argument("--run-operator-name", required=True)
    package.add_argument("--adapter-author-name", required=True)
    package.add_argument(
        "--secret-value",
        action="append",
        default=[],
        metavar="VALUE",
        help=(
            "An exact value that must never survive into the package. Repeatable. "
            "Provider-token shapes and host paths are rewritten without this."
        ),
    )
    validate = actions.add_parser(
        "validate", help="Refuse a submission package before anything is uploaded."
    )
    validate.add_argument("--submission-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the community-intake CLI."""

    args = build_parser().parse_args(argv)
    if args.action == "validate":
        artifacts = validate_community_harness_submission(args.submission_dir)
        print(f"validated {len(artifacts)} artifact(s) in {args.submission_dir}")
        return 0
    submission = build_community_harness_submission(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        submission_id=args.submission_id,
        submitter_name=args.submitter_name,
        submitter_github=args.submitter_github,
        run_operator_name=args.run_operator_name,
        adapter_author_name=args.adapter_author_name,
        secret_values=tuple(args.secret_value),
    )
    print(
        f"packaged {submission.artifact_count} artifact(s), "
        f"{submission.total_bytes} bytes, "
        f"{submission.redacted_file_count} file(s) redacted, into "
        f"{submission.submission_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
