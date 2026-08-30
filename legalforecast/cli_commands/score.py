# pyright: reportPrivateUsage=false

"""The ``legalforecast score`` command adapter.

The public ``legalforecast.cli`` module remains the compatibility facade.  This
module owns the score command's parser registration and handler while resolving
shared CLI helpers through the facade at call time.  The late binding is
intentional: existing tests and downstream callers patch those helpers on
``legalforecast.cli`` and must continue to observe the patched behavior.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from legalforecast.cli_commands import corpus_manifest as _corpus_manifest
from legalforecast.cli_commands import stage_a_replay as _stage_a_replay
from legalforecast.evals.run_record_scoring import (
    score_run_records,
    score_run_records_against_labels_release,
)
from legalforecast.labeling import outcome_label_from_record
from legalforecast.release import (
    load_forecast_execution,
    load_run_manifest,
    validate_manifest_against_forecast,
    validate_release,
)


def register_stage_a_replay(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the cycle-neutral Stage A executor beside acquisition commands.

    Registration stays here rather than in the facade so the heavy executor
    loads lazily while production verifiers still contain reviewed CLI-facade
    bridges during the command-slice migration.  The owner-directed corpus
    manifest commands register through the same hook for the same reason, and
    so the facade's line count stays frozen.
    """

    _stage_a_replay.register(subparsers)
    _stage_a_replay.register_issuance(subparsers)
    _corpus_manifest.register(subparsers)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the score command on the root parser."""

    score = subparsers.add_parser(
        "score",
        help="Parse model outputs and score them against locked labels.",
    )
    score.add_argument("--runs", type=Path, required=True)
    labels = score.add_mutually_exclusive_group()
    labels.add_argument("--labels", type=Path)
    labels.add_argument(
        "--labels-release",
        type=Path,
        help="Validated public labels-release.json for official scoring.",
    )
    score.add_argument(
        "--forecast-release",
        "--forecast",
        dest="forecast_release",
        type=Path,
        help="Forecast-release.json paired with --labels-release.",
    )
    score.add_argument(
        "--artifact-root",
        type=Path,
        help="Root containing forecast-release referenced public artifacts.",
    )
    score.add_argument(
        "--manifest",
        "--run-manifest",
        dest="manifest",
        type=Path,
        help="Canonical locked benchmark-run manifest selecting the run cases.",
    )
    score.add_argument("--output", type=Path, required=True)
    score.add_argument("--unit-scores-output", type=Path)
    score.add_argument("--base-rate", type=float)
    score.add_argument(
        "--include-ablation-in-model-id",
        action="store_true",
        help="Separate summaries by model and run ablation (model::ablation).",
    )
    score.add_argument("--dry-run", action="store_true")
    score.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Score model runs against locked labels and write the result artifacts."""

    from legalforecast import cli as _cli_ns

    runs_path = cast(Path, args.runs)
    labels_path = cast(Path | None, args.labels)
    labels_release_path = cast(Path | None, args.labels_release)
    forecast_release_path = cast(Path | None, args.forecast_release)
    artifact_root = cast(Path | None, args.artifact_root)
    manifest_path = cast(Path | None, args.manifest)
    output_path = cast(Path, args.output)
    run_records = _cli_ns._read_records(runs_path)
    labels_release = None
    if labels_path is None and labels_release_path is None:
        raise ValueError("one of --labels or --labels-release is required")
    if labels_release_path is not None:
        if forecast_release_path is None or artifact_root is None:
            raise ValueError(
                "--labels-release requires --forecast-release and --artifact-root"
            )
        forecast, labels_release = validate_release(
            forecast_release_path,
            labels_release_path,
            artifact_root=artifact_root,
        )
        if manifest_path is not None:
            loaded_manifest = load_run_manifest(manifest_path)
            validate_manifest_against_forecast(loaded_manifest.manifest, forecast)
        label_records = ()
    else:
        label_records = _cli_ns._read_records(cast(Path, labels_path))
        if manifest_path is not None:
            loaded_manifest = load_run_manifest(manifest_path)
            if forecast_release_path is not None:
                if artifact_root is None:
                    raise ValueError("--forecast-release requires --artifact-root")
                execution = load_forecast_execution(
                    forecast_release_path,
                    artifact_root=artifact_root,
                )
                validate_manifest_against_forecast(
                    loaded_manifest.manifest,
                    execution.release,
                )
    unit_scores_output = cast(Path | None, args.unit_scores_output)
    if cast(bool, args.dry_run):
        output_paths = (
            (output_path,)
            if unit_scores_output is None
            else (
                output_path,
                unit_scores_output,
            )
        )
        return _cli_ns._write_dry_run_plan(
            "score",
            output_path,
            input_path=runs_path,
            output_paths=output_paths,
            record_count=len(run_records),
            log_record_count=len(run_records),
            label_count=(
                labels_release.unit_count
                if labels_release is not None
                else len(label_records)
            ),
        )

    if labels_release is not None:
        summaries = score_run_records_against_labels_release(
            run_records,
            labels_release,
            base_rate=cast(float | None, args.base_rate),
            include_ablation_in_model_id=cast(bool, args.include_ablation_in_model_id),
        )
    else:
        summaries = score_run_records(
            run_records,
            tuple(outcome_label_from_record(record) for record in label_records),
            base_rate=cast(float | None, args.base_rate),
            include_ablation_in_model_id=cast(bool, args.include_ablation_in_model_id),
        )
    _cli_ns._write_json(
        output_path,
        {
            "generated_at": _cli_ns._iso_datetime(datetime.now(UTC)),
            "summaries": [summary.to_record() for summary in summaries],
        },
    )
    _cli_ns._log_event("score", "artifact_written", output_path, len(summaries))
    if unit_scores_output is not None:
        unit_score_records = [
            unit_score.to_record()
            for summary in summaries
            for unit_score in summary.unit_scores
        ]
        _cli_ns._write_jsonl(unit_scores_output, unit_score_records)
        _cli_ns._log_event(
            "score",
            "artifact_written",
            unit_scores_output,
            len(unit_score_records),
        )
    return 0
