"""Scoring for outcome-blinded multi-harness release runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol, cast

import legalforecast.multiharness.release_task_validation as _release_task_validation
from legalforecast.evals.output_parser import parsed_output_from_public_record
from legalforecast.release.models import ForecastRelease, LabelsRelease

RELEASE_HARNESS_TRACKS = frozenset({"native", "neutral"})


class MultiHarnessRunLike(Protocol):
    """Attributes consumed from a completed multi-harness run."""

    @property
    def selection(self) -> Any: ...

    @property
    def rows(self) -> Sequence[Any]: ...


RELEASE_FAILURE_POLICY_ID = "failure-brier-1.0-v1"


def score_release(
    run: MultiHarnessRunLike,
    forecast_release: ForecastRelease,
    labels_release: LabelsRelease,
    *,
    failure_brier: float = 1.0,
    score_schema_version: str,
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
        _release_task_validation.validate_selected_release_task_metadata(
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
        "schema_version": score_schema_version,
        "failure_policy": {
            "policy_id": RELEASE_FAILURE_POLICY_ID,
            "failure_brier": failure_brier,
            "description": (
                "execution and invalid-output failures receive a fixed Brier penalty"
            ),
        },
        "selection": {
            "coverage_kind": getattr(
                run.selection,
                "coverage_kind",
                "full" if set(selected_unit_ids) == set(units_by_id) else "scoped",
            ),
            "selected_task_ids": list(selected_task_ids),
            "selected_case_ids": sorted(set(selected_case_ids)),
            "selected_unit_ids": list(scoreable_selected_ids),
            "expected_unit_count": len(scoreable_selected_ids),
            "release_scoreable_unit_count": len(expected_scoreable),
            "release_case_count": len(release_case_ids),
            "full_release_selected": set(selected_unit_ids) == set(units_by_id),
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
