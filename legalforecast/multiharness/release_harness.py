"""Release-backed adapter protocol and public-safe normalized receipts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

from legalforecast._json_io import write_json_object_safe
from legalforecast.contracts import (
    FORECAST_RELEASE_V1,
    RAW_BYTES_PREFIXED_SHA256_V1,
    RELEASE_HARNESS_RECEIPT_V1,
)
from legalforecast.evals.output_parser import (
    ParsedModelOutput,
    parse_model_output,
    parsed_output_from_public_record,
    public_parser_record,
)
from legalforecast.immutable_io import (
    ImmutableIOError,
    read_single_link_file,
    write_file_create_only,
)
from legalforecast.multiharness.adapters import HarnessAdapter, SolverInputAdapter
from legalforecast.multiharness.artifacts import project_lfb_adapter_record
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SolverInputEntry,
)
from legalforecast.multiharness.spec import (
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import (
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
)
from legalforecast.release.models import ForecastRelease, LabelsRelease

if TYPE_CHECKING:
    from legalforecast.multiharness.runner import MultiHarnessRun

RELEASE_HARNESS_RECEIPT_SCHEMA_VERSION = str(RELEASE_HARNESS_RECEIPT_V1)
RELEASE_FORECAST_OUTPUT_ARTIFACT_ID = "release-forecast-output-private"
RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID = "release-harness-transcript-private"
RELEASE_HARNESS_TRACKS = frozenset({"native", "neutral"})
RELEASE_HARNESS_RECEIPT_NAME = "release-harness-receipt.json"
RELEASE_HARNESS_LFB_RECORD_NAME = "lfb-inspect-record.json"
RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME = "private-logs/lfb-inspect-record.json"


class ReleaseHarnessError(ValueError):
    """Raised when an adapter violates the release-backed harness protocol."""


@dataclass(frozen=True, slots=True)
class ReleaseHarnessReceipt:
    """One normalized, public-safe receipt shared by every harness track."""

    content: Mapping[str, Any]
    receipt_sha256: str

    def __post_init__(self) -> None:
        validate_public_record(dict(self.content), "release harness receipt")
        _validate_release_receipt_content(self.content)
        validate_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != release_record_sha256(self.content):
            raise ReleaseHarnessError("release harness receipt digest does not match")

    def to_record(self) -> dict[str, Any]:
        return {**dict(self.content), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, RELEASE_HARNESS_RECEIPT_SCHEMA_VERSION)
        receipt_sha256 = require_str(record, "receipt_sha256")
        content = {
            key: value for key, value in record.items() if key != "receipt_sha256"
        }
        return cls(content=content, receipt_sha256=receipt_sha256)


@dataclass(frozen=True, slots=True)
class ReleaseHarnessProjection:
    """Normalized receipt plus public and private LFB scoring evidence."""

    receipt: ReleaseHarnessReceipt
    lfb_record: Mapping[str, Any] | None
    private_lfb_record: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class _ReleaseReceiptEvidence:
    """Authenticated row evidence used by projection and aggregate validation."""

    content: Mapping[str, Any]
    raw_output: str
    parsed: ParsedModelOutput
    required_unit_ids: tuple[str, ...]
    track: str
    tool_call_count: int
    release_id: str
    forecast_release_digest: str
    unit_id: str | None
    case_id: str
    transcript_sha256: str
    should_score: bool


def is_release_task(request: RunRequest) -> bool:
    """Return whether a request is bound to the additive release protocol."""

    return request.task.metadata.get("release_schema_version") == str(
        FORECAST_RELEASE_V1
    )


def project_and_write_release_harness_result(
    request: RunRequest,
    result: RunResult,
    workspace: Path,
    solver_input_root: Path | None,
    solver_input_entry: SolverInputEntry | None,
) -> Mapping[str, Any] | None:
    """Write normalized release evidence and return the existing LFB score row."""

    if not is_release_task(request):
        return None
    if solver_input_root is None or solver_input_entry is None:
        raise ReleaseHarnessError(
            "release harness projection requires authenticated solver input"
        )
    projection = project_release_harness_result(
        request,
        result,
        workspace,
        solver_input_root,
        solver_input_entry,
    )
    write_release_json_create_only(
        workspace / RELEASE_HARNESS_RECEIPT_NAME,
        projection.receipt.to_record(),
    )
    if projection.lfb_record is not None:
        if projection.private_lfb_record is None:
            raise AssertionError("private LFB projection is unavailable")
        write_release_json_create_only(
            workspace / RELEASE_HARNESS_LFB_RECORD_NAME,
            projection.lfb_record,
        )
        write_release_json_create_only(
            workspace / RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME,
            projection.private_lfb_record,
        )
    return projection.lfb_record


def validate_resumed_release_harness_result(
    request: RunRequest,
    result: RunResult,
    workspace: Path,
    solver_input_root: Path | None,
    solver_input_entry: SolverInputEntry | None,
) -> Mapping[str, Any] | None:
    """Rebuild and compare exact release evidence before accepting resume."""

    if not is_release_task(request):
        return None
    if solver_input_root is None or solver_input_entry is None:
        raise ReleaseHarnessError(
            "release harness resume requires authenticated solver input"
        )
    projection = project_release_harness_result(
        request,
        result,
        workspace,
        solver_input_root,
        solver_input_entry,
    )
    stored_receipt = ReleaseHarnessReceipt.from_record(
        _read_object(workspace / RELEASE_HARNESS_RECEIPT_NAME, "release receipt")
    )
    if stored_receipt.to_record() != projection.receipt.to_record():
        raise ReleaseHarnessError("stored release receipt does not match")
    _validate_stored_lfb_projection(workspace, projection)
    return projection.lfb_record


def repair_resumed_release_harness_result(
    request: RunRequest,
    result: RunResult,
    workspace: Path,
    solver_input_root: Path | None,
    solver_input_entry: SolverInputEntry | None,
) -> Mapping[str, Any] | None:
    """Idempotently finish trusted derived evidence after an interrupted row."""

    if not is_release_task(request):
        return None
    if solver_input_root is None or solver_input_entry is None:
        raise ReleaseHarnessError(
            "release harness repair requires authenticated solver input"
        )
    projection = project_release_harness_result(
        request,
        result,
        workspace,
        solver_input_root,
        solver_input_entry,
    )
    _validate_or_create_release_record(
        workspace / RELEASE_HARNESS_RECEIPT_NAME,
        projection.receipt.to_record(),
        "release receipt",
    )
    if projection.lfb_record is None:
        _require_release_record_absent(
            workspace / RELEASE_HARNESS_LFB_RECORD_NAME,
            "release LFB record",
        )
        _require_release_record_absent(
            workspace / RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME,
            "private release LFB record",
        )
        return None
    if projection.private_lfb_record is None:
        raise AssertionError("private LFB projection is unavailable")
    _validate_or_create_release_record(
        workspace / RELEASE_HARNESS_LFB_RECORD_NAME,
        projection.lfb_record,
        "release LFB record",
    )
    _validate_or_create_release_record(
        workspace / RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME,
        projection.private_lfb_record,
        "private release LFB record",
    )
    return projection.lfb_record


def run_and_project_solver_input_adapter(
    adapter: HarnessAdapter,
    request: RunRequest,
    workspace: Path,
    solver_input_root: Path | None,
    solver_input_entry: SolverInputEntry | None,
) -> tuple[RunResult, Mapping[str, Any] | None]:
    """Run a plan-only adapter and persist any release-backed projection."""

    release_task = is_release_task(request)
    if release_task and (solver_input_root is None or solver_input_entry is None):
        raise ReleaseHarnessError("release adapter requires authenticated solver input")
    if release_task and not isinstance(adapter, SolverInputAdapter):
        raise ReleaseHarnessError(
            "command adapter does not support authenticated release solver input"
        )
    if solver_input_root is not None and isinstance(adapter, SolverInputAdapter):
        result = adapter.run_with_solver_input(request, workspace, solver_input_root)
    else:
        result = adapter.run(request, workspace)
    if result.request_id != request.request_id:
        raise ValueError("run result request_id does not match request")
    write_json_object_safe(workspace / "result.json", result.to_record())
    if result.status != "succeeded":
        return result, None
    lfb_record = project_and_write_release_harness_result(
        request,
        result,
        workspace,
        solver_input_root,
        solver_input_entry,
    )
    result = _mark_invalid_release_forecast(result, lfb_record)
    if result.status != "succeeded":
        write_json_object_safe(workspace / "result.json", result.to_record())
    return result, lfb_record


def _mark_invalid_release_forecast(
    result: RunResult,
    lfb_record: Mapping[str, Any] | None,
) -> RunResult:
    """Turn invalid or defaulted release forecasts into retryable failures."""

    if not isinstance(lfb_record, Mapping):
        return result
    parser_record = lfb_record.get("parser_output")
    if not isinstance(parser_record, Mapping):
        return result
    parser_record = cast(Mapping[str, Any], parser_record)
    status = parser_record.get("status")
    defaulted_unit_ids = parser_record.get("defaulted_unit_ids", [])
    is_valid = parser_record.get("is_valid") is True
    has_defaults = isinstance(defaulted_unit_ids, list) and bool(
        cast(list[Any], defaulted_unit_ids)
    )
    if is_valid and not has_defaults:
        return result
    summary = dict(result.public_summary)
    parser_issues = parser_record.get("issues", [])
    summary.update(
        {
            "error_type": "InvalidForecastOutput",
            "error_message": "release forecast output failed validation",
            "parser_status": status,
            "parser_issues": parser_issues,
            "defaulted_unit_ids": defaulted_unit_ids,
            "original_result_sha256": result.result_sha256,
        }
    )
    summary["normalized_result_sha256"] = release_record_sha256(
        _normalized_result_digest_payload(
            result,
            status="failed",
            public_summary=summary,
        )
    )
    return replace(result, status="failed", public_summary=summary)


def _normalized_result_digest_payload(
    result: RunResult,
    *,
    status: str,
    public_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the digest payload for a result normalized after adapter output."""

    return {
        "result_id": result.result_id,
        "request_id": result.request_id,
        "status": status,
        "artifacts": [artifact.to_record() for artifact in result.artifacts],
        "public_summary": dict(public_summary),
    }


def collect_release_harness_receipts(
    rows: Iterable[tuple[RunRequest, RunResult, Path]],
) -> tuple[Mapping[str, Any], ...]:
    """Read per-row normalized receipts for the aggregate public artifact."""

    return tuple(
        projection.receipt.to_record()
        for projection in collect_release_harness_projections(rows)
    )


def collect_release_harness_projections(
    rows: Iterable[tuple[RunRequest, RunResult, Path]],
) -> tuple[ReleaseHarnessProjection, ...]:
    """Rebuild and validate all durable release receipts and LFB projections."""

    projections: list[ReleaseHarnessProjection] = []
    for request, result, workspace in rows:
        if not is_release_task(request):
            continue
        receipt_path = workspace / RELEASE_HARNESS_RECEIPT_NAME
        if result.status != "succeeded" and not receipt_path.is_file():
            continue
        if result.request_id != request.request_id:
            raise ReleaseHarnessError("release result request does not match row")
        packet_sha256, prompt_sha256, forecast_release_digest = _release_task_metadata(
            request
        )
        evidence = _release_receipt_evidence(
            request,
            result,
            workspace,
            packet_sha256=packet_sha256,
            prompt_sha256=prompt_sha256,
            forecast_release_digest=forecast_release_digest,
        )
        receipt = ReleaseHarnessReceipt.from_record(
            _read_object(receipt_path, "release receipt")
        )
        projection = _projection_from_evidence(request, result, evidence)
        if receipt.to_record() != projection.receipt.to_record():
            raise ReleaseHarnessError("release receipt does not match row evidence")
        _validate_stored_lfb_projection(workspace, projection)
        projections.append(projection)
    return tuple(projections)


def project_release_harness_result(
    request: RunRequest,
    result: RunResult,
    workspace: Path,
    solver_input_root: Path,
    solver_input_entry: SolverInputEntry,
) -> ReleaseHarnessProjection:
    """Authenticate one adapter forecast and project shared receipt/scoring rows."""

    metadata = request.task.metadata
    if metadata.get("release_schema_version") != str(FORECAST_RELEASE_V1):
        raise ReleaseHarnessError("task is not backed by forecast-release.v1")
    if result.request_id != request.request_id or result.status != "succeeded":
        raise ReleaseHarnessError(
            "release harness projection requires a successful result"
        )
    packet_sha256, prompt_sha256, forecast_release_digest = (
        _authenticated_release_metadata(
            request,
            solver_input_root,
            solver_input_entry,
        )
    )
    evidence = _release_receipt_evidence(
        request,
        result,
        workspace,
        packet_sha256=packet_sha256,
        prompt_sha256=prompt_sha256,
        forecast_release_digest=forecast_release_digest,
    )
    return _projection_from_evidence(request, result, evidence)


RELEASE_SCORE_SCHEMA_VERSION = "legalforecast.multiharness.release_score.v1"
RELEASE_FAILURE_POLICY_ID = "failure-brier-1.0-v1"


def score_multiharness_release(
    run: MultiHarnessRun,
    forecast_release: ForecastRelease,
    labels_release: LabelsRelease,
    *,
    failure_brier: float = 1.0,
) -> Mapping[str, Any]:
    """Score selected release units, retaining complete failure accounting.

    The terminal benchmark treats an execution failure as a scored unit with a
    fixed Brier penalty of ``1.0``.  It never invents a probability for a
    timeout, crash, denial, skipped row, or invalid model response.  Missing
    rows remain selection/incompleteness diagnostics and are separate from
    execution failures.  Successful rows are scored from their authenticated
    public parser projection.
    """

    if isinstance(failure_brier, bool):
        raise ValueError("failure_brier must be numeric")
    failure_brier = float(failure_brier)
    if failure_brier != 1.0:
        raise ValueError("failure_brier is fixed at 1.0 for terminal releases")
    if labels_release.release_id != forecast_release.release_id:
        raise ValueError("labels release identity differs from forecast release")
    if labels_release.forecast_release_digest != forecast_release.release_digest:
        raise ValueError("labels release binds a different forecast release")

    units_by_id = {unit.unit_id: unit for unit in forecast_release.prediction_units}
    labels_by_id = {
        label.unit_id: label.outcome for label in labels_release.unit_outcomes
    }
    expected_scoreable = {
        unit.unit_id for unit in forecast_release.prediction_units if unit.should_score
    }
    if set(labels_by_id) != expected_scoreable:
        raise ValueError("labels release does not match forecast scoreable unit set")

    selected_tasks = tuple(run.selection.tasks)
    selected_task_ids = tuple(task.task_id for task in selected_tasks)
    selected_unit_ids: list[str] = []
    selected_case_ids: list[str] = []
    selected_units_by_task: dict[str, tuple[str, ...]] = {}
    release_case_ids = {case.case_id for case in forecast_release.cases}
    for task in selected_tasks:
        metadata = task.metadata
        case_id = metadata.get("case_id")
        if not isinstance(case_id, str) or case_id not in release_case_ids:
            raise ValueError("selected release task has an unknown case_id")
        selected_case_ids.append(case_id)
        raw_required = metadata.get("required_unit_ids")
        if not isinstance(raw_required, list | tuple) or not raw_required:
            raise ValueError("selected release task has no required_unit_ids")
        required = tuple(cast(list[Any] | tuple[Any, ...], raw_required))
        if any(not isinstance(unit_id, str) for unit_id in required):
            raise ValueError("selected release task unit IDs must be strings")
        unknown = set(required).difference(units_by_id)
        if unknown or any(
            units_by_id[unit_id].case_id != case_id for unit_id in required
        ):
            raise ValueError("selected release task units do not match its case")
        if metadata.get("case_batch") is True:
            expected_case_units = tuple(
                sorted(
                    unit.unit_id
                    for unit in forecast_release.prediction_units
                    if unit.case_id == case_id
                )
            )
            if required != expected_case_units:
                raise ValueError(
                    "selected case task does not contain the complete case unit set"
                )
        _validate_selected_release_task_metadata(
            task,
            required_unit_ids=required,
            units_by_id=units_by_id,
            forecast_release=forecast_release,
        )
        selected_units_by_task[task.task_id] = required
        selected_unit_ids.extend(required)
    if len(selected_unit_ids) != len(set(selected_unit_ids)):
        raise ValueError("selection repeats a release prediction unit")
    scoreable_selected_ids = tuple(
        unit_id for unit_id in selected_unit_ids if units_by_id[unit_id].should_score
    )
    if not scoreable_selected_ids:
        raise ValueError("selection contains no scoreable release units")

    rows_by_task: dict[str, list[Any]] = {}
    for row in run.rows:
        rows_by_task.setdefault(row.task.task_id, []).append(row)
    missing_task_ids = tuple(
        task_id for task_id in selected_task_ids if task_id not in rows_by_task
    )
    treatment_rows: dict[tuple[str, str, str], list[Any]] = {}
    selected_task_id_set = set(selected_task_ids)
    for task_id, rows in rows_by_task.items():
        if task_id not in selected_task_id_set:
            continue
        for row in rows:
            treatment_key = _release_treatment_key(row)
            treatment_rows.setdefault(treatment_key, []).append(row)

    model_reports: list[dict[str, Any]] = []
    for _treatment_key, rows in sorted(treatment_rows.items()):
        known_tracks = {
            track
            for row in rows
            for track in (_release_row_track(row),)
            if track is not None
        }
        if len(known_tracks) > 1:
            raise ValueError(
                "release treatment rows disagree about harness track: "
                + ", ".join(sorted(known_tracks))
            )
        known_track = next(iter(known_tracks), None)
        for row in rows:
            _release_treatment_id(row, known_track=known_track)
        treatment_id = _release_treatment_id(
            rows[0],
            known_track=known_track,
        )
        # One adapter/model treatment must have at most one row for each task.
        rows_by_selected_task: dict[str, Any] = {}
        for row in rows:
            task_id = row.task.task_id
            if task_id in rows_by_selected_task:
                raise ValueError(
                    f"treatment {treatment_id} has duplicate row for {task_id}"
                )
            rows_by_selected_task[task_id] = row
        model_missing_task_ids = tuple(
            task_id
            for task_id in selected_task_ids
            if task_id not in rows_by_selected_task
        )
        model_missing_unit_ids = tuple(
            unit_id
            for task_id in model_missing_task_ids
            for unit_id in selected_units_by_task[task_id]
            if units_by_id[unit_id].should_score
        )
        missing_units = [
            _release_missing_unit(
                task=task,
                unit_id=unit_id,
                outcome=labels_by_id[unit_id],
            )
            for task_id in model_missing_task_ids
            for task in selected_tasks
            if task.task_id == task_id
            for unit_id in selected_units_by_task[task_id]
            if units_by_id[unit_id].should_score
        ]
        unit_scores: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        usage: list[dict[str, Any]] = []
        for task in selected_tasks:
            row = rows_by_selected_task.get(task.task_id)
            required = selected_units_by_task[task.task_id]
            scoreable = tuple(
                unit_id for unit_id in required if units_by_id[unit_id].should_score
            )
            if row is None:
                continue
            result = row.result
            summary = dict(result.public_summary)
            usage_record = _release_usage_record(summary)
            if usage_record:
                usage.append({"task_id": task.task_id, **usage_record})
            parser = _release_parser_projection(row)
            if result.status != "succeeded":
                failure_kind = _release_failure_kind(result.status, summary)
                for unit_id in scoreable:
                    failures.append(
                        _release_failure_unit(
                            task=task,
                            unit_id=unit_id,
                            outcome=labels_by_id[unit_id],
                            status=result.status,
                            failure_kind=failure_kind,
                            failure_brier=failure_brier,
                            summary=summary,
                            usage=usage_record,
                            parser=None,
                        )
                    )
                continue
            if parser is None:
                for unit_id in scoreable:
                    failures.append(
                        _release_failure_unit(
                            task=task,
                            unit_id=unit_id,
                            outcome=labels_by_id[unit_id],
                            status="failed",
                            failure_kind="projection_missing",
                            failure_brier=failure_brier,
                            summary=summary,
                            usage=usage_record,
                            parser=None,
                        )
                    )
                continue
            parser_record = parser.get("parser_output")
            if isinstance(parser_record, Mapping):
                parser_record = cast(Mapping[str, Any], parser_record)
            else:
                parser_record = parser
            try:
                parsed = parsed_output_from_public_record(parser_record)
            except (TypeError, ValueError):
                parsed = None
            if (
                parsed is None
                or not parsed.is_valid
                or tuple(parsed.required_unit_ids) != required
            ):
                failure_kind = "invalid_output"
                for unit_id in scoreable:
                    failures.append(
                        _release_failure_unit(
                            task=task,
                            unit_id=unit_id,
                            outcome=labels_by_id[unit_id],
                            status="failed",
                            failure_kind=failure_kind,
                            failure_brier=failure_brier,
                            summary=summary,
                            usage=usage_record,
                            parser=parser_record,
                        )
                    )
                continue
            for unit_id in scoreable:
                prediction = parsed.prediction_for(unit_id)
                if prediction.defaulted:
                    failures.append(
                        _release_failure_unit(
                            task=task,
                            unit_id=unit_id,
                            outcome=labels_by_id[unit_id],
                            status="failed",
                            failure_kind="defaulted_prediction",
                            failure_brier=failure_brier,
                            summary=summary,
                            usage=usage_record,
                            parser=parser_record,
                        )
                    )
                    continue
                probability = prediction.probability_fully_dismissed
                unit_scores.append(
                    _release_success_unit(
                        task=task,
                        unit_id=unit_id,
                        outcome=labels_by_id[unit_id],
                        probability=probability,
                        parser_status=parsed.status.value,
                        raw_output_sha256=parsed.raw_output_sha256,
                        usage=usage_record,
                    )
                )

        # Unit-level failures are intentionally in the score denominator.
        all_units = sorted(
            (*unit_scores, *failures),
            key=lambda record: (record["case_id"], record["unit_id"]),
        )
        by_case: dict[str, list[dict[str, Any]]] = {}
        for record in all_units:
            by_case.setdefault(record["case_id"], []).append(record)
        micro = _mean(record["brier"] for record in all_units) if all_units else None
        equal_case = (
            _mean(
                _mean(record["brier"] for record in case_records)
                for case_records in by_case.values()
            )
            if by_case
            else None
        )
        headline_metrics_available = not model_missing_task_ids
        if not headline_metrics_available:
            micro = None
            equal_case = None
        expected_count = len(scoreable_selected_ids)
        failed_count = len(failures)
        completed_count = len(unit_scores)
        invalid_count = sum(
            record["failure_kind"]
            in {"invalid_output", "defaulted_prediction", "projection_missing"}
            for record in failures
        )
        model_reports.append(
            {
                "treatment_id": treatment_id,
                "adapter_id": rows[0].adapter_manifest.adapter_id,
                "model_key": rows[0].model_config.model_key,
                "case_count": len(by_case),
                "unit_count": len(all_units),
                "completed_unit_count": len(unit_scores),
                "failed_unit_count": len(failures),
                "invalid_unit_count": invalid_count,
                "selection_complete": not model_missing_task_ids,
                "missing_task_ids": list(model_missing_task_ids),
                "missing_unit_ids": list(model_missing_unit_ids),
                "selection_incomplete_unit_count": len(model_missing_unit_ids),
                "selected_unit_count": expected_count,
                "reported_unit_count": len(all_units),
                "missing_unit_count": len(missing_units),
                "headline_metrics_available": headline_metrics_available,
                "headline_metrics_suppressed_reason": (
                    "selection_incomplete" if not headline_metrics_available else None
                ),
                "completion_rate": completed_count / expected_count,
                "failure_rate": failed_count / expected_count,
                "micro_brier": micro,
                "equal_case_brier": equal_case,
                "unit_scores": all_units,
                "failures": failures,
                "selection_missing": missing_units,
                "unit_records": sorted(
                    (*all_units, *missing_units),
                    key=lambda record: (record["case_id"], record["unit_id"]),
                ),
                "usage": usage,
            }
        )

    selection_complete = not missing_task_ids
    headline_metrics_available = (
        bool(model_reports)
        and selection_complete
        and all(report["headline_metrics_available"] for report in model_reports)
    )
    headline_metrics_suppressed_reason = (
        None
        if headline_metrics_available
        else "selection_incomplete"
        if not selection_complete
        else "no_treatment_rows"
    )
    return {
        "schema_version": RELEASE_SCORE_SCHEMA_VERSION,
        "failure_policy": {
            "policy_id": RELEASE_FAILURE_POLICY_ID,
            "failure_brier": failure_brier,
            "description": (
                "execution and invalid-output failures receive a fixed Brier penalty"
            ),
        },
        "selection": {
            "selected_task_ids": list(selected_task_ids),
            "selected_case_ids": sorted(set(selected_case_ids)),
            "selected_unit_ids": list(scoreable_selected_ids),
            "expected_unit_count": len(scoreable_selected_ids),
            "missing_task_ids": list(missing_task_ids),
            "incomplete_unit_count": sum(
                len(
                    tuple(
                        unit_id
                        for unit_id in selected_units_by_task[task_id]
                        if units_by_id[unit_id].should_score
                    )
                )
                for task_id in missing_task_ids
            ),
            "complete": selection_complete,
        },
        "headline_metrics_available": headline_metrics_available,
        "headline_metrics_suppressed_reason": headline_metrics_suppressed_reason,
        "models": model_reports,
    }


def _validate_selected_release_task_metadata(
    task: Any,
    *,
    required_unit_ids: tuple[str, ...],
    units_by_id: Mapping[str, Any],
    forecast_release: ForecastRelease,
) -> None:
    """Bind selected task metadata to the exact forecast release contract."""

    metadata = task.metadata
    expected_schema = str(FORECAST_RELEASE_V1)
    if metadata.get("release_schema_version") != expected_schema:
        raise ValueError("selected release task schema does not match forecast")
    if metadata.get("release_id") != forecast_release.release_id:
        raise ValueError("selected release task release_id does not match forecast")
    if metadata.get("forecast_release_digest") != forecast_release.release_digest:
        raise ValueError(
            "selected release task forecast_release_digest does not match forecast"
        )

    raw_unit_ids = metadata.get("unit_ids")
    if raw_unit_ids is not None:
        if not isinstance(raw_unit_ids, list | tuple):
            raise ValueError(
                "selected release task unit_ids do not match required units"
            )
        unit_ids = cast(list[Any] | tuple[Any, ...], raw_unit_ids)
        if tuple(unit_ids) != (*required_unit_ids,):
            raise ValueError(
                "selected release task unit_ids do not match required units"
            )
    expected_scoreable = tuple(
        unit_id for unit_id in required_unit_ids if units_by_id[unit_id].should_score
    )
    raw_scoreable = metadata.get("scoreable_unit_ids")
    if raw_scoreable is not None:
        if not isinstance(raw_scoreable, list | tuple):
            raise ValueError(
                "selected release task scoreable_unit_ids do not match forecast"
            )
        scoreable_ids = cast(list[Any] | tuple[Any, ...], raw_scoreable)
        if tuple(scoreable_ids) != (*expected_scoreable,):
            raise ValueError(
                "selected release task scoreable_unit_ids do not match forecast"
            )
    should_score = metadata.get("should_score")
    if not isinstance(should_score, bool) or should_score != bool(expected_scoreable):
        raise ValueError("selected release task should_score does not match forecast")

    raw_unit_id = metadata.get("unit_id")
    if raw_unit_id is not None and (
        not isinstance(raw_unit_id, str)
        or len(required_unit_ids) != 1
        or raw_unit_id != required_unit_ids[0]
    ):
        raise ValueError("selected release task unit_id does not match required units")

    raw_unit_metadata = metadata.get("unit_metadata")
    if raw_unit_metadata is None:
        return
    if not isinstance(raw_unit_metadata, list):
        raise ValueError("selected release task unit_metadata does not match units")
    unit_metadata = cast(list[Any], raw_unit_metadata)
    if len(unit_metadata) != len(required_unit_ids):
        raise ValueError("selected release task unit_metadata does not match units")
    records_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_record in unit_metadata:
        if not isinstance(raw_record, Mapping):
            raise ValueError("selected release task unit_metadata is invalid")
        record = cast(Mapping[str, Any], raw_record)
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or unit_id in records_by_id:
            raise ValueError("selected release task unit_metadata has invalid IDs")
        records_by_id[unit_id] = record
    if tuple(records_by_id) != required_unit_ids:
        raise ValueError("selected release task unit_metadata IDs do not match units")
    for unit_id in required_unit_ids:
        value = records_by_id[unit_id].get("should_score")
        if value is not units_by_id[unit_id].should_score:
            raise ValueError(
                "selected release task unit_metadata should_score does not match"
            )


def _release_treatment_key(row: Any) -> tuple[str, str, str]:
    record = cast(Mapping[str, Any] | None, row.lfb_record)
    expected = {
        "adapter_id": row.adapter_manifest.adapter_id,
        "adapter_version": row.adapter_manifest.adapter_version,
        "model_key": row.model_config.model_key,
    }
    if isinstance(record, Mapping):
        for field_name, expected_value in expected.items():
            value = record.get(field_name)
            if value is not None and value != expected_value:
                raise ValueError(
                    f"release row {field_name} does not match treatment identity"
                )
    summary = row.result.public_summary
    for field_name, expected_value in expected.items():
        value = summary.get(field_name)
        if value is not None and value != expected_value:
            raise ValueError(
                f"release result {field_name} does not match treatment identity"
            )
    return (
        row.adapter_manifest.adapter_id,
        row.adapter_manifest.adapter_version,
        row.model_config.model_key,
    )


def _release_row_track(row: Any) -> str | None:
    """Read a row's optional track while checking all available copies agree."""

    record = cast(Mapping[str, Any] | None, row.lfb_record)
    track_candidates: list[str] = []
    if isinstance(record, Mapping):
        metadata = record.get("metadata")
        if isinstance(metadata, Mapping):
            record_metadata = cast(Mapping[str, Any], metadata)
            raw_track = record_metadata.get("harness_track")
            if isinstance(raw_track, str):
                track_candidates.append(raw_track)
        raw_track = record.get("run_label")
        if isinstance(raw_track, str):
            track_candidates.append(raw_track)
    raw_track = row.result.public_summary.get("harness_track")
    if isinstance(raw_track, str):
        track_candidates.append(raw_track)
    if len(set(track_candidates)) > 1:
        raise ValueError("release row harness track does not match treatment identity")
    track = track_candidates[0] if track_candidates else None
    if track is not None and track not in RELEASE_HARNESS_TRACKS:
        raise ValueError("release row harness track is invalid")
    return track


def _release_treatment_id(row: Any, *, known_track: str | None = None) -> str:
    record = cast(Mapping[str, Any] | None, row.lfb_record)
    treatment_key = _release_treatment_key(row)
    row_track = _release_row_track(row)
    if row_track is not None and known_track is not None and row_track != known_track:
        raise ValueError("release treatment rows disagree about harness track")
    track = row_track or known_track or "unknown"
    treatment_id = f"{track}:{treatment_key[0]}:{treatment_key[1]}:{treatment_key[2]}"
    if isinstance(record, Mapping):
        raw_treatment_id = record.get("treatment_id")
        if raw_treatment_id is not None and raw_treatment_id != treatment_id:
            raise ValueError(
                "release row treatment_id does not match treatment identity"
            )
    return treatment_id


def _release_parser_projection(row: Any) -> Mapping[str, Any] | None:
    record = cast(Mapping[str, Any] | None, row.lfb_record)
    if not isinstance(record, Mapping):
        return None
    parser = record.get("parser_output")
    if isinstance(parser, Mapping):
        return record
    return None


def _release_usage_record(summary: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "provider_request_count",
        "request_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost",
    )
    return {key: summary[key] for key in keys if key in summary}


def _release_failure_kind(status: str, summary: Mapping[str, Any]) -> str:
    error_type = summary.get("error_type")
    if isinstance(error_type, str) and error_type.strip():
        return error_type
    if status == "interrupted":
        return "interrupted"
    return status


def _release_failure_unit(
    *,
    task: Any,
    unit_id: str,
    outcome: int,
    status: str,
    failure_kind: str,
    failure_brier: float,
    summary: Mapping[str, Any],
    usage: Mapping[str, Any],
    parser: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "case_id": task.metadata["case_id"],
        "unit_id": unit_id,
        "outcome": outcome,
        "probability_fully_dismissed": None,
        "brier": failure_brier,
        "status": status,
        "failure_kind": failure_kind,
        "error_type": summary.get("error_type"),
        "error_message": summary.get("error_message"),
        "parser_status": parser.get("status") if parser is not None else None,
        "parser_issues": parser.get("issues", []) if parser is not None else [],
        "parser_defaulted_unit_ids": (
            parser.get("defaulted_unit_ids", []) if parser is not None else []
        ),
        "usage": dict(usage),
        "scored": True,
    }


def _release_missing_unit(
    *,
    task: Any,
    unit_id: str,
    outcome: int,
) -> dict[str, Any]:
    """Represent a selected unit with no row without treating it as a failure."""

    return {
        "case_id": task.metadata["case_id"],
        "unit_id": unit_id,
        "outcome": outcome,
        "probability_fully_dismissed": None,
        "brier": None,
        "status": "selection_missing",
        "failure_kind": "selection_missing",
        "error_type": None,
        "error_message": None,
        "parser_status": None,
        "parser_issues": [],
        "parser_defaulted_unit_ids": [],
        "usage": {},
        "scored": False,
    }


def _release_success_unit(
    *,
    task: Any,
    unit_id: str,
    outcome: int,
    probability: float,
    parser_status: str,
    raw_output_sha256: str,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": task.metadata["case_id"],
        "unit_id": unit_id,
        "outcome": outcome,
        "probability_fully_dismissed": probability,
        "brier": (probability - outcome) ** 2,
        "status": "scored",
        "failure_kind": None,
        "parser_status": parser_status,
        "raw_output_sha256": raw_output_sha256,
        "usage": dict(usage),
        "scored": True,
    }


def _mean(values: Iterable[float]) -> float:
    values_tuple = tuple(values)
    if not values_tuple:
        raise ValueError("cannot calculate a mean over no values")
    return sum(values_tuple) / len(values_tuple)


def _projection_from_evidence(
    request: RunRequest,
    result: RunResult,
    evidence: _ReleaseReceiptEvidence,
) -> ReleaseHarnessProjection:
    receipt = ReleaseHarnessReceipt(
        content=evidence.content,
        receipt_sha256=release_record_sha256(evidence.content),
    )
    if not evidence.should_score and (
        evidence.parsed.is_valid and not evidence.parsed.defaulted_unit_ids
    ):
        return ReleaseHarnessProjection(
            receipt=receipt,
            lfb_record=None,
            private_lfb_record=None,
        )
    summary = result.public_summary
    adapter_id = request.adapter.adapter_id
    subject_id = evidence.unit_id or evidence.case_id
    inspect_metadata: dict[str, Any] = {
        "forecast_release_digest": evidence.forecast_release_digest,
        "harness_track": evidence.track,
        "release_id": evidence.release_id,
        "should_score": str(evidence.should_score).lower(),
        "transcript_sha256": evidence.transcript_sha256,
    }
    if evidence.unit_id is not None:
        inspect_metadata["unit_id"] = evidence.unit_id
    inspect = {
        "sample_id": subject_id,
        "candidate_id": f"{evidence.release_id}:{subject_id}",
        "case_id": evidence.case_id,
        "related_family_id": None,
        "mdl_family_id": None,
        "solver_id": f"{adapter_id}:{request.model_key}",
        "solver_kind": f"release_{evidence.track}",
        "run_label": evidence.track,
        "ablation": "none",
        "raw_output": evidence.raw_output,
        "raw_output_sha256": evidence.parsed.raw_output_sha256,
        "required_unit_ids": list(evidence.required_unit_ids),
        "request_count": _summary_request_count(summary),
        "input_tokens": _optional_non_negative_summary_int(summary, "input_tokens"),
        "output_tokens": _optional_non_negative_summary_int(summary, "output_tokens"),
        "estimated_cost": _optional_non_negative_summary_number(
            summary, "estimated_cost"
        ),
        "tool_call_logs": [
            {"tool_call_index": index + 1} for index in range(evidence.tool_call_count)
        ],
        "execution_backend": _summary_execution_backend(summary, evidence.track),
        "metadata": inspect_metadata,
    }
    projected = project_lfb_adapter_record(
        inspect,
        request,
        artifacts=result.artifacts,
    )
    public_lfb = dict(projected.inspect_record)
    public_lfb.pop("raw_output", None)
    public_lfb["parser_output"] = public_parser_record(evidence.parsed)
    validate_public_record(public_lfb, "public release LFB record")
    return ReleaseHarnessProjection(
        receipt=receipt,
        lfb_record=public_lfb,
        private_lfb_record=projected.inspect_record,
    )


def _release_receipt_evidence(
    request: RunRequest,
    result: RunResult,
    workspace: Path,
    *,
    packet_sha256: str,
    prompt_sha256: str,
    forecast_release_digest: str,
) -> _ReleaseReceiptEvidence:
    output_artifact = _required_output_artifact(result)
    raw_output_bytes = _read_workspace_artifact(workspace, output_artifact)
    transcript_artifact = _required_transcript_artifact(result)
    transcript_bytes = _read_workspace_artifact(workspace, transcript_artifact)
    try:
        raw_output = raw_output_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ReleaseHarnessError(
            "release forecast output must be strict UTF-8"
        ) from exc

    metadata = request.task.metadata
    required_unit_ids = _required_string_list(metadata, "required_unit_ids")
    parsed = parse_model_output(raw_output, required_unit_ids=required_unit_ids)
    summary = result.public_summary
    track = _required_summary_str(summary, "harness_track")
    if track not in RELEASE_HARNESS_TRACKS:
        raise ReleaseHarnessError("harness_track must be neutral or native")
    transcript_sha256 = _required_summary_str(summary, "transcript_sha256")
    validate_sha256(transcript_sha256, "transcript_sha256")
    if transcript_sha256 != transcript_artifact.sha256:
        raise ReleaseHarnessError("transcript commitment does not match artifact")
    _validate_transcript_binding(
        transcript_bytes,
        request=request,
        packet_sha256=packet_sha256,
        prompt_sha256=prompt_sha256,
        output_sha256=output_artifact.sha256,
    )

    tool_call_count = _non_negative_summary_int(summary, "tool_call_count")
    adapter_id = request.adapter.adapter_id
    adapter_version = request.adapter.adapter_version
    release_id = require_release_metadata_str(metadata, "release_id")
    raw_unit_id = metadata.get("unit_id")
    if raw_unit_id is not None and (
        not isinstance(raw_unit_id, str) or not raw_unit_id.strip()
    ):
        raise ReleaseHarnessError("task metadata unit_id must be a non-empty string")
    unit_id = raw_unit_id
    case_id = require_release_metadata_str(metadata, "case_id")
    should_score = _required_metadata_bool(metadata, "should_score")
    tools = _required_summary_string_list(summary, "allowed_tools")
    content: dict[str, Any] = {
        "schema_version": RELEASE_HARNESS_RECEIPT_SCHEMA_VERSION,
        "receipt_id": f"{request.request_id}:{adapter_id}",
        "release_id": release_id,
        "forecast_release_digest": forecast_release_digest,
        "case_id": case_id,
        "unit_id": unit_id,
        "should_score": should_score,
        "packet_sha256": packet_sha256,
        "prompt_sha256": prompt_sha256,
        "harness_track": track,
        "treatment_id": f"{track}:{adapter_id}:{adapter_version}:{request.model_key}",
        "adapter": {
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "model_key": request.model_key,
        },
        "tools": {
            "policy": _required_summary_str(summary, "tool_policy"),
            "allowed": list(tools),
            "call_count": tool_call_count,
        },
        "network_policy": request.sandbox_policy.network_policy,
        "limits": {
            "timeout_seconds": request.sandbox_policy.timeout_seconds,
            "pids": request.sandbox_policy.pids_limit,
            "memory": request.sandbox_policy.memory_limit,
            "cpu": request.sandbox_policy.cpu_limit,
        },
        "transcript_sha256": transcript_sha256,
        "result": {
            "run_result_sha256": result.result_sha256,
            "forecast_output_sha256": output_artifact.sha256,
            "parser_output": public_parser_record(parsed),
        },
    }
    return _ReleaseReceiptEvidence(
        content=content,
        raw_output=raw_output,
        parsed=parsed,
        required_unit_ids=required_unit_ids,
        track=track,
        tool_call_count=tool_call_count,
        release_id=release_id,
        forecast_release_digest=forecast_release_digest,
        unit_id=unit_id,
        case_id=case_id,
        transcript_sha256=transcript_sha256,
        should_score=should_score,
    )


def _validate_transcript_binding(
    payload: bytes,
    *,
    request: RunRequest,
    packet_sha256: str,
    prompt_sha256: str,
    output_sha256: str,
) -> None:
    try:
        value: object = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseHarnessError(
            "release transcript must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ReleaseHarnessError("release transcript must be an object")
    transcript = cast(dict[str, Any], value)
    expected = {
        "request_sha256": request.request_sha256,
        "packet_sha256": packet_sha256,
        "prompt_sha256": prompt_sha256,
        "response_sha256": output_sha256,
    }
    for field_name, expected_value in expected.items():
        if transcript.get(field_name) != expected_value:
            raise ReleaseHarnessError(
                f"release transcript {field_name} does not match row evidence"
            )


def _required_output_artifact(result: RunResult) -> ArtifactRecord:
    matches = tuple(
        artifact
        for artifact in result.artifacts
        if artifact.artifact_id == RELEASE_FORECAST_OUTPUT_ARTIFACT_ID
    )
    if len(matches) != 1:
        raise ReleaseHarnessError(
            "release adapter result must contain one forecast output artifact"
        )
    artifact = matches[0]
    _require_private_artifact(artifact, "release forecast output")
    return artifact


def _required_transcript_artifact(result: RunResult) -> ArtifactRecord:
    matches = tuple(
        artifact
        for artifact in result.artifacts
        if artifact.artifact_id == RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID
    )
    if len(matches) != 1:
        raise ReleaseHarnessError(
            "release adapter result must contain one transcript artifact"
        )
    artifact = matches[0]
    _require_private_artifact(artifact, "release transcript")
    return artifact


def _require_private_artifact(artifact: ArtifactRecord, label: str) -> None:
    if artifact.public:
        raise ReleaseHarnessError(f"{label} artifact must be private")
    path = validate_safe_relative_path(artifact.path, f"{label} path")
    if not path.startswith("private-logs/"):
        raise ReleaseHarnessError(f"{label} artifact must be under private-logs")


def _read_workspace_artifact(workspace: Path, artifact: ArtifactRecord) -> bytes:
    validate_safe_relative_path(artifact.path, "forecast output path")
    payload = read_release_regular_file(workspace / artifact.path)
    if len(payload) != artifact.size_bytes:
        raise ReleaseHarnessError("release forecast output size does not match")
    if release_bytes_sha256(payload) != artifact.sha256:
        raise ReleaseHarnessError("release forecast output sha256 does not match")
    return payload


def read_release_regular_file(path: Path) -> bytes:
    """Read one immutable single-link file without following any symlink."""

    try:
        return read_single_link_file(path, label="release harness input")
    except ImmutableIOError as exc:
        raise ReleaseHarnessError("release harness input is unavailable") from exc


def write_release_create_only(path: Path, payload: bytes, *, mode: int) -> None:
    try:
        write_file_create_only(path, payload, mode=mode)
    except ImmutableIOError as exc:
        raise ReleaseHarnessError(
            "release harness staging path is unavailable"
        ) from exc


def write_release_json_create_only(path: Path, record: Mapping[str, Any]) -> None:
    """Write one canonical release-runtime record without following links."""

    write_release_create_only(path, release_canonical_bytes(record), mode=0o600)


def _validate_stored_lfb_projection(
    workspace: Path,
    projection: ReleaseHarnessProjection,
) -> None:
    public_path = workspace / RELEASE_HARNESS_LFB_RECORD_NAME
    private_path = workspace / RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME
    if projection.lfb_record is None:
        _require_release_record_absent(public_path, "release LFB record")
        _require_release_record_absent(private_path, "private release LFB record")
        return
    if projection.private_lfb_record is None:
        raise AssertionError("private LFB projection is unavailable")
    if _read_object(public_path, "release LFB record") != projection.lfb_record:
        raise ReleaseHarnessError("stored release LFB record does not match")
    if (
        _read_object(private_path, "private release LFB record")
        != projection.private_lfb_record
    ):
        raise ReleaseHarnessError("stored private release LFB record does not match")


def _validate_or_create_release_record(
    path: Path,
    expected: Mapping[str, Any],
    label: str,
) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        write_release_json_create_only(path, expected)
        return
    except OSError as exc:
        raise ReleaseHarnessError(f"{label} path is unavailable") from exc
    if _read_object(path, label) != expected:
        raise ReleaseHarnessError(f"stored {label} does not match")


def _require_release_record_absent(path: Path, label: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ReleaseHarnessError(f"{label} path is unavailable") from exc
    raise ReleaseHarnessError(f"unscoreable release row must not contain {label}")


def require_release_metadata_str(metadata: Mapping[str, Any], name: str) -> str:
    value = metadata.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ReleaseHarnessError(f"task metadata {name} must be a non-empty string")
    return value


def _required_metadata_bool(metadata: Mapping[str, Any], name: str) -> bool:
    value = metadata.get(name)
    if not isinstance(value, bool):
        raise ReleaseHarnessError(f"task metadata {name} must be a boolean")
    return value


def _validate_release_receipt_content(content: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "receipt_id",
        "release_id",
        "forecast_release_digest",
        "case_id",
        "unit_id",
        "should_score",
        "packet_sha256",
        "prompt_sha256",
        "harness_track",
        "treatment_id",
        "adapter",
        "tools",
        "network_policy",
        "limits",
        "transcript_sha256",
        "result",
    }
    if set(content) != expected:
        raise ReleaseHarnessError("release harness receipt fields are invalid")
    require_schema_version(content, RELEASE_HARNESS_RECEIPT_SCHEMA_VERSION)
    for field_name in ("receipt_id", "release_id", "case_id"):
        require_str(content, field_name)
    unit_id = content.get("unit_id")
    if unit_id is not None and (not isinstance(unit_id, str) or not unit_id.strip()):
        raise ReleaseHarnessError("release receipt unit_id must be null or non-empty")
    if not isinstance(content.get("should_score"), bool):
        raise ReleaseHarnessError("release receipt should_score must be a boolean")
    for field_name in (
        "forecast_release_digest",
        "packet_sha256",
        "prompt_sha256",
        "transcript_sha256",
    ):
        validate_sha256(require_str(content, field_name), field_name)
    track = require_str(content, "harness_track")
    if track not in RELEASE_HARNESS_TRACKS:
        raise ReleaseHarnessError("release receipt harness_track is invalid")

    adapter = require_mapping(content, "adapter")
    if set(adapter) != {"adapter_id", "adapter_version", "model_key"}:
        raise ReleaseHarnessError("release receipt adapter fields are invalid")
    adapter_id = require_str(adapter, "adapter_id")
    adapter_version = require_str(adapter, "adapter_version")
    model_key = require_str(adapter, "model_key")
    treatment_id = require_str(content, "treatment_id")
    if treatment_id != f"{track}:{adapter_id}:{adapter_version}:{model_key}":
        raise ReleaseHarnessError("release receipt treatment_id does not match")

    tools = require_mapping(content, "tools")
    if set(tools) != {"policy", "allowed", "call_count"}:
        raise ReleaseHarnessError("release receipt tools fields are invalid")
    require_str(tools, "policy")
    allowed = require_sequence(tools, "allowed")
    if any(not isinstance(item, str) or not item.strip() for item in allowed):
        raise ReleaseHarnessError("release receipt allowed tools are invalid")
    if len(allowed) != len(set(cast(Sequence[str], allowed))):
        raise ReleaseHarnessError("release receipt allowed tools must be unique")
    _receipt_non_negative_int(tools.get("call_count"), "tools.call_count")

    require_str(content, "network_policy")
    limits = require_mapping(content, "limits")
    if set(limits) != {"timeout_seconds", "pids", "memory", "cpu"}:
        raise ReleaseHarnessError("release receipt limits fields are invalid")
    _receipt_non_negative_int(limits.get("timeout_seconds"), "limits.timeout_seconds")
    pids = limits.get("pids")
    if pids is not None:
        _receipt_non_negative_int(pids, "limits.pids")
    for field_name in ("memory", "cpu"):
        value = limits.get(field_name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ReleaseHarnessError(f"release receipt limits.{field_name} is invalid")

    result = require_mapping(content, "result")
    if set(result) != {
        "run_result_sha256",
        "forecast_output_sha256",
        "parser_output",
    }:
        raise ReleaseHarnessError("release receipt result fields are invalid")
    validate_sha256(require_str(result, "run_result_sha256"), "run_result_sha256")
    validate_sha256(
        require_str(result, "forecast_output_sha256"),
        "forecast_output_sha256",
    )
    parsed_output_from_public_record(require_mapping(result, "parser_output"))


def _receipt_non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReleaseHarnessError(f"release receipt {field_name} is invalid")
    return value


def _authenticated_release_metadata(
    request: RunRequest,
    solver_input_root: Path,
    solver_input_entry: SolverInputEntry,
) -> tuple[str, str, str]:
    packet_sha256, prompt_sha256, forecast_release_digest = _release_task_metadata(
        request
    )
    if solver_input_entry.task_id != request.task.task_id:
        raise ReleaseHarnessError("solver input task does not match request")
    if solver_input_entry.task_sha256 != request.task.task_sha256:
        raise ReleaseHarnessError("solver input packet commitment does not match")
    if solver_input_entry.prompt_sha256 != prompt_sha256:
        raise ReleaseHarnessError("solver input prompt metadata does not match")
    if solver_input_entry.task_record_sha256 != release_record_sha256(
        request.task.to_record()
    ):
        raise ReleaseHarnessError(
            "solver input task metadata commitment does not match"
        )
    prompt = read_release_regular_file(solver_input_root / SOLVER_INPUT_ENTRY_PATH)
    if release_bytes_sha256(prompt) != prompt_sha256:
        raise ReleaseHarnessError("prompt commitment does not match solver input")
    return packet_sha256, prompt_sha256, forecast_release_digest


def _release_task_metadata(request: RunRequest) -> tuple[str, str, str]:
    metadata = request.task.metadata
    packet_sha256 = require_release_metadata_str(metadata, "packet_sha256")
    prompt_sha256 = require_release_metadata_str(metadata, "prompt_sha256")
    forecast_release_digest = require_release_metadata_str(
        metadata,
        "forecast_release_digest",
    )
    validate_sha256(packet_sha256, "packet_sha256")
    validate_sha256(prompt_sha256, "prompt_sha256")
    validate_sha256(forecast_release_digest, "forecast_release_digest")
    validate_sha256(request.task.task_sha256, "task_sha256")
    if packet_sha256.removeprefix("sha256:") != request.task.task_sha256.removeprefix(
        "sha256:"
    ):
        raise ReleaseHarnessError("packet commitment does not match task")
    return packet_sha256, prompt_sha256, forecast_release_digest


def _required_summary_str(summary: Mapping[str, Any], name: str) -> str:
    value = summary.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ReleaseHarnessError(f"result summary {name} must be a non-empty string")
    return value


def _required_string_list(metadata: Mapping[str, Any], name: str) -> tuple[str, ...]:
    values = _optional_string_list(metadata, name)
    if not values:
        raise ReleaseHarnessError(f"task metadata {name} must not be empty")
    return values


def _required_summary_string_list(
    summary: Mapping[str, Any], name: str
) -> tuple[str, ...]:
    if name not in summary:
        raise ReleaseHarnessError(f"result summary {name} must be an array")
    return _optional_string_list(summary, name)


def _optional_string_list(metadata: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = metadata.get(name, ())
    if not isinstance(value, list | tuple):
        raise ReleaseHarnessError(f"task metadata {name} must be an array")
    values = tuple(cast(tuple[object, ...] | list[object], value))
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ReleaseHarnessError(
            f"task metadata {name} must contain non-empty strings"
        )
    typed = cast(tuple[str, ...], values)
    if len(typed) != len(set(typed)):
        raise ReleaseHarnessError(f"task metadata {name} must be unique")
    return typed


def _non_negative_summary_int(summary: Mapping[str, Any], name: str) -> int:
    value = summary.get(name)
    if type(value) is not int or value < 0:
        raise ReleaseHarnessError(f"result summary {name} must be non-negative")
    return value


def _optional_non_negative_summary_int(summary: Mapping[str, Any], name: str) -> int:
    value = summary.get(name, 0)
    if type(value) is not int or value < 0:
        raise ReleaseHarnessError(f"result summary {name} must be non-negative")
    return value


def _optional_non_negative_summary_number(
    summary: Mapping[str, Any], name: str
) -> float:
    value = summary.get(name, 0.0)
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise ReleaseHarnessError(f"result summary {name} must be non-negative")
    return float(value)


def _summary_request_count(summary: Mapping[str, Any]) -> int:
    for field_name in ("provider_request_count", "request_count"):
        if field_name in summary:
            return _non_negative_summary_int(summary, field_name)
    return 1


def _summary_execution_backend(summary: Mapping[str, Any], track: str) -> str:
    value = summary.get("execution_backend")
    if value is None:
        return f"release_{track}"
    if not isinstance(value, str) or not value.strip():
        raise ReleaseHarnessError("result summary execution_backend is invalid")
    return value


def release_canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(record), sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def release_record_sha256(record: Mapping[str, Any]) -> str:
    return release_bytes_sha256(release_canonical_bytes(record))


def release_bytes_sha256(payload: bytes) -> str:
    commitment = RAW_BYTES_PREFIXED_SHA256_V1.commit(
        payload,
        domain=FORECAST_RELEASE_V1,
    )
    return str(commitment.digest)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(read_release_regular_file(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseHarnessError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ReleaseHarnessError(f"{label} must be an object")
    return cast(dict[str, Any], decoded)
