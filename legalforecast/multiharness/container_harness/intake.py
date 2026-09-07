"""Validate a tracked harness-lane package before any upload.

This is the intake trigger model's Python half: measure the actual bytes,
enforce size caps, run the publication secret scan, and only then copy.  The
workflow that calls this module is ``workflow_dispatch`` only with empty
top-level permissions; it has no ``pull_request_target`` path.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from legalforecast.multiharness.container_harness.publication import (
    PublicationError,
    validate_published_package,
)
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


def validate_intake_package(package_dir: Path) -> tuple[Path, ...]:
    """Refuse a package that is missing, linked, oversized, or secret-bearing."""

    files = _package_files(package_dir)
    if len(files) > MAX_ARTIFACT_COUNT:
        raise IntakeError(
            f"{len(files)} artifacts exceeds the intake cap of {MAX_ARTIFACT_COUNT}"
        )
    total = 0
    for path in files:
        size = path.lstat().st_size
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
            PublicationGuardrailConfig(
                public_paths=files,
                max_text_bytes=MAX_ARTIFACT_BYTES,
            )
        )
    except PublicationGuardrailError as exc:
        raise IntakeError(f"publication guardrail: {exc}") from exc
    try:
        validate_published_package(package_dir)
    except PublicationError as exc:
        raise IntakeError(str(exc)) from exc
    return files


def publish_intake_package(package_dir: Path, destination: Path) -> None:
    """Validate the package, then copy regular files to a new destination."""

    files = validate_intake_package(package_dir)
    if destination.exists():
        raise IntakeError(f"destination already exists: {destination}")
    root = package_dir.resolve()
    for path in files:
        _copy_regular_file(path, destination / path.relative_to(root))


def _package_files(package_dir: Path) -> tuple[Path, ...]:
    """Return regular files under ``package_dir``, refusing any symlink."""

    if package_dir.is_symlink():
        raise IntakeError("package directory must not be a symlink")
    if not package_dir.is_dir():
        raise IntakeError(f"package is not a directory: {package_dir}")
    root = package_dir.resolve()
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in (*dirnames, *filenames):
            child = current / name
            if child.is_symlink():
                relative = child.relative_to(root).as_posix()
                raise IntakeError(f"package contains a symlink: {relative}")
        for name in filenames:
            child = current / name
            if stat.S_ISREG(child.lstat().st_mode):
                files.append(child)
    if not files:
        raise IntakeError("package contains no files")
    return tuple(sorted(files))


def _copy_regular_file(source: Path, destination: Path) -> None:
    """Copy one file without following a symlink that appears after validation."""

    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise IntakeError(f"package contains a symlink: {source.name}") from exc
    with os.fdopen(fd, "rb") as handle:
        payload = handle.read()
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise IntakeError(
            f"{source.name} is {len(payload)} bytes; the intake cap is "
            f"{MAX_ARTIFACT_BYTES}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


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
