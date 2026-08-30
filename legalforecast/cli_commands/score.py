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
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from legalforecast.cli_commands import corpus_manifest as _corpus_manifest
from legalforecast.cli_commands import stage_a_replay as _stage_a_replay
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_sha256,
)
from legalforecast.evals.run_record_scoring import (
    score_run_records,
    score_run_records_against_labels_release,
)
from legalforecast.immutable_io import read_single_link_file
from legalforecast.labeling import outcome_label_from_record
from legalforecast.release import (
    load_forecast_execution,
    load_run_manifest,
    validate_manifest_against_forecast,
    validate_release,
)
from legalforecast.runner.ledger import RunnerLedger


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
    score.add_argument(
        "--expected-run-identity-sha256",
        "--expected-run-identity",
        dest="expected_run_identity_sha256",
        help=(
            "Exact run identity SHA-256 emitted by the manifest-mode execution "
            "ledger. Required with --labels-release."
        ),
    )
    score.add_argument(
        "--model-registry",
        type=Path,
        help=(
            "Frozen model registry used by the manifest-mode execution. Required "
            "with --labels-release."
        ),
    )
    score.add_argument(
        "--expected-model-registry-sha256",
        dest="expected_model_registry_sha256",
        help=(
            "Exact frozen model-registry SHA-256. May be read from --ledger when "
            "that stronger typed authority is supplied."
        ),
    )
    score.add_argument(
        "--ledger",
        "--run-ledger",
        dest="ledger",
        type=Path,
        help=(
            "Manifest-mode execution ledger that supplies the exact run and "
            "registry identity when explicit values are not passed."
        ),
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
    expected_run_identity_sha256 = cast(
        str | None,
        getattr(args, "expected_run_identity_sha256", None),
    )
    model_registry_path = cast(Path | None, getattr(args, "model_registry", None))
    expected_model_registry_sha256 = cast(
        str | None,
        getattr(args, "expected_model_registry_sha256", None),
    )
    ledger_path = cast(Path | None, getattr(args, "ledger", None))
    output_path = cast(Path, args.output)
    run_records = _cli_ns._read_records(runs_path)
    labels_release = None
    forecast = None
    loaded_manifest = None
    model_registry = None
    if labels_path is None and labels_release_path is None:
        raise ValueError("one of --labels or --labels-release is required")
    if labels_release_path is not None:
        if (
            manifest_path is None
            or forecast_release_path is None
            or artifact_root is None
        ):
            raise ValueError(
                "--labels-release requires --manifest, --forecast-release, "
                "and --artifact-root"
            )
        forecast, labels_release = validate_release(
            forecast_release_path,
            labels_release_path,
            artifact_root=artifact_root,
        )
        loaded_manifest = load_run_manifest(manifest_path)
        validate_manifest_against_forecast(loaded_manifest.manifest, forecast)
        (
            expected_run_identity_sha256,
            expected_model_registry_sha256,
        ) = _resolve_locked_authority(
            expected_run_identity_sha256=expected_run_identity_sha256,
            expected_model_registry_sha256=expected_model_registry_sha256,
            model_registry_path=model_registry_path,
            ledger_path=ledger_path,
        )
        registry_bytes = read_single_link_file(
            cast(Path, model_registry_path),
            label="model registry",
        )
        actual_registry_sha256 = model_registry_sha256(registry_bytes)
        if actual_registry_sha256 != expected_model_registry_sha256:
            raise ValueError("model registry bytes differ from frozen authority")
        model_registry = load_model_registry_bytes(registry_bytes)
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
                forecast = execution.release
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
            forecast_release=(forecast if loaded_manifest is not None else None),
            manifest=(
                loaded_manifest.manifest if loaded_manifest is not None else None
            ),
            expected_run_identity_sha256=expected_run_identity_sha256,
            model_registry=model_registry,
            expected_model_registry_sha256=expected_model_registry_sha256,
        )
    else:
        summaries = score_run_records(
            run_records,
            tuple(outcome_label_from_record(record) for record in label_records),
            base_rate=cast(float | None, args.base_rate),
            include_ablation_in_model_id=cast(bool, args.include_ablation_in_model_id),
        )
    output: dict[str, object] = {
        "generated_at": _cli_ns._iso_datetime(datetime.now(UTC)),
        "summaries": [summary.to_record() for summary in summaries],
    }
    if (
        labels_release is not None
        and forecast is not None
        and loaded_manifest is not None
    ):
        output["identity"] = {
            "run_manifest_id": str(loaded_manifest.manifest.run_id),
            "run_manifest_sha256": loaded_manifest.sha256,
            "forecast_release_id": forecast.release_id,
            "forecast_release_digest": forecast.release_digest,
            "labels_release_id": labels_release.release_id,
            "labels_release_digest": labels_release.release_digest,
            "labels_forecast_release_digest": labels_release.forecast_release_digest,
            "run_identity_sha256": cast(str, expected_run_identity_sha256),
            "model_registry_sha256": cast(str, expected_model_registry_sha256),
            "models": _locked_model_bindings(run_records),
        }
    _cli_ns._write_json(output_path, output)
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


def _resolve_locked_authority(
    *,
    expected_run_identity_sha256: str | None,
    expected_model_registry_sha256: str | None,
    model_registry_path: Path | None,
    ledger_path: Path | None,
) -> tuple[str, str]:
    """Resolve official scoring inputs from explicit values or one run ledger."""

    if model_registry_path is None:
        raise ValueError("--labels-release requires --model-registry")
    ledger_binding = None
    if ledger_path is not None:
        with RunnerLedger(ledger_path) as ledger:
            ledger_binding = ledger.read_run_binding()
    if ledger_binding is not None:
        if (
            expected_run_identity_sha256 is not None
            and expected_run_identity_sha256 != ledger_binding.identity_sha256
        ):
            raise ValueError("expected run identity differs from execution ledger")
        if (
            expected_model_registry_sha256 is not None
            and expected_model_registry_sha256 != ledger_binding.model_registry_sha256
        ):
            raise ValueError("expected model registry differs from execution ledger")
        expected_run_identity_sha256 = ledger_binding.identity_sha256
        expected_model_registry_sha256 = ledger_binding.model_registry_sha256
    if expected_run_identity_sha256 is None:
        raise ValueError("--labels-release requires the expected run identity")
    if expected_model_registry_sha256 is None:
        raise ValueError(
            "--labels-release requires the expected model registry SHA-256 or --ledger"
        )
    return expected_run_identity_sha256, expected_model_registry_sha256


def _locked_model_bindings(
    run_records: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    """Project validated receipt bindings without copying provider output."""

    bindings: set[tuple[str, str, str]] = set()
    for raw_record in run_records:
        record = raw_record
        model_key = record.get("model_key")
        entry_sha256 = record.get("model_registry_entry_sha256")
        served_version = record.get("served_model_version")
        if not all(
            isinstance(value, str) and value
            for value in (model_key, entry_sha256, served_version)
        ):
            raise ValueError("locked run receipt lacks model binding")
        bindings.add(
            (
                cast(str, model_key),
                cast(str, entry_sha256),
                cast(str, served_version),
            )
        )
    return [
        {
            "model_key": model_key,
            "model_registry_entry_sha256": entry_sha256,
            "served_model_version": served_version,
        }
        for model_key, entry_sha256, served_version in sorted(bindings)
    ]
