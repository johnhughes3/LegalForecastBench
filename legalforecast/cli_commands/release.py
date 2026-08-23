# pyright: reportPrivateUsage=false

"""The ``legalforecast release`` public contract commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from legalforecast.immutable_io import ImmutableIOError
from legalforecast.release import (
    issue_release,
    issue_synthetic_release,
    load_forecast_draft,
    load_labels_draft,
    publish_release,
    validate_release,
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register release issuance and validation on the root parser."""

    release = subparsers.add_parser(
        "release", help="Issue and validate public forecast and labels releases."
    )
    commands = release.add_subparsers(dest="release_command", metavar="COMMAND")

    issue = commands.add_parser(
        "issue", help="Issue a release pair from strict drafts and artifact bytes."
    )
    issue.add_argument("--forecast-draft", type=Path, required=True)
    issue.add_argument("--labels-draft", type=Path, required=True)
    issue.add_argument("--artifact-root", type=Path, required=True)
    issue.add_argument("--output-dir", type=Path, required=True)
    issue.set_defaults(handler=run_issue)

    synthetic = commands.add_parser(
        "issue-synthetic", help="Issue the deterministic three-case fixture."
    )
    synthetic.add_argument("--output-dir", type=Path, required=True)
    synthetic.set_defaults(handler=run_issue_synthetic)

    validate = commands.add_parser(
        "validate", help="Validate a paired release and every referenced artifact."
    )
    validate.add_argument("--forecast", type=Path, required=True)
    validate.add_argument("--labels", type=Path, required=True)
    validate.add_argument("--artifact-root", type=Path, required=True)
    validate.set_defaults(handler=run_validate)


def run_issue(args: argparse.Namespace) -> int:
    """Issue and create-only publish a generic release pair."""

    issued = issue_release(
        load_forecast_draft(cast(Path, args.forecast_draft)),
        load_labels_draft(cast(Path, args.labels_draft)),
        artifact_root=cast(Path, args.artifact_root),
    )
    output_dir = cast(Path, args.output_dir)
    try:
        publish_release(output_dir, issued)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc
    _print_issue_status(output_dir, issued.forecast.release_digest)
    return 0


def run_issue_synthetic(args: argparse.Namespace) -> int:
    """Issue and create-only publish the deterministic fixture."""

    output_dir = cast(Path, args.output_dir)
    try:
        issued = issue_synthetic_release(output_dir)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc
    _print_issue_status(output_dir, issued.forecast.release_digest)
    return 0


def run_validate(args: argparse.Namespace) -> int:
    """Validate a paired public release."""

    forecast, labels = validate_release(
        cast(Path, args.forecast),
        cast(Path, args.labels),
        artifact_root=cast(Path, args.artifact_root),
    )
    print(
        json.dumps(
            {
                "case_count": forecast.case_count,
                "forecast_release_digest": forecast.release_digest,
                "labels_release_digest": labels.release_digest,
                "release_id": forecast.release_id,
                "unit_count": forecast.unit_count,
                "valid": True,
            },
            sort_keys=True,
        )
    )
    return 0


def _print_issue_status(output_dir: Path, forecast_digest: str) -> None:
    print(
        json.dumps(
            {
                "forecast_release": str(output_dir / "forecast-release.json"),
                "forecast_release_digest": forecast_digest,
                "labels_release": str(output_dir / "labels-release.json"),
            },
            sort_keys=True,
        )
    )
