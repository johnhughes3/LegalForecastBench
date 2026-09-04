"""Validate a tracked harness-lane package before any upload.

This is the intake trigger model's Python half: measure the actual bytes,
enforce size caps, run the publication secret scan, and only then copy.  The
workflow that calls this module is ``workflow_dispatch`` only with empty
top-level permissions; it has no ``pull_request_target`` path.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    PublicationGuardrailError,
    enforce_publication_guardrails,
)

MAX_ARTIFACT_BYTES: Final = 8 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 64 * 1024 * 1024
MAX_ARTIFACT_COUNT: Final = 2_000


class IntakeError(RuntimeError):
    """Raised when a package cannot be validated or published."""


def validate_intake_package(package_dir: Path) -> None:
    """Refuse a package that is missing, oversized, or secret-bearing."""

    if not package_dir.is_dir():
        raise IntakeError(f"package is not a directory: {package_dir}")
    files = tuple(sorted(path for path in package_dir.rglob("*") if path.is_file()))
    if not files:
        raise IntakeError("package contains no files")
    if len(files) > MAX_ARTIFACT_COUNT:
        raise IntakeError(
            f"{len(files)} artifacts exceeds the intake cap of {MAX_ARTIFACT_COUNT}"
        )
    total = 0
    for path in files:
        size = path.stat().st_size
        if size > MAX_ARTIFACT_BYTES:
            raise IntakeError(
                f"{path.name} is {size} bytes; the intake cap is {MAX_ARTIFACT_BYTES}"
            )
        total += size
    if total > MAX_TOTAL_BYTES:
        raise IntakeError(
            f"the package is {total} bytes; the intake cap is {MAX_TOTAL_BYTES}"
        )
    try:
        enforce_publication_guardrails(
            PublicationGuardrailConfig(public_paths=(package_dir,))
        )
    except PublicationGuardrailError as exc:
        raise IntakeError(f"publication guardrail: {exc}") from exc


def publish_intake_package(package_dir: Path, destination: Path) -> None:
    """Validate the package, then copy it to a destination that must not exist."""

    validate_intake_package(package_dir)
    if destination.exists():
        raise IntakeError(f"destination already exists: {destination}")
    shutil.copytree(package_dir, destination)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI for the maintainer-triggered intake workflow."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.multiharness.container_harness.intake",
        description="Validate a harness-lane package before any upload.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate without copying.")
    validate.add_argument("--package-dir", type=Path, required=True)
    publish = subparsers.add_parser(
        "publish", help="Validate, then copy to a new destination."
    )
    publish.add_argument("--package-dir", type=Path, required=True)
    publish.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_intake_package(args.package_dir)
        else:
            publish_intake_package(args.package_dir, args.destination)
    except IntakeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
