"""Aggregate isolated official case-job outputs into a public-safe bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast._hashing import is_lowercase_sha256
from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.evals.baselines import (
    BaselineId,
    BaselinePrediction,
    BaselineSuite,
    BaselineTrainingExample,
    BaselineUnitFeatures,
    fit_baseline_suite_from_training_examples,
    load_baseline_training_examples,
)
from legalforecast.evals.bootstrap import (
    BootstrapInferenceResult,
    ModelScoreInput,
    paired_clustered_bootstrap,
)
from legalforecast.evals.model_registry import ModelRegistryEntry, load_model_registry
from legalforecast.evals.output_parser import parse_model_output
from legalforecast.evals.response_verification import (
    RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD,
    RESPONSE_RETRYABLE_OPS_EVENT_FIELD,
    RESPONSE_VERIFICATION_SCHEMA_FIELD,
    RESPONSE_VERIFICATION_SCHEMA_VERSION,
)
from legalforecast.evals.scorers import (
    ScoreSummary,
    ScoringCase,
    brier_score,
    score_cases,
)
from legalforecast.labeling.label_outcomes import (
    AmendmentClass,
    LaterProceduralChange,
    OutcomeCitation,
    OutcomeLabel,
    UnitResolution,
)
from legalforecast.protocol.freeze import sha256_file
from legalforecast.publication.dispatch_provenance import (
    DispatchProvenanceError,
    load_dispatch_provenance,
)
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)
from legalforecast.reporting.cadence import (
    DEFAULT_PAIRED_DELTA_SD,
    DEFAULT_POWER,
    DEFAULT_TARGET_MDE,
    DEFAULT_TWO_SIDED_ALPHA,
    CyclePowerInput,
    CyclePowerReport,
    CycleSeries,
    classify_cycle_power,
)
from legalforecast.reporting.leaderboard import (
    AccountingLeaderboardRow,
    build_benchmark_leaderboard_report,
    summarize_accounting_leaderboard,
)

OFFICIAL_AGGREGATE_SCHEMA_VERSION = "legalforecast-official-aggregate-v1"
PER_CASE_METRICS_SCHEMA_VERSION = "legalforecast.per_case_metrics.v1"
_PACKET_TOKEN_FIELDS = (
    "estimated_input_tokens",
    "input_tokens",
    "prompt_tokens",
    "estimated_prompt_tokens",
    "packet_token_count",
    "token_count",
)
_PACKET_SIZE_FIELDS = ("packet_size_bytes", "size_bytes")
_TOKEN_ESTIMATE_BYTES_PER_TOKEN = 4
_PACKET_TOKEN_ESTIMATOR = (
    "manifest input/prompt token counts; fallback ceil(packet_size_bytes / 4)"
)
_TEMPERATURE_ZERO_RATIONALE = (
    "Official runs set registry temperature to 0 to reduce avoidable sampling "
    "variance and make prompt/context differences easier to audit. Provider-side "
    "nondeterminism is still possible and should be measured with the repeat "
    "sampling protocol."
)

JsonRecord = dict[str, Any]
PacketKey = tuple[str, str]
OutputKey = tuple[str, str, str]


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
    cycle_series: CycleSeries
    clean_motion_count: int
    prediction_unit_count: int
    model_registry_path: Path | None = None
    dispatch_provenance_path: Path | None = None
    baseline_training_examples_path: Path | None = None
    model_keys: tuple[str, ...] = ()
    allow_incomplete_model_set: bool = False
    allow_no_baselines: bool = False
    deferred_ablations: tuple[str, ...] = ()
    ablation: str | None = None
    generated_at: datetime | None = None
    title: str = "LegalForecastBench Official Results"
    base_rate: float | None = None
    elapsed_days: int | None = None
    official_window_days: int | None = None
    paired_delta_sd: float | None = None
    target_mde: float = DEFAULT_TARGET_MDE
    target_power: float = DEFAULT_POWER
    two_sided_alpha: float = DEFAULT_TWO_SIDED_ALPHA

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_non_empty(self.title, "title")
        if self.ablation is not None:
            _require_non_empty(self.ablation, "ablation")
        for model_key in self.model_keys:
            _require_non_empty(model_key, "model_keys")
            if ":" not in model_key:
                raise ValueError("model_keys must use provider:model_id")
        if self.generated_at is not None:
            _require_aware_datetime(self.generated_at, "generated_at")
        CyclePowerInput(
            cycle_id=self.cycle_id,
            series=self.cycle_series,
            clean_motion_count=self.clean_motion_count,
            prediction_unit_count=self.prediction_unit_count,
            elapsed_days=self.elapsed_days,
            official_window_days=self.official_window_days,
            paired_delta_sd=(
                self.paired_delta_sd
                if self.paired_delta_sd is not None
                else DEFAULT_PAIRED_DELTA_SD
            ),
            target_mde=self.target_mde,
            target_power=self.target_power,
            two_sided_alpha=self.two_sided_alpha,
        )


@dataclass(frozen=True, slots=True)
class OfficialAggregationResult:
    """Paths and validation facts from an official aggregation."""

    public_dir: Path
    private_debug_dir: Path
    artifact_manifest_path: Path
    cycle_power_path: Path
    leaderboard_path: Path
    run_card_path: Path
    expected_matrix_row_count: int
    aggregated_matrix_row_count: int
    expected_case_count: int
    aggregated_case_count: int
    model_count: int


@dataclass(frozen=True, slots=True)
class _CyclePowerInputResolution:
    cycle_input: CyclePowerInput
    paired_delta_sd_source: str
    warning: str | None = None


@dataclass(slots=True)
class _AccountingTotals:
    """Public-safe accounting totals for one model."""

    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_call_count: int = 0
    allowed_tool_call_count: int = 0
    denied_tool_call_count: int = 0

    def add(self, record: Mapping[str, Any]) -> None:
        self.request_count += _required_int(record, "request_count")
        self.prompt_tokens += _required_int(record, "prompt_tokens")
        self.completion_tokens += _required_int(record, "completion_tokens")
        self.total_tokens += _required_int(record, "total_tokens")
        self.tool_call_count += _required_int(record, "tool_call_count")
        self.allowed_tool_call_count += _required_int(
            record,
            "allowed_tool_call_count",
        )
        self.denied_tool_call_count += _required_int(
            record,
            "denied_tool_call_count",
        )


@dataclass(frozen=True, slots=True)
class _BaselineAggregateArtifacts:
    run_records: tuple[JsonRecord, ...] = ()
    accounting_records: tuple[JsonRecord, ...] = ()
    prediction_records: tuple[JsonRecord, ...] = ()
    training_period: Mapping[str, str] | None = None


def aggregate_official_results(
    config: OfficialAggregationConfig,
) -> OfficialAggregationResult:
    """Aggregate complete per-case outputs into public and debug bundles."""

    generated_at = config.generated_at or datetime.now(UTC)
    expected_packet_rows = _expected_rows(
        config.run_input_manifest_path,
        config.cycle_id,
        ablation=config.ablation,
    )
    case_outputs = _discover_case_outputs(config.per_case_dir)
    registry_entries = _registry_entries(config)
    expected_model_keys, registry_model_keys = _expected_model_key_sets(
        config,
        registry_entries=registry_entries,
    )
    dispatch_provenance = _dispatch_provenance(
        config,
        expected_model_keys=expected_model_keys,
    )
    packet_token_budget = _packet_token_budget_record(
        expected_packet_rows,
        registry_entries=registry_entries,
    )
    expected_rows = _expected_output_rows(
        expected_packet_rows,
        case_outputs=case_outputs,
        model_keys=expected_model_keys,
    )
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

    labels_sha256 = _labels_frozen_sha256(
        config.run_input_manifest_path,
        labels_path=config.labels_path,
    )
    labels = _load_labels(config.labels_path)
    cycle_baseline_training_examples = _cycle_baseline_training_examples(
        expected_packet_rows,
        labels,
    )
    baseline_artifacts = _baseline_aggregate_artifacts(
        config,
        expected_packet_rows=expected_packet_rows,
        generated_at=generated_at,
    )
    run_records.extend(baseline_artifacts.run_records)
    accounting_records.extend(baseline_artifacts.accounting_records)
    primary_run_records = _primary_run_records(run_records)
    multi_ablation_bundle = len(_ablations_in_run_records(primary_run_records)) > 1
    repeat_variance_report = _repeat_variance_report(
        tuple(run_records),
        labels,
        cycle_id=config.cycle_id,
        generated_at=generated_at,
    )
    ablation_delta_report = _ablation_delta_report(
        primary_run_records,
        labels,
        cycle_id=config.cycle_id,
        generated_at=generated_at,
        base_rate=config.base_rate,
    )
    summaries = _score_run_records(
        primary_run_records,
        labels,
        base_rate=config.base_rate,
        include_ablation_in_model_id=multi_ablation_bundle,
    )
    inference = _official_bootstrap_inference(summaries)
    accounting_rows = summarize_accounting_leaderboard(accounting_records)
    report_accounting_rows = _accounting_rows_for_report(
        accounting_rows,
        include_ablation_in_model_id=multi_ablation_bundle,
    )
    report = build_benchmark_leaderboard_report(
        summaries,
        accounting_rows=report_accounting_rows,
        inference=inference,
        repeat_variance_rows=_repeat_variance_summary_rows(repeat_variance_report),
        title=config.title,
    )
    cycle_power_inputs = _cycle_power_input(
        config,
        inference=inference,
        repeat_variance_report=repeat_variance_report,
    )
    cycle_power = classify_cycle_power(cycle_power_inputs.cycle_input)
    cycle_power_record = _cycle_power_record(
        cycle_power,
        config=config,
        paired_delta_sd_source=cycle_power_inputs.paired_delta_sd_source,
        warning=cycle_power_inputs.warning,
    )

    public_dir = config.output_dir / "public"
    private_debug_dir = config.output_dir / "private-debug"
    public_dir.mkdir(parents=True, exist_ok=True)
    private_debug_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(private_debug_dir / "runs.jsonl", run_records)
    _write_jsonl(private_debug_dir / "accounting.jsonl", accounting_records)
    _write_jsonl(private_debug_dir / "case-metrics.jsonl", metrics_records)
    if baseline_artifacts.prediction_records:
        _write_jsonl(
            private_debug_dir / "baseline-predictions.jsonl",
            baseline_artifacts.prediction_records,
        )
    if cycle_baseline_training_examples:
        _write_jsonl(
            public_dir / "baseline-training-examples.jsonl",
            [example.to_record() for example in cycle_baseline_training_examples],
        )

    score_records = _score_records_with_accounting(
        summaries,
        accounting_rows=accounting_rows,
        accounting_records=accounting_records,
        include_ablation_in_model_id=multi_ablation_bundle,
    )
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
    cycle_power_path = public_dir / "cycle-power.json"
    _write_json(
        cycle_power_path,
        {
            "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
            "cycle_id": config.cycle_id,
            "generated_at": _format_datetime(generated_at),
            "cycle_power": cycle_power_record,
        },
    )
    variance_dir = public_dir / "variance"
    variance_dir.mkdir(parents=True, exist_ok=True)
    _write_json(variance_dir / "repeat-sampling.json", repeat_variance_report)
    if ablation_delta_report["rows"]:
        _write_json(public_dir / "ablation-deltas.json", ablation_delta_report)

    report_dir = public_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    leaderboard_path = report_dir / "leaderboard.json"
    _write_json(
        leaderboard_path,
        {
            "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
            "cycle_id": config.cycle_id,
            "generated_at": _format_datetime(generated_at),
            "cycle_power": cycle_power_record,
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
            expected_model_keys=expected_model_keys,
            registry_model_keys=registry_model_keys,
            dispatch_provenance=dispatch_provenance,
            packet_token_budget=packet_token_budget,
            summaries=summaries,
            accounting_records=accounting_records,
            cycle_power_record=cycle_power_record,
            baseline_artifacts=baseline_artifacts,
            cycle_baseline_training_example_count=(
                len(cycle_baseline_training_examples)
            ),
            ablation_delta_count=len(ablation_delta_report["rows"]),
            repeat_variance_report=repeat_variance_report,
            labels_sha256=labels_sha256,
        ),
    )
    enforce_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(public_dir,))
    )
    artifact_manifest_path = _write_public_artifact_manifests(public_dir, generated_at)

    return OfficialAggregationResult(
        public_dir=public_dir,
        private_debug_dir=private_debug_dir,
        artifact_manifest_path=artifact_manifest_path,
        cycle_power_path=cycle_power_path,
        leaderboard_path=leaderboard_path,
        run_card_path=run_card_path,
        expected_matrix_row_count=len(expected_rows),
        aggregated_matrix_row_count=len(case_outputs),
        expected_case_count=len(
            {case_id for case_id, _ablation in expected_packet_rows}
        ),
        aggregated_case_count=len(
            {case_id for case_id, _ablation, _model in case_outputs}
        ),
        model_count=len({_model for _case_id, _ablation, _model in expected_rows}),
    )


def _score_records_with_accounting(
    summaries: Sequence[ScoreSummary],
    *,
    accounting_rows: Sequence[AccountingLeaderboardRow],
    accounting_records: Sequence[Mapping[str, Any]],
    include_ablation_in_model_id: bool = False,
) -> list[JsonRecord]:
    rows_by_model = _accounting_rows_by_model(
        accounting_rows,
        include_ablation_in_model_id=include_ablation_in_model_id,
    )
    totals_by_model = _accounting_totals_by_model(
        accounting_records,
        include_ablation_in_model_id=include_ablation_in_model_id,
    )
    reference_summary = _baseline_reference_summary(summaries)
    score_records: list[JsonRecord] = []
    for summary in summaries:
        row = rows_by_model.get(summary.model_id)
        totals = totals_by_model.get(summary.model_id)
        if row is None or totals is None:
            raise OfficialAggregationError(
                f"accounting summary missing for model_id={summary.model_id}"
            )
        record = summary.to_record()
        record["row_type"] = _score_row_type(summary.model_id)
        record.update(_public_accounting_fields(row, totals))
        record.update(_reference_skill_fields(summary, reference_summary))
        score_records.append(record)
    return score_records


def _score_row_type(model_id: str) -> str:
    base_model_id = model_id.split("::", maxsplit=1)[0]
    if base_model_id in {baseline.value for baseline in BaselineId}:
        return "baseline"
    return "model"


def _accounting_rows_by_model(
    accounting_rows: Sequence[AccountingLeaderboardRow],
    *,
    include_ablation_in_model_id: bool = False,
) -> dict[str, AccountingLeaderboardRow]:
    rows_by_model: dict[str, AccountingLeaderboardRow] = {}
    for row in accounting_rows:
        model_id = _display_model_id(
            row.model_id,
            _ablation_label(row.run_label),
            include_ablation=include_ablation_in_model_id,
        )
        if model_id in rows_by_model:
            raise OfficialAggregationError(
                f"multiple accounting summaries for model_id={model_id}"
            )
        rows_by_model[model_id] = row
    return rows_by_model


def _accounting_rows_for_report(
    accounting_rows: Sequence[AccountingLeaderboardRow],
    *,
    include_ablation_in_model_id: bool,
) -> tuple[AccountingLeaderboardRow, ...]:
    if not include_ablation_in_model_id:
        return tuple(accounting_rows)
    return tuple(
        replace(
            row,
            model_id=_display_model_id(
                row.model_id,
                _ablation_label(row.run_label),
                include_ablation=True,
            ),
        )
        for row in accounting_rows
    )


def _accounting_totals_by_model(
    accounting_records: Sequence[Mapping[str, Any]],
    *,
    include_ablation_in_model_id: bool = False,
) -> dict[str, _AccountingTotals]:
    totals_by_model: dict[str, _AccountingTotals] = {}
    for record in accounting_records:
        model_id = _display_model_id(
            _required_str(record, "model_id"),
            _record_ablation(record),
            include_ablation=include_ablation_in_model_id,
        )
        totals = totals_by_model.setdefault(model_id, _AccountingTotals())
        totals.add(record)
    return totals_by_model


def _public_accounting_fields(
    row: AccountingLeaderboardRow,
    totals: _AccountingTotals,
) -> JsonRecord:
    return {
        "solver_id": row.solver_id,
        "provider": row.provider,
        "model_version_or_snapshot": row.model_version_or_snapshot,
        "run_label": row.run_label,
        "run_count": row.run_count,
        "request_count": totals.request_count,
        "prompt_tokens": totals.prompt_tokens,
        "completion_tokens": totals.completion_tokens,
        "total_tokens": totals.total_tokens,
        "tool_call_count": totals.tool_call_count,
        "allowed_tool_call_count": totals.allowed_tool_call_count,
        "denied_tool_call_count": totals.denied_tool_call_count,
        "mean_tool_calls_per_case": row.mean_tool_calls_per_case,
        "median_tool_calls_per_case": row.median_tool_calls_per_case,
        "p95_tool_calls_per_case": row.p95_tool_calls_per_case,
        "mean_latency_ms": row.mean_latency_ms,
        "p95_latency_ms": row.p95_latency_ms,
        "total_estimated_cost": row.total_estimated_cost,
        "cost_per_case": row.cost_per_case,
        "cost_per_prediction_unit": row.cost_per_prediction_unit,
        "content_filter_rate": row.content_filter_rate,
    }


def _ablations_in_run_records(
    run_records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    return tuple(sorted({_record_ablation(record) for record in run_records}))


def _record_ablation(record: Mapping[str, Any]) -> str:
    return (
        _optional_str(record, "ablation")
        or _optional_str(record, "run_label")
        or "full_packet"
    )


def _ablation_label(value: str | None) -> str:
    return value or "full_packet"


def _display_model_id(
    model_id: str,
    ablation: str,
    *,
    include_ablation: bool,
) -> str:
    return f"{model_id}::{ablation}" if include_ablation else model_id


def _baseline_aggregate_artifacts(
    config: OfficialAggregationConfig,
    *,
    expected_packet_rows: Mapping[PacketKey, JsonRecord],
    generated_at: datetime,
) -> _BaselineAggregateArtifacts:
    if config.baseline_training_examples_path is None:
        if not config.allow_no_baselines:
            raise OfficialAggregationError(
                "baseline_training_examples_path is required for official "
                "aggregation; pass --allow-no-baselines only for partial/debug "
                "or explicitly disclosed first-cycle bundles"
            )
        return _BaselineAggregateArtifacts()
    training_examples = load_baseline_training_examples(
        config.baseline_training_examples_path
    )
    suite = fit_baseline_suite_from_training_examples(training_examples)
    run_records: list[JsonRecord] = []
    accounting_records: list[JsonRecord] = []
    prediction_records: list[JsonRecord] = []
    features_for_usage: list[BaselineUnitFeatures] = []
    for (case_id, ablation), row in sorted(expected_packet_rows.items()):
        features = _baseline_features_for_packet_row(row, case_id=case_id)
        features_for_usage.extend(features)
        prediction_sets = tuple(suite.predict(feature) for feature in features)
        for baseline_id in _scored_baseline_ids():
            predictions = tuple(
                prediction_set.prediction_for(baseline_id)
                for prediction_set in prediction_sets
            )
            run_record = _baseline_run_record(
                row,
                case_id=case_id,
                ablation=ablation,
                baseline_id=baseline_id,
                predictions=predictions,
                suite=suite,
                generated_at=generated_at,
            )
            run_records.append(run_record)
            accounting_records.append(
                _baseline_accounting_record(
                    run_record,
                    baseline_id=baseline_id,
                    suite=suite,
                    generated_at=generated_at,
                )
            )
            prediction_records.append(
                {
                    "case_id": case_id,
                    "candidate_id": _optional_str(row, "candidate_id"),
                    "ablation": ablation,
                    "baseline_id": baseline_id.value,
                    "training_period": suite.training_period_record(),
                    "predictions": [
                        prediction.to_record() for prediction in predictions
                    ],
                }
            )
    usage = suite.judge_history_usage_summary(tuple(features_for_usage))
    return _BaselineAggregateArtifacts(
        run_records=tuple(run_records),
        accounting_records=tuple(accounting_records),
        prediction_records=tuple(prediction_records),
        training_period=suite.training_period_record()
        | {"judge_history_usage": json.dumps(usage.to_record(), sort_keys=True)},
    )


def _cycle_baseline_training_examples(
    expected_packet_rows: Mapping[PacketKey, JsonRecord],
    labels: Sequence[OutcomeLabel],
) -> tuple[BaselineTrainingExample, ...]:
    labels_by_unit = {label.unit_id: label for label in labels}
    examples: list[BaselineTrainingExample] = []
    seen_unit_ids: set[str] = set()
    for (case_id, _ablation), row in sorted(expected_packet_rows.items()):
        if "baseline_features" not in row:
            continue
        for features in _baseline_features_for_packet_row(row, case_id=case_id):
            label = labels_by_unit.get(features.unit_id)
            if label is None or label.fully_dismissed is None:
                continue
            if features.unit_id in seen_unit_ids:
                continue
            seen_unit_ids.add(features.unit_id)
            examples.append(
                BaselineTrainingExample(
                    features=features,
                    fully_dismissed=label.fully_dismissed,
                    decision_date=_label_decision_date(label),
                )
            )
    return tuple(examples)


def _label_decision_date(label: OutcomeLabel) -> date:
    try:
        return date.fromisoformat(label.first_written_disposition_date)
    except ValueError as exc:
        raise OfficialAggregationError(
            "baseline training export requires ISO decision dates in labels"
        ) from exc


def _scored_baseline_ids() -> tuple[BaselineId, ...]:
    return (
        BaselineId.GLOBAL_BASE_RATE,
        BaselineId.COURT_NOS_MOTION_BASE_RATE,
        BaselineId.METADATA_ONLY,
        BaselineId.JUDGE_HISTORY,
    )


def _baseline_features_for_packet_row(
    row: Mapping[str, Any],
    *,
    case_id: str,
) -> tuple[BaselineUnitFeatures, ...]:
    baseline_features = row.get("baseline_features")
    if isinstance(baseline_features, Sequence) and not isinstance(
        baseline_features,
        str | bytes,
    ):
        features = tuple(
            BaselineUnitFeatures.from_record(_mapping(item, "baseline_features"))
            for item in cast(Sequence[object], baseline_features)
        )
        if not features:
            raise OfficialAggregationError("baseline_features must not be empty")
        return features

    metadata = _metadata_mapping(row)
    unit_ids = _baseline_unit_ids(row)
    return tuple(
        BaselineUnitFeatures(
            unit_id=unit_id,
            case_id=case_id,
            court=_baseline_required_str(row, metadata, "court"),
            district=_baseline_required_str(row, metadata, "district"),
            circuit=_baseline_required_str(row, metadata, "circuit"),
            nos_macro_category=_baseline_required_str(
                row,
                metadata,
                "nos_macro_category",
            ),
            motion_type=_baseline_required_str(row, metadata, "motion_type"),
            judge_id=_baseline_optional_str(row, metadata, "judge_id")
            or _baseline_optional_str(row, metadata, "judge"),
            represented_party_status=_baseline_optional_str(
                row,
                metadata,
                "represented_party_status",
            ),
            government_party_status=_baseline_optional_str(
                row,
                metadata,
                "government_party_status",
            ),
            claim_count=_baseline_optional_int(row, metadata, "claim_count"),
            defendant_count=_baseline_optional_int(row, metadata, "defendant_count"),
            motion_length_tokens=_baseline_optional_int(
                row,
                metadata,
                "motion_length_tokens",
            ),
            complaint_length_tokens=_baseline_optional_int(
                row,
                metadata,
                "complaint_length_tokens",
            ),
            case_age_days=_baseline_optional_int(row, metadata, "case_age_days"),
            docket_entry_count=_baseline_optional_int(
                row,
                metadata,
                "docket_entry_count",
            ),
        )
        for unit_id in unit_ids
    )


def _baseline_unit_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    required_unit_ids = row.get("required_unit_ids")
    if isinstance(required_unit_ids, Sequence) and not isinstance(
        required_unit_ids,
        str | bytes,
    ):
        return tuple(
            _required_str_value(value)
            for value in cast(Sequence[object], required_unit_ids)
        )
    prediction_units = row.get("prediction_units")
    if isinstance(prediction_units, Sequence) and not isinstance(
        prediction_units,
        str | bytes,
    ):
        unit_ids: list[str] = []
        for item in cast(Sequence[object], prediction_units):
            unit = _mapping(item, "prediction_units")
            if _optional_bool_default(unit, "should_score", default=True):
                unit_ids.append(_required_str(unit, "unit_id"))
        if unit_ids:
            return tuple(unit_ids)
    raise OfficialAggregationError(
        "baseline scoring requires required_unit_ids, prediction_units, or "
        "baseline_features in each run-input manifest row"
    )


def _baseline_run_record(
    row: Mapping[str, Any],
    *,
    case_id: str,
    ablation: str,
    baseline_id: BaselineId,
    predictions: Sequence[BaselinePrediction],
    suite: BaselineSuite,
    generated_at: datetime,
) -> JsonRecord:
    required_unit_ids = tuple(prediction.unit_id for prediction in predictions)
    raw_output = _baseline_raw_output(baseline_id, predictions)
    raw_output_sha256 = _sha256_prefixed(raw_output)
    model_id = baseline_id.value
    return {
        "sample_id": f"{case_id}-{ablation}-{model_id}",
        "candidate_id": _optional_str(row, "candidate_id"),
        "case_id": case_id,
        "related_family_id": _optional_str(row, "related_family_id"),
        "mdl_family_id": _optional_str(row, "mdl_family_id"),
        "solver_id": f"baseline:{model_id}",
        "solver_kind": "empirical_baseline",
        "model_id": model_id,
        "run_label": ablation,
        "ablation": ablation,
        "raw_output": raw_output,
        "raw_output_sha256": raw_output_sha256,
        "required_unit_ids": list(required_unit_ids),
        "request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_total_tokens": 0,
        "estimated_cost": 0.0,
        "tool_call_logs": [],
        "execution_backend": "deterministic_baseline",
        "metadata": {
            "provider": "legalforecast_baseline",
            "model_id": model_id,
            "model_version_or_snapshot": _baseline_version(suite),
            "baseline_id": model_id,
            "training_period_start": suite.training_period_start.isoformat(),
            "training_period_end": suite.training_period_end.isoformat(),
            "generated_at": _format_datetime(generated_at),
        },
    }


def _baseline_accounting_record(
    run_record: Mapping[str, Any],
    *,
    baseline_id: BaselineId,
    suite: BaselineSuite,
    generated_at: datetime,
) -> JsonRecord:
    unit_count = len(_list(run_record, "required_unit_ids"))
    return {
        "sample_id": _required_str(run_record, "sample_id"),
        "candidate_id": _optional_str(run_record, "candidate_id"),
        "case_id": _required_str(run_record, "case_id"),
        "solver_id": _required_str(run_record, "solver_id"),
        "solver_kind": _required_str(run_record, "solver_kind"),
        "provider": "legalforecast_baseline",
        "model_id": baseline_id.value,
        "model_version_or_snapshot": _baseline_version(suite),
        "served_model_version": None,
        "evaluation_timestamp": _format_datetime(generated_at),
        "raw_output_sha256": _required_str(run_record, "raw_output_sha256"),
        "prediction_unit_count": unit_count,
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "tool_call_count": 0,
        "allowed_tool_call_count": 0,
        "denied_tool_call_count": 0,
        "latency_ms": 0.0,
        "estimated_cost": 0.0,
        "cost_per_case": 0.0,
        "cost_per_prediction_unit": 0.0,
        "invalid_output": False,
        "refusal": False,
        "content_filter": False,
        "invalid_output_reason": None,
        "run_label": _optional_str(run_record, "run_label"),
        "ablation": _optional_str(run_record, "ablation"),
        "execution_backend": "deterministic_baseline",
    }


def _baseline_raw_output(
    baseline_id: BaselineId,
    predictions: Sequence[BaselinePrediction],
) -> str:
    return json.dumps(
        {
            "case_assessment": (
                f"Deterministic empirical baseline: {baseline_id.value}."
            ),
            "predictions": [
                {
                    "unit_id": prediction.unit_id,
                    "probability_fully_dismissed": (
                        prediction.probability_fully_dismissed
                    ),
                    "rationale": (
                        f"{baseline_id.value}; fallback={prediction.fallback_level}"
                    ),
                }
                for prediction in predictions
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _baseline_version(suite: BaselineSuite) -> str:
    return (
        f"historical-{suite.training_period_start.isoformat()}"
        f"_{suite.training_period_end.isoformat()}"
    )


def _baseline_reference_summary(
    summaries: Sequence[ScoreSummary],
) -> ScoreSummary | None:
    by_model = {summary.model_id: summary for summary in summaries}
    for baseline_id in (
        BaselineId.JUDGE_HISTORY,
        BaselineId.METADATA_ONLY,
        BaselineId.COURT_NOS_MOTION_BASE_RATE,
        BaselineId.GLOBAL_BASE_RATE,
    ):
        if baseline_id.value in by_model:
            return by_model[baseline_id.value]
    return None


def _reference_skill_fields(
    summary: ScoreSummary,
    reference_summary: ScoreSummary | None,
) -> JsonRecord:
    if reference_summary is None:
        return {
            "brier_skill_score_reference_model_id": None,
            "brier_skill_score_over_reference": None,
        }
    if reference_summary.micro_brier == 0:
        skill: float | None = None
    else:
        skill = 1 - (summary.micro_brier / reference_summary.micro_brier)
    return {
        "brier_skill_score_reference_model_id": reference_summary.model_id,
        "brier_skill_score_over_reference": skill,
    }


def _metadata_mapping(row: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = row.get("metadata")
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise OfficialAggregationError("run-input metadata must be an object")
    return cast(Mapping[str, Any], metadata)


def _baseline_required_str(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    field_name: str,
) -> str:
    value = _baseline_optional_str(row, metadata, field_name)
    if value is None:
        raise OfficialAggregationError(
            f"baseline scoring requires {field_name} in run-input manifest rows"
        )
    return value


def _baseline_optional_str(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    field_name: str,
) -> str | None:
    value = row.get(field_name)
    if value is None:
        value = metadata.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OfficialAggregationError(f"{field_name} must be a non-empty string")
    return value


def _baseline_optional_int(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    field_name: str,
) -> int | None:
    value = row.get(field_name)
    if value is None:
        value = metadata.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise OfficialAggregationError(f"{field_name} must be an integer")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate official per-case outputs into a public-safe bundle."
    )
    parser.add_argument("--per-case-dir", type=Path, required=True)
    parser.add_argument("--run-input-manifest", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument(
        "--cycle-series",
        choices=[series.value for series in CycleSeries],
        required=True,
        help="Cycle cadence used for claim-strength classification.",
    )
    parser.add_argument("--clean-motion-count", type=int, required=True)
    parser.add_argument("--prediction-unit-count", type=int, required=True)
    parser.add_argument(
        "--model-key",
        action="append",
        default=[],
        help=(
            "Expected registry key in provider:model_id form. Repeat for a "
            "multi-model matrix."
        ),
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        help=(
            "Frozen model registry JSON. When --model-key is omitted, every "
            "registry entry is treated as an expected model output."
        ),
    )
    parser.add_argument(
        "--baseline-training-examples",
        type=Path,
        help=(
            "JSONL or JSON historical baseline corpus. When provided, "
            "global, court/NOS/motion, metadata-only, and judge-history "
            "baselines are scored as deterministic pseudo-model rows."
        ),
    )
    parser.add_argument(
        "--dispatch-provenance",
        type=Path,
        help=(
            "Validated JSON provenance for original/amendment dispatches. The "
            "record must cover every expected registry model."
        ),
    )
    parser.add_argument(
        "--allow-incomplete-model-set",
        action="store_true",
        help=(
            "Permit aggregation without a registry or explicit expected model "
            "keys. Intended only for partial/debug bundles and recorded in the "
            "run card."
        ),
    )
    parser.add_argument(
        "--allow-no-baselines",
        action="store_true",
        help=(
            "Permit aggregation without baseline-training examples. Intended only "
            "for partial/debug or explicitly disclosed first-cycle bundles and "
            "recorded in the run card."
        ),
    )
    parser.add_argument(
        "--deferred-ablation",
        action="append",
        default=[],
        help=(
            "A planned ablation intentionally deferred from this cycle, recorded "
            "in the run card for publication disclosure."
        ),
    )
    parser.add_argument("--elapsed-days", type=int)
    parser.add_argument("--official-window-days", type=int)
    parser.add_argument(
        "--paired-delta-sd",
        type=float,
        help=(
            "Override the paired delta standard deviation used for MDE analysis. "
            "When omitted, aggregation derives it from observed bootstrap deltas "
            "or repeat-variance summaries before falling back to the documented "
            f"default {DEFAULT_PAIRED_DELTA_SD:g}."
        ),
    )
    parser.add_argument(
        "--target-mde",
        type=float,
        default=DEFAULT_TARGET_MDE,
        help="Target minimum detectable effect for cycle-power analysis.",
    )
    parser.add_argument(
        "--target-power",
        type=float,
        default=DEFAULT_POWER,
        help="Target statistical power for cycle-power analysis.",
    )
    parser.add_argument(
        "--two-sided-alpha",
        type=float,
        default=DEFAULT_TWO_SIDED_ALPHA,
        help="Two-sided alpha for cycle-power analysis.",
    )
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
            cycle_series=CycleSeries(cast(str, args.cycle_series)),
            clean_motion_count=cast(int, args.clean_motion_count),
            prediction_unit_count=cast(int, args.prediction_unit_count),
            model_registry_path=cast(Path | None, args.model_registry),
            dispatch_provenance_path=cast(Path | None, args.dispatch_provenance),
            baseline_training_examples_path=cast(
                Path | None,
                args.baseline_training_examples,
            ),
            model_keys=tuple(cast(Sequence[str], args.model_key)),
            allow_incomplete_model_set=cast(bool, args.allow_incomplete_model_set),
            allow_no_baselines=cast(bool, args.allow_no_baselines),
            deferred_ablations=tuple(cast(Sequence[str], args.deferred_ablation)),
            ablation=cast(str | None, args.ablation),
            title=cast(str, args.title),
            base_rate=cast(float | None, args.base_rate),
            elapsed_days=cast(int | None, args.elapsed_days),
            official_window_days=cast(int | None, args.official_window_days),
            paired_delta_sd=cast(float | None, args.paired_delta_sd),
            target_mde=cast(float, args.target_mde),
            target_power=cast(float, args.target_power),
            two_sided_alpha=cast(float, args.two_sided_alpha),
        )
    )
    print(
        json.dumps(
            {
                "artifact_manifest": str(result.artifact_manifest_path),
                "cycle_power": str(result.cycle_power_path),
                "leaderboard": str(result.leaderboard_path),
                "run_card": str(result.run_card_path),
                "expected_matrix_row_count": result.expected_matrix_row_count,
                "aggregated_matrix_row_count": result.aggregated_matrix_row_count,
                "expected_case_count": result.expected_case_count,
                "aggregated_case_count": result.aggregated_case_count,
                "model_count": result.model_count,
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
) -> dict[PacketKey, JsonRecord]:
    manifest = _read_json_object(path)
    if _required_str(manifest, "cycle_id") != cycle_id:
        raise OfficialAggregationError("run-input manifest cycle_id mismatch")
    rows: dict[PacketKey, JsonRecord] = {}
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


def _expected_model_key_sets(
    config: OfficialAggregationConfig,
    *,
    registry_entries: Sequence[ModelRegistryEntry],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    registry_model_keys = tuple(entry.registry_key for entry in registry_entries)
    if config.model_keys:
        if registry_model_keys:
            missing = sorted(set(config.model_keys) - set(registry_model_keys))
            if missing:
                raise OfficialAggregationError(
                    f"model_keys missing from registry: {missing}"
                )
            omitted = sorted(set(registry_model_keys) - set(config.model_keys))
            if omitted and not config.allow_incomplete_model_set:
                raise OfficialAggregationError(
                    "incomplete model set: explicit model_keys omit registry "
                    f"entries {omitted}; pass --allow-incomplete-model-set only "
                    "for partial/debug bundles"
                )
        return config.model_keys, registry_model_keys
    if registry_model_keys:
        return registry_model_keys, registry_model_keys
    if config.allow_incomplete_model_set:
        return (), ()
    raise OfficialAggregationError(
        "expected model set is required for official aggregation; pass "
        "--model-registry, repeat --model-key for each expected model, or use "
        "--allow-incomplete-model-set for an explicitly partial/debug bundle"
    )


def _registry_entries(
    config: OfficialAggregationConfig,
) -> tuple[ModelRegistryEntry, ...]:
    if config.model_registry_path is None:
        return ()
    return load_model_registry(config.model_registry_path).entries


def _dispatch_provenance(
    config: OfficialAggregationConfig,
    *,
    expected_model_keys: Sequence[str],
) -> JsonRecord | None:
    if config.dispatch_provenance_path is None:
        return None
    try:
        return load_dispatch_provenance(
            config.dispatch_provenance_path,
            expected_cycle_id=config.cycle_id,
            expected_model_keys=expected_model_keys,
        )
    except DispatchProvenanceError as exc:
        raise OfficialAggregationError(str(exc)) from exc


def _packet_token_budget_record(
    expected_packet_rows: Mapping[PacketKey, JsonRecord],
    *,
    registry_entries: Sequence[ModelRegistryEntry],
) -> JsonRecord:
    packet_tokens = [
        {
            "case_id": case_id,
            "ablation": ablation,
            "estimated_input_tokens": _packet_input_tokens(row),
        }
        for (case_id, ablation), row in sorted(expected_packet_rows.items())
    ]
    if not packet_tokens:
        raise OfficialAggregationError("packet token reporting requires model packets")

    registry_budgets = [_registry_budget_record(entry) for entry in registry_entries]
    smallest_prompt_budget = (
        min(
            _required_int(budget, "prompt_input_token_budget")
            for budget in registry_budgets
        )
        if registry_budgets
        else None
    )
    if smallest_prompt_budget is not None and smallest_prompt_budget <= 0:
        raise OfficialAggregationError(
            "registry context_limit must exceed max_output_tokens for every model"
        )
    if smallest_prompt_budget is not None:
        over_budget = [
            packet
            for packet in packet_tokens
            if _required_int(packet, "estimated_input_tokens") > smallest_prompt_budget
        ]
        if over_budget:
            raise OfficialAggregationError(
                "packet token budget exceeded smallest evaluated model prompt budget: "
                f"{over_budget}"
            )

    return {
        "estimator": _PACKET_TOKEN_ESTIMATOR,
        "bytes_per_token_fallback": _TOKEN_ESTIMATE_BYTES_PER_TOKEN,
        "smallest_context_limit": (
            min(entry.context_limit for entry in registry_entries)
            if registry_entries
            else None
        ),
        "smallest_prompt_input_token_budget": smallest_prompt_budget,
        "registry_budgets": registry_budgets,
        "temperature_policy": _temperature_policy_record(registry_entries),
        "overall": _token_distribution(
            [
                _required_int(packet, "estimated_input_tokens")
                for packet in packet_tokens
            ]
        ),
        "by_ablation": _token_distribution_by_ablation(packet_tokens),
    }


def _registry_budget_record(entry: ModelRegistryEntry) -> JsonRecord:
    return {
        "model_key": entry.registry_key,
        "context_limit": entry.context_limit,
        "max_output_tokens": entry.max_output_tokens,
        "prompt_input_token_budget": entry.context_limit - entry.max_output_tokens,
        "temperature": entry.temperature,
    }


def _temperature_policy_record(
    registry_entries: Sequence[ModelRegistryEntry],
) -> JsonRecord:
    temperatures = sorted({float(entry.temperature) for entry in registry_entries})
    return {
        "registry_temperatures": temperatures,
        "all_registry_temperatures_zero": bool(temperatures)
        and all(temperature == 0 for temperature in temperatures),
        "rationale": _TEMPERATURE_ZERO_RATIONALE,
    }


def _packet_input_tokens(row: Mapping[str, Any]) -> int:
    for field_name in _PACKET_TOKEN_FIELDS:
        value = _optional_nonnegative_int(row, field_name)
        if value is not None:
            return value
    for field_name in _PACKET_SIZE_FIELDS:
        size_bytes = _optional_nonnegative_int(row, field_name)
        if size_bytes is not None:
            return math.ceil(size_bytes / _TOKEN_ESTIMATE_BYTES_PER_TOKEN)
    raise OfficialAggregationError(
        "run-input model_packets rows require packet token counts or packet_size_bytes "
        "for packet budget reporting"
    )


def _token_distribution_by_ablation(
    packet_tokens: Sequence[Mapping[str, Any]],
) -> JsonRecord:
    grouped: dict[str, list[int]] = defaultdict(list)
    for packet in packet_tokens:
        grouped[_required_str(packet, "ablation")].append(
            _required_int(packet, "estimated_input_tokens")
        )
    return {
        ablation: _token_distribution(tokens)
        for ablation, tokens in sorted(grouped.items())
    }


def _token_distribution(values: Sequence[int]) -> JsonRecord:
    if not values:
        raise OfficialAggregationError("token distribution requires values")
    sorted_values = sorted(values)
    return {
        "count": len(sorted_values),
        "min": sorted_values[0],
        "p50": _nearest_rank(sorted_values, 0.50),
        "p90": _nearest_rank(sorted_values, 0.90),
        "p95": _nearest_rank(sorted_values, 0.95),
        "max": sorted_values[-1],
        "mean": sum(sorted_values) / len(sorted_values),
    }


def _nearest_rank(sorted_values: Sequence[int], quantile: float) -> int:
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be in (0, 1]")
    index = min(len(sorted_values) - 1, math.ceil(len(sorted_values) * quantile) - 1)
    return sorted_values[index]


def _expected_output_rows(
    expected_packet_rows: Mapping[PacketKey, JsonRecord],
    *,
    case_outputs: Mapping[OutputKey, Path],
    model_keys: Sequence[str],
) -> dict[OutputKey, JsonRecord]:
    if model_keys:
        return {
            (case_id, ablation, model_key): expected_row
            for (case_id, ablation), expected_row in expected_packet_rows.items()
            for model_key in model_keys
        }

    outputs_by_packet: dict[PacketKey, list[OutputKey]] = defaultdict(list)
    for output_key in case_outputs:
        case_id, ablation, _model_key = output_key
        outputs_by_packet[(case_id, ablation)].append(output_key)

    rows: dict[OutputKey, JsonRecord] = {}
    for packet_key, expected_row in expected_packet_rows.items():
        output_keys = outputs_by_packet.get(packet_key, [])
        if len(output_keys) > 1:
            raise OfficialAggregationError(
                "multiple model outputs found for "
                f"case_id={packet_key[0]}, ablation={packet_key[1]}; pass "
                "--model-key for each expected registry entry"
            )
        if output_keys:
            rows[output_keys[0]] = expected_row
        else:
            case_id, ablation = packet_key
            rows[(case_id, ablation, "*")] = expected_row
    return rows


def _discover_case_outputs(root: Path) -> dict[OutputKey, Path]:
    outputs: dict[OutputKey, Path] = {}
    for runs_path in sorted(root.rglob("runs.jsonl")):
        case_dir = runs_path.parent
        runs = _read_jsonl(runs_path)
        if not runs:
            raise OfficialAggregationError(f"empty runs artifact: {runs_path}")
        case_id = _required_str(runs[0], "case_id")
        ablation = _optional_str(runs[0], "ablation") or "full_packet"
        model_key = _required_str(runs[0], "solver_id")
        key = (case_id, ablation, model_key)
        if key in outputs:
            raise OfficialAggregationError(
                "duplicate per-case output: "
                f"case_id={case_id}, ablation={ablation}, model_key={model_key}"
            )
        outputs[key] = case_dir
    return outputs


def _validate_coverage(
    expected_rows: Mapping[OutputKey, JsonRecord],
    case_outputs: Mapping[OutputKey, Path],
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
    key: OutputKey,
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
    _validate_response_verification_flags(key, runs, accounting)
    _validate_metrics_hashes(key, metrics, runs)
    _validate_accounting_hashes(key, runs, accounting)


def _validate_common_case_fields(
    key: OutputKey,
    record: Mapping[str, Any],
) -> None:
    case_id, ablation, model_key = key
    if _required_str(record, "case_id") != case_id:
        raise OfficialAggregationError(f"case_id mismatch in output: {key}")
    record_ablation = _optional_str(record, "ablation") or _optional_str(
        record,
        "run_label",
    )
    if record_ablation is not None and record_ablation != ablation:
        raise OfficialAggregationError(f"ablation mismatch in output: {key}")
    if model_key != "*" and "solver_id" in record:
        record_model_key = _required_str(record, "solver_id")
        if record_model_key != model_key:
            raise OfficialAggregationError(f"model key mismatch in output: {key}")


def _validate_metrics_record(
    key: OutputKey,
    *,
    expected_row: Mapping[str, Any],
    metrics: Mapping[str, Any],
    cycle_id: str,
    run_count: int,
) -> None:
    _case_id, ablation, model_key = key
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

    expected_sha256 = _expected_packet_sha256(expected_row)
    actual_sha256 = _required_str(metrics, "packet_sha256")
    _require_hex_sha256(actual_sha256, "metrics packet_sha256")
    if actual_sha256 != expected_sha256:
        raise OfficialAggregationError(f"packet SHA-256 mismatch in output: {key}")

    if _required_str(metrics, "ablation") != ablation:
        raise OfficialAggregationError(f"metrics ablation mismatch in output: {key}")
    if model_key != "*":
        metric_model_key = _optional_str(metrics, "model_key") or _required_str(
            metrics,
            "solver_id",
        )
        if metric_model_key != model_key:
            raise OfficialAggregationError(
                f"metrics model key mismatch in output: {key}"
            )


def _expected_packet_sha256(expected_row: Mapping[str, Any]) -> str:
    sha256 = _optional_str(expected_row, "sha256")
    packet_sha256 = _optional_str(expected_row, "packet_sha256")
    if sha256 is None and packet_sha256 is None:
        raise OfficialAggregationError(
            "run-input packet row requires sha256 or packet_sha256"
        )
    for field_name, value in (
        ("sha256", sha256),
        ("packet_sha256", packet_sha256),
    ):
        if value is not None:
            _require_hex_sha256(value, f"run-input {field_name}")
    if sha256 is not None and packet_sha256 is not None and sha256 != packet_sha256:
        raise OfficialAggregationError(
            "run-input packet row has conflicting sha256 and packet_sha256"
        )
    return sha256 or cast(str, packet_sha256)


def _validate_run_raw_output_hash(record: Mapping[str, Any]) -> None:
    raw_output = _required_str(record, "raw_output")
    expected = _required_str(record, "raw_output_sha256")
    actual = _sha256_prefixed(raw_output)
    if expected != actual:
        raise OfficialAggregationError(
            f"raw_output_sha256 mismatch for case_id={_required_str(record, 'case_id')}"
        )


def _validate_response_verification_flags(
    key: OutputKey,
    runs: Sequence[Mapping[str, Any]],
    accounting: Sequence[Mapping[str, Any]],
) -> None:
    for record in runs:
        if _optional_str(record, "execution_backend") == "inspect_ai":
            schema_version = _metadata_str(record, RESPONSE_VERIFICATION_SCHEMA_FIELD)
            if schema_version != RESPONSE_VERIFICATION_SCHEMA_VERSION:
                raise OfficialAggregationError(
                    "live response verification metadata missing or invalid: "
                    f"{_output_context(key, record)}"
                )
        if _optional_metadata_text_bool(
            record,
            RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD,
        ):
            raise OfficialAggregationError(
                "response grounding artifacts detected in official output: "
                f"{_output_context(key, record)}"
            )
        if _optional_metadata_text_bool(
            record,
            RESPONSE_RETRYABLE_OPS_EVENT_FIELD,
        ):
            raise OfficialAggregationError(
                "retryable response ops event unresolved in official output: "
                f"{_output_context(key, record)}"
            )
    for record in accounting:
        if _optional_bool(record, "retryable_ops_event", default=False):
            raise OfficialAggregationError(
                "retryable response ops event unresolved in official accounting: "
                f"{_output_context(key, record)}"
            )


def _optional_metadata_text_bool(
    record: Mapping[str, Any],
    field_name: str,
) -> bool:
    value = _metadata_str(record, field_name)
    if value is None:
        return False
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized in {"false", "none", "unknown"}:
        return False
    raise OfficialAggregationError(f"metadata[{field_name}] must be a boolean flag")


def _output_context(key: OutputKey, record: Mapping[str, Any]) -> str:
    return (
        f"case_id={key[0]}, ablation={key[1]}, model_key={key[2]}, "
        f"model_id={_optional_str(record, 'model_id') or 'unknown'}"
    )


def _validate_metrics_hashes(
    key: OutputKey,
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
    key: OutputKey,
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


def _primary_run_records(
    run_records: Sequence[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Return only the first sample from each repeat-sampled case row."""

    return tuple(
        dict(record) for record in run_records if _record_repeat_index(record) == 1
    )


def _repeat_variance_report(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    cycle_id: str,
    generated_at: datetime,
) -> JsonRecord:
    labels_by_unit_id = {label.unit_id: label for label in labels}
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in run_records:
        if _record_repeat_count(record) < 2:
            continue
        model_id = _record_model_id(record)
        case_id = _required_str(record, "case_id")
        ablation = (
            _optional_str(record, "ablation")
            or _optional_str(record, "run_label")
            or "full_packet"
        )
        groups[(model_id, case_id, ablation)].append(record)

    rows: list[JsonRecord] = []
    for (model_id, case_id, ablation), records in sorted(groups.items()):
        if len(records) < 2:
            continue
        ordered_records = sorted(records, key=_record_repeat_index)
        run_briers = tuple(
            _run_micro_brier(record, labels_by_unit_id) for record in ordered_records
        )
        mean_brier = _mean(run_briers)
        sample_variance = _sample_variance(run_briers)
        rows.append(
            {
                "model_id": model_id,
                "solver_id": _required_str(ordered_records[0], "solver_id"),
                "case_id": case_id,
                "ablation": ablation,
                "repeat_count": len(ordered_records),
                "repeat_indices": [
                    _record_repeat_index(record) for record in ordered_records
                ],
                "unit_count": len(_list(ordered_records[0], "required_unit_ids")),
                "mean_micro_brier": mean_brier,
                "sample_variance_micro_brier": sample_variance,
                "sample_stddev_micro_brier": math.sqrt(sample_variance),
                "min_micro_brier": min(run_briers),
                "max_micro_brier": max(run_briers),
                "run_micro_briers": list(run_briers),
                "raw_output_sha256": [
                    _required_str(record, "raw_output_sha256")
                    for record in ordered_records
                ],
            }
        )

    summary_by_model = _summarize_repeat_variance_rows(rows)
    return {
        "schema_version": "legalforecast-repeat-variance-v1",
        "cycle_id": cycle_id,
        "generated_at": _format_datetime(generated_at),
        "method": "prebudgeted_repeat_sample_subset_with_primary_run_scoring",
        "repeat_sampling_present": bool(rows),
        "summary_by_model": summary_by_model,
        "rows": rows,
        "notes": [
            "Headline scores use repeat_index=1 only.",
            "Rows summarize repeated provider calls for the same model/case/ablation.",
        ],
    }


def _repeat_variance_summary_rows(report: Mapping[str, Any]) -> tuple[JsonRecord, ...]:
    return tuple(
        dict(_mapping(row, "repeat variance summary"))
        for row in _list(report, "summary_by_model", default=())
    )


def _summarize_repeat_variance_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    rows_by_model: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_model[_required_str(row, "model_id")].append(row)

    summary_rows: list[JsonRecord] = []
    for model_id, model_rows in sorted(rows_by_model.items()):
        variances = [
            _required_float(row, "sample_variance_micro_brier") for row in model_rows
        ]
        repeat_run_count = sum(_required_int(row, "repeat_count") for row in model_rows)
        mean_variance = _mean(variances)
        summary_rows.append(
            {
                "model_id": model_id,
                "repeated_case_count": len(model_rows),
                "repeat_run_count": repeat_run_count,
                "mean_within_case_variance": mean_variance,
                "root_mean_within_case_variance": math.sqrt(mean_variance),
                "max_within_case_stddev": max(
                    _required_float(row, "sample_stddev_micro_brier")
                    for row in model_rows
                ),
            }
        )
    return summary_rows


def _run_micro_brier(
    record: Mapping[str, Any],
    labels_by_unit_id: Mapping[str, OutcomeLabel],
) -> float:
    required_unit_ids = tuple(
        _required_str_value(value) for value in _list(record, "required_unit_ids")
    )
    parsed = parse_model_output(
        _required_str(record, "raw_output"),
        required_unit_ids=required_unit_ids,
    )
    briers: list[float] = []
    for unit_id in required_unit_ids:
        label = labels_by_unit_id.get(unit_id)
        if label is None:
            raise OfficialAggregationError(
                f"labels missing for required units: {[unit_id]}"
            )
        outcome = label.primary_outcome
        if outcome is None:
            raise OfficialAggregationError(
                f"ambiguous label cannot be scored: {unit_id}"
            )
        prediction = parsed.prediction_for(unit_id)
        briers.append(brier_score(prediction.probability_fully_dismissed, outcome))
    return _mean(briers)


def _record_repeat_index(record: Mapping[str, Any]) -> int:
    value = record.get("repeat_index")
    if value is None:
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise OfficialAggregationError("repeat_index must be a positive integer")
    return value


def _record_repeat_count(record: Mapping[str, Any]) -> int:
    value = record.get("repeat_count")
    if value is None:
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise OfficialAggregationError("repeat_count must be a positive integer")
    return value


def _record_model_id(record: Mapping[str, Any]) -> str:
    return (
        _optional_str(record, "model_id")
        or _metadata_str(record, "model_id")
        or _required_str(record, "solver_id")
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise OfficialAggregationError("cannot compute mean of empty values")
    return sum(values) / len(values)


def _sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _score_run_records(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    base_rate: float | None,
    include_ablation_in_model_id: bool = False,
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
        model_id = _display_model_id(
            _record_model_id(record),
            _record_ablation(record),
            include_ablation=include_ablation_in_model_id,
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


def _ablation_delta_report(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    cycle_id: str,
    generated_at: datetime,
    base_rate: float | None,
) -> JsonRecord:
    summaries = _score_run_records_by_model_ablation(
        run_records,
        labels,
        base_rate=base_rate,
    )
    rows: list[JsonRecord] = []
    grouped: dict[str, dict[str, ScoreSummary]] = defaultdict(dict)
    for (model_id, ablation), summary in summaries.items():
        grouped[model_id][ablation] = summary
    for model_id, by_ablation in sorted(grouped.items()):
        full_packet = by_ablation.get("full_packet")
        metadata_only = by_ablation.get("metadata_only")
        if full_packet is None or metadata_only is None:
            continue
        delta = full_packet.micro_brier - metadata_only.micro_brier
        inference = paired_clustered_bootstrap(
            (
                ModelScoreInput(
                    model_id="full_packet",
                    unit_scores=full_packet.unit_scores,
                ),
                ModelScoreInput(
                    model_id="metadata_only",
                    unit_scores=metadata_only.unit_scores,
                ),
            )
        )
        [pairwise_delta] = inference.pairwise_deltas
        rows.append(
            {
                "model_id": model_id,
                "full_packet_micro_brier": full_packet.micro_brier,
                "metadata_only_micro_brier": metadata_only.micro_brier,
                "full_packet_minus_metadata_only_micro_brier": delta,
                "full_packet_minus_metadata_only_ci_low": pairwise_delta.ci_low,
                "full_packet_minus_metadata_only_ci_high": pairwise_delta.ci_high,
                "probability_full_packet_better": (pairwise_delta.probability_a_better),
                "record_text_improves_brier": delta < 0,
                "case_count": min(full_packet.case_count, metadata_only.case_count),
                "prediction_unit_count": min(
                    full_packet.unit_count,
                    metadata_only.unit_count,
                ),
            }
        )
    return {
        "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
        "cycle_id": cycle_id,
        "generated_at": _format_datetime(generated_at),
        "comparison": "full_packet_minus_metadata_only_micro_brier",
        "confidence_interval_method": "paired_clustered_bootstrap",
        "rows": rows,
    }


def _score_run_records_by_model_ablation(
    run_records: Sequence[Mapping[str, Any]],
    labels: tuple[OutcomeLabel, ...],
    *,
    base_rate: float | None,
) -> dict[tuple[str, str], ScoreSummary]:
    if not run_records:
        return {}
    labels_by_unit_id = {label.unit_id: label for label in labels}
    effective_base_rate = (
        _computed_base_rate(labels) if base_rate is None else base_rate
    )

    cases_by_key: dict[tuple[str, str], list[ScoringCase]] = defaultdict(list)
    for record in run_records:
        required_unit_ids = tuple(
            _required_str_value(value) for value in _list(record, "required_unit_ids")
        )
        missing_labels = sorted(set(required_unit_ids) - set(labels_by_unit_id))
        if missing_labels:
            raise OfficialAggregationError(
                f"labels missing for required units: {missing_labels}"
            )
        model_id = _record_model_id(record)
        ablation = (
            _optional_str(record, "ablation")
            or _optional_str(record, "run_label")
            or "full_packet"
        )
        parsed = parse_model_output(
            _required_str(record, "raw_output"),
            required_unit_ids=required_unit_ids,
        )
        cases_by_key[(model_id, ablation)].append(
            ScoringCase(
                case_id=_required_str(record, "case_id"),
                candidate_id=_optional_str(record, "candidate_id"),
                model_id=f"{model_id}::{ablation}",
                related_family_id=_optional_str(record, "related_family_id"),
                mdl_family_id=_optional_str(record, "mdl_family_id"),
                parsed_output=parsed,
                outcome_labels=tuple(
                    labels_by_unit_id[unit_id] for unit_id in required_unit_ids
                ),
            )
        )
    return {
        key: score_cases(tuple(cases), base_rate=effective_base_rate)
        for key, cases in sorted(cases_by_key.items())
    }


def _official_bootstrap_inference(
    summaries: Sequence[ScoreSummary],
) -> BootstrapInferenceResult | None:
    if len(summaries) < 2:
        return None
    return paired_clustered_bootstrap(
        tuple(
            ModelScoreInput(
                model_id=summary.model_id,
                unit_scores=summary.unit_scores,
            )
            for summary in summaries
        )
    )


def _computed_base_rate(labels: Sequence[OutcomeLabel]) -> float:
    outcomes = [
        label.primary_outcome for label in labels if label.primary_outcome is not None
    ]
    if not outcomes:
        raise OfficialAggregationError("at least one non-ambiguous label is required")
    return sum(outcomes) / len(outcomes)


def _cycle_power_input(
    config: OfficialAggregationConfig,
    *,
    inference: BootstrapInferenceResult | None,
    repeat_variance_report: Mapping[str, Any],
) -> _CyclePowerInputResolution:
    paired_delta_sd = config.paired_delta_sd
    source = "explicit_config"
    warning: str | None = None
    if paired_delta_sd is None:
        paired_delta_sd = _paired_delta_sd_from_bootstrap(
            inference,
            clean_motion_count=config.clean_motion_count,
        )
        source = "observed_pairwise_bootstrap_deltas"
    if paired_delta_sd is None:
        paired_delta_sd = _paired_delta_sd_from_repeat_variance(repeat_variance_report)
        source = "repeat_variance_report"
    if paired_delta_sd is None:
        paired_delta_sd = DEFAULT_PAIRED_DELTA_SD
        source = "default_fallback"
        warning = (
            "paired_delta_sd fell back to the default 0.05 because no explicit "
            "value, observed pairwise bootstrap estimate, or repeat-variance "
            "estimate was available"
        )
    return _CyclePowerInputResolution(
        cycle_input=CyclePowerInput(
            cycle_id=config.cycle_id,
            series=config.cycle_series,
            clean_motion_count=config.clean_motion_count,
            prediction_unit_count=config.prediction_unit_count,
            elapsed_days=config.elapsed_days,
            official_window_days=config.official_window_days,
            paired_delta_sd=paired_delta_sd,
            target_mde=config.target_mde,
            target_power=config.target_power,
            two_sided_alpha=config.two_sided_alpha,
        ),
        paired_delta_sd_source=source,
        warning=warning,
    )


def _paired_delta_sd_from_bootstrap(
    inference: BootstrapInferenceResult | None,
    *,
    clean_motion_count: int,
) -> float | None:
    if inference is None or clean_motion_count <= 0 or len(inference.replicates) < 2:
        return None
    model_ids = tuple(sorted(inference.observed_micro_briers))
    estimates: list[float] = []
    for index, model_a in enumerate(model_ids):
        for model_b in model_ids[index + 1 :]:
            deltas = [
                replicate.micro_briers[model_a] - replicate.micro_briers[model_b]
                for replicate in inference.replicates
                if model_a in replicate.micro_briers
                and model_b in replicate.micro_briers
            ]
            if len(deltas) < 2:
                continue
            estimate = math.sqrt(_sample_variance(deltas)) * math.sqrt(
                clean_motion_count
            )
            if estimate > 0:
                estimates.append(estimate)
    return max(estimates) if estimates else None


def _paired_delta_sd_from_repeat_variance(
    repeat_variance_report: Mapping[str, Any],
) -> float | None:
    estimates = [
        _required_float(row, "root_mean_within_case_variance")
        for row in _repeat_variance_summary_rows(repeat_variance_report)
    ]
    positive_estimates = [estimate for estimate in estimates if estimate > 0]
    return max(positive_estimates) if positive_estimates else None


def _cycle_power_record(
    cycle_power: CyclePowerReport,
    *,
    config: OfficialAggregationConfig,
    paired_delta_sd_source: str,
    warning: str | None,
) -> JsonRecord:
    record = cycle_power.to_record()
    record["elapsed_days"] = config.elapsed_days
    record["official_window_days"] = config.official_window_days
    mde_analysis = dict(_mapping(record["mde_analysis"], "mde_analysis"))
    mde_analysis["paired_delta_sd_source"] = paired_delta_sd_source
    mde_analysis["target_power_source"] = "explicit_config"
    mde_analysis["target_mde_source"] = "explicit_config"
    mde_analysis["two_sided_alpha_source"] = "explicit_config"
    record["mde_analysis"] = mde_analysis
    if warning is not None:
        record["warnings"] = [*list(_list(record, "warnings")), warning]
    return record


def _labels_frozen_sha256(
    run_input_manifest_path: Path,
    *,
    labels_path: Path,
) -> str:
    """Enforce labels-frozen-before-scoring and return the labels sha256.

    Blind-to-predictions scoring requires that the labels are locked before any
    model output exists. The frozen run-input manifest records the labels
    artifact sha256 at dispatch/build time; aggregation recomputes the hash of
    the labels file it was handed and refuses to score on any drift. Fail-closed:
    a manifest that never froze a labels hash, or a labels file that no longer
    matches the frozen hash, aborts aggregation instead of silently scoring a
    swapped label set.
    """

    manifest = _read_json_object(run_input_manifest_path)
    frozen = _optional_str(manifest, "labels_sha256")
    if frozen is None:
        raise OfficialAggregationError(
            "run-input manifest is missing labels_sha256; labels must be frozen "
            "(hashed into the run-input manifest) before scoring"
        )
    _require_hex_sha256(frozen, "run-input labels_sha256")
    actual = sha256_file(labels_path)
    if actual != frozen:
        raise OfficialAggregationError(
            "labels hash drift: run-input manifest froze labels_sha256="
            f"{frozen} but the scored labels file hashes to {actual}; refusing to "
            "score a label set that was not frozen before model outputs existed"
        )
    return actual


def _load_labels(path: Path) -> tuple[OutcomeLabel, ...]:
    labels = tuple(_outcome_label(record) for record in _read_jsonl(path))
    if not labels:
        raise OfficialAggregationError("labels file must not be empty")
    return labels


def _outcome_label(record: Mapping[str, Any]) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=_required_str(record, "unit_id"),
        unit_resolution=UnitResolution(_required_str(record, "unit_resolution")),
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
    expected_rows: Mapping[OutputKey, JsonRecord],
    expected_model_keys: Sequence[str],
    registry_model_keys: Sequence[str],
    dispatch_provenance: Mapping[str, Any] | None,
    packet_token_budget: Mapping[str, Any],
    summaries: Sequence[ScoreSummary],
    accounting_records: Sequence[Mapping[str, Any]],
    cycle_power_record: Mapping[str, Any],
    baseline_artifacts: _BaselineAggregateArtifacts,
    cycle_baseline_training_example_count: int,
    ablation_delta_count: int,
    repeat_variance_report: Mapping[str, Any],
    labels_sha256: str,
) -> JsonRecord:
    baseline_reference = _baseline_reference_summary(summaries)
    private_debug_outputs = [
        "runs.jsonl",
        "accounting.jsonl",
        "case-metrics.jsonl",
    ]
    if baseline_artifacts.prediction_records:
        private_debug_outputs.append("baseline-predictions.jsonl")
    public_outputs = [
        "scores.json",
        "unit-scores.jsonl",
        "cycle-power.json",
        "variance/repeat-sampling.json",
        "report/leaderboard.json",
        "report/leaderboard.csv",
        "report/leaderboard.md",
        "report/leaderboard.html",
    ]
    if cycle_baseline_training_example_count:
        public_outputs.append("baseline-training-examples.jsonl")
    if ablation_delta_count:
        public_outputs.append("ablation-deltas.json")
    return {
        "schema_version": OFFICIAL_AGGREGATE_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "run_type": "official",
        "ablation_filter": config.ablation,
        "labels_sha256": labels_sha256,
        "model_keys": list(config.model_keys),
        "model_registry_path": (
            str(config.model_registry_path)
            if config.model_registry_path is not None
            else None
        ),
        "baseline_training_examples_path": (
            str(config.baseline_training_examples_path)
            if config.baseline_training_examples_path is not None
            else None
        ),
        "baseline_model_ids": [
            baseline_id.value for baseline_id in _scored_baseline_ids()
        ]
        if baseline_artifacts.run_records
        else [],
        "baseline_training_period": (
            dict(baseline_artifacts.training_period)
            if baseline_artifacts.training_period is not None
            else None
        ),
        "brier_skill_score_reference_model_id": (
            baseline_reference.model_id if baseline_reference is not None else None
        ),
        "registry_model_keys": list(registry_model_keys),
        "expected_model_keys": list(expected_model_keys),
        "dispatch_provenance": (
            dict(dispatch_provenance) if dispatch_provenance is not None else None
        ),
        "allow_incomplete_model_set": config.allow_incomplete_model_set,
        "allow_no_baselines": config.allow_no_baselines,
        "deferred_ablations": list(config.deferred_ablations),
        "cycle_baseline_training_example_count": (
            cycle_baseline_training_example_count
        ),
        "ablation_delta_count": ablation_delta_count,
        "first_cycle_ablation_plan": {
            "required_ablations": ["full_packet", "metadata_only"],
            "deferred_ablations": ["judge_removed"],
            "defer_reason": (
                "judge_removed roughly doubles full-document model cost and is "
                "deferred until budget sign-off; metadata_only remains the "
                "required low-cost run-1 ablation."
            ),
        },
        "packet_token_budget": dict(packet_token_budget),
        "generated_at": _format_datetime(generated_at),
        "expected_matrix_rows": len(expected_rows),
        "case_count": len({case_id for case_id, _ablation, _model in expected_rows}),
        "ablation_count": len(
            {_ablation for _case_id, _ablation, _model in expected_rows}
        ),
        "model_count": len(summaries),
        "accounting_record_count": len(accounting_records),
        "cycle_power": dict(cycle_power_record),
        "repeat_variance_summary": [
            dict(row) for row in _repeat_variance_summary_rows(repeat_variance_report)
        ],
        "public_outputs": public_outputs,
        "private_debug_outputs": private_debug_outputs,
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
    if relative_path == "cycle-power.json":
        return "cycle_power"
    if relative_path == "scores.json":
        return "score_summary"
    if relative_path == "unit-scores.jsonl":
        return "unit_scores"
    return "official_artifact"


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return read_jsonl_objects(
        path,
        error_factory=OfficialAggregationError,
        missing_message=lambda missing_path: f"JSONL artifact missing: {missing_path}",
        non_object_message=lambda line_path, line_number: (
            f"{line_path} line {line_number} is not an object"
        ),
    )


def _read_json_object(path: Path) -> JsonRecord:
    return read_json_object(
        path,
        error_factory=OfficialAggregationError,
        missing_message=lambda missing_path: f"JSON artifact missing: {missing_path}",
        non_object_message=lambda object_path: f"{object_path} is not a JSON object",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_object(
        path,
        payload,
        indent=2,
        sort_keys=True,
        trailing_newline=True,
    )


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    write_jsonl_objects(path, records, sort_keys=True)


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


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OfficialAggregationError(f"{field_name} must contain objects")
    return cast(Mapping[str, Any], value)


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


def _metadata_str(record: Mapping[str, Any], field_name: str) -> str | None:
    metadata_value = record.get("metadata")
    if metadata_value is None:
        return None
    if not isinstance(metadata_value, Mapping):
        raise OfficialAggregationError("metadata must be an object")
    metadata = cast(Mapping[str, object], metadata_value)
    value = metadata.get(field_name)
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


def _optional_nonnegative_int(
    record: Mapping[str, Any],
    field_name: str,
) -> int | None:
    value = _optional_int(record, field_name)
    if value is None:
        return None
    if value < 0:
        raise OfficialAggregationError(f"{field_name} must be non-negative")
    return value


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_hex_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise OfficialAggregationError(f"{field_name} must be a lowercase SHA-256 hex")


def _format_datetime(value: datetime) -> str:
    return format_utc_iso_z(value)


if __name__ == "__main__":
    raise SystemExit(main())
