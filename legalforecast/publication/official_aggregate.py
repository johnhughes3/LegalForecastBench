"""Aggregate isolated official case-job outputs into a public-safe bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.output_parser import parse_model_output
from legalforecast.evals.scorers import ScoreSummary, ScoringCase, score_cases
from legalforecast.labeling.label_outcomes import (
    AmendmentClass,
    LaterProceduralChange,
    OutcomeCitation,
    OutcomeLabel,
)
from legalforecast.protocol.freeze import sha256_file
from legalforecast.reporting.leaderboard import (
    build_benchmark_leaderboard_report,
    summarize_accounting_leaderboard,
)

OFFICIAL_AGGREGATE_SCHEMA_VERSION = "legalforecast-official-aggregate-v1"
PER_CASE_METRICS_SCHEMA_VERSION = "legalforecast.per_case_metrics.v1"

JsonRecord = dict[str, Any]


class OfficialAggregationError(ValueError):
    """Raised when per-case outputs cannot form a complete official bundle."""


@dataclass(frozen=True, slots=True)
class OfficialAggregationConfig:
    """Inputs for aggregating one official evaluation matrix run."""

    per_case_dir: Path
    run_input_manifest_path: Path
    labels_path: Path
    output_dir: Path
    cycle_id: str
    ablation: str | None = None
    generated_at: datetime | None = None
    title: str = "LegalForecastBench Official Results"
    base_rate: float | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_non_empty(self.title, "title")
        if self.ablation is not None:
            _require_non_empty(self.ablation, "ablation")
        if self.generated_at is not None:
            _require_aware_datetime(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class OfficialAggregationResult:
    """Paths and validation facts from an official aggregation."""

    public_dir: Path
    private_debug_dir: Path
    artifact_manifest_path: Path
    leaderboard_path: Path
    run_card_path: Path
    expected_case_count: int
    aggregated_case_count: int


def aggregate_official_results(
    config: OfficialAggregationConfig,
) -> OfficialAggregationResult:
    """Aggregate complete per-case outputs into public and debug bundles."""

    generated_at = config.generated_at or datetime.now(UTC)
    expected_rows = _expected_rows(
        config.run_input_manifest_path,
        config.cycle_id,
        ablation=config.ablation,
    )
    case_outputs = _discover_case_outputs(config.per_case_dir)
    _validate_coverage(expected_rows, case_outputs)

    run_records: list[JsonRecord] = []
    accounting_records: list[JsonRecord] = []
    metrics_records: list[JsonRecord] = []
    for key, expected_row in sorted(expected_rows.items()):
        case_output = case_outputs[key]
        runs = _read_jsonl(case_output / "runs.jsonl")
        accounting = _read_jsonl(case_output / "accounting.jsonl")
        metrics = _read_json_object(case_output / "metrics.json")
        _validate_case_records(
            key,
            expected_row=expected_row,
            runs=runs,
            accounting=accounting,
            metrics=metrics,
            cycle_id=config.cycle_id,
        )
        run_records.extend(runs)
        accounting_records.extend(accounting)
        metrics_records.append(metrics)

    labels = _load_labels(config.labels_path)
    summaries = _score_run_records(
        tuple(run_records),
        labels,
        base_rate=config.base_rate,
    )
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=summarize_accounting_leaderboard(accounting_records),
        title=config.title,
    )

    public_dir = config.output_dir / "public"
    private_debug_dir = config.output_dir / "private-debug"
    public_dir.mkdir(parents=True, exist_ok=True)
    private_debug_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(private_debug_dir / "runs.jsonl", run_records)
    _write_jsonl(private_debug_dir / "accounting.jsonl", accounting_records)
    _write_jsonl(private_debug_dir / "case-metrics.jsonl", metrics_records)

    score_records = [summary.to_record() for summary in summaries]
    _write_json(
        public_dir / "scores.json",
        {
            "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
            "cycle_id": config.cycle_id,
            "generated_at": _format_datetime(generated_at),
            "summaries": score_records,
        },
    )
    _write_jsonl(
        public_dir / "unit-scores.jsonl",
        [
            unit_score.to_record()
            for summary in summaries
            for unit_score in summary.unit_scores
        ],
    )

    report_dir = public_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    leaderboard_path = report_dir / "leaderboard.json"
    _write_json(
        leaderboard_path,
        {
            "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
            "cycle_id": config.cycle_id,
            "generated_at": _format_datetime(generated_at),
            **report.to_record(),
        },
    )
    (report_dir / "leaderboard.csv").write_text(report.to_csv(), encoding="utf-8")
    (report_dir / "leaderboard.md").write_text(report.to_markdown(), encoding="utf-8")
    (report_dir / "leaderboard.html").write_text(report.to_html(), encoding="utf-8")

    run_card_path = public_dir / "run-cards" / "aggregate-run-card.json"
    _write_json(
        run_card_path,
        _aggregate_run_card(
            config=config,
            generated_at=generated_at,
            expected_rows=expected_rows,
            summaries=summaries,
            accounting_records=accounting_records,
        ),
    )
    artifact_manifest_path = _write_public_artifact_manifests(public_dir, generated_at)

    return OfficialAggregationResult(
        public_dir=public_dir,
        private_debug_dir=private_debug_dir,
        artifact_manifest_path=artifact_manifest_path,
        leaderboard_path=leaderboard_path,
        run_card_path=run_card_path,
        expected_case_count=len(expected_rows),
        aggregated_case_count=len({case_id for case_id, _ablation in expected_rows}),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate official per-case outputs into a public-safe bundle."
    )
    parser.add_argument("--per-case-dir", type=Path, required=True)
    parser.add_argument("--run-input-manifest", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--ablation")
    parser.add_argument("--title", default="LegalForecastBench Official Results")
    parser.add_argument("--base-rate", type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = aggregate_official_results(
        OfficialAggregationConfig(
            per_case_dir=cast(Path, args.per_case_dir),
            run_input_manifest_path=cast(Path, args.run_input_manifest),
            labels_path=cast(Path, args.labels),
            output_dir=cast(Path, args.output_dir),
            cycle_id=cast(str, args.cycle_id),
            ablation=cast(str | None, args.ablation),
            title=cast(str, args.title),
            base_rate=cast(float | None, args.base_rate),
        )
    )
    print(
        json.dumps(
            {
                "artifact_manifest": str(result.artifact_manifest_path),
                "leaderboard": str(result.leaderboard_path),
                "run_card": str(result.run_card_path),
                "expected_case_count": result.expected_case_count,
                "aggregated_case_count": result.aggregated_case_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _expected_rows(
    path: Path,
    cycle_id: str,
    *,
    ablation: str | None,
) -> dict[tuple[str, str], JsonRecord]:
    manifest = _read_json_object(path)
    if _required_str(manifest, "cycle_id") != cycle_id:
        raise OfficialAggregationError("run-input manifest cycle_id mismatch")
    rows: dict[tuple[str, str], JsonRecord] = {}
    for row in _record_sequence(manifest, "model_packets"):
        case_id = _required_str(row, "case_id")
        row_ablation = _optional_str(row, "ablation") or "full_packet"
        if ablation is not None and row_ablation != ablation:
            continue
        key = (case_id, row_ablation)
        if key in rows:
            raise OfficialAggregationError(
                f"duplicate run-input row: case_id={case_id}, ablation={row_ablation}"
            )
        rows[key] = row
    if not rows:
        if ablation is None:
            raise OfficialAggregationError("run-input manifest has no model packets")
        raise OfficialAggregationError(
            f"run-input manifest has no model packets for ablation={ablation}"
        )
    return rows


def _discover_case_outputs(root: Path) -> dict[tuple[str, str], Path]:
    outputs: dict[tuple[str, str], Path] = {}
    for runs_path in sorted(root.rglob("runs.jsonl")):
        case_dir = runs_path.parent
        runs = _read_jsonl(runs_path)
        if not runs:
            raise OfficialAggregationError(f"empty runs artifact: {runs_path}")
        case_id = _required_str(runs[0], "case_id")
        ablation = _optional_str(runs[0], "ablation") or "full_packet"
        key = (case_id, ablation)
        if key in outputs:
            raise OfficialAggregationError(
                f"duplicate per-case output: case_id={case_id}, ablation={ablation}"
            )
        outputs[key] = case_dir
    return outputs


def _validate_coverage(
    expected_rows: Mapping[tuple[str, str], JsonRecord],
    case_outputs: Mapping[tuple[str, str], Path],
) -> None:
    expected = set(expected_rows)
    actual = set(case_outputs)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise OfficialAggregationError(f"missing per-case outputs: {missing}")
    if extra:
        raise OfficialAggregationError(f"unexpected per-case outputs: {extra}")


def _validate_case_records(
    key: tuple[str, str],
    *,
    expected_row: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    accounting: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    cycle_id: str,
) -> None:
    if not runs:
        raise OfficialAggregationError(f"case output has no runs: {key}")
    if not accounting:
        raise OfficialAggregationError(f"case output has no accounting: {key}")
    _validate_metrics_record(
        key,
        expected_row=expected_row,
        metrics=metrics,
        cycle_id=cycle_id,
        run_count=len(runs),
    )
    for record in runs:
        _validate_common_case_fields(key, record)
        _validate_run_raw_output_hash(record)
    for record in accounting:
        _validate_common_case_fields(key, record)
    _validate_metrics_hashes(key, metrics, runs)
    _validate_accounting_hashes(key, runs, accounting)


def _validate_common_case_fields(
    key: tuple[str, str],
    record: Mapping[str, Any],
) -> None:
    case_id, ablation = key
    if _required_str(record, "case_id") != case_id:
        raise OfficialAggregationError(f"case_id mismatch in output: {key}")
    record_ablation = _optional_str(record, "ablation") or _optional_str(
        record,
        "run_label",
    )
    if record_ablation is not None and record_ablation != ablation:
        raise OfficialAggregationError(f"ablation mismatch in output: {key}")


def _validate_metrics_record(
    key: tuple[str, str],
    *,
    expected_row: Mapping[str, Any],
    metrics: Mapping[str, Any],
    cycle_id: str,
    run_count: int,
) -> None:
    _case_id, ablation = key
    if _required_str(metrics, "schema_version") != PER_CASE_METRICS_SCHEMA_VERSION:
        raise OfficialAggregationError(f"metrics schema mismatch in output: {key}")
    if _required_str(metrics, "cycle_id") != cycle_id:
        raise OfficialAggregationError(f"metrics cycle_id mismatch in output: {key}")
    _validate_common_case_fields(key, metrics)
    if _required_int(metrics, "run_record_count") != run_count:
        raise OfficialAggregationError(f"metrics run count mismatch in output: {key}")

    expected_object_key = _optional_str(expected_row, "object_key") or _optional_str(
        expected_row,
        "packet_object_key",
    )
    if expected_object_key is not None:
        actual_object_key = _required_str(metrics, "packet_object_key")
        if actual_object_key != expected_object_key:
            raise OfficialAggregationError(
                f"packet object key mismatch in output: {key}"
            )

    expected_sha256 = _optional_str(expected_row, "sha256")
    if expected_sha256 is not None:
        _require_hex_sha256(expected_sha256, "run-input sha256")
        actual_sha256 = _required_str(metrics, "packet_sha256")
        _require_hex_sha256(actual_sha256, "metrics packet_sha256")
        if actual_sha256 != expected_sha256:
            raise OfficialAggregationError(f"packet SHA-256 mismatch in output: {key}")

    if _required_str(metrics, "ablation") != ablation:
        raise OfficialAggregationError(f"metrics ablation mismatch in output: {key}")


def _validate_run_raw_output_hash(record: Mapping[str, Any]) -> None:
    raw_output = _required_str(record, "raw_output")
    expected = _required_str(record, "raw_output_sha256")
    actual = _sha256_prefixed(raw_output)
    if expected != actual:
        raise OfficialAggregationError(
            f"raw_output_sha256 mismatch for case_id={_required_str(record, 'case_id')}"
        )


def _validate_metrics_hashes(
    key: tuple[str, str],
    metrics: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
) -> None:
    run_hashes = sorted(_required_str(record, "raw_output_sha256") for record in runs)
    metric_hashes = sorted(
        _required_str_value(value) for value in _list(metrics, "raw_output_sha256")
    )
    if metric_hashes != run_hashes:
        raise OfficialAggregationError(
            f"metrics raw_output_sha256 values mismatch in output: {key}"
        )


def _validate_accounting_hashes(
    key: tuple[str, str],
    runs: Sequence[Mapping[str, Any]],
    accounting: Sequence[Mapping[str, Any]],
) -> None:
    run_hashes = {_required_str(record, "raw_output_sha256") for record in runs}
    accounting_hashes = {
        _required_str(record, "raw_output_sha256") for record in accounting
    }
    missing = sorted(run_hashes - accounting_hashes)
    extra = sorted(accounting_hashes - run_hashes)
    if missing:
        raise OfficialAggregationError(
            f"accounting missing raw_output_sha256 values for {key}: {missing}"
        )
    if extra:
        raise OfficialAggregationError(
            f"accounting has unexpected raw_output_sha256 values for {key}: {extra}"
        )


def _score_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    base_rate: float | None,
) -> tuple[ScoreSummary, ...]:
    if not run_records:
        raise OfficialAggregationError("at least one run record is required")
    labels_by_unit_id = {label.unit_id: label for label in labels}
    effective_base_rate = (
        _computed_base_rate(labels) if base_rate is None else base_rate
    )

    cases_by_model: dict[str, list[ScoringCase]] = defaultdict(list)
    for record in run_records:
        required_unit_ids = tuple(
            _required_str_value(value) for value in _list(record, "required_unit_ids")
        )
        missing_labels = sorted(set(required_unit_ids) - set(labels_by_unit_id))
        if missing_labels:
            raise OfficialAggregationError(
                f"labels missing for required units: {missing_labels}"
            )
        model_id = _optional_str(record, "model_id") or _required_str(
            record, "solver_id"
        )
        parsed = parse_model_output(
            _required_str(record, "raw_output"),
            required_unit_ids=required_unit_ids,
        )
        cases_by_model[model_id].append(
            ScoringCase(
                case_id=_required_str(record, "case_id"),
                candidate_id=_optional_str(record, "candidate_id"),
                model_id=model_id,
                related_family_id=_optional_str(record, "related_family_id"),
                mdl_family_id=_optional_str(record, "mdl_family_id"),
                parsed_output=parsed,
                outcome_labels=tuple(
                    labels_by_unit_id[unit_id] for unit_id in required_unit_ids
                ),
            )
        )
    return tuple(
        score_cases(tuple(cases), base_rate=effective_base_rate)
        for _model_id, cases in sorted(cases_by_model.items())
    )


def _computed_base_rate(labels: Sequence[OutcomeLabel]) -> float:
    outcomes = [
        label.primary_outcome for label in labels if label.primary_outcome is not None
    ]
    if not outcomes:
        raise OfficialAggregationError("at least one non-ambiguous label is required")
    return sum(outcomes) / len(outcomes)


def _load_labels(path: Path) -> tuple[OutcomeLabel, ...]:
    labels = tuple(_outcome_label(record) for record in _read_jsonl(path))
    if not labels:
        raise OfficialAggregationError("labels file must not be empty")
    return labels


def _outcome_label(record: Mapping[str, Any]) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=_required_str(record, "unit_id"),
        fully_dismissed=_optional_bool(record, "fully_dismissed"),
        amendment_class=AmendmentClass(_required_str(record, "amendment_class")),
        ambiguous=_required_bool(record, "ambiguous"),
        label_confidence=_required_float(record, "label_confidence"),
        supporting_citations=tuple(
            _outcome_citation(citation)
            for citation in _record_sequence(record, "supporting_citations")
        ),
        first_written_disposition_id=_required_str(
            record, "first_written_disposition_id"
        ),
        first_written_disposition_date=_required_str(
            record, "first_written_disposition_date"
        ),
        first_written_disposition_locked=_optional_bool_default(
            record,
            "first_written_disposition_locked",
            default=True,
        ),
        later_procedural_changes=tuple(
            LaterProceduralChange(_required_str_value(change))
            for change in _list(record, "later_procedural_changes", default=())
        ),
        notes=_optional_str(record, "notes"),
    )


def _outcome_citation(record: Mapping[str, Any]) -> OutcomeCitation:
    return OutcomeCitation(
        document_id=_required_str(record, "document_id"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _aggregate_run_card(
    *,
    config: OfficialAggregationConfig,
    generated_at: datetime,
    expected_rows: Mapping[tuple[str, str], JsonRecord],
    summaries: Sequence[ScoreSummary],
    accounting_records: Sequence[Mapping[str, Any]],
) -> JsonRecord:
    return {
        "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "run_type": "official",
        "ablation_filter": config.ablation,
        "generated_at": _format_datetime(generated_at),
        "expected_matrix_rows": len(expected_rows),
        "case_count": len({case_id for case_id, _ablation in expected_rows}),
        "ablation_count": len({_ablation for _case_id, _ablation in expected_rows}),
        "model_count": len(summaries),
        "accounting_record_count": len(accounting_records),
        "public_outputs": [
            "scores.json",
            "unit-scores.jsonl",
            "report/leaderboard.json",
            "report/leaderboard.csv",
            "report/leaderboard.md",
            "report/leaderboard.html",
        ],
        "private_debug_outputs": [
            "runs.jsonl",
            "accounting.jsonl",
            "case-metrics.jsonl",
        ],
        "notes": [
            "Raw per-case model outputs are kept under private-debug.",
            "Public outputs contain scores, aggregate diagnostics, and hashes.",
        ],
    }


def _write_public_artifact_manifests(public_dir: Path, generated_at: datetime) -> Path:
    artifact_records: list[JsonRecord] = []
    for path in sorted(public_dir.rglob("*")):
        if not path.is_file() or path.name in {
            "artifact-index.json",
            "artifact-manifest.json",
        }:
            continue
        relative_path = path.relative_to(public_dir).as_posix()
        artifact_records.append(
            {
                "path": relative_path,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "bundle_role": _bundle_role(relative_path),
            }
        )
    index = {
        "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
        "generated_at": _format_datetime(generated_at),
        "artifact_count": len(artifact_records),
        "artifacts": artifact_records,
    }
    manifest = {
        "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
        "generated_at": _format_datetime(generated_at),
        "artifacts": [record["path"] for record in artifact_records],
    }
    _write_json(public_dir / "artifact-index.json", index)
    manifest_path = public_dir / "artifact-manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _bundle_role(relative_path: str) -> str:
    if relative_path.startswith("report/"):
        return "leaderboard_report"
    if relative_path.startswith("run-cards/"):
        return "run_card"
    if relative_path == "scores.json":
        return "score_summary"
    if relative_path == "unit-scores.jsonl":
        return "unit_scores"
    return "official_artifact"


def _read_jsonl(path: Path) -> list[JsonRecord]:
    if not path.is_file():
        raise OfficialAggregationError(f"JSONL artifact missing: {path}")
    records: list[JsonRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise OfficialAggregationError(
                    f"{path} line {line_number} is not an object"
                )
            records.append(cast(JsonRecord, value))
    return records


def _read_json_object(path: Path) -> JsonRecord:
    if not path.is_file():
        raise OfficialAggregationError(f"JSON artifact missing: {path}")
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OfficialAggregationError(f"{path} is not a JSON object")
    return cast(JsonRecord, value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(record), sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _record_sequence(
    record: Mapping[str, Any], field_name: str
) -> tuple[JsonRecord, ...]:
    value = record.get(field_name)
    if not isinstance(value, list):
        raise OfficialAggregationError(f"{field_name} must be a list")
    records: list[JsonRecord] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise OfficialAggregationError(f"{field_name} must contain objects")
        records.append(cast(JsonRecord, item))
    return tuple(records)


def _sha256_prefixed(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _list(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: Sequence[object] | None = None,
) -> tuple[object, ...]:
    value = record.get(field_name, default)
    if value is None:
        raise OfficialAggregationError(f"{field_name} must be a list")
    if not isinstance(value, list | tuple):
        raise OfficialAggregationError(f"{field_name} must be a list")
    return tuple(cast(Sequence[object], value))


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    return _required_str_value(value)


def _required_str_value(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OfficialAggregationError("required string field is missing")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    return _required_str_value(value)


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise OfficialAggregationError(f"{field_name} must be a boolean")
    return value


def _optional_bool(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool | None = None,
) -> bool | None:
    value = record.get(field_name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise OfficialAggregationError(f"{field_name} must be a boolean")
    return value


def _optional_bool_default(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool,
) -> bool:
    value = _optional_bool(record, field_name, default=default)
    if value is None:
        return default
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise OfficialAggregationError(f"{field_name} must be an integer")
    return value


def _required_float(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OfficialAggregationError(f"{field_name} must be numeric")
    return float(value)


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise OfficialAggregationError(f"{field_name} must be an integer")
    return value


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_hex_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OfficialAggregationError(f"{field_name} must be a lowercase SHA-256 hex")


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
