# pyright: reportPrivateUsage=false

"""The public ``legalforecast manifest`` command adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from legalforecast.release import (
    load_run_manifest,
    validate_manifest_against_forecast,
    validate_release,
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register validation of the locked public benchmark-run manifest."""

    manifest = subparsers.add_parser(
        "manifest",
        help="Validate the locked public benchmark-run manifest.",
    )
    commands = manifest.add_subparsers(dest="manifest_command", metavar="COMMAND")
    validate = commands.add_parser(
        "validate",
        help="Validate a locked manifest and optionally its paired releases.",
    )
    validate.add_argument(
        "--manifest",
        "--run-manifest",
        dest="manifest",
        type=Path,
        required=True,
        help="Canonical locked benchmark-run manifest JSON.",
    )
    validate.add_argument(
        "--forecast",
        type=Path,
        help="Outcome-blinded forecast-release.json to cross-check.",
    )
    validate.add_argument(
        "--labels",
        type=Path,
        help="Labels-release.json to validate with the forecast release.",
    )
    validate.add_argument(
        "--artifact-root",
        type=Path,
        help="Root containing forecast-release referenced public artifacts.",
    )
    validate.set_defaults(handler=run_validate)


def run_validate(args: argparse.Namespace) -> int:
    """Validate one locked manifest without consulting private corpus state."""

    loaded = load_run_manifest(cast(Path, args.manifest))
    forecast_path = cast(Path | None, args.forecast)
    labels_path = cast(Path | None, args.labels)
    artifact_root = cast(Path | None, args.artifact_root)
    if (forecast_path is None) != (labels_path is None) or (
        forecast_path is not None and artifact_root is None
    ):
        raise ValueError(
            "--forecast, --labels, and --artifact-root must be passed together"
        )

    result: dict[str, object] = {
        "manifest_schema_version": loaded.manifest.schema_version,
        "manifest_sha256": loaded.sha256,
        "run_id": str(loaded.manifest.run_id),
        "selected_case_count": len(loaded.manifest.selected_cases),
        "valid": True,
    }
    if forecast_path is not None and labels_path is not None:
        forecast, labels = validate_release(
            forecast_path,
            labels_path,
            artifact_root=cast(Path, artifact_root),
        )
        validate_manifest_against_forecast(loaded.manifest, forecast)
        result.update(
            {
                "forecast_release_digest": forecast.release_digest,
                "labels_release_digest": labels.release_digest,
                "release_id": forecast.release_id,
            }
        )
    print(json.dumps(result, sort_keys=True))
    return 0
