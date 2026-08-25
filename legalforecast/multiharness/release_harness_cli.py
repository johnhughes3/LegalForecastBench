"""CLI seam for release-backed multi-harness task issuance."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from legalforecast.multiharness.spec import TaskIndex
from legalforecast.multiharness.task_loaders import (
    DEFAULT_LFB_SUITE_VERSION,
    DEFAULT_RELEASE_LFB_SUITE_VERSION,
    LfbTaskLoader,
    ReleaseLfbTaskLoader,
)


def add_lfb_task_index_arguments(parser: argparse.ArgumentParser) -> None:
    """Add legacy packet and additive forecast-release.v1 task inputs."""

    parser.add_argument(
        "--input",
        type=Path,
        help="Legacy LFB packet JSONL input for --suite lfb.",
    )
    parser.add_argument(
        "--forecast-release",
        type=Path,
        help=(
            "Authenticated forecast-release.v1 JSON for --suite lfb. This is "
            "mutually exclusive with --input and never loads labels."
        ),
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        help=(
            "Root containing the packet, prompt, and document bytes committed "
            "by --forecast-release."
        ),
    )


def release_task_index_plan_fields(args: argparse.Namespace) -> dict[str, str | None]:
    """Return path-only dry-run fields without opening release bytes."""

    return {
        "forecast_release": _path_record(cast(Path | None, args.forecast_release)),
        "artifact_root": _path_record(cast(Path | None, args.artifact_root)),
    }


def lfb_task_index_from_args(
    args: argparse.Namespace,
    *,
    suite_version: str | None,
    index_id: str | None,
    selection_namespace: str | None,
) -> TaskIndex:
    """Load either additive release tasks or legacy packet JSONL tasks."""

    input_path = cast(Path | None, args.input)
    forecast_path = cast(Path | None, args.forecast_release)
    artifact_root = cast(Path | None, args.artifact_root)
    if input_path is not None and forecast_path is not None:
        raise ValueError("pass either --input or --forecast-release, not both")
    if forecast_path is None:
        if artifact_root is not None:
            raise ValueError("--artifact-root requires --forecast-release")
        if input_path is None:
            raise ValueError("--input or --forecast-release is required for lfb")
        return LfbTaskLoader(
            suite_version=suite_version or DEFAULT_LFB_SUITE_VERSION,
        ).load_packet_jsonl(
            input_path,
            index_id=index_id or "legalforecast-mtd",
            selection_namespace=selection_namespace or "legalforecast_mtd",
            solver_input_root=cast(Path | None, args.solver_input_root),
        )
    if artifact_root is None:
        raise ValueError("--artifact-root is required with --forecast-release")
    return ReleaseLfbTaskLoader(
        suite_version=suite_version or DEFAULT_RELEASE_LFB_SUITE_VERSION,
    ).load_forecast_release(
        forecast_path,
        artifact_root=artifact_root,
        index_id=index_id or "legalforecast-release",
        selection_namespace=selection_namespace or "legalforecast_mtd",
        solver_input_root=cast(Path | None, args.solver_input_root),
    )


def _path_record(path: Path | None) -> str | None:
    return path.as_posix() if path is not None else None
