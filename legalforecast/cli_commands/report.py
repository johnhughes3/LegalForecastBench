# pyright: reportPrivateUsage=false

"""The ``legalforecast report`` command adapter."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast import cli_support as _cli_support
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
    require_official_registry_entries,
)
from legalforecast.immutable_io import read_single_link_file
from legalforecast.release import (
    ForecastRelease,
    LabelsRelease,
    LoadedRunManifest,
    load_run_manifest,
    validate_manifest_against_forecast,
    validate_release,
)
from legalforecast.reporting.leaderboard import (
    build_benchmark_leaderboard_report,
    infer_leaderboard_score_comparisons,
    summarize_accounting_leaderboard,
)
from legalforecast.reporting.score_summary_codec import score_summary_from_record
from legalforecast.runner.ledger import RunnerLedger


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the report command on the root parser."""

    report = subparsers.add_parser(
        "report",
        help="Render leaderboard artifacts from score summaries.",
    )
    report.add_argument("--scores", type=Path, required=True)
    report.add_argument("--output-dir", type=Path, required=True)
    report.add_argument(
        "--manifest",
        "--run-manifest",
        dest="manifest",
        type=Path,
        help="Canonical locked benchmark-run manifest for this report.",
    )
    report.add_argument(
        "--forecast-release",
        "--forecast",
        dest="forecast_release",
        type=Path,
        help="Forecast-release.json paired with the report's labels release.",
    )
    report.add_argument(
        "--labels-release",
        type=Path,
        help="Labels-release.json used by the official scoring boundary.",
    )
    report.add_argument(
        "--artifact-root",
        type=Path,
        help="Root containing forecast-release referenced public artifacts.",
    )
    report.add_argument("--accounting", type=Path)
    report.add_argument("--title", default="LegalForecast-MTD Leaderboard")
    report.add_argument("--bootstrap-replicates", type=int, default=5000)
    report.add_argument("--bootstrap-seed", type=int, default=20260514)
    report.add_argument("--dry-run", action="store_true")
    report.add_argument("--model-registry", type=Path)
    report.add_argument(
        "--frozen-model-registry",
        type=Path,
        help=(
            "Frozen model registry used for the official score artifact. "
            "When supplied, its bytes and every reported model binding are checked."
        ),
    )
    report.add_argument(
        "--expected-run-identity-sha256",
        "--expected-run-identity",
        dest="expected_run_identity_sha256",
        help="Expected run identity SHA-256 from the manifest execution ledger.",
    )
    report.add_argument(
        "--expected-model-registry-sha256",
        dest="expected_model_registry_sha256",
        help="Expected frozen model-registry SHA-256.",
    )
    report.add_argument(
        "--ledger",
        "--run-ledger",
        dest="ledger",
        type=Path,
        help="Manifest execution ledger supplying expected report provenance.",
    )
    report.add_argument("--contamination-boundary")
    report.add_argument("--cohort-id")
    report.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Render leaderboard artifacts from score summaries."""

    scores_path = cast(Path, args.scores)
    output_dir = cast(Path, args.output_dir)
    score_payload = _cli_support.read_json_object(scores_path)
    summary_records = _cli_support.required_record_sequence(score_payload, "summaries")
    contract = _validate_contract_inputs(args)
    provenance: Mapping[str, Any] | None = None
    if contract is not None:
        loaded_manifest, forecast, labels = contract
        provenance = _validate_score_payload_identity(
            score_payload,
            summary_records,
            loaded_manifest=loaded_manifest,
            forecast=forecast,
            labels=labels,
            expected_run_identity_sha256=cast(
                str | None, getattr(args, "expected_run_identity_sha256", None)
            ),
            expected_model_registry_sha256=cast(
                str | None, getattr(args, "expected_model_registry_sha256", None)
            ),
            ledger_path=cast(Path | None, getattr(args, "ledger", None)),
            frozen_model_registry_path=cast(
                Path | None, getattr(args, "frozen_model_registry", None)
            ),
        )
    accounting_records = (
        _cli_support.read_records(cast(Path, args.accounting))
        if cast(Path | None, args.accounting) is not None
        else []
    )
    json_path, csv_path, markdown_path, html_path = _cli_support.report_paths(
        output_dir
    )
    sidecar_path = output_dir / "contamination-tier-sidecar.json"
    registry_path, contamination_boundary, cohort_id = _contamination_inputs(args)
    if cast(bool, args.dry_run):
        planned_outputs = _cli_support.report_paths(output_dir)
        if registry_path is not None:
            planned_outputs = (*planned_outputs, sidecar_path)
        return _cli_support.write_dry_run_plan(
            "report",
            output_dir / "report.plan.json",
            input_path=scores_path,
            output_paths=planned_outputs,
            record_count=len(summary_records),
            accounting_count=len(accounting_records),
        )

    summaries = tuple(score_summary_from_record(record) for record in summary_records)
    accounting_rows = (
        summarize_accounting_leaderboard(accounting_records)
        if accounting_records
        else ()
    )
    inference = infer_leaderboard_score_comparisons(
        summaries,
        replicates=cast(int, args.bootstrap_replicates),
        seed=cast(int, args.bootstrap_seed),
    )
    title = cast(str, args.title)
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=accounting_rows,
        inference=inference,
        title=title,
    )
    _cli_support.write_report_artifacts(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        html_path=html_path,
        generated_at=datetime.now(UTC),
    )
    if provenance is not None:
        report_payload = _cli_support.read_json_object(json_path)
        report_payload["provenance"] = dict(provenance)
        _cli_support.write_json(json_path, report_payload)
    written = [json_path, csv_path, markdown_path, html_path]
    if (
        registry_path is not None
        and contamination_boundary is not None
        and cohort_id is not None
    ):
        from legalforecast.evals.model_registry import load_model_registry
        from legalforecast.reporting.contamination_tiers import (
            build_contamination_tier_sidecar,
            classify_leaderboard_models,
            frozen_result_digest,
            sidecar_rows_from_registry,
            write_contamination_tier_sidecar,
        )

        registry = load_model_registry(registry_path)
        model_ids = tuple(
            row.model_id for row in report.rows if row.row_type == "model"
        )
        tiers = classify_leaderboard_models(
            model_ids,
            registry=registry,
            contamination_boundary=contamination_boundary,
        )
        sidecar = build_contamination_tier_sidecar(
            result_digest=frozen_result_digest(json_path.read_bytes()),
            cohort_id=cohort_id,
            contamination_boundary=contamination_boundary,
            rows=sidecar_rows_from_registry(
                model_ids,
                registry=registry,
                contamination_boundary=contamination_boundary,
            ),
        )
        write_contamination_tier_sidecar(sidecar_path, sidecar)
        markdown_path.write_text(
            report.to_markdown(contamination_tiers=tiers),
            encoding="utf-8",
        )
        html_path.write_text(
            report.to_html(contamination_tiers=tiers),
            encoding="utf-8",
        )
        written.append(sidecar_path)
    for path in written:
        _cli_support.log_event("report", "artifact_written", path, len(report.rows))
    return 0


def _validate_contract_inputs(
    args: argparse.Namespace,
) -> tuple[LoadedRunManifest, ForecastRelease, LabelsRelease] | None:
    """Validate optional official provenance inputs before rendering output."""

    manifest_path = cast(Path | None, getattr(args, "manifest", None))
    forecast_path = cast(Path | None, getattr(args, "forecast_release", None))
    labels_path = cast(Path | None, getattr(args, "labels_release", None))
    artifact_root = cast(Path | None, getattr(args, "artifact_root", None))
    if not any((manifest_path, forecast_path, labels_path, artifact_root)):
        return None
    if None in (manifest_path, forecast_path, labels_path, artifact_root):
        raise ValueError(
            "--manifest, --forecast-release, --labels-release, and "
            "--artifact-root must be passed together"
        )
    loaded_manifest = load_run_manifest(cast(Path, manifest_path))
    forecast, labels = validate_release(
        cast(Path, forecast_path),
        cast(Path, labels_path),
        artifact_root=cast(Path, artifact_root),
    )
    validate_manifest_against_forecast(loaded_manifest.manifest, forecast)
    return loaded_manifest, forecast, labels


def _validate_score_payload_identity(
    score_payload: Mapping[str, Any],
    summary_records: Sequence[Mapping[str, Any]],
    *,
    loaded_manifest: LoadedRunManifest,
    forecast: ForecastRelease,
    labels: LabelsRelease,
    expected_run_identity_sha256: str | None = None,
    expected_model_registry_sha256: str | None = None,
    ledger_path: Path | None = None,
    frozen_model_registry_path: Path | None = None,
) -> Mapping[str, Any]:
    """Ensure a report renders the exact material produced by strict scoring."""

    expected_identity = {
        "run_manifest_id": str(loaded_manifest.manifest.run_id),
        "run_manifest_sha256": loaded_manifest.sha256,
        "forecast_release_id": forecast.release_id,
        "forecast_release_digest": forecast.release_digest,
        "labels_release_id": labels.release_id,
        "labels_release_digest": labels.release_digest,
        "labels_forecast_release_digest": labels.forecast_release_digest,
    }
    identity = score_payload.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("score artifact identity does not match report inputs")
    identity_mapping = cast(Mapping[str, Any], identity)
    if any(
        identity_mapping.get(key) != value for key, value in expected_identity.items()
    ):
        raise ValueError("score artifact identity does not match report inputs")
    run_identity = _require_sha256(
        identity_mapping.get("run_identity_sha256"),
        "score artifact run identity",
    )
    registry_identity = _require_sha256(
        identity_mapping.get("model_registry_sha256"),
        "score artifact model registry",
    )
    if expected_run_identity_sha256 is not None:
        if run_identity != _require_sha256(
            expected_run_identity_sha256,
            "expected run identity",
        ):
            raise ValueError("score artifact run identity differs from expected")
    if expected_model_registry_sha256 is not None:
        if registry_identity != _require_sha256(
            expected_model_registry_sha256,
            "expected model registry",
        ):
            raise ValueError("score artifact model registry differs from expected")
    if ledger_path is not None:
        with RunnerLedger(ledger_path) as ledger:
            binding = ledger.read_run_binding()
        if run_identity != binding.identity_sha256:
            raise ValueError(
                "score artifact run identity differs from execution ledger"
            )
        if registry_identity != binding.model_registry_sha256:
            raise ValueError(
                "score artifact model registry differs from execution ledger"
            )

    raw_model_records = identity_mapping.get("models")
    if not isinstance(raw_model_records, list) or not raw_model_records:
        raise ValueError("score artifact identity lacks model bindings")
    bindings: list[dict[str, str]] = []
    for raw_model_record in cast(list[object], raw_model_records):
        if not isinstance(raw_model_record, Mapping):
            raise ValueError("score artifact model binding is not an object")
        model_record = cast(Mapping[str, Any], raw_model_record)
        model_key = model_record.get("model_key")
        entry_sha256 = model_record.get("model_registry_entry_sha256")
        served_version = model_record.get("served_model_version")
        if not isinstance(model_key, str) or not model_key:
            raise ValueError("score artifact model binding is incomplete")
        if not isinstance(entry_sha256, str) or not entry_sha256:
            raise ValueError("score artifact model binding is incomplete")
        if not isinstance(served_version, str) or not served_version:
            raise ValueError("score artifact model binding is incomplete")
        bindings.append(
            {
                "model_key": model_key,
                "model_registry_entry_sha256": _require_sha256(
                    entry_sha256,
                    "model registry entry",
                ),
                "served_model_version": served_version,
            }
        )
    if frozen_model_registry_path is not None:
        registry_bytes = read_single_link_file(
            frozen_model_registry_path,
            label="model registry",
        )
        if model_registry_sha256(registry_bytes) != registry_identity:
            raise ValueError("model registry bytes differ from score artifact")
        registry = load_model_registry_bytes(registry_bytes)
        for binding in bindings:
            model_key = binding["model_key"]
            if ":" not in model_key:
                raise ValueError("score artifact model key is not provider:model_id")
            provider, model_id = model_key.split(":", 1)
            try:
                entry = registry.get(provider, model_id)
            except KeyError as exc:
                raise ValueError(
                    "score artifact model key is absent from frozen registry: "
                    f"{model_key}"
                ) from exc
            require_official_registry_entries((entry,))
            if binding["model_registry_entry_sha256"] != model_registry_entry_sha256(
                entry
            ):
                raise ValueError("score artifact model registry entry differs")
            if binding["served_model_version"] != entry.model_version_or_snapshot:
                raise ValueError("score artifact served model version differs")

    expected_case_by_unit = {
        unit.unit_id: unit.case_id
        for unit in forecast.prediction_units
        if unit.should_score
    }
    expected_units = set(expected_case_by_unit)
    for summary in summary_records:
        unit_scores = summary.get("unit_scores")
        if not isinstance(unit_scores, list):
            raise ValueError("score summary lacks its unit scores")
        unit_ids: list[str] = []
        score_records = cast(list[Mapping[str, Any]], unit_scores)
        for score in score_records:
            unit_id = score.get("unit_id")
            case_id = score.get("case_id")
            if not isinstance(unit_id, str) or not isinstance(case_id, str):
                raise ValueError("score summary unit score lacks identity")
            if expected_case_by_unit.get(unit_id) != case_id:
                raise ValueError("score summary unit-to-case identity differs")
            unit_ids.append(unit_id)
        if set(unit_ids) != expected_units or len(unit_ids) != len(set(unit_ids)):
            raise ValueError("score summary unit set differs from labels release")
        if summary.get("unit_count") != len(score_records):
            raise ValueError("score summary unit_count differs from unit scores")
    return {
        **dict(identity_mapping),
        "run_identity_sha256": run_identity,
        "model_registry_sha256": registry_identity,
        "models": bindings,
    }


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a 64-character SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a 64-character SHA-256") from exc
    return value.lower()


def _contamination_inputs(
    args: argparse.Namespace,
) -> tuple[Path | None, date | None, str | None]:
    registry_path = cast(Path | None, args.model_registry)
    boundary_raw = cast(str | None, args.contamination_boundary)
    cohort_id = cast(str | None, args.cohort_id)
    provided = (
        registry_path is not None,
        boundary_raw is not None,
        cohort_id is not None,
    )
    if not any(provided):
        return None, None, None
    if not all(provided):
        raise ValueError(
            "--model-registry, --contamination-boundary, and --cohort-id must "
            "be passed together"
        )
    return (
        registry_path,
        date.fromisoformat(cast(str, boundary_raw)),
        cohort_id,
    )
